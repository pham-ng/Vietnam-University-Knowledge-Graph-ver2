"""Web server cho VN-Edu LOD.

  /                 trang chủ: thống kê, tải dữ liệu, truy vấn mẫu
  /sparql           SPARQL 1.1 Protocol (GET/POST, ?query=...)
  /query            giao diện truy vấn YASGUI
  /resource/...     tra cứu URI (dereference) — HTML cho người, Turtle/JSON-LD/RDF-XML/N-Triples cho máy
  /ontology         ontology (HTML hoặc RDF)
  /dataset          mô tả VoID/DCAT
  /download/<file>  tải dump RDF
  /healthz          kiểm tra sống (cho giám sát / load balancer)

Backend:
  --backend local   rdflib nạp data/gold/vnedu-all.ttl vào bộ nhớ (không cần Fuseki)
  --backend fuseki  chuyển tiếp truy vấn tới Fuseki (config.FUSEKI_URL)
  --backend auto    (mặc định) dùng Fuseki nếu đang chạy, ngược lại dùng local

Chạy:
  py app/server.py                  máy chủ phát triển của Flask (chỉ dùng khi phát triển)
  py app/server.py --prod           máy chủ WSGI waitress (đa luồng, dùng khi triển khai)
  waitress-serve --call app.server:create_app    hoặc  gunicorn "app.server:create_app()"

An toàn (endpoint SPARQL mở cho công chúng):
  * SERVICE chỉ được gọi tới endpoint trong danh sách cho phép (Wikidata, DBpedia) — chống SSRF:
    nếu không, ai cũng có thể bắt máy chủ gửi yêu cầu tới địa chỉ nội bộ.
  * Không cho FROM / FROM NAMED (rdflib có thể tải URL bất kỳ).
  * Giới hạn độ dài truy vấn và thời gian chạy.
  * Đường dẫn /resource/... được kiểm tra theo mẫu URI của dataset trước khi đưa vào truy vấn — chống chèn SPARQL.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, Response, abort, render_template, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import config  # noqa: E402

log = logging.getLogger("vnedu.server")

QUERIES_DIR = config.ROOT / "queries"
RDF_MIME = {"text/turtle": "turtle", "application/ld+json": "json-ld",
            "application/rdf+xml": "xml", "application/n-triples": "nt"}
FMT_PARAM = {"ttl": "text/turtle", "jsonld": "application/ld+json", "rdf": "application/rdf+xml",
             "nt": "application/n-triples"}

# ------------------------------------------------------------------ giới hạn & kiểm tra đầu vào

MAX_QUERY_CHARS = int(os.environ.get("VNEDU_MAX_QUERY_CHARS", 20_000))
QUERY_TIMEOUT_S = float(os.environ.get("VNEDU_QUERY_TIMEOUT", 30))
ALLOWED_SERVICE_HOSTS = {"query.wikidata.org", "dbpedia.org"}
# URI tài nguyên của dataset: <loại>/<slug>, slug chỉ gồm chữ thường không dấu, số, gạch nối
RESOURCE_PATH = re.compile(r"^[a-z]+/[a-z0-9]+(?:-[a-z0-9]+)*$")
_COMMENT = re.compile(r"(?m)(^|\s)#[^\n]*")
_SERVICE = re.compile(r"\bSERVICE\s+(?:SILENT\s+)?(\S+)", re.I)
_FROM = re.compile(r"\bFROM\s+(?:NAMED\s+)?(<|[A-Za-z_][\w-]*:)", re.I)


class QueryRejected(ValueError):
    """Truy vấn bị từ chối vì lý do an toàn (trả về HTTP 400/413)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def check_query(query: str) -> None:
    """Ném QueryRejected nếu truy vấn vi phạm chính sách của endpoint công khai."""
    if len(query) > MAX_QUERY_CHARS:
        raise QueryRejected(f"Truy vấn dài quá {MAX_QUERY_CHARS} ký tự.", 413)
    body = _COMMENT.sub(r"\1", query)
    for target in _SERVICE.findall(body):
        m = re.match(r"<([^>]*)>", target)
        if not m:
            raise QueryRejected("SERVICE phải dùng IRI đầy đủ, ví dụ <https://query.wikidata.org/sparql>.")
        u = urlparse(m.group(1))
        if u.scheme not in ("http", "https") or u.hostname not in ALLOWED_SERVICE_HOSTS:
            raise QueryRejected(f"SERVICE chỉ được gọi tới: {', '.join(sorted(ALLOWED_SERVICE_HOSTS))}.")
    if _FROM.search(body):
        raise QueryRejected("Endpoint không hỗ trợ FROM / FROM NAMED (toàn bộ dữ liệu đã nằm trong graph mặc định).")


