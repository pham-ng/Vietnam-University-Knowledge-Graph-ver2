# Giấy phép dữ liệu và quyền theo nguồn

Dưới phạm vi quyền mà nhóm dự án nắm giữ, phần biên soạn, mô hình dữ liệu, ontology, SHACL và các đóng góp gốc của
VN-Edu LOD được phát hành theo **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**:
https://creativecommons.org/licenses/by-sa/4.0/ (toàn văn: https://creativecommons.org/licenses/by-sa/4.0/legalcode).

Tuyên bố này **không tái cấp phép nội dung của bên thứ ba**. Mỗi giá trị vẫn chịu điều kiện của nguồn tương ứng;
`prov:wasDerivedFrom`, `data/bronze/*.meta.json` và các observation của bản phát hành phải được giữ lại. Với nguồn
không công bố giấy phép dữ liệu mở rõ ràng, dự án chỉ ghi nhận các sự kiện công khai tối thiểu và không khẳng định rằng
CC BY-SA có thể thay thế điều khoản của cơ quan cung cấp.

Bạn được sao chép, phân phối, chỉnh sửa và dùng cho mục đích thương mại, với điều kiện **ghi nguồn** (VN-Edu LOD,
https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/) và **phát hành sản phẩm phái sinh dưới cùng giấy phép**.

## Vì sao là CC BY-SA

Dữ liệu được dẫn xuất từ:

| Nguồn | Giấy phép | Ghi chú |
|---|---|---|
| Wikidata | CC0 1.0 | không ràng buộc |
| Wikipedia tiếng Việt (infobox, đoạn mở đầu) | CC BY-SA 4.0 | **share-alike** ⇒ dữ liệu phái sinh phải dùng giấy phép tương thích |
| DBpedia | CC BY-SA 3.0 | dùng làm liên kết và năm thành lập dự phòng |
| Research Organization Registry (ROR) | CC0 1.0 | tên viết tắt và định danh ROR; không dùng tâm địa phương làm tọa độ campus |
| OpenStreetMap (Nominatim) | ODbL 1.0 | chỉ dùng toạ độ điểm đơn lẻ, ghi nguồn © OpenStreetMap contributors |
| Cổng tuyển sinh Bộ GD&ĐT | **không thấy giấy phép dữ liệu mở dạng máy đọc được tại thời điểm snapshot** | mã tuyển sinh và thông tin liên hệ công khai; phải giữ nguồn và tự kiểm tra quyền khi tái sử dụng |
| Văn bản pháp lý và quyết định đổi tên/chủ quản | nguồn công báo hoặc cơ quan ban hành | giữ nguyên số, ngày hiệu lực và URL; việc tái sử dụng tuân theo pháp luật áp dụng |

Giấy phép của từng ảnh chụp nguồn được ghi trong `data/bronze/*.meta.json`; mỗi thực thể có `prov:wasDerivedFrom`
trỏ tới nguồn gốc cụ thể. Mã nguồn (`scripts/`, `app/`, `site_src/`, `tests/`…) dùng giấy phép MIT — xem `LICENSE`.
## Media and source-specific rights

The dataset license does not relicense remotely linked photographs, logos, trademarks,
or other third-party media. Their individual source-page terms remain applicable.
Unknown, fair-use and unrecognized media licenses are link-only in the generated site;
only the explicitly recognized public-domain/CC0/CC BY/CC BY-SA labels are embedded.
This conservative display policy is not a legal determination or a guarantee of source metadata.
Retain source links, attribution and license metadata when reusing individual assets.

## Five-star scope

The five-star statement applies to the publication mechanics of the openly licensed
compilation and link graph. It is not a blanket warranty that every upstream fact is
independently open-licensed, accurate, current, or free of third-party rights.
