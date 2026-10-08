"""Render a reproducible, data-driven TBox-ABox neighborhood."""

from pathlib import Path
import argparse
import shutil
import subprocess

from rdflib import Graph, Namespace, RDF, RDFS, OWL

VNEDU = Namespace("https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology#")
UNIVERSITY = Namespace("https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/university/")


def local(node):
    return str(node).rstrip("/").rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def label(graph, node):
    values = list(graph.objects(node, RDFS.label))
    vi = [value for value in values if getattr(value, "language", None) == "vi"]
    return str((vi or values or [local(node)])[0]).replace('"', '\\"')


def node_id(node):
    return "n_" + "_".join(char if char.isalnum() else "_" for char in local(node))


def most_specific_types(graph, node, allowed):
    """Keep leaf asserted/materialized types so the bridge stays readable."""
    types = {item for item in graph.objects(node, RDF.type) if item in allowed}
    return {
        item for item in types
        if not any(
            other != item and (item in set(graph.transitive_objects(other, RDFS.subClassOf)))
            for other in types
        )
    }


def dot_render(lines, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    dot = output.with_suffix(".dot")
    dot.write_text("\n".join(lines), encoding="utf-8")
    dot_bin = shutil.which("dot") or r"D:\Sematicweb\Graphviz\Graphviz-12.2.1-win64\bin\dot.exe"
    subprocess.run([dot_bin, "-Tpng", "-Gdpi=180", str(dot), "-o", str(output)], check=True)


def render_tbox(graph, output):
    """Render a readable schema diagram: hierarchy plus domain-property-range signatures."""
    core = [
        "Organization", "EducationalOrganization", "HigherEducationInstitution", "University",
        "UniversitySchool", "Academy", "OfficerSchool", "NationalUniversity", "RegionalUniversity",
        "MemberInstitution", "Branch", "GoverningBody", "Ministry", "AdministrativeUnit",
        "Country", "Region", "Province", "Person", "Alumnus", "InstitutionLeader",
        "AcademicProgram", "Major", "FieldOfStudy", "SourceObservation", "LeadershipObservation",
        "MeasurementObservation", "ClassificationObservation", "EducationParticipant",
    ]
    classes = {VNEDU[name] for name in core}
    for child in list(classes):
        classes.update(parent for parent in graph.objects(child, RDFS.subClassOf)
                       if str(parent).startswith(str(VNEDU)))

    signatures = [
        ("locatedIn", "Organization", "AdministrativeUnit"),
        ("memberOf", "EducationalOrganization", "HigherEducationInstitution"),
        ("branchOf", "Branch", "HigherEducationInstitution"),
        ("governedBy", "EducationalOrganization", "GoverningBody"),
        ("offersProgram", "EducationalOrganization", "AcademicProgram"),
        ("ofMajor", "AcademicProgram", "Major"),
        ("inField", "Major", "FieldOfStudy"),
        ("trainsMajor", "EducationalOrganization", "Major"),
        ("educatedAt", "Person", "EducationalOrganization"),
        ("hasAlumnus", "EducationalOrganization", "Person"),
    ]
    lines = [
        "digraph TBoxArchitecture {",
        'graph [rankdir=LR, splines=polyline, overlap=false, nodesep=0.42, ranksep=1.0, bgcolor="white", pad=0.25];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=12, color="#607d8b", fillcolor="#e3f2fd", margin="0.12,0.08"];',
        'edge [fontname="Arial", fontsize=9, color="#78909c", arrowsize=0.7];',
        'subgraph cluster_hierarchy { label="TBox | class hierarchy"; color="#90caf9"; style="rounded"; fontname="Arial";'
    ]
    for cls in sorted(classes, key=local):
        lines.append(f'  {node_id(cls)} [label="{label(graph, cls)}\\n({local(cls)})", fillcolor="#bbdefb"];')
    for child in sorted(classes, key=local):
        for parent in graph.objects(child, RDFS.subClassOf):
            if parent in classes:
                lines.append(f'  {node_id(child)} -> {node_id(parent)} [label="subClassOf", color="#1565c0"];')
    lines.append("}")
    lines.append('subgraph cluster_signatures { label="TBox | property signatures"; color="#ce93d8"; style="rounded"; fontname="Arial";')
    for name, domain, range_name in signatures:
        prop_id = "p_" + name
        lines.append(f'  {prop_id} [shape=diamond, label="{name}", fillcolor="#f3e5f5", color="#8e24aa"];')
        lines.append(f'  {node_id(VNEDU[domain])} -> {prop_id} [label="domain", color="#8e24aa"];')
        lines.append(f'  {prop_id} -> {node_id(VNEDU[range_name])} [label="range", color="#8e24aa"];')
    lines.append('  chain [shape=note, label="property chain\\noffersProgram / ofMajor => trainsMajor", fillcolor="#fff8e1", color="#ef6c00"];')
    lines.append(f'  p_offersProgram -> chain [style=dashed, color="#ef6c00", arrowhead=none];')
    lines.append(f'  p_ofMajor -> chain [style=dashed, color="#ef6c00", arrowhead=none];')
    lines.append(f'  chain -> p_trainsMajor [style=dashed, color="#ef6c00"];')
    lines.append('  disjoint [shape=note, label="Disjointness is selective\\nMajor != FieldOfStudy\\nlegal types are time-qualified", fillcolor="#ffebee", color="#c62828"];')
    lines.append(f'  {node_id(VNEDU.Major)} -> disjoint [style=dashed, color="#c62828", arrowhead=none];')
    lines.append(f'  {node_id(VNEDU.FieldOfStudy)} -> disjoint [style=dashed, color="#c62828", arrowhead=none];')
    lines.append("}")
    lines.append('legend [shape=note, label="Blue arrows = subclass hierarchy\\nPurple diamonds = domain/range signature\\nOrange dashed = property chain\\nRed note = selected disjointness", fillcolor="#fafafa", color="#9e9e9e"];')
    lines.append("}")
    dot_render(lines, output)


def render_abox(graph, output, max_programs, max_majors):
    """Render a readable instance neighborhood for one real university."""
    university = UNIVERSITY["dai-hoc-bach-khoa-ha-noi"]
    types = {node for node in graph.objects(university, RDF.type) if str(node).startswith(str(VNEDU))}
    types.update({
        VNEDU.Organization,
        VNEDU.EducationalOrganization,
        VNEDU.HigherEducationInstitution,
        VNEDU.University,
        VNEDU.GoverningBody,
        VNEDU.Ministry,
        VNEDU.AdministrativeUnit,
        VNEDU.Province,
        VNEDU.Region,
        VNEDU.Country,
        VNEDU.AcademicProgram,
        VNEDU.Major,
        VNEDU.FieldOfStudy,
    })
    classes = set(types)
    for child in list(classes):
        classes.update(parent for parent in graph.objects(child, RDFS.subClassOf) if str(parent).startswith(str(VNEDU)))
    programs = list(graph.objects(university, VNEDU.offersProgram))[:max_programs]
    majors = list(graph.objects(university, VNEDU.trainsMajor))[:max_majors]
    governing = list(graph.objects(university, VNEDU.governedBy))
    locations = list(graph.objects(university, VNEDU.locatedIn))
    fields = []
    for major in majors:
        fields.extend(graph.objects(major, VNEDU.inField))
    fields = list(dict.fromkeys(fields))[:4]
    abox = list(dict.fromkeys([university, *governing, *locations, *fields, *programs, *majors]))

    lines = [
        "digraph TBoxABox {",
        'graph [rankdir=LR, splines=polyline, overlap=false, nodesep=0.35, ranksep=0.8, bgcolor="white", pad=0.25];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=12, color="#607d8b", fillcolor="#e3f2fd", margin="0.10,0.07"];',
        'edge [fontname="Arial", fontsize=9, color="#78909c", arrowsize=0.7];',
        'subgraph cluster_tbox { label="TBox | classes and axioms"; color="#90caf9"; style="rounded"; fontname="Arial";',
    ]
    for cls in sorted(classes, key=local):
        lines.append(f'  {node_id(cls)} [label="{label(graph, cls)}\\n({local(cls)})", fillcolor="#bbdefb"];')
    for child in sorted(classes, key=local):
        for parent in graph.objects(child, RDFS.subClassOf):
            if parent in classes:
                lines.append(f'  {node_id(child)} -> {node_id(parent)} [label="subClassOf", color="#1565c0"];')
    lines.append("}")
    lines.append('subgraph cluster_abox { label="ABox | real individuals and links"; color="#ffcc80"; style="rounded"; fontname="Arial";')
    for node in abox:
        fill = "#ffcc80" if node == university else "#fff3e0"
        lines.append(f'  {node_id(node)} [label="{label(graph, node)}\\n({local(node)})", fillcolor="{fill}"];')
    lines.append("}")
    for node in abox:
        for cls in most_specific_types(graph, node, classes):
            lines.append(f'  {node_id(node)} -> {node_id(cls)} [label="rdf:type", style=dashed, color="#8e24aa"];')
    colors = {VNEDU.governedBy: "#c62828", VNEDU.locatedIn: "#2e7d32", VNEDU.offersProgram: "#ef6c00", VNEDU.trainsMajor: "#6d4c41", VNEDU.inField: "#00838f"}
    for predicate, objects in [(VNEDU.governedBy, governing), (VNEDU.locatedIn, locations), (VNEDU.offersProgram, programs), (VNEDU.trainsMajor, majors)]:
        for obj in objects:
            lines.append(f'  {node_id(university)} -> {node_id(obj)} [label="{local(predicate)}", color="{colors[predicate]}"];')
    for major in majors:
        for field in graph.objects(major, VNEDU.inField):
            if field in abox:
                lines.append(f'  {node_id(major)} -> {node_id(field)} [label="inField", color="{colors[VNEDU.inField]}"];')
    for program in programs:
        for major in graph.objects(program, VNEDU.ofMajor):
            if major in abox:
                lines.append(f'  {node_id(program)} -> {node_id(major)} [label="ofMajor", color="#6a1b9a"];')
    lines.append('legend [shape=note, fillcolor="#fafafa", color="#9e9e9e", label="Legend\\nrdf:type = dashed purple\\nsubClassOf = blue\\nABox links = coloured"];')
    lines.append("}")
    dot_render(lines, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, default=Path("ontology/vnedu.ttl"))
    parser.add_argument("--data", type=Path, default=Path("data/gold/vnedu-all.ttl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tbox-output", type=Path)
    parser.add_argument("--max-programs", type=int, default=4)
    parser.add_argument("--max-majors", type=int, default=4)
    args = parser.parse_args()
    graph = Graph()
    graph.parse(args.ontology, format="turtle")
    graph.parse(args.data, format="turtle")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    render_abox(graph, args.output, args.max_programs, args.max_majors)
    if args.tbox_output:
        render_tbox(graph, args.tbox_output)


if __name__ == "__main__":
    main()
