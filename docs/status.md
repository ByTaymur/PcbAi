# Uygulama durumu — 14 Ekim 2026

Çekirdek sürümü **0.1.31**, VS Code eklentisi kodu **0.1.30** (14 Ekim'de `~/.vscode/extensions` altında kurulu en yeni
**0.1.25**; 0.1.29 kurulumu ve elle kabulü açık), son üretilen KiCad PCM arşivi
`pcbai-kicad-0.1.14.zip` (ZIP metaverisi 0.1.14; kurulum/kabul K-3 ayrı ve açık).
Bu numaralar **PLAN.md Faz 1 kabulünün tamamlandığı** anlamına gelmez.
Plan 30 haftalık ürün hedefidir; kalan işler aşağıda açıkça ayrılmıştır.

## R2-C1 — BOM metadata denetimi, ilk dilim (P2 kabulü açık)

`check_bom_fields` native root XML'de alan eksikleri/alias çatışmaları, exact
pasif değerleri, yazım grupları ve beyan edilen footprint ailesini inceler.
Kaynak yazılmaz; otomatik MPN/stock ataması, montaj veya üretim onayı yok.
Bilinmeyen kategori veya birim incomplete; native footprint otoritesi özel alanla
değiştirilmez. Kaynak `bom` ve deterministic metadata kanıtı; fiziksel parça
uyumu değildir. [Ölçüm ve açık sınırlar](spikes/R2-C1.md).

Son uygulayan10/10 OK/0.760sn, bağımsız10/10 OK/0.728sn (alt süreç1.000), skip yok;
bağımsız Ruff/diff0. İki denetim karşı örneği femto suffix/native footprint
düzeltildi. #21 authored XML fixture tek 10000-ohm grubu; gerçek native #1 iki
bileşende elle beklenen6 eksikle eşleşti ve kaynak korunur. P2 referansındaki
elle sayım ve geniş taksonomi açık; tam C1 kabulü yok. Raw `.pcbai-state/r2-c1/`.
0.1.30'un tam discover takımı ve yeni eklenti kurulumu ölçülmedi.
Son sabit geniş hedef **55/55 OK/43.382 sn**, Python exit0 (43.750 sn alt süreç),
skip yok; BOM/findings/manifest/MCP/MCP kurulum sözleşmesi/fixture katalogu.
Ruff executable ve lisans exit0. Raw `r2-c1/final-delta/`.

## R2-B4 / S13 — deneysel ayrı DFM incelemesi (tam kabul açık)

`check_fab_dfm` açık session/document/revision ile native paket kopyasını ayrı
pcb-dfm sürecinde inceler. Sabit zorunlu kontrol listesi, eksik ölçüm/N/A/çökme
kapsamı, rapor kimliği ve native kalibrasyon skorun önündedir. Dosya adı görünümü
baytları korur; özel KiCad katman adlarını dış parser'ın kaçırması giderildi.
Maske çıkarılmış gerçek negatif denemede upstream pass/null üretti; PcbAi maske
listesi ve zorunlu sonlu ölçüm kontrolüyle temiz geçişi engeller.
Üretici native minimumları ayrı B2 kontrolüdür; montaj/stok/üretim doğrulanmaz.

Son uygulayan **9/9 OK/4.243 sn**, bağımsız **9/9 OK/4.100 sn** (alt süreç4.359),
gerçek ayrı worker dahil; bağımsız Ruff/diff exit0. Önceki geniş hedef **27/27
OK/20.698 sn**, son maske/ölçüm deltasından önce. Beş demo başlangıç süresi/belleği,
108 satır kapsamı, G85 1 hit/1 slot ve yanlış güven karşı örnekleri
[S13](spikes/S13.md) içinde. 20 bağımsız bulgu etiketi **inconclusive**; doğruluk
yüzdesi veya tamamlanmış R2-B4 kabulü yok. Eğrisel sınır kalibrasyonu incomplete.
Raw `.pcbai-state/r2-b4/`; yayın kanıtı yazılmadı. Kaynak eklenti kurulmadı.

Son sabit 0.1.29 geniş hedef **65/65 OK/125.488 sn**, Python exit0 (125.937 sn
alt süreç), skip yok: DFM/profil/native beşli paket/bağlantı/env envanteri/manifest/MCP.
Ruff executable, lisans ve doctor exit0; doctor8.516 sn. Raw `r2-b4/final/`.
Bu koşu 0.1.29'un tam discover takımı değildir; ayrı native CLI genel kabulü
0.1.28 kaydıdır. Son belgeler/raw sonuçlar bağımsız salt okunur denetimde eşleşti.

## R2-B3 — bağlantı otoriteleri, ilk dilim (tam kapsam açık)

Check_fab_connections gerçek Gerber geometri adalarını, native PCB IPC-D-356 yüzey
padlarını ve native şematik pin gruplarını ayrı kıyaslar. #1 gerçek fixture native
DRC temizken fiziksel Gerber adası şematikte farklı iki neti birleştirdi: gerber_schematic_short
ve ipc_schematic_partition_conflict. Gerber–IPC kendi aralarında aynı yanlış modeli
taşıdığından bu hata yalnız o iki otoritenin farkı diye sunulmaz.
[Ölçüm/sınırlar](spikes/R2-B3.md). Pozitif mm doğrusal standart aperture/yüzey IPC alt
kümesi; karmaşık region/macro/arc ve PTH/via yolu incomplete. Tam RD-C2/R2-B3 açık;
üretim paketi kabulü ve fiziksel doğrulama değildir. L-FAB-CONNECTION-SUBSET kayıtlı.
Yinelenen pin flashı/katmanı, kaymış koordinat, kayıt dışı pad ve native XML kimlik
tekrarı temiz kapsam sayılmaz. Source=fab; geometri/topoloji, alt kümede deterministic.
Genel fab kaynağının varsayılan confidence'ı heuristic'tir.

Son uygulayan **43/43 OK/26.672 sn**, Python exit0 (27.391 sn alt süreç), skip yok;
Ruff modül/executable ve lisans exit0. Önceki bağımsız **38/38 OK/16.446 sn**
XML/limit son deltası öncesi; son bağımsız delta ayrıca bekleniyor.
Genel takım ve ayrı CLI/doctor koşuları **0xC000013A ile kesildi**; başarılı sayılmaz.
Raw .pcbai-state/r2-b3/; yayın JSON'u değişmedi. Kaynak VS Code 0.1.24, kurulmadı.
B1 düzeltmesi: etkin mask/silk/Edge dosyaları zorunlu; kapalı layer manifestte açık
omitted_disabled_layers listesinde. Assembly pasta zorunluluğu korunur. Gerçek #1 ZIP
ve eksik etkin mask negatif testi geçer; kaynak proje baytları değişmez.

Son iki P2: kesin kesir/kare mesafe ve tekil native net code/name ile kapandı;
teğet bakır birleşir, gerçek küçük boşluk kapanmaz. Katman 500 şekil bütçesi.
37004c7 birleşim sonrası bağımsız **44/44 OK/42.485 sn**, Python exit0/skip yok,
Ruff/diff temiz. Kaynak VS Code 0.1.27; kurulum yapılmadı. Son uygulayan geniş hedefli
ve ayrı CLI/doctor ölçümü aşağıda; geçmişte kesilen koşu başarı sayılmaz.

Son birleşik hedefli **111 test OK /125.662 sn**, Python exit0 (126.719 sn alt süreç),
**2 skip**. Ayrı gerçek KiCad CLI **11/11 OK /220.998 sn**, Python exit0 (221.281 sn
alt süreç); doctor exit0/7.110 sn. Ruff modül/executable ve lisans exit0.
Koşular ayrı süreç grubunda ve gizli konsolda; raw .pcbai-state/r2-b3/post-merge/.
İki skip yalnız hesabın symlink oluşturma yetkisi olmadığı dosya/waiver testleridir;
KiCad CLI testlerinde skip yok. Doctor KiCad10.0.4 için IPC minimum10.0.6 sağlanmıyor
diye raporladı; yeni canlı IPC kabulü iddiası yok.
Birleşik 0.1.28'in ayrı süreç grubundaki son genel discover koşusu **488 test /
1617.292 sn, Python exit0** (alt süreç1621.062), **5 skip** tamamlandı. Raw
`.pcbai-state/r2-b3/wave-final/`. Atlamalar: KiCad10.0.4 bozuk DRU'yu exit0 kabul
ettiğinden native rejection testi; yapılandırılmamış Freerouting/happy modele ait
iki kabul; hesabın symlink yetkisi olmayan iki test. Bu ölçüm yeni 0.1.29 DFM kodunu
veya fiziksel/üretim/canlı IPC kabulünü kapsamaz; eski kesilen koşu başarı sayılmaz.

## Özel DRC kural kapısı + KiCad 10.0.7 şartı (14 Ekim, dal `ip/kicad-dru-kapisi`)

