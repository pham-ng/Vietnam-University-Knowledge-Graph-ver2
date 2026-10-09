"""Kiểm thử ontology: suy luận cho kết quả ĐÚNG và phát hiện dữ liệu SAI.

Chạy:  py -m pytest tests -q
Mỗi test dựng một đồ thị nhỏ (ontology + vài triple), suy luận OWL 2 RL bằng owlrl rồi kiểm tra.
"""
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from common import load_ontology  # noqa: E402
from step5_reason import consistency, reason  # noqa: E402

V = Namespace("https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology#")
R = Namespace("https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/")


@pytest.fixture(scope="module")
def onto():
    return load_ontology()


def closure_of(onto, triples):
    g = Graph()
    g += onto
    for t in triples:
        g.add(t)
    return reason(g)


def test_ontology_is_consistent_alone(onto):
    assert consistency(reason(onto + Graph())) == []


def test_location_chain_through_2025_merger(onto):
    """Trường ở Bình Dương (tỉnh cũ) => ở TP.HCM (tỉnh mới) => ở Nam Bộ => ở Việt Nam."""
    u, bd, hcm, nb, vn = R.u, R.bd, R.hcm, R.nb, R.vn
    c = closure_of(onto, [
        (u, RDF.type, V.UniversitySchool), (u, V.locatedIn, bd),
        (bd, RDF.type, V.FormerProvince), (bd, V.mergedInto, hcm),
        (hcm, RDF.type, V.CentrallyGovernedCity), (hcm, V.partOf, nb),
        (nb, RDF.type, V.Region), (nb, V.partOf, vn), (vn, RDF.type, V.Country)])
    for place in (bd, hcm, nb, vn):
        assert (u, V.locatedIn, place) in c
    assert (hcm, RDF.type, V.Province) in c            # CentrallyGovernedCity ⊑ Province
    assert (hcm, V.mergedFrom, bd) in c                # nghịch đảo


def test_military_classification_via_subordination(onto):
    """Trường thuộc Quân chủng Hải quân, Quân chủng thuộc Bộ Quốc phòng => MilitaryInstitution."""
    u, navy = R.navy_academy, R.navy
    c = closure_of(onto, [(u, RDF.type, V.Academy), (u, V.governedBy, navy),
                          (navy, RDF.type, V.GoverningBody), (navy, V.subordinateTo, V.MinistryOfNationalDefence)])
    assert (u, V.governedBy, V.MinistryOfNationalDefence) in c
    assert (u, RDF.type, V.MilitaryInstitution) in c
    assert (u, RDF.type, V.HigherEducationInstitution) in c
    assert (V.MinistryOfNationalDefence, V.governs, u) in c


def test_member_institution_and_inverse(onto):
    m, vnu = R.uet, R.vnu
    c = closure_of(onto, [(m, RDF.type, V.UniversitySchool), (m, V.memberOf, vnu), (vnu, RDF.type, V.NationalUniversity)])
    assert (m, RDF.type, V.MemberInstitution) in c
    assert (vnu, V.hasMember, m) in c


def test_private_inferred_from_company_owner(onto):
    u, fpt = R.fptu, R.fpt_edu
    c = closure_of(onto, [(u, RDF.type, V.UniversitySchool), (u, V.ownedBy, fpt), (fpt, RDF.type, V.Company)])
    assert (u, V.ownership, V.PrivateOwnership) in c
    assert (u, RDF.type, V.PrivateInstitution) in c


def test_people_roles(onto):
    p, u = R.p, R.u
    c = closure_of(onto, [(u, RDF.type, V.UniversitySchool), (u, V.rector, p), (p, RDF.type, V.Person),
                          (R.a, RDF.type, V.Person), (R.a, V.alumnusOf, u)])
    assert (p, V.leads, u) in c and (u, V.hasLeader, p) in c       # rector ⊑ hasLeader, inverse leads
    assert (p, RDF.type, V.InstitutionLeader) in c
    assert (R.a, RDF.type, V.Alumnus) in c and (u, V.hasAlumnus, R.a) in c


def test_trains_major_chain(onto):
    c = closure_of(onto, [(R.u, V.offersProgram, R.prog), (R.prog, V.ofMajor, R.cntt)])
    assert (R.u, V.trainsMajor, R.cntt) in c
    assert (R.prog, V.offeredBy, R.u) in c


def test_defunct_from_dissolution_year(onto):
    """EduOrg ⊓ ∃dissolutionYear.xsd:integer ⊑ DefunctInstitution (VD: Viện Đại học Vạn Hạnh 1964–1975)."""
    c = closure_of(onto, [(R.vh, RDF.type, V.UniversitySchool),
                          (R.vh, V.dissolutionYear, Literal("1975", datatype=XSD.integer))])
    assert (R.vh, RDF.type, V.DefunctInstitution) in c
    c2 = closure_of(onto, [(R.u, RDF.type, V.UniversitySchool)])
    assert (R.u, RDF.type, V.DefunctInstitution) not in c2


# ---------------------------------------------------------------- phát hiện dữ liệu sai