# ------------------------------------------------------------------ backends

class LocalBackend:
    """rdflib trong bộ nhớ. rdflib không tự ngắt truy vấn nên chạy trong luồng riêng có hạn thời gian."""
    name = "rdflib (bộ nhớ)"

    def __init__(self, path: Path = config.ALL_TTL):
        from rdflib import Graph
        log.info("Nạp %s ...", path.name)
        self.graph = Graph().parse(path)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="sparql")
        log.info("  %d triple", len(self.graph))

    def _run(self, query: str):
        fut = self.pool.submit(self.graph.query, query)
        try:
            res = fut.result(timeout=QUERY_TIMEOUT_S)
            if res.type == "SELECT" or res.type == "ASK":
                res.bindings  # buộc đánh giá hết trong giới hạn thời gian  # noqa: B018
            return res
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise QueryRejected(f"Truy vấn chạy quá {QUERY_TIMEOUT_S:.0f} giây.", 503) from None

    def protocol(self, query: str, accept: str) -> Response:
        res = self._run(query)
        if res.type in ("CONSTRUCT", "DESCRIBE"):
            mime = next((m for m in RDF_MIME if m in accept), "text/turtle")
            return Response(res.graph.serialize(format=RDF_MIME[mime]), mimetype=mime)
        if "text/csv" in accept:
            return Response(res.serialize(format="csv"), mimetype="text/csv")
        if "sparql-results+xml" in accept:
            return Response(res.serialize(format="xml"), mimetype="application/sparql-results+xml")
        return Response(res.serialize(format="json"), mimetype="application/sparql-results+json")

    def select(self, query: str) -> list[dict]:
        return json.loads(self._run(query).serialize(format="json"))["results"]["bindings"]

    def construct(self, query: str):
        return self._run(query).graph


class FusekiBackend:
    def __init__(self):
        self.endpoint = f"{config.FUSEKI_URL}/{config.FUSEKI_DATASET}/sparql"
        self.name = f"Apache Jena Fuseki ({self.endpoint})"
        self.session = requests.Session()

    def _post(self, query: str, accept: str) -> requests.Response:
        try:
            return self.session.post(self.endpoint, data={"query": query}, headers={"Accept": accept or "*/*"},
                                     timeout=QUERY_TIMEOUT_S)
        except requests.Timeout:
            raise QueryRejected(f"Truy vấn chạy quá {QUERY_TIMEOUT_S:.0f} giây.", 503) from None

    def protocol(self, query: str, accept: str) -> Response:
        r = self._post(query, accept)
        return Response(r.content, status=r.status_code, mimetype=r.headers.get("Content-Type", "text/plain"))

    def select(self, query: str) -> list[dict]:
        r = self._post(query, "application/sparql-results+json")
        r.raise_for_status()
        return r.json()["results"]["bindings"]

    def construct(self, query: str):
        from rdflib import Graph
        r = self._post(query, "text/turtle")
        r.raise_for_status()
        return Graph().parse(data=r.text, format="turtle")


def install_user_agent() -> None:
    """rdflib gọi SERVICE bằng urllib và GHI CỨNG User-Agent "rdflibForAnUser" — Wikidata trả HTTP 429 cho UA này
    (chính sách User-Agent của Wikimedia). Bộ xử lý urllib dưới đây ghi đè UA của mọi yêu cầu đi ra bằng UA có
    thông tin liên hệ của dự án, để truy vấn federated hoạt động trên máy chủ công khai."""
    import urllib.request

    class _ProjectUserAgent(urllib.request.BaseHandler):
        handler_order = 100

        def http_request(self, req):
            req.add_header("User-Agent", config.USER_AGENT)
            return req

        https_request = http_request

    urllib.request.install_opener(urllib.request.build_opener(_ProjectUserAgent()))


def fuseki_alive() -> bool:
    try:
        return requests.get(f"{config.FUSEKI_URL}/$/ping", timeout=2).ok
    except requests.RequestException:
        return False


# ------------------------------------------------------------------ helpers

def load_inferred() -> set[tuple[str, str, str]]:
    """Các triple do bộ suy luận sinh ra (để đánh dấu trên giao diện)."""
    from rdflib import Graph
    path = config.RDF_DIR / "vnedu-inferred.ttl"
    return {(str(s), str(p), str(o)) for s, p, o in Graph().parse(path)} if path.exists() else set()


@lru_cache(maxsize=1)
def example_queries() -> tuple[dict, ...]:
    out = []
    for f in sorted(QUERIES_DIR.glob("*.rq")):
        text = f.read_text(encoding="utf-8")
        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), f.stem)
        out.append({"file": f.name, "title": title, "federated": "SERVICE" in text})
    return tuple(out)


