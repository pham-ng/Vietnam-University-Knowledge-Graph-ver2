"""Hồi quy cho các lỗi do đánh giá độc lập (10/2026) phát hiện: căn chỉnh DBpedia lệch kiểu, owl:sameAs tới
trang định hướng Wikimedia, thực thể trùng, mã tuyển sinh của cơ sở đã giải thể, sai loại hình sở hữu,
và việc bản build phụ thuộc thời điểm chạy."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import config  # noqa: E402

V = config.ONTO_NS
R = config.RES_NS
DBO = "http://dbpedia.org/ontology/"
WD = "http://www.wikidata.org/entity/"
RDF_LANG = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"


@pytest.fixture(scope="module")
def onto():
    return Graph().parse(ROOT / "ontology" / "vnedu.ttl")


@pytest.fixture(scope="module")
def data():
    if not config.DATA_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    return Graph().parse(config.DATA_TTL)


@pytest.fixture(scope="module")
def closure():
    if not config.ALL_TTL.exists():
        pytest.skip("chưa chạy pipeline")
    return Graph().parse(config.ALL_TTL)


def dbpedia_signatures():
    with (ROOT / "data" / "reference" / "dbpedia_property_signatures.csv").open(encoding="utf-8") as fh:
        return {row["property"]: row for row in csv.DictReader(fh)}


# ------------------------------------------------------------------ ontology <-> DBpedia

def test_dbpedia_subproperty_alignments_are_type_compatible(onto, data):
    """Import DBpedia không được làm ontology + dữ liệu mâu thuẫn (HermiT: 2.2 + DBpedia = không nhất quán)."""
    signatures = dbpedia_signatures()
    aligned = [(p, o) for p, o in onto.subject_objects(RDFS.subPropertyOf) if str(o).startswith(DBO)]
    assert aligned
    for prop, target in aligned:
        sig = signatures[str(target)]
        kinds = sig["types"].split()
        ours_object = (prop, RDF.type, OWL.ObjectProperty) in onto
        assert ours_object == ("ObjectProperty" in kinds), f"{prop} và {target} khác loại thuộc tính"
        if ours_object or not sig["range"]:
            continue
        for value in data.objects(None, prop):            # mọi literal thực tế phải thuộc range của DBpedia
            if sig["range"] == RDF_LANG:
                assert value.language, (prop, value)
            else:
                assert not value.language and str(value.datatype or XSD.string) == sig["range"], (prop, value)


def test_no_external_term_is_redeclared_with_a_conflicting_kind(onto):
    signatures = dbpedia_signatures()
    for term, sig in signatures.items():
        declared_datatype = (URIRef(term), RDF.type, OWL.DatatypeProperty) in onto
        assert not (declared_datatype and "ObjectProperty" in sig["types"].split()), term


# ------------------------------------------------------------------ định danh

NON_ARTICLE = {"Q4167410", "Q4167836", "Q11266439", "Q13406463", "Q22808320"}


def test_no_owl_sameas_to_wikimedia_disambiguation_or_list_items(data):
    types = {row["qid"]: set(row.get("types") or [])
             for row in json.loads((config.BRONZE_DIR / "wd_institutions.json").read_text(encoding="utf-8"))}
    links = Graph().parse(config.LINKS_TTL) + data
    bad = [(s, o) for s, o in links.subject_objects(OWL.sameAs)
           if str(o).startswith(WD) and types.get(str(o)[len(WD):], set()) & NON_ARTICLE]
    assert not bad
    assert (URIRef(R + "university/dai-hoc-can-tho-19661975"), None, None) not in data


def test_admission_codes_are_unique_among_active_institutions(data):
    owners = defaultdict(set)
    for inst, code in data.subject_objects(URIRef(V + "admissionCode")):
        assert (inst, URIRef(V + "dissolutionYear"), None) not in data, f"cơ sở đã giải thể vẫn có mã {code}: {inst}"
        owners[str(code)].add(inst)
    assert {c: s for c, s in owners.items() if len(s) > 1} == {}


def test_duplicate_wikidata_items_are_one_resource_with_both_sameas(data):
    ytc = [s for s in data.subjects(URIRef(V + "admissionCode"), Literal("YTC"))]
    assert len(ytc) == 1
    links = Graph().parse(config.LINKS_TTL)
    assert {URIRef(WD + "Q10829176"), URIRef(WD + "Q5649327")} <= set(links.objects(ytc[0], OWL.sameAs))


@pytest.mark.parametrize("old, new", [
    ("truong-dai-hoc-y-te-cong-cong-2", "truong-dai-hoc-y-te-cong-cong"),
    ("truong-dai-hoc-phong-chay-chua-chay", "hoc-vien-phong-chay-chua-chay-va-cuu-nan-cuu-ho"),
])
def test_retired_uris_stay_dereferenceable_and_point_to_successor(data, old, new):
    """Cool URIs don't change: URI đã công bố của bản ghi bị gộp vẫn tra được, chỉ sang URI hiện hành."""
    from rdflib.namespace import DCTERMS
    assert (URIRef(R + "university/" + old), DCTERMS.isReplacedBy, URIRef(R + "university/" + new)) in data


