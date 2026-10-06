"""BƯỚC 2 — Thu thập dữ liệu từ 2 nguồn độc lập: Wikidata + Wikipedia tiếng Việt.

  1. Wikidata: mọi cơ sở GDĐH ở Việt Nam (P31/P279* Q38723, P17 Q881)
  2. Wikipedia tiếng Việt: duyệt đệ quy thể loại "Đại học Việt Nam", "Học viện Việt Nam", ...
     + toàn bộ bài viwiki được Wikidata trỏ tới (sitelink) -> đọc infobox
  3. Hợp hai tập (khoá chung = QID), lấy chi tiết từ Wikidata cho toàn bộ
  4. Tỉnh/thành (34 hiện hành + 29 tỉnh cũ sắp xếp năm 2025), cựu sinh viên

Đầu ra (tầng BRONZE data/bronze/, JSON giữ nguyên cấu trúc nhiều giá trị để bước 3 đối chiếu):
  wd_institutions.json, wd_entities.json, wd_provinces.json, wd_alumni.json, viwiki_pages.json
Mọi phản hồi HTTP được cache ở data/bronze/http_cache/ (xoá để lấy dữ liệu mới).
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_wikidata as wd  # noqa: E402
import collect_wikipedia as wp  # noqa: E402
import config  # noqa: E402
from common import record_manifest  # noqa: E402


SOURCES = {"viwiki_pages.json": "https://vi.wikipedia.org/w/api.php",
           "wd_institutions.json": config.WIKIDATA_SPARQL, "wd_entities.json": config.WIKIDATA_SPARQL,
           "wd_provinces.json": config.WIKIDATA_SPARQL, "wd_alumni.json": config.WIKIDATA_SPARQL,
           "dbp_years.json": config.DBPEDIA_SPARQL}


def save(name: str, obj) -> None:
    """Ghi một ảnh chụp tầng BRONZE + tệp .meta.json (nguồn, thời điểm, số bản ghi) + manifest."""
    import datetime
    path = config.BRONZE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=sorted), encoding="utf-8")
    meta = {"source": SOURCES.get(name, ""), "retrieved_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "records": len(obj), "user_agent": config.USER_AGENT,
            "license": "CC BY-SA 4.0" if "viwiki" in name else ("CC BY-SA 3.0" if "dbp" in name else "CC0 1.0")}
    path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    record_manifest("bronze", path, len(obj), "records", source=meta["source"], license=meta["license"])
    print(f"  -> {path.relative_to(config.ROOT)} ({len(obj)})")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("[1/5] Wikidata: tập cơ sở GDĐH ...")
    hei = wd.hei_qids()
    base = wd.institution_facts(hei)
    titles = [f["labels"]["vititle"] for f in base.values() if f.get("labels", {}).get("vititle")]
    print(f"  {len(hei)} thực thể, {len(titles)} có bài viwiki")

    print("[2/5] Wikipedia tiếng Việt: thể loại + infobox ...")
    guesses = {q: f["labels"]["vi"] for q, f in base.items()
               if f.get("labels", {}).get("vi") and not f["labels"].get("vititle")}
    pages = wp.collect(titles, guesses)
    save("viwiki_pages.json", pages)

    print("[3/5] Hợp hai nguồn & lấy chi tiết Wikidata ...")
    universe = sorted(set(hei) | {p["qid"] for p in pages if p["qid"]}, key=lambda q: int(q[1:]))
    facts = wd.institution_facts(universe)
    for q, f in facts.items():
        f["in_wikidata_hei_class"] = q in hei
    save("wd_institutions.json", list(facts.values()))
    save("dbp_years.json", wd.dbpedia_years(universe))

    referenced = set()
    for f in facts.values():
        referenced |= set(f.get("parents", [])) | {r["v"] for r in f.get("leaders", [])}
    save("wd_entities.json", wd.labels_of(referenced - set(facts)))

    print("[4/5] Tỉnh/thành ...")
    with (config.CURATED_DIR / "province_mergers_2025.csv").open(encoding="utf-8") as fh:
        former = {r["former_province"] for r in csv.DictReader(fh)}
    save("wd_provinces.json", wd.provinces(former))

    print("[5/5] Cựu sinh viên ...")
    save("wd_alumni.json", wd.alumni(universe))
    print("Xong bước 2.")


if __name__ == "__main__":
    main()
