# Plan — VS Code'da kart ve şematik görünümü, işaretler, KiCad paketi

Tarih: 11 Ekim 2026 · Durum: **G0, G1, G2 ve G3 (PCB + şematik) uygulandı**; VS Code 0.1.6 kart ve şematik görünümü ile işaretler sunar. G4–G6 açık · Ana plan: [PLAN.md](../PLAN.md) bölüm 5.13 ve Faz 6.

### Ölçülen ilerleme — 11 Ekim 2026

- G0: SHA-256 doğrulamalı yerel Node 22.23.3 (`.tools/node`, mevcut kabuk için `scripts/dev-env.ps1`),
  CadAI’dan yalnız okunarak alınan MIT three.js paketi, nonce CSP’li panel. Gerçek VS Code 1.141.0
  Extension Host’unda boş panel ve servisle ecc83’ün yedi yerel SVG katmanı yüklendi.
- S7: ecc83, interf_u ve pic_programmer’de 281 dairesel pad merkezi; en büyük hata **0,00005 mm**.
  Dönüşüm kopyaya eklenen üç kalibrasyon dairesinden ölçülür, sabit kart ofseti değildir.
- G1: bu üç kartta **103 footprint merkezi** doğru referansla seçildi; gerçek DRC raporunun
  **10 konumu** SVG üzerine doğru çizildi (pic_programmer’de konumlu bulgu yok). Katman, zoom/pan,
  çakışan öğe seçimi ve dosya değişince yenileme var. Genel geometri sınırlamaları `docs/tools.md`’dedir.
- G3: PCB nokta/çizgi/alan/UUID öğe işaretleri, önizlemeli ekleme/düzenleme/silme, HMAC, checkpoint,
  kalıcılık ve MCP okuması var. `apply_markers`, `pcbai://markers`, gerekçeli `blocked` ve değişiklik
  kanıtlı `done` var. Şematik kayıt şeması ve değer değiştirme kabul testi eklendi; **şematik işaret
  arayüzü ve sembol/pin/net bağları G2’ye bağlı ve yapılmadı**. G3’ün tamamı bitti sayılmaz.
- G5’ten yenileme ve panoya “Ajana sor” eklendi; son tarayıcı koşusunda yenileme **5,4–9,6 sn**.
  **2 sn kabulü geçmedi**. G4 etkileşimli 3B, G6 KiCad’de seçtirme ve K-1–K-4 bu pakette yapılmadı.

### Ölçülen ilerleme — G2, 11 Ekim 2026

- S8: altı demoda 3510 pin bağlantı noktası KiCad SVG'siyle 0,0 mm; tüm netler netlistle aynı ([S8](spikes/S8.md)).
- `render_sch`/`scene_sch`/`hit_test_sch` ve VS Code 0.1.6 şematik paneli. Tarayıcı kabulü (gerçek Chromium,
  gerçek servis/CLI): complex_hierarchy'de R203/R303 kendi sayfasında, pin net vurgusu netlistle aynı,
  sayfalar arası net geçişi, çift tıklamayla alt sayfa; video'da ERC işaretleri UUID'den doğru konumda.
- G3 şematik: sayfa örneğine bağlı işaretler; "#1 bu direnç 4,7k olsun" gerçek `set_value` ile `done`.
  Şematik panel kart panelinden ayrıdır (sekme yerine ayrı komut).

Kanıtlar: [S7](spikes/S7.md), [koordinat ölçümleri](spikes/S7-result.json),
[gerçek Extension Host](spikes/G0-host-result.json), [tarayıcı kabulü](spikes/G1-browser-result.json).
G0/G1 ve PCB G3 bu çalışma için tek VS Code 0.1.4 paketinde birleştirildi; ayrı aşama sürümleri yayımlanmadı.

## 1. Neden şimdi

PLAN.md'de görünüm ve işaretler Faz 6'daydı (Mart 2027). Oysa kullanıcının PcbAi ile çalışma biçimi bu: kartı ve
devreyi VS Code'da görmek, numaralı işaret koyup "#2: bu hat 1 mm olsun" diye tarif etmek. Bugünkü eklenti (0.1.3)
kayıtlı kartın statik 3B PNG'sini ve ölçülerini gösterir; etkileşimli 2B/3B, şematik görünümü ve işaretler açıktır.
Bu plan etkileşimli görünümü **ayrı bir iz** olarak öne alır:

- Okuma tarafı (kartı/şematiği gösterme, tıklayınca ne olduğunu söyleme, ERC/DRC bulgularını üstüne çizme) bugünkü
  dosya modu çekirdeğiyle yapılabilir; başka faza bağlı değildir.
- İşaret koyma ve ajanın işaretleri okuması da hemen yapılabilir.
- İşarete göre **değişiklik** ise o değişikliği yapan araca bağlıdır: şematikte değer değiştirme bugün var
  (`set_value`); kartta taşıma/iz genişliği Faz 5a'nın araçlarıyla (İP-5.4) gelir. İşaret altyapısı önceden hazır olur.

Öneri: Faz 1'in kalanından sonra (S1/S3 canlı denemeleriyle paralel) G0–G5 uygulanır; Faz 6 bunun yerine "görünümün
canlı mod ve PCB düzenleme araçlarıyla birleştirilmesi" olur. Takvim etkisi: Faz 2 yaklaşık 3 hafta kayar ya da
görünüm ikinci bir ajana verilir (çekirdekle sözleşme bölüm 4'te sabit).

## 2. Kullanıcının göreceği

```text
┌ VS Code ─────────────────────────────────────────────────────────────────────────────┐
│ [Kart] [Şematik] [3B]          Katmanlar: ☑F.Cu ☑B.Cu ☑F.Silk ☐F.Fab …   Revizyon a1b2 │
│ ┌──────────────────────────────────────────────────────────┐ ┌ İşaretler ───────────┐ │
│ │                                                          │ │ #1 J1  sol kenara al │ │
│ │     ①  ┌──J1──┐        ┌─U1─┐                            │ │ #2 iz  1 mm olsun    │ │
│ │        └──────┘  ②━━━━━│    │      ⚠ DRC: clearance      │ │ #3 alan GND dökümü   │ │
│ │                        └────┘                            │ ├ Bulgular ────────────┤ │
│ │                  ③ ░░░░░░░░░                             │ │ DRC 0 hata 2 uyarı   │ │
│ └──────────────────────────────────────────────────────────┘ │ ERC 0 / 0            │ │
│ Seçili: R5 · 10k · R_0603 · (34,20; 18,05) mm · F.Cu   [İşaret koy] [Ajana sor]   │ │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Kart (2B):** katman açıp kapama, yakınlaştırma/kaydırma, fareyle üstüne gelince öğe bilgisi, tıklayınca seçim
  (footprint, pad, iz, via, döküm, kart kenarı), mm cinsinden imleç konumu, DRC bulgularının konumunda işaret.
- **Şematik:** sayfa sayfa gezinme (hiyerarşi ağacı), sembol/pin/tel/etikete tıklama, **net vurgulama** (bir pine
  tıklayınca bağlı olduğu her şey parlar), ERC bulguları.
- **3B:** kartın GLB modeli; döndürme, yakınlaştırma, bileşen seçimi (G4'teki denemeye bağlı).
- **İşaretler:** nokta, çizgi, alan, öğe (footprint/pad/iz/sembol/net). Numaralı; her birinin notu var. Kalıcıdır
  (projeyle birlikte saklanır). Ajan `get_markers` ile okur, değişiklikten sonra işaretin durumunu günceller.
- **Canlı yenileme:** ajan ya da kullanıcı dosyayı değiştirince (revizyon karması değişince) görünüm kendiliğinden yenilenir.

## 3. Mimari

```text
VS Code webview (HTML + JS, three.js)          VS Code eklenti süreci (extension.js)            PcbAi servisi
  çizim, katmanlar, seçim, işaret çizme   ⇄     postMessage köprüsü, belirteci tutar      ⇄     /call: render_*, scene_*,
  (ağ erişimi yok, belirteci görmez)             dosyaları webview URI'sine çevirir              markers_*, erc, drc
                                                                                                  ↓
                                                                     kicad-cli (SVG, GLB) · s-expr okuyucu (geometri)
```

- **Görüntü KiCad'den, anlam bizden:** resim `kicad-cli` ile üretilir (KiCad'in kendi çizimi, renkleri birebir).
  Tıklanınca "ne bu" sorusunu servisin dosyadan çıkardığı **geometri dizini** yanıtlar. İkisi aynı koordinat
  sistemine eşlenir (S7 denemesi). Böylece SVG içindeki yapıya güvenmek gerekmez.
- **Önbellek:** her çıktı `<durum klasörü>/views/<oturum>/<revizyon karması>/…` altında; revizyon aynıysa yeniden
  üretilmez. Kart SVG'si katman başına ayrı dosya (`--mode-multi`), webview katmanları üst üste koyar.
- **Güvenlik:** webview'de sıkı CSP (yalnızca `vscode-resource`), uzak içerik yok; servis belirteci yalnızca eklenti
  sürecinde kalır. Dosyalardan gelen metinler (referans, değer, işaret notu) webview'de metin olarak basılır, HTML
  olarak asla. Dışarıdan gelen işaret `trusted: false` taşır (CadAI kuralı).

## 4. Çekirdek sözleşmesi (yeni araçlar)

| Araç | Girdi | Çıktı |
|---|---|---|
| `render_pcb` | session, document, layers? | revizyon, kart sınır kutusu (mm), katman başına SVG yolu + mm↔SVG dönüşüm matrisi |
| `render_sch` | session, document (sayfa) | sayfa SVG yolu, sayfa boyutu (mm), dönüşüm matrisi, alt sayfa listesi |
| `render_3d` | session, document | GLB yolu, bileşen referansı ↔ düğüm adı eşlemesi (bulunabildiyse) |
| `scene_pcb` | session, document | footprint (ref, değer, konum, dönüş, yüz, avlu çokgeni, pad'ler), iz (uç noktalar, genişlik, katman, net), via, döküm çokgenleri, kart kenarı |
| `scene_sch` | session, document | sembol (ref, değer, sınır kutusu, pin konumları), tel, bağlantı noktası, etiket; net adı her pin/tele (KiCad netlistinden) |
| `hit_test` | session, document, x_mm, y_mm, katmanlar | en yakın öğeler (tür, kimlik, uzaklık) |
| `get_markers` | session | işaretler (bölüm 5) |
| `set_marker` / `delete_marker` | session, işaret | kaydedilen işaret (yalnızca VS Code arayüzünden; ajan için ayrı onay) |

- Geometri dizini mevcut bayt koruyan okuyucuyla (`pcbai/sexpr`) yazılır; footprint içi öğelerin konumu footprint
  dönüşü ve yüz (aynalama) uygulanarak hesaplanır. Şematikte pin konumu sembol dönüşü/aynalaması ve birimiyle hesaplanır.
- Net adları tahmin edilmez: şematikte `kicad-cli sch export netlist` sonucu kullanılır (PLAN ilkesi 3).

## 5. İşaretler

```json
{"n": 2, "kind": "line", "space": "pcb", "document": "Kartim.kicad_pcb", "layer": "F.Cu",
 "points_mm": [[12.0, 30.5], [25.0, 30.5]], "anchor": {"type": "track", "uuid": "…"},
 "note": "bu hat 1 mm olsun", "status": "open", "trusted": true, "revision": "a1b2…", "created": "…"}
```

- **Türler:** PCB'de nokta, çizgi, alan, öğe; şematikte sembol, pin, net, alan. Numara proje içinde artar, silinen
  numara yeniden kullanılmaz.
- **Saklama:** projede `pcbai/markers.json` (PLAN 3.6). Her işaret HMAC ile imzalanır (anahtar kullanıcının durum
  klasöründe). İmzası tutmayan ya da dosyayla gelen işaret `trusted: false`; ajan buna dayanarak yazmadan önce onay ister.
- **Bağ:** işaret hem koordinat hem öğe kimliği (UUID) taşır. Revizyon değişince servis bağı yeniden çözer: öğe
  duruyorsa işaret onunla gider; silinmişse işaret "kopuk" olur ve kullanıcıya gösterilir, tahminle yeniden bağlanmaz.
- **Durum:** `open` → ajan uyguladı → `done` (hangi değişiklik/kanıt kimliğiyle) ya da `blocked` (neden). Ajanın
  yanıtı panelde işaretin altında görünür.
- **Ajan tarafı:** MCP `get_markers` aracı, `pcbai://markers` kaynağı ve `apply_markers` istemi ("her işareti tek tek
  uygula, hangi değişikliğin hangi işarete ait olduğunu söyle"). Değişiklik aracı yoksa (ör. PCB taşıma Faz 5a'dan
  önce) işaret `blocked: "araç henüz yok"` olur; sessizce atlanmaz.
