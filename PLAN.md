# PcbAi — problemden karta yapay zekâ destekli elektronik tasarım (KiCad)

Tarih: 13 Ekim 2026 · Durum: **plan v1.1 + çekirdek 0.1.22** (faz kabulleri açık; [uygulama durumu](docs/status.md)) · Kardeş proje: CadAI (ayrı depo, FreeCAD/Fusion).
PcbAi, CadAI'da işe yarayan yaklaşımı KiCad'e taşır; CadAI'ın koduna ve klasör yapısına dokunmaz.

**Bu belge:** 0 özet · 1–2 ne ve neden · 3–5 nasıl çalışacak (mimari, veri sözleşmeleri, alt sistemler) · 6–7 nasıl
doğrulayacağız, nasıl çalışacağız · 8–9 iş planı ve takvim · 10–14 sonuç, riskler, kararlar, ilk iki hafta, sonrası ·
15–16 kaynaklar ve sürüm notları.

---

## 0. Özet

- **Ne:** KiCad 10 için bir MCP sunucusu, arka planda çalışan bir çekirdek servis ve bir VS Code eklentisi. Kullanıcı
  bir problem yazar; ajan gereksinimden üretim dosyasına kadar gider ve her adımı ölçerek kanıtlar.
- **Nasıl:** LLM koordinat değil **devre IR'si (JSON)** üretir. IR'yi **test edilmiş devre blokları** ve deterministik
  motorlar (şematik yazıcı, yerleşim, Freerouting) çizer. Doğruluğu `kicad-cli` (ERC/DRC), ngspice (SPICE) ve el hesabı
  ölçer. Her sayı bir kanıt kaydına bağlanır; rapor bu kayıtlardan üretilir.
- **Ne zaman:** 30 hafta (12 Ekim 2026 – 7 Mayıs 2027), 8 faz; her faz kıyas setiyle ölçülen bir sürüm. KiCad 11
  çıkınca ayrı bir geçiş fazı.
- **İlk somut hedef (v0.3, Aralık 2026 sonu):** kıyas setindeki 5 problemin şematiği elle müdahalesiz ERC=0, bloklar
  SPICE testinden geçmiş, parçalar stokta.
- **Uçtan uca hedef (v0.8, Nisan 2027):** 5 problemin en az 4'ü problemden Gerber/BOM/CPL + kanıtlı rapora; iki kart
  JLCPCB'de üretilip ölçülmüş.

---

## 1. Hedef ve kapsam

Kullanıcı bir **problem** yazar:

> "12 V girişli, USB-C'den programlanan, 2 röle süren STM32 kartı; 50 × 40 mm'ye sığsın, JLCPCB'de üretilsin."

PcbAi, kullanıcının **açık KiCad projesi** üzerinde, her adımı ölçerek doğrulayarak:

1. Gereksinimleri yapılandırır (giriş gerilimi, akım bütçesi, arayüzler, kart ölçüsü, katman sayısı, üretici, maliyet).
2. **Gerçek ve stokta olan** bileşenleri bulur; sembol + footprint + 3B modeli projeye getirir.
3. Şematiği çizer (okunur yerleşim, etiketler, güç sembolleri) ve **ERC**'den geçirir.
4. **Simülasyon** yapar (ngspice: çalışma noktası, geçici rejim, AC; regülatör, filtre, bölücü, op-amp kazancı…).
5. PCB'ye aktarır, kısıtlara göre **yerleştirir**, **rotalar**, bakır döküm yapar, **DRC/DFM**'den geçirir.
6. Üretim çıktılarını (Gerber, delik, BOM, dizgi dosyası, STEP) ve **kanıtlı tasarım raporunu** verir.

Kullanıcı CadAI'daki gibi VS Code'daki kart/şematik görünümünde **numaralı işaret koyarak** tarif eder:
"#1: bu konnektörü sol kenara al", "#2: bu hat 1 mm olsun", "#3: buraya bakır dökme".

**Vaat edilmeyen:** "Tek tuşla üretime hazır kart". Ajan ilk geçişi yapar ve denetler; yüksek hız (USB 3, DDR, RF),
yüksek gerilim ve emniyet kritik kartlarda insan onayı ve uzman incelemesi zorunludur. Bu sınır ticari araçlarda da aynı.

### 1.1 Kullanım senaryosu (v0.8)

1. Kullanıcı VS Code'da boş bir KiCad projesi açar ve Claude Code'a problemi yazar.
2. Ajan gereksinimleri çıkarır, belirsizleri sorar ("röle kontakları kaç A?", "USB-C yalnızca güç mü?").
3. Blok listesi + güç bütçesi tablosu gelir; kullanıcı onaylar.
4. Şematik alt sayfalar hâlinde oluşur, ERC=0; bloklar SPICE testinden geçer; LDO ısısı gibi uyarılar sayıyla gelir.
5. Kart çerçevesi ve skorlu yerleşim adayları; kullanıcı VS Code'da işaretlerle düzeltir.
6. Rota + döküm, DRC/DFM=0; Gerber/delik/BOM/CPL zip'i ve gereksinim ↔ kanıt raporu.
7. İstenirse CadAI kartın STEP'inden kutuyu tasarlar; kutudan gelen montaj delikleri karta geri yazılır.

### 1.2 Kapsam

| İçinde (v0.8) | Dışında (insana bırakılır ya da sonraki sürüm) |
|---|---|
| 2 katman (4 katman Faz 5 sonunda, deneysel) | Yüksek hız: USB 3, DDR, PCIe, Ethernet PHY yerleşimi |
| ≤ ~150 bileşen, SMD + THT | RF tasarımı (anten eşleştirme), BGA fanout |
| Gömülü dijital, düşük güç analog, ≤ 24 V / ≤ 5 A güç | Şebeke gerilimi (230 V), emniyet/tıbbi/otomotiv sertifikası |
| JLCPCB (önce), PCBWay (sonra); SMT dizgi BOM/CPL | Flex/rigid-flex; empedans garantisi (yalnızca kaba hesap) |

### 1.3 Başarı ölçütleri (ürün düzeyi)

