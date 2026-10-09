"""Reproducible production-like security and concurrency smoke test.

This starts the committed WSGI path (Waitress, local read-only RDF backend) on
loopback, exercises concurrent health requests, and checks the public attack
guards.  It is evidence for application hardening and a small acceptance load,
not a certification of a particular cloud provider, TLS termination, firewall,
or high-volume capacity target.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "reports" / "production-readiness.json"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, round((len(values) - 1) * p))
    return round(values[index] * 1000, 2)


def timed_get(url: str) -> tuple[int, float]:
    started = time.perf_counter()
    response = requests.get(url, timeout=20)
    return response.status_code, time.perf_counter() - started


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    site_dir = os.environ.get("VNEDU_READINESS_SITE", "site_server")
    if not ((ROOT / site_dir / ".nojekyll").is_file() and (ROOT / site_dir / "index.html").is_file()):
        raise RuntimeError(f"Missing generated site {site_dir!r}; run step7_publish.py for that target first")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               VNEDU_SERVE_SITE=site_dir, VNEDU_QUERY_TIMEOUT="5",
               VNEDU_QUERY_WORKERS="2")
    process = subprocess.Popen(
        [sys.executable, "app/server.py", "--prod", "--backend", "local",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ready = False
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    ready = True
                    break
            except OSError:
                pass
            time.sleep(0.25)
        if not ready:
            raise RuntimeError("Waitress did not open its loopback port within 15 seconds")
        if requests.get(base + "/healthz", timeout=30).status_code != 200:
            raise RuntimeError("Waitress health check did not return HTTP 200")

        with ThreadPoolExecutor(max_workers=2) as pool:
            samples = list(pool.map(timed_get, [base + "/healthz"] * 8))
        with ThreadPoolExecutor(max_workers=8) as pool:
            overload = list(pool.map(timed_get, [base + "/healthz"] * 8))
        latencies = [elapsed for status, elapsed in samples]
        status_counts = {}
        for status, _ in samples:
            status_counts[str(status)] = status_counts.get(str(status), 0) + 1
        overload_status_counts = {}
        for status, _ in overload:
            overload_status_counts[str(status)] = overload_status_counts.get(str(status), 0) + 1

        health = requests.get(base + "/healthz", timeout=10)
        headers = {key: health.headers.get(key, "") for key in (
            "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Permissions-Policy", "X-Request-ID")}
        html_headers = {key: requests.get(base + "/", timeout=10).headers.get(key, "") for key in (
            "Content-Security-Policy", "Permissions-Policy", "X-Request-ID")}
        injection = requests.get(
            base + "/resource/university/a%3E%20%3Fp%20%3Fo%20%7D%20UNION%20%7B%20%3Fs%20%3Fp%20%3Fo%20%7D",
            timeout=10)
        ssrf = requests.post(base + "/sparql", data={
            "query": "SELECT * WHERE { SERVICE <http://127.0.0.1:3030/x> { ?s ?p ?o } }"
        }, timeout=10)
        oversized = requests.post(base + "/sparql", data={
            "query": "SELECT * WHERE { ?s ?p ?o } #" + "x" * 30000
        }, timeout=10)
        checks = {
            "health_status": health.status_code == 200,
            "normal_load_no_5xx": all(status == 200 for status, _ in samples),
            "overload_backpressure": any(status == 503 for status, _ in overload),
            "security_headers": all(headers.values()) and all(html_headers.values()),
            "resource_injection_rejected": injection.status_code == 404,
            "ssrf_rejected": ssrf.status_code == 400,
            "oversized_query_rejected": oversized.status_code == 413,
        }
        result = {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "server": "Waitress via app/server.py --prod --backend local",
            "scope": "normal bounded concurrency, intentional overload, and security guards",
            "load": {"requests": len(samples), "workers": 2,
                     "status_counts": status_counts,
                     "latency_ms": {"p50": percentile(latencies, .50),
                                    "p95": percentile(latencies, .95),
                                    "max": round(max(latencies, default=0) * 1000, 2)},
                     "overload_requests": len(overload),
                     "overload_status_counts": overload_status_counts},
            "headers": {**headers, "html": html_headers},
            "security_status_codes": {"resource_injection": injection.status_code,
                                       "ssrf": ssrf.status_code,
                                       "oversized_query": oversized.status_code},
            "checks": checks,
            "all_checks_passed": all(checks.values()),
            "limitations": [
                "Loopback acceptance evidence only; no TLS, reverse proxy, firewall, or cloud IAM claim.",
                "Not a high-volume capacity benchmark and not a production security certification.",
            ],
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["all_checks_passed"] else 2
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
