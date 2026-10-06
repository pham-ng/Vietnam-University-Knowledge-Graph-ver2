"""BƯỚC 7 — Công bố: sinh site tĩnh cho GitHub Pages (https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/) -> site/

Mỗi URI của dataset đều DEREFERENCE được trên Web (nguyên tắc Linked Data 2 & 3):
  <BASE>resource/university/dai-hoc-bach-khoa-ha-noi        -> trang HTML (người đọc) có nhúng JSON-LD (máy đọc)
  <BASE>resource/university/dai-hoc-bach-khoa-ha-noi.ttl    -> Turtle
  <BASE>resource/university/dai-hoc-bach-khoa-ha-noi.jsonld -> JSON-LD
  <BASE>ontology  (+ .ttl/.jsonld),  <BASE>ontology#Lop -> mục tương ứng trong tài liệu ontology
  <BASE>dataset   (VoID + DCAT),     <BASE>download/*.ttl -> dump đầy đủ
(GitHub Pages không có content negotiation phía máy chủ: máy đọc lấy JSON-LD nhúng trong HTML — chuẩn JSON-LD 1.1 —
hoặc thêm đuôi .ttl/.jsonld; trang HTML có <link rel="alternate"> trỏ tới các bản RDF.)

Kèm ứng dụng: thống kê, bản đồ, tra cứu, cây ontology, SPARQL chạy trong trình duyệt (Oxigraph WASM).
"""
import html
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import PREFIXES, bind_prefixes, load_ontology, vn_key  # noqa: E402

SITE = config.ROOT / "site"
SRC = config.ROOT / "site_src"
BASE = config.BASE
ROOT_PATH = urlparse(BASE).path            # "/Vietnam-University-Knowledge-Graph-ver2/"
REPO = "https://github.com/pham-ng/Vietnam-University-Knowledge-Graph-ver2"
INFERRED_TTL = config.GOLD_DIR / "vnedu-inferred.ttl"
CONTEXT = {p: str(ns) for p, ns in PREFIXES.items()} | {"prov": "http://www.w3.org/ns/prov#"}
HEI_KINDS = {"University", "UniversitySchool", "Academy", "OfficerSchool", "NationalUniversity",
             "RegionalUniversity", "HigherEducationInstitution"}
KIND_VI = {"University": "Đại học", "UniversitySchool": "Trường đại học", "Academy": "Học viện",
           "OfficerSchool": "Trường sĩ quan", "NationalUniversity": "Đại học quốc gia",
           "RegionalUniversity": "Đại học vùng", "HigherEducationInstitution": "Đơn vị GDĐH khác",
           "Branch": "Phân hiệu", "VocationalCollege": "Cao đẳng", "Seminary": "Chủng viện",
           "Institute": "Viện", "AcademicUnit": "Khoa"}

env = Environment(autoescape=True)

LAYOUT = env.from_string("""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<meta name="description" content="{{ desc }}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{{ root }}assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230f6e64'/><text x='16' y='22' font-size='16' text-anchor='middle' fill='white' font-family='sans-serif' font-weight='700'>VN</text></svg>">
{% for alt in alternates %}<link rel="alternate" type="{{ alt[0] }}" href="{{ alt[1] }}">
{% endfor %}{{ head|safe }}
<script src="{{ root }}assets/common.js"></script>
</head>
<body>
<header class="top"><div class="bar">
  <a class="brand" href="{{ root }}">VN-Edu <span>LOD</span></a>
  <nav class="main">
    {% for href, label in nav %}<a href="{{ root }}{{ href }}" class="{{ 'on' if active == href else '' }}">{{ label }}</a>{% endfor %}
  </nav>
  <button class="theme-btn" type="button" aria-label="Đổi giao diện sáng/tối">◐ Giao diện</button>
</div></header>
<main class="{{ main_class }}">{{ body|safe }}</main>
<footer>Dữ liệu liên kết mở về giáo dục đại học Việt Nam · <a href="{{ root }}dataset">VoID/DCAT</a> ·
<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a> · nguồn: Wikidata (CC0), Wikipedia tiếng Việt (CC BY-SA)
· <a href="{{ repo }}">mã nguồn</a></footer>
</body>
</html>""")
NAV = [("", "Tổng quan"), ("map", "Bản đồ"), ("explore", "Tra cứu"), ("ontology", "Ontology"),
       ("sparql", "SPARQL"), ("dataset", "Dataset"), ("about", "Giới thiệu"), ("demo", "Demo")]


