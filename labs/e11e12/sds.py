"""Native single-target adapter for the pinned upstream SDS project."""
import argparse
import json
from pathlib import Path
import subprocess

TARGETS = {"sds-test": "sds.c"}
COMPILER_FLAGS = ("-Wall", "-std=c99", "-pedantic", "-O2", "-DSDS_TEST_MAIN")
BUILD_TARGET = "sds-test"
HEADER = "sdsalloc.h"
EXPECTED_OUTPUT = "46 tests, 46 passed, 0 failed"
SOURCE = "https://github.com/antirez/sds"
BASE_COMMIT = "fb463145c9c245636feb28b5aac0fc897e16f67e"
TARGET_COMMIT = "a9a03bb3304030bb8a93823a9aeb03c157831ba9"
FIX_COMMIT = "9cbfaf54d13bfc17d6dd2e7b88a2bb5f0cd2b03b"
DOCKERFILE_BROKEN = (
    "FROM python:3.13-slim\n"
    "WORKDIR /work\n"
    "COPY sds.c sds.h sdsalloc.h testhelp.h Makefile ./\n"
    "RUN make sds-test\n"
    'CMD ["sh", "-c", "./sds-test > /tmp/sds-tests.log && tail -n 1 /tmp/sds-tests.log"]\n'
)


def write_requests(repo, output):
    from prepare import BASE_IMAGE, CANDIDATE_BASE, INSTALL

    repo = Path(repo).resolve()
    output = Path(output).resolve()
    for revision in (BASE_COMMIT, TARGET_COMMIT, FIX_COMMIT):
        subprocess.run(["git", "rev-parse", "--verify", revision + "^{commit}"], cwd=repo,
                       check=True, capture_output=True, text=True)
    output.mkdir(parents=True, exist_ok=True)
    candidate = output / "candidate.Dockerfile"
    text = DOCKERFILE_BROKEN.replace("FROM " + BASE_IMAGE, "FROM " + CANDIDATE_BASE, 1)
    candidate.write_text(text.replace("RUN make sds-test", INSTALL + "\nRUN make sds-test", 1), encoding="utf-8")
    request = {
        "mode": "e12", "profile": "sds", "repo": str(repo), "base": BASE_COMMIT,
        "target": TARGET_COMMIT, "candidate": str(candidate),
        "expected_output": EXPECTED_OUTPUT, "build_timeout": 600,
    }
    records = {
        "e12.json": request,
        "e11-a.json": dict(request, mode="e11-a"),
        "e11-a-upstream-fix.json": dict(request, mode="e11-a", base=TARGET_COMMIT, target=FIX_COMMIT),
        "dataset.json": {
            "source": SOURCE, "source_type": "external-open-source", "license": "BSD-3-Clause",
            "base_commit": BASE_COMMIT, "target_commit": TARGET_COMMIT, "upstream_fix_commit": FIX_COMMIT,
            "changes": {
                TARGET_COMMIT: "Merge general improvements from Redis; native Makefile still omits sdsalloc.h",
                FIX_COMMIT: "Add the missing sdsalloc.h prerequisite to sds-test",
            },
            "adaptation": "Native sds-test target and upstream compiler flags; detached runtime Dockerfile adapter",
            "expected_missing_dependency": {"target": BUILD_TARGET, "dependency": HEADER},
            "expected_output": EXPECTED_OUTPUT,
            "candidate_source": "Course dependency-install candidate adapted to native SDS build and test commands",
        },
    }
    for name, data in records.items():
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/sds-input"))
    args = parser.parse_args()
    print(write_requests(args.repo, args.out))


if __name__ == "__main__":
    main()
