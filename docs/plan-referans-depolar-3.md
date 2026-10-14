# Plan — referans depolar, üçüncü dalga (R3)

Tarih: 14 Ekim 2026 · Durum: **R3-A1 tamam, diğerleri açık** · Başlangıç ağacı: `ip/ip-isaret-paneli/ad8bd87`,
çekirdek 0.1.27 · Bağlı: [RD planı](plan-referans-depolar.md), [R2 planı](plan-referans-depolar-2.md),
[U0–U8 planı](plan-uretim-dogrulama.md), [rota/yerleşim planı](plan-rota-yerlesim.md), [IR v1](ir.md),
[PLAN.md](../PLAN.md), [eksikler](plan-eksikler.md), [uygulama durumu](status.md)

Bu belge 24 açık kaynak depodan PcbAi'ye **neyin, hangi yolla** alınacağını ve her işin ne zaman "bitti" sayılacağını
söyler. RD/R2/U planlarının yerine geçmez. Mevcut bir paketle örtüşen iş yeni paket açmaz, o paketin kabul listesine
**ek madde** olarak girer (bölüm 3). Yeni paketler `R3-` önekini taşır; rota planındaki `R0–R9` sıra numaralarıyla
karışmaz. Uygulayan ajan (Codex) her paketi bitirince ölçülen sonucu status.md'ye yazar ve buradaki kutuyu işaretler;
denetçi ajan kodu değiştirmez, AGENTS.md iki ajanlı düzenine uyar.

---

## 0. Özet

- **24 depodan 8'i işe yarar, 5'i yalnızca fikir, 11'i alakasız** (bölüm 1). İsim benzerliği yüzünden listeye giren
  oyun yapay zekâları, ZK kriptografi ve mantık-kapısı kütüphaneleri ayıklandı.
- **Yeni yetenekler (bugün hiçbir planda yok):**
  1. `readable_netlist`: gerçek netlistin LLM'e uygun, net başına gruplanmış ve pin açıklamalı metin hâli (tscircuit).
  2. IR v1.1: **birimli tolerans aralığı** ve **`assert` ifadesi** (atopile). Bugün `params` serbest sözlük,
     `quantity` sayı ya da serbest metin; aralık ve doğrulama ifadesi yok.
  3. Parametrik parça seçici: "10 kΩ ±1 % 0402 ≥ 1/16 W" isteğinden **aday listesi** (atopile). Seçim yapmaz,
     aday üretir; MPN yalnızca katalogdan gelir (RD-D5 kuralı).
  4. Gereksinim dosyasıyla SPICE doğrulaması: `requirements` → ölçüm → pass/fail tablosu + karmalı manifest
     (multisim-mcp).
  5. Ajan düzeltme döngüsü bütçesi: en fazla N tur, **aynı bulgu kimliği tekrar ederse dur** (boardsmith ERCAgent).
  6. Şematik görsel düzeltme döngüsü: render → okunurluk puanı → aday düzeltme (EEschematic).
  7. Tasarım akışı skill paketi: gereksinim mülakatı → `SPEC.md` → mimari → parça → blok → ERC incelemesi (skidl-skills).
  8. Hiyerarşik sayfa araçları: `add_sheet`, `add_sheet_pin`, `add_hier_label` (mcp-kicad-sch-api).
  9. VS Code eklentisi için uçtan uca arayüz testi (circuit-mcp, yalnızca geliştirme aracı).
- **Var olan paketleri besleyenler:** boardsmith'in 11 denetimi → RD-B4; easyeda-copilot kısıtlı yerleşim ve net
  sınıfı → U8 / rota planı; multisim-mcp sweep ve Bode → U6; EEschematic → RD-E1/E2.
- **İlke korunur:** PcbAi LLM API çağırmaz; ajan döngüsü istemcidedir. Her yazma önizleme → checkpoint → uygula →
  geri okuma. Görsel/sezgisel sonuç kapı açmaz. Atlanan kontrol "geçti" sayılmaz.
- **Süre:** Zorunlu yeni paketler **30 iş günü**, mevcut paketlere eklenen kabul maddeleri **+6 gün** (bölüm 3);
  toplam zorunlu **36 gün** (~7 hafta-ajan). Ayrıca **8 gün kesilebilir** iş.

---

