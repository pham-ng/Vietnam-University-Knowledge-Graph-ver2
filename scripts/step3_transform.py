"""BƯỚC 3b — Chuyển dữ liệu đã tích hợp (tầng SILVER data/silver) sang RDF theo ontology vnedu (dữ liệu 4 sao).

Đầu ra: tầng GOLD data/gold/vnedu-data.ttl

* Mỗi thực thể có HTTP URI riêng, ổn định (slug từ tên tiếng Việt), dereference được qua app/server.py
* Chỉ khẳng định MỘT chiều của các cặp thuộc tính nghịch đảo (memberOf, governedBy, alumnusOf, ...);
  chiều ngược lại, lớp định nghĩa, chuỗi thuộc tính... do bộ suy luận sinh ra ở bước 5
* Nguồn gốc từng thực thể: prov:wasDerivedFrom -> item Wikidata và bản sửa đổi (oldid) cụ thể của bài viwiki
"""
import json
import re
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, RDF, RDFS, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import DBO, GEO, SCHEMA, VNEDU, Minter, bind_prefixes, field_uri, major_uri, read_csv, record_manifest, vn_key  # noqa: E402

PROV = Namespace("http://www.w3.org/ns/prov#")
WD = Namespace("http://www.wikidata.org/entity/")
CLEAN = config.SILVER_DIR

KIND_CLASS = {
    "University": VNEDU.University, "UniversitySchool": VNEDU.UniversitySchool, "Academy": VNEDU.Academy,
    "OfficerSchool": VNEDU.OfficerSchool, "NationalUniversity": VNEDU.NationalUniversity,
    "RegionalUniversity": VNEDU.RegionalUniversity, "HigherEducationInstitution": VNEDU.HigherEducationInstitution,
    "Branch": VNEDU.Branch, "VocationalCollege": VNEDU.VocationalCollege,
    "Seminary": VNEDU.EducationalOrganization, "Institute": VNEDU.EducationalOrganization,
    "AcademicUnit": VNEDU.EducationalOrganization,
}
BODY_CLASS = {"Ministry": VNEDU.Ministry, "ProvincialPeoplesCommittee": VNEDU.ProvincialPeoplesCommittee,
              "GoverningBody": VNEDU.GoverningBody, "Company": VNEDU.Company}
# Cơ quan có cá thể tham chiếu sẵn trong ontology (dùng trong lớp định nghĩa MilitaryInstitution/PoliceInstitution)
ONTOLOGY_INDIVIDUALS = {vn_key("Bộ Quốc phòng"): VNEDU.MinistryOfNationalDefence,
                        vn_key("Bộ Công an"): VNEDU.MinistryOfPublicSecurity}


def load(name):
    return json.loads((CLEAN / f"{name}.json").read_text(encoding="utf-8"))


def lit(v, dt=None, lang=None):
    return None if v in (None, "", []) else Literal(v, datatype=dt, lang=lang)


def add_reused(g, s, p, item):
    """Gắn giá trị là URI Wikidata có sẵn (không tạo URI mới) + nhãn để hiển thị/truy vấn."""
    o = WD[item["qid"]]
    g.add((s, p, o))
    for lang in ("vi", "en"):
        if item.get(lang):
            g.add((o, RDFS.label, Literal(item[lang], lang=lang)))


def add_media(g, s, p, m):
    """Ảnh/biểu trưng: URI của chính tệp trên Wikimedia (tái sử dụng), kèm ảnh thu nhỏ, trang mô tả, giấy phép, ghi công."""
    if not m:
        return
    o = URIRef(m["url"])
    g.add((s, p, o))
    g.add((o, RDF.type, SCHEMA.ImageObject))
    if m.get("thumb"):
        g.add((o, SCHEMA.thumbnailUrl, URIRef(m["thumb"])))
    if m.get("page"):
        g.add((o, SCHEMA.mainEntityOfPage, URIRef(m["page"])))
    if m.get("license"):
        g.add((o, SCHEMA.license, Literal(m["license"])))
    if m.get("artist"):
        g.add((o, SCHEMA.creditText, Literal(m["artist"])))


