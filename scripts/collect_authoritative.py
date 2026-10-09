"""Collect current authoritative enrichment for institutions already in SILVER.

The collector deliberately uses exact normalized-name matches for the Ministry
admissions directory.  Approximate matches are exported as review candidates,
never merged automatically.  ROR records are fetched only for ROR IDs already
linked to an institution by Wikidata.

Outputs
-------
data/bronze/moet_admissions.json
    Current public Ministry directory.  Contact details are fetched for exact
    matches to this project's institution registry.
data/bronze/ror_organizations.json
    ROR schema 2.1 records for the already-linked ROR identifiers.
data/reports/authoritative-collection.json
    Collection counts and failures; no failed request is silently accepted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import record_manifest, vn_key  # noqa: E402

MOET_LIST_URL = "https://tuyensinh.moet.gov.vn/ts/ThongTinTruong/GetData"
MOET_DETAIL_URL = "https://tuyensinh.moet.gov.vn/ts/ThongTinTruong/ViewDetail"
MOET_PUBLIC_URL = "https://tuyensinh.moet.gov.vn/ts/"
ROR_API = "https://api.ror.org/v2/organizations/https%3A%2F%2Fror.org%2F{}"
USER_AGENT = "Mozilla/5.0 (compatible; VNEduLOD/2.2; +https://github.com/pham-ng/Vietnam-University-Knowledge-Graph-ver2)"

_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        _local.session = session
    return session


def _request(method: str, url: str, *, attempts: int = 5, **kwargs) -> requests.Response:
    delay = 1.5
    for attempt in range(1, attempts + 1):
        try:
            response = _session().request(method, url, timeout=90, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == attempts:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 20)
    raise AssertionError("unreachable")


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _detail_value(document: str, label: str) -> str:
    pattern = rf"<label[^>]*>\s*{re.escape(label)}\s*</label>\s*<div[^>]*>(.*?)</div>"
    match = re.search(pattern, document, flags=re.I | re.S)
    return _clean_html(match.group(1)) if match else ""


def _fetch_moet_detail(row: dict) -> tuple[str, dict]:
    response = _request("POST", MOET_DETAIL_URL, data={"Id": row["Id"], "LOAI_HO_TRO": "1"})
    document = response.text
    website_match = re.search(r'<a\s+href="([^"]+)"[^>]*target="_blank"', document, flags=re.I)
    return row["Id"], {
        "email": _detail_value(document, "Email:"),
        "telephone": _detail_value(document, "Điện thoại:"),
        "website": html.unescape(website_match.group(1)).strip() if website_match else "",
    }


def collect_moet(insts: dict, workers: int) -> tuple[list[dict], list[dict]]:
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": MOET_PUBLIC_URL}
    payload = {
        "indexPage": 1,
        "sortQuery": "",
        "pageSize": 500,
        "type": 1,
        "searchModel[Type]": 1,
        "searchModel[Code]": "",
        "searchModel[Name]": "",
    }
    data = _request("POST", MOET_LIST_URL, data=payload, headers=headers).json()
    rows = data.get("ListItem", [])
    known = {vn_key(item["name_vi"]): key for key, item in insts.items()}
    matched = {row["Id"]: known[vn_key(row["TEN_DON_VI"])] for row in rows if vn_key(row["TEN_DON_VI"]) in known}
    failures: list[dict] = []
    details: dict[str, dict] = {}
    # Fetch every directory record so a clean pipeline run does not depend on a
    # previous SILVER snapshot and newly discovered institutions are covered.
    selected = rows
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_moet_detail, row): row for row in selected}
        for future in as_completed(futures):
            row = futures[future]
            try:
                key, detail = future.result()
                details[key] = detail
            except Exception as exc:  # recorded and rejected rather than silently producing blanks
                failures.append({"source": "moet", "code": row.get("MA"), "id": row.get("Id"), "error": str(exc)})

    output = []
    for row in rows:
        output.append({
            "code": (row.get("MA") or "").strip().upper(),
            "name": (row.get("TEN") or row.get("TEN_DON_VI") or "").strip(),
            "id": row.get("Id") or "",
            "matched_institution_key": matched.get(row.get("Id"), ""),
            **details.get(row.get("Id"), {}),
        })
    return output, failures


def _fetch_ror(ror_id: str) -> tuple[str, dict]:
    response = _request("GET", ROR_API.format(ror_id))
    return ror_id, response.json()


def collect_ror(insts: dict, workers: int) -> tuple[dict, list[dict]]:
    ids = sorted({ror_id for item in insts.values() for ror_id in item.get("ror", [])})
    records: dict[str, dict] = {}
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_ror, ror_id): ror_id for ror_id in ids}
        for future in as_completed(futures):
            ror_id = futures[future]
            try:
                key, record = future.result()
                records[key] = record
            except Exception as exc:
                failures.append({"source": "ror", "ror": ror_id, "error": str(exc)})
    return dict(sorted(records.items())), failures


def _write_snapshot(name: str, data, source: str, license_name: str) -> None:
    path = config.BRONZE_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    retrieved = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    meta = {"source": source, "retrieved_at": retrieved, "records": len(data), "license": license_name}
    path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    record_manifest("bronze", path, len(data), "records", source=source, license=license_name,
                    retrieved_at=retrieved)


def load_collection_registry() -> dict:
    """Build a minimal name/ROR registry without requiring a previous SILVER run."""
    insts = {}
    silver = config.SILVER_DIR / "institutions.json"
    if silver.exists():
        insts.update(json.loads(silver.read_text(encoding="utf-8")))
    wikidata = config.BRONZE_DIR / "wd_institutions.json"
    if wikidata.exists():
        for row in json.loads(wikidata.read_text(encoding="utf-8")):
            labels = row.get("labels", {})
            name = labels.get("vititle") or labels.get("vi") or ""
            if name:
                insts.setdefault(row["qid"], {"name_vi": name, "ror": row.get("ror", [])})
            elif row.get("ror"):
                insts.setdefault(row["qid"], {"name_vi": row["qid"], "ror": row.get("ror", [])})
    return insts


def collect_all(workers: int = 6, skip_moet: bool = False, skip_ror: bool = False) -> dict:
    insts = load_collection_registry()
    failures: list[dict] = []
    summary = {"retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}

    if not skip_moet:
        print("[authoritative] Ministry admissions directory and public contacts ...", flush=True)
        moet, failed = collect_moet(insts, workers)
        failures.extend(failed)
        _write_snapshot("moet_admissions.json", moet, MOET_PUBLIC_URL,
                        "Official public facts; no machine-readable open-data licence stated")
        summary["moet"] = {"records": len(moet), "matched": sum(bool(r["matched_institution_key"]) for r in moet),
                           "details": sum("email" in r for r in moet), "failures": len(failed)}

    if not skip_ror:
        print("[authoritative] ROR schema 2.1 records ...", flush=True)
        ror, failed = collect_ror(insts, workers)
        failures.extend(failed)
        _write_snapshot("ror_organizations.json", ror, "https://api.ror.org/v2/organizations", "CC0 1.0")
        summary["ror"] = {"records": len(ror), "failures": len(failed)}

    summary["failures"] = failures
    out = config.REPORTS_DIR / "authoritative-collection.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    if failures:
        raise RuntimeError(f"Authoritative collection incomplete: {len(failures)} failed requests")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip-moet", action="store_true")
    parser.add_argument("--skip-ror", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    summary = collect_all(args.workers, args.skip_moet, args.skip_ror)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
