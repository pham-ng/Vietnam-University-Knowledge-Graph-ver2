"""Sinh các file truy vấn mẫu .rq (chạy: py queries/_generate.py). Mỗi truy vấn có dòng chú thích đầu tiên làm tiêu đề."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = """PREFIX vnedu: <https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>
"""

Q = {}

Q["01_truong_theo_tinh_moi"] = """# [Suy luận] Số cơ sở GDĐH theo 34 tỉnh/thành sau sắp xếp 2025 — trường ghi ở tỉnh cũ được tự quy về tỉnh mới
{P}
SELECT ?tinh (COUNT(DISTINCT ?u) AS ?so_co_so) (COUNT(DISTINCT ?u_tinh_cu) AS ?trong_do_ghi_o_tinh_cu)
WHERE {{
  ?u a vnedu:HigherEducationInstitution ; vnedu:locatedIn ?t .
  ?t a vnedu:Province ; rdfs:label ?tinh FILTER(LANG(?tinh) = "vi")
  OPTIONAL {{ ?u vnedu:locatedIn ?cu . ?cu vnedu:mergedInto ?t . BIND(?u AS ?u_tinh_cu) }}
}}
GROUP BY ?tinh
ORDER BY DESC(?so_co_so)
LIMIT 15
"""

Q["02_theo_mien_va_so_huu"] = """# [Suy luận] Cơ sở GDĐH theo miền và loại hình sở hữu (miền suy ra qua chuỗi locatedIn ∘ partOf)
{P}
SELECT ?mien (COUNT(DISTINCT ?u) AS ?tong) (COUNT(DISTINCT ?cl) AS ?cong_lap) (COUNT(DISTINCT ?tt) AS ?tu_thuc)
WHERE {{
  ?u a vnedu:HigherEducationInstitution ; vnedu:locatedIn ?m .
  ?m a vnedu:Region ; rdfs:label ?mien FILTER(LANG(?mien) = "vi")
  OPTIONAL {{ ?u a vnedu:PublicInstitution  BIND(?u AS ?cl) }}
  OPTIONAL {{ ?u a vnedu:PrivateInstitution BIND(?u AS ?tt) }}
}}
GROUP BY ?mien ORDER BY DESC(?tong)
"""

Q["03_truong_quan_doi_cong_an"] = """# [Suy luận] Trường quân đội & công an — phân loại tự động bằng lớp định nghĩa (governedBy ∘ subordinateTo)
{P}
SELECT ?loai ?truong (GROUP_CONCAT(DISTINCT ?cq; separator=", ") AS ?co_quan_truc_tiep)
WHERE {{
  VALUES (?c ?loai) {{ (vnedu:MilitaryInstitution "Quân đội") (vnedu:PoliceInstitution "Công an") }}
  ?u a ?c ; rdfs:label ?truong FILTER(LANG(?truong) = "vi")
  OPTIONAL {{
    ?u vnedu:governedBy ?b . ?b rdfs:label ?l FILTER(LANG(?l) = "vi")
    FILTER(?b NOT IN (vnedu:MinistryOfNationalDefence, vnedu:MinistryOfPublicSecurity))
  }}
  BIND(COALESCE(?l, "—") AS ?cq)
}}
GROUP BY ?loai ?truong ORDER BY ?loai ?truong
"""

Q["04_tra_ma_truong"] = """# Tra cứu theo mã trường tuyển sinh (VD: BKA, KHA, NTH, YHB, QHI)
{P}
SELECT ?ma ?truong ?so_huu ?tinh ?nam_tl ?web
WHERE {{
  VALUES ?ma {{ "BKA" "KHA" "NTH" "NTS" "YHB" "QHI" }}
  ?u vnedu:admissionCode ?ma ; rdfs:label ?truong FILTER(LANG(?truong) = "vi")
  OPTIONAL {{ ?u vnedu:ownership/rdfs:label ?so_huu FILTER(LANG(?so_huu) = "vi") }}
  OPTIONAL {{ ?u vnedu:locatedIn ?t . ?t a vnedu:Province ; rdfs:label ?tinh FILTER(LANG(?tinh) = "vi") }}
  OPTIONAL {{ ?u vnedu:foundingYear ?y BIND(STR(?y) AS ?nam_tl) }}
  OPTIONAL {{ ?u vnedu:website ?web }}
}}
ORDER BY ?ma
"""

Q["05_dai_hoc_va_thanh_vien"] = """# [Suy luận] Các cơ sở có đơn vị thành viên — hasMember là nghịch đảo được suy ra từ memberOf
{P}
SELECT ?co_so (COUNT(DISTINCT ?tv) AS ?so_thanh_vien) (GROUP_CONCAT(DISTINCT ?ten_tv; separator=" · ") AS ?thanh_vien)
WHERE {{
  ?dh vnedu:hasMember ?tv ; rdfs:label ?co_so .
  ?tv rdfs:label ?ten_tv .
  FILTER(LANG(?co_so) = "vi" && LANG(?ten_tv) = "vi")
}}
GROUP BY ?co_so ORDER BY DESC(?so_thanh_vien)
"""

Q["06_tinh_cu_tinh_moi"] = """# Sắp xếp đơn vị hành chính 2025 (NQ 202/2025/QH15): tỉnh mới, các tỉnh cũ hợp nhất vào, số cơ sở ghi ở tỉnh cũ
{P}
SELECT ?tinh_moi (GROUP_CONCAT(DISTINCT ?ten_cu; separator=", ") AS ?hop_nhat_tu) (COUNT(DISTINCT ?u) AS ?co_so_ghi_o_tinh_cu)
WHERE {{
  ?cu vnedu:mergedInto ?moi ; rdfs:label ?ten_cu . ?moi rdfs:label ?tinh_moi .
  FILTER(LANG(?ten_cu) = "vi" && LANG(?tinh_moi) = "vi")
  OPTIONAL {{ ?u a vnedu:EducationalOrganization ; vnedu:locatedIn ?cu }}
}}
GROUP BY ?tinh_moi ORDER BY DESC(?co_so_ghi_o_tinh_cu)
"""

Q["07_ho_so_truong"] = """# Hồ sơ đầy đủ của Đại học Bách khoa Hà Nội (mã BKA) — gồm thông tin suy luận và liên kết ra ngoài
{P}
SELECT ?thuoc_tinh (GROUP_CONCAT(DISTINCT ?v; separator=" | ") AS ?gia_tri)
WHERE {{
  ?u vnedu:admissionCode "BKA" ; ?p ?o .
  FILTER(?p NOT IN (vnedu:hasAlumnus, <https://schema.org/alumni>))
  OPTIONAL {{ ?o rdfs:label ?ol FILTER(LANG(?ol) = "vi") }}
  BIND(COALESCE(?ol, STR(?o)) AS ?v)
  BIND(REPLACE(STR(?p), "^.*[#/]", "") AS ?thuoc_tinh)
}}
GROUP BY ?thuoc_tinh ORDER BY ?thuoc_tinh
"""

Q["08_dao_tao_nganh"] = """# [Suy luận] Trường đào tạo ngành Công nghệ thông tin (trainsMajor = offersProgram ∘ ofMajor; chương trình là dữ liệu mẫu)
{P}
SELECT ?mien ?tinh ?truong
WHERE {{
  ?u vnedu:trainsMajor ?n . ?n vnedu:code "7480201" .
  ?u rdfs:label ?truong FILTER(LANG(?truong) = "vi")
  OPTIONAL {{ ?u vnedu:locatedIn ?t . ?t a vnedu:Province ; rdfs:label ?tinh FILTER(LANG(?tinh) = "vi") }}
  OPTIONAL {{ ?u vnedu:locatedIn ?m . ?m a vnedu:Region ; rdfs:label ?mien FILTER(LANG(?mien) = "vi") }}
}}
ORDER BY ?mien ?truong
"""

Q["09_cuu_sinh_vien"] = """# [Suy luận] Trường có nhiều cựu sinh viên nổi tiếng nhất (lớp Alumnus suy ra từ alumnusOf)
{P}
SELECT ?truong (COUNT(DISTINCT ?p) AS ?so_cuu_sv) (COUNT(DISTINCT ?ck) AS ?chinh_khach)
WHERE {{
  ?p a vnedu:Alumnus ; vnedu:alumnusOf ?u .
  ?u rdfs:label ?truong FILTER(LANG(?truong) = "vi")
  OPTIONAL {{ ?p <https://schema.org/hasOccupation> <http://www.wikidata.org/entity/Q82955> BIND(?p AS ?ck) }}
}}
GROUP BY ?truong ORDER BY DESC(?so_cuu_sv) LIMIT 12
"""

Q["10_lanh_dao"] = """# [Suy luận] Người đứng đầu các đại học quốc gia & vùng (rector/director ⊑ hasLeader, nghịch đảo leads)
{P}
SELECT ?co_so ?vai_tro ?nguoi ?hoc_ham
WHERE {{
  VALUES ?c {{ vnedu:NationalUniversity vnedu:RegionalUniversity }}
  ?u a ?c ; rdfs:label ?co_so ; ?r ?p .
  VALUES (?r ?vai_tro) {{ (vnedu:rector "Hiệu trưởng") (vnedu:director "Giám đốc") }}
  ?p a vnedu:InstitutionLeader ; rdfs:label ?nguoi .
  FILTER(LANG(?co_so) = "vi")
  OPTIONAL {{ ?p vnedu:honorific ?hoc_ham }}
}}
ORDER BY ?co_so
"""

Q["11_lien_ket_5_sao"] = """# Thống kê liên kết ra các dataset bên ngoài (tiêu chí 5 sao)
{P}PREFIX foaf:  <http://xmlns.com/foaf/0.1/>

SELECT ?dataset ?vi_tu (COUNT(*) AS ?so_lien_ket)
WHERE {{
  VALUES ?p {{ owl:sameAs skos:closeMatch foaf:isPrimaryTopicOf }}
  ?s ?p ?o . FILTER(STRSTARTS(STR(?s), "https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/resource/"))
  BIND(REPLACE(STR(?p), "^.*[#/]", "") AS ?vi_tu)
  BIND(IF(CONTAINS(STR(?o), "wikidata.org"), "Wikidata", IF(CONTAINS(STR(?o), "dbpedia.org"), "DBpedia",
       IF(CONTAINS(STR(?o), "geonames.org"), "GeoNames", IF(CONTAINS(STR(?o), "ror.org"), "ROR",
       IF(CONTAINS(STR(?o), "wikipedia.org"), "Wikipedia", "khác"))))) AS ?dataset)
}}
GROUP BY ?dataset ?vi_tu ORDER BY DESC(?so_lien_ket)
"""

Q["12_federated_wikidata"] = """# TRUY VẤN LIÊN KẾT (federated): theo owl:sameAs sang Wikidata lấy diện tích tỉnh, tính mật độ cơ sở GDĐH. Cần Internet.
{P}PREFIX wdt:   <http://www.wikidata.org/prop/direct/>

SELECT ?tinh ?so_co_so ?dien_tich_km2 ?co_so_tren_1000km2
WHERE {{
  {{
    SELECT ?wd ?tinh (COUNT(DISTINCT ?u) AS ?so_co_so) WHERE {{
      ?u a vnedu:HigherEducationInstitution ; vnedu:locatedIn ?t .
      ?t a vnedu:Province ; rdfs:label ?tinh ; owl:sameAs ?wd .
      FILTER(LANG(?tinh) = "vi" && STRSTARTS(STR(?wd), "http://www.wikidata.org/entity/"))
    }} GROUP BY ?wd ?tinh ORDER BY DESC(?so_co_so) LIMIT 6
  }}
  # OPTIONAL {{ SERVICE … }}: engine gửi từng ?wd đã biết sang Wikidata (bind join)
  OPTIONAL {{ SERVICE <https://query.wikidata.org/sparql> {{ ?wd wdt:P2046 ?dien_tich_km2 }} }}
  BIND(ROUND(100000 * ?so_co_so / ?dien_tich_km2) / 100 AS ?co_so_tren_1000km2)
}}
ORDER BY DESC(?so_co_so)
"""

Q["13_federated_dbpedia"] = """# TRUY VẤN LIÊN KẾT (federated): theo owl:sameAs sang DBpedia lấy ảnh, khẩu hiệu, số SV. Cần Internet.
{P}PREFIX dbo:   <http://dbpedia.org/ontology/>

SELECT ?truong ?dbp ?anh ?khau_hieu ?so_sv_dbpedia
WHERE {{
  {{
    SELECT ?dbp WHERE {{
      VALUES ?ma {{ "BKA" "KHA" "NTH" "YHB" }}
      ?u vnedu:admissionCode ?ma ; owl:sameAs ?dbp .
      FILTER(STRSTARTS(STR(?dbp), "http://dbpedia.org/resource/"))
    }}
  }}
  OPTIONAL {{ SERVICE <https://dbpedia.org/sparql> {{
    ?dbp rdfs:label ?ten_en FILTER(LANG(?ten_en) = "en")   # mẫu bắt buộc chứa ?dbp -> engine thay biến (bind join)
    OPTIONAL {{ ?dbp dbo:thumbnail ?anh }}
    OPTIONAL {{ ?dbp dbo:motto ?khau_hieu }}
    OPTIONAL {{ ?dbp dbo:numberOfStudents ?so_sv_dbpedia }}
  }} }}
  ?u owl:sameAs ?dbp ; rdfs:label ?truong .
  FILTER(LANG(?truong) = "vi")
}}
"""

Q["14_nganh_theo_linh_vuc"] = """# Danh mục ngành theo lĩnh vực (TT 09/2022/TT-BGDĐT) và liên kết skos:closeMatch sang Wikidata
{P}
SELECT ?ma_lv ?linh_vuc ?ma_nganh ?nganh ?wikidata
WHERE {{
  ?n a vnedu:Major ; vnedu:code ?ma_nganh ; skos:prefLabel ?nganh ; vnedu:inField ?f .
  ?f vnedu:code ?ma_lv ; skos:prefLabel ?linh_vuc .
  FILTER(LANG(?nganh) = "vi" && LANG(?linh_vuc) = "vi")
  OPTIONAL {{ ?n skos:closeMatch ?wikidata FILTER(STRSTARTS(STR(?wikidata), "http://www.wikidata.org/")) }}
}}
ORDER BY ?ma_nganh
"""

Q["15_chat_luong_du_lieu"] = """# Chất lượng dữ liệu: tỉ lệ cơ sở GDĐH có từng thuộc tính
{P}
SELECT ?thuoc_tinh ?so_co_so ?tong ((ROUND(1000 * ?so_co_so / ?tong) / 10) AS ?phan_tram)
WHERE {{
  {{ SELECT (COUNT(?x) AS ?tong) WHERE {{ ?x a vnedu:HigherEducationInstitution }} }}
  {{
    SELECT ?thuoc_tinh (COUNT(DISTINCT ?u) AS ?so_co_so) WHERE {{
      VALUES (?p ?thuoc_tinh) {{
        (vnedu:foundingYear "năm thành lập") (vnedu:ownership "loại hình sở hữu") (vnedu:locatedIn "tỉnh/thành")
        (vnedu:website "website") (vnedu:hasLeader "lãnh đạo") (vnedu:admissionCode "mã trường")
        (owl:sameAs "liên kết ngoài") (<http://www.w3.org/2003/01/geo/wgs84_pos#lat> "toạ độ")
        (vnedu:motto "khẩu hiệu") (vnedu:shortName "tên viết tắt")
      }}
      ?u a vnedu:HigherEducationInstitution ; ?p ?o .
    }} GROUP BY ?thuoc_tinh
  }}
}}
ORDER BY DESC(?so_co_so)
"""

for name, body in Q.items():
    (HERE / f"{name}.rq").write_text(body.format(P=P), encoding="utf-8")
print(f"{len(Q)} truy vấn")
