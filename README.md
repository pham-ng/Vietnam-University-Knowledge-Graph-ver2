# VN-Edu LOD 2.0 — Dữ liệu liên kết mở về giáo dục đại học Việt Nam

Đồ thị tri thức 5 sao về giáo dục đại học Việt Nam. Dữ liệu lấy từ **hai nguồn độc lập** (Wikidata và Wikipedia
tiếng Việt), được **đối chiếu chéo**, mô hình hoá bằng một **ontology OWL 2 RL** để suy luận đúng và đầy đủ,
**kiểm định bằng SHACL**, liên kết tới Wikidata, DBpedia, GeoNames, ROR và Wikipedia, rồi phục vụ qua
**Apache Jena Fuseki**, giao diện web và terminal.

🌐 **Bản công bố:** <https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/> — [bản đồ](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/map) ·
[tra cứu](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/explore) · [cây ontology](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology) ·
[SPARQL trong trình duyệt](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/sparql) · [VoID/DCAT](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/dataset) · [**kịch bản demo**](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/demo) ·
ví dụ URI: [`…/resource/university/dai-hoc-bach-khoa-ha-noi`](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/university/dai-hoc-bach-khoa-ha-noi)
([.ttl](https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/university/dai-hoc-bach-khoa-ha-noi.ttl))

| | Số lượng |
|---|---|
| Cơ sở giáo dục (sau khi lọc & gộp) | **300** — 271 cơ sở GDĐH (196 trường đại học, 41 học viện, 14 đại học, 10 trường sĩ quan, 10 đơn vị thành viên tên đặc thù); 7 phân hiệu, 12 trường cao đẳng, 10 đơn vị khác |
| Phân loại do suy luận | 221 công lập · 35 tư thục · 44 trường thành viên · 21 trường quân đội · 7 trường công an · 11 cơ sở đã giải thể |
| Đơn vị hành chính | 34 tỉnh/thành (từ 01/07/2025) + 29 tỉnh cũ đã sáp nhập + 3 miền + quốc gia |
| Cơ quan chủ quản / chủ sở hữu | 47 (15 Bộ, UBND tỉnh, cơ quan Đảng, quân chủng/binh chủng, 5 tập đoàn giáo dục) |
| Người | 1.668 (1.481 cựu sinh viên, 187 người đứng đầu cơ sở) |
| Ngành / lĩnh vực đào tạo | 37 / 16 (TT 09/2022/TT-BGDĐT) |
| Triple | 17.940 khẳng định + 3.670 liên kết + **14.484 suy luận** = 36.750 (kèm ontology, VoID) |
| Liên kết ra ngoài | 1.878 Wikidata · 258 DBpedia · 195 ROR · 63 GeoNames · 1.188 Wikipedia · 88 skos:closeMatch |
| Tái sử dụng URI có sẵn | 217 URI Wikidata làm giá trị (nghề nghiệp, giới tính); 72% triple dùng từ vựng chuẩn — xem [docs/uri-strategy.md](docs/uri-strategy.md) |

## Chạy nhanh

```bash
powershell -ExecutionPolicy Bypass -File run_all.ps1
```

```bash
powershell -ExecutionPolicy Bypass -File fuseki/run_fuseki.ps1
```

```bash
py app/server.py
```

`run_all.ps1` chạy bước 2 → 7 (thu thập → … → công bố site tĩnh), đánh giá liên kết, sinh sơ đồ, rồi chạy **46 test**. Mọi phản hồi HTTP được cache trong
`data/bronze/http_cache/` nên kết quả tái lập được; muốn tải dữ liệu mới nhất thì thêm `-Fresh`. `run_fuseki.ps1` tự
tải Fuseki (Java 8 → 3.17.0, Java 11+ → 4.10.0) và mở endpoint `http://localhost:3030/vnedu/sparql`. Web chạy ở
http://localhost:8000 và tự dùng Fuseki nếu Fuseki đang chạy. Xem trước site công bố y hệt GitHub Pages:
`py scripts/serve_site.py` → http://localhost:8010/Vietnam-University-Knowledge-Graph-ver2/.

### Kiến trúc dữ liệu Medallion ([docs/architecture.md](docs/architecture.md))

