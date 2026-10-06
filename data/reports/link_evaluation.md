# Đánh giá phương pháp liên kết

Tập đánh giá: **86** cơ sở GDĐH có tên tiếng Anh và liên kết DBpedia xác định theo định danh (Wikidata QID ↔ DBpedia `owl:sameAs`) — dùng làm *ground truth*.

Phương pháp so sánh: so khớp chuỗi kiểu **Silk** — Jaccard trên token chữ thường của tên tiếng Anh với `rdfs:label@en` của DBpedia; chọn ứng viên điểm cao nhất nếu ≥ θ.

| θ | số liên kết | đúng | sai | precision | recall | F1 |
|---|---|---|---|---|---|---|
| 0.2 | 85 | 72 | 13 | 84.7% | 83.7% | 0.842 |
| 0.3 | 82 | 72 | 10 | 87.8% | 83.7% | 0.857 |
| 0.4 | 80 | 72 | 8 | 90.0% | 83.7% | 0.867 |
| 0.5 | 76 | 70 | 6 | 92.1% | 81.4% | 0.864 |
| 0.6 | 76 | 70 | 6 | 92.1% | 81.4% | 0.864 |
| 0.7 | 73 | 68 | 5 | 93.2% | 79.1% | 0.855 |
| 0.8 | 68 | 64 | 4 | 94.1% | 74.4% | 0.831 |
| 0.9 | 58 | 57 | 1 | 98.3% | 66.3% | 0.792 |
| 1.0 | 58 | 57 | 1 | 98.3% | 66.3% | 0.792 |

Liên kết theo định danh (phương pháp của dự án): precision **100%** theo định nghĩa, recall = 86/86 trên tập này, và không cần chọn ngưỡng.

## Ví dụ liên kết SAI của so khớp chuỗi ở θ = 0.2 (13 trường hợp)

| tên nguồn | bị nối tới (sai) | đúng ra phải là | điểm |
|---|---|---|---|
| Hanoi University of Science and Technology | University of Science and Technology of Hanoi | Hanoi University of Science and Technology | 1.00 |
| International University - Vietnam National University Ho Chi Minh City | Vietnam National University, Ho Chi Minh City | Ho Chi Minh City International University | 0.88 |
| Ho Chi Minh City University of | University of Economics Ho Chi Minh City | Ho Chi Minh City University of Economics and Finance | 0.86 |
| VNU-HCM University of Science | VNU University of Science | Ho Chi Minh City University of Science | 0.80 |
| An Giang University - Vietnam National University Ho Chi Minh City | Vietnam National University, Ho Chi Minh City | An Giang University | 0.78 |
| Hue University of Foreign Languages and International Studies | VNU University of Languages and International Studies | Huế College of Foreign Languages | 0.67 |
| Hong Duc University | Hong Bang International University | Hồng Đức University | 0.40 |
| Lac Hong University | Hong Bang International University | Lạc Hồng University | 0.40 |
| Hue University | Vinh University | Huế University | 0.33 |
| Van Hien University | Van Xuan University of Technology | Văn Hiến University | 0.33 |
| Nong Lam University | Vinh University | Ho Chi Minh City University of Agriculture and Forestry | 0.25 |
| Quang Binh University | Vinh University | Quảng Bình University | 0.25 |
| Sports and Physical Gymnastics University II | University of Transport and Communications | Ho Chi Minh City University of Sport | 0.22 |

Kết luận: tên các trường Việt Nam có nhiều token chung (*University*, *Hanoi*, *Ho Chi Minh City*, *Technology*…), nên so khớp chuỗi với ngưỡng thấp (như θ = 0.2 trong dự án smartphone tham khảo) sinh nhiều liên kết sai; ngưỡng cao lại bỏ sót. Vì vậy dự án ưu tiên liên kết theo định danh dùng chung (QID, ROR, GeoNames), chỉ dùng so khớp nhãn (kèm xác minh quốc gia) khi không có định danh.
