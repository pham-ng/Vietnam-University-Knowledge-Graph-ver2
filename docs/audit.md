# Đánh giá trung thực VN-Edu 2.0 (so với repo `Vietnam-University-Knowledge-Graph`)

Mọi con số dưới đây đều do script đo được và chạy lại được:
[`audit/old_repo_stats.py`](../audit/old_repo_stats.py), [`audit/benchmark.py`](../audit/benchmark.py),
[`audit/check_links.py`](../audit/check_links.py), [`audit/check_rdf.py`](../audit/check_rdf.py),
[`scripts/eval_linking.py`](../scripts/eval_linking.py).

## 1. So với repo cũ

| Tiêu chí | Repo cũ (`vio`) | VN-Edu 2.0 |
|---|---|---|
| Triple | 9.649 | 39.507 (20.446 khẳng định + 3.674 liên kết + 14.666 suy luận) |
| Thực thể "trường" | 327, gắn kiểu `University` cho cả bệnh viện (Bệnh viện Quân y 103), ký túc xá, dự án khu đô thị, trường trung học, thậm chí một chính khách (Trường Chinh) | 300, phân theo loại hình pháp lý; 68 thực thể bị loại có ghi lý do |
| **Nhất quán logic** khi suy luận OWL 2 RL | **349 mâu thuẫn** (344 `Site ⊥ Place` do `geo:lat rdfs:domain Site`; 5 trường có 2 năm thành lập) | **0** (có test tự động) |
| Câu hỏi có đáp án chuẩn (năm thành lập, trụ sở, chủ quản) | **13/21** (ĐH Luật HN "1727", HV Hải quân "2022", ĐH An Giang "1976", ĐH Thủ Dầu Một ở "Bình Phước") | **21/21** |
| Câu hỏi tổng hợp/so sánh: công lập vs tư thục, theo miền, sau sáp nhập tỉnh, đã giải thể, theo mã tuyển sinh | không biểu diễn được (thiếu khái niệm) | trả lời được |
| Thành viên ĐHQG HN | 62 (sai) | 12 |
| Liên kết ngoài | 305, chỉ Wikidata | 1.880 Wikidata · 260 DBpedia · 195 ROR · 63 GeoNames · 1.188 Wikipedia |
| Kiểm định | không | JSON Schema (silver) + SHACL + kiểm tra nhất quán + 46 test |

**Những điểm repo cũ làm tốt hơn** (nói thật):
- Toạ độ: 344 so với 106. Nhưng 240/344 là "Approximate" (xấp xỉ), chỉ 104 là "Exact".
- Số sinh viên: 96 so với 57; số giảng viên: 76 so với 33.
- Mô hình *Site* (nhiều cơ sở của một trường) là ý tưởng hay, dù cài đặt sai.

## 2. Câu hỏi phức tạp

Các câu đã chạy được và cho kết quả hợp lý ([`data/reports/benchmark.md`](../data/reports/benchmark.md)):
- **tổng hợp**: công lập 221 / tư thục 35; theo miền; theo 34 tỉnh mới;
- **so sánh**: năm thành lập trung bình công lập 1972, tư thục 1999;
- **lớn nhất/nhỏ nhất theo nhóm**: cơ sở lâu đời nhất mỗi miền;
- **nhiều bước**: cựu sinh viên là chính khách của các trường thuộc ĐHQG HN;
- **federated**: sang Wikidata và DBpedia.

Lưu ý kỹ thuật: rdflib **không so sánh được `xsd:gYear`**, nên truy vấn có phép so sánh năm phải ép kiểu
`xsd:integer(STR(?y))`. Jena/Fuseki thì so sánh được trực tiếp.

## 3. Bộ ba RDF có chuẩn mực không?

[`audit/check_rdf.py`](../audit/check_rdf.py) cho kết quả:
- 0 literal sai kiểu, 0 IRI lỗi, 0 thẻ ngôn ngữ sai, 0 blank node trong dữ liệu;
- mọi thực thể có `rdfs:label` và `rdf:type`;
- mọi thuộc tính và lớp đều được khai báo trong ontology;
- 0 đích `sameAs` trùng (đã sửa một ca do DBpedia sai).

Còn chưa tối ưu: nghề nghiệp (`occupation`) và giới tính đang là chuỗi, chưa phải IRI trỏ tới Wikidata.

## 4. Quan hệ dựa trên cơ sở nào, chính xác đến đâu?

| Quan hệ | Cơ sở | Độ tin cậy |
|---|---|---|
| `locatedIn` | infobox, rồi Wikidata P131, rồi văn bản; sáp nhập theo NQ 202/2025/QH15 | cao; mâu thuẫn ghi trong `conflicts.csv` |
| `memberOf` | Wikidata P749/P361 + infobox "thành viên của", **chỉ nhận khi đích là cơ sở có trong dataset** | cao |
| `governedBy` | infobox + Wikidata; dự phòng bằng cụm "trực thuộc …" trong đoạn mở đầu, chuẩn hoá theo danh sách Bộ chính thức | khá; 2 trường tư thục có "Bộ GD&ĐT" (SHACL cảnh báo) |
| `ownership` | infobox "hệ / loại hình" + Wikidata; dự phòng bằng văn bản (regex chặt) | khá; 35/271 không xác định |
| lãnh đạo | Wikidata (bỏ người đã hết nhiệm kỳ) + infobox | trung bình: infobox có thể chưa cập nhật; gộp người theo tên nên có thể nhầm người trùng tên |
| năm thành lập | năm sớm nhất giữa các nguồn (tính từ tiền thân) | là **một quy ước**: ví dụ ĐH Điện lực 1898 là năm tiền thân mà trường công bố |