| Tầng | Thư mục | Nội dung | Cổng chất lượng |
|---|---|---|---|
| 🟫 Bronze | `data/bronze/` | Ảnh chụp gốc từ Wikidata, Wikipedia, DBpedia (+ `*.meta.json`: nguồn, thời điểm, giấy phép, số bản ghi) và `http_cache/` | Bất biến, tái lập được |
| ⬜ Silver | `data/silver/` | Thực thể đã nhận diện, hợp nhất, làm sạch | **JSON Schema** [`schemas/silver.schema.json`](schemas/silver.schema.json): bản ghi sai thì **dừng pipeline** |
| 🟨 Gold | `data/gold/` | RDF theo ontology + liên kết + suy luận + VoID/DCAT | **SHACL** + **kiểm tra nhất quán OWL** + kiểm thử suy luận |
| 📚 Reference | `data/reference/` | Dữ liệu tham chiếu nhập tay có căn cứ pháp lý (NQ 202/2025, TT 09/2022) | Kiểm tra bằng schema (tỉnh cũ phải có tỉnh mới, …) |
| 📊 Reports | `data/reports/` | [`quality_report.md`](data/reports/quality_report.md), [`link_evaluation.md`](data/reports/link_evaluation.md), mâu thuẫn, giá trị dự phòng, loại bỏ, SHACL | — |

`data/manifest.json` ghi **dòng dõi dữ liệu** (lineage): mọi tệp của mọi tầng, số bản ghi/triple, SHA-256, thời điểm tạo.
Sơ đồ ontology sinh tự động từ TTL: [docs/ontology.md](docs/ontology.md).

---

## Bước 1 — Ontology ([ontology/vnedu.ttl](ontology/vnedu.ttl))

### Nguyên tắc thiết kế

1. **Profile OWL 2 RL.** Suy luận bằng luật (owlrl, Jena, GraphDB, RDFox) vừa *sound* vừa *complete*, nên có thể
   materialize toàn bộ hệ quả và nạp vào Fuseki.
2. Chỉ căn chỉnh với từ vựng ngoài bằng `rdfs:subClassOf` hoặc `rdfs:subPropertyOf`. **Không** dùng `owl:equivalentClass`
   sang schema.org hay DBpedia.
3. **Không** khai báo lại domain/range cho thuộc tính của từ vựng ngoài (`geo:lat`, `foaf:name`, …).
4. Các thuộc tính tham gia property chain có range là lớp cha chung, để chuỗi suy luận không sinh mâu thuẫn.
5. Ràng buộc "phải có" (cardinality, kiểu dữ liệu, khoảng giá trị) đặt ở **SHACL**, vì OWL dùng giả định thế giới mở.
6. Có **lớp định nghĩa** để bộ suy luận tự phân loại, và **tiên đề rời nhau / thuộc tính hàm** để phát hiện dữ liệu sai.

### Lớp

```
Organization ⊑ foaf:Organization, schema:Organization
├─ EducationalOrganization ⊑ schema:EducationalOrganization
│  ├─ HigherEducationInstitution ⊑ schema:CollegeOrUniversity          ┐ loại hình pháp lý theo Luật GDĐH,
│  │  ├─ University (đại học) ⊑ dbo:University                         │ xác định từ tên chính thức,
│  │  │  ├─ NationalUniversity (ĐHQG)   RegionalUniversity (ĐH vùng)   │ AllDisjointClasses
│  │  ├─ UniversitySchool (trường đại học) ⊑ dbo:University            │
│  │  ├─ Academy (học viện)                                            │
│  │  └─ OfficerSchool (trường sĩ quan)                                ┘
│  ├─ Branch (phân hiệu)   VocationalCollege (cao đẳng)        — rời với HEI
│  └─ lớp định nghĩa (suy luận tự phân loại):
│     PublicInstitution  ≡ EduOrg ⊓ ∋ownership.{Public}
│     PrivateInstitution ≡ EduOrg ⊓ ∋ownership.{Private}            (rời với Public)
│     MilitaryInstitution ≡ EduOrg ⊓ ∋governedBy.{Bộ Quốc phòng}
│     PoliceInstitution   ≡ EduOrg ⊓ ∋governedBy.{Bộ Công an}
│     EduOrg ⊓ ∃memberOf.HEI ⊑ MemberInstitution
│     EduOrg ⊓ ∃dissolutionYear.xsd:gYear ⊑ DefunctInstitution
├─ GoverningBody ⊑ schema:GovernmentOrganization — Ministry, ProvincialPeoplesCommittee
└─ Company (chủ sở hữu trường tư)            — EduOrg ⊥ GoverningBody ⊥ Company
Person ⊑ foaf:Person, schema:Person ;  Person ⊓ ∃alumnusOf.EduOrg ⊑ Alumnus ;  Person ⊓ ∃leads.EduOrg ⊑ InstitutionLeader
AdministrativeUnit — Country, Region, Province (34, ⊒ CentrallyGovernedCity), FormerProvince — AllDisjointClasses
FieldOfStudy, Major ⊑ skos:Concept ;  AcademicProgram ⊑ schema:EducationalOccupationalProgram
Organization ⊥ Person ⊥ AdministrativeUnit
```

