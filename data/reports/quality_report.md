# Báo cáo chất lượng dữ liệu VN-Edu LOD

*Sinh tự động bởi `scripts/step6_report.py` sau mỗi lần chạy pipeline.*

## 1. Dòng dõi dữ liệu (Medallion)

| Tầng | Tệp | Số lượng | SHA-256 | Tạo lúc |
|---|---|---|---|---|
| bronze | `data/bronze/dbp_years.json` | 72 records | `c0b0f72eae48` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/viwiki_images.json` | 280 records | `4df5192d37df` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/viwiki_links.json` | 80 records | `c1a26b63cff7` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/viwiki_pages.json` | 279 records | `f3a91fa46eb3` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/wd_alumni.json` | 1,531 records | `af11c19def93` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/wd_entities.json` | 12 records | `9dff7acfa914` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/wd_institutions.json` | 363 records | `3539a0481f33` | 2026-10-08T10:27:16 |
| bronze | `data/bronze/wd_provinces.json` | 63 records | `9bc0e96c5231` | 2026-10-08T10:27:16 |
| silver | `data/silver/governing_bodies.json` | 50 records | `6bee7090a9a7` | 2026-10-08T10:27:16 |
| silver | `data/silver/institutions.json` | 300 records | `b2b5ced4ac50` | 2026-10-08T10:27:16 |
| silver | `data/silver/people.json` | 1,695 records | `c32c2a143d12` | 2026-10-08T10:27:16 |
| silver | `data/silver/provinces.json` | 63 records | `4cbac2c46a0d` | 2026-10-08T10:27:16 |
| gold | `data/gold/vnedu-all.ttl` | 48,418 triples | `137c62b73aa5` | 2026-10-08T10:27:42 |
| gold | `data/gold/vnedu-data.ttl` | 22,903 triples | `73d2ecace72d` | 2026-10-08T10:27:17 |
| gold | `data/gold/vnedu-inferred.ttl` | 20,990 triples | `0a91cb037fcf` | 2026-10-08T10:27:35 |
| gold | `data/gold/vnedu-links.ttl` | 3,674 triples | `9058bbfe77eb` | 2026-10-08T10:27:17 |
| gold | `data/gold/void.ttl` | 96 triples | `64829a0cf1a6` | 2026-10-08T10:27:17 |

## 2. Độ đầy đủ — 271 cơ sở giáo dục đại học (tầng silver)

| Thuộc tính | Có | Tỉ lệ | |
|---|---|---|---|
| năm thành lập | 261 | 96.3% | `███████████████████░` |
| tỉnh/thành | 263 | 97.0% | `███████████████████░` |
| loại hình sở hữu | 247 | 91.1% | `██████████████████░░` |
| website | 221 | 81.5% | `████████████████░░░░` |
| lãnh đạo | 195 | 72.0% | `██████████████░░░░░░` |
| cơ quan chủ quản | 130 | 48.0% | `██████████░░░░░░░░░░` |
| tên tiếng Anh | 226 | 83.4% | `█████████████████░░░` |
| tên viết tắt | 88 | 32.5% | `██████░░░░░░░░░░░░░░` |
| khẩu hiệu | 126 | 46.5% | `█████████░░░░░░░░░░░` |
| toạ độ | 164 | 60.5% | `████████████░░░░░░░░` |
| mã trường | 60 | 22.1% | `████░░░░░░░░░░░░░░░░` |
| mã ROR | 192 | 70.8% | `██████████████░░░░░░` |
| số sinh viên | 25 | 9.2% | `██░░░░░░░░░░░░░░░░░░` |
| số giảng viên | 33 | 12.2% | `██░░░░░░░░░░░░░░░░░░` |
| giới thiệu chung | 261 | 96.3% | `███████████████████░` |
| lịch sử | 217 | 80.1% | `████████████████░░░░` |
| biểu trưng | 144 | 53.1% | `███████████░░░░░░░░░` |
| ảnh | 93 | 34.3% | `███████░░░░░░░░░░░░░` |
| ngày thành lập đầy đủ | 114 | 42.1% | `████████░░░░░░░░░░░░` |
| tên khác | 53 | 19.6% | `████░░░░░░░░░░░░░░░░` |
| điện thoại | 174 | 64.2% | `█████████████░░░░░░░` |
| email | 87 | 32.1% | `██████░░░░░░░░░░░░░░` |
| khuôn viên | 41 | 15.1% | `███░░░░░░░░░░░░░░░░░` |

## 3. Nguồn của giá trị và mâu thuẫn giữa các nguồn

Giá trị chính lấy từ Wikidata và infobox Wikipedia tiếng Việt (đối chiếu chéo). Khi cả hai đều thiếu, dùng nguồn dự phòng — mỗi giá trị đều được ghi lại trong `filled.csv`:

| Nguồn dự phòng | Trường | Số giá trị |
|---|---|---|
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
| founding_year | 32 |
| province | 5 |
| birth_date | 5 |

Thực thể bị loại khỏi phạm vi (`excluded.csv`): **68**

| Lý do | Số |
|---|---|
| đơn vị cấp khoa/bộ môn, không có nhãn tiếng Việt | 44 |
| chỉ có trong Wikidata, không có nhãn tiếng Việt và bài viwiki | 12 |
| không phải cơ sở GDĐH (trường phổ thông / bài không phải tổ chức) | 8 |
| trùng với … | 4 |

Giá trị chưa phân giải được, cần rà soát tay (`unresolved.csv`): **7**

## 4. Kiểm định

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

## 5. Liên kết (5 sao)

| Đích | Thuộc tính | Số liên kết |
|---|---|---|
| wikidata | `owl:sameAs` | 1880 |
| wikipedia | `foaf:isPrimaryTopicOf` | 1188 |
| dbpedia | `owl:sameAs` | 260 |
| ror | `owl:sameAs` | 195 |
| geonames | `owl:sameAs` | 63 |
| wikidata | `skos:closeMatch` | 51 |
| dbpedia | `skos:closeMatch` | 37 |

Đánh giá phương pháp liên kết: xem [link_evaluation.md](link_evaluation.md) — so khớp chuỗi kiểu Silk so với liên kết theo định danh.

## 6. Checklist 5 sao

| | Tiêu chí | Bằng chứng |
|---|---|---|
| ★ | Công khai, giấy phép mở | `dct:license` CC BY-SA 4.0 trong VoID/DCAT; giấy phép từng nguồn trong `*.meta.json` |
| ★★ | Có cấu trúc, máy đọc được | JSON (bronze/silver), RDF (gold) |
| ★★★ | Định dạng mở | JSON, CSV, Turtle |
| ★★★★ | Chuẩn W3C, URI dereference được | RDF/OWL 2 RL/SHACL/SPARQL 1.1/PROV-O; 48,418 triple (trong đó 20,990 suy luận); HTTP URI + content negotiation (`app/server.py`) |
| ★★★★★ | Liên kết tới dataset khác | 3,674 liên kết tới Wikidata, DBpedia, ROR, GeoNames, Wikipedia; `void:Linkset` |
