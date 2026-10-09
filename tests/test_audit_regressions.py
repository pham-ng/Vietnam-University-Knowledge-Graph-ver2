"""Counterexamples discovered during the independent audit (no external requests)."""
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts'), str(ROOT / 'app')]
from server import check_query, QueryRejected
from common import load_ontology
from step5_reason import consistency, reason

V = Namespace('https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology#')
R = Namespace('https://example.org/')


@pytest.mark.parametrize('query', [
    'SELECT * WHERE { SERVICE<http://127.0.0.1:9999/> { ?s ?p ?o } }',
    'SELECT * FROM<http://127.0.0.1:9999/> WHERE { ?s ?p ?o }',
    'SELECT * FROM NAMED<file:///etc/passwd> WHERE { GRAPH ?g { ?s ?p ?o } }',
    'SELECT * WHERE { SERVICE <https://query.wikidata.org:8443/sparql> { ?s ?p ?o } }',
    'SELECT * WHERE { SERVICE <https://dbpedia.org/redirect?url=http://127.0.0.1> { ?s ?p ?o } }',
    'SELECT * WHERE { SERVICE <https://user@dbpedia.org/sparql> { ?s ?p ?o } }',
])
def test_query_policy_handles_real_sparql_syntax(query):
    with pytest.raises(QueryRejected):
        check_query(query)


def test_security_keywords_in_literals_are_not_operations():
    check_query('SELECT ("SERVICE <http://localhost/> FROM <file:///x>" AS ?text) WHERE {}')


def test_reasoner_datatype_errors_are_not_silently_dropped():
    graph = load_ontology()
    graph.add((R.program, V.degreeLevel, Literal('Bachelor', datatype=XSD.integer, normalize=False)))
    assert consistency(reason(graph))


def test_language_tagged_degree_level_is_consistent():
    graph = load_ontology()
    graph.add((R.program, V.degreeLevel, Literal('đại học', lang='vi')))
    from owlrl.Closure import ERRNS
    assert not list(reason(graph).objects(None, ERRNS.error))


def test_literal_ranges_checked_without_relying_on_reasoner_coverage():
    from step5_reason import asserted_constraints
    graph = Graph()
    graph.add((R.program, V.degreeLevel, Literal('Bachelor')))
    # OWL 2 RL cannot use rdf:langString as a range.  The release therefore
    # uses rdfs:Literal, intentionally accepting plain and language-tagged text.
    assert asserted_constraints(graph, load_ontology())[0]
    graph.set((R.program, V.degreeLevel, Literal('Bachelor', lang='en')))
    assert asserted_constraints(graph, load_ontology())[0]


def test_quality_gate_stops_on_either_kind_of_failure():
    from step5_reason import require_quality
    for problems, conforms in [([('error',)], True), ([], False)]:
        with pytest.raises(SystemExit):
            require_quality(problems, conforms)
    require_quality([], True)


def test_registered_uri_survives_rename_insertion_and_retirement():
    from common import Minter
    first = Minter('person')
    old = first.mint('Same Name', key='Q2')
    restored = Minter('person', first.registry)
    new = restored.mint('Same Name', key='Q1')
    assert new != old
    assert restored.mint('Renamed Person', key='Q2') == old
    assert Minter('person', restored.registry).mint('Same Name', key='Q3') not in (old, new)


def test_same_name_does_not_merge_unidentified_people_across_schools(monkeypatch):
    import step3_integrate as integrate
    monkeypatch.setattr(integrate, 'load', lambda _: [])
    def school():
        return {'leaders': [{'qid': '', 'name': 'Nguyễn Văn Hùng', 'role': 'rector', 'honorific': ''}]}
    schools = {'Q1': school(), 'Q2': school()}
    people = integrate.build_people(schools, {}, {})
    assert len(people) == 2
    assert schools['Q1']['leaders'][0]['person_key'] != schools['Q2']['leaders'][0]['person_key']


