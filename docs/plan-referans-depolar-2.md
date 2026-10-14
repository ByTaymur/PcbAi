# Plan — referans depolar, ikinci dalga (R2)

Tarih: 13 Ekim 2026, güncelleme 14 Ekim · Durum: **U0, R2-A1 ve R2-A2 tamam;
ölçümler ve sınırlar status.md'de** · Başlangıç ağacı: `main/937b0bf`, çekirdek 0.1.22, VS Code 0.1.18 · Bağlı:
[U0–U8 planı](plan-uretim-dogrulama.md), [RD planı](plan-referans-depolar.md), [PLAN.md](../PLAN.md),
[eksikler](plan-eksikler.md), [uygulama durumu](status.md), [limits.md](limits.md)

Bu belge yedi yeni açık kaynak depodan PcbAi'ye **neyin, hangi yolla, hangi RD dalgasında** alınacağını ve her işin ne
zaman "bitti" sayılacağını söyler. RD planının yerine geçmez; onun paketlerini (RD-B4, B5, C1–C3, D5, F6, G2, H2) besler
ve dört yeni alan açar: yoksayılan kural kapısı, bulgu muafiyeti, kullanıcı stoğu ile parça atama, serigrafi düzeni.
Uygulayan ajan her paketi bitirince ölçülen sonucu status.md'ye yazar ve buradaki kutuyu işaretler.

**İki belgenin işbölümü.** Aynı yedi depo için [U0–U8 planı](plan-uretim-dogrulama.md) üst çerçevedir: mimari, ortak
adaptör sözleşmesi, paket durumları (`draft…released`), devre davranışı (U6) ve STM32/sistem doğrulaması (U7).
Bu belge (R2) uygulanacak **iş paketlerinin** ayrıntısıdır: dosyalar, fixture'lar, süre, kesme sırası. Bir iş iki
belgede geçiyorsa kabul ölçütü daha sıkı olanıdır; eşleme bölüm 1.2'dedir. Yeni iş yalnızca R2'ye paket olarak eklenir.

---

## 0. Özet

- **U0-F1 ile ölçülen açık kapatıldı:** Eski PcbAi, ecc83 kopyasında clearance error iken **69**,
  ignore iken **0** bulguya rağmen eksik kapsam bildirmiyordu. Çekirdek 0.1.23, proje severity
  ayarları ve native ignored_checks birleşimini okur; zorunlu ignore artık `checks_incomplete`
  ve CLI exit 2 üretir ([R2-A1](spikes/R2-A1.md)). Üretim profili yükseltmesi R2-B2'de kalır.
