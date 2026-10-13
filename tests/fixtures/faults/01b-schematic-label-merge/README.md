# #1b — Şematik etiketleri niyette ayrı iki neti birleştiriyor

KiCad projesi: 15×10 mm kart, iki tek-pin konnektör, iki pad ve tek 0.25 mm iz.
Şematikte birbirine tel ile bağlanmayan J1.1 ve J2.1, aynı sayfada aynı `SENSE` yerel
etiketini taşır. KiCad bu pinleri tek `/SENSE` netine birleştirir. PCB iki padı aynı
nete atar ve iz ile birleştirir; şematikle tutarlıdır. #1 fixture'ından türetilmiştir.

`intent.json`, tasarım niyetini iki **ayrı** net olarak kaydeder:
`/SENSE_A=[J1.1]`, `/SENSE_B=[J2.1]`. JSON veridir, yürütülecek kod değildir.
Niyet adlarını şematiğe ikinci etiket olarak eklemek bu vakayı değiştireceğinden yapılmaz.
Exclusion, severity ignore veya özel DRC kuralı kullanılmaz.

13 Ekim 2026, PcbAi 0.1.14 / gerçek KiCad CLI 10.0.4 ölçümü:

- Normal DRC ve parite: `ok=true`, `verified=drc_ok`, **0 hata, 0 uyarı**, bulgu listesi boş.
- Native KiCad netlisti: `/SENSE=[J1.1, J2.1]`; niyetteki iki ayrı üye kümesiyle uyuşmuyor.
- Kaynak fixture SHA-256 haritası koşu öncesi/sonrası eşit.

Yakalaması gereken: **RD-C2 `netlist_assert` + IR niyet kıyası**. Bugünkü PcbAi
DRC/paritesi bu niyet dosyasını tüketmez; hiçbir mevcut araç bu niyet ihlalini yakalamaz.
`tests.test_fault_fixtures.FaultFixtureTests.test_01b_parity_clean_but_intent_violated`
normal DRC ve paritenin sıfır bulguyla dönmesini, native netlistte iki pinin tek
net olmasını ve niyette iki ayrı net bulunmasını sabitler. Testin geçmesi, ürünün
kusuru yakaladığı anlamına gelmez: bu **bilinen kaçaktır** (RD-A5: `L-NO-INTENT-CHECK`).

Yeniden ölç: depo kökünde
`.\.venv\Scripts\python.exe -m unittest tests.test_fault_fixtures -v`.
Testler özel geçici kopyada çalışır; kaynak fixture SHA-256 haritasının önce/sonra
eşitliği doğrulanır. KiCad CLI yoksa testler açıkça skip edilir.
