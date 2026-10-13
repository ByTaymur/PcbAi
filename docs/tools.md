# Uygulanmış araçlar — 0.1.8

| Araç | Girdi / sonuç |
|---|---|
| pcbai_status | Oturumlar, kökler, kaydedilmiş revizyon ve yetenekler |
| doctor | Gerçek kurulum yolları ve sürümleri; bulunma ve test edilmiş olma ayrı |
| search_parts | query/limit?; kurulu KiCad veya PCBAI_SYMBOLS kütüphanelerinin özel FTS5 metadata dizini, kalıtılan alanlar, SHA-256 yenileme; katalog/stok araması değildir |
| circuit_blocks | Yerleşik üç pasif tarif, sürüm/parametre şeması/portlar; olgunluk 0, stok ve tarif kabulü yok |
| hand_calc | calculation/params; sabit formüller, boyutlu SI ayrıştırma, özgün/normalize girdiler, birimli sayılar ve evidence_id; fiziksel kabul değildir |
| plan_circuit | ir; kapalı Draft2020 IR, gerçek yerel literal pin/pad, ray/net ve pasif blok genişletmesi; proje dosyası yazmaz, electrical=incomplete, ready_to_apply=false. [IR sözleşmesi](ir.md) |
| add_block | session/document/revision/mode; preview: block/params/instance/x_mm/y_mm, apply: yalnız candidate_id. Üç pasif tarif, tek frozen aday/checkpoint, global anotasyon, yalıtılmış yerel netler, exact native üyeler; yeni ERC hatası apply'i engeller. Olgunluk 0. [Sınırlar](ir.md) |
| part_info | lib_id/kind=symbol veya footprint; katı kalıtım çözümü, birimler/pinler veya padler, kaynak karması, güvenilmeyen metadata |
| verify_part | symbol/footprint/datasheet_pins?; benzersiz **literal** elektrik pin/pad numaraları, çoklu pad; mekanik/NPTH ayrı. Veri sayfası tablosu kullanıcı girdisidir; stok/ömür/3B denetlenmemiştir |
| discover_ipc | Yerel kanalları yoklar; kayıtlı proje/belge eşleşmeleri ve başarısız yoklamalar ayrı döner |
| live_board_summary | session/document/endpoint_id; canlı tampon SHA-256, footprint ve katman/net sayıları |
| get_selection | session/document/endpoint_id; canlı seçili öğeler, tampon SHA-256; salt okunur |
| project_summary | session; belge türü, SHA-256, sembol/footprint, PCB net/katman/segment/via sayıları |
| list_symbols | session + document; her proje/sayfa örneği ayrı: Reference, project, sheet_path, unit, UUID/lib_id/konum |
| list_footprints | session + document; footprint properties ve konum |
| list_nets | session + PCB document; dosyadaki net numarası/adı |
| net_info | session/document/net; pad üyeliği, footprint-local pad konumu, segment/via sayısı; bağlantı doğrulaması değildir |
| scene_pcb | session/document/revision?; mm cinsinden footprint, pad, iz/yay, via, bölge ve kenar geometri dizini |
| render_pcb | session/document/revision; layers?; revizyon önbelleğinde KiCad katman SVG’leri ve ölçülen mm↔SVG matrisleri |
| hit_test | session/document/x_mm/y_mm; layers?, tolerance_mm?; görünür öğeler ve mesafeleri |
| simulate | session/kök şematik/revision?; vectors?, max_points?; şematikteki tek `.tran/.ac/.dc/.op` komutu KiCad'in ngspice'ıyla; vektörler, min/max/final, kanıt kimliği. `.control` atılır; model dosyası proje/KiCad dışında ise ret ([S5](spikes/S5.md)) |
| render_3d | session/PCB/revision; KiCad GLB (ipek, maske, pad), boyut/karma, `components` (GLB düğüm adı = footprint referansı), `without_model`, `display_model_substitutions` |
| render_sch | session/kök şematik/revision; her sayfa örneği için KiCad SVG’si, ölçülen mm↔SVG matrisi, sayfa adı/UUID yolu/dosyası ve KiCad netlisti |
| scene_sch | session/kök şematik/revision?/sheet (UUID örnek yolu); sembol (örnek referansı, birim, gövde sınırı), pin (bağlantı noktası, net), tel, bus, etiket, bağlantı, alt sayfa ve pinleri; `net_members` ve sayfa listesi |
| hit_test_sch | session/kök şematik/sheet/x_mm/y_mm; tolerance_mm?; sayfa örneğindeki öğeler |
| get_markers | session; projedeki işaretler, HMAC güveni, markers_revision ve UUID bağı çözümü; bağlı işarette `target_item` (referans/değer/pin/net) |
| update_marker_status | session/document/revision/markers_revision/mode; preview: n/status/reason, done için change_id; apply: candidate_id |
| erc | session + .kicad_sch; geçici proje kopyasında JSON raporu |
| drc | session + .kicad_pcb; isteğe bağlı parity; unconnected/parity bulguları dahil |
| schematic_pdf | session + .kicad_sch; özel durum klasöründe PDF ve SHA-256 |
| board_stats | session + .kicad_pcb; gerçek CLI geometri/footprint ölçümleri, ham JSON ve kanıt kimliği |
| render_board | session + .kicad_pcb; side, width/height (64–2048); kopyadan PNG, gerçek piksel boyutu ve SHA-256 |
| export_fab | session + .kicad_pcb; kopyada Gerber/delik ZIP, kaynak revizyonu ve her dosyanın karması |
| start_job | session/document/revision/tool; ERC/DRC/PDF/PNG/SVG/stats/fab salt okunur arka plan işi |
| job_status | job_id; queued/running/completed/failed, hedef, zamanlar ve asıl araç sonucu |
| set_value | session/document/revision/mode; preview: reference/value; apply: candidate_id |
| add_symbol | session/şematik/revision/mode; preview: lib_id/reference/x_mm/y_mm, unit/value/footprint/rotation_deg/mirror?; 1,27 mm ızgara, açık referans; mevcut proje önbelleği korunur |
| connect | aynı hedef; preview: name, endpoints=[{reference,pin,unit?}], kind=local/global?; pin noktalarında etiket, gerçek kök netlistinde ortak net ve bütün üyeleri ölçülür |
| add_label | aynı hedef; preview: name/x_mm/y_mm/kind?/rotation_deg?; local/global etiket; hiyerarşik pin yaratmaz |
| replace_part | aynı hedef; preview: reference/lib_id/value?/footprint?; tüm birimler aynı dosyada, pin kimliği/konumu/türü korunmalıdır; sembol/pin UUID'leri sabit |
| move_footprint | session/PCB/revision/mode; preview: reference + x_mm/y_mm/rotation_deg/side; apply: candidate_id. Bayt koruyan; yüz değiştirme KiCad kuralıyla (yerel y yansır, katman F↔B, metin aynası) |
| set_track_width | session/PCB/revision/mode; preview: width_mm + uuids **ya da** net |
| add_zone | session/PCB/revision/mode; preview: net, bakır layer, points_mm, clearance_mm?, min_thickness_mm?, priority?; dolgu KiCad'in kopyada hesapladığı poligonlardır |
| set_netclass | session/.kicad_pro/revision/mode; preview: netclass + clearance/track_width/via_diameter/via_drill mm ve/veya patterns; DRC projenin kartında |
| checkpoint | session/document/revision, isteğe bağlı label; bir belgenin değişmez kopyası |
| design_history | session; checkpoint kimlikleri ve hedef/revizyon |
| restore_checkpoint | session/document/revision/mode; preview: checkpoint_id; apply: candidate_id |

