# Plan — eksikler ve tamamlama sırası

Tarih: 13 Ekim 2026 · Durum: **uygulama sürüyor** (çekirdek 0.1.11, VS Code 0.1.16; rota/yerleşim, parça/şematik, IR ve tek-dosya pasif blok yazımı eklendi, faz ve canlı kabuller açık) · Kaynaklar: [PLAN.md](../PLAN.md), [plan-gorunum.md](plan-gorunum.md),
[status.md](status.md). Bu belge "şu an ne yok, hangi sırayla, nasıl ve ne zaman bitti sayılır" sorusunu yanıtlar.
Uygulayan ajan her iş paketini bitirince [status.md](status.md)'ye ölçülen sonucu yazar ve buradaki satırı işaretler.

## 12 Ekim — IR ve pasif blok çatısı

- [x] Tek/paylaşılmayan şematikte `add_block`: üç tarife ait altı varyantın tamamı
  tek frozen aday, gerçek kök ERC ve tam native net üye kümeleriyle ölçüldü; tek checkpoint
  ve bayt eşit restore. Toplu/global anotasyon, namespace/cache/grid/yerleşim kapıları.
  Bu adım çoklu sayfa `apply_circuit` ve kalıcı IR eşlemesi değildir.
- [x] Blok yazım farkı uygulayan 79/79, bağımsız 41/41; yerleşim P2 düzeltildi.
- [x] Service-state/proje çakışması: başlangıçta mkdir/ACL/marker/checkpoint öncesi açık ret;
  gerçek junction/retained-lock bağımsız ölçümü. Son birleşik tam takım 243/242 geçti/1 symlink skip,
  ayrı gerçek CLI 11/11; [13 Ekim ölçümleri](status.md).

- [x] İP-3.1 kapalı/paketlenmiş Draft2020 şema, boyutlu SI/range ayrıştırıcı, JSON sınırları,
  bilinmeyen alan önerisi; kullanıcı metni yürütülmez, uzak şema çözülmez. [Sözleşme](ir.md).
- [x] İP-3.2 başlangıç çatısı: sürümlü üç yerleşik pasif tarif, kapalı parametreler, gerçek
  Device:R/C ve 0603 pin/pad haritaları; tüm tarifler olgunluk **0**.
- [x] İP-3.4 **ön denetim bölümü**: `plan_circuit`, literal pin/port/rail başvuruları,
  benzersiz kimlik, gerçek pin/pad karmaları, kaynak-net birleşimi, ray çatışması ve
  genişletilmiş 150 parça sınırı. Elektriksel aşama eksik; uygulanabilirlik kabulü verilmez.
- [x] İP-4.3 başlangıç `hand_calc`: sekiz hesap, normalize girdiler, birimler,
  varsayımlar ve özgün girdi/rapor karmasıyla kanıt.
- [x] Genişletilmiş RC değerleri gerçek ngspice transient/AC ile el hesabına kıyaslandı;
  kurulu kütüphanelerde 5 parçalık ön denetim pin/pad uyumlu. Ölçümler status.md'de.
- [x] Paket kapısı: tam 228/227 geçti/1 Windows symlink skip; ayrı CLI 11/11,
  bağımsız 42/42, gerçek servis/MCP 4/4, wheel/core sürüm 0.1.9, Ruff/lisans temiz.
- [ ] İP-3.1/3.4 tam gerilim/akım bütçesi, veri sayfası/pin işlevi/STM32 AF denetimleri.
- [ ] İP-3.2 alt sayfa şablonu/yer tutucu/layout, İP-3.5 çoklu sayfa apply ve IR↔UUID eşlemesi.
- [ ] İP-3.6 ilk 11 olgunluk-1 blok; İP-3.7 semantik onarım/küçük model modu;
  İP-3.8 gerçek model kıyası. İdeal RC kıyası tarif/ERC/CI/fiziksel kabulü kapatmaz.

## 12 Ekim — yerel parça ve şematik paketi

- [x] İP-2.4 yerel KiCad FTS5 dizini: gerçek "AMS1117 3.3" araması doğru sembolü buldu;
  kalıtılan metadata, içerik karmasıyla yenileme ve güvenli sorgu/yazma yolları.