### Suy luận mà ontology hỗ trợ (đều có test trong [tests/test_reasoning.py](tests/test_reasoning.py))

| Tiên đề | Ví dụ thực tế trong dữ liệu |
|---|---|
| `locatedIn ∘ mergedInto ⊑ locatedIn`, `locatedIn ∘ partOf ⊑ locatedIn`, `partOf` bắc cầu | ĐH Thủ Dầu Một chỉ ghi **Bình Dương** → suy ra TP. Hồ Chí Minh (sáp nhập 2025), rồi Nam Bộ, rồi Việt Nam |
| `governedBy ∘ subordinateTo ⊑ governedBy` + lớp định nghĩa | HV Hải quân chỉ ghi "Quân chủng Hải quân" → thuộc Bộ Quốc phòng → **MilitaryInstitution** (24 trường quân đội và công an) |
| `∃ownedBy.Company ⊑ ∋ownership.{Private}` | Trường ĐH FPT có chủ sở hữu FPT Education → **tư thục** |
| `rector, director ⊑ hasLeader`, `inverseOf leads` | Hiệu trưởng hoặc giám đốc → **InstitutionLeader** |
| `offersProgram ∘ ofMajor ⊑ trainsMajor` | Trường đào tạo ngành X, suy ra từ chương trình đào tạo |
| inverse: `memberOf/hasMember`, `governedBy/governs`, `alumnusOf/hasAlumnus`, `mergedInto/mergedFrom` | Chỉ cần khẳng định một chiều, chiều còn lại do bộ suy luận sinh ra |
| `ownership` hàm + `AllDifferent(Public, Private)` | Một trường bị ghi vừa công lập vừa tư thục → **phát hiện mâu thuẫn** |
| `AllDisjointClasses` loại hình | Vừa là Học viện vừa là Trường đại học → **mâu thuẫn** |
| `Organization ⊥ Person` | Dùng một người làm cơ quan chủ quản → **mâu thuẫn** |
| `foundingYear` hàm | Hai năm thành lập khác nhau → **mâu thuẫn** |

## Bước 2 — Thu thập ([scripts/step2_collect.py](scripts/step2_collect.py))

| Nguồn | Cách lấy | Thu được |
|---|---|---|
| Wikidata | `P31/P279* Q38723` ∧ `P17 Q881`, sau đó mỗi thuộc tính một truy vấn `VALUES` (tránh timeout và tích Descartes) | tên vi/en, năm thành lập/giải thể, website, toạ độ, tên viết tắt, khẩu hiệu, **ROR**, tổ chức cha, **lãnh đạo đương nhiệm** (bỏ người đã có `P582`), số SV kèm năm, đơn vị hành chính |
| Wikipedia tiếng Việt | Duyệt đệ quy 164 thể loại ("Đại học Việt Nam", "Học viện Việt Nam", …) **và** mọi bài được Wikidata trỏ tới; parse infobox bằng `mwparserfromhell` | **mã trường tuyển sinh**, loại hình (công lập/tư thục), cơ quan chủ quản, hiệu trưởng/giám đốc kèm học hàm, quy mô, tên cũ, địa chỉ |
| Wikidata | 34 tỉnh hiện hành + 29 tỉnh cũ | GeoNames, dân số (kèm năm), diện tích, toạ độ |
| Tham chiếu nhập tay ([data/reference](data/reference)) | NQ 202/2025/QH15, TT 09/2022 | tỉnh cũ → tỉnh mới (**Wikidata chưa có**), tỉnh → miền, danh mục ngành |

