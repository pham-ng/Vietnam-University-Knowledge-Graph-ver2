"""Kiểm thử máy chủ web (Flask test client + backend rdflib trên dữ liệu thật):
chức năng, content negotiation theo nguyên tắc Linked Data, và các lỗ hổng đã từng tồn tại (SSRF, chèn SPARQL)."""
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import threading
import time
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
import config  # noqa: E402
import server  # noqa: E402
from server import (FixedWindowLimiter, LocalBackend, QueryRejected, build_site_if_missing,  # noqa: E402
                    check_query, create_app)

BKA = "resource/university/dai-hoc-bach-khoa-ha-noi"


def hei_count() -> str:
    """Đáp án đối chiếu tính độc lập bằng rdflib trên bản gold (không hard-code con số)."""
    g = Graph().parse(config.ALL_TTL)
    return str(len(set(g.subjects(URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                                  URIRef(config.ONTO_NS + "HigherEducationInstitution")))))


@pytest.fixture(scope="module")
def client():
    if not config.ALL_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    backend = LocalBackend()
    app = create_app(backend, site_dir=None)        # giao diện dự phòng (app/templates)
    app.config["TESTING"] = True
    yield app.test_client()
    backend.close()


@pytest.fixture(scope="module")
def site_client():
    """Máy chủ phục vụ giao diện đầy đủ (site_server/, build bằng VNEDU_SITE_DIR=site_server VNEDU_SITE_ROOT=/)."""
    site = ROOT / "site_server"
    if not config.ALL_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    build_site_if_missing(site)                     # như khi máy chủ khởi động: tự build thay vì bỏ qua test
    if not (site / "index.html").exists():
        pytest.fail("không build được site_server")
    backend = LocalBackend()
    app = create_app(backend, site_dir=site)
    app.config["TESTING"] = True
    yield app.test_client()
    backend.close()


# ------------------------------------------------------------------ chức năng

def test_home_shows_statistics(client):
    r = client.get("/")
    assert r.status_code == 200
    assert hei_count() in r.get_data(as_text=True)          # số cơ sở GDĐH


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_local_healthz_does_not_execute_sparql(tmp_path, monkeypatch):
    """Platform probes must stay O(1), not parse the full RDF dump per request."""
    release = tmp_path / "release.ttl"
    release.write_text("# validated release\n", encoding="utf-8")
    backend = LocalBackend(release)
    monkeypatch.setattr(backend, "select", lambda _query: pytest.fail("health probe executed SPARQL"))
    app = create_app(backend, inferred=set(), site_dir=None)
    app.config["TESTING"] = True
    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_local_healthz_rejects_missing_or_empty_release(tmp_path):
    missing = LocalBackend(tmp_path / "missing.ttl")
    app = create_app(missing, inferred=set(), site_dir=None)
    assert app.test_client().get("/healthz").status_code == 503

    empty_path = tmp_path / "empty.ttl"
    empty_path.touch()
    empty = LocalBackend(empty_path)
    app = create_app(empty, inferred=set(), site_dir=None)
    assert app.test_client().get("/healthz").status_code == 503


def test_resource_html_for_browsers(client):
    r = client.get("/" + BKA, headers={"Accept": "text/html"})
    assert r.status_code == 200 and "text/html" in r.content_type
    assert "Bách khoa Hà Nội" in r.get_data(as_text=True)
    assert r.headers["Vary"] == "Accept"


@pytest.mark.parametrize("accept, fmt", [("text/turtle", "turtle"), ("application/ld+json", "json-ld"),
                                         ("application/n-triples", "nt"), ("application/rdf+xml", "xml")])
def test_resource_content_negotiation(client, accept, fmt):
    r = client.get("/" + BKA, headers={"Accept": accept})
    assert r.status_code == 200 and r.content_type.startswith(accept)
    g = Graph().parse(data=r.get_data(as_text=True), format=fmt)
    assert (URIRef(config.RES_NS + BKA[len("resource/"):]), URIRef(config.ONTO_NS + "admissionCode"), Literal("BKA")) in g


def test_resource_format_parameter(client):
    r = client.get(f"/{BKA}?format=ttl")
    assert r.status_code == 200 and r.content_type.startswith("text/turtle")


