# Báo cáo chất lượng dữ liệu VN-Edu LOD

*Sinh tự động bởi `scripts/step6_report.py` sau mỗi lần chạy pipeline.*

## 1. Dòng dõi dữ liệu (Medallion)

| Tầng | Tệp | Số lượng | SHA-256 | Tạo lúc |
|---|---|---|---|---|
| bronze | `data/bronze/dbp_years.json` | 72 records | `c0b0f72eae48` | 2026-10-08T00:42:37 |
| bronze | `data/bronze/moet_admissions.json` | 405 records | `8f078d80eb5f` | 2026-10-09T03:11:10 |
| bronze | `data/bronze/ror_organizations.json` | 202 records | `c5e8fc0c544a` | 2026-10-09T03:11:20 |
| bronze | `data/bronze/viwiki_images.json` | 280 records | `4df5192d37df` | 2026-10-08T00:42:37 |
| bronze | `data/bronze/viwiki_links.json` | 80 records | `c1a26b63cff7` | 2026-10-08T00:42:36 |
| bronze | `data/bronze/viwiki_pages.json` | 279 records | `f3a91fa46eb3` | 2026-10-08T00:42:36 |
| bronze | `data/bronze/wd_alumni.json` | 1,531 records | `af11c19def93` | 2026-10-08T00:42:39 |
| bronze | `data/bronze/wd_entities.json` | 12 records | `9dff7acfa914` | 2026-10-08T00:42:37 |
| bronze | `data/bronze/wd_institutions.json` | 363 records | `3539a0481f33` | 2026-10-08T00:42:37 |
| bronze | `data/bronze/wd_provinces.json` | 63 records | `9bc0e96c5231` | 2026-10-08T00:42:37 |
| silver | `data/silver/governing_bodies.json` | 50 records | `6bee7090a9a7` | 2026-10-09T03:27:35 |
| silver | `data/silver/institutions.json` | 300 records | `638e84551dae` | 2026-10-09T03:27:35 |
| silver | `data/silver/people.json` | 1,702 records | `5de5683cb457` | 2026-10-09T03:27:35 |
| silver | `data/silver/provinces.json` | 63 records | `4cbac2c46a0d` | 2026-10-09T03:27:35 |
| gold | `data/gold/vnedu-all.ttl` | 87,117 triples | `7dfefff61537` | 2026-10-09T08:43:46 |
| gold | `data/gold/vnedu-data.ttl` | 59,428 triples | `53099a993834` | 2026-10-09T03:27:39 |
| gold | `data/gold/vnedu-inferred.ttl` | 23,169 triples | `fe463668be11` | 2026-10-09T08:43:43 |
| gold | `data/gold/vnedu-links.ttl` | 3,558 triples | `53197c8a1276` | 2026-10-09T08:27:43 |
| gold | `data/gold/void.ttl` | 104 triples | `f40a7c2e99d4` | 2026-10-09T08:27:47 |

## 2. Độ đầy đủ — 271 cơ sở giáo dục đại học (tầng silver)

