"""Collect C1-C8 evidence on a Linux Docker host for a fixed project request."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'labs/e11e12'))
import pipeline
from handoff_a_to_b import make_handoff


def require(condition, message):
    if not condition:
        raise ValueError(message)


def container_path(path):
    return '/course/' + path.resolve().relative_to(ROOT).as_posix()


def host_path(value):
    path = ROOT / value[len('/course/'):] if value.startswith('/course/') else Path(value)
    return path.resolve()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_artifacts(folder, result):
    prefix = 'artifact://' + result['job_id'] + '/'
    for item in result['artifacts']:
        require(item['uri'].startswith(prefix), 'Artifact refers to another task')
        path = (folder / item['uri'][len(prefix):]).resolve()
        require(path.is_relative_to(folder), 'Artifact path leaves task directory')
        require(digest(path) == item['sha256'] and path.stat().st_size == item['bytes'],
                'Artifact hash or size differs: ' + item['uri'])
    return len(result['artifacts'])


def patch_case(spec_path):
    spec = pipeline.read(spec_path)
    project, output = Path(spec['project']), Path(spec['out'])
    _, _, _, options = pipeline.project_profile(spec['request'])
    options['expected_output'] = spec['request'].get('expected_output', '1')
    verdict = pipeline.validate(project, Path(spec['patch']), output, **options)
    print(json.dumps(verdict))
    return 0 if not verdict['accepted'] and verdict['rollback'] and verdict['source_unchanged'] else 1


class ExchangeRun:
    def __init__(self, args):
        self.args = args
        self.output = args.out.resolve()
        require(self.output.is_relative_to(ROOT / 'work') and self.output != ROOT / 'work',
                'Output must be a fresh directory below work/')
        self.output.mkdir(parents=True, exist_ok=False)
        self.request = pipeline.read(args.request)
        self.source = host_path(self.request['repo'])
        require(self.source.is_relative_to(ROOT / 'data'), 'Project must be under data/')
        require(self.request['base'] != self.request['target'], 'Use distinct base and target commits')
        self.a_request = dict(self.request, mode='e11-a')
        self.b_request = None
        self.a_result = None
        self.records = {}
        self.source_unchanged = None
        self.source_before = self.source_state()
        pipeline.save(self.output / 'input.json', self.request)
        pipeline.save(self.output / 'context.json', {
            'scope': args.scope, 'provider': args.provider, 'executor': args.executor,
            'source_url': args.source_url, 'implementation_sha': self.git(ROOT, 'rev-parse', 'HEAD'),
            'implementation_status': self.git(ROOT, 'status', '--porcelain'),
            'project': str(self.source), 'source_before': self.source_before,
            'base': self.request['base'], 'target': self.request['target'],
            'image': args.image, 'api_url': args.api_url,
        })

    def git(self, project, *args):
        return subprocess.check_output(['git', '-C', str(project), *args], text=True).strip()

    def source_state(self):
        return {'head': self.git(self.source, 'rev-parse', 'HEAD'),
                'status': self.git(self.source, 'status', '--porcelain'),
                'makefile_sha256': digest(pipeline.project_directory(self.source, self.request) / 'Makefile')}

    def command(self, name, argv):
        folder = self.output / 'commands'
        folder.mkdir(exist_ok=True)
        started = time.time()
        with (folder / (name + '.stdout.log')).open('w') as stdout, \
             (folder / (name + '.stderr.log')).open('w') as stderr:
            process = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        pipeline.save(folder / (name + '.json'), {
            'argv': argv, 'exit_code': process.returncode,
            'started_at_unix': started, 'ended_at_unix': time.time(),
        })
        return process.returncode

    def job(self, name, request):
        request_path = self.output / 'requests' / (name + '.json')
        pipeline.save(request_path, request)
        folder = self.output / name
        code = self.command(name, [sys.executable, 'run_e11e12.py', 'run',
                                  '--request', str(request_path), '--out', str(folder)])
        result = pipeline.read(folder / 'result.json')
        checked_artifacts(folder, result)
        require((code == 0) == (result['status'] == 'SUCCEEDED'),
                name + ': exit code and result status disagree')
        return result

    def residuals(self, name, result):
        folder = self.output / name
        tokens = [result['job_id'], str(folder), container_path(folder)]
        clients = subprocess.check_output(['ps', '-eo', 'pid,args'], text=True).splitlines()
        matching_clients = [line for line in clients if ('docker build ' in line or 'docker run ' in line)
                            and any(token in line for token in tokens)]
        rows = subprocess.check_output(['docker', 'ps', '--no-trunc', '--format', '{{json .}}'], text=True)
        matching_containers = [json.loads(line) for line in rows.splitlines()
                               if any(token in line for token in tokens)]
        cid = folder / 'draft-build/verify-container-id.txt'
        observation = {'observed_at_unix': time.time(), 'task_tokens': tokens,
                       'docker_clients': matching_clients, 'running_containers': matching_containers,
                       'verify_container_id': cid.read_text().strip() if cid.exists() else None}
        if cid.exists():
            process = subprocess.run(['docker', 'inspect', cid.read_text().strip()],
                                     capture_output=True, text=True)
            observation['verify_container_inspect_exit'] = process.returncode
            if process.returncode == 0:
                state = json.loads(process.stdout)[0]['State']
                observation['verify_container_state'] = state
        pipeline.save(self.output / (name + '-residuals.json'), observation)
        require(not observation.get('verify_container_state', {}).get('Running'),
                'Timed-out verification container is still running')
        require(not matching_clients and not matching_containers, 'Task still has Docker clients or containers')
        return observation

    def c1(self):
        self.a_result = self.job('c1-a', self.a_request)
        require(self.a_result['status'] == 'SUCCEEDED', 'A normal task failed')
        handoff = make_handoff(self.output / 'c1-a/result.json', self.request['target'])
        report_path = self.output / 'handoff/fixed-md.json'
        pipeline.save(report_path, handoff)
        self.b_request = dict(self.request, mode='e11-b', fixed_report=container_path(report_path),
                              fixed_report_sha256=digest(report_path))
        result = self.job('c1-b', self.b_request)
        require(result['status'] == 'SUCCEEDED', 'B normal task failed')
        received = self.output / 'c1-b/fixed-md-input.json'
        require(received.read_bytes() == report_path.read_bytes(), 'B received different report bytes')
        require(pipeline.read(received)['source_report'] == handoff['source_report'], 'A provenance changed')
        recheck = pipeline.read(self.output / 'c1-b/recheck.json')
        require(recheck['commit'] == self.request['target'], 'B recheck targets another commit')
        require(not any(item['type'] == 'MISSING' for item in recheck['data']['findings']),
                'Missing dependencies remain after B repair')
        return {'a_job_id': self.a_result['job_id'], 'b_job_id': result['job_id'],
                'source_report': handoff['source_report'], 'transfer_sha256': digest(report_path)}

    def c2(self):
        require(self.b_request is not None, 'C1 did not produce a handoff request')
        result = self.job('c2-stale', dict(self.b_request, target=self.request['base']))
        require(result.get('error', {}).get('code') == 'STALE_REPORT' and not result['stages'],
                'Old report was not rejected before build')
        return {'job_id': result['job_id'], 'error': result['error']}

    def c3(self):
        require(self.b_request is not None, 'C1 did not produce a handoff request')
        original = self.output / 'handoff/fixed-md.json'
        changed = self.output / 'handoff/changed-fixed-md.json'
        changed.write_bytes(original.read_bytes() + b'\n')
        result = self.job('c3-tampered', dict(self.b_request, fixed_report=container_path(changed)))
        require(result.get('error', {}).get('code') == 'ARTIFACT_HASH_MISMATCH' and not result['stages'],
                'Changed transfer was not rejected before build')
        return {'original_sha256': digest(original), 'changed_sha256': digest(changed),
                'declared_sha256': self.b_request['fixed_report_sha256'], 'error': result['error']}

    def c4(self):
        result = self.job('c4-timeout', dict(self.request, mode='e12', build_timeout=0.01))
        inner = pipeline.read(self.output / 'c4-timeout/draft-build/result.json')
        require(result['status'] in ('FAILED', 'TIMED_OUT') and inner['status'] == 'TIMED_OUT',
                'Short build timeout did not fail with inner TIMED_OUT')
        self.residuals('c4-timeout', result)
        return {'outer_status': result['status'], 'inner_status': inner['status'], 'error': result['error']}

    def c5(self):
        folder = self.output / 'c5-rejected-patch'
        checkout = folder / 'project'
        pipeline.snapshot(self.source, self.request['target'], checkout, folder / 'logs',
                          subdir=pipeline.project_subdir(self.request))
        project = pipeline.project_directory(checkout, self.request)
        makefile = project / 'Makefile'
        before = {'head': self.git(project, 'rev-parse', 'HEAD'), 'makefile_sha256': digest(makefile)}
        lines = makefile.read_text().splitlines(keepends=True)
        recipe = next(index for index, line in enumerate(lines) if line.startswith('\t'))
        changed = list(lines)
        changed[recipe] = '\tfalse\n'
        patch_file = folder / 'wrong.patch'
        patch_file.write_text(''.join(difflib.unified_diff(lines, changed, fromfile='a/Makefile', tofile='b/Makefile')))
        spec = folder / 'spec.json'
        pipeline.save(spec, {'request': self.request, 'project': container_path(project),
                             'patch': container_path(patch_file), 'out': container_path(folder / 'validation')})
        code = self.command('c5-validation', [
            'docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
            '-e', 'HOME=/tmp', '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-v', f'{ROOT}:/course', '-w', '/course', self.args.image,
            'python3', 'labs/e13e14/verify_exchange.py', '--patch-case', container_path(spec),
        ])
        verdict = pipeline.read(folder / 'validation/validation.json')
        after = {'head': self.git(project, 'rev-parse', 'HEAD'), 'makefile_sha256': digest(makefile)}
        pipeline.save(folder / 'source-state.json', {'before': before, 'after': after})
        require(code == 0 and not verdict['accepted'] and verdict['rollback'] and verdict['source_unchanged']
                and before == after and verdict['checks'].get('patch_applies'),
                'Wrong applicable patch was not rejected without changing the source')
        return {'validation': verdict, 'before': before, 'after': after}

    def c6(self):
        folder = self.output / 'c6-secret-log'
        folder.mkdir()
        log = folder / 'probe.log'
        log.write_text('api_key = "' + 'sk-' + 'a' * 24 + '"\n')
        before = digest(log)
        try:
            hit = self.command('c6-hit', [sys.executable, 'labs/e13e14/scan_runtime_logs.py', str(log)])
        finally:
            log.write_text('probe completed\n')
        clean = self.command('c6-clean', [sys.executable, 'labs/e13e14/scan_runtime_logs.py', str(log)])
        outcome = {'hit_exit': hit, 'clean_exit': clean, 'before_sha256': before, 'after_sha256': digest(log)}
        pipeline.save(folder / 'scan-results.json', outcome)
        require(hit == 1 and clean == 0, 'Fake key detection or clean rescan failed')
        return outcome

    def c7(self):
        failed = self.job('c7-failed', dict(self.a_request, base='0' * 40))
        good = self.job('c7-normal', self.a_request)
        require(failed['status'] == 'FAILED' and good['status'] == 'SUCCEEDED', 'Failure isolation task status differs')
        require(failed['job_id'] != good['job_id'] and failed['trace_id'] != good['trace_id'],
                'Failure and success reused task identifiers')
        self.residuals('c7-failed', failed)
        return {'failed_job_id': failed['job_id'], 'successful_job_id': good['job_id'],
                'successful_artifacts_checked': checked_artifacts(self.output / 'c7-normal', good)}

    def c8(self):
        folder = self.output / 'c8-idempotency'
        folder.mkdir()
        requests = []

        def call(name, path, body=None):
            if body is not None:
                pipeline.save(folder / (name + '-request.json'), body)
            payload = json.dumps(body).encode() if body is not None else None
            request = Request(self.args.api_url.rstrip('/') + path, data=payload,
                              headers={'Content-Type': 'application/json'})
            try:
                response = urlopen(request, timeout=30)
            except HTTPError as error:
                response = error
            with response:
                value = json.loads(response.read())
                requests.append({'name': name, 'path': path, 'status': response.status})
                pipeline.save(folder / (name + '-response.json'),
                              {'status': response.status, 'headers': dict(response.headers), 'body': value})
                return response.status, value

        key = 'e13-' + uuid.uuid4().hex
        body = {'idempotency_key': key, 'input': self.a_request}
        try:
            code, first = call('first', '/v1/jobs', body)
            require(code == 202, 'API did not accept the first job')
            code, repeated = call('same-input', '/v1/jobs', body)
            require(code == 202 and first['job_id'] == repeated['job_id'], 'Same input created another job')
            code, conflict = call('changed-input', '/v1/jobs', {
                'idempotency_key': key, 'input': dict(self.a_request, target=self.request['base'])})
            require(code == 409 and conflict.get('error') == 'IDEMPOTENCY_CONFLICT',
                    'Changed input did not return HTTP 409 / IDEMPOTENCY_CONFLICT')
            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                code, state = call('poll', '/v1/jobs/' + first['job_id'])
                require(code == 200 and state['trace_id'] == first['trace_id'], 'Polling changed task identity')
                if state['status'] not in ('QUEUED', 'RUNNING'):
                    break
                time.sleep(1)
            require(state['status'] == 'SUCCEEDED', 'Idempotent A job did not complete successfully')
            return {'job_id': first['job_id'], 'trace_id': first['trace_id'], 'conflict': conflict,
                    'final_state': state}
        finally:
            pipeline.save(folder / 'http-log.json', requests)

    def run(self):
        for number in range(1, 9):
            name = 'C' + str(number)
            try:
                details = getattr(self, 'c' + str(number))()
                self.records[name] = {'status': 'PASS', 'details': details}
            except Exception as error:
                self.records[name] = {'status': 'FAIL', 'error': f'{type(error).__name__}: {error}'}
            pipeline.save(self.output / 'summary.json', self.summary())
            print(name, self.records[name]['status'], flush=True)
        after = self.source_state()
        self.source_unchanged = after == self.source_before
        pipeline.save(self.output / 'source-state.json', {'before': self.source_before, 'after': after})
        pipeline.save(self.output / 'summary.json', self.summary())
        return 0 if self.summary()['all_passed'] else 1

    def summary(self):
        return {'scope': self.args.scope, 'provider': self.args.provider, 'executor': self.args.executor,
                'source_url': self.args.source_url, 'base': self.request['base'], 'target': self.request['target'],
                'cases': self.records, 'source_unchanged': self.source_unchanged,
                'all_passed': self.source_unchanged is True and len(self.records) == 8 and
                all(record['status'] == 'PASS' for record in self.records.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--image', help='Existing E11-E12 teaching image')
    parser.add_argument('--api-url', default='http://127.0.0.1:8080')
    parser.add_argument('--scope', choices=('a09-self-test', 'paired-exchange'), default='a09-self-test')
    parser.add_argument('--provider', default='A09')
    parser.add_argument('--executor', default='A09 / 241250033')
    parser.add_argument('--source-url', default='local A09 project')
    parser.add_argument('--patch-case', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.patch_case:
        return patch_case(args.patch_case)
    if not args.request or not args.out or not args.image:
        parser.error('--request, --out and --image are required')
    if urlsplit(args.api_url).hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('--api-url must point to a loopback endpoint')
    return ExchangeRun(args).run()


if __name__ == '__main__':
    raise SystemExit(main())