**Sorun (ölçüldü, KiCad 10.0.4, ecc83):** `kicad-cli pcb drc` derlenemeyen `.kicad_dru` dosyasını sessizce atıp
yerleşik kurallarla rapor üretiyor ve 0 dönüyor (324 → 2 ihlal, mesaj yok). Düzeltme KiCad master'da (bozuk kuralda
exit 3), 10.0 dalına taşınmadı (Diode pcb PR #1381, 5 Ekim 2026). 10.0.7 sürüm notlarında bu düzeltme yok.
Yani hiçbir kararlı KiCad bunu çözmüyor; kapı PcbAi'de.

**Kapı (`pcbai/kicad/dru.py`, `custom_rules_gate`):**
1. Yapısal ön denetim: tam S-ifadesi, tek `(version …)`, yalnız `(rule …)`, adlı/yinelenmeyen kural, en az bir
   `constraint`, bilinen madde adları, dengeli `condition`, uzunluk kısıtlarında birim. Hata → `custom_rules_invalid`
   (KiCad çağrılmadan, 0,2 sn).
2. Yükleme yoklaması: kopyada kural dosyasına her bakırda tetiklenen adlı bir kural eklenir, ayrı DRC koşulur;
   ad raporda yoksa → `custom_rules_not_loaded`. Bakır yoksa `custom_rules` satırı `skipped/no_copper_for_probe`.
   Sonuç (KiCad yolu, kart ve kural SHA-256'sı) bellekte önbellekte; asıl DRC özgün dosyayla koşar.
3. Exit 3 (KiCad master davranışı) → `custom_rules_invalid`.

`checks_run` içinde yeni `custom_rules` satırı: kural yoksa `not_applicable`, yüklendiyse zorunlu `ran`.

Ölçülen (ecc83): kural yok 6,5 sn; geçerli kural 12,0 sn (yoklama dahil, ilk çağrı); eksik parantez 0,2 sn
`custom_rules_invalid`; bilinmeyen kısıt türü ve bozuk `condition` 5,8 sn `custom_rules_not_loaded` (KiCad tüm
dosyayı atıyor, yoklama yakalıyor). KiCad'in kendi demolarındaki iki `.kicad_dru` (jetson 5, vme-wren 11 kural) ve
eklentinin 5 kural kalıbı ön denetimden yanlış alarm olmadan geçti. `tests/test_dru.py` artık 10.0.4'te atlanmıyor:
bozuk dosyanın PcbAi'de reddini doğruluyor.

**Sürüm şartı:** desteklenen KiCad 10.0.7+ (10.0 dalı). `doctor` → `kicad_cli.supported`, `requirements_unmet`;
`python -m pcbai doctor` şart karşılanmazsa 1 döner, `scripts/check.ps1` durur. PCM paketi `kicad_version: 10.0.7`.
**Bu makine 10.0.4: `doctor` 1 dönüyor; KiCad 10.0.7'ye yükseltilene kadar check.ps1 geçmez.**

Sınır: KiCad'in tek kuralı atıp dosyanın kalanını yüklediği bir durum ölçülmedi; olursa yoklama bunu görmez.

## R3-A1 `readable_netlist` (14 Ekim, dal `ip/r3-a1-netlist`)

[R3 planı](plan-referans-depolar-3.md) ilk paketi. Kaydedilmiş kök şematiğin `kicad-cli` netlisti, ajanın devreyi
okuması için net başına gruplanmış metin olarak döner (biçim fikri tscircuit, MIT; kod alınmadı).
`parse_netlist` artık pin adı/türünü (`pinfunction`, `pintype`) ve kütüphane parçasını da taşır; mevcut alanlar değişmedi.

Ölçülen (bu makine, KiCad 10.0.4 demoları, varsayılan 12 000 karakter):

| Demo | Net | Varsayılan yazılan / karakter | Kesildi | Özet net | Atlanan tek pinli | Tam çıktı (60 000) |
|---|---|---|---|---|---|---|
| complex_hierarchy | 52 | 50 / 6 237 | hayır | 1 | 2 | 52 net, 7 228 kr |
| pic_programmer | 111 | 34 / 5 213 | hayır | 1 | 77 | 111 net, 13 299 kr |
| ecc83 | 13 | 9 / 1 156 | hayır | 0 | 4 | 13 net, 1 532 kr |
| interf_u | 173 | 108 / 11 923 | evet | 2 | 63 | 173 net, 20 981 kr |
| video | 588 | 58 / 11 798 | evet | 5 | 217 | 284 net, 59 854 kr, kesildi |

İlk çağrı süresi (netlist dışa aktarımı dahil) 1,1–4,4 sn. Beş demoda yazılan her netin pin kümesi KiCad
netlistiyle birebir (`tests/test_readable_netlist.py`). Birim testleri: alan enjeksiyonu (`
`, U+2028), uzun
alan kısaltma, büyük net özeti, kesilme bildirimi, bilinmeyen net reddi, PCB belgesi reddi.
Test: `tests.test_readable_netlist tests.test_sch_scene tests.test_mcp_setup` 24/24; `ruff check .` temiz.
Tam takım bu dalda: 476 test, OK (5 skip), 1 403 sn.

Sınırlar: rol/alt devre etiketi yok (RD-B2 analizi gelince eklenecek); `review_snapshot` (RD-F1) henüz yok;
çekirdek sürümü artırılmadı (ana dalda paralel iş var, birleştirmede artırılacak); VS Code paneli yok, araç MCP
ve `/call` üzerinden.

## Denetim P0/P1 kod düzeltmeleri + KiCad İşaret koy (14 Ekim, dal `ip/ip-isaret-paneli`)

[Denetim raporundaki](denetim-raporu-2026-10-14.md) kodla kapatılabilen maddeler:

- **CI (P0):** WSL sürüm testi yalnız Windows'ta koşar (`tests/test_engine_inventory.py`). GitHub koşusu yeniden
  ölçülmedi; yeşil bağlantı hâlâ açık.
- **H1/E4 MCP zaman aşımı (P0):** MCP `autoroute`/`autoplace` önizlemesini `start_job` + `job_status` ile yürütür;
  `PCBAI_MCP_JOB_WAIT` (120 sn) içinde bitmeyen iş `status=running` + `job_id` döner. Zaman aşımına uğrayan yazım
  `service_timeout`, `changed=null` döner. Talimata eklendi. Sahte uzun iş ile birim testi; gerçek 200 sn motor
  koşusu ölçülmedi.
- **E1/E2/E3 tek hüküm (P0):** VS Code `PcbAi: Denetle` (eklenti 0.1.26), KiCad "PcbAi ERC/DRC" düğmesi ve
  `review_board` istemi toplu `check` aracını kullanır; `checks_incomplete`, muaf, süresi dolmuş, yetim ve politikayı
  aşan muafiyetler gösterilir. Fixture #17/#24 ile üç istemcide elle kabul yapılmadı; VS Code JS'i bu makinede Node
  olmadığı için çalıştırılmadı.
- **H2:** `suggested_restore` her yolda `{tool, arguments[, requires]}`.
- **H3:** muafiyet süre politikası kayıt başına; düşürülen politika dosyayı kilitlemez, aşan kayıt
  `policy_exceeded_waivers` olarak görünür, muaf tutmaz, `delete_waiver` ile silinir. 365 gün üst sınır sabit.
  JSON checkpoint geri yükleme aracı hâlâ yok.
- **H4:** `Jobs.close()` en fazla 10 sn bekler, hâlâ çalışan iş kimliklerini döner.
- **KiCad İşaret koy (IM):** turuncu düğme Asistan penceresinde işaret notunu açar; PCB seçimi (bileşene bağlı ya da
  nokta) veya kaydedilmiş şematik bileşeni hedeflenir. Gerçek KiCad içinde elle kabul yapılmadı.

Açık kalanlar (kodla bu turda yapılmadı): H5/H6 performans, H7, belge birleştirme (README, plan-eksikler çelişkileri,
`.pcbai-state` bağlantıları), sürüm hizalama/PCM ZIP/public depo, Faz 0 kıyas seti, KiCad 10.0.7, RD-G2 fixture'ları,
fiziksel kart, GE canlı durum ekranı (yalnız plan).

Ölçüm: tam takım 469 test, 5 skip, 1 hata (`test_kicad_plugin_describe_still_renders`, kaldırılan `describe`
fonksiyonu); test `check_lines` için yeniden yazıldı ve tek başına geçti (`test_verify_findings` +
`test_kicad_assistant` 31 OK). Ruff temiz.

İkinci tur (aynı gün): H5 isteğe bağlı `PCBAI_EDITOR_CHECK=project` (varsayılan değişmedi; Windows süreç komut
satırı sorgusu canlı denendi, gerçek iki-KiCad kabulü yapılmadı), H6 revizyon özet önbelleği (büyük 3B projede süre
ölçülmedi), H7 iş sonucu kırpma, `restore_waivers` (bozuk dosyada checkpoint'ten geri yükleme), README/status/
plan-eksikler çelişkileri, `.pcbai-state` bağlantıları "yerel kayıt" metni. Tam takım **473 test OK, 5 skip**,
1541,8 sn; Ruff temiz.

## R2-B2 — birleşik üretici profilleri (14 Ekim)

Beş kaynaklı profil; fab_profiles/check_fab_profile; native kaydedilmiş/varsayılan
minimumlar ölçülerek kopyada yalnız sıkılaştırılır, açık gevşetme reddedilir.
Native ignore kimlikleri error olur; bilinmeyen proje-only ignore incomplete kalır.
Export_fab(profile) aynı sıkılaştırılmış kopyanın temiz DRC'sini zorunlu tutar.
Bulgu fab_profile/deterministic/kicad; profile/input SHA ve iki revizyon raporda.
Malzeme/bakır ağırlığı/proses varsayımı doğrulanmış sayılmaz, üretici teyidi gerekir.
BOM/CPL dönüşümü ve montaj kapısı B2 metaverisinden otomatik yapılmaz.
[Kaynak kıyası ve ölçüm](spikes/R2-B2.md). Native API probu **3/3 exit0**.
İlk hedefli **48 OK/75.478 sn**; denetim düzeltmeleri sonrası son uygulayan delta
**36/36 OK/22.556 sn**, Python exit0 (22.938 sn alt süreç), skip yok; module/executable
Ruff exit0. Son bağımsız delta **42/42 OK/23.121 sn**, Python exit0 (23.500 sn),
skip yok, Ruff/diff temiz. PYTHONPATH import enjeksiyonu -I altında etkisiz ölçüldü.
Sentetik kapalı kenar/kapalı bakır halka generic temiz, .6 mm track tabanı beklenen
native track_width bulguları; kaynak revizyon sabit. Aynı adaydan dışa aktarım regresyonu
bütün native çağrılarda kontrol edilmiş kopya revizyonunu doğrular.
Kaynak VS Code 0.1.23 MCP katalog senkronu; kurulu sürüm değiştirilmedi. Genel takım,
ayrı CLI ve fiziksel/üretim/EMC kabulü bu pakette iddia edilmez.
Raw kayıtlar .pcbai-state/r2-b2/; docs/spikes yayın JSON'u değişmedi.

AJ-4/AJ-5 ana dal çalışmaları merge ile korundu. Merge sonrası son **44/44 hedef test
OK/24.672 sn**, Python exit0 (25.235 sn alt süreç), skip yok; native profil/aynı aday
dışa aktarımı, MCP, handoff, KiCad assistant ve servis regresyonları dahil.
Modül/executable Ruff ve lisans denetimi exit0. Kaynak VS Code 0.1.23, kurulum yok.

## R2-B1 — tam ham üretim paketi (14 Ekim)

Sonraki AJ-3 merge'i de korundu; prompt/MCP/events ek **18/18 OK/0.181 sn**, Python
exit 0 (0.656 sn alt süreç), direct Ruff exit 0. Native B1 kodu bu merge'de değişmedi.

Eşzamanlı AJ-2/AJ-7/AJ-S1 ana dal işleri merge ile korundu. Registry MCP araç kopyası
model_coverage için yenilendi, kaynak VS Code sürümü 0.1.21 (kurulum yapılmadı).
Merge sonrası son **26/26 hedef test OK/5.749 sn**, Python exit 0 (alt süreç 6.313 sn);
MCP katalog ve servis event regresyonları dahil. Direct Ruff ve lisans exit 0.
Node MCP testi PATH'te node olmadığı için çalıştırılamadı; JS testi başarı iddiası verilmez.

Export_fab assembly?; Gerber/drill + IPC-D-356 + iki yüz mm ham POS + JSON stats;
assembly=true pasta, her dosya role/SHA/bytes, job varsa dahil. Production_verified false.
X2 FileFunction/source stack ile özel bakır adları doğru tanınır; units MOMM, requested
katman/native output, finite CSV/yüz/ref, stats ve IPC terminal denetimleri fail-closed.
Ham POS eligible footprint'lerdir; native exclusion flag korunur, supplier rotation/BOM yok.
[Ölçüm ve sınırlar](spikes/R2-B1.md). Uygulayan 12 test OK/113.956 sn (PS combined shell1,
Python0 atfedilmedi); bağımsız 12/12 OK/155.300 sn/Python0/skip yok, **5 demo/10 ZIP**,
kaynak revizyon ve bütün dosya SHA'ları korundu. Metadata delta bağımsız 12/12/7.258 sn/Python0.
Gerçek excluded footprint ve nonzero aux-origin 100/200: eligible refs X=kartX/Y=-kartY;
POS mutlak, dışlanan ref yok. İlk direct Ruff B023 test closure buldu; default binding
düzeltildi ve direct Ruff0. Son MOMM guard/metadata delta bağımsız **12/12 OK/7.151 sn /
Python exit 0**, skip yok; doğrudan Ruff executable exit 0, diff temiz. 10 ZIP koşusu bu
son guard eklenmeden önceydi; son delta fake guard+gerçek origin/exclusion testini içerir.
Genel/ayrı CLI takım henüz bu pakette koşulmadı; birleşik dalgada ölçülür. Raw kayıtlar
`.pcbai-state/r2-b1/`, yayın JSON'u/user card/settings/CadAI değişmedi. Yeni dependency yok;
montaj/DFM/fiziksel/üretim kabulü değildir. Kalan R2 geliştirmeleri devam ediyor.

## R2-A3 — model bağlama kapsamı (14 Ekim)

Native XML fiziksel referansları ile güvenli üst düzey SPICE eleman/model/alt devre bağımlılıkları
eşleştirilir; `model_coverage`, `simulate`, pasif tarif sonuçları coverage döndürür.
Min_coverage bütün parçaların oranını kullanır, işçi öncesi eksik kapsamı engeller; aktif
oran ayrı, aktif yoksa null. Omitted/excluded IC paydadan düşmez; connected ve gerekçe görünür.
Yapısal bağlamadır, pin/net/datasheet/firmware/fiziksel doğrulama değildir.
[Rapor ve sınırlar](spikes/R2-A3.md). Son uygulayan hedef 35 test OK/9.106 sn;
bağımsız son 35/35 OK/5.316 sn, Python exit 0, skip yok; Ruff/diff temiz.
Gerçek Sallen–Key 1,0; hariç U1 kapsam dışı ve eşik altında worker başlamaz.
Denetçinin tab-koşul ve .end sonrası yanlış bağlama bulguları negatif testlerle kapatıldı.
Genel takım ve ayrı 11-test CLI bu paket için koşulmadı; birleşik dalga sonunda ölçülür.
Ham kayıtlar `.pcbai-state/r2-a3/`; yayın JSON'u ve kullanıcı ayar/kartları değişmedi.
Yeni bağımlılık/model dosyası paketlenmedi. Devam eden hedef kalan R2 paketleridir.

## R2-A2 — süreli ve görünür bulgu muafiyeti (14 Ekim)

`ip/r2-a2-waivers`, ayrı worktree; [rapor](spikes/R2-A2.md),
[veri fixture #24](../tests/fixtures/faults/24-expired-waiver/README.md).
Sabit kök `pcbai-waivers.json`: exact ERC/DRC/parity finding_id, gerekçe, sorumlu,
created/expires; UTC gün sınırı, varsayılan 90 gün (`PCBAI_WAIVER_MAX_DAYS`, 1–365).
Toplu check tüm bulguları korur; etkin/muaf/dolmuş/yetim listelerini ayrıca döndürür.
Tüm etkin bulgular muafsa CLI 0, etkin bulgu varsa 1; bozuk politika veya eksik denetim 2.
Zorunlu ignored kural, failed/skipped coverage ve düzenleme araçlarının yeni-hata kapıları muaf olmaz.
Proje SHA ve snapshot yan dosyayı içerir; kayıtlar kanıtta hash/gün/süre politikasına bağlanır.
Get/set/delete araçları; revision-bound preview/apply, checkpoint, disk SHA geri okuması.
Kaydedilmiş değişiklik readback/kanıt hatasında changed=true kalır.

Başlangıç ölçümü 1 ERC bulgusu + geçerli JSON → checks_findings, waived alanı ve araç yok.
İlk hızlı 18/18 OK/0.675 sn; ilk gerçek CLI dahil 19/19 OK/52.641 sn (0/1/2 gerçek süreç).
Bağımsız ilk hedef 35/35 OK/49.795 sn. Denetçi iki açık buldu: directory sidecar snapshot'tan
kayboluyordu; boyut limiti revision/copy öncesinde yoktu. Fixed input shape + bounded bytes ile
düzeltildi; sonraki bağımsız 29 test/28 geçti/1 symlink skip/0.976 sn, Python exit 0.

Son ek concurrency testi iki farklı oturumda 99 aday + 2 eşzamanlı preview ile önce FAIL
(2 başarı/101 aday, 1.138 sn). Ortak RLock preview/apply lifecycle'ına eklendi; test 1/1 OK/1.077 sn.
Bağımsız son hızlı delta 24 test/23 geçti/1 symlink skip/3.682 sn, Python exit 0; Ruff/diff temiz.
**Son kodun hedef takımı: 41 test / 40 geçti / 1 symlink yetkisi skip / 62.232 sn; Python exit 0.**
Alt süreç 62.579 sn; gerçek muafiyet CLI 0/1/2 ve manifest/native contract regresyonları dahildir.
Genel takım son RLock/concurrency testi ve UTC test-clock düzeltmesi öncesi kaynakta
**377 test / 372 geçti / 5 skip / 1114.854 sn; Python exit 0** tamamlandı (alt süreç 1117.985 sn).
Skip: malformed DRU ret kabulü KiCad 10.0.4'te yok, yapılandırılmamış Freerouting gerçek demo,
iki ayrı Windows symlink yetkisi testi ve dış kicad-happy kalibrasyonu.
Bu genel koşu son kilitli kodun genel ölçümü olarak sunulmaz; tek sonraki ürün farkı ortak
RLock wrapper'larıdır, 41 hedef test ve bağımsız 24-test delta ile doğrulandı.
Son test-only UTC clock düzeltmesi sonrası gerçek muafiyet CLI testi ayrıca **1/1 OK / 58.508 sn /
Python exit 0**, alt süreç 59.125 sn. Son kilitli ürün kodunda ayrı gerçek KiCad CLI
**11/11 OK / 258.630 sn / skip yok / Python exit 0**, alt süreç 258.906 sn.
Son Ruff, lisans ve diff denetimleri exit 0; bağımsız nihai kaynak/belge denetimi temiz.
172 doküman bağı doğrulandı; ignored raw-state bağları ana workspace'a çözüldü. İlk worktree
bağ deneyi raw-state dosyaları orada olmadığından başarısızdı; düzeltilen bağ denetimi exit 0.

Checkpoint ilk oluşturma blob'u b'' ve before_file_exists=false; genel restore_checkpoint KiCad
belgesi içindir, bu JSON'u/yokluğu otomatik geri yüklemez. Delete geçerli boş container bırakır.
UI eklenmedi; eklenti sürümü değişmedi. Native raporlar, kullanıcı kart/ayarları, CadAI ve yayın
JSON'u değiştirilmedi. Ham kayıtlar `.pcbai-state/r2-a2/` altında. Bu teslim fiziksel/üretim/EMC,
SPICE veya canlı IPC kabulü değildir; çalışan eski servis yeni kod için yeniden yüklenmelidir.

## R2-A1 — yoksayılan zorunlu kural kapısı (14 Ekim)

`ip/r2-a1-ignore`, ayrı worktree: kontrol kopyasının `.kicad_pro` severity ayarları ve native
ignored_checks birleşimi; kararlı rule kapsam satırları; zorunlu ignore → `checks_incomplete`.
Doğrudan ERC/DRC ve toplu check aynı politikayı kullanır; CLI `sch/pcb/all` exit 2.
Yardımcı assembly/library/style tanıları optional kayıt ve uyarı olarak görünür kalır.
Bilinmeyen ignored kural zorunlu; eksik/bozuk native kapsam veya settings temiz rapor olamaz.
Override dahil kontrol kopyasının girdi SHA'ları kanıt kaydına bağlanır.

[Rapor](spikes/R2-A1.md), [fixture #17](../tests/fixtures/faults/17-ignored-required-rule/README.md).
Yedi severity testi ve yeni bir native-format contract testi eklendi. Bağımsız denetçi
22 hedef test / 109.368 sn / skip yok, ek 14 regresyon; son native-coverage güçlendirmesinde
11 reader/contract ve ayrıca gerçek snapshot/override SHA testi 1/1 geçti. Ruff/diff/lisans temiz.
**Son kaynakta tam takım: 353 test / 349 geçti / 4 skip / 1121.016 sn; Python exit 0.**
Alt süreç toplamı 1124.672 sn; CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP (134218240) ile
konsol kesintisinden ayrıldı. Skip: malformed DRU reddi (KiCad 10.0.4), yapılandırılmamış
Freerouting güvenlik deneyi, Windows symlink yetkisi ve dış kicad-happy kalibrasyonu.
Son tek satırlık aliasing düzeltmesi ve ek manifest testi bu tam kaynak koşusuna dahildir.
Tam koşudan sonra fixture'daki üretilmiş kişisel `.prl` dosyası çıkarıldı; kod/geometri
değişmedi. Bu temizlik sonrası severity takımı **7/7 OK / 85.873 sn / exit 0** tekrarlandı.
Önceki tam koşu 352 test/5898.966 sn, 2 fail/5 skip: ham evidence raporu sözleşmesi
ek kapsam alanıyla bozulmuştu, native report aynen korunarak düzeltildi; connect geri okuması timeout
sonraki hedef tekrarda geçti. Düzeltme sonrası finding/readback/severity 23/23 OK/84.439 sn.
Bu başarısız genel koşu final başarılı koşu olarak kullanılmaz.
Son küçük aliasing düzeltmesi, aggregate kapsam yükseltmesinin child kanıt kaydını değiştirmesini
engeller; yeni test bağımsız 1/1 geçti. Son kaynakta hedef takım 45/45 OK/141.171 sn;
PowerShell stderr redirection shell exit 1 bildirdi, Python exit 0 ayrıca atfedilmedi.
Ayrı gerçek KiCad CLI 11/11 OK, skip yok, 223.786 sn test/224.375 sn alt süreç, Python exit 0.
Genel tekrar 0xC000013A/993.547 sn ile kesildi; sonuç tam takım başarısı değildir.
Son kodun konsolsuz genel koşusu tamamlandı; kesilen koşularla birleştirilmiş başarı sayısı verilmedi.
Ara ölçüm koşuları final kod değişince durdurulup arşivlendi; tamamlanmış final takım diye sunulmaz.

Kullanıcı kartı/ayarlarına yazılmadı, yayın JSON'u değiştirilmedi. Bu iş kayıtlı dosya kontrol
kapsamıdır; artımlı düzenlemeyi sıkı üretim kapısına dönüştürmez. Canlı IPC, SPICE model,
fiziksel kart/EMC/üretim doğrulaması değildir. Çalışan eski servis yeni kaynak için yeniden yüklenmelidir.

## U0 — sabit kaynak ve gerçek komut değerlendirmesi (14 Ekim)

`ip/u0-kaynak-deneyleri`: [U0.md](spikes/U0.md), `scripts/spike_u0.py` ve izole deney
requirements kaydı eklendi. Yedi upstream commit sabitlendi; çekirdek/eklenti sürümü ve çalışma zamanı
bağımlılıkları değişmedi. Beş kaynak CLI için 16 komut ve bozuk girdi deneyi; eSim/Hauksbee not_run.
Kaynak kopyası SHA'ları korundu. Uygulayan `.pcbai-state/u0/run-3/`, bağımsız
`.pcbai-state/u0/audit-run-final/`: exit/statüler ve giriş SHA'ları eşit, timeout yok.

Ölçülen açık: aynı bakırda clearance error **69**, ignore **0**; native ignored_checks içinde clearance,
PcbAi iki koşuda `checks_findings` ve 3 kapsam satırı `ran`; ignored kural için incomplete üretmiyor.
R2-A1 açık. pcb-dfm 108 kontrolde 72 N/A, toplam fail/105 violation; bulgular elle kalibre edilmedi.
Inspector PCB'siz bozuk şematikte exit 0/health 100/passed true; bozuk PCB'de exit 1.
Astra generic profil 26 DRC maddesiyle blocked/assembly_ready=false.

Tam unittest logu: **344 test OK, 5 skip, 1070.683 sn**; PowerShell stderr redirection katmanı
shell exit **1**, bu koşuya Python exit 0 atfedilmedi. Ayrı gerçek KiCad CLI: **11/11 OK, skip yok**,
321.437 sn test/322.093 sn alt süreç, doğrudan subprocess Python exit **0**.
Ruff ve proje lisans denetimi exit **0**. Denetçi ayrıca 14 contract/manifest testi OK.
Scriptte git status return-code kontrolü düzeltildi; son bağımsız tekrar doğruladı.
İlk deneyin cp1254 konsol hatası `-X utf8` ile düzeltildi. İlk tek-seferlik ignored deneyinde
state dizini eksikliği vardı; yeni özel koşuda düzeltildi, kabul sayısı son tekrar aracındaki 69'dur.

Bu teslim kaynak/komut değerlendirmesi; ürün adaptörü, canlı IPC, doğru DFM/geometri, gerçek model/firmware,
fiziksel kart, üretim ve EMC kabulü değildir. Transitif/model lisansları ve iki not_run aracın runtime'ı açık.
Yayın result.json'u yazılmadı; mevcut yayın kanıtlarına ve kullanıcı kart/ayarlarına yazılmadı.

## Yedi depo — üretim ve davranış doğrulaması geliştirme planı

[plan-uretim-dogrulama.md](plan-uretim-dogrulama.md) eklendi: yedi referans deponun
ilgili işlevleri, mevcut kod ve RD/PLAN bağı, U0–U8 bağımlılıkları, fixture/kabul ölçütleri,
lisans ve kanıt sınırları. RD-C3 referans farkları sessiz ayıklama yerine bulgu ve
profil kurallarıyla gerekçeli ayıklama olarak hizalandı. U7, P3/IR STM32G431CBU6
ile F103/F429 hedeflerini ayrı backend/periferik kapsamı üzerinden değerlendirir.

Belge işi: uygulayan `.venv` Ruff exit 0, altı yerel plan bağlantısı mevcut (PowerShell
denetimi exit 0); bağımsız denetçi kendi `.venv` Ruff ve link denetimini exit 0 ile
tekrarladı. Denetçi iki kapsam/tutarlılık bulgusu bildirdi; RD-C3 ve G431 kapsamı düzeltildi
ve denetçinin son salt okunur kontrolüyle kapandı. Staged `git diff --cached --check` temiz.
İlk Python tek-satır link komutu PowerShell alıntılama nedeniyle SyntaxError/exit 1 verdi;
yerine çalışan bağlantı denetimi kullanıldı. Kod değişmediğinden unittest/gerçek KiCad CLI
takımı çalıştırılmadı; bu kayıt testlerin geçtiği iddiası değildir. Upstream README belgeleri
incelendi; harici araç kurulumu, tam kaynak/lisans denetimi, canlı IPC, SPICE koşusu,
fiziksel kart ve üretim/EMC kabulü bu teslimde yapılmadı. Entegrasyon U0–U8 olarak açık.

## EK-2 — IR parça/pin yardımı, dal ip/ek2-parca-yardimi

VS Code geliştirme paketi **0.1.18**, çekirdek **0.1.22** değişmedi. Yalnız
`*.pcbai-ir.json`/`*.pcbai.json` için yerel schema, symbol/footprint/literal pin
tamamlama ve düz metin hover; yeni yerel parça arama komutu salt okunur JSON
sekmesinde pin/pad kontrolünü gösterir. Genel footprint arama indeksi yok;
alternatif sembolün yerel Footprint alanıyla sınırlıdır. Provider servis başlatmaz.

Tampon byte/node/depth/string sınırları; URI/version/session/revision iptali;
her istekte taze kütüphane SHA okumaları ve SHA kapsamlı sunum cache'i var.
Gerçek kök/parent çözümlemesi mevcut ve dangling junction kaçışlarını reddeder;
unpaired surrogate reddedilir. Bağımsız denetim bu kök kaçışlarını ve widget
filterText boşluğunu buldu; düzeltmeler regresyonlara eklendi. Geniş indeks
güncellik kontrolü performans için gevşetilmedi.

Paketlenmiş, yalıtılmış VS Code **1.90.2** + özel gerçek serviste sembol/hover,
01/1, iki birim+ortak pin, footprint kaynağı, SHA değişimi ve zararlı Markdown
kaçışı geçti. Yanlış lib/pin için gerçek öneri widget'ından alternatif kabulü
ayrıca ölçülür. İki kütüphane korpusunda 3 warmup+10 örnek p95 **52,96 ms**.
223 özel kopya kütüphane (kurulumda 244.306.544 bayt; SHA testi sonra özel fixture'ı
değiştirir) nihai ölçümünde p95 **374,23 ms**, indeks ön yükleme **35,781 sn**:
**150 ms hedefi karşılanmadı**. Küçük korpus sonucu geniş kabul diye sunulmaz.

20 hedefli Python testi OK (19 geçti, EK-1 bozuk DRU ret kabulü 1 açık skip),
Son tekrarda **11,134 sn**; dört JS regresyonu, Ruff ve lisans denetimi temiz.
Bağımsız denetçi kök/dangling junction, Unicode ve widget filtreleme bulgularının
düzeltmelerini teyit etti; Python 9/9 ve Node kontrollerini kendisi geçti.
Yeni arama komutunun araç sırası/mock UI akışı testlidir; gerçek quick-pick UI
uçtan uca kabulü bu Host senaryosunda ölçülmedi. Bu koşu tam
çekirdek takım, canlı IPC, SPICE veya üretim kabulü değildir. Kanıtlar worktree
`.pcbai-state/eklenti-ozellikleri/` altında; yayın JSON'u yazılmadı.

## EK-1 — DRU editörü, dal ip/ek1-dru

VS Code 0.1.17: özgün DRU TextMate grammar, yorum/parantez/folding ve beş
düzenlenebilir clearance/track/via/keepout/skew şablonu. Statik katkılar VSIX'e
dahil; çekirdek 0.1.22 değişmedi. Gerçek TextMate+Oniguruma scope testi ve
mevcut JS regresyonları geçti. Yalıtılmış, paketten açılan VS Code 1.90.2
Host'unda dil seçimi, snippet ekleme ve folding geçti; kullanıcı kurulumu değişmedi.
KiCad 10.0.4 kopyası geçerli özel kuralı uygular; bozuk kuralda CLI exit 0
ve temel DRC bulguları dönebilir. Bu ret kabulü tamamlanmadı; test açık skip
ve ham çıktıyla sınırı kaydeder. Renklendirme/DRC exit kodu syntax validator değildir.
Geliştirme kanıtı worktree `.pcbai-state/eklenti-ozellikleri/`; yayın JSON'u yok.
Son hedefli ölçüm: 4 Python testi OK (3 geçti, 1 açık ret-kabul skip),
10,467 sn; Ruff exit 0. Bağımsız denetçinin yakaladığı geçersiz `via_drill`
şablonu `hole_size` olarak düzeltildi; gerçek KiCad testinde beş şablonun
yanına eklenen isimli pozitif clearance kuralının uygulanması artık zorunlu.
Yalnız CLI exit 0 beş şablon için de kabul sayılmaz.

## EK-0 — 13 Ekim, dal ip/ek0-uyumluluk

Kaynak/commit/lisans ve minimum API matrisi [EK0](spikes/EK0.md) içinde.
44 gerçek Gerber PyGerber 2.4.3 strict parse+bbox; 6 Excellon açık skipped;
mm/inç/yay-negatif fixture'ları okundu, bozuk dosya reddedildi. Altı özel demo
kopyasının export öncesi/sonrası revizyonları eşit. Ürün bağımlılığı/kod alımı yok.
Ruff exit 0; kurulu Host güncelleme mutex'inde çalıştırılamadı. Yalıtılmış
portable 1.90.2 gerçek Host'unda eklenti açıldı ve provider API'leri doğrulandı;
bu API keşfi dil/IR teslim kabulü değildir.
EK-1/2 ve gerçek Host kabulleri henüz açık. Yayın kanıtı yazılmadı.
Bağımsız salt okunur denetçi 10 kaynak metadatasının SHA'sını, 44/6 korpus
sayımını ve mm/bozuk PyGerber probe'unu doğruladı; Viewer lisans satırı düzeltildi.
İki mevcut VS Code testi OK (0,218 sn); tam takım bu belge paketinde tekrar koşulmadı.

## Dal entegrasyonu — 13 Ekim

- Tüm `ip/*` dalları tek doğrusal zincirdi; `main` bu zincirin ucuna (RD-A3, `afb140d`) ilerletildi,
  `ip/gizlilik` (yerel ev yolu temizliği, `scripts/export_public.py`) ve `ip/rd-cli-denetim-duzeltmeleri`
  (0.1.22) `--no-ff` ile birleştirildi. Tek çatışma PLAN.md başlık satırıydı. Birleşen dallar ve
  `PcbAi-gizlilik` worktree'si silindi (yalnız önbellek dosyaları vardı); depoda tek dal `main`.
- 0.1.22 birleşik ağaç `.venv` tam takım: **342 test OK, 11 skip**, **565,773 sn**; Ruff exit **0**.
  Skip'ler: 7 gerçek yazım testi (KiCad açıktı), symlink yetkisi, yapılandırılmamış Freerouting/TraceMaker
  (2) ve kicad-happy. Takip edilen dosyalarda yerel ev yolu eşleşmesi **0**.
- KiCad kapalıyken ayrı koşu: `test_kicad_integration` + `test_sch_authoring_integration` **14/14 OK**;
  skip eden 7 yazım testinin **6'sı OK** (blok şematik, PCB taşıma/iz/bölge/DRC, net sınıfı).
  Net sınıfı testi bir koşuda başarısız, tekrarında geçti; kararsızlık ayrıca izlenmeli.
- **Ölçülmedi:** G2-f (`test_sch_scene` R203 işaretçi → `set_value`). İki koşuda test ortasında
  `explorer.exe` üzerinden KiCad açıldı ve yazım doğru biçimde `editor_open` ile reddedildi.
  Atlama koşulu yalnız test başında, editör denetimi yazım anında ölçülür; bu bir kod hatası değil,
  KiCad kapalı tutulan bir koşuda yeniden ölçülmelidir.

## RD dalga 1 tamamlandı — D1-1…D1-7

- Ortak bulgu şeması/kimliği, kimlikli sınırlar, `checks_run` ve `check`, CLI 0/1/2,
  içeriksiz `audit.jsonl`, ayrı sayı/üyelik/ad/çokluk kalibrasyonu ve 13 yazıcıda bağımsız disk geri okuması tamamlandı.
  Çekirdek **0.1.21**; VS Code kodu değişmedi. Her paket ayrı dal ve commit zincirinde; 13 Ekim'de main'e alındı.
- Son `.venv` tam takım: **337 test, 334 geçti, 3 skip**, Python exit **0**;
  unittest **1542,108 sn**, alt süreç **1548,688 sn**. Gerçek KiCad entegrasyonu **11/11**, skip yok.
  Skip'ler Windows symlink yetkisi ve tam koşu kabuğunda yapılandırılmamış iki motor testi.
  Bu iki motor testi `dev-env.ps1` yapılandırmasıyla ayrıca gerçek Freerouting/TraceMaker üzerinden
  **2/2 OK**, **439,029 sn**, skip yok; gerçek preview/apply/checkpoint/restore dahil.
- Son readback/Engine hedef koşusu **50/50 OK**, **104,319 sn**, skip yok. 13 yazıcıda semantik yazım enjeksiyonu,
  doğru SHA/yanlış niyet, fazladan net üyesi, kayıp dosya ve farklı proje R1 regresyonları ölçüldü.
  Uyuşmazlık `ok=false, changed=true, verified=readback_mismatch`; dosya kendiliğinden geri alınmaz.
- Son güçlendirilmiş kalibrasyon **10/10 OK**, **115,085 sn**, gerçek beş demo, skip yok.
  Bileşen/sayfa/net/PCB toplamları ve üye bölümlemesi eşit; pic_programmer'da **19** pin tekrar farkı,
  pic_programmer/video'da ad seçimi farkları raporlanır ve bağımlı dedektörler engellenir.
  Tek kaynak provenance ile single-file sayfa sayısı ölçülür; metadata yoksa bilinmez.
  CLI iz toplamı vermediğinden segment/arc kaynağı `saved_geometry`; bunu CLI ölçümü diye sunmuyoruz.
- R7: beş demo × iki gerçek TraceMaker koşusu; **10/10** sonuç önceki tabloyla eşit ve kaynak hashleri korunmuş.
  ecc83 14→0, pic_programmer 86→14, stickhub 128→29 açık bağlantı; video/interf_u dört koşuda UUID kapısında ret.
  Kıyas süreci exit **1** (bu retler nedeniyle); gerileme yok, temiz demo veya K5 kalite kabulü yok.
- Ruff `.venv\Scripts\ruff.exe check .` ve lisans denetimi temiz; wheel derlemesi ve izole wheel regresyonları geçti.
  [Bağımsız hedefli denetim özeti](rd-dalga1-denetim-ozeti.md): bulgular giderildi ve yeniden üretildi.
  Son metadata için beş bağımsız probe ve güçlendirilmiş bağımsız 10-test koşusu geçti (106,442 sn, skip yok).
  Uygulayan ölçümü tek başına bağımsız tam takım, canlı IPC, fiziksel kart veya üretim kabulü değildir.
- RD-G2 **5/16 fixture** (#1, #1b, #9, #12, #13). #1b niyet sınırı RD-C2'ye kadar açık.
  S11 yayın JSON'u yazılmadı; **RD-B1** ve geçmiş imza temizliği açık; main birleştirmesi 13 Ekim'de yapıldı.
  Geliştirme günlükleri `.pcbai-state/rd-wave1/` altında: `final-full.txt`, `final-full-process.json`,
  `readback.txt`, `calibration-real.txt`, `engines.txt`, `r7.json`, `r7-comparison.json`.

## D1-1 / RD-A1 — ortak bulgu şeması (dal `ip/rd-a1-bulgu`)

- **Uygulama ve uygulayan doğrulaması tamamlandı; bağımsız hedefli Codex denetimi tamamlandı.**
  `pcbai/verify/finding.schema.json` ve `findings.py` ERC/DRC/parite ve diğer
  dalga 1 kaynaklarını ortak şemaya çevirir. KiCad `description`, `type`, `group`, item UUID/pos
  ve diğer ham alanlar korunur; `exclusion`/`ignore` özgün severity'si `raw_severity` alanında kalır.
  Ham KiCad raporu kanıt kaydında değişmez; `verified` değerlerinin anlamı korunur.
- `finding_id`: kaynak, kural, grup ve sıralı item UUID'lerinden SHA-256 ilk 12 hex.
  UUID'li item'ın konumu kimliğe girmez; UUID'siz konum 0,001 mm'ye decimal round-to-even ile yuvarlanır.
  Yinelenen kimlikler deterministik `#n` alır; motor kıyası temel kimlik ve çokluğu kullanır.
  Böylece 1→2 yinelenen bulgu geçişinde yalnız bir yeni hata bulunur; sıra eki değişimi ek hata sayılmaz.
- ERC/DRC, şematik/PCB/motor önizlemeleri ve apply kapısı ortak normalleştirmeyi kullanır.
  Motor önizlemesindeki gerçek DRC bulgularının kaynağı `drc`/`parity` olarak kalır.
  Çekirdek 0.1.15; eklenti kodları/sürümleri değişmedi. Şema wheel paket verisine eklendi.
- `tests/test_verify_findings.py` **15 yeni test**: şema, kimlik tekrarı, UUID'li hareket,
  UUID'siz yuvarlama, kararlı yinelenen sıra eki/çokluk, ham alanlar ve kanıt raporu korunması,
  kaynak/severity eşlemesi, yanlış rapor reddi, motor önizlemesi ve KiCad eklentisi render uyumluluğu.
  İki farklı geçici dizindeki `ecc83-pp` DRC koşuları aynı kimlik listesini verdi; kaynak SHA haritası korundu.
- Tam takım **274 test, OK (271 geçti, 3 skip)**; Python exit 0, 867,938 sn (unittest 864,110 sn).
  Skip'ler önceki gibi Windows symlink yetkisi ve ortamda tanımlı olmayan iki gerçek motor testi.
  Kapalı editör gerektiren gerçek PCB/şematik yazma testleri geçti.
  Ayrı gerçek KiCad entegrasyonu **11/11**, skip yok, Python exit 0, 268,765 sn (unittest 268,471 sn).
  Birleşik CLI/eklenti/motor/çekirdek/VS Code/fixture/yeni şema uyumluluğu **74/74**, exit 0, 50,516 sn.
- Ruff ve lisans denetimi exit 0. Wheel oluşturuldu; `python -I` ile wheel içinden 0.1.15 sürümü ve
  paketlenmiş JSON Schema yüklenerek normalleştirme doğrulandı; kullanıcı ortamına paket kurulmadı.
- Önceki tam ve ayrı CLI koşuları `0xC000013A` ile özet oluşmadan kesildi (352,625 ve 167,922 sn).
  Yerel çalıştırıcı `CREATE_NO_WINDOW` kullanarak alt süreci başlattıktan sonra yukarıdaki tamamlanmış sonuçlar alındı;
  kesin kesinti nedeni belirlenmedi. Ürün/test kodu bu kesinti için değiştirilmedi, önceki günlükler korundu.
  Geliştirme kanıtları `.pcbai-state/d1-1/` altında (`full-hidden.txt`, `full-hidden-process.json`,
  `kicad-hidden.txt`, `kicad-hidden-process.json`, `compat.txt`, statik denetim ve wheel günlükleri).
  Gerçek Freerouting/TraceMaker kalitesi, canlı IPC, fiziksel kart/üretim doğrulanmadı.
  Yayın kanıtı oluşturulmadı; D1-2 başlamadı. Paket bağımsız denetim sonrası birleştirilir.

## RD dalga 0 — 13 Ekim 2026 (dal `ip/rd-dalga0`)

### D1-0 kapanış uygulaması — 13 Ekim 2026

- **D1-0 kabul edildi.** Claude, `ef05261` commit'ini bağımsız denetledi: KiCad editörleri kapalıyken
  proje `.venv` ortamında **259 test, OK (256 geçti, 3 skip), 693,0 sn**, Python exit 0.
  Skip'ler Windows symlink yetkisi ve bu kabukta tanımlı olmayan iki motor (Freerouting, TraceMaker).
  Yeni dört karakterizasyon testi, şematik yazım entegrasyonu, Ruff ve lisans denetimi geçti.
  Uygulayanın `0xC000013A` kesintileri denetimde tekrarlanmadı; tam takım doğrulaması kapandı.
  [Depoda erişilebilir özet](rd-dalga0-denetim-ozeti.md#d1-0-kabulü); ham rapor yerel
  `.pcbai-state/audit-rd-dalga0/d1-0-review.md`. Canlı IPC/fiziksel kart/üretim kabulü değildir.
  Engel olmayan not: fixture kaynak SHA kontrolü `finally` içinde olduğundan, ikinci bir hata asıl test hatasını
  gölgeleyebilir; bu denetimde kod değiştirilmedi.

- `S11.md` ölçülen projeyi `ecc83-pp` olarak belirtir; `ecc83-pp_v2` ölçülmedi.
  AGENTS.md test/lint/CLI/doctor/MCP komutları proje `.venv` yorumlayıcısını kullanır.
- `tests/test_fault_fixtures.py` dört karakterizasyon testi ekler: #1 düz DRC temiz ama parite J2.1
  `net_conflict`; #9 DRC/parite temiz ama native ad→üye eşlemesi dış JSON ile ters;
  #12 araç eksikse `ok=false/not_run/missing_dependency`; #1b DRC/parite temiz ama niyetteki ayrı netler birleşik.
  Her fixture özel geçici kopyada ölçülür; kaynak dosyalarının SHA-256 haritası önce/sonra eşitliği doğrulanır.
- RD-G2 **4/16 fixture** (#1, #1b, #9, #12; #1b, #1'in alt vakası).
  #1b bilinen niyet kaçağıdır; geçen karakterizasyon testi ürünün kusuru yakaladığı anlamına gelmez.
  Yeni ürün yakalayıcısı, canlı IPC/SPICE/fiziksel kart/üretim doğrulaması eklenmedi; çekirdek/eklenti sürümü değişmedi.
- [Dalga 0 denetim özeti](rd-dalga0-denetim-ozeti.md) depoda erişilebilir; ham rapor ve geliştirme
  günlükleri yerel `.pcbai-state/` altında kalır. S11 yayın JSON'u yazılmadı; **RD-B1 açık**.
- Önceki uygulayan koşuları (bağımsız kabulden önce): dört fixture testi **4/4**, skip yok; süreç exit 0, 165,344 sn.
  J2.1 pad UUID doğrulaması eklendikten sonra ilgili test ayrıca **1/1**, exit 0, 16,469 sn.
  Ruff ve lisans denetimi exit 0; `doctor` KiCad CLI 10.0.4'ü buldu, canlı IPC bağlı değil,
  Freerouting/TraceMaker bu kabuk ortamında bulunamadı. Kanıtlar `.pcbai-state/d1-0/` altında.
  Ayrı gerçek KiCad entegrasyonu **11/11**, skip yok; alt süreç exit 0, 343,813 sn
  (unittest süresi 340,518 sn). İlk tam koşu **259 test, 1 failure, 3 skip**, alt süreç exit 1,
  967,141 sn: uygulayan koşu sırasında #1b README'sini güncellediği için kaynak SHA koruması
  bu değişikliği yakaladı; fark yalnız README'de, KiCad/JSON fixture baytları eşit.
  İlk günlük ve süreç sonucu korundu (`full.txt`, `full-process.json`); fixture değişiklikleri
  bittikten sonra tam takım yeniden başlatıldı. Tekrar **259 test, 2 failure, 5 skip**, alt süreç exit 1,
  689,359 sn (unittest 684,664 sn); yeni dört test geçti. Mevcut `NetclassEngineTests.test_power_class_change_with_real_drc_and_byte_equal_restore`
  ve `SchematicMarkerFlowTests.test_marker_on_r203_drives_real_value_edit_to_done` açık KiCad nedeniyle
  `editor_open` ile reddedildi; iki şematik yazım testi de bu nedenle skip oldu.
  Diğer üç skip Windows symlink yetkisi ve iki motor ortamıdır. Günlükler `full-retry.txt`,
  `full-retry-process.json`; o tam koşu yeşil değildi ve kapalı editörlerle yeniden doğrulama gerekiyordu.
  Kullanıcı editörleri kapattıktan sonra üçüncü tam koşu `full-closed.txt`/`full-closed-process.json`:
  yeni dört test geçti, fakat korpus testinde unittest özeti oluşmadan süreç
  **3221225786 (0xC000013A)** ile sonlandı, 211,437 sn. Bu tamamlanmış veya başarılı test koşusu değildir.
  Kapalı editörlerle dar `closed-writes` koşusunda önceki iki failure'ı veren test ayrı ayrı `ok` oldu;
  ardından şematik yazım entegrasyonu sırasında aynı **3221225786** koduyla 101,078 sn'de sonlandı.
  Dar koşunun da unittest özeti yok; 5/5 geçti sayılmaz. Sonlanmanın nedeni belirlenmedi;
  uygulayan tamamlanmış tek tam takım yeşili elde edemedi. Yukarıdaki bağımsız denetim bu doğrulama açığını kapattı;
  önceki koşuların günlükleri korunur, tamamlanmamış koşular başarılı sayılmaz.

### Önceki dalga 0 ölçümü ve bağımsız denetimi

- **Uygulayan ölçümü ve bağımsız denetim tamamlandı; RD-B1 yayın kanıtı açık.** Çekirdek/VS Code değiştirilmedi.
  [S11](spikes/S11.md), geliştirme sonucu (yerel kayıt `.pcbai-state/s11/result.json`).
  kicad-happy MIT commit `06840467ad0f5d76af45f64449b1f5ecb10f052f`, KiCad 10.0.4/Python 3.11.5;
  klon dışında `-I`, shell=False, 120 sn timeout ile özel demo kopyaları. Upstream kodu pakete alınmadı.
- Beş R7 demosu × şematik/PCB × iki tekrar: **20/20 exit 0**, **10/10** finding_id kümesi,
  liste ve ham çıktı SHA eşit. Süre **0,223–16,852 sn**, Windows analiz süreci peak working set
  **40,60–194,50 MiB**. Bütün demo klasörlerinin önce/sonra/son SHA-256 haritaları eşit.
- **385 şematik bileşeni, 13 sayfa örneği, 932 net**: sayılar ve referans kümeleri native netlistle eşit.
  Beş demoda net üye kümeleri eşit; pic_programmer **19 ağda pinleri yineliyor**, çokluk korunan
  listeler birebir değil (U2.7/U2.14 ×4, U5 pinleri ×2). Adsız/UUID kapsamlı net adları native
  adlarla birebir değil; üye eşitliği ad eşitliği diye sunulmaz. RD-A4 bu kıyası tamamladı;
  ad seçimi farkları yukarıdaki dalga 1 sonucunda ayrıca raporlanır.
- PCB **386 footprint, 3055 pad**; düz iz/yay/via/zone/net toplamları, ön/arka toplamları ve CLI
  boyutları eşit. SMD sınıfı video **144/143**, interf_u **1/0**: `BUS1` connect pad'lı kenar
  konnektörü, CLI'de belirtilmemiş. İlk oracle via'yı iz saydı; düzeltildi, ilk ve son loglar ayrı.
- Tek tekrar **474 bulgu**: şematik 225, PCB 249; **439 deterministic/35 heuristic/0 datasheet-backed**.
  Tohum 11013 ile rastgele 20 dosya incelemesi: **14 doğru/2 yanlış/4 belirsiz**. İki alias bulgusu
  aynı port metninin sayfa UUID kapsamını farklı ad sanıyor. Belirsizler: üretici fiyatı, RC aktarım
  işlevi, yuvarlak avlu yerine kutu alanı, gerilim payından tasarım amacı çıkarımı. Etiketler uygulayana ait.
- RD-G2 **3/16 fixture**; yeni yakalayıcı kod yok. [#1](../tests/fixtures/faults/01-drc-zero-short/README.md):
  bakırda iki şematik net birleşirken gerçek normal DRC **0 hata/0 uyarı**; mevcut parite **1 net_conflict**.
  [#9](../tests/fixtures/faults/09-wrong-net-members/README.md): doğru kart normal/pariteli DRC temiz,
  dış JSON iki netin üyelerini ters bildirir; mevcut kalibrasyon aracı yok, yanlış JSON denetlenmiş sayılmaz.
  [#12](../tests/fixtures/faults/12-missing-required-tool/README.md): boş geçerli şematikte mevcut araç ERC temiz;
  gerekli araç yokken **ok=false/verified=not_run/missing_dependency**, ölçüm boş. Toplam checks_incomplete/CLI exit 2 açık.
  Fixture kanıtı (yerel kayıt `.pcbai-state/s11/faults/result.json`).
- Uygulayan tam takım **255 test: 254 geçti, 1 Windows symlink yetkisi skip**, **1134,383 sn**;
  günlük (yerel kayıt `.pcbai-state/s11/unittest-full.txt`). Ayrı gerçek KiCad CLI **11/11**, skip yok,
  **276,517 sn**; günlük (yerel kayıt `.pcbai-state/s11/unittest-kicad.txt`). PowerShell stderr redirection'ı
  unittest çıktısını NativeCommandError olarak sardı ve kabuk exit 1 döndü; iki günlükte de unittest
  `OK` var. Kabuk exit'i test başarısızlığı veya Python exit 0 kanıtı olarak sunulmaz.
  Ruff 0.17.0 doğrudan binary denetimi `All checks passed!`, `python -m ruff check .` exit 0,
  lisans denetimi exit 0; süreç sonuçları (yerel kayıt `.pcbai-state/s11/static-checks.json`).
- Sınırlar: salt dosya/default analiz ölçümü; lifecycle/datasheet, EMC/termal/SPICE/cross/fab dedektörleri,
  fiziksel kart/üretim ve bütün KiCad 10 özellikleri ölçülmedi. Uygulayan ölçümü tek başına bağımsız denetim değildir;
  bu ölçüm ürün kabulü değildir.
  Bağımsız [denetim özeti](rd-dalga0-denetim-ozeti.md): 255 test OK, 3 skip
  (Windows symlink yetkisi ve 2 motor ortamı); gerçek KiCad 11/11, Ruff temiz. Ölçüm iddialarını çürüten bulgu yok;
  denetimde yayın JSON'u ve ecc83 proje adı eksik bulundu. Bunlar önceki uygulayan sonuçlarından ayrı denetçi ölçümleridir.
  K15, K16 adım 1, K20 ve K21 kabul: [karar 0004](decisions/0004-referans-depolar.md).
  K16 adım 2 (vendor), K17, K18 ve K19 açık. [Dalga 1 tarifindeki](plan-rd-dalga1.md) D1-1…D1-7 uygulanmadı;
  D1-0 uygulama durumu yukarıdadır. Yayın sonucu yazılmadı, push yok.

## Gerçek WSL/TraceMaker — 13 Ekim 2026 (dal `ip/tracemaker-wsl`)

- Kullanıcının yeniden başlatması sonrası WSL2 çalıştı. SHA-256 doğrulanmış Ubuntu 26.04.1
  ayrı PcbAi-Ubuntu dağıtımına kuruldu; GCC 15.2.0/CMake 4.2.3/Ninja CPU build **99/99**.
  CUDA, Python binding ve upstream test paketi kapalı; PCBench kullanılmadı.
  [S10 kurulumu ve ikili kimlikleri](spikes/S10.md),
  build (yerel kayıt `.pcbai-state/wsl-build.json`), doctor (yerel kayıt `.pcbai-state/tracemaker-postboot-doctor.txt`).
- Gerçek 0.9.0 CLI kısmi rota için **3**, ölümcül hata için **1** döndürüyor. Önceki 0/1
  izin listesi düzeltildi: route 0/3, place yalnız 0. Kısmi rota `route_complete_reported=false`;
  tamamlama/DRC/kalite kabulü verilmez. Kaynak, korunan baytlar, refill ve yeni hata kimliği
  kontrolleri adaydan önce/uygulamada korunur.
- Uygulayan son ilgili inventory/route/evidence/engine/servis/MCP **60/60**, **12,933 sn**;
  koşu (yerel kayıt `.pcbai-state/tracemaker-final-focused.txt`). Bağımsız son protocol/route **25/25**,
  **3,315 sn**. Windows cp1254 konsol hatası benchmark'ı kesiyordu; backslashreplace düzeltmesi
  gerçek koşu ve bağımsız temsil edilemeyen Unicode fixture'ında ölçüldü. İlk kısmi/önceki
  protokol kıyasları korunur; son ölçüm ayrı dosyadır.
  Bağımsız son rapor (yerel kayıt `.pcbai-state/audit-all-plan/tracemaker-wsl-review.md`).
- Bağımsız gerçek Linux process-group ölçümü: TERM'i yok sayan owned parent+child için
  GNU timeout 1 sn + kill-after 5 → **137**, iki PID de yok; erken Windows timeout sonrası
  Linux sınırında da iki PID yok, geç çıktı yazımı yok.
  Süreç ölçümü (yerel kayıt `.pcbai-state/audit-all-plan/wsl-timeout-results.json`).
- Bağımsız gerçek tiny route iki tekrarda raw-byte/route UUID/geometri eşit; **1→0**,
  blockers boş, gerçek frozen apply/checkpoint ve bayt eşit restore. Gerçek kilit kapısı reddetti.
  Tiny place ve ecc83 eco çalıştı ama **moved=0/no-op**; anlamlı yerleşim kalite kabulü değildir.
- Uygulayan gerçek yapılandırılmış motor entegrasyonu **2/2**, skip yok, **329,263 sn**;
  koşu (yerel kayıt `.pcbai-state/tracemaker-runtime-native.txt`). TraceMaker ve Freerouting gerçek
  küçük fixture preview/render/apply/checkpoint/restore ile ecc83 yeni-hata ret kapısı geçti.
- Beş KiCad demosu × iki koşu; bütün kaynaklar korundu. Son kıyas (yerel kayıt `.pcbai-state/tracemaker-exit-bench.md`),
  JSON (yerel kayıt `.pcbai-state/tracemaker-exit-bench.json`). Ecc83 **14→0**, DRC **42→30** ama iki yeni
  zone clearance → uygulama bloke. Pic **86→14**, DRC **86→14**, 1 via; stickhub **128→29**,
  DRC **128→29**, 19 via. Son iki adayda yeni hata yok; tamamlanmış/temiz kart kabulü yok.
  Video/interf_u duplicate/missing UUID kapısında reddedildi. Ölçülen üç demo çiftinde raw
  motor çıktı SHA-256 aynı; tüm kaynak-kart koruma kontrolleri doğru. Kıyas komutunun genel
  exit 1'i reddedilen kartlar nedeniyle beklenendir; beş temiz demo geçti diye sunulmaz.
- Editable/core/wheel **0.1.14**, 70 dosya, core-only/schema import ve ikili/plugin ayrımı geçti.
  Paket (yerel kayıt `.pcbai-state/tracemaker-runtime-wheel-check.json`), SHA-256
  `45004376b7ec904237e4e148d358f1d4547878dfbbbe49ac3abdd5decae3a171`.
  Ruff/lisans temiz. Önceki tam 252 takım bu son exit-protokol regresyonunu kapsamıyor;
  bu fark son ilgili ve gerçek motor koşularıyla ölçüldü.
- Gerçek iki-pad hareket denemesinde yalnız üst düzey konumun sıfır açı gösterimi farklıydı:
  `(at x y)` ↔ `(at x y 0)`. Yerleşim bekçisi bu iki izinli gösterimi karşılaştırırken eşit sayar;
  kilit, pad/net, değer, iç koordinat ve diğer baytlar korunur, rota bekçisi değişmez.
  Regresyon/olumsuz testler son 60 takımında. Üst üste padli scratch fixture guard'ı geçse de
  **0→2 unconnected** ile apply reddedildi; kaynak korunur. Bu ayrı elektriksel kapı gevşetilmedi.
- Ayrık başlangıçlı owned iki-pad routable fixture gerçek **moved=2**, **2→2 unconnected**,
  blockers boş; frozen bayt eşit apply/checkpoint/bayt eşit restore bağımsız ölçüldü.
  Hareket deneyi (yerel kayıt `.pcbai-state/audit-all-plan/tracemaker-moving-place-separated.json`).
  Bu işlem kabulü beş demodaki yerleşim kalitesi, blok kısıt aktarımı veya fiziksel kabul değildir.
- Kurulu 0.1.14 özel HTTP→MCP stdio status/gerçek WSL motor keşfi **2/2**;
  ölçüm (yerel kayıt `.pcbai-state/tracemaker-mcp-smoke.json`). Versiyon/protokol/PCM son **17/17**,
  **2,418 sn**; kayıt (yerel kayıt `.pcbai-state/tracemaker-final-package-contract.txt`).
- Ortam değişkenleri kullanıcı düzeyinde kaydedildi; dev-env açık process override'ını korur.
  Eski servis/terminal yeniden başlatılmalı veya dev-env dot-source edilmeli. Envanterdeki
  `tested=false`/commit `null`, ayrı manuel build/runtime kanıtıyla otomatik doldurulmaz.

## Pasif tarif SPICE testi — 13 Ekim 2026 (dal `ip/pasif-spice`)

- `spice_block_test`: üç pasif tarifin altı varyantı, tarifin literal pin gruplarından
  oluşturulan ideal R/C netlistiyle gerçek ngspice'ta ölçüldü. Bölücü DC gerilim/akım,
  RC low/high-pass kesim genlik/faz, debounce pullup/pulldown transient karşılaştırması.
  Yüzde 1 ve açık mutlak taban toleransları; eksik/NaN/uyumsuz vektörler hata,
  geçerli ama yanlış ölçüm `passed=false`/`simulation_mismatch` döner.
- Kapalı parametreler, SI/range ve sayı-türü kontrolü; kullanıcı metni SPICE satırı olmaz.
  Özel geçici klasör, ayrı worker, 60 sn timeout. Özgün girdiler, tarif/testbench sürümü,
  netlist SHA ve `source=simulated` ölçümler kanıta bağlıdır; kullanıcı projesine yazım yok.
- Son ilgili takım **52/52**, skip yok, **5,226 sn**;
  koşu (yerel kayıt `.pcbai-state/passive-spice-final-focused.txt`). Bağımsız **48/48**, **4,651 sn**;
  eksik/NaN/AC/time typing ve gerçek kısa-devre mutation olumsuz ölçümleri;
  rapor (yerel kayıt `.pcbai-state/audit-all-plan/passive-spice-review.md`).
  AC scale'de bool imaginary kabulü P2 düzeltildi ve regresyon eklendi. İlk başarısız
  float-literal/AC-scale koşusu korunur; son ölçümler yeşildir.
- Tam takım **252 test: 251 geçti, 1 Windows symlink yetkisi skip**, **1180,332 sn**;
  koşu (yerel kayıt `.pcbai-state/passive-spice-full.txt`). Bu koşu başlarken altı yeni test vardı;
  son bool-scale regresyonu ve cevap sözleşmesi ayrıca son 52 takımında ve kurulu sürümün
  plugin/servis/SPICE **25/25**, **19,723 sn** koşusunda doğrulandı.
- Gerçek global Engine altı varyant **6/6**; özel HTTP→MCP stdio keşif/simülasyon/ret
  **3/3**. Ölçümler (yerel kayıt `.pcbai-state/passive-spice-measure.json`),
  MCP (yerel kayıt `.pcbai-state/passive-spice-mcp.json`).
- Ayrı gerçek KiCad CLI **11/11**, skip yok, **270,643 sn**;
  koşu (yerel kayıt `.pcbai-state/passive-spice-cli.txt`). Kullanıcı ayarlarına/kartlarına yazılmadı;
  gerçek apply/restore, netlist, render ve fab ölçümleri özel fixture'larda geçti.
- Örneklerde en büyük göreli fark: bölücüler **%0**, RC **%1,6e-14**,
  debounce pullup **%0,000177**, pulldown **%0,0000312**. Bunlar belirtilen ideal
  girdilerin ölçümüdür; tüm değer aralığı veya gerçek komponent toleransı kabulü değildir.
- Editable **0.1.13**, wheel 70 dosya: schema/core-only/yeni araç import; ikili/plugin yok.
  Paket denetimi (yerel kayıt `.pcbai-state/passive-spice-wheel-check.json`), SHA-256
  `ee26be460a4b9040a716cf3aceea85a37c5674b51aec4b64bc2183c537a97034`.
- Tarifler **olgunluk 0**. İdeal topology testi gerçek şematik/parça modeli/ERC/stock/
  fiziksel kabul sağlamaz; çok küçük/sıfır uyarımda mutlak tolerans baskındır.
  Windows yeniden başlatma kullanıcı tarafından sonraya bırakıldı; Linux motor kabulleri açık.

## TraceMaker sürüm arayüzü — 13 Ekim 2026 (dal `ip/tracemaker-surum`)

- Pinned 0.9.0 kaynak CLI'si `version` alt komutunu kullanıyor; `--version` sorgusu yanlıştı.
  Envanter sorgusu düzeltildi, lowercase `tracemaker 0.9.0` semver ayrıştırması eklendi.
  Nonzero sorgu `available=false` kalır; `tested=false`, bilinmeyen commit `null` korunur.
- Uygulayan ilgili route/engine/MCP/servis takımında **57/57**, skip yok, **145,153 sn**;
  koşu (yerel kayıt `.pcbai-state/tracemaker-version-tests.txt`). Bağımsız **55/55**, **16,081 sn**,
  strict gerçek fake-child protokolü ve nonzero-query ölçümü; rapor (yerel kayıt `.pcbai-state/audit-all-plan/tracemaker-version-review.md`).
  Ruff/lisans temiz. Önceki 243 tam takım yeni üç envanter testini kapsamadı.
- Editable ve bağımsız wheel import **0.1.12**; 69 dosya, şema mevcut, dış ikili/plugin yok.
  Paket ölçümü (yerel kayıt `.pcbai-state/tracemaker-version-wheel-check.json`), SHA-256
  `7d6fdecd89ffc8b1504a0e54882d284f1ffabd21eebeb6789596327e3b1a5c34`.
- Bu kaynak/arayüz denetimi gerçek Linux motorunu çalıştırma değildir. WSL yeniden başlatma,
  derleme, beş demo kıyası, determinizm/timeout ve K5 açık kalır.

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
  Rapor (yerel kayıt `.pcbai-state/audit-all-plan/state-yapilandirma-review.md`).
- Kesilen ilk tam koşu tamamlanmış kabul edilmedi. Yeniden başlatılan son tam takım
  **243 test: 242 geçti, 1 Windows symlink yetkisi skip**, **833,536 sn**;
  kayıt (yerel kayıt `.pcbai-state/state-resumed-full.txt`). Blok yazımı ve state farkları birlikte kapsandı.
  Ayrı gerçek CLI **11/11**, skip yok, **262,264 sn**; kayıt (yerel kayıt `.pcbai-state/state-final-cli.txt`).
  Gerçek şematik/kart apply ve restore atlanmadı. Ruff/lisans temiz.
- Editable **0.1.11** kuruldu; wheel 69 dosya, schema/core-only import, dış ikili/plugin yok.
  Paket denetimi (yerel kayıt `.pcbai-state/state-wheel-check.json`), SHA-256
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
  IR/hesap/işaret ve dokuz yeni blok testi. Koşu (yerel kayıt `.pcbai-state/block-final-focused.txt`).
  Önceki 228 tam takım 0.1.9 IR paketine aittir; bu farkın tek tam 237 koşusu yapılmış gibi sunulmaz.
- İlk test fixture'ında eski IR pin konumu 5 mm off-grid idi; 5,08 mm yapıldı. Diğer yanlış beklentiler:
  güncel ref context'i olmayan ikinci plan ve singleton ERC uyarısına rağmen erc_ok bekleme.
  Başarısız ilk koşu (yerel kayıt `.pcbai-state/block-first-tests.txt`) ve
  ara koşu (yerel kayıt `.pcbai-state/block-focused-tests.txt`) korunur; son tekrar yeşildir.
- Bağımsız denetçi **41/41**, skip yok, 99,153 sn; ayrıca gerçek preview/apply/tek checkpoint/
  frozen bytes/bayt eşit restore, signed marker done ve preview-evidence reddi, ERC identity injection.
  Yerleşim P2 (görünür property/free-text scene'e girmiyordu) düzeltildi; bağımsız field/text/sheet
  property recheck artık reddediyor. Rapor (yerel kayıt `.pcbai-state/audit-all-plan/add-block-review.md`).
- Native ölçüm bir şematik SVG sayfası, 3 exact net, 0 hata/2 uyarı; candidate bytes tam eşit,
  checkpoint restore bayt eşit. Ölçüm ve render (yerel kayıt `.pcbai-state/block-measure/result.json`).
- Kurulu **0.1.10**, gerçek özel HTTP servisi → MCP stdio ile `add_block` önizleme/apply ve
  checkpoint/restore tamamlandı; kaynak önizlemede değişmedi, geri yükleme bayt eşit,
  gerçek iki ERC uyarısı korundu. MCP kayıt (yerel kayıt `.pcbai-state/block-mcp-smoke.json`).
- Ruff/lisans temiz; editable **0.1.10**, wheel **69 dosya**, core-only/schema import başarılı,
  harici ikili/plugin yok. Paket (yerel kayıt `.pcbai-state/block-wheel-check.json`).
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
  Ölçüm (yerel kayıt `.pcbai-state/ir-measure/result.json`). Birleşik divider/RC yük etkisi bu ölçümde yoktur.
- Bağımsız denetçi **42/42**, skip yok, 1,962 sn; yüksek geçiren RC ve yüklenmiş bölücü gerçek
  ngspice kıyasları, adversarial JSON/ölçek/net ve izole wheel/dependency import kontrolleri.
  Ruff/lisans temiz, kalan maddi bulgu yok. Rapor (yerel kayıt `.pcbai-state/audit-all-plan/ir-bloklar-review.md`).
- Gerçek özel yerel HTTP servisi → MCP stdio akışında **4/4** kontrol: araç listesi, hesap/kanıt,
  IR ön denetim ve boolean miktar reddi. Kayıt (yerel kayıt `.pcbai-state/ir-mcp-smoke.json`).
- Son sürüm/manifestte odaklı takım **15/15**, skip yok, 0,520 sn;
  koşu (yerel kayıt `.pcbai-state/ir-final-focused.txt`). Ayrı gerçek KiCad CLI **11/11**, skip yok,
  295,993 sn; kayıt (yerel kayıt `.pcbai-state/ir-cli-tests.txt`). Kullanıcı editörleri kapalıydı.
- Tam takım **228 test: 227 geçti, 1 Windows symlink yetkisi skip**, 800,626 sn;
  koşu (yerel kayıt `.pcbai-state/ir-full-tests.txt`). Gerçek yazma/restore testleri atlanmadı.
  Ruff ve lisans denetimi temiz. Doctor, WSL dağıtımını boş/TraceMaker'ı eksik gösteriyor;
  önceki yeniden başlatma ihtiyacı sürüyor, S10/K5 kapatılmadı.
- Editable 0.1.9 kuruldu; son wheel **68 dosya**, paketlenmiş IR şeması, core-only import,
  yabancı motor ikilisi/plugin bağımlılığı yok. SHA-256
  `83e9f7f1d8589686f4ad36136ab0781232bc9952e6183f1e738d7fba1de7ee59`;
  denetim (yerel kayıt `.pcbai-state/ir-wheel-check.json`). Çalışan eski servisler kendiliğinden güncellenmez.
- Bu ölçümler çoklu sayfa apply/UUID eşleme, gerilim/akım/STM32 AF, bağımsız datasheet/stok,
  11 olgunluk-1 blok, gerçek model kıyası veya fiziksel kart kabulünü kapatmaz.

## Yerel parça ve şematik yazımı — 12 Ekim 2026 (dal `ip/parts-sch`)

- `search_parts`: özel SQLite FTS5 dizini, parametreli/alıntılanmış sorgu, kalıtılan metadata,
  SHA-256 içerik yenileme; veritabanı/journal/WAL/SHM için symlink/junction/hardlink yazma engeli.
  Geçersiz kalıtım kayıtları atlanır ve `index_warnings` döner; indirilen katalog/stok yok.
- İlk tam CST dizin oluşturma yavaştı. Yalnız metadata için dengeli sözdizimi taraması eklendi;
  gerçek kurulu kütüphanelerde ilk arama **36,18 sn**, sonraki **0,29 sn**.
  Ölçüm (yerel kayıt `.pcbai-state/parts-measure/index-timing.json`). Sembol/pin doğrulaması hâlâ tam CST ile yapılır.
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
  İlk bağımsız denetim (yerel kayıt `.pcbai-state/audit-all-plan/parts-sch-review.md`).
  Denetçi kullanım sınırına takıldığı için son farkın bağımsız tekrar koşusu tamamlanamadı;
  uygulayanın regresyonları bağımsız denetim diye sunulmaz. ikinci salt okunur son
  kod denetimi de 240 sn'de zaman aşımına uğradı; geçerli sonuç yok.
- Son tam takım **209 test: 195 geçti, 14 skip**, 326,077 sn; Ruff/lisans temiz.
  Tam koşu (yerel kayıt `.pcbai-state/parts-full-after-fix.txt`). Skip: bir Windows symlink yetkisi,
  13 açık KiCad nedeniyle yazma deneyi. Kapalı ortamda önceki odaklı 17/17 ayrı ölçümdür.
  İlk tam koşu **209 test, 2 hata, 3 skip**, 650,022 sn:
  biri paketlenmiş çekirdeğin `kicad_plugin.configure` bağımlılığıydı (çekirdek permissions'a alındı,
  taze iki checkout + parça regresyonları **8/8** geçti); diğeri koşu sırasında açılan
  KiCad'in gerçek yazmayı doğru reddetmesiydi. Başarısız ilk koşu (yerel kayıt `.pcbai-state/parts-full-tests.txt`)
  korunur; bulgular temiz kabulüne dönüştürülmez.
- Geliştirme ortamının build bağımlılıkları tamamlandı, editable çekirdek **0.1.8** kuruldu;
  `.pcbai-state/wheels/pcbai-0.1.8-py3-none-any.whl` üretildi. Eski çalışan servisler
  kaynak değişimini otomatik yüklemez; bu kurulum canlı kullanıcı oturumu kabulü değildir.
- Wheel yalnız çekirdek+MCP ile taze klasörde açılıp yeni araçlar import edildi; **61 dosya**,
  harici motor ikilisi/development plugin bağımlılığı yok. Paket denetimi (yerel kayıt `.pcbai-state/wheel-check.json`).
- Ayrı zorunlu gerçek CLI takımında **11 test: 8 geçti, 3 açık-editör skip**, 167,210 sn;
  kayıt (yerel kayıt `.pcbai-state/parts-separate-cli.txt`). Bunlar atlanan gerçek edit/restore kabullerini kapatmaz.
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
  Uygulayan (yerel kayıt `.pcbai-state/parts-final-focused.txt`),
  son bağımsız rapor (yerel kayıt `.pcbai-state/audit-all-plan/parts-sch-final.md`).
  Tam 209 takım önceki guard farkındadır; son fark için bu ayrı ölçümler kullanılır, 213 testin
  tek tam koşusu yapılmış gibi sunulmaz. Son leading-zero `#PWR01` referans deltası ayrıca **11/11**.
- Bağımsız taze FTS ölçümü: **39,484 sn / 0,391 sn**, 22.776 parça, uyarı yok;
  kayıt (yerel kayıt `.pcbai-state/audit-all-plan/parts-sch-final-index-timing-recheck.json`).
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
- Beş demo × iki JAR koşusu güncel tabloda (yerel kayıt `.pcbai-state/s4-current.md`): ecc83 ve pic_programmer
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
Kayıtlar tam takım (yerel kayıt `.pcbai-state/audit-all-plan/final-unittest-dev.txt`),
ayrı CLI (yerel kayıt `.pcbai-state/audit-all-plan/final-cli.txt`),
bağımsız inceleme (yerel kayıt `.pcbai-state/audit-all-plan/final-review.md`) altındadır;
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
  zaman aşımına uğradı; geçerli denetim sayılmadı. 
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
Yeni browser raporu (yerel kayıt `.pcbai-state/G1-browser-result.json`) ve ekran görüntüleri (yerel kayıt `.pcbai-state/viewer-e2e/`)
yalnız `.pcbai-state/` altında. Eski yayın kanıtları git blob'larıyla karşılaştırıldı, değişmedi.
Yenileme 7,754 / 18,804 / 9,768 sn (diğer denetimlerle eşzamanlı koşu); G5 kabulü sayılmaz.

Ek gerçek Extension Host koşusu başarısız: beklenen rapor üretilemedi; geçici profil log dosyası
temizlenirken WinError 32/267. Kullanıcı profiliyle kabul yapılmış sayılmaz. Kalan kendi geçici
profil klasörünü silme işlemi otomatik onay denetiminde "blocked by policy" ile reddedildi;
klasörün kalanı geçici dizinde bırakıldı. Yerel host logu (yerel kayıt `.pcbai-state/eksikler-ilk-paket/host-audit.txt`).

Yerel nihai ölçümler: 131 test (yerel kayıt `.pcbai-state/eksikler-ilk-paket/e1-package-tests.txt`),
ayrı CLI (yerel kayıt `.pcbai-state/eksikler-ilk-paket/final-cli.txt`),
staging sonucu (yerel kayıt `.pcbai-state/eksikler-ilk-paket/e1-package-result.json`),
doctor (yerel kayıt `.pcbai-state/eksikler-ilk-paket/final-doctor.json`),
paket SHA-256 (yerel kayıt `.pcbai-state/eksikler-ilk-paket/artifacts.json`),
eski yayın kanıtları değişmedi (yerel kayıt `.pcbai-state/eksikler-ilk-paket/published-preservation.json`).

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
  kaydedildi. İki ayrı yazan uygulama ve düzeltmelerin B tarafından tekrar
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

## D1-2 — 13 Ekim 2026

Kimlikli limit kaydı ve docs/limits.md eklendi. 2 limit testi OK, Ruff exit 0; dosya/belge kanıt bağlantıları doğrulandı.

Bağımsız hedefli Codex denetimi tamamlandı. Son dalga doğrulaması ayrıca kaydedilir; hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Geliştirme kanıtları `.pcbai-state/rd-wave1/` altında; yayın JSON'u yazılmadı.

## D1-3 — 13 Ekim 2026

check aracı ve checks_run manifesti eklendi; eksik/çöken kontrol incomplete, excluded bulgu findings olur. 27 hedefli test OK, Ruff exit 0; gerçek fixture #1 pariteyi yakaladı.

Bağımsız hedefli Codex denetimi tamamlandı. Son dalga doğrulaması ayrıca kaydedilir; hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Geliştirme kanıtları `.pcbai-state/rd-wave1/` altında; yayın JSON'u yazılmadı.

## D1-4 — 13 Ekim 2026

pcbai check komutu eklendi; gerçek alt süreçlerde 0/1/2 çıkışları ve JSON doğrulandı. 5 CLI testi OK; Ruff exit 0.

Bağımsız hedefli Codex denetimi tamamlandı. Son dalga doğrulaması ayrıca kaydedilir; hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Geliştirme kanıtları `.pcbai-state/rd-wave1/` altında; yayın JSON'u yazılmadı.

## D1-5 — 13 Ekim 2026

Engine.call üzerinde içeriksiz audit.jsonl eklendi: süreç/iş parçacığı kilidi, 10 MB tek yedek, yazma hatasında uyarı. 17 audit/job/manifest testi OK, Ruff exit 0; argüman metni loglanmaz.

Bağımsız hedefli Codex denetimi tamamlandı. Son dalga doğrulaması ayrıca kaydedilir; hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Geliştirme kanıtları `.pcbai-state/rd-wave1/` altında; yayın JSON'u yazılmadı.

## D1-6/RD-A4 — 13 Ekim 2026

Kalibrasyon: 10 test gerçek beş demo ile geçti (40,209 sn, skip yok). Net bölümlemesi beşinde eşit; pic_programmer 19 çokluk farkı ve iki demoda ad seçimi farkları bağımlı dedektörleri engeller. UUID kapsamı yalnız açık native sayfa eşlemesiyle normalleştirilir. CLI iz sayısı sunmadığından segment/arc toplamı kaydedilmiş geometriyle ölçülür. A2 hata manifestinde istenen parite ve giriş hashleri bağımsız denetim bulgusuna göre düzeltildi.

Bağımsız hedefli Codex denetimi tamamlandı. Son dalga doğrulaması ayrıca kaydedilir; hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Geliştirme kanıtları `.pcbai-state/rd-wave1/` altında; yayın JSON'u yazılmadı.

## D1-7/RD-A3 — 13 Ekim 2026

13 yazma aracında disk SHA ve bağımsız niyet geri okuması, checkpoint geri yükleme önerisi ve MCP changed=true hata sözleşmesi eklendi. 50 readback/Engine testi OK, gerçek connect/add_block netlisti dahil; 13 semantik yazım enjeksiyonu ve SHA doğru yanlış aday testleri geçti. Fixture #13 eklendi (5/16). Bağımsız denetim iki hata yolunu buldu; proje kapsamı ve yazım sonrası kayıp belge yanıtları düzeltildi. Ruff .venv executable exit 0.

Bağımsız hedefli Codex denetimi tamamlandı. Son dalga doğrulaması ayrıca kaydedilir; hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Geliştirme kanıtları `.pcbai-state/rd-wave1/` altında; yayın JSON'u yazılmadı.

## Dalga 1 denetim düzeltmeleri — 13 Ekim 2026

CLI JSON çıktısı cp1252 strict dahil ASCII güvenli Unicode kaçışlarıyla yazılır; parse edilen değerler kayıpsızdır ve 0/1/2 çıkışları korunur. Denetim kaydı thread-local/nested çağrı bağlamında aracın mevcut doğrulanmış hedefini kullanır; fazladan proje hash taraması kaldırıldı, güvenlik kontrolleri korunur. Son üretilen PCM arşivi metadata 0.1.14 olarak doğrulandı. Hedefli son test ölçümü aşağıda kaydedilir; önceki 337-test tam koşu 0.1.21 içindir.

Son düzeltme koşusu **76 test OK**, **100,030 sn**, Python exit **0**, skip yok
(`post-review-final-tests.txt`). CLI, audit, Engine, jobs, manifest ve 13 yazıcının readback testleri dahil.
Bağımsız denetçi aynı ürün koduyla CLI/cp1252 testlerini geçti; düzeltilmiş audit beklentisiyle
**6 test OK**, **0,365 sn**, skip yok. İç içe çağrı hedefi ve ek tarama yokluğu ayrıca ölçüldü.
Ruff ve lisans denetimi temiz. İlk ölçümlerde testin sabit hash sayısı beklentisi yanlıştı;
aracın kendi zorunlu taramalarıyla audit sarmalayıcısı kıyaslanacak şekilde düzeltildi.
Bu düzeltme turunda tam takım yeniden koşulmadı (337-test ölçümü 0.1.21'e aittir); 0.1.22 tam takımı daha sonra
dal entegrasyonunda ölçüldü: 342 OK / 11 skip (bkz. "Dal entegrasyonu — 13 Ekim").
Hedefli testler canlı IPC/fiziksel kart/üretim kabulü değildir. Yayın JSON'u yazılmadı.
Çalışan eski servis bu kodu kendiliğinden yüklemez; takım bitince `python -m pcbai stop` ile durdurulabilir,
ilk istemci isteğinde yeniden açılır. Bekleyen önizlemeler yeniden oluşturulmalıdır.

## AJ-1 VS Code ajan seçici — 14 Ekim 2026

VS Code eklentisi 0.1.19. Yan panelde **YAPAY ZEKÂ / Ajan** listesi ve `PcbAi: Ajan seç` komutu: Claude Code,
Claude Code (terminal), Codex, Codex (terminal), Cline, Kilo Code, Roo Code, GitHub Copilot Chat, Sadece panoya kopyala.
Seçim `globalState['pcbai.agent']`'ta; kurulu olmayan ajan seçilemez, kayıtlı seçim kaldırılınca tercih sırasına düşer.
`agents.js` CadAI `agents.js@1878212`'den uyarlandı; Claude Code için ölçülmüş `claude-vscode.editor.open` yolu ilk sırada.
Teslim sonucu (`sent`/`typed`/`typed+clipboard`/`clipboard`/`opened`) kullanıcıya aynen bildirilir. Kart ve şematik
görünümündeki "Ajana sor" aynı yoldan seçili ajana gider. Terminal CLI'ları yalnız `.exe` ile, kabuksuz argv olarak
açılır; 7000 karakteri aşan istem `<proje>/.pcbai-state/prompts/<uuid>.md` dosyasına yazılır (24 saatte silinir).

Ölçüm (proje `.tools/node` v22.23.3): `test_extension.js`, `test/sidebar.test.js`, yeni `test/agents.test.js`,
`test/part_assist.test.js` geçti. `test/dru.test.js` bu ortamda `vscode-textmate` geliştirme bağımlılığı kurulu
olmadığı için başlamadı (değişiklikten bağımsız). Python kodu değişmedi. Gerçek VS Code Host'unda her ajanın
kutuya yazma kabulü (plan AJ-1 "Bitti") **yapılmadı**; testler sahte `vscode` API'siyle dalları ölçer.


## 14 Ekim — AJ-S1 KiCad wx pencere denemesi (dal `ip/ajs1-wx`)

Sonuç `docs/spikes/AJ-S1.md`; deneme betikleri `scripts/spikes/ajs1/`. Ölçülen (KiCad kapalı, eklenti venv
Python 3.11.5, wx 4.2.2/wxWidgets 3.3.2): wx.Frame 0,54 s'de açıldı, ön planda ve odakta; ikinci örnek soketle
mevcut pencereyi öne getirip 0,25 s'de çıktı; sahte üst süreç ölünce pencere 0,29 s'de kapandı; kipy
bağlantısız yoklama medyan 0,94 ms. kipy 0.8.0'da `Board.revert()` (RevertDocument) var. Gerçek KiCad'de ön
plan, bloklama, gerçek `get_selection` maliyeti, düğmeden tek örnek ve KiCad kapanışı **ölçülmedi** — elle adım
bekliyor; izole deneme düğmesi `Documents\KiCad\10.0\plugins\org.pcbai.ajs1` yerinde bırakıldı. Ön karar: wx.

## AJ-2 MCP'yi ajanlara bağla — 14 Ekim 2026

VS Code eklentisi 0.1.20. Yeni komut `PcbAi: MCP'yi ajanlara bağla` (`pcbai.connectAgents`); yan paneldeki
"Ajan için MCP ekle" düğmesi bu komuta gider, `pcbai.addMcp` geriye uyum için kalır. `mcp_setup.js` CadAI
`mcp_setup.js@da608c7`'den uyarlandı. Hedefler: Claude Code çalışma alanı `.mcp.json` (proje listesiyle) ve isteğe bağlı
`claude mcp add -s user`, Codex `~/.codex/config.toml` `[mcp_servers.pcbai]` (alt tablolar dahil değiştirilir, diğer
tablolar korunur), Cline/Kilo/Roo `globalStorage/<ext>/settings/*mcp_settings.json`, VS Code kullanıcı `mcp.json`.
VS Code'da `vscode.lm.registerMcpServerDefinitionProvider` çalışma anında varsa yerel kayıt yapılır ve `mcp.json`
kopyası kaldırılmak üzere önerilir; `engines` 1.90'da kaldı. Her yazımdan önce `*.pcbai-bak` yedeği; ayrıştırılamayan
JSON/TOML'a bayt düzeyinde dokunulmaz; sonuç "Codex: yazıldı, Kilo Code: JSON bozuk, dokunulmadı" biçiminde bildirilir.
Seçili ajanın pcbai kaydı yoksa yan panel uyarı satırı gösterir.

Kullanıcı düzeyi kayıtlar `PCBAI_PROJECTS` taşımaz. `mcp_server/client.py`: proje listesi boşken çalışan servise
bağlanır; servis yoksa servis başlatmaz, `ServiceUnavailable` ile Türkçe talimat döner. MCP vekili bu durumda
`tools/list`'te yalnız `pcbai_status`'u gösterir, çağrı `service_unavailable` hatalı araç sonucu döner.
Onaysız araç listesi (Cline `autoApprove`, Kilo/Roo `alwaysAllow`) kayıttaki `readOnlyHint=true` ve
`destructiveHint!=true` araçlardan üretilir; paketlenen kopya `mcp_tools.json`
`python -m mcp_server.readonly_tools --write` ile üretilir ve testle kayda eşit tutulur. `start_job` listede: yazan motor
işleri yalnız `mode=preview` ile kabul ediliyor.

Ölçüm: `tests/test_mcp_setup.py` 6 test + `tests/test_mcp.py` 7 test OK; eklenti `test/mcp_setup.test.js` (geçici
userDir/HOME, 7 hedef), `test_extension.js`, `test/sidebar.test.js`, `test/agents.test.js`, `test/part_assist.test.js`
geçti; `test/dru.test.js` `vscode-textmate` kurulu olmadığından başlamadı (main'de de aynı). Tam Python takımı **384 test OK, 5 skip, 1.428,3 sn**. Ruff temiz. VSIX 0.1.20
`mcp_setup.js` ve `mcp_tools.json`'u içeriyor. Testler gerçek `%USERPROFILE%\.codex` ya da globalStorage dosyalarına
yazmadı. Gerçek Claude Code/Codex/Cline'ın `pcbai_status` çağırması (elle kabul) **yapılmadı**.

## AJ-7 (kısmi) servis olay kaydı — 14 Ekim 2026

Ön koşul AJ-4 main'de **değil**; bu dal yalnız AJ-4'e bağlı olmayan servis tarafını içerir. `pcbai/service/events.py`:
bellekte son 500 olay (`seq`, zaman, istemci, araç, `ok`/`blocked`/`error:<kod>`, `change_id`); argüman değeri yazılmaz.
`Engine.call(..., client=)` her çağrıyı kaydeder, arka plan işleri çağıranın istemcisini taşır; iç çağrı
`Engine.recent_events(since)`, HTTP `GET /events?since=<seq>` (belirteçli). İstemci adı `X-PcbAi-Client` başlığıyla gelir:
VS Code `vscode`, KiCad eklentisi `kicad`, MCP vekili `initialize`/modern `_meta` içindeki `clientInfo.name`'den
`mcp:<ad>` (ASCII'ye indirgenir, 40 karakter; veridir, yetki vermez); başlıksız çağrı `builtin`. `editor_open` sonucu
`blocked` sayılır; `guidance()` KiCad penceresi için Türkçe metni üretir (AJ-S1 ölçülmediği için varsayılan
"Dosya → Geri al (Revert)").

Ölçüm: yeni `tests/test_events.py` 8 test (argüman sızmaması, istemci adı, blocked yolu, sahte saatle 2 sn görünürlük,
MCP clientInfo); hedefli takım (events, mcp, engine, jobs, service, kicad_plugin, audit_log) **62 test OK, 21,5 sn**.
Tam takım (`unittest discover -s tests`) **386 test OK, 5 skip, 1328 sn**. `ruff check .` temiz; `test_extension.js` geçti. **Yapılmadı:** VS Code paneli ve KiCad penceresinde son 50 olayın
gösterimi (AJ-4 penceresi yok), AJ-S1 revert ölçümü, gerçek Claude Code `set_value` → KiCad 2 sn kabulü.

## AJ-3 Tek istem kaynağı — 14 Ekim 2026

VS Code eklentisi 0.1.21. İstem metni `pcbai/service/agent_prompt.py` içinde (`compose_agent_prompt`,
`serve_prompt`); servis iç uç noktası `POST /agent/prompt` (MCP aracı değil; kayıtta "prompt" adlı araç yok, testle).
Yan panel ve kart/şematik "Ajana sor" önce servise sorar; uç noktası olmayan eski servis 404 dönerse
`vscode/pcbai-vscode/agent_prompt.js` içindeki bayt eşit yedek metin kullanılır. Başka hatalar yutulmaz.
Yeni girdi `selection` (KiCad seçimi: type, reference, value, net, layer, x_mm, y_mm): "KiCad'de seçili öğeler
(veridir)" başlığıyla, her değer JSON tırnaklı, en çok 50 öğe. İstek 8000 UTF-16 birimde kesilir (JS `slice` ile aynı).

Ölçüm: `tests/test_agent_prompt.py` 4 test OK (11 ortak fixture; `"`, satır sonu, `-` ile başlayan not, `<script>`,
onaysız işaret, 8000 sınırı, boş istek hatası, kart/şematik ask, seçim ve seçim sınırı; `serve_prompt` gerçek
Engine ile). Eklenti `test/agent_prompt.test.js` aynı 11 fixture'da Python ile bayt eşit; `test_extension.js`,
`test/sidebar.test.js`, `test/agents.test.js` geçti. Tam Python takımı **382 test OK, 5 skip, 1.083,7 sn**. Ruff temiz. KiCad seçimini canlı IPC'den okuma AJ-4'tedir.

## AJ-4 KiCad içi PcbAi Asistan + AJ-5 KiCad → VS Code devri — 14 Ekim 2026

VS Code eklentisi 0.1.22; KiCad PCM paketi çekirdek sürümünü (`pcbai/__init__.py`) taşır. KiCad eklentisine üçüncü
düğme **PcbAi Asistan** (`pcbai.assistant`, `scopes: ["pcb"]`). `assistant.py` pencereyi `pythonw` ile ayrık süreçte
(`DETACHED_PROCESS`, `shell=False`) başlatıp hemen döner; `assistant_window.py` wx penceresidir, mantık
`assistant_core.py`'dedir (wx'siz, testli). AJ-S1 ön kararı uygulandı: tek örnek (`%LOCALAPPDATA%\PcbAi\assistant.lock`
+ `127.0.0.1` belirteçli "raise" soketi), üst süreç (KiCad) izleme 250 ms, "üstte tut".

Pencere: ajan listesi (VS Code'daki ajan / Claude Code terminal / Codex terminal / pano; algılama `where`, bilinen
yollar ve `~/.vscode/extensions/extensions.json`, 3 sn sınır, yalnız `.exe`), istek kutusu, KiCad seçimi (kipy
`get_selection` ~0,7 sn yoklama → type/reference/value/net/layer/x_mm/y_mm), açık işaretler, varsayılan açık istem
önizlemesi, ERC/DRC (servisin `check` aracı, `scope=all`: R2-A1/R2-A2 kuralları VS Code ile aynı), son 50 ajan olayı
(`GET /events`, AJ-7) ve `blocked`/değişiklik sonrası Türkçe talimat. İstem `POST /agent/prompt`'tan gelir (AJ-3).
Terminal ajanları yeni konsolda argv ile başlar; 7000 karakteri aşan istem `<proje>/.pcbai-state/prompts/` dosyasına
yazılır. Ajan seçimi `%APPDATA%\PcbAi\assistant.json`; KiCad ayarları değişmez. Yerleşik model AJ-6 bölümündedir.

AJ-5: servis `pcbai/service/handoff.py` + iç uç noktalar `/handoff/create|take|report|status` (MCP aracı değil).
Kayıt `<state>/handoff/<uuid>.json`, 10 dk ömür, tek kullanım; alındıktan sonra istem kayıttan silinir. KiCad penceresi
yalnız kimliği taşıyan `vscode://taymur.pcbai-vscode/handoff?id=<uuid>` bağlantısını açar. Eklenti (`handoff.js`,
`onUri`) istemi alır, yan paneldeki istek kutusuna doldurur, panelde seçili ajana `agents.open()` ile verir ve sonucu
(`typed`, `clipboard`…) servise yazar; pencere bunu durum satırında gösterir. Proje bu VS Code penceresinde açık
değilse sorar ("Yine de gönder" / "Klasörü aç"); tahmin etmez.

Ölçüm: yeni `tests/test_kicad_assistant.py` 11 test (algılama, `.cmd` reddi, seçim satırları, servis istemi, argv/
kabuksuz CLI, uzun istem dosyası ve 24 sa temizlik, devir URL'sinde yalnız kimlik, check satırları, servisle aynı
talimat metni, tek örnek ve yanlış belirteç), `tests/test_handoff.py` 3 test, `tests/test_service.py` gerçek servis
sürecinde devir uç noktaları; `tests/test_kicad_plugin.py` yeni eylem, ikon ve PCM şemasıyla geçti. Eklenti
`test/handoff.test.js` (geçersiz kimlik, tek kullanım, proje sor/reddet/klasör aç/yine de gönder, sonuç bildirimi)
ve diğer 6 eklenti testi geçti. Tam Python takımı (main birleşik) **427 test OK, 5 skip, 955,3 sn**; ruff temiz. KiCad 10'un Python'u (wx 4.2.2) ile pencere KiCad kapalıyken kuruldu: dört satır
algılandı, bağlantı hatası durum satırında göründü, çökme yok. VSIX 0.1.22 ve PCM zip yeni dosyaları içeriyor.
**Yapılmadı (elle kabul):** gerçek KiCad 10'da düğmenin pencereyi açması, öne gelme/odak, ikinci tıklama, seçimin
istemde görünmesi, KiCad kapanınca pencerenin kapanması, terminal CLI'nın istemi alması ve KiCad → VS Code devriyle
istemin Claude Code kutusuna düşmesi.

## AJ-6 Yerleşik model + AJ-7 VS Code etkinlik paneli — 14 Ekim 2026

VS Code eklentisi 0.1.24 (dalda 0.1.23 yazılmıştı; main R2-B2 ile 0.1.23 olduğu için birleştirmede artırıldı). `kicad_plugin/assistant_model.py` CadAI `agent.py` + `providers.py@da608c7` uyarlaması;
PcbAi Asistan penceresinde "Yerleşik model — bu pencerede" satırı sohbet panelini açar (sağlayıcı, model, sunucu,
Planla/Uygula, Durdur, Yeni sohbet, Paketi kur). Sağlayıcılar: Ollama (yerel `/api/chat`, `num_ctx` 16384), LM Studio
ve OpenAI uyumlu (`/chat/completions`), Claude (resmi `anthropic` SDK; `claude-opus-5-5`, `output_config.effort`,
`fallbacks: "default"` + `server-side-fallback-2026-07-01`, zorlanmış `tool_choice` yok, thinking blokları yanıtla
aynen geri gönderilir, `refusal` açıkça bildirilir). SDK eklenti ortamına yalnız kullanıcı onayıyla
`python -m pip install anthropic` (argv, `shell=False`, 600 sn) ile kurulur; yoksa satır "anthropic kurulu değil" der.
API anahtarı yalnız ortam değişkeninden okunur, ayara yalnız değişken adı yazılır, hata metinlerinde `***` ile
gizlenir. Araçlar servis üzerinden (`builtin` istemci adı, AJ-7 kaydında görünür) aynı önizle/uygula ve revizyon
kapılarıyla çalışır; Planla modunda `destructiveHint` araçları modele sunulmaz ve çağrılırsa reddedilir; Uygula
modunda `mode=preview` serbest, diğer yazan çağrılar pencerede çözülmüş argümanlar + son önizleme özetiyle onay
ister. Aynı hatalı çağrının 3. tekrarında tur durur; bilinmeyen araç da yanıtlanır (geçmiş geçerli kalır). Yerel
küçük modellere PLAN 5.12 çekirdeğinin bugün var olan araçları + mesajdaki sözcüklerle eşleşen araçlar verilir.

AJ-7 tamamlandı: VS Code yan panelinde "Ajan etkinliği" listesi `GET /events?since=` ile 2 sn'de bir (panel açıkken)
yalnız yeni olayları çeker, son 50'yi gösterir; `blocked` için "kartı kaydedip editörü kapatın", değişiklik için
"Dosya → Geri al (Revert)" talimatı mesaj satırına düşer.

Ölçüm: yeni `tests/test_assistant_model.py` 13 test — gerçek Engine üzerinde Planla modunda yazan araç sunulmaması
ve reddi, Uygula modunda önizlemenin onaysız / uygulamanın onaylı çalışması (ret: dosya bayt eşit kalır; onay:
`R1` değeri `4k7` olur, olaylar `builtin`), aynı hatalı çağrıda 3. tekrarda durma, bilinmeyen araç, küçük araç kümesi;
yerel sahte HTTP sunucusuyla Ollama ve OpenAI protokolü (anahtar yalnız `Authorization` başlığında, gövdede yok);
sahte `anthropic` modülüyle Claude istek biçimi, ham içerik geri gönderimi, paket/anahtar yokluğu, `refusal`; paket
kurulumu argv'si; anahtarın ayar/profil/hata metnine girmemesi. `tests/test_kicad_assistant.py` beş satırlı katalogla
güncellendi. Eklenti `test/sidebar.test.js` etkinlik listesini (yalnız yeni olaylar, iki talimat) ölçer; 7 eklenti testi
geçti. Tam Python takımı (main birleşik) **457 test OK, 5 skip, 1.234,5 sn**; ruff temiz. KiCad 10 Python'u (wx 4.2.2) ile pencere yerleşik model paneliyle kuruldu: dört sağlayıcı, Claude satırında
"anthropic kurulu değil · ANTHROPIC_API_KEY tanımlı değil" ve "Paketi kur" görünür, servis yokken gönderim açık hata.
**Yapılmadı:** gerçek modelle kabul (plan: Ollama ile "R5 değerini oku" + onaylı `set_value`, Claude API ile aynı
senaryo) — bu makinede Ollama/LM Studio çalışmıyor, `ANTHROPIC_API_KEY` yok, `anthropic` kurulu değil; gerçek KiCad
içinde onay penceresi; VS Code panelinde gerçek Claude Code `set_value` olayının 2 sn içinde görünmesi.

## IP — yan panelde işaret silme ve "bitti" (14 Ekim 2026, dal `ip/ip-isaret-paneli`)

IP-1…IP-3 uygulandı ([plan](plan-isaret-paneli.md)). Yalnız görünüm kanalında `set_marker_status` (open/done):
kanıtsız elle "bitti" `closed_by="user"`, `reason="Kullanıcı elle işaretledi"` yazar; `open`'a dönüş bu alanları
temizler; önizle/uygula, `markers_revision`, kontrol noktası, imza ve onaysız işaret reddi aynen. MCP listesinde yok;
ajanın kanıtsız `update_marker_status done` çağrısı hâlâ reddedilir. Yan panel: satırda Bitti/Yeniden aç ve Sil (onaylı),
"Bitenleri gizle" ve "Bitenleri sil" (ilk hatada durur, kaçının silindiğini söyler), `stale_markers`'ta yenileyip
tekrarlamaz. Kart/şematik görünümünde Bitti/Yeniden aç düğmesi. Bitmiş işaretler istemlere girmez (Python + JS, ortak
fikstür `done_excluded`). VS Code eklentisi 0.1.25.

Ölçüm: tam Python takımı **464 test OK, 5 skip, 1.207 sn**; ruff temiz. Eklenti: 7 birim testi geçti (`sidebar.test.js`
yeni işaret adımlarıyla; 12 ortak istem fikstürü), `viewer.e2e.js` (kartta Bitti → Yeniden aç adımı dahil) ve
`sch.e2e.js` geçti (`PCBAI_TEST_PYTHON` = proje `.venv`). `test/dru.test.js` `vscode-textmate` modülü eksik olduğu için
main'de de çalışmıyor. **Yapılmadı:** IP-4 gerçek VS Code + Claude Code elle kabulü.
