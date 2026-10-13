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
4. **PcbAi'ye kaydet** ve **PcbAi ERC/DRC** düğmelerini kayıtlı demo kopyasında deneyin.
   Gerçek KiCad kabulü henüz ölçülmedi; bu adımlar kabul sonucu değildir.

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
