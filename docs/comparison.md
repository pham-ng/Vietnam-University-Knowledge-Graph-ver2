# So sánh với các phiên bản / dự án tham khảo

> Đánh giá đầy đủ, có số liệu đo lại được: [audit.md](audit.md).

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
| URI `semanticweb.org` không dereference được; không có VoID | 2.241 URI công khai tra cứu được trên GitHub Pages; VoID + DCAT |
| ChatGPT là một nguồn dữ liệu (không truy được nguồn gốc) | Chỉ dùng nguồn mở có giấy phép; `prov:wasDerivedFrom` tới bản sửa đổi cụ thể |
