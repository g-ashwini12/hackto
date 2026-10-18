"""Latency + memory benchmark for the PS2 pipeline (runs fully on-device).

Uploads a document to the running API, asks a fixed question set N times and
reports per-stage p50/p95 from the Server-Timing header, Ollama token speed,
and memory of the API and model processes.

    python scripts/benchmark.py --doc samples/sample_rental_agreement.txt --rounds 3 --out bench.json
"""
import argparse
import json
import resource
import statistics
import sys
import time
import urllib.request
import uuid
from typing import Dict, List

QUESTIONS = [
    "When is the rent due and how much is it?",
    "What happens if I pay rent late?",
    "How can the agreement be terminated?",
    "When will my security deposit be returned?",
    "Who pays for plumbing repairs?",
    "Does the agreement mention pets?",           # document is silent
    "Is the lock-in clause enforceable?",          # must escalate, no model call
]


def _request(url: str, fields: Dict[str, str] = None, file_path: str = None):
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in (fields or {}).items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    if file_path:
        name = file_path.rsplit("/", 1)[-1]
        with open(file_path, "rb") as f:
            data = f.read()
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                 f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read())
        timing = resp.headers.get("Server-Timing", "")
    return payload, timing, (time.perf_counter() - start) * 1000.0


def _parse_server_timing(header: str) -> Dict[str, float]:
    out = {}
    for part in filter(None, (p.strip() for p in header.split(","))):
        name, _, dur = part.partition(";dur=")
        out[name] = float(dur or 0)
    return out


def _pct(values: List[float], p: float) -> float:
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round((len(s) - 1) * p)))], 1)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--doc", default="samples/sample_rental_agreement.txt")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out")
    args = ap.parse_args()

    up, up_timing, up_ms = _request(f"{args.api}/upload", file_path=args.doc)
    if "doc_id" not in up:
        print("upload failed:", up)
        return 1
    print(f"upload {up_ms:.0f} ms  category={up.get('category')}  stages={_parse_server_timing(up_timing)}")

    stages: Dict[str, List[float]] = {}
    e2e: List[float] = []
    for r in range(args.rounds):
        for q in QUESTIONS:
            body, timing, ms = _request(f"{args.api}/chat", fields={"doc_id": up["doc_id"], "query": q})
            e2e.append(ms)
            for name, dur in _parse_server_timing(timing).items():
                stages.setdefault(name, []).append(dur)
            if r == 0:
                print(f"{ms:7.0f} ms  {q}\n          -> {(body.get('response') or body.get('error', ''))[:110]}")

    report = {
        "doc": args.doc,
        "rounds": args.rounds,
        "upload_ms": round(up_ms, 1),
        "chat_e2e_ms": {"p50": _pct(e2e, .5), "p95": _pct(e2e, .95), "max": round(max(e2e), 1)},
        "stages_ms": {k: {"p50": _pct(v, .5), "p95": _pct(v, .95), "n": len(v)} for k, v in sorted(stages.items())},
        "server_metrics": _get(f"{args.api}/dashboard/metrics"),
        "ollama": _get(f"{args.api}/health/ready"),
        "bench_client_max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    print(json.dumps({k: report[k] for k in ("chat_e2e_ms", "stages_ms", "ollama")}, indent=2))
    print("avg tokens/s:", report["server_metrics"].get("avg_tokens_per_s"),
          "| stdev e2e ms:", round(statistics.pstdev(e2e), 1))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