Her sonuç `ok`, `changed`, `verified`, `summary`, `measurements`, `warnings` alanlarını taşır.
Belge hedefli sonuçlarda `target={session, document, revision}` vardır. Revizyon sayısal sayaç yerine
projedeki KiCad kaynakları, kuralları ve kütüphanelerinin SHA-256 toplamıdır.

Yeni şematik araçları önizle → aynı aday/revizyonla uygula → checkpoint → atomik yazım → gerçek
**kök ERC** akışındadır; alt sayfa düzenlemesinde aday yalnız alt dosyayı değiştirir, ERC kökten çalışır.
Tek fiziksel dosyanın birden fazla sayfa örneği veya başka proje kaydı varsa yazma reddedilir.
`add_symbol`/`connect`/`add_label` artımlı kurulumda yeni ERC bulgularını raporlayarak uygulanabilir;
bu temiz devre kabulü değildir. `replace_part` yeni ERC hatası ekliyorsa uygulanamaz.
Etiketler aynı kapsamda önceden var olan netleri de birleştirir; `connect` tüm ölçülen üyeleri gösterir.
Araçlar kütüphane tablolarını, parça stok durumunu veya çok dosyalı IR'yi yönetmez.
Program yolu araç argümanı değildir. `PCBAI_SYMBOLS`/`PCBAI_FOOTPRINTS` kullanıcı ortamı özel kökler
tanımlayabilir; özel kütüphanede lisans `unknown` kalır. İlk dizin oluşturma bir kez yapılır;
metadata taraması pin/çizim geçerliliği sertifikası değildir, `part_info` ve yazıcı tam ayrıştırır.