- [x] İP-2.8 tek/paylaşılmayan dosya araçları: `add_symbol`, `connect`, `add_label`, `replace_part`;
  önizlenen aday/revizyon, checkpoint, gerçek kök ERC. Pin bağlantısı gerçek netlistten ölçülür.
- [x] İP-2.7 **yalnız yapısal bölüm**: kalıtılan pinler, literal numaralar, çoklu pad ve NPTH ayrımı;
  kullanıcı pin tablosu bağımsız veri sayfası kabulü diye sunulmaz.
- [ ] İP-2.2 modelin çok dosyalı yazıcı/alt sayfa/kararlı numaralama tamamı; shared sheet yazımı
  ve pin geometrisi değişen replacement güvenli biçimde reddediliyor.
- [ ] İP-2.5/2.6 katalog, JLC2KiCadLib getirme, 3B ve kütüphane tablosu yönetimi.
- [ ] İP-2.7 tam veri sayfası/güç pinleri/3B/stok/yaşam döngüsü ve Faz 2 P2 kabulü.
- [x] Son farkın bağımsız tekrar denetimi: kotası yeniden kullanılabilen denetçi ek üç P1 buldu;
  sheet/ancestor/sibling root/UUID kimlik düzeltmeleri kendi yeniden üretimleriyle reddedildi.
  Son kapalı-GUI hedefleri uygulayan **61/61**, bağımsız **64/64**, skip yok;
  tam 209 koşusu ve ayrı deltanın sınırları status.md'de korunur.

Ölçümler ve doğrulama sınırları [status.md](status.md)'de; ürün fazı kapatılmadı.

## 12 Ekim — rota/yerleşim paketi

- [x] R3 yazılımı: native/WSL/JAR program keşfi, seçenek izin listesi, bütçe, süreç ağacı zaman aşımı,
  ayrı DSN/SES worker, doctor. TraceMaker'ın canlı sürüm/commit/WSL kabulü açık.
- [x] R4 yazılımı: yabancı öğe bekçisi, UUID (yazım varyantları dahil), net/katman, kilit,
  geçerli dışhat/avlu konturu ve yeni DRC **kimliği** denetimi.
- [x] R5/R6 yazılımı: `autoroute`, `autoplace`, `route_engines`, yalnız preview arka plan işleri,
  aynı revizyonda immutable aday, tekrar denetim, checkpoint, atomik yazma, geri yükleme.
  Sahte motor gerçek alt süreçte route/place; gerçek JAR motorla küçük düzenekte SVG/apply/restore.
- [x] R8 yazılımı: motor/bütçe seçimi, önce/sonra SVG ve ölçü/tanı paneli; Chromium UI testi,
  kaynakla eşleşen **VS Code 0.1.16 yüklendi**. Gerçek Extension Host motor/elle kabulü açık.
- [x] R7 kıyas **betiği**: beş KiCad demosu × iki gerçek JAR koşusu;
  [güncel yerel tablo](../.pcbai-state/s4-current.md), [S4](spikes/S4.md).
- [ ] R0/R2/S10: WSL kurulumuna izin verildi, Windows bileşenleri kuruldu; yeniden başlatma,
  Ubuntu, TraceMaker cpu-only derleme ve gerçek rota/yerleşim/timeout/determinizm ölçümü gerekiyor.
- [ ] R1/R5/R6 motor kalite kabulü ve R7/K5 seçimi: ecc83/pic_programmer yeni DRC;
  video/interf_u kaynak UUID tekrarı; stickhub korunan öğe farkı. Engeller gevşetilmedi.
- [x] SPICE güvenlik düzeltmesi: nested model dosyaları denetlenip bellekte açılır;
  dosya kaynaklı/dış süreç çalışan modeller ve izin dışı direktifler reddedilir.

K12 ayrı program/paketlememe sınırı uygulanır; K13 kurulum onaylı ama ortam hazır değil;
K14 kullanıcı seçimiyle **yalnız KiCad demoları**. [Karar](decisions/0003-engines.md).
Bu paket Faz 2–4'ün parça/şematik/IR/blok işlerini, Faz 5 senkron/DFM/üretim işlerini veya
Faz 7 orkestrasyon/fiziksel kart kabulünü kapatmaz. Test ve bağımsız denetim sonuçları status.md'de.