- **"Ajana sor" düğmesi:** seçili öğe ya da işaret için Claude Code sohbetine hazır bir metin bırakır ("#2 işaretini
  uygula") — VS Code'un sohbet API'si izin verdiği ölçüde; yoksa panoya kopyalar.

## 6. Aşamalar

Her aşama bir eklenti sürümüdür ve sonunda kullanıcı bir şeyi gerçekten kullanabilir.

| Aşama | İş | Bitti ölçütü | Süre |
|---|---|---|---|
| **G0** Ön koşullar | Node 22 kurulumu (eklenti testleri), S7 koordinat denemesi, three.js paketini CadAI'dan al (MIT, `three-bundle.js`), webview iskeleti + CSP | Boş webview açılıyor; S7 sonucu `docs/spikes/S7.md`'de: SVG'de tıklanan noktanın mm karşılığı 0,05 mm içinde | 2–3 gün |
| **G1** Kart 2B (salt okunur) | `render_pcb`, `scene_pcb`, katmanlar, yakınlaştır/kaydır, üstüne gelince bilgi, tıklayınca seçim, DRC bulgu katmanı, revizyonla yenileme | ecc83 ve iki demo kartta: her footprint'e tıklanınca doğru referans; DRC bulguları konumunda | 1 hafta |
| **G2** Şematik (salt okunur) | `render_sch`, `scene_sch`, hiyerarşi ağacı, net vurgulama (netlistten), ERC bulgu katmanı | complex_hierarchy demosunda: R203/R303 iki örnek doğru; bir pine tıklanınca netin tüm pinleri vurgulanıyor (KiCad netlistiyle aynı) | 1 hafta |
| **G3** İşaretler | Sözleşme (bölüm 5), servis araçları, webview'de koyma/düzenleme/silme, panel, MCP `get_markers` + `apply_markers` | Kartta ve şematikte işaret koy → VS Code'u kapat-aç → işaretler duruyor; Claude Code `get_markers` ile okuyor; şematikte "#1 bu direnç 4,7k olsun" `set_value` önizleme/uygulama ile uçtan uca | 1 hafta |
| **G4** 3B | `render_3d`, three.js görüntüleyici, bileşen seçimi (GLB düğüm adları referans içeriyorsa; değilse yalnızca görüntü) | Demo kart açılıyor, yavaş GPU'da da (CadAI'daki kademeli WebGL yaklaşımı) | 3–4 gün |
| **G5** Ajanla döngü | Değişiklik sonrası otomatik yenileme, işaret durumu (`done`/`blocked`), "Ajana sor", sonuç/kanıt paneli | Ajan bir değeri değiştirince görünüm 2 sn içinde yenileniyor, işaret `done` ve kanıt kimliğini gösteriyor | 3–4 gün |
| **G6** KiCad ile çapraz seçim | Canlı modda (S1 sonrası): VS Code'da seçince KiCad'de seç (`add_to_selection`), KiCad'deki seçimi göster | KiCad açıkken iki yönde seçim çalışıyor | Faz 1 canlı katmanından sonra |