| Thuộc tính | Có | Tỉ lệ | |
|---|---|---|---|
| năm thành lập | 261 | 96.3% | `███████████████████░` |
| tỉnh/thành | 263 | 97.0% | `███████████████████░` |
| loại hình sở hữu | 247 | 91.1% | `██████████████████░░` |
| website | 243 | 89.7% | `██████████████████░░` |
| lãnh đạo | 195 | 72.0% | `██████████████░░░░░░` |
| cơ quan chủ quản | 138 | 50.9% | `██████████░░░░░░░░░░` |
| tên tiếng Anh | 226 | 83.4% | `█████████████████░░░` |
| tên viết tắt | 177 | 65.3% | `█████████████░░░░░░░` |
| khẩu hiệu | 126 | 46.5% | `█████████░░░░░░░░░░░` |
| toạ độ | 164 | 60.5% | `████████████░░░░░░░░` |
| mã trường | 218 | 80.4% | `████████████████░░░░` |
| mã ROR | 192 | 70.8% | `██████████████░░░░░░` |
| số sinh viên | 25 | 9.2% | `██░░░░░░░░░░░░░░░░░░` |
| số giảng viên | 33 | 12.2% | `██░░░░░░░░░░░░░░░░░░` |
| giới thiệu chung | 261 | 96.3% | `███████████████████░` |
| lịch sử | 217 | 80.1% | `████████████████░░░░` |
| biểu trưng | 144 | 53.1% | `███████████░░░░░░░░░` |
| ảnh | 93 | 34.3% | `███████░░░░░░░░░░░░░` |
| ngày thành lập đầy đủ | 114 | 42.1% | `████████░░░░░░░░░░░░` |
| tên khác | 53 | 19.6% | `████░░░░░░░░░░░░░░░░` |
| điện thoại | 235 | 86.7% | `█████████████████░░░` |
| email | 215 | 79.3% | `████████████████░░░░` |
| khuôn viên | 41 | 15.1% | `███░░░░░░░░░░░░░░░░░` |

## 3. Nguồn hiện hành và chính sách chấp nhận

Các giá trị mới chỉ được hợp nhất khi tên chính thức khớp chính xác. Ngoại lệ duy nhất là cặp tên cũ–tên hiện hành đã được khai báo bằng quyết định đổi tên có ngày; fuzzy match chỉ được xem là ứng viên. Thời điểm truy xuất là thời điểm của snapshot, không được diễn giải thành thời hạn hiệu lực pháp lý.

| Nguồn | Bản ghi | Truy xuất (UTC) | Giấy phép/trạng thái |
|---|---:|---|---|
| Cổng tuyển sinh Bộ GDĐT | 405 | 2026-10-08T20:11:10+00:00 | Official public facts; no machine-readable open-data licence stated |
| ROR schema 2.1 | 202 | 2026-10-08T20:11:20+00:00 | CC0 1.0 |

| Trường có nguồn cấp thuộc tính | Số cơ sở GDĐH |
|---|---:|
| mã tuyển sinh — Bộ GDĐT | 202 |
| email — Bộ GDĐT | 201 |
| website — Bộ GDĐT | 204 |
| tên viết tắt — ROR | 147 |
| tên cũ — quyết định đổi tên | 4 |
| cơ quan chủ quản trực tiếp — văn bản pháp lý | 41 |

**Toạ độ:** `nominatim-address` 58, `viwiki` 13, `wikidata` 93. Không dùng toạ độ ROR làm toạ độ campus vì ROR/GeoNames thường biểu diễn tâm địa phương, không phải điểm của cơ sở.

**Campus:** `vnedu:campus` hiện lưu diện tích/mô tả khuôn viên từ nguồn, không đồng nghĩa với địa chỉ trụ sở. Không tự động sao chép địa chỉ vào trường này chỉ để tăng coverage.

## 4. Nguồn của giá trị và mâu thuẫn giữa các nguồn

Giá trị chính lấy từ Wikidata và infobox Wikipedia tiếng Việt (đối chiếu chéo). Khi cả hai đều thiếu, dùng nguồn dự phòng — mỗi giá trị đều được ghi lại trong `filled.csv`:

| Nguồn dự phòng | Trường | Số giá trị |
|---|---|---|
| 1723/QĐ-TTg | direct_governed_by | 41 |
| DBpedia (infobox Wikipedia tiếng Anh) | founding_year | 1 |
| Wikidata – mô tả | ownership | 7 |
| phân biệt thực thể trùng tên | name_vi | 1 |
| toạ độ → OpenStreetMap Nominatim | province | 1 |
| viwiki – đoạn mở đầu | dissolution_year | 11 |
| viwiki – đoạn mở đầu | founding_year | 18 |
| viwiki – đoạn mở đầu | governed_by/member_of | 38 |
| viwiki – đoạn mở đầu | ownership | 19 |
| viwiki – đoạn mở đầu | province | 11 |
| địa chỉ → OpenStreetMap Nominatim (kiểm tra cùng tỉnh) | coordinates | 63 |
| địa danh trong tên | province | 6 |

