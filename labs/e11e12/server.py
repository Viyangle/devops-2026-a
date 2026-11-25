"""Single-worker asynchronous classroom job API, bound to loopback by default."""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import uuid
from urllib.parse import unquote

from pipeline import MODES, ROOT, SCHEMA, execute, save


class RequestError(ValueError):
    def __init__(self, code, status=400):
        self.status = status
        super().__init__(code)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.jobs = {}
        self.keys = {}
        for path in self.root.glob('job-*/state.json'):
            state = json.loads(path.read_text())
            if state['status'] in ('QUEUED', 'RUNNING'):
                state.update(status='FAILED', error={
                    'code': 'SERVER_RESTARTED',
                    'message': 'Resubmit with a new key',
                })
                save(path, state)
            self.jobs[state['job_id']] = state
            self.keys[state['idempotency_key']] = (
                state['request_hash'], state['job_id'],
            )

    def get(self, job_id):
        with self.lock:
            state = self.jobs.get(job_id)
            return copy.deepcopy(state) if state is not None else None

    def source_report(self, reference):
        if not isinstance(reference, dict):
            raise RequestError('input_report requires uri and sha256')
        uri = reference.get('uri')
        digest = reference.get('sha256')
        match = re.fullmatch(
            r'artifact://(job-[0-9a-f]{32})/incremental-check\.json',
            uri if isinstance(uri, str) else '',
        )
        if not match or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise RequestError('INVALID_REPORT_REFERENCE')
        state = self.jobs.get(match[1])
        if state is None:
            raise RequestError('UPSTREAM_NOT_FOUND')
        if state['status'] in ('QUEUED', 'RUNNING'):
            raise RequestError('UPSTREAM_NOT_READY', 409)
        if state['status'] != 'SUCCEEDED':
            raise RequestError('UPSTREAM_FAILED')
        folder = self.root / match[1] / 'evidence'
        try:
            request = json.loads((folder / 'request.json').read_text())
            result = json.loads((folder / 'result.json').read_text())
        except (OSError, ValueError) as exc:
            raise RequestError('UPSTREAM_REPORT_UNAVAILABLE') from exc
        if request.get('mode') != 'e11-a' or result.get('status') != 'SUCCEEDED':
            raise RequestError('INVALID_REPORT_SOURCE')
        stage_reference = next((stage['artifact'] for stage in result['stages']
                                if stage['name'] == 'incremental-check'), None)
        if stage_reference is None or stage_reference['uri'] != uri:
            raise RequestError('INVALID_REPORT_REFERENCE')
        if stage_reference['sha256'] != digest:
            raise RequestError('ARTIFACT_HASH_MISMATCH')
        path = folder / 'incremental-check.json'
        if not path.is_file():
            raise RequestError('UPSTREAM_REPORT_UNAVAILABLE')
        return path

    def submit(self, request, key):
        if not isinstance(request, dict):
            raise ValueError('input must be a JSON object')
        if not isinstance(key, str) or not key or len(key) > 128:
            raise ValueError('idempotency_key required, max 128 characters')
        if request.get('mode') not in MODES:
            raise ValueError('Unknown mode')
        for field in ('repo', 'candidate', 'fixed_report'):
            if field in request:
                path = Path(request[field]).resolve()
                if not path.is_relative_to((ROOT / 'data').resolve()):
                    raise ValueError(field + ' must be under /course/data')
        if not all(request.get(field) for field in ('repo', 'base', 'target')):
            raise ValueError('repo/base/target required')
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with self.lock:
            if key in self.keys:
                old, job_id = self.keys[key]
                if old != digest:
                    raise RequestError('IDEMPOTENCY_CONFLICT', 409)
                return copy.deepcopy(self.jobs[job_id])
            source = self.source_report(request.get('input_report')) if request['mode'] == 'e12-repair' else None
            job_id = 'job-' + uuid.uuid4().hex
            state = {
                'schema_version': SCHEMA,
                'job_id': job_id,
                'trace_id': 'trace-' + uuid.uuid4().hex,
                'status': 'QUEUED',
                'idempotency_key': key,
                'request_hash': digest,
            }
            save(self.root / job_id / 'state.json', state)
            self.jobs[job_id] = state
            self.keys[key] = (digest, job_id)
            self.pool.submit(self.work, job_id, copy.deepcopy(request), source)
            return copy.deepcopy(state)

    def work(self, job_id, request, source=None):
        with self.lock:
            state = self.jobs[job_id]
            state['status'] = 'RUNNING'
            trace_id = state['trace_id']
            save(self.root / job_id / 'state.json', state)
        folder = self.root / job_id / 'evidence'
        options = {'trace_id': trace_id}
        if source is not None:
            options['source_report'] = source
        try:
            result = execute(request, folder, job_id, **options)
        except Exception as exc:
            result = {
                'schema_version': SCHEMA,
                'job_id': job_id,
                'trace_id': trace_id,
                'status': 'FAILED',
                'error': {'code': 'WORKER_FAILED', 'message': str(exc)},
            }
            save(folder / 'result.json', result)
        with self.lock:
            state.update({field: result[field] for field in ('status', 'error') if field in result})
            save(self.root / job_id / 'state.json', state)


def create_server(host='127.0.0.1', port=8080, store=None):
    store = store if store is not None else Store(ROOT / 'work/api-jobs')

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, obj):
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != '/v1/jobs':
                return self.reply(404, {'error': 'NOT_FOUND'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536:
                    raise ValueError('Request size must be 1..65536')
                body = json.loads(self.rfile.read(size))
                state = store.submit(body['input'], body['idempotency_key'])
                self.reply(202, state)
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(getattr(exc, 'status', 400), {'error': str(exc)})

        def do_GET(self):
            if self.path == '/health':
                return self.reply(200, {'status': 'ok', 'schema_version': SCHEMA})
            parts = self.path.split('?')[0].strip('/').split('/')
            if len(parts) < 3 or parts[:2] != ['v1', 'jobs']:
                return self.reply(404, {'error': 'NOT_FOUND'})
            job_id = parts[2]
            state = store.get(job_id)
            if state is None:
                return self.reply(404, {'error': 'NOT_FOUND'})
            folder = store.root / job_id / 'evidence'
            if len(parts) == 3:
                return self.reply(200, state)
            if parts[3:] == ['artifacts']:
                if state['status'] in ('QUEUED', 'RUNNING') or not (folder / 'result.json').exists():
                    return self.reply(409, {'error': 'RESULT_NOT_READY'})
                return self.reply(200, json.loads((folder / 'result.json').read_text()))
            if len(parts) >= 5 and parts[3] == 'files':
                name = unquote('/'.join(parts[4:]))
                path = (folder / name).resolve()
                if not path.is_relative_to(folder.resolve()) or '.git' in path.parts or not path.is_file():
                    return self.reply(404, {'error': 'NOT_FOUND'})
                data = path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('X-Content-SHA256', hashlib.sha256(data).hexdigest())
                self.end_headers()
                self.wfile.write(data)
                return
            self.reply(404, {'error': 'NOT_FOUND'})

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.store = store
    return httpd


def serve(host='127.0.0.1', port=8080, directory=ROOT / 'work/api-jobs'):
    httpd = create_server(host, port, Store(directory))
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        httpd.store.pool.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--store', type=Path, default=ROOT / 'work/api-jobs')
    arguments = parser.parse_args()
    serve(arguments.host, arguments.port, arguments.store)