def page(path: str, title: str, body: str, active: str = "", head: str = "", desc: str = "",
         alternates=(), main_class: str = "") -> None:
    out = SITE / (path + ".html" if path else "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(LAYOUT.render(title=title, body=body, active=active, head=head, desc=desc or title,
                                 alternates=alternates, root=ROOT_PATH, nav=NAV, repo=REPO, main_class=main_class),
                   encoding="utf-8")


# ---------------------------------------------------------------- tải dữ liệu

def load_graphs():
    onto = load_ontology()
    data = Graph().parse(config.DATA_TTL)
    links = Graph().parse(config.LINKS_TTL)
    inferred = Graph().parse(INFERRED_TTL)
    void = Graph().parse(config.VOID_TTL)
    full = Graph()
    for g in (onto, data, links, inferred, void):
        full += g
    bind_prefixes(full)
    return onto, data, links, inferred, void, full


def short(g: Graph, u) -> str:
    try:
        return g.namespace_manager.normalizeUri(u)
    except Exception:  # noqa: BLE001
        return str(u)


def best_label(g: Graph, u):
    labs = list(g.objects(u, RDFS.label))
    for lang in ("vi", "en", None):
        for l in labs:
            if getattr(l, "language", None) == lang:
                return str(l)
    return None


def local_href(u: str) -> str | None:
    """URI thuộc dataset -> đường dẫn trên site (không đuôi, đúng như URI)."""
    if u.startswith(BASE):
        return ROOT_PATH + u[len(BASE):]
    return None


# ---------------------------------------------------------------- trang tài nguyên

RES_TPL = env.from_string("""
<p class="sub" style="margin:0 0 4px">{{ kind }}</p>
<h1>{{ title }}</h1>
<p class="uri">{{ uri }}<br>
  <a href="{{ slug }}.ttl">Turtle</a> · <a href="{{ slug }}.jsonld">JSON-LD</a> ·
  <a href="{{ root }}sparql?describe={{ uri|urlencode }}">Truy vấn SPARQL</a>
  {% if n_inf %} · <span class="pill inf">suy luận</span> = {{ n_inf }} giá trị do bộ suy luận OWL 2 RL sinh ra{% endif %}</p>
{% if panel %}<div class="res-grid"><div class="res-main">{{ panel.article|safe }}</div>{{ panel.aside|safe }}</div>
<h2>Toàn bộ dữ kiện RDF</h2>
{% elif lat %}<div id="minimap" style="height:220px;border-radius:12px;border:1px solid var(--line);margin:0 0 16px"></div>{% endif %}
<div class="card table-wrap"><table>
<tr><th>Thuộc tính</th><th>Giá trị</th></tr>
{% for g in props %}<tr><td class="p">{{ g.label }}<small>{{ g.short }}</small></td><td>
{% for v in g.vals[:80] %}<div>{{ v|safe }}</div>{% endfor %}
{% if g.vals|length > 80 %}<div class="lang">… và {{ g.vals|length - 80 }} giá trị khác</div>{% endif %}</td></tr>
{% endfor %}</table></div>
{% if incoming %}<h2>Được tham chiếu bởi</h2><div class="card table-wrap"><table>
{% for g in incoming %}<tr><td class="p">{{ g.label }}<small>{{ g.short }}</small></td><td>
{% for v in g.vals[:60] %}<div>{{ v|safe }}</div>{% endfor %}
{% if g.vals|length > 60 %}<div class="lang">… và {{ g.vals|length - 60 }} thực thể khác</div>{% endif %}</td></tr>
{% endfor %}</table></div>{% endif %}
""")