Yeni (13 Ekim): sekiz referans deponun kaynak incelemesinden çıkan geliştirme planı — denetim katmanı,
bağımsız üretim doğrulaması, datasheet güven kapısı; paketler RD-A…RD-H, dalga 0'da S11 →
[plan-referans-depolar.md](plan-referans-depolar.md).

## 0. Başlangıç durumu (11 Ekim 2026, ölçülen)

Aşağıdaki tablo plan öncesi kayıttır. İlk paket sonrası ölçümler [status.md](status.md)'dedir.

| Alan | Var | Yok |
|---|---|---|
| Çekirdek (0.1.3) | Dosya modu oturumlar, okuma araçları, ERC/DRC, PDF, PNG render, kart ölçüsü, Gerber/delik zip, `net_info`, değer düzenleme + checkpoint/geri yükleme, arka plan işleri | Sembol ekleme/bağlama, parça, IR, bloklar, SPICE, PCB düzenleme, BOM/CPL |
| Canlı KiCad (IPC) | Salt okunur bağlanma, kart özeti, seçim okuma (tek KiCad örneğinde) | İkinci örnek, kaydedilmemiş değişiklik ölçümü (S3), KiCad'de seçtirme, canlı yazma |
| VS Code (0.1.4, kurulu) | Komutlar, kart 2B görünümü (katman, seçim, DRC), kartta işaretler, PNG önizleme | Şematik görünümü, şematik işaretleri, 3B etkileşim, hızlı yenileme, KiCad'le çapraz seçim |
| KiCad eklentisi | İki düğmenin kodu (`kicad_plugin/`), elle kopyalanmış | PCM paketi, "Yüklü" listesinde görünme, API açık değil, gerçek KiCad'de hiç denenmedi |
| Doğrulama | 118 Python testi, gerçek Chromium görünüm testi, S1 (kısmi), S2, S7 | S3–S6, kıyas seti P1–P6, rakip kıyası, uzak CI, gerçek kart |
| Depo | git, iki commit | 52 dosya commit edilmemiş; LICENSE yok (K1 açık) |

## 1. Hemen (bloklayıcılar, 1–2 gün)

- [x] **E-1 Kayda alma:** commit edilmemiş 0.1.3/0.1.4 işi ayrı ve anlamlı commit'lere bölünür (çekirdek görünüm araçları,
  işaretler, VS Code görünümü, KiCad eklentisi, test/kanıt betikleri). Testler her commit'te yeşil.
  **Bitti:** `git status` temiz; her commit'in mesajı ne yaptığını ve ölçüldüğü testi söylüyor.
  Kayıt: çekirdek `a6ad092`, VS Code/lisans `48aa46b`, önceki belge/kanıtlar `646bb4c`;
  KiCad paketi ve kalan deneme betikleri sonraki paket commit'inde. Son ölçüm 131 test/1 skip,
  ayrı CLI 11/11 ve Ruff temiz; belge-only commit aynı kod/test ağacının sonucunu kullanır.
- [x] **E-2 Lisans (K1):** Kullanıcı LGPL-2.1-or-later kabul etti; [karar kaydı](decisions/0002-license.md).
  KiCad paketi `license` alanını zorunlu tutuyor; karar verilmeden paket yayımlanamaz.
  Öneri LGPL-2.1-or-later (CadAI ile aynı). **Bitti:** `LICENSE`, `pyproject.toml`, `package.json`, `plugin.json` aynı lisansı söylüyor.