Mâu thuẫn giữa các nguồn (`conflicts.csv`):

| Trường | Số mâu thuẫn |
|---|---|
| website | 137 |
| email | 37 |
| founding_year | 32 |
| province | 5 |
| birth_date | 5 |
| admission_codes | 3 |

Thực thể bị loại khỏi phạm vi (`excluded.csv`): **68**

| Lý do | Số |
|---|---|
| đơn vị cấp khoa/bộ môn, không có nhãn tiếng Việt | 44 |
| chỉ có trong Wikidata, không có nhãn tiếng Việt và bài viwiki | 12 |
| không phải cơ sở GDĐH (trường phổ thông / bài không phải tổ chức) | 8 |
| trùng với … | 4 |

Giá trị chưa phân giải được, cần rà soát tay (`unresolved.csv`): **7**

## 5. Kiểm định

| Cổng kiểm định | Tầng | Kết quả |
|---|---|---|
| JSON Schema (`schemas/silver.schema.json`) | silver | ✅ đạt — 0 vi phạm |
| Nhất quán logic OWL 2 RL (disjoint, functional, AllDifferent) | gold | ✅ nhất quán |
| SHACL (`shapes/vnedu-shapes.ttl`) | gold | ✅ conforms — 0 vi phạm, 34 cảnh báo, 1 thông tin |

| Mức | Thông điệp SHACL | Số |
|---|---|---|
| Warning | Thiếu năm thành lập. | 22 |
| Warning | Thiếu tỉnh/thành nơi đặt trụ sở. | 12 |
| Info | Trường thành viên đặt ở tỉnh khác với đại học chủ quản (https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/province/an-giang ≠ https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/province/thanh-pho-ho-chi-minh). | 1 |

## 6. Liên kết (5 sao)

| Đích | Thuộc tính | Số liên kết |
|---|---|---|
| wikidata | `owl:sameAs` | 1850 |
| wikipedia | `foaf:isPrimaryTopicOf` | 1188 |
| dbpedia | `owl:sameAs` | 201 |
| ror | `owl:sameAs` | 195 |
| geonames | `owl:sameAs` | 63 |
| wikidata | `skos:closeMatch` | 35 |
| dbpedia | `skos:closeMatch` | 26 |

Đánh giá phương pháp liên kết: xem [link_evaluation.md](link_evaluation.md) — so khớp chuỗi kiểu Silk so với liên kết theo định danh.

## 7. Checklist 5 sao

| | Tiêu chí | Bằng chứng |
|---|---|---|
| ★ | Công khai, quyền tái sử dụng minh bạch | CC BY-SA 4.0 chỉ áp dụng cho phần dự án có quyền cấp phép; `dct:rights`, `LICENSE-DATA.md` và `*.meta.json` giữ điều kiện riêng của từng nguồn (nguồn Bộ GD&ĐT chưa công bố giấy phép dữ liệu mở dạng máy đọc được) |
| ★★ | Có cấu trúc, máy đọc được | JSON (bronze/silver), RDF (gold) |
| ★★★ | Định dạng mở | JSON, CSV, Turtle |
| ★★★★ | Chuẩn W3C, URI dereference được | RDF/OWL 2 RL/SHACL/SPARQL 1.1/PROV-O; 87,117 triple (trong đó 23,169 suy luận); HTTP URI + content negotiation (`app/server.py`) |
| ★★★★★ | Liên kết tới dataset khác | 3,558 liên kết tới Wikidata, DBpedia, ROR, GeoNames, Wikipedia; `void:Linkset` |