PREFIX_MAP = (("vnedu:", config.ONTO_NS), ("", config.RES_NS),
              ("rdf:", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
              ("rdfs:", "http://www.w3.org/2000/01/rdf-schema#"), ("owl:", "http://www.w3.org/2002/07/owl#"),
              ("skos:", "http://www.w3.org/2004/02/skos/core#"), ("foaf:", "http://xmlns.com/foaf/0.1/"),
              ("geo:", "http://www.w3.org/2003/01/geo/wgs84_pos#"), ("wd:", "http://www.wikidata.org/entity/"),
              ("dbr:", "http://dbpedia.org/resource/"), ("dbo:", "http://dbpedia.org/ontology/"),
              ("schema:", "https://schema.org/"), ("prov:", "http://www.w3.org/ns/prov#"),
              ("dct:", "http://purl.org/dc/terms/"), ("void:", "http://rdfs.org/ns/void#"),
              ("xsd:", "http://www.w3.org/2001/XMLSchema#"))


def short(uri: str) -> str:
    for prefix, ns in PREFIX_MAP:
        if uri.startswith(ns):
            return prefix + uri[len(ns):]
    return uri


def wants_rdf() -> str | None:
    if request.args.get("format") in FMT_PARAM:
        return FMT_PARAM[request.args["format"]]
    best = request.accept_mimetypes.best_match(["text/html", *RDF_MIME])
    return best if best in RDF_MIME else None


def group(rows, node_key: str, label_key: str, triple_of, inferred) -> list[dict]:
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
            "inferred": triple_of(p, n["value"]) in inferred,
        }
        g["values"].append(values[key])
    order = ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://www.w3.org/2000/01/rdf-schema#label"]
    return sorted(groups.values(), key=lambda g: (order.index(g["uri"]) if g["uri"] in order else 9,
                                                  g["uri"] in ("http://www.w3.org/2002/07/owl#sameAs",), g["short"]))


def rdf_response(graph, mime: str) -> Response:
    from common import bind_prefixes
    bind_prefixes(graph)
    return Response(graph.serialize(format=RDF_MIME[mime]), mimetype=mime)


# ------------------------------------------------------------------ ứng dụng