- [ ] **E-3 Ortam:** KiCad 10.0.4 → 10.0.7 (`flip_items` ≥ 10.0.6 ister); kullanıcı KiCad'de API'yi açar
  (Tercihler → Eklentiler → KiCad API'yi etkinleştir). **Bitti:** `doctor` 10.0.7 ve `enable_server: true` gösteriyor.
  12 Ekim ölçümü: API ayarı artık **true**; KiCad hâlâ 10.0.4. Ortam kabulü tamamlanmadı.
- [x] **E-4 İki ajanlı çalışma düzeni** (bölüm 8): kural AGENTS.md'ye yazıldı; bağımsız denetçi
  testleri yeniden çalıştırdı. Kanıt betikleri varsayılan olarak `.pcbai-state/` kullanıyor;
  yayın yazımı açık seçim gerektiriyor; junction/hardlink regresyonları var.

## 2. KiCad paketi — "Yüklü" listesinde görünmesi (2–3 gün)

| Kod | İş | Nasıl | Bitti |
|---|---|---|---|
| K-1 | PCM paketi | `kicad_plugin/build_pcm.py` → `kicad_plugin/dist/pcbai-kicad-<sürüm>.zip`. Kökte `metadata.json` (zorunlu alanlar: `name`, `description`, `description_full`, `identifier` = `org.pcbai.kicad`, `type` = `plugin`, `author{name, contact}`, `license`, `resources`, `versions[{version, status, kicad_version: "10.0", runtime: "ipc"}]`). **`runtime: "ipc"` şart**, yoksa KiCad SWIG eklentisi sanar. `plugins/` altında `plugin.json`, `requirements.txt`, `*.py`, simgeler; `resources/icon.png` (64×64). | `metadata.json` kurulu `pcm.v2.schema.json` ile doğrulanıyor (test) |
| K-2 | Yol bilgisini paketten çıkarma | Bugün `pcbai_location.json` makineye özel yolu paketin içine yazıyor. Yeni sıra: `PCBAI_ROOT` ortamı → `%APPDATA%\PcbAi\location.json` (VS Code eklentisi ya da `scripts/install_*` yazar) → bulunamazsa açıklayıcı pencere. | Paket iki farklı klasördeki PcbAi kopyasıyla da çalışıyor (test) |
| K-3 | Kurulum | Elle kopyalanmış `Documents\KiCad\10.0\plugins\org.pcbai.kicad` kaldırılır (aynı kimlikte iki eklenti olmamalı). KiCad → Eklenti ve İçerik Yöneticisi → **Dosyadan yükle…** → zip. `install.py` bundan sonra yalnızca geliştirme içindir (README'de böyle yazar). | Eklenti "Yüklü" sekmesinde, PcbAi simgesiyle görünüyor |
| K-4 | Gerçek KiCad kabulü | API açık KiCad'de PCB editörü: iki düğme görünür; ilk tıklamada KiCad venv kurar (`%LOCALAPPDATA%\KiCad\10.0\python-environments\org.pcbai.kicad`); "PcbAi'ye kaydet" proje yolunu doğru verir; "ERC/DRC" sonuç penceresi açılır. | Ekran görüntüsü + pencere metni `docs/status.md`'de; hata varsa düzeltilip yeniden denenmiş |

Risk: KiCad PCM IPC paketinde `requirements.txt` kurulumu internet ister; çevrimdışı kurulumda düğme hata verir — pencere metni bunu söylemeli.

- [x] **K-1:** ZIP üretildi; `runtime: "ipc"`, lisans ve kurulu PCM/API şemaları testten geçti.
- [x] **K-2:** Paket içinde konum dosyası yok; aynı ZIP iki ayrı gerçek kaynak kopyasıyla ayrı servis
  başlatıp doğru proje oturumunu döndürdü. Bu, canlı KiCad IPC bağlantısı değildir.
- [ ] **K-3/K-4:** PCM'de kullanıcı kurulumu ve gerçek KiCad düğme kabulü henüz yapılmadı.
  [Kurulum adımları](../kicad_plugin/README.md).

## 3. Görünüm eksikleri

### 3.1 G2 — Şematik görünümü (1,5 hafta) ← en büyük eksik

| Kod | İş | Nasıl | Bitti |
|---|---|---|---|
| G2-a | S8 denemesi: şematik SVG ↔ mm | `kicad-cli sch export svg --exclude-drawing-sheet` sayfa başına SVG; şematik koordinatı sayfa mm'sidir. S7 gibi ölçülür: bilinen sembol pinlerinin SVG konumu ↔ dosyadan hesaplanan konum. | `docs/spikes/S8.md`: 3 demo (ecc83, complex_hierarchy, pic_programmer) en büyük hata ≤ 0,05 mm |
| G2-b | `render_sch` | Sayfa başına SVG, revizyon önbelleği, dönüşüm matrisi, sayfa boyutu. Hiyerarşik sayfa **örnek yolu** (sheet path) ile anılır; aynı dosyanın iki örneği ayrı sayfadır (referanslar farklı). | complex_hierarchy'de her örnek ayrı açılıyor |
| G2-c | `scene_sch` | Sembol: referans (örnek yoluna göre), değer, `lib_symbols` grafiğinden sınır kutusu (dönüş/aynalama/birim uygulanmış), pin konumları; tel, bağlantı noktası, etiket, sayfa sembolü ve pinleri. | Birim testleri: dönüş 0/90/180/270, aynalama, çok birim |
| G2-d | Net eşleme | Net adı tahmin edilmez: `kicad-cli sch export netlist --format kicadxml` → (örnek yolu, referans, pin) → net. Tellerin neti pin uçlarından yayılır, KiCad netlistiyle kıyaslanır. | Rastgele 20 pin için net kümesi KiCad netlistiyle aynı |
| G2-e | Webview | Sayfa ağacı (hiyerarşi), yakınlaştır/kaydır, tıklayınca sembol/pin/tel/etiket bilgisi, pine tıklayınca netin tüm pinleri ve telleri vurgulu (sayfalar arası: diğer sayfada kaç pin var yazar), ERC bulguları sayfa + konumla. Kart görünümüyle aynı panel, sekmeyle geçiş. | Tarayıcı testi: complex_hierarchy'de R203 ve R303 ayrı seçiliyor; net vurgusu netlistle aynı |
| G2-f | Şematik işaretleri (G3'ün kalanı) | `space: "sch"`: sembol, pin, net, alan; bağ = (sayfa örnek yolu, sembol UUID, pin numarası). Koyma/düzenleme/silme kart işaretleriyle aynı akış. | "#1 bu direnç 4,7k olsun" → ajan `get_markers` → `set_value` önizle/uygula → işaret `done` + kanıt kimliği; uçtan uca test |

- [x] **G2-a S8:** 6 demo, 3510 pin bağlantı noktası 0,0 mm; sayfa matrisi birim; [S8](spikes/S8.md).
- [x] **G2-b `render_sch`:** sayfa örneği başına SVG, ölçülen matris, revizyon önbelleği; complex_hierarchy'de
  iki örnek ayrı sayfa. Sayfa kimliği `${SHEETPATH}` kalibrasyon metniyle ölçülür, dosya adına güvenilmez.
- [x] **G2-c `scene_sch`:** sembol/pin/tel/bus/etiket/bağlantı/alt sayfa; dönüş 0–270, aynalama, çok birim
  birim testleri. Pin bağlantı noktaları S8'de KiCad çizimiyle aynı.
- [x] **G2-d net eşleme:** 6 demoda **tüm netler** ve rastgele 20'şer pin KiCad netlistiyle aynı; tellerin
  %98–100'ü net adı alıyor, çelişki 0; bilinmeyen `null` kalıyor.
- [x] **G2-e webview:** `PcbAi: Şematik görünümünü aç` (VS Code 0.1.6). Sayfa ağacı, çift tıklama/üst sayfa,
  seçim, net vurgusu ve diğer sayfalara geçiş, ERC. Tarayıcı testi: iki örnekte 30/30 sembol kendi referansıyla,
  R203/R303 ayrı; net vurgusu netlistle aynı. Kart görünümüyle aynı panel yerine **ayrı panel** (aynı CSS/köprü düzeni).
- [x] **G2-f şematik işaretleri:** `sheet` örnek yolu + UUID bağı, `target_item`; gerçek complex_hierarchy
  kopyasında "#1 bu direnç 4,7k olsun" → `get_markers` → `set_value` (gerçek ERC) → `done` + change_id testi geçti.

### 3.2 G5 — Hızlı yenileme (3–4 gün)

- **Ölç önce:** 9,7 sn'nin dağılımı (kicad-cli çağrı sayısı ve süresi, kalibrasyon kopyası, `scene_pcb` ayrıştırma,
  webview'e aktarım) `docs/spikes/G5.md`'ye.
- **Yöntemler (ölçüme göre):** katmanları tek `--mode-multi` çağrısında üretmek (katman başına süreç yerine);
  kalibrasyonu kart dış hattının karmasına göre önbelleğe almak (dış hat değişmedikçe yeniden ölçmemek);
  değişmeyen katmanın SVG'sini yeniden göndermemek; yenilenirken eski görüntüyü gösterip "yenileniyor" demek;
  `scene_pcb`'yi ayrıştırma önbelleğiyle hızlandırmak.
- **Bitti:** ecc83 boyutunda kartta, değer değişikliğinden görünümün yenilenmesine p50 ≤ 2 sn, p95 ≤ 3 sn
  (10 ölçüm); pic_programmer'da süre yazılır.

- [x] **G5:** ölçüm + tek `--mode-multi` çağrısı, net tablosu, yoklama aralıkları. ecc83 tarayıcıda 10 ölçüm
  p50 1,44 sn / p95 1,79 sn (kabul geçti); pic_programmer 3,5 sn kayıtlı. [G5](spikes/G5.md).

### 3.3 G4 — Etkileşimli 3B (4–5 gün)

- **S9 denemesi:** `kicad-cli pcb export glb` düğüm adlarında referans (R5, U1) var mı; yoksa bileşen başına
  `--component-filter` ile ayrı GLB üretip birleştirmenin süresi. Sonuç `docs/spikes/S9.md`.
- **Görüntüleyici:** CadAI'dan alınmış three.js; döndür/yakınlaştır, üst/alt/izometrik, kart kalınlığı, bileşenleri
  gizle/göster; WebGL kademeli açılış ve bağlam kaybı kurtarma (CadAI yöntemi).
- **Seçim:** S9 olumluysa tıklanan bileşen 2B görünümdeki seçimle eşleşir; değilse yalnızca görüntü.
- **Bitti:** üç demo kart 3B açılıyor (yavaş GPU'da da); S9 olumluysa tıklanan bileşenin referansı doğru.

- [x] **G4:** S9 olumlu (düğüm adı = referans). `render_3d`, VS Code 0.1.9 `PcbAi: Kartın 3B görünümünü aç`: döndür/yakınlaştır, üst/alt/izometrik, bileşen gizle/göster, tıklayınca referans; WebGL düşük güç yedeği ve bağlam kaybı kurtarma. Yazılımsal WebGL ile üç demo açıldı; görünür bileşenlerde 87/87 doğru seçim. [S9](spikes/S9.md).

### 3.4 G6 — KiCad ile çapraz seçim (S1 ve S3'ten sonra, 3–4 gün)

- VS Code'da seçilen öğe → KiCad'de `add_to_selection` (canlı mod, PCB). KiCad'deki seçim → görünümde vurgu (seçim
  okuma zaten var; değişince bildirim için kısa aralıkla yoklama).
- **Bitti:** API açık KiCad'de iki yönde seçim; ikinci KiCad örneği açıkken yanlış örneğe gitmiyor (sorar).

### 3.5 Diğer görünüm eksikleri

- **"Ajana sor":** bugün panoya kopyalıyor. Claude Code VS Code eklentisinin komutla istem alıp almadığı araştırılır;
  alıyorsa doğrudan gönderir, almıyorsa panoda kalır. (1 gün araştırma)
- **Kaydedilmemiş değişiklik uyarısı:** canlı mod geldiğinde (S3) görünüm "KiCad'de kaydedilmemiş değişiklik var" der.

## 4. Kartta işaretle değişiklik (Faz 5a'dan öne alınan çekirdek, 1,5–2 hafta)

Kart işaretleri bugün koyulabiliyor ama uygulanamıyor ("bu hat 1 mm olsun" → `blocked`). Gerekli en küçük araç seti:

| Araç | Ne yapar | Doğrulama |
|---|---|---|
| `move_footprint` | Taşı / döndür / yüz değiştir | DRC (kopyada) + avlu çakışması |
| `set_track_width` | Bir iz ya da netin izlerinin genişliği | DRC; genişlik net sınıfı alt sınırının altındaysa ret |
| `add_zone` | Çokgen + net + katman, doldurma kopyada | DRC + `--refill-zones` |
| `set_netclass` | Net sınıfı genişlik/aralık | DRC |

- [x] **Bölüm 4 uygulandı (çekirdek 0.1.5):** dört araç, DRC kapısı (`new_violations`), KiCad kâhini (6 demo, 7 kart, 401 işlem, 0 fark). Kabul testleri: P101 taşıma işareti, iz işareti ve GND alan işareti `done` + kanıt; bağlantılı R1 taşıması 0→14 hatayla reddedildi; geri yükleme bayt eşit. Flip sırasında metin açıları KiCad'in okunur tutma kuralı nedeniyle 180° farklı yazılabilir (görüntü aynı).

Hepsi önizle/uygula, checkpoint, revizyon hedefi, kaydedilmemiş değişiklik/kilit koruması kullanır (bugünkü
`set_value` düzeni). Dosya modunda s-expr yazıcıyla; canlı mod S3 sonrası IPC commit'iyle.
**Bitti:** kart görünümünde "#1 J1'i sol kenara al", "#2 bu hat 1 mm olsun", "#3 buraya GND dökümü" işaretleri ajan
tarafından uygulanıp `done` + DRC kanıtıyla işaretleniyor; geri yükleme bayt eşit.

## 5. Faz 0 / Faz 1 açıkları

| Kod | İş | Bitti |
|---|---|---|
| S1 (kalan) | İkinci KiCad örneğine bağlanamama nedeni; kanal adları | İki örnek açıkken her biri doğru projeyle eşleşiyor |
| S3 | Dış değişikliğe KiCad'in tepkisi, kayıttan sonra `get_as_string` = dosya mı, `revert` | Ölçümler `docs/spikes/S3.md`'de; kaydedilmemiş değişiklik denetimi buna göre yazılmış |
| S4 | Freerouting 2.5 yerel CLI: DSN → SES → içe aktarma → DRC ([plan](plan-rota-yerlesim.md) R1) | Beş demo kartta (izsiz kopya) rotalanmamış bağlantı 0 ya da nedeni; S10 ile aynı ölçüler |
| S10 | TraceMaker (WSL, `cpu-only`) aynı beş kartta; determinizm, bekçi, zaman aşımı ([plan](plan-rota-yerlesim.md) R2) | `docs/spikes/S10.md`; K13 kararından sonra |
| S5 ✅ | KiCad `ngspice.dll` alt süreçte | RC `.tran` sonucu el hesabıyla %1 içinde — **geçti**: %0,0002; sallen_key \|H(f₀)\| %0,002; `simulate` aracı ([S5](spikes/S5.md)) |
| S6 | JLC katalog kaynağı (jlcparts / kicad-jlcpcb-tools DB) | Boyut, hız, tazelik, koşullar; K9 kapanır |
| P1–P6 | Kıyas seti: `problem.md`, `requirements.json`, `checks.py`, P2 referans çözümü | Denetimler referansta geçiyor, boş projede kalıyor |
| Baseline | 6 rakip araç × P1, P2 | `docs/baseline.md` |
| CI | GitHub uzak deposu ve CI koşusu (K11: depo görünürlüğü) | Yeşil CI bağlantısı status.md'de |
| Extension Host | Gerçek VS Code içinde kart görünümü ve işaretler (sahte modülsüz) | `scripts/test_extension_host.py` kart + işaret senaryosuyla geçiyor |

## 6. Ürün eksikleri (PLAN Faz 2–7)

Bunlar PLAN.md'de iş paketi düzeyinde tanımlı; burada yalnızca sıra ve başlangıç noktası:

1. **Faz 2 — yazıcı, parça, şematik düzenleme:** sembol ekleme/bağlama (`lib_symbols` kopyası, UUID, örnekler),
   KiCad kütüphane dizini, JLC katalog (S6), JLC2KiCadLib, `verify_part`. İlk iş paketi İP-2.2 (şematik modeli);
   G2'nin `scene_sch`'ı bunun okuma yarısıdır, ortak kod olmalı.
2. **Faz 3 — IR + bloklar + en küçük SPICE çalıştırıcı (S5).**
3. **Faz 4 — simülasyon derinleştirme + 20+ blok.**
4. **Faz 5 — PCB:** senkron, yerleşim, rota (S4, S10), döküm; bölüm 4'teki araçlar 5a'nın parçasıdır. Yerleşim ve rota
   dış motorlarla: [plan-rota-yerlesim.md](plan-rota-yerlesim.md) (R0–R9, ~2,5 hafta; İP-5.6 tavlamanın yerini alabilir).
5. **Faz 7 — orkestrasyon, kanıtlı rapor, gerçek kart 1 ve 2.**

## 7. Sıra ve takvim (öneri)

| Hafta | İş | Sonuç |
|---|---|---|
| 1 (12–16 Ekim) | E-1–E-4, K-1–K-4 | Depo temiz, lisans var, eklenti KiCad'de "Yüklü" ve düğmeler gerçek KiCad'de denenmiş |
| 2–3 (19–30 Ekim) | G2 (S8 dahil) + G2-f | VS Code'da şematik + şematik işaretleri; "#1 bu direnç 4,7k" uçtan uca |
| 3 (paralel) | G5 | Yenileme ≤ 2 sn |
| 4 (2–6 Kasım) | S1 kalan + S3, ardından G6 | Canlı mod okuma güvenli; KiCad'le çapraz seçim |
| 5–6 (9–20 Kasım) | Bölüm 4 kart düzenleme araçları | Kart işaretleri uygulanıyor |
| 6 (paralel) | G4 (S9 dahil) | Etkileşimli 3B |
| 7+ | Bölüm 5 kalanları (S4–S6, P1–P6, baseline, CI), sonra PLAN Faz 2 | Ana plana dönüş |

Bu sıra PLAN.md takvimini yaklaşık 5 hafta kaydırır; kaymaması için görünüm (bölüm 3) ile çekirdek (bölüm 4–6)
iki ajana ayrılır (bölüm 8).

## 8. İki ajanlı çalışma düzeni

Bu depoda Codex ve Claude Code aynı anda çalışıyor. Çakışmayı önlemek için:

- **Bir iş paketi = bir ajan = bir dal** (`ip/g2-sematik`, `ip/k-pcm`…). İş paketi bitince dal birleştirilir.
  Ana klasörde iki ajan aynı anda yazmaz; ikinci ajan `git worktree` ile ayrı klasörde çalışır.
- **Roller:** biri uygular, diğeri bağımsız denetler (testleri kendisi koşar, iddiaları yeniden üretir, bulguyu
  yazar). Denetleyen düzeltmeyi uygulayana bırakır, kendisi kodu değiştirmez (kullanıcı aksini istemedikçe).
- **Kanıt dosyaları:** `docs/spikes/*-result.json` yalnızca yayın koşusunda yazılır; geliştirme ve denetim koşuları
  `.pcbai-state/` altına yazar. (11 Ekim'de denetim koşusu `G1-browser-result.json`'ın üzerine yazdı; sonuçlar aynı
  çıktı ama kural bunu önlemeli.)
- **Kayıt:** her iş paketinin sonunda commit + `docs/status.md` satırı + bu belgede işaret. Commit edilmemiş iş bir
  günden uzun kalmaz.
- **Sürüm:** VS Code eklentisi her değişiklikte sürüm artırır (önbellek); çekirdek sürümü `pcbai/__init__.py`.

## 9. Bitti tanımı (her iş paketi)

Testler yeşil (KiCad açıksa atlanan yazma testleri KiCad kapalıyken ayrıca koşulmuş) · ruff temiz · ilgili belge
güncel · ölçülen sonuç `docs/status.md`'de · görünüm işiyse tarayıcı testi ve ekran görüntüsü · kullanıcıya görünen
işse kurulu sürümde elle denenmiş · commit edilmiş.