def test_unknown_resource_is_404(client):
    assert client.get("/resource/university/khong-ton-tai").status_code == 404


def test_sparql_select_json_and_csv(client):
    q = "PREFIX vnedu: <%s> SELECT (COUNT(?u) AS ?n) WHERE { ?u a vnedu:HigherEducationInstitution }" % config.ONTO_NS
    r = client.post("/sparql", data={"query": q}, headers={"Accept": "application/sparql-results+json"})
    assert r.status_code == 200
    expected = hei_count()
    assert json.loads(r.data)["results"]["bindings"][0]["n"]["value"] == expected
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    r = client.get("/sparql", query_string={"query": q}, headers={"Accept": "text/csv"})
    assert r.status_code == 200 and r.get_data(as_text=True).splitlines()[1].strip() == expected


def test_sparql_syntax_error_is_400_not_500(client):
    r = client.post("/sparql", data={"query": "SELEKT * WHERE {"})
    assert r.status_code == 400 and r.get_data(as_text=True).startswith("Truy vấn không hợp lệ")


def test_query_parser_guard_serializes_non_reentrant_parser(monkeypatch):
    """Cold concurrent requests must not race RDFLib's lazy pyparsing initialization."""
    from rdflib.plugins.sparql import parser

    active = 0
    state_lock = threading.Lock()

    def non_reentrant_parser(_query):
        nonlocal active
        with state_lock:
            if active:
                raise RuntimeError("concurrent parser entry")
            active += 1
        try:
            time.sleep(0.01)
            return []
        finally:
            with state_lock:
                active -= 1

    monkeypatch.setattr(parser, "parseQuery", non_reentrant_parser)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(check_query, ["ASK {}"] * 8))


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in r.headers
    assert "Content-Security-Policy" in r.headers
    assert r.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert r.headers["X-Request-ID"]


def test_rate_limiter_bounds_a_single_client():
    limiter = FixedWindowLimiter(2, window_seconds=60)
    assert limiter.allow("client-a")
    assert limiter.allow("client-a")
    assert not limiter.allow("client-a")
    assert limiter.allow("client-b")


def test_download_and_query_file_traversal(client):
    assert client.get("/download/vnedu-all.ttl").status_code == 200
    assert client.get("/download/..%2F..%2Fconfig.py").status_code == 404
    assert client.get("/query?file=../config.py").status_code == 200        # bỏ qua tên tệp lạ, không đọc
    assert "BASE =" not in client.get("/query?file=../config.py").get_data(as_text=True)


# ------------------------------------------------------------------ lỗ hổng đã sửa

@pytest.mark.parametrize("path", [
    "/resource/x%3E%20%3Fp%20%3Fo%20%7D%20UNION%20%7B%20%3Fs%20%3Fp%20%3Fo%20%7D%20%23",   # x> ?p ?o } UNION { ?s ?p ?o } #
    "/resource/university/a%3E",
    "/resource/university/A-HOA",
    "/resource/university/a/b/c",
])
def test_sparql_injection_via_resource_path_is_rejected(client, path):
    """Trước đây phần đường dẫn được ghép thẳng vào truy vấn (trả 500 / chạy truy vấn tuỳ ý)."""
    for accept in ("text/html", "text/turtle"):
        assert client.get(path, headers={"Accept": accept}).status_code == 404


@pytest.mark.parametrize("query", [
    "SELECT * WHERE { SERVICE <http://127.0.0.1:8010/x> { ?s ?p ?o } }",
    "SELECT * WHERE { SERVICE SILENT <http://169.254.169.254/latest/meta-data> { ?s ?p ?o } }",
    "SELECT * WHERE { SERVICE <file:///etc/passwd> { ?s ?p ?o } }",
    "SELECT * WHERE { SERVICE ?ep { ?s ?p ?o } }",
    "SELECT * WHERE { service <https://evil.example/sparql> { ?s ?p ?o } }",
    "SELECT * FROM <http://127.0.0.1:3030/x> WHERE { ?s ?p ?o }",
])
def test_ssrf_is_blocked(client, query):
    """Trước đây SERVICE tuỳ ý khiến máy chủ gửi yêu cầu tới địa chỉ nội bộ (đã tái hiện được)."""
    with pytest.raises(QueryRejected):
        check_query(query)
    assert client.post("/sparql", data={"query": query}).status_code == 400