Phần làm sạch infobox xử lý các lỗi hay gặp: `<br>`, `{{*}}`, `{{plainlist}}` dính chữ (ví dụ "BKHN**HUST**"),
`{{start date|1956|3|6}}`, `{{coord|…}}` dạng độ-phút-giây, chú thích `<ref>`, và ký tự ẩn (soft hyphen).

## Bước 3 — Tích hợp ([step3_integrate.py](scripts/step3_integrate.py)) và RDF 4 sao ([step3_transform.py](scripts/step3_transform.py))

* **Nhận diện thực thể** bằng QID. Phát hiện và **gộp 3 cặp item trùng** trên Wikidata (ví dụ *Hanoi Law University*
  có 2 QID), giữ cả hai trong `owl:sameAs`.
* **Loại 67 thực thể ngoài phạm vi**, có ghi lý do vào `excluded.csv`. Đó là những thứ Wikidata xếp nhầm vào "cơ sở
  GDĐH": khoa/bộ môn, trường THPT chuyên, bài "History of …", và item chỉ có nhãn tiếng Anh mà không kiểm chứng được.
* **Loại hình pháp lý lấy từ tên chính thức**, không lấy từ `P31` của Wikidata (vốn lẫn lộn đại học, cao đẳng, khoa).
* **Phân giải trường "thuộc tổ chức / thành viên của / trực thuộc" theo loại của đích**: đích là cơ sở GDĐH thì thành
  `memberOf` (hoặc `branchOf`), là Bộ/UBND/cơ quan thì thành `governedBy`, là doanh nghiệp thì thành `ownedBy`. Bỏ qua
  các giá trị nhiễu kiểu "Nhóm 3" hay "Hệ thống Đại học ASEAN".
* **Chọn tỉnh** theo thứ tự tin cậy: trường "thành phố/tỉnh" của infobox, rồi Wikidata P131, rồi địa chỉ trụ sở. Nếu
  Wikidata chỉ ra tỉnh cũ nằm trong tỉnh mới thì giữ tỉnh cũ (chi tiết hơn); bộ suy luận sẽ quy về tỉnh mới.
* **Năm thành lập** lấy năm sớm nhất giữa Wikidata, infobox viwiki và DBpedia (truyền thống tính từ tiền thân). Mọi
  chênh lệch đều ghi vào `conflicts.csv`.
* **Nguồn dự phòng** chỉ dùng khi các nguồn có cấu trúc đều thiếu, theo thứ tự tin cậy. Mỗi giá trị lấy theo cách này
  đều ghi vào `filled.csv` (23 giá trị):
  - **tỉnh/thành**: Wikidata trụ sở (P159/P276), rồi câu "trụ sở / đặt tại / ở …" trong đoạn mở đầu bài viwiki, rồi mô
    tả Wikidata, rồi reverse geocoding toạ độ qua OpenStreetMap Nominatim, cuối cùng là địa danh trong tên trường (bỏ qua
    "Hồ Chí Minh" khi là tên người);
  - **năm thành lập / giải thể**: câu "được thành lập vào năm…", "tồn tại từ năm A đến năm B", "bị giải thể…" trong đoạn
    mở đầu (đã bỏ chú thích ảnh), lấy năm **gần từ khoá nhất**.
  Cách này phát hiện được 5 cơ sở đã giải thể mà Wikidata không ghi: Viện ĐH Huế, Vạn Hạnh, Minh Đức (1975);
  ĐH Tài chính – Kế toán (2001); ĐH Răng Hàm Mặt (2009).
* **Sửa sitelink thiếu**: item Wikidata chưa nối bài viwiki được tìm theo tiêu đề và tìm kiếm toàn văn; chỉ nhận bài chưa
  gắn với item khác.
* **Tên người**: bóc học hàm, học vị, quân hàm, chức sắc tôn giáo (GS, PGS-TS, TTND, GVCC, Thiếu tướng, Hòa thượng, …)
  vào `vnedu:honorific`.
* Kiểm tra miền giá trị: toạ độ phải nằm trong lãnh thổ Việt Nam, năm phải trong khoảng 1800 đến nay, số liệu phải là
  số nguyên dương. Với ngày sinh `YYYY-01-01` (Wikidata dùng khi chỉ biết năm), không sinh ngày sinh giả.
* Mỗi cơ sở có `prov:wasDerivedFrom` trỏ tới item Wikidata và **bản sửa đổi cụ thể (oldid)** của bài viwiki.

