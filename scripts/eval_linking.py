"""Đánh giá phương pháp liên kết: so khớp chuỗi kiểu Silk (Jaccard trên token) vs liên kết theo định danh.

Ground truth: owl:sameAs DBpedia sinh từ định danh (Wikidata QID -> DBpedia owl:sameAs), do cả hai phía
cùng tham chiếu một QID nên coi là chính xác.
Ứng viên: tên tiếng Anh của cơ sở so với rdfs:label@en của các tài nguyên DBpedia (cùng tập đích).
Với mỗi ngưỡng θ: liên kết mỗi cơ sở với ứng viên có điểm cao nhất nếu điểm ≥ θ, rồi tính precision/recall/F1.

Đầu ra: data/reports/link_evaluation.md
"""
import json
import re
import sys
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import OWL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from httpcache import sparql  # noqa: E402

REPORT = config.REPORTS_DIR / "link_evaluation.md"


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    silver = json.loads((config.SILVER_DIR / "institutions.json").read_text(encoding="utf-8"))
    umap = json.loads((config.SILVER_DIR / "uri_map.json").read_text(encoding="utf-8"))["institution"]
    name_en = {umap[k]: i["name_en"] for k, i in silver.items() if i.get("name_en")}

    links = Graph().parse(config.LINKS_TTL)
    truth = {str(s): str(o) for s, o in links.subject_objects(OWL.sameAs)
             if str(o).startswith("http://dbpedia.org/resource/") and str(s) in name_en}
    targets = sorted(set(truth.values()))
    labels = {}
    for i in range(0, len(targets), 80):
        vals = " ".join(f"<{t}>" for t in targets[i:i + 80])
        for r in sparql(config.DBPEDIA_SPARQL,
                        f'SELECT ?d ?l WHERE {{ VALUES ?d {{ {vals} }} ?d rdfs:label ?l FILTER(LANG(?l) = "en") }}'):
            labels[r["d"]] = r["l"]
    sources = [s for s in truth if truth[s] in labels]
    print(f"{len(sources)} cơ sở có tên tiếng Anh + liên kết DBpedia theo định danh; {len(labels)} nhãn DBpedia")

    best = {}
    for s in sources:
        scored = sorted(((jaccard(name_en[s], labels[t]), t) for t in labels), reverse=True)
        best[s] = scored[0]

    rows = []
    for theta in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        pred = {s: t for s, (sc, t) in best.items() if sc >= theta}
        tp = sum(1 for s, t in pred.items() if truth[s] == t)
        p = tp / len(pred) if pred else 0.0
        r = tp / len(sources)
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        rows.append((theta, len(pred), tp, len(pred) - tp, p, r, f1))

    wrong = [(name_en[s], labels[t], labels[truth[s]], sc) for s, (sc, t) in best.items()
             if sc >= 0.2 and t != truth[s]]
    wrong.sort(key=lambda x: -x[3])

    lines = ["# Đánh giá phương pháp liên kết", "",
             f"Tập đánh giá: **{len(sources)}** cơ sở GDĐH có tên tiếng Anh và liên kết DBpedia xác định theo định danh "
             "(Wikidata QID ↔ DBpedia `owl:sameAs`) — dùng làm *ground truth*.", "",
             "Phương pháp so sánh: so khớp chuỗi kiểu **Silk** — Jaccard trên token chữ thường của tên tiếng Anh với "
             "`rdfs:label@en` của DBpedia; chọn ứng viên điểm cao nhất nếu ≥ θ.", "",
             "| θ | số liên kết | đúng | sai | precision | recall | F1 |", "|---|---|---|---|---|---|---|"]
    for theta, n, tp, fp, p, r, f1 in rows:
        lines.append(f"| {theta:.1f} | {n} | {tp} | {fp} | {p:.1%} | {r:.1%} | {f1:.3f} |")
    lines += ["", "Liên kết theo định danh (phương pháp của dự án): precision **100%** theo định nghĩa, recall "
              f"= {len(sources)}/{len(sources)} trên tập này, và không cần chọn ngưỡng.", "",
              f"## Ví dụ liên kết SAI của so khớp chuỗi ở θ = 0.2 ({len(wrong)} trường hợp)", "",
              "| tên nguồn | bị nối tới (sai) | đúng ra phải là | điểm |", "|---|---|---|---|"]
    for a, b, c, sc in wrong[:25]:
        lines.append(f"| {a} | {b} | {c} | {sc:.2f} |")
    lines += ["", "Kết luận: tên các trường Việt Nam có nhiều token chung (*University*, *Hanoi*, *Ho Chi Minh City*, "
              "*Technology*…), nên so khớp chuỗi với ngưỡng thấp (như θ = 0.2 trong dự án smartphone tham khảo) sinh nhiều "
              "liên kết sai; ngưỡng cao lại bỏ sót. Vì vậy dự án ưu tiên liên kết theo định danh dùng chung (QID, ROR, "
              "GeoNames), chỉ dùng so khớp nhãn (kèm xác minh quốc gia) khi không có định danh."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for theta, n, tp, fp, p, r, f1 in rows:
        print(f"  θ={theta:.1f}: {n:4} liên kết, đúng {tp:4}, sai {fp:4}, P={p:.1%} R={r:.1%} F1={f1:.3f}")
    print(f"  -> {REPORT.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
