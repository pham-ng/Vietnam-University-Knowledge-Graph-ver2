# Báo cáo chất lượng dữ liệu VN-Edu LOD

*Sinh tự động bởi `scripts/step6_report.py` sau mỗi lần chạy pipeline.*

## 1. Dòng dõi dữ liệu (Medallion)

| Tầng | Tệp | Số lượng | SHA-256 | Tạo lúc |
|---|---|---|---|---|
| bronze | `data/bronze/dbp_years.json` | 72 records | `c0b0f72eae48` | 2026-10-10T02:39:31 |
| bronze | `data/bronze/moet_admissions.json` | 405 records | `49df1786c58e` | 2026-10-10T02:39:32 |
| bronze | `data/bronze/ror_organizations.json` | 202 records | `c5e8fc0c544a` | 2026-10-10T02:39:32 |
| bronze | `data/bronze/viwiki_images.json` | 280 records | `4df5192d37df` | 2026-10-10T02:39:31 |
| bronze | `data/bronze/viwiki_links.json` | 80 records | `c1a26b63cff7` | 2026-10-10T02:39:30 |
| bronze | `data/bronze/viwiki_pages.json` | 279 records | `f3a91fa46eb3` | 2026-10-10T02:39:30 |
| bronze | `data/bronze/wd_alumni.json` | 1,531 records | `af11c19def93` | 2026-10-10T02:39:32 |
| bronze | `data/bronze/wd_entities.json` | 12 records | `9dff7acfa914` | 2026-10-10T02:39:31 |
| bronze | `data/bronze/wd_institutions.json` | 363 records | `3539a0481f33` | 2026-10-10T02:39:31 |
| bronze | `data/bronze/wd_provinces.json` | 63 records | `9bc0e96c5231` | 2026-10-10T02:39:31 |
| silver | `data/silver/governing_bodies.json` | 50 records | `a4fa23b18217` | 2026-10-10T02:39:34 |
| silver | `data/silver/institutions.json` | 297 records | `84f8a4538209` | 2026-10-10T02:39:34 |
| silver | `data/silver/people.json` | 1,703 records | `6e7c31f5af19` | 2026-10-10T02:39:34 |
| silver | `data/silver/provinces.json` | 63 records | `4cbac2c46a0d` | 2026-10-10T02:39:34 |
| gold | `data/gold/vnedu-all.ttl` | 87,162 triples | `291c59601820` | 2026-10-10T02:40:58 |
| gold | `data/gold/vnedu-data.ttl` | 59,392 triples | `c5cb46485ee6` | 2026-10-10T02:39:38 |
| gold | `data/gold/vnedu-geo-osm.ttl` | 126 triples | `6ac319066fa9` | 2026-10-10T02:39:38 |
| gold | `data/gold/vnedu-inferred.ttl` | 23,014 triples | `cd94af955141` | 2026-10-10T02:40:54 |
| gold | `data/gold/vnedu-links.ttl` | 3,557 triples | `64e97a1b1caa` | 2026-10-10T02:39:40 |
| gold | `data/gold/void.ttl` | 129 triples | `4a0e75501ec1` | 2026-10-10T02:40:55 |

## 2. Độ đầy đủ — 268 cơ sở giáo dục đại học (tầng silver)

| Thuộc tính | Có | Tỉ lệ | |
|---|---|---|---|
| năm thành lập | 259 | 96.6% | `███████████████████░` |
| tỉnh/thành | 260 | 97.0% | `███████████████████░` |
| loại hình sở hữu | 246 | 91.8% | `██████████████████░░` |
| website | 241 | 89.9% | `██████████████████░░` |
| lãnh đạo | 195 | 72.8% | `███████████████░░░░░` |
| cơ quan chủ quản | 138 | 51.5% | `██████████░░░░░░░░░░` |
| tên tiếng Anh | 225 | 84.0% | `█████████████████░░░` |
| tên viết tắt | 177 | 66.0% | `█████████████░░░░░░░` |
| khẩu hiệu | 126 | 47.0% | `█████████░░░░░░░░░░░` |
| toạ độ | 164 | 61.2% | `████████████░░░░░░░░` |
| mã trường | 216 | 80.6% | `████████████████░░░░` |
| mã ROR | 192 | 71.6% | `██████████████░░░░░░` |
| số sinh viên | 25 | 9.3% | `██░░░░░░░░░░░░░░░░░░` |
| số giảng viên | 33 | 12.3% | `██░░░░░░░░░░░░░░░░░░` |
| giới thiệu chung | 260 | 97.0% | `███████████████████░` |
| lịch sử | 217 | 81.0% | `████████████████░░░░` |
| biểu trưng | 144 | 53.7% | `███████████░░░░░░░░░` |
| ảnh | 93 | 34.7% | `███████░░░░░░░░░░░░░` |
| ngày thành lập đầy đủ | 114 | 42.5% | `█████████░░░░░░░░░░░` |
| tên khác | 53 | 19.8% | `████░░░░░░░░░░░░░░░░` |
| điện thoại | 233 | 86.9% | `█████████████████░░░` |
| email | 213 | 79.5% | `████████████████░░░░` |
| khuôn viên | 41 | 15.3% | `███░░░░░░░░░░░░░░░░░` |