## Bước 4 — Liên kết 5 sao ([scripts/step4_link.py](scripts/step4_link.py))

| Liên kết | Cách tìm |
|---|---|
| `owl:sameAs` Wikidata | theo nguồn gốc. Cơ quan và miền chưa có QID thì tìm bằng API Wikidata với nhãn tiếng Việt và **xác minh `P17 = Việt Nam`** (để tránh nối nhầm sang "Bộ VHTTDL Hàn Quốc" hay khái niệm chung "type of ministry"; cả hai lỗi này đã gặp thật) |
| `owl:sameAs` DBpedia | hỏi endpoint DBpedia: `?d owl:sameAs wd:Q…` |
| `owl:sameAs` ROR, GeoNames | qua `P6782`, `P1566` của Wikidata |
| `skos:closeMatch` ngành → Wikidata, DBpedia | khớp nhãn chính xác và loại mô tả tạp chí/họ tên; ghi đè bằng `link_overrides.csv` |
| `foaf:isPrimaryTopicOf` | bài Wikipedia tiếng Việt và tiếng Anh |

Mô tả dataset theo **VoID + DCAT** ([data/gold/void.ttl](data/gold/void.ttl)): giấy phép, nguồn, `void:Linkset` cho từng
đích liên kết, `dcat:Distribution` cho các dump. Kết quả so khớp được ghi ra `data/reports/links/*.csv` để rà soát.

### Vì sao liên kết theo định danh chứ không so khớp tên? ([data/reports/link_evaluation.md](data/reports/link_evaluation.md))

[scripts/eval_linking.py](scripts/eval_linking.py) mô phỏng cách liên kết kiểu **Silk** (Jaccard trên token của tên, như
dự án tham khảo `hust-semantic-web`). Thí nghiệm so khớp tên tiếng Anh của 87 trường với nhãn DBpedia, lấy liên kết theo
định danh (QID) làm chuẩn đối chiếu:

| θ | precision | recall | F1 |
|---|---|---|---|
| 0.2 (mức dự án tham khảo dùng) | 83,7% | 82,8% | 0,832 |
| 0.5 | 90,9% | 80,5% | 0,854 |
| 0.9 | 98,3% | 65,5% | 0,786 |

Ca tiêu biểu: *Hanoi University of Science and Technology* (HUST) và *University of Science and Technology of Hanoi*
(USTH) có **cùng tập từ**, nên Jaccard = 1.0 cho cả hai. Không ngưỡng nào tách được hai trường này, chỉ định danh
dùng chung (QID, ROR) mới làm được.

## Bước 5 — Suy luận, kiểm tra và truy vấn

* [scripts/step5_reason.py](scripts/step5_reason.py) gồm 4 việc:
  - materialize bằng **owlrl**, sinh 14.090 triple mới về cá thể;
  - kiểm tra nhất quán (disjoint, AllDifferent, thuộc tính hàm, `owl:Nothing`); kết quả hiện tại là **nhất quán**;
  - kiểm định **SHACL** ([shapes/vnedu-shapes.ttl](shapes/vnedu-shapes.ttl)): `conforms = True`, kèm 27 cảnh báo thiếu
    thông tin và 2 cảnh báo "trường tư thục mà infobox ghi Bộ GD&ĐT là chủ quản";
  - gộp tất cả thành `vnedu-all.ttl`.
  Không đưa `owl:sameAs` ra ngoài vào suy luận, vì làm vậy sẽ nhân bản mọi triple sang URI của Wikidata.
* **Fuseki**: [fuseki/run_fuseki.ps1](fuseki/run_fuseki.ps1) (hoặc `fuseki/start.cmd`, `fuseki/docker-compose.yml`
  cùng `scripts/step5_load_fuseki.py`).
* **Web** [app/server.py](app/server.py):
  - `/sparql`: SPARQL 1.1 Protocol;
  - `/query`: YASGUI kèm 15 truy vấn mẫu;
  - `/resource/…`: **dereference URI** có content negotiation (trình duyệt nhận HTML, máy nhận Turtle/JSON-LD qua
    `Accept` hoặc `?format=ttl`); mỗi giá trị do bộ suy luận sinh ra có nhãn "suy luận";
  - `/ontology`, `/dataset` (VoID), `/download/…`.
