#!/usr/bin/env bash
# GitHub 只负责调度；本脚本在 A 组 60.204.240.40 执行所有实验检查。
set -euo pipefail
mkdir -p work/ci
exec > >(tee work/ci/server-console.log) 2>&1
git rev-parse HEAD > work/ci/commit.txt
python3 - <<'PY'
import json, os, platform
from pathlib import Path
Path('work/ci/host.json').write_text(json.dumps({
    'hostname': platform.node(), 'platform': platform.platform(),
    'server': '60.204.240.40', 'repository': 'Viyangle/devops-2026-a',
    'run_id': os.environ['E7_RUN_ID'], 'execution': 'SSH on A-group server',
}, ensure_ascii=False, indent=2) + '\n')
PY
python3 scripts/doctor.py --out work/ci/env.json | tee work/ci/doctor.log
docker version > work/ci/docker-version.txt
python3 -m compileall -q services/buildchecker/buildchecker scripts tests/e7
python3 -m unittest discover -s tests/e7 -v 2>&1 | tee work/ci/oracle-tests.log
python3 scripts/secret_scan.py . --history | tee work/ci/source-scan.log
IMAGE=e7-buildchecker:group-ci
docker build --progress=plain -f services/buildchecker/Dockerfile -t "$IMAGE" . 2>&1 | tee work/ci/build.log
docker image inspect "$IMAGE" > work/ci/service-image-inspect.json
python3 scripts/secret_scan.py . --image "$IMAGE" | tee work/ci/image-scan.log
args=()
if [[ "${FAIL_DEMO:-false}" == true ]]; then
    args+=(--inject-bad-oracle)
fi
python3 scripts/run_e7_a_gate.py --image "$IMAGE" --out work/ci/gate "${args[@]}" 2>&1 | tee work/ci/gate-console.log
