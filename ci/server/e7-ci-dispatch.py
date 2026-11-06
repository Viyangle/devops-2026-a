#!/usr/bin/env python3
"""Install as root-owned /usr/local/libexec/e7-ci-dispatch for the e7ci SSH key."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path('/var/lib/e7-a-ci')
match = re.fullmatch(r'(run|fetch) ([0-9]+-[0-9]+) ([0-9a-f]{40})(?: (true|false))?',
                     os.environ.get('SSH_ORIGINAL_COMMAND', ''))
if not match:
    sys.exit('Expected run RUN-ATTEMPT SHA true|false or fetch RUN-ATTEMPT SHA')
action, run_id, sha, fail_demo = match.groups()
if (action == 'run') != (fail_demo is not None):
    sys.exit('run requires fail_demo; fetch does not accept it')
run = ROOT / 'runs' / run_id / sha
repo = run / 'repository'
if action == 'fetch':
    if not (repo / 'work/ci/exit-code.json').is_file():
        sys.exit('This run has not finished; its evidence is still being written')
    sys.exit(subprocess.call(['tar', '-czf', '-', '-C', str(repo), 'work/ci']))

run.mkdir(parents=True, exist_ok=False)
evidence = repo / 'work/ci'
evidence.mkdir(parents=True)
with (run / 'source.bundle').open('wb') as bundle:
    shutil.copyfileobj(sys.stdin.buffer, bundle)

code = 1
try:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                       timeout=120).strip()
    git('init', '-q')
    git('fetch', '-q', str(run / 'source.bundle'), '+refs/*:refs/source/*')
    if git('rev-parse', 'refs/source/heads/e7-ci') != sha:
        raise ValueError('Bundle revision does not match the triggering SHA')
    git('checkout', '-q', '--detach', sha)
    git('config', 'user.name', '241250033')
    git('config', 'user.email', '52848497+mcjiansheng@users.noreply.github.com')
    env = dict(os.environ, E7_RUN_ID=run_id, FAIL_DEMO=fail_demo)
    # timeout covers both lock waiting and execution; flock passes its lock to the child.
    code = subprocess.call(['timeout', '--signal=TERM', '--kill-after=30', '25m',
                            'flock', str(ROOT / 'runs' / '.lock'),
                            'bash', 'scripts/run_e7_server_ci.sh'], cwd=repo, env=env)
except Exception as error:
    (evidence / 'dispatch-error.txt').write_text(str(error) + '\n')
    print(error, file=sys.stderr)
finally:
    (evidence / 'exit-code.json').write_text(json.dumps({'exit_code': code, 'sha': sha}) + '\n')
sys.exit(code)
