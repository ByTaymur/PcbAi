# Plan — referans depolarla geliştirme (RD)

Tarih: 13 Ekim 2026 · Durum: **plan v1; dalga 0 ölçüldü ve denetlendi, K15/K16-1/K20/K21 kabul ([0004](decisions/0004-referans-depolar.md)); dalga 1 D1-1…D1-7 uygulandı ([tarif](plan-rd-dalga1.md)); son ölçüm [status.md](status.md)** · Bağlı: [PLAN.md](../PLAN.md), [plan-eksikler.md](plan-eksikler.md),
[status.md](status.md), [tools.md](tools.md)

Bu belge sekiz referans depodan (bölüm 1) ve KiCad ekosistemindeki başka projelerden (bölüm 1.1) PcbAi'ye
**neyin, hangi yolla, hangi fazda** alınacağını ve her işin ne zaman "bitti" sayılacağını söyler. PLAN.md'nin yerine geçmez. PLAN'daki iş paketlerini (İP) besler, bazılarının içini
doldurur. Bu durum her paketin "PLAN bağı" satırında yazar. Uygulayan ajan her paketi bitirince ölçülen sonucu
status.md'ye yazar ve buradaki kutuyu işaretler.

---

## 0. Özet

- **Ne değişir:** PcbAi bugün KiCad'in kendi denetimlerini (ERC/DRC/parite) güvenli biçimde çalıştırıyor ve dosyaya
  ölçerek yazıyor. Eksik olan, **devrenin kendisini anlayan denetim katmanı**: dekuplaj, güç ağacı, datasheet
  sınırları, termal, EMC, şematik↔kart çapraz kontrolü, üretim çıktısının **üreten araçtan bağımsız** doğrulanması.
  Referans depolar bu katmanın büyük kısmını çözmüş durumda.
- **Ana kaynak:** `aklofas/kicad-happy` (MIT). 74 bin satır saf Python, 60+ dedektör, EMC, termal, SPICE, fab kapısı,
  datasheet güven kapısı. KiCad 10 dosyalarını okuyor. `Zane456/PCB-Agent-Teams` kendi kontrol kapılarında zaten
  bunu çağırıyor; alanda fiilî standart haline gelmiş.
- **İkinci kaynaklar:**
  - **pcb-skill** (MIT): bağımsız Gerber doğrulama ve karşıt inceleme protokolü. Gerçek bir kartta yakalanmış
    9 hatayı da belgeliyor.
  - **eda-agent** (Apache-2.0): şematik okunurluk ölçütleri, IPC-7351 footprint denetimi, araç yüzeyi tasarımı,
    ölçülen kapılı otonom döngü.
  - **easyeda-agent** (MIT): tipli eylemler, yazma sonrası geri okuma.
- **İlke korunur:** Bulgu, ölçüm ve kanıt kaydı olmadan rapor yok. Dış analiz motoru da **önce KiCad'in kendi
  sayılarını yeniden üretmek** zorunda; üretemiyorsa bulgusu kart hakkında değil motor hakkındadır.
- **Kazanç:** v0.3'te şematik denetim raporu; v0.6'da bağımsız doğrulanmış üretim paketi; v0.8'de her kapının ölçülen
  sayıyla geçtiği `design_board`. B1 (uydurma parça/pin = 0) ve B3 (her sayı kanıtlı) ölçütleri ilk kez otomatik
  ölçülebilir hale gelir.
- **Ekosistem araçları (bölüm 4.I):** KiKit (panel), InteractiveHtmlBom (montaj görünümü), KiRI (görsel fark),
  pygerber (ikinci Gerber ayrıştırıcısı), KiCad'in resmî KLC denetçisi, pyplacer (yerleşim kıyas tabanı),
  kicad-sch-api (bağımsız yazıcı kıyası) ve küçük ama doğrudan işe yarayan fikirler (yanıt grounding kapısı,
  çıkış kodu sözleşmesi).
- **Süre:** RD-A…H paketlerinin bir kısmı PLAN'daki İP'lerin yerine geçer (İP-2.7, 5.3, 5.11, 7.1'in içi); net ek
  yük **3–4 hafta**. Ekosistem paketleri (RD-I) yaklaşık **6 hafta-ajan** ekler; bunun yaklaşık 2 haftası kesilebilir
  (bölüm 6). Toplam, PLAN'ın 12. ve 29–30. hafta tamponlarını aşar. Bu yüzden RD-I'nin kesilebilir kısmı varsayılan
  olarak "zaman kalırsa" sayılır (K20).

---

## 1. İncelenen depolar: kaynak kodda ne var?

Klonlar 13 Ekim 2026'da `--depth 1` ile alındı ve yalnızca okundu, hiçbir şey çalıştırılmadı. "Kaynakta" yazan
satırlar dosyadan doğrulandı. "README" yazanlar deponun kendi iddiasıdır.

| Depo (son commit) | Lisans | Kaynakta doğrulanan | PcbAi'de kullanım |
|---|---|---|---|
| **aklofas/kicad-happy** (5 Eki 2026) | MIT | `analyze_schematic` (10,4k satır), `analyze_pcb` (7,5k), `domain_detectors`/`signal_detectors`/`validation_detectors` (60+ `detect_*`/`audit_*`), `emc_rules` (4,5k), `analyze_thermal`, `cross_verify`, `cross_analysis`, `fab_release_gate` (pass/warn/fail/skip), `diff_analysis`, `what_if`, `finding_schema` (kararlı `finding_id`, `deterministic/heuristic/datasheet-backed`), `datasheet_types/trust_gating` (`min_confidence` zorunlu), `datasheet_score`, `spice_tolerance`, `extract_parasitics`, `translate_bom_pnp`, `deep_review_gate` (kanıtsız bulgu karantinaya). KiCad 10 ad tabanlı netleri belgelenmiş. Kendi s-expr ayrıştırıcısı ve bağlantı modeli var | **Ana analiz motoru** (RD-B). Önce ayrı süreç, sonra seçilen modüller atıfla |
| **salitronic/eda-agent** (12 Eki 2026) | Apache-2.0 | `schematic_layout` (Sugiyama, ızgara, tel/etiket/güç portu kararı), `schematic_neatness` + `quality` (11 ölçüt, ağırlıklar ölçüme dayalı), `motifs` (VF2 alt çizge), `landpattern/ipc7351` + `audit` (kaynaklı IPC-7351B sayıları; aynalı footprint = kusur), `klc` (KiCad sembol kuralları), `value_checks` (kristal yük C'leri eşit mi), `rule_synthesis`/`trace_sizing` (her sayının kaynağı assert'li), `autonomy` (`MEASURED_GATES`), `tools/registry` (`minimal`: `tool_catalog`+`tool_invoke`), `bulk_hints`, `review` (`design_review_snapshot`) | Şematik okunurluk, footprint denetimi, araç yüzeyi (RD-E, RD-D6, RD-F). **Kod alma K15'e bağlı** |
| **daishuge/pcb-skill** (10 Eyl 2026) | MIT | `scripts/verify/` (RS-274X/Excellon okuyucu, `outline_check`, `drill_census`, `mask_check`, `clearance`, `pad_reconcile`, `netlist_assert`, `mesh3d`; her biri `--selftest`). `02-review.md` karşıt inceleme protokolü. `case-study.md`: gerçek kartta yakalanan 9 hata | Bağımsız üretim doğrulaması (RD-C2), inceleme protokolü (RD-F4), hata kataloğu (RD-G2) |
| **zhoushoujianwork/easyeda-agent** (11 Eki 2026) | MIT (+ bir alt klasör Apache-2.0) | Tipli eylemler, "ekran görüntüsü tipli geri okumanın yerine geçmez" kuralı, `library/modules/*.topology.json` (blok benzeri modüller), `fab-rules-jlcpcb.json`, SHA-256 doğrulamalı kurulum | Yazma sonrası geri okuma (RD-A3), DFM profili verisi, skill dağıtımı (RD-H1) |
| **Shaurya-Sethi/circuitron** (arşivlenmiş) | MIT | Plan → onay → SKiDL → ERC döngüsü; kütüphaneye karşı uydurma-API kontrolü. Yazar artık "kodlama ajanı + kaynak indeksi" öneriyor | PcbAi'de büyük ölçüde **zaten var** (`plan_circuit` gerçek sembol/pin karması). Ek iş yok, yalnızca RD-G1'de IR hata örnekleri |
| **autonomous-ai/openharness** (13 Eki 2026) | MIT | Ajanı sarmalamadan, transcript ve hook okuyarak çoklu ajan yönetimi; oturum başına worktree; `harness.json` alan paketi | İki ajanlı düzen için yardımcı (RD-H3), yalnızca spike |
| **Zane456/PCB-Agent-Teams** (27 Tem 2026) | **PolyForm NC** | 10 skill, aşama kapıları, `.bom_readiness.json` nöbetçi dosyası, MPN yalnız distribütör API'sinden. Kontrol kapıları kicad-happy analizörlerini çağırıyor | **Yalnızca fikir.** Kod, metin, şema ve şablon alınmaz |
| **assalas/pcb-designer-ai-agent** (3 Eki 2026) | **Özel, ticari yasak** | Gereksinim → BOM → netlist → footprint hattı, JSON-RPC, datasheet'ten footprint çıkarma kıyas seti | **Yalnızca fikir** (RD-G4) |

PLAN 2.1'de kicad-happy "MCP değil, çizmez, denetler" diye geçiyor. Kaynak incelemesi denetim kapsamının PLAN 5.9'un
öngördüğünden çok geniş olduğunu gösterdi. Bu plan o bölümün uygulama yolunu değiştirir.

### 1.1 Ekosistem projeleri (13 Ekim 2026)

Lisans, yıldız ve son commit bilgileri 13 Ekim'de GitHub API'den alındı. Açıklamalar README düzeyindedir; kaynak kodu
ilgili RD-I paketinin ilk adımında okunur. PLAN.md'de zaten geçenler (mixelpixx/Konnect, kicad-mcp-pro,
mcp-server-kicad, kicad-copilot, kicad-tools, SKiDL, atopile, tscircuit, SchGen, jlcparts, kicad-jlcpcb-tools,
JLC2KiCad_lib, STM32_open_pin_data, Freerouting, TraceMaker) burada tekrar edilmez.

