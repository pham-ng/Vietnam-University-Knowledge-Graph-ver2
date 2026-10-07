"""Render a readable, report-ready overview of the local VN-Edu ontology.

This is deliberately a deterministic renderer for the committed Turtle file.  It
is not a Protégé screenshot: it gives the report a reproducible visual artefact
and avoids implying that a GUI export was obtained when it was not.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from rdflib import Graph, Namespace, RDF, RDFS, OWL


VNEDU = Namespace("https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology#")


def local(term) -> str:
    value = str(term)
    if value.startswith(str(VNEDU)):
        return value[len(str(VNEDU)) :]
    if value.startswith("http://schema.org/"):
        return "schema:" + value.rsplit("/", 1)[-1]
    if value.startswith("http://www.w3.org/2004/02/skos/core#"):
        return "skos:" + value.rsplit("#", 1)[-1]
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def class_colour(name: str) -> str:
    if name.endswith("Observation") or name in {"LeadershipObservation", "ClassificationObservation"}:
        return "#f4b183"
    if name in {"Province", "FormerProvince", "Region", "Country", "AdministrativeUnit", "CentrallyGovernedCity", "ProvincialPeoplesCommittee"}:
        return "#9dc3e6"
    if name in {"Person", "Alumnus", "InstitutionLeader", "EducationParticipant"}:
        return "#c6e0b4"
    if name in {"Organization", "EducationalOrganization", "HigherEducationInstitution", "University", "NationalUniversity", "RegionalUniversity", "Academy", "Company", "GoverningBody", "Ministry", "Branch", "School", "VocationalCollege", "PrivateInstitution", "PublicInstitution", "MilitaryInstitution", "PoliceInstitution", "MemberInstitution", "UniversitySchool", "OfficerSchool", "DefunctInstitution", "ProvincialPeoplesCommittee"}:
        return "#b4c7e7"
    return "#d9e1f2"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, default=Path("ontology/vnedu.ttl"))
    parser.add_argument("--output", type=Path, default=Path("docs/report/figures/ontology-ttl-derived-reference.png"))
    args = parser.parse_args()

    graph = Graph().parse(args.ontology, format="turtle")
    classes = {term for term in graph.subjects(RDF.type, OWL.Class) if str(term).startswith(str(VNEDU))}
    class_names = {term: local(term) for term in classes}

    hierarchy = nx.DiGraph()
    hierarchy.add_nodes_from(class_names.values())
    for child, _, parent in graph.triples((None, RDFS.subClassOf, None)):
        if child in classes and parent in classes:
            hierarchy.add_edge(class_names[child], class_names[parent])

    selected = {
        "locatedIn", "partOf", "memberOf", "branchOf", "governedBy", "directlyGovernedBy",
        "reportedGovernedBy", "stateManagedBy", "ownedBy", "hasLeader", "educatedAt",
        "offersProgram", "ofMajor", "trainsMajor", "predecessor", "successor",
        "bornIn", "birthAreaInCurrentCrosswalk", "nationality", "mergedInto",
    }
    relation_rows: list[tuple[str, str, str]] = []
    for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
        prop_name = local(prop)
        if not str(prop).startswith(str(VNEDU)) or prop_name not in selected:
            continue
        domains = [local(item) for item in graph.objects(prop, RDFS.domain)]
        ranges = [local(item) for item in graph.objects(prop, RDFS.range)]
        for domain in domains:
            for range_ in ranges:
                relation_rows.append((domain, prop_name, range_))

    fig, (left, right) = plt.subplots(1, 2, figsize=(20, 12), gridspec_kw={"width_ratios": [1.35, 1]})
    fig.patch.set_facecolor("white")
    fig.suptitle(
        "VN-Edu ontology 2.2 — class hierarchy and selected relations",
        fontsize=19,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.958,
        f"Generated deterministically from ontology/vnedu.ttl • {len(classes)} classes • "
        f"{len({p for p in graph.subjects(RDF.type, OWL.ObjectProperty) if str(p).startswith(str(VNEDU))})} object properties • "
        f"{len({p for p in graph.subjects(RDF.type, OWL.DatatypeProperty) if str(p).startswith(str(VNEDU))})} datatype properties",
        ha="center",
        fontsize=10,
        color="#555555",
    )

    pos = nx.spring_layout(hierarchy, seed=19, k=2.3, iterations=400, scale=1.0)
    nx.draw_networkx_edges(
        hierarchy,
        pos,
        ax=left,
        edge_color="#7f8c8d",
        width=0.9,
        arrows=True,
        arrowsize=9,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.03",
    )
    nx.draw_networkx_nodes(
        hierarchy,
        pos,
        ax=left,
        node_color=[class_colour(node) for node in hierarchy.nodes],
        node_size=760,
        edgecolors="#40566b",
        linewidths=0.7,
    )
    nx.draw_networkx_labels(hierarchy, pos, ax=left, font_size=6.1, font_weight="bold")
    left.set_title("Named local classes and rdfs:subClassOf", fontsize=13, pad=12)
    left.axis("off")

    relations = nx.DiGraph()
    edge_labels: dict[tuple[str, str], str] = {}
    for domain, prop_name, range_ in relation_rows:
        relations.add_edge(domain, range_, property=prop_name)
        key = (domain, range_)
        edge_labels[key] = (edge_labels[key] + "\n" if key in edge_labels else "") + prop_name
    rpos = nx.spring_layout(relations, seed=23, k=1.45, iterations=300)
    nx.draw_networkx_edges(
        relations,
        rpos,
        ax=right,
        edge_color="#557a95",
        width=1.0,
        arrows=True,
        arrowsize=11,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.08",
    )
    nx.draw_networkx_nodes(
        relations,
        rpos,
        ax=right,
        node_color=[class_colour(node) for node in relations.nodes],
        node_size=950,
        edgecolors="#40566b",
        linewidths=0.7,
    )
    nx.draw_networkx_labels(relations, rpos, ax=right, font_size=6.8, font_weight="bold")
    nx.draw_networkx_edge_labels(
        relations,
        rpos,
        edge_labels=edge_labels,
        ax=right,
        font_size=5.7,
        label_pos=0.52,
        rotate=False,
        bbox={"alpha": 0.8, "color": "white", "pad": 0.5},
    )
    right.set_title("Selected domain–property–range signatures", fontsize=13, pad=12)
    right.axis("off")

    legend = [
        ("#b4c7e7", "organizations"),
        ("#9dc3e6", "geography"),
        ("#c6e0b4", "people / participation"),
        ("#f4b183", "qualified observations"),
    ]
    fig.text(0.5, 0.018, "  ".join(f"■ {label}" for colour, label in legend), ha="center", fontsize=9, color="#40566b")
    fig.text(
        0.5,
        0.002,
        "Visual overview from the committed Turtle; it is not a screenshot or proof of Protégé layout. "
        "Dashed/selected relation view omits less central properties for readability.",
        ha="center",
        fontsize=8,
        color="#666666",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=250, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {args.output} ({len(classes)} classes, {len(relation_rows)} selected signatures)")


if __name__ == "__main__":
    main()
