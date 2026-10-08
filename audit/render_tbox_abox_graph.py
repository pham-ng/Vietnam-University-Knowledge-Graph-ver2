"""Render a reproducible, data-driven TBox-ABox neighborhood."""

from pathlib import Path
import argparse
from collections import OrderedDict
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


def dot_render(lines, output, engine="dot"):
    output.parent.mkdir(parents=True, exist_ok=True)
    dot = output.with_suffix(".dot")
    dot.write_text("\n".join(lines), encoding="utf-8")
    fallback = rf"D:\Sematicweb\Graphviz\Graphviz-12.2.1-win64\bin\{engine}.exe"
    graphviz_bin = shutil.which(engine) or fallback
    command = [graphviz_bin]
    if engine == "neato":
        # -n2 preserves the hand-authored positions used by the ER/GraphRAG map.
        command.append("-n2")
    command.extend(["-Tpng", "-Gdpi=180", str(dot), "-o", str(output)])
    subprocess.run(command, check=True)


def local_classes(graph):
    """Return every local OWL class, including classes seen only in subclass axioms."""
    classes = {
        node for node in graph.subjects(RDF.type, OWL.Class)
        if str(node).startswith(str(VNEDU))
    }
    classes.update(
        node for node in graph.objects(None, RDFS.subClassOf)
        if str(node).startswith(str(VNEDU))
    )
    return classes


def local_object_signatures(graph):
    """Return asserted local object-property signatures, preserving unspecified endpoints."""
    properties = {
        node for node in graph.subjects(RDF.type, OWL.ObjectProperty)
        if str(node).startswith(str(VNEDU))
    }
    signatures = []
    for predicate in sorted(properties, key=local):
        domains = [node for node in graph.objects(predicate, RDFS.domain)
                   if str(node).startswith(str(VNEDU))]
        ranges = [node for node in graph.objects(predicate, RDFS.range)
                  if str(node).startswith(str(VNEDU))]
        domains = domains or [None]
        ranges = ranges or [None]
        for domain in domains:
            for range_node in ranges:
                signatures.append((predicate, domain, range_node))
    return signatures


SIGNATURE_MODULES = OrderedDict([
    ("Organization and governance", set((
        "branchOf hasBranch hasMember memberOf hasPart partOf ownedBy ownership "
        "governedBy directlyGovernedBy reportedGovernedBy stateManagedBy governs "
        "subordinateTo hasLeader leads director rector councilChair predecessor successor"
    ).split())),
    ("Education and people", set((
        "offersProgram offeredBy ofMajor trainsMajor inField educatedAt alumnusOf "
        "hasAlumnus hasEducationParticipant nationality birthPlace bornIn "
        "birthAreaInCurrentCrosswalk"
    ).split())),
    ("Geography and change", set("locatedIn mergedFrom mergedInto".split())),
])


def render_tbox_hierarchy_clean(graph, output):
    """Render the complete local class hierarchy without property-edge crossings."""
    classes = local_classes(graph)
    palette = {
        "Organization": "#dbeafe",
        "EducationalOrganization": "#bfdbfe",
        "HigherEducationInstitution": "#93c5fd",
        "AcademicProgram": "#fef3c7",
        "Major": "#fde68a",
        "FieldOfStudy": "#fef9c3",
        "Person": "#dcfce7",
        "AdministrativeUnit": "#d1fae5",
        "SourceObservation": "#f3e8ff",
    }
    lines = [
        "digraph TBoxHierarchyClean {",
        'graph [rankdir=LR, splines=ortho, overlap=false, concentrate=false, '
        'nodesep=0.22, ranksep=0.42, bgcolor="white", pad=0.25, '
        'fontname="Arial", fontsize=18, ordering=out];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10, '
        'color="#64748b", fillcolor="#f8fafc", margin="0.10,0.06"];',
        'edge [color="#2563eb", penwidth=1.1, arrowsize=0.6];',
    ]
    for cls in sorted(classes, key=local):
        fill = palette.get(local(cls), "#f8fafc")
        lines.append(
            f'  {node_id(cls)} [label="{local(cls)}", fillcolor="{fill}"];'
        )
    for child in sorted(classes, key=local):
        parents = sorted(
            (parent for parent in graph.objects(child, RDFS.subClassOf) if parent in classes),
            key=local,
        )
        for parent in parents:
            lines.append(f'  {node_id(child)} -> {node_id(parent)};')
    lines.append(
        '  legend [shape=note, style="filled", fillcolor="#ffffff", color="#94a3b8", '
        'label="All local OWL classes\\nBlue orthogonal arrows = asserted rdfs:subClassOf\\n'
        'Node colours group the main ontology modules"];'
    )
    lines.append("}")
    dot_render(lines, output)