def render_value(full, o, inferred_flag: bool) -> str:
    if isinstance(o, Literal):
        s = html.escape(str(o))
        if o.language:
            s += f' <span class="lang">@{o.language}</span>'
        elif o.datatype:
            s += f' <span class="lang">{html.escape(short(full, o.datatype))}</span>'
    else:
        u = str(o)
        lab = best_label(full, o) or short(full, o)
        href = local_href(u) or (u.replace(BASE + "ontology#", ROOT_PATH + "ontology#") if u.startswith(BASE) else u)
        ext = "" if u.startswith(BASE) else ' <span class="pill ext">ngoài</span>'
        s = f'<a href="{html.escape(href)}">{html.escape(lab)}</a>{ext}'
    if inferred_flag:
        s += ' <span class="pill inf" title="Sinh ra bởi bộ suy luận OWL 2 RL">suy luận</span>'
    return s


def vn_date(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{int(dd)} tháng {int(m)} năm {y}"


def institution_panels() -> dict[str, dict]:
    """URI cơ sở -> {aside: infobox HTML, article: giới thiệu + lịch sử HTML}. Dữ liệu lấy từ tầng silver (cùng nguồn với RDF)."""
    load = lambda n: json.loads((config.SILVER_DIR / f"{n}.json").read_text(encoding="utf-8"))  # noqa: E731
    insts, bodies, provs, people, umap = (load("institutions"), load("governing_bodies"), load("provinces"),
                                          load("people"), load("uri_map"))
    esc = html.escape

    def a(uri, text):
        return f'<a href="{esc(local_href(uri) or uri)}">{esc(text)}</a>'

    def person(l):
        pk = l["qid"] or "name:" + vn_key(l["name"])
        u = umap["person"].get(pk)
        hon = people.get(pk, {}).get("honorific") or l.get("honorific") or ""
        name = a(u, l["name"]) if u else esc(l["name"])
        return (f'<span class="lang">{esc(hon)}</span> ' if hon else "") + name

    def figure(m, alt, cls):
        if not m:
            return ""
        cap = " · ".join(x for x in (esc(m.get("license") or ""), esc((m.get("artist") or "")[:80])) if x)
        return (f'<figure class="{cls}"><a href="{esc(m.get("page") or m["url"])}" title="Trang mô tả tệp trên Wikimedia">'
                f'<img src="{esc(m.get("thumb") or m["url"])}" alt="{esc(alt)}" loading="lazy"></a>'
                f'<figcaption>{cap or "Wikimedia"}</figcaption></figure>')

    out = {}
    for k, i in insts.items():
        uri = umap["institution"][k]
        rows = []

        def row(label, val):
            if val:
                rows.append(f"<tr><th>{label}</th><td>{val}</td></tr>")

        row("Tên khác", "<br>".join(esc(x) for x in i.get("alt_names", [])))
        row("Tên tiếng Anh", esc(i.get("name_en") or ""))
        row("Viết tắt", esc(", ".join(i["short_names"])))
        row("Mã trường", esc(", ".join(i["admission_codes"])))
        row("Tên cũ", "<br>".join(esc(x) for x in i["former_names"][:6]))
        own = {"public": "Công lập", "private": "Tư thục"}.get(i.get("ownership"), "")
        row("Loại hình", esc(" · ".join(x for x in (KIND_VI.get(i["kind"], ""), own) if x)))
        fy, fd = i.get("founding_year"), i.get("founding_date")
        if fd:
            row("Thành lập", esc(vn_date(fd)) + (f' <span class="lang">(mốc sớm nhất giữa các nguồn: {fy})</span>'
                                                  if fy and str(fy) != fd[:4] else ""))
        elif fy:
            row("Thành lập", str(fy))
        if i.get("dissolution_year"):
            row("Giải thể / sáp nhập", str(i["dissolution_year"]))
        row("Chủ quản", "<br>".join(a(umap["body"][b], bodies[b]["name_vi"]) for b in i["governed_by"]))
        row("Tổ chức mẹ", "<br>".join(a(umap["body"][b], bodies[b]["name_vi"]) for b in i["owned_by"]))
        row("Thành viên của", "<br>".join(a(umap["institution"][m], insts[m]["name_vi"]) for m in i["member_of"]))
        row("Phân hiệu của", "<br>".join(a(umap["institution"][m], insts[m]["name_vi"]) for m in i["branch_of"]))
        for role, label in (("rector", "Hiệu trưởng"), ("director", "Giám đốc"), ("chair", "Chủ tịch hội đồng trường")):
            row(label, "<br>".join(person(l) for l in i["leaders"] if l["role"] == role))
        qid_inst = {x["qid"]: kk for kk, x in insts.items() if x.get("qid")}
        row("Đối tác", "<br>".join(
            a(umap["institution"][qid_inst[pt["qid"]]], pt["name"]) if pt["qid"] in qid_inst else
            f'<a href="https://www.wikidata.org/wiki/{pt["qid"]}">{esc(pt["name"])}</a> <span class="pill ext">Wikidata</span>'
            for pt in i.get("partners", [])))
        row("Địa chỉ", esc(i.get("address") or ""))
        pq = i.get("province")
        if pq:
            pr = provs[pq]
            cur = provs[pr["merged_into"]] if pr["status"] == "former" else None
            val = a(umap["province"][pq], pr["name_vi"])
            if cur:
                val += f' → {a(umap["province"][pr["merged_into"]], cur["name_vi"])} <span class="lang">(từ 7/2025)</span>'
            row("Tỉnh/thành", val)
        row("Khuôn viên", esc(i.get("campus") or ""))
        row("Tài trợ / ngân sách", esc(i.get("funding") or ""))
        row("Sinh viên", f'{i["students"]:,}'.replace(",", ".") if i.get("students") else "")
        row("Giảng viên", f'{i["academic_staff"]:,}'.replace(",", ".") if i.get("academic_staff") else "")
        row("Khẩu hiệu", f'<i>{esc(i["motto_vi"])}</i>' if i.get("motto_vi") else "")
        row("Điện thoại", esc(i.get("telephone") or ""))
        row("Email", f'<a href="mailto:{esc(i["email"])}">{esc(i["email"])}</a>' if i.get("email") else "")
        row("Website", f'<a href="{esc(i["website"])}">{esc(re.sub(r"^https?://(www\.)?|/$", "", i["website"]))}</a>'
            if i.get("website") else "")
        aside = (f'<aside class="ibox"><div class="ibox-title">{esc(i["name_vi"])}</div>'
                 + figure(i.get("logo"), "Biểu trưng " + i["name_vi"], "ibox-logo")
                 + f'<table>{"".join(rows)}</table>'
                 + figure(i.get("image"), "Ảnh " + i["name_vi"], "ibox-photo")
                 + ('<div id="minimap" class="ibox-map"></div>' if i.get("lat") else "")
                 + "</aside>")

        art = []
        if i.get("abstract"):
            art.append(f'<h2>Giới thiệu chung</h2><p>{esc(i["abstract"])}</p>')
        if i.get("history"):
            paras = [f"<p>{esc(x)}</p>" for x in i["history"].split("\n\n")]
            body = "".join(paras[:2])
            if len(paras) > 2:
                body += f'<details><summary>Đọc tiếp ({len(paras) - 2} đoạn)</summary>{"".join(paras[2:])}</details>'
            art.append(f"<h2>Lịch sử</h2>{body}")
        if art and i.get("viwiki"):
            rev = i.get("viwiki_revid")
            src = f"https://vi.wikipedia.org/w/index.php?oldid={rev}" if rev else \
                f"https://vi.wikipedia.org/wiki/{i['viwiki'].replace(' ', '_')}"
            art.append(f'<p class="src">Văn bản trích từ bài <a href="{esc(src)}">«{esc(i["viwiki"])}»</a> trên Wikipedia '
                       f'tiếng Việt{f" (bản sửa đổi {rev})" if rev else ""}, giấy phép '
                       f'<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.vi">CC BY-SA 4.0</a>. '
                       f'Trong RDF: <code>dbo:abstract</code>, <code>vnedu:history</code>.</p>')
        out[uri] = {"aside": aside, "article": "".join(art)}
    return out


SCHEMA_NS = "https://schema.org/"
MEDIA_PROPS = {URIRef(SCHEMA_NS + "logo"), URIRef(SCHEMA_NS + "image")}
LONG_TEXT = {URIRef("http://dbpedia.org/ontology/abstract"), URIRef(config.ONTO_NS + "history")}


def build_resources(onto, data, links, inferred, void, full) -> int:
    panels = institution_panels()
    pred_label = {p: best_label(onto, p) for p in set(full.predicates())}
    inf = set(inferred)
    out_by_s, in_by_o = defaultdict(list), defaultdict(list)
    for s, p, o in full:
        if isinstance(s, URIRef) and str(s).startswith(BASE) and "#" not in str(s):
            out_by_s[s].append((p, o))
        if isinstance(o, URIRef) and str(o).startswith(BASE) and isinstance(s, URIRef) and str(s).startswith(BASE):
            in_by_o[o].append((p, s))
    pub = Graph()     # phần được mô tả (CBD) của mỗi tài nguyên = data + links + inferred + void
    for g in (data, links, inferred, void):
        pub += g
    order = [RDF.type, RDFS.label, SKOS.prefLabel]
    n = 0
    for s, po in out_by_s.items():
        rel = str(s)[len(BASE):]
        if rel.startswith("download/") or rel in ("ontology",) or rel.startswith("ontology/"):
            continue
        groups = defaultdict(list)
        n_inf = 0
        panel = panels.get(str(s))
        for p, o in po:
            if panel and p in LONG_TEXT:
                continue
            flag = (s, p, o) in inf
            n_inf += flag
            groups[p].append(render_value(full, o, flag))
        props = [{"label": pred_label.get(p) or short(full, p), "short": short(full, p), "vals": sorted(set(v))}
                 for p, v in groups.items()]
        props.sort(key=lambda g: (next((i for i, x in enumerate(order) if short(full, x) == g["short"]), 9),
                                  g["short"] == "owl:sameAs", g["short"]))
        inc = defaultdict(list)
        for p, x in in_by_o.get(s, []):
            inc[p].append(render_value(full, x, (x, p, s) in inf))
        incoming = [{"label": pred_label.get(p) or short(full, p), "short": short(full, p), "vals": sorted(set(v))}
                    for p, v in inc.items()]
        # RDF của tài nguyên
        cbd = Graph()
        bind_prefixes(cbd)
        cbd.bind("prov", "http://www.w3.org/ns/prov#")
        for p, o in po:
            if (s, p, o) in pub:
                cbd.add((s, p, o))
                if isinstance(o, URIRef) and not str(o).startswith(BASE) and (p in MEDIA_PROPS or str(p).endswith("affiliation")):
                    for p2, o2 in pub.predicate_objects(o):
                        cbd.add((o, p2, o2))
        jsonld = cbd.serialize(format="json-ld", context=CONTEXT, indent=1)
        out = SITE / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        (SITE / (rel + ".ttl")).write_text(cbd.serialize(format="turtle"), encoding="utf-8")
        (SITE / (rel + ".jsonld")).write_text(jsonld, encoding="utf-8")
        title = best_label(full, s) or rel
        kinds = [best_label(onto, t) for t in full.objects(s, RDF.type) if str(t).startswith(config.ONTO_NS)]
        lat, lon = full.value(s, URIRef("http://www.w3.org/2003/01/geo/wgs84_pos#lat")), \
            full.value(s, URIRef("http://www.w3.org/2003/01/geo/wgs84_pos#long"))
        head = f'<script type="application/ld+json">{jsonld}</script>'
        if lat is not None:
            head += ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
                     '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>'
                     f'<script>addEventListener("DOMContentLoaded",()=>{{const m=L.map("minimap",{{scrollWheelZoom:false}})'
                     f'.setView([{float(lat)},{float(lon)}],15);L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",'
                     f'{{attribution:"© OpenStreetMap"}}).addTo(m);L.circleMarker([{float(lat)},{float(lon)}],{{radius:8,color:"#0f6e64"}}).addTo(m)}})</script>')
        body = RES_TPL.render(kind=", ".join(sorted({k for k in kinds if k}))[:160] or rel.split("/")[0],
                              title=title, uri=str(s), slug=rel.rsplit("/", 1)[-1], props=props, incoming=incoming,
                              n_inf=n_inf, root=ROOT_PATH, lat=lat, panel=panel)
        page(rel, f"{title} · VN-Edu LOD", body, head=head, desc=f"{title} — dữ liệu liên kết mở VN-Edu",
             alternates=[("text/turtle", rel.rsplit('/', 1)[-1] + ".ttl"),
                         ("application/ld+json", rel.rsplit('/', 1)[-1] + ".jsonld")])
        n += 1
    return n