Dosya okuma/denetim/çıktı araçları isteğe bağlı `revision` kabul eder; eski revizyon reddedilir.
`start_job` için revizyon zorunludur. En fazla 4 iş aktiftir, son 100 iş tutulur; bağlantı kapansa da
iş devam eder. `job_status` belge kilidini beklemez. İstek kapanınca işlem yeniden gönderilmez.
Sonuçtaki `job.result.ok` asıl işin başarısını belirtir; durum yoklamasının `ok=true` olması işin
geçtiği anlamına gelmez. Servis yeniden başlarsa işler/kimlikler kaybolur; `unknown_job` döner.
Kapatma devam eden işleri bekler; yeni işler reddedilir. Yazma araçları arka plan işine alınamaz.

IPC için `ipc` bağımlılığı ve etkin KiCad API gerekir. `discover_ipc` yalnız okur; ayarları açmaz.
`PCBAI_KICAD_SOCKETS` yapılandırması JSON `ipc://` kanal listesi kabul eder (en fazla 16);
yoksa `KICAD_API_SOCKET`, ardından varsayılan/PID kanalları denenir. Araç argümanlarından
program yolu veya kanal URL'si kabul edilmez; `endpoint_id` keşiften seçilir. Kayıtlı oturum ve PCB
birlikte eşleşmelidir; kanalda birden çok belge varsa ilk belge seçilmez. Her yoklama/okuma 5 saniyelik
ayrı Python süreciyle sınırlıdır. Canlı `live_revision` ile diskteki proje `target.revision` farklı
kavramlardır. `buffer_matches_saved_bytes=false`, biçim farkından da kaynaklanabilir; unsaved denetimi
diye kullanılmaz. Canlı yazma/save/revert aracı sunulmaz, dosya yazma koruması aynen sürer.

Render/PDF/ZIP ve PCB istatistikleri özel kanıt kaydına bağlanır. Kaynak revizyonu işlem sırasında
değişirse çıktı iptal edilip silinir. `export_fab` tüm bakır katmanları, maskeler, ipek ve Edge.Cuts
ile Excellon delik çıktısını içerir; yalnız kopyadaki bölgeler doldurulur. BOM/CPL ve üretici DFM
bu temel dışa aktarımın kapsamına girmez. `verified=not_run`, üretim kabulü verilmediğini korur.
KiCad 10.0.4 render piksel boyutu istekten farklı olabilir; `dimensions` PNG başlığından ölçülür.

`render_sch` kopyada üç KiCad çağrısı yapar: XML netlist, görüntü SVG’leri ve kalibrasyonlu SVG’ler.
Kalibrasyon kopyasındaki `${SHEETPATH}` metni her SVG’nin hangi sayfa örneği olduğunu, üç daire
dönüşüm matrisini ölçer ([S8](spikes/S8.md)). Sayfa ağacı netlistten gelir; dosya adına güvenilmez.
`scene_sch` netleri yalnız KiCad netlistinden alır: pin `(referans, pin)` ile, tel/etiket aynı sayfada
dokunduğu netlist pinlerinden; pini olmayan küme yalnız tam adı netlistte varsa etiketten. Aksi `null`.
Şematik işaretleri `space: "sch"`, `document` = sayfanın dosyası ve `sheet` = örnek yoludur; bağ
(sayfa örneği, öğe UUID’si) ile çözülür, ortak dosyanın diğer örneğinde görünmez.

Kart düzenleme araçları `set_value` düzenini izler: önizleme adayı, aynı revizyonda uygulama, kapalı KiCad editörleri, yazma kilidi, checkpoint ve değişiklik kanıtı. Önizleme gerçek DRC'yi mevcut dosya ve aday için ayrı kopyalarda çalıştırır (`drc_before`/`drc_after`); aday **yeni DRC hatası** ekliyorsa uygulama `new_violations` ile reddedilir, dosyaya dokunulmaz. Uyarılar kapıyı etkilemez, sonuçta raporlanır. Taşıma/döndürme/yüz değiştirme KiCad'in kendi `pcbnew` sonucuyla karşılaştırılarak doğrulanmıştır (`scripts/oracle_fp_check.py`); içinde zone/grup/ölçü olan footprint reddedilir. KiCad 10 kartları netleri öğede adla tutar (`(net "VCC")`); okuma araçları iki biçimi de destekler. `update_marker_status` done kanıtı için bu dört aracı da kabul eder.