def render_tbox_signatures_clean(graph, output, module_filter=None):
    """Render exact local domain-property-range rows with isolated, non-crossing edges."""
    signatures = local_object_signatures(graph)
    modules = SIGNATURE_MODULES
    grouped = OrderedDict((name, []) for name in modules)
    grouped["Other local object properties"] = []
    for signature in signatures:
        name = local(signature[0])
        target = next((module for module, names in modules.items() if name in names), "Other local object properties")
        grouped[target].append(signature)
    if module_filter:
        grouped = OrderedDict((name, rows) for name, rows in grouped.items() if name == module_filter)

    lines = [
        "digraph TBoxSignaturesClean {",
        'graph [rankdir=LR, splines=ortho, overlap=false, concentrate=false, '
        'nodesep=0.24, ranksep=0.75, bgcolor="white", pad=0.25, newrank=true];',
        'node [fontname="Arial", fontsize=10, color="#475569", margin="0.09,0.05"];',
        'edge [fontname="Arial", fontsize=8, arrowsize=0.55, penwidth=1.0];',
    ]
    module_colors = ["#2563eb", "#d97706", "#059669", "#7c3aed"]
    row_number = 0
    for module_index, (module, rows) in enumerate(grouped.items()):
        if not rows:
            continue
        color = module_colors[module_index % len(module_colors)]
        cluster_id = "cluster_" + str(module_index)
        lines.append(
            f'  subgraph {cluster_id} {{ label="{module}"; color="{color}"; '
            'style="rounded"; fontname="Arial"; fontsize=13; rankdir=LR;'
        )
        domain_ids, property_ids, range_ids = [], [], []
        for predicate, domain, range_node in rows:
            base = f"r{row_number}"
            domain_id, property_id, range_id = base + "_d", base + "_p", base + "_r"
            domain_ids.append(domain_id)
            property_ids.append(property_id)
            range_ids.append(range_id)
            domain_label = label(graph, domain) if domain else "unspecified domain"
            range_label = label(graph, range_node) if range_node else "unspecified range"
            lines.append(
                f'    {domain_id} [shape=box, style="rounded,filled", fillcolor="#eff6ff", '
                f'label="{domain_label}\\n({local(domain) if domain else "—"})"];'
            )
            lines.append(
                f'    {property_id} [shape=diamond, style="filled", fillcolor="#f3e8ff", '
                f'color="{color}", label="{local(predicate)}"];'
            )
            lines.append(
                f'    {range_id} [shape=box, style="rounded,filled", fillcolor="#f8fafc", '
                f'label="{range_label}\\n({local(range_node) if range_node else "—"})"];'
            )
            lines.append(f'    {domain_id} -> {property_id} [color="{color}"];')
            lines.append(f'    {property_id} -> {range_id} [color="{color}"];')
            row_number += 1
        lines.append("    { rank=same; " + "; ".join(domain_ids) + "; }")
        lines.append("    { rank=same; " + "; ".join(property_ids) + "; }")
        lines.append("    { rank=same; " + "; ".join(range_ids) + "; }")
        for ids in (domain_ids, property_ids, range_ids):
            for first, second in zip(ids, ids[1:]):
                lines.append(f'    {first} -> {second} [style=invis, weight=100];')
        lines.append("  }")
    lines.append(
        '  legend [shape=note, style="filled", fillcolor="#ffffff", color="#94a3b8", '
        'label="Each row is one asserted local object-property signature.\\n'
        'Left box = domain; diamond = predicate; right box = range.\\n'
        'An unspecified endpoint is shown explicitly, not invented."];'
    )
    lines.append("}")
    dot_render(lines, output)


