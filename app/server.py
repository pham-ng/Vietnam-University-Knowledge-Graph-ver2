"""Web server cho VN-Edu LOD (cổng 8000, trùng với config.BASE).

  /                 trang chủ: thống kê, tải dữ liệu, truy vấn mẫu
  /sparql           SPARQL endpoint chuẩn (GET/POST, ?query=...)
  /query            giao diện truy vấn YASGUI
  /resource/...     tra cứu URI (dereference) — HTML cho người, Turtle/JSON-LD cho máy
  /ontology         ontology (HTML hoặc Turtle)
  /dataset          mô tả VoID
  /download/<file>  tải dump RDF

Backend:
  --backend local   rdflib nạp data/gold/vnedu-all.ttl vào bộ nhớ (không cần Fuseki)
  --backend fuseki  chuyển tiếp truy vấn tới Fuseki (config.FUSEKI_URL)
  --backend auto    (mặc định) dùng Fuseki nếu đang chạy, ngược lại dùng local
"""
import argparse
import json
import sys
import threading
from pathlib import Path

import requests
from flask import Flask, Response, abort, render_template, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

app = Flask(__name__)
QUERIES_DIR = config.ROOT / "queries"
RDF_MIME = {"text/turtle": "turtle", "application/ld+json": "json-ld",
            "application/rdf+xml": "xml", "application/n-triples": "nt"}
FMT_PARAM = {"ttl": "text/turtle", "jsonld": "application/ld+json", "rdf": "application/rdf+xml",
             "nt": "application/n-triples"}


# ------------------------------------------------------------------ backends

class LocalBackend:
    name = "rdflib (bộ nhớ)"

    def __init__(self):
        from rdflib import Graph
        print(f"Nạp {config.ALL_TTL.name} ...")
        self.graph = Graph().parse(config.ALL_TTL)
        self.lock = threading.Lock()
        print(f"  {len(self.graph)} triple")

    def protocol(self, query: str, accept: str) -> Response:
        with self.lock:
            res = self.graph.query(query)
        if res.type in ("CONSTRUCT", "DESCRIBE"):
            mime = next((m for m in RDF_MIME if m in accept), "text/turtle")
            return Response(res.graph.serialize(format=RDF_MIME[mime]), mimetype=mime)
        if "text/csv" in accept:
            return Response(res.serialize(format="csv"), mimetype="text/csv")
        if "sparql-results+xml" in accept:
            return Response(res.serialize(format="xml"), mimetype="application/sparql-results+xml")
        return Response(res.serialize(format="json"), mimetype="application/sparql-results+json")

    def select(self, query: str) -> list[dict]:
        with self.lock:
            res = self.graph.query(query)
        return json.loads(res.serialize(format="json"))["results"]["bindings"]

    def construct(self, query: str):
        with self.lock:
            return self.graph.query(query).graph


class FusekiBackend:
    def __init__(self):
        self.endpoint = f"{config.FUSEKI_URL}/{config.FUSEKI_DATASET}/sparql"
        self.name = f"Apache Jena Fuseki ({self.endpoint})"

    def protocol(self, query: str, accept: str) -> Response:
        r = requests.post(self.endpoint, data={"query": query}, headers={"Accept": accept or "*/*"}, timeout=300)
        return Response(r.content, status=r.status_code, mimetype=r.headers.get("Content-Type", "text/plain"))

    def select(self, query: str) -> list[dict]:
        r = requests.post(self.endpoint, data={"query": query},
                          headers={"Accept": "application/sparql-results+json"}, timeout=120)
        r.raise_for_status()
        return r.json()["results"]["bindings"]

    def construct(self, query: str):
        from rdflib import Graph
        r = requests.post(self.endpoint, data={"query": query}, headers={"Accept": "text/turtle"}, timeout=120)
        r.raise_for_status()
        return Graph().parse(data=r.text, format="turtle")


def fuseki_alive() -> bool:
    try:
        return requests.get(f"{config.FUSEKI_URL}/$/ping", timeout=2).ok
    except requests.RequestException:
        return False


backend = None
INFERRED: set[tuple[str, str, str]] = set()   # các triple do bộ suy luận sinh ra (để đánh dấu trên giao diện)


def load_inferred() -> None:
    from rdflib import Graph
    path = config.RDF_DIR / "vnedu-inferred.ttl"
    if path.exists():
        INFERRED.update((str(s), str(p), str(o)) for s, p, o in Graph().parse(path))


# ------------------------------------------------------------------ helpers

def example_queries() -> list[dict]:
    out = []
    for f in sorted(QUERIES_DIR.glob("*.rq")):
        text = f.read_text(encoding="utf-8")
        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), f.stem)
        out.append({"file": f.name, "title": title, "federated": "SERVICE" in text})
    return out


