import json
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

ROOT = Path(__file__).resolve().parents[1]
V = Namespace("https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology#")
SCHEMA = Namespace("https://schema.org/")
PROV = Namespace("http://www.w3.org/ns/prov#")


def institutions():
    return json.loads((ROOT / "data" / "silver" / "institutions.json").read_text(encoding="utf-8"))


def test_ministry_directory_values_are_current_and_source_qualified():
    hust = institutions()["Q3075696"]
    assert hust["admission_codes"] == ["BKA"]
    assert hust["email"] == "vp@hust.edu.vn"
    assert hust["website"] == "https://hust.edu.vn/"
    for field in ("admission_codes", "email", "website"):
        refs = hust["field_sources"][field]
        assert refs and refs[0]["source"] == "https://tuyensinh.moet.gov.vn/ts/"
        assert refs[0]["retrieved_at"]
        assert refs[0]["values"]


def test_legal_governance_is_not_downgraded_to_reported_governance():
    hust = institutions()["Q3075696"]
    assert hust["direct_governed_by"] == ["name:bo-giao-duc-va-dao-tao"]
    assert "name:bo-giao-duc-va-dao-tao" not in hust["governed_by"]
    ref = hust["field_sources"]["direct_governed_by"][0]
    assert ref["record"] == "1723/QĐ-TTg"
    assert ref["source"].startswith("https://congbao.chinhphu.vn/")


def test_curated_national_university_memberships_are_source_qualified():
    records = institutions()
    cases = {
        "Q5873997": ("Q943759", "https://hcmus.edu.vn/"),
        "Q10829064": ("Q1076729", "https://ussh.vnu.edu.vn/"),
    }
    for child_key, (parent_key, source_prefix) in cases.items():
        child = records[child_key]
        assert parent_key in child["member_of"]
        refs = child["field_sources"]["member_of"]
        assert any(parent_key in ref["values"] and ref["source"].startswith(source_prefix)
                   and ref["retrieved_at"] for ref in refs)


def test_ror_acronyms_are_value_scoped():
    hcmue = institutions()["Q10489198"]
    ref = hcmue["field_sources"]["short_names"][0]
    assert set(ref["values"]) <= set(hcmue["short_names"])
    assert ref["source"] == "https://api.ror.org/v2/organizations"


def test_gold_contains_claim_level_provenance():
    graph = Graph().parse(ROOT / "data" / "gold" / "vnedu-data.ttl", format="turtle")
    subjects = set(graph.subjects(V.admissionCode, Literal("BKA")))
    assert len(subjects) == 1
    subject = next(iter(subjects))
    observations = [o for o in graph.subjects(RDF.subject, subject)
                    if (o, RDF.predicate, V.admissionCode) in graph and (o, RDF.object, Literal("BKA")) in graph]
    assert observations
    observation = observations[0]
    assert (observation, PROV.wasDerivedFrom, URIRef("https://tuyensinh.moet.gov.vn/ts/")) in graph
    assert list(graph.objects(observation, DCTERMS.identifier))


def test_ror_locality_centroids_are_not_promoted_to_campus_coordinates():
    for item in institutions().values():
        assert item.get("coord_source") != "ror"


def test_dated_rename_preserves_legal_identity_and_ministry_match():
    hyute = institutions()["Q7896405"]
    old_name = "Trường Đại học Sư phạm Kỹ thuật Hưng Yên"
    assert hyute["name_vi"] == "Trường Đại học Công nghệ Kỹ thuật Hưng Yên"
    assert old_name in hyute["former_names"]
    assert hyute["admission_codes"] == ["SKH"]
    assert hyute["direct_governed_by"] == ["name:bo-giao-duc-va-dao-tao"]
    rename_ref = hyute["field_sources"]["former_names"][0]
    assert rename_ref["record"] == "2606/QĐ-BGDĐT"
    assert rename_ref["valid_through"] == "2026-09-03"


def test_legal_dates_are_distinct_from_retrieval_timestamps_in_rdf():
    graph = Graph().parse(ROOT / "data" / "gold" / "vnedu-data.ttl", format="turtle")
    subject = next(graph.subjects(V.admissionCode, Literal("SKH")))
    ministry = next(graph.objects(subject, V.directlyGovernedBy))
    observations = [o for o in graph.subjects(RDF.subject, subject)
                    if (o, RDF.predicate, V.directlyGovernedBy) in graph
                    and (o, RDF.object, ministry) in graph]
    assert len(observations) == 1
    observation = observations[0]
    assert (observation, V.validFrom,
            Literal("2025-08-12T00:00:00", datatype=XSD.dateTime)) in graph
    generated = list(graph.objects(observation, PROV.generatedAtTime))
    assert generated and str(generated[0]).startswith("2026-10-09")
