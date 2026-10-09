# Sơ đồ ontology VN-Edu

*Sinh tự động từ `ontology/vnedu.ttl` bởi `scripts/gen_docs.py`* — 44 lớp, 40 thuộc tính quan hệ, 29 thuộc tính dữ liệu, 948 triple.

Release 2.3 passes the OWL API `OWL2RLProfile` gate with zero violations; see `data/reports/owl2rl-profile.txt`.

Mũi tên rỗng = kế thừa (`rdfs:subClassOf`); mũi tên có nhãn = thuộc tính quan hệ (domain → range).

![Protégé OntoGraf screenshot of the committed ontology](report/figures/ontology-protege-screenshot.png)

GraphDB Workbench 11.1.0 was also connected to the local `vnedu-ontology-d` repository after loading the committed Turtle. The following are direct repository-backed screenshots; the hierarchy view reports 57 classes and the visual graph focuses on `vnedu:University`.

![GraphDB class hierarchy of the committed ontology](report/figures/ontology-graphdb-hierarchy.png)

![GraphDB visual graph for vnedu:University](report/figures/ontology-graphdb-visual.png)

```mermaid
classDiagram
  direction LR
  class AcademicProgram["AcademicProgram<br/>Chương trình đào tạo"]
  class Academy["Academy<br/>Học viện"]
  class AdministrativeUnit["AdministrativeUnit<br/>Đơn vị hành chính"]
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
  class GeographicArea["GeographicArea<br/>Khu vực địa lý"]
  class GoverningBody["GoverningBody<br/>Cơ quan / tổ chức chủ quản"]
  class HigherEducationInstitution["HigherEducationInstitution<br/>Cơ sở giáo dục đại học"]
  class InstitutionHead["InstitutionHead<br/>Người đứng đầu cơ sở giáo dục"]
  class InstitutionLeader["InstitutionLeader<br/>Lãnh đạo cơ sở giáo dục (được nguồn ghi nhận)"]
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
  class PoliticalSocialOrganization["PoliticalSocialOrganization<br/>Tổ chức Đảng / tổ chức chính trị - xã hội"]
  class PrivateInstitution["PrivateInstitution<br/>Cơ sở tư thục"]
  class Province["Province<br/>Tỉnh / thành phố (hiện hành)"]
  class ProvincialPeoplesCommittee["ProvincialPeoplesCommittee<br/>Ủy ban nhân dân cấp tỉnh"]
  class PublicInstitution["PublicInstitution<br/>Cơ sở công lập"]
  class Region["Region<br/>Miền"]
  class RegionalUniversity["RegionalUniversity<br/>Đại học vùng"]
  class ReligiousOrganization["ReligiousOrganization<br/>Tổ chức tôn giáo"]
  class SourceObservation["SourceObservation<br/>SourceObservation"]
  class StateAgency["StateAgency<br/>Cơ quan nhà nước"]
  class University["University<br/>Đại học"]
  class UniversitySchool["UniversitySchool<br/>Trường đại học"]
  class VocationalCollege["VocationalCollege<br/>Trường cao đẳng"]
  HigherEducationInstitution <|-- Academy
  GeographicArea <|-- AdministrativeUnit
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
  InstitutionLeader <|-- InstitutionHead
  Person <|-- InstitutionLeader
  SourceObservation <|-- LeadershipObservation
  SourceObservation <|-- MeasurementObservation
  EducationalOrganization <|-- MemberInstitution
  StateAgency <|-- Ministry
  University <|-- NationalUniversity
  HigherEducationInstitution <|-- OfficerSchool
  GoverningBody <|-- PoliticalSocialOrganization
  AdministrativeUnit <|-- Province
  StateAgency <|-- ProvincialPeoplesCommittee
  GeographicArea <|-- Region
  University <|-- RegionalUniversity
  GoverningBody <|-- ReligiousOrganization
  GoverningBody <|-- StateAgency
  HigherEducationInstitution <|-- University
  HigherEducationInstitution <|-- UniversitySchool
  EducationalOrganization <|-- VocationalCollege
  Person --> EducationalOrganization : alumnusOf
  Person --> GeographicArea : birthAreaInCurrentCrosswalk
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
  EducationalOrganization --> Person : hasHead
  Organization --> Person : hasLeader
  HigherEducationInstitution --> EducationalOrganization : hasMember
  GeographicArea --> GeographicArea : hasPart
  Person --> EducationalOrganization : headOf
  Major --> FieldOfStudy : inField
  Person --> Organization : leads
  Organization --> GeographicArea : locatedIn
  EducationalOrganization --> HigherEducationInstitution : memberOf
  Province --> FormerProvince : mergedFrom
  FormerProvince --> Province : mergedInto
  Person --> Country : nationality
  AcademicProgram --> Major : ofMajor
  AcademicProgram --> EducationalOrganization : offeredBy
  EducationalOrganization --> AcademicProgram : offersProgram
  EducationalOrganization --> Company : ownedBy
  EducationalOrganization --> OwnershipType : ownership
  GeographicArea --> GeographicArea : partOf
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
| Phân loại (⊑) | Person ⊓ ∃headOf.EducationalOrganization ⊑ **InstitutionHead** |
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
| Hàm (tối đa 1 giá trị) | **establishmentYear** |
| Hàm (tối đa 1 giá trị) | **foreignInvested** |
| Hàm (tối đa 1 giá trị) | **foundingYear** |
| Hàm (tối đa 1 giá trị) | **mergedInto** |
| Hàm (tối đa 1 giá trị) | **ownership** |
| Nghịch đảo | **alumnusOf** ⇄ **hasAlumnus** |
| Nghịch đảo | **branchOf** ⇄ **hasBranch** |
| Nghịch đảo | **educatedAt** ⇄ **hasEducationParticipant** |
| Nghịch đảo | **governedBy** ⇄ **governs** |
| Nghịch đảo | **hasHead** ⇄ **headOf** |
| Nghịch đảo | **leads** ⇄ **hasLeader** |
| Nghịch đảo | **memberOf** ⇄ **hasMember** |
| Nghịch đảo | **mergedInto** ⇄ **mergedFrom** |
| Nghịch đảo | **offersProgram** ⇄ **offeredBy** |
| Nghịch đảo | **partOf** ⇄ **hasPart** |
| Nghịch đảo | **predecessor** ⇄ **successor** |
| Rời nhau | University ⊥ UniversitySchool ⊥ Academy ⊥ OfficerSchool |
| Rời nhau | HigherEducationInstitution ⊥ Branch ⊥ VocationalCollege |
| Rời nhau | StateAgency ⊥ PoliticalSocialOrganization ⊥ ReligiousOrganization |
| Rời nhau | EducationalOrganization ⊥ GoverningBody ⊥ Company |
| Rời nhau | Country ⊥ Region ⊥ Province ⊥ FormerProvince |
| Rời nhau | Organization ⊥ Person ⊥ GeographicArea |
| Rời nhau | RegionalUniversity ⊥ NationalUniversity |
| Rời nhau | PrivateInstitution ⊥ PublicInstitution |
| Rời nhau | Major ⊥ FieldOfStudy |
