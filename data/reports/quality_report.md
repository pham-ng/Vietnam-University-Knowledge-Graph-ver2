# Báo cáo chất lượng dữ liệu VN-Edu LOD

*Sinh tự động bởi `scripts/step6_report.py` sau mỗi lần chạy pipeline.*

## 1. Dòng dõi dữ liệu (Medallion)

| Tầng | Tệp | Số lượng | SHA-256 | Tạo lúc |
|---|---|---|---|---|
| bronze | `data/bronze/dbp_years.json` | 72 records | `7a669856282b` | 2026-10-06T11:01:36 |
| bronze | `data/bronze/viwiki_pages.json` | 279 records | `bdf7dd176216` | 2026-10-06T11:01:35 |
| bronze | `data/bronze/wd_alumni.json` | 1,531 records | `05c0781d29f8` | 2026-10-06T11:02:02 |
| bronze | `data/bronze/wd_entities.json` | 5 records | `e52e8701c307` | 2026-10-06T11:01:36 |
| bronze | `data/bronze/wd_institutions.json` | 363 records | `0bb7368d5b1d` | 2026-10-06T11:01:36 |
| bronze | `data/bronze/wd_provinces.json` | 63 records | `e27588d03d60` | 2026-10-06T11:01:36 |
| silver | `data/silver/governing_bodies.json` | 47 records | `ccffa0054580` | 2026-10-06T11:05:20 |
| silver | `data/silver/institutions.json` | 300 records | `ab01a17c40af` | 2026-10-06T11:05:20 |
| silver | `data/silver/people.json` | 1,668 records | `e97912df19c1` | 2026-10-06T11:05:21 |
| silver | `data/silver/provinces.json` | 63 records | `a3275bbe296d` | 2026-10-06T11:05:21 |
| gold | `data/gold/vnedu-all.ttl` | 36,750 triples | `555d18b750f5` | 2026-10-06T14:05:40 |
| gold | `data/gold/vnedu-data.ttl` | 17,940 triples | `5fe1bf47ca64` | 2026-10-06T14:04:55 |
| gold | `data/gold/vnedu-inferred.ttl` | 14,484 triples | `51428252484d` | 2026-10-06T14:05:27 |
| gold | `data/gold/vnedu-links.ttl` | 3,670 triples | `e313f8b31c68` | 2026-10-06T14:04:57 |
| gold | `data/gold/void.ttl` | 96 triples | `639e70eead3d` | 2026-10-06T14:04:57 |

## 2. Độ đầy đủ — 271 cơ sở giáo dục đại học (tầng silver)

| Thuộc tính | Có | Tỉ lệ | |
|---|---|---|---|
| năm thành lập | 261 | 96.3% | `███████████████████░` |
| tỉnh/thành | 263 | 97.0% | `███████████████████░` |
| loại hình sở hữu | 247 | 91.1% | `██████████████████░░` |
| website | 221 | 81.5% | `████████████████░░░░` |
| lãnh đạo | 189 | 69.7% | `██████████████░░░░░░` |
| cơ quan chủ quản | 131 | 48.3% | `██████████░░░░░░░░░░` |
| tên tiếng Anh | 226 | 83.4% | `█████████████████░░░` |
| tên viết tắt | 88 | 32.5% | `██████░░░░░░░░░░░░░░` |
| khẩu hiệu | 122 | 45.0% | `█████████░░░░░░░░░░░` |
| toạ độ | 163 | 60.1% | `████████████░░░░░░░░` |
| mã trường | 60 | 22.1% | `████░░░░░░░░░░░░░░░░` |
| mã ROR | 192 | 70.8% | `██████████████░░░░░░` |
| số sinh viên | 24 | 8.9% | `██░░░░░░░░░░░░░░░░░░` |
| số giảng viên | 33 | 12.2% | `██░░░░░░░░░░░░░░░░░░` |

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
| viwiki – đoạn mở đầu | governed_by/member_of | 39 |
| viwiki – đoạn mở đầu | ownership | 19 |
| viwiki – đoạn mở đầu | province | 11 |
| địa chỉ → OpenStreetMap Nominatim (kiểm tra cùng tỉnh) | coordinates | 62 |
| địa danh trong tên | province | 6 |

Mâu thuẫn giữa các nguồn (`conflicts.csv`):

| Trường | Số mâu thuẫn |
|---|---|
| founding_year | 32 |
| birth_date | 5 |
| province | 4 |

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
| SHACL (`shapes/vnedu-shapes.ttl`) | gold | ✅ conforms — 0 vi phạm, 36 cảnh báo, 1 thông tin |

| Mức | Thông điệp SHACL | Số |
|---|---|---|
| Warning | Thiếu năm thành lập. | 22 |
| Warning | Thiếu tỉnh/thành nơi đặt trụ sở. | 12 |
| Warning | Cơ sở tư thục lại có Bộ làm cơ quan chủ quản — cần kiểm tra. | 2 |
| Info | Trường thành viên đặt ở tỉnh khác với đại học chủ quản (https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/province/an-giang ≠ https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/province/thanh-pho-ho-chi-minh). | 1 |

## 5. Liên kết (5 sao)

| Đích | Thuộc tính | Số liên kết |
|---|---|---|
| wikidata | `owl:sameAs` | 1878 |
| wikipedia | `foaf:isPrimaryTopicOf` | 1188 |
| dbpedia | `owl:sameAs` | 258 |
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
| ★★★★ | Chuẩn W3C, URI dereference được | RDF/OWL 2 RL/SHACL/SPARQL 1.1/PROV-O; 36,750 triple (trong đó 14,484 suy luận); HTTP URI + content negotiation (`app/server.py`) |
| ★★★★★ | Liên kết tới dataset khác | 3,670 liên kết tới Wikidata, DBpedia, ROR, GeoNames, Wikipedia; `void:Linkset` |