## 3. Nguồn hiện hành và chính sách chấp nhận

Các giá trị mới chỉ được hợp nhất khi tên chính thức khớp chính xác. Ngoại lệ duy nhất là cặp tên cũ–tên hiện hành đã được khai báo bằng quyết định đổi tên có ngày; fuzzy match chỉ được xem là ứng viên. Thời điểm truy xuất là thời điểm của snapshot, không được diễn giải thành thời hạn hiệu lực pháp lý.

| Nguồn | Bản ghi | Truy xuất (UTC) | Giấy phép/trạng thái |
|---|---:|---|---|
| Cổng tuyển sinh Bộ GDĐT | 405 | 2026-10-09T03:31:04+00:00 | Official public facts; no machine-readable open-data licence stated |
| ROR schema 2.1 | 202 | 2026-10-09T03:31:18+00:00 | CC0 1.0 |

| Trường có nguồn cấp thuộc tính | Số cơ sở GDĐH |
|---|---:|
| mã tuyển sinh — Bộ GDĐT | 200 |
| email — Bộ GDĐT | 199 |
| website — Bộ GDĐT | 202 |
| tên viết tắt — ROR | 147 |
| tên cũ — quyết định đổi tên | 5 |
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
| https://congbao.hatinh.gov.vn/vbpq_hatinh.nsf/64f0c917e087475547256f96002869cb/8D30CB0399EAB67D47258B510030C135/$file/bao-cao-so-ket-5-nam-nam-thuc-hien-Luat-Giao-duc-dai-hoc-ban-hanh-(04.07.2024_16h48p51)_signed.pdf | ownership | 1 |
| https://hcmus.edu.vn/dhqg-tp-hcm-va-cac-don-vi-thanh-vien/ | member_of | 1 |
| https://ussh.vnu.edu.vn/vi/ | member_of | 1 |
| https://vbu.edu.vn/ | ownership | 1 |
| https://www.rmit.edu.vn/about-us | ownership | 1 |
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
| website | 136 |
| email | 37 |
| founding_year | 32 |
| province | 5 |
| birth_date | 5 |
| admission_codes | 3 |
| ownership | 2 |

Thực thể bị loại khỏi phạm vi (`excluded.csv`): **71**

| Lý do | Số |
|---|---|
| đơn vị cấp khoa/bộ môn, không có nhãn tiếng Việt | 44 |
| chỉ có trong Wikidata, không có nhãn tiếng Việt và bài viwiki | 12 |
| không phải cơ sở GDĐH (trường phổ thông / bài không phải tổ chức) | 8 |
| trùng với … | 4 |
| trang hệ thống Wikimedia (định hướng / thể loại / bản mẫu / danh sách), không phải tổ chức | 1 |
| trùng với … (cùng tên, cùng đang hoạt động) | 1 |
| trùng với … (đổi tên/chuyển đổi theo Quyết định của Thủ tướng Chính phủ (công bố 04/08/202 | 1 |

Giá trị chưa phân giải được, cần rà soát tay (`unresolved.csv`): **7**

## 5. Kiểm định

| Cổng kiểm định | Tầng | Kết quả |
|---|---|---|
| JSON Schema (`schemas/silver.schema.json`) | silver | ✅ đạt — 0 vi phạm |
| Nhất quán logic OWL 2 RL (disjoint, functional, AllDifferent) | gold | ✅ nhất quán |
| SHACL (`shapes/vnedu-shapes.ttl`) | gold | ✅ conforms — 0 vi phạm, 33 cảnh báo, 1 thông tin |

| Mức | Thông điệp SHACL | Số |
|---|---|---|
| Warning | Thiếu năm thành lập. | 21 |
| Warning | Thiếu tỉnh/thành nơi đặt trụ sở. | 12 |
| Info | Trường thành viên đặt ở tỉnh khác với đại học chủ quản (https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/province/an-giang ≠ https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/province/thanh-pho-ho-chi-minh). | 1 |

## 6. Liên kết (5 sao)

| Đích | Thuộc tính | Số liên kết |
|---|---|---|
| wikidata | `owl:sameAs` | 1850 |
| wikipedia | `foaf:isPrimaryTopicOf` | 1186 |
| dbpedia | `owl:sameAs` | 202 |
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
| ★★★★ | Chuẩn W3C, URI dereference được | RDF/OWL 2 RL/SHACL/SPARQL 1.1/PROV-O; 87,162 triple (trong đó 23,014 suy luận); HTTP URI + content negotiation (`app/server.py`) |
| ★★★★★ | Liên kết tới dataset khác | 3,557 liên kết tới Wikidata, DBpedia, ROR, GeoNames, Wikipedia; `void:Linkset` |
