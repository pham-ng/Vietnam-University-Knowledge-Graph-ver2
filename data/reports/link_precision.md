# Precision của liên kết owl:sameAs — mẫu ngẫu nhiên phân tầng

Seed 20261009; mẫu rút từ toàn bộ owl:sameAs đã phát hành (không dùng tập tham chiếu của linker). Mỗi liên kết được đối chiếu loại thực thể, tên (và năm sinh với người) với siêu dữ liệu của chính đích; trường hợp không qua kiểm tra tự động được đánh giá thủ công (`data/reference/link_precision_review.csv`).

| Tầng | Số liên kết | Mẫu | Đúng | Sai | Chưa đánh giá | Precision | Wilson 95% |
|---|--:|--:|--:|--:|--:|--:|---|
| wikidata | 1850 | 60 | 60 | 0 | 0 | 100.0% | 94.0% – 100.0% |
| dbpedia | 202 | 20 | 20 | 0 | 0 | 100.0% | 83.9% – 100.0% |
| ror | 195 | 10 | 10 | 0 | 0 | 100.0% | 72.2% – 100.0% |
| geonames | 63 | 10 | 10 | 0 | 0 | 100.0% | 72.2% – 100.0% |

**Precision có trọng số theo kích thước tầng: 100.0%** (chưa trọng số: 100/100, Wilson 95% 96.3% – 100.0%).

Phân loại tự động: correct 93, review 7.

## Hạn chế

- Một người đánh giá thủ công cho các trường hợp không qua kiểm tra tự động; chưa có người thứ hai để đo Cohen κ.
- Chỉ ước lượng precision; recall cần tập vàng gồm cả các cặp không được liên kết.
- Kiểm tra tự động dùng nhãn và loại ở phía đích, độc lập với quy tắc khớp của linker, nhưng cả hai cùng dựa vào nhãn tên nên không hoàn toàn độc lập.