| Proje | Lisans · ★ · son commit | Ne | PcbAi'de kullanım | Paket |
|---|---|---|---|---|
| [yaqwsx/KiKit](https://github.com/yaqwsx/KiKit) | MIT · 2040 · 9 Eki 2026 | Panelizasyon, üretici ön ayarları, stencil | Ayrı süreçte bağımlılık; `pcbnew` SWIG'e dayanıp dayanmadığı S12'de ölçülür | RD-I3 |
| [openscopeproject/InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom) | MIT · 4601 · 10 Eki 2026 | Etkileşimli montaj BOM'u (HTML) | Üretim paketine ve rapora ek | RD-I4 |
| [leoheck/kiri](https://github.com/leoheck/kiri) | MIT · 711 · 22 Haz 2026 | Git revizyonları arasında görsel şematik/kart farkı | Fikir; gerekirse kod (atıfla) | RD-I5 |
| [Argmaster/pygerber](https://github.com/Argmaster/pygerber) | MIT · 122 · 24 Mar 2026 | Gerber X3/X2 ayrıştırıcı, render, linter | İsteğe bağlı bağımlılık; ikinci bağımsız ayrıştırıcı | RD-I2 |
| KiCad `kicad-library-utils` (GitLab; GitHub aynası 2020'de kalmış) | GPL-3.0 (GitLab'da doğrulanacak) | Resmî KLC sembol/footprint denetçisi | **Ayrı program**; kod alınmaz | RD-I1 |
| [circuit-synth/kicad-sch-api](https://github.com/circuit-synth/kicad-sch-api), [circuit-synth](https://github.com/circuit-synth/circuit-synth) | MIT · 54 / 285 · Ara 2025 / Mar 2026 | Bayt koruyan şematik yazıcı iddiası, JSON ara temsil, MCP | Yalnızca test bağımlılığı: bağımsız yazıcı kıyası | RD-I6 |
| [eLSeR17/pcb-ai-agent](https://github.com/eLSeR17/pcb-ai-agent) | MIT · 0 · 18 Eyl 2026 | Yanıt grounding kapısı, 21 altın eval, STM32 HAL şablonları + `gcc -fsyntax-only` | Fikir | RD-I7, RD-I8 |
| [l34rn3d/pcb-design-toolkit](https://github.com/l34rn3d/pcb-design-toolkit) | MIT · 0 · 7 Eki 2026 | KiCad 10.0.6'da test edilmiş doğrulama betikleri; çıkış kodu 0/1/2 sözleşmesi | Fikir | RD-I9 |
| [ajokela/pyplacer](https://github.com/ajokela/pyplacer) | BSD-3 · 0 · 24 Nis 2026 | Bağımlılıksız benzetimli tavlama yerleştirici; Quilter'a karşı ölçülmüş (yazarın ölçümü: en iyi tohumda %93,8, Quilter %99,4) | Ayrı süreçte kıyas tabanı; K5 kararında kod adayı | RD-I10 |
| [ArnolFokam/PCBWorld](https://github.com/ArnolFokam/PCBWorld) | BSD-3 (motor ayrı, GPL-3) · 0 · 7 Eki 2026 | KiCad push-and-shove rotalayıcısı üzerinde RL ortamı, 3 aşamalı değerlendirme | Fikir | RD-I11 |
| [Robotips/uConfig](https://github.com/Robotips/uConfig) | GPL-3.0 · 587 · 24 Şub 2026 | PDF'ten LLM'siz pin tablosu çıkarımı | **Ayrı program**; spike | RD-I12 |
| [CK-Consulting/BLPL](https://github.com/CK-Consulting/BLPL) | Apache-2.0 · 0 · 13 Eki 2026 | Markdown tasarım belgesi → KiCad; JSON Schema'lı 0–8 aşamaları, kapı onay vermeden üretim yok | Yalnızca fikir (K15) | RD-I13 |

**Alınmayanlar:**
- **KiBot** (AGPL-3.0): çıktı otomasyonu `kicad-cli` ve RD-C ile örtüşüyor.
- **spicelib, PySpice** (GPL-3.0): kendi ngspice işçimiz var.
- **Lisanssız depolar:** kicad-happy-testharness, NeurPCB, KiCraft, datasheet-parser-new. Bütün hakları saklı,
  yalnızca fikir olarak geçer.
- **Bakımı durmuş:** RL_PCB ve KiCad-Diff (2024); KiRI daha iyi bir seçenek.
- **İncelenmedi:** blwfish/kicad-mcp (MIT) ve tylerwagler/KiCad-MCP (GPL-3.0), PLAN 2.1'deki sunucularla örtüşüyor
  görünüyor.

---

## 2. Lisans ve kod alma kuralları

| Kaynak | Kural |
|---|---|
| MIT (kicad-happy, pcb-skill, easyeda-agent, circuitron, openharness) | Kod alınabilir. Dosya başında kaynak depo, commit ve özgün telif; `NOTICE`'e satır; `scripts/check_licenses.py` alınan dosyaları da tarar. LGPL-2.1-or-later ile uyumlu |
| Apache-2.0 (eda-agent, easyeda-agent `beautify/`) | **K15 kararı gerekir.** Apache-2.0, LGPL-2.1 ile uyumlu sayılmaz; yalnızca "or later" sayesinde LGPL-3 altında birleşebilir, yani dağıtılan bütün fiilen LGPL-3 olur. **Öneri:** kod alınmaz, fikir ve kamu kaynaklı sayılar (IPC-7351, KLC) atıfla, temiz yeniden yazımla kullanılır |
| BSD-3 (pyplacer, PCBWorld sarmalayıcısı) | Kod alınabilir; telif bildirimi ve lisans metni korunur, `NOTICE`'e satır. LGPL-2.1-or-later ile uyumlu |
| GPL-3.0 / AGPL-3.0 (KLC denetçisi, uConfig, PCBWorld motoru) | Yalnızca **ayrı program** (KiCad ve Freerouting gibi); yol yapılandırmadan, `shell=False`, zaman aşımı. Kod, bağlama ve ikili paketlenmez (K12 deseni) |
| Lisans dosyası olmayan depolar | Bütün haklar saklı sayılır: yalnızca fikir |
| PolyForm NC, özel lisans | Yalnızca fikir. Dosya açılıp kopyalanmaz; uygulayan ajan bu depoları kaynak olarak göstermez, yalnızca bu belgedeki fikir satırını kullanır |
| Veri (kural tabloları, IPC sayıları, JLC yetenekleri) | Yayımlayanın belgesine tarihle atıf. Depodan kopyalanan veri dosyası kendi lisansını taşır |

**K16: kicad-happy entegrasyon biçimi.** Öneri iki adımlıdır:

1. S11'de ayrı süreç ve sabitlenmiş commit. Desen `pcbai/external.py` ve motorlardaki gibi; `doctor` sürüm/commit gösterir.
2. Ölçümden sonra benimsenen dedektörler `pcbai/verify/vendor/kicad_happy/` altına atıfla alınır. Upstream commit
   `UPSTREAM.json` dosyasında tutulur; senkron betiği farkı gösterir.

Alternatif tam yeniden yazımdır. 74 bin satır olduğu için önerilmez.

---

## 3. Mimari: yeni denetim katmanı

PLAN 3.5'teki `pcbai/verify/` klasörü bu planla somutlaşır:

```
pcbai/verify/
  findings.py      ortak bulgu şeması + kararlı finding_id + adaptörler (ERC/DRC/motor/analiz)
  manifest.py      checks_run: hangi kontrol çalıştı / atlandı / çöktü ve neden
  calibrate.py     dış motorun KiCad sayılarını yeniden üretme denetimi
  analyze.py       analyze_design: sch / pcb / cross / thermal / emc koşucusu (ayrı süreç)
  vendor/          seçilmiş MIT modüller (K16 adım 2)
  fab/             bağımsız Gerber/Excellon okuyucu ve kontrolleri (RD-C2)
  gate.py          fab_gate ve ölçülen aşama kapıları
pcbai/parts/datasheet/   SpecValue şeması, güven kapısı, kalite puanı (RD-D)
```

**Akış:** Araç → KiCad (CLI/IPC) + analiz motoru → ham çıktı → `calibrate` → `findings` (tek şema) → `manifest`
→ kanıt kaydı. Sonuç MCP aracı, VS Code paneli (tıklayınca konum), işaretler (`diagnostic_markers` gibi geçici)
ve rapordur (İP-7.2).

**Ortak bulgu şeması** (RD-A1). Mevcut `erc_findings`/`drc_findings` ve motor `new_findings` buna çevrilir:

```json
{"finding_id": "pcb:DRC-clearance:u3", "source": "drc|erc|analysis|fab|review",
 "rule_id": "DEC-001", "severity": "error|warning|info",
 "confidence": "deterministic|heuristic|datasheet-backed",
 "evidence_source": "kicad|topology|geometry|datasheet|catalog|calculation",
 "items": [{"uuid": "...", "reference": "C5", "pin": "1", "net": "+3V3", "sheet": "/power/"}],
 "position_mm": [x, y], "measured": {"value": 4.1, "unit": "mm"}, "limit": {"max": 2.0, "unit": "mm"},
 "failure_scenario": "...", "cheapest_fix": "...", "evidence_id": "ev-..."}
```

`finding_id` aynı girdide her koşuda aynıdır. Bugünkü `new_violations` kimlik karşılaştırması bu kimliğe taşınır.

---

## 4. İş paketleri

Her paket ayrı dalda yürür (`ip/rd-a1-bulgu` gibi). Uygulayan Codex, bağımsız denetçi Claude'dur (AGENTS.md).
Süreler tek uygulayan ajan içindir.

### A. Güven temeli (önce bunlar: "yeşil sonuç yalan söylemesin")

- [x] **RD-A1 Ortak bulgu şeması uygulaması** (kicad-happy `finding_schema` fikri; upstream kod alınmadı).
  `pcbai/verify/findings.py`; ERC, DRC, motor ve parite adaptörleri. `verified` değerleri korunur, bulgular tek biçimde döner.
  D1-1 / `ip/rd-a1-bulgu`, çekirdek 0.1.15: 274 test OK/3 skip, gerçek KiCad 11/11, Ruff/lisans temiz.
  **Bağımsız hedefli denetim tamamlandı; 13 Ekim'de main'e alındı**; [sonuç ve sınırlar](status.md).
  **Bitti:** Mevcut ERC/DRC/motor testleri yeni şemayla geçiyor. Aynı dosyada iki koşu aynı `finding_id` kümesini
  veriyor. Şema JSON Schema ile doğrulanıyor. **PLAN bağı:** 5.9 ortak bulgu biçimi. **Süre:** 3 gün.
- [x] **RD-A2 `checks_run` manifesti** (kicad-happy `capability_mode`, `fab_release_gate` skip ≠ pass). Her denetim
  sonucu `{check_id, status: ran|skipped|failed|not_applicable, reason, inputs_sha256}` taşır. Yeni
  `verified=checks_incomplete`; `checks_ok` yalnızca kapsamın zorunlu kontrolleri `ran` ve hiçbir bulgu yoksa yazılır.
  **Bitti (dalga 1 kapsamı):** eksik CLI, eksik belge ve çöken kontrol manifestte görünür; parite istenmediği de
  açıkça kayıtlıdır. `check` ERC/DRC/parite/board_stats çalıştırır; SPICE ve 3B model kapısı bu dalgada yoktur.
  **Süre:** 2 gün.
- [x] **RD-A3 Yazma sonrası bağımsız geri okuma** (easyeda-agent tipli geri okuma). Her yazma aracı `apply` sonrası
  dosyayı **diskten yeniden ayrıştırır** ve niyeti ölçer: değer, konum, net üyeliği, UUID, aday baytlarıyla
  SHA-256 eşitliği. Sonuç `readback: {checked: [...], mismatches: [...]}` alanına yazılır. Uyuşmazlıkta
  `verified=readback_mismatch` döner ve iş durur; kör yeniden deneme yok, geri dönüş için checkpoint önerilir.
  **Bitti:** Her yazma aracında (set_value, add_symbol, connect, add_label, replace_part, add_block, move_footprint,
  set_track_width, add_zone, set_netclass, motor apply) hata enjeksiyonlu test uyuşmazlığı yakalıyor. **Süre:** 4 gün.
- [x] **RD-A4 Motor kalibrasyonu** (pcb-skill "modelini araca karşı doğrula"). Dış analiz motoru bulgu üretmeden önce
  KiCad'in sayılarını yeniden üretir: bileşen ve sayfa örneği sayısı, net sayısı, **net üyeleri** (`kicad-cli`
  netlisti), pad sayısı ve `board_stats` toplamları. Uyuşmazlık `source=calibration` bulgusu olur ve o motorun ilgili
  dedektörleri `skipped(reason=calibration_failed)` sayılır. Mevcut S7/S8 kalibrasyon dairelerinin genelleştirilmesidir.
  **Bitti:** Bilerek bozulmuş net modeli (bir üye eksik) kalibrasyonda düşüyor. **Süre:** 3 gün.
- [x] **RD-A5 Yetenek sınırları belgesi** (easyeda-agent, eda-agent). `docs/limits.md`: "yapılamaz, neden, hangi
  ölçümle görüldü". Örnekler: IPC'de canlı şematik yok, kaydedilmemiş tampon ölçülemiyor, KiCad 10.0.4 render boyutu.
  Araç sonuçları ilgili satıra `limit_id` ile bağlanır. **Süre:** 1 gün.
- [x] **RD-A6 Denetim kaydı** (eda-agent). Her araç çağrısı için süre, girdi/çıktı boyutu, sonuç ve hedef revizyonu
  `<state>/audit.jsonl` dosyasına yazılır. Kanıt kayıtlarıyla `evidence_id` üzerinden bağlanır. **Süre:** 1 gün.

### B. Analiz motoru (kicad-happy entegrasyonu)

- [ ] **RD-B1 S11 spike: kicad-happy KiCad 10 ölçümü.** Ölçüm tamam, bağımsız denetim tamam (çürütülen iddia yok);
  K16 adım 1 kabul. ecc83 proje adı D1-0'da `ecc83-pp` olarak belirtildi. **Açık:** yayın sonuç JSON'u.
  [S11](spikes/S11.md): 20/20 koşu, 474 bulgu, 14 doğru/2 yanlış/4 belirsiz; pin çokluğu ve kategori farkları açık.
  Sabitlenmiş commit, KiCad'in Python 3.11'i, ayrı süreç.
  Beş KiCad demosunda şematik ve PCB analizi; süre, bellek, çıktı karması; RD-A4 kalibrasyonu (net üyeleri
  `kicad-cli` netlistiyle birebir mi?); iki koşuda determinizm; dedektör başına bulgu sayısı; 20 bulgunun elle
  doğru/yanlış etiketlenmesi. **Bitti:** `docs/spikes/S11.md` + sonuç JSON'u, K16 önerisi. **Süre:** 3 gün.
- [ ] **RD-B2 `analyze_design` aracı.** Salt okunur, `start_job` uyumlu. `scope=sch|pcb|cross|thermal|emc`, isteğe
  bağlı `detectors=[...]`. Sonuç: bulgular (RD-A1), `checks_run` (RD-A2), tanınan alt devreler (bölücü, RC/LC,
  LDO/buck, dekuplaj, kristal, op-amp, transistör sürücü, koruma), **güç ağacı** (ray → kaynak → tüketiciler) ve
  kanıt kimliği. Revizyon değişirse sonuç iptal edilir (mevcut desen). **Bitti:** Demolarda çalışıyor; MCP ve
  `/call` testleri var; VS Code bulgu paneli konum gösteriyor. **Süre:** 5 gün.
- [ ] **RD-B3 Blok ↔ tanınan alt devre bağı.** `add_block`/`apply_circuit` ile yazılan her blok, analizde kendi
  türüyle tanınmalı. Tanınmıyorsa blok veya dedektör hatalıdır; bu, bloğun kendi testi olur. Elle çizilmiş alt
  devrelerde kicad-happy `simulate_subcircuits` fikriyle testbench üretilir, ama **bizim** ngspice işçimizle (S5
  güvenlik sınırları aynen). **Bitti:** Üç pasif blok ve P1–P5 referans çözümlerindeki alt devreler tanınıyor.
  **PLAN bağı:** İP-3.2 blok test düzeneği, İP-3.6. **Süre:** 4 gün.
- [ ] **RD-B4 `design_checks`** (PLAN 5.9 listesi + kaynaklar). Kurallar:
  - her VDD/VDDA pininde dekuplaj
  - I²C pull-up varlığı, aralığı ve **adres çakışması**
  - USB-C CC dirençleri, kullanılmayan MCU pinleri
  - güç bütçesi ve doğrusal regülatör ısısı
  - polariteli parçalarda serigrafi işareti
  - kristal yük kondansatörlerinin **eşitliği** (eda-agent `value_checks` fikri)
  - 5 V toleranslı olmayan pine 5 V
  - mutlak sınır ve önerilen çalışma aralığı ihlali (yalnızca `datasheet-backed`, RD-D2)
  - ESD koruma kapsamı, ray kaynağı olmayan güç pini (`audit_rail_sources`)

  Her kuralın en az bir pozitif ve bir negatif fixture'ı vardır. **Bitti:** P2/P3 referans çözümlerinde kural sonuçları
  elle kontrolle uyuşuyor. **PLAN bağı:** İP-5.3 `design_checks` öne alınır. **Süre:** 6 gün.
- [ ] **RD-B5 Şematik ↔ kart çapraz denetimi** (`cross_verify`, `cross_analysis`). Ölçülenler:
  - dekuplaj ped–pin mesafesi (P2 ≤ 2 mm, P3 ≤ 3 mm kıyas ölçütleri buradan ölçülür)
  - akıma göre güç izi genişliği (IPC-2152; akım IR'den veya kullanıcıdan gelir)
  - konnektör akım kapasitesi, termal via yeterliliği
  - **yasak alanın gerçek kural alanı (rule area) olup olmadığı**: yalnızca çizim katmanındaki "keepout" kusurdur
  - fark çifti uzunluk farkı

  **Bitti:** P2–P4 ölçütleri dosyadan otomatik ölçülüyor. **PLAN bağı:** 5.7 "ölçülen denetimler", İP-5.7.
  **Süre:** 5 gün.
- [ ] **RD-B6 Termal ve EMC ön uyum** (`analyze_thermal`, `emc_rules`). Nokta kaynak modelli Tj tahmini (`approximate`
  etiketi, ortam sıcaklığı profilden) ve EMC kural riski. Raporda "ön uyum riski, ölçüm veya alan çözücü değildir"
  yazar. **Bitti:** P2 LDO Tj tahmini `hand_calc` ile %10 içinde. **Süre:** 4 gün.
- [ ] **RD-B7 Parazitik → SPICE** (`extract_parasitics`). İz direnci, via endüktansı ve kuplaj kapasitesi testbench'e
  eklenir; "yaklaşık" etiketi taşır. PLAN 5.6'daki "layout etkisi simüle edilmez" sınırını kısmen daraltır.
  **Süre:** 4 gün (Faz 5c sonu, kesilebilir).
- [ ] **RD-B8 `what_if` ve `design_diff`.** `what_if`: dosyaya yazmadan değer değiştirir; etkilenen hesapları ve
  isteğe bağlı SPICE'ı önce/sonra gösterir. `design_diff`: iki checkpoint veya revizyon arasında bileşen, net, bulgu
  (`finding_id` ile) ve SPICE sonucu farkı. VS Code kontrol noktası ağacına bağlanır. Görsel fark RD-I5'tedir. **Bitti:** "R5=4.7k" önizlemesi
  bölücü çıkışını el hesabı ve SPICE ile gösteriyor; iki checkpoint farkı yeni/kapanan bulguları listeliyor.
  **PLAN bağı:** İP-6.5. **Süre:** 4 gün.

- [ ] **RD-B8s Tam tarihsel proje snapshot altyapısı.** EK-3b'nin ayrı önkoşulu:
  dosya/hash manifesti, gerekli proje ve kütüphane blob'ları, bütünlük doğrulaması ve
  izole materialization. Eksik geçmiş dosya/kütüphane durumunda güncel dosya kullanılmaz;
  kapsam kısmi, geçmiş ERC/netlist kıyası atlanmış gösterilir. **Bitti:** tam iki snapshot
  kararlı yeniden kuruluyor; eksik blob ve bağımlılık açık raporlanıyor. **Süre:** spike
  sonrası tahminlenecek; RD-B8'in 4 günü veya EK özellik toplamında örtük sayılmaz.

### C. Üretim doğrulaması (Faz 5c)

- [ ] **RD-C1 `fab_gate`** (kicad-happy `fab_release_gate` + PLAN 5.10 çıktı kapısı). Kategoriler:
  - rota tamamlığı
  - ERC/DRC (dökümler doldurulmuş), parite
  - BOM: MPN/LCSC kapsamı ve stok
  - DFM profili
  - RD-C2 bağımsız doğrulama
  - açık FATAL/SERIOUS inceleme bulgusu

  Her kontrol pass/warn/fail/skip döner; **skip geçme sayılmaz**. **Bitti:** Eksik girdide `not_ready` ve nedenleri;
  temiz kartta `ready` ve manifest. **PLAN bağı:** İP-5.11 kapısı. **Süre:** 3 gün.
- [ ] **RD-C2 Bağımsız Gerber/Excellon doğrulaması** (pcb-skill `verify/`, MIT). Kendi RS-274X/Excellon okuyucumuz;
  tanımadığı komutta reddeder. Kontroller:
  - dış hat kapalılığı ve ölçüsü; kart dışında bakır/delik
  - delik sayımı (PTH/NPTH, alt küme kanıtı)
  - maske açıklıkları
  - farklı bakırlar arası aralık (raster; numpy yoksa `skipped`)
  - **pad uzlaştırma**: Gerber bakır adaları ↔ PCB net haritası ↔ şematik netlisti
  - `netlist_assert`: geometriden must-connect / must-not-connect

  `export_fab` her çıktıyı bu doğrulamadan geçirir. Okuyucunun kendisi ikinci bir ayrıştırıcıyla (pygerber,
  RD-I2) çapraz kontrol edilir. **Bitti:** Hata kataloğundaki 1 numaralı fixture yakalanıyor:
  "DRC sıfır ama iki net kısa". Eksik katman ve kaymış delik de yakalanıyor. **Süre:** 7 gün.
- [ ] **RD-C3 JLC BOM/CPL ve iki BOM.** kicad-happy `translate_bom_pnp` (MIT) + PLAN 5.10 dönüş düzeltme tablosu.
  BOM'da olmayan CPL satırları ayıklanır. **Satın alma BOM'u ve montaj BOM'u ayrıdır.** Hazırlık durumu
  `manifest.json` içinde `bom_readiness` alanına yazılır. **Bitti:** P2 çıktısı JLC biçim denetiminden geçiyor.
  **PLAN bağı:** İP-5.11. **Süre:** 3 gün.
- [ ] **RD-C4 3B girişim ve mekanik ön kontroller.** `render_3d` GLB'sinden bileşen gövdesi çakışması (modül altına
  düşen kondansatör), konnektörün takılma yüzünün kart kenarına bakması (footprint metadata yoksa `skipped`) ve
  yüksekliği kutu sınırını aşan parçalar. **Bitti:** Hata kataloğu fixture'ları 2 ve 3 yakalanıyor. **PLAN bağı:**
  İP-7.3 CadAI akışına girdi. **Süre:** 4 gün.

### D. Parça ve datasheet

- [ ] **RD-D1 Datasheet çıkarım şeması** (kicad-happy `datasheets/schemas`, MIT). `pcbai/parts/datasheet/`
  altında regulator, mcu, opamp, diode, transistor, crystal ve pinout türleri. Her alan bir SpecValue'dur:
  `{value, unit, page, quote, confidence, extractor}`. Çıkarım önbelleği PDF SHA-256'sına bağlıdır. **Süre:** 3 gün.
- [ ] **RD-D2 Güven kapısı.** Her kural `min_confidence` beyan eder. `datasheet-backed` etiketi yalnızca **alıntısı,
  belirtilen sayfada ayrı süreçteki metin çıkarımıyla bulunan** alandan alınabilir (`deep_review_gate` deseni).
  LLM çıkarımı kullanıcı girdisi kadar güvenilmezdir; kapıyı geçmeyen alan bulguyu `heuristic`e düşürür, sessizce
  atlanmaz. **Bitti:** Sahte alıntı reddediliyor; doğru alıntı geçiyor. **Süre:** 3 gün.
- [ ] **RD-D3 Çıkarım kalite puanı** (`datasheet_score` fikri). Deterministik rubrik: pin kapsamı, gerilim sınırları,
  çalışma koşulları, uygulama devresi. Eşik altı → yeniden çıkarım ya da kullanıcı onayı. **Süre:** 2 gün.
- [ ] **RD-D4 `verify_part` genişletmesi.** Datasheet pin tablosu (bugün kullanıcı girdisi) ↔ çıkarım önbelleği; mutlak
  sınır ve önerilen çalışma aralığı; yaşam döngüsü ve sıcaklık aralığı (`lifecycle_audit` fikri). Ağ isteği yalnızca
  kullanıcı onayıyla yapılır, anahtarlar ortamdan okunur (K18). **PLAN bağı:** İP-2.7. **Süre:** 4 gün.
- [ ] **RD-D5 Distribütör kaynakları.** LCSC (anahtarsız), DigiKey/Mouser/element14 (anahtarlı). **MPN yalnızca
  katalogdan gelir**; modelin hafızasından MPN reddedilir. Bu, B1 ölçütünü korur. **PLAN bağı:** İP-2.5, S6.
  **Süre:** 4 gün.
- [ ] **RD-D6 Footprint ve sembol kuralları.** IPC-7351B land pattern denetimi: paket ölçüsünden beklenen pad
  geometrisi ↔ footprint, dört çeyrek dönüş denenir, **aynalı footprint kusurdur**, 1. pin kontrol edilir. Sayılar
  kamu kaynaklarından (IPC-7351, üretici paket çizimleri) atıfla alınır; eda-agent'tan kod alınmaz (K15). KLC kuralları
  bu pakette yazılmaz, KiCad'in resmî denetçisi kullanılır (RD-I1). **Bitti:** Bilerek aynalanmış SOT-23 ve yanlış
  hatveli SOIC yakalanıyor. **Süre:** 4 gün.

### E. Şematik okunurluk (Faz 3)

- [ ] **RD-E1 Okunurluk ölçütleri** (eda-agent `quality` + `schematic_neatness` fikri). Ayrı ayrı raporlanan ölçütler:
  gövde çakışması, gövdeden geçen tel, tel kesişmesi, büküm, yayılma (bbox/en-boy), etikete düşme oranı, güç teli
  uzunluğu. Bugünkü `add_block` çakışma denetimi bunun alt kümesidir. **Bitti:** `add_block` ve `apply_circuit`
  adayları puan ve dökümle dönüyor; elle çizilmiş referans sayfalarla kıyas tablosu var. **Süre:** 4 gün.
- [ ] **RD-E2 Motif tanıma + katmanlı kök sayfa yerleşimi.** Motifler: bypass C, bölücü, RC, pull-up/down. Kök sayfada
  bloklar ve serbest parçalar sinyal akışına göre katmanlanır (Sugiyama). PLAN 5.4'teki "sütunlara dizme"nin ölçülebilir
  hâlidir. Temiz yeniden yazım (K15). **Bitti:** P3 kök sayfasında RD-E1 puanı elle düzenlenmiş referansın ±%20'si
  içinde. **PLAN bağı:** İP-3.5. **Süre:** 7 gün.
- [ ] **RD-E3 Tel / etiket / güç portu politikası.** Kısa yerel bağlantılar tel, sayfa içi uzak bağlantılar yerel
  etiket, raylar güç sembolü. Karar eşikleri RD-E1 ölçümüyle seçilir. **Süre:** 2 gün.

### F. Ajan iş akışı ve araç yüzeyi

- [ ] **RD-F1 `review_snapshot`** (eda-agent `design_review_snapshot`). Tek çağrıda proje özeti, ERC/DRC/parite,
  `analyze_design` bulguları, BOM durumu, `checks_run` ve açık işaretler. Yanıttaki `review_guidance` iki kuralı
  taşır: cihaz işlevi iddiası datasheet'e dayanır; bulgu, ham ERC/DRC mesajını aktarmaktan fazlasını söyler. PLAN'daki
  `review_board` istemi bunu kullanır. **Süre:** 3 gün.
- [ ] **RD-F2 Araç kümesi modu.** `PCBAI_TOOLSET=small|full|minimal`. `minimal`, araçları birleştirmeden yalnızca
  `tool_catalog` (arama) ve `tool_invoke` (adla çağırma) reklam eder; şema ve açıklamalar korunur. PLAN 5.12'deki
  küçük model çekirdeğiyle birlikte yapılır. **Bitti:** Her modda araç listesi boyutu ve belirteç sayısı ölçülmüş;
  qwen3:8b ile `small` ve `minimal` kıyası. **Süre:** 3 gün.
- [ ] **RD-F3 Toplu düzenleme** (eda-agent bulk + `bulk_hints`). `batch` önizlemesi birden çok yazma adımını **tek
  aday, tek checkpoint, tek ERC/DRC** olarak üretir; bir adım başarısızsa hiçbir şey uygulanmaz. Aynı tekil araç kısa
  sürede N kez çağrılırsa yanıta bir kez `hint_bulk` eklenir. **Bitti:** On `set_value` → tek aday, tek geri dönüş
  adımı. **Süre:** 4 gün.
- [ ] **RD-F4 Karşıt inceleme protokolü** (pcb-skill `02-review`). Her G kapısında (G1–G5) ayrı, salt okunur bir
  incelemeci çalışır:
  1. Durma ölçütü inceleme başlamadan yazılır ("tek geçiş, sıralı liste, ÖNCE DÜZELT: <id'ler>").
  2. İncelemeci kendi dışa aktarımından model kurar ve önce kalibre eder (RD-A4).
  3. Her bulguda FATAL/SERIOUS/MINOR + ölçüm + arıza senaryosu + en ucuz düzeltme bulunur.
  4. Yazma gerektiren belirsizlik bulgu değil, düzeltme geçişine talimattır.

  MCP istemi `review_phase`; AGENTS.md iki ajanlı düzenine eklenir. **Bitti:** Bir faz kabulü bu protokolle kayıtlı.
  **Süre:** 2 gün.
- [ ] **RD-F5 Ölçülen aşama kapıları** (eda-agent `MEASURED_GATES`). `design_board` durum makinesinde her kapı
  `{check_id, measured, pass_if}` taşır. Ajan "geçti" diyemez, kapıyı araç sonucu kapatır. **PLAN bağı:** İP-7.1'in
  içi. **Süre:** 3 gün.
- [ ] **RD-F6 Kullanıcı / üretici profili.** `pcbai/profile.json` (proje) + kullanıcı varsayılanı. Alanlar: bölge,
  üretici, lehim yöntemi, sıcaklık aralığı ve eldeki stok. Lehim yöntemi el ise alt yüzeyde sonlanan paketler ve
  0402'den küçük parçalar için uyarı verilir (pcb-skill el montajı ilkesi). Parça arama, DFM ve termal profili okur.
  **Süre:** 2 gün.
- [ ] **RD-F7 Sessizlik bekçisi** (pcb-skill: 10 sa 53 dk sessiz kalan rota koşusu). Uzun işler heartbeat üretir;
  süre sınırı içinde ilerleme yoksa iş `stalled` olur ve kullanıcıya görünür. Bekleme koşulu, filtre çökse bile bir
  satır üretecek biçimde kurulur. **Süre:** 2 gün.

### G. Kıyas ve regresyon

- [ ] **RD-G1 Üç katmanlı regresyon** (kicad-happy). Katmanlar:
  1. Deterministik golden JSON: demolar ve fixture'lar; bulgu kimlikleri, sayılar.
  2. Sabit beklentiler: bileşen sayısı, tanınan alt devreler, güç ağacı.
  3. LLM incelemesi: yalnızca faz sonlarında (maliyet).

  CI'da golden kayması kırmızı yapar; bilinçli değişiklik golden güncellemesiyle aynı commit'e girer. **Süre:** 3 gün.
- [ ] **RD-G2 Hata kataloğu** (bölüm 5) — **5/16 fixture** (#1, #1b, #9, #12, #13); #1/#9/#12 bağımsız denetimde yeniden üretildi,
  #1b ve dört karakterizasyon testi D1-0'da eklendi, `ef05261` bağımsız denetimle kabul edildi (259 test OK, 3 skip).
  `tests/fixtures/faults/` altında her biri tek bir hatayı içeren küçük KiCad
  projeleri; her fixture onu yakalaması gereken paketi söyler. "Yeşil kart doğru kart değildir" testleri.
  **Süre:** 4 gün, paketlerle birlikte artımlı.
- [ ] **RD-G3 Geniş korpus (isteğe bağlı, K17).** kicad-happy-testharness yaklaşımı (5.800+ proje; README iddiası).
  K14 kararı kıyası KiCad demolarıyla sınırladı; korpus yalnızca **analiz motorunun çökme/kalibrasyon** testi olarak,
  depo dışında ve sonuç yayımlanmadan önerilir.
- [ ] **RD-G4 Datasheet çıkarım kıyası** (assalas "Reef" fikri, yalnızca fikir). 20 parçalık, elle etiketli set:
  pin tablosu, mutlak sınırlar, paket ölçüleri. Model ve yöntem seçimi bu ölçüme dayanır. **Süre:** 3 gün.

### H. Dağıtım ve orkestrasyon (Faz 7 ve sonrası)

- [ ] **RD-H1 Agent Skill paketi.** MCP'ye ek olarak `pcbai` skill'i (`SKILL.md` + iş akışı/inceleme referansları).
  Claude Code ve Codex skill klasörlerine SHA-256 doğrulamalı kurulum; VS Code "MCP'yi ajana ekle" akışına seçenek.
  **Süre:** 2 gün.
- [ ] **RD-H2 GitHub Action.** PcbAi kullanıcılarının KiCad depolarında PR başına `analyze_design`, `design_diff` ve
  `fab_gate` raporu (kicad-happy `action/` fikri). **Süre:** 3 gün.
- [ ] **RD-H3 Paralel ajan yardımcısı** (openharness, spike). Ajan başına `git worktree` açan/kapatan betik; ajan CLI'sı
  sarmalanmaz, durum transcript ve hook'tan okunur. AGENTS.md'deki "ikinci yazıcı ayrı worktree" kuralını mekanikleştirir.
  **Süre:** 2 gün.

### I. Ekosistem araçları (bölüm 1.1)

Her paketin ilk adımı, ilgili deponun **kaynak kodunu** ve güncel lisans dosyasını okumaktır. README düzeyindeki
iddialar paket kabulünde kanıt sayılmaz. Bir dış araç PcbAi'ye girmeden önce RD-A4 kalibrasyonundan geçer.

- [ ] **RD-I1 Resmî KLC denetçisi** (KiCad `kicad-library-utils`, GPL-3.0, ayrı program).
  - **Ne:** Sembol ve footprint kütüphane kuralları (KLC) için KiCad'in kendi denetçisi kullanılır.
  - **Ne zaman çalışır:** `PCBAI_SYMBOLS`/`PCBAI_FOOTPRINTS` özel kütüphanelerinde ve içe alınan JLC parçalarında
    (İP-2.6).
  - **Çıktı:** RD-A1 bulguları; kural kimliği KLC numarasıdır (S4.1 gibi).
  - **Yapılandırma:** Program yolu yalnızca yapılandırmadan gelir; `doctor` sürüm/commit gösterir. Eksikse
    kontrol `skipped` olur (RD-A2).
  - **Bitti:** Bilerek bozulmuş sembol (ızgara dışı pin, yanlış elektriksel tip) ve footprint (avlu eksik)
    yakalanıyor; GitLab'daki güncel lisans ve sürüm `docs/decisions/` altına yazıldı.
  - **PLAN bağı:** İP-2.6, İP-2.7. **Süre:** 3 gün.
- [ ] **RD-I2 İkinci Gerber ayrıştırıcısı** (pygerber, MIT, isteğe bağlı bağımlılık).
  - **Ne:** Aynı Gerber/Excellon dosyasında RD-C2'deki kendi okuyucumuzla karşılaştırma: katman listesi,
    aperture tablosu, flash/çizgi sayısı, sınır kutusu.
  - **Uyuşmazlıkta:** Kart bulgusu değil, `source=calibration` okuyucu bulgusu olur (RD-A4).
  - **Bitti:** KiCad demolarının Gerber'lerinde iki ayrıştırıcı uyuşuyor; bilerek bozulmuş dosyayı en az biri
    reddediyor. Lisans denetimi pygerber'in bağımlılık zincirini de geçiyor; pygerber yoksa kontrol `skipped`.
  - **Süre:** 2 gün.
- [ ] **RD-I3 S12 + panelizasyon** (KiKit, MIT, ayrı süreç).
  - **S12 spike'ı:** KiKit KiCad 10.0.x'te ve KiCad'in Python'unda çalışıyor mu, `pcbnew` SWIG'e ne kadar
    bağlı, Windows'ta yol/kurulum.
  - **Olumluysa `panelize` aracı:** Önizleme yalnızca kopyada yeni panel dosyası üretir; kullanıcı kartına yazılmaz.
    Uygulama ayrı bir `pcbai/fab/panel-*.kicad_pcb` dosyası olur. Panel DRC'si ve RD-C2 bağımsız doğrulama zorunlu.
    KiKit'in JLC/PCBWay ön ayarları RD-C3 çıktısıyla karşılaştırılır.
  - **Bitti:** P2'nin 2×3 paneli DRC=0 ve RD-C2 temiz; S12 sonucu `docs/spikes/S12.md`.
  - **Risk:** KiCad 11'de SWIG kalkıyor; Faz 8'de yeniden değerlendirilir. **Süre:** 4 gün (kesilebilir).
- [ ] **RD-I4 Etkileşimli montaj BOM'u** (InteractiveHtmlBom, MIT).
  - **Ne:** Üretim paketine ve rapora (İP-7.2) `ibom.html` eklenir.
  - **Doğrulama:** Üretimi KiCad'in Python'unda ayrı süreçte yapılır; ibom'daki referans/konum/yüz bilgisi CPL
    ile birebir karşılaştırılır.
  - **VS Code:** Dosya yalnızca harici tarayıcıda ya da uzak içerik yasaklı ayrı bir webview'da açılır; mevcut
    görünümlerin "betiksiz SVG" kuralı gevşetilmez.
  - **Bitti:** P2 ibom'u üretiliyor ve CPL ile birebir. **Süre:** 2 gün (kesilebilir).
- [ ] **RD-I5 Görsel tasarım farkı** (KiRI fikri, MIT). RD-B8 `design_diff`'in görsel katmanıdır.
  - **Ne:** İki checkpoint veya revizyonun mevcut `render_sch`/`render_pcb` SVG'leri ve ölçülmüş dönüşümleri
    üst üste konur; değişen öğeler UUID'leriyle listelenir.
  - **Neden yeniden kurulur:** KiRI git'e ve Linux kabuğuna dayalı, PcbAi checkpoint'leri git değil. Yaklaşım
    alınır, gerekirse kod parçası atıfla alınır.
  - **Bitti:** VS Code'da iki checkpoint arası şematik ve kart farkı yan yana ve üst üste görünüyor; eklenen,
    silinen ve taşınan öğeler ayrı renkte ve listede.
  - **PLAN bağı:** İP-6.5. **Süre:** 4 gün.
- [ ] **RD-I6 Bağımsız şematik yazıcı kıyası** (kicad-sch-api + circuit-synth, MIT, yalnızca test bağımlılığı).
  - **Ne:** On düzenleme senaryosu (sembol ekle, etiketle bağla, değer değiştir, alt sayfa) hem bizim yazıcımızla
    hem kicad-sch-api ile yapılır. İki sonucun `kicad-cli` netlistleri ve ERC sonuçları karşılaştırılır; farklar
    bulgu olur.
  - **IR eşleme:** circuit-synth'in JSON ara temsili ile bizim IR'miz arasında eşleme tablosu çıkarılır
    (`docs/ir.md` eki); içe aktarma yolu için fikir.
  - **Bitti:** Karşılaştırma raporu `.pcbai-state/` altında, farkların her biri açıklanmış.
  - **Risk:** kicad-sch-api'ye Aralık 2025'ten beri commit yok; ürün bağımlılığı yapılmaz.
  - **PLAN bağı:** İP-2.1 kabulüne ek kanıt. **Süre:** 3 gün.
- [ ] **RD-I7 Yanıt ve rapor grounding kapısı** (pcb-ai-agent fikri).
  - **Rapor tarafı:** `design_report`, kanıt kaydında karşılığı olmayan referans (R5, U3), net adı ya da sayı
    içeremez. Rapor bizim tarafımızda üretildiği için bu kontrol deterministiktir.
  - **Sohbet tarafı:** İsteğe bağlı `check_claims(text, session)` aracı, ajanın yanıtındaki iddiaları aynı oturumun
    araç sonuçları ve kanıtlarıyla eşleştirir; eşleşmeyenleri listeler. Ayrıştırma sezgiseldir ve sonuç `heuristic`
    olarak işaretlenir.
  - **Bitti:** Uydurma sayı içeren rapor taslağı reddediliyor; 10 örnek yanıtta eşleşme ve kaçırma oranı ölçüldü.
  - **PLAN bağı:** B3 ölçütü, İP-7.2. **Süre:** 3 gün.
- [ ] **RD-I8 Firmware duman testi şablonu** (pcb-ai-agent fikri).
  - **Ne:** Kart 2 (İP-7.5) için IR'deki pin atamalarından (STM32_open_pin_data ile doğrulanmış) STM32 HAL
    LED/röle/SWD şablonu üretilir.
  - **Denetim:** `arm-none-eabi-gcc -fsyntax-only -Wall -Werror` ayrı süreçte çalışır; derleyici yoksa `skipped`.
  - **Kapsam sınırı:** Link, flash veya donanım çalışması iddia edilmez.
  - **Bitti:** P3 pin atamasıyla şablon sözdizimi denetiminden geçiyor. **Süre:** 3 gün (kesilebilir).
- [x] **RD-I9 CLI çıkış kodu sözleşmesi** (pcb-design-toolkit fikri). `python -m pcbai check <proje> [--scope ...]`.
  - **Çıkış kodları:** `0` beyan edilen kapsam geçti, `1` bulgu incelenmeli, `2` zorunlu kontrol çöktü,
    atlandı ya da bilinmiyor. Anlamı RD-A2 ile aynıdır; RD-H2 GitHub Action bunu kullanır.
  - **Bitti:** Üç durumun her biri için CLI testi. **Süre:** 1 gün.
- [ ] **RD-I10 Yerleşim kıyas tabanı** (pyplacer, BSD-3, ayrı süreç).
  - **Ne:** S10/R7 kıyas tablosuna "benzetimli tavlama tabanı" sütunu eklenir: yerleşimi kaldırılmış beş KiCad
    demosunda pyplacer + Freerouting rota oranı, süre ve tohum dağılımı.
  - **Uyum:** KiCad 10'daki ad tabanlı net biçimi için gereken uyarlama ölçülür.
  - **Skor ve K5:** Maliyet terimleri (HPWL, sert/yumuşak çakışma, kart sınırı, tıkanıklık, pad çıkış yönü)
    İP-5.6 skorunun başlangıç listesidir. K5 kendi tavlamamızı yazma yönünde kapanırsa kod atıfla alınabilir.
  - **Bitti:** Kıyas tablosu `docs/spikes/S10.md` ekinde. **PLAN bağı:** İP-5.6, K5. **Süre:** 3 gün.
- [ ] **RD-I11 Rota değerlendirme hattı** (PCBWorld fikri; kod alınmaz). R7 motor kıyası üç aşamada raporlanır:
  - yasallık (yeni DRC kimliği yok)
  - tamamlık (rotalanmamış bağlantı)
  - kalite (via, uzunluk, büküm)

  Bir aşamayı geçemeyen motor sonraki aşamada puanlanmaz. **Süre:** 1 gün (kesilebilir).
- [ ] **RD-I12 Deterministik pin tablosu çıkarımı spike'ı** (uConfig, GPL-3.0, ayrı program).
  - **Ne:** RD-D2'de LLM çıkarımına karşı ikinci bağımsız kaynak. Aynı pin adını iki bağımsız yöntem bulursa
    alan `confidence=high` olur, uyuşmazlık bulgudur.
  - **Önce:** uConfig'in başsız (CLI) kipi var mı ölçülür; yoksa spike "uygun değil" diye kapanır.
  - **Bitti:** RD-G4 setindeki 20 parçada ölçüm. **Süre:** 2 gün (kesilebilir).
- [ ] **RD-I13 Markdown gereksinim girişi** (BLPL fikri; Apache, kod alınmaz). G1 kapısında kullanıcının
  `requirements.md` şablonu `requirements.json`'a ayrıştırılır. Her aşama çıktısı JSON Schema ile doğrulanır;
  belirsiz alan soruya dönüşür. **PLAN bağı:** İP-7.1. **Süre:** 1 gün.

---

## 5. Hata kataloğu: neyi yakalamalıyız?

pcb-skill vaka çalışmasındaki gerçek hatalar ve diğer depoların dersleri. Her satır bir RD-G2 fixture'ıdır.
"Bugün" sütunu PcbAi 0.1.21'in ölçülen durumunu belirtir: ölçülmedi, araç yok ya da kısmi.

| # | Hata (kaynak) | Neden kaçtı | Yakalayan paket | Bugün |
|---|---|---|---|---|
| 1 | Net portları beş neti kısa devre etti, **DRC sıfır** (pcb-skill) | DRC kendi net modeline göre temizdi | RD-C2 pad uzlaştırma + `netlist_assert`, RD-A4 | Fixture #1: `check --scope pcb` parite bulgusu, CLI exit 1; Gerber tarafı yok |
| 1b (1'in alt vakası) | Aynı yerel etiket niyette ayrı netleri birleştirdi | DRC ve parite aynı yanlış şematik modelini kabul eder | RD-C2 `netlist_assert` + IR niyet kıyası | Fixture ve karakterizasyon testi var; niyet ihlali bilinen kaçak, ürün yakalayıcısı yok |
| 2 | Esnek kablo soketi 180° döndürülmüş, panel takılamıyor (pcb-skill) | Elektriksel olarak doğru | RD-C4 takılma yüzü, RD-D6 1. pin | Yok |
| 3 | Kondansatör modül gövdesinin altında (pcb-skill) | Avlu çakışması yoktu, gövde 3B'de çakışıyordu | RD-C4 3B girişim | Yok |
| 4 | Batarya fişi konnektöre ulaşamıyor (pcb-skill) | Mekanik | RD-C4 + İP-7.3 CadAI | Yok |
| 5 | Anten yasak alanı yalnızca çizim katmanında (pcb-skill) | Kural alanı değildi, DRC görmedi | RD-B5 | Yok |
| 6 | Güç rayları akım sınırının 2,5 katı, pil altında gömülü (pcb-skill) | Akım IR'de yoktu | RD-B5 IPC-2152 + RD-F6 | Yok |
| 7 | Algılama pini mutlak minimumun 1 V altında (pcb-skill) | Datasheet sınırı denetlenmedi | RD-B4 + RD-D2 | Yok |
| 8 | Şarj akımı paketin ısıl kapasitesini aşıyor (pcb-skill) | Termal hesap yoktu | RD-B6 | `hand_calc` LDO kısmi |
| 9 | Üç denetleyici yanlış şeyi ölçtü (pcb-skill) | Araç kalibre edilmemişti | RD-A4, RD-A2 | Fixture #9: bölümleme eşitken iki `net_name_member_swap` bulgusu |
| 10 | Uydurma MPN veya pin (Zane456, circuitron) | Model hafızası | RD-D5, mevcut `plan_circuit`/`verify_part` | Kısmi (KiCad kütüphanesi) |
| 11 | Kristal yük kondansatörleri farklı değerde (eda-agent) | Bağlantı doğru, değer uyumsuz | RD-B4 | Yok |
| 12 | Atlanan kontrol "temiz" sayıldı (kicad-happy) | Eksik araç sessizce geçti | RD-A2 | Fixture #12: `check` checks_incomplete, CLI exit 2 |
| 13 | Yazılan değer niyetten farklı (easyeda-agent) | Ekran görüntüsüne güvenildi | RD-A3 | Fixture #13: SHA doğru yanlış aday ve 13 yazıcı enjeksiyonu readback_mismatch |
| 14 | Rapor ya da yanıtta araç çıktısında olmayan sayı veya referans (pcb-ai-agent) | Model metni ölçümden ayrıştı | RD-I7 | Yok |
| 15 | Kendi Gerber okuyucumuz bir komutu yanlış yorumluyor | Tek ayrıştırıcıya güvenildi | RD-I2, RD-A4 | Okuyucu henüz yok |
| 16 | Özel kütüphanedeki sembolün pini ızgara dışında ya da elektriksel tipi yanlış | KLC denetlenmedi | RD-I1 | Yok |

---

## 6. Takvim

PLAN bölüm 9 takvimine yerleşir. Tarihler PLAN'ın hafta numaralarıyla aynıdır.

| Dalga | Tarih | PLAN fazı | Paketler | Çıkış |
|---|---|---|---|---|
| 0 | 13–23 Eki 2026 | Faz 0 | RD-B1 (S11), K15/K16 kararları, RD-G2'nin ilk üç fixture'ı (#1, #9, #12) | S11 raporu, kararlar |
| 1 | 26 Eki – 6 Kas | Faz 1 | RD-A1, A2, A3, A4, A5, A6, I9 | Tek bulgu şeması, geri okuma, kalibrasyon, CLI çıkış kodları |
| 2 | 9–27 Kas | Faz 2 | RD-B2, D1, D2, D3, D5 (S6 ile), F2, F3, I1, I6; I12 spike | `analyze_design`, datasheet güven kapısı, KLC denetimi |
| 3 | 30 Kas – 25 Ara | Faz 3 | RD-B3, B4, E1, E2, E3, F1, G1 | v0.3: şematik denetim raporu + okunurluk puanı |
| 4 | 4–22 Oca 2027 | Faz 4 | RD-B8, D4, G4, I5 | what-if, tasarım farkı (veri + görsel) |
| 5 | 25 Oca – 5 Mar | Faz 5 | RD-B5, B6, D6, C1, C2, C3, C4, I2, I10, I11; B7, I3 (S12), I4 (kesilebilir) | v0.6: bağımsız doğrulanmış üretim paketi, panel, montaj BOM'u |
| 6 | 8 Mar – 23 Nis | Faz 6–7 | RD-F4, F5, F6, F7, H1, H2, I7, I13; H3 spike; I8 (kesilebilir) | v0.8: ölçülen kapılı `design_board`, kanıtsız sayı içermeyen rapor |

**Kesme sırası** (gecikmede, PLAN 9'a eklenir): RD-I8 → RD-I12 → RD-I11 → RD-I4 → RD-I3 → RD-B7 → RD-H2 → RD-G3 →
RD-E2 (yerine basit sütun yerleşimi) → RD-B6 EMC kısmı. A, C2, D2, I2 ve I7 paketleri **kesilmez**; bunlar
doğrulamanın kendisidir.

### 6.1 PLAN.md'ye etkiler

| PLAN İP | Değişiklik |
|---|---|
| İP-2.7 `verify_part` | RD-D1–D4 ile datasheet tarafı somutlaşır |
| İP-3.2 / 3.6 bloklar | Blok testine "analizde tanınma" eklenir (RD-B3) |
| İP-3.5 `apply_circuit` | Aday puanı RD-E1, kök yerleşim RD-E2 |
| İP-5.3 `design_checks`, `dfm_check` | Faz 3'e çekilir ve kicad-happy tabanlı olur (RD-B4) |
| İP-5.7 ölçülen yerleşim denetimleri | RD-B5 |
| İP-5.11 çıktı kapısı | RD-C1–C3; bağımsız Gerber doğrulaması zorunlu adım olur |
| İP-6.5 sonuç paneli | Ortak bulgu şeması, `design_diff`, `checks_run` görünümü |
| İP-7.1 `design_board` | Ölçülen kapılar (RD-F5), karşıt inceleme (RD-F4) |
| 5.12 araç kümeleri | `minimal` modu eklenir (RD-F2) |
| 2.5 lisans tablosu | kicad-happy, pcb-skill, KiKit, InteractiveHtmlBom, KiRI, pygerber, kicad-sch-api (MIT); pyplacer (BSD-3); KLC denetçisi, uConfig (GPL-3, ayrı program); eda-agent, BLPL (K15); KiBot (AGPL, kullanılmaz); PolyForm/özel/lisanssız (yalnızca fikir) satırları |
| İP-2.1 s-expr yazıcı | Kabulüne bağımsız yazıcı kıyası eklenir (RD-I6) |
| İP-2.6 parça getirme | İçe alınan parçalar KLC denetiminden geçer (RD-I1) |
| İP-5.6 yerleşim, K5 | pyplacer kıyas tabanı ve maliyet terimleri (RD-I10) |
| İP-5.11 çıktı | Panel (RD-I3), `ibom.html` (RD-I4), ikinci Gerber ayrıştırıcısı (RD-I2) |
| İP-7.2 rapor | Kanıtsız sayı ve referans içeremez (RD-I7) |
| İP-7.5 kart 2 | Firmware duman testi şablonu (RD-I8) |

---

## 7. Riskler

| Risk | Önlem |
|---|---|
| kicad-happy kendi bağlantı modelini kullanıyor, KiCad netlistiyle ayrışabilir | RD-A4 kalibrasyonu; uyuşmazlıkta dedektör `skipped` |
| Hızlı değişen upstream (RC etiketleri, şema sürümleri) | Sabitlenmiş commit, `UPSTREAM.json`, golden testler (RD-G1) |
| Sezgisel dedektörlerin yanlış pozitifleri kullanıcıyı yorar | `confidence` alanı; `heuristic` bulgular varsayılan olarak `warning`dan yukarı çıkmaz; S11'de elle etiketlenmiş yanlış pozitif oranı |
| Datasheet çıkarımı uydurur | RD-D2 alıntı/sayfa kapısı; kapıyı geçmeyen değer kural beslemez |
| Apache/NC kod sızıntısı | K15; lisans denetimi alınan dosyaları tarar; denetçi diff'te kaynak başlığı arar |
| Ağ istekleri ve API anahtarları | Varsayılan çevrimdışı; anahtarlar ortamdan okunur; istek öncesi kullanıcı onayı (K18) |
| Kapsam şişmesi | PLAN ilkesi korunur: kıyas ölçütü düşmeden yeni özellik eklenmez; dalga sonunda kıyas yeniden koşulur |
| KiKit ve InteractiveHtmlBom `pcbnew` SWIG'e dayanıyor olabilir; KiCad 11'de SWIG kalkıyor | Yalnızca ayrı süreç; S12'de bağımlılık ölçülür; Faz 8'de yeniden değerlendirilir; ikisi de kesilebilir |
| Az yıldızlı, yeni depolar (pcb-ai-agent, pyplacer, pcb-design-toolkit, PCBWorld) | Yalnızca fikir ya da ayrı süreçte kıyas; ürün bağımlılığı yapılmaz |
| Bakımı yavaşlamış bağımlılık (kicad-sch-api) | Yalnızca test bağımlılığı; kırılırsa kıyas `skipped` olur, ürün etkilenmez |
| GPL ayrı programların kurulumu kullanıcıya yük | `doctor` eksik programı ve etkisini (hangi kontrol `skipped`) açıkça gösterir; zorunlu değildirler |

---

## 8. Kararlar (kullanıcı)

| Kod | Karar | Öneri | Durum |
|---|---|---|---|
| K15 | eda-agent (Apache-2.0) kodu alınsın mı? | Hayır; fikir + kamu kaynaklı sayılarla temiz yeniden yazım. Alınırsa dağıtım fiilen LGPL-3 olur | **Kabul** 13 Eki ([0004](decisions/0004-referans-depolar.md)) |
| K16 | kicad-happy entegrasyon biçimi | Önce ayrı süreç + sabit commit (S11), sonra seçilen modüller atıfla `vendor/` altına | **Adım 1 kabul** 13 Eki; adım 2 (vendor) RD-A4/B2 sonrası ayrıca sorulur |
| K17 | Demolar dışında geniş korpus | Yalnızca çökme/kalibrasyon için, depo dışında, sonuç yayımlanmadan | Açık (RD-G3 öncesi) |
| K18 | Distribütör API'leri (ağ, anahtar) | LCSC anahtarsız varsayılan; diğerleri kullanıcı anahtarıyla, istek başına onay | Açık (dalga 2 RD-D öncesi) |
| K19 | Skill olarak dağıtım (RD-H1) | Evet, v0.8 yayınında MCP'nin yanında | Açık (dalga 6 RD-H1 öncesi) |
| K20 | RD-I'nin kesilebilir kısmı (I3, I4, I8, I11, I12) | Varsayılan "zaman kalırsa"; zorunlu olanlar I1, I2, I5, I6, I7, I9, I10, I13 | **Kabul** 13 Eki |
| K21 | GPL ayrı programlar (KLC denetçisi, uConfig) kurulumu | İsteğe bağlı; `doctor` yönlendirir. PcbAi paketine girmez (K12 deseni) | **Kabul** 13 Eki |

---

## 9. İlk adım

S11 (RD-B1): kicad-happy sabit commit ile beş KiCad demosunda ayrı süreçte koşulur. Net üyeleri `kicad-cli`
netlistiyle karşılaştırılır, determinizm ve süre ölçülür, 20 bulgu elle etiketlenir. Sonuç `docs/spikes/S11.md`'ye
yazılır ve K16 kesinleşir. Aynı hafta K15, K20 ve K21 kararları alınır ve RD-G2'nin ilk üç hata fixture'ı hazırlanır.