- **Üretim paketi eksikleri (ölçüldü):** `export_fab` bugün yalnızca Gerber + delik yazıyor; pasta katmanı, IPC-D-356
  netlisti, konum (CPL) ve BOM yok, `production_verified=false`. Yerel `kicad-cli` 10.0.4'te `ipcd356`, `ipc2581`,
  `odb`, `pos`, `stats` alt komutları mevcut (13 Ekim'de `kicad-cli pcb export --help` ile görüldü).
- **Yeni yetenekler:**
  - Kullanıcının kendi stok dosyasıyla genel değer → gerçek parça (LCSC/MPN) atama ve BOM alan denetimi (jBOM).
  - Tek "üretici profili": DRC alt sınırları + BOM/CPL biçimi + DFM kural seti (Astra, pcb-dfm, jBOM).
  - Montaj kapısı: BOM ↔ CPL ↔ kart ↔ şematik çelişkisi varsa üretim yok (hauksbee, BOM-CPL eklentisi).
  - İkinci bağımsız DFM denetçisi Gerber üzerinden, ayrı süreçte (pcb-dfm).
  - Yığın farkındalıklı yerleşim kuralları: dönüş yolu, anahtarlama düğümü, fark çifti (pcb-inspector).
  - Bulgu muafiyeti: zorunlu gerekçe + **son kullanma tarihi**, gizlenmez (hauksbee).
  - Ajanın kendi görme yeteneği için inceleme görüntüleri; PcbAi hiçbir LLM API'sini çağırmaz (pcb-inspector fikri).
- **İlke korunur:** Dış araç önce KiCad'in kendi sayılarını yeniden üretir (RD-A4). Çöken veya atlanan kontrol "geçti"
  sayılmaz (RD-A2). Görsel/sezgisel sonuç kapı açmaz.
- **Süre:** Toplam **55 iş günü**; **10 günü kesilebilir** (S13 olumsuzsa 13). RD paketleriyle örtüşen 4 gün iki kez
  sayılmaz; RD planına **net zorunlu ek yük 38–41 gün** (~8 hafta-ajan), RD dalga 2–6'ya dağılır (bölüm 6).

---

## 1. İncelenen depolar: kaynak kodda ne var?

Klonlar 13 Ekim 2026'da `--depth 1` ile alındı ve yalnızca okundu; hiçbir kod çalıştırılmadı, hiçbir bağımlılık
kurulmadı. "Kaynakta" yazan satırlar dosyadan doğrulandı. "README" yazanlar deponun kendi iddiasıdır ve kanıt sayılmaz.

| Depo (commit, tarih) | Lisans | Kaynakta doğrulanan | PcbAi'de kullanım |
|---|---|---|---|
| **takzen/pcb-inspector** (`d29e120`, 22 Eyl 2026) | MIT | Python ~4,5k satır. Kendi s-expr okuyucusu ve kart modeli (`pcb_model.py` 827 satır); beş kural: `HEUR-DEC-001` dekuplaj mesafesi (karşı yüzde kart kalınlığı eklenir, besleme pini **şematik pin adından** tanınır), `HEUR-PWR-001` iz genişliği (kendi net sınıfına göre uyarı, kılavuza göre öneri), `HEUR-DIFF-001` fark çifti kayması (yay ve via geçişleri dahil; yalnızca hızlı arayüz adı kritik olabilir), `HEUR-DCDC-001` anahtarlama düğümü (SW/LX pini **veya** endüktör–dönüştürücü topolojisi; yalnız ad yetmez), `HEUR-GND-001` dönüş yolu (yalnızca **komşu** katmandaki GND düzlemi; katman sırası dosyadaki yığından). `kicad-cli pcb render` görüntüsünü barındırılan görme modeline gönderen katman, MCP sunucusu, GitHub Action. Bağımlılık: shapely, pydantic, typer, mcp | RD-B5 kural fikirleri ve ikinci uygulama (R2-D); görsel inceleme fikri (R2-E1) |
| **NextBuilder/KiCad-Astra** (`6102d86`, 11 Eyl 2026) | MIT | Python ~5k satır, KiCad 10.0.6 IPC API (`kicad-python 0.8.0`). Deterministik referans etiketi yerleşimi (`labels.py`: yükseklik, çizgi, aralık, ızgara; kilitli/gizli alan korunur; son geometri kapısı KiCad DRC). Üretim profili (`manufacturing.py`): kopyadaki kurallar yalnızca **sıkılaştırılır**, devre dışı DRC kontrolü varsa ve DRC kalemi kalırsa dışa aktarım **reddedilir**. Yerel A* tek bağlantı rotacısı, OpenAI ile yerleşim önerisi | R2-A1 (yoksayılan kural), R2-B2 (profil), R2-F1 (serigrafi). Rotacı ve LLM yerleşimi alınmaz (K5, motorlar var) |
| **mfgs-us/pcb-dfm** (`b94d0f7`, 10 Ağu 2026) | **Apache-2.0** | Gerber ZIP üzerinde JSON şemalı **108 kontrol tanımı** (`check_data/checks/*.json`) + Python uygulamaları; üretici kural setleri: `default`, `conservative_2layer`, `jlcpcb_2layer`, `jlcpcb_4layer`, `oshpark`, `pcbway`, `advanced_hdi`. Girdi bağdaştırıcıları: IPC-356, IPC-2581, ODB++, KiCad, BOM. "Çöken kontrol `fail` olur, uygulaması olmayan `not_applicable`" kuralı. Gerber için gerbonara (1.5.x); G85 yuvalı delikleri gerbonara reddediyor, kendi kodları işliyor. GitHub Action. README: ağ listesi/yığın girdisi olmadan bazı kontroller sezgisel veya yer tutucu | Ayrı süreçte ikinci DFM denetçisi (R2-B4). **Kod alınmaz (K15)** |
| **hauksbee-dev/hauksbee** (`9ec0c21`, 11 Eki 2026) | Kaynak **Apache-2.0** (+ MIT evalexpr); **varsayılan binary GPL-3.0**, `permissive` binary Apache-2.0 (`COMPLIANCE.md`, U0) | Rust, 14 crate; KiCad/Eagle/Altium/IPC-2581/ODB++/Gerber+IPC-D-356 girdisinden tek elektriksel IR; USB-C CC sınıflandırması, boot strap, I²C yükü, geri besleme yolu, akım kapasitesi, kahverengi düşüş geçici durumu, MCU firmware eş-simülasyonu, git geçmişinden "hatalı/düzeltilmiş" regresyon çiftleri. **Muafiyet: gerekçe ve son kullanma tarihi zorunlu, muaf bulgu gizlenmez** (LIMITATIONS.md). `model_coverage` kapısı (bağlanan aktif IC oranı). MCP araçları: `analyze_board`, `run_checks`, `model_coverage`… Windows x64 yalnızca beta "permissive" yapı. README: yedi kartta %99,7–100 net bölümleme uyumu | Fikirler: R2-A2 muafiyet, R2-A3 kapsam oranı, R2-B3 IPC-D-356 yetkisi, R2-B5 montaj kapısı, R2-H1 regresyon çiftleri. Ayrı program spike'ı kesilebilir (R2-H2). **Kod alınmaz (K15)** |
| **plocher/jBOM** (`8e98cd3`, 10 Ağu 2026) | MIT | Python ~13k satır servis katmanı. Genel değerli şematik ("10k 0603") + kullanıcı **stok dosyası** (CSV/XLSX/Numbers) → BOM/CPL; `sophisticated_inventory_matcher.py` (1160 satır), `audit_service.py` (1468 satır: alan taksonomisi, `QUALITY_ISSUE` satırları, onarım CSV'si → `annotate`), sekiz tedarikçi/üretici profili (jlc, pcbway, seeed, digikey, mouser, farnell, newark, generic), `rotation_correction_service.py` + `transformations.csv` (55 satır, Fabrication-Toolkit'ten MIT ile alınmış), LCSC/Mouser arama, veri sayfası URL hijyeni | R2-C1 alan denetimi, R2-C2 stok eşleştirme, R2-C4 BOM biçimleri; değer normalleştirme kodu atıfla alınabilir |
| **prrvchr/KiCad-BOM-CPL-Plugin** (`2fc86b7`, 4 Eyl 2026) | **MPL-2.0** | Tek dosya, 389 satır, Eeschema BOM eklentisi. `Supplier`/`SupplierRef` (veya `LCSCRef`, `JLCPcbRef`) alanlarıyla tedarikçi başına ayrı BOM; isteğe bağlı `Quantity` (0 = BOM dışı) ve bileşen başına `Rotation` düzeltmesi; adet çarpanı (N kart) | Yalnızca fikir (R2-B5, R2-C4); kod basit, temiz yazılır |
| **FOSSEE/eSim** (`1a25a46`, 27 Eyl 2026, sürüm 2.6) | **GPL-3.0** | KiCad XML netlist → ngspice dönüştürücü, **785** alt devre (74xx/CD4000 dijital entegreler dahil), cihaz model kütüphanesi (diyot, transistör…), GHDL/Verilator ile karma sinyal (NGHDL), ngspice → Modelica, LTspice/PSpice → KiCad dönüştürücü, sky130/IHP PDK'ları. 14.351 dosya; Windows'ta uzun yol nedeniyle çalışma ağacı tam açılmadı (git nesnelerinden okundu) | Yalnızca kullanıcının kurduğu model kütüphanesine **yol** (R2-G1) ve spike (R2-G2). Kod ve model dosyası paketlenmez |

### 1.1 Mevcut PcbAi ile örtüşme

| Konu | Bugün PcbAi (ölçülen) | RD'de planlı | Bu plan ne ekler |
|---|---|---|---|
| ERC/DRC/parite | Var; `--severity-all`, hariç tutulanlar sayılıyor | — | `ignore` kural kapısı (R2-A1) |
| Bulgu şeması, manifest | Var (RD-A1/A2) | — | Muafiyet (R2-A2), kapsam oranı (R2-A3) |
| Üretim çıktısı | Gerber + Excellon, manifest SHA | RD-C1–C3 | Pasta, IPC-D-356, CPL ham çıktısı, stats (R2-B1); profil (R2-B2); montaj kapısı (R2-B5) |
| Bağımsız Gerber doğrulaması | Yok | RD-C2 (kendi okuyucu), RD-I2 (pygerber) | Üçüncü bağımsız kaynak: IPC-D-356 (R2-B3) ve pcb-dfm (R2-B4) |
| Parça | Yerel KiCad kütüphane indeksi, `verify_part` | RD-D5 katalog, İP-2.5 jlcparts | Kullanıcı stoğu (R2-C2), alan denetimi (R2-C1), alan yazımı (R2-C3) |
| Yerleşim denetimi | DRC + motor metrikleri | RD-B5 (kicad-happy `cross_verify`) | İkinci uygulama ve kıyas (R2-D1/D2) |
| SPICE | KiCad ngspice işçisi, pasif blok testleri | RD-B3, B7 | Model kütüphanesi yolu ve kapsam (R2-G1, R2-A3) |
| Görsel inceleme | Etkileşimli SVG/3B görünüm | — | Ajanın görmesi için sabit görüntü seti (R2-E1) |

### 1.2 U0–U8 ile eşleme

| U paketi ([plan](plan-uretim-dogrulama.md)) | R2 paketleri | Not |
|---|---|---|
| U0 kaynak envanteri | Bölüm 1, S13/S14/S16'nın ilk ölçümü | **Tamam** ([U0](spikes/U0.md)); kalibrasyon ve elle etiket S13/S14'te |
| U1 BOM, envanter, parça | R2-C1, R2-C2, R2-C3 | MPN ve SKU ayrı alan (U1); eşleşme parça onayı değildir |
| U2 CPL/POS, şablonlar | R2-C4, R2-B5 dönüş kısmı, RD-C3 | U2'nin 0/90/180/270°, iki yüz ve origin fixture'ları R2-B5 kabulüne eklenir |
| U3 Gerber/Excellon DFM | R2-B1, R2-B3, R2-B4 | U0-F2: skor ve çıkış kodu kapı açmaz |
| U4 sıkı kapı ve yayın | R2-A1, R2-A2, R2-B2, R2-B5, RD-C1 | Paket durumları ve manifest hashine bağlı onay U4'te; muafiyet biçimi R2-A2 |
| U5 bağımsız tasarım/EMC | R2-D1, R2-D2, R2-E1, bölüm I | U0-F3: PCB/net/stackup ön koşulu adaptörde doğrulanır |
| U6 devre davranışı, modeller | R2-G1, R2-G2, R2-A3 | Güç katı, köşe/tolerans testleri U6'nın; R2 yalnız model yolu ve kapsam oranını verir |
| U7 STM32/sistem | R2-H2 (yalnız spike) | U0-F4: hauksbee G4/F4'te ADC/DMA/clock eksik; U7 ayrı plan olarak kalır, R2 süresine dahil değil |
| U8 yerleşim/finishing | R2-F1 | Rota motorları ölçümsüz değişmez (K5) |

**Süre birleşimi.** U planındaki dalga tahminleri (U1–U6 ve U8 için 26–45 gün) ile R2'nin 55 günü **aynı işi** sayar;
toplanmaz. Uygulama takibi R2 paket kutularıyla yapılır; U7 ve fiziksel/EMC kabulü R2 dışında ayrı tahminlenir.

---

## 2. Lisans ve kod alma kuralları

RD planı bölüm 2 aynen geçerlidir. Bu dalgaya özgü satırlar:

| Kaynak | Kural |
|---|---|
| pcb-inspector, KiCad-Astra, jBOM (MIT) | Kod alınabilir: dosya başında depo, commit, özgün telif; `NOTICE` satırı; `scripts/check_licenses.py` taraması. **Çekirdeğe yeni bağımlılık eklenmez** (bugün yalnızca `jsonschema`); shapely/pydantic gerektiren kod ya ayrı süreçte çalışır ya da bağımlılıksız yeniden yazılır (K23) |
| jBOM `transformations.csv` | Fabrication-Toolkit'ten MIT ile alınmış veri. Alınırsa iki kaynak da `NOTICE`'e yazılır; PLAN'daki kicad-jlcpcb-tools tablosuyla satır satır kıyaslanır |
| pcb-dfm, hauksbee (kaynak Apache-2.0; hauksbee varsayılan binary GPL-3.0) | K15 gereği kod alınmaz. **Ayrı program** olarak kullanım K22 (Apache yapı) veya K21 (GPL yapı) desenine bağlıdır: kullanıcının kurduğu yalıtılmış ortam, yol yalnızca yapılandırmadan, `shell=False`, zaman aşımı, PcbAi paketine girmez |
| KiCad-BOM-CPL-Plugin (MPL-2.0) | Dosya düzeyinde copyleft. Kod alınmaz; fikirler temiz yazılır (iş küçük) |
| eSim (GPL-3.0) | Ayrı program/veri. Model ve alt devre dosyaları paketlenmez; kullanıcı kendi kurulumunun yolunu verir (K26). Her model dosyasının kendi kaynağı/lisansı bilinmiyorsa sonuçta `license_unknown` uyarısı görünür |
| Üretici kural sayıları (JLC, PCBWay, OSHPark) | Üreticinin kendi sayfasına tarihle atıf; depodaki JSON yalnızca karşılaştırma kaynağıdır. Profil "üreticiyle doğrulayın" etiketi taşır |

---

## 3. Mimari etkisi

```
pcbai/verify/
  severities.py    R2-A1: .kicad_pro rule_severities + ERC ayarı okuyucu, ignore → checks_incomplete
  waivers.py       R2-A2: gerekçe + bitiş tarihli muafiyet, finding_id ile eşleşir
  coverage.py      R2-A3: model/analiz kapsam oranı (aktif parça başına bound/unbound)
  layout/          R2-D2: yığın farkındalıklı kurallar (bağımlılıksız geometri)
  adapters/pcb_dfm.py, adapters/pcb_inspector.py   R2-B4, R2-D1: ayrı süreç bağdaştırıcıları
pcbai/fab/
  profiles/*.json  R2-B2: üretici profili (DRC alt sınırları, pasta, BOM/CPL biçimi, DFM kural seti kimliği)
  package.py       R2-B1: tam üretim paketi + manifest rolleri
  assembly.py      R2-B5: BOM ↔ CPL ↔ kart ↔ şematik montaj kapısı
  rotation.py      RD-C3 + R2-B5: dönüş düzeltmesi (tablo + bileşen alanı)
pcbai/parts/
  fields.py        R2-C1: alan taksonomisi ve değer normalleştirme
  inventory.py     R2-C2: kullanıcı stok dosyası okuyucu ve eşleştirici
pcbai/sch/edit.py  R2-C3: set_fields yazıcısı (RD-A3 geri okumalı)
pcbai/pcb/silk.py  R2-F1: referans etiketi düzeni
pcbai/sim/models.py R2-G1: model kütüphanesi indeksi
```

**Akış (üretim):** `export_fab(profile)` → kopyada profil kuralları + DRC (R2-B2) → paket (R2-B1) → montaj kapısı
(R2-B5) → bağımsız doğrulama (RD-C2 kendi okuyucu, R2-B3 IPC-D-356, R2-B4 pcb-dfm, RD-I2 pygerber) → `fab_gate`
(RD-C1) → manifest. Her adım `checks_run` satırı üretir; biri `skipped/failed` ise paket `not_ready`.

**Yeni MCP araçları (taslak, adlar uygulamada kesinleşir):** `audit_fields`, `match_inventory`, `set_fields`,
`manage_waivers`, `review_views`, `arrange_refdes`; `export_fab` ve `check` yeni parametre alır (`profile`,
`assembly`). Yazan her araç preview → apply, kontrol noktası ve RD-A3 geri okumasıyla çalışır.

---

## 4. İş paketleri

Her paket ayrı dalda ve **ayrı `git worktree`**'de yürür (`ip/r2-a1-ignore` gibi); bitince main'e alınır ve worktree
kaldırılır. Bir ajan uygular, ayrı bir ajan bağımsız denetler (AGENTS.md). Süreler tek uygulayan ajan içindir.
Her paketin ilk adımı ilgili deponun **sabitlenmiş commit'teki** kaynağını yeniden okumaktır; bu belgedeki satır
numaraları ve dosya adları 13 Ekim klonuna aittir.

### A. Güven açıkları (önce bunlar)

- [x] **R2-A1 Yoksayılan kural kapısı** (çekirdek 0.1.23; [ölçüm ve sınırlar](spikes/R2-A1.md), son takım [status.md](status.md)). KiCad-Astra fikri; kod alınmadı.
  - `.kicad_pro` içindeki `board.design_settings.rule_severities` ve `erc.rule_severities` okunur. `ignore` değerli
    her kural `checks_run` satırına `status=skipped, reason=rule_ignored_in_project` olarak yazılır.
  - Kapsamın zorunlu kuralı (ör. `clearance`, `shorting_items`, `unconnected_items`, `pin_not_connected`) ignore ise
    sonuç `verified=checks_incomplete` olur; `check` CLI çıkış kodu 2. Zorunlu olmayanlar uyarı olarak listelenir.
  - Profil kapsamında (R2-B2) kopyada ignore → error yükseltilmiş ikinci DRC isteğe bağlı koşulur; kullanıcı dosyası
    değişmez. Ölçüm: aynı kartta orijinal ve yükseltilmiş DRC farkı.
  - **Ölçüldü (U0-F1):** KiCad 10.0.4 `--severity-all` raporunda ignore yapılmış kural bulgu üretmiyor (69 → 0);
    raporun `ignored_checks` listesinde `clearance` görünüyor. Uygulama hem `.kicad_pro`'yu hem bu listeyi okur;
    iki kaynağın birleşimi kullanılır, birinde görülen ignore kapsamdan düşmez. Eksik/bozuk native
    alan `invalid_report`; bozuk proje ayarı `invalid_project_settings`. U0'nun 69 → 0 ölçümü
    başlangıç kanıtıdır; depodaki küçük #17 fixture ayrı ERC/DRC ve CLI regresyonudur.
  - **Bitti:** Hata kataloğu #17 (bölüm 5) yakalanıyor; temiz projede davranış değişmiyor; ERC tarafı ayrıca test.
  - **PLAN bağı:** 5.10 çıktı kapısı, RD-A2. **Süre:** 2 gün. **Kesilmez.**
- [x] **R2-A2 Bulgu muafiyeti** (çekirdek 0.1.24; [rapor ve sınırlar](spikes/R2-A2.md), hauksbee waiver fikri; kod alınmadı).
  - Proje kökünde `pcbai-waivers.json`: `{finding_id, reason, owner, expires (ISO tarih), created}`. Gerekçesiz veya
    tarihsiz satır reddedilir; süre üst sınırı yapılandırılır (öneri 90 gün).
  - Muaf bulgu **gizlenmez**: sonuçta `waived` listesinde, gerekçesiyle görünür. Süresi dolan muafiyet bulguyu otomatik
    olarak etkinleştirir ve `waiver_expired` uyarısı verir. Eşleşmeyen (yetim) muafiyet ayrıca listelenir.
  - Kontrolü toptan kapatmak muafiyet değildir; muafiyet tek `finding_id`'ye bağlanır. Dosya yazımı preview/apply ile.
  - `check` çıkış kodu: tüm aktif bulgular muafsa 0, ama özet satırında muaf sayısı ve en yakın bitiş tarihi yazar.
  - **Bitti:** Gerekçesiz satır reddi, süre dolumu (sabit UTC günle test), yetim muafiyet ve `finding_id` değişince
    muafiyetin düşmesi testli. Son hedef takım 41 test/40 geçti/1 symlink skip; gerçek CLI 0/1/2 ölçüldü.
    Muafiyet yalnız toplu check'te; edit gates ve ham rapor korunur. UI ve yan dosya restore aracı kapsam dışı.
    **PLAN bağı:** İP-6.5 panel, RD-A1. **Süre:** 2 gün.
- [x] **R2-A3 Kapsam oranı** (0.1.25; [ölçüm/sınırlar](spikes/R2-A3.md), hauksbee fikri; kod alınmadı).
  - SPICE ve analiz sonuçları, aktif bileşenlerin (IC, transistör, regülatör) kaçının modellendiğini **referansla**
    döndürür: `coverage: {bound: [...], unbound: [...], ratio}`. Bağlı ağda olup modellenemeyen ayrı gösterilir.
  - Kapsam kapısı isteğe bağlıdır (`min_coverage`); bütün fiziksel bileşenlerin oranı eşik
    altında ise `checks_incomplete`; aktif oran ayrıca görünür, aktif yoksa null.
  - **Bitti:** Pasif blok testlerinde oran 1,0; modeli olmayan op-amp eklenince `unbound` listesinde. **Süre:** 1 gün.

### B. Üretim paketi ve bağımsız doğrulama (RD-C'nin genişlemesi)

- [x] **R2-B1 Tam ham üretim paketi.** 0.1.26, [ölçüm/sınırlar](spikes/R2-B1.md); `export_fab` genişledi, her dosya manifestte role taşır. Üretim onayı değildir.
  - Montaj istenirse `F.Paste`/`B.Paste` katmanları; `pcb export ipcd356` netlisti; `pcb export pos` (mm, CSV,
    ayrı yüzler); `pcb export stats` JSON; Gerber job dosyası üretiliyorsa pakete girer.
  - BOM/CPL dönüştürme bu pakette değil, RD-C3'te; burada ham KiCad çıktısı arşivlenir.
  - Kaynak revizyonu değişmez (bugünkü kopya deseni korunur).
  - **Bitti:** Beş demoda paket içeriği ve SHA'ları manifestte; pasta katmanı yalnızca montajda; `production_verified`
    hâlâ `false` (doğrulama sonraki paketlerde). **PLAN bağı:** İP-5.11. **Süre:** 2 gün.
- [x] **R2-B2 Birleşik üretici profili** (Astra profil + pcb-dfm kural setleri + jBOM profilleri + RD-F6).
  - Uygulama 0.1.27; [ölçüm/sınırlar](spikes/R2-B2.md). Native minimum ölçümü ve aynı sıkılaştırılmış kopyada DRC/dışa aktarım. Üretim onayı değildir.
  - `pcbai/fab/profiles/{jlcpcb-2l,jlcpcb-4l,pcbway,oshpark,generic}.json`: DRC alt sınırları (aralık, iz, delik,
    halka, kenar, serigrafi yükseklik/çizgi/aralık), pasta isteği, BOM/CPL sütun biçimi, dönüş aralığı,
    DFM kural seti kimliği. Her sayı `source_url` ve `retrieved` tarihi taşır; "üreticiyle doğrulayın" etiketi zorunlu.
  - Profil **kopyadaki** kuralları yalnızca sıkılaştırır (Astra deseni); gevşetme isteği reddedilir. Sonuç KiCad'in
    DRC'siyle ölçülür, bulgular `source=fab_profile`.
  - Profil sayıları pcb-dfm `jlcpcb_*` ve jBOM `jlc` profilleriyle kıyaslanır; fark tabloya yazılır, otomatik seçilmez.
  - **Bitti:** Aynı demo `generic` ile temiz, sıkı bir profille beklenen yeni bulguları veriyor; kullanıcı dosyası
    baytı değişmiyor. **PLAN bağı:** 5.10, RD-F6. **Süre:** 3 gün.
- [ ] **R2-B3 IPC-D-356 bağlantı yetkisi** (hauksbee "girdi yetkisi" fikri). RD-C2'ye eklenir.
  - İlk dilim 0.1.28: [ölçüm/sınırlar](spikes/R2-B3.md). Yüzey/doğrusal Gerber alt kümesinde üçlü kıyas var;
    karmaşık Gerber, kaplamalı yol ve tam paket kabulü açık. Tamamlandı işaretlenmez.
  - KiCad'in kendi `ipcd356` netlisti, RD-C2 Gerber okuyucusunun bakır adalarıyla ve şematik netlistiyle üç yönlü
    kıyaslanır. Üçü ayrışırsa hangisinin neyi söylediği bulguda yazar; IPC-D-356 kart verisinden geldiği için
    "şematik niyeti" kanıtı sayılmaz.
  - **Bitti:** Hata kataloğu #1 (DRC sıfır, iki net kısa) üçlü Gerber/IPC/şematik kıyasıyla yakalanıyor.
    Ölçüm düzeltmesi: Gerber ve PCB tabanlı IPC aynı yanlış gruplamada uyumludur; şematik otoritesi farkı gösterir.
    Karmaşık çizim/kaplamalı yol kapsamı ve hazır paketin aynı denetimi ayrıca tamamlanmalıdır. **Süre:** 1 gün.
- [ ] **R2-B4 S13 + pcb-dfm ayrı süreç bağdaştırıcısı.**
  - **14 Ekim /0.1.29 ilk dilim:** deneysel salt okunur bağdaştırıcı, zorunlu ölçüm
    kapsamı ve native kalibrasyon eklendi; [S13 ölçümü](spikes/S13.md). 20 bağımsız
    etiket inconclusive; tam olumlu spike/kabul açık, üretim kapısında kullanılmaz.
  - **S13 spike (2 gün):** KiCad'in Python'u veya kullanıcı yorumlayıcısıyla yalıtılmış ortamda pcb-dfm sabit commit;
    beş demonun R2-B1 paketlerinde süre, bellek, çökme, `not_applicable` oranı; KiCad Excellon yuvalarının
    (G85) işlenişi; 20 bulgunun elle doğru/yanlış etiketi; gerbonara ve bağımlılık lisansları. Sonuç `docs/spikes/S13.md`.
  - **Bağdaştırıcı (3 gün, S13 olumluysa):** `PCBAI_PCB_DFM` yolu; profil → kural seti eşlemesi; her kontrol
    `checks_run` satırı; çöken kontrol `failed`, uygulanmayan `not_applicable` ama **zorunlu listede ise** kapı açmaz.
    Bulgular A1 şemasına `source=fab`, `confidence=heuristic` (kuralın kendi beyanı deterministik değilse) ile çevrilir.
  - RD-A4 kalibrasyonu: pcb-dfm'in delik sayısı, kart ölçüsü ve katman listesi `board_stats`/drill raporuyla eşleşmeli.
  - **U0-F2:** `run` her zaman exit 0, `--must-pass` yok, `not_applicable` ve bilinmeyen durum skorda 0 ağırlık
    alıyor. Bağdaştırıcı profilin zorunlu `check_id` kümesini tek tek doğrular (tekil, bilinen durum, şema sürümü);
    eksik/bilinmeyen/N/A zorunlu kontrol `checks_incomplete`. Toplam skor veya çıkış kodu tek başına kapı açamaz.
    U0'da ecc83 ZIP'inde 108 kontrolün 72'si `not_applicable` çıktı; bu oran S13'te kural seti başına raporlanır.
  - **Bitti:** Beş demoda kalibrasyon geçiyor ya da uyuşmazlık `source=calibration` bulgusu; bilerek bozulmuş Gerber
    (eksik maske, halka ihlali) yakalanıyor. **Süre:** 5 gün (spike dahil). Apache: K22.
- [ ] **R2-B5 Montaj kapısı** (hauksbee assembly evidence, BOM-CPL eklentisi, pcb-dfm `duplicate_refdes`).
  - Kontroller: şematikte DNP olan parça CPL/BOM'da yok; kartta yerleşen her SMD parça CPL'de ve montaj BOM'unda var;
    yinelenen referans; bilinmeyen referans; yüz (üst/alt) ↔ CPL tutarlılığı; montaj BOM'unda her satırda üretici
    parça numarası (profilin istediği alan); adet × kart sayısı ≤ stok (stok biliniyorsa).
  - Dönüş: önce bileşenin kendi `Rotation`/`JLC_Rotation` alanı (BOM-CPL eklentisi fikri), yoksa tablo (RD-C3);
    hangisinin uygulandığı CPL satırının yanında kanıtta yazar. Tablo eşleşmesi yoksa `skipped`, sessiz 0° değil.
  - Çelişki varsa paket `not_ready`; tamamen boş montaj (hiç aktif parça yok) ayrıca reddedilir.
  - **Bitti:** Katalog #18–#21 fixture'ları yakalanıyor. **PLAN bağı:** İP-5.11, RD-C1, RD-C3. **Süre:** 3 gün
    (RD-C3'ün 3 gününden 1'i örtüşür, net 2).

### C. BOM ve parça atama (jBOM, BOM-CPL)

- [ ] **R2-C1 BOM alan denetimi** (jBOM `audit_service` fikri; değer normalleştirme kodu MIT, atıfla alınabilir).
  - **14 Ekim /0.1.30 ilk dilim:** check_bom_fields, native alan otoritesi, exact
    sınırlı pasif normalizasyonu, #21 fixture ve iki bileşenli native sayım eklendi;
    [ölçüm](spikes/R2-C1.md). P2 elle kabulü ve geniş taksonomi açık; kod alınmadı.
  - Taksonomi: değer biçimi (`10K`/`10k`/`10kΩ`/`10000` aynı değer mi), tolerans/gerilim alanları, kategoriye göre
    zorunlu alanlar (dirençte değer+paket, kondansatörde değer+gerilim+dielektrik), MPN/LCSC/Manufacturer varlığı,
    aynı değer grubunda tutarsız alanlar, footprint ↔ değer kategorisi uyumsuzluğu (0603 direnç footprint'li kondansatör).
  - Çıktı A1 bulgusu (`source=bom`, `confidence=deterministic`) ve önerilen düzeltme; yazım R2-C3'e bırakılır.
  - **Bitti:** Katalog #21 (yalnız büyük/küçük harf farkıyla bölünen BOM satırı) yakalanıyor; P2 referansında elle
    sayılan eksik alan sayısıyla eşleşiyor. **Süre:** 2 gün.
- [ ] **R2-C2 Kullanıcı stoğu ile parça eşleştirme** (jBOM inventory fikri).
  - Girdi: kullanıcının CSV stok dosyası (`IPN, Category, Value, Package, Manufacturer, MPN, LCSC, Qty, Priority`);
    sütun eşleme dosyası isteğe bağlı. XLSX ikinci adım (K25). Dosya metni veridir; formül/makro çalıştırılmaz,
    boyut ve satır sınırı vardır.
  - Eşleştirme: kategori + normalleştirilmiş değer + paket; tolerans ve gerilim "en az" kuralıyla; birden çok aday varsa
    `Priority`, sonra stok. Eşleşmeyen parça açıkça listelenir; **model hafızasından MPN atanmaz** (B1 ölçütü).
  - Çıktı: önizleme tablosu (referans → önerilen alanlar, gerekçe, kaynak satır numarası) ve `set_fields` adayı.
  - Stok yeterliliği: `Qty` ≥ adet × kart sayısı; değilse uyarı. Ağ yok; katalog/LCSC araması RD-D5 ve K18'e bağlı.
  - **Bitti:** 30 satırlık örnek stokla P2'nin pasifleri eşleşiyor; yanlış paket ve yetersiz stok vakaları testli;
    eşleşme deterministik (iki koşu aynı). **PLAN bağı:** İP-2.5 (katalog yoksa yerel stok yolu), RD-F6 "eldeki stok".
    **Süre:** 4 gün.
- [ ] **R2-C3 `set_fields` yazıcısı.**
  - Birden çok sembolde alan ekleme/değiştirme (LCSC, MPN, Manufacturer, DNP, Rotation) **tek aday, tek checkpoint,
    tek ERC** olarak (RD-F3 deseni). Paylaşılan sayfa dosyasında etkilenen örnekler ayrıca listelenir (`set_value` deseni).
  - RD-A3 geri okuması: her alan diskten yeniden okunur; bir alan bile farklıysa `readback_mismatch`.
  - **Bitti:** On alanlık aday tek geri alma adımı; hiyerarşide R203/R303 benzeri paylaşılan örnek doğru raporlanıyor;
    enjeksiyonlu yazım hatası yakalanıyor. **Süre:** 3 gün.
- [ ] **R2-C4 Tedarikçi BOM biçimleri** (jBOM profilleri, BOM-CPL eklentisi).
  - R2-B2 profilindeki sütun tanımlarıyla JLC, PCBWay, LCSC, DigiKey, Mouser BOM'ları; tedarikçiye göre ayrı dosya;
    adet çarpanı; satın alma BOM'u ↔ montaj BOM'u ayrımı (RD-C3).
  - **Bitti:** P2 için JLC BOM'u JLC'nin belgelenmiş sütunlarıyla, DigiKey BOM'u ayrı dosyada; adet çarpanı testli.
    **Süre:** 2 gün (RD-C3 ile 1 gün örtüşür, net 1).

### D. Yerleşim denetimi (pcb-inspector)

- [ ] **R2-D1 S14: iki yerleşim denetçisinin kıyası.** pcb-inspector (sabit commit, ayrı süreç) ve kicad-happy
  (RD-B1 düzeni) beş demoda aynı beş soruyu yanıtlar: dekuplaj mesafesi, güç izi, fark çifti kayması, anahtarlama
  düğümü, dönüş yolu. Ölçülen: değer farkı, aynı bileşen kümesi mi, yanlış pozitif örnekleri (elle 20 etiket).
  **U0-F3:** pcb-inspector PCB bulamayınca kuralları boş döndürüp "passed, health_score 100" verebiliyor; bağdaştırıcı
  PCB, net ve yığın girdisini önce doğrular, eksikse kontrol `skipped(reason=missing_input)` olur.
  **Bitti:** `docs/spikes/S14.md` + kural başına "hangi kaynak, neden" kararı. **Süre:** 2 gün.
- [ ] **R2-D2 Yığın farkındalıklı yerleşim kuralları** (S14 kararına göre; RD-B5'in içi).
  - Dönüş yolu: yalnızca **komşu** bakır katmandaki referans düzlemi sayılır; katman sırası `.kicad_pcb` yığınından.
  - Anahtarlama düğümü: SW/LX pin adı veya endüktör + dönüştürücü topolojisi; net adı tek başına kanıt değildir.
    Alan ölçüsü "dışbükey zarf" ise `approximate` etiketi taşır; gerçek akım döngüsü iddia edilmez.
  - Fark çifti: yay ve via geçişi dahil uzunluk; yalnızca hızlı arayüz adları `error` olabilir.
  - Dekuplaj: besleme pini şematik pin adından; karşı yüzde kart kalınlığı eklenir.
  - Güç izi: kendi net sınıfının altında `warning`, profil kılavuzunun altında `info`.
  - Geometri bağımlılıksız yazılır veya S14'e göre pcb-inspector ayrı süreçte çağrılır (K23); shapely çekirdeğe girmez.
  - **Bitti:** Her kural için pozitif/negatif fixture; P2–P4 ölçütleri (RD-B5) bu kurallarla dosyadan ölçülüyor.
    **Süre:** 4 gün (RD-B5'in 5 gününden 1'i örtüşür, net 3).

### E. Görsel inceleme

- [ ] **R2-E1 `review_views` aracı** (pcb-inspector görsel katman fikri; API çağrısı yok).
  - Ön ve arka yüz `kicad-cli pcb render` PNG'si, katman bazlı SVG ve bir kontrol listesi (kutupluluk/1. pin işareti,
    serigrafi okunurluğu, test noktası erişimi, kenar ve montaj deliği boşluğu, konnektör erişimi) döndürür.
  - Görüntüyü **ajanın kendi modeli** yorumlar; PcbAi hiçbir LLM sağlayıcısına istek atmaz, API anahtarı okumaz (K24).
  - Ajanın görsel yorumu bulgu olacaksa koordinat ve öğe UUID'si zorunludur; `confidence=heuristic`, `source=review`;
    kapı açmaz ve deterministik bir kontrolle ya da kullanıcı onayıyla desteklenmeden `error` olamaz.
  - **Bitti:** Beş demoda görüntü seti < 30 sn; görüntü-öğe koordinat dönüşümü ölçülmüş (render ↔ SVG ↔ mm).
    **PLAN bağı:** RD-F1 `review_snapshot`, RD-F4. **Süre:** 2 gün.

### F. Serigrafi

- [ ] **R2-F1 `arrange_refdes`** (KiCad-Astra `labels.py` fikri). Kesilebilir.
  - Referans etiketleri profilin yükseklik/çizgi değerleriyle, ızgarada, gövdeye en yakın serbest konuma yerleşir;
    kilitli ve gizli alanlara dokunulmaz; pad, maske açıklığı ve kart kenarından boşluk korunur.
  - Aday dosyada KiCad DRC'si (serigrafi kuralları) son kapıdır; yeni bulgu varsa aday reddedilir.
  - Preview/apply, checkpoint, RD-A3 geri okuması; yalnızca etiket konum/boyutu değişir, başka bayt değişmez.
  - **Bitti:** Beş demoda serigrafi DRC bulgusu artmıyor; elle sayılan çakışma sayısı azalıyor; bayt farkı yalnızca
    etiket alanlarında. **Süre:** 4 gün (kesilebilir).

### G. Simülasyon modelleri (eSim)

- [ ] **R2-G1 Model kütüphanesi yolu** (eSim kütüphane düzeni fikri).
  - `PCBAI_SPICE_MODELS` (birden çok yol) altındaki `.lib/.sub/.mod/.cir` dosyaları ad → dosya indeksine alınır;
    dosya metni veridir, `.include` yalnızca indekslenmiş kökler içinde çözülür, yol kaçışı reddedilir.
  - SPICE testinde parça modelle bağlanırsa kaynak dosya ve SHA kanıta yazılır; lisansı bilinmiyorsa uyarı (K26).
  - **Bitti:** Kullanıcının kurduğu eSim kütüphanesinden 1N4007 ve bir BJT modeliyle yarım dalga doğrultucu ve ortak
    emetör testi koşuyor; kütüphane yoksa `skipped`. R2-A3 kapsam oranı modeli görüyor. **Süre:** 2 gün.
- [ ] **R2-G2 S15: dijital alt devre spike'ı.** eSim'in 74xx/CD4000 alt devrelerinden beşi KiCad'in ngspice'ında
  (XSPICE kod modelleri gerekir) koşuyor mu; süre ve kararlılık. **Bitti:** `docs/spikes/S15.md`, "uygun/uygun değil".
  **Süre:** 2 gün (kesilebilir).

### H. Regresyon ve dış motor

- [ ] **R2-H1 Gerçek düzeltme çiftleri** (hauksbee git-history fikri; RD-G2'nin genişlemesi).
  - Açık lisanslı donanım depolarında belgelenmiş "hata → düzeltme" commit çiftleri; her çift `tests/fixtures/faults/`
    altında hash sabitli, kaynak ve lisansla. Test: ilgili dedektör iki revizyonda farklı sonuç veriyor.
  - Sonuç dili: "dedektör iki revizyonu ayırdı"; kök neden veya kartın düzeldiği iddia edilmez.
  - **Bitti:** En az beş çift; her biri hangi paketin yakaladığını söylüyor. **Süre:** 3 gün (2'si kesilebilir).
- [ ] **R2-H2 S16: hauksbee ayrı program spike'ı.** Windows x64 beta yapısı yalıtılmış ortamda; beş demoda
  `run_checks` çıktısı; USB-C CC, boot strap, geri besleme yolu bulguları RD-B4 kurallarımızla kıyas. Kurulamazsa
  "uygun değil" diye kapanır. U0'da program PATH'te yoktu (`not_run`). Varsayılan binary GPL-3.0 olduğundan
  kullanıcı hangi yapıyı kurduğunu `doctor` çıktısında görür; ikisi de PcbAi'ye paketlenmez.
  **Süre:** 2 gün (kesilebilir). Lisans: K22 (Apache yapı) ve K21 (GPL yapı) desenleri.

### I. `design_checks` kural adayları (RD-B4'e eklenir)

pcb-dfm kontrol adlarından ve hauksbee analizlerinden seçilmiş, bugün PcbAi'de olmayan kurallar. Her kural en az bir
pozitif ve bir negatif fixture ile, kural numarası ve `confidence` beyanıyla gelir:

- boot/strap pinlerinin tanımlı seviyede olması; reset pininde pull-up
- açık kollektör/açık savak çıkışında pull-up; aynı ağda iki itme-çekme çıkış (sürücü çakışması)
- sürücüsü olmayan ağ, tek pinli ağ; beslemesi olmayan IC
- ray adı takma adları (`+3V3`, `3V3`, `VCC_3V3` ayrı ağ ama aynı niyet) — IR niyetiyle kıyas (#1b ile ilişkili)
- LED seri direnci; USB-C CC dirençleri (RD-B4'te var) için hauksbee sınıflandırma fikri
- geri besleme yolu (USB VBUS ↔ pil/regülatör çıkışı)
- fiducial ve test noktası/debug portu erişimi (montaj profili istiyorsa)

**Süre:** 4 gün; RD-B4'ün 6 gününe eklenir.

---

## 5. Hata kataloğu eklemeleri

RD planı bölüm 5'in devamıdır; numaralar oradan sürer. "Bugün" sütunu R2-A1/A2 dahil 0.1.24 durumudur.

| # | Hata (kaynak) | Neden kaçar | Yakalayan paket | Bugün |
|---|---|---|---|---|
| 17 | Projede `clearance` kuralı `ignore`, iki bakır aralığı yetersiz (Astra) | KiCad bulguyu hiç üretmez | R2-A1 | Fixture #17: ERC/DRC kapsam eksikliği, sch/pcb/all CLI exit 2; kaynak korunuyor |
| 18 | CPL'de parça 90°/180° dönük (BOM-CPL eklentisi, jBOM) | Kütüphane sıfır yönü üreticininkiyle farklı | R2-B5, RD-C3 | Yok (CPL üretilmiyor) |
| 19 | Şematikte DNP, CPL'de var (hauksbee) | Değişken/DNP bilgisi çıktıya taşınmadı | R2-B5 | Yok |
| 20 | Yinelenen referans (pcb-dfm `duplicate_refdes`) | Elle kopyalama, açıklama yapılmadı | R2-B5, ERC kısmen | ERC'nin yakalayıp yakalamadığı ölçülmedi |
| 21 | `10K` ve `10k` iki ayrı BOM satırı (jBOM) | Değer metni normalleştirilmedi | R2-C1 | Yok |
| 22 | Montaj siparişinde pasta katmanı yok | Üretim paketi pastasız | R2-B1 | **Bugün olur:** `export_fab` pasta yazmıyor |
| 23 | Sinyal komşu katmanda referans düzlemi olmadan uzun yol (pcb-inspector) | DRC geometri kuralı değil | R2-D2 | Yok |
| 24 | Muafiyet süresi dolmuş ama bulgu hâlâ gizli | Kalıcı kapatma | R2-A2 | Veri fixture #24: sabit UTC günde etkin bulgu/waiver_expired; ayrı gerçek #1 CLI süresi dolunca exit 1 |
| 25 | Stokta 50 adet var, 10 kart × 6 gerekiyor | Adet × kart sayısı hesaplanmadı | R2-C2, R2-B5 | Yok |

---

## 6. Takvim

RD planı bölüm 6'daki dalgalara yerleşir; yeni dalga açılmaz.

| RD dalgası | Tarih | Bu plandan |
|---|---|---|
| 2 | 9–27 Kas 2026 | **R2-A1**, R2-A2, R2-A3, R2-C1, R2-C3; S13 spike (R2-B4 ilk yarısı) |
| 3 | 30 Kas – 25 Ara | R2-C2, R2-C4, bölüm I kuralları (RD-B4 ile), R2-D1 (S14), R2-E1 |
| 4 | 4–22 Oca 2027 | R2-G1, R2-H1 (zorunlu kısım) |
| 5 | 25 Oca – 5 Mar | R2-B1, R2-B2, R2-B3, R2-B4 bağdaştırıcı, R2-B5, R2-D2 (RD-B5 ile); R2-F1 (kesilebilir) |
| 6 | 8 Mar – 23 Nis | R2-H2, R2-G2 (kesilebilir) |

**R2-A1 dalga 2 beklemeden hemen yapılabilir:** 2 günlük, bağımsız ve bir güven açığını kapatıyor.

| Kalem | Gün |
|---|---|
| A (A1 2 + A2 2 + A3 1) | 5 |
| B (B1 2 + B2 3 + B3 1 + B4 5 + B5 3) | 14 |
| C (C1 2 + C2 4 + C3 3 + C4 2) | 11 |
| D (D1 2 + D2 4) | 6 |
| E1 | 2 |
| F1 (kesilebilir) | 4 |
| G (G1 2 + G2 2, G2 kesilebilir) | 4 |
| H (H1 3 + H2 2; H1'in 2'si ve H2 kesilebilir) | 5 |
| I (RD-B4'e ek) | 4 |
| **Toplam** | **55** |
| Kesilebilir (F1 4 + G2 2 + H1 2 + H2 2; S13 olumsuzsa R2-B4 bağdaştırıcısı +3) | −10 (−13) |
| RD'de zaten sayılmış örtüşme (B5↔C3 1, C4↔C3 1, D2↔B5 1, bölüm I'in RD-B4 içi 1) | −4 |
| **Net zorunlu ek yük** | **41 (S13 olumsuzsa 38)** |

**Kesme sırası** (gecikmede): R2-H2 → R2-G2 → R2-F1 → R2-H1'in ikinci yarısı → R2-B4 bağdaştırıcısı (S13 olumsuzsa
otomatik) → R2-E1. **Kesilmez:** R2-A1, R2-A2, R2-B1, R2-B5, R2-C1; bunlar doğrulamanın ya da üretim paketinin
kendisidir.

### 6.1 PLAN.md ve RD planına etkiler

| Yer | Değişiklik |
|---|---|
| PLAN 5.10 çıktı kapısı | Yoksayılan kural kapısı (R2-A1); montaj kapısı (R2-B5); pasta ve IPC-D-356 paketin parçası (R2-B1) |
| PLAN İP-2.5 katalog | Katalog yokken kullanıcı stoğu yolu (R2-C2); MPN yalnızca stok veya katalogdan |
| PLAN İP-5.11 | Birleşik profil (R2-B2); tedarikçi BOM biçimleri (R2-C4) |
| PLAN İP-6.5 panel | Muaf bulgular ve bitiş tarihleri görünür (R2-A2) |
| RD-A2 | `rule_ignored_in_project` nedeni; kapsam oranı (R2-A3) |
| RD-B4 | Bölüm I kuralları |
| RD-B5 | R2-D1 kıyası ve R2-D2 kuralları |
| RD-C1 / C2 / C3 | R2-B3 üçüncü bağımlı kaynak, R2-B4 ikinci DFM, R2-B5 montaj; dönüş tablosu iki kaynakla kıyas |
| RD-F6 profil | R2-B2 ile birleşir; kullanıcı profili üretici profiline başvurur |
| RD-G2 | Katalog #17–#25 ve gerçek düzeltme çiftleri (R2-H1) |
| RD-H2 GitHub Action | pcb-inspector ve pcb-dfm Action'ları fikir kaynağı; PcbAi `check` çıkış kodları (RD-I9) kullanılır |
| PLAN 2.5 lisans tablosu | pcb-inspector, KiCad-Astra, jBOM (MIT); pcb-dfm, hauksbee (Apache, ayrı program, K22); KiCad-BOM-CPL-Plugin (MPL, yalnız fikir); eSim (GPL-3, yalnız kullanıcı kurulumuna yol) |

---

## 7. Riskler

| Risk | Önlem |
|---|---|
| `ignore` davranışı KiCad sürümüne göre değişebilir | R2-A1 önce fixture ile ölçer; KiCad sürümü kanıta yazılır; sürüm değişince test yeniden koşar |
| Muafiyet "kalıcı susturma"ya dönüşür | Gerekçe + bitiş tarihi zorunlu, üst sınır, muaf bulgu raporda görünür, süre dolunca otomatik etkin |
| Stok dosyası bozuk, büyük veya kötü niyetli | Yalnızca CSV (ilk adım), boyut/satır sınırı, formül değerlendirilmez, hücre metni veri; eşleşmeyen parça açıkça listelenir |
| Değer normalleştirme yanlış eşleştirir (10n ↔ 10µ gibi) | Birim ayrıştırıcısı IR'nin `units.py`'siyle ortak; belirsiz değer eşleştirilmez, soruya döner |
| Üretici sayıları eskir | `source_url` + `retrieved` tarihi; 180 günden eski profil uyarı verir; "üreticiyle doğrulayın" etiketi |
| pcb-dfm sezgisel/yer tutucu kontrolleri yanlış güven verir | Kalibrasyon (RD-A4), `not_applicable` ≠ pass, `confidence` kuralın beyanından; zorunlu listede değilse kapı açmaz |
| pcb-inspector ve kicad-happy birbirini tutmaz | S14 bunu ölçer; uyuşmazlık `source=calibration` bulgusu; kural başına tek kaynak seçilir |
| Görsel yorum uydurma koordinat üretir | R2-E1: koordinat/UUID zorunlu, `heuristic`, kapı açmaz; RD-I7 grounding kapısı uygulanır |
| Yeni bağımlılıklar çekirdeği şişirir | K23: çekirdek yalnızca `jsonschema`; ağır kütüphaneler ayrı süreçte |
| hauksbee Windows yapısı beta | Spike kesilebilir; ürün bağımlılığı yapılmaz |
| eSim model dosyalarının lisansı karışık | Paketlenmez; kullanıcı yolu; lisans bilinmiyorsa sonuçta uyarı |
| Paralel uygulama ana klasörü kirletir | Her paket ayrı worktree; bitince main'e alınır ve worktree kaldırılır (13 Ekim entegrasyon dersi) |

---

## 8. Kararlar (kullanıcı)

| Kod | Karar | Öneri | Durum |
|---|---|---|---|
| K22 | Apache-2.0 araçlar (pcb-dfm, hauksbee) ayrı program olarak kullanılsın mı? | Evet, yalnızca kullanıcının kurduğu yalıtılmış ortamda, yol yapılandırmadan; PcbAi paketine ve koduna girmez (K21 deseni) | Açık (S13 öncesi) |
| K23 | Çekirdeğe shapely/pydantic gibi bağımlılık eklensin mi? | Hayır; geometri bağımsız yazılır ya da dış araç ayrı süreçte çağrılır | Açık (R2-D2 öncesi) |
| K24 | Görsel inceleme PcbAi içinden bir LLM API'sini çağırsın mı? | Hayır; PcbAi görüntü üretir, ajan kendi modeliyle bakar; anahtar okunmaz | Açık (R2-E1 öncesi) |
| K25 | Stok dosyası biçimleri | Önce CSV; XLSX ikinci adım (`openpyxl` isteğe bağlı ek); Apple Numbers yok | Açık (R2-C2 öncesi) |
| K26 | eSim/üretici SPICE modelleri | Paketlenmez; kullanıcı yolu; lisans bilinmiyorsa uyarı | Açık (R2-G1 öncesi) |
| K27 | Muafiyet dosyası kullanıcı projesine yazılsın mı? | `pcbai-waivers.json` proje kökünde, preview/apply ile; git'te izlenebilir | R2-A2'de önerilen araç yolu uygulandı; bu geliştirmede kullanıcı projesine yazılmadı |

---

## 9. Tamamlanan ilk adım

Ölçüm U0'da yapıldı (U0-F1: 69 → 0). R2-A1 çekirdek 0.1.23'te tamamlandı:
`tests/fixtures/faults/17-ignored-required-rule/`, ERC/DRC ignored kapsamı, CLI exit 2 ve kaynak SHA
koruması doğrulandı ([rapor](spikes/R2-A1.md)). R2-A2 de 0.1.24'te tamamlandı
([rapor](spikes/R2-A2.md)). K22–K26 kararları ve diğer paketler açık;
S13 için pcb-dfm commit'i U0'da sabitlendi (`b94d0f7`).

Sonraki iş bölüm 6'daki bağımlılık ve kesme sırasından seçilir; R2-A1/A2 tekrar uygulanmaz.