def test_offline_cache_miss_never_calls_network(monkeypatch, tmp_path):
    import httpcache
    monkeypatch.setenv('VNEDU_OFFLINE', '1')
    monkeypatch.setattr(httpcache, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(httpcache._session, 'get', lambda *a, **k: pytest.fail('network called'))
    with pytest.raises(RuntimeError, match='Offline cache miss'):
        httpcache.get_json('https://example.org/data', {})


def test_future_year_and_impossible_calendar_date_rejected():
    from test_data_contract import errors_for
    from step3_integrate import THIS_YEAR
    assert errors_for(founding_year=THIS_YEAR + 1)
    assert errors_for(founding_date='2020-02-31')


def test_public_sparql_accepts_raw_post_and_blocks_compact_ssrf():
    from server import create_app
    from flask import Response
    class Backend:
        def protocol(self, query, accept):
            return Response('{"boolean": true}', mimetype='application/sparql-results+json')
    client = create_app(Backend(), inferred=set(), site_dir=None).test_client()
    assert client.post('/sparql', data='ASK {}', content_type='application/sparql-query').status_code == 200
    assert client.post('/sparql', data='SELECT * WHERE { SERVICE<http://127.0.0.1/> { ?s ?p ?o } }',
                       content_type='application/sparql-query').status_code == 400


def test_expensive_query_is_terminated_and_capacity_recovers(tmp_path, monkeypatch):
    import multiprocessing
    import time
    import server
    graph = Graph()
    for n in range(100):
        graph.add((R[str(n)], R.value, Literal(n)))
    path = tmp_path / 'input.ttl'
    graph.serialize(path, format='turtle')
    backend = server.LocalBackend(path)
    backend.warmup()
    before_count = len(multiprocessing.active_children())
    monkeypatch.setattr(server, 'QUERY_TIMEOUT_S', 2)
    with pytest.raises(QueryRejected) as error:
        backend.select('SELECT ?a ?b ?c ?d WHERE { ?a ?p ?o . ?b ?q ?r . ?c ?s ?t . ?d ?v ?w }')
    assert error.value.status == 503
    monkeypatch.setattr(server, 'QUERY_TIMEOUT_S', 15)
    deadline = time.monotonic() + 10
    while True:
        try:
            assert len(backend.select('SELECT ?s WHERE { ?s ?p ?o } LIMIT 1')) == 1
            break
        except QueryRejected:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
    assert len(multiprocessing.active_children()) == before_count
    backend.close()


def test_federation_redirects_are_disabled():
    import urllib.request
    from server import install_user_agent
    install_user_agent()
    handler = next(h for h in urllib.request._opener.handlers if type(h).__name__ == '_NoRedirect')
    with pytest.raises(QueryRejected):
        handler.redirect_request(None, None, 302, '', {}, 'http://127.0.0.1/')


def test_publisher_rejects_project_root_and_source_directories(tmp_path, monkeypatch):
    import config
    from step7_publish import validate_site_output
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    with pytest.raises(ValueError):
        validate_site_output(tmp_path)
    data = tmp_path / 'data'
    data.mkdir()
    with pytest.raises(ValueError):
        validate_site_output(data)
    validate_site_output(tmp_path / 'new-site')


def test_publisher_rejects_stale_validation(tmp_path, monkeypatch):
    import common
    import config
    monkeypatch.setattr(config, 'REPORTS_DIR', tmp_path)
    with pytest.raises(SystemExit, match='Missing or stale'):
        common.require_validated_release()


def test_failed_validation_preserves_previous_serving_files(tmp_path, monkeypatch, capsys):
    import step5_reason as step
    from rdflib.namespace import RDFS, OWL
    ontology = Graph()
    ontology.add((R['count'], RDF.type, OWL.DatatypeProperty))
    ontology.add((R['count'], RDFS.range, XSD.integer))
    invalid = Graph()
    invalid.add((R.entity, R['count'], Literal('not an integer')))
    data_path, inferred_path, all_path = (tmp_path / name for name in ('data.ttl', 'inferred.ttl', 'all.ttl'))
    invalid.serialize(data_path, format='turtle')
    inferred_path.write_text('previous inference', encoding='utf-8')
    all_path.write_text('previous release', encoding='utf-8')
    monkeypatch.setattr(step.config, 'ROOT', tmp_path)
    monkeypatch.setattr(step.config, 'DATA_TTL', data_path)
    monkeypatch.setattr(step.config, 'ALL_TTL', all_path)
    monkeypatch.setattr(step, 'INFERRED_TTL', inferred_path)
    monkeypatch.setattr(step, 'REPORTS', tmp_path / 'reports')
    monkeypatch.setattr(step, 'load_ontology', lambda: ontology)
    with capsys.disabled():
        with pytest.raises(SystemExit, match='Quality gate failed'):
            step.main()
    assert inferred_path.read_text() == 'previous inference'
    assert all_path.read_text() == 'previous release'
