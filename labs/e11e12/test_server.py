import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import pipeline
import server


class JobApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = server.Store(self.root / 'jobs')
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.store.pool.shutdown)

    def request(self, mode='e11-a'):
        return {
            'mode': mode,
            'repo': str(server.ROOT / 'data/project'),
            'base': 'a' * 40,
            'target': 'b' * 40,
            'candidate': str(server.ROOT / 'data/candidate.Dockerfile'),
        }

    def complete(self, request, folder, job_id, **options):
        pipeline.save(folder / 'request.json', request)
        report = {
            'schema_version': 'e11e12-1',
            'job_id': job_id,
            'trace_id': options['trace_id'],
            'kind': 'incremental-check',
            'commit': request['target'],
            'status': 'SUCCEEDED',
            'data': {'findings': []},
        }
        pipeline.save(folder / 'incremental-check.json', report)
        reference = pipeline.artifact(folder / 'incremental-check.json', folder, job_id)
        result = {
            'schema_version': 'e11e12-1',
            'job_id': job_id,
            'trace_id': options['trace_id'],
            'status': 'SUCCEEDED',
            'stages': [{'name': 'incremental-check', 'artifact': reference}],
            'artifacts': [reference],
        }
        pipeline.save(folder / 'result.json', result)
        return result

    def completed_source(self, mode='e11-a'):
        with patch.object(server, 'execute', side_effect=self.complete):
            state = self.store.submit(self.request(mode), 'source')
            self.store.pool.submit(lambda: None).result(timeout=5)
        folder = self.store.root / state['job_id'] / 'evidence'
        result = json.loads((folder / 'result.json').read_text())
        return state, result['stages'][0]['artifact']

    def test_trace_id_is_available_while_queued_and_stays_the_same(self):
        started = threading.Event()
        finish = threading.Event()

        def execute(request, folder, job_id, **options):
            started.set()
            self.assertTrue(finish.wait(5))
            return self.complete(request, folder, job_id, **options)

        with patch.object(server, 'execute', side_effect=execute):
            queued = self.store.submit(self.request(), 'trace')
            self.assertEqual(queued['status'], 'QUEUED')
            self.assertTrue(queued['trace_id'].startswith('trace-'))
            try:
                self.assertTrue(started.wait(5))
                running = self.store.get(queued['job_id'])
                self.assertEqual(running['status'], 'RUNNING')
                self.assertEqual(running['trace_id'], queued['trace_id'])
            finally:
                finish.set()
            self.store.pool.submit(lambda: None).result(timeout=5)
        complete = self.store.get(queued['job_id'])
        self.assertEqual(complete['status'], 'SUCCEEDED')
        self.assertEqual(complete['trace_id'], queued['trace_id'])
        report = json.loads((self.store.root / queued['job_id'] / 'evidence/incremental-check.json').read_text())
        self.assertEqual(report['trace_id'], queued['trace_id'])

    def test_concurrent_same_key_enqueues_one_job(self):
        with patch.object(self.store.pool, 'submit') as dispatch:
            with ThreadPoolExecutor(max_workers=8) as clients:
                responses = list(clients.map(lambda _: self.store.submit(self.request(), 'concurrent'), range(16)))
        self.assertEqual(len({response['job_id'] for response in responses}), 1)
        self.assertEqual(len({response['trace_id'] for response in responses}), 1)
        self.assertEqual(dispatch.call_count, 1)
        responses[0]['status'] = 'changed by client'
        self.assertEqual(self.store.get(responses[0]['job_id'])['status'], 'QUEUED')

    def test_repair_consumes_completed_a_report_by_exact_uri(self):
        source, reference = self.completed_source()
        request = dict(self.request('e12-repair'), input_report=reference)
        with patch.object(server, 'execute', side_effect=self.complete) as execute:
            queued = self.store.submit(request, 'repair')
            self.store.pool.submit(lambda: None).result(timeout=5)
        self.assertEqual(self.store.get(queued['job_id'])['status'], 'SUCCEEDED')
        options = execute.call_args.kwargs
        self.assertEqual(options['source_report'], self.store.root / source['job_id'] / 'evidence/incremental-check.json')
        self.assertEqual(options['trace_id'], queued['trace_id'])
        self.assertNotEqual(queued['trace_id'], source['trace_id'])
        self.assertEqual(execute.call_args.args[0]['input_report']['sha256'], reference['sha256'])

    def test_repair_rejects_pending_or_wrong_source_without_creating_job(self):
        with patch.object(self.store.pool, 'submit'):
            source = self.store.submit(self.request(), 'pending')
        reference = {'uri': f"artifact://{source['job_id']}/incremental-check.json", 'sha256': 'a' * 64}
        with self.assertRaisesRegex(server.RequestError, 'UPSTREAM_NOT_READY') as raised:
            self.store.submit(dict(self.request('e12-repair'), input_report=reference), 'repair')
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(len(self.store.jobs), 1)
        with self.store.lock:
            self.store.jobs[source['job_id']]['status'] = 'FAILED'
        with self.assertRaisesRegex(server.RequestError, 'UPSTREAM_FAILED'):
            self.store.submit(dict(self.request('e12-repair'), input_report=reference), 'repair')
        for uri in (f"artifact://{source['job_id']}/../incremental-check.json",
                    f"artifact://{source['job_id']}/full-check.json"):
            with self.subTest(uri=uri), self.assertRaisesRegex(server.RequestError, 'INVALID_REPORT_REFERENCE'):
                self.store.submit(dict(self.request('e12-repair'), input_report=dict(reference, uri=uri)), 'repair')

    def test_completed_e12_job_cannot_be_used_as_a_report_source(self):
        _, reference = self.completed_source('e12')
        with self.assertRaisesRegex(server.RequestError, 'INVALID_REPORT_SOURCE'):
            self.store.submit(dict(self.request('e12-repair'), input_report=reference), 'repair')

    def test_restart_preserves_completed_job_and_marks_pending_job_failed(self):
        source, reference = self.completed_source()
        with patch.object(self.store.pool, 'submit'):
            pending = self.store.submit(self.request(), 'pending')
        restarted = server.Store(self.store.root)
        self.addCleanup(restarted.pool.shutdown)
        self.assertEqual(restarted.get(source['job_id'])['status'], 'SUCCEEDED')
        self.assertEqual(restarted.get(source['job_id'])['trace_id'], source['trace_id'])
        failed = restarted.get(pending['job_id'])
        self.assertEqual(failed['status'], 'FAILED')
        self.assertEqual(failed['error']['code'], 'SERVER_RESTARTED')
        self.assertEqual(failed['trace_id'], pending['trace_id'])
        failed['error']['code'] = 'changed by client'
        self.assertEqual(restarted.get(pending['job_id'])['error']['code'], 'SERVER_RESTARTED')
        with patch.object(restarted.pool, 'submit') as dispatch:
            duplicate = restarted.submit(self.request(), 'pending')
            self.assertEqual(duplicate['job_id'], pending['job_id'])
            self.assertEqual(duplicate['status'], 'FAILED')
            dispatch.assert_not_called()
            repair = restarted.submit(dict(self.request('e12-repair'), input_report=reference), 'repair-after-restart')
            self.assertEqual(repair['status'], 'QUEUED')

    def test_unexpected_worker_failure_has_queryable_result(self):
        with patch.object(server, 'execute', side_effect=RuntimeError('test worker error')):
            queued = self.store.submit(self.request(), 'failure')
            self.store.pool.submit(lambda: None).result(timeout=5)
        state = self.store.get(queued['job_id'])
        result = json.loads((self.store.root / queued['job_id'] / 'evidence/result.json').read_text())
        self.assertEqual(state['status'], 'FAILED')
        self.assertEqual(result['error']['code'], 'WORKER_FAILED')
        self.assertEqual(result['trace_id'], queued['trace_id'])

    def test_http_pending_result_download_hash_idempotency_and_restart(self):
        source, reference = self.completed_source()
        restarted = server.Store(self.store.root)
        self.addCleanup(restarted.pool.shutdown)
        httpd = server.create_server('127.0.0.1', 0, restarted)
        thread = threading.Thread(target=httpd.serve_forever)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f'http://127.0.0.1:{httpd.server_address[1]}'

        def call(path, body=None):
            payload = json.dumps(body).encode() if body is not None else None
            request = Request(base + path, data=payload, headers={'Content-Type': 'application/json'})
            try:
                response = urlopen(request, timeout=5)
            except HTTPError as error:
                response = error
            with response:
                return response.status, dict(response.headers), response.read()

        code, _, data = call(f"/v1/jobs/{source['job_id']}")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)['trace_id'], source['trace_id'])
        code, _, data = call(f"/v1/jobs/{source['job_id']}/artifacts")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)['status'], 'SUCCEEDED')
        code, headers, data = call(f"/v1/jobs/{source['job_id']}/files/incremental-check.json")
        self.assertEqual(code, 200)
        self.assertEqual(hashlib.sha256(data).hexdigest(), reference['sha256'])
        self.assertEqual(headers['X-Content-SHA256'], reference['sha256'])
        for path in ('%2e%2e/state.json', '.git/config'):
            self.assertEqual(call(f"/v1/jobs/{source['job_id']}/files/{path}")[0], 404)
        with patch.object(restarted.pool, 'submit'):
            body = {'idempotency_key': 'http-repair', 'input': dict(self.request('e12-repair'), input_report=reference)}
            code, _, data = call('/v1/jobs', body)
            self.assertEqual(code, 202)
            queued = json.loads(data)
            self.assertEqual(queued['status'], 'QUEUED')
            self.assertTrue(queued['trace_id'])
            self.assertEqual(json.loads(call('/v1/jobs', body)[2])['job_id'], queued['job_id'])
            self.assertEqual(call(f"/v1/jobs/{queued['job_id']}/artifacts")[0], 409)
            changed = {'idempotency_key': body['idempotency_key'], 'input': dict(body['input'], target='c' * 40)}
            code, _, data = call('/v1/jobs', changed)
            self.assertEqual(code, 409)
            self.assertEqual(json.loads(data)['error'], 'IDEMPOTENCY_CONFLICT')


if __name__ == '__main__':
    unittest.main()
