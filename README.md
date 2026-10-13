# PcbAi

KiCad projesini yapay zekâ ajanlarına yerel MCP araçlarıyla açan Python çekirdeği.
Mevcut çekirdek **0.1.14**, VS Code eklentisi **0.1.16**: kayıtlı şematik/kart ve salt okunur canlı PCB, gerçek ERC/DRC,
PDF/PNG, PCB ölçümleri, temel Gerber/delik ZIP, arka plan işleri, önizlemeli değer değişikliği,
checkpoint ve geri yükleme; etkileşimli kart katmanları, seçim ve kalıcı PCB işaretleri. [Ürün planı](PLAN.md)
ile [uygulama durumu](docs/status.md) ayrı tutulur.

İsteğe bağlı motorlar için `autoroute`, `autoplace`, `route_engines` ve VS Code'da önce/sonra aday paneli
vardır. Yeni DRC hatası, artan rotalanmamış bağlantı veya kart dışı yerleşim uygulamayı engeller.
Motorların demo kalite kabulü ve PLAN.md'nin kalan ürün fazları tamamlanmış sayılmaz.

Yerel KiCad parça araması, kalıtılan sembol/pad bilgisi ve pin/pad denetimi; önizlemeli `add_symbol`,
`connect`, `add_label`, `replace_part` araçları eklendi. Bağlantı gerçek netlistten, ERC kök şematikten
ölçülür. Paylaşılan şematik dosyalarına yazma engellenir. Katalog, canlı stok, veri sayfası/3B ve
çok dosyalı IR kabulleri hâlâ açıktır. [Araç sözleşmeleri](docs/tools.md).

`circuit_blocks`, `hand_calc`, `plan_circuit`: üç taslak pasif blok, boyutlu SI değerleri,
gerçek yerel pin/pad/net başvuruları ve kanıtlı el hesapları. Ön denetim proje yazmaz;
elektriksel kabul eksik, bloklar olgunluk 0. [IR v1 sözleşmesi ve örnek](docs/ir.md).

`add_block`, üç pasif tarifi tek şematik adayında oluşturur: sabit kütüphane baytları,
toplu anotasyon, gerçek netlerin tam üye kontrolü ve tek checkpoint/geri yükleme.
Netler yalıtılmış yerel adlardır; mevcut netlere bağlantı ve tam IR compiler ayrı işlerdir.

`spice_block_test`, bu üç pasif tarifin altı varyantını gerçek ngspice ile el hesabına
kıyaslar; ölçülen hata ve tolerans kanıta kaydedilir. İdeal simülasyon ERC, stok veya
fiziksel kabul sağlamaz; blok olgunluğu 0 kalır. [Girdiler ve sınırlar](docs/ir.md).

Çekirdek güncellemesinden sonra eski servisi `python -m pcbai stop` ile durdurup yeniden başlatın;
çalışan eski süreç yeni araçları otomatik yüklemez.

## Kurulum

Python 3.11+ ve KiCad CLI gerekir. Bu Windows makinesinde `.venv` KiCad'in Python 3.11'iyle kuruldu.

