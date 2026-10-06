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
from common import PREFIXES, bind_prefixes, load_ontology  # noqa: E402

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
{% if lat %}<div id="minimap" style="height:220px;border-radius:12px;border:1px solid var(--line);margin:0 0 16px"></div>{% endif %}
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


def build_resources(onto, data, links, inferred, void, full) -> int:
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
        for p, o in po:
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
                              n_inf=n_inf, root=ROOT_PATH, lat=lat)
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
        text = text.replace("{{ROOT}}", ROOT_PATH).replace("{{BASE}}", BASE)
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
