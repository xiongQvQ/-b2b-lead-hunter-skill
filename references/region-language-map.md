# Region Language Map

Use this map for query language, optional Maps `gl`/`hl`, and local buyer terms. Extend only when a run needs it.

```json
{
  "United States": {"gl": "us", "hl": "en", "language": "English", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "installer"]},
  "Canada": {"gl": "ca", "hl": "en", "language": "English", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "installer"]},
  "United Kingdom": {"gl": "uk", "hl": "en", "language": "English", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "installer"]},
  "Australia": {"gl": "au", "hl": "en", "language": "English", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "installer"]},
  "Germany": {"gl": "de", "hl": "de", "language": "German", "terms": ["Importeur", "Distributor", "Großhändler", "Händler", "Vertriebspartner", "Installateur"]},
  "France": {"gl": "fr", "hl": "fr", "language": "French", "terms": ["importateur", "distributeur", "grossiste", "agent", "revendeur", "installateur"]},
  "Italy": {"gl": "it", "hl": "it", "language": "Italian", "terms": ["importatore", "distributore", "grossista", "agente", "rivenditore", "installatore"]},
  "Spain": {"gl": "es", "hl": "es", "language": "Spanish", "terms": ["importador", "distribuidor", "mayorista", "agente", "revendedor", "instalador"]},
  "Netherlands": {"gl": "nl", "hl": "nl", "language": "Dutch", "terms": ["importeur", "distributeur", "groothandel", "agent", "dealer", "installateur"]},
  "Poland": {"gl": "pl", "hl": "pl", "language": "Polish", "terms": ["importer", "dystrybutor", "hurtownik", "agent", "dealer", "instalator"]},
  "Czech Republic": {"gl": "cz", "hl": "cs", "language": "Czech", "terms": ["dovozce", "distributor", "velkoobchod", "agent", "prodejce", "instalatér"]},
  "Japan": {"gl": "jp", "hl": "ja", "language": "Japanese", "terms": ["輸入業者", "販売代理店", "卸売業者", "代理店", "販売店", "施工業者"]},
  "South Korea": {"gl": "kr", "hl": "ko", "language": "Korean", "terms": ["수입업체", "유통업체", "도매업체", "대리점", "딜러", "설치업체"]},
  "India": {"gl": "in", "hl": "en", "language": "English", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "installer"]},
  "Brazil": {"gl": "br", "hl": "pt", "language": "Portuguese", "terms": ["importador", "distribuidor", "atacadista", "agente", "revendedor", "instalador"]},
  "Mexico": {"gl": "mx", "hl": "es", "language": "Spanish", "terms": ["importador", "distribuidor", "mayorista", "agente", "revendedor", "instalador"]},
  "UAE": {"gl": "ae", "hl": "en", "language": "English/Arabic", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "supplier"]},
  "Saudi Arabia": {"gl": "sa", "hl": "ar", "language": "Arabic", "terms": ["مستورد", "موزع", "تاجر جملة", "وكيل", "مورد"]},
  "Vietnam": {"gl": "vn", "hl": "vi", "language": "Vietnamese", "terms": ["nhà nhập khẩu", "nhà phân phối", "bán buôn", "đại lý", "nhà cung cấp"]},
  "Thailand": {"gl": "th", "hl": "th", "language": "Thai", "terms": ["ผู้นำเข้า", "ผู้จัดจำหน่าย", "ค้าส่ง", "ตัวแทน", "ผู้ขาย"]},
  "Indonesia": {"gl": "id", "hl": "id", "language": "Indonesian", "terms": ["importir", "distributor", "grosir", "agen", "dealer", "pemasang"]},
  "Malaysia": {"gl": "my", "hl": "en", "language": "English/Malay", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "pembekal"]},
  "Philippines": {"gl": "ph", "hl": "en", "language": "English", "terms": ["importer", "distributor", "wholesaler", "agent", "dealer", "supplier"]}
}
```

Rule: for non-English markets, mix local-language and English queries. For Maps/local channels, bias local language.
