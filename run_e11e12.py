"""Run the E11–E12 environment, CLI and loopback API on a Linux Docker host."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["build", "prepare", "prepare-sds", "run", "serve", "test"])
    parser.add_argument("--request", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--base-image")
    args = parser.parse_args()

    student = subprocess.run(
        ["git", "config", "--local", "user.name"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9]{6,16}", student):
        parser.error("Set local git user.name to your numeric student ID")
    image = f"course-e11e12:{student}"
    print(f"IMAGE={image}", flush=True)

    if args.stage == "build":
        base = ["--build-arg", f"BASE_IMAGE={args.base_image}"] if args.base_image else []
        return subprocess.call(
            ["docker", "build", "--progress=plain", *base,
             "-f", "labs/e11e12/Dockerfile", "-t", image, "labs/e11e12"], cwd=ROOT,
        )

    request_mode = None
    if args.stage == "run":
        if not args.request or not args.out:
            parser.error("--request and --out required")
        request = (ROOT / args.request).resolve()
        out = (ROOT / args.out).resolve()
        if not request.is_relative_to(ROOT) or not out.is_relative_to(ROOT / "work") or out == ROOT / "work":
            parser.error("Request inside repo and output below work/ required")
        request_mode = json.loads(request.read_text(encoding="utf-8")).get("mode")

    uses_draft = args.stage == "serve" or request_mode in ("e11-b", "e12", "e12-repair")
    # Buildx exchanges registry auth from this client. Generated programs run networkless.
    network = "bridge" if uses_draft else "none"
    docker = ["docker", "run", "--rm", "--network", network]
    if uses_draft:
        sock = Path("/var/run/docker.sock")
        docker += ["--group-add", str(sock.stat().st_gid), "-v", f"{sock}:{sock}"]
    if args.stage == "serve":
        docker += ["--init", "-p", f"127.0.0.1:{args.port}:8080"]
    docker += [
        "--cap-add", "SYS_PTRACE", "--user", f"{os.getuid()}:{os.getgid()}",
        "-e", "HOME=/tmp", "-e", f"COURSE_HOST_ROOT={ROOT}",
        "-e", "PYTHONPATH=/course/labs/e11e12", "-v", f"{ROOT}:/course",
        "-w", "/course", image, "python3",
    ]
    if args.stage == "prepare":
        docker += ["labs/e11e12/prepare.py"]
    elif args.stage == "prepare-sds":
        docker += ["labs/e11e12/sds.py", "--repo", "data/sds"]
    elif args.stage == "serve":
        directory = "api-jobs" if args.port == 8080 else f"api-jobs-{args.port}"
        docker += ["labs/e11e12/server.py", "--host", "0.0.0.0", "--store", f"work/{directory}"]
        os.execvp("docker", docker)
    elif args.stage == "test":
        docker += ["-m", "unittest", "discover", "-s", "labs/e11e12", "-v"]
    else:
        docker += [
            "labs/e11e12/pipeline.py", "--request", f"/course/{request.relative_to(ROOT)}",
            "--out", f"/course/{out.relative_to(ROOT)}",
        ]
    return subprocess.call(docker, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