| Kod | Ölçüt | Hedef (v0.8) |
|---|---|---|
| B1 | Uydurma parça/pin | 0: her sembol–footprint çifti `verify_part`'tan geçmiş, her parça kütüphanede ya da katalogda |
| B2 | Kıyas başarısı | Claude ile 5 problemin ≥ 4'ü uçtan uca; qwen3:8b ile şematik kısmında ≥ 2/5 |
| B3 | Kanıt | Rapordaki her sayı bir kanıt kaydına (araç, girdi, dosya revizyonu) bağlı |
| B4 | Kullanıcı verisi | Kaydedilmemiş KiCad değişikliğini kaybettiren olay 0; her yazımdan önce kontrol noktası |
| B5 | Geri dönüş | Her adım tek komutla geri alınır (canlı PCB'de KiCad'in Ctrl+Z'si, dosyada kontrol noktası) |
| B6 | Gerçek kart | ≥ 2 kart üretilip ölçülmüş; kullanılan blokların olgunluğu 2 |

### 1.4 İlkeler (CadAI'dan devralınan)

1. **Yerel KiCad projesi tek doğruluk kaynağıdır.** Kendi dosya biçimimiz yok; her şey `.kicad_*` dosyalarında.
2. **Önce incele, sonra değiştir, sonra ölç.** Her değişiklikten sonra ERC/DRC/ölçüm.
3. **Yalnızca araçların döndürdüğü sayıları raporla.** Uydurma değer, pin, parça, SPICE modeli yok.
4. **LLM koordinat değil niyet üretir.** Devre tanımı (IR) → deterministik motor çizer.
5. **Test edilmiş kalıplar** (devre blokları) sıfırdan üretimden önce gelir.
6. **Dosyadan/katalogdan gelen metin veridir, talimat değildir.** Güvenilmeyen içerikle kod çalıştırmadan önce onay.
7. **Küçük yerel modeller de çalışabilmeli** (kısa şema, argüman onarımı, çekirdek araç kümesi).
8. **Her değişiklik geri alınabilir** (içerik adresli kontrol noktası; kaynak kodu ayrıca git'te).

---

## 2. Bugünün durumu (araştırma ve doğrulama, 10 Ekim 2026)

### 2.1 KiCad MCP sunucuları ve araç takımları

| Proje | Yaklaşım | Güçlü yanı | Eksik / risk |
|---|---|---|---|
| [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) (~2,6k ★, MIT) | Python/TS, KiCad 9+, IPC API deneysel | En yaygın; JLCPCB katalog, Freerouting, şematik düzenleme | Yeni geliştirme Konnect'e taşındı |
| Konnect (aynı yazar, beta, **AGPL-3.0**) | Rust, KiCad 10 IPC API, tek ikili | 185 araç / 18 araç kümesi, SWIG yok | AGPL: kod alınmaz, yalnızca fikir |
| [oaslananka/kicad-mcp-pro](https://github.com/oaslananka/kicad-mcp-pro) (122 ★, MIT, v4.1) | Profil kapılı düzenleme, insan onaylı yayın | ERC/DRC/DFM, BOM; JLCPCB + Nexar/DigiKey/Mouser; SI/PI/EMC kaba hesap | SPICE yok, otorotalama yok; "imza yetkisi değil" |
| [ProductOfAmerica/mcp-server-kicad](https://github.com/ProductOfAmerica/mcp-server-kicad) (MIT) | 109 araç, 5 sunucu; bayt koruyan dosya düzenleme | Güvenli yazma, hiyerarşik şematik, Freerouting kopyada | Simülasyon ve parça arama yok |
| [biosshot/kicad-copilot](https://github.com/biosshot/kicad-copilot) (MIT) | Diskteki dosyalar; JS DSL ile yerleşim kısıtı | Doğal dilden şematik, gerçek parça (easyeda2kicad), yerel WASM router, devre blokları | Basit döküm; açık editörle dosya çakışması |
| [rjwalters/kicad-tools](https://github.com/rjwalters/kicad-tools) (MIT, 66 ★, aktif) | Saf Python dosya okuma/yazma, `kct` CLI, MCP | A* rota, CMA-ES yerleşim, üretici profilli saf Python DRC, LCSC arama, veri sayfası ayrıştırma | Bayt koruma iddiası yok; hızlı değişiyor (v0.21'de kırıcı değişiklik) |
| [aklofas/kicad-happy](https://skills.sh/aklofas/kicad-happy/spice) (MIT, skill) | Şematik analiz → JSON → SPICE testbench | Alt devreyi tanıyıp ngspice/LTspice/Xyce ile doğrular | MCP değil; çizmez, denetler |
| [kicad-jlcpcb](https://www.claudepluginhub.com/plugins/beckhamlabsllc-kicad-jlcpcb) | LCSC/JLCPCB "basic" öncelikli parça | Stok/temel parça tercihi, EasyEDA'dan pin haritası | Dar kapsam |

SPICE tarafı: [ltspice-mcp](https://glama.ai/mcp/servers/Cognitohazard/ltspice-mcp) (ngspice/LTspice/QSPICE/Xyce,
spicelib üzerinde, geliştirme aşamasında), [py4spice](https://pypi.org/project/py4spice) (KiCad 7+ şematiğinden ngspice).

Rota tarafı: [Freerouting 2.5.0](https://github.com/freerouting/freerouting/releases) (5 Ekim 2026): Windows için
yerel CLI (Java gerekmez), KiCad 10+ için doğrudan IPC modu, HTTP API (`POST /v1/autoroute`) ve MCP aracı
(`autoroute_board`); DSN/SES yolu yedek olarak duruyor. Sonraki sürümde KiCad SWIG desteği kalkacak.
[TraceMaker](https://github.com/DingoOz/TraceMaker) 0.9.0 (GPL-3.0, C++20, yalnız Linux): rota + yerleşim, KiCad 9/10,
`--work` ile deterministik; README'ye göre PCBench'in en zor grubunda %54,5 temiz kart (Freerouting 2.5: %36,4) —
doğrulanmadı, S10'da ölçülür ([plan](docs/plan-rota-yerlesim.md)).

### 2.2 Kod ile devre ve araştırma

- **SKiDL**, **CircuitDK** (KiCad 10, deneysel), **atopile**, **tscircuit**: devreyi kodla tanımlar, netlist/şematik üretir.
- [CircuitLM](https://arxiv.org/abs/2601.04505v1): çok ajanlı, bileşen bilgi tabanı + ERC ile doğrulama.
- [PCBSchemaGen](https://arxiv.org/abs/2602.00510v1): datasheet kısıtlı, SKiDL üretir, denetle-onar döngüsü.
- [SchGen](https://alphaxiv.org/abs/2605.30345): 20B model, şematiği Python kodu olarak üretir. Kodu açık:
  [microsoft/SchGen](https://github.com/microsoft/SchGen) (MIT, 38 ★). IR üreticisine alternatif olarak denenebilir.
- [pcbGPT](https://arxiv.org/abs/2606.01188) (Mayıs 2026): doğal dil gereksiniminden düzenlenebilir KiCad şematiği;
  Python DSL + parça arama + doğrulama, 20 gömülü görevde pass@1 0,90. IR + doğrulama döngüsü için yöntem kaynağı.
- [jefcoder/circuitron](https://github.com/jefcoder/circuitron) (MIT, 14 ★, son commit Kasım 2025): çok ajanlı;
  plan → parça ara → SKiDL üret → ERC → düzelt. Simülasyon ve blok kütüphanesi yok.
- **Ortak ders:** LLM'e çizgi çizdirilmiyor; yapılandırılmış devre tanımı üretiliyor, motor çiziyor, ERC geri besliyor.
  En sık hata **uydurma parça ve pin**.

### 2.3 Ticari

- **Flux.ai** (Mart 2026'da 37 M$ yatırım): tarayıcıda; ajan bileşen yerleştiriyor, tek tıkla AI yerleşim/rota, canlı
  fiyat/stok. Kapalı bahçe; kritik hatları yine insan çiziyor.
- **Quilter**: fizik tabanlı + pekiştirmeli öğrenme ile paralel aday layout, empedans kontrolü, 2026'da BGA fanout.
  Yalnızca layout; şematik ve simülasyon yok.

### 2.4 KiCad 10 (bu makinede ve kaynak kodda doğrulandı)

- **Kurulu: KiCad 10.0.4** (`C:\Program Files\KiCad\10.0`); son sürüm 10.0.7. KiCad ile gelenler: Python 3.11.5 (SWIG
  `pcbnew` ile), `ngspice.dll` + kod modelleri (`lib\ngspice\*.cm`), ~220 sembol ve ~155 footprint kütüphanesi,
  3B modeller, `share\kicad\demos` altında 18 demo klasörü.
- Makinede: sistem Python 3.14.2, git 2.52, Ollama 0.15.6 (servis kapalı). **Yok:** Java (Freerouting yerel CLI'si
  istemiyor), Node (eklenti testleri için gerekli), ayrı ngspice konsolu (KiCad'in DLL'i yetiyor).
- **IPC API:** yalnızca açık GUI ve yalnızca PCB editörü. Bu makinede **kapalı** (`kicad_common.json` →
  `api.enable_server: false`). Dışarıdan bağlanan istemci ortam değişkeni almaz; varsayılan soket
  `%TEMP%\kicad\api.sock`, ikinci KiCad örneğinde ada PID eklenir. Dışa aktarma ve çizim API'de yok (KiCad 11).
- **kicad-python 0.8.0** (30 Ağustos 2026, MIT): öğe oluştur/güncelle/sil, commit (tek geri al adımı), seçim, döküm
  doldurma, kaydet/geri yükle (`revert`), kartı metin olarak alma (`get_as_string`), netler, net sınıfları, katman
  yığını. `flip_items` için KiCad ≥ 10.0.6 gerekir. **0.8.0'da yok:** kütüphaneden footprint yerleştirme, netlist içe
  alma ("şematikten PCB'yi güncelle"), dışa aktarım, şematik erişimi. Bunlar kipy'nin ana dalında var; büyük
  olasılıkla KiCad 11 ile gelir.
- **`kicad-cli` 10:** ERC/DRC JSON çıktısı; `pcb drc --schematic-parity` (şematik–kart uyumu), `--refill-zones
  --save-board` (dökümü başsız doldurur); `pcb render` (3B PNG); `pcb export` (gerbers, drill, pos, step, glb, svg,
  ipc2581, odb, stats…); `sch export netlist --format spice`, `bom`, `svg`, `pdf`. **Specctra DSN dışa aktarımı yok.**
- KiCad 10 şemalarında "uzak sağlayıcı" (remote provider: sembol/footprint/3B/SPICE indirme, KiCad içinde web paneli)
  tanımı var (`share\kicad\schemas\kicad-remote-provider-metadata-v1.schema.json`). İleride PcbAi'nin doğrulanmış
  parçalarını KiCad'in kendi panelinde sunmak için araştırılacak.
- SWIG `pcbnew` kullanımdan kalkıyor; PcbAi'de yalnızca ayrı süreçte DSN/SES için kullanılır.

### 2.5 Lisans tablosu: ne alınır, ne yalnızca çalıştırılır

| Bileşen | Lisans | PcbAi'de kullanım |
|---|---|---|
| kicad-python (kipy) | MIT | Bağımlılık (servis) |
| JLC2KiCadLib | MIT | Bağımlılık: JLC/EasyEDA parçasını sembol + footprint + 3B model olarak getirme |
| jlcparts, kicad-jlcpcb-tools | MIT | Çevrimdışı katalog verisi; CPL dönüş düzeltme tablosu (atıfla) |
| kicad-tools, SKiDL | MIT | Kıyas ve fikir; kicad-tools yerleşim/rota motoru adayı |
| easyeda2kicad | **AGPL-3.0** | Kod alınmaz; yalnızca kullanıcı isterse ayrı süreç |
| kiutils | **GPL-3.0** (2024'ten beri güncellenmiyor) | Kullanılmaz |
| kicad-skip | LGPL-2.1 (2024'ten beri güncellenmiyor) | Kullanılmaz |
| Konnect | **AGPL-3.0** | Yalnızca fikir |
| KiCad, Freerouting | GPL-3.0 | Ayrı program (kicad-cli, IPC, CLI) |
| TraceMaker | GPL-3.0 | Ayrı program (WSL ya da yerel); kod, `bindings/` ve ikili alınmaz/paketlenmez (K12) |
| ngspice | Açık kaynak (BSD tabanlı) | KiCad'in DLL'i, ayrı süreçte |
| CadAI | LGPL-2.1-or-later (telif sende) | Kendi kodun; kopyalanabilir (lisans kararı K1) |

CI'da bağımlılık lisans denetimi yapılır: GPL/AGPL bir bağımlılık girerse yapı kırmızı olur.

### 2.6 Boşluk = PcbAi'nin farkı

Mevcut projeler "KiCad'e araç takımı"; kicad-tools buna yerleşim, rota ve DRC profillerini de ekliyor. Hiçbirinde
birlikte olmayanlar:

1. **Problemden karta uçtan uca döngü**, her adımda ölçülmüş kanıt ve gereksinim ↔ kanıt raporu.
2. **Test edilmiş devre blokları:** her blok ERC + SPICE + el hesabı geçme ölçütü taşır; gerçek kartta ölçülünce
   olgunluğu yükselir (CadAI'daki `freecad_recipes` karşılığı).
3. **Simülasyonun tasarım döngüsüne gömülmesi** (blok başına geçti/kaldı).
4. **İşaretle tarif** ve VS Code'da canlı 2B/3B kart + şematik görünümü.
5. **Mekanikle birlikte tasarım:** CadAI ile aynı ajanda iki MCP sunucusu.
6. **Küçük yerel model desteği** ve CadAI'ın güvenlik modeli (veri ≠ talimat, çözülmüş argümanla onay).

---

## 3. Mimari

### 3.1 Bileşenler

```text
VS Code eklentisi                                       AI ajanları (Claude Code, Codex, Cline, Kilo, Ollama…)
(kart 3B/2B, şematik, işaretler, sonuç paneli)                       | MCP (stdio)
            |                                           mcp_server/pcbai_mcp.py — yalnızca stdlib, ince vekil
            | HTTP 127.0.0.1 + belirteç                              | HTTP 127.0.0.1 + belirteç
            +------------------------------+-------------------------+
                                           |
                     pcbai servisi (KiCad'in Python 3.11'iyle kurulan venv, tek örnek)
        oturumlar · araç kaydı · uzun işler · işaretler · kontrol noktaları · kanıt kaydı · tasarım durumu
  +---------+----------+----------+-----------+------------+-----------+------------+-----------+
  |         |          |          |           |            |           |            |           |
Devre IR  Bloklar    Parça      Şematik     PCB motoru   Simülasyon  Doğrulama    Üretim +
(şema,    (alt sayfa, servisi   yazıcı      (senkron,    (ngspice,   (ERC, DRC,   rapor
hesap)    SPICE      (KiCad,    (bayt       yerleşim,    ölçüm, el   DFM, tasarım
          testi)     JLC)       koruyan)    rota, döküm) hesabı)     kuralları)
                                           |
        +----------------------------------+-----------------------------------+
        |                                  |                                   |
KiCad 10 GUI — IPC API (kipy)       .kicad_* dosyaları                 Dış programlar (ayrı süreç, zaman aşımlı)
canlı PCB: oku, değiştir, seçim;    şematik her zaman; KiCad           kicad-cli · KiCad Python + pcbnew (DSN/SES)
her değişiklik tek geri al adımı    kapalıyken her şey                 ngspice.dll · freerouting-cli · JLC2KiCadLib
```

**Neden ayrı bir servis (CadAI'daki köprü düzeni):**
- Birden çok ajan (Claude Code + Cline) ve VS Code aynı durumu paylaşır: oturumlar, işaretler, kontrol noktaları, uzun işler.
- Uzun işler (rota, Monte Carlo) araç çağrısından bağımsız sürer; `job_status` ile izlenir.
- MCP vekili CadAI'ın `cadai_mcp.py`'sinden uyarlanır; yalnızca standart kütüphane ister, her Python 3.9+'ta çalışır.
- Servisin bağımlılıkları (kipy, numpy, matplotlib, pypdf, JLC2KiCadLib) kendi venv'inde kalır; ajanın Python'una dokunmaz.

**Kim başlatır:** VS Code eklentisi (`.kicad_pro` içeren çalışma alanında) ya da MCP vekili (servis yoksa). Tek örnek:
`%APPDATA%\PcbAi\service.json` (port, belirteç, PID; yalnızca kullanıcıya açık) + PID canlılık denetimi.

**KiCad'i bulma:** servis `%TEMP%\kicad\api*.sock` adlarını (Windows'ta adlandırılmış kanallar) tarar, her örneğe kipy
ile bağlanır, `get_version` ve `get_open_documents` ile açık kartı ve projeyi öğrenir. Birden çok örnek varsa **sorar**.
Tarama yetmezse (S1 denemesi karar verir) PCB editörüne küçük bir IPC eklentisi konur: araç çubuğu düğmesi kendi
`KICAD_API_SOCKET` / `KICAD_API_TOKEN` değerlerini servise bildirir.

### 3.2 Çalışma modları

| İşlem | Canlı mod (KiCad açık, kart PCB editöründe) | Dosya modu (KiCad kapalı) |
|---|---|---|
| Kart okuma | IPC (kipy) | s-expr okuyucu |
| Footprint taşı/döndür/çevir, iz, via, döküm | IPC commit (KiCad'de tek Ctrl+Z) | Dosyaya yazım |
| Şematikten karta footprint ekleme | Dosyaya yazım + `board.revert()` (KiCad 10'da API yok) | Dosyaya yazım |
| Şematik değişikliği | Dosyaya yazım + KiCad'de yeniden yükleme (KiCad 10'da şematik API yok) | Dosyaya yazım |
| ERC | `kicad-cli sch erc` (diskteki dosya) | Aynı |
| DRC | `get_as_string()` → geçici kopya (+ `.kicad_pro`, `.kicad_dru`) → `kicad-cli pcb drc` | `kicad-cli pcb drc` |
| Döküm doldurma | IPC `refill_zones` | Kopyada `kicad-cli pcb drc --refill-zones --save-board` |
| Gerber, STEP, render | kicad-cli: kaydedilmiş dosya ya da geçici kopya | kicad-cli |

### 3.3 Bir değişikliğin yolu

```text
Kullanıcı: "R5'i 4,7k yap"   →   ajan: set_value(ref="R5", value="4k7")
 1. Hedef denetimi: oturum, belge, revizyon. Ajan eski revizyonu görüyorsa "yeniden incele" hatası.
 2. Önizleme: ortak sayfanın etkilenen bütün referanslarını bildir; aynı revizyona bağlı aday oluştur.
 3. Çakışma denetimi: kilit dosyası ya da kaydedilmemiş değişiklik varsa dur, kullanıcıya sor.
 4. CLI ön denetimi ve revizyon denetimi; yazımdan önce özel durumda SHA-256 blob + manifest checkpoint'i.
    .kicad_sch'de yalnızca hedef Value alanlarının baytları değişir; geçici dosya + yeniden adlandırma (atomik yazım).
 5. kicad-cli sch erc --format json → bulgular konumlarıyla.
 6. Sonuç: {changed, verified: "erc_ok", summary: "R5: 10k → 4k7", evidence: ["ev-0142"]}
 7. Proje içerik revizyonu değişir. Gelecek görünüm fazında VS Code yenilenir; KiCad'e yeniden yükle bildirimi.
```

### 3.4 Temel kararlar

| Konu | Karar | Neden |
|---|---|---|
| Dil | Servis Python 3.11 (KiCad'in Python'uyla kurulan venv); MCP vekili yalnızca stdlib (3.9+); VS Code düz JavaScript | Tekerlek (wheel) uyumu; KiCad eklentileri de bu Python'u kullanıyor; CadAI ile aynı düzen |
| MCP | CadAI vekilinden uyarlanır: MCP 2026-07-28 (durumsuz) + eski `initialize` | CadAI'da kanıtlandı |
| KiCad sürümü | **10.0.7** hedef (en az 10.0.6: `flip_items`); 11 çıkınca Faz 8 | PCB IPC API 10'da olgun; şematik API ve başsız mod 11'de |
| Şematik yazımı | Dosya düzeyinde, **kendi bayt koruyan s-expr** yazıcımız | 10'da şematik API yok; kiutils GPL, kicad-skip bakımsız, kicad-tools bayt koruma iddia etmiyor |
| Şematik düzeni | **Her blok bir hiyerarşik alt sayfa**; kök sayfa blokları etiketlerle bağlar | Okunurluk, bloğun tek başına ERC/SPICE testi, yeniden uygulamada izolasyon |
| PCB | Açıksa IPC (canlı, geri al çalışır); kapalıysa dosya + kicad-cli | Kullanıcı değişikliği anında görür |
| SWIG `pcbnew` | Yalnızca ayrı süreçte, KiCad'in Python'uyla DSN dışa / SES içe aktarma | kicad-cli'de DSN yok; SWIG kalkıyor |
| LLM çıktısı | **Devre IR (JSON)**: bloklar, raylar, parçalar, bağlantılar, kısıtlar; koordinat yok | Araştırmaların ortak dersi; küçük model de üretebilir |
| Simülasyon | KiCad'in `ngspice.dll`'i, ctypes ile alt süreçte; ayrı ngspice konsolu isteğe bağlı | Ek kurulum yok; çökme servisi düşürmez |
| Otorota | Freerouting 2.5 yerel CLI (Java yok), kopya üzerinde; sonuç onayla tek commit | Açık kaynak, ölçülebilir, geri alınabilir |
| Parça | KiCad kütüphanesi → çevrimdışı JLC kataloğu → JLC2KiCadLib (MIT) ile getirme | Çevrimdışı önce; uydurma pin yok; AGPL kod yok |
| Geçmiş | Proje dışında içerik adresli SHA-256 blob + JSON manifest (`%LOCALAPPDATA%\PcbAi\history\…`); [karar](docs/decisions/0001-core.md) | Kullanıcının git geçmişine dokunmaz; mevcut çekirdekte tek belge geri yüklenir, çok belgeli atomik işlem ayrı iş paketi |
| Yazma kilidi | Özel durum klasöründe `locks/<proje-kökü-karması>.lock`; tüm yazarlar aynı durum klasöründe | Proje kökünde kalıcı kilit bırakmaz; aynı köke ait süreçler birbirini dışlar |
| Lisans | LGPL-2.1-or-later ([K1 kabulü](docs/decisions/0002-license.md), 11 Ekim 2026) | Kod CadAI ile iki yönde serbest akar; MIT projelerden atıfla alınabilir |
| Dış program yolu | Ayar + ortam değişkeni + PATH + olağan klasörler; **yapay zekâ yol seçemez** | CadAI `external.py` kuralı |
| CadAI ilişkisi | Ayrı depo, ayrı MCP sunucusu (`pcbai`); ortak kod önce kopya | CadAI yapısı bozulmaz |

### 3.5 Klasör yapısı (depo)

```text
PcbAi/
├─ PLAN.md · AGENTS.md · README.md · LICENSE · SECURITY.md · pyproject.toml
├─ pcbai/
│  ├─ service/        HTTP servis (127.0.0.1 + belirteç), oturumlar, uzun işler, sürüm sayaçları
│  ├─ core/           contract.py, registry.py, args.py, small.py (CadAI'dan uyarlanır)
│  ├─ kicad/          discover.py (soket tarama), ipc.py (kipy sarmalayıcı), cli.py (kicad-cli), files.py (atomik yazım, kilit)
│  ├─ sexpr/          bayt koruyan okuyucu/yazıcı, düğüm düzenleme, KiCad biçimi
│  ├─ ir/             JSON şeması, birim ayrıştırma ("3v3" → 3,3 V, "4k7" → 4700 Ω), doğrulama, hesaplar
│  ├─ blocks/<ad>/    block.json, block.py, sheet.kicad_sch, layout.json, testbench.cir, test_block.py, README.md
│  ├─ parts/          kicad_index.py, catalog.py (JLC SQLite), importer.py (JLC2KiCadLib), verify.py, datasheet.py, rules.py
│  ├─ sch/            model.py (sembol, tel, etiket, sayfa), apply.py (IR → sayfalar), layout.py, edit.py
│  ├─ pcb/            sync.py, outline.py, placement/ (kural + tavlama), routing/ (Freerouting, DSN/SES), zones.py, netclass.py
│  ├─ sim/            ngspice.py (DLL, alt süreç), testbench.py, measure.py, hand_calc.py, plots.py, models/
│  ├─ verify/         erc.py, drc.py, dfm/ (jlcpcb_2l.json, jlcpcb_4l.json → .kicad_dru), design_checks.py
│  ├─ fab/            gerber/drill/pos/bom, JLC BOM/CPL + dönüş düzeltmesi, zip + manifest
│  ├─ report/         evidence.py (kanıt kaydı), design_report.py (MD + HTML)
│  ├─ workflow/       design_board durum makinesi, onay kapıları
│  ├─ markers.py · history.py · external.py · config.py
│  └─ tools/          MCP araç tanımları (gruplar hâlinde)
├─ mcp_server/pcbai_mcp.py   MCP vekili (yalnızca stdlib)
├─ kicad_plugin/             isteğe bağlı IPC eklentisi: plugin.json + araç çubuğu düğmesi
├─ vscode/pcbai-vscode/      VS Code eklentisi
├─ benchmark/                P1…P6: problem.md, requirements.json, checks.py, reference/ (elle çizilmiş çözüm); run.py
├─ docs/                     baseline.md, spikes/S1…S7.md, ir.md, blocks.md, tools.md, decisions/ (karar kayıtları)
└─ tests/                    unit/ (KiCad gerekmez), cli/ (kicad-cli), sim/ (ngspice), live/ (KiCad GUI)
```

### 3.6 Kullanıcı projesinde PcbAi'nin yazdıkları

```text
Kartim/
├─ Kartim.kicad_pro · Kartim.kicad_sch · Kartim.kicad_pcb · <blok alt sayfaları>.kicad_sch
└─ pcbai/
   ├─ requirements.json   gereksinimler (set_requirements)
   ├─ circuit.ir.json     son uygulanan IR + IR kimliği ↔ sembol UUID eşlemesi
   ├─ state.json          tasarım durumu (design_board nerede kaldı)
   ├─ markers.json        işaretler (HMAC imzalı)
   ├─ evidence.jsonl      ölçüm kayıtları (rapor bunlardan üretilir)
   ├─ lib/                pcbai.kicad_sym, pcbai.pretty/, 3dmodels/, spice/ (kütüphane tablosuna ${KIPRJMOD} ile eklenir)
   ├─ sim/                testbench'ler, sonuçlar, grafikler
   ├─ fab/v<n>-<tarih>/   üretim çıktıları + manifest.json (karmalar, tasarım revizyonu)
   └─ report/             design_report.md / .html
```

### 3.7 Açık editörle dosya çakışması

KiCad diskte değişen dosyayı kaydedilmemiş tamponla birleştirmez. Kural:

- **Yazmadan önce:**
  - PCB (canlı): `board.get_as_string()` diskteki dosyayla aynı değilse kaydedilmemiş değişiklik var → dur, sor.
  - Şematik: KiCad 10'da şematik durumu API'den sorulamaz → kilit dosyası (`~Kartim.kicad_sch.lck`) ve değişiklik
    zamanı; editör açıksa kullanıcıdan kaydetmesi istenir.
- Her yazımdan önce kontrol noktası; yazım atomik; diff okunur (KiCad dosyaları metin).
- **Yazımdan sonra:** PCB'de `revert()` ile yeniden yükleme; şematikte "yeniden yükle" bildirimi.
- KiCad 10'un dış değişikliğe tepkisi ve kilit dosyası adı S3 denemesinde ölçülür; sonuç buraya yazılır.

### 3.8 Oturum ve güvenlik

- Servis yalnızca 127.0.0.1'i dinler; belirteç zorunlu ve sabit zamanlı karşılaştırılır; `service.json` yalnızca kullanıcıya açık.
- Her değiştiren araç hedef taşır (oturum, belge, revizyon); hedef değişmişse işlem yanlış projeye uygulanmaz (CadAI `check_target`).
- Araçlar proje kökü dışına yazmaz; dosya yolları kökün içine çözülür.
- Birden çok KiCad projesi açıksa ajan **tahmin etmez**, kullanıcıya sorar.
- Onay penceresi **çözülmüş araç adı ve argümanlarını** gösterir (`run_kicad_python`, dosya yazan araçlar, indirme).
- Dosyadan, katalogdan ve veri sayfasından gelen metin veridir; `trusted: false` işaretle kod çalıştırma ve yazma onay ister.
- İndirilen kütüphane/model dosyaları `pcbai/lib/` altına gider, SHA-256 ve lisansıyla kaydedilir.
- API anahtarları (JLCPCB, Nexar/DigiKey/Mouser) kullanıcı ayarında; ajana ve kayıtlara gösterilmez.

---

## 4. Veri sözleşmeleri

### 4.1 Araç sonucu

Her araç aynı biçimde döner (CadAI sözleşmesi); işlemin durumu ile doğrulamanın durumu ayrıdır:

```json
{"ok": true, "changed": true, "verified": "erc_ok", "summary": "R5: 10k → 4k7",
 "measurements": [{"id": "ev-0142", "quantity": "erc_errors", "value": 0}],
 "warnings": [], "target": {"session": "k1", "document": "Kartim.kicad_sch", "revision": 18}}
```

Ağır değişikliklerde önizleme/uygulama ayrımı: `apply_circuit`, `place_components`, `autoroute` önce
`mode="preview"` ile aday döndürür (`candidate_id`, skor, resim); `mode="apply"` yalnızca önizlenmiş aday kimliğini kabul eder.

### 4.2 Devre IR

**12 Ekim uygulama farkı:** kapalı v1 şema/SI ayrıştırıcı, yerel literal pin/pad/net ön denetimi,
`plan_circuit`, üç olgunluk-0 pasif tarif ve sekiz `hand_calc` hesabı mevcut.
**13 Ekim farkı:** `spice_block_test` bu üç tarifin ideal topolojisini gerçek ngspice ile
el hesabına kıyaslar; olgunluk/şematik/ERC/CI ve fiziksel kabul kapıları açık kalır.
[Gerçek sözleşme](docs/ir.md), [ölçümler](docs/status.md). Aşağıdaki tam ürün örneği/hedefi
henüz desteklenmiyor: buck/STM32/USB/röle, stok/AF/güç bütçesi, çoklu sayfa apply kabulü açık.

```json
{
  "ir_version": 1,
  "requirements": {"vin": "9-24 V", "board_mm": [50, 40], "layers": 2, "fab": "jlcpcb", "assembly": "smt", "budget_usd": 15},
  "rails": {"+5V": {"from": "PWR.vout"}, "+3V3": {"from": "LDO.vout"}, "GND": {"ground": true}},
  "blocks": [
    {"id": "PWR", "block": "buck_regulator", "params": {"vin_max": 24, "vout": 5.0, "iout": 1.5}},
    {"id": "LDO", "block": "ldo", "params": {"vin": "+5V", "vout": 3.3, "iout": 0.3}},
    {"id": "MCU", "block": "stm32_min", "params": {"part": "STM32G431CBU6", "hse_mhz": 8, "swd": true}},
    {"id": "USB", "block": "usb_c_device", "params": {"esd": true}},
    {"id": "K",   "block": "relay_driver", "params": {"coil_v": 5, "count": 2}}
  ],
  "parts": [{"id": "J3", "symbol": "Connector:Screw_Terminal_01x02", "role": "röle kontak çıkışı", "verified": false}],
  "connections": [["USB.DP", "MCU.PA12"], ["USB.DM", "MCU.PA11"], ["K.IN1", "MCU.PB0"], ["K.IN2", "MCU.PB1"],
                  ["K.COM1", "J3.1"]],
  "constraints": [{"edge": "USB.J1", "side": "left"}, {"keepout_mm": 3, "around": "K"}],
  "assumptions": ["Röle kontakları ≤ 24 V DC"]
}
```

`plan_circuit` IR'yi dört aşamada doğrular ve **hiçbir dosya yazmaz**:

1. **Şema:** JSON Schema; birimler ayrıştırılır; bilinmeyen alana öneri ("vout_v" → "vout").
2. **Başvuru:** blok var mı, port/pin var mı (MCU pinleri sembolden ve ST'nin pin verisinden), net adları çakışıyor mu.
3. **Elektrik:** gerilim alanı uyumu (5 V çıkış → 3,3 V pine), akım bütçesi (ray başına toplam ≤ kaynak), pin işlev
   çakışması (alternatif fonksiyon tablosu), eksik güç/toprak, sürülmeyen giriş, rayın tek kaynağı olması.
4. **Hesap:** blok değerleri (E serisine yuvarlama), kayıplar, ısı tahmini (LDO kaybı = (Vin − Vout)·I).

Çıktı: hesaplanmış değerler + uyarılar + eksikler + **kullanıcıya sorular** (belirsiz gereksinim).

### 4.3 Blok

```text
pcbai/blocks/ldo/
├─ block.json       kimlik, sürüm, kategori, parametre şeması, portlar (power_in/power_out/signal/analog/diff),
│                   varsayılan parçalar (KiCad sembol + footprint + LCSC, alternatifler), geçme ölçütleri, olgunluk
├─ block.py         compute(params) → değerler, parça seçimi, SPICE alt devresi; el hesabı formülleri (hand_calc ile ortak)
├─ sheet.kicad_sch  okunur çizilmiş alt sayfa; değerler yer tutucu (${R1_VALUE}); portlar = hiyerarşik etiketler
├─ layout.json      küme içi göreli yerleşim (U merkez, Cin solda ≤ 2 mm, Cout sağda ≤ 2 mm), dönüşler, yasak alan
├─ testbench.cir    kaynak, yük ve ölçüm (.meas) şablonu
└─ test_block.py    tek başına: ERC=0, SPICE geçti, SPICE ↔ el hesabı %5 içinde
```

**Olgunluk:** 0 taslak · 1 ERC + SPICE + el hesabı geçti (CI'da) · 2 gerçek kartta ölçüldü (ölçüm `README.md`'de).
Raporda her bloğun olgunluğu yazılır; olgunluğu 0 olan blok "doğrulanmamış" uyarısıyla kullanılır.

### 4.4 İşaret

```json
{"n": 2, "kind": "line", "space": "pcb", "layer": "F.Cu", "points_mm": [[12.0, 30.5], [25.0, 30.5]],
 "item": {"type": "track", "uuid": "…"}, "note": "bu hat 1 mm olsun", "trusted": true, "revision": 18}
```

- PCB: nokta, çizgi, alan, öğe (footprint/pad/iz). Şematik: sembol, pin, net, alan (`space: "sch"` + sayfa yolu).
- `pcbai/markers.json` içinde, HMAC ile imzalı; dosyayla dışarıdan gelen işaret `trusted: false` olur (CadAI kuralı).
- Model değişince kopan işaret (öğe silinmiş) kullanıcıya gösterilir; tahminle yeniden bağlanmaz.

### 4.5 Gereksinimler ve kanıt kaydı

- `requirements.json`: her gereksinim bir denetime bağlanır (`board_mm` → kart çerçevesi ölçümü; `vout` → SPICE
  `.op`; `budget_usd` → BOM maliyeti).
- `evidence.jsonl` satırı: `{id, time, tool, check, inputs_hash, files: {sch: <dosya SHA-256>, pcb: <dosya SHA-256>}, quantity,
  value, unit, limit, pass}`.
- Rapordaki her sayı bir `ev-…` kimliğine bağlıdır; kimliği olmayan sayı rapora giremez (B3).

### 4.6 Tasarım durumu

`pcbai/state.json`: aşama (gereksinim → mimari → parça → şematik → simülasyon → PCB → çıktı), her aşamanın sonucu,
bekleyen onay kapısı, son hata. Ajanın bağlamı sıfırlansa da `design_status` ile kaldığı yerden devam edilir (küçük
modeller ve uzun oturumlar için).

---

## 5. Alt sistemler: nasıl yapılacak

### 5.1 KiCad erişim katmanı (`pcbai/kicad/`)

- `discover.py`: soket/kanal tarama, `ping`, `get_version` (≥ 10.0.6 değilse uyarı), `get_open_documents`, `get_project`.
- `ipc.py`: kipy üzerine ince katman. Her PcbAi değişikliği `begin_commit` … `push_commit` arasındadır (hata olursa
  `drop_commit`) → KiCad'de tek geri al adımı. Ayrıca seçim, `get_as_string`, `revert`, `refill_zones`, net
  sınıfları, katman yığını.
- `cli.py`: kicad-cli sarmalayıcıları; her biri JSON ya da dosya döndürür, geçici klasöre yazar, zaman aşımlıdır.
- `files.py`: atomik yazım, kilit dosyası, kaydedilmemiş değişiklik denetimi, proje kökü sınırı.
- KiCad 11 geldiğinde değişen yalnızca bu katman ve şematik için `sch/` olur.

### 5.2 S-expr okuyucu/yazıcı (`pcbai/sexpr/`)

- **Koşul:** oku → değiştirmeden yaz = aynı bayt. Düzenleme yalnızca değişen düğümün baytlarını değiştirir; diff küçük kalır.
- **Yöntem:** somut sözdizimi ağacı; her belirteç önündeki boşluk ve satır sonuyla saklanır. Düzenleme API'si: yol
  ya da UUID ile bul, atom değiştir, çocuk ekle/sil. Yeni düğümler KiCad 10'un yazdığı biçimde (sekme girintisi,
  satır kırılımları) yazılır; biçim kuralları demo dosyalarından çıkarılıp testle sabitlenir.
- **Test verisi:** KiCad ile gelen demo projeler ve şablonlar (`share\kicad\demos`, `template`) → %100 gidiş-dönüş.
  Rastgele düzenleme testi: düzenlenen dosya `kicad-cli sch erc` / `pcb drc` ile hatasız açılmalı.
- **Şematik tuzakları (her biri ayrı test):** eklenen sembolün tanımı `lib_symbols` içine kopyalanır; UUID'ler
  benzersiz; alt sayfa örnekleri (`instances`, sayfa yolu) ve referanslar; çok birimli semboller (`unit`);
  döndürme/aynalamada pin konumu; bağlantı yalnızca uç noktalar tam çakışınca oluşur (1,27 mm ızgara); üç tel
  birleşiminde bağlantı noktası (junction); güç sembolleri (`#PWR`) ve ERC için `PWR_FLAG`; hiyerarşik etiket ↔
  sayfa pini eşleşmesi.

### 5.3 Parça servisi (`pcbai/parts/`)

Sıra (çevrimdışı önce, uydurma pin yasak):

1. **KiCad kütüphaneleri:** ilk açılışta sembol ve footprint dizini çıkarılır (ad, açıklama, anahtar sözcük, veri
   sayfası, footprint filtresi) → SQLite FTS5 (`%LOCALAPPDATA%\PcbAi\index.db`).
2. **JLC kataloğu:** çevrimdışı veritabanı (jlcparts ya da kicad-jlcpcb-tools'un yayımladığı SQLite; S6 seçer):
   stok, fiyat kademesi, basic/extended, paket, LCSC numarası. Büyük olduğu için (jlcparts ~620 MB indirme, ~5 GB
   disk) kullanıcı onayıyla indirilir, haftalık yenilenir. JLCPCB resmi API'si anahtar ister ve yalnızca LCSC
   numarasından ayrıntı verir; anonim erişim Temmuz 2026'dan beri kapalı (kicad-tools README'sine göre).
3. **Getirme:** KiCad'de karşılığı yoksa JLC2KiCadLib ile sembol + footprint + 3B model `pcbai/lib/` altına; proje
   kütüphane tablolarına `${KIPRJMOD}` ile eklenir. easyeda2kicad (AGPL) yalnızca kullanıcı isterse ayrı süreçte.
4. **İsteğe bağlı, anahtarlı:** Nexar/Octopart, DigiKey, Mouser.

**Eşleştirme:** pasiflerde (R, C, L, LED) KiCad'in genel sembolü + paketten footprint (`0603` →
`Resistor_SMD:R_0603_1608Metric`); entegrede önce MPN'si KiCad kütüphanesinde olan sembol (ör.
`Regulator_Linear:AMS1117-3.3`), yoksa içe alma.

**`verify_part`:**
- Sembol pin sayısı = footprint pad sayısı; pin numarası ↔ pad eşleşmesi; birden çok pad'li pinler (açık ped vb.).
- Pin adları ↔ veri sayfası pin tablosu (pypdf ile metin, ayrı süreçte); eşleşmezse **uyarı + kullanıcı onayı**.
- Güç/toprak pinlerinin hepsi bağlı mı; açıkta bırakılmaması gereken pin var mı.
- Paket ölçüsü ↔ 3B model sınır kutusu; yaşam döngüsü (aktif/NRND/EOL); stok ≥ adet × kart sayısı.

**`rules.py`:** E serisi, tolerans, MLCC'de gerilim payı ve DC kutuplama düşümü, dirençte güç payı (P ≤ %50 anma),
diyot/MOSFET akım-gerilim payları. Her kural testli.

### 5.4 Şematik üretimi (`pcbai/sch/`)

- **Kök sayfa:** her blok bir sayfa sembolüdür. Bloklar sinyal akışına göre sütunlara dizilir (giriş/koruma → güç →
  çekirdek → arayüzler → çıkışlar); sayfa pinleri kısa tel + etiketle bağlanır. Raylar (+3V3, GND) her sayfada güç sembolüdür.
- **Blok sayfası:** `sheet.kicad_sch` kopyalanır (örnek başına ayrı dosya: `K1_relay.kicad_sch`), yer tutucular
  hesaplanan değerlerle doldurulur, referanslar yeniden numaralanır, yerel netlere blok öneki verilir.
- **Serbest parçalar** (IR `parts`): "Diğer" sayfasına ızgara yerleşimi, her pine kısa tel + etiket; "doğrulanmamış" işaretli.
- **Kararlı numaralama:** IR kimliği ↔ sembol UUID eşlemesi `circuit.ir.json`'da; yeniden uygulamada R7 yine R7 kalır.
- **Artımlı yeniden uygulama:** yeni IR ile eskisinin farkı alınır, yalnızca değişen bloklar yeniden yazılır.
  Kullanıcının elle değiştirdiği sayfa (karması son uygulamadan farklı) değişecekse önce sorulur.
- **Her yazımdan sonra ERC;** ihlaller sayfa + konumla döner, VS Code'da işaret olur. Düzeltme döngüsü en çok 5 tur, sonra kullanıcıya.
- **Düzenleme araçları:** `add_symbol`, `connect` (etiketle), `add_label`, `set_value`, `replace_part` aynı yazıcıyı kullanır.

### 5.5 Blok kütüphanesi (`pcbai/blocks/`)

İlk 11 blok kıyas setinin beş problemini kapsar (Faz 3):

| Blok | Parametreler | Hesap | Geçme ölçütü |
|---|---|---|---|
| `connector` | tür (pin başlığı, JST, vidalı klemens), pin sayısı, akım | Akıma göre klemens | ERC; parça KiCad kütüphanesinde |
| `usb_c_power_sink` | akım, ESD | CC1 ve CC2'ye ayrı 5,1 kΩ (Rd) | `.op`: 56 kΩ Rp'li kaynakla CC gerilimi 0,25–0,61 V |
| `ldo` | vin, vout, iout | Pd = (Vin−Vout)·I, Tj tahmini, Cin/Cout veri sayfasından | Vout ±%2 (300 mA'de); yük basamağında çökme < %5; Tj < 125 °C |
| `led_indicator` | besleme, renk (Vf), akım | R = (Vs−Vf)/I, E24, direnç gücü | LED akımı ±%10 |
| `ne555_astable` | f, doluluk | f = 1,44/((R1+2R2)·C), doluluk = (R1+R2)/(R1+2R2) | `.tran`: f ±%10, doluluk ±5 puan |
| `stm32_min` | parça, HSE, SWD, BOOT0 | Her VDD'ye 100 nF + 4,7 µF, VDDA filtresi, kristal yük kapasitörü | Kural: her VDD/VDDA pininde dekuplaj; BOOT0/NRST bağlı; SWD pinleri başlıkta |
| `button_debounce` | τ, çekme yönü | RC | `.tran`: çıkış 5τ'da %99 |
| `relay_driver` | bobin V/I, adet, lojik seviye | NPN/N-MOSFET, taban/geçit direnci, flyback diyot | `.tran`: kapanışta bobin gerilimi < Vbobin + 1 V; transistör akım payı ≥ 2× |
| `opamp_single_supply` | kazanç, bant, besleme | Rf/Rg (E96), Vcc/2 ön gerilim, GBW gereksinimi = G·fH | `.ac`: kazanç ±1 dB, −3 dB noktaları; çıkış DC = Vcc/2 ±%5 |
| `electret_mic_bias` | kapsül akımı, besleme | Bias direnci, kuplaj kapasitörü | `.op`: kapsül gerilimi aralıkta; `.ac`: alt kesim ≤ 20 Hz |
| `rc_filter` | fc, tür | R, C (E serisi) | `.ac`: fc ±%5 |

Faz 4'te eklenecekler (toplam 20'yi geçer):

- `usb_c_device` (USB 2.0 + ESD, ör. `USBLC6-2SC6`), `reverse_polarity_pmos` (ters polaritede akım < 1 µA),
  `input_protection` (sigorta + TVS; Vrwm ≥ Vin_max), `buck_regulator` (Vout ±%2, ripple < 50 mV).
- `crystal` (C1 = C2 = 2·(CL − Cstray)), `i2c_pullup` (Rp_min = (VDD − 0,4 V)/3 mA, Rp_max = tr/(0,8473·Cb);
  `.tran`: yükselme süresi 100 kHz'de < 1000 ns, 400 kHz'de < 300 ns).
- `uart_usb_bridge`, `can_transceiver` (120 Ω sonlandırma), `rs485` (boşta diferansiyel gerilim > 200 mV),
  `adc_input_divider` (oran ±%1, örnekleme süresinde oturma).
- `h_bridge_driver`, `esp32_module` (EN RC, IO0, anten yasak alanı), `mosfet_low_side`, `sallen_key`.

Kütüphanede olmayan devre için LLM IR'ye serbest parça/net yazabilir; araç bunu **"doğrulanmamış"** diye işaretler,
ek ERC/SPICE ister ve raporda ayrı gösterir.

### 5.6 Simülasyon (`pcbai/sim/`)

1. **Motor:** KiCad'in `ngspice.dll`'i ctypes ile ayrı bir alt süreçte yüklenir (kod modelleri `lib\ngspice\*.cm`).
   Çökme ya da takılma servisi etkilemez; zaman aşımı var. Ayrı ngspice konsolu ayarlanırsa o da kullanılabilir.
2. **Netlist:** (a) blok testi: `block.py` alt devreyi seçilen değerlerle yazar, `testbench.cir` kaynak/yük/ölçüm
   ekler; (b) tüm devre: `kicad-cli sch export netlist --format spice`. Sembollerin `Sim.*` alanlarını PcbAi doldurur;
   modeli olmayan sembol listelenir, sessizce atlanmaz.
3. **Analizler:** `.op`, `.tran`, `.ac`, `.dc`, `.meas` → sayılar (Vout, ripple, faz payı, kesim frekansı, kayıp güç).
4. **Sonuç:** ölçülen değer + ölçüt + geçti/kaldı + grafik PNG (matplotlib, Agg); ajan grafiğe bakar. Her sonuç bir kanıt kaydıdır.
5. **Model zinciri:** kendi davranışsal modellerimiz (depoda, lisansı bizde) → KiCad `Simulation_SPICE` → üretici
   modeli (kullanıcı onayıyla indirilir, `pcbai/lib/spice/` altına, lisansı not edilir; çoğu yeniden dağıtılamadığı
   için depoya girmez) → ideal model **"yaklaşık"** etiketiyle. Uydurma model parametresi yok.
6. **El hesabıyla kıyas (`hand_calc`):** bölücü, RC kesim, LDO kaybı, buck ripple, I²C Rp, LED direnci, kristal
   kapasitörü, op-amp bandı. SPICE ile %5 içinde olmalı; değilse model ya da formül yanlıştır → bulgu.
7. **İleri (Faz 4):** `.step` parametre taraması, Monte Carlo (tolerans), sıcaklık taraması.

Sınır: SPICE devre davranışını doğrular, **layout etkisini değil** (parazitik, SI/PI, EMC). Bunlar için kaba hesap
(iz genişliği IPC-2152, mikroşerit empedansı, akım yoğunluğu) raporlanır ve "alan çözücünün yerine geçmez" yazılır.

### 5.7 PCB: senkron, çerçeve, yerleşim (`pcbai/pcb/`)

**Senkron (`sync_pcb`, KiCad 10):** `kicad-cli sch export netlist` (kicadsexpr) → karttaki footprint'lerle sembol yolu
(`path`) üzerinden fark → yeni footprint'ler kütüphanedeki `.kicad_mod`'dan kopyalanır (referans, değer, alanlar,
yol, pad netleri), değişenler güncellenir, silinecekler sorulur → dosyaya yazılır → canlı modda `revert()`.
**Doğrulama:** `kicad-cli pcb drc --schematic-parity` → uyumsuzluk 0. KiCad 11'de `import_netlist` ile değiştirilir.

**Çerçeve:** dikdörtgen ya da köşesi yuvarlatılmış çerçeve, DXF'ten ya da CadAI'dan gelen dış hat; montaj delikleri
(M3: 3,2 mm, çevresinde yasak alan); kutudan gelen yasak alanlar.

**Yerleşim:**
- (a) **Kural tabanlı başlangıç:** IR kısıtları (konnektör kenara, yasak alanlar); her blok bir küme olarak kendi
  `layout.json`'ıyla neredeyse hazır gelir (dekuplaj pine yakın, kristal MCU'ya yakın, buck sıcak döngüsü küçük).
- (b) **İyileştirme:** kümeler ve tek parçalar üzerinde benzetimli tavlama. Maliyet = net başına yarım çevre tel
  uzunluğu + ratsnest kesişmesi + avlu (courtyard) çakışması + kural cezası (dekuplaj mesafesi, kenar, yasak alan,
  ısıl ayrım) + kaplanan alan. Sabit tohum, süre sınırı, birkaç aday.
- (c) **Yasallaştırma:** ızgaraya oturtma, avlu çakışması 0, yalnızca izin verilen yüz.
- (d) **Önizleme:** geçici kopyada SVG + 3B PNG + skor dökümü; ajan resme bakar; kullanıcı onaylar ya da işaretle düzeltir.
- (e) **Uygulama:** canlı modda tek IPC commit (taşı/döndür/çevir).
- **Karşılaştırma motoru:** kicad-tools'un yerleşim optimizasyonu (MIT) ve TraceMaker-place (GPL, ayrı program) aynı kıyas
  setinde ölçülür; iyi olan seçilir (K5). TraceMaker-place ölçütü tutturursa (b) tavlaması yazılmaz
  ([plan](docs/plan-rota-yerlesim.md) bölüm 6).
- **Ölçülen denetimler** (optimizasyona güvenilmez): dekuplaj ped–pin mesafesi, konnektör avlusunun kenara uzaklığı,
  kristal–MCU mesafesi, anten yasak alanının boşluğu, buck sıcak döngü alanı (yaklaşık çokgen).

### 5.8 Rota ve döküm (`pcbai/pcb/routing/`, `zones.py`)

1. **Net sınıfları:** güç (genişlik akımdan, IPC-2152), varsayılan sinyal, USB diferansiyel çift (90 Ω için katman
   yığınından yaklaşık genişlik/aralık, "yaklaşık" etiketli). Alt sınırlar DFM profilinden.
2. **Döküm:** GND dökümü (alt, gerekirse üst), dikiş viaları, ısıl bağlantılar; damla uçlar KiCad ayarıyla.
3. **Freerouting hattı (kopya üzerinde):** KiCad'in Python'u + `pcbnew` ile DSN dışa aktarma → `freerouting-cli`
   (`-de` / `-do`; bayraklar S4'te doğrulanır) → SES → `pcbnew` ile kopyaya içe aktarma → döküm doldurma + DRC.
4. **Ölçüm:** rotalanmamış bağlantı, via sayısı, toplam uzunluk, DRC hataları → önizleme.
5. **Uygulama:** canlı modda kopyadaki iz/via'lar tek IPC commit ile eklenir (tek Ctrl+Z); dosya modunda kontrol
   noktası + değiştirme.
6. **Geri besleme:** rotalanmamış bağlantı kalırsa sıkışık bölgeler raporlanır → yeniden yerleşim (en çok 3 tur) → kullanıcı.
7. **Alternatifler:** TraceMaker route (S10, motor bağdaştırıcısı `pcbai/pcb/engines/`, [plan](docs/plan-rota-yerlesim.md));
   Faz 5c'de ölçülür: Freerouting'in KiCad 10 IPC modu, kicad-tools A* rotası. KiCad 11'de SWIG
   kalkınca DSN/SES için Freerouting IPC ya da kendi DSN yazıcımız.

### 5.9 Doğrulama ve DFM (`pcbai/verify/`)

- **ERC/DRC:** kicad-cli JSON → ortak bulgu biçimi `{severity, type, text, position_mm, items, sheet}` → VS Code işareti.
- **DFM = profilden üretilen kural dosyası:** `dfm/jlcpcb_2l.json` (min iz/aralık, halka, delik, via, delik-delik,
  bakır-kenar, serigrafi, maske köprüsü) → `.kicad_dru` özel kuralları → geometriyi KiCad'in DRC'si ölçer. Profil
  değerleri üreticinin yayımladığı yeteneklerden tarihiyle alınır.
- **Tasarım denetimleri (bizim):** her güç pininde dekuplaj, I²C hatlarında pull-up, USB-C CC dirençleri,
  kullanılmayan MCU pinleri, güç bütçesi, doğrusal regülatör ısısı, polariteli parçalarda serigrafi işareti, montaj delikleri.
- Her bulgu: ölçülen değer + sınır + konum + kanıt kimliği.

### 5.10 Üretim çıktıları (`pcbai/fab/`)

- kicad-cli: Gerber, delik (PTH/NPTH ayrı), konum (CSV, mm), BOM (`sch export bom`, LCSC alanıyla), STEP (CadAI için
  `--user-origin` ile konum dosyasıyla aynı koordinatlar), isteğe bağlı IPC-2581/ODB++.
- JLC biçimi: BOM (Comment, Designator, Footprint, LCSC), CPL (Designator, Mid X/Y, Layer, Rotation) + dönüş
  düzeltme tablosu (kicad-jlcpcb-tools'tan atıfla); son kontrol JLC'nin önizlemesinde insanda.
- `pcbai/fab/v<n>-<tarih>/` + `manifest.json` (dosya karmaları, proje içerik revizyonu; varsa kaynak git commit'i ayrıca).
- **Çıktı kapısı:** ERC=0, DRC=0 (döküm doldurulmuş), parite=0, her BOM satırında LCSC ve yeterli stok; değilse
  "üretime hazır değil" + nedenler.

### 5.11 Kanıtlı tasarım raporu (`pcbai/report/`)

- Gereksinim ↔ kanıt tablosu: gereksinim, denetim, ölçülen, sınır, sonuç, kanıt kimliği.
- Kullanılan bloklar ve olgunlukları; doğrulanmamış parça/bloklar ayrı başlıkta.
- SPICE grafikleri; ERC/DRC/DFM özeti; BOM + maliyet (katalog fiyatı, tarihiyle).
- Varsayımlar ve sınırlar (layout etkisi simüle edilmedi vb.); "zor" sınıftaki kartta insan incelemesi gereken maddeler.
- Biçim: Markdown + HTML; şematik PDF (`sch export pdf`) ve kart resimleri (`pcb render`) ekli.

### 5.12 MCP sunucusu ve araçlar

- `pcbai_mcp.py`, CadAI'ın `cadai_mcp.py`'sinden: servis keşfi/başlatma, araç vekilliği, `readOnly`/`destructive`
  açıklamaları, `structuredContent`, kaynaklar, istemler, araç kümeleri (`PCBAI_TOOLSET=small|full|small+sim…`).
- **MCP `instructions` metni** (CadAI'daki gibi): önce incele, sonra değiştir, sonra ölç; yalnızca araçların
  döndürdüğü sayıları raporla; birden çok oturumda tahmin etme; işaretlerde önce `get_markers`.
- **Kaynaklar:** `pcbai://status`, `pcbai://requirements`, `pcbai://ir`, `pcbai://markers`, `pcbai://report`.
- **İstemler** (Claude Code'da eğik çizgi komutu olur): `design_board`, `apply_markers`, `review_board`, `fix_erc`, `fix_drc`.

| Grup | Araçlar |
|---|---|
| Oturum/inceleme | `pcbai_status`, `select_session`, `refresh_context`, `project_summary`, `list_symbols`, `list_nets`, `net_info`, `list_footprints`, `get_selection`, `get_markers`, `job_status` |
| Gereksinim/akış | `set_requirements`, `check_requirements`, `design_status` |
| Bloklar/IR | `circuit_blocks`, `plan_circuit`, `apply_circuit` (önizle/uygula) |
| Parça | `search_parts`, `part_info`, `import_part`, `verify_part`, `bom_cost` |
| Şematik | `add_symbol`, `connect`, `add_label`, `set_value`, `replace_part`, `erc` |
| Simülasyon | `spice_block_test`, `spice_simulate`, `spice_sweep`, `hand_calc` |
| PCB | `sync_pcb`, `set_board_outline`, `add_mounting_holes`, `place_components` (önizle/uygula), `move_footprint`, `route_net`, `autoroute` (önizle/uygula), `add_zone`, `set_netclass`, `drc`, `dfm_check`, `design_checks` |
| Çıktı | `export_fab`, `render_board`, `schematic_pdf`, `design_report` |
| Geçmiş | `checkpoint`, `design_history`, `restore_checkpoint` |
| Kaçış kapısı | `run_kicad_python` (IPC API, ayrı süreç, onaylı) |

Küçük model çekirdeği (~13): `project_summary`, `design_status`, `circuit_blocks`, `plan_circuit`, `apply_circuit`,
`search_parts`, `erc`, `spice_block_test`, `sync_pcb`, `place_components`, `autoroute`, `drc`, `export_fab`. Diğerleri
kullanıcının mesajındaki sözcüklerle eklenir (CadAI `small.py`).

### 5.13 VS Code eklentisi (`vscode/pcbai-vscode/`)

> Ayrıntılı ve öne alınmış plan (11 Ekim 2026): [docs/plan-gorunum.md](docs/plan-gorunum.md) — kart/şematik/3B görünümü,
> işaretler (G0–G6, ~5 hafta) ve KiCad eklentisinin PCM paketi olarak kurulması.
> Eksiklerin tamamı ve tamamlama sırası: [docs/plan-eksikler.md](docs/plan-eksikler.md).
> Ajan seçimi (Claude Code, Codex, Cline, Kilo, Copilot…) ve KiCad içi asistan penceresi: [docs/plan-ajan-arayuz.md](docs/plan-ajan-arayuz.md).

CadAI eklentisinin iskeleti (extension.js, bridge.js, mcp_setup.js, agents.js, three.js görüntüleyici, build_vsix.py) uyarlanır.

- **Kart 3B:** `kicad-cli pcb export glb` → three.js; yalnızca kart değişince yeniden üretilir (dosya karması).
- **2B katmanlar:** katman başına kart alanına kırpılmış SVG, üst üste; yakınlaştır/kaydır; tıklanan nokta → mm →
  isabet testi (servis) → öğe; DRC bulguları işaret olarak.
- **Şematik:** sayfa başına `sch export svg`; tıklanan nokta → sembol/pin/net (ayrıştırılmış geometriden); net vurgulama.
- **Çapraz seçim:** bulgu ya da işarete tıklayınca KiCad'de seç (IPC `add_to_selection`, yalnızca PCB).
- **İşaretler:** nokta/çizgi/alan/öğe + not; ajan `get_markers` ile okur.
- **Panel:** ERC/DRC/DFM/SPICE bulguları (tıkla → konuma git), kanıtlar, BOM ve maliyet, kontrol noktası ağacı;
  "Servisi başlat", "MCP'yi ajana ekle" (Claude Code `.mcp.json`, Cline, Kilo, Codex).
- Yenileme servisin sürüm sayaçlarından (`/version`) gelir, gecikmelidir; değişmeyen katman yeniden üretilmez.

### 5.14 Ajan iş akışı (`design_board`)

Servis tarafında bir durum makinesi + MCP istemi. Her aşama `state.json`'a yazılır; onay kapıları kullanıcıdadır.

| Aşama | Ne olur | Kapı |
|---|---|---|
| 1 Gereksinim | Problem → `requirements.json`; belirsizler soru olarak | G1: gereksinimler onaylı |
| 2 Mimari | IR v1 → `plan_circuit`: değerler, güç bütçesi, uyarılar | G2: blok listesi + güç bütçesi |
| 3 Parça | Her blok için varsayılan parça → `verify_part` → BOM maliyeti ↔ bütçe | — |
| 4 Şematik | `apply_circuit` → ERC döngüsü (≤ 5 tur) → şematik PDF | G3: şematik incelemesi |
| 5 Simülasyon | Tüm bloklarda `spice_block_test`; kalan blokta 2. ya da 3. aşamaya dönüş | — |
| 6 PCB | Senkron → çerçeve → yerleşim önizlemesi → rota önizlemesi → DRC/DFM döngüsü | G4: yerleşim (işaretlerle düzeltme) |
| 7 Çıktı | `export_fab` → `design_report` | G5: son insan onayı |

Durma kuralları: aynı hatalı çağrının 3. tekrarında dur (CadAI); döngü sınırı aşılınca kullanıcıya dön; her aşamada
kısa durum raporu ver.

---

## 6. Test ve ölçüm

### 6.1 Katmanlar

| Katman | Ne | Nasıl |
|---|---|---|
| Birim | s-expr gidiş-dönüş (demolar), IR doğrulama, birim ayrıştırma, blok hesapları, `args.py`, MCP vekili | `python -m unittest`, KiCad gerekmez |
| CLI | ERC/DRC JSON, netlist, fab çıktıları, DFM kuralları | kicad-cli; yoksa `skip` |
| SPICE | Blok testbench'leri, el hesabı kıyası | KiCad'in ngspice.dll'i; yoksa `skip` |
| Canlı | IPC ile yerleştirme, commit/geri al, `revert`, kaydedilmemiş değişiklik koruması | Ayrı KiCad ayar klasörü (`KICAD_CONFIG_HOME`, API orada açık), geçici proje; kullanıcının ayarlarına ve projelerine dokunmaz |
| Blok | Her blok ERC=0 + SPICE geçti + el hesabı %5 içinde | CI matrisi |
| Kıyas | `benchmark/` problemleri uçtan uca | Sonuç **dosyadan** denetlenir |
| Model | Claude ve qwen3:8b ile başarı oranı | `PCBAI_EVAL_MODEL=... python benchmark/run.py` |

### 6.2 Kıyas seti

| Kod | Problem | Dosyadan denetlenen ölçütler |
|---|---|---|
| P1 | 9 V pil, NE555 ile 1 Hz yanıp sönen LED; ≤ 30×25 mm | f 1 Hz ±%10; LED akımı ≤ 20 mA; ERC/DRC=0 |
| P2 | USB-C'den 5 V → 3,3 V 300 mA LDO, güç LED'i, 2,54 mm çıkış başlığı; ≤ 25×20 mm, JLC SMT | CC1/CC2'de ayrı 5,1 kΩ; Vout ±%2 @300 mA; Tj tahmini < 125 °C; dekuplaj ≤ 2 mm; ERC/DRC=0 |
| P3 | STM32G431CBU6 minimum kart: USB-C güç, LDO, 8 MHz HSE, SWD başlığı, reset, BOOT0, LED + buton; ≤ 40×30 mm | Her VDD/VDDA'da dekuplaj ≤ 3 mm; HSE yük kapasitörü hesaplı; SWD pinleri başlıkta; ERC/DRC=0 |
| P4 | 12 V giriş, iki 12 V röle (kontaklar ≤ 24 V DC, 5 A), 3,3/5 V lojik girişi, röle başına LED; ≤ 60×40 mm | Her bobinde doğru yönde flyback diyot; transistör akım payı ≥ 2×; kontak hatları IPC-2152 genişliğinde; ERC/DRC=0 |
| P5 | Elektret mikrofon ön yükselteci, tek 5 V besleme, 40 dB, 20 Hz–20 kHz; ≤ 30×20 mm | `.ac`: 1 kHz'de 40 dB ±1 dB, bant sınırları; çıkış DC = Vcc/2 ±%5; op-amp GBW ≥ G·fH·2 = 4 MHz |
| P6 | Bölüm 1'deki problem (12 V, USB-C, STM32, 2 röle, 50×40 mm, JLC) | Uçtan uca gösterim: P2–P4 ölçütlerinin birleşimi + maliyet ≤ bütçe |

Ortak ölçütler: parçalar stokta, kart ölçüsü sağlanmış, maliyet bütçede, rapordaki her sayı kanıtlı.
Her problemde `reference/` altında **elle çizilmiş bir çözüm** bulunur: `checks.py` önce bu çözümde geçmeli, boş
projede anlamlı biçimde kalmalıdır. Böylece denetimin kendisi de test edilmiş olur.

### 6.3 Kıyas koşucusu (`benchmark/run.py`)

1. Şablon projeyi geçici klasöre kopyalar (dosya modu; tekrarlanabilir).
2. Ajanı çalıştırır: Claude Code başsız (`claude -p`, `--mcp-config benchmark/mcp.json`, `--allowedTools "mcp__pcbai"`;
   başsızda onay verilemediği için izin kuralları önceden tanımlanır) ya da yerel model (CadAI'ın ajan döngüsü +
   Ollama `/api/chat`).
3. `checks.py` dosyalardan denetler; sonuç `benchmark/results/<tarih>-<model>.json`: ölçüt başına geçti/kaldı, süre,
   araç çağrısı, belirteç, maliyet.
4. Her problem × model 3 kez koşulur (LLM değişkenliği); başarı oranı raporlanır. Claude koşuları yalnızca faz sonlarında (maliyet).

### 6.4 Gerçek kart doğrulaması

- **Kart 1 (Faz 5 sonu):** P2 (USB-C → 3,3 V), JLC SMT dizgili. Ölçülecekler: yüksüz ve 300 mA'de Vout, LDO
  sıcaklığı, LED akımı.
- **Kart 2 (Faz 7):** P3 ya da P6'nın doğrulanmış v0.6 tasarımı Faz 7 başlamadan dondurulur.
  G5 üretim kapısı ve insanın sipariş onayı sonrası sipariş **Faz 7'nin ilk haftasında** verilir;
  üretim/kargo sürerken orkestrasyon ve rapor geliştirilir. Kart gelince ST-Link ile SWD'den
  yanıp sönen LED yazılımı yüklenir; röleler sürülür. Teslim/yeniden üretim gecikmesi 29–30. hafta
  tamponuna taşınabilir; fiziksel ölçüm yapılmadan v0.8 kart kabulü verilmez.
- Ölçümler blok `README.md`'lerine yazılır → olgunluk 2. Bütçe: kart başına birkaç on dolar + kargo/gümrük (sipariş
  anında JLC fiyatı kontrol edilir).

---

## 7. Çalışma düzeni

- **Depo:** git, `main` + iş paketi dalları (`ip-2.1-sexpr`); küçük commit'ler. GitHub deposu (görünürlük K11).
- **CI (GitHub Actions):** ruff; birim testleri (Python 3.11, 3.13); MCP vekili (3.9/3.11/3.13); eklenti (Node 22);
  CLI ve SPICE testleri Linux'ta KiCad 10 paketiyle; bağımlılık lisans denetimi. Canlı GUI testleri yerelde (Windows).
- **AGENTS.md** (CadAI'daki gibi; Claude Code, Codex, Cline, Kilo için ortak): test komutları, sürüm artırma kuralı,
  testlerde kullanıcının KiCad ayarlarına ve projelerine dokunmama, öğrendikçe eklenen KiCad 10 tuzakları.
- **İş paketi (İP) bitti tanımı:** testler yeşil · ruff temiz · ilgili belge (`docs/ir.md`, `docs/tools.md`…) güncel
  · PLAN.md'de sürüm notu · dokunulan yol kıyas setini etkiliyorsa kıyas yeniden koşulmuş ve ölçüt düşmemiş.
- **Karar kayıtları:** her açık karar kapanınca `docs/decisions/NNNN-<konu>.md` (bağlam, seçenekler, karar, neden).
- **Çapraz kontrol:** hatası pahalı işlerde (s-expr yazıcı, IR şeması, dosya yazan yollar, güvenlik) bağımsız ikinci ajanla
  protokolü: ikinci ajan aynı işi bağımsız planlar ve uygular, farklar deftere yazılır.
- **Sürüm:** 0.x; her faz bir küçük sürüm. Sürüm `pyproject.toml`, MCP `SERVER_INFO`, `package.json` ve
  `plugin.json`'da birlikte artar.

---

## 8. İş planı: fazlar ve iş paketleri

Süreler tek geliştirici + ajanlar için. Her İP'nin sonunda bölüm 7'deki bitti tanımı geçerlidir.

### Faz 0 — Hazırlık, ölçüm, doğrulama denemeleri (2 hafta) → v0.0

- **İP-0.1 Ortam.** KiCad 10.0.4 → 10.0.7; IPC API'yi aç (Tercihler → Eklentiler; `api.enable_server`); Freerouting
  2.5.0 Windows CLI'si (Java gerekmez); servis venv'i (KiCad'in Python 3.11'i + kicad-python 0.8.0); Node 22 (eklenti
  testleri); Ollama servisi + `qwen3:8b`. **Bitti:** `python -m pcbai.doctor` hepsini sürümüyle buluyor.
- **İP-0.2 Depo iskeleti.** git, LICENSE (K1), README, AGENTS.md, SECURITY.md, pyproject (ruff), CI
  (lint + birim). **Bitti:** CI yeşil.
- **İP-0.3 Kıyas seti.** P1–P6: `problem.md`, `requirements.json`, `checks.py`, şablon proje; P2'nin referans çözümü
  KiCad'de elle çizilir. **Bitti:** P2 denetimleri referansta geçiyor, boş projede kalıyor.
- **İP-0.4 Mevcut araçlarla kıyas.** mixelpixx, kicad-mcp-pro, mcp-server-kicad, kicad-copilot, Circuitron (son commit
  Kasım 2025; önce KiCad 10'la çalışıyor mu bakılır), kicad-tools → P1 ve P2. Kaydedilenler: kurulum süresi, ölçüt
  sonuçları, hata türleri (uydurma pin/parça, ERC, okunmaz şematik), süre. **Bitti:** `docs/baseline.md`, en az 4 araç × 2 problem.
- **İP-0.5 Doğrulama denemeleri** (her biri ≤ 1 gün; sonuç `docs/spikes/` altında):

| Kod | Soru | Karar verdiği yer |
|---|---|---|
| S1 | Dışarıdan kipy ile belirteçsiz bağlanılıyor mu; iki KiCad örneğinde soket/kanal adları ne; `get_open_documents` proje yolunu veriyor mu? | KiCad keşfi; eklenti gerekli mi (K10) |
| S2 | En küçük s-expr okuyucu/yazıcı demo dosyalarında bayt bayt aynı yazıyor mu; zor yapılar neler? | K2 kesinleşir |
| S3 | KiCad 10 açıkken şematik/kart diskte değişince ne yapıyor; `revert()` temiz yüklüyor mu; kayıttan sonra `get_as_string()` dosyayla aynı mı; kilit dosyasının adı ne? | Çakışma koruması (3.7) |
| S4 | Demo kartta `pcbnew` DSN → freerouting-cli → SES → içe aktarma → DRC; süre ve bayraklar; Freerouting IPC modu | Rota hattı (5.8) |
| S5 | KiCad'in `ngspice.dll`'i ctypes ile alt süreçte RC `.tran` çalıştırıp vektör döndürüyor mu; kod modelleri yükleniyor mu? | Simülasyon motoru (5.6) |
| S6 | jlcparts ve kicad-jlcpcb-tools veritabanı: indirme/disk boyutu, sorgu hızı, stok tazeliği, kullanım koşulları; JLCPCB resmi API erişimi | Katalog kaynağı (K9) |
| S7 | `pcb export svg/glb` ve `sch export svg` koordinatları mm'ye nasıl eşleniyor? | VS Code görünümleri (5.13) |
| S10 | TraceMaker WSL'de derleniyor mu; demo kartlarda rotalanmamış/DRC/via; `--work` determinizmi; dokunmadığı bayt aynı mı ([plan](docs/plan-rota-yerlesim.md)) | K5, K13 |

- **Kabul (v0.0):** baseline dolu; P2 denetimleri doğrulanmış; S1–S7 yanıtlanmış; K1, K2, K8, K9, K10 kapanmış.

### Faz 1 — Servis, MCP vekili, okuma ve denetim (2 hafta) → v0.1

- **İP-1.1 Ortak çekirdek.** CadAI'dan `contract.py`, `registry.py`, `args.py`, `small.py`, `external.py` (anahtarlar:
  `kicad_cli`, `kicad_python`, `freerouting`, `ngspice`), testleriyle birlikte. **Bitti:** kopyalanan testler geçiyor.
- **İP-1.2 Servis.** CadAI `cadai_core/bridge.py` düzeni: `/health`, `/version`, `/tools`, `/call`, `/ui`; uzun işler
  (`job_status`); tek örnek kilidi; `service.json`. **Bitti:** iki istemci aynı anda çalışıyor; servis düşünce vekil
  yeniden başlatıyor.
- **İP-1.3 MCP vekili.** `cadai_mcp.py` → `pcbai_mcp.py`: keşif/başlatma, araç vekilliği, kaynaklar, istemler, araç
  kümeleri, `instructions`. **Bitti:** uyarlanan `test_mcp_server.py` 3.9/3.11/3.13'te geçiyor; Claude Code ve Cline bağlanıyor.
- **İP-1.4 KiCad keşfi ve oturumlar.** S1'e göre `discover.py`; `pcbai_status`, `select_session`; belirsizlikte sorma;
  dosya modu (VS Code çalışma alanındaki `.kicad_pro`). **Bitti:** iki KiCad açıkken araç tahmin etmiyor (canlı test).
- **İP-1.5 Okuma araçları.** `project_summary` (kart ölçüsü, katman, footprint/net/sembol/sayfa sayıları),
  `list_symbols`, `list_nets`, `net_info`, `list_footprints`, `get_selection`; dosyadan okuma S2 okuyucusuyla.
  **Bitti:** demo projelerde sayılar `kicad-cli pcb export stats` ile aynı.
- **İP-1.6 Denetim ve çıktı (okuma).** `erc`, `drc` (konumlu ortak bulgu biçimi), `render_board`, `schematic_pdf`,
  temel `export_fab` (kopyada). **Bitti:** bilerek bozulmuş bir projede bulgular doğru konumda.
- **İP-1.7 En küçük VS Code eklentisi.** Servisi başlatma, durum çubuğu, "MCP'yi ajana ekle", bulgu listesi.
- **İP-1.8 KiCad eklentisi (yalnızca S1 gerektirirse).** `plugin.json` + "PcbAi'ye bağla" düğmesi.
- **Kabul (v0.1):** ajan açık projeyi doğru özetliyor; ERC/DRC sonuçlarını konumlarıyla veriyor; birden çok proje
  açıkken soruyor.

### Faz 2 — Yazıcı, kontrol noktası, parça, şematik düzenleme (3 hafta) → v0.2

- **İP-2.1 S-expr yazıcı.** Somut sözdizimi ağacı, düzenleme API'si, KiCad biçiminde yeni düğüm; bağımsız ikinci ajanla ile çapraz
  kontrol. **Bitti:** demolarda %100 gidiş-dönüş; rastgele düzenleme testinde kicad-cli dosyaları hatasız açıyor.
- **İP-2.2 Şematik modeli.** Sembol (`lib_symbols` kopyası), tel, bağlantı noktası, etiketler, güç sembolleri,
  `PWR_FLAG`, alt sayfa ve örnekleri, numaralama, döndürmede pin konumu. **Bitti:** 5.2'deki her tuzak için test var.
- **İP-2.3 Kontrol noktası ve çakışma koruması.** İçerik adresli blob + manifest; `checkpoint`, `restore_checkpoint`, `design_history`;
  S3'e göre kilit + kaydedilmemiş değişiklik denetimi; atomik yazım. **Bitti:** canlı testte kaydedilmemiş değişiklik
  varken yazım reddediliyor.
- **İP-2.4 KiCad kütüphane dizini.** FTS5 dizini; `search_parts` (KiCad kaynağı). **Bitti:** "AMS1117 3.3" araması
  `Regulator_Linear:AMS1117-3.3` buluyor.
- **İP-2.5 JLC kataloğu.** S6 kararıyla onaylı indirme ve dizin; `search_parts` (katalog), `part_info`, `bom_cost`.
- **İP-2.6 Parça getirme.** JLC2KiCadLib → `pcbai/lib/`, kütüphane tabloları, 3B modeller, karma + lisans kaydı.
- **İP-2.7 `verify_part`.** Pin/pad, numara, güç pinleri, 3B kutu, yaşam döngüsü, stok; veri sayfası pin tablosu (ayrı süreç).
- **İP-2.8 Şematik düzenleme araçları.** `add_symbol`, `connect`, `add_label`, `set_value`, `replace_part`; her yazımdan sonra ERC.
- **Kabul (v0.2):** P2 şematiğini ajan (henüz IR'siz) araçlarla elle müdahalesiz ERC=0'a getiriyor; her parça LCSC
  numaralı ve stokta; kontrol noktasından geri dönüş çalışıyor.

### Faz 3 — Devre IR, bloklar, blok testi (4 hafta) → v0.3 ← en büyük değer

12 Ekim **Faz 2 yazılım ilerlemesi (0.1.8):** yerel FTS5 araması, katı sembol kalıtımı,
pin/pad yapısal denetimi ve dört önizlemeli şematik aracı eklendi. Gerçek KiCad'de iki direnç
etiketlerle bağlandı, net üyeleri ölçüldü, ERC=0 ve bayt eşit checkpoint geri dönüşü geçti.
Bu Faz 2 kabulü değildir: JLC katalog/getirme/stok, bağımsız veri sayfası/3B, P2 ve canlı
çakışma deneyleri açıktır. Ölçüm ve denetim sınırları [status.md](docs/status.md)'dedir.

- **İP-3.1 IR şeması.** JSON Schema (2020-12), birim ayrıştırıcı, dört doğrulama aşaması; `docs/ir.md`.
- **İP-3.2 Blok çatısı.** `block.json` şeması, `block.py` arayüzü, alt sayfa şablonu + yer tutucu doldurma, olgunluk,
  blok test düzeneği (tek başına ERC + SPICE + el hesabı).
- **İP-3.3 En küçük SPICE çalıştırıcı.** Taslakta Faz 4'teydi; bloklar SPICE'sız test edilemeyeceği için öne alındı.
  S5'e göre `sim/ngspice.py`, testbench üretimi, `.meas` okuma, `spice_block_test`.
- **İP-3.4 `plan_circuit`.** Doğrulama + hesap + güç bütçesi + pin işlev çakışması (STM32 pin/AF verisi: ST'nin
  `STM32_open_pin_data` deposu, lisansı bu İP'de doğrulanır) + sorular.
- **İP-3.5 `apply_circuit`.** IR → alt sayfalar + kök sayfa, numaralama, IR ↔ UUID eşlemesi, artımlı yeniden
  uygulama, elle düzenleme algılama, ERC döngüsü; önizle/uygula.
- **İP-3.6 İlk 11 blok** (5.5'teki tablo), her biri olgunluk 1.
- **İP-3.7 IR onarımı ve küçük model modu.** LLM'lerin sık hataları: pin takma adları (`D+`/`DP`/`USB_DP`,
  `GND`/`VSS`), metin birimler, eksik ray, port yerine pin numarası. Hata mesajı doğru bir IR örneği gösterir.
- **İP-3.8 Model kıyası.** P1–P5'in şematik kısmı: Claude ve qwen3:8b, 3'er koşu.
- **Kabul (v0.3):** P1–P5 şematik kısmı 5/5 ERC=0 ve şematik düzeyi ölçütler geçiyor (Claude); qwen3:8b oranı
  ölçülmüş (hedef ≥ 2/5); 11 blok olgunluk 1.

### Faz 4 — Simülasyon derinleştirme + 20+ blok (3 hafta) → v0.4

- **İP-4.1** Tüm devre SPICE: kicad-cli SPICE netlisti, `Sim.*` alanları, `spice_simulate` (op/tran/ac/dc), grafikler.
- **İP-4.2** Model zinciri: kendi davranışsal modellerimiz, KiCad simülasyon kütüphanesi, onaylı üretici modeli
  indirme + lisans kaydı, "yaklaşık" etiketi.
- **İP-4.3** `hand_calc` aracı (blok formülleriyle ortak).
- **İP-4.4** `spice_sweep`: `.step`, Monte Carlo, sıcaklık.
- **İP-4.5** Kalan bloklar (5.5'teki liste), her biri olgunluk 1.
- **Kabul (v0.4):** buck/LDO/filtre/op-amp bloklarında SPICE ↔ el hesabı %5 içinde; P5 kazancının tolerans dağılımı
  raporlanmış; 20+ blok olgunluk 1.

### Faz 5 — PCB (6 hafta) → v0.5 (5a + 5b), v0.6 (5c)

**5a — Senkron, çerçeve, kurallar (2 hafta)**
- **İP-5.1** `sync_pcb` (dosya + `revert`); doğrulama `--schematic-parity` = 0.
- **İP-5.2** `set_board_outline` (dikdörtgen, yuvarlatılmış, DXF, CadAI'dan), `add_mounting_holes`.
- **İP-5.3** Net sınıfları (IPC-2152), DFM profilleri → `.kicad_dru`, `dfm_check`, `design_checks`.
- **İP-5.4** Elle PCB araçları (IPC): `move_footprint` (taşı/döndür/çevir), `add_zone`, `set_netclass`, `route_net`
  (kısa iki nokta izi; DRC ile doğrulanır).

**5b — Yerleşim (2 hafta)**
- **İP-5.5** Kural tabanlı başlangıç (kenar, küme, `layout.json`, yasak alan).
- **İP-5.6** Benzetimli tavlama + yasallaştırma + skor + adaylar + önizleme; tek commit ile uygulama; kicad-tools ve
  TraceMaker-place ile kıyas (K5). TraceMaker-place benimsenirse yerine `autoplace` + blok kısıtlarını aktarma
  ([plan](docs/plan-rota-yerlesim.md) R6).
- **İP-5.7** Ölçülen yerleşim denetimleri (5.7 sonu) → kanıt.

**5c — Rota, döküm, çıktı (2 hafta)**
- **İP-5.8** `autoroute`: Freerouting (S4) ve TraceMaker (S10) bağdaştırıcıları, yabancı değişiklik denetimi, ölçüm,
  önizleme, tek commit ile uygulama ([plan](docs/plan-rota-yerlesim.md) R3–R5).
- **İP-5.9** Döküm, dikiş viaları, doldurma, damla uçlar.
- **İP-5.10** Rota → yerleşim geri beslemesi (≤ 3 tur).
- **İP-5.11** Son üretim çıktısı: JLC BOM/CPL + dönüş düzeltmesi, çıktı kapısı, manifest.
- **İP-5.12** Gerçek kart 1 siparişi (P2).

**Kabul:** v0.5 — P1–P5 yerleşimi ölçütleri sağlıyor (dekuplaj ≤ 2 mm, konnektörler kenarda, kart ölçüsü);
v0.6 — 5 kartın 4'ü 2 katmanda DRC=0 (döküm doldurulmuş), parite 0, rotalanmamış bağlantı 0; kart 1 sipariş edilmiş.

### Faz 6 — VS Code görünümleri ve işaretler (3 hafta) → v0.7

- **İP-6.1** 3B kart görünümü (GLB, CadAI görüntüleyicisi), artımlı yenileme.
- **İP-6.2** 2B katman görünümü, isabet testi, DRC işaretleri.
- **İP-6.3** Şematik görünümü, net vurgulama, PCB'de çapraz seçim.
- **İP-6.4** İşaretler (PCB + şematik), imza, `get_markers`, `apply_markers` istemi.
- **İP-6.5** Sonuç paneli: bulgular, kanıtlar, BOM/maliyet, kontrol noktası ağacı.
- **Kabul (v0.7):** "#1 bu konnektörü sol kenara al", "#2 bu hat 1 mm olsun", "#3 buraya GND dökümü", "#4
  (şematikte) bu direnç 4,7k olsun" uçtan uca çalışıyor; görünüm testleri başsız tarayıcıda (CadAI `test:viewer` yöntemi).

### Faz 7 — Problemden karta orkestrasyon, rapor, gerçek kart (4 hafta) → v0.8

- **İP-7.0** İlk hafta kart 2 siparişi: v0.6'dan doğrulanıp dondurulmuş P3/P6, güncel ERC/DRC/DFM,
  üretim manifest'i ve G5 insan onayı. Teslim süresi/bütçesi sipariş anında kontrol edilir; geliştirme
  ve ölçüm hazırlıkları üretim/kargo ile paralel yürür. Kart kabulü fiziksel ölçüme bağlı kalır.
- **İP-7.1** `design_board` durum makinesi, `design_status`, G1–G5 kapıları, kaldığı yerden devam.
- **İP-7.2** `design_report` (MD + HTML), kanıt bağları; eksik kanıt varsa rapor üretilmez.
- **İP-7.3** CadAI ile birlikte: STEP → CadAI `kicad_board` → kutu; kutudan dış hat ve montaj delikleri
  `set_board_outline` ile geri yazılır (onaylı); iki MCP sunucusu aynı ajanda test edilir.
- **İP-7.4** Tam kıyas koşusu (Claude + qwen3:8b), P6 gösterimi.
- **İP-7.5** İP-7.0'da sipariş edilen gerçek kart 2: teslim sonrası SWD'den yazılım, ölçüm, blok olgunlukları.
- **İP-7.6** Yayın: README, SECURITY.md, VSIX, kurulum rehberi, kısa demo kaydı.
- **Kabul (v0.8):** Claude ile 5 problemin ≥ 4'ü uçtan uca (ölçütler + rapor); P6'dan üretim dosyası + rapor; kart 2 çalışıyor.

### Faz 8 — KiCad 11 geçişi (KiCad 11 çıkınca, 2–3 hafta) → v0.9

- Şematik IPC API'ye taşınır: canlı düzenleme, yeniden yükleme gerekmez. Senkron `import_netlist` /
  `place_footprint_from_library` ile yapılır.
- Dışa aktarımlar API'den; başsız `kicad-cli api-server` ile CI'da canlı testler; SWIG kaldırılır (DSN/SES yerine
  Freerouting IPC ya da kendi yazıcımız).
- Dosya modu yedek olarak kalır. KiCad 11 adayı (RC) çıkar çıkmaz canlı test takımı ayrı ayar klasöründe ona karşı koşulur.

---

## 9. Takvim (kabaca)

| Hafta | Tarih | Faz | Sürüm |
|---|---|---|---|
| 1–2 | 12–23 Ekim 2026 | Faz 0: hazırlık, kıyas, denemeler | v0.0 |
| 3–4 | 26 Ekim – 6 Kasım | Faz 1: servis, MCP, okuma | v0.1 |
| 5–7 | 9–27 Kasım | Faz 2: yazıcı, parça, şematik düzenleme | v0.2 |
| 8–11 | 30 Kasım – 25 Aralık | Faz 3: IR + 11 blok + SPICE çalıştırıcı | v0.3 |
| 12 | 28 Aralık – 1 Ocak 2027 | Tampon | — |
| 13–15 | 4–22 Ocak | Faz 4: simülasyon + 20+ blok | v0.4 |
| 16–21 | 25 Ocak – 5 Mart | Faz 5: PCB (5a, 5b, 5c) + kart 1 siparişi | v0.5, v0.6 |
| 22–24 | 8–26 Mart | Faz 6: VS Code görünümleri, işaretler | v0.7 |
| 25–28 | 29 Mart – 23 Nisan | Faz 7: ilk hafta kart 2 siparişi (v0.6), orkestrasyon/rapor, teslim sonrası ölçüm | v0.8 (kart ölçümü şartıyla) |
| 29–30 | 26 Nisan – 7 Mayıs | Tampon: kart 2 teslim/yeniden üretim ve ölçüm gecikmesi öncelikli | — |
| — | KiCad 11 çıkınca | Faz 8: geçiş | v0.9 |

Gecikmede kesilecekler sırasıyla: şematik görünümü (İP-6.3) → 4 katman → Monte Carlo → PCBWay profili.
Doğrulama adımları hiçbir zaman kesilmez.

---

## 10. Sonuçta ne elde edilir

| Sürüm | Kullanıcı ne yapabilir |
|---|---|
| v0.1 | Ajana açık projeyi sorar; ERC/DRC bulgularını konumlarıyla alır; render ve PDF ister |
| v0.2 | Sohbetle şematik düzenler (gerçek, doğrulanmış, stokta parçalarla); her adımı geri alabilir |
| v0.3 | Problemden okunur şematiğe ulaşır; bloklar ERC + SPICE testli |
| v0.4 | Her devre kararının simülasyon ve el hesabı kanıtını görür |
| v0.6 | Şematikten yerleşmiş, rotalanmış, DRC temiz karta ulaşır |
| v0.7 | Kartı ve şematiği VS Code'da gösterip işaretle tarif eder |
| v0.8 | Problemden üretim dosyası + kanıtlı rapora ulaşır; CadAI ile kutuyu tasarlar |

| Kart sınıfı | Beklenen sonuç |
|---|---|
| Basit (LED, 555, sensör kırılım kartı, LDO) | Problemden üretim dosyasına, ERC/DRC temiz; kullanıcı yalnızca gözden geçirir |
| Orta (MCU + USB + güç + birkaç G/Ç, 2–4 katman) | Şematik ve parça seçimi büyük ölçüde hazır; yerleşimi kullanıcı işaretlerle düzeltir; rota otomatik + rötuş |
| Zor (yüksek hız, RF, yüksek akım/gerilim, BGA) | Şematik, BOM, kurallar ve denetim raporu hazır; layout ve imza insanda |

---

## 11. Riskler ve önlemler

| Risk | Önlem |
|---|---|
| Uydurma pin/parça | Yalnızca kütüphane/katalog parçası, `verify_part`, veri sayfası pin kıyası, B1 ölçütü |
| Okunmaz şematik | Blok = alt sayfa, blokların elle çizilmiş sayfası; serbest parçada ızgara + etiket |
| Kötü yerleşim → kötü rota | Blok içi hazır yerleşim, skorlu önizleme, işaretle düzeltme, rota → yerleşim geri beslemesi |
| KiCad 11 proje ortasında gelir | İnce erişim katmanı (`kicad/`, `sch/`); dosya modu her zaman yedek; Faz 8 ayrı |
| KiCad'in dış değişikliğe tepkisi belirsiz | S3 ile ölçülür; kaydedilmemiş değişiklik denetimi; kontrol noktası |
| Dosya bozulması | Bayt koruyan yazıcı + gidiş-dönüş testi + atomik yazım + kontrol noktası |
| JLC veri erişimi değişir (anonim erişim Temmuz 2026'da kapandı) | Çevrimdışı veritabanı, anahtarlı resmi API, KiCad kütüphanesiyle çevrimdışı çalışma |
| Freerouting değişir (2.5'te kırıcı bayraklar; sonraki sürümde SWIG gidiyor) | Sürüm sabitlenir, ince bağdaştırıcı, S4 testi CI'da |
| Dış motor karta yabancı değişiklik yazar / CLI'si değişir (TraceMaker genç) | Commit sabitlenir; bayt düzeyinde yabancı değişiklik denetimi uygulamayı engeller |
| SPICE modeli yok ya da yaklaşık | Model zinciri + "yaklaşık" etiketi + el hesabı kıyası; uydurma parametre yok |
| Veri sayfası ayrıştırma güvenilmez | Yalnızca uyarı + onay; tek başına kanıt sayılmaz |
| LLM IR hataları | Dört aşamalı doğrulama, IR onarımı, doğru örnek gösteren hata, küçük model modu |
| İstem enjeksiyonu (parça açıklaması, veri sayfası, işaret notu) | Veri ≠ talimat; `trusted` bayrağı; çözülmüş argümanla onay |
| Lisans bulaşması | Lisans tablosu (2.5), CI'da bağımlılık lisans denetimi, AGPL/GPL kod alınmaz |
| Tek geliştirici, süre | Faz başına kıyas ölçütü; gecikmede kesme sırası (bölüm 9); tampon haftalar |
| Gerçek kart çalışmaz | Amaç zaten bunu yakalamak: ölçüm bloğa yazılır, düzeltilir; iki sipariş turu bütçelenir |
| Kapsam şişmesi | Kıyas ölçütü düşmeden yeni özellik eklenmez |

---

## 12. Açık kararlar

| Kod | Karar | Öneri | Ne zaman |
|---|---|---|---|
| K1 (kapandı) | Lisans | LGPL-2.1-or-later; kullanıcı 11 Ekim 2026'da kabul etti ([karar](docs/decisions/0002-license.md)) | Faz 0, İP-0.2 |
| K2 | S-expr kütüphanesi | Kendi bayt koruyan yazıcımız (kiutils GPL, kicad-skip bakımsız) | S2'den sonra |
| K3 | CadAI ile ortak kod | Önce kopya; iki proje olgunlaşınca ortak paket | Faz 7'den sonra |
| K4 | VS Code eklentisi | Ayrı eklenti; CadAI'ınki bozulmaz | Faz 1 |
| K5 | Yerleşim/rota motoru | TraceMaker, Freerouting, kicad-tools ölçülür; kendi tavlamamız yalnızca adaylar ölçütü tutturamazsa ([plan](docs/plan-rota-yerlesim.md) 6) | S4 + S10 sonrası |
| K6 | Kıyas modelleri | Claude Sonnet 5.5 (ana), Claude Haiku 5.5 (hızlı/ucuz), qwen3:8b (yerel); faz sonlarında Opus 5.5 üst sınır olarak | Faz 0 |
| K7 | Şematik düzeni | Her blok bir alt sayfa | Faz 3 başı |
| K8 | Servis Python'u | KiCad'in Python 3.11'iyle venv | Faz 0 |
| K9 | Katalog kaynağı | S6 sonucuna göre | Faz 0 |
| K10 | KiCad eklentisi gerekli mi | S1 sonucuna göre | Faz 0 |
| K11 | Depo görünürlüğü | v0.3'e kadar özel, sonra açık | v0.3 |
| K12 | TraceMaker lisans sınırı | Ayrı süreç; kod/bağlama/ikili alınmaz, paketlenmez | S10 öncesi |
| K13 | TraceMaker ortamı | WSL2 + Ubuntu, `cpu-only` (kullanıcı kararı: yönetici yetkisi, yeniden başlatma) | S10 öncesi |
| K14 | Kıyas kartları | KiCad demoları + PCBench alt kümesi depo dışında; yalnız sonuç yayımlanır | R7 öncesi |

12 Ekim uygulama kaydı: K12 ayrı süreç/paketlememe sınırı uygulandı; K13 WSL kurulumunu kullanıcı
onayladı, Windows bileşenleri kuruldu ve yeniden başlatma gerekiyor; K14 için kullanıcı **yalnız KiCad
demolarını** seçti. K5 açık. Rota/yerleşim bağdaştırıcıları, güvenlik/DRC kapıları, işler ve VS Code aday
paneli uygulanmıştır; bu durum Faz 5 veya diğer fazların kabulü değildir.
[Karar ve ölçüm sınırları](docs/decisions/0003-engines.md).

---

## 13. İlk iki hafta (12–23 Ekim 2026)

| Gün | İş |
|---|---|
| Pzt 12 | İP-0.1 ortam; İP-0.2 depo iskeleti; K1 kararı |
| Sal 13 | S1 (kipy keşfi), S3 (dış değişikliğe tepki) |
| Çar 14 | S2 (s-expr gidiş-dönüş), S5 (ngspice.dll) |
| Per 15 | İP-0.3: P1–P6 `problem.md` + `requirements.json`; P2 referans çözümü KiCad'de |
| Cum 16 | P2 `checks.py` referansta doğrulanır; S4 (Freerouting) |
| Pzt 19 – Sal 20 | İP-0.4: kıyas koşuları (6 araç × P1, P2) |
| Çar 21 | S6 (katalog), S7 (koordinat eşlemesi) |
| Per 22 | `docs/baseline.md`, karar kayıtları (K1, K2, K8, K9, K10) |
| Cum 23 | Faz 0 kabulü → v0.0; Faz 1 iş paketleri denemelerin sonucuna göre gözden geçirilir |

---

## 14. Sonrası (v1.0 yolu)

- 4 katman ve empedans kontrollü rota yardımı (insan onaylı).
- PCBWay ve diğer üretici profilleri; topluluğun blok eklemesi (blok sözleşmesi + CI).
- Doğrulanmış parça ve blokları KiCad 10'un uzak sağlayıcı arayüzüyle KiCad'in kendi panelinde sunma.
- IR üretimi için küçük model ince ayarı; SchGen ve pcbGPT yöntemleriyle kıyas.
- CadAI ile ortak paket (K3); Fusion/SolidWorks kutu akışı CadAI üzerinden.

---

## 15. Kaynaklar

- KiCad 10: <https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/> · 10.0.7: <https://www.kicad.org/blog/2026/10/KiCad-10.0.7-Release/>
- IPC API: <https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/> · kicad-python:
  <https://pypi.org/project/kicad-python/> · kaynak: <https://gitlab.com/kicad/code/kicad-python>
- KiCad 11 geliştirme haberleri: <https://forum.kicad.info/t/post-v10-new-features-and-development-news/66611>
- MCP sunucuları: <https://github.com/mixelpixx/KiCAD-MCP-Server> · <https://github.com/oaslananka/kicad-mcp-pro> ·
  <https://github.com/ProductOfAmerica/mcp-server-kicad> · <https://github.com/biosshot/kicad-copilot> · <https://github.com/rjwalters/kicad-tools>
- Rota: Freerouting <https://github.com/freerouting/freerouting/releases>
- kicad-happy SPICE: <https://skills.sh/aklofas/kicad-happy/spice> · ltspice-mcp: <https://glama.ai/mcp/servers/Cognitohazard/ltspice-mcp> · py4spice: <https://pypi.org/project/py4spice>
- Parça: JLC2KiCadLib <https://github.com/TousstNicolas/JLC2KiCad_lib> · jlcparts <https://github.com/yaqwsx/jlcparts> ·
  kicad-jlcpcb-tools <https://github.com/Bouni/kicad-jlcpcb-tools> · easyeda2kicad (AGPL) <https://github.com/uPesy/easyeda2kicad.py> ·
  CircuitDK <https://pypi.org/project/circuitdk/0.1.4/> · kicad-jlcpcb <https://www.claudepluginhub.com/plugins/beckhamlabsllc-kicad-jlcpcb>
- Lisansı denetlenen kütüphaneler: kiutils (GPL-3.0) <https://github.com/mvnmgrx/kiutils> · kicad-skip (LGPL-2.1)
  <https://github.com/psychogenic/kicad-skip> · SKiDL (MIT) <https://github.com/devbisme/skidl>
- Araştırma: CircuitLM <https://arxiv.org/abs/2601.04505v1> · PCBSchemaGen <https://arxiv.org/abs/2602.00510v1> ·
  SchGen <https://alphaxiv.org/abs/2605.30345> (kod: <https://github.com/microsoft/SchGen>) · pcbGPT <https://arxiv.org/abs/2606.01188>
- Benzer açık proje: Circuitron <https://github.com/jefcoder/circuitron>
- Ticari: Flux <https://www.flux.ai/p/blog/ai-assistance-inside-every-ecad-tools> · Quilter <https://www.quilter.ai/newsroom/quilter-bga-fanout-automation-2026-releases>

---

## 16. Sürüm notları

### Plan v1 — 10 Ekim 2026

Taslağa göre değişenler:

- **Makine durumu düzeltildi:** kurulu sürüm KiCad **10.0.4** (taslakta 9.0.7 yazıyordu). 10.0.7'ye geçilmesinin
  nedeni `flip_items` (≥ 10.0.6). IPC API bu makinede kapalı.
- **Lisans doğrulaması:** easyeda2kicad AGPL-3.0 → parça getirmenin ana yolu JLC2KiCadLib (MIT). kiutils GPL-3.0 →
  kendi s-expr yazıcımız (K2). CadAI'ın LGPL-2.1+ olduğu not edildi; K1 önerisi buna göre güncellendi.
- **KiCad 10 yetenekleri kaynaktan doğrulandı (2.4):** DSN dışa aktarımı yok; kütüphaneden footprint yerleştirme ve
  netlist içe alma kipy 0.8.0'da yok → senkron dosya + `revert` ile; DRC başsız döküm doldurabiliyor.
- **Mimari:** MCP vekili + ayrı servis (CadAI köprü düzeni); çalışma modları tablosu; bir değişikliğin yolu.
- **Şematik düzeni:** her blok bir hiyerarşik alt sayfa (K7).
- **Bağımlılık hatası düzeltildi:** SPICE çalıştırıcı Faz 3'e alındı; taslakta bloklar Faz 3'te SPICE testli olacaktı
  ama SPICE köprüsü Faz 4'teydi.
- **Faz 3 blokları kıyas setine göre seçildi:** taslağın listesinde P1 için 555, P5 için mikrofon bloğu yoktu.
- **kicad-tools** rakip tablosuna, kıyas setine ve yerleşim motoru adaylarına eklendi. **Freerouting 2.5.0:** Java'sız
  Windows CLI; KiCad 10 IPC modu alternatif.
- **Eklenenler:** veri sözleşmeleri (bölüm 4), doğrulama denemeleri S1–S7, ölçütleri tanımlı kıyas seti ve referans
  çözümler, gerçek kart doğrulaması ve blok olgunluğu, iş paketleri ve bitti tanımı, tarihli takvim, ilk iki hafta.

### İlk çalışan çekirdek 0.1.0 — 10 Ekim 2026

- Ayrı git deposu ve KiCad Python 3.11.5 venv'i kuruldu. CadAI ve kullanıcı KiCad ayarları değiştirilmedi.
- Stdlib yerel servis/MCP, kayıtlı dosya oturumları, şematik/PCB okuma, gerçek ERC/DRC ve PDF uygulandı.
- Önizleme/revizyon bağlı Value düzenleme, tek belge checkpoint ve restore, ham raporla kanıt kaydı eklendi.
- Güvenlik: kullanıcıya özel state ve alt nesne ACL'leri, proje sınırı/junction kontrolü, OS yazma kilidi,
  KiCad proje yöneticisi dahil açık süreç engeli, atomik replace sırasında owner/izin koruması.
- Yerel testler ve gerçek KiCad entegrasyonu çalıştırıldı; nihai sayılar [durum kaydında](docs/status.md).
- Faz 0/1'in tüm kabulü verilmedi: canlı IPC, kıyas, VS Code ve ileriki fazlar açık.
  S2 ölçümü: 162 dosyanın 161'i strict okunuyor, bir tolerans farkı fail closed; [deney kaydı](docs/spikes/S2.md).

### Denetim düzeltmeleri 0.1.1 — 11 Ekim 2026

- Ortak hiyerarşik sayfa örnekleri proje/kök UUID'sinden çözülür; her kopya ayrı listelenir.
  Value önizlemesi tüm etkilenen referansları ve yolları bildirir; çok birimli ortak semboller birlikte güncellenir.
- Kalıcı OS kilidi özel durumun `locks/` klasörüne taşındı; yeni Value kontrol karakterleri reddedilir.
- Geçmiş kararı gölge git yerine içerik adresli blob + manifest olarak eşitlendi; çok belgeli atomik geri dönüş açık iştir.
- Kart 2 siparişi Faz 7'nin başında doğrulanmış v0.6 tasarımından verilecek; teslim/ölçüm tamponu ayrıldı.
- Çekirdek ilk commit'le kayda alındı. Lisans K1 ve uzak CI açık. Yerel test ve gerçek hiyerarşik netlist
  sonuçları [durum kaydında](docs/status.md); bağımsız denetim kapsamı da orada.

### Faz 1 ilerlemesi 0.1.2 — 11 Ekim 2026

- Revizyon bağlı salt okunur arka plan işleri, gerçek PCB istatistikleri, PNG render ve temel Gerber/delik ZIP eklendi.
- PCB net üyeliği ve katman/segment/via özetleri; özel kanıt kaydına bağlı çıktılar eklendi.
- Salt okunur IPC keşfi/PCB/seçim katmanı uygulandı. S1'de bir gerçek izole oturum ölçüldü;
  ikinci kanal ve S3 kabulü açık. Kullanıcı ayarları ve mevcut kullanıcı GUI oturumu değiştirilmedi.
- VS Code 0.1.3 kayıtlı kart PNG önizlemesi ve ölçüm komutları paketlendi. Etkileşimli görünüm/işaretler açık.
- Ölçüm sonuçları ve atlanan kontroller [durum kaydında](docs/status.md); faz kabulleri tamamlanmış gösterilmez.
