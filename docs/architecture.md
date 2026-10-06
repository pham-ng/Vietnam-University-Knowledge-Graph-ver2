# Kiến trúc dữ liệu (Medallion)

```mermaid
flowchart LR
  subgraph SRC[Nguồn mở]
    WD[(Wikidata<br/>SPARQL)]
    VW[(Wikipedia tiếng Việt<br/>MediaWiki API)]
    DBP[(DBpedia<br/>SPARQL)]
    OSM[(OpenStreetMap<br/>Nominatim)]
    REF[/Văn bản pháp lý<br/>NQ 202/2025, TT 09/2022/]
  end
  subgraph BRONZE[🟫 BRONZE — dữ liệu gốc, bất biến]
    CACHE[http_cache/<br/>mọi phản hồi HTTP]
    RAW[wd_*.json · viwiki_pages.json<br/>dbp_years.json + .meta.json]
  end
  subgraph SILVER[⬜ SILVER — tích hợp, làm sạch, kiểm định]
    INT[institutions · governing_bodies<br/>people · provinces .json]
    JS{{JSON Schema<br/>hợp đồng dữ liệu}}
    REP1[reports: conflicts · filled<br/>excluded · unresolved]
  end
  subgraph GOLD[🟨 GOLD — Linked Data 5★]
    DATA[vnedu-data.ttl]
    LINKS[vnedu-links.ttl<br/>+ void.ttl]
    INF[vnedu-inferred.ttl<br/>OWL 2 RL]
    ALL[vnedu-all.ttl]
    SH{{SHACL + kiểm tra<br/>nhất quán}}
  end
  ONTO[[ontology/vnedu.ttl]]
  WD & VW & DBP & OSM --> CACHE --> RAW
  REF --> INT
  RAW -->|B3a tích hợp & đối chiếu| INT --> JS
  INT --> REP1
  JS -->|đạt| DATA
  ONTO --> DATA
  DATA -->|B4 liên kết| LINKS
  DATA & ONTO -->|B5 suy luận| INF
  DATA & LINKS & INF & ONTO --> ALL --> SH
  ALL --> FUS[(Apache Jena Fuseki<br/>SPARQL endpoint)]
  ALL --> WEB[Web: tra cứu URI,<br/>content negotiation, YASGUI]
  ALL --> CLI[Terminal: query.py]
  FUS -. federated SERVICE .-> WD & DBP
```

| Tầng | Thư mục | Nội dung | Kiểm soát chất lượng |
|---|---|---|---|
| Bronze | `data/bronze/` | Phản hồi API (cache) + ảnh chụp JSON theo nguồn, kèm `.meta.json` | Tái tạo từ cache; các tệp snapshot được ghi lại, lịch sử do Git lưu |
| Silver | `data/silver/` | Thực thể đã nhận diện, hợp nhất, chuẩn hoá; một bản ghi / thực thể | **JSON Schema** (`schemas/silver.schema.json`), báo cáo mâu thuẫn / giá trị dự phòng / loại bỏ |
| Gold | `data/gold/` | RDF theo ontology, liên kết 5★, suy luận, VoID/DCAT | **SHACL**, kiểm tra nhất quán OWL, kiểm thử suy luận |

`data/manifest.json` ghi lại dòng dõi dữ liệu (lineage): mỗi tệp của mỗi tầng, số bản ghi/triple, SHA-256, thời điểm tạo.
