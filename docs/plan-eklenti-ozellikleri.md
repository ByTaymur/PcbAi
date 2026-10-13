# Plan — VS Code eklentilerinden PcbAi'ye faydalı özellikler

13 Ekim 2026 · Durum: **EK-0 tamam; EK-1/2 işlevleri uygulandı; EK-1 bozuk kural ret kabulü ve EK-2 geniş korpus performans hedefi açık**.
Başlangıç ağacı: `main/2cd413a`, çekirdek 0.1.22, VS Code 0.1.16.
Bağlı: [RD planı](plan-referans-depolar.md), [görünüm planı](plan-gorunum.md),
[uygulama durumu](status.md), [eksikler](plan-eksikler.md).

Amaç: kural yazımını kolaylaştırmak, parça/pin bilgisini yazarken göstermek, değişiklikleri
görsel incelemek ve üretim çıktısını bağımsız ölçmek. Mevcut şematik/PCB görüntüleyicisi,
parça indeksi, önizleme/checkpoint, bulgu şeması ve manifest yeniden kullanılır.

Bu belge yeni bir takvim taahhüdü değildir. Süreler ilk tahmindir; RD-C2/RD-B8 gibi
mevcut bağımlılıkların yapım süresi bu tahminlere dahil değildir. Birleşik main tam takım
ve kapanış ölçümü [status.md](status.md) içinde kayıtlıdır; açık kabul sınırları korunur.

## 1. Kaynaklar ve alınacak fikir

