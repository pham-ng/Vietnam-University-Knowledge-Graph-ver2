# Sơ đồ ontology VN-Edu

*Sinh tự động từ `ontology/vnedu.ttl` bởi `scripts/gen_docs.py`* — 39 lớp, 38 thuộc tính quan hệ, 27 thuộc tính dữ liệu, 862 triple.

Release 2.2 passes the OWL API `OWL2RLProfile` gate with zero violations; see `data/reports/owl2rl-profile.txt`.

Mũi tên rỗng = kế thừa (`rdfs:subClassOf`); mũi tên có nhãn = thuộc tính quan hệ (domain → range).

![Protégé OntoGraf screenshot of the committed ontology](report/figures/ontology-protege-screenshot.png)

The same committed `ontology/vnedu.ttl` was also loaded into GraphDB Workbench 11.1.0
(`vnedu-ontology-d`) for a repository-backed view. The class-hierarchy view reports 57
classes, while the visual graph below focuses on `vnedu:University` and its asserted
superclass/alignment links. These are direct screenshots of GraphDB, not generated
illustrations.

![GraphDB class hierarchy of the committed ontology](report/figures/ontology-graphdb-hierarchy.png)

![GraphDB visual graph for vnedu:University](report/figures/ontology-graphdb-visual.png)

## TBox–ABox view

The repository-backed view is now also populated with the serving union
`data/gold/vnedu-all.ttl`, not only the ontology file. In the local GraphDB repository
`vnedu-ontology-d`, the verified SPARQL count is 74,972 total statements: 73,794 explicit
and 1,178 inferred statements. The saved visual configuration
`VN-Edu TBox-ABox instance neighborhood` starts at the real individual
`resource/university/dai-hoc-bach-khoa-ha-noi` and exposes its most-specific types,
governance, location, programmes, majors and fields.

The schema and instance layers are intentionally separated in the report. The TBox view
shows the multi-level class hierarchy plus domain–property–range signatures and the
`offersProgram / ofMajor => trainsMajor` chain. The ABox view shows named individuals and
their asserted or materialized links. A dashed `rdf:type` edge is a typing assertion or
entailment; it is not a relational foreign key. Domain and range provide OWL semantic
typing, while cardinality, datatype, temporal and completeness rules are checked by
SHACL.

![Data-driven TBox architecture](report/figures/tbox-architecture.png)

![Data-driven ABox instance neighborhood](report/figures/abox-instance-neighborhood.png)