Service-state kayıtlı projelerden ayrı olmalıdır. `PCBAI_STATE_DIR` bir projenin altında/eşit veya
projeyi kapsıyorsa başlangıç `invalid_state_directory` ile durur; varsayılan LOCALAPPDATA/PcbAi uygundur.

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,ipc]'
.\.venv\Scripts\python.exe -m pcbai doctor
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\ruff.exe check .
```

`ipc` isteğe bağlı bağımlılıktır; canlı PCB keşfi ve seçimi salt okunurdur. API etkin olmalıdır;
PcbAi KiCad ayarlarını değiştirmez. `discover_ipc` ile kanal, ardından açık oturum/belge seçilir.
KiCad 10.0.4 dosya denetimleri çalışır. Plandaki ≥10.0.6 şartı gelecekteki IPC flip işlemleri içindir.

## İsteğe bağlı rota ve yerleşim motorları

Motor programı kullanıcı tarafından kurulur; PcbAi GPL motor kodunu, bağlamalarını veya ikilisini paketlemez.
Program yolları yalnız ortam/PATH'ten seçilir; MCP argümanı olarak yürütülebilir yol alınmaz.

```powershell
$env:PCBAI_FREEROUTING = '<freerouting-cli.exe dosyası>'
# Native 2.5.0 CLI bu makinede serileştirme hatası verdi; aynı sürüm için açık JAR yedeği:
$env:PCBAI_FREEROUTING = '<freerouting-2.5.0.jar dosyası>'
$env:PCBAI_JAVA = '<Java 25 java.exe dosyası>'
# Ubuntu/cpu-only derleme hazırsa:
$env:PCBAI_TRACEMAKER = 'wsl:Ubuntu:/<derleme>/src/app/tracemaker'
$env:PCBAI_TRACEMAKER_PLACE = 'wsl:Ubuntu:/<derleme>/src/place/tracemaker-place'
python -m pcbai doctor
```

Bu ortam değerleri servisin başlatıldığı kabukta bulunmalıdır. VS Code'da **Otomatik rota (önizle)** veya
**Otomatik yerleşim (önizle)** motor/bütçe seçtirir; önce/sonra SVG, ölçüler ve engelleme nedenleri gösterir.
**Bu adayı uygula** yalnız gösterilen aday kimliğiyle ve aynı revizyonda çalışır; KiCad editörleri kapalı olmalıdır.
`autoplace` yalnız TraceMaker-place destekler. WSL kurulumu bu makinede yeniden başlatma bekliyor.
[Motor kararı ve sınırlar](docs/decisions/0003-engines.md), [tekrar ölçüm](docs/spikes/S4.md).

Bu çalışma ağacında doğrulanmış yerel araçlar varsa `. ./scripts/dev-env.ps1`, yalnız mevcut kabuğun
PATH'ine `.venv` ve Node'u ekler; açıkça ayarlanmamışsa yerel JAR/JRE ortam değerlerini doldurur.
Sistem PATH'i değişmez. Denetim için `python -m unittest discover -s tests -v` ve `python -m ruff check .`.

## Bir projeyi kullanma

```powershell
.\.venv\Scripts\python.exe -m pcbai inspect 'C:\Kartim\Kartim.kicad_pro'
.\.venv\Scripts\python.exe -m pcbai serve --project 'C:\Kartim\Kartim.kicad_pro'
```

Birden çok proje için `--project` tekrarlanabilir. Servis yalnız kaydedilen projelere erişir.
Servisi bu terminalde `Ctrl+C` ile durdurabilirsiniz.

Claude Code `.mcp.json` veya MCP destekleyen başka istemciye şu kayıt eklenir (örnek yolları değiştirin):

```json
{
  "mcpServers": {
    "pcbai": {
      "command": "C:\\PcbAi\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.pcbai_mcp"],
      "cwd": "C:\\PcbAi",
      "env": {"PCBAI_PROJECTS": "[\"C:\\\\Kartim\\\\Kartim.kicad_pro\"]"}
    }
  }
}
```

MCP istemciniz `cwd` desteklemiyorsa `env.PYTHONPATH` değerini PcbAi köküne ayarlayın
veya kurulu `.venv` Python'unu kullanın. Vekil servisi gerektiğinde penceresiz başlatır.
Servis istemcilerden bağımsız yaşar; kayıtlı proje listesi değiştirilirse servisi yeniden başlatın.
Arka planda başlatılan servisi durdurmak için `.\.venv\Scripts\python.exe -m pcbai stop` kullanın.
MCP vekili Python 3.9+ stdlib kullanır; çekirdek servis Python 3.11+ ister.

## VS Code ve KiCad eklentileri

```powershell
.\.venv\Scripts\python.exe vscode\pcbai-vscode\build_vsix.py
code --install-extension vscode\pcbai-vscode\dist\pcbai-vscode-0.1.16.vsix --force
.\.venv\Scripts\python.exe kicad_plugin\build_pcm.py
.\.venv\Scripts\python.exe kicad_plugin\configure.py
```

- **VS Code** (`.kicad_pro` içeren çalışma alanında): Ctrl+Shift+P → "PcbAi": servisi başlat/durdur, durum,
  ERC ve DRC, şematik PDF, kart PNG önizlemesi, **Kart 2B görünümünü aç** (katmanlar, seçim, DRC ve işaretler),
  **Kartın 3B görünümünü aç** (döndür, üst/alt, bileşen seçimi),
  **Şematik görünümünü aç** (sayfa ağacı, sembol/pin/tel seçimi, netlistten net vurgusu, ERC ve şematik işaretleri),
  kart ölçümleri ve `.mcp.json`'a kayıt. Yeni paketi kurduktan sonra VS Code penceresini yeniden yükleyin.
  Paket bu deponun yolunu `pcbai.root` varsayılanı olarak taşır.
- **KiCad 10** PCB editöründe iki düğme: *PcbAi'ye kaydet* (projeyi servise ekler; ajanlar `pcbai_status` ile görür)
  ve *PcbAi ERC/DRC* (kaydedilmiş dosyaları denetler, sonucu pencerede gösterir). Düğmeler için
  Tercihler → Eklentiler → **KiCad API'yi etkinleştir** açık olmalı; kurulum betiği KiCad ayarlarını değiştirmez.
  İlk tıklamada KiCad eklentinin Python ortamını kurar ve `kicad-python` indirir (internet gerekir).
  ZIP'i Eklenti ve İçerik Yöneticisi → **Dosyadan yükle…** ile seçin. Eski elle kurulan kopyayı önce
  kaldırın; `install.py` yalnız geliştirme içindir. [Paket ve konum ayarı](kicad_plugin/README.md).
- Servis birden çok istemciyi paylaşır: istenen projeler serviste kayıtlıysa bağlanılır. Kayıtlı değilse eklenti
  onay alıp servisi tüm projelerle yeniden başlatır (bekleyen önizlemeler silinir).

## Değer değişikliği

1. `pcbai_status` ile oturumları listele, kullanıcı projesinin `session` kimliğini seç.
2. `project_summary` ve `list_symbols` ile hedefi ve güncel `revision` değerini al.
3. KiCad'i proje yöneticisi dahil kapat. `set_value` çağrısında `mode="preview"`,
   `session`, `document`, `revision`, `reference`, `value` gönder.
4. Dönen önizlemeyi ve `affected_references`/`affected_instances` listesini incele. Ortak alt sayfa
   dosyasındaki değişiklik bütün kopyaları etkiler (örneğin R203 ve R303); bu durum uyarıyla bildirilir.
   `mode="apply"` çağrısında yalnız aynı hedef ve `candidate_id` gönder.
5. Sonuç ERC ölçümü ve geri dönüş `checkpoint` kimliği içerir. ERC bulguları varsa sonuç bunu açıkça gösterir.

`restore_checkpoint` aynı önizleme/uygulama düzenini kullanır. Önizleme 15 dakika geçerlidir;
projede ilgili başka dosya/kural/kütüphane değişince eski revizyonla uygulanamaz.
`list_symbols` kayıtlı proje adı/kök UUID'sine ait her sayfa örneğini ayrı listeler; eski `Reference` alanı
`property_reference` olarak korunur. Yeni değer metninde kontrol karakterleri kabul edilmez.

## Ayarlar ve sınırlar

- `PCBAI_KICAD_CLI`: kullanıcı tarafından belirlenen `kicad-cli` yolu.
- `PCBAI_STATE_DIR`: özel servis/kanıt/checkpoint klasörü (varsayılan `%LOCALAPPDATA%\PcbAi`).
  Projeye yazan tüm PcbAi istemcileri aynı durum klasörünü kullanmalıdır; süreçler arası kilitler
  bunun `locks/` altındadır. Sürüm yükseltirken eski servisi önce durdurun.
- `PCBAI_PROJECTS`: MCP için `.kicad_pro` yollarının JSON listesi.
- `PCBAI_SERVICE_PYTHON`: servis Python'u; varsayılan projedeki `.venv`.
- `PCBAI_KICAD_SOCKETS`: isteğe bağlı yerel IPC kanal listesi (`["ipc://..."]`); araçlar URL yerine
  keşfin döndürdüğü `endpoint_id` kullanır. Proje ve belge ayrıca açıkça seçilir.
- Dosya modu kaydedilmemiş tamponları görmez. Şematik netleri geometriden tahmin edilmez;
  `list_nets` şu anda PCB dosyalarını kabul eder.
- Tek dosya checkpoint'i tüm projeyi geri almaz. Kontrol noktaları SHA-256 ile doğrulanır.
- Özel durum klasörü boş veya PcbAi'nin yönetim işaretini taşıyan, mevcut kullanıcıya ait klasör olmalıdır.
  Önceden var olan alt dosyaların erişim izinleri de yalnız kullanıcıya açık hâle getirilir.
  Proje dosyası değişimlerinde mevcut izinler korunur; korunamıyorsa yazma reddedilir.
- Simülasyon: şematikteki `.tran/.ac/.dc/.op` komutu KiCad'in ngspice'ıyla (`simulate`).
- Kart düzenleme (dosya modu): footprint taşı/döndür/yüz değiştir, iz genişliği, dökme alanı, net sınıfı; hepsi gerçek DRC kapısıyla.
- Temel Gerber/delik ZIP, VS Code kart 2B ve şematik görünümü ile işaretler vardır; KiCad ile
  çapraz seçim, üretici DFM, BOM/CPL, katalog/stok, IR ve otorota henüz yoktur.
- ERC/DRC temizliği gerçek devrenin elektriksel/fiziksel çalıştığının kanıtı değildir.

Uzun denetim/çıktı için `start_job` çağrısına `session`, `document`, `revision` ve `tool` gönderin;
`job_status(job_id)` ile asıl araç sonucunu izleyin. Servis yeniden başladığında iş kimlikleri geçersiz olur.
İzole canlı bağlantı deneyini yeniden çalıştırma: `python scripts/spike_ipc.py --run --output .pcbai-state/S1-result.json`.
Deney yalnız kendi oluşturduğu geçici KiCad süreçlerini sonlandırır; kullanıcı uygulamalarını kapatmaz.
Deneme/denetim raporları `.pcbai-state/` altına gider. Yayın kanıtını değiştirmek için Python deneylerinde
`--publish`, tarayıcı deneyinde `PCBAI_PUBLISH_EVIDENCE=1` açıkça seçilmelidir.
