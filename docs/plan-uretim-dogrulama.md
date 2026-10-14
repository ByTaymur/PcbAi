# Plan — yedi referans depoyla tasarım, simülasyon ve üretim doğrulaması

Tarih: 13 Ekim 2026 · Güncelleme: 14 Ekim · Durum: **U0 ilk kaynak/komut ölçümü tamam; ürün entegrasyonu açık**

Dal: `ip/uretim-dogrulama-plani`

Ürün hedefi: [PLAN.md](../PLAN.md) · Uygulama: [status.md](status.md)
Bağlı planlar: [referans depolar](plan-referans-depolar.md), [kalan işler](plan-eksikler.md),
[rota/yerleşim](plan-rota-yerlesim.md), [dalga 1](plan-rd-dalga1.md).

U0 ölçümü: [U0.md](spikes/U0.md). İlgili ikinci plan: [R2](plan-referans-depolar-2.md).
Beş kaynak CLI çalıştı; eSim/Hauksbee runtime deneyi açık. R2-A1 ignored kural kapısı
0.1.23'te uygulandı; [rapor](spikes/R2-A1.md). R2-A2 süreli/görünür bulgu muafiyeti
0.1.24'te uygulandı; [rapor](spikes/R2-A2.md). Üretim/BOM/CPL adaptörleri açık kalır.

## 1. Hedef ve kapsam kararı

Kullanıcının isteği: aşağıdaki yedi deponun PcbAi ürün hedefini kapsayan bütün ilgili işlevlerini
geliştirme kapsamına almak. İlk teslim kapsamlı Markdown planıdır. Kod entegrasyonu sonraki iş paketleridir.

Hedef yalnız mevcut kartı denetlemek değildir: gereksinim → kontrollü tasarım → bağımsız denetim → düzeltme →
yeniden denetim → izlenebilir üretim paketi döngüsüdür. Mevcut kartın salt okunur denetimi bu sistemin ilk
çalışabilir kesitidir. Yeni plan PLAN.md'nin veya RD planının yerine geçmez; RD-C1/C2/C3, RD-D ve
İP-4/5/7 paketlerinin uygulama seçeneklerini ve kabul ölçütlerini ayrıntılandırır.

**Kapsama almak, yedi uygulamayı bütünüyle kopyalamak veya aynı kontrolleri yedi kez çalıştırmak değildir.**
Her ilgili özellik için bir iş paketi, ana uygulama yolu, bağımsız kıyas ve ölçülen kabul sonucu gerekir.
Lisansı, uyumluluğu veya doğruluğu kabul edilmemiş araç için işlev kapsamda kalır; entegrasyon yöntemi
ayrı süreç, özgün uygulama veya ertelenmiş araştırma olabilir.

## 2. Mevcut başlangıç: yeniden yazılmayacak altyapı

Bu tablo yerel kod ve status.md incelemesidir; bu çalışma yeni çalışma zamanı kabulü vermez.

| Alan | Bugün bulunan | Bu planın ekleyeceği |
|---|---|---|
| Güvenli düzenleme | Hedef oturum/belge/revizyon, önizlenen aday, checkpoint, yazım sonrası geri okuma | Harici araçları aynı sözleşmeye bağlamak |
| ERC/DRC/parite | `pcbai/tools/engine.py` içindeki `check`; ortak bulgular ve `checks_run` | Üretim ve simülasyon kontrol kapsamını açık profillerle genişletmek |
| Üretim dışa aktarımı | `pcbai/kicad/exports.py`: kopyada Gerber/Excellon, hash manifesti; `production_verified=False` | BOM/CPL, bağımsız çıktı denetimi ve ayrı yayın kapısı |
| Simülasyon | `pcbai/sim/runner.py`, ayrı ngspice worker; üç pasif tarif/altı varyantın ideal SPICE testleri | Gerçek model, tolerans/köşe, güç katı ve sınırlı sistem doğrulaması |
| Parça | Yerel KiCad indeksi, yapısal pin/pad doğrulaması, IR ön denetimi | Envanter/MPN/SKU, datasheet, stok, varyant ve model kimliği |
| Bağımsız analiz | RD-A ortak şema/limit/kanıt çatısı; kicad-happy adaptörü ve kalibrasyon | Yeni motorları aynı giriş kimliği ve hata kataloğuyla kıyaslamak |