def test_documented_rename_merges_former_entity(data):
    academy = URIRef(R + "university/hoc-vien-phong-chay-chua-chay-va-cuu-nan-cuu-ho")
    assert (academy, URIRef(V + "admissionCode"), Literal("PCH")) in data
    assert (academy, URIRef(V + "formerName"), Literal("Trường Đại học Phòng cháy chữa cháy", lang="vi")) in data
    assert not list(data.subjects(RDFS.label, Literal("Trường Đại học Phòng cháy chữa cháy", lang="vi")))


# ------------------------------------------------------------------ loại hình sở hữu

@pytest.mark.parametrize("slug, ownership, foreign", [
    ("truong-dai-hoc-quoc-te-rmit-viet-nam", "PrivateOwnership", True),
    ("truong-dai-hoc-ha-tinh", "PublicOwnership", False),
    ("hoc-vien-phat-giao-viet-nam", "ReligiousOrganizationOwnership", False),
])
def test_cited_ownership_corrections(data, slug, ownership, foreign):
    inst = URIRef(R + "university/" + slug)
    assert set(data.objects(inst, URIRef(V + "ownership"))) == {URIRef(V + ownership)}
    assert ((inst, URIRef(V + "foreignInvested"), Literal(True)) in data) is foreign


def test_religious_institution_is_neither_public_nor_private(closure):
    inst = URIRef(R + "university/hoc-vien-phat-giao-viet-nam")
    types = set(closure.objects(inst, RDF.type))
    assert URIRef(V + "PublicInstitution") not in types and URIRef(V + "PrivateInstitution") not in types


# ------------------------------------------------------------------ build tái lập

def test_retrieval_time_is_kept_when_content_is_unchanged(tmp_path):
    import collect_authoritative as ca
    path = tmp_path / "x.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    path.with_suffix(".meta.json").write_text('{"retrieved_at": "2026-01-01T00:00:00+00:00"}', encoding="utf-8")
    assert ca.stable_retrieved_at(path, '{"a": 1}') == "2026-01-01T00:00:00+00:00"
    assert ca.stable_retrieved_at(path, '{"a": 2}') != "2026-01-01T00:00:00+00:00"


def test_authoritative_sources_are_served_from_the_bundled_cache(monkeypatch):
    """Cổng Bộ GD&ĐT và ROR phải đi qua bộ đệm: chạy offline không được chạm mạng."""
    import collect_authoritative as ca
    import httpcache
    monkeypatch.setenv("VNEDU_OFFLINE", "1")
    monkeypatch.setattr(httpcache._session, "get", lambda *a, **k: pytest.fail("chạm mạng khi offline"))
    monkeypatch.setattr(httpcache._session, "post", lambda *a, **k: pytest.fail("chạm mạng khi offline"))
    insts = ca.load_collection_registry()
    moet, failures = ca.collect_moet(insts, workers=2)
    assert not failures and len(moet) > 300
    ror, failures = ca.collect_ror(insts, workers=2)
    assert not failures and len(ror) > 100