def create_app(backend=None, inferred: set | None = None) -> Flask:
    """Application factory (dùng cho waitress/gunicorn và cho test)."""
    if backend is None:
        backend = FusekiBackend() if fuseki_alive() else LocalBackend()
    inferred = load_inferred() if inferred is None else inferred
    install_user_agent()
    app = Flask(__name__)
    app.config["BACKEND"] = backend
    app.json.ensure_ascii = False

    @lru_cache(maxsize=1)
    def home_stats():
        """Thống kê trang chủ chỉ đổi khi dữ liệu đổi -> tính một lần."""
        stats = backend.select("""
            PREFIX vnedu: <%s>
            SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE {
              VALUES ?c { vnedu:HigherEducationInstitution vnedu:PublicInstitution vnedu:PrivateInstitution
                          vnedu:MemberInstitution vnedu:MilitaryInstitution vnedu:PoliceInstitution vnedu:Province
                          vnedu:FormerProvince vnedu:GoverningBody vnedu:InstitutionLeader vnedu:Alumnus vnedu:Major }
              ?s a ?c .
            } GROUP BY ?c""" % config.ONTO_NS)
        links = backend.select("""
            SELECT ?t (COUNT(*) AS ?n) WHERE {
              ?s <http://www.w3.org/2002/07/owl#sameAs>|<http://www.w3.org/2004/02/skos/core#closeMatch>|<http://xmlns.com/foaf/0.1/isPrimaryTopicOf> ?o .
              BIND(IF(CONTAINS(STR(?o), "wikidata"), "Wikidata", IF(CONTAINS(STR(?o), "dbpedia"), "DBpedia",
                   IF(CONTAINS(STR(?o), "geonames"), "GeoNames", IF(CONTAINS(STR(?o), "ror.org"), "ROR", "Wikipedia")))) AS ?t)
            } GROUP BY ?t ORDER BY DESC(?n)""")
        total = int(backend.select("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")[0]["n"]["value"])
        return {short(b["c"]["value"]): int(b["n"]["value"]) for b in stats}, links, total

    def describe(uri: str):
        """Các triple đi ra, đi vào (giới hạn) và nhãn của một tài nguyên. `uri` đã được kiểm tra bằng RESOURCE_PATH."""
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

    @app.before_request
    def _start_timer():
        request.environ["vnedu.t0"] = time.perf_counter()

    @app.after_request
    def _headers_and_log(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        t0 = request.environ.get("vnedu.t0")
        if t0 is not None:
            log.info("%s %s %d %.0fms", request.method, request.path, resp.status_code, 1000 * (time.perf_counter() - t0))
        return resp

    @app.errorhandler(404)
    def _not_found(_e):
        return Response("Không tìm thấy tài nguyên.", status=404, mimetype="text/plain; charset=utf-8")

    @app.errorhandler(Exception)
    def _internal(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        log.exception("Lỗi không lường trước")
        return Response("Lỗi máy chủ. Vui lòng thử lại sau.", status=500, mimetype="text/plain; charset=utf-8")

    @app.route("/")
    def home():
        counts, links, total = home_stats()
        dumps = [f.name for f in sorted(config.RDF_DIR.glob("*.ttl"))]
        return render_template("home.html", counts=counts, links=links, total=total, inferred=len(inferred),
                               queries=example_queries(), dumps=dumps, backend=backend.name, base=config.BASE)

    @app.route("/healthz")
    def healthz():
        try:
            ok = bool(backend.select("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"))
        except Exception:  # noqa: BLE001
            ok = False
        return {"status": "ok" if ok else "degraded", "backend": backend.name}, (200 if ok else 503)

    @app.route("/sparql", methods=["GET", "POST"])
    def sparql():
        q = request.values.get("query")
        if not q:
            return render_template("query.html", queries=example_queries(), initial=None)
        try:
            check_query(q)
            resp = backend.protocol(q, request.headers.get("Accept", ""))
        except QueryRejected as e:
            resp = Response(str(e), status=e.status, mimetype="text/plain; charset=utf-8")
        except Exception as e:  # noqa: BLE001 — lỗi cú pháp (pyparsing) của rdflib: thông báo có ích cho người dùng
            msg = str(e).splitlines()[0][:300] if str(e) else type(e).__name__
            resp = Response(f"Truy vấn không hợp lệ: {msg}", status=400, mimetype="text/plain; charset=utf-8")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @app.route("/query")
    def query_ui():
        name = request.args.get("file", "")
        known = {q["file"] for q in example_queries()}
        initial = (QUERIES_DIR / name).read_text(encoding="utf-8") if name in known else None
        return render_template("query.html", queries=example_queries(), initial=initial)

    @app.route("/queries/<name>")
    def query_file(name):
        return send_from_directory(QUERIES_DIR, name, mimetype="application/sparql-query")

    @app.route("/resource/<path:rest>")
    def resource(rest):
        if not RESOURCE_PATH.fullmatch(rest):
            abort(404)
        uri = config.RES_NS + rest
        mime = wants_rdf()
        if mime:
            g = backend.construct(f"CONSTRUCT {{ <{uri}> ?p ?o }} WHERE {{ <{uri}> ?p ?o }}")
            if not len(g):
                abort(404)
            resp = rdf_response(g, mime)
            resp.headers["Vary"] = "Accept"
            return resp
        out, inc = describe(uri)
        if not out and not inc:
            abort(404)
        props = group(out, "o", "ol", lambda p, v: (uri, p, v), inferred)
        labels = [v for g in props if g["short"] == "rdfs:label" for v in g["values"]]
        title = next((v["value"] for v in labels if v["lang"] == "vi"), labels[0]["value"] if labels else rest)
        resp = Response(render_template(
            "resource.html", uri=uri, title=title, kind=rest.split("/")[0], props=props,
            incoming=group(inc, "s", "sl", lambda p, v: (v, p, uri), inferred), base=config.BASE,
            n_inferred=sum(v["inferred"] for g in props for v in g["values"])))
        resp.headers["Vary"] = "Accept"
        return resp

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
        return rdf_response(Graph().parse(config.VOID_TTL), wants_rdf() or "text/turtle")

    @app.route("/download/<name>")
    def download(name):
        mime = {".ttl": "text/turtle", ".nt": "application/n-triples"}.get(Path(name).suffix, "application/octet-stream")
        return send_from_directory(config.RDF_DIR, name, mimetype=mime, as_attachment=True)

    @app.template_filter("short")
    def short_filter(uri):
        return short(uri)

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description="VN-Edu LOD web server")
    ap.add_argument("--backend", choices=["auto", "local", "fuseki"], default="auto")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))   # Render/Heroku cấp qua $PORT
    ap.add_argument("--prod", action="store_true", help="chạy bằng máy chủ WSGI waitress thay cho máy chủ phát triển")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    use_fuseki = args.backend == "fuseki" or (args.backend == "auto" and fuseki_alive())
    app = create_app(FusekiBackend() if use_fuseki else LocalBackend())
    log.info("Backend: %s — mở http://%s:%d/", app.config["BACKEND"].name, args.host, args.port)
    if args.prod:
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=8)
    else:
        app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
