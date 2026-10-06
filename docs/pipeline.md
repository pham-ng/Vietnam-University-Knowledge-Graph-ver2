# Chi tiết kỹ thuật từng bước của pipeline

> Tài liệu này giữ phần mô tả chi tiết (trước đây nằm trong README). Bản tóm tắt dễ đọc: [README](../README.md).

## Kiến trúc dữ liệu Medallion ([architecture.md](architecture.md))

| Tầng | Thư mục | Nội dung | Cổng chất lượng |
|---|---|---|---|
| 🟫 Bronze | `data/bronze/` | Ảnh chụp gốc từ Wikidata, Wikipedia, DBpedia (+ `*.meta.json`: nguồn, thời điểm, giấy phép, số bản ghi) và `http_cache/` | Bất biến, tái lập được |
| ⬜ Silver | `data/silver/` | Thực thể đã nhận diện, hợp nhất, làm sạch | **JSON Schema** [`schemas/silver.schema.json`](../schemas/silver.schema.json): bản ghi sai thì **dừng pipeline** |
| 🟨 Gold | `data/gold/` | RDF theo ontology + liên kết + suy luận + VoID/DCAT | **SHACL** + **kiểm tra nhất quán OWL** + kiểm thử suy luận |
| 📚 Reference | `data/reference/` | Dữ liệu tham chiếu nhập tay có căn cứ pháp lý (NQ 202/2025, TT 09/2022) | Kiểm tra bằng schema (tỉnh cũ phải có tỉnh mới, …) |
| 📊 Reports | `data/reports/` | [`quality_report.md`](../data/reports/quality_report.md), [`link_evaluation.md`](../data/reports/link_evaluation.md), mâu thuẫn, giá trị dự phòng, loại bỏ, SHACL | — |

`data/manifest.json` ghi **dòng dõi dữ liệu** (lineage): mọi tệp của mọi tầng, số bản ghi/triple, SHA-256, thời điểm tạo.
Sơ đồ ontology sinh tự động từ TTL: [docs/ontology.md](ontology.md).

## Bước 1 — Ontology ([ontology/vnedu.ttl](../ontology/vnedu.ttl))

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

### Suy luận mà ontology hỗ trợ (đều có test trong [tests/test_reasoning.py](../tests/test_reasoning.py))

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

## Bước 2 — Thu thập ([scripts/step2_collect.py](../scripts/step2_collect.py))

| Nguồn | Cách lấy | Thu được |
|---|---|---|
| Wikidata | `P31/P279* Q38723` ∧ `P17 Q881`, sau đó mỗi thuộc tính một truy vấn `VALUES` (tránh timeout và tích Descartes) | tên vi/en, năm thành lập/giải thể, website, toạ độ, tên viết tắt, khẩu hiệu, **ROR**, tổ chức cha, **lãnh đạo đương nhiệm** (bỏ người đã có `P582`), số SV kèm năm, đơn vị hành chính |
| Wikipedia tiếng Việt | Duyệt đệ quy 164 thể loại ("Đại học Việt Nam", "Học viện Việt Nam", …) **và** mọi bài được Wikidata trỏ tới; parse infobox bằng `mwparserfromhell` | **mã trường tuyển sinh**, loại hình (công lập/tư thục), cơ quan chủ quản, hiệu trưởng/giám đốc kèm học hàm, quy mô, tên cũ, địa chỉ |
| Wikidata | 34 tỉnh hiện hành + 29 tỉnh cũ | GeoNames, dân số (kèm năm), diện tích, toạ độ |
| Tham chiếu nhập tay ([data/reference](../data/reference)) | NQ 202/2025/QH15, TT 09/2022 | tỉnh cũ → tỉnh mới (**Wikidata chưa có**), tỉnh → miền, danh mục ngành |

Phần làm sạch infobox xử lý các lỗi hay gặp: `<br>`, `{{*}}`, `{{plainlist}}` dính chữ (ví dụ "BKHN**HUST**"),
`{{start date|1956|3|6}}`, `{{coord|…}}` dạng độ-phút-giây, chú thích `<ref>`, và ký tự ẩn (soft hyphen).