# The map intentionally chooses one representative direction from inverse pairs.
# The complete, asserted signature inventory remains in the module figures above.
UNIQUE_RELATIONS = [
    ("governedBy", "governedBy", "#b91c1c"),
    ("hasLeader", "hasLeader", "#be123c"),
    ("locatedIn", "locatedIn", "#15803d"),
    ("offersProgram", "offersProgram", "#c2410c"),
    ("ofMajor", "ofMajor", "#7e22ce"),
    ("inField", "inField", "#0f766e"),
    ("trainsMajor", "trainsMajor", "#92400e"),
    ("educatedAt", "educatedAt", "#0369a1"),
    ("nationality", "nationality", "#047857"),
    ("bornIn", "bornIn", "#166534"),
    ("memberOf", "memberOf", "#1d4ed8"),
    ("hasBranch", "hasBranch", "#1e40af"),
    ("ownedBy", "ownedBy", "#a16207"),
    ("ownership", "ownership", "#a16207"),
    ("partOf", "partOf", "#4d7c0f"),
    ("mergedFrom", "mergedFrom", "#4b5563"),
    ("birthAreaInCurrentCrosswalk", "birthAreaInCurrentCrosswalk", "#0f766e"),
]


UNIQUE_POSITIONS = {
    # Organization and governance module (upper half).
    "Organization": (0.0, 8.2),
    "EducationalOrganization": (4.0, 8.2),
    "HigherEducationInstitution": (8.0, 8.2),
    "University": (12.0, 9.8),
    "UniversitySchool": (12.0, 7.4),
    "Branch": (16.0, 7.4),
    "GoverningBody": (8.0, 5.7),
    "Company": (13.5, 4.3),
    "OwnershipType": (16.5, 2.8),
    # People and education module (middle/lower half).
    "Person": (0.0, 4.4),
    "InstitutionLeader": (4.0, 4.8),
    "AcademicProgram": (4.0, 1.7),
    "Major": (8.0, 1.7),
    "FieldOfStudy": (12.0, 0.2),
    # Geography and temporal crosswalk module (bottom).
    "AdministrativeUnit": (0.0, -0.4),
    "Country": (4.0, -1.8),
    "Region": (8.0, -1.8),
    "Province": (12.0, -1.8),
    "FormerProvince": (16.0, -3.2),
}


