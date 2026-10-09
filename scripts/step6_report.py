"""BƯỚC 6 — Báo cáo chất lượng dữ liệu xuyên suốt 3 tầng Medallion -> data/reports/quality_report.md

Gồm: dòng dõi dữ liệu (manifest), độ đầy đủ theo trường, nguồn của từng giá trị, mâu thuẫn giữa các nguồn,
kết quả kiểm định JSON Schema (silver) / SHACL + nhất quán OWL (gold), thống kê liên kết, checklist 5 sao.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

R = config.REPORTS_DIR
HEI_KINDS = {"University", "UniversitySchool", "Academy", "OfficerSchool", "NationalUniversity",
             "RegionalUniversity", "HigherEducationInstitution"}
FIELDS = [("founding_year", "năm thành lập"), ("province", "tỉnh/thành"), ("ownership", "loại hình sở hữu"),
          ("website", "website"), ("leaders", "lãnh đạo"), ("_governance", "cơ quan chủ quản"),
          ("name_en", "tên tiếng Anh"), ("short_names", "tên viết tắt"), ("motto_vi", "khẩu hiệu"),
          ("lat", "toạ độ"), ("admission_codes", "mã trường"), ("ror", "mã ROR"),
          ("students", "số sinh viên"), ("academic_staff", "số giảng viên"),
          ("abstract", "giới thiệu chung"), ("history", "lịch sử"), ("logo", "biểu trưng"), ("image", "ảnh"),
          ("founding_date", "ngày thành lập đầy đủ"), ("alt_names", "tên khác"), ("telephone", "điện thoại"),
          ("email", "email"), ("campus", "khuôn viên")]


def read(name):
    p = R / name
    return list(csv.DictReader(p.open(encoding="utf-8-sig"))) if p.exists() else []


def bar(frac: float, width: int = 20) -> str:
    n = round(frac * width)
    return "█" * n + "░" * (width - n)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    manifest = json.loads(config.MANIFEST.read_text(encoding="utf-8")) if config.MANIFEST.exists() else {}
    insts = json.loads((config.SILVER_DIR / "institutions.json").read_text(encoding="utf-8"))
    hei = [i for i in insts.values() if i["kind"] in HEI_KINDS]
    L = ["# Báo cáo chất lượng dữ liệu VN-Edu LOD", "",
         "*Sinh tự động bởi `scripts/step6_report.py` sau mỗi lần chạy pipeline.*", ""]

    L += ["## 1. Dòng dõi dữ liệu (Medallion)", "", "| Tầng | Tệp | Số lượng | SHA-256 | Tạo lúc |", "|---|---|---|---|---|"]
    for layer in ("bronze", "silver", "gold"):
        for f, m in sorted(manifest.get(layer, {}).items()):
            L.append(f"| {layer} | `{f}` | {m['count']:,} {m['unit']} | `{m['sha256'][:12]}` | {m['generated_at']} |")

    L += ["", f"## 2. Độ đầy đủ — {len(hei)} cơ sở giáo dục đại học (tầng silver)", "",
          "| Thuộc tính | Có | Tỉ lệ | |", "|---|---|---|---|"]
    for f, label in FIELDS:
        n = (sum(1 for i in hei if i.get("governed_by") or i.get("direct_governed_by"))
             if f == "_governance" else sum(1 for i in hei if i.get(f)))
        L.append(f"| {label} | {n} | {n / len(hei):.1%} | `{bar(n / len(hei))}` |")

    meta_rows = []
    for filename, label in (("moet_admissions.meta.json", "Cổng tuyển sinh Bộ GDĐT"),
                            ("ror_organizations.meta.json", "ROR schema 2.1")):
        path = config.BRONZE_DIR / filename
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            meta_rows.append((label, meta.get("records", 0), meta.get("retrieved_at", ""), meta.get("license", "")))
    sourced = Counter()
    for inst in hei:
        for field, refs in inst.get("field_sources", {}).items():
            if refs:
                sourced[field] += 1
    coord_sources = Counter(i.get("coord_source", "unknown") for i in hei if i.get("lat") is not None)
    L += ["", "## 3. Nguồn hiện hành và chính sách chấp nhận", "",
          "Các giá trị mới chỉ được hợp nhất khi tên chính thức khớp chính xác. Ngoại lệ duy nhất là cặp tên cũ–tên hiện hành "
          "đã được khai báo bằng quyết định đổi tên có ngày; fuzzy match chỉ được xem là ứng viên. "
          "Thời điểm truy xuất là thời điểm của snapshot, không được diễn giải thành thời hạn hiệu lực pháp lý.", "",
          "| Nguồn | Bản ghi | Truy xuất (UTC) | Giấy phép/trạng thái |", "|---|---:|---|---|"]
    for label, count, retrieved, licence in meta_rows:
        L.append(f"| {label} | {count} | {retrieved} | {licence} |")
    L += ["", "| Trường có nguồn cấp thuộc tính | Số cơ sở GDĐH |", "|---|---:|",
          f"| mã tuyển sinh — Bộ GDĐT | {sourced['admission_codes']} |",
          f"| email — Bộ GDĐT | {sourced['email']} |",
          f"| website — Bộ GDĐT | {sourced['website']} |",
          f"| tên viết tắt — ROR | {sourced['short_names']} |",
          f"| tên cũ — quyết định đổi tên | {sourced['former_names']} |",
          f"| cơ quan chủ quản trực tiếp — văn bản pháp lý | {sourced['direct_governed_by']} |", "",
          "**Toạ độ:** " + ", ".join(f"`{k}` {v}" for k, v in sorted(coord_sources.items())) + ". "
          "Không dùng toạ độ ROR làm toạ độ campus vì ROR/GeoNames thường biểu diễn tâm địa phương, không phải điểm của cơ sở.", "",
          "**Campus:** `vnedu:campus` hiện lưu diện tích/mô tả khuôn viên từ nguồn, không đồng nghĩa với địa chỉ trụ sở. "
          "Không tự động sao chép địa chỉ vào trường này chỉ để tăng coverage."]

    filled, conflicts, excluded, unresolved = read("filled.csv"), read("conflicts.csv"), read("excluded.csv"), read("unresolved.csv")
    L += ["", "## 4. Nguồn của giá trị và mâu thuẫn giữa các nguồn", "",
          "Giá trị chính lấy từ Wikidata và infobox Wikipedia tiếng Việt (đối chiếu chéo). Khi cả hai đều thiếu, dùng "
          "nguồn dự phòng — mỗi giá trị đều được ghi lại trong `filled.csv`:", "",
          "| Nguồn dự phòng | Trường | Số giá trị |", "|---|---|---|"]
    for (src, fld), n in sorted(Counter((r["source"], r["field"]) for r in filled).items()):
        L.append(f"| {src} | {fld} | {n} |")
    L += ["", "Mâu thuẫn giữa các nguồn (`conflicts.csv`):", "", "| Trường | Số mâu thuẫn |", "|---|---|"]
    for fld, n in Counter(r["field"] for r in conflicts).most_common():
        L.append(f"| {fld} | {n} |")
    L += ["", f"Thực thể bị loại khỏi phạm vi (`excluded.csv`): **{len(excluded)}**", "", "| Lý do | Số |", "|---|---|"]
    for reason, n in Counter(re.sub(r"Q[0-9]+", "…", r["reason"].split(" — ")[0])[:90] for r in excluded).most_common():
        L.append(f"| {reason} | {n} |")
    L += ["", f"Giá trị chưa phân giải được, cần rà soát tay (`unresolved.csv`): **{len(unresolved)}**"]

    sv = read("silver_validation.csv")
    L += ["", "## 5. Kiểm định", "", "| Cổng kiểm định | Tầng | Kết quả |", "|---|---|---|",
          f"| JSON Schema (`schemas/silver.schema.json`) | silver | {'✅ đạt — 0 vi phạm' if not sv else f'❌ {len(sv)} vi phạm'} |"]
    cons = (R / "consistency.txt").read_text(encoding="utf-8").splitlines() if (R / "consistency.txt").exists() else []
    n_incons = int(cons[1].split()[0]) if len(cons) > 1 else -1
    L.append(f"| Nhất quán logic OWL 2 RL (disjoint, functional, AllDifferent) | gold | "
             f"{'✅ nhất quán' if n_incons == 0 else f'❌ {n_incons} vi phạm'} |")
    shacl = read("shacl-report.csv")
    sev = Counter(r["severity"] for r in shacl)
    L.append(f"| SHACL (`shapes/vnedu-shapes.ttl`) | gold | {'✅ conforms' if not sev.get('Violation') else '❌'} — "
             f"{sev.get('Violation', 0)} vi phạm, {sev.get('Warning', 0)} cảnh báo, {sev.get('Info', 0)} thông tin |")
    if shacl:
        L += ["", "| Mức | Thông điệp SHACL | Số |", "|---|---|---|"]
        for (s, m), n in Counter((r["severity"], r["message"]) for r in shacl).most_common():
            L.append(f"| {s} | {m} | {n} |")

    gold = manifest.get("gold", {})
    links = gold.get("data/gold/vnedu-links.ttl", {}).get("linksets", {})
    L += ["", "## 6. Liên kết (5 sao)", "", "| Đích | Thuộc tính | Số liên kết |", "|---|---|---|"]
    for k, n in sorted(links.items(), key=lambda x: -x[1]):
        t, p = k.split("|")
        L.append(f"| {t} | `{p}` | {n} |")
    if (R / "link_evaluation.md").exists():
        L += ["", "Đánh giá phương pháp liên kết: xem [link_evaluation.md](link_evaluation.md) — so khớp chuỗi kiểu Silk "
              "so với liên kết theo định danh."]

    inferred = gold.get("data/gold/vnedu-inferred.ttl", {}).get("count", 0)
    total = gold.get("data/gold/vnedu-all.ttl", {}).get("count", 0)
    L += ["", "## 7. Checklist 5 sao", "", "| | Tiêu chí | Bằng chứng |", "|---|---|---|",
          "| ★ | Công khai, quyền tái sử dụng minh bạch | CC BY-SA 4.0 chỉ áp dụng cho phần dự án có quyền cấp phép; "
          "`dct:rights`, `LICENSE-DATA.md` và `*.meta.json` giữ điều kiện riêng của từng nguồn (nguồn Bộ GD&ĐT chưa "
          "công bố giấy phép dữ liệu mở dạng máy đọc được) |",
          "| ★★ | Có cấu trúc, máy đọc được | JSON (bronze/silver), RDF (gold) |",
          "| ★★★ | Định dạng mở | JSON, CSV, Turtle |",
          f"| ★★★★ | Chuẩn W3C, URI dereference được | RDF/OWL 2 RL/SHACL/SPARQL 1.1/PROV-O; {total:,} triple "
          f"(trong đó {inferred:,} suy luận); HTTP URI + content negotiation (`app/server.py`) |",
          f"| ★★★★★ | Liên kết tới dataset khác | {sum(links.values()):,} liên kết tới Wikidata, DBpedia, ROR, GeoNames, "
          "Wikipedia; `void:Linkset` |"]
    out = R / "quality_report.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  -> {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
