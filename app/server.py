"""Web server cho VN-Edu LOD.

  /                 trang chủ: thống kê, tải dữ liệu, truy vấn mẫu
  /sparql           SPARQL 1.1 Protocol (GET/POST, ?query=...)
  /query            giao diện truy vấn YASGUI
  /resource/...     tra cứu URI (dereference) — HTML cho người, Turtle/JSON-LD/RDF-XML/N-Triples cho máy
  /ontology         ontology (HTML hoặc RDF)
  /dataset          mô tả VoID/DCAT
  /download/<file>  tải dump RDF
  /healthz          kiểm tra sống (cho giám sát / load balancer)

Giao diện: nếu đã build site cho máy chủ (VNEDU_SITE_DIR=site_server VNEDU_SITE_ROOT=/ python scripts/step7_publish.py)
thì máy chủ phục vụ CHÍNH giao diện đầy đủ đó (giống GitHub Pages: infobox, bản đồ, tra cứu, cây ontology, demo) và
bổ sung phần chỉ máy chủ làm được (content negotiation, SPARQL endpoint, federated). Chưa build thì dùng giao diện
dự phòng đơn giản trong app/templates/.

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
import atexit
import multiprocessing
import queue
import secrets
import threading
import json
import logging
import mimetypes
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, Response, abort, make_response, render_template, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import config  # noqa: E402

log = logging.getLogger("vnedu.server")
SITE_DIR = config.ROOT / os.environ.get("VNEDU_SERVE_SITE", "site_server")
for _ext, _mime in ((".ttl", "text/turtle"), (".jsonld", "application/ld+json"), (".nt", "application/n-triples"),
                    (".rq", "application/sparql-query"), (".svg", "image/svg+xml")):
    mimetypes.add_type(_mime, _ext)

QUERIES_DIR = config.ROOT / "queries"
# CDN mà các trang trong site_src dùng (Oxigraph WASM, Leaflet, D3); CSP chỉ mở đúng các host này.
CDN_HOSTS = "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com"
RDF_MIME = {"text/turtle": "turtle", "application/ld+json": "json-ld",
            "application/rdf+xml": "xml", "application/n-triples": "nt"}
FMT_PARAM = {"ttl": "text/turtle", "jsonld": "application/ld+json", "rdf": "application/rdf+xml",
             "nt": "application/n-triples"}

# ------------------------------------------------------------------ giới hạn & kiểm tra đầu vào

MAX_QUERY_CHARS = int(os.environ.get("VNEDU_MAX_QUERY_CHARS", 20_000))
QUERY_TIMEOUT_S = float(os.environ.get("VNEDU_QUERY_TIMEOUT", 30))
MAX_RESULT_BYTES = int(os.environ.get("VNEDU_MAX_RESULT_BYTES", 8 * 1024 * 1024))
MAX_BODY_BYTES = int(os.environ.get("VNEDU_MAX_BODY_BYTES", MAX_QUERY_CHARS * 12))
# Thời gian một truy vấn được chờ worker rảnh trước khi nhận 503 (thay vì bị từ chối ngay).
QUEUE_WAIT_S = float(os.environ.get("VNEDU_QUEUE_WAIT", 5))
SELECT_MIME = ("application/sparql-results+json", "text/csv", "application/sparql-results+xml")
ALLOWED_SERVICE_URLS = {"https://query.wikidata.org/sparql", "https://dbpedia.org/sparql"}
# URI tài nguyên của dataset: <loại>/<slug>, slug chỉ gồm chữ thường không dấu, số, gạch nối
RESOURCE_PATH = re.compile(r"^[a-z]+/[a-z0-9]+(?:-[a-z0-9]+)*$")
# RDFLib's pyparsing grammar is lazily initialized and is not safe to initialize
# from several Waitress threads at once.  Parsing is short; serialize this gate,
# while query execution remains concurrent in the bounded worker pool.
QUERY_PARSE_LOCK = threading.Lock()


class QueryRejected(ValueError):
    """Truy vấn bị từ chối vì lý do an toàn (trả về HTTP 400/413)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class FixedWindowLimiter:
    """Small dependency-free per-client limiter for a public read-only endpoint.

    A reverse proxy remains the primary production control. This application-level
    limiter provides a safe fallback for a single process and makes overload visible
    to the caller instead of allowing unbounded query fan-out.
    """

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = max(0, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = int(time.time())
        bucket = now // self.window_seconds
        with self._lock:
            previous = self._windows.get(key)
            count = previous[1] if previous and previous[0] == bucket else 0
            if count >= self.limit:
                return False
            self._windows[key] = (bucket, count + 1)
            if len(self._windows) > 10_000:
                self._windows = {k: v for k, v in self._windows.items() if v[0] >= bucket}
            return True


def check_query(query: str) -> None:
    """Ném QueryRejected nếu truy vấn vi phạm chính sách của endpoint công khai."""
    if len(query) > MAX_QUERY_CHARS:
        raise QueryRejected(f"Truy vấn dài quá {MAX_QUERY_CHARS} ký tự.", 413)
    from pyparsing import ParseResults
    from rdflib import URIRef
    from rdflib.plugins.sparql.parser import parseQuery
    from rdflib.plugins.sparql.parserutils import CompValue

    # Validate syntax, not text: comments, literals and zero whitespace are legal SPARQL.
    def visit(node):
        if isinstance(node, CompValue):
            if node.name == "DatasetClause":
                raise QueryRejected("Endpoint không hỗ trợ FROM / FROM NAMED.")
            if node.name == "ServiceGraphPattern":
                term = node["term"]
                if not isinstance(term, URIRef) or str(term) not in ALLOWED_SERVICE_URLS:
                    raise QueryRejected("SERVICE phải dùng một endpoint HTTPS đầy đủ trong danh sách cho phép.")
            for value in node.values():
                visit(value)
        elif isinstance(node, (list, tuple, ParseResults)):
            for value in node:
                visit(value)

    with QUERY_PARSE_LOCK:
        visit(parseQuery(query))


def _query_worker(path, connection):
    """Load RDF once, then evaluate requests in a persistent, killable process."""
    from rdflib import Graph
    try:
        install_user_agent()
        graph = Graph().parse(path)
        connection.send(("ready", True, len(graph)))
        while True:
            task = connection.recv()
            if task is None:
                break
            query, mode, accept = task
            try:
                check_query(query)
                result = graph.query(query)
                # accept: các MIME client chấp nhận, đã xếp theo q giảm dần và bỏ q=0 (xem preferred_mimes)
                prefs = [m.strip() for m in accept.split(",") if m.strip()] if mode == "protocol" else []
                if result.type in ("CONSTRUCT", "DESCRIBE"):
                    mime = next((m for m in prefs if m in RDF_MIME), "text/turtle")
                    payload = result.graph.serialize(format=RDF_MIME[mime], encoding="utf-8")
                else:
                    allowed = SELECT_MIME if result.type == "SELECT" else SELECT_MIME[::2]   # ASK không có CSV
                    mime = next((m for m in prefs if m in allowed), SELECT_MIME[0])
                    fmt = {"application/sparql-results+json": "json", "text/csv": "csv",
                           "application/sparql-results+xml": "xml"}[mime]
                    payload = result.serialize(format=fmt)
                if len(payload) > MAX_RESULT_BYTES:
                    raise ValueError(
                        f"Result exceeds {MAX_RESULT_BYTES // (1024 * 1024)} MiB; use LIMIT or download the RDF dump.")
                connection.send(("result", True, mime, payload))
            except Exception as exc:  # noqa: BLE001 — lỗi được chuyển có cấu trúc về tiến trình web
                connection.send(("result", False, "", str(exc)))
    except Exception as exc:
        try:
            connection.send(("ready", False, str(exc)))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


# ------------------------------------------------------------------ backends

class LocalBackend:
    """RDFLib in bounded persistent workers; timed-out work is terminated."""
    name = "rdflib (persistent isolated worker)"

    def __init__(self, path: Path = config.ALL_TTL):
        self.path = Path(path).resolve()
        self.worker_count = max(1, int(os.environ.get("VNEDU_QUERY_WORKERS", "1")))
        self.context = multiprocessing.get_context("spawn")
        self.available = queue.Queue(maxsize=self.worker_count)
        self.workers: list[tuple[multiprocessing.Process, object]] = []
        self.pool_lock = threading.Lock()
        self.started = False
        self.closed = False
        atexit.register(self.close)

    def _spawn_worker(self):
        parent, child = self.context.Pipe(duplex=True)
        process = self.context.Process(target=_query_worker, args=(self.path, child), daemon=True)
        process.start()
        child.close()
        startup_timeout = float(os.environ.get("VNEDU_WORKER_STARTUP_TIMEOUT", max(120, QUERY_TIMEOUT_S * 4)))
        if not parent.poll(startup_timeout):
            process.terminate()
            process.join()
            parent.close()
            raise RuntimeError(f"RDF worker did not load {self.path.name} within {startup_timeout:g} seconds")
        kind, ok, detail = parent.recv()
        if kind != "ready" or not ok:
            process.join(timeout=1)
            if process.is_alive():
                process.terminate()
                process.join()
            parent.close()
            raise RuntimeError(f"RDF worker could not load {self.path.name}: {detail}")
        log.info("RDF worker %s ready with %s triples", process.pid, detail)
        return process, parent

    def warmup(self) -> None:
        """Start the bounded worker pool and parse the immutable release once."""
        with self.pool_lock:
            if self.started or self.closed:
                return
            self.started = True
            try:
                for _ in range(self.worker_count):
                    worker = self._spawn_worker()
                    self.workers.append(worker)
                    self.available.put_nowait(worker)
            except Exception:
                self.started = False
                self._close_workers()
                raise

    def _close_workers(self) -> None:
        for process, connection in self.workers:
            try:
                if process.is_alive():
                    connection.send(None)
                    process.join(timeout=1)
                if process.is_alive():
                    process.terminate()
                    process.join()
            except (BrokenPipeError, EOFError, OSError, ValueError):
                if process.is_alive():
                    process.terminate()
                    process.join()
            finally:
                connection.close()
                if process.pid is not None:
                    process.close()
        self.workers.clear()
        while True:
            try:
                self.available.get_nowait()
            except queue.Empty:
                break

    def close(self) -> None:
        with self.pool_lock:
            if self.closed:
                return
            self.closed = True
            self._close_workers()

    def _retire(self, worker) -> None:
        process, connection = worker
        with self.pool_lock:
            if worker in self.workers:
                self.workers.remove(worker)
        if process.is_alive():
            process.terminate()
            process.join()
        connection.close()
        if process.pid is not None:
            process.close()

    def _replace_async(self) -> None:
        def replace():
            try:
                worker = self._spawn_worker()
            except Exception:  # noqa: BLE001 — pool remains unavailable and the error is logged
                log.exception("Could not restart RDF worker")
                return
            with self.pool_lock:
                if self.closed:
                    process, connection = worker
                    if process.is_alive():
                        process.terminate()
                        process.join()
                    connection.close()
                    process.close()
                    return
                self.workers.append(worker)
                self.available.put_nowait(worker)

        threading.Thread(target=replace, name="vnedu-rdf-worker-restart", daemon=True).start()

    def pool_status(self) -> dict:
        """Số worker sống / đang rảnh — để /healthz phản ánh tình trạng pool mà không tốn truy vấn."""
        with self.pool_lock:
            alive = sum(1 for process, _ in self.workers if process.is_alive())
        return {"workers": self.worker_count, "alive": alive, "idle": self.available.qsize(), "started": self.started}

    def healthy(self) -> bool:
        """Constant-time readiness check for the validated, immutable RDF release.

        Running a SPARQL query here is deceptively expensive: the isolated local
        backend must start a child process and parse the complete dump.  Render
        probes every few seconds, so query-based probes overlap, exhaust all
        worker slots, and can prevent an otherwise healthy deployment from ever
        becoming ready.  RDF syntax and release hashes are checked by the build
        and CI quality gates; readiness only needs to verify that the selected
        release artifact is present and readable.
        """
        try:
            with self.path.open("rb") as stream:
                return self.path.stat().st_size > 0 and bool(stream.read(1))
        except OSError:
            return False

    def _execute(self, query: str, mode: str, accept: str = ""):
        self.warmup()
        try:
            worker = self.available.get(timeout=QUEUE_WAIT_S)
        except queue.Empty:
            raise QueryRejected("Máy chủ đang bận. Vui lòng thử lại sau.", 503) from None
        process, connection = worker
        reusable = False
        try:
            connection.send((query, mode, accept))
            if not connection.poll(QUERY_TIMEOUT_S):
                self._retire(worker)
                self._replace_async()
                raise QueryRejected(f"Truy vấn chạy quá {QUERY_TIMEOUT_S:g} giây.", 503)
            kind, ok, mime, payload = connection.recv()
            if kind != "result":
                raise RuntimeError("RDF worker returned an invalid response")
            reusable = True
            if not ok:
                raise ValueError(payload)
            return mime, payload
        except (EOFError, BrokenPipeError, OSError):
            if worker in self.workers:
                self._retire(worker)
                self._replace_async()
            raise QueryRejected("Tiến trình truy vấn đã dừng.", 503) from None
        finally:
            if reusable and process.is_alive():
                self.available.put_nowait(worker)

    def protocol(self, query: str, accept: str) -> Response:
        mime, payload = self._execute(query, "protocol", accept)
        return Response(payload, mimetype=mime)

    def select(self, query: str) -> list[dict]:
        return json.loads(self._execute(query, "select")[1])["results"]["bindings"]

    def construct(self, query: str):
        from rdflib import Graph
        return Graph().parse(data=self._execute(query, "construct")[1], format="turtle")


class FusekiBackend:
    def __init__(self):
        self.endpoint = f"{config.FUSEKI_URL}/{config.FUSEKI_DATASET}/sparql"
        self.name = f"Apache Jena Fuseki ({self.endpoint})"
        self.session = requests.Session()

    def healthy(self) -> bool:
        """Use Fuseki's inexpensive server ping for readiness."""
        try:
            return self.session.get(f"{config.FUSEKI_URL}/$/ping", timeout=2).ok
        except requests.RequestException:
            return False

    def _post(self, query: str, accept: str) -> requests.Response:
        try:
            return self.session.post(self.endpoint, data={"query": query, "timeout": int(QUERY_TIMEOUT_S * 1000)},
                                     headers={"Accept": accept or "*/*"}, timeout=QUERY_TIMEOUT_S,
                                     allow_redirects=False)
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
            target = urlparse(req.full_url)
            endpoint = f"{target.scheme}://{target.netloc}{target.path}"
            if endpoint not in ALLOWED_SERVICE_URLS or target.fragment:
                raise QueryRejected("Đích yêu cầu SERVICE không được phép.")
            req.add_header("User-Agent", config.USER_AGENT)
            return req

        https_request = http_request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise QueryRejected("SERVICE redirects are disabled.")

    urllib.request.install_opener(urllib.request.build_opener(_ProjectUserAgent(), _NoRedirect()))


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


def preferred_mimes(supported) -> str:
    """Các MIME trong `supported` mà client chấp nhận, theo q giảm dần; q=0 nghĩa là KHÔNG chấp nhận."""
    accept = request.accept_mimetypes
    if not accept:
        return ""
    ranked = sorted(((accept[m], -i, m) for i, m in enumerate(supported) if accept[m] > 0), reverse=True)
    return ", ".join(m for _, _, m in ranked)


def rdf_response(graph, mime: str) -> Response:
    from common import bind_prefixes
    bind_prefixes(graph)
    return Response(graph.serialize(format=RDF_MIME[mime]), mimetype=mime)


# ------------------------------------------------------------------ ứng dụng

def create_app(backend=None, inferred: set | None = None, site_dir: Path | None = SITE_DIR) -> Flask:
    """Application factory (dùng cho waitress/gunicorn và cho test)."""
    if backend is None:
        backend = FusekiBackend() if fuseki_alive() else LocalBackend()
    inferred = load_inferred() if inferred is None else inferred
    install_user_agent()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    app.config["BACKEND"] = backend
    app.config["RATE_LIMITER"] = FixedWindowLimiter(
        os.environ.get("VNEDU_RATE_LIMIT_PER_MINUTE", "0"), 60)
    cors_origins = {value.strip() for value in os.environ.get("VNEDU_CORS_ORIGINS", "*").split(",") if value.strip()}
    site = site_dir if site_dir and (site_dir / "index.html").exists() else None
    app.config["SITE"] = site
    if site:
        log.info("Giao diện: %s", site)

    def site_page(rel: str, status: int = 200):
        """Trả trang HTML đã build (rel không đuôi, ví dụ 'resource/university/x'); None nếu không có."""
        if site is None:
            return None
        f = site / (rel + ".html" if rel else "index.html")
        if not f.is_file():
            return None
        resp = send_from_directory(site, f.relative_to(site).as_posix(), mimetype="text/html")
        resp.status_code = status
        return resp
    app.json.ensure_ascii = False

    @lru_cache(maxsize=1)
    def home_stats():
        """Thống kê trang chủ chỉ đổi khi dữ liệu đổi -> tính một lần."""
        stats = backend.select("""
            PREFIX vnedu: <%s>
            SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE {
              VALUES ?c { vnedu:HigherEducationInstitution vnedu:PublicInstitution vnedu:PrivateInstitution
                          vnedu:MemberInstitution vnedu:MilitaryInstitution vnedu:PoliceInstitution vnedu:Province
                          vnedu:FormerProvince vnedu:GoverningBody vnedu:InstitutionLeader vnedu:EducationParticipant vnedu:Major }
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
        request.environ["vnedu.request_id"] = secrets.token_hex(8)
        if request.path == "/sparql" and request.method != "OPTIONS":
            client = request.remote_addr or "unknown"
            if not app.config["RATE_LIMITER"].allow(client):
                response = Response("Quá nhiều truy vấn; vui lòng thử lại sau.",
                                    status=429, content_type="text/plain; charset=utf-8")
                response.headers["Retry-After"] = "60"
                return response
        return None

    @app.after_request
    def _headers_and_log(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if resp.content_type.startswith("text/html"):
            resp.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                f"script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' {CDN_HOSTS}; "
                f"style-src 'self' 'unsafe-inline' {CDN_HOSTS} https://fonts.googleapis.com; "
                "img-src 'self' data: https:; font-src 'self' data: https:; worker-src 'self' blob:; "
                f"connect-src 'self' {CDN_HOSTS} https://query.wikidata.org https://dbpedia.org; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'",
            )
        if request.is_secure or os.environ.get("VNEDU_FORCE_HSTS") == "1":
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        resp.headers["X-Request-ID"] = request.environ.get("vnedu.request_id", "")
        if request.path == "/sparql":
            resp.headers.setdefault("Cache-Control", "no-store")
            origin = request.headers.get("Origin")
            allowed = "*" if "*" in cors_origins else origin if origin in cors_origins else None
            if allowed:
                resp.headers["Access-Control-Allow-Origin"] = allowed
                if allowed != "*":
                    resp.headers.add("Vary", "Origin")
                if request.method == "OPTIONS":         # preflight: POST application/sparql-query từ trang khác
                    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
                    resp.headers["Access-Control-Max-Age"] = "86400"
        t0 = request.environ.get("vnedu.t0")
        if t0 is not None:
            log.info("%s %s %d %.0fms request_id=%s", request.method, request.path, resp.status_code,
                     1000 * (time.perf_counter() - t0), request.environ.get("vnedu.request_id", ""))
        return resp

    @app.errorhandler(404)
    def _not_found(_e):
        page = site_page("404", 404) if request.accept_mimetypes.accept_html else None
        return page or Response("Không tìm thấy tài nguyên.", status=404, content_type="text/plain; charset=utf-8")

    @app.errorhandler(QueryRejected)
    def _rejected(e):
        """Bận / quá giờ ở bất kỳ route nào (vd. /resource) -> 503 + Retry-After, không phải 500."""
        resp = Response(str(e), status=e.status, content_type="text/plain; charset=utf-8")
        if e.status == 503:
            resp.headers["Retry-After"] = "10"
        return resp

    @app.errorhandler(Exception)
    def _internal(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        log.exception("Lỗi không lường trước")
        return Response("Lỗi máy chủ. Vui lòng thử lại sau.", status=500, content_type="text/plain; charset=utf-8")

    @app.route("/")
    def home():
        page = site_page("")
        if page:
            return page
        counts, links, total = home_stats()
        dumps = [f.name for f in sorted(config.RDF_DIR.glob("*.ttl"))]
        return render_template("home.html", counts=counts, links=links, total=total, inferred=len(inferred),
                               queries=example_queries(), dumps=dumps, backend=backend.name, base=config.BASE)

    @app.route("/healthz")
    def healthz():
        try:
            checker = getattr(backend, "healthy", None)
            ok = bool(checker()) if checker else bool(backend.select("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"))
        except Exception:  # noqa: BLE001
            ok = False
        body = {"backend": backend.name, "ui": "site" if site else "fallback",
                "commit": (os.environ.get("RENDER_GIT_COMMIT") or "local")[:8]}
        status_of = getattr(backend, "pool_status", None)
        if status_of:
            pool = body["query_pool"] = status_of()
            # pool đã khởi động mà không còn worker nào sống -> endpoint không phục vụ được
            ok = ok and not (pool["started"] and pool["alive"] == 0)
        body["status"] = "ok" if ok else "degraded"
        return body, (200 if ok else 503)

    @app.route("/sparql", methods=["GET", "POST"])
    def sparql():
        q = (request.get_data(as_text=True) if request.mimetype == "application/sparql-query"
             else request.values.get("query"))
        if not q:
            return site_page("sparql") or render_template("query.html", queries=example_queries(), initial=None)
        supported = (*SELECT_MIME, *RDF_MIME)
        if isinstance(backend, LocalBackend) and request.headers.get("Accept") and not preferred_mimes(supported):
            # Client chỉ chấp nhận loại không hỗ trợ (vd. image/png) -> 406, liệt kê các loại có thể trả
            return Response("Không có định dạng kết quả phù hợp với Accept. Hỗ trợ: " + ", ".join(supported),
                            status=406, content_type="text/plain; charset=utf-8")
        try:
            check_query(q)
            accept = (preferred_mimes(supported) if isinstance(backend, LocalBackend)
                      else request.headers.get("Accept", ""))
            resp = backend.protocol(q, accept)
        except QueryRejected as e:
            resp = _rejected(e)
        except Exception as e:  # noqa: BLE001 — lỗi cú pháp (pyparsing) của rdflib: thông báo có ích cho người dùng
            msg = str(e).splitlines()[0][:300] if str(e) else type(e).__name__
            resp = Response(f"Truy vấn không hợp lệ: {msg}", status=400, content_type="text/plain; charset=utf-8")
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

    def static_rdf(rel: str, mime: str):
        """Bản RDF đã build sẵn của tài nguyên (cùng nội dung GitHub Pages); None nếu chưa build."""
        if site is None:
            return None
        f = site / "resource" / (rel + (".jsonld" if mime == "application/ld+json" else ".ttl"))
        if not f.is_file():
            return None
        if mime in ("text/turtle", "application/ld+json"):
            return send_from_directory(site, f.relative_to(site).as_posix(), mimetype=mime)
        from rdflib import Graph                                # N-Triples / RDF/XML: chuyển từ Turtle
        return rdf_response(Graph().parse(f, format="turtle"), mime)

    def resource_rdf(rel: str, mime: str):
        """Tra cứu RDF không chiếm worker SPARQL khi đã có bản tĩnh; nếu chưa build thì CONSTRUCT."""
        resp = static_rdf(rel, mime)
        if resp is None:
            uri = config.RES_NS + rel
            g = backend.construct(f"CONSTRUCT {{ <{uri}> ?p ?o }} WHERE {{ <{uri}> ?p ?o }}")
            if not len(g):
                abort(404)
            resp = rdf_response(g, mime)
        return resp

    @app.route("/resource/<path:rest>")
    def resource(rest):
        m = re.fullmatch(r"(.+)\.(ttl|jsonld)", rest)
        if m and RESOURCE_PATH.fullmatch(m.group(1)):          # .../x.ttl, .../x.jsonld giống GitHub Pages
            return resource_rdf(m.group(1), {"ttl": "text/turtle", "jsonld": "application/ld+json"}[m.group(2)])
        if not RESOURCE_PATH.fullmatch(rest):
            abort(404)
        uri = config.RES_NS + rest
        mime = wants_rdf()
        if mime:
            resp = resource_rdf(rest, mime)
            resp.headers["Vary"] = "Accept"
            return resp
        page = site_page("resource/" + rest)
        if page:
            page.headers["Vary"] = "Accept"
            return page
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

    @app.route("/ontology/<version>")
    def ontology_version(version):
        from rdflib import Graph
        fmt = "text/turtle" if version.endswith(".ttl") else "application/ld+json" if version.endswith(".jsonld") else wants_rdf()
        key = version.removesuffix(".ttl").removesuffix(".jsonld")
        if not re.fullmatch(r"[0-9]+\.[0-9]+", key):
            abort(404)
        source = config.ROOT / "ontology" / "versions" / (key + ".ttl")
        if not source.is_file():
            abort(404)
        if fmt:
            return rdf_response(Graph().parse(source), fmt)
        response = make_response(f'<h1>Ontology {key}</h1><a href="{key}.ttl">Turtle</a> · <a href="{key}.jsonld">JSON-LD</a>')
        response.headers["Vary"] = "Accept"
        return response

    @app.route("/ontology")
    def ontology():
        from common import load_ontology
        g = load_ontology()
        mime = wants_rdf()
        if mime:
            return rdf_response(g, mime)
        page = site_page("ontology")
        if page:
            return page
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
        mime = wants_rdf()
        if not mime and _rest is None and request.accept_mimetypes.accept_html:
            page = site_page("dataset")
            if page:
                return page
        if not mime and _rest and site_page("dataset/" + _rest):
            return site_page("dataset/" + _rest)
        return rdf_response(Graph().parse(config.VOID_TTL), mime or "text/turtle")

    @app.route("/download/<name>")
    def download(name):
        """Dump RDF (vnedu-all.ttl, .nt, .zip, shapes, schema): ưu tiên bản trong giao diện đã build, rồi data/gold."""
        base = site / "download" if site and (site / "download" / name).is_file() else config.RDF_DIR
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return send_from_directory(base, name, mimetype=mime, as_attachment=not name.endswith((".ttl", ".nt")))

    @app.route("/<path:rel>")
    def static_site(rel):
        if site is None:
            abort(404)
        target = (site / rel).resolve()
        if site.resolve() not in target.parents and target != site.resolve():
            abort(404)
        if target.is_file():
            return send_from_directory(site, rel)
        page = site_page(rel.rstrip("/"))
        if page:
            return page
        abort(404)

    @app.template_filter("short")
    def short_filter(uri):
        return short(uri)

    return app


def build_site_if_missing(site_dir: Path = SITE_DIR) -> None:
    """Build giao diện (đường dẫn gốc /) nếu chưa có — để máy chủ luôn có giao diện đầy đủ kể cả khi nền tảng
    triển khai không chạy bước build riêng. Chạy trong tiến trình con nên bộ nhớ (~170 MB) được trả lại trước khi phục vụ."""
    if (site_dir / "index.html").exists():
        return
    # Fixed local build command; no request data reaches the process API.
    import subprocess  # nosec B404
    log.info("Chưa có giao diện ở %s — đang build (≈20 giây) ...", site_dir)
    env = dict(os.environ, VNEDU_SITE_DIR=site_dir.name, VNEDU_SITE_ROOT="/", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "step7_publish.py")], env=env, cwd=ROOT,  # nosec B603
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log.error("Build giao diện thất bại, dùng giao diện dự phòng: %s", r.stdout[-2000:] + r.stderr[-2000:])
    else:
        log.info("Đã build giao diện: %s", r.stdout.strip().splitlines()[-2:])


def main() -> None:
    ap = argparse.ArgumentParser(description="VN-Edu LOD web server")
    ap.add_argument("--backend", choices=["auto", "local", "fuseki"], default="auto")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))   # Render/Heroku cấp qua $PORT
    ap.add_argument("--prod", action="store_true", help="chạy bằng máy chủ WSGI waitress thay cho máy chủ phát triển")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.prod:
        build_site_if_missing()
    use_fuseki = args.backend == "fuseki" or (args.backend == "auto" and fuseki_alive())
    backend = FusekiBackend() if use_fuseki else LocalBackend()
    if isinstance(backend, LocalBackend):
        backend.warmup()
    app = create_app(backend)
    log.info("Backend: %s — mở http://%s:%d/", app.config["BACKEND"].name, args.host, args.port)
    if args.prod:
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=8)
    else:
        app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
