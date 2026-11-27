"""HTTP handlers for the four E14 roles, using the E11/E12 implementations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'labs/e11e12'))
import pipeline

ROLE = os.environ['E14_ROLE']


def local(value, area='work'):
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT / area):
        raise pipeline.Failure('INVALID_PATH', f'Path must be inside {ROOT / area}')
    return path


def run(data):
    project = local(data['project'])
    out = local(data['out'])
    if out.exists():
        raise pipeline.Failure('OUTPUT_EXISTS', 'Use a fresh role output directory')
    request = data['request']
    targets, scan_options, build_target, validation_options = pipeline.project_profile(request)
    if ROLE == 'draft':
        request = dict(request, candidate=str(local(request['candidate'], 'data')))
        result = pipeline.draft_for(request, project, out)
        return {'status': 'SUCCEEDED', 'result': result,
                'artifact': str(out / 'draft-build/result.json')}
    if ROLE == 'buildchecker':
        result = pipeline.full(project, out, build_target)
        return {'status': 'SUCCEEDED', 'result': result,
                'artifact': str(out / 'findings.json')}
    if ROLE == 'echecker':
        base = local(data['base'])
        old = pipeline.scan(base, **scan_options)
        graph = pipeline.read(local(data['baseline_graph']))
        projected = {
            target: sorted({edge['dependency'] for edge in graph if edge['target'] == target})
            for target in targets
        }
        if old['actual'] != projected:
            raise pipeline.Failure('GRAPH_MISMATCH', 'BuildChecker baseline differs from GCC observations')
        old['actual'] = projected
        current = pipeline.scan(project, old, **scan_options)
        reference = pipeline.read(local(data['target_findings']))
        if reference['status'] != 'SUCCEEDED' or pipeline.normalized(
                current['findings'], targets) != pipeline.normalized(reference['findings'], targets):
            raise pipeline.Failure('FINDINGS_MISMATCH', 'Incremental and full target findings differ')
        if current['commit'] != data['target_commit']:
            raise pipeline.Failure('STALE_REPORT', 'Incremental report belongs to another target')
        pipeline.save(out / 'baseline-cache.json', old)
        envelope = {
            'schema_version': pipeline.SCHEMA, 'kind': 'incremental-check',
            'status': 'SUCCEEDED', 'commit': data['target_commit'],
            'job_id': data['job_id'], 'trace_id': data['trace_id'], 'data': current,
        }
        report = out / 'incremental-check.json'
        pipeline.save(report, envelope)
        return {'status': 'SUCCEEDED', 'report': str(report),
                'sha256': pipeline.artifact(report, out, data['job_id'])['sha256']}
    if ROLE == 'mdfixer':
        report = local(data['report'])
        envelope = pipeline.load_artifact(report, data['report_sha256'])
        current = pipeline.report_data(envelope, data['target_commit'], 'incremental-check')
        if (envelope['job_id'], envelope['trace_id']) != (data['job_id'], data['trace_id']):
            raise pipeline.Failure('TASK_MISMATCH', 'Report belongs to another task')
        diff, edits = pipeline.patch(project, current)
        details = {'edits': edits, 'input_report': data['input_report']}
        if not diff:
            pipeline.save(out / 'repair-plan.json', edits)
            return {'status': 'SUCCEEDED', **details,
                    'validation': {'accepted': True, 'action': 'NO_CHANGES'}}
        candidate = out / 'candidate.patch'
        candidate.parent.mkdir(parents=True)
        candidate.write_text(diff, encoding='utf-8')
        pipeline.save(out / 'repair-plan.json', edits)
        validation_options['expected_output'] = request.get('expected_output', '1')
        verdict = pipeline.validate(project, candidate, out / 'validation', **validation_options)
        if not verdict['accepted']:
            raise pipeline.Failure('REPAIR_REJECTED', 'Inspect repair-work/validation/validation.json')
        return {'status': 'SUCCEEDED', **details, 'patch': str(candidate),
                'sha256': pipeline.artifact(candidate, out, data['job_id'])['sha256'],
                'validation': verdict}
    raise pipeline.Failure('UNKNOWN_ROLE', f'Unknown role {ROLE}')


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data):
        body = (json.dumps(data, ensure_ascii=False) + '\n').encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            self.reply(200, {'status': 'ok', 'role': ROLE})
        else:
            self.reply(404, {'error': 'NOT_FOUND'})

    def do_POST(self):
        if self.path != '/v1/run':
            self.reply(404, {'error': 'NOT_FOUND'})
            return
        start = time.monotonic()
        data = {}
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 100000:
                raise pipeline.Failure('INVALID_REQUEST', 'Expected a JSON request of at most 100000 bytes')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise pipeline.Failure('INVALID_REQUEST', 'Expected a JSON object')
            result = run(data)
            code = 200
        except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            result = {}
            pipeline.mark_failure(result, exc)
            result['role'] = ROLE
            code = 422
        print(json.dumps({
            'role': ROLE, 'job_id': data.get('job_id') if isinstance(data, dict) else None,
            'trace_id': data.get('trace_id') if isinstance(data, dict) else None,
            'stage': data.get('stage') if isinstance(data, dict) else None,
            'status': result['status'], 'error_code': result.get('error', {}).get('code'),
            'elapsed_ms': round((time.monotonic() - start) * 1000),
        }), flush=True)
        self.reply(code, result)


if __name__ == '__main__':
    if ROLE not in {'draft', 'buildchecker', 'echecker', 'mdfixer'}:
        raise SystemExit('Invalid E14_ROLE')
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