# ---------------------------------------------------------------- dữ liệu cho ứng dụng

def app_data(full, onto) -> dict:
    load = lambda n: json.loads((config.SILVER_DIR / f"{n}.json").read_text(encoding="utf-8"))  # noqa: E731
    insts, bodies, provs, umap = load("institutions"), load("governing_bodies"), load("provinces"), load("uri_map")
    V = config.ONTO_NS
    types = defaultdict(set)
    for s, t in full.subject_objects(RDF.type):
        if str(t).startswith(V):
            types[str(s)].add(str(t)[len(V):])

    def cur(q):
        p = provs.get(q)
        return p["merged_into"] if p and p["status"] == "former" else q

    rows = []
    for k, i in insts.items():
        u = umap["institution"][k]
        pq = i.get("province")
        cq = cur(pq) if pq else None
        rows.append({
            "uri": u, "href": local_href(u), "name": i["name_vi"], "en": i["name_en"], "kind": i["kind"],
            "kindVi": KIND_VI[i["kind"]], "hei": i["kind"] in HEI_KINDS,
            "own": i.get("ownership"), "year": i.get("founding_year"), "end": i.get("dissolution_year"),
            "prov": provs[cq]["name_vi"] if cq else None, "provOld": provs[pq]["name_vi"] if pq and pq != cq else None,
            "region": provs[cq]["region"] if cq else None,
            "lat": i.get("lat"), "lon": i.get("long"), "coord": i.get("coord_source"),
            "codes": i["admission_codes"], "short": i["short_names"][:3], "web": i.get("website"),
            "gov": [bodies[b]["name_vi"] for b in i["governed_by"]],
            "member": [insts[m]["name_vi"] for m in i["member_of"]],
            "military": "MilitaryInstitution" in types[u], "police": "PoliceInstitution" in types[u],
            "logo": (i.get("logo") or {}).get("thumb"),
            "intro": bool(i.get("abstract")), "hist": bool(i.get("history")),
        })
    prov_rows = [{"name": p["name_vi"], "uri": umap["province"][q], "href": local_href(umap["province"][q]),
                  "region": p["region"], "lat": p["lat"], "lon": p["long"], "pop": p["population"], "area": p["area"],
                  "merged": sorted(pp["name_vi"] for pp in provs.values() if pp.get("merged_into") == q)}
                 for q, p in provs.items() if p["status"] == "current"]
    manifest = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    return {"institutions": rows, "provinces": prov_rows,
            "linksets": manifest["gold"]["data/gold/vnedu-links.ttl"].get("linksets", {}),
            "triples": {k.rsplit("/", 1)[-1]: v["count"] for k, v in manifest["gold"].items()},
            "shacl": manifest["gold"]["data/gold/vnedu-all.ttl"].get("shacl_results", {}),
            "consistent": manifest["gold"]["data/gold/vnedu-all.ttl"].get("consistent"),
            "people": len(umap["person"]), "bodies": len(bodies)}