## Bước 3 — Tích hợp ([step3_integrate.py](../scripts/step3_integrate.py)) và RDF 4 sao ([step3_transform.py](../scripts/step3_transform.py))

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
  đều ghi vào `filled.csv` 
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

## Bước 4 — Liên kết 5 sao ([scripts/step4_link.py](../scripts/step4_link.py))

| Liên kết | Cách tìm |
|---|---|
| `owl:sameAs` Wikidata | theo nguồn gốc. Cơ quan và miền chưa có QID thì tìm bằng API Wikidata với nhãn tiếng Việt và **xác minh `P17 = Việt Nam`** (để tránh nối nhầm sang "Bộ VHTTDL Hàn Quốc" hay khái niệm chung "type of ministry"; cả hai lỗi này đã gặp thật) |
| `owl:sameAs` DBpedia | hỏi endpoint DBpedia: `?d owl:sameAs wd:Q…` |
| `owl:sameAs` ROR, GeoNames | qua `P6782`, `P1566` của Wikidata |
| `skos:closeMatch` ngành → Wikidata, DBpedia | khớp nhãn chính xác và loại mô tả tạp chí/họ tên; ghi đè bằng `link_overrides.csv` |
| `foaf:isPrimaryTopicOf` | bài Wikipedia tiếng Việt và tiếng Anh |

Mô tả dataset theo **VoID + DCAT** ([data/gold/void.ttl](../data/gold/void.ttl)): giấy phép, nguồn, `void:Linkset` cho từng
đích liên kết, `dcat:Distribution` cho các dump. Kết quả so khớp được ghi ra `data/reports/links/*.csv` để rà soát.

### Vì sao liên kết theo định danh chứ không so khớp tên? ([data/reports/link_evaluation.md](../data/reports/link_evaluation.md))