* **Terminal** [query.py](query.py): `py query.py --list`, `py query.py queries/03_truong_quan_doi_cong_an.rq`, `py query.py -i`
  (dùng `--local` nếu không chạy Fuseki).
* **Báo cáo chất lượng** [scripts/step6_report.py](scripts/step6_report.py) → [data/reports/quality_report.md](data/reports/quality_report.md):
  dòng dõi dữ liệu, độ đầy đủ theo trường, nguồn của giá trị, mâu thuẫn, kết quả các cổng kiểm định, checklist 5 sao.
* **Kiểm thử**: `py -m pytest tests -q`, gồm **46 test**:
  - [test_reasoning.py](tests/test_reasoning.py): 8 test suy luận đúng, 5 test phát hiện dữ liệu sai, 1 test toàn bộ dữ liệu thật nhất quán;
  - [test_extraction.py](tests/test_extraction.py): 29 test trích xuất dùng câu thật từ Wikipedia (gồm ca "chú thích ảnh năm 1920" và chuẩn hoá tên Bộ);
  - [test_data_contract.py](tests/test_data_contract.py): 3 test chứng minh JSON Schema chặn được bản ghi sai.

### Truy vấn mẫu ([queries/](queries), sinh bởi `queries/_generate.py`)

| # | Nội dung | Cần suy luận |
|---|---|---|
| 01 | Số cơ sở theo 34 tỉnh mới (trường ghi ở tỉnh cũ tự quy về tỉnh mới) | ✔ |
| 02 | Theo miền × công lập/tư thục | ✔ |
| 03 | Trường quân đội & công an | ✔ |
| 04 | Tra theo mã trường tuyển sinh (BKA, KHA, NTH, YHB, QHI) | |
| 05 | Đại học và đơn vị thành viên | ✔ |
| 06 | Tỉnh cũ → tỉnh mới (NQ 202/2025/QH15) | |
| 07 | Hồ sơ đầy đủ ĐHBK Hà Nội | ✔ |
| 08 | Trường đào tạo ngành CNTT, theo miền | ✔ |
| 09 | Cựu sinh viên nổi tiếng theo trường | ✔ |
| 10 | Lãnh đạo các ĐHQG và ĐH vùng | ✔ |
| 11 | Thống kê liên kết 5 sao | |
| 12 | **Federated** → Wikidata: diện tích tỉnh, mật độ cơ sở | |
| 13 | **Federated** → DBpedia: ảnh, khẩu hiệu, số SV | |
| 14 | Danh mục ngành + `skos:closeMatch` | |
| 15 | Chất lượng dữ liệu: % cơ sở có từng thuộc tính | |

Hai truy vấn federated dùng mẫu `OPTIONAL { SERVICE … }` có một mẫu bắt buộc chứa biến liên kết. Nhờ vậy cả Jena lẫn
rdflib đều gửi từng URI đã biết sang endpoint ngoài (bind join) thay vì tải toàn bộ dữ liệu bên đó về.

## Bước 6–7 — Báo cáo chất lượng & công bố ([scripts/step7_publish.py](scripts/step7_publish.py))

`step7_publish.py` sinh site tĩnh `site/` (≈6.700 tệp), GitHub Actions ([.github/workflows/pages.yml](.github/workflows/pages.yml))
đưa lên **GitHub Pages** tại URI gốc cố định `https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/`:

| Đường dẫn | Nội dung |
|---|---|
| `resource/<loại>/<tên>` | **2.211 URI tra cứu được** — HTML cho người, **JSON-LD nhúng** (JSON-LD 1.1) cho máy, `<link rel="alternate">` tới `.ttl` / `.jsonld` |
| `ontology` (+`.ttl`, `.jsonld`) | tài liệu ontology + **cây lớp tương tác** (D3); `ontology#Lop` neo đúng mục |
| `dataset` | VoID + DCAT (giấy phép, linkset, phân phối) |
| `/` | thống kê (theo tỉnh 2025, miền × sở hữu, thập kỷ thành lập, loại hình, chủ quản, liên kết), chỉ số chất lượng |
| `map` | bản đồ Leaflet: điểm theo miền, lớp mật độ theo tỉnh, lọc theo sở hữu/loại hình, popup dẫn tới URI |
| `explore` | tra cứu không dấu, lọc, sắp xếp, **xuất CSV** |
| `sparql` | **SPARQL 1.1 trong trình duyệt** (Oxigraph WebAssembly) trên toàn bộ 36.750 triple — không cần máy chủ |
| `download/` | dump Turtle, N-Triples, ZIP, shapes, JSON Schema |

