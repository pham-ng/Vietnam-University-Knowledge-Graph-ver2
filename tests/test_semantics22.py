"""Negative competency tests for ontology 2.2 and evidence-qualified data."""
import sys
from pathlib import Path
import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, OWL, XSD
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts'), str(ROOT / 'app')]
from common import load_ontology, VNEDU as V, SCHEMA
from observations import observe
from step5_reason import reason
R = Namespace('urn:test:')


@pytest.fixture(scope='module')
def closure():
    g = load_ontology()
    for triple in [(R.u, V.directlyGovernedBy, R.navy), (R.navy, V.subordinateTo, V.MinistryOfNationalDefence),
                   (R.u, V.councilChair, R.person), (R.u, V.ownedBy, R.company),
                   (R.person, V.educatedAt, R.u),
                   (R.program, V.offeredBy, R.u), (R.program, V.offeredBy, R.other),
                   (R.program, V.ofMajor, R.major1), (R.program, V.ofMajor, R.major2)]:
        g.add(triple)
    return reason(g)


def test_direct_governance_does_not_propagate(closure):
    assert (R.u, V.governedBy, V.MinistryOfNationalDefence) in closure
    assert (R.u, V.directlyGovernedBy, V.MinistryOfNationalDefence) not in closure


def test_governance_and_ownership_do_not_imply_parent(closure):
    assert (R.u, SCHEMA.parentOrganization, R.navy) not in closure
    assert (R.u, SCHEMA.parentOrganization, R.company) not in closure


def test_council_chair_not_employee(closure):
    assert (R.u, V.hasLeader, R.person) in closure
    assert (R.u, SCHEMA.employee, R.person) not in closure
    assert (R.person, SCHEMA.worksFor, R.u) not in closure


def test_attendance_not_alumni(closure):
    assert (R.person, RDF.type, V.EducationParticipant) in closure
    assert (R.person, RDF.type, V.Alumnus) not in closure
    assert (R.person, SCHEMA.alumniOf, R.u) not in closure


def test_joint_program_does_not_merge_providers_or_majors(closure):
    assert (R.u, OWL.sameAs, R.other) not in closure
    assert (R.major1, OWL.sameAs, R.major2) not in closure


def test_undated_observation_and_stable_identity():
    g = Graph()
    a = observe(g, R.u, V.rector, R.person, 'a' * 64, V.LeadershipObservation)
    b = observe(g, R.u, V.rector, R.person, 'a' * 64, V.LeadershipObservation)
    assert a == b
    assert (a, V.temporalStatus, Literal('unknown')) in g
    assert not list(g.objects(a, V.validFrom))
    assert (R.u, V.rector, R.person) not in g  # reification does not assert a fact
    assert observe(g, R.u, V.rector, R.person, 'b' * 64) != a


@pytest.mark.parametrize('start,end', [('2020-02-31', None), ('2024-01-01', '2023-01-01')])
def test_invalid_temporal_bounds_rejected(start, end):
    with pytest.raises(ValueError):
        observe(Graph(), R.u, V.rector, R.person, 'a' * 64, valid_from=start, valid_through=end)


def test_date_qualified_observation():
    g = Graph()
    node = observe(g, R.u, V.rector, R.person, 'a' * 64,
                   valid_from='2020-01-01', valid_through='2022-12-31')
    assert (node, V.temporalStatus, Literal('qualified')) in g
    assert (node, V.validFrom, Literal('2020-01-01T00:00:00', datatype=XSD.dateTime)) in g


def test_ambiguous_search_is_not_identity(monkeypatch):
    import step4_link as link
    monkeypatch.setattr(link, 'get_json', lambda *a, **k: {'search': [
        {'id': 'Q1', 'label': 'Example', 'description': 'institution'},
        {'id': 'Q2', 'label': 'Example', 'description': 'institution'}]})
    assert link.search_wikidata('Example', 'en') == ('', '', '')


def test_ambiguous_dbpedia_target_rejected(monkeypatch):
    import step4_link as link
    monkeypatch.setattr(link, 'sparql', lambda *a, **k: [
        {'w': 'http://www.wikidata.org/entity/Q1', 'd': 'http://dbpedia.org/resource/A'},
        {'w': 'http://www.wikidata.org/entity/Q1', 'd': 'http://dbpedia.org/resource/B'}])
    assert link.dbpedia_for(['Q1']) == {}


def test_immutable_version_routes():
    from server import create_app
    client = create_app(object(), inferred=set(), site_dir=None).test_client()
    for version in ('2.0', '2.1', '2.2', '2.3', '2.4'):
        response = client.get('/ontology/' + version, headers={'Accept': 'text/turtle'})
        assert response.status_code == 200
        graph = Graph().parse(data=response.data, format='turtle')
        assert list(graph.objects(None, OWL.versionIRI))
    assert client.get('/ontology/999.1').status_code == 404


def test_latest_archive_matches_current():
    from rdflib.compare import isomorphic
    assert isomorphic(load_ontology(), Graph().parse(ROOT / 'ontology/versions/2.4.ttl'))