[scripts/eval_linking.py](../scripts/eval_linking.py) mô phỏng cách liên kết kiểu **Silk** (Jaccard trên token của tên, như
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

* [scripts/step5_reason.py](../scripts/step5_reason.py) gồm 4 việc:
  - materialize bằng **owlrl**, sinh 20.990 triple mới về cá thể;
  - kiểm tra nhất quán (disjoint, AllDifferent, thuộc tính hàm, `owl:Nothing`); kết quả hiện tại là **nhất quán**;
  - kiểm định **SHACL** ([shapes/vnedu-shapes.ttl](../shapes/vnedu-shapes.ttl)): `conforms = True`, kèm 34 cảnh báo thiếu
    thông tin và 0 cảnh báo "trường tư thục mà infobox ghi Bộ GD&ĐT là chủ quản";
  - gộp tất cả thành `vnedu-all.ttl`.
  Không đưa `owl:sameAs` ra ngoài vào suy luận, vì làm vậy sẽ nhân bản mọi triple sang URI của Wikidata.
* **Fuseki**: [fuseki/run_fuseki.ps1](../fuseki/run_fuseki.ps1) (hoặc `fuseki/start.cmd`, `fuseki/docker-compose.yml`
  cùng `scripts/step5_load_fuseki.py`).
* **Web** [app/server.py](../app/server.py):
  - `/sparql`: SPARQL 1.1 Protocol;
  - `/query`: YASGUI kèm 15 truy vấn mẫu;
  - `/resource/…`: **dereference URI** có content negotiation (trình duyệt nhận HTML, máy nhận Turtle/JSON-LD qua
    `Accept` hoặc `?format=ttl`); mỗi giá trị do bộ suy luận sinh ra có nhãn "suy luận";
  - `/ontology`, `/dataset` (VoID), `/download/…`.
* **Terminal** [query.py](../query.py): `py query.py --list`, `py query.py queries/03_truong_quan_doi_cong_an.rq`, `py query.py -i`
  (dùng `--local` nếu không chạy Fuseki).
* **Báo cáo chất lượng** [scripts/step6_report.py](../scripts/step6_report.py) → [data/reports/quality_report.md](../data/reports/quality_report.md):
  dòng dõi dữ liệu, độ đầy đủ theo trường, nguồn của giá trị, mâu thuẫn, kết quả các cổng kiểm định, checklist 5 sao.
* **Kiểm thử**: `py -m pytest tests -q`, gồm **84 test** (thêm [test_server.py](../tests/test_server.py): 27 test máy chủ web — content negotiation, SSRF, chèn SPARQL) (thêm [test_infobox_media.py](../tests/test_infobox_media.py): 11 test infobox, ảnh, lịch sử):
  - [test_reasoning.py](../tests/test_reasoning.py): 8 test suy luận đúng, 5 test phát hiện dữ liệu sai, 1 test toàn bộ dữ liệu thật nhất quán;
  - [test_extraction.py](../tests/test_extraction.py): 29 test trích xuất dùng câu thật từ Wikipedia (gồm ca "chú thích ảnh năm 1920" và chuẩn hoá tên Bộ);
  - [test_data_contract.py](../tests/test_data_contract.py): 3 test chứng minh JSON Schema chặn được bản ghi sai.

### Truy vấn mẫu ([queries/](../queries), sinh bởi `queries/_generate.py`)

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

## Bước 6–7 — Báo cáo chất lượng & công bố ([scripts/step7_publish.py](../scripts/step7_publish.py))

`step7_publish.py` sinh site tĩnh `site/` (≈6.700 tệp), GitHub Actions ([.github/workflows/pages.yml](../.github/workflows/pages.yml))
đưa lên **GitHub Pages** tại URI gốc cố định `https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/`:

| Đường dẫn | Nội dung |
|---|---|
| `resource/<loại>/<tên>` | **2.241 URI tra cứu được** — HTML cho người, **JSON-LD nhúng** (JSON-LD 1.1) cho máy, `<link rel="alternate">` tới `.ttl` / `.jsonld` |
| `ontology` (+`.ttl`, `.jsonld`) | tài liệu ontology + **cây lớp tương tác** (D3); `ontology#Lop` neo đúng mục |
| `dataset` | VoID + DCAT (giấy phép, linkset, phân phối) |
| `/` | thống kê (theo tỉnh 2025, miền × sở hữu, thập kỷ thành lập, loại hình, chủ quản, liên kết), chỉ số chất lượng |
| `map` | bản đồ Leaflet: điểm theo miền, lớp mật độ theo tỉnh, lọc theo sở hữu/loại hình, popup dẫn tới URI |
| `explore` | tra cứu không dấu, lọc, sắp xếp, **xuất CSV** |
| `sparql` | **SPARQL 1.1 trong trình duyệt** (Oxigraph WebAssembly) trên toàn bộ 48.428 triple — không cần máy chủ |
| `download/` | dump Turtle, N-Triples, ZIP, shapes, JSON Schema |

GitHub Pages là hosting tĩnh nên không có content negotiation phía máy chủ; máy đọc lấy RDF bằng JSON-LD nhúng trong
trang hoặc thêm đuôi `.ttl` / `.jsonld`. Nếu cần negotiation thật, có thể đăng ký `https://w3id.org/vnedu/` trỏ về site này.

## Thang 5 sao

| Sao | Đạt được bằng |
|---|---|
| ★ | **Công khai trên Web** tại https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ với giấy phép **CC BY-SA 4.0** ([LICENSE-DATA.md](../LICENSE-DATA.md)). Phải là share-alike vì dữ liệu dẫn xuất từ Wikipedia (CC BY-SA); Wikidata là CC0 |
| ★★ | Có cấu trúc, máy đọc được (JSON trong `data/bronze`, `data/silver`; CSV trong `data/reference`) |
| ★★★ | Định dạng mở, không độc quyền (CSV, JSON, Turtle) |
| ★★★★ | Chuẩn W3C: RDF, OWL 2 RL, SHACL, SPARQL 1.1, PROV-O, VoID/DCAT, JSON-LD 1.1. Mỗi thực thể có HTTP URI công khai, cố định, tra cứu được (HTML + JSON-LD nhúng, `.ttl`, `.jsonld`) |
| ★★★★★ | Liên kết tới Wikidata, DBpedia, GeoNames, ROR, Wikipedia (`owl:sameAs`, `skos:closeMatch`, `foaf:isPrimaryTopicOf`); mô tả linkset trong VoID; truy vấn federated đi theo liên kết |