## 1. İncelenen depolar (14 Ekim 2026, README düzeyinde)

Kaynak kod satır satır okunmadı; her paketin ilk adımı ilgili deponun sabit bir commit'inde kaynak incelemesidir
(bölüm 4, R3-0). Yıldız sayıları ve lisanslar 14 Ekim'de GitHub sayfasından okundu.

### 1.1 Kullanılacaklar

| Depo | Lisans | Olgunluk | Ne alınır | Nereye |
|---|---|---|---|---|
| [ForestHubAI/boardsmith](https://github.com/ForestHubAI/boardsmith) | **AGPL-3.0** | 1 commit (squash), 36★ | 11 tasarım denetimi listesi, parça bilgi kaydı şeması (ratings, I²C adresi, init dizisi), ERC düzeltme döngüsü durma kuralı, `--no-llm` deterministik mod fikri | RD-B4 ek, R3-B1, R3-C1 |
| [atopile/atopile](https://github.com/atopile/atopile) | MIT | 2,8k commit, ~4k★, aktif | Birimli tolerans, `assert` kısıtı, parametrik parça seçimi, karta yerleşimi koruyarak güncelleme fikri | R3-A2, R3-A3 |
| [tscircuit/circuit-json-to-readable-netlist](https://github.com/tscircuit/circuit-json-to-readable-netlist) | MIT | 49 commit | Net başına gruplanmış, pin açıklamalı LLM netlist biçimi | R3-A1 |
| [biosshot/easyeda-copilot](https://github.com/biosshot/easyeda-copilot) | MIT | ~560 commit, 176★ | Fonksiyonel bloklarla kısıtlı yerleşim, kenar/keepout, net sınıfı + diferansiyel çift + fanout + via stitching tek işlemde, şematiği bloklara göre sayfalama | U8 ek, R3-D1 |
| [yxy050208/multisim-mcp](https://github.com/yxy050208/multisim-mcp) | MIT (NI dosyaları hariç) | 215 commit, v1.2.0 | `verify_experiment_requirements`, sweep planı, Bode analizi, SHA-256 `manifest.json`, iş iptal/yeniden deneme | R3-C2, U6 ek |
| [nickkraakman/skidl-skills](https://github.com/nickkraakman/skidl-skills) | MIT | Claude Code eklentisi | 9 ajanlı akış: gereksinim mülakatı, mimari, parça bulucu, datasheet arşivi, blok kodlayıcı, ERC incelemecisi | R3-E1 |
| [eelab-dev/EEschematic](https://github.com/eelab-dev/EEschematic) | MIT | 61 commit | Netlist → okunaklı şematik; görsel geri bildirimle yerleşim iterasyonu, few-shot alt devre örnekleri | R3-D2, RD-E2 ek |
| [AvestimehrResearchGroup/AICircuit](https://github.com/AvestimehrResearchGroup/AICircuit) | MIT | araştırma veri seti | Analog/RF spesifikasyon → parametre veri seti ve simülasyon hattı | R3-F2 (kesilebilir) |

### 1.2 Yalnızca fikir

| Depo | Lisans | Fikir | Neden kod yok |
|---|---|---|---|
| [circuit-synth/mcp-kicad-sch-api](https://github.com/circuit-synth/mcp-kicad-sch-api) | MIT | Hiyerarşik sayfa/pin/etiket araç adları ve sözleşmesi | 9 araçlık ince sarmalayıcı; bizim önizleme/checkpoint sözleşmemiz yok. kicad-sch-api zaten RD planında |
| [colaco1123/K-AI](https://github.com/colaco1123/K-AI) | MIT | KiCad araç çubuğu düğmesinden istem gönderme | Tarayıcı oturumu kazıma, kırılgan; AJ planındaki KiCad içi arayüz zaten var |
| [mfranzon/circuitiny](https://github.com/mfranzon/circuitiny) | MIT | Devreden ESP-IDF iskeleti ve yerel firmware simülasyonu | Kapsam U7 (STM32) ile çakışır; ESP32 hedefi şimdilik yok |
| [clharman/circuit-mcp](https://github.com/clharman/circuit-mcp) | Apache-2.0 | Electron/web için MCP üzerinden uçtan uca test | K15 gereği kod alınmaz; **ayrı geliştirici aracı** olarak çalıştırılır, paketlenmez (R3-F1) |
| [gitcommitshow/resilient-llm](https://github.com/gitcommitshow/resilient-llm) | MIT | Yeniden deneme / devre kesici | PcbAi LLM çağırmaz; yalnızca dış motor süreçlerinde (Freerouting, ngspice) "aynı hata N kez → dur" kuralı RD-F7'ye not |

### 1.3 Alakasız (atlandı)

`rlcevg/CircuitAI` (RTS oyun yapay zekâsı), `mvcisback/py-aiger` ve `py-aiger-bv` (AIG mantık-kapısı formel
doğrulama), `zksecurity/zk-skills` (ZK kriptografi denetimi), `dobriban/Principles-of-AI-LLMs` (ders notu),
`galgtonold/ai_combinator` (Factorio modu), `CIrcui-try/Circuit` (skill akış editörü), `QuantumLogicsLabs/CircuitMind`
(**tescilli lisans**, oyuncak düzeyi), `KshKnsl/CircuitAI` (dijital kapı demosu), `tscircuit/chat.tscircuit.com`
(README'de devre üretim mantığı yok), `Corning-AI/PCBai` (kod yok, yalnızca "Coming Soon" README).

**Not (K21):** `Corning-AI/PCBai` adı bizimkiyle neredeyse aynı. Kod yok, ama PyPI/VS Code Marketplace adı ve
GitHub araması çakışabilir. Karar kullanıcıda (bölüm 7).

---

## 2. Lisans kuralları

RD planı bölüm 2 aynen geçerlidir. Bu dalga için ek:

| Kaynak | Kural |
|---|---|
| boardsmith (AGPL-3.0) | **Kod, veri dosyası (`shared/knowledge/seed/`) ve test fixture'ı açılıp kopyalanmaz.** Uygulayan ajan yalnızca bu belgedeki fikir satırlarını kullanır. Parça değerleri (I²C adresi, gerilim sınırı) üretici datasheet'inden atıfla alınır |
| atopile, tscircuit, easyeda-copilot, multisim-mcp, skidl-skills, EEschematic (MIT) | Kod alınabilir; dosya başında kaynak depo, commit, özgün telif; `NOTICE` satırı; `scripts/check_licenses.py` taraması. **Öneri:** biçim ve fikir alınır, temiz yeniden yazılır; TypeScript kaynaklar zaten doğrudan alınamaz |
| multisim-mcp | NI dosya biçimleri, şablonları ve örnekleri hiçbir koşulda alınmaz |
| circuit-mcp (Apache-2.0) | Yalnızca geliştirme makinesinde ayrı süreç; `pyproject.toml` bağımlılığı ve VSIX içeriği olmaz |
| AICircuit veri seti (MIT) | İndirilen veri `.pcbai-state/` dışına, depoya girmez; kullanılırsa commit ve SHA-256 kaydedilir |

---

## 3. Var olan paketlere eklenen kabul maddeleri

Bu maddeler yeni paket değildir. İlgili paket uygulanırken kabul listesine eklenir; süre o pakete eklenir.

| Paket | Ek madde | Kaynak | Ek süre |
|---|---|---|---|
| **RD-B4 `design_checks`** | Üç yeni kural: (a) **bağlı iki pin arasında gerilim düzeyi uyumu** (3,3 V çıkış → 5 V CMOS girişi VIH), (b) **ortak hatta saat/hız uyumu** (I²C 400 kHz cihaz + 1 MHz yapılandırma), (c) **pull-up değeri ↔ hat kapasitesi ↔ hız** el hesabıyla (`hand_calc` kanıtı). Her biri pozitif + negatif fixture | boardsmith | +2 gün |
| **RD-B4** | Denetim kaydı `{rule_id, inputs, measured, limit, source}`; `source` ∈ `datasheet-backed`/`heuristic`/`user`. Kaynaksız sınır `heuristic` olur, bulgu düzeyi en çok WARN | boardsmith + RD-D2 | 0 (mevcut ilkenin yazılı hâli) |
| **U6** | `sweep` (tek parametre, en çok 50 nokta) ve `ac` sonucundan **Bode özeti**: −3 dB frekansı, faz payı, kazanç payı. Ölçüm yoksa `not_measured`, NaN geçmez | multisim-mcp | +2 gün |
| **U8 / rota planı R6** | `autoplace` girdisine IR `constraints` + **blok gruplama** (aynı blok id'li parçalar bir bölgede). Kabul: P2'de dekuplaj kondansatörü kendi IC'sinin bloğunda | easyeda-copilot | +1 gün |
| **RD-E2** | Few-shot motif kütüphanesi: bölücü, RC, LDO, op-amp evirmeyen yükselteç için elle düzenlenmiş referans yerleşim; motif tanınırsa referans yerleşim önerilir | EEschematic | +1 gün |
| **RD-F7** | Dış süreç aynı hata imzasıyla 3 kez düşerse `stalled_repeating`, yeniden deneme yok | resilient-llm fikri | 0 |

---

## 4. Yeni iş paketleri

### R3-0. Kaynak incelemesi (önce bu)

- [ ] **R3-0 Sabit commit'lerde kaynak okuması.** atopile (`solver`, `picker`, `parameters`), tscircuit netlist
  dönüştürücü, easyeda-copilot (`placement`, `router`), multisim-mcp (`requirements`, `manifest`), skidl-skills
  (`skills/`, `agents/`, `hooks/`), EEschematic (istem ve döngü). boardsmith **açılmaz** (AGPL; fikir bu belgede).
  Çıktı: `docs/spikes/R3-0.md`. Her depo için commit, incelenen dosyalar, alınacak biçim/algoritma özeti, **bizde
  karşılığı olan dosya:satır**, alınmayacaklar ve nedeni. **Bitti:** Bölüm 4'teki her paket için en az bir somut
  "şu fonksiyonun şu davranışı" satırı var; README'den çıkarılmış ama kaynakta olmayan iddia işaretlendi.
  **Süre:** 2 gün. **Dal:** `ip/r3-0-kaynak`.

### A. Ajanın devreyi anlaması ve IR

- [x] **R3-A1 `readable_netlist` aracı.** *(14 Ekim, `ip/r3-a1-netlist`; ölçüm status.md'de)* Salt okunur. Girdi: kayıtlı proje, isteğe bağlı `nets=[...]`,
  `max_nets`, `include_power` (varsayılan özet). Kaynak: `pcbai/tools/engine.py` `saved_netlist` / `_netlist`
  (gerçek `kicad-cli` netlisti); yeni hesap yok. Çıktı biçimi:

  ```
  NET: +3V3  (6 pin, güç)
    - U1.8   VDD        STM32G431CBU6
    - C3.1   ~          100nF  dekuplaj?   ← yalnızca analiz varsa, "?" ile
  NET: I2C1_SDA  (3 pin)
    - U1.42  PB7        STM32G431CBU6
    - R4.2   ~          4k7
  ```

  - Pin adı ve parça değeri sembol/netlistten; **rol tahmini yalnızca RD-B2 analizi varsa** ve `?` işaretli.
  - Güç/toprak netleri üyeleri çoksa özetlenir (`GND: 41 pin, 18 parça`), istenirse açılır.
  - Revizyon SHA-256'sı ve netlist karması yanıtta; dosya değişince eski çıktı geçersiz.
  - Boyut sınırı: varsayılan 12 000 karakter; aşılırsa `truncated=true` ve kalan net sayısı. Sessiz kesme yok.
  - Dosya metni veridir: değer/alan metinleri satır sonu ve kontrol karakterinden arındırılır (istem enjeksiyonu).

  **Bitti:** Beş KiCad demosunda net ve pin sayısı `kicad-cli` netlistiyle birebir; truncation testi; kötü niyetli
  değer alanı (`"\nNET: FAKE"`) testi; MCP ve `/call` testleri. `review_snapshot` (RD-F1) bu çıktıyı kullanır.
  **Süre:** 2 gün. **Dal:** `ip/r3-a1-netlist`.

- [ ] **R3-A2 IR v1.1: tolerans ve `assert`.** Geriye uyumlu (v1 dosyası v1.1 olarak okunur).
  - `$defs/quantity` genişler: `{"nom": "10k", "tol": "1%"}`, `{"min": "3.0V", "max": "3.6V"}` veya mevcut
    sayı/metin. Birim çözümü mevcut `pcbai/ir/units.py`.
  - Yeni üst alan `asserts`: en çok 64 ifade, **kendi küçük ayrıştırıcımız** (eval yok, `ast` bile yok):
    `blocks.div1.vout within 3.3V +- 2%`, `rails.+3V3.current < 300mA`, `parts.R4.value in 2k2..10k`.
    Dilbilgisi: başvuru, karşılaştırma (`< <= > >= within in`), aralık, birimli sayı. Başka hiçbir şey.
  - `plan_circuit` her `assert`'i `hand_calc` ile **köşe analizi** yaparak değerlendirir (toleransların min/max
    kombinasyonu, en çok 2^8 köşe; fazlası `skipped_too_many_corners`). Sonuç: `pass/fail/not_evaluable` + köşe.
  - `spice_block_test` varsa aynı `assert` SPICE ile de değerlendirilir; iki sonuç ayrı alanlarda.

  **Bitti:** Şema testleri (geçerli/geçersiz 20 örnek); ayrıştırıcı bulanık testi (rastgele girdi çökme yok, eval
  yok); bölücü bloğunda ±1 % dirençle `vout within 3.3V +- 2%` geçer, ±5 % ile köşede kalır ve köşe raporlanır;
  docs/ir.md güncellendi. **Süre:** 4 gün. **Dal:** `ip/r3-a2-ir-tolerans`. **Bağımlılık:** yok.

- [ ] **R3-A3 Parametrik parça seçici (`find_parts`).** Salt okunur, aday üretir.
  - Girdi: `kind` (resistor|capacitor|inductor|diode|led), `value` + `tol`, `package`, `min_voltage`, `min_power`,
    `dielectric`, isteğe bağlı `profile` (RD-F6).
  - Kaynak sırası: (1) kullanıcı stok dosyası (R2/U1 jBOM adaptörü varsa), (2) yerel katalog önbelleği (RD-D5),
    (3) yalnızca KiCad kütüphanesindeki sembol+footprint (MPN'siz, `unsourced`). **Ağ isteği yalnızca kullanıcı
    onayıyla** (K18).
  - Çıktı: aday listesi, her aday için hangi koşulu hangi kaynağa göre sağladığı, sağlanamayan koşul açıkça.
    Değer E-serisine yuvarlanırsa yuvarlama ve yeni `assert` sonucu (R3-A2) gösterilir.
  - **Model hafızasından MPN kabul edilmez**; aday yoksa `no_candidate` + hangi koşulun elediği.
  - `replace_part` ile uygulanır; seçici kendisi yazmaz.

  **Bitti:** Stok dosyası fixture'ında 10 istek beklenen adayları veriyor; 0402'de 1 W isteği `no_candidate`
  + eleyen koşul; X7R/16 V isteği Y5V adayı döndürmüyor. **Süre:** 4 gün. **Bağımlılık:** U1 adaptörü yoksa yalnızca
  kaynak (3) ile çalışır, (1)/(2) testleri `skip` gerekçeli. **Dal:** `ip/r3-a3-parca-secici`.

### B. Tasarım bilgisi

- [ ] **R3-B1 Parça bilgi kaydı şeması.** `pcbai/parts/knowledge/` altında JSON şeması ve 20 başlangıç parçası.
  - Alanlar: MPN, paket, pin rolleri, `vdd_range`, `io_levels` (VIL/VIH/VOL/VOH), `abs_max`, `i2c_addresses`
    (sabit + adres pini ile seçilebilenler), `bus_max_hz`, `required_externals` (dekuplaj, pull-up, kristal yükü),
    `init_notes`. Her sayısal alan RD-D1 SpecValue: `{value, unit, page, quote, source_sha256}`.
  - Başlangıç listesi P1–P3 referans tasarımlarındaki parçalardan seçilir (STM32G431CBU6, AMS1117-3.3/AP2112K,
    BME280, SSD1306, 24C02, MCP2551/TJA1051, CH340C, USB-C alıcı, MOSFET'ler…). **Değerler datasheet'ten,
    sayfa ve alıntıyla**; boardsmith verisi kullanılmaz.
  - RD-D2 güven kapısı: alıntısı doğrulanmayan alan `heuristic`.
  - RD-B4 kuralları bu kaydı okur; kayıtta olmayan parça için kural `not_evaluable` döner, atlanmaz.

  **Bitti:** 20 parça şemadan geçiyor; RD-D2 alıntı doğrulaması 20/20 parçada çalıştırıldı ve sonuç status.md'de;
  bir sahte alıntı reddediliyor. **Süre:** 4 gün (veri girişi dahil). **Dal:** `ip/r3-b1-bilgi`.
  **PLAN bağı:** İP-2.7, RD-D1.

### C. Ajan döngüsü ve doğrulama

- [ ] **R3-C1 Düzeltme döngüsü bütçesi (`fix_loop` sözleşmesi).** PcbAi döngüyü kendisi çalıştırmaz; istemciye
  durumu ve durma kararını verir.
  - Yeni salt okunur araç `loop_status(loop_id)`: tur sayısı, her turda açılan/kapanan `finding_id`'ler,
    **yinelenen bulgu** (kapanıp yeniden açılan veya 2 tur değişmeyen), kalan bütçe.
  - Önizleme araçları isteğe bağlı `loop_id` alır. Bütçe (varsayılan 5 tur, profilde değişir) dolunca veya aynı
    bulgu kümesi 2 tur tekrarlanınca önizleme `loop_exhausted` ile reddedilir; kullanıcı açıkça yeni döngü başlatır.
  - VS Code iş panelinde döngü turu ve durma nedeni görünür.

  **Bitti:** Sentetik senaryo: ERC hatasını düzeltip başka hata açan ajan 2. turda `repeating` alıyor; 5 turda
  bütçe doluyor; checkpoint geri yüklemesi döngüyü sıfırlamıyor (aynı `loop_id`). **Süre:** 3 gün.
  **PLAN bağı:** RD-F5 ölçülen kapılar, U8 agent döngüsü. **Dal:** `ip/r3-c1-dongu`.

- [ ] **R3-C2 Gereksinim dosyası ile SPICE doğrulaması (`verify_requirements`).** `start_job` uyumlu.
  - Girdi: IR `asserts` (R3-A2) veya ayrı `requirements` listesi: `{id, probe, analysis, measure, limit}`.
    `measure` ∈ `dc_value|ripple_pp|rise_time|f_3db|phase_margin|max|min|rms`.
  - Mevcut ngspice işçisi ve güvenlik sınırları aynen (S5). Testbench üretimi mevcut `pcbai/blocks/spice.py`.
  - Çıktı: gereksinim başına `pass/fail/not_measured` + ölçülen değer + sınır; dalga biçimi CSV ve SVG
    `.pcbai-state/` altında; `manifest.json` her dosyanın SHA-256'sı, ngspice sürümü, model kimlikleri, IR karması.
  - Ölçüm noktası netlistte yoksa `not_measured`, sessiz `pass` yok.

  **Bitti:** Üç pasif tarifin altı varyantında el hesabı ile aynı yönde sonuç; bilerek yanlış sınırlı gereksinim
  `fail`; olmayan prob `not_measured`; manifest yeniden koşuda bayt eşit (zaman damgası hariç).
  **Süre:** 4 gün. **Bağımlılık:** R3-A2 (assert yolu için; liste yolu bağımsız). **PLAN bağı:** U6, İP-4.1.
  **Dal:** `ip/r3-c2-gereksinim`.

### D. Şematik ve kart düzeni

- [ ] **R3-D1 Hiyerarşik sayfa araçları.** Önizlemeli `add_sheet`, `add_sheet_pin`, `add_hier_label`.
  - Mevcut `pcbai/sch/edit.py` yazma yolu, kilit/revizyon/checkpoint kuralları aynen.
  - `add_block` isteğe bağlı `as_sheet=true`: blok kendi alt sayfasına, dış netler sayfa pini olarak yazılır
    (easyeda-copilot "sayfaları fonksiyonel bloklara ayır" fikri).
  - Paylaşılan şematik dosyasına yazma engeli korunur; aynı alt sayfa iki kez örneklenirse açık hata (çoklu örnek
    desteği bu pakette yok).
  - Kabul ERC kök şematikten, bağlantı gerçek netlistten ölçülür.

  **Bitti:** Bölücü bloğu alt sayfa olarak eklendiğinde kök ERC temiz, netlistte üyeler beklenen; sayfa pini ↔
  hiyerarşik etiket adı uyuşmazlığı ERC'de yakalanıyor; geri yükleme bayt eşit. **Süre:** 4 gün.
  **Dal:** `ip/r3-d1-hiyerarsi`.

- [ ] **R3-D2 Şematik görsel düzeltme döngüsü.** `add_block`/`apply_circuit` adayı için:
  render (mevcut `sch_render`) → RD-E1 okunurluk puanı → **kural tabanlı** yeniden yerleşim önerisi
  (gövde çakışmasını kaldır, telleri kısalt, güç sembolüne geç) → yeni aday. En çok 3 tur; puan iyileşmezse durur.
  PcbAi görüntü yorumlamak için LLM çağırmaz; görüntü ajana `review_image` olarak verilir, ajanın önerisi yine
  önizleme aracından geçer. **Bitti:** Bilerek dağınık üretilmiş 5 aday için puan monoton iyileşiyor veya döngü
  gerekçeyle duruyor. **Süre:** 3 gün. **Bağımlılık:** RD-E1. **Kesilebilir.** **Dal:** `ip/r3-d2-sema-duzen`.

### E. Ajan iş akışı

- [ ] **R3-E1 `pcbai-design` skill paketi.** `skills/pcbai-design/` (Claude Code ve Codex için aynı içerik,
  `SKILL.md` + alt belgeler). Akış:
  1. **Gereksinim mülakatı** → projede `SPEC.md` (giriş gerilimi, akım, arayüzler, boyut, katman, bütçe, üretici).
     SPEC alanları IR `requirements` ile birebir; skill IR iskeletini de yazar.
  2. **Mimari** → bloklar ve raylar, güç ağacı; `plan_circuit` ön denetimi.
  3. **Parça** → `find_parts` (R3-A3), `verify_part`; MPN yalnızca araçtan.
  4. **Şematik** → `add_block`/`add_symbol`/`connect`, her adım önizle → uygula.
  5. **İnceleme** → `readable_netlist`, `design_checks`, `verify_requirements`, ERC; RD-F4 karşıt inceleme biçimi.
  6. Her aşama sonunda ölçülen kapı (RD-F5); ajan "geçti" yazamaz, araç sonucu alıntılanır.

  Skill dosyaları kod yürütmez; yalnızca PcbAi MCP araçlarını çağırır. **Bitti:** P1 (basit pasif) ve P2 (LDO +
  I²C sensör) senaryoları skill ile baştan sona koşuldu, döküm `.pcbai-state/` altında, sonuç status.md'de;
  hangi adımda insan müdahalesi gerektiği yazıldı. **Süre:** 3 gün. **Bağımlılık:** R3-A1, R3-A3 (yoksa adım 3
  `search_parts` ile). **Dal:** `ip/r3-e1-skill`.

### F. Test ve kıyas

- [ ] **R3-F1 VS Code uçtan uca arayüz testi.** Mevcut Chromium testlerinin yetmediği akışlar için (işaret paneli,
  önce/sonra aday paneli, iş durumu). circuit-mcp ya da doğrudan Playwright **yalnızca geliştirici makinesinde**;
  CI'da yoksa `skip` gerekçeli. **Bitti:** Üç akış (işaret ekle/tamamla/sil, autoroute önizle→uygula, iş iptal)
  otomatik koşuyor. **Süre:** 2 gün. **Kesilebilir.** **Dal:** `ip/r3-f1-e2e`.

- [ ] **R3-F2 Analog blok kıyas seti.** AICircuit'in basit devrelerinden (ortak kaynaklı yükselteç) fikir alınarak
  kendi küçük setimiz: 10 spesifikasyon → blok parametresi görevi; değerlendirme `verify_requirements` ile.
  Blok olgunluğunu 0'dan yükseltmek için ölçüt. **Süre:** 3 gün. **Kesilebilir.** **Bağımlılık:** R3-C2.

---

## 5. Sıra ve takvim

| Sıra | Paket | Süre | Bağımlılık | Kesilebilir |
|---|---|---|---|---|
| 1 | R3-0 kaynak incelemesi | 2 | — | hayır |
| 2 | R3-A1 `readable_netlist` | 2 | — | hayır |
| 3 | R3-A2 IR tolerans + assert | 4 | — | hayır |
| 4 | R3-B1 parça bilgi kaydı | 4 | RD-D1 şeması (yoksa SpecValue bu pakette tanımlanır) | hayır |
| 5 | RD-B4 ek maddeleri (bölüm 3) | +2 | R3-B1 | hayır |
| 6 | R3-C1 döngü bütçesi | 3 | — | hayır |
| 7 | R3-C2 `verify_requirements` | 4 | R3-A2 | hayır |
| 8 | R3-A3 parça seçici | 4 | U1 kısmen | hayır |
| 9 | R3-D1 hiyerarşik sayfa | 4 | — | hayır |
| 10 | R3-E1 skill paketi | 3 | A1, A3 | hayır |
| 11 | R3-D2 görsel düzeltme | 3 | RD-E1 | **evet** |
| 12 | R3-F1 e2e | 2 | — | **evet** |
| 13 | R3-F2 kıyas seti | 3 | R3-C2 | **evet** |

Zorunlu yeni paketler (R3-0, A1, A2, A3, B1, C1, C2, D1, E1) **30 gün**; bölüm 3 ekleri **+6 gün**; toplam
zorunlu **36 gün**. Kesilebilir paketler (D2, F1, F2) **8 gün**.

Paralellik: 2–3 (A1, A2) ve 6 (C1) birbirinden bağımsız; ayrı worktree'lerde aynı anda yürüyebilir.

---

## 6. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| boardsmith fikri ile AGPL kodu arasında sınır bulanıklaşır | Lisans ihlali | Depo açılmaz; R3-0 inceleme listesinde yok; parça verisi yalnızca datasheet'ten |
| `assert` dili büyür, ikinci bir programlama dili olur | Güvenlik ve bakım | Dilbilgisi bu belgede sabit; genişleme ayrı karar (K22) |
| Parça bilgi kaydında elle girilen değer yanlış | Yanlış "geçti" | RD-D2 alıntı kapısı; kayıtsız/kanıtsız alan `heuristic` ve WARN üstüne çıkamaz |
| `readable_netlist` büyük kartta bağlamı doldurur | Ajan yanlış özetler | Sert sınır + `truncated`; net filtresi; güç netleri özet |
| Skill paketi araçlardan önce yazılır, var olmayan araç çağırır | Kırık akış | R3-E1 en son; skill testinde araç adları `tools/list` ile doğrulanır |
| Döngü bütçesi kullanıcıyı gereksiz durdurur | Kullanım zorluğu | Bütçe profilde; durma nedeni ve "yeni döngü" düğmesi görünür |
| README'deki iddia kaynakta yok | Boşa iş | R3-0 önce; iddia kaynakta yoksa paket kapsamı daraltılır |

---

## 7. Kararlar (kullanıcı)

- **K21 İsim çakışması.** `Corning-AI/PCBai` (MIT, kod yok) ile ad benzerliği. Seçenekler: (a) şimdilik bir şey yapma,
  PyPI/Marketplace adlarını şimdi rezerve et; (b) yeniden adlandırma değerlendirmesi. **Öneri:** (a).
- **K22 `assert` dilinin kapsamı.** Bölüm R3-A2'deki dilbilgisi yeterli mi, yoksa ifade (`vout = vin * R2/(R1+R2)`)
  de gerekir mi? **Öneri:** yalnızca karşılaştırma; ifade hesabı blok tariflerinde kalır.
- **K23 Skill paketinin yeri.** Bu depoda `skills/` mı, ayrı `embedded-software-skills` deposunda mı?
  **Öneri:** bu depoda; araç sürümüyle birlikte değişir.
- **K24 ESP32 hedefi.** circuitiny/boardsmith ESP32 odaklı; PLAN STM32 odaklı. **Öneri:** şimdilik hayır.

---

## 8. İlk adım

R3-0 kaynak incelemesi (`ip/r3-0-kaynak`) ile R3-A1 `readable_netlist` (`ip/r3-a1-netlist`) aynı anda ayrı
worktree'lerde başlayabilir; ikisi de hiçbir karara bağlı değil. K21–K24 bu sürede kullanıcıdan alınır.
Her paket sonunda: test + ruff sonucu ve sınırlar `docs/status.md`'ye, ilerleme `docs/plan-eksikler.md`'ye.
