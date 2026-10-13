# PcbAi · KiCad (VS Code)

VS Code açılınca etkinleşir; durum çubuğunda servisin durumu görünür. Komutlar (Ctrl+Shift+P → "PcbAi"):

- **Servisi başlat / durdur**: çalışma alanındaki KiCad projelerini kaydederek yerel PcbAi servisini açar.
- **Durum**: kayıtlı oturumlar (çıktı panelinde "PcbAi").
- **ERC ve DRC çalıştır**: kök şematikte ERC, kartta DRC (şematik varsa parite dahil). Kaydedilmiş dosyalar
  denetlenir; sonuçlar konumlarıyla ve kanıt kimliğiyle çıktı panelinde.
- **Şematik PDF**: kök şematiğin PDF'ini üretip açar.
- **Kart önizlemesini aç (3B PNG)**: kayıtlı kartı arka plan işinde render edip VS Code içinde gösterir.
  Birden çok kart varsa belge seçtirir. Güncellemek için komutu tekrar çalıştırın.
- **Kart ölçülerini göster**: gerçek KiCad CLI ile kart genişlik/yükseklik ve footprint sayısı, kanıt kimliğiyle.
- **Otomatik rota / Otomatik yerleşim (önizle)**: kurulu motor ve bütçe seçimi, arka plan işi, önce/sonra
  SVG, ölçü tablosu ve tanı işaretleri. Gösterilen aday aynı revizyonda uygulanır; yeni DRC, artan açık bağlantı,
  kart dışı yerleşim veya yabancı öğe değişimi engeldir. KiCad kapalı olmalıdır; kurulum [ana README](../../README.md)'dedir.
- **MCP'yi bu çalışma alanına ekle**: `.mcp.json`'a `pcbai` kaydı yazar (mevcut dosya bozulmaz, farklı kayıt varsa sorar).

Ayarlar: `pcbai.root` (PcbAi deposu; paketlerken yazılan yol varsayılandır), `pcbai.python`.
PNG önizlemesi betiksizdir. Etkileşimli kart ve işaretler için aşağıdaki Kart 2B komutunu kullanın.
# Etkileşimli görünüm — 0.1.5

Komut paletinden **PcbAi: Kart 2B görünümünü aç**: kayıtlı kartın KiCad katman SVG’lerini açar.
Katmanları açıp kapatın; tekerlekle yakınlaştırın, orta tuş veya Alt+sürüklemeyle kaydırın.
Tıklama öğeyi seçer; çakışan öğeler alt seçim listesinden seçilebilir. **DRC çalıştır** gerçek
bulguları konumlarında gösterir. Görünüm yalnız kaydedilmiş dosyayı okur.

İşaret notunu yazıp Nokta/Çizgi/Alan seçin ve kartı tıklayın; alan için **Alanı bitir** kullanın.
Seçili UUID öğesi için **Seçili öğeye işaret koy** vardır. **Önizlemeyi uygula** kayıt öncesinde
not ve koordinatları gösterir. İşaretler projedeki `pcbai/markers.json` dosyasında kalır; düzenleme
ve silme de önizlemelidir. **Ajana sor** MCP isteğini panoya kopyalar.

Dosya/revizyon değişince panel kendiliğinden yenilenir; katman tercihleri korunur, eski DRC bulguları
temizlenir. G2 şematik görüntüsü, G4 etkileşimli 3B ve G6 KiCad’de seçtirme henüz yoktur.

Geliştirme ortamı:

```powershell
python scripts/install_node.py
. ./scripts/dev-env.ps1
python -m pcbai doctor
node .tools/node/node_modules/npm/bin/npm-cli.js --version
```

Node 22.23.3 `.tools/node` içine SHA-256 doğrulamasıyla kuruludur; sistem PATH’i/registry değişmez.
`dev-env.ps1` yalnız mevcut kabuk için PATH ve `PCBAI_NODE` ayarlar. Servis yolları VS Code
`pcbai.root` / `pcbai.python` ayarları veya `PCBAI_ROOT` / `PCBAI_PYTHON` ortamından gelir.

Kabul betikleri (depo kökünden): `python scripts/spike_svg.py`, `python scripts/test_extension_host.py`,
`node vscode/pcbai-vscode/test/viewer.e2e.js`. Tarayıcı testi için eklenti klasöründe `npm ci --ignore-scripts`
ve `node node_modules/playwright/cli.js install chromium` gerekir. Betikler yalnız izole demo kopyalarını kullanır.

Raporlar varsayılan olarak `.pcbai-state/` altına gider; yayımlanmış kanıtları değiştirmek için Python
betiklerinde `--publish`, tarayıcı betiğinde `PCBAI_PUBLISH_EVIDENCE=1` açıkça seçilir. Junction/hardlink
üzerinden kanıt yazımı reddedilir. Eklenti LGPL-2.1-or-later; vendor MIT lisansları pakette korunur.

# Kural editörü (EK-1)

IR yardımı (EK-2): `*.pcbai-ir.json` ve `*.pcbai.json` dosyalarında
`parts[].symbol`, footprint ve `connections[][]` literal pin değerleri için
tamamlama/hover vardır. Servis açık ve dosya kayıtlı proje kökünde olmalıdır;
yardım kendiliğinden servis başlatmaz. `PcbAi: Yerel parça ara` komutu yerel
sembol/footprint/pin-pad bilgisini salt okunur bir JSON sekmesinde açar.
Footprint önerileri sembolün gerçek Footprint alanıyla sınırlıdır. Stok,
datasheet ve üretim kabulü verilmez. Kısmi JSON yardımcı öneriler alabilir;
bu geçerli veya kaydedilmiş tasarım iddiası değildir. Geniş kütüphane
korpusunda 150 ms performans hedefi henüz karşılanmadı.

Worktree'den paketlerken `build_vsix.py --service-root <.venv içeren depo>`
ile servis kökü seçilebilir; `pcbai.root` / `pcbai.python` ayarları bunu değiştirebilir.

`.kicad_dru` dosyalarında renklendirme, parantez/yorum/folding ve
`pcbai-clearance`, `pcbai-track-width`, `pcbai-via`, `pcbai-keepout`,
`pcbai-length-match` şablonları vardır. Dosyanın başına `(version 1)` ekleyin.
Şablonlar düzenlenebilir örnektir; KiCad kural sözdizimi kontrolü ve üretici
koşulları ayrıca doğrulanmalıdır. Renklendirme bir doğrulayıcı değildir.