GitHub Pages là hosting tĩnh nên không có content negotiation phía máy chủ; máy đọc lấy RDF bằng JSON-LD nhúng trong
trang hoặc thêm đuôi `.ttl` / `.jsonld`. Nếu cần negotiation thật, có thể đăng ký `https://w3id.org/vnedu/` trỏ về site này.

## Thang 5 sao

| Sao | Đạt được bằng |
|---|---|
| ★ | **Công khai trên Web** tại https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ với giấy phép **CC BY-SA 4.0** ([LICENSE-DATA.md](LICENSE-DATA.md)). Phải là share-alike vì dữ liệu dẫn xuất từ Wikipedia (CC BY-SA); Wikidata là CC0 |
| ★★ | Có cấu trúc, máy đọc được (JSON trong `data/bronze`, `data/silver`; CSV trong `data/reference`) |
| ★★★ | Định dạng mở, không độc quyền (CSV, JSON, Turtle) |
| ★★★★ | Chuẩn W3C: RDF, OWL 2 RL, SHACL, SPARQL 1.1, PROV-O, VoID/DCAT, JSON-LD 1.1. Mỗi thực thể có HTTP URI công khai, cố định, tra cứu được (HTML + JSON-LD nhúng, `.ttl`, `.jsonld`) |
| ★★★★★ | Liên kết tới Wikidata, DBpedia, GeoNames, ROR, Wikipedia (`owl:sameAs`, `skos:closeMatch`, `foaf:isPrimaryTopicOf`); mô tả linkset trong VoID; truy vấn federated đi theo liên kết |

## So sánh với phiên bản `vio` trước đây

| Vấn đề trong `vio.owl.ttl` / dữ liệu cũ | Hậu quả | VN-Edu 2.0 |
|---|---|---|
| `geo:lat rdfs:domain vio:Site` (định nghĩa lại từ vựng ngoài) | mọi thứ có toạ độ (kể cả tỉnh) bị suy ra là `Site`, mà `Site ⊥ Place`, nên **mâu thuẫn** | không khai báo lại domain/range của từ vựng ngoài |
| `isPartOf` bắc cầu + `locatedInDistrict ∘ isPartOf → locatedInCity` (range `City`) | tỉnh bị suy ra là `City`, mà `City ⊥ Province`, nên **mâu thuẫn** | một `locatedIn` với range là lớp cha `AdministrativeUnit` |
| `University ≡ dbo:University ≡ schema:CollegeOrUniversity` | kéo theo ngữ nghĩa ngoài, mọi "college" thành university | chỉ dùng `subClassOf` |
| `wikidataEntity ⊑ owl:sameAs` | không hợp lệ trong OWL DL | dùng `owl:sameAs` trực tiếp |
| `owl:minCardinality` cho `hasSite`, `geo:lat` | vô tác dụng dưới giả định thế giới mở | chuyển sang SHACL |
| Năm thành lập lấy từ văn bản (ví dụ Học viện Hải quân **2022**, ĐH An Giang **1976**) | sai số liệu | đối chiếu Wikidata ↔ infobox, ghi mâu thuẫn (Học viện Hải quân **1955**, ĐH An Giang **1999**) |
| Chỉ dùng 1 nguồn cho mỗi trường thông tin; không có `prov` | không truy được nguồn gốc | 2 nguồn, có báo cáo mâu thuẫn, kèm `prov:wasDerivedFrom` tới bản sửa đổi viwiki |
| Không phân biệt chủ quản / thành viên / chủ sở hữu | "thành viên của = Bộ GD&ĐT" | phân giải theo loại của đích |
| Không có đơn vị hành chính sau 2025 | dữ liệu lỗi thời | 34 tỉnh mới + 29 tỉnh cũ + suy luận sáp nhập |
| Chỉ liên kết Wikidata | | + DBpedia, ROR, GeoNames, Wikipedia; VoID/DCAT |

## So sánh với dự án tham khảo `hust-semantic-web` (smartphone)

Những gì **học được và đã áp dụng**:

