"""Compose the course components and pass versioned evidence between stages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "labs/e8e10"),
    str(ROOT / "labs/e8e10/environment/services/buildchecker"),
    str(ROOT / "labs/e11e12/vendor"),
]
from lab import patch, scan, validate

SCHEMA = "e11e12-1"
DEFAULT_TARGETS = {"main.o": "main.c", "helper.o": "helper.c"}
MODES = ("e11-a", "e11-b", "e12", "e12-repair")
EXECUTION_ERRORS = (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired)


class Failure(ValueError):
    def __init__(self, code, message, status="FAILED"):
        self.code = code
        self.status = status
        super().__init__(message)


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read(path):
    return json.loads(path.read_bytes())


def artifact(path, out, job_id):
    data = path.read_bytes()
    return {
        "uri": f"artifact://{job_id}/{path.relative_to(out).as_posix()}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def check_envelope(report, commit, kind=None):
    if report.get("schema_version") != SCHEMA:
        raise Failure("SCHEMA_MISMATCH", f"Expected {SCHEMA}")
    if report.get("commit") != commit:
        raise Failure("STALE_REPORT", "Report belongs to another commit")
    if report.get("status") != "SUCCEEDED":
        raise Failure("UPSTREAM_FAILED", "Upstream stage did not succeed")
    if kind and report.get("kind") != kind:
        raise Failure("ARTIFACT_TYPE_MISMATCH", f"Expected {kind}")


def load_artifact(path, expected_sha256):
    return json.loads(verified_bytes(path, expected_sha256))


def verified_bytes(path, expected_sha256):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise Failure("ARTIFACT_HASH_MISMATCH", "Artifact content changed during transfer")
    return data


def report_data(envelope, commit, kind):
    check_envelope(envelope, commit, kind)
    data = envelope["data"]
    if data.get("commit") != commit:
        raise Failure("STALE_REPORT", "Report data belongs to another commit")
    return data


def command(argv, cwd, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        result = subprocess.run(argv, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        raise Failure("COMMAND_FAILED", f"{argv[0]} failed; see {log.name}")
    return log.read_text(encoding="utf-8", errors="replace").strip()


def project_subdir(request):
    subdir = Path(request.get("project_subdir", "."))
    if subdir.is_absolute() or ".." in subdir.parts:
        raise Failure("INVALID_REQUEST", "project_subdir must be inside the repository")
    return subdir


def project_directory(checkout, request):
    project = (checkout / project_subdir(request)).resolve()
    if not project.is_relative_to(checkout.resolve()):
        raise Failure("INVALID_REQUEST", "project_subdir resolves outside the repository")
    return project


def snapshot(repo, revision, dest, logs, *, subdir=Path(".")):
    sha = command(["git", "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"],
                  repo, logs / f"{dest.name}-resolve.log")
    command(["git", "clone", "--no-hardlinks", "--no-checkout", str(repo), str(dest)],
            repo, logs / f"{dest.name}-clone.log")
    if subdir.parts:
        command(["git", "sparse-checkout", "set", "--cone", "--", subdir.as_posix()],
                dest, logs / f"{dest.name}-sparse.log")
    command(["git", "checkout", "--detach", sha], dest, logs / f"{dest.name}-checkout.log")
    return sha


def project_profile(request):
    name = request.get("profile", "course")
    if name == "course":
        return DEFAULT_TARGETS, {}, "app", {}
    if name == "b09-greeting":
        options = {"targets": DEFAULT_TARGETS, "compiler_flags": ["-std=c11", "-Wall", "-Wextra", "-Werror"]}
        return DEFAULT_TARGETS, options, "app", {**options, "rebuild_header": "extra.h"}
    if name == "sds":
        import sds
        scan_options = {"targets": sds.TARGETS, "compiler_flags": sds.COMPILER_FLAGS}
        return sds.TARGETS, scan_options, sds.BUILD_TARGET, {
            **scan_options, "build_target": sds.BUILD_TARGET, "rebuild_header": sds.HEADER,
        }
    raise Failure("UNSUPPORTED_PROJECT", f"Unknown project profile {name!r}; add a project mapping and validation")


def full(project, folder, build_target):
    from buildchecker.fullcheck import full_check
    report = full_check(project, folder, build_command=f"make {build_target}")
    if report["status"] != "SUCCEEDED":
        status = "TIMED_OUT" if report["status"] == "TIMED_OUT" else "FAILED"
        raise Failure("FULL_CHECK_FAILED", report.get("error", "Inspect full build logs"), status)
    return report


def normalized(findings, targets):
    return sorted((f["type"], f["target"], f["dependency"]) for f in findings if f["target"] in targets)


def stage(out, result, name, commit, data, filenames=()):
    job = result["job_id"]
    envelope = {
        "schema_version": SCHEMA, "job_id": job, "trace_id": result["trace_id"],
        "kind": name, "commit": commit, "status": "SUCCEEDED", "data": data,
        "artifacts": [artifact(out / filename, out, job) for filename in filenames],
    }
    path = out / f"{name}.json"
    save(path, envelope)
    reference = artifact(path, out, job)
    result["stages"].append({"name": name, "artifact": reference})
    return reference


def analyze_commits(request, out, result, targets, scan_options, build_target):
    base = project_directory(out / "base-project", request)
    target = project_directory(out / "target-project", request)
    base_full = full(base, out / "baseline-full", build_target)
    baseline = scan(base, **scan_options)
    edges = read(out / "baseline-full/actual-graph.json")
    projected = {
        name: sorted({edge["dependency"] for edge in edges if edge["target"] == name})
        for name in targets
    }
    if projected != baseline["actual"]:
        raise Failure("GRAPH_MISMATCH", "BuildChecker baseline differs from GCC observations")
    baseline["actual"] = projected
    save(out / "baseline-cache.json", baseline)
    stage(out, result, "full-check", result["base_commit"], base_full,
          ("baseline-full/actual-graph.json", "baseline-full/findings.json", "baseline-cache.json"))
    incremental = scan(target, baseline, **scan_options)
    save(out / "incremental-report.json", incremental)
    target_full = full(target, out / "target-full", build_target)
    if normalized(target_full["findings"], targets) != normalized(incremental["findings"], targets):
        raise Failure("FINDINGS_MISMATCH", "Incremental and full target findings differ")
    return stage(out, result, "incremental-check", result["target_commit"], incremental,
                 ("incremental-report.json", "target-full/findings.json"))


def repair(request, out, result, current, reference, build_target, validation_options):
    target = project_directory(out / "target-project", request)
    commit = result["target_commit"]
    before = (target / "Makefile").read_bytes()
    diff, edits = patch(target, current)
    details = {"edits": edits, "input_report": reference}
    if diff:
        candidate = out / "candidate.patch"
        candidate.write_text(diff, encoding="utf-8")
        save(out / "repair-plan.json", edits)
        stage(out, result, "repair", commit, details, ("candidate.patch", "repair-plan.json"))
        verdict = validate(target, candidate, out / "validation", **validation_options)
        if not verdict["accepted"]:
            raise Failure("REPAIR_REJECTED", "Inspect validation/validation.json")
    else:
        stage(out, result, "repair", commit, {**details, "action": "NO_CHANGES"})
        verdict = {"accepted": True, "action": "NO_CHANGES"}
    try:
        final = full(target, out / "final-full", build_target)
        if any(item["type"] == "MISSING" for item in final["findings"]):
            raise Failure("RECHECK_FAILED", "Missing dependencies remain after repair")
    except EXECUTION_ERRORS:
        if diff:
            (target / "Makefile").write_bytes(before)
        raise
    files = ["final-full/findings.json"]
    if diff:
        files.append("validation/validation.json")
    stage(out, result, "recheck", commit, {
        "validation": verdict, "findings": final["findings"],
        "patched_makefile_sha256": hashlib.sha256((target / "Makefile").read_bytes()).hexdigest(),
    }, files)


def downstream(request, out, result):
    mode = request["mode"]
    targets, scan_options, build_target, validation_options = project_profile(request)
    commit = result["target_commit"]
    if mode in ("e11-a", "e12"):
        reference = analyze_commits(request, out, result, targets, scan_options, build_target)
        if mode == "e11-a":
            return
        report = load_artifact(out / "incremental-check.json", reference["sha256"])
        current = report_data(report, commit, "incremental-check")
    elif mode == "e12-repair":
        reference = request["input_report"]
        report = load_artifact(out / "source-report.json", reference["sha256"])
        current = report_data(report, commit, "incremental-check")
    else:
        current = report_data(read(out / "fixed-md-input.json"), commit, "fixed-md")
        reference = stage(out, result, "fixed-md", commit, current, ("fixed-md-input.json",))
        current = report_data(load_artifact(out / "fixed-md.json", reference["sha256"]), commit, "fixed-md")
    validation_options["expected_output"] = request.get("expected_output", "1")
    repair(request, out, result, current, reference, build_target, validation_options)


def mark_failure(result, exc):
    result.update(
        status=getattr(exc, "status", "TIMED_OUT" if isinstance(exc, subprocess.TimeoutExpired) else "FAILED"),
        error={"code": getattr(exc, "code", "EXECUTION_FAILED"), "message": str(exc)},
    )


def run_in_draft(out, result, image):
    host_root = Path(os.environ.get("COURSE_HOST_ROOT", ROOT))
    host_out = host_root / out.relative_to(ROOT)
    name = result["job_id"] + "-execution"
    argv = [
        "docker", "run", "--rm", "--name", name, "--network", "none",
        "--cap-add", "SYS_PTRACE", "--user", f"{os.getuid()}:{os.getgid()}",
        "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{host_root / 'labs'}:/course/labs:ro", "-v", f"{host_out}:/evidence",
        "--entrypoint", "python3", image, "/course/labs/e11e12/pipeline.py", "--resume", "/evidence",
    ]
    state = out / "stage-state.json"
    save(state, result)
    save(out / "image-execution.json", {"image_id": image, "command": argv})
    try:
        with (out / "image-execution.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15, check=False)
        raise
    if process.returncode:
        raise Failure("IMAGE_EXECUTION_FAILED", "Inspect image-execution.log")
    result.update(read(state))


def validate_project(project, request):
    targets, _, _, _ = project_profile(request)
    names = {path.name for path in project.glob("*.c")}
    if names != set(targets.values()) or not (project / "Makefile").is_file():
        raise Failure("UNSUPPORTED_PROJECT", f"Expected {', '.join(targets.values())} and explicit Make rules")
    if targets == DEFAULT_TARGETS and not (project / "config.h").is_file():
        raise Failure("UNSUPPORTED_PROJECT", "Course profile requires config.h for the header validation")


def draft_for(request, target, out):
    from draft.autobuild import auto_build

    if request.get("profile") == "sds":
        from sds import dockerfile
        # The upstream tree has no Dockerfile. Only the detached target gets this build adapter.
        broken = dockerfile(request.get("draft_base", "python:3.13-slim"))
        (target / "Dockerfile.broken").write_text(broken, encoding="utf-8")
    draft = auto_build(
        target, Path(request["candidate"]).resolve(), out / "draft-build",
        request.get("expected_output", "1"), timeout=request.get("build_timeout", 600),
        base_image_override=request.get("draft_image_override"),
    )
    if draft["status"] != "SUCCEEDED":
        status = "TIMED_OUT" if draft["status"] == "TIMED_OUT" else "FAILED"
        raise Failure("DRAFT_FAILED", draft.get("error", "Inspect draft-build logs"), status)
    return draft


def execute(request, out, job_id=None, *, trace_id=None, source_report=None):
    if out.exists() and any(out.iterdir()):
        raise Failure("OUTPUT_EXISTS", "Use a fresh output directory")
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": SCHEMA, "job_id": job_id or f"job-{uuid.uuid4().hex}",
        "trace_id": trace_id or f"trace-{uuid.uuid4().hex}", "status": "RUNNING", "stages": [],
    }
    save(out / "request.json", request)
    try:
        mode = request["mode"]
        if mode not in MODES:
            raise Failure("INVALID_REQUEST", "Unknown mode")
        repo = Path(request["repo"]).resolve()
        if not repo.is_dir():
            raise Failure("INVALID_REQUEST", "Repository missing")
        subdir = project_subdir(request)
        for revision in ("base", "target"):
            checkout = out / f"{revision}-project"
            result[f"{revision}_commit"] = snapshot(repo, request[revision], checkout, out / "logs", subdir=subdir)
            validate_project(project_directory(checkout, request), request)
        commit = result["target_commit"]
        if mode == "e11-b":
            report_path = Path(request["fixed_report"])
            if "fixed_report_sha256" in request:
                data = verified_bytes(report_path, request["fixed_report_sha256"])
            else:
                data = report_path.read_bytes()
            report_data(json.loads(data), commit, "fixed-md")
            (out / "fixed-md-input.json").write_bytes(data)
        if mode == "e12-repair":
            if source_report is None:
                raise Failure("INVALID_REQUEST", "Submit e12-repair with an A report URI through the task API")
            data = verified_bytes(source_report, request["input_report"]["sha256"])
            report_data(json.loads(data), commit, "incremental-check")
            (out / "source-report.json").write_bytes(data)
        if mode == "e11-a":
            downstream(request, out, result)
            result["status"] = "SUCCEEDED"
        else:
            draft = draft_for(request, project_directory(out / "target-project", request), out)
            stage(out, result, "draft", commit, draft, ("draft-build/result.json",))
            run_in_draft(out, result, draft["attempts"][-1]["image_id"])
    except EXECUTION_ERRORS as exc:
        mark_failure(result, exc)
    result["artifacts"] = [
        artifact(path, out, result["job_id"]) for path in sorted(out.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(out).parts and not path.is_symlink()
    ]
    save(out / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--resume", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.resume:
        state = args.resume / "stage-state.json"
        result = read(state)
        try:
            downstream(read(args.resume / "request.json"), args.resume, result)
            result["status"] = "SUCCEEDED"
        except EXECUTION_ERRORS as exc:
            mark_failure(result, exc)
        save(state, result)
        return 0
    if not args.request or not args.out:
        parser.error("--request and --out required")
    result = execute(read(args.request), args.out.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
