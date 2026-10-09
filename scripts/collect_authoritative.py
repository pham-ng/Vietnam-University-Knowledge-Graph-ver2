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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import httpcache  # noqa: E402 — bộ đệm dùng chung: chạy lại không cần Internet, kết quả tái lập
from common import record_manifest, vn_key  # noqa: E402

MOET_LIST_URL = "https://tuyensinh.moet.gov.vn/ts/ThongTinTruong/GetData"
MOET_DETAIL_URL = "https://tuyensinh.moet.gov.vn/ts/ThongTinTruong/ViewDetail"
MOET_PUBLIC_URL = "https://tuyensinh.moet.gov.vn/ts/"
ROR_API = "https://api.ror.org/v2/organizations/https%3A%2F%2Fror.org%2F{}"
USER_AGENT = "Mozilla/5.0 (compatible; VNEduLOD/2.2; +https://github.com/pham-ng/Vietnam-University-Knowledge-Graph-ver2)"
# Cổng tuyển sinh từ chối User-Agent dạng bot (403) -> dùng UA kiểu trình duyệt cho các request tới Bộ.
MOET_HEADERS = {"User-Agent": USER_AGENT, "Referer": MOET_PUBLIC_URL}
# Lỗi khi tải (hết lượt thử lại -> SystemExit, hoặc thiếu bộ đệm khi chạy offline) được ghi nhận, không nuốt im.
FETCH_ERRORS = (Exception, SystemExit)


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _detail_value(document: str, label: str) -> str:
    pattern = rf"<label[^>]*>\s*{re.escape(label)}\s*</label>\s*<div[^>]*>(.*?)</div>"
    match = re.search(pattern, document, flags=re.I | re.S)
    return _clean_html(match.group(1)) if match else ""


def _fetch_moet_detail(row: dict) -> tuple[str, dict]:
    document = httpcache.get_text(MOET_DETAIL_URL, {"Id": row["Id"], "LOAI_HO_TRO": "1"}, method="POST",
                                  headers=MOET_HEADERS)
    website_match = re.search(r'<a\s+href="([^"]+)"[^>]*target="_blank"', document, flags=re.I)
    return row["Id"], {
        "email": _detail_value(document, "Email:"),
        "telephone": _detail_value(document, "Điện thoại:"),
        "website": html.unescape(website_match.group(1)).strip() if website_match else "",
    }


def collect_moet(insts: dict, workers: int) -> tuple[list[dict], list[dict]]:
    headers = {**MOET_HEADERS, "X-Requested-With": "XMLHttpRequest"}
    payload = {
        "indexPage": 1,
        "sortQuery": "",
        "pageSize": 500,
        "type": 1,
        "searchModel[Type]": 1,
        "searchModel[Code]": "",
        "searchModel[Name]": "",
    }
    data = httpcache.get_json(MOET_LIST_URL, payload, method="POST", headers=headers)
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
            except FETCH_ERRORS as exc:  # recorded and rejected rather than silently producing blanks
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
    return ror_id, httpcache.get_json(ROR_API.format(ror_id), {})


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
            except FETCH_ERRORS as exc:
                failures.append({"source": "ror", "ror": ror_id, "error": str(exc)})
    return dict(sorted(records.items())), failures


def _write_snapshot(name: str, data, source: str, license_name: str) -> None:
    path = config.BRONZE_DIR / name
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    retrieved = stable_retrieved_at(path, text)
    path.write_text(text, encoding="utf-8")
    meta = {"source": source, "retrieved_at": retrieved, "records": len(data), "license": license_name}
    path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    record_manifest("bronze", path, len(data), "records", source=source, license=license_name,
                    retrieved_at=retrieved)


# Trường do pipeline tự ghép (không phải dữ liệu nguồn): đổi khi quy tắc ghép đổi, không có nghĩa là đã tải lại.
DERIVED_KEYS = {"matched_institution_key"}


def _source_part(text: str):
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in DERIVED_KEYS}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(json.loads(text))


def stable_retrieved_at(path: Path, new_text: str) -> str:
    """Thời điểm thu thập chỉ đổi khi DỮ LIỆU NGUỒN đổi: dữ liệu lấy lại từ bộ đệm giữ nguyên thời điểm gốc.

    Trước đây mỗi lần build ghi now(), làm đổi mã băm snapshot và toàn bộ URI observation dù dữ liệu y hệt."""
    meta = path.with_suffix(".meta.json")
    if path.exists() and meta.exists() and _source_part(path.read_text(encoding="utf-8")) == _source_part(new_text):
        previous = json.loads(meta.read_text(encoding="utf-8")).get("retrieved_at")
        if previous:
            return previous
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


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
    summary = {}

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

    metas = [config.BRONZE_DIR / n for n in ("moet_admissions.meta.json", "ror_organizations.meta.json")]
    summary["retrieved_at"] = max((json.loads(m.read_text(encoding="utf-8"))["retrieved_at"]
                                   for m in metas if m.exists()), default="")
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
