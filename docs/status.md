# Uygulama durumu — 13 Ekim 2026

Çekirdek sürümü **0.1.11**, kurulu VS Code eklentisi **0.1.16**, önceki KiCad PCM paketi `pcbai-kicad-0.1.5.zip`.
Bu numaralar **PLAN.md Faz 1 kabulünün tamamlandığı** anlamına gelmez.
Plan 30 haftalık ürün hedefidir; kalan işler aşağıda açıkça ayrılmıştır.

## State/proje ayrımı — 13 Ekim 2026 (dal `ip/state-yapilandirma`)

- State ve kayıtlı proje kökleri birbirini içeremez/eşit olamaz. Hem gerçek çözümlenmiş hem
  mutlak lexical yol kontrol edilir; Windows case/junction, noktalı yollar, sibling-prefix ve çoklu
  kökler kapsanır. `invalid_state_directory` açık hata verir, yapılandırma sessiz taşınmaz.
- Kontrol Engine'de history/evidence/export/index öncesi; serve/inspect yollarında private-directory
  mkdir/ACL/marker ve singleton öncesi çalışır. Tek kullanımlık project iterator korunur;
  `~` genişletmesi denetlenen ve hazırlanan aynı yola uygulanır. Gerçek KiCad kilit kapısı gevşetilmedi.
- Bağımsız son hedefler **55 test: 54 geçti, 1 eski symlink yetkisi skip**, 11,124 sn;
  konfigürasyon **6/6**, 0,076 sn. Gerçek iki Windows junction ve eski retained-lock P2 yeniden
  üretimi erken retle kapandı; yeni state/history/export/ACL yazımı yok.
  [Rapor](../.pcbai-state/audit-all-plan/state-yapilandirma-review.md).
- Kesilen ilk tam koşu tamamlanmış kabul edilmedi. Yeniden başlatılan son tam takım
  **243 test: 242 geçti, 1 Windows symlink yetkisi skip**, **833,536 sn**;
  [kayıt](../.pcbai-state/state-resumed-full.txt). Blok yazımı ve state farkları birlikte kapsandı.
  Ayrı gerçek CLI **11/11**, skip yok, **262,264 sn**; [kayıt](../.pcbai-state/state-final-cli.txt).
  Gerçek şematik/kart apply ve restore atlanmadı. Ruff/lisans temiz.
- Editable **0.1.11** kuruldu; wheel 69 dosya, schema/core-only import, dış ikili/plugin yok.
  [Paket denetimi](../.pcbai-state/state-wheel-check.json), SHA-256
  `373f882bb0f0818527fa52ab1011e95ed0df7651b4a57f78d069a06e34ee8c7e`.
- 13 Ekim WSL tekrar denetimi hâlâ `Wsl/WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED` döndürüyor.
  Windows yeniden başlatılmadan Ubuntu/TraceMaker derlemesi ve S10 motor kıyası çalıştırılamıyor.
  Fiziksel kartlar, tam IR compiler, stok/AF ve diğer açık fazlar bu testlerle tamamlanmış sayılmaz.

## Tek dosyada pasif blok yazımı — 12 Ekim 2026 (dal `ip/pasif-blok-yazimi`)

- `add_block`: üç mevcut pasif tarifi (altı varyant) yalnız byte içinde birleştiren tek aday;
  toplu/global anotasyon, sabit UUID/önbellek tanımı, görünür pasif non-power pin geometrisi/türü,
  gerçek footprint pin/pad ve aynı kütüphane revizyonu denetimi. Proje cache'i korunur.
- Otomatik yerel namespace ve exact native net üye kümeleri; singleton pin ve debounce aliasları
  ayrı ele alınır. Eksik/ek/eski pin veya ayrı netlerin birleşmesi aday üretimini engeller.
- 1,27 mm ızgara, sayfa sınırı ve mevcut gövde/hat/etiket/görünür alan/serbest metin çakışması;
  metin kutuları muhafazakâr/yaklaşık. Desteklenmeyen kök çizim öğesi `unsupported_layout`.
  Yerleşim tek satır, rotasyon/ayna yok; tam grafik okunabilirlik sertifikası değildir.
- Tek checkpoint/atomik apply, gerçek root ERC önce/sonra ve apply-time tekrar; aynı sayıda
  farklı yeni ERC hata kimliği de reddedilir. RC dış portları **0 hata, 2 isolated_pin_label
  uyarısı** verir; `verified=erc_findings` korunur. Olgunluk **0**, çoklu dosya/IR eşleme yok.
- Uygulayan son odaklı **79/79**, skip yok, 103,644 sn; ilgili engine/servis/MCP, eski şematik,
  IR/hesap/işaret ve dokuz yeni blok testi. [Koşu](../.pcbai-state/block-final-focused.txt).
  Önceki 228 tam takım 0.1.9 IR paketine aittir; bu farkın tek tam 237 koşusu yapılmış gibi sunulmaz.
- İlk test fixture'ında eski IR pin konumu 5 mm off-grid idi; 5,08 mm yapıldı. Diğer yanlış beklentiler:
  güncel ref context'i olmayan ikinci plan ve singleton ERC uyarısına rağmen erc_ok bekleme.
  Başarısız [ilk koşu](../.pcbai-state/block-first-tests.txt) ve
  [ara koşu](../.pcbai-state/block-focused-tests.txt) korunur; son tekrar yeşildir.