| Kaynak | Belgelenen özellik | PcbAi karşılığı |
|---|---|---|
| [KiCad Custom Design Rules](https://cimos.github.io/vscode-kicad-dru-extension) | DRU renklendirmesi ve snippets; doğrulayıcı yok | EK-1 kural editörü |
| [SKiDL IntelliSense](https://marketplace.visualstudio.com/items?itemName=ashergarland.skidl-lsp) | Parça/pin tamamlama, hover ve tanılama | EK-2 mevcut IR/parça araçlarının editör arayüzü |
| [KiCad Viewer — geliştiricinin açıklaması](https://forum.kicad.info/t/kicad-viewer-vscode-extension-for-viewing-diffing-kicad-files/69515) | KiCad CLI ile SVG önizleme ve görsel diff | EK-3/EK-3b; mevcut RD-I5/RD-B8 |
| [Gerber X3/X2 Format Support](https://github.com/Argmaster/vscode-gerber-format-support) | PyGerber dil sunucusu, komut yardımı ve sınırlı render | EK-4/EK-5; mevcut RD-I2/RD-C2 |

Bunlar yazar belgelerinden çıkarılmış adaylardır; PcbAi'de kurulum/uyumluluk ölçülmüş değildir.
Başlangıç tercihi kendi arayüzümüzü geliştirmek ve mevcut çekirdeği kullanmaktır.
Upstream kod alınırsa sabit commit, lisans metni, kaynak/yerel değişiklik kaydı ve bağımlılık
denetimi uygulama paketinde tamamlanır. Dört eklentiyi birlikte kurmak planın bir adımı değildir.

## 2. Sıra ve kapsam

| Paket | Teslim | Bağımlılık | Tahmini iş günü |
|---|---|---|---|
| EK-0 | Uyumluluk ve kaynak incelemesi | Birleşik main kabulü | 0,5–1 |
| EK-1 | DRU renklendirmesi ve kural şablonları | EK-0 | 1–2 |
| EK-2 | IR/parça panelinde tamamlama ve hover | EK-0, mevcut parça araçları | 2–3 |
| EK-3 | Önizlenen değişikliğin görsel farkı | EK-0, mevcut render/aday altyapısı | 3–5 |
| EK-4 | Gerber inceleme paneli | EK-0, mevcut export_fab | 2–3 |
| EK-5 | İki Gerber okuyucusuyla kıyas | EK-4, RD-C2 okuyucusu, RD-A4 | 3–5 |
| EK-3b | Geçmiş revizyon/checkpoint karşılaştırması | EK-3, RD-B8 ve tam snapshot altyapısı | 2–3 |

EK-0…EK-5 toplamı **11,5–19 iş günü**; tarihsel diff ile **13,5–22 iş günü**.
RD-I2/RD-I5 işleri bu planla birlikte sayılır; RD planına ikinci kez süre eklenmez.
Bu plan eski RD-I2 2 gün / RD-I5 4 gün tahminlerinin yerine EK-5 3–5 gün /
EK-3+EK-3b 5–8 gün tahminlerini önerir: aynı kapsamdaki net artış **2–7 gün**.
EK-0/1/2/4 yeni kapsamının 5,5–9 günüyle özellik kapsamının net eki **7,5–16 gün** olur.
Bu tam master plan bütçesi değildir: tam tarihsel snapshot yakalama/materialize altyapısının
sahibi **RD-B8s**, süresi spike sonrası ayrıca tahminlenecektir. RD-C2/RD-B8 süreleri kendi
paketlerinde kalır; ana takvim tarihleri burada değiştirilmez.
İlk teslim EK-0/1/2'dir (**3,5–6 gün**). Görsel diff ayrı teslimdir; Gerber işleri kendi
üretim doğrulama dalgasına bağlanır. Takvim sıkışırsa önce EK-3b, sonra EK-4'ün komut hover'ı ertelenir.

## EK-0 — uyumluluk ve kaynak incelemesi

- Her adayın kaynak deposu/commit'i, lisansı, desteklediği biçimler ve bağımlılıkları kaydedilir.
- VS Code manifestinin ilan ettiği minimum sürüm ile kurulu sürümde gereken API'ler kontrol edilir.
  Yeni custom diff API'si zorunlu yapılmaz; mevcut webview ile yan yana/üst üste gösterim temel yoldur.
- Beş KiCad demosu, complex_hierarchy ve küçük hatalı dosyalar kabul korpusu olur.
  Yalnız özel kopyalar ve uygulayana ait durum dizini kullanılır.
- PyGerber'in güncel Gerber ve Excellon kapsamı ayrıca denenir. Excellon desteklenmiyorsa
  o kontrol `skipped` kalır; diğer okuyucunun Excellon sonucu çift doğrulanmış sayılmaz.
- **Bitti:** `docs/spikes/EK0.md` uyumluluk matrisi, açık sınırlar ve seçilen yaklaşımı içerir.
  Geliştirme ham çıktıları `.pcbai-state/eklenti-ozellikleri/`; yayın JSON'u yalnız açık yayın koşusunda.

## EK-1 — kural editörü

- `.kicad_dru` için dil tanımı, yorum/parantez/folding, kural/koşul/kısıt renklendirmesi.
- Clearance, iz genişliği, via boyutu, yasak alan ve uzunluk eşleme şablonları.
  Şablonlar düzenlenebilir örnektir; üreticiye uygunluk etiketi verilmez.
- Statik JSON grammar/snippets; ayrı LSP veya otomatik paket kurulumu gerekmez.
  Dosya yazma kullanıcının normal VS Code düzenlemesidir; yeni MCP yazıcı eklenmez.
- **Dosyalar (öneri):** `vscode/pcbai-vscode/package.json`, `syntaxes/kicad-dru.tmLanguage.json`,
  `snippets/kicad-dru.json`, `language-configuration/kicad-dru.json`.
- **Kabul:** örnek kurallar grammar/folding/snippet kontrollerinden geçer; gerçek KiCad kopyasında
  geçerli kural kabul edilir, bozuk kural reddedilir. Renklendirme doğrulama yerine geçmez.
- **Testler (planlanan):** `test/dru.test.js`; gerçek Extension Host'ta dosya açma ve snippet ekleme.

## EK-2 — parça/pin yardımı

- İlk kapsam PcbAi IR JSON `parts[].symbol`, `parts[].footprint`, `parts[].unit` ve
  `connections[][]` literal pin endpoint'leridir. `symbol` araçların `lib_id` alanına eşlenir.
  Parça arama arayüzü ve editör adaptörü yeni teslimdir; mevcut VS Code parça paneli yoktur.
  Yalnız `*.pcbai-ir.json` / `*.pcbai.json` dosyaları otomatik seçilir; genel JSON kapsam dışıdır.
- `search_parts`, `part_info`, `verify_part` ve IR JSON Schema yeniden kullanılır.
  Hover'da kütüphane kaynağı ve SHA gösterilir; pin/pad eşleşmesi stok veya datasheet kabulü değildir.
- Kaydedilmemiş IR metni sınırlı JSON verisi olarak ayrıştırılır. Kısmi/bozuk tampon için
  yalnız uygun tamamlama verilir; geçerli tasarım veya kaydedilmiş revizyon iddiası üretilmez.
- Önbellek kütüphane SHA ve oturum/revizyon kapsamlıdır. Eski sorgu yanıtı yeni tamponu değiştirmez.
  Yanıt belge URI/tampon sürümüyle eşlenir; hover metni kaçışlanır ve çalıştırılabilir Markdown/HTML kabul edilmez.
  Şematik metninde caret→UUID/sayfa çözümü ve SKiDL Python desteği sonraki genişlemedir.
- **Dosyalar (öneri):** `extension.js`, `part_assist.js`, `package.json`, mevcut IR şeması bağlantısı.
- **Kabul:** yanlış lib_id/pin için gerçek yerel alternatif; `01` ve `1` ayrı; çoklu birim ve
  farklı oturum sonuçları karışmaz; kütüphane değişince cache yenilenir.
  Sembol arama metadata indeksidir; footprint alternatifleri sembolün gerçek Footprint kaynağıyla
  sınırlanır. Yeni genel footprint arama indeksi bu teslimde yoktur.
  SHA güncellik kontrolü ile tampon/oturum kapsamlı cache birlikte tasarlanır; debounce tek başına
  sorgu gecikmesini azaltmaz. Mevcut arka uç ön ölçümünde sıcak sorgu 299–321 ms idi.
  Sıcak tamamlama için önerilen hedef p95 ≤150 ms; donanım/korpus/süre raporlanır, ölçülmeden karşılandı denmez.
- **Testler (planlanan):** `test/part_assist.test.js`; gerçek kütüphaneyle hover/tamamlama Host ölçümü.

## EK-3 — önizleme görsel farkı

- İlk teslim kayıtlı proje ile aynı revizyondan üretilmiş frozen adayın karşılaştırmasıdır.
  Mevcut motor before/after görünümü diğer PCB ve şematik adaylara genişletilir.
- Yan yana, üst üste ve saydamlık; eklenen/silinen/taşınan öğeler listesi. Değer/lib_id
  değişimi de listede görülür. Liste UUID, literal referans ve sayfa örneğine bağlıdır.
- Önce/sonra render'ı aynı doğrulanmış proje snapshot'ında aday override'ıyla ölçülür.
  SVG hizası ölçülen mm dönüşümleriyle kurulur; farklı zoom veya sayfa sırası değişiklik sayılmaz.
- Yeni okuma sözleşmesi: `design_preview(session, document, revision, candidate_id)`;
  `before`, `after`, `changes`, `inputs_sha256`, `evidence_id`, `limitations` döner.
  Revizyon değişmiş/aday süresi dolmuşsa yenisi istenir; kullanıcı dosyası yazılmaz.
- **Dosyalar (öneri):** `pcbai/verify/design_diff.py`, `tools/engine.py`, mevcut render modülleri;
  VS Code `diff_view.js`, `extension.js`, `package.json`.
- **Kabul:** yalnız değer değişimi, 0,01 mm taşıma, ekleme/silme ve hiyerarşik sayfa örneği doğru
  ayrılır; değişmeyen proje diff'i boş; farklı SVG kökeni yanlış hareket üretmez.
  DRC/bulgu farkı ve görsel geometri farkı ayrı gösterilir. Genel bus kapsamı ölçülmeden tamamlandı denmez.
- **Testler (planlanan):** `tests/test_design_diff.py`, `test/diff.e2e.js`; gerçek CLI ve Host kıyası.

## EK-3b — geçmiş tasarım karşılaştırması

- Mevcut checkpoint tek belge baytlarını saklar; bütün eski projeyi yeniden kurduğu varsayılmaz.
- Ayrı **RD-B8s** paketiyle tam proje dosya/hash manifesti, kütüphane bağımlılık envanteri ve
  gerekli blob'lar yakalanır; bütünlük ve eksik blob kabulü bu pakete aittir. RD-B8 veri diff'idir.
  RD-B8s henüz uygulanmadı ve süresi bu EK toplamına dahil değildir. Git revizyonları
  da ayrı, sınırlandırılmış kopyalarda materialize edilir. Git/kaynak dosyaları kod olarak yürütülmez.
- Eksik geçmiş bağımlılığı varsa kapsam açıkça kısmi gösterilir; bugün kaydedilmiş başka dosyalar
  sessizce eski tasarıma karıştırılmaz. Tam geçmiş ERC/netlist kıyası bu durumda atlanır.
- **Bitti:** iki tam snapshot için geçmiş şematik/PCB farkı; eksik snapshot için dürüst kısmi kapsam.
  Bu paket mevcut **RD-I5/RD-B8** kapsamını tamamlar, EK-3 MVP'si tek başına RD-I5'i kapatmaz.
- **Testler (planlanan):** `test_missing_snapshot_blob_is_incomplete`, `test_missing_library_dependency_is_incomplete`,
  `test_current_child_sheet_not_used_as_historical_input`, `test_two_complete_snapshots_have_stable_diff`.

## EK-4 — Gerber inceleme paneli

- `export_fab` çıktısından dosya/katman seçimi, zoom/pan ve sınırlı komut açıklamaları.
- Gerber X2 FileFunction bilgisi varsa kullanılır; yalnız dosya uzantısından katman uydurulmaz.
- İsteğe bağlı PyGerber adaptörü ayrı süreçte, yapılandırılmış yorumlayıcıyla, timeout/boyut
  sınırı ve `shell=False` ile çalışır. Kullanıcı dosyasına veya global Python ortamına otomatik kurulum yoktur.
- SVG mevcut güvenlik süzgecinden geçirilir; uzak içerik ve dosya kaynaklı betik çalışmaz.
  Açma/render başarısı üretim kabulü diye gösterilmez.
- **Dosyalar (öneri):** `pcbai/fab/gerber_preview.py`, `doctor.py`, `tools/engine.py`,
  VS Code `gerber_view.js`, `extension.js`, `package.json`.
- **Kabul:** bakır/maske/profil görünümü; mm/inç, yay, negatif polarite örnekleri; bozuk/büyük dosyada
  kontrollü hata; eksik araç için `skipped` + kayıtlı limit. Gerber önizlemesi var diye RD-C2/RD-I2 kapanmaz.
- **Testler (planlanan):** `tests/test_gerber_preview.py`, `test/gerber.e2e.js`.

## EK-5 — bağımsız Gerber okuyucu kıyası

- Mevcut **RD-I2** gerçekleştirilir: RD-C2 okuyucusu ve PyGerber aynı giriş hashlerini inceler.
- Katman/aperture, flash/çizgi/yay sayıları ve bbox birim/polarite normalizasyonuyla karşılaştırılır.
  İki okuyucu aynı yüksek seviye sonucu vermiyorsa neden ve kapsanan komutlar gösterilir.
- Uyuşmazlık A1 `source=calibration` bulgusudur; kartın elektriksel hatası diye sınıflanmaz.
  Eksik okuyucu veya desteklenmeyen biçim A2 manifestinde görünür; çift doğrulama temiz sayılmaz.
- **Dosyalar (öneri):** `pcbai/verify/adapters/pygerber.py`, RD-C2 okuyucusu, manifest/limit bağlantıları.
- **Kabul:** beş demo üretim paketi, mm/inç-yay-polarite fixture'ları ve bilerek bozuk dosya;
  toleranslar çıktı başına açık. Bağımlılık lisans denetimi ve eksik araç testi geçer.
- **Testler (planlanan):** `tests/test_gerber_calibrate.py`. RD-C2 hazır değilse EK-5 engeli raporlanır;
  EK-4'ün gösterimiyle bu kabulün karşılandığı söylenmez.

## 3. Paket kapanışı ve çalışma kuralları

- Her uygulama paketi kendi `git worktree`/dalında; ana klasörde başka yazıcı veya test varsa dosya değişikliği yok.
  İkinci ajan salt okunur denetçi; ikinci uygulayan gerekiyorsa onun da ayrı worktree'si olur.
- Ürün kodu değişen VS Code paketinde eklenti sürümü; çekirdek ürün davranışı veya sözleşmesi değişirse çekirdek yama sürümü artırılır.
  Plan belgesi sürüm artırmaz. `package-lock`/manifest ve `pcbai/__init__.py`/pyproject tutarlı kalır.
- Hedefli testler → etkilenen entegrasyon/Host ölçümü → paket bağımsız denetimi → ayrı commit.
  Çekirdek değişikliğinde gerekli tam takım/gerçek CLI kontrolleri de tamamlanır.
- Host/KiCad yoksa açık skip; skip kabul değildir. Kullanıcı kartı, ayarları veya açık servisi testte değiştirilmez.
- Sonuç/sınırlar `status.md`, ilerleme `plan-eksikler.md`; RD-I2/RD-I5 ancak kendi tam ölçütleri karşılanınca işaretlenir.
- Görünüm bir öğeyi gösteremese bile model sonucu gizlenmez. Dosya/buffer içeriği veri olarak kalır.

İlk uygulama komutu: **"EK-0'dan başla, sonra EK-1 ve EK-2'yi tamamla."**
Bu belgeyi hazırlama talebi uygulamayı, eklenti kurulumunu, main birleştirmesini veya yayın koşusunu başlatmaz.

## 4. Plan doğrulaması

Salt okunur ayrı Codex denetçisi kapsam, bağımlılık, süre toplamları ve checkpoint sınırını inceledi;
engelleyici bulgu yok. Eski/yeni RD sürelerinin farkı ve çekirdek davranışı için sürüm artışı açıklığı giderildi.
Bu belge incelemesidir; eklenti, gerçek Host, Gerber veya uygulama kabul testi değildir.
