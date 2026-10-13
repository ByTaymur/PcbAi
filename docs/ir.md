# Devre IR v1 ve pasif blok ön denetimi

`plan_circuit` proje dosyası yazmadan devre niyetini inceler. Paketlenmiş
[Draft 2020-12 şeması](../pcbai/ir/circuit.schema.json), gerçek yerel KiCad
sembolleri/padleri ve uygulamanın sabit hesap formülleri kullanılır.
Çıktıdaki `ready_to_apply=false`, `production_verified=false` ve
`stages.electrical=incomplete` bu sürümün sınırıdır. Ön denetim bir ERC,
veri sayfası, stok, STM32 AF, üretim veya fiziksel kart kabulü değildir.

Şema, `jsonschema` çalışma zamanı bağımlılığıyla denetlenir; uzak şema
çözümlemesi kapalıdır. [Validator API](https://python-jsonschema.readthedocs.io/en/stable/validate/).
Nesneler kapalıdır; bilinmeyen alan için yakın ad önerisi döner, girdi otomatik
değiştirilmez. Ek blok kodu, `$ref`, dosya içinden Python veya SPICE ifadeleri çalıştırılmaz.

## Örnek

`plan_circuit` argümanı `{"ir": ...}` biçimindedir:

```json
{
  "ir_version": 1,
  "requirements": {"vin": "9-24 V", "board_mm": [40, 30], "layers": 2},
  "rails": {"GND": {"ground": true}},
  "blocks": [
    {"id": "DIV", "block": "voltage_divider", "params": {
      "vin": "12 V", "r_top": "10k", "r_bottom": "10k", "r_load": "20k"
    }},
    {"id": "RC", "block": "rc_filter", "params": {"r": "10k", "c": "100nF", "type": "lowpass"}}
  ],
  "parts": [],
  "connections": [["DIV.OUT", "RC.IN"], ["DIV.GND", "RC.GND", "@GND"]],
  "constraints": [{"edge": "DIV.R1", "side": "left"}],
  "assumptions": ["12 V ideal kaynak; RC çıkış yükü ayrıca modellenmedi"]
}
```

Bu örnekte bölücünün hesabı yalnız açık `r_load` yükünü içerir. Sonraki RC'nin
frekansa bağlı yükü birleşik devre hesabına katılmaz; blok hesapları bağımsızdır.
`board_mm`, fab/assembly/bütçe ve yerleşim kısıtları niyet verisidir; bu araç
kart boyutunu, üretim koşulunu veya maliyeti ölçmez. `edge` gerçek parça veya
`blok.parça` kimliğine; `around` blok/parça kimliğine başvurmalıdır.

## Başvurular ve netler

- Blok ve serbest parça kimlikleri birlikte benzersizdir; nokta içermez.
  `DIV.OUT` kayıtlı port, `U1.01` gerçek **literal** pin numarasıdır.
  `01`, `1`, `A1` ayrı kimliklerdir. Pin adı/takma adı yerine numara kullanılır.
- `@GND` açık raydır. Rayın `from` kaynağı gerçek `power_out` pin/port olmalıdır;
  kaynak rayın netine otomatik katılır. Başka iki rayı birleştirmek reddedilir.
  `voltage` ve `current_limit` yalnız `caller_declared` veridir, datasheet kabulü vermez.
- Üretilen parçalarda `DIV/R1` gibi ayrı iç kimlikler kullanılır. Port haritaları
  gerçek sembolün seçilmiş birim/ortak pinleriyle kontrol edilir. Footprint varsa
  benzersiz elektrik pin/pad kümesi karşılaştırılır. Kaynak SHA-256 değerleri döner.
- Bloklar içindeki ortak pinlere bağlanan portlar aynı nette toplanır. Kaynak,
  açık bağlantılar ve port iç bağlantıları netin bütün üyelerini belirler.
  Eksik toprak bağlantısı soru; yalnız tek pinli dış arayüz uyarı üretir.
- En çok 64 blok, 150 **genişletilmiş** parça, 64 ray, 1000 bağlantı;
  JSON 1 MiB, 20.000 düğüm ve 16 derinlik sınırındadır. NaN/Infinity, kontrol
  karakteri, JSON dışı değer ve aşırı büyüklük reddedilir.

## SI değerleri ve hesaplar

Sayısal değerler beklenen boyutun temel SI birimindedir: Ω, F, H, V, A, s,
Hz, W, m. Metin `100nF`, `300 mA`, `1 MHz`, `4k7` direnç kodunu destekler.
`m` milli, `M` mega; SPICE'ın `M= milli` kuralı burada kullanılmaz.
Boyut belli olduğunda birimsiz ön ek desteklenir (`10k` direnç = 10.000 Ω).
Uzunluk için `1m` metre, `1mm` milimetredir; boşluklu `1 m` açık metredir.
Karışıklığı önlemek için zaman/gerilim gibi boyutlarda `1ms`, `1mV` yazılır.
Sıfır dışındaki destekli giriş büyüklüğü `1e-24`–`1e30`; formüllerin pozitiflik
ve geçerli alan kontrolleri ayrıca uygulanır. Aralık `9-24 V` veya
`{"min":"9V","max":"24V"}` biçimindedir.

`hand_calc` için `calculation` ve `params` zorunludur:

```json
{"calculation":"rc_filter","params":{"r":"10k","c":"100nF"}}
```

| Hesap | Zorunlu parametreler | İsteğe bağlı |
|---|---|---|
| divider | vin, r_top, r_bottom | r_load |
| rc_filter / button_debounce | r, c | settling_percent (varsayılan 99) |
| led_resistor | vin, vf, current | series (E12/E24) |
| ldo_loss | vin, vout, current | ambient_c **ve** theta_c_per_w |
| opamp_gain | r_feedback, r_ground | gbw |
| crystal_load | load, stray | — |
| e_series | value, dimension | series (E12/E24) |

Çıktı formül sürümü, normalize SI girdileri, birimli sonuçlar, varsayımlar ve
uyarıları içerir. LED hesabı hedef/tercihli direnç ile elde edilen akımı ayrı
yazar. Termal direnç, LED Vf, GBW ve parazit kapasitans kullanıcı varsayımıdır.
Kanıt `.pcbai-state/evidence/` altında özgün girdiyi, ölçüm türünü `calculated`
ve rapor karmasını saklar. `evidence_id` her araç raporunun sayısal sonuçlarını bağlar.

## Bloklar ve kalan kabul

`circuit_blocks` üç yerleşik tarifin sürümünü ve kapalı parametre şemasını döndürür:
`voltage_divider`, `rc_filter` (lowpass/highpass), `button_debounce` (pullup/pulldown).
Varsayılanlar gerçek `Device:R`/`Device:C`, 0603 footprint'lerdir; stok seçimi yoktur.
Debounce tarifinde INPUT/OUT aynı dış kontak düğümüdür; anahtar haricidir.
Pulldown tarifinde SUPPLY portu yoktur. İdeal RC, mekanik kontak sıçramasını doğrulamaz.

Üçü de olgunluk **0**. Genişletilmiş RC değerleriyle gerçek ngspice transient ve
AC kıyası test edilse de tarif başına ERC + SPICE + el hesabı CI kabulü ve fiziksel
ölçüm henüz tamamlanmamıştır. Bu nedenle olgunluk 1/2 verilmez.

Faz 3'ün çoklu alt sayfa `apply_circuit`, kalıcı IR↔UUID/artımlı eşleme, doğrulanmış
gerilim/akım/AF verisi, ilk 11 olgunluk-1 blok ve model kıyası ayrı açık işlerdir.

## Tek dosyada blok yazımı (`add_block`, 0.1.10)

`add_block` bir kayıtlı/paylaşılmayan sayfada tek bir yerleşik pasif tarifi kurar:

```json
{"session":"<oturum>","document":"demo.kicad_sch","revision":"<SHA-256>",
 "mode":"preview","block":"rc_filter","instance":"FILTER1",
 "params":{"r":"10k","c":"100nF","type":"lowpass"},"x_mm":25.4,"y_mm":50.8}
```

Önizlemenin `candidate_id` değeri aynı session/document/revision ile `mode=apply`
çağrısında kullanılır; apply yeni parametre kabul etmez. Açık editör/kilit engeli,
tek checkpoint, atomik yazım ve gerçek kök ERC tekrar denetimi uygulanır.

Semboller, referanslar, UUID'ler ve tüm bağlantı etiketleri tek adayda sabitlenir.
Proje önbelleği korunur; iki görünür passive `1`/`2` pini, birim, pin konum/türleri
ve non-power anlamı uyumsuzsa tarif reddedilir. Aynı kurulu kütüphane dosyasının
iki revizyonu tek adayda karıştırılmaz. Uygulama kütüphaneyi yeniden okuyarak üretmez.
Referanslar bütün yetkili kökte topluca ayrılır; büyük/küçük harf ve leading-zero
yazımlar muhafazakâr biçimde rezerve edilir.

Netler yalnız yerel `PcbAi_<instance>_<port>` adlarıdır; instance ASCII harf/rakam/_
ve en çok 32 karakter. Kullanılmış namespace veya geometri/metin çakışması reddedilir.
Mevcut netler otomatik kullanılmaz. Dış arayüz singleton pinleri gerçek ERC'de
`isolated_pin_label` uyarısı verebilir: RC örneğinde **0 hata, 2 uyarı** saklanır,
`verified=erc_findings` döner. Yeni **hata kimliği** apply'i engeller; yalnız sayım
eşitliği yeterli değildir. `can_apply` dosya yazım kapısıdır, elektriksel/fiziksel kabul değildir.

Native netlist her beklenen netin tam üye kümesini ve ayrı net kimliğini doğrular;
ek/eski pin, eksik pin veya iki netin istem dışı birleşmesi aday üretimini durdurur.
Debounce INPUT/OUT aynı fiziksel net olarak yalnız bir kere etiketlenir.

Yerleşim yatay sütunlarda, dönüş/ayna olmadan, 1,27 mm ızgarada yapılır. Sembol,
pin/etiket ve görünür alanlar sayfaya sığmalıdır. Metin kutuları yaklaşık ve
muhafazakârdır; glyph düzeyinde okunabilirlik kabulü verilmez. `text_box`, tablo,
resim ve desteklenmeyen kök çizim öğeleri `unsupported_layout` ile reddedilir.
Bu sınırlı tarif yazıcısı çoklu alt sayfa compiler, kalıcı eşleme veya artımlı IR apply değildir.

## Pasif tarif simülasyonu (`spice_block_test`)

`block` ve `params` alır; oturum veya kullanıcı şematiği gerekmez. Örnek:

```json
{"block":"rc_filter","params":{"r":"10k","c":"100nF","type":"highpass"}}
```

Yerleşik tarifin gerçek pin grupları ideal R/C netlistine çevrilir. Bölücü için DC
çıkış gerilimi ve kaynak akımı; RC için kesimde genlik ve faz; debounce için 0,25/0,5/1/2/4
zaman sabitindeki ideal şarj/deşarj yanıtı gerçek ngspice ile ölçülür. El hesabı aynı
normalize girdileri kullanır. Her ölçüm beklenen değer, birim, hata, tolerans ve `passed`
ile döner; fark varsa `passed=false`, `verified=simulation_mismatch` korunur.

Tolerans yüzde 1; sıfır yakınında gerilim/genlik/faz için mutlak 1e-9, akım/frekans
için 1e-15 tabanı vardır. Desteklenen R: 1e-3–1e12 Ω, C: 1e-15–1 F, RC: 1e-12–1e6 s,
kaynak büyüklüğü en çok 1 MV. Aralık dışı girdiler simülatörden önce reddedilir.
Kullanıcı metni SPICE satırına kopyalanmaz; yalnız doğrulanmış sayılar kullanılır.
Koşu özel geçici klasörde, ayrı süreçte en çok 60 saniye sürer.
Sıfır veya çok küçük kaynak denemesinde mutlak tolerans baskındır; böyle bir koşu tek
başına tarif topolojisinin yeterli uyarıldığına dair kabul değildir.

Özgün girdiler, tarif/testbench sürümü, netlist SHA-256 ve `source=simulated` ölçümler
kanıta kaydedilir. Bu araç ideal tarif topolojisini sınar; kullanıcının şematiğini,
parça modelini veya gerçek anahtar sekmesini doğrulamaz. `erc_verified`, `stock_verified`
ve `physically_verified` false kalır; tarif olgunluğu 0. Olgunluk 1 kabulü ayrıca
tarif ERC/CI ve diğer plan kapılarının tamamlanmasını gerektirir.