Toplam G0–G5: yaklaşık 5 hafta. PCB üzerinde işaretle **değişiklik** (taşı, iz genişliği, döküm) Faz 5a araçları
gelince G3 altyapısına bağlanır; ek görünüm işi gerekmez.

## 7. Test

- **Birim (KiCad gerekmez):** geometri dizini — dönüş/aynalama/yüz altında pad ve pin konumları, isabet testi,
  işaret imzası ve bağ çözme (öğe taşındı, silindi).
- **Gerçek kicad-cli:** demo projelerde `render_*` çıktısı üretiliyor; SVG ↔ mm eşlemesi bilinen footprint
  merkezlerinde 0,05 mm içinde; şematik net vurgusu KiCad netlistiyle aynı küme.
- **Görünüm uçtan uca:** başsız tarayıcıda (CadAI'nın `test:viewer` yöntemi) webview açılır, bilinen noktaya
  tıklanır, seçilen referans ve ekran görüntüsü denetlenir. Node gerekir (G0).
- **Elle kabul:** kullanıcı kendi bir kartında G1–G3'ü dener; bulgular `docs/status.md`'ye yazılır.

## 8. KiCad tarafı: eklentinin "Yüklü" listesinde görünmesi

**Teşhis (11 Ekim 2026):**
- KiCad'in Eklenti ve İçerik Yöneticisi (PCM) yalnızca kendi kurduğu paketleri listeler (`Documents\KiCad\10.0\3rdparty\plugins`:
  bu makinede kikit ve impartGUI). `install.py` eklentiyi elle `Documents\KiCad\10.0\plugins\` altına kopyaladı;
  KiCad bu klasördeki eklentileri yükler ama PCM listesinde **göstermez**. Yani görünmemesi kurulum yönteminden.
- Düğmeler de çıkmıyor: `kicad_common.json`'da `api.enable_server` hâlâ `false` ve KiCad eklentinin Python ortamını
  (`%LOCALAPPDATA%\KiCad\10.0\python-environments\org.pcbai.kicad`) hiç oluşturmamış — eklenti henüz yüklenmemiş.

**Yapılacaklar (K-1 … K-4):**
1. **K-1 PCM paketi:** `kicad_plugin/build_pcm.py` → `dist/pcbai-kicad-<sürüm>.zip`: kökte `metadata.json`
   (KiCad PCM şeması: identifier `org.pcbai.kicad`, type `plugin`, sürüm, KiCad 10 uyumu, açıklama, lisans),
   `plugins/` altında bugünkü dosyalar (`plugin.json`, `requirements.txt`, `*.py`, simgeler), `resources/icon.png`.
   PcbAi deposunun yolu paketin içine değil, ilk çalıştırmada kullanıcıdan alınır ya da `%APPDATA%\PcbAi\location.json`
   dosyasından okunur (paket makineye özel olmamalı).
2. **K-2 Kurulum:** KiCad → Eklenti ve İçerik Yöneticisi → **Dosyadan yükle…** → zip. Elle kurulan kopya
   (`plugins\org.pcbai.kicad`) önce silinir; aynı kimlikte iki eklenti olmamalı.
3. **K-3 API:** Tercihler → Eklentiler → **KiCad API'yi etkinleştir**; ardından PCB editörünü yeniden aç. İlk açılışta
   KiCad Python ortamını kurar ve `kicad-python` indirir.
4. **K-4 Kabul:** eklenti PCM'in "Yüklü" sekmesinde görünür; PCB editöründe iki düğme var; "PcbAi'ye kaydet" gerçek
   KiCad'de proje yolunu doğru verir (S1'in bir parçası); hata olursa pencere metni `docs/status.md`'ye yazılır.
   `metadata.json` KiCad'in PCM şemasıyla doğrulanır (kurulu KiCad'in `share\kicad\schemas\pcm.v2.schema.json`).

## 9. Riskler

| Risk | Önlem |
|---|---|
| kicad-cli SVG koordinatları sürümle değişir | S7 testi CI'da; dönüşüm matrisi her çıktıda yeniden hesaplanır, sabit kodlanmaz |
| Büyük kartta SVG ağır | Katman başına dosya, yalnızca açık katmanlar yüklenir; revizyon önbelleği |
| GLB düğüm adları bileşeni göstermez | 3B'de seçim isteğe bağlı; 2B seçim esas |
| Kaydedilmemiş KiCad değişiklikleri görünmez | Görünümde sürekli "kaydedilmiş dosya · revizyon" etiketi; canlı mod (G6) gelene kadar |
| Webview'e dosya metninden betik sızması | Metin olarak basma, CSP, uzak içerik yok |
| İşaretin bağlı olduğu öğe değişir | UUID + koordinat; kopan işaret gösterilir, tahminle bağlanmaz |