def ontology_data(onto, full) -> dict:
    """Cây lớp + thông tin từng lớp/thuộc tính cho trang ontology."""
    V = config.ONTO_NS
    loc = lambda u: str(u)[len(V):] if str(u).startswith(V) else None  # noqa: E731

    def lab(u, lang):
        return next((str(o) for o in onto.objects(u, RDFS.label) if getattr(o, "language", None) == lang), "")

    def rdf_list(node):
        out = []
        while node and node != RDF.nil:
            out.append(onto.value(node, RDF.first))
            node = onto.value(node, RDF.rest)
        return out

    count = Counter(str(t) for t in full.objects(None, RDF.type))
    classes = {}
    for c in set(onto.subjects(RDF.type, OWL.Class)):
        if not loc(c):
            continue
        parents = [loc(x) for x in onto.objects(c, RDFS.subClassOf) if loc(x)]
        ext = [short(full, x) for x in onto.objects(c, RDFS.subClassOf) if isinstance(x, URIRef) and not loc(x)]
        definition = ""
        eq = onto.value(c, OWL.equivalentClass)
        if isinstance(eq, BNode) and onto.value(eq, OWL.intersectionOf) is not None:
            parts = []
            for x in rdf_list(onto.value(eq, OWL.intersectionOf)):
                if isinstance(x, URIRef):
                    parts.append(loc(x) or short(full, x))
                    parents.append(loc(x)) if loc(x) else None
                elif onto.value(x, OWL.hasValue) is not None:
                    parts.append(f"∋{loc(onto.value(x, OWL.onProperty))}.{{{loc(onto.value(x, OWL.hasValue))}}}")
            definition = "≡ " + " ⊓ ".join(parts)
        for b in onto.subjects(RDFS.subClassOf, c):
            if isinstance(b, BNode) and onto.value(b, OWL.intersectionOf) is not None:
                parts = []
                for x in rdf_list(onto.value(b, OWL.intersectionOf)):
                    if isinstance(x, URIRef):
                        parts.append(loc(x) or short(full, x))
                    elif onto.value(x, OWL.someValuesFrom) is not None:
                        f = onto.value(x, OWL.someValuesFrom)
                        parts.append(f"∃{loc(onto.value(x, OWL.onProperty))}.{loc(f) or short(full, f)}")
                definition = " ⊓ ".join(parts) + " ⊑ " + loc(c)
        disj = sorted({loc(x) for x in onto.objects(c, OWL.disjointWith) if loc(x)} |
                      {loc(y) for d in onto.subjects(RDF.type, OWL.AllDisjointClasses)
                       for y in rdf_list(onto.value(d, OWL.members)) if c in rdf_list(onto.value(d, OWL.members)) and y != c})
        classes[loc(c)] = {"id": loc(c), "vi": lab(c, "vi"), "en": lab(c, "en"), "comment": str(onto.value(c, RDFS.comment) or ""),
                           "parents": sorted(set(p for p in parents if p and p != loc(c))), "external": ext,
                           "defined": definition, "disjoint": disj, "count": count.get(str(c), 0)}
    props = []
    for kind, label in ((OWL.ObjectProperty, "object"), (OWL.DatatypeProperty, "data")):
        for p in sorted(set(onto.subjects(RDF.type, kind)), key=str):
            chars = [x for x, t in (("bắc cầu", OWL.TransitiveProperty), ("hàm", OWL.FunctionalProperty)) if (p, RDF.type, t) in onto]
            chains = [" ∘ ".join(loc(x) or "" for x in rdf_list(ch)) for ch in onto.objects(p, OWL.propertyChainAxiom)]
            props.append({"id": loc(p) or short(full, p), "kind": label, "vi": lab(p, "vi"), "en": lab(p, "en"),
                          "domain": loc(onto.value(p, RDFS.domain)) or (short(full, onto.value(p, RDFS.domain)) if onto.value(p, RDFS.domain) else ""),
                          "range": loc(onto.value(p, RDFS.range)) or (short(full, onto.value(p, RDFS.range)) if onto.value(p, RDFS.range) else ""),
                          "inverse": loc(onto.value(p, OWL.inverseOf)) or "", "super": [short(full, x) for x in onto.objects(p, RDFS.subPropertyOf)],
                          "chars": chars, "chains": chains,
                          "uses": sum(1 for _ in full.triples((None, p, None)))})
    return {"ns": V, "classes": classes, "properties": props}