```mermaid
classDiagram
  direction LR
  class AcademicProgram["AcademicProgram<br/>Chương trình đào tạo"]
  class Academy["Academy<br/>Học viện"]
  class AdministrativeUnit["AdministrativeUnit<br/>Đơn vị hành chính / vùng"]
  class Alumnus["Alumnus<br/>Cựu sinh viên"]
  class Branch["Branch<br/>Phân hiệu"]
  class CentrallyGovernedCity["CentrallyGovernedCity<br/>Thành phố trực thuộc trung ương"]
  class ClassificationObservation["ClassificationObservation<br/>ClassificationObservation"]
  class Company["Company<br/>Doanh nghiệp / tập đoàn giáo dục"]
  class Country["Country<br/>Quốc gia"]
  class DefunctInstitution["DefunctInstitution<br/>Cơ sở đã giải thể / sáp nhập"]
  class EducationParticipant["EducationParticipant<br/>EducationParticipant"]
  class EducationalOrganization["EducationalOrganization<br/>Cơ sở giáo dục"]
  class FieldOfStudy["FieldOfStudy<br/>Lĩnh vực đào tạo"]
  class FormerProvince["FormerProvince<br/>Tỉnh cũ (trước 01/07/2025)"]
  class GoverningBody["GoverningBody<br/>Cơ quan chủ quản"]
  class HigherEducationInstitution["HigherEducationInstitution<br/>Cơ sở giáo dục đại học"]
  class InstitutionLeader["InstitutionLeader<br/>Người đứng đầu cơ sở giáo dục"]
  class LeadershipObservation["LeadershipObservation<br/>LeadershipObservation"]
  class Major["Major<br/>Ngành đào tạo"]
  class MeasurementObservation["MeasurementObservation<br/>MeasurementObservation"]
  class MemberInstitution["MemberInstitution<br/>Trường/đơn vị thành viên"]
  class MilitaryInstitution["MilitaryInstitution<br/>Cơ sở đào tạo quân đội"]
  class Ministry["Ministry<br/>Bộ / cơ quan ngang bộ"]
  class NationalUniversity["NationalUniversity<br/>Đại học quốc gia"]
  class OfficerSchool["OfficerSchool<br/>Trường sĩ quan"]
  class Organization["Organization<br/>Tổ chức"]
  class OwnershipType["OwnershipType<br/>Loại hình sở hữu"]
  class Person["Person<br/>Người"]
  class PoliceInstitution["PoliceInstitution<br/>Cơ sở đào tạo Công an nhân dân"]
  class PrivateInstitution["PrivateInstitution<br/>Cơ sở tư thục"]
  class Province["Province<br/>Tỉnh / thành phố (hiện hành)"]
  class ProvincialPeoplesCommittee["ProvincialPeoplesCommittee<br/>Ủy ban nhân dân cấp tỉnh"]
  class PublicInstitution["PublicInstitution<br/>Cơ sở công lập"]
  class Region["Region<br/>Miền"]
  class RegionalUniversity["RegionalUniversity<br/>Đại học vùng"]
  class SourceObservation["SourceObservation<br/>SourceObservation"]
  class University["University<br/>Đại học"]
  class UniversitySchool["UniversitySchool<br/>Trường đại học"]
  class VocationalCollege["VocationalCollege<br/>Trường cao đẳng"]
  HigherEducationInstitution <|-- Academy
  Person <|-- Alumnus
  EducationalOrganization <|-- Branch
  Province <|-- CentrallyGovernedCity
  SourceObservation <|-- ClassificationObservation
  Organization <|-- Company
  AdministrativeUnit <|-- Country
  EducationalOrganization <|-- DefunctInstitution
  Person <|-- EducationParticipant
  Organization <|-- EducationalOrganization
  AdministrativeUnit <|-- FormerProvince
  Organization <|-- GoverningBody
  EducationalOrganization <|-- HigherEducationInstitution
  Person <|-- InstitutionLeader
  SourceObservation <|-- LeadershipObservation
  SourceObservation <|-- MeasurementObservation
  EducationalOrganization <|-- MemberInstitution
  GoverningBody <|-- Ministry
  University <|-- NationalUniversity
  HigherEducationInstitution <|-- OfficerSchool
  AdministrativeUnit <|-- Province
  GoverningBody <|-- ProvincialPeoplesCommittee
  AdministrativeUnit <|-- Region
  University <|-- RegionalUniversity
  HigherEducationInstitution <|-- University
  HigherEducationInstitution <|-- UniversitySchool
  EducationalOrganization <|-- VocationalCollege
  Person --> EducationalOrganization : alumnusOf
  Person --> AdministrativeUnit : birthAreaInCurrentCrosswalk
  Person --> AdministrativeUnit : bornIn
  Branch --> HigherEducationInstitution : branchOf
  EducationalOrganization --> Person : councilChair
  EducationalOrganization --> GoverningBody : directlyGovernedBy
  EducationalOrganization --> Person : director
  Person --> EducationalOrganization : educatedAt
  EducationalOrganization --> GoverningBody : governedBy
  GoverningBody --> EducationalOrganization : governs
  EducationalOrganization --> Person : hasAlumnus
  HigherEducationInstitution --> Branch : hasBranch
  EducationalOrganization --> Person : hasEducationParticipant
  Organization --> Person : hasLeader
  HigherEducationInstitution --> EducationalOrganization : hasMember
  AdministrativeUnit --> AdministrativeUnit : hasPart
  Major --> FieldOfStudy : inField
  Person --> Organization : leads
  Organization --> AdministrativeUnit : locatedIn
  EducationalOrganization --> HigherEducationInstitution : memberOf
  Province --> FormerProvince : mergedFrom
  FormerProvince --> Province : mergedInto
  Person --> Country : nationality
  AcademicProgram --> Major : ofMajor
  AcademicProgram --> EducationalOrganization : offeredBy
  EducationalOrganization --> AcademicProgram : offersProgram
  EducationalOrganization --> Company : ownedBy
  EducationalOrganization --> OwnershipType : ownership
  AdministrativeUnit --> AdministrativeUnit : partOf
  EducationalOrganization --> Organization : predecessor
  EducationalOrganization --> Person : rector
  EducationalOrganization --> GoverningBody : reportedGovernedBy
  EducationalOrganization --> GoverningBody : stateManagedBy
  GoverningBody --> GoverningBody : subordinateTo
  Organization --> Organization : successor
  EducationalOrganization --> Major : trainsMajor
```

