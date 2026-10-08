# Sơ đồ ontology VN-Edu

*Sinh tự động từ `ontology/vnedu.ttl` bởi `scripts/gen_docs.py`* — 34 lớp, 33 thuộc tính quan hệ, 20 thuộc tính dữ liệu, 759 triple.

Mũi tên rỗng = kế thừa (`rdfs:subClassOf`); mũi tên có nhãn = thuộc tính quan hệ (domain → range).

```mermaid
classDiagram
  direction LR
  class AcademicProgram["AcademicProgram<br/>Chương trình đào tạo"]
  class Academy["Academy<br/>Học viện"]
  class AdministrativeUnit["AdministrativeUnit<br/>Đơn vị hành chính / vùng"]
  class Alumnus["Alumnus<br/>Cựu sinh viên"]
  class Branch["Branch<br/>Phân hiệu"]
  class CentrallyGovernedCity["CentrallyGovernedCity<br/>Thành phố trực thuộc trung ương"]
  class Company["Company<br/>Doanh nghiệp / tập đoàn giáo dục"]
  class Country["Country<br/>Quốc gia"]
  class DefunctInstitution["DefunctInstitution<br/>Cơ sở đã giải thể / sáp nhập"]
  class EducationalOrganization["EducationalOrganization<br/>Cơ sở giáo dục"]
  class FieldOfStudy["FieldOfStudy<br/>Lĩnh vực đào tạo"]
  class FormerProvince["FormerProvince<br/>Tỉnh cũ (trước 01/07/2025)"]
  class GoverningBody["GoverningBody<br/>Cơ quan chủ quản"]
  class HigherEducationInstitution["HigherEducationInstitution<br/>Cơ sở giáo dục đại học"]
  class InstitutionLeader["InstitutionLeader<br/>Người đứng đầu cơ sở giáo dục"]
  class Major["Major<br/>Ngành đào tạo"]
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
  class University["University<br/>Đại học"]
  class UniversitySchool["UniversitySchool<br/>Trường đại học"]
  class VocationalCollege["VocationalCollege<br/>Trường cao đẳng"]
  HigherEducationInstitution <|-- Academy
  Person <|-- Alumnus
  EducationalOrganization <|-- Branch
  Province <|-- CentrallyGovernedCity
  Organization <|-- Company
  AdministrativeUnit <|-- Country
  EducationalOrganization <|-- DefunctInstitution
  Organization <|-- EducationalOrganization
  AdministrativeUnit <|-- FormerProvince
  Organization <|-- GoverningBody
  EducationalOrganization <|-- HigherEducationInstitution
  Person <|-- InstitutionLeader
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
  Person --> AdministrativeUnit : bornIn
  Branch --> HigherEducationInstitution : branchOf
  EducationalOrganization --> Person : councilChair
  EducationalOrganization --> Person : director
  EducationalOrganization --> GoverningBody : governedBy
  GoverningBody --> EducationalOrganization : governs
  EducationalOrganization --> Person : hasAlumnus
  HigherEducationInstitution --> Branch : hasBranch
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
| Phân loại (⊑) | Person ⊓ ∃alumnusOf.EducationalOrganization ⊑ **Alumnus** |
| Phân loại (⊑) | Person ⊓ ∃leads.EducationalOrganization ⊑ **InstitutionLeader** |
| Chuỗi thuộc tính | bornIn ∘ mergedInto ⊑ **bornIn** |
| Chuỗi thuộc tính | bornIn ∘ partOf ⊑ **bornIn** |
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
| Hàm (tối đa 1 giá trị) | **ofMajor** |
| Hàm (tối đa 1 giá trị) | **offeredBy** |
| Hàm (tối đa 1 giá trị) | **ownership** |
| Nghịch đảo | **alumnusOf** ⇄ **hasAlumnus** |
| Nghịch đảo | **branchOf** ⇄ **hasBranch** |
| Nghịch đảo | **governedBy** ⇄ **governs** |
| Nghịch đảo | **leads** ⇄ **hasLeader** |
| Nghịch đảo | **memberOf** ⇄ **hasMember** |
| Nghịch đảo | **mergedInto** ⇄ **mergedFrom** |
| Nghịch đảo | **offersProgram** ⇄ **offeredBy** |
| Nghịch đảo | **partOf** ⇄ **hasPart** |
| Nghịch đảo | **predecessor** ⇄ **successor** |
| Rời nhau | University ⊥ UniversitySchool ⊥ Academy ⊥ OfficerSchool |
| Rời nhau | HigherEducationInstitution ⊥ Branch ⊥ VocationalCollege |
| Rời nhau | EducationalOrganization ⊥ GoverningBody ⊥ Company |
| Rời nhau | Country ⊥ Region ⊥ Province ⊥ FormerProvince |
| Rời nhau | Organization ⊥ Person ⊥ AdministrativeUnit |
| Rời nhau | RegionalUniversity ⊥ NationalUniversity |
| Rời nhau | PrivateInstitution ⊥ PublicInstitution |
| Rời nhau | Major ⊥ FieldOfStudy |