# ---------------------------------------------------------------- main

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    shutil.copytree(SRC / "assets", SITE / "assets")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    print("Nạp đồ thị ...")
    onto, data, links, inferred, void, full = load_graphs()

    print("Dump & tệp RDF ...")
    (SITE / "download").mkdir()
    for f in (config.ALL_TTL, config.DATA_TTL, config.LINKS_TTL, INFERRED_TTL, config.VOID_TTL):
        shutil.copy(f, SITE / "download" / f.name)
    nt = SITE / "download" / "vnedu-all.nt"
    full.serialize(nt, format="nt", encoding="utf-8")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:   # nén ra ngoài rồi chuyển vào (tránh zip tự chứa chính nó)
        z = shutil.make_archive(str(Path(tmp) / "vnedu-lod-rdf"), "zip", SITE / "download")
        shutil.move(z, SITE / "download" / "vnedu-lod-rdf.zip")
    shutil.copy(config.ROOT / "shapes" / "vnedu-shapes.ttl", SITE / "download" / "vnedu-shapes.ttl")
    shutil.copy(config.SILVER_SCHEMA, SITE / "download" / "silver.schema.json")
    o = load_ontology()
    bind_prefixes(o)
    (SITE / "ontology.ttl").write_text(o.serialize(format="turtle"), encoding="utf-8")
    (SITE / "ontology.jsonld").write_text(o.serialize(format="json-ld", context=CONTEXT, indent=1), encoding="utf-8")
    (SITE / "dataset.ttl").write_text(void.serialize(format="turtle"), encoding="utf-8")

    print("Trang tài nguyên (dereference URI) ...", flush=True)
    n = build_resources(onto, data, links, inferred, void, full)
    print(f"  {n} tài nguyên × (HTML + .ttl + .jsonld)")

    print("Dữ liệu ứng dụng ...")
    (SITE / "data").mkdir()
    (SITE / "data" / "app.json").write_text(json.dumps(app_data(full, onto), ensure_ascii=False), encoding="utf-8")
    (SITE / "data" / "ontology.json").write_text(json.dumps(ontology_data(onto, full), ensure_ascii=False), encoding="utf-8")
    queries = [{"file": f.name, "title": f.read_text(encoding="utf-8").splitlines()[0].lstrip("# "),
                "text": f.read_text(encoding="utf-8")} for f in sorted((config.ROOT / "queries").glob("*.rq"))]
    (SITE / "data" / "queries.json").write_text(json.dumps(queries, ensure_ascii=False), encoding="utf-8")

    print("Trang ứng dụng ...")
    for tpl in sorted((SRC / "pages").glob("*.html")):
        name = tpl.stem
        text = tpl.read_text(encoding="utf-8")
        meta = dict(re.findall(r"<!--\s*(title|desc|main):\s*(.*?)\s*-->", "\n".join(text.split("\n")[:4])))
        head = ""
        if "<!--HEAD-->" in text:
            head, text = text.split("<!--HEAD-->", 1)[1].split("<!--/HEAD-->", 1)[0], text.split("<!--/HEAD-->", 1)[1]
        text = text.replace("{{ROOT}}", ROOT_PATH).replace("{{BASE}}", BASE).replace("{{SPARQL}}", config.PUBLIC_SPARQL)
        head = head.replace("{{ROOT}}", ROOT_PATH).replace("{{BASE}}", BASE)
        path = "" if name == "index" else name
        alts = [("text/turtle", "ontology.ttl"), ("application/ld+json", "ontology.jsonld")] if name == "ontology" else []
        page(path, meta.get("title", name), text, active=path, head=head, desc=meta.get("desc", ""),
             alternates=alts, main_class=meta.get("main", ""))
    # trang 404 + sitemap
    page("404", "Không tìm thấy · VN-Edu LOD", f'<h1>Không tìm thấy</h1><p>URI này không có trong dataset. '
         f'<a href="{ROOT_PATH}explore">Tra cứu</a> hoặc <a href="{ROOT_PATH}">về trang chủ</a>.</p>')
    urls = [BASE + p for p in ("", "map", "explore", "ontology", "sparql", "dataset", "about")] + \
           [BASE + str(p.relative_to(SITE).with_suffix("")).replace("\\", "/") for p in (SITE / "resource").rglob("*.html")]
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(f"<url><loc>{html.escape(u)}</loc></url>" for u in urls) + "\n</urlset>\n", encoding="utf-8")
    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file()) / 1e6
    print(f"  -> site/ ({sum(1 for _ in SITE.rglob('*') if _.is_file())} tệp, {size:.1f} MB)")
    print("Xong bước 7.")


if __name__ == "__main__":
    main()