`render_pcb` ayrı katman SVG’leri üretir. Geçici kopyaya eklenen üç kalibrasyon dairesiyle dönüşümü
ölçer; kullanıcı kartına yazmaz. Katmanlar aynı viewBox’ı taşımalıdır. SVG içinde etkin/uzak içerik
reddedilir; webview görüntüleri betiksiz resim olarak yükler. Oval ve yuvarlatılmış pad’lerin isabet
geometrisi desteklenir; özel/trapez pad’lerde sınır kutusu yaklaşımı açık uyarı taşır. Geometri okuması
bir bağlantı veya DRC doğrulaması değildir; bulgular ayrı gerçek `drc` sonucundan gelir.

`set_marker` ve `delete_marker` MCP araç listesinde ve `/call` yolunda **yoktur**; eklenti bunları
aynı Bearer koruması altındaki `/view/call` yolundan kullanır. Bu taşıma ayrımı MCP aracısının yazma
yetkisini sınırlar; aynı yerel kullanıcı adına kod çalıştırabilen bir istemciye karşı ayrı bir UI kimlik
kanıtı değildir. Her işaret yazımı preview → candidate → aynı tasarım ve işaret revizyonunda apply
izler, önce checkpoint alınır. Kalıcılık `pcbai/markers.json`, HMAC anahtarı özel servis durumundadır.
Yeni numaralar silme ve servis yeniden başlatmalarında tekrar kullanılmaz. Kopan UUID bağı tahminle
yeniden bağlanmaz. Şematik koordinat kayıt şeması var; şematik görüntü ve sembol/pin/net bağları G2’yi bekler.

MCP `pcbai://markers` kaynağı kayıtlı oturumları ayrı döndürür; `apply_markers` istemi açık oturum
ister, onaysız notları talimat saymaz ve araçsız işleri gerekçeyle `blocked` olarak raporlar.
`update_marker_status` yalnız imzalı işaretin durumunu değiştirir, notunu/konumunu değiştiremez.
`done`, aynı hedef/revizyonda gerçek yazmanın `change_id` kanıtını gerektirir; DRC/ERC veya render
kanıtı tek başına yeterli değildir. Bu durum elektriksel ya da üretim kabulü vermez.

`list_symbols` modern `instances` kayıtlarını proje adı ve kök şematik UUID'siyle filtreler;
proje adı boş olan geçerli kayıtlar yalnız kök UUID eşleşiyorsa seçilir. Eşleşme yoksa
görünen `Reference` alanına geri dönmez. `property_reference` bu eski alanı, `properties` tüm
dosya özelliklerini taşır; türetilen üst alanlar özel özelliklerle değiştirilemez. Örnek kaydı
olmayan eski sembollerde görünen referans kullanılır. Sayfa yolları dosyadaki kayıtlardır;
bu sürüm kökten erişilebilir tüm hiyerarşiyi yeniden çözümlemez.

`set_value` önizlemesi `affected_references` (tekilleştirilmiş) ve `affected_instances`
(`project`, `sheet_path`, `reference`, `unit`, `uuid`) içerir. Ortak dosyaya dokunulduğundan diğer
projelerin kayıtları da etki listesine girer. Çok birimli sembollerin bütün birimleri güncellenir;
aynı proje/kök içindeki belirsiz referans/birim ve tutarsız eski değer reddedilir. Etki listesi ve ortak sayfa uyarısı
uygulama, etkisiz uygulama ve son denetim arızası sonuçlarında da korunur.
Yeni Value metninde C0/C1 kontrol karakterleri (DEL dahil) ve Unicode surrogate kodları reddedilir.
Okuyucu, eski dosyalardaki tab/satır sonlarını koruyabilir; bu kabul yeni değer yazma izni değildir.
Yinelenmiş `Value` veya `Reference` özellikleri, okuma ve düzenlemede `invalid_document` ile reddedilir.

