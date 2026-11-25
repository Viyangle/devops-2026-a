"""Exercise real CLI-prepared jobs over HTTP and retain both sides of the handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(base_url, request_path, output):
    output.mkdir(parents=True)
    target_request = json.loads(request_path.read_text(encoding="utf-8"))
    prefix = f"smoke-{uuid4().hex[:10]}"
    requests = []

    def call(path, status=200, body=None, expect=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        request = Request(base_url.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as http_error:
            response = http_error
        with response:
            payload = response.read()
            requests.append({"path": path, "status": response.code})
            require(response.code == status, f"{path}: expected HTTP {status}, got {response.code}: {payload[:500]}")
            if expect:
                require(json.loads(payload)["error"] == expect, f"{path}: expected {expect}")
            return payload, response.headers

    def record(name, data):
        (output / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    def queue(name, data, key=None):
        body = {"idempotency_key": key or f"{prefix}-{name}", "input": data}
        record(f"{name}-request", body)
        state = json.loads(call("/v1/jobs", 202, body)[0])
        record(f"{name}-submitted", state)
        return state

    def complete(name, initial, status="SUCCEEDED"):
        path = f"/v1/jobs/{initial['job_id']}"
        deadline = time.monotonic() + 900
        observations = [initial["status"]]
        while time.monotonic() < deadline:
            state = json.loads(call(path)[0])
            require(state["trace_id"] == initial["trace_id"], "Trace ID changed during polling")
            if state["status"] != observations[-1]:
                observations.append(state["status"])
            if state["status"] not in ("QUEUED", "RUNNING"):
                break
            time.sleep(1)
        record(f"{name}-state", state)
        record(f"{name}-poll", observations)
        require(state["status"] == status, f"{name}: {state}")
        result = json.loads(call(f"{path}/artifacts")[0])
        record(f"{name}-result", result)
        require(result["trace_id"] == state["trace_id"], name + ": manifest trace mismatch")
        return result

    def download(name, result, filename):
        job = result["job_id"]
        uri = f"artifact://{job}/{filename}"
        reference = next(item for item in result["artifacts"] if item["uri"] == uri)
        payload, headers = call(f"/v1/jobs/{job}/files/{filename}")
        digest = hashlib.sha256(payload).hexdigest()
        require(digest == reference["sha256"] == headers["X-Content-SHA256"], f"{name}: artifact hash mismatch")
        (output / f"{name}-{Path(filename).name}").write_bytes(payload)
        record(f"{name}-{Path(filename).name}-headers", dict(headers))
        return reference

    try:
        record("health", json.loads(call("/health")[0]))

        a_input = dict(target_request, mode="e11-a")
        a_job = queue("a", a_input)
        a_result = complete("a", a_job)
        md = download("a", a_result, "incremental-check.json")

        b_input = dict(target_request, mode="e12-repair", input_report=md)
        b_job = queue("b", b_input)
        b_result = complete("b", b_job)
        download("b", b_result, "candidate.patch")
        download("b", b_result, "repair.json")
        download("b", b_result, "recheck.json")
        require(json.loads((output / "b-repair.json").read_text())["data"]["input_report"] == md,
                "B did not consume the A report reference")

        e12 = queue("e12", target_request)
        duplicate = queue("e12-duplicate", target_request, f"{prefix}-e12")
        require(duplicate["job_id"] == e12["job_id"], "Same request dispatched another job")
        conflict = {"idempotency_key": f"{prefix}-e12",
                    "input": dict(target_request, target=target_request["base"])}
        call("/v1/jobs", 409, conflict, "IDEMPOTENCY_CONFLICT")
        stale = queue("stale", dict(b_input, target=target_request["base"]))
        stale_result = complete("stale", stale, "FAILED")
        require(stale_result["error"]["code"] == "STALE_REPORT" and not stale_result["stages"],
                "Stale report reached a build or repair phase")
        wrong_sha = {"idempotency_key": f"{prefix}-wrong-sha",
                     "input": dict(b_input, input_report=dict(md, sha256="0" * 64))}
        call("/v1/jobs", 400, wrong_sha, "ARTIFACT_HASH_MISMATCH")

        result = complete("e12", e12)
        stages = ["draft", "full-check", "incremental-check", "repair", "recheck"]
        require([stage["name"] for stage in result["stages"]] == stages, "E12 stage order differs")
        for name in stages:
            download("e12", result, f"{name}.json")
            report = json.loads((output / f"e12-{name}.json").read_bytes())
            commit = result["base_commit"] if name == "full-check" else result["target_commit"]
            require((report["job_id"], report["trace_id"], report["commit"]) ==
                    (result["job_id"], result["trace_id"], commit), f"{name}: envelope identity differs")
        download("e12", result, "candidate.patch")
        download("e12", result, "image-execution.json")
        execution = json.loads((output / "e12-image-execution.json").read_bytes())
        draft = json.loads((output / "e12-draft.json").read_bytes())["data"]
        require(execution["image_id"] == draft["attempts"][-1]["image_id"], "DRAFT image was not reused")
        print(f"HTTP_OK e12={result['job_id']} a={a_result['job_id']} b={b_result['job_id']}")
    finally:
        record("http-log", requests)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.url, args.request, args.out)


if __name__ == "__main__":
    main()