Mevcut `verification()` zorunlu kontrollerde yalnız `ran` kabul eder; `skipped`, `failed` ve
`not_applicable` zorunlu kontrolde `checks_incomplete` verir. Bu davranış yanlışlıkla gevşetilmez.
Uygulanmayan kontroller, sürümlü profil oluşturulurken gerekçesiyle zorunlu kümenin dışında belirlenir.
Koşu sırasında başarısız kontrolü sonradan isteğe bağlıya çevirmek yasaktır.

## 3. Yedi deponun rolü ve kanıt düzeyi

13 Ekim'de aşağıdaki birincil depo belgeleri web üzerinden incelendi. Bunlar **upstream belge beyanıdır**;
plan hazırlanırken depolar kurulmadı ve entegrasyon testleri çalıştırılmadı.
14 Ekim U0 kaynak/komut ölçümleri bu başlangıç incelemesini ilerletti; sonuç ve açık kapsam U0.md içindedir.

| Depo | Belgelerde bulunan ilgili işlevler | PcbAi'de önerilen rol ve sınır |
|---|---|---|
| [jBOM](https://github.com/plocher/jBOM) | Envanteri devre tasarımından ayırma; parça eşleme; BOM/yerleşim çıktıları; alan ve datasheet kaynak denetimi; annotate | Öncelikli BOM motoru. Otomatik eşleşme parça onayı sayılmaz. Annotate sadece kopyada aday üretir; kaynak yazımı PcbAi üzerinden yapılır. |
| [KiCad-BOM-CPL-Plugin](https://github.com/prrvchr/KiCad-BOM-CPL-Plugin) | Manufacturer/PartNumber/Supplier/SupplierRef alanları; tedarikçiye göre BOM gruplama; adet; position CSV'den JLC CPL ve Rotation düzeltmesi | Alan eşleme ve tedarikçi şablonları için kıyas. Belgelenmiş test KiCad 5.1.5/Ubuntu; güncel uyumluluk kanıtlanmamış. Kullanım koşulları ayrıca incelenir. |
| [pcb-dfm](https://github.com/mfgs-us/pcb-dfm) | Gerber ZIP; Gerber/Excellon; JSON kuralları; DFM raporu; CLI. U0 kaynak okumasında doğrudan KiCad girişi de doğrulandı | Gerçek üretim ZIP'i ana otorite; KiCad'den CLI veya native renderer ile ZIP üretimi ayrı kıyas. Skor/exit zorunlu kontrol kapsamını kanıtlamaz. |
| [KiCad-Astra](https://github.com/NextBuilder/KiCad-Astra) | Kart yakalama/kısıtlar; yerleşim önerisi; sınırlı yerel rota; referans yazısı düzenleme; DRC farkı; kopyada sıkı üretim denetimi ve hashli çıktı | Üretim kapısı ve yerleşim/finishing kıyası. Aynı KiCad DRC bağımsız fizik motoru sayılmaz. Çıktı `exported_for_review`; `assembly_ready=false`, doğrulanmış BOM/MPN üretmez. |
| [eSim](https://github.com/FOSSEE/eSim) | KiCad→ngspice dönüşümü; DC/AC/transient; model/subcircuit; dalga çizimi; NGHDL ve Verilog karma sinyal akışları | Mevcut ngspice motorunu geliştirecek model/testbench ve dönüşüm kıyası. Ayrı GUI zorunlu olmayacak; model dağıtım hakları ayrı incelenir. |
| [Hauksbee](https://github.com/hauksbee-dev/hauksbee) | Tasarım/üretim/montaj/firmware girdilerini ilişkilendirme; model kapsamı; analog ve termal tahminler; seçili MCU backend'leri; tekrar üretilebilir manifest | Araştırma ardından desteklenen kartlarda sistem doğrulaması. Tam STM32 desteği varsayılmaz; GPIO/PWM/ADC/periferik kapsamı chip ve backend bazında ölçülür. |
| [pcb-inspector](https://github.com/takzen/pcb-inspector) | ERC/DRC; dekuplaj, güç izi, diferansiyel skew, anahtarlama döngüsü ve dönüş yolu sezgiselleri; CLI/MCP/HTML; görsel AI incelemesi | Mevcut analiz motoruna bağımsız kıyas ve eksik dedektör adayı. Sezgisel/görsel bulgu ölçülmüş EMC uygunluğu değildir. Ağlı görsel analiz ayrı tercih olur. |

Depo düzeyinde görülen lisans etiketleri: jBOM, Astra ve pcb-inspector MIT; pcb-dfm ve Hauksbee Apache-2.0.
Bu etiketler alt bağımlılık/model haklarını doğrulamaz. U0 kaynak LICENSE okuması eSim GPL-3.0,
BOM-CPL-Plugin MPL-2.0 olduğunu doğruladı; R2 kuralları uyarınca kod/model paketlenmez.
Hauksbee varsayılan binary GPL-3.0, permissive binary Apache-2.0 olduğundan dağıtım biçimi ayrıca doğrulanır.

## 4. Mimari: tek proje kimliği, ayrı kontrol motorları

```text
Gereksinim + KiCad projesi + montaj varyantı + üretici profili
                         |
       PcbAi oturumu / SHA-256 proje görüntüsü
                         |
  Tasarım önerisi → aday → önizleme → kontrol → checkpoint → uygula
                         |
   +---------------------+-----------------------+
   |                     |                       |
KiCad ERC/DRC      Parça + BOM/CPL          Devre davranışı
parite/döküm       jBOM/şablonlar           ngspice + modeller
   |                     |                       |
   +------------ Gerber / Excellon ---------------+
                         |
  Bağımsız üretim denetimi + BOM/CPL uzlaştırma
  pcb-dfm / RD-C2 + ikinci parser / Astra kıyası
                         |
  Model kapsamı + desteklenen firmware (Hauksbee)
  Bağımsız layout denetimi (pcb-inspector / RD-B)
                         |
  checks_run + bulgular + kanıtlar → üretim kapısı
                         |
  Mühendis incelemesi → aynı manifestte onay → yayın paketi
```

Şema/PCB, hiyerarşi, kütüphaneler, `.kicad_pro/.kicad_dru`, envanter, DNP varyantı, stackup,
üretici kuralları, modeller ve firmware ayrı hashlenir. Paket tek belge hashine bağlanmaz.
Çıktıların kaynak görüntüsüyle bağı koparsa sonuç `stale_revision` olur.

Yeni analiz adaptörleri `pcbai/verify/adapters/` çatısını; üretim modülleri PLAN'daki `pcbai/fab/` alanını;
simülasyon işleri `pcbai/sim/` alanını kullanır. Araç başına ayrı orkestratör veya paralel proje modeli kurulmaz.

## 5. Ortak sonuç ve çalıştırma sözleşmesi

Her adaptörün girdisi: session/document/revision, profil ve varyant kimliği, doğrulanmış proje kopyası,
zaman/çıktı bütçesi ve izin verilen veri yolları. Çıktısı:

- Kontrol kimliği, required durumu, `ran/skipped/failed/not_applicable` ve gerekçe.
- Araç sürümü/commit'i, girdi/çıktı SHA-256'ları, profil/model hashleri, süre, çıkış kodu.
- Ortak finding kimliği; dosya/UUID/RefDes/net/koordinat; severity; kural kaynağı.
- Ölçüm değeri/birimi/eşik, veri kaynağı ve varsayımlar; kanıt dosyası veya evidence_id.
- Desteklenmeyen nesne/katman/model/periferik ve kapsama etkisi.

`ran` yalnız aracın çalıştığını söyler; başarılı mühendislik sonucu bulgular ve ölçüm eşikleriyle belirlenir.
Boş/bozuk JSON, çökme, timeout, bilinmeyen format ve eksik çıktı temiz rapora dönüştürülmez.
Deterministik, sezgisel, datasheet destekli, simüle edilmiş ve fiziksel ölçüm kanıtları ayrı etiketlenir.

Programlar yalnız yapılandırma/ortam/PATH üzerinden bulunur. `shell=False`, timeout, süreç ağacı sonlandırma,
çıktı boyut sınırı ve bağımlılık izolasyonu gerekir. Harici programlar salt okunur kaynak yerine çalışma
kopyasına erişir; KiCad kullanıcı ayarlarını kullanmak zorundaysa yalıtılmış profil hazırlanır.
ZIP path traversal, symlink/junction, dış model/include, aşırı açılan arşiv ve uzak şema erişimi engellenir.
Model dosyası/yapılandırma/kullanıcı metni kod olarak yürütülmez. Mevcut SPICE direktif izin listesi korunur.

## 6. Uygulama paketleri ve kabul ölçütleri

### U0 — Yedi depo için kaynak envanteri ve küçük deneyler

**Bağ:** RD dalga 0 yöntemi, lisans kararları. **Bağımlılık:** yok.

Her deponun sabit commit'i, LICENSE/NOTICE, bağımlılık/model lisansları, destek matrisi, gerçek CLI/API,
şema sürümleri, dış ağ ve yazım davranışı kaynakta incelenir. İlgili işlevlerin tam listesi çıkarılır:
her işlev için U1–U8'e eşleme veya gerekçeli kapsam dışı satırı bulunmalıdır. README ve kaynak bulgusu ayrılır.
Yalıtılmış ortamda temiz ve hatalı fixture ile smoke test yapılır; kullanıcı kartına/ayarına dokunulmaz.

**Teslim:** `docs/spikes/U0.md`, depo/özellik matrisi ve sabitleme kaydı. Geliştirme ham çıktıları
`.pcbai-state/uretim-dogrulama/u0/` altında. Yayın result.json'u sadece açık yayın koşusunda yazılır.
**Kabul:** yedi deponun her biri için çalıştı/çalışmadı/uyumsuz sonucu, gerçek komut/exit ve yeniden üretim
adımları; seçilen entegrasyon yolu. Çalışmayan araç uygulanmış özellik diye işaretlenmez.

- [x] İlk sabit kaynak/CLI değerlendirmesi ve bağımsız smoke: [U0 sonucu](spikes/U0.md).
- [ ] eSim/Hauksbee runtime, transitif/model lisans kabulü ve U3/U5 dedektör kalibrasyonu sonraki paketlerde açık.

### U1 — BOM normalizasyonu, envanter ve parça seçimi

**Bağ:** RD-C3, RD-D4/D5, İP-2.5/2.7/5.11. **Bağımlılık:** U0.

jBOM öncelikli adaptör; BOM-CPL-Plugin alanları alternatif içe alma eşlemesidir. Ortak kayıt:
RefDes/UUID/sheet path, değer, footprint, üretici, MPN, tedarikçi/SKU, miktar, tolerans,
gerilim/güç sınıfı, datasheet kaynağı, DNP/varyant ve doğrulama tarihi.
MPN ile SKU ayrı tutulur; aynı değer+footprint elektriksel eşdeğerlik için yeterli sayılmaz.
Parça eşleşmesi aday üretir; datasheet/pin/rating denetimi ve stok kaynağı ayrı kapılardır.

Satın alma BOM'u ile montaj BOM'u ayrı çıkarılır. Alternatif parça, çoklu tedarikçi, maliyet ve
çok kartlık adet hesabı desteklenir. Stok/fiyat zaman damgalı kanıttır; ağsız eski kayıt güncel stok sayılmaz.
Annotate/alan onarımı mevcut preview/apply üzerinden geçer.

**Kabul:** eksik/çelişkili MPN, yinelenen RefDes, farklı rating'li aynı değer, yanlış footprint,
varyant/DNP, 1/10 kart adedi, tedarikçi değiştirme ve stok bilinmiyor fixture'ları beklenen sonucu verir.
Her BOM satırı kaynak bileşen kümesine geri izlenir; kritik bilinmeyen alan sessizce doldurulmaz.

### U2 — CPL/POS ve tedarikçi şablonları

**Bağ:** RD-C3, İP-5.11. **Bağımlılık:** U1.

Kaydedilmiş aynı revizyondan KiCad position çıktısı alınır. jBOM ve BOM-CPL-Plugin ile koordinat/dönüş kıyası
yapılır. Birim, origin, üst/alt yüz, açı yönü, pin-1 ve tedarikçi rotation offset'i açık profil alanlarıdır.
JLC ilk şablondur; LCSC satın alma BOM'u ve genel tedarikçi BOM'u ayrı formatlardır.
Diğer üretici şablonu gerçek format fixture'ı geldikçe eklenir.

**Kabul:** asimetrik/polarize footprint, 0/90/180/270°, negatif koordinat, farklı origin ve iki yüz fixture'ı;
beklenen fiziksel pad/pin-1 konumu ile ölçülen kıyas. DNP hariç montaj RefDes kümesi ve izin verilen
THT/elle montaj ayrımları BOM/CPL arasında eşittir. Fazladan/eksik referans önce bulgu olur; sessiz ayıklanmaz.
CSV escaping, duplicate, NaN ve mm/inch uyuşmazlığı reddedilir. Portal kabulü ayrıca ve ölçülerek kaydedilir.

### U3 — Gerber/Excellon bağımsız DFM

**Bağ:** RD-C2/RD-I2, İP-5.3/5.11. **Bağımlılık:** U0; yayın için U2.

pcb-dfm gerçek çıktı ZIP'ini inceler; RD-C2 ve ikinci parser ile geometri/format kıyası yapılır.
Katman sırası/kimliği, birim, dışhat/cutout, PTH/NPTH/slot, bakır genişlik/aralık/kenar,
annular ring, maske açıklığı/web ve silk kontrolleri kaynakta desteklenme durumuyla envantere girer.
Profil: üretici/proses/katman/kalınlık/bakır ağırlığı, min/max değerler, kaynak tarihi ve sürüm.
Desteklenmeyen plated slot veya aperture macro varsa tam DFM geçti denmez.

U0 bulgusu gereği toplam score/exit 0 yeterli değildir: profilin her zorunlu check_id'si JSON'da
tekil, bilinen statülü ve uygulanmış olmalıdır. Eksik/bilinmeyen/N/A zorunlu kontrol incomplete verir;
pcb-dfm CLI'sinde `--must-pass` varsayılmaz.

Gerber geometri denetimi ile elektriksel niyet denetimi ayrıdır. Kaynak net haritası, pad uzlaştırma,
IPC-D-356 gibi bağlantı kanıtı ve must-connect/must-not-connect şartları eksikse DFM skoru kısa devre
olmadığını kanıtlamaz. Profil eşikleri üretici verisinden alınır; varsayılan değerler evrensel limit olmaz.

**Kabul:** temiz 2/4 katman; eksik/yanlış katman; açık dışhat; kaymış drill; dar iz/maske köprüsü;
kenara yakın bakır; bozuk/zararlı ZIP; desteklenmeyen primitive fixture'ları. Bilinen boyut/delik sayımı ve
iki parser sonucu karşılaştırılır; farklar kabul toleransı ve nedenleriyle kaydedilir. RD-G2 kısa/niyet
fixture'ları net uzlaştırma bölümünde yakalanır; Gerber'dan net adının tahmin edilmesi kabul edilmez.

### U4 — Tasarım kabulü, sıkı üretim kapısı ve yayın

**Bağ:** RD-C1, İP-5.11/7.1. **Bağımlılık:** U1–U3 ve gerekli parça denetimleri.

Astra'nın kopyada kuralları/dökümleri denetleme yaklaşımı mevcut PcbAi mekanizmasıyla kıyaslanır.
İncremental düzenlemede yeni hata yaratmama ile üretimde sıfır bloklayıcı hata iki ayrı politikadır.
Üretim profili zorunlu ERC, DRC, parite, rota tamamlığı, BOM/CPL, DFM, bağımsız çıktı kontrolü ve
tasarıma ait davranış gereksinimlerini tanımlar. Bastırılmış/ignored kontroller ve istisnalar görünür kalır.

Paket durumu önerisi: `draft`, `blocked`, `review_ready`, `approved`, `released`.
`review_ready` yalnız profil kapsamındaki denetimler tamam ve bloklayıcı bulgu yok demektir.
Mühendis onayı belirli manifest hashine, varyanta, profile ve çıktı hashlerine bağlıdır; girdi/çıktı
değişikliği onayı geçersiz kılar. İstisna kural/bulgu kimliği, gerekçe, yetkili kişi, kapsam ve süre taşır.
Eksik kontrol veya bilinmeyen model istisna üzerinden başarılı ölçüm gibi sunulmaz.

`export_fab` mevcut taslak çıktı davranışı korunarak geliştirilir; üretime onaylı yayın ayrı kapıdan geçer.
ZIP: Gerber/drill, BOM/CPL, şematik PDF, montaj belgeleri, rapor, profil/araç sürümleri ve SHA manifesti.
Paste/stencil, etiket, polarite ve montaj varyantı gereklilikleri profil bazında değerlendirilir.

**Kabul:** her zorunlu kontrolü tek tek eksiltme/çökertme/bozma yayın kapısını kapatır;
temiz fixture review_ready olur; onaydan sonra tek bayt değişikliği yayın reddi verir.
Başarısız rapor alınabilir; üretime onaylı paket çıkarılamaz. Otomatik sipariş bu planın kapsamı dışındadır.

### U5 — Bağımsız tasarım ve EMC/EMI ön denetimi

**Bağ:** RD-B/RD-G2, İP-5.3/7.1. **Bağımlılık:** U0 ve mevcut analiz kalibrasyonu.

pcb-inspector dedektörleri kicad-happy ve KiCad kaynak verisiyle kıyaslanır: dekuplaj mesafesi,
güç izi, diferansiyel skew, anahtarlama döngüsü ve GND dönüş yolu. Aynı KiCad CLI çağrısının tekrarı
bağımsız algoritma kanıtı sayılmaz. U0'da bulunan diğer ilgili kurallar da aynı matrise eklenir.
Net adı tek başına işlev belirlemez; pin rolü, topoloji, stackup ve kullanıcı gereksinimi kullanılır.

U0'da PCB'siz şematik analyze için yanlış temiz sonuç ölçüldü. Adaptör PCB/net/stackup ön koşullarını
ve kural kapsamını kendisi doğrular; upstream `executed/passed` etiketi tek başına kabul değildir.

PcbAi'ye özgü ek kapsam: gate-driver yakınlığı, yüksek di/dt döngüsü, analog ölçüm dönüşü,
SW node kuplajı, USB/CAN/ADC hassas bölge ve datasheet kaynaklı mesafe/yerleşim gereksinimleri.
Bunlar kaynakta varmış gibi sunulmaz; eksikse özgün dedektör işi açılır.
AI görsel incelemesi yalnız yardımcı bulgu üretir; görüntü/ağ paylaşımı açık tercih ve bağımsız kanıt gerektirir.

**Kabul:** her dedektör için pozitif/negatif/karşı örnek; uzman etiketli doğru/yanlış/belirsiz sonuç tablosu;
objeye/koordinata geri izlenebilir bulgu. GND yüzdesi, loop alanı veya mesafe sonucu EMC uygunluk
belgesi değildir. Nihai EMC/EMI kabulü seçilen ürüne/standarda göre fiziksel ön uyumluluk/laboratuvar ölçümüdür.

### U6 — Devre davranışı, modeller ve güç katı

**Bağ:** İP-3.3/4.1–4.3, RD-D. **Bağımlılık:** U0 ve mevcut ngspice güvenliği.

eSim'den uygun dönüşüm/model/testbench yaklaşımları alınır; PcbAi'nin ngspice worker'ı ana motor kalır.
DC/op, transient, AC, sweep ve tolerans/köşe testleri; modeli olmayan bileşen için açık kapsam eksikliği.
Model kimliği/pin sırası/birimler/datasheet şartları hashli kayıtla tutulur. Mevcut ideal tarif kıyası ile
karttaki gerçek şemadan çıkarılmış devre simülasyonu ayrı sonuçlardır.

Önce RC/bölücü → LDO/op-amp/filtre → MOSFET/gate-driver → buck ve akım ölçümü.
Güç katında başlangıç/yük adımı, ripple, UVLO, gate gerilimi, deadtime, çapraz iletim, bootstrap,
shunt/amplifier doygunluğu ve örnekleme penceresi tasarım gereksinimine göre ölçülür.
NGHDL/Verilog ortak simülasyonu ancak gerekli blok ve lisans/backend kanıtı varsa ayrı alt paket olur.

**Kabul:** ideal testlerde el hesabı kıyası; gerçek model testlerinde datasheet deney koşulu/referans dalga;
eşikler testten önce belirlenir. Model yok, yakınsamama, ölçüm yok, NaN, timeout ve yanlış pin eşleme
geçmez. Güç devresi sonuçları daha sonra osiloskop/yük/sıcaklık ölçümleriyle kıyaslanır.

### U7 — STM32 ve sistem doğrulaması

**Bağ:** İP-3.4/7.2/7.3; U6 davranış kanıtları. **Bağımlılık:** U0, parça/model kimliği ve U6.

Hauksbee model kapsamı ve board/BOM/CPL/firmware ilişkilendirmesi ayrı adaptör olarak denenir.
STM32F103/F429 ve PLAN P3/IR hedefindeki STM32G431CBU6 için MCU/package, firmware SHA, backend sürümü, clock/pin/AF/periferik
matrisi çıkarılır. Desteklenmeyen hedef veya TIM/PWM/ADC/DMA/interrupt yolu için açık ret/kapsam eksikliği.
Hauksbee dışındaki modeller de aynı kimlik/pin sözleşmesine tabidir.

Ölçülecek sistem senaryoları: reset/boot/SWD, güç açılışı, GPIO/UART/CAN/I2C/SPI ihtiyacı,
PWM–ADC zaman ilişkisi, gate-driver enable/fault ve brownout. Hangi periferik gerçekten register
seviyesinde modelleniyor, hangisi davranışsal veya desteklenmiyor raporda ayrı gösterilir.
Statik pin/AF kontrolü simülasyonun yerine geçmez; simülatör firmware kabulü fiziksel kart kabulü değildir.

**Kabul:** desteklenen küçük firmware'de beklenen gözlemler; yanlış pin/model/varyant, eksik periferik
ve firmware değişikliği olumsuz fixture'ları; manifestten yeniden üretim.
Fiziksel aşamada SWD ve scope/logic analyzer ile PWM/deadtime, ADC tetik, fault ve brownout ölçülür.
Tam hedef desteklenmiyorsa statik ve desteklenen alt sistem raporu verilir; bütün firmware geçti denmez.

### U8 — Yerleşim/rota/finishing ve agent döngüsü

**Bağ:** İP-5, rota/yerleşim planı R4–R9, RD-F, İP-6/7. **Bağımlılık:** U0; yayın için U4.

Astra'nın yakalama, kısıt, yerleşim, sınırlı rota, referans yazısı ve işlem yaklaşımı mevcut motorlarla
kıyaslanır. Kilitli/elle rotalanmış/hassas nesneler, keepout, konektör bölgeleri ve net sınıfları korunur.
Eksik faydalı finishing işlevleri eklenir; rota motorları ölçüm olmadan değiştirilmez.
CLI/MCP ve mevcut VS Code paneli bulgu/evidence_id üzerinden aynı sonuçları gösterir.

Agent döngüsü: öner → preview → denetle → uygula → geri oku → bağımsız denetle.
Süre/deneme bütçesi ve durma gerekçesi görünür olur; ajanın kendi raporu bağımsız kontrol yerine geçmez.
**Kabul:** kilit/UUID/net/katman korunumu; yeni DRC retleri; etiket çakışması/okunurluk;
aynı revizyon aday uygulaması ve bayt eşit restore. Eklenti değişirse kendi sürümü artırılır.

## 7. Sıra, bağımlılıklar ve tahmin

| Dalga | İş | Çıkış koşulu | İlk planlama tahmini |
|---|---|---|---|
| 0 | U0, yedi depo kaynak/CLI deneyleri | Tam özellik matrisi ve entegrasyon kararları | 3–5 uygulayan iş günü |
| 1 | U1 + U2 | İzlenebilir satın alma/montaj BOM ve ölçülmüş CPL | 5–8 gün |
| 2 | U3 → U4 | Gerçek ZIP denetimi ve revizyona bağlı yayın kapısı | 8–12 gün |
| 3 | U5 + U8 | Bağımsız tasarım denetimi ve kontrollü finishing | 5–10 gün |
| 4 | U6 | Gerçek model/testbench ve gereksinim ölçümleri | 8–15 gün |
| 5 | U7 + fiziksel/EMC ölçüm hazırlığı | Hedef/backend kapsamı ve fiziksel kabul planı | U0 sonucunda tahminlenecek |

Tahminler taahhüt değildir; mevcut RD/PLAN işlerinin yerine gelen süreler iki kez sayılmaz.
U0 sonrasında RD-C1/C2/C3'ün eski toplamı ve bu tahminler birlikte yeniden hesaplanır.
Model lisansı, STM32 periferik kapsamı ve üretici kuralları takvim bağımlılığıdır.
Tam U7 desteği bulunamasa da U1–U4 üretim verisi kontrol altyapısı teslim edilebilir; davranış gereksinimi
eksik tasarım üretim kapısında yine blocked kalır.

## 8. Denetim, kanıt ve iş paketi bitişi

Bir uygulayan ajan, ayrı `ip/uN-*` dalı; bağımsız denetçi kod yazmaz, ölçümleri kendisi tekrarlar.
İkinci yazıcı gerekiyorsa ayrı worktree. Denetçi bulgusu dosya/satır, fixture, komut ve beklenen/gerçek sonuç içerir.
Her paket status.md ve plan-eksikler.md kaydıyla ve anlamlı commit ile biter.

Uygulama değişikliklerinde proje ortamı kullanılır:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m unittest tests.test_kicad_integration -v
.\.venv\Scripts\python.exe -m pcbai doctor
```

Hedefli adaptör/motor/model testleri bu komutlara eklenir; KiCad/araç yoksa gerekçeli skip,
zorunlu mühendislik kontrolde incomplete. Yayın kanıtları `docs/spikes/*-result.json` yalnız açık yayın
koşusunda yazılır; geliştirme/denetim `.pcbai-state/` altında kalır.

**Bu planın bitiş ölçütü:** yedi deponun rolleri, mevcut kodla bağlantıları, U0–U8 işleri,
bağımlılıklar, kabul ölçütleri ve kanıt sınırları belgeli; yerel bağlantılar ve diff denetlenmiş.
**Entegrasyonun bitiş ölçütü:** sabitlenmiş araçlarla ilgili olumlu/olumsuz fixture'lar,
gerçek CLI/simülasyon ölçümleri ve bağımsız denetim tamam; ürün/fiziksel/EMC kabulü ayrıca kaydedilmiş.