Kalıcı yazma kilidi `<PCBAI_STATE_DIR>/locks/<kanonik proje kökü SHA-256>.lock` altındadır;
aynı kökteki projeler aynı kilidi paylaşır. Tüm yazarlar aynı durum klasörünü kullanmalıdır.
Proje kökünde yeni `.pcbai-write.lock` oluşmaz. Atomik değişim için aynı dizinde oluşturulan
geçici dosya işlem sonunda temizlenir.

`verified=not_run` denetim yapılmadığını; `erc_ok`/`drc_ok` sıfır hata ve sıfır uyarı olduğunu;
`erc_findings`/`drc_findings` geçerli raporda bulgu bulunduğunu gösterir. Değişiklik kaydedildiği hâlde
son kontrol çalışamazsa `changed=true, verified=verification_failed` ve checkpoint döner.
İhlal çıkış kodu 5 komut arızası sayılmaz. Eksik/bozuk rapor hiçbir durumda temiz sayılmaz.

Kaynak: `pcbai://status`. İstem: `review_board`. MCP `initialize` (2024-11-05…2025-11-25)
ve modern `server/discover` (2026-07-28) desteklenir. stdout yalnız satır başına JSON-RPC içerir.

Kanıtlar `%LOCALAPPDATA%\PcbAi\evidence\ev-*.json` altında araç, zaman, hedef revizyonu, girdi/rapor karması
ve ham KiCad raporuyla saklanır. Proje içine evidence.jsonl yazımı sonraki rapor fazına aittir.

Servisi kapatma: `python -m pcbai stop`; mevcut belirteçle `/shutdown` çağrısı yapar, yeni servis
başlatmaz. Aktif belge işlemleri tamamlanmadan servis kilidi bırakılmaz; yeni işlemler reddedilir.

## Dış motorlar — 0.1.7

- `route_engines`: açık yapılandırılmış `tracemaker` / `freerouting`, sürüm, yerel/WSL durumu.
  `tested=false` gerçek demo/WSL kabulü ölçülmediğini belirtir.
- `autoroute` / `autoplace`: `mode=preview`, açık hedef/revizyon ve `engine` gerektirir.
  Yalnız izin listeli `options`; program yolu, kabuk, config/view/hold/KB argümanları alınmaz.
  `autoplace` Freerouting ile reddedilir; `scratch` zaten yerleşmiş kartta reddedilir.
- `start_job`: bu iki araç için yalnız `mode=preview`; sonuç `candidate_id`, `engine_run`,
  `engine_metrics`, `new_findings`, `blockers`, `preview_evidence_id` döndürür. Aday ömrü
  sonuç hazır olduğunda başlar. Uygulama arka plan işi olarak başlatılamaz.
- `engine_preview`: aynı hedef ve aday için gerçek önce/sonra SVG ve ölçülmüş mm↔SVG dönüşümü.
- `discard_candidate`: adayı servis belleğinden kaldırır; proje dosyalarını değiştirmez.
- `mode=apply`: yalnız hedef/revizyon/adayı alır; yeni motor/seçenek verilemez. Kilit ve editör
  kontrolü, tekrar DRC, checkpoint, atomik yazım ve son DRC/kanıt akışını kullanır.

`new_violations`, DRC hata **kimliklerini** karşılaştırır; sayının aynı kalması yeterli değildir.
Motorlar için rotalanmamış bağlantı kimlikleri rota ilerledikçe değişebildiğinden sayıları ayrı ölçülür.
Dökümler önce/sonra kopyada doldurulur. Yabancı düğüm değişimi, belirsiz/bozuk dış hat veya kilitli
parça değişimi reddedilir. Yeni segment/arc/via için UUID, net, bakır katmanı ve boyut denetimi vardır.

`diagnostic_markers` aday panelindeki geçici ölçüm işaretleridir; proje `markers.json` notları değildir.
Motor çıkış/girdi hashleri ile doldurulmuş adayın `candidate_sha256` karması ayrı tutulur.
TraceMaker rota `--work` ile deterministik kipte istenir; yerleşim ve Freerouting için
determinizm iddia edilmez. Kaydedilmemiş canlı PCB yazması veya üretim onayı verilmez.

SPICE: iç içe `.include` / seçili `.lib` içerikleri sınır, döngü, boyut ve direktif/model izin listesi
denetiminden sonra bellekte açılır. `.control` çalıştırılmaz; dosya kaynaklı ve dış süreç çalıştıran
XSPICE model türleri reddedilir. Genel üretici modellerinin tamamını destekleme iddiası yoktur.