def render_unique_relation_map(graph, output):
    """Render one ER/GraphRAG-style node per class and curved semantic links.

    This is a presentation view, not a new ontology. It uses asserted local
    domain/range signatures and deliberately omits inverse aliases from this
    canvas so that each conceptual relation is drawn once. The exact inventory
    is still rendered by ``render_tbox_signatures_clean``.
    """
    signatures = {
        local(predicate): (domain, range_node)
        for predicate, domain, range_node in local_object_signatures(graph)
        if domain is not None and range_node is not None
    }
    selected = [item for item in UNIQUE_RELATIONS if item[0] in signatures]
    classes = set()
    for predicate, _, _ in selected:
        domain, range_node = signatures[predicate]
        classes.update((domain, range_node))
    # Keep the main class spine visible even if a future edit removes one edge.
    classes.update(VNEDU[name] for name in (
        "Organization", "EducationalOrganization", "HigherEducationInstitution",
        "University", "Person", "AcademicProgram", "Major", "FieldOfStudy",
        "AdministrativeUnit", "Country", "Region", "Province", "FormerProvince",
        "GoverningBody", "Branch", "Company", "OwnershipType",
    ))

    palette = {
        "Organization": "#dbeafe",
        "EducationalOrganization": "#bfdbfe",
        "HigherEducationInstitution": "#93c5fd",
        "University": "#60a5fa",
        "UniversitySchool": "#bfdbfe",
        "Branch": "#c7d2fe",
        "GoverningBody": "#fecaca",
        "Company": "#fde68a",
        "OwnershipType": "#fef3c7",
        "Person": "#bbf7d0",
        "InstitutionLeader": "#dcfce7",
        "AcademicProgram": "#fed7aa",
        "Major": "#fde68a",
        "FieldOfStudy": "#fef9c3",
        "AdministrativeUnit": "#a7f3d0",
        "Country": "#d1fae5",
        "Region": "#d1fae5",
        "Province": "#d1fae5",
        "FormerProvince": "#d1fae5",
    }
    lines = [
        "digraph OntologyUniqueRelationMap {",
        'graph [layout=neato, overlap=false, splines=curved, outputorder=edgesfirst, '
        'sep="+18", esep="+10", bgcolor="white", pad=0.35, '
        'fontname="Arial", fontsize=18];',
        'node [shape=box, style="rounded,filled", fixedsize=false, pin=true, '
        'fontname="Arial", fontsize=12, color="#475569", penwidth=1.1, '
        'margin="0.13,0.08"];',
        'edge [fontname="Arial", fontsize=9, arrowsize=0.65, penwidth=1.25, '
        'labelfloat=true, labeldistance=1.3];',
    ]
    for cls in sorted(classes, key=local):
        x, y = UNIQUE_POSITIONS.get(local(cls), (0.0, 0.0))
        fill = palette.get(local(cls), "#f8fafc")
        lines.append(
            f'  {node_id(cls)} [label="{local(cls)}", fillcolor="{fill}", '
            # Graphviz neato reads fixed coordinates in points, not inches.
            f'pos="{x * 72:.1f},{y * 72:.1f}!"];'
        )

    # Show only hierarchy edges between nodes that are already in this map.
    # They are light and dashed so the business relations remain dominant.
    for child in sorted(classes, key=local):
        for parent in graph.objects(child, RDFS.subClassOf):
            if parent in classes and str(parent).startswith(str(VNEDU)):
                lines.append(
                    f'  {node_id(child)} -> {node_id(parent)} [label="is-a", '
                    'style=dashed, color="#94a3b8", penwidth=0.8, arrowsize=0.45, arrowhead=none, '
                    'constraint=false];'
                )

    for predicate, display, color in selected:
        domain, range_node = signatures[predicate]
        lines.append(
            f'  {node_id(domain)} -> {node_id(range_node)} [label="{display}", '
            f'color="{color}", fontcolor="{color}", constraint=false];'
        )

    lines.append(
        '  legend [shape=note, pin=true, pos="1224,684!", style="filled", '
        'fillcolor="#ffffff", color="#94a3b8", fontsize=10, '
        'label="One box = one local OWL class\\n'
        'Solid coloured arrows = representative domain/range relations\\n'
        'Dashed grey links = asserted is-a (subClassOf)\\n'
        'Inverse aliases are not duplicated on this canvas\\n'
        'Colours indicate visual modules, not extra OWL axioms"];'
    )
    lines.append("}")
    dot_render(lines, output, engine="neato")


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
    parser.add_argument("--clean-hierarchy-output", type=Path)
    parser.add_argument("--clean-signatures-output", type=Path)
    parser.add_argument("--clean-signatures-prefix", type=Path)
    parser.add_argument("--unique-relations-output", type=Path)
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
    if args.clean_hierarchy_output:
        render_tbox_hierarchy_clean(graph, args.clean_hierarchy_output)
    if args.clean_signatures_output:
        render_tbox_signatures_clean(graph, args.clean_signatures_output)
    if args.clean_signatures_prefix:
        slugs = {
            "Organization and governance": "organization",
            "Education and people": "education",
            "Geography and change": "geography",
            "Other local object properties": "other",
        }
        for module in [*SIGNATURE_MODULES.keys(), "Other local object properties"]:
            render_tbox_signatures_clean(
                graph,
                args.clean_signatures_prefix.parent / f"{args.clean_signatures_prefix.name}-{slugs[module]}.png",
                module_filter=module,
            )
    if args.unique_relations_output:
        render_unique_relation_map(graph, args.unique_relations_output)


if __name__ == "__main__":
    main()
