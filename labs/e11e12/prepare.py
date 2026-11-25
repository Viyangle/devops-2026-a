"""Generate the reproducible classroom requests in a fresh workspace."""
from pipeline import ROOT, save
from lab import commit, fixture, scan

BASE_IMAGE = "python:3.13-slim"
CANDIDATE_BASE = BASE_IMAGE + "@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f"
INSTALL = "RUN apt-get update && apt-get install -y --no-install-recommends build-essential git strace && rm -rf /var/lib/apt/lists/*"


def write_dockerfiles(project, candidate, inputs):
    broken = (
        f"FROM {BASE_IMAGE}\nWORKDIR /work\nCOPY {' '.join(inputs)} ./\n"
        'RUN make app\nCMD ["./app"]\n'
    )
    (project / "Dockerfile.broken").write_text(broken, encoding="utf-8")
    repaired = broken.replace(f"FROM {BASE_IMAGE}", f"FROM {CANDIDATE_BASE}", 1)
    candidate.write_text(repaired.replace("RUN make app", f"{INSTALL}\nRUN make app", 1), encoding="utf-8")


def main():
    root = ROOT / "data/integration-sample"
    if root.exists():
        raise SystemExit("data/integration-sample already exists; preserve it and choose a new workspace")
    project = root / "repo"
    fixture(project)
    candidate = root / "candidate.Dockerfile"
    write_dockerfiles(project, candidate, ("main.c", "helper.c", "config.h", "extra.h", "unused.h", "Makefile"))
    base = commit(project, "integration C0")
    main_c = project / "main.c"
    main_c.write_text('#include "extra.h"\n' + main_c.read_text())
    target = commit(project, "integration C1 add project include")
    fixed = root / "fixed-md.json"
    save(fixed, {"schema_version": "e11e12-1", "kind": "fixed-md", "status": "SUCCEEDED",
                 "commit": target, "data": scan(project)})
    (project / "helper.c").write_text("int helper(void){return 0+0;}\n")
    body_commit = commit(project, "integration C2 change helper body")
    request = {"repo": str(project), "base": base, "target": target,
               "candidate": str(candidate), "expected_output": "1", "build_timeout": 600}
    for mode in ("e11-a", "e11-b", "e12"):
        save(root / f"{mode}.json", dict(request, mode=mode, **(
            {"fixed_report": str(fixed)} if mode == "e11-b" else {}
        )))
    save(root / "e11-a-reuse.json", dict(request, mode="e11-a", base=target, target=body_commit))
    save(root / "stale-report.json", dict(request, mode="e11-b", target=body_commit, fixed_report=str(fixed)))
    save(root / "dataset.json", {
        "source": "course-generated", "base_commit": base, "target_commit": target,
        "body_commit": body_commit, "candidate_source": "course Dockerfile with build and trace tools",
    })
    print(root)


if __name__ == "__main__":
    main()
