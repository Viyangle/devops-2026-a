"""Run a fixed E12 request through the four E14 HTTP services."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'labs/e11e12'))
import pipeline

PORTS = {
    role: int(os.environ.get(f'E14_{role.upper()}_PORT', port))
    for role, port in {'buildchecker': 18081, 'echecker': 18082,
                       'draft': 18083, 'mdfixer': 18084}.items()
}


def container_path(path):
    return '/course/' + path.resolve().relative_to(ROOT.resolve()).as_posix()


def host_path(value):
    if not isinstance(value, str) or not value.startswith('/course/'):
        raise pipeline.Failure('INVALID_PATH', 'Expected a /course/ path')
    path = (ROOT / value[len('/course/'):]).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise pipeline.Failure('INVALID_PATH', 'Path escapes repository')
    return path


def call(role, payload, evidence):
    request = urllib.request.Request(
        f'http://127.0.0.1:{PORTS[role]}/v1/run', data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        result = json.loads(exc.read())
        pipeline.save(evidence, result)
        error = result.get('error', {})
        raise pipeline.Failure(error.get('code', 'SERVICE_FAILED'),
                               f'{role}: {error.get("message", result)}',
                               result.get('status', 'FAILED')) from exc
    pipeline.save(evidence, result)
    if result['status'] != 'SUCCEEDED':
        raise pipeline.Failure('SERVICE_FAILED', f'{role} did not succeed')
    return result


def execute(request, out):
    out = out.resolve()
    if out.exists():
        raise pipeline.Failure('OUTPUT_EXISTS', 'Use a new output directory')
    if out == ROOT / 'work' or not out.is_relative_to((ROOT / 'work').resolve()):
        raise pipeline.Failure('INVALID_PATH', 'Output must be below work/')
    out.mkdir(parents=True)
    result = {
        'schema_version': pipeline.SCHEMA, 'runtime': 'e14-four-services',
        'job_id': 'job-' + uuid.uuid4().hex, 'trace_id': 'trace-' + uuid.uuid4().hex,
        'status': 'RUNNING', 'stages': [],
    }
    pipeline.save(out / 'request.json', request)

    def payload(project, folder, **extra):
        return {'project': container_path(project), 'out': container_path(folder),
                'job_id': result['job_id'], 'trace_id': result['trace_id'],
                'request': request, **extra}

    try:
        repo = host_path(request['repo'])
        candidate = host_path(request['candidate'])
        if not repo.is_relative_to(ROOT / 'data') or not candidate.is_relative_to(ROOT / 'data'):
            raise pipeline.Failure('INVALID_PATH', 'Input project and candidate must be in data/')
        base, target = out / 'base-project', out / 'target-project'
        subdir = pipeline.project_subdir(request)
        for revision, project in (('base', base), ('target', target)):
            if not re.fullmatch(r'[0-9a-f]{40}', request[revision]):
                raise pipeline.Failure('INVALID_REQUEST', 'Use complete Git commit SHAs')
            result[revision + '_commit'] = pipeline.snapshot(repo, request[revision], project, out / 'logs',
                                                             subdir=subdir)
            pipeline.validate_project(pipeline.project_directory(project, request), request)
        base = pipeline.project_directory(base, request)
        target = pipeline.project_directory(target, request)
        commit = result['target_commit']
        drafted = call('draft', payload(target, out / 'draft-work', stage='draft'), out / 'draft-response.json')
        pipeline.stage(out, result, 'draft', commit, drafted['result'])

        baseline = call('buildchecker', payload(base, out / 'baseline-full', stage='full-check'), out / 'baseline-response.json')
        pipeline.stage(out, result, 'full-check', result['base_commit'], baseline['result'],
                       ('baseline-full/actual-graph.json', 'baseline-full/findings.json'))
        call('buildchecker', payload(target, out / 'target-full', stage='target-full'), out / 'target-response.json')
        increment = call('echecker', payload(
            target, out / 'incremental', stage='incremental-check', base=container_path(base),
            baseline_graph=container_path(out / 'baseline-full/actual-graph.json'),
            target_findings=container_path(out / 'target-full/findings.json'), target_commit=commit),
            out / 'incremental-response.json')
        report = host_path(increment['report'])
        data = pipeline.verified_bytes(report, increment['sha256'])
        pipeline.report_data(json.loads(data), commit, 'incremental-check')
        current_report = out / 'incremental-check.json'
        current_report.write_bytes(data)
        reference = pipeline.artifact(current_report, out, result['job_id'])
        result['stages'].append({'name': 'incremental-check', 'artifact': reference})

        repair = call('mdfixer', payload(
            target, out / 'repair-work', stage='repair', report=container_path(current_report),
            report_sha256=reference['sha256'], input_report=reference, target_commit=commit),
            out / 'repair-response.json')
        pipeline.stage(out, result, 'repair', commit, repair,
                       ('repair-work/candidate.patch',) if 'patch' in repair else ())
        final = call('buildchecker', payload(target, out / 'final-full', stage='recheck'), out / 'recheck-response.json')
        findings = final['result']['findings']
        if any(item['type'] == 'MISSING' for item in findings):
            raise pipeline.Failure('RECHECK_FAILED', 'Missing dependencies remain after repair')
        pipeline.stage(out, result, 'recheck', commit,
                       {'validation': repair['validation'], 'findings': findings},
                       ('final-full/findings.json',))
        result['status'] = 'SUCCEEDED'
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        pipeline.mark_failure(result, exc)
    result['artifacts'] = [
        pipeline.artifact(path, out, result['job_id']) for path in sorted(out.rglob('*'))
        if path.is_file() and '.git' not in path.relative_to(out).parts and not path.is_symlink()
    ]
    pipeline.save(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = execute(pipeline.read(args.request), args.out)
    print(json.dumps({'status': result['status'], 'job_id': result['job_id'],
                      'trace_id': result['trace_id'], 'stages': [x['name'] for x in result['stages']],
                      'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