| Ý tưởng của họ | Áp dụng trong VN-Edu (và làm chặt hơn) |
|---|---|
| Kiến trúc Medallion bronze → silver → gold | Giữ nguyên ý tưởng, thêm **cổng kiểm định ở mỗi ranh giới tầng** (JSON Schema ở silver; SHACL và kiểm tra nhất quán ở gold), `*.meta.json` cho bronze, `manifest.json` (SHA-256) cho lineage |
| Sơ đồ kiến trúc + sơ đồ ontology (draw.io) | Sơ đồ Mermaid **sinh tự động từ TTL** (`scripts/gen_docs.py`), không thể lệch với ontology thật |
| Liên kết bằng Silk (quy tắc so khớp khai báo) | Đánh giá định lượng cách so khớp tên kiểu Silk (bảng ở trên) để chứng minh lựa chọn liên kết theo định danh |
| Nhiều nguồn dữ liệu | Wikidata + Wikipedia + DBpedia + OpenStreetMap + văn bản pháp lý, mỗi nguồn ghi giấy phép |

Những điểm **họ còn thiếu** (đã kiểm chứng trên file của họ) mà VN-Edu đã xử lý:

| Vấn đề trong `hust-semantic-web` | VN-Edu |
|---|---|
| Lớp `SmartPhone` khai báo ở namespace `…/phuongbv/…#SmartPhone`, nhưng cả 814 cá thể trong gold có kiểu `…/hust/master/…owl#SmartPhone`, nên domain/range và suy luận không áp dụng được cho dữ liệu | Namespace thống nhất; có test kiểm tra suy luận trên dữ liệu thật |
| `Tablet ≡ SmartPhone` (tablet bị coi là điện thoại) | Chỉ dùng `≡` cho lớp định nghĩa có điều kiện; các loại hình rời nhau (`AllDisjointClasses`) |
| 13.273/14.057 literal là `xsd:string` (RAM, dung lượng, kích thước) | Kiểu dữ liệu chuẩn (`xsd:gYear`, `nonNegativeInteger`, `decimal`, `date`) + SHACL kiểm khoảng giá trị |
| Không SHACL, không kiểm tra nhất quán, không test | SHACL + kiểm tra nhất quán OWL 2 RL + 46 test |
| Silk θ = 0.2, chỉ 53/814 thiết bị có liên kết; nhiều bước làm tay qua GUI, CSV tải từ trình duyệt | Liên kết tự động, tái lập được; 99% cơ sở có liên kết |
| URI `semanticweb.org` không dereference được; không có VoID | 2.211 URI công khai tra cứu được trên GitHub Pages; VoID + DCAT |
| ChatGPT là một nguồn dữ liệu (không truy được nguồn gốc) | Chỉ dùng nguồn mở có giấy phép; `prov:wasDerivedFrom` tới bản sửa đổi cụ thể |

## Giới hạn đã biết

* Wikipedia và Wikidata là nguồn cộng đồng biên tập. Lãnh đạo, quy mô sinh viên… có thể đã cũ; mỗi giá trị đều truy được
  về bản sửa đổi gốc để kiểm chứng.
* `programs.csv` (trường nào đào tạo ngành nào) là **dữ liệu mẫu nhập tay** cho 16 trường. Nên đối chiếu với đề án tuyển
  sinh trước khi dùng.
* Số sinh viên chỉ có ở 24 cơ sở GDĐH, mã trường ở 60: infobox viwiki còn thiếu. Bổ sung từ nguồn chính thức (Bộ GD&ĐT)
  là hướng mở rộng hợp lý.
* Còn **12 cơ sở thiếu tỉnh và 22 cơ sở thiếu năm thành lập**, chủ yếu là chủng viện, cao đẳng và cơ sở lịch sử không có
  bài Wikipedia (đã thử tìm theo tiêu đề và tìm kiếm toàn văn). Đây là khoảng trống thật của nguồn mở; dự án để chúng ở
  dạng cảnh báo SHACL thay vì tự điền.
* Đánh giá trung thực toàn diện (so với repo cũ, kiểm tra liên kết, RDF, thang 5 sao): [docs/audit.md](docs/audit.md).
* GitHub Pages không có content negotiation phía máy chủ (xem bước 7); SPARQL endpoint HTTP (Fuseki) chỉ chạy cục bộ, bản công khai dùng SPARQL trong trình duyệt (không hỗ trợ SERVICE/federated).