def add(g, s, p, o):
    if o is not None:
        g.add((s, p, o))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    insts, bodies, people, provs = load("institutions"), load("governing_bodies"), load("people"), load("provinces")
    g = Graph()
    bind_prefixes(g)
    g.bind("prov", PROV)

    # ------------------------------------------------------------ URI
    m_org, m_body, m_prov, m_person, m_reg = (Minter(k) for k in ("university", "organization", "province", "person", "region"))
    u_inst = {k: m_org.mint(i["name_vi"], i["name_en"], k) for k, i in sorted(insts.items())}
    u_body = {k: ONTOLOGY_INDIVIDUALS.get(vn_key(b["name_vi"])) or m_body.mint(b["name_vi"], k) for k, b in sorted(bodies.items())}
    u_prov = {k: m_prov.mint(p["name_vi"], k) for k, p in sorted(provs.items(), key=lambda x: (x[1]["status"], x[0]))}
    u_person = {k: m_person.mint(p["name_vi"], p["name_en"], k) for k, p in sorted(people.items())}
    country = URIRef(config.RES_NS + "country/viet-nam")

    # ------------------------------------------------------------ địa lý
    g.add((country, RDF.type, VNEDU.Country))
    g.add((country, RDFS.label, Literal("Việt Nam", lang="vi")))
    g.add((country, RDFS.label, Literal("Vietnam", lang="en")))
    regions = {}
    for name, en in (("Bắc Bộ", "Northern Vietnam"), ("Trung Bộ", "Central Vietnam"), ("Nam Bộ", "Southern Vietnam")):
        r = regions[name] = m_reg.mint(name)
        g.add((r, RDF.type, VNEDU.Region))
        g.add((r, RDFS.label, Literal(name, lang="vi")))
        g.add((r, RDFS.label, Literal(en, lang="en")))
        g.add((r, VNEDU.partOf, country))
    for k, p in provs.items():
        s = u_prov[k]
        if p["status"] == "current":
            g.add((s, RDF.type, VNEDU.CentrallyGovernedCity if p["central_city"] else VNEDU.Province))
            g.add((s, VNEDU.partOf, regions[p["region"]]))
        else:
            g.add((s, RDF.type, VNEDU.FormerProvince))
            add(g, s, VNEDU.mergedInto, u_prov.get(p["merged_into"]))
        add(g, s, RDFS.label, lit(p["name_vi"], lang="vi"))
        add(g, s, RDFS.label, lit(p["name_en"], lang="en"))
        add(g, s, VNEDU.population, lit(p["population"], XSD.nonNegativeInteger))
        add(g, s, VNEDU.area, lit(p["area"], XSD.decimal))
        add(g, s, GEO.lat, lit(p["lat"], XSD.decimal))
        add(g, s, GEO.long, lit(p["long"], XSD.decimal))
        add(g, s, PROV.wasDerivedFrom, WD[k])

    # ------------------------------------------------------------ cơ quan chủ quản / doanh nghiệp
    for k, b in bodies.items():
        s = u_body[k]
        g.add((s, RDF.type, BODY_CLASS[b["kind"]]))
        g.add((s, RDFS.label, Literal(b["name_vi"], lang="vi")))
        add(g, s, RDFS.label, lit(b.get("name_en"), lang="en"))
        for sup in b.get("subordinate_to", []):
            g.add((s, VNEDU.subordinateTo, u_body[sup]))

    # ------------------------------------------------------------ cơ sở giáo dục
    for k, i in insts.items():
        s = u_inst[k]
        g.add((s, RDF.type, KIND_CLASS[i["kind"]]))
        add(g, s, RDFS.label, lit(i["name_vi"], lang="vi"))
        add(g, s, SKOS.prefLabel, lit(i["name_vi"], lang="vi"))
        add(g, s, RDFS.label, lit(i["name_en"], lang="en"))
        for n in i["short_names"]:
            g.add((s, VNEDU.shortName, Literal(n)))
        for n in i["former_names"]:
            g.add((s, VNEDU.formerName, Literal(n, lang="vi")))
        for c in i["admission_codes"]:
            g.add((s, VNEDU.admissionCode, Literal(c)))
        add(g, s, VNEDU.foundingYear, lit(str(i["founding_year"]) if i.get("founding_year") else None, XSD.gYear))
        add(g, s, VNEDU.dissolutionYear, lit(str(i["dissolution_year"]) if i.get("dissolution_year") else None, XSD.gYear))
        if i.get("ownership"):
            g.add((s, VNEDU.ownership, VNEDU.PublicOwnership if i["ownership"] == "public" else VNEDU.PrivateOwnership))
        add(g, s, VNEDU.motto, lit(i["motto_vi"], lang="vi"))
        for text, lang in i["motto_other"]:
            add(g, s, VNEDU.motto, lit(text, lang=lang or None))
        add(g, s, VNEDU.numberOfStudents, lit(i.get("students"), XSD.nonNegativeInteger))
        add(g, s, VNEDU.numberOfUndergraduates, lit(i.get("undergraduates"), XSD.nonNegativeInteger))
        add(g, s, VNEDU.numberOfPostgraduates, lit(i.get("postgraduates"), XSD.nonNegativeInteger))
        add(g, s, VNEDU.academicStaff, lit(i.get("academic_staff"), XSD.nonNegativeInteger))
        add(g, s, VNEDU.address, lit(i.get("address")))
        for n in i.get("alt_names", []):
            g.add((s, SKOS.altLabel, Literal(n)))
        add(g, s, SCHEMA.foundingDate, lit(i.get("founding_date"), XSD.date))
        add(g, s, SCHEMA.telephone, lit(i.get("telephone")))
        add(g, s, SCHEMA.email, lit(i.get("email")))
        add(g, s, VNEDU.campus, lit(i.get("campus")))
        add(g, s, VNEDU.funding, lit(i.get("funding")))
        add(g, s, DBO.abstract, lit(i.get("abstract"), lang="vi"))
        add(g, s, VNEDU.history, lit(i.get("history"), lang="vi"))
        add_media(g, s, SCHEMA.logo, i.get("logo"))
        add_media(g, s, SCHEMA.image, i.get("image"))
        # Đối tác: trỏ thẳng tới cơ sở trong dataset nếu có, nếu không thì tới URI Wikidata (tái sử dụng)
        qid_inst = {x["qid"]: kk for kk, x in insts.items() if x.get("qid")}
        for pt in i.get("partners", []):
            if pt["qid"] in qid_inst:
                g.add((s, DBO.affiliation, u_inst[qid_inst[pt["qid"]]]))
            else:
                add_reused(g, s, DBO.affiliation, {"qid": pt["qid"], "vi": pt["name"]})
        add(g, s, GEO.lat, lit(i.get("lat"), XSD.decimal))
        add(g, s, GEO.long, lit(i.get("long"), XSD.decimal))
        if i.get("website"):
            g.add((s, VNEDU.website, URIRef(i["website"].replace(" ", "%20"))))
        add(g, s, VNEDU.locatedIn, u_prov.get(i.get("province")))
        for m in i["member_of"]:
            g.add((s, VNEDU.memberOf, u_inst[m]))
        for m in i["branch_of"]:
            g.add((s, VNEDU.branchOf, u_inst[m]))
        for b in i["governed_by"]:
            g.add((s, VNEDU.governedBy, u_body[b]))
        for b in i["owned_by"]:
            g.add((s, VNEDU.ownedBy, u_body[b]))
        if i["qid"]:
            g.add((s, PROV.wasDerivedFrom, WD[i["qid"]]))
        if i["viwiki"] and i["viwiki_revid"]:
            g.add((s, PROV.wasDerivedFrom, URIRef(f"https://vi.wikipedia.org/w/index.php?oldid={i['viwiki_revid']}")))

    # ------------------------------------------------------------ con người
    for k, p in people.items():
        s = u_person[k]
        g.add((s, RDF.type, VNEDU.Person))
        add(g, s, RDFS.label, lit(p["name_vi"], lang="vi"))
        add(g, s, RDFS.label, lit(p["name_en"], lang="en"))
        add(g, s, FOAF.name, lit(p["name_vi"] or p["name_en"]))
        # Wikidata ghi ngày 01-01 khi chỉ biết năm -> không phát sinh ngày sinh giả
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.get("birth_date") or "") and not p["birth_date"].endswith("-01-01"):
            g.add((s, VNEDU.birthDate, Literal(p["birth_date"], datatype=XSD.date)))
        # TÁI SỬ DỤNG URI có sẵn thay vì tạo mới: giá trị giới tính / nghề nghiệp là chính item Wikidata
        # (schema:gender, schema:hasOccupation) — ta không mô tả gì thêm về chúng ngoài nhãn để hiển thị.
        if p.get("gender"):
            add_reused(g, s, SCHEMA.gender, p["gender"])
        add(g, s, VNEDU.honorific, lit(p.get("honorific")))
        for o in p["occupations"]:
            add_reused(g, s, SCHEMA.hasOccupation, o)
        for sch in p["alumnus_of"]:
            g.add((s, VNEDU.alumnusOf, u_inst[sch]))
        for l in p["leads"]:
            role_prop = {"rector": VNEDU.rector, "director": VNEDU.director, "chair": VNEDU.councilChair}[l["role"]]
            g.add((u_inst[l["org"]], role_prop, s))
        if p["qid"]:
            g.add((s, PROV.wasDerivedFrom, WD[p["qid"]]))

    # ------------------------------------------------------------ ngành / chương trình (dữ liệu nhập tay)
    for r in read_csv(config.CURATED_DIR / "fields.csv"):
        f = field_uri(r["code"])
        g.add((f, RDF.type, VNEDU.FieldOfStudy))
        g.add((f, VNEDU.code, Literal(r["code"])))
        for lang in ("vi", "en"):
            g.add((f, SKOS.prefLabel, Literal(r[f"name_{lang}"], lang=lang)))
            g.add((f, RDFS.label, Literal(r[f"name_{lang}"], lang=lang)))
    majors = {}
    for r in read_csv(config.CURATED_DIR / "majors.csv"):
        m = major_uri(r["code"])
        majors[r["code"]] = r
        g.add((m, RDF.type, VNEDU.Major))
        g.add((m, VNEDU.code, Literal(r["code"])))
        for lang in ("vi", "en"):
            g.add((m, SKOS.prefLabel, Literal(r[f"name_{lang}"], lang=lang)))
            g.add((m, RDFS.label, Literal(r[f"name_{lang}"], lang=lang)))
        g.add((m, VNEDU.inField, field_uri(r["field_code"])))
    alias = {}
    for k, i in insts.items():
        for n in [i["name_vi"], i["viwiki"]] + i["former_names"]:
            if n:
                alias.setdefault(vn_key(n), k)
                alias.setdefault(vn_key(re.sub(r"^Trường ", "", n)), k)
    missing = set()
    for r in read_csv(config.CURATED_DIR / "programs.csv"):
        n = r["university_name_vi"]
        k = alias.get(vn_key(n)) or alias.get(vn_key(re.sub(r"^Trường ", "", n)))
        if not k or r["major_code"] not in majors:
            missing.add(n)
            continue
        prog = URIRef(f"{config.RES_NS}program/{u_inst[k].rsplit('/', 1)[1]}-{r['major_code']}")
        g.add((prog, RDF.type, VNEDU.AcademicProgram))
        g.add((prog, RDFS.label, Literal(f"{majors[r['major_code']]['name_vi']} – {insts[k]['name_vi']}", lang="vi")))
        g.add((prog, VNEDU.ofMajor, major_uri(r["major_code"])))
        g.add((u_inst[k], VNEDU.offersProgram, prog))
        add(g, prog, VNEDU.degreeLevel, lit(r["degree_level"], lang="vi"))
    if missing:
        print(f"  ! programs.csv: không khớp {sorted(missing)}")

    # bảng ánh xạ khoá -> URI cho bước liên kết
    keymap = {"institution": {k: str(v) for k, v in u_inst.items()}, "body": {k: str(v) for k, v in u_body.items()},
              "province": {k: str(v) for k, v in u_prov.items()}, "person": {k: str(v) for k, v in u_person.items()},
              "region": {k: str(v) for k, v in regions.items()}, "country": str(country)}
    (CLEAN / "uri_map.json").write_text(json.dumps(keymap, ensure_ascii=False, indent=1), encoding="utf-8")

    config.RDF_DIR.mkdir(parents=True, exist_ok=True)
    g.serialize(config.DATA_TTL, format="turtle", encoding="utf-8")
    record_manifest("gold", config.DATA_TTL, len(g), "triples", derived_from="data/silver/*.json")
    print(f"  -> {config.DATA_TTL.relative_to(config.ROOT)} ({len(g)} triple)")
    print("Xong bước 3.")


if __name__ == "__main__":
    main()