## Tiên đề phục vụ suy luận

| Loại tiên đề | Nội dung |
|---|---|
| Lớp định nghĩa (≡) | **MilitaryInstitution** ≡ EducationalOrganization ⊓ ∋governedBy.{MinistryOfNationalDefence} |
| Lớp định nghĩa (≡) | **PoliceInstitution** ≡ EducationalOrganization ⊓ ∋governedBy.{MinistryOfPublicSecurity} |
| Lớp định nghĩa (≡) | **PrivateInstitution** ≡ EducationalOrganization ⊓ ∋ownership.{PrivateOwnership} |
| Lớp định nghĩa (≡) | **PublicInstitution** ≡ EducationalOrganization ⊓ ∋ownership.{PublicOwnership} |
| Phân loại (⊑) | EducationalOrganization ⊓ ∃memberOf.HigherEducationInstitution ⊑ **MemberInstitution** |
| Phân loại (⊑) | EducationalOrganization ⊓ ∃dissolutionYear.integer ⊑ **DefunctInstitution** |
| Phân loại (⊑) | Person ⊓ ∃alumnusOf.EducationalOrganization ⊑ **Alumnus** |
| Phân loại (⊑) | Person ⊓ ∃leads.EducationalOrganization ⊑ **InstitutionLeader** |
| Chuỗi thuộc tính | bornIn ∘ mergedInto ⊑ **birthAreaInCurrentCrosswalk** |
| Chuỗi thuộc tính | bornIn ∘ partOf ⊑ **birthAreaInCurrentCrosswalk** |
| Chuỗi thuộc tính | birthAreaInCurrentCrosswalk ∘ partOf ⊑ **birthAreaInCurrentCrosswalk** |
| Chuỗi thuộc tính | governedBy ∘ subordinateTo ⊑ **governedBy** |
| Chuỗi thuộc tính | locatedIn ∘ partOf ⊑ **locatedIn** |
| Chuỗi thuộc tính | locatedIn ∘ mergedInto ⊑ **locatedIn** |
| Chuỗi thuộc tính | offersProgram ∘ ofMajor ⊑ **trainsMajor** |
| Bắc cầu | **partOf** |
| Bắc cầu | **subordinateTo** |
| Hàm (tối đa 1 giá trị) | **birthDate** |
| Hàm (tối đa 1 giá trị) | **branchOf** |
| Hàm (tối đa 1 giá trị) | **dissolutionYear** |
| Hàm (tối đa 1 giá trị) | **foundingYear** |
| Hàm (tối đa 1 giá trị) | **mergedInto** |
| Hàm (tối đa 1 giá trị) | **ownership** |
| Nghịch đảo | **alumnusOf** ⇄ **hasAlumnus** |
| Nghịch đảo | **branchOf** ⇄ **hasBranch** |
| Nghịch đảo | **educatedAt** ⇄ **hasEducationParticipant** |
| Nghịch đảo | **governedBy** ⇄ **governs** |
| Nghịch đảo | **leads** ⇄ **hasLeader** |
| Nghịch đảo | **memberOf** ⇄ **hasMember** |
| Nghịch đảo | **mergedInto** ⇄ **mergedFrom** |
| Nghịch đảo | **offersProgram** ⇄ **offeredBy** |
| Nghịch đảo | **partOf** ⇄ **hasPart** |
| Nghịch đảo | **predecessor** ⇄ **successor** |
| Rời nhau | HigherEducationInstitution ⊥ Branch ⊥ VocationalCollege |
| Rời nhau | EducationalOrganization ⊥ GoverningBody ⊥ Company |
| Rời nhau | Country ⊥ Region ⊥ Province ⊥ FormerProvince |
| Rời nhau | Organization ⊥ Person ⊥ AdministrativeUnit |
| Rời nhau | RegionalUniversity ⊥ NationalUniversity |
| Rời nhau | PrivateInstitution ⊥ PublicInstitution |
| Rời nhau | Major ⊥ FieldOfStudy |
