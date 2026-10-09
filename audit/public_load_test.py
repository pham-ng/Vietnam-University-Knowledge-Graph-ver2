"""Bounded, read-only load probe for the deployed VN-Edu endpoint.

The default workload is deliberately small enough for a student deployment.  It
measures cold-start recovery separately from warm request latency and never sends
updates.  Passing this probe is operational evidence, not an SLA or capacity
certificate.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "data" / "reports" / "public-load-test.json"
COUNT_QUERY = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"


def percentile(values: list[float], quantile: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, int((len(values) - 1) * quantile + 0.5))
    return round(values[index] * 1000, 2)


def request_once(base: str, index: int, timeout: float) -> dict:
    mode = index % 3
    if mode == 0:
        url, params, accept, expected = base + "/healthz", None, "application/json", "application/json"
    elif mode == 1:
        url = base + "/resource/university/truong-dai-hoc-vinuni"
        params, accept, expected = None, "text/turtle", "text/turtle"
    else:
        url, params = base + "/sparql", {"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"}
        accept, expected = "application/sparql-results+json", "application/sparql-results+json"
    started = time.perf_counter()
    try:
        response = requests.get(url, params=params, headers={"Accept": accept}, timeout=timeout)
        elapsed = time.perf_counter() - started
        content_type = response.headers.get("Content-Type", "").lower()
        return {"status": response.status_code, "seconds": elapsed,
                "valid_type": expected in content_type, "mode": mode}
    except requests.RequestException as exc:
        return {"status": 0, "seconds": time.perf_counter() - started,
                "valid_type": False, "mode": mode, "error": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://vnedu-lod.onrender.com")
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--cold-start-timeout", type=float, default=120)
    parser.add_argument("--expected-triples", type=int, default=0)
    parser.add_argument("--max-warm-p95-ms", type=float, default=10_000)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    base = args.base.rstrip("/")

    cold_started = time.perf_counter()
    health_status = 0
    while time.perf_counter() - cold_started < args.cold_start_timeout:
        try:
            response = requests.get(base + "/healthz", timeout=min(30, args.timeout))
            health_status = response.status_code
            if response.ok:
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    cold_seconds = round(time.perf_counter() - cold_started, 3)

    triples = 0
    count_status = 0
    try:
        count = requests.get(base + "/sparql", params={"query": COUNT_QUERY},
                             headers={"Accept": "application/sparql-results+json"}, timeout=args.timeout)
        count_status = count.status_code
        if count.ok:
            triples = int(count.json()["results"]["bindings"][0]["n"]["value"])
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        pass

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        rows = list(pool.map(lambda i: request_once(base, i, args.timeout), range(max(1, args.requests))))
    statuses = Counter(str(row["status"]) for row in rows)
    latencies = [row["seconds"] for row in rows]
    errors = sum(row["status"] != 200 or not row["valid_type"] for row in rows)
    checks = {
        "cold_start_recovered": health_status == 200,
        "release_triple_count": not args.expected_triples or triples == args.expected_triples,
        "zero_request_errors": errors == 0,
        "warm_p95_within_probe_target": percentile(latencies, .95) <= args.max_warm_p95_ms,
    }
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": base,
        "scope": "bounded read-only public probe; not an SLA or high-volume capacity certificate",
        "cold_start": {"seconds": cold_seconds, "status": health_status},
        "release": {"count_query_status": count_status, "triples": triples,
                    "expected_triples": args.expected_triples or None},
        "warm_load": {"requests": len(rows), "concurrency": args.concurrency,
                      "status_counts": dict(statuses), "errors": errors,
                      "latency_ms": {"p50": percentile(latencies, .50),
                                     "p95": percentile(latencies, .95),
                                     "p99": percentile(latencies, .99),
                                     "max": round(max(latencies, default=0) * 1000, 2)}},
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
