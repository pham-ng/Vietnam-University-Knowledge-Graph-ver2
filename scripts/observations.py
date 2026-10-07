"""Evidence-qualified records; absence of dates is never evidence of current validity."""
import hashlib
import json
from datetime import date

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

import config
from common import VNEDU

PROV = Namespace('http://www.w3.org/ns/prov#')


def observe(graph, subject, predicate, value, snapshot_digest, category=None,
            sources=(), valid_from=None, valid_through=None, reference_year=None, unit=None):
    for bound in (valid_from, valid_through):
        if bound:
            date.fromisoformat(bound)
    if valid_from and valid_through and valid_from > valid_through:
        raise ValueError('Observation interval ends before it starts')
    if reference_year is not None and not 1 <= int(reference_year) <= 9999:
        raise ValueError('Invalid reference year')
    sources = sorted(set(map(str, sources)))
    payload = [subject.n3(), predicate.n3(), value.n3(), snapshot_digest, sources,
               valid_from, valid_through, reference_year, unit, str(category)]
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
    node = URIRef(config.RES_NS + 'observation/' + digest)
    graph.add((node, RDF.type, VNEDU.SourceObservation))
    if category:
        graph.add((node, RDF.type, category))
    for pred, obj in ((RDF.subject, subject), (RDF.predicate, predicate), (RDF.object, value)):
        graph.add((node, pred, obj))
    graph.add((node, VNEDU.snapshotDigest, Literal(snapshot_digest)))
    status = 'qualified' if valid_from or valid_through or reference_year else 'unknown'
    graph.add((node, VNEDU.temporalStatus, Literal(status)))
    for source in sources:
        graph.add((node, PROV.wasDerivedFrom, URIRef(source)))
    for pred, val, dt in ((VNEDU.validFrom, valid_from, XSD.date),
                          (VNEDU.validThrough, valid_through, XSD.date),
                          (VNEDU.referenceYear, reference_year, XSD.gYear)):
        if val is not None:
            graph.add((node, pred, Literal(str(val), datatype=dt)))
    if unit:
        graph.add((node, VNEDU.measurementUnit, Literal(unit)))
    return node


def qualify_snapshot(graph, silver_dir):
    # Exact normalized input digests, not a claim of statement-level upstream attribution.
    inputs = {p.name: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for p in sorted(silver_dir.glob('*.json')) if p.name != 'uri_map.json'}
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    measures = {VNEDU.numberOfStudents, VNEDU.numberOfUndergraduates,
                VNEDU.numberOfPostgraduates, VNEDU.academicStaff, VNEDU.population, VNEDU.area}
    roles = {VNEDU.rector, VNEDU.director, VNEDU.councilChair}
    relations = {VNEDU.reportedGovernedBy, VNEDU.ownedBy, VNEDU.ownership,
                 VNEDU.memberOf, VNEDU.branchOf, VNEDU.educatedAt, VNEDU.locatedIn}
    types = {VNEDU.University, VNEDU.UniversitySchool, VNEDU.Academy, VNEDU.OfficerSchool}
    for s, p, o in list(graph):
        category = (VNEDU.MeasurementObservation if p in measures else
                    VNEDU.LeadershipObservation if p in roles else
                    VNEDU.ClassificationObservation if p == RDF.type and o in types else None)
        if category or p in relations:
            sources = list(graph.objects(s, PROV.wasDerivedFrom))
            if p in roles:
                sources += list(graph.objects(o, PROV.wasDerivedFrom))
            observe(graph, s, p, o, digest, category, sources,
                    unit=('square kilometre' if p == VNEDU.area else 'person') if p in measures else None)
    return {'snapshot_sha256': digest, 'inputs': inputs,
            'source_scope': 'entity-level source context; individual claim provenance not established',
            'temporal_scope': 'undated source snapshot; no current-validity assertion'}