def short(uri: str) -> str:
    for prefix, ns in (("vnedu:", config.ONTO_NS), ("", config.RES_NS),
                       ("rdf:", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
                       ("rdfs:", "http://www.w3.org/2000/01/rdf-schema#"), ("owl:", "http://www.w3.org/2002/07/owl#"),
                       ("skos:", "http://www.w3.org/2004/02/skos/core#"), ("foaf:", "http://xmlns.com/foaf/0.1/"),
                       ("geo:", "http://www.w3.org/2003/01/geo/wgs84_pos#"), ("wd:", "http://www.wikidata.org/entity/"),
                       ("dbr:", "http://dbpedia.org/resource/"), ("dct:", "http://purl.org/dc/terms/"),
                       ("void:", "http://rdfs.org/ns/void#"), ("xsd:", "http://www.w3.org/2001/XMLSchema#")):
        if uri.startswith(ns):
            return prefix + uri[len(ns):]
    return uri


def wants_rdf() -> str | None:
    if request.args.get("format") in FMT_PARAM:
        return FMT_PARAM[request.args["format"]]
    best = request.accept_mimetypes.best_match(["text/html", *RDF_MIME])
    return best if best in RDF_MIME else None


def describe(uri: str):
    """Mô tả 1 tài nguyên: các triple đi ra, triple đi vào (giới hạn) và nhãn."""
    out = backend.select(f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?p ?o ?ol ?pl WHERE {{
          <{uri}> ?p ?o .
          OPTIONAL {{ ?o rdfs:label ?ol }}
          OPTIONAL {{ ?p rdfs:label ?pl FILTER(LANG(?pl) = "vi") }}
        }}""")
    inc = backend.select(f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?s ?p ?sl ?pl WHERE {{
          ?s ?p <{uri}> .
          OPTIONAL {{ ?s rdfs:label ?sl }}
          OPTIONAL {{ ?p rdfs:label ?pl FILTER(LANG(?pl) = "vi") }}
        }} LIMIT 1000""")
    return out, inc


def group(rows, node_key: str, label_key: str, triple_of) -> list[dict]:
    groups: dict[str, dict] = {}
    values: dict[tuple, dict] = {}
    for b in rows:
        p = b["p"]["value"]
        n = b[node_key]
        lab = b.get(label_key)
        key = (p, n["value"], n.get("xml:lang"))
        if key in values:  # cùng giá trị, khác nhãn -> ưu tiên nhãn tiếng Việt
            if lab and lab.get("xml:lang") == "vi":
                values[key]["label"] = lab["value"]
            continue
        g = groups.setdefault(p, {"uri": p, "short": short(p), "label": b.get("pl", {}).get("value"), "values": []})
        values[key] = {
            "type": n["type"], "value": n["value"], "short": short(n["value"]) if n["type"] == "uri" else n["value"],
            "label": lab["value"] if lab else None, "lang": n.get("xml:lang"),
            "datatype": short(n["datatype"]) if "datatype" in n else None,
            "local": n["value"].startswith(config.BASE),
            "inferred": triple_of(p, n["value"]) in INFERRED,
        }
        g["values"].append(values[key])
    order = ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://www.w3.org/2000/01/rdf-schema#label"]
    return sorted(groups.values(), key=lambda g: (order.index(g["uri"]) if g["uri"] in order else 9,
                                                  g["uri"] in ("http://www.w3.org/2002/07/owl#sameAs",), g["short"]))


def rdf_response(graph, mime: str) -> Response:
    from common import bind_prefixes
    bind_prefixes(graph)
    return Response(graph.serialize(format=RDF_MIME[mime]), mimetype=mime)


# ------------------------------------------------------------------ routes

@app.route("/")
def home():
    stats = backend.select("""
        PREFIX vnedu: <%s>
        SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE {
          VALUES ?c { vnedu:HigherEducationInstitution vnedu:PublicInstitution vnedu:PrivateInstitution
                      vnedu:MemberInstitution vnedu:MilitaryInstitution vnedu:PoliceInstitution vnedu:Province
                      vnedu:FormerProvince vnedu:GoverningBody vnedu:InstitutionLeader vnedu:Alumnus vnedu:Major }
          ?s a ?c .
        } GROUP BY ?c""" % config.ONTO_NS)
    counts = {short(b["c"]["value"]): int(b["n"]["value"]) for b in stats}
    links = backend.select("""
        SELECT ?t (COUNT(*) AS ?n) WHERE {
          ?s <http://www.w3.org/2002/07/owl#sameAs>|<http://www.w3.org/2004/02/skos/core#closeMatch>|<http://xmlns.com/foaf/0.1/isPrimaryTopicOf> ?o .
          BIND(IF(CONTAINS(STR(?o), "wikidata"), "Wikidata", IF(CONTAINS(STR(?o), "dbpedia"), "DBpedia",
               IF(CONTAINS(STR(?o), "geonames"), "GeoNames", IF(CONTAINS(STR(?o), "ror.org"), "ROR", "Wikipedia")))) AS ?t)
        } GROUP BY ?t ORDER BY DESC(?n)""")
    total = backend.select("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")[0]["n"]["value"]
    inferred = len(INFERRED)
    dumps = [f.name for f in sorted(config.RDF_DIR.glob("*.ttl"))]
    return render_template("home.html", counts=counts, links=links, total=int(total), inferred=inferred, queries=example_queries(),
                           dumps=dumps, backend=backend.name, base=config.BASE)


@app.route("/sparql", methods=["GET", "POST"])
def sparql():
    q = request.values.get("query")
    if not q:
        return render_template("query.html", queries=example_queries(), initial=None)
    try:
        resp = backend.protocol(q, request.headers.get("Accept", ""))
    except Exception as e:  # lỗi cú pháp, lỗi SERVICE, ...
        return Response(f"Lỗi truy vấn: {e}", status=400, mimetype="text/plain; charset=utf-8")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/query")
def query_ui():
    name = request.args.get("file")
    initial = (QUERIES_DIR / Path(name).name).read_text(encoding="utf-8") if name and (QUERIES_DIR / Path(name).name).exists() else None
    return render_template("query.html", queries=example_queries(), initial=initial)


@app.route("/queries/<name>")
def query_file(name):
    return send_from_directory(QUERIES_DIR, name, mimetype="application/sparql-query")


@app.route("/resource/<path:rest>")
def resource(rest):
    uri = config.RES_NS + rest
    mime = wants_rdf()
    if mime:
        g = backend.construct(f"CONSTRUCT {{ <{uri}> ?p ?o }} WHERE {{ <{uri}> ?p ?o }}")
        if not len(g):
            abort(404)
        return rdf_response(g, mime)
    out, inc = describe(uri)
    if not out and not inc:
        abort(404)
    labels = [v for g in group(out, "o", "ol", lambda p, v: (uri, p, v)) if g["short"] == "rdfs:label" for v in g["values"]]
    title = next((v["value"] for v in labels if v["lang"] == "vi"), labels[0]["value"] if labels else rest)
    return render_template("resource.html", uri=uri, title=title, kind=rest.split("/")[0],
                           props=group(out, "o", "ol", lambda p, v: (uri, p, v)),
                           incoming=group(inc, "s", "sl", lambda p, v: (v, p, uri)), base=config.BASE,
                           n_inferred=sum(v["inferred"] for g in group(out, "o", "ol", lambda p, v: (uri, p, v)) for v in g["values"]))


@app.route("/ontology")
def ontology():
    from common import load_ontology
    g = load_ontology()
    mime = wants_rdf()
    if mime:
        return rdf_response(g, mime)
    from rdflib import OWL, RDF, RDFS, URIRef

    def label(t, lang):
        return next((str(o) for o in g.objects(t, RDFS.label) if getattr(o, "language", None) == lang), "")

    terms = []
    for kind in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
        for t in sorted(set(g.subjects(RDF.type, kind))):
            if not isinstance(t, URIRef) or not str(t).startswith(config.ONTO_NS):
                continue
            supers = [o for pred in (RDFS.subClassOf, RDFS.subPropertyOf, OWL.equivalentClass)
                      for o in g.objects(t, pred) if isinstance(o, URIRef)]
            terms.append({"t": str(t), "kind": str(kind), "name": str(t).split("#")[-1],
                          "vi": label(t, "vi"), "en": label(t, "en"),
                          "comment": str(g.value(t, RDFS.comment) or ""),
                          "supers": [short(str(o)) for o in supers],
                          "domain": short(str(g.value(t, RDFS.domain) or "")),
                          "range": short(str(g.value(t, RDFS.range) or ""))})
    return render_template("ontology.html", terms=terms, ns=config.ONTO_NS)


@app.route("/dataset")
@app.route("/dataset/<path:_rest>")
def dataset(_rest=None):
    from rdflib import Graph
    g = Graph().parse(config.VOID_TTL)
    return rdf_response(g, wants_rdf() or "text/turtle")


@app.route("/download/<name>")
def download(name):
    return send_from_directory(config.RDF_DIR, name, mimetype="text/turtle", as_attachment=True)


@app.template_filter("short")
def short_filter(uri):
    return short(uri)


def main() -> None:
    global backend
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["auto", "local", "fuseki"], default="auto")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    use_fuseki = args.backend == "fuseki" or (args.backend == "auto" and fuseki_alive())
    backend = FusekiBackend() if use_fuseki else LocalBackend()
    load_inferred()
    print(f"Backend: {backend.name}")
    print(f"Mở http://localhost:{args.port}/")
    app.run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