## 5. Liên kết ngoài có hợp lệ, người ngoài có dùng được không?

[`audit/check_links.py`](../audit/check_links.py) lấy ngẫu nhiên 30 liên kết mỗi loại:
- **150/150 tra cứu được** (HTTP 200);
- Wikidata, DBpedia và GeoNames **trả RDF** khi xin `text/turtle`/RDF;
- ROR 30/30 đúng tổ chức ở Việt Nam;
- Wikidata 29/30 khớp nhãn. Ca còn lại vẫn đúng thực thể, chỉ là nhãn bên Wikidata là tên cũ.

Xác minh chéo DBpedia đã loại 14 liên kết mơ hồ, ví dụ `dbr:Pleiku` bị DBpedia gắn nhầm vào tỉnh Gia Lai.

## 6. Thang 5 sao — đánh giá nghiêm khắc

| Sao | Yêu cầu | Trạng thái |
|---|---|---|
| ★ | **Có trên Web** + giấy phép mở | ✅ **Đã khắc phục**: công bố tại https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ (GitHub Pages), giấy phép CC BY-SA 4.0 (`LICENSE-DATA.md`, VoID/DCAT, `*.meta.json`). *Trước đó: chỉ nằm trên máy cục bộ — chưa đạt.* |
| ★★ ★★★ | Có cấu trúc, định dạng mở | ✅ JSON/CSV/Turtle |
| ★★★★ | Chuẩn W3C + **URI để người khác trỏ tới** | ✅ **Đã khắc phục**: URI gốc đổi từ `http://localhost:8000/` sang `https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/`; 2.241 URI tra cứu được (HTML + JSON-LD nhúng, `.ttl`, `.jsonld`). Repo cũ dùng `http://vi.dbpedia.org/…` — tên miền không thuộc quyền mình — nên không đạt. |
| ★★★★★ | Liên kết tới dataset khác | ✅ hợp lệ và đã kiểm chứng |

**Kết luận (cập nhật): sau bước 7, dataset đạt đủ 5 sao** — có trên Web, giấy phép mở, URI công khai cố định tra cứu
được, chuẩn W3C, liên kết ra ngoài đã kiểm chứng. Nâng cấp tuỳ chọn: đăng ký `https://w3id.org/vnedu/` để có
content negotiation phía máy chủ (GitHub Pages là hosting tĩnh).

## 7. Hạn chế còn lại

1. Bản công khai không có SPARQL endpoint HTTP (dùng SPARQL trong trình duyệt; Fuseki chạy cục bộ) và không có content negotiation phía máy chủ.
2. **Độ phủ**:
   - Chỉ dựa trên Wikidata và Wikipedia, chưa có danh sách chính thức của Bộ GD&ĐT nên không chứng minh được là đầy đủ.
   - Số trường tư thục nhận ra được (35) nhiều khả năng **thấp hơn thực tế** (theo thống kê của Bộ, khoảng 1/4 số cơ sở
     GDĐH là ngoài công lập; con số này nên được đối chiếu lại).
   - 35 cơ sở chưa rõ loại hình sở hữu; 12 thiếu tỉnh, 22 thiếu năm thành lập.
3. **Số liệu quy mô thưa**: số sinh viên chỉ có ở 57/271 cơ sở, giảng viên 33, toạ độ 106, mã trường tuyển sinh 60.
4. **Ngành và chương trình đào tạo là dữ liệu mẫu nhập tay**: 37 ngành và 78 chương trình, trong khi danh mục TT 09/2022
   có hàng trăm ngành. Truy vấn "trường nào đào tạo ngành X" vì vậy **chưa đáng tin cho thống kê**.
5. **Chưa mô hình hoá thời gian**:
   - lãnh đạo không có nhiệm kỳ;
   - số sinh viên không kèm năm thống kê trong RDF;
   - đổi tên và sáp nhập trường chỉ có dạng `formerName`.
6. **Nguồn cộng đồng biên tập**: lãnh đạo và quy mô có thể đã cũ. Mỗi giá trị truy được về bản sửa đổi gốc, nhưng chưa có
   đợt kiểm tra thủ công độc lập (nên lấy mẫu khoảng 50 trường để đối chiếu với website của trường hoặc của Bộ cho báo cáo).
7. **Benchmark nhỏ**: 21 sự kiện có đáp án chuẩn, chọn theo những trường nổi tiếng. Đây là bằng chứng định tính, chưa phải
   phép đo độ chính xác trên toàn bộ dataset.
8. **Phụ thuộc dịch vụ ngoài**: truy vấn federated phụ thuộc Wikidata/DBpedia còn hoạt động; thu thập lại phụ thuộc giới hạn
   tốc độ của Wikimedia (có cache để giảm rủi ro).
