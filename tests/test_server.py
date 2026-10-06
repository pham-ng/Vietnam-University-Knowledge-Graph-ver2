"""Kiểm thử máy chủ web (Flask test client + backend rdflib trên dữ liệu thật):
chức năng, content negotiation theo nguyên tắc Linked Data, và các lỗ hổng đã từng tồn tại (SSRF, chèn SPARQL)."""
import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
import config  # noqa: E402
from server import LocalBackend, QueryRejected, check_query, create_app  # noqa: E402

BKA = "resource/university/dai-hoc-bach-khoa-ha-noi"


@pytest.fixture(scope="module")
def client():
    if not config.ALL_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    app = create_app(LocalBackend(), site_dir=None)        # giao diện dự phòng (app/templates)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(scope="module")
def site_client():
    """Máy chủ phục vụ giao diện đầy đủ (site_server/, build bằng VNEDU_SITE_DIR=site_server VNEDU_SITE_ROOT=/)."""
    site = ROOT / "site_server"
    if not (site / "index.html").exists():
        pytest.skip("chưa build site_server")
    app = create_app(LocalBackend(), site_dir=site)
    app.config["TESTING"] = True
    return app.test_client()


# ------------------------------------------------------------------ chức năng

def test_home_shows_statistics(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "271" in r.get_data(as_text=True)          # số cơ sở GDĐH


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


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
    assert json.loads(r.data)["results"]["bindings"][0]["n"]["value"] == "271"
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    r = client.get("/sparql", query_string={"query": q}, headers={"Accept": "text/csv"})
    assert r.status_code == 200 and r.get_data(as_text=True).splitlines()[1].strip() == "271"


def test_sparql_syntax_error_is_400_not_500(client):
    r = client.post("/sparql", data={"query": "SELEKT * WHERE {"})
    assert r.status_code == 400 and r.get_data(as_text=True).startswith("Truy vấn không hợp lệ")


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in r.headers


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

@pytest.mark.parametrize("path", ["/", "/map", "/explore", "/ontology", "/sparql", "/dataset", "/about", "/demo"])
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