def test_detects_conflicting_ownership(onto):
    """ownership là FunctionalProperty + PublicOwnership ≠ PrivateOwnership => mâu thuẫn."""
    c = closure_of(onto, [(R.u, RDF.type, V.UniversitySchool),
                          (R.u, V.ownership, V.PublicOwnership), (R.u, V.ownership, V.PrivateOwnership)])
    kinds = {p[0] for p in consistency(c)}
    assert kinds & {"AllDifferent bị gộp (sameAs)", "disjointWith"}


def test_current_legal_types_are_disjoint(onto):
    """Ontology 2.4: loại pháp lý phản ánh tên chính thức HIỆN HÀNH, nên một cơ sở không thể vừa là Học viện vừa là
    Trường đại học (AllDisjointClasses). Lịch sử đổi loại (Trường ĐH PCCC -> Học viện) ghi bằng formerName/predecessor,
    không bằng hai rdf:type đồng thời."""
    c = closure_of(onto, [(R.u, RDF.type, V.Academy), (R.u, RDF.type, V.UniversitySchool)])
    assert any(p[0] == "AllDisjointClasses" for p in consistency(c))


def test_detects_person_used_as_organization(onto):
    """Lỗi kiểu dữ liệu: dùng một người làm cơ quan chủ quản => Person ⊓ Organization = ∅."""
    c = closure_of(onto, [(R.u, RDF.type, V.UniversitySchool), (R.p, RDF.type, V.Person), (R.u, V.governedBy, R.p)])
    assert any(p[0] == "AllDisjointClasses" for p in consistency(c))


def test_detects_two_founding_years(onto):
    c = closure_of(onto, [(R.u, RDF.type, V.UniversitySchool),
                          (R.u, V.foundingYear, Literal("1956", datatype=XSD.integer)),
                          (R.u, V.foundingYear, Literal("2022", datatype=XSD.integer))])
    assert any(p[0] == "FunctionalProperty (dữ liệu)" for p in consistency(c))


def test_member_of_academy_is_not_contradictory(onto):
    """Học viện Báo chí là thành viên Học viện CTQG (một Academy) — không được sinh mâu thuẫn."""
    c = closure_of(onto, [(R.ajc, RDF.type, V.Academy), (R.ajc, V.memberOf, R.hcma), (R.hcma, RDF.type, V.Academy)])
    assert consistency(c) == []
    assert (R.ajc, RDF.type, V.MemberInstitution) in c


def test_real_dataset_is_consistent():
    p = ROOT / "data" / "gold" / "vnedu-data.ttl"
    if not p.exists():
        pytest.skip("chưa chạy pipeline")
    g = load_ontology() + Graph().parse(p)
    assert consistency(reason(g)) == []


# ------------------------------------------------------------------ ontology 2.1

def test_birthplace_chain_through_2025_merger(onto):
    """Người sinh ở Bình Dương (tỉnh cũ) => sinh ra tại TP.HCM, Nam Bộ, Việt Nam (bornIn ∘ mergedInto, bornIn ∘ partOf)."""
    p, bd, hcm, nb, vn = R.p, R.bd, R.hcm, R.nb, R.vn
    c = closure_of(onto, [
        (p, RDF.type, V.Person), (p, V.bornIn, bd),
        (bd, RDF.type, V.FormerProvince), (bd, V.mergedInto, hcm),
        (hcm, RDF.type, V.Province), (hcm, V.partOf, nb), (nb, RDF.type, V.Region), (nb, V.partOf, vn)])
    for place in (hcm, nb, vn):
        assert (p, V.birthAreaInCurrentCrosswalk, place) in c
        assert (p, V.bornIn, place) not in c


def test_predecessor_successor_inverse_and_alignment(onto):
    """predecessor ↔ successor là nghịch đảo; căn chỉnh sang dbo:predecessor."""
    new, old = R.new, R.old
    c = closure_of(onto, [(new, RDF.type, V.UniversitySchool), (new, V.predecessor, old)])
    DBO = Namespace("http://dbpedia.org/ontology/")
    assert (old, V.successor, new) in c
    assert (new, DBO.predecessor, old) in c
    assert (old, RDF.type, V.Organization) in c


def test_state_management_is_not_governing_body(onto):
    """Trường tư chịu quản lý nhà nước của Bộ nhưng KHÔNG có cơ quan chủ quản -> vẫn là tư thục, không mâu thuẫn."""
    u, moet = R.priv, R.moet
    c = closure_of(onto, [(u, RDF.type, V.UniversitySchool), (u, V.ownership, V.PrivateOwnership),
                          (u, V.stateManagedBy, moet), (moet, RDF.type, V.Ministry)])
    assert (u, RDF.type, V.PrivateInstitution) in c
    assert (u, V.governedBy, moet) not in c
    assert consistency(c) == []


def test_every_object_property_has_domain_and_range(onto):
    """Ontology 2.1: mọi quan hệ của vnedu: đều khai báo domain và range (trừ website/birthPlace trỏ ra ngoài)."""
    from rdflib.namespace import RDFS
    missing = [str(p) for p in onto.subjects(RDF.type, OWL.ObjectProperty) if str(p).startswith(str(V))
               and str(p).split("#")[-1] not in ("website", "birthPlace")
               and ((p, RDFS.domain, None) not in onto or (p, RDFS.range, None) not in onto)]
    assert missing == []
