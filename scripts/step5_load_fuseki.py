"""BƯỚC 5 — Nạp dữ liệu vào một Fuseki đang chạy (bản có quyền cập nhật, VD: Docker / TDB2).

  py scripts/step5_load_fuseki.py                              # Fuseki chạy cục bộ không mật khẩu
  py scripts/step5_load_fuseki.py --user admin --password vnedu-admin   # Docker (fuseki/docker-compose.yml)

Nếu chạy Fuseki bằng fuseki\\run_fuseki.ps1 (chế độ --file) thì dữ liệu đã được nạp sẵn,
không cần script này.

Script sẽ: tạo dataset (nếu chưa có) -> thay toàn bộ default graph bằng vnedu-all.ttl
(Graph Store Protocol, HTTP PUT) -> chạy một truy vấn kiểm tra.
"""
import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=config.FUSEKI_URL)
    ap.add_argument("--dataset", default=config.FUSEKI_DATASET)
    ap.add_argument("--user")
    ap.add_argument("--password")
    args = ap.parse_args()
    auth = (args.user, args.password) if args.user else None

    try:
        requests.get(f"{args.url}/$/ping", timeout=5).raise_for_status()
    except requests.RequestException:
        raise SystemExit(f"Không kết nối được Fuseki tại {args.url}")

    r = requests.get(f"{args.url}/$/datasets/{args.dataset}", auth=auth, timeout=10)
    if r.status_code == 404:
        print(f"Tạo dataset /{args.dataset} (TDB2) ...")
        requests.post(f"{args.url}/$/datasets", data={"dbName": args.dataset, "dbType": "tdb2"},
                      auth=auth, timeout=30).raise_for_status()

    print(f"Nạp {config.ALL_TTL.name} ...")
    with config.ALL_TTL.open("rb") as f:
        r = requests.put(f"{args.url}/{args.dataset}/data?default", data=f,
                         headers={"Content-Type": "text/turtle; charset=utf-8"}, auth=auth, timeout=600)
    r.raise_for_status()

    r = requests.post(f"{args.url}/{args.dataset}/sparql", data={"query": "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"},
                      headers={"Accept": "application/sparql-results+json"}, auth=auth, timeout=60)
    n = r.json()["results"]["bindings"][0]["n"]["value"]
    print(f"Xong: {n} triple trong {args.url}/{args.dataset}  (endpoint: {args.url}/{args.dataset}/sparql)")


if __name__ == "__main__":
    main()