@pytest.mark.parametrize("query", [
    "SELECT * WHERE { SERVICE <https://query.wikidata.org/sparql> { ?s ?p ?o } } LIMIT 1",
    "SELECT * WHERE { SERVICE <https://dbpedia.org/sparql> { ?s ?p ?o } } LIMIT 1",
    "PREFIX vnedu: <%s>\n# SERVICE <http://127.0.0.1/> trong chú thích thì không tính\nSELECT * WHERE { ?s a vnedu:Province }"
    % config.ONTO_NS,
])
def test_allowed_federated_queries_pass_the_guard(query):
    check_query(query)          # không ném lỗi


def test_query_too_long(client):
    r = client.post("/sparql", data={"query": "SELECT * WHERE { ?s ?p ?o } #" + "x" * 30_000})
    assert r.status_code == 413


def test_outbound_user_agent_overrides_rdflib_default(client):
    """rdflib ghi cứng UA 'rdflibForAnUser' cho SERVICE -> Wikidata trả 429. Máy chủ phải ghi đè bằng UA của dự án."""
    import urllib.request
    req = urllib.request.Request("https://query.wikidata.org/sparql", headers={"user-agent": "rdflibForAnUser"})
    for h in urllib.request._opener.handlers:                           # opener do create_app() cài đặt
        if hasattr(h, "https_request") and type(h).__name__ == "_ProjectUserAgent":
            req = h.https_request(req)
    assert req.get_header("User-agent") == config.USER_AGENT


# ------------------------------------------------------------------ máy chủ phục vụ giao diện đầy đủ (giống GitHub Pages)

@pytest.mark.parametrize("path", ["/", "/map", "/explore", "/ontology", "/sparql", "/links", "/dataset", "/about", "/demo"])
def test_site_pages_are_served(site_client, path):
    r = site_client.get(path, headers={"Accept": "text/html"})
    assert r.status_code == 200 and "text/html" in r.content_type
    assert 'href="/assets/style.css"' in r.get_data(as_text=True)      # build với đường dẫn gốc "/"


