# Chiến lược URI: khi nào tái sử dụng, khi nào tạo mới?

> Câu hỏi: *"Sao không dùng lại các URI đã có mà lại tạo mới?"*

**Trả lời ngắn:** dự án **tái sử dụng ở mọi chỗ có thể**: từ vựng, thuộc tính, và những giá trị mà ta không mô tả thêm.
Dự án **chỉ tạo URI mới cho những thực thể mà nó tự công bố dữ kiện**, rồi dùng `owl:sameAs` để khẳng định đó cùng là
một thực thể với URI đã có trên Wikidata, DBpedia, ROR, GeoNames. Đây chính là khuyến nghị của W3C trong *Best Practices
for Publishing Linked Data* và *Linked Data Patterns*: "re-use vocabularies", "mint URIs for your own resources and link
them with owl:sameAs".

## 1. Những gì được TÁI SỬ DỤNG (đo trên `data/gold/vnedu-data.ttl`)

| Mức | Tái sử dụng | Số liệu |
|---|---|---|
| Từ vựng (thuộc tính) | `rdfs:label`, `schema:hasOccupation`, `schema:gender`, `prov:wasDerivedFrom`, `foaf:name`, `geo:lat/long`, `skos:prefLabel`… | **72%** số triple dùng thuộc tính của từ vựng chuẩn (12.923/17.940) |
| Lớp | Mọi lớp `vnedu:` đều được căn chỉnh `rdfs:subClassOf` sang `schema:`, `foaf:`, `dbo:` | 76 tiên đề căn chỉnh; sau suy luận mỗi cơ sở cũng có kiểu `schema:CollegeOrUniversity`, `dbo:University`… |
| **Giá trị** | Nghề nghiệp, giới tính: dùng **thẳng URI Wikidata** (`wd:Q82955` = politician, `wd:Q6581097` = male) | **217 URI Wikidata** được dùng lại làm giá trị trong 2.518 triple; **không** tạo `vnedu:occupation/…` |
| Danh mục pháp lý | Cá thể `vnedu:MinistryOfNationalDefence` có `owl:sameAs wd:Q6866771` | — |

## 2. Những gì được TẠO MỚI và vì sao

2.211 URI mới gồm: 300 cơ sở, 63 tỉnh, 1.668 người, 45 cơ quan, 37 ngành, 78 chương trình, 16 lĩnh vực, 3 miền, 1 quốc gia.
**1.874 trong số đó (85%) có `owl:sameAs`** tới URI đã có. Lý do không ghi thẳng dữ kiện lên URI của Wikidata:

1. **Nguyên tắc Linked Data số 3**: tra cứu một URI phải trả về thông tin hữu ích *từ người công bố*. Ta không điều
   khiển được `http://www.wikidata.org/entity/Q3075696` trả gì; dữ kiện riêng của ta (mã tuyển sinh BKA, loại hình pháp
   lý, tỉnh sau sáp nhập 2025, kết quả suy luận) chỉ tra cứu được qua URI của ta.
2. **Dữ kiện khác nguồn**: ta có quy ước riêng (năm thành lập tính từ tiền thân, loại hình theo Luật GDĐH), và có cả kết
   quả đối chiếu chéo. Ghi chúng lên URI Wikidata sẽ trộn lẫn nguồn gốc (provenance) của hai dataset.
3. **Có thực thể Wikidata không có**: ngành theo mã TT 09/2022, quan hệ tỉnh cũ → tỉnh mới 2025, lãnh đạo lấy từ
   infobox, chương trình đào tạo, cơ sở chỉ có bài viwiki. Với các thực thể này, bắt buộc phải tạo URI mới.
4. **Ổn định và trách nhiệm**: URI của ta nằm dưới không gian tên ta quản lý (`https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/`),
   nên cam kết được việc tra cứu luôn hoạt động.
5. **Đồng nhất không hoàn toàn**: ngành đào tạo ≠ ngành khoa học, nên dùng `skos:closeMatch` chứ không phải
   `owl:sameAs`. Nếu dùng chung URI thì không diễn đạt được sắc thái này.

## 3. `owl:sameAs` được dùng thế nào ("trỏ về cùng một thực thể")

| Đích | Số liên kết | Cách đảm bảo đúng |
|---|---|---|
| Wikidata | 1.878 | theo nguồn gốc dữ liệu; cơ quan và miền thì tìm theo nhãn **và xác minh `P17 = Việt Nam`** |
| DBpedia | 258 | lấy từ `owl:sameAs` của DBpedia, **loại 14 ca DBpedia trỏ một tài nguyên tới nhiều item** (ví dụ `dbr:Pleiku` → tỉnh Gia Lai) |
| ROR | 195 | mã P6782 của Wikidata; kiểm tra mẫu 30/30 đúng tổ chức ở Việt Nam |
| GeoNames | 63 | mã P1566 của Wikidata |

- **Gộp thực thể trùng trong chính dataset**: 3 cặp item Wikidata trùng nhau (ví dụ *Hanoi Law University* có 2 QID) được
  gộp về **một** URI của ta, kèm `owl:sameAs` tới **cả hai** QID.
- **Tận dụng `sameAs` khi truy vấn** (smushing): truy vấn
  [12](../queries/12_federated_wikidata.rq)/[13](../queries/13_federated_dbpedia.rq) đi theo `owl:sameAs` sang
  Wikidata/DBpedia để lấy diện tích tỉnh, ảnh, khẩu hiệu, những dữ kiện **ta không lưu**. Đó chính là lợi ích của việc
  "trỏ về cùng một thực thể".
- **Vì sao không đưa `owl:sameAs` vào bộ suy luận**: ngữ nghĩa của `owl:sameAs` sẽ chép **mọi** triple sang URI
  Wikidata/DBpedia, làm dữ liệu phình gấp nhiều lần và trộn lẫn nguồn gốc. Ta để bên dùng dữ liệu quyết định khi nào gộp.

## 4. So với repo cũ

Repo cũ cũng tạo URI riêng và dùng `owl:sameAs` (305 liên kết, chỉ tới Wikidata), nhưng:
- URI nằm dưới `http://vi.dbpedia.org/resource/`, **một tên miền không thuộc quyền dự án**, nên không ai tra cứu được.
  Đây là "chiếm dụng" không gian tên của DBpedia tiếng Việt.
- Định nghĩa `vio:wikidataEntity rdfs:subPropertyOf owl:sameAs` là không hợp lệ trong OWL DL.
- Nghề nghiệp, giới tính, chức danh lưu dạng chuỗi, tức không tái sử dụng URI có sẵn.
