# KiCad 10 IPC paketi

PcbAi LGPL-2.1-or-later lisanslıdır. Normal kurulum PCM zip'i ile yapılır:

```powershell
python kicad_plugin/build_pcm.py
python kicad_plugin/configure.py
```

Çıktı `dist/pcbai-kicad-0.1.3.zip`; sürüm `pcbai/__init__.py`'den gelir. ZIP kökünde
`metadata.json`, altında `plugins/` ve `resources/icon.png` vardır. PCM sürüm kaydı
`runtime: "ipc"` içerir; `plugin.json` ise çalıştırıcıyı `runtime.type: "python"` olarak tanımlar.
Dosyalar açık listeyle paketlenir; depo yolu, kurulum betikleri ve kullanıcı yapılandırması pakete girmez.

1. Önceden elle kurulan `Documents/KiCad/10.0/plugins/org.pcbai.kicad` varsa yedeğini alıp
   kaldırın; PCM ve geliştirme kopyası aynı anda bulunmamalı.
2. KiCad → Eklenti ve İçerik Yöneticisi → **Dosyadan yükle…** → ZIP.
3. Tercihler → Eklentiler → **KiCad API'yi etkinleştir**. PCB editörünü yeniden açın.
4. **PcbAi'ye kaydet** (mavi halka), **PcbAi İşaret koy** (turuncu artı), **PcbAi ERC/DRC** ve **PcbAi Asistan**
   düğmelerini kayıtlı demo kopyasında deneyin.
   Gerçek KiCad kabulü henüz ölçülmedi; bu adımlar kabul sonucu değildir.

## İşaret koy (IM)

Turuncu artı **PcbAi İşaret koy**, Asistan penceresini açar (açıksa öne getirir) ve imleci **İşaret notu** kutusuna
koyar. Yer seçimi:

- **PCB: KiCad seçimi.** Pencere KiCad seçimini okur ve "Hedef" satırında gösterir. Seçimde kimliği olan bir bileşen
  varsa işaret ona bağlanır (bileşen taşınınca işaret de taşınır); yoksa ilk öğenin konumu nokta olur. Bileşen
  kaydedilmiş kartta yoksa işaret nokta olarak konur ve durum satırı bunu söyler.
- **Şematik: kaydedilmiş sayfa.** KiCad 10'da şematik düzenleyiciye eklenti düğmesi konamaz ve canlı şematik seçimi
  okunamaz (`L-IPC-NO-LIVE-SCH`). Bu yüzden sayfa ve bileşen (referansa göre sıralı) pencereden seçilir; liste
  kaydedilmiş dosyadan okunur ("sayfaları oku"). İşaret bileşenin UUID'sine ve sayfa örneğine bağlanır.

Düğmeler: **İşaret koy**, **Koy ve ajana gönder** (yalnız yeni işaret işaretli olarak seçili ajana gider), listeden
bir işaret seçilince notu kutuya gelir: **Notu kaydet**, **Bu işareti uygula** (yalnız o işaretle gönderir).
Yazım VS Code paneliyle aynı yoldan gider (`/view/call` → `set_marker` önizle + uygula); işaretler
`pcbai/markers.json`'da ortaktır ve VS Code görünümlerinde de görünür.

## PcbAi Asistan penceresi (AJ-4)

**PcbAi Asistan** düğmesi ayrı bir wx penceresi açar (KiCad 10 IPC'de yerleştirilebilir panel yok). Düğme
pencereyi ayrık süreçte başlatıp hemen döner; ikinci tıklama yeni pencere açmaz, mevcut pencereyi öne getirir;
KiCad kapanınca pencere de kapanır. Pencerede ajan seçimi (VS Code'daki ajan, Claude Code ve Codex terminali,
pano), istek kutusu, KiCad seçimi (yaklaşık 0,7 sn'de bir okunur), açık işaretler, oluşan istemin önizlemesi,
ERC/DRC (servisin `check` aracı) ve son 50 ajan olayı bulunur. İstem metni servisten gelir (`POST /agent/prompt`).
"VS Code'daki ajan" satırı istemi URL'ye koymaz: servis tek kullanımlık bir devir kaydı tutar, VS Code eklentisi
onu alıp panelde seçili ajana verir ve sonucu pencerenin durum satırına geri yazar (AJ-5). Terminal ajanları istemi
doğrudan başlatır; bu yüzden önizleme varsayılan olarak açıktır. Ajan seçimi `%APPDATA%/PcbAi/assistant.json`'da
tutulur; KiCad ayarları değişmez.

**Yerleşik model (AJ-6).** "Yerleşik model — bu pencerede" satırı pencerede sohbet açar. Sağlayıcılar: Ollama
(`/api/chat`, `num_ctx` 16384), LM Studio ve OpenAI uyumlu sunucular (`/chat/completions`), Claude (resmi
`anthropic` SDK, varsayılan `claude-opus-5-5`, sunucu tarafı yedek model açık). SDK eklenti ortamında yoksa
"Paketi kur" onaydan sonra `pip install anthropic` çalıştırır. API anahtarı yalnız ortam değişkeninden okunur
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`); ayar dosyasına yalnız değişkenin adı yazılır. Araçlar pencerede değil
PcbAi servisinde `builtin` istemci adıyla çalışır: **Planla** modunda yazan araçlar modele hiç sunulmaz;
**Uygula** modunda önizleme serbest, `apply` ve diğer yazan çağrılar çözülmüş argümanlar ve önizleme özetiyle onay
ister. Aynı hatalı çağrının 3. tekrarında tur durur. Yerel küçük modellere küçük araç kümesi verilir.

Konum çözüm sırası: `PCBAI_ROOT` → `%APPDATA%/PcbAi/location.json` (`{"root": "mutlak yol"}`)
→ açıklayıcı hata. `configure.py` bu dış dosyayı yazar; KiCad ayarlarını değiştirmez. Açık ama
geçersiz `PCBAI_ROOT` sessizce başka depoya düşmez. İki farklı depo için aynı paket kullanılabilir.
Windows dışındaki konum varsayılanı `~/.config/PcbAi/location.json`'dır.

İlk tıklamada KiCad eklenti Python ortamını oluşturur ve `requirements.txt` içindeki
`kicad-python` bağımlılığını indirir; internet gerekir. Kurulum KiCad tarafında başarısız olursa
KiCad'in ortam kurulum hatası incelenmelidir; giriş betiğine ulaşan eksik `kipy` hatası ayrıca açıklanır.

`install.py` yalnız geliştirme içindir. Normal PCM kurulumundan ayrı kullanılır. `--dest` ve
`--location` izole deneme yollarını destekler; dosya hedeflerinde symlink, junction ve hardlink reddedilir.
Betik hedef klasörü topluca silmez; eski `pcbai_location.json` dosyasını kaldırır.

Doğrulama: `python -m unittest tests.test_kicad_plugin -v`. Dev bağımlılığı `jsonschema` ile
kurulu KiCad'ın `pcm.v2.schema.json` ve `api.v1.schema.json` dosyaları kullanılır; KiCad/şema yoksa
şema testi açıkça atlanır. ZIP testi, şema kabulü ve iki kaynak kopyasıyla gerçek servis bağlantısı
canlı KiCad IPC/düğme kabulü değildir.

Paket yapısı ve IPC sürüm alanı: [KiCad resmi paket belgesi](https://dev-docs.kicad.org/en/addons/).