def test_site_resource_page_has_infobox_and_conneg(site_client):
    r = site_client.get("/resource/university/truong-dai-hoc-vinuni", headers={"Accept": "text/html"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "ibox" in html and "Tan Yap-Peng" in html and "Giới thiệu chung" in html
    r = site_client.get("/resource/university/truong-dai-hoc-vinuni", headers={"Accept": "text/turtle"})
    assert r.content_type.startswith("text/turtle") and "councilChair" in r.get_data(as_text=True)


@pytest.mark.parametrize("path, mime", [("/resource/university/truong-dai-hoc-vinuni.ttl", "text/turtle"),
                                        ("/resource/university/truong-dai-hoc-vinuni.jsonld", "application/ld+json"),
                                        ("/data/app.json", "application/json"),
                                        ("/download/vnedu-all.ttl", "text/turtle"),
                                        ("/assets/common.js", "text/javascript")])
def test_site_static_files(site_client, path, mime):
    r = site_client.get(path)
    assert r.status_code == 200 and r.content_type.split(";")[0] in (mime, "application/javascript")


def test_site_404_and_traversal(site_client):
    assert site_client.get("/khong-ton-tai", headers={"Accept": "text/html"}).status_code == 404
    assert site_client.get("/resource/university/khong-ton-tai.ttl").status_code == 404
    assert site_client.get("/..%2F..%2Fconfig.py").status_code == 404
    assert site_client.get("/%2e%2e/%2e%2e/config.py").status_code == 404


# ------------------------------------------------------------------ hồi quy sau đánh giá độc lập (10/2026)

def test_csp_allows_every_external_script_used_by_the_site():
    """CSP từng chặn chính Oxigraph/Leaflet/D3 của giao diện -> /sparql treo, /map hỏng."""
    import re
    app = create_app(object(), inferred=set(), site_dir=None)
    app.config["TESTING"] = True

    @app.route("/_csp_probe")
    def _probe():
        return "<p>x</p>"

    csp = app.test_client().get("/_csp_probe").headers["Content-Security-Policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";") if " " in d.strip())
    used = set()
    for page in (ROOT / "site_src").rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        used |= set(re.findall(r'(?:src=|import[^;]*?from\s*|import\()\s*["\'](https://[^/"\']+)', text))
    assert used, "không tìm thấy script ngoài nào — biểu thức kiểm tra đã lỗi thời"
    for host in used:
        assert host in directives["script-src"], host
    assert "'wasm-unsafe-eval'" in directives["script-src"]          # Oxigraph biên dịch WebAssembly
    assert "https://cdn.jsdelivr.net" in directives["connect-src"]  # tải tệp .wasm


@pytest.mark.parametrize("headers", [{}, {"Accept": "text/html"}])
def test_ontology_version_html_is_not_500(headers):
    client = create_app(object(), inferred=set(), site_dir=None).test_client()
    r = client.get("/ontology/2.2", headers=headers)
    assert r.status_code == 200 and "2.2.ttl" in r.get_data(as_text=True)


@pytest.fixture
def busy_backend(tmp_path, monkeypatch):
    """Pool đã khởi động nhưng không còn worker rảnh (một truy vấn nặng đang chạy)."""
    release = tmp_path / "release.ttl"
    release.write_text("# release\n", encoding="utf-8")
    backend = LocalBackend(release)
    backend.started = True
    monkeypatch.setattr(server, "QUEUE_WAIT_S", 0.05)
    return backend


def test_busy_pool_returns_503_with_retry_after(busy_backend):
    client = create_app(busy_backend, inferred=set(), site_dir=None).test_client()
    r = client.post("/sparql", data={"query": "ASK {}"})
    assert r.status_code == 503 and r.headers["Retry-After"]
    # tra cứu RDF khi không có bản tĩnh cũng phải là 503 (trước đây là 500)
    r = client.get("/" + BKA, headers={"Accept": "text/turtle"})
    assert r.status_code == 503 and r.headers["Retry-After"]


def test_queued_query_waits_for_a_free_worker(busy_backend, monkeypatch):
    """Truy vấn đến khi pool bận được chờ ngắn thay vì bị từ chối tức thì."""
    monkeypatch.setattr(server, "QUEUE_WAIT_S", 2)
    sentinel = object()
    threading.Timer(0.2, busy_backend.available.put_nowait, args=(sentinel,)).start()
    assert busy_backend.available.get(timeout=server.QUEUE_WAIT_S) is sentinel


def test_healthz_reports_query_pool(busy_backend):
    client = create_app(busy_backend, inferred=set(), site_dir=None).test_client()
    body = client.get("/healthz").get_json()
    assert body["query_pool"]["idle"] == 0
    assert body["status"] == "degraded"          # đã khởi động nhưng không còn worker nào sống


def test_resource_rdf_is_served_without_the_query_worker(site_client):
    """Dereference không được phụ thuộc worker SPARQL: một truy vấn nặng không làm 'chết' URI."""
    backend = site_client.application.config["BACKEND"]
    original = backend.construct
    backend.construct = lambda _q: pytest.fail("dereference dùng worker SPARQL")
    try:
        for accept, fmt in (("text/turtle", "turtle"), ("application/ld+json", "json-ld"),
                            ("application/n-triples", "nt")):
            r = site_client.get("/resource/university/truong-dai-hoc-vinuni", headers={"Accept": accept})
            assert r.status_code == 200 and r.content_type.startswith(accept)
            assert len(Graph().parse(data=r.get_data(as_text=True), format=fmt)) > 10
    finally:
        backend.construct = original


@pytest.mark.parametrize("accept, expected", [
    ("text/csv;q=0, application/sparql-results+json", "application/sparql-results+json"),
    ("application/sparql-results+xml, application/sparql-results+json;q=0.5", "application/sparql-results+xml"),
    ("text/csv", "text/csv"),
    ("", "application/sparql-results+json"),
])
def test_sparql_select_honours_q_values(client, accept, expected):
    r = client.get("/sparql", query_string={"query": "SELECT ?x WHERE { BIND(1 AS ?x) }"}, headers={"Accept": accept})
    assert r.status_code == 200 and r.content_type.startswith(expected)


@pytest.mark.parametrize("accept, expected", [
    ("application/rdf+xml, text/turtle;q=0.1", "application/rdf+xml"),
    ("text/turtle;q=0, application/n-triples", "application/n-triples"),
])
def test_sparql_construct_honours_q_values(client, accept, expected):
    q = "CONSTRUCT { <urn:a> <urn:b> <urn:c> } WHERE {}"
    r = client.get("/sparql", query_string={"query": q}, headers={"Accept": accept})
    assert r.status_code == 200 and r.content_type.startswith(expected)


# ------------------------------------------------------------------ 406, CORS preflight, giao diện terminal (đánh giá 10/2026)

def test_sparql_returns_406_when_no_acceptable_format(client):
    r = client.get("/sparql", query_string={"query": "SELECT ?x WHERE { BIND(1 AS ?x) }"}, headers={"Accept": "image/png"})
    assert r.status_code == 406 and "application/sparql-results+json" in r.get_data(as_text=True)
    # trình duyệt gửi */* -> vẫn trả JSON như trước
    r = client.get("/sparql", query_string={"query": "SELECT ?x WHERE { BIND(1 AS ?x) }"},
                   headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    assert r.status_code == 200 and r.content_type.startswith("application/sparql-results+json")


def test_sparql_cors_preflight(client):
    r = client.open("/sparql", method="OPTIONS", headers={
        "Origin": "https://example.org", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in r.headers["Access-Control-Allow-Methods"]
    assert "content-type" in r.headers["Access-Control-Allow-Headers"].lower()


def test_sparql_page_never_links_unsafe_iris():
    """Kết quả IRI('javascript:...') không được thành link bấm được (XSS khi người dùng bấm)."""
    page = (ROOT / "site_src" / "pages" / "sparql.html").read_text(encoding="utf-8")
    assert "VN.safeHref(" in page and "<a href=\"${VN.esc(href)}\"" in page
    common = (ROOT / "site_src" / "assets" / "common.js").read_text(encoding="utf-8")
    assert "safeHref(u)" in common and "https?:" in common


def _query_cli(*args, stdin=None):
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "query.py"), "--local", *args], input=stdin,
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONUTF8": "1"})


def test_query_cli_exit_codes_and_csv():
    if not config.ALL_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    assert _query_cli("SELEKT *").returncode == 1                       # lỗi cú pháp -> exit 1
    missing = _query_cli("queries/khong-ton-tai.rq")
    assert missing.returncode == 2 and "Không tìm thấy tệp" in missing.stderr
    ok = _query_cli("SELECT ?u WHERE { ?u vnedu:admissionCode \"BKA\" }", "-f", "csv")
    assert ok.returncode == 0 and config.RES_NS + "university/" in ok.stdout   # CSV giữ IRI đầy đủ


def test_query_cli_repl_run_index_and_trailing_query():
    if not config.ALL_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    out = _query_cli("-i", stdin=":run 0\n").stdout
    assert "Dùng: :run <số từ 1 đến" in out                            # không chạy nhầm tệp cuối
    out = _query_cli("-i", stdin="SELECT (1 AS ?x) WHERE {}").stdout   # không có dòng trống cuối
    assert "1 dòng" in out


def test_links_page_data_matches_linkset(site_client):
    """Trang Liên kết LOD: số liệu lấy từ đúng tệp liên kết đã phát hành."""
    data = site_client.get("/data/links.json").get_json()
    links = Graph().parse(config.LINKS_TTL)
    assert data["total"] == sum(1 for s, _, o in links if str(s).startswith(config.RES_NS) and isinstance(o, URIRef))
    assert {t["key"] for t in data["targets"] if t["count"]} == {"wikidata", "dbpedia", "ror", "geonames", "wikipedia"}
    assert all(i["href"].startswith("resource/") for t in data["targets"] for i in t["items"])