- Bağımsız denetçi **41/41**, skip yok, 99,153 sn; ayrıca gerçek preview/apply/tek checkpoint/
  frozen bytes/bayt eşit restore, signed marker done ve preview-evidence reddi, ERC identity injection.
  Yerleşim P2 (görünür property/free-text scene'e girmiyordu) düzeltildi; bağımsız field/text/sheet
  property recheck artık reddediyor. [Rapor](../.pcbai-state/audit-all-plan/add-block-review.md).
- Native ölçüm bir şematik SVG sayfası, 3 exact net, 0 hata/2 uyarı; candidate bytes tam eşit,
  checkpoint restore bayt eşit. [Ölçüm ve render](../.pcbai-state/block-measure/result.json).
- Kurulu **0.1.10**, gerçek özel HTTP servisi → MCP stdio ile `add_block` önizleme/apply ve
  checkpoint/restore tamamlandı; kaynak önizlemede değişmedi, geri yükleme bayt eşit,
  gerçek iki ERC uyarısı korundu. [MCP kayıt](../.pcbai-state/block-mcp-smoke.json).
- Ruff/lisans temiz; editable **0.1.10**, wheel **69 dosya**, core-only/schema import başarılı,
  harici ikili/plugin yok. [Paket](../.pcbai-state/block-wheel-check.json).
  SHA-256 `01d6d5fa4f1adb216469d749133ac204202528276d499f1f42117e97fa131f7a`.
- Ayrı eski P2: service-state proje içine seçilirse kendi retained `.lock` dosyası `editor_open`
  yaratır. Varsayılan LOCALAPPDATA state dışarıdadır. Bağımsız yeniden üretim raporda;
  bu paket configuration-state düzeltmesini veya planın tamamını kapatmaz.

## IR ve pasif blok çatısı — 12 Ekim 2026 (dal `ip/ir-bloklar`)

- Paketlenmiş kapalı Draft2020 IR şeması, boyutlu SI/range ayrıştırıcı; JSON boyut/düğüm/derinlik,
  NaN/Infinity/kontrol karakteri/bilinmeyen alan sınırları. Uzak şema veya kullanıcı kodu yürütülmez.
  Runtime `jsonschema>=4.26,<5`, şema wheel package-data içinde. [Sözleşme](ir.md).
- `circuit_blocks`: voltage_divider, low/highpass rc_filter ve pullup/pulldown button_debounce;
  sürüm/kapalı parametreler, gerçek Device:R/C + 0603 varsayılanları, literal port/pin haritaları.
  Tarifler olgunluk **0**; debounce dış kontak ağıdır, INPUT/OUT aynı fiziksel düğümdür.
- `plan_circuit`: benzersiz ID/literal pin/port/unit, gerçek sembol/footprint karmaları/pin-pad,
  kaynak-pin → ray-net birleşimi, ortak port aliasları, ray kısa devresi reddi,
  genişletilmiş 150 parça sınırı. Constraint başvurusu kontrol edilir; yerleşim uygulanmaz.
  Proje dosyası yazılmaz; `electrical=incomplete`, `ready_to_apply=false`, `production_verified=false`.
- `hand_calc`: sekiz sabit hesap; yüklenmiş bölücü/KCL/güç dengesi, RC kesim/yerleşme,
  LED hedef/tercihli direnç/gerçekleşen akım, varsayımsal LDO ısı, opamp, kristal ve E12/E24.
  Birimler, formül sürümü, özgün/normalize girdiler ve `calculated` kanıt ayrı kaydedilir.
- Uygulayan odaklı **15/15**, skip yok, 0,349 sn; gerçek genişletilmiş RC transient/AC dahil.
  Kurulu KiCad kütüphanesinde 5 parça/4 net ön denetimi **5,391 sn**, hepsi pin/pad uyumlu.
  İdeal RC transient beş noktada en büyük fark **%0,000177**; kesimde AC farkı **%1,716e-11**.
  [Ölçüm](../.pcbai-state/ir-measure/result.json). Birleşik divider/RC yük etkisi bu ölçümde yoktur.
- Bağımsız denetçi **42/42**, skip yok, 1,962 sn; yüksek geçiren RC ve yüklenmiş bölücü gerçek
  ngspice kıyasları, adversarial JSON/ölçek/net ve izole wheel/dependency import kontrolleri.
  Ruff/lisans temiz, kalan maddi bulgu yok. [Rapor](../.pcbai-state/audit-all-plan/ir-bloklar-review.md).
- Gerçek özel yerel HTTP servisi → MCP stdio akışında **4/4** kontrol: araç listesi, hesap/kanıt,
  IR ön denetim ve boolean miktar reddi. [Kayıt](../.pcbai-state/ir-mcp-smoke.json).
- Son sürüm/manifestte odaklı takım **15/15**, skip yok, 0,520 sn;
  [koşu](../.pcbai-state/ir-final-focused.txt). Ayrı gerçek KiCad CLI **11/11**, skip yok,
  295,993 sn; [kayıt](../.pcbai-state/ir-cli-tests.txt). Kullanıcı editörleri kapalıydı.
- Tam takım **228 test: 227 geçti, 1 Windows symlink yetkisi skip**, 800,626 sn;
  [koşu](../.pcbai-state/ir-full-tests.txt). Gerçek yazma/restore testleri atlanmadı.
  Ruff ve lisans denetimi temiz. Doctor, WSL dağıtımını boş/TraceMaker'ı eksik gösteriyor;
  önceki yeniden başlatma ihtiyacı sürüyor, S10/K5 kapatılmadı.
- Editable 0.1.9 kuruldu; son wheel **68 dosya**, paketlenmiş IR şeması, core-only import,
  yabancı motor ikilisi/plugin bağımlılığı yok. SHA-256
  `83e9f7f1d8589686f4ad36136ab0781232bc9952e6183f1e738d7fba1de7ee59`;
  [denetim](../.pcbai-state/ir-wheel-check.json). Çalışan eski servisler kendiliğinden güncellenmez.
- Bu ölçümler çoklu sayfa apply/UUID eşleme, gerilim/akım/STM32 AF, bağımsız datasheet/stok,
  11 olgunluk-1 blok, gerçek model kıyası veya fiziksel kart kabulünü kapatmaz.

## Yerel parça ve şematik yazımı — 12 Ekim 2026 (dal `ip/parts-sch`)

- `search_parts`: özel SQLite FTS5 dizini, parametreli/alıntılanmış sorgu, kalıtılan metadata,
  SHA-256 içerik yenileme; veritabanı/journal/WAL/SHM için symlink/junction/hardlink yazma engeli.
  Geçersiz kalıtım kayıtları atlanır ve `index_warnings` döner; indirilen katalog/stok yok.
- İlk tam CST dizin oluşturma yavaştı. Yalnız metadata için dengeli sözdizimi taraması eklendi;
  gerçek kurulu kütüphanelerde ilk arama **36,18 sn**, sonraki **0,29 sn**.
  [Ölçüm](../.pcbai-state/parts-measure/index-timing.json). Sembol/pin doğrulaması hâlâ tam CST ile yapılır.
- `part_info`: katı kalıtım çözümü, eksik/döngülü/çok derin ebeveyn ve yinelenen tanım reddi;
  birimler, ortak/varsayılan gövde pinleri, literal pin numaraları ve gerçek dosya karmaları.
- `verify_part`: benzersiz elektrik pin/pad numaraları, aynı pine birden fazla pad; NPTH/mekanik
  pad ayrı. Kullanıcı pin tablosu `caller_supplied`; stok, yaşam döngüsü, 3B ve bağımsız veri
  sayfası kabulü verilmez. Özel kütüphane lisansı bilinmiyorsa `unknown` kalır.
- `add_symbol`, `connect`, `add_label`, `replace_part`: immutable önizleme, aynı hedef/revizyon,
  kapalı editör/kilit, checkpoint, atomik yazım, gerçek kök ERC ve kanıt. Projedeki sembol
  önbelleği otoritedir; başka tanımla sessiz yenilenmez. Yeni kütüphane baytları adayda sabitlenir.
- Paylaşılan fiziksel sayfa ve yabancı proje/örnek kaydı olan dosyada yazma reddedilir.
  Pin kimliği/konumu/türü değişen veya birden çok dosyaya yayılan parça değiştirme reddedilir;
  kabul edilen değişimde sembol/pin UUID'leri korunur. 1,27 mm ızgara ve kardinal dönüş/ayna testli.
- `connect` sonucu ortak net ve tüm üyeler gerçek kök KiCad netlistinden ölçülür; aynı isimli mevcut
  bağlantılar da görünür. Yerel/global etiket desteklenir; hiyerarşik pin yaratımı ayrı iştir.
  Artımlı kurulumdaki ERC bulguları saklanmaz; `replace_part` yeni ERC hatası eklerse uygulanamaz.
- İşaret `done` kapısı yeni şematik/rota araçlarının hedef eşleşen gerçek değişiklik kanıtını kabul eder.
- Gerçek AMS1117-3.3 kalıtımı/SOT-223 çoklu pad/PWR_FLAG yerleştirmesi; iki direnç bağlantısı
  **ERC=0**, gerçek net üyeleri, bayt eşit checkpoint restore: odaklı **17/17**, 150,682 sn.
  Bu ölçümden sonra replacement/global label ve işaret kanıtı denetimi eklendi.
  Son global-label/replacement adayının gerçek özel-kopya ERC/netlist testi **1/1**, 4,403 sn;
  bu açık kullanıcı editörüyle gerçek apply kabulü değildir.
- Bağımsız denetçi ilk farkta **9/9** kendi testini çalıştırdı; foreign shared dosya, PWR_FLAG,
  metadata kalıtımı, NPTH ve ilk arama timeout bulguları uygulayan tarafından düzeltildi.
  [İlk bağımsız denetim](../.pcbai-state/audit-all-plan/parts-sch-review.md).
  Denetçi kullanım sınırına takıldığı için son farkın bağımsız tekrar koşusu tamamlanamadı;
  uygulayanın regresyonları bağımsız denetim diye sunulmaz. Claude Opus 5 salt okunur son
  kod denetimi de 240 sn'de zaman aşımına uğradı; geçerli sonuç yok (IKIZ-DEFTERI.md).
- Son tam takım **209 test: 195 geçti, 14 skip**, 326,077 sn; Ruff/lisans temiz.
  [Tam koşu](../.pcbai-state/parts-full-after-fix.txt). Skip: bir Windows symlink yetkisi,
  13 açık KiCad nedeniyle yazma deneyi. Kapalı ortamda önceki odaklı 17/17 ayrı ölçümdür.
  İlk tam koşu **209 test, 2 hata, 3 skip**, 650,022 sn:
  biri paketlenmiş çekirdeğin `kicad_plugin.configure` bağımlılığıydı (çekirdek permissions'a alındı,
  taze iki checkout + parça regresyonları **8/8** geçti); diğeri koşu sırasında açılan
  KiCad'in gerçek yazmayı doğru reddetmesiydi. Başarısız [ilk koşu](../.pcbai-state/parts-full-tests.txt)
  korunur; bulgular temiz kabulüne dönüştürülmez.
- Geliştirme ortamının build bağımlılıkları tamamlandı, editable çekirdek **0.1.8** kuruldu;
  `.pcbai-state/wheels/pcbai-0.1.8-py3-none-any.whl` üretildi. Eski çalışan servisler
  kaynak değişimini otomatik yüklemez; bu kurulum canlı kullanıcı oturumu kabulü değildir.
- Wheel yalnız çekirdek+MCP ile taze klasörde açılıp yeni araçlar import edildi; **61 dosya**,
  harici motor ikilisi/development plugin bağımlılığı yok. [Paket denetimi](../.pcbai-state/wheel-check.json).
- Ayrı zorunlu gerçek CLI takımında **11 test: 8 geçti, 3 açık-editör skip**, 167,210 sn;
  [kayıt](../.pcbai-state/parts-separate-cli.txt). Bunlar atlanan gerçek edit/restore kabullerini kapatmaz.
- Yeniden erişilebilen bağımsız denetçi son hedefli takımını kendisi çalıştırdı:
  **28/28**, skip yok, 5,925 sn; yerel parça/yazıcı/işaret ve özel-kopya native aday denetimi.
  Bu GUI açıkken kullanıcı projesinde gerçek apply değildir.
- Son inceleme üç ek P1 buldu: foreign **sheet** kayıtları/üst sayfa, iki projece kullanılan boş
  alt sayfa, UUID case/dash farkıyla gizlenen referans. Kaydedilmiş yetkili kökler ve ancestor
  sheet kayıtları taranır; bilinmeyen/bozuk graph fail-closed, UUID yolları kanonik kimlikle karşılaştırılır.
  Görünüm/netlist sayfa eşlemesi de aynı kimliği kullanır. Üç somut yeniden üretim artık reddediliyor.
- Kullanıcı KiCad'i kapattıktan sonra son kaynakta uygulayan geniş hedefler **61/61**, 214,926 sn;
  bağımsız denetçi **64/64**, skip yok, 244,967 sn. Gerçek G2 işaret → değer → done ve
  tüm authoring preview/apply/ERC/netlist/checkpoint/restore denetimleri dahil.
  [Uygulayan](../.pcbai-state/parts-final-focused.txt),
  [son bağımsız rapor](../.pcbai-state/audit-all-plan/parts-sch-final.md).
  Tam 209 takım önceki guard farkındadır; son fark için bu ayrı ölçümler kullanılır, 213 testin
  tek tam koşusu yapılmış gibi sunulmaz. Son leading-zero `#PWR01` referans deltası ayrıca **11/11**.
- Bağımsız taze FTS ölçümü: **39,484 sn / 0,391 sn**, 22.776 parça, uyarı yok;
  [kayıt](../.pcbai-state/audit-all-plan/parts-sch-final-index-timing-recheck.json).
  İlk audit helper SQLite stream'ini kapatmadığı için cleanup hatası verdi; ürün `closing()`
  kullanır, düzeltilmiş helper başarılıdır. Son wheel yeniden üretildi ve import denetimi geçti.

**Açık kabul:** katalog/JLC parça getirme, bağımsız veri sayfası/3B/stock, P2 stoklu devre,
çok dosyalı IR/alt sayfa yazımı ve canlı çakışma kabulleri. Bu paket Faz 2 kabulü değildir.

## Rota/yerleşim yazılımı — 12 Ekim 2026 (dal `ip/plan-tamamlama`)

- Yeni `route_engines`, `autoroute`, `autoplace`, `engine_preview`, `discard_candidate`.
  Önizleme işleri bağlantıdan bağımsız; uygulama iş olarak reddedilir, adayın ömrü sonuç hazırken başlar.
  Aynı hedef/SHA-256 revizyonu, kilit/editör, tekrar DRC, checkpoint, atomik yazım ve son kanıt korunur.
- Motorlar ayrı süreçte/private kopyada; program yolu yalnız env/PATH. TraceMaker native/WSL argv,
  açık Linux HOME/XDG ve GNU timeout; Freerouting native CLI veya açık Java/JAR yedeği.
  DSN/SES `pcbnew` yalnız ayrı KiCad Python worker'ında. Her koşunun argv/sürüm/girdi/çıktı karması
  kaydedilir; commit veya determinizm ölçülmediyse uydurulmaz.
- Bekçi: korunan düğümlerin baytları, yeni/geçerli/benzersiz UUID, net/katman/boyut; rota ve yerleşim
  yetkileri ayrı; kilitli parça/rota korunur. Yerleşimde konkav çentik/iç delik, dosyada farklı sıradaki
  courtyard kenarları ve uppercase UUID bağları denetlenir. DRC aynı sayıda farklı hata eklese de engeldir.
- Dökümler önce/sonra kopyada doldurulur. Legacy board syntax, DSN girdisinde orijinal kalır;
  ölçüm için hazırlanmış yeni fill düğümleri pcbnew'e format göçü gibi verilmez.
- VS Code **0.1.16** yeniden paketlendi/yüklendi; CLI listesi doğrulandı. Motor/bütçe seçimi,
  önce/sonra SVG, ölçü tablosu, ölçülmüş mm→SVG dönüşümüyle geçici tanı işaretleri, aynı adayla apply/cancel.
  Gerçek Chromium **fixture backend** ile UI/engelli aday/yanlış hedef/HTML güvenliği geçti;
  bu gerçek Extension Host veya gerçek kullanıcı kartı kabulü değildir.
- Gerçek JAR motoru, bize ait küçük rota düzeneğinde preview → gerçek önce/sonra SVG → apply →
  checkpoint'ten bayt eşit restore testini geçti. Gerçek ecc83 demo adayı yeni DRC üretince yazma reddedildi.
- Beş demo × iki JAR koşusu [güncel tabloda](../.pcbai-state/s4-current.md): ecc83 ve pic_programmer
  kalite engeline takıldı; video/interf_u kaynak UUID'leri zaten yinelenmiş; stickhub'ta korunan öğe farkı.
  **Varsayılan motor veya üretim kabulü verilmedi.** [S4](spikes/S4.md), [baseline](baseline-motorlar.md).
- Native Freerouting 2.5.0 Windows CLI ölçülen GraalVM `ComponentOutline` hatasıyla zaman aşımına uğradı;
  Java/JAR yedeği aynı resmi sürümle ve ayrı SHA-256 doğrulanmış Temurin JRE ile yerel `.tools/` içinde.
  Harici motor/JRE/bağlama PcbAi paketlerinde yok. CI denetimi yasak import/bağımlılık/binary paketlemesini
  kapsar; tüm transitif bağımlılıkların genel SPDX lisans kabulü değildir.
- Kullanıcı WSL + Ubuntu kurulumunu onayladı. Windows bileşenleri kuruldu, çıktı yeniden başlatma
  istiyor; bilgisayar yeniden başlatılmadı. Ubuntu/TraceMaker/S10/K5 kabulü açık; PCBench indirilmedi.
  Doctor: KiCad **10.0.4**, API ayarı **true**; canlı bağlantı kabulü çıkarılmaz.
- Bağımsız denetimde bulunan SPICE nested `.include`/code-model kaçışı düzeltildi; dosya parametreleri
  ve dış süreç modelleri reddedilir, modeller bellekte açılır. RC/Sallen-Key gerçek SPICE testleri geçti.

Bağımsız denetçi doğru `.venv`/KiCad Python 3.11.5 geliştirme ortamında tam takımı kendisi çalıştırdı:
**191 test, 190 geçti, 1 Windows symlink skip**, 543,853 sn. Ayrı gerçek CLI **11/11**, skip yok.
Son canonical UUID/dışhat/tanı farkı için ayrıca **20/20** bağımsız hedefli test, Ruff temiz.
Core full sonrası bu sınırlı delta ayrıca ölçüldü; bütün takım aynı delta için yeniden çalıştırılmış
gibi gösterilmez. `scripts/check_licenses.py` temiz; VSIX 0.1.16 engine dosyaları kaynakla bayt eşit.
İlk sistem Python 3.14 denetimi eski bridge timeout'u ve eksik `jsonschema` nedeniyle başarısızdı;
bu koşu silinmedi, yeni başarılı `.venv` koşusundan ayrı tutuldu.
Kayıtlar [tam takım](../.pcbai-state/audit-all-plan/final-unittest-dev.txt),
[ayrı CLI](../.pcbai-state/audit-all-plan/final-cli.txt),
[bağımsız inceleme](../.pcbai-state/audit-all-plan/final-review.md) altındadır;
önceki `docs/spikes/*-result.json` yayın kanıtları değiştirilmedi.

**Kalan ürün işleri:** Faz 2 katalog/getirme/tam parça doğrulama/P2; Faz 3 IR ve 11 olgun blok;
Faz 4 ileri SPICE ve 20+ olgun blok; PCB senkron/çerçeve/DFM/BOM/CPL/yerleşim kısıtları; G6 ve canlı
IPC yazma; gerçek Extension Host/PCM; orkestrasyon/kanıt raporu/uzak CI/model kıyası; iki fiziksel kart.
KiCad 11 geçişi uygun sürüm ortamına bağlıdır. Bu satırlar tamamlandı olarak işaretlenmedi.

## S5 SPICE — 11 Ekim 2026 (dal `ip/s5-spice`)

- KiCad'in `ngspice.dll`'i ctypes ile ayrı süreçte; netlist `kicad-cli sch export netlist --format spice`. Yeni `simulate` aracı (arka plan işi de olabilir), çekirdek **0.1.6**.
- Kabul: RC geçici cevabı elle hesaba göre en çok **%0,0002** (sınır %1). Gerçek sallen_key şematiği |H(f₀)| = 0,50001 (elle 0,5, %0,002). Beş simülasyon demosu çalıştı. [S5](spikes/S5.md).
- Güvenlik: şematikten gelen `.control` betikleri çalıştırılmaz; model dosyaları proje/KiCad dışında olamaz. SPICE model dosyaları artık snapshot'a ve revizyona dahil.

## Düzeltme: kicad-cli kullanıcı ayarlarına yazıyordu — 11 Ekim 2026

- **Ölçülen hata:** KiCad 10.0.4'te her `kicad-cli` çağrısı kullanıcının `%APPDATA%\kicad\10.0\kicad_common.json` dosyasındaki `system.working_dir` alanını çağrının klasörüyle değiştiriyor. PcbAi'nin ERC/DRC/SVG/GLB çağrıları bu yüzden alanı `…\Temp\pcbai-check-…` yapıyordu (AGENTS.md kuralının ihlali; önceki "ayar değişmedi" ölçümleri yalnız IPC deneyini kapsıyordu). Başka alan değişmedi; alan yalnız dosya iletişim kutularının başlangıç klasörüdür.
- **Düzeltme:** `pcbai.external.run` her kicad-cli çağrısını, kullanıcının ayar dosyaları + kütüphane tabloları + renk temalarının kopyalandığı geçici `KICAD_CONFIG_HOME/<sürüm>` ile çalıştırır. Kütüphane tablosu yoksa KiCad'in şablon tabloları konur (yoksa kicad-cli 0xC0000005 ile çöküyor — ölçüldü).
- **Kanıt:** ayar klasörünün SHA-256 sözlüğü tüm takımdan önce/sonra aynı (163 test, 162 geçti, 1 skip; gerçek CLI ve pcbnew kâhini dahil). Regresyon testi `tests/test_kicad_config.py`. Bedel: takım 438 → 612 sn.
- `working_dir` alanının eski değeri bilinmiyor; kullanıcı ayarı izinsiz değiştirilmedi.

## G4 etkileşimli 3B — 11 Ekim 2026 (dal `ip/g4-3b`)

- S9 olumlu ([rapor](spikes/S9.md)): KiCad GLB düğümleri referansla adlandırılıyor. `render_3d` aracı (revizyon önbelleği, GLB güvenlik denetimi); VS Code **0.1.9** 3B paneli. three.js paketi `GLTFLoader` eklenerek `scripts/build_three_vendor.mjs` ile CadAI'nın node_modules'undan **yalnız okunarak** yeniden üretildi; CadAI deposu değişmedi (git durumu temiz).
- Gerçek Chromium + yazılımsal WebGL: ecc83 / interf_u / pic_programmer açıldı; görünür bileşenlere tıklama 10/10, 21/21, 56/56 doğru; gizle/göster ve görünüm düğmeleri; kaynak baytları aynı. Eski model yolları yalnız görüntü kopyasında kurulu `.step`'e yönlendiriliyor (öncesinde ecc83'te 1, interf_u'da 0 seçilebilir bileşen vardı).

## Bölüm 4 kart düzenleme — 11 Ekim 2026 (dal `ip/pcb-duzenleme`)

- Yeni araçlar `move_footprint`, `set_track_width`, `add_zone`, `set_netclass` (preview/apply, checkpoint, kanıt). Önizleme gerçek DRC'yi önce/sonra ölçer; yeni DRC hatası uygulamayı `new_violations` ile engeller.
- **KiCad kâhini:** aynı işlemler KiCad 10.0.4'ün `pcbnew` Python'uyla da yapılıp UUID bazında karşılaştırıldı: ecc83 (2 kart), interf_u, pic_programmer, video, stickhub — **401 işlem, 0 fark** (konum, açı, katman, ayna, poligon/yay noktaları). İki gerçek hata bu yolla bulundu ve düzeltildi: poligon içindeki yayların yansıtılmaması; dökümde `filled_areas_thickness` eksikliği/karışık net biçimi (KiCad'in dolu kartı 1 hata, bizimki 80 → düzeltme sonrası 1, aynı `zones_intersect`).
- **KiCad 10 net adları:** `scene_pcb`, `list_nets`, `net_info` artık `(net "VCC")` biçimini okuyor (önce KiCad 10 kartlarında net adı boş dönüyordu; pic_programmer'da artık 111 net = şematik netlisti).
- Gerçek KiCad kabulü (demo kopyaları, KiCad kapalı): pic_programmer P101 işaretiyle 1 mm taşıma → done → bayt eşit geri yükleme; ecc83 R1 2 mm taşıması 0→14 DRC hatasıyla **reddedildi**, dosya değişmedi; iz işareti (0,8→0,7 mm) ve F.Cu GND alan işareti done; B.Cu'daki çakışan GND dökümü reddedildi; POWER net sınıfı 0,25 mm uygulandı, 1,0 mm 0→499 hatayla reddedildi, proje dosyası bayt eşit geri yüklendi.
- `python -m unittest discover -s tests`: **157 test, 156 geçti, 1 skip** (symlink). `ruff check .` exit 0.

**Sınır:** düzenlemeler dosya modundadır (KiCad kapalı olmalı); canlı IPC yazma yok. Rota bağlantısını koruyarak taşıma (izleri birlikte götürme) yok; DRC kapısı bunu engeller. Flip'te metin açısı KiCad'den 180° farklı yazılabilir (okunur tutma; görüntü aynı).

## G5 hızlı yenileme — 11 Ekim 2026 (dal `ip/g5-yenileme`)

- Ölçüm önce ([G5](spikes/G5.md)): eski yolda süre 8 ayrı kicad-cli çağrısındaydı (ecc83 3,8 sn servis).
- `render_pcb` tek `--mode-multi` çağrısı + gizli kalibrasyon katmanı; eşleme tutmazsa eski yol.
  `scene_pcb` net tablosu bir kez kurulur. Yoklama 500 ms / iş yoklaması 100 ms. VS Code **0.1.7**.
- Servis: ecc83 p50 0,81 sn; gerçek Chromium uçtan uca ecc83 10 ölçüm **p50 1,44 sn, p95 1,79 sn** — kabul geçti.
  pic_programmer 3,5 sn (kayıt). S7 hızlı yolda: 281 pad, en büyük hata 0,00005 mm.
- 142 test (141 geçti, 1 skip); `ruff check .` exit 0 (`.venv/Scripts/ruff.exe`; bu kabukta `python -m ruff`
  çıktıyı göstermiyor, çıkış kodu doğru). Kart ve şematik tarayıcı testleri geçti.

## G2 şematik görünümü ve şematik işaretleri — 11 Ekim 2026 (dal `ip/g2-sematik`)

- **S8** ([rapor](spikes/S8.md), `--publish` ile yazıldı): 6 demo, 18 sayfa örneği, **3510 pin bağlantı
  noktası** KiCad SVG köşesiyle 0,0 mm; sayfa matrisi ölçülerek birim; tüm netler (1089) netlistle aynı.
- Yeni araçlar `render_sch`, `scene_sch`, `hit_test_sch`; `start_job` `render_sch` kabul eder. Şematik
  işaretleri `sheet` örnek yolu ve UUID bağıyla; `get_markers` bağlı işarette `target_item` döner.
- VS Code **0.1.6** `PcbAi: Şematik görünümünü aç`; bu makineye kuruldu (`code --list-extensions`: 0.1.6).
- Ölçülen KiCad davranışı: ERC JSON konumları 100 kat küçük ve bazı bulgular yanlış sayfaya yazılıyor;
  görünüm yalnız UUID'si sayfada bulunan öğeyi çizer.
- `python -m unittest discover -s tests`: **142 test, 141 geçti, 1 skip** (symlink yetkisi). Gerçek CLI:
  complex_hierarchy sayfa/örnek/net testi ve "#1 bu direnç 4,7k olsun" → `set_value` (gerçek ERC) →
  `done` + change_id testi KiCad kapalıyken skip olmadan geçti. `ruff check .` exit 0.
- Chromium şematik kabulü (`npm run test:sch`, gerçek servis/CLI, demo kopyası): iki örnekte 30/30 sembol
  kendi referansıyla seçildi (Q2xx/Q3xx merkezinde kendi pini), R203/R303 ayrı; pin net vurgusu netlist üyeleriyle aynı; sayfalar arası net
  düğmesi diğer örneği açtı; çift tıklama alt sayfaya girdi; R203'e bağlı işaret kaydedildi, şematik
  baytları değişmedi, not HTML olarak yürümedi; video'da `/graphic/` ERC işaretleri C56/C57 konumunda,
  kökte yalnız J4. İlk yükleme yaklaşık 3 sn. Rapor `.pcbai-state/G2-browser-result.json`.
- Kart görünümü tarayıcı testi gerileme için yeniden koştu: 103 footprint, 10 DRC konumu, işaretler geçti;
  yenileme 4,4 / 7,0 / 7,1 sn (G5 kabulü hâlâ açık).

**Açık:** şematik paneli kart paneliyle aynı sekmede değil, ayrı komut. Bitmap içeren şematiklerin SVG'si
reddedilir. Bus üyeleri vurgulanmaz. Gerçek Extension Host'ta şematik komutu ve kullanıcının kendi
projesinde elle deneme yapılmadı. E-3, K-3/K-4 kullanıcı adımları bekliyor.

## Eksikler planı — ilk paket, 11 Ekim 2026

- **E-1:** önceki çalışma kayda alındı: `a6ad092` çekirdek, `48aa46b` VS Code/lisans,
  `646bb4c` plan ve eski ölçüm kanıtları. Çekirdek staging ağacının izole kopyasında 117 test
  (116 geçti, 1 symlink skip); VS Code staging ağacında 118 test (117 geçti, 1 symlink skip).
  İkisinde de Ruff exit 0. Belge/kanıt commit'inde aynı kod/test ağacının sonucu kullanıldı.
- **E-2 / K1:** kullanıcı LGPL-2.1-or-later kabul etti; [karar](decisions/0002-license.md).
  LICENSE, pyproject, VS Code manifest/kilit kaydı, KiCad manifest ve PCM metaverisi eşleşiyor.
  VSIX ve PCM ZIP lisans metnini içeriyor; üçüncü taraf MIT metinleri korunuyor.
- **E-4:** AGENTS.md'de bir paket/bir uygulayan/bir dal, yazan ikinci ajan için worktree ve
  salt okunur bağımsız denetçi kuralı var. Deneme raporları `.pcbai-state/` altında; Python `--publish`
  veya browser `PCBAI_PUBLISH_EVIDENCE=1` olmadan yayımlanmış kanıt yazımı yapılmıyor.
  Installer/config/Python/browser çıktılarında junction/hardlink sentinel regresyonları geçti.
- **K-1:** `kicad_plugin/dist/pcbai-kicad-0.1.3.zip` üretildi; kökte metadata, plugins altında
  çalışma dosyaları/lisans/24–48 px simgeler, resources altında 64×64 simge. Açık dosya listesi ve
  sabit ZIP metaverisi; iki üretim bayt eşit. `versions[].runtime="ipc"`. Kurulu KiCad 10.0.4'ün
  PCM v2 ve API v1 şemalarıyla doğrulandı; şema testi atlanmadı.
- **K-2:** paket konum dosyası taşımıyor. `PCBAI_ROOT` → dış kullanıcı `PcbAi/location.json` →
  açıklayıcı hata. Açık ama geçersiz ortam ayarı başka depoya düşmüyor. Aynı çıkarılmış paket iki
  gerçek kaynak kopyasında ayrı servis başlattı, doğru proje oturumu ve health döndürdü; servisler
  kapatıldı. KiCad API kullanılmadı; canlı IPC kabulü sayılmaz.
- Bağımsız Codex denetçisi çekirdekte 69 hedefli test + Ruff, paket/düzeltmelerde 14 test + Ruff ve
  güçlendirilmiş iki-servis testini ayrı çalıştırdı. S7 değişken gölgelemesi, hardlink yazımı ve browser
  junction kaçışı bulundu, düzeltildi ve yeniden denetlendi. İki Claude salt okunur çağrısı 180/120 sn'de
  zaman aşımına uğradı; geçerli denetim sayılmadı. Ayrıntı [defterde](../IKIZ-DEFTERI.md).
- S7 gerçek CLI deneyi tekrar koştu; `.pcbai-state/S7-result.json`: üç demo, 281 dairesel pad,
  en büyük hata yaklaşık 0,00005 mm, kaynak revizyonları değişmedi. `docs/spikes/*-result.json`
  önceki yayın kanıtları korundu. G5 için mevcut karesel scene maliyeti [ayrı kayıtta](spikes/G5.md);
  2 sn yenileme kabulü hâlâ açık.

**Açık:** E-3 KiCad yükseltme/API açılması (doctor hâlâ 10.0.4 / API kapalı); K-3 PCM'de gerçek kurulum;
K-4 gerçek KiCad düğmeleri. Kurulu VS Code hâlâ 0.1.4; 0.1.5 VSIX yalnız hazırlandı. G2 ve sonraki iş
paketleri uygulanmadı. Kullanıcı KiCad ayarları/kartları ve CadAI değiştirilmedi; uzak CI, SPICE, fiziksel
kart veya üretim kabulü verilmedi.

Son paket staging ağacının izole kopyasında `python -m unittest discover -s tests -v`:
**131 test, 130 geçti, 1 skip** (Windows symlink oluşturma yetkisi). Gerçek şematik edit/restore,
ortak hiyerarşi ve işaret→değer→done testleri bu kez skip olmadan geçti; açık editör koruması
gevşetilmedi. Ayrı `python -m unittest tests.test_kicad_integration -v`: **11/11 geçti**, skip yok.
Gerçek ecc83: ERC 0 hata/0 uyarı, DRC 0 hata/2 uyarı. PNG/Gerber/delik ZIP ve bayt eşit restore geçti.
Ruff staging ağacında ve güncel çalışma ağacında exit 0; görünüm kabulü bu sayılardan çıkarılmaz.

Ek Chromium 156.0.8078.4 koşusu exit 0: üç demoda **103 footprint seçimi**, **10 DRC konumu**,
üç kartta işaret kalıcılığı; ecc83'te dört işaret türü/düzenleme/silme. Kaynak kart baytları aynı.
Yeni [browser raporu](../.pcbai-state/G1-browser-result.json) ve [ekran görüntüleri](../.pcbai-state/viewer-e2e/)
yalnız `.pcbai-state/` altında. Eski yayın kanıtları git blob'larıyla karşılaştırıldı, değişmedi.
Yenileme 7,754 / 18,804 / 9,768 sn (diğer denetimlerle eşzamanlı koşu); G5 kabulü sayılmaz.

Ek gerçek Extension Host koşusu başarısız: beklenen rapor üretilemedi; geçici profil log dosyası
temizlenirken WinError 32/267. Kullanıcı profiliyle kabul yapılmış sayılmaz. Kalan kendi geçici
profil klasörünü silme işlemi otomatik onay denetiminde "blocked by policy" ile reddedildi;
klasörün kalanı geçici dizinde bırakıldı. Yerel [host logu](../.pcbai-state/eksikler-ilk-paket/host-audit.txt).

Yerel nihai ölçümler: [131 test](../.pcbai-state/eksikler-ilk-paket/e1-package-tests.txt),
[ayrı CLI](../.pcbai-state/eksikler-ilk-paket/final-cli.txt),
[staging sonucu](../.pcbai-state/eksikler-ilk-paket/e1-package-result.json),
[doctor](../.pcbai-state/eksikler-ilk-paket/final-doctor.json),
[paket SHA-256](../.pcbai-state/eksikler-ilk-paket/artifacts.json),
[eski yayın kanıtları değişmedi](../.pcbai-state/eksikler-ilk-paket/published-preservation.json).

## Çalışan yollar

- Ayrı git deposu; KiCad Python 3.11.5 ile yerel `.venv`; özgün stdlib servis/MCP kodu.
- KiCad 10.0.4 keşfi ve doctor; IPC kapalı/Freerouting eksik. Node 22.23.3 yerel `.tools/node` içinde;
  `scripts/dev-env.ps1` mevcut kabukta PATH/PCBAI_NODE ayarlar, sistem PATH’i değişmez.
- Açıkça kaydedilmiş dosya oturumları; şematik, footprint, PCB netleri ve proje özeti.
- Gerçek CLI ile izole proje kopyasında ERC/DRC; kaynak/kural/kütüphane SHA-256 revizyonu.
- Şematik PDF çıktısı; kanıt dosyaları ve geri alınabilir tek belge checkpoint'i.
- Değer düzenleme/geri yükleme: preview → candidate → aynı revision'da apply; çok birimli semboller.
- Ortak hiyerarşik sayfanın her örneği ayrı listelenir; Value önizlemesi etkilenen tüm referansları,
  birimleri, yolları ve diğer proje kayıtlarını gösterir. Boş proje adı kök UUID eşleşmesiyle desteklenir.
- Yeni Value kontrol karakterleri reddedilir; kalıcı yazma kilidi özel durumun `locks/` klasöründedir.
- Loopback HTTP + Bearer, private Windows DACL, singleton, tarayıcı Origin/Host reddi.
- MCP eski initialize ve modern discovery; gerçek stdio → servis araç çağrısı.

## Önceki doğrulama — 0.1.1

Doğrulama 71 ayrı testi kapsar: 65 çekirdek/servis/protokol testi ve 6 gerçek KiCad entegrasyon testi.
Windows symlink oluşturma yetkisi olmadığı için tek symlink testi skip edilir; junction testi gerçekten
çalıştırılıp geçmiştir. Tam takım son düzeltmelerden sonra yeniden çalıştırılmıştır: 70 geçti,
1 symlink testi atlandı. Ruff temizdir. Uzak CI koşulmadı; depoda remote tanımlı değil.

Gerçek ecc83 demo kopyasında:

- ERC: 0 hata, 0 uyarı.
- DRC: 0 hata, 2 uyarı (uyarılar başarı diye gizlenmez).
- R değerini düzenleme → gerçek ERC → checkpoint'ten geri yükleme: orijinal dosyayla bayt eşitliği geçti.
- Gerçek PDF üretimi geçti. Yanlış token, Origin, Host ve ikinci servis örneği reddedildi.
- İki istemci aynı oturumları gördü; ölmüş servis yeniden başlatıldı; MCP stdout yalnız JSON idi.
- Kurulu 162 s-expr dosyasının 161'i strict parser ile okunup aynı bayt döndürüyor. Bir demo PCB
  (`royalblue54L_feather/RoyalBlue54L-Feather.kicad_pcb`) bozuk parantez yapısı nedeniyle reddediliyor;
  KiCad CLI bunu toleransla açıyor. Dosya değiştirilmedi. S2'nin %100 parse kabulü henüz sağlanmadı.

Gerçek complex_hierarchy demo kopyasında R203 ve R303 ayrı listelendi; her iki referansın önizlemesi
aynı aday dosya karmasını ve iki etkiyi verdi. R303 üzerinden yapılan düzenleme sonrası gerçek KiCad
XML netlistinde **R203=47k ve R303=47k** ölçüldü; checkpoint'ten geri dönüş bayt eşit geçti.
Kurulu 115 şematiğin tamamı örnek okuyucuyla tarandı; boş proje adı kayıtları dahil okuma hatası yok.
Sentetik testler ayrıca çok birim, yabancı proje/kök, belirsiz birim, eski referans, metaveri çakışması,
kontrol karakteri, etkisiz uygulama ve denetim arızasında etki listesinin korunmasını kapsar.

## Denetim sonrası plan ve depo

- 0.1.0 çekirdeği `ab5f5fb` commit'iyle kayda alındı; düzeltmeler ayrı commit'tedir.
- PLAN 3.4 / İP-2.3, uygulamadaki SHA-256 blob + manifest geçmişiyle eşitlendi. Proje checkpoint'i git değildir.
- Kart 2, doğrulanmış v0.6 tasarımından Faz 7 ilk haftasında sipariş edilecek; teslim/ölçüm için
  29–30. hafta tamponu öncelikli. Fiziksel ölçüm olmadan v0.8 kabulü yok.
- K1 lisans kararı açık; bu yüzden LICENSE henüz eklenmedi. Uzak CI yerel test diye gösterilmez.

### VS Code ve KiCad eklentileri — 11 Ekim 2026

- `vscode/pcbai-vscode` (düz JS, VSIX stdlib ile paketlenir) ve `kicad_plugin` (KiCad 10 IPC, `plugin.json` KiCad'in
  `api.v1` şemasıyla doğrulandı) eklendi; ikisi de bu makineye kuruldu.
- Gerçek servise karşı doğrulandı: VS Code komutları VS Code'un Node'uyla sahte `vscode` modülü üzerinden;
  KiCad eklentisi KiCad'in Python'uyla sahte kipy üzerinden (ecc83 kopyası: ERC 0/0, DRC 0 hata/8 uyarı, iki proje
  kaydında servis birleşik listeyle yeniden başladı); eklentinin yazdığı `.mcp.json` ile MCP vekili 2 oturum gördü.
- **Gerçek KiCad içinde düğmeye basılarak denenmedi:** KiCad API bu makinede kapalı; açılıp düğmeler denenmeli.
- `mcp_server/client.py`: proje listesi eşitlik yerine alt küme olarak karşılaştırılır (paylaşılan servis); testli.

### Faz 1 ilerlemesi — 0.1.2, 11 Ekim 2026

- `start_job` / `job_status`: bağlantıdan bağımsız salt okunur işler; zorunlu hedef/revizyon, 4 aktif iş sınırı,
  100 sonuç sınırı, kapanışta bekleme. Yazma işleri kabul edilmez; eski revizyonda başlamaz/sonuç vermez.
- `board_stats`: gerçek KiCad CLI JSON raporu; mm boyutlar ve footprint sayısı kanıt kaydına bağlı.
  ecc83 kopyası **52,0700 × 46,3550 mm, 15 footprint**; okuyucu sayısıyla eşleşti.
- `render_board`: gerçek PNG, kaydedilmiş projenin kopyasında. `export_fab`: tüm bakır katmanları, maskeler,
  ipek, kart kenarı ve Excellon delikleri ZIP + dosya karmalarıyla. Kaynak revizyonu değişmedi.
  Gerber X2 `FileFunction` kayıtlarıyla üst/alt bakır ve profil doğrulandı; özel katman adları destekleniyor.
  BOM/CPL, DFM veya üretim kabulü iddia edilmez.
- PDF/PNG/ZIP kanıt kaydına bağlanır; işlem sırasında kaynak değişirse çıktı silinir.
  KiCad 10.0.4 render istek boyutundan farklı PNG üretebiliyor; araç gerçek dosya boyutunu döndürür.
- `net_info`: tam net adıyla pad üyeliği ve segment/via sayısı; pad konumu açıkça footprint-local.
  Proje özetine PCB net/katman/segment/via sayıları ve tutarlı revizyon kontrolü eklendi.
- `discover_ipc`, `live_board_summary`, `get_selection`: salt okunur kanallar, kayıtlı proje/belge eşleşmesi,
  açık kanal kimliği, 5 saniyelik ayrı süreç sınırı. Canlı yazma/save/revert yok; dosya yazma engeli korunuyor.
- **S1 kısmi gerçek ölçüm:** geçici ayarlarla bir PCB'de belirteçsiz bağlantı, proje yolu, tampon ve boş seçim
  okundu. İkinci PID kanalına erişilemedi. Kullanıcı ayarlarının SHA-256 sözlükleri değişmedi;
  kullanıcının açık KiCad proje yöneticisi kapatılmadı. [Deney ve sınırlar](spikes/S1.md).
- VS Code **0.1.3**: kayıtlı kart PNG önizlemesi ve gerçek kart ölçümleri komutları; arka plan işlerini kullanır.
  PNG webview'ında betikler kapalı, CSP/çıktı klasörü sınırı ve metin kaçışları var. Node testi VS Code'un
  Electron çalışma zamanında sahte `vscode` + yerel sahte servis ile geçti; gerçek Extension Host içinde
  panel açma ölçülmedi. VSIX paketlendi, bu oturumda yeni paket kurulu VS Code'a yüklenmedi.

Önceki 0.1.2 tam koşu: `python -m unittest discover -s tests -v` — **96 test, 93 geçti, 3 skip**.
Symlink oluşturma yetkisi yok; açık kullanıcı KiCad proje yöneticisi nedeniyle iki gerçek yazma/restore
testi atlandı. Sentetik yazma regresyonları yalnız süreç listesini yalıtır; gerçek kilit dosyası ve OS kilidi
kontrolleri korunur. Proje yöneticisinin yazmayı engellemesi ayrıca testlidir. Önceki 0.1.1'deki gerçek
yazma/restore kanıtı bu koşuda tekrar ölçülmüş sayılmaz. Uzak CI ve gerçek VS Code Extension Host denenmedi.
`python -m unittest tests.test_kicad_integration -v` ayrıca çalıştırıldı: **8 test, 6 geçti, 2 skip**
(aynı açık editör nedeniyle yazma testleri). `python -m ruff check .` temiz;
`python -m pcbai doctor` çekirdek 0.1.2 / KiCad 10.0.4'ü doğruladı. Doctor bağlantı deneyi yapmaz;
S1'in geçici ayarlarla ölçülen sonucu, kullanıcının API ayarını açık hâle getirmez. SPICE henüz ölçülmedi.

### Görünüm — 0.1.3 çekirdek / 0.1.4 VS Code, 11 Ekim 2026

- **G0:** SHA-256 doğrulanmış Node 22.23.3, yerel MIT three.js/three-mesh-bvh paketi, `media/`,
  nonce CSP’li panel. CadAI uygulama kodu değiştirilmedi. Gerçek VS Code **1.141.0** Extension Host’unda
  hem boş panel hem gerçek servis üzerinden ecc83’ün **7 yerel SVG katmanı** yüklendi. Kullanıcı profili,
  eklenti klasörü ve servis durumu bu kabul deneyinde yalıtıldı.
- **S7 PCB alt-deneyi:** üç demo kopyasında **281 dairesel pad**; en büyük hata **0,00005 mm**,
  sınır **0,05 mm**. Ön/arka yüzün asimetrik pad koordinatı gerçek CLI ile ayrıca doğrulandı.
  Kalibrasyon daireleri yalnız kopyaya yazılır. Şematik SVG ve GLB dönüşümleri henüz ölçülmedi.
- **G1:** `scene_pcb`, `render_pcb`, `hit_test`; tüm bakır katmanları, ipek/fab/kenar SVG’leri;
  katman aç/kapa, zoom/pan, hover, tıklama ve çakışan öğe seçimi. Chromium’da ecc83/interf_u/pic_programmer
  üzerindeki **103 footprint merkezinin tamamı** doğru referans verdi. Gerçek DRC’nin **10 konumu** doğru
  çizildi (pic_programmer’de konumlu bulgu yok). Kaydedilmemiş KiCad tamponu gösterilmez.
- **G3 PCB:** nokta/çizgi/alan/UUID öğesi; numaralı notlar, önizleme/uygulama, düzenleme/silme,
  checkpoint, HMAC ve OS yazma kilidi. Projede `pcbai/markers.json` saklanır; paneli yeniden açınca
  kayıtlar korundu, kart baytları değişmedi. Tam dört tür ve düzenleme/silme ecc83’te; kalıcılık
  üç kartta tarayıcıyla ölçüldü. UUID taşınma/dönüş ve silinince kopuk bağ birim testlidir.
- MCP `get_markers` gerçek stdio → servis ile okundu. `pcbai://markers` ve açık oturumlu `apply_markers`
  var. Ajan yalnız imzalı işareti gerekçeyle `blocked` veya aynı hedefteki `change_id` kanıtıyla `done`
  yapabilir; durum yazımı da preview/apply’dır. İşaret oluşturma/silme yalnız `/view/call` yolundadır.
- **G3 tam kabulü açık:** şematik koordinat şeması ve işaret → `set_value` → kanıtlı `done` regresyonu
  var; şematik görünümü, sembol/pin/net bağları ve şematik işaret arayüzü **G2’yi bekler**. Gerçek
  şematik değer değiştirme kabul testi açık kullanıcı KiCad’i nedeniyle skip oldu; koruma gevşetilmedi.
- **G5 kısmi:** revizyonla otomatik yenileme ve “Ajana sor” isteğini panoya kopyalama var. Son tarayıcı
  koşusunda yenileme **5,422 / 7,868 / 9,580 sn**; **2 sn kabulü geçmedi**. Eski DRC sonuçları yeni
  revizyonda temizlenir. G2, G4, G6 ve K-1–K-4 tamamlanmadı; kullanıcı kartında elle kabul yapılmadı.
- VSIX paketlendi ve **yüklendi**; gerçek CLI listesi `taymur.pcbai-vscode@0.1.4` doğruladı.
  Açık kullanıcı VS Code penceresi yeniden yüklenmeli; eski servis yeni çekirdeği yüklemek için yeniden
  başlatılmalı. Kullanıcı KiCad ayarları/kartları deneylerde değiştirilmedi. Git commit oluşturulmadı;
  önceki çalışma ağacı ve bu değişiklikler birlikte duruyor, HEAD hâlâ `0ff61f3`.

Son tam koşu: `python -m unittest discover -s tests -v` — **118 test, 114 geçti, 4 skip**.
Skip’ler: Windows symlink oluşturma yetkisi ve açık KiCad nedeniyle üç gerçek şematik yazma testi
(edit/restore, ortak hiyerarşi, yeni işaret→değer→durum kabulü). Gerçek CLI ayrı koşusu:
`python -m unittest tests.test_kicad_integration -v` — **11 test, 8 geçti, 3 skip**.
`python -m ruff check .` ve üç JS dosyasının Node syntax denetimi temiz. Doctor çekirdek 0.1.3,
KiCad 10.0.4 ve etkin geliştirme kabuğundaki Node yolunu doğruladı. Uzak CI, canlı IPC, SPICE,
fiziksel kart ve üretim doğrulaması bu testlerden çıkarılamaz.

Kanıtlar: [S7](spikes/S7.md), [281 pad ölçümü](spikes/S7-result.json),
[gerçek Extension Host](spikes/G0-host-result.json), [tarayıcı](spikes/G1-browser-result.json).

## Tamamlanmamış kabul koşulları

- Faz 0: KiCad yükseltme, S1'in iki oturum kabulü ve S3 canlı deneyleri, S4–S6 ve S7 şematik/GLB; katalog ve lisans kararları; P1–P6 referans
  kartlar ve dört rakiple kıyas. Var olmayan ölçümler tamamlanmış gösterilmiyor.
- Faz 1: çok örnekli GUI IPC keşfi, dolu seçim ve unsaved/revert ölçümleri; kullanıcı kartında elle VS Code kabulü.
  Uzun işler, render ve temel dışa aktarım uygulandı; tüm fazın kabulü hâlâ açık.
- Faz 2+: sembol ekleme/bağlama, parça ve stok doğrulama, IR/bloklar/SPICE, PCB yerleştirme ve rota,
  Gerber/BOM/CPL, şematik/3B/çapraz görünüm, G3 şematik kabulü, orkestrasyon, kanıt raporu ve fiziksel iki kart doğrulaması.
- GitHub Actions dosyası eklendi; uzak CI bu oturumda çalıştırılmadı. KiCad olmayan CI'da gerçek CLI
  testleri açıkça skip edilir; yerel gerçek CLI kanıtının yerini tutmaz.
- 0.1.0 için İkiz bağımsız plan tamamlandı. Geniş kod denetimi 300 saniyede zaman aşımına uğradı; geçerli
  sonuç sayılmadı. Odaklı ikinci denetim başarılı; üç bulgunun doğrulanan kısımları düzeltildi ve
  [deftere](../IKIZ-DEFTERI.md) işlendi. İki ayrı yazan uygulama ve düzeltmelerin B tarafından tekrar
  denetimi yapılmadı; ana ajan regresyon testlerini ve gerçek CLI kontrollerini çalıştırdı.
- 0.1.1 için bağımsız plan başarılı; geniş denetim 180 saniyede zaman aşımına uğradı. Daraltılmış
  model denetimi başarılı oldu; kök filtresi, yinelenmiş Value ve uyarı metniyle ilgili üç bulgu
  yeniden üretilip düzeltildi. Son düzeltmelerin B tarafından tekrar denetimi yapılmadı;
  iki bağımsız yazan uygulama veya bağımsız kilit/engine onayı iddia edilmiyor.

## Sonraki iş paketi

G2 ve G3 şematik tamamlandı (yukarıda). Görünüm izinde sıradaki G5 için 2 sn
yenileme optimizasyonu; KiCad paketi K-1–K-4 ayrı iş. Ana planın canlı izinde S1 ikinci kanal ve S3
disk/tampon/revert ölçümleri, dolu seçim; ardından P2 ve doğrulanmış sembol/pin/footprint dizini. Bu altyapı
üzerine IR ve SPICE testli bloklar. Üretim kabulü gerçek kart ölçümü olmadan verilmeyecek.
