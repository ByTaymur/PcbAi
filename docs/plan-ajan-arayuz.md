# Plan — çok ajanlı entegrasyon ve KiCad içi arayüz (AJ)

14 Ekim 2026 · Durum: **AJ-1…AJ-7 uygulandı** (VS Code 0.1.24); gerçek KiCad/VS Code/model kabulleri açık, ayrıntı
[status.md](status.md). Başlangıç ağacı: `main/35ba333`, VS Code 0.1.18.
Bağlı: [PLAN 5.13](../PLAN.md), [görünüm planı](plan-gorunum.md), [eksikler](plan-eksikler.md) (bölüm 3.5
"Ajana sor"), [durum](status.md).

Amaç: kullanıcı PcbAi'ye **hangi ajanla çalışacağını kendisi seçer** (Claude Code, Codex, Cline, Kilo, Roo,
Copilot, terminal CLI'ları, yerel model ya da yalnızca pano) ve bunu **hem VS Code'dan hem de KiCad'in içinden**
yapar. Bütün ajanlar aynı `pcbai` MCP araçlarını kullanır; bu plan yalnızca *istemin nerede oluştuğunu*, *hangi
ajana nasıl ulaştığını* ve *MCP kaydının her ajana nasıl yazıldığını* düzenler. Araç kümesi ve güvenlik kapıları
(önizle/uygula, revizyon, kontrol noktası) değişmez.

Hedef görünüm (CadAI yan panelindeki seçicinin aynısı):

```text
YAPAY ZEKÂ
Ajan [Claude Code — mesaj kutusuna yazılır          v]
      Claude Code — mesaj kutusuna yazılır
      Claude Code (terminal) — mesaj doğrudan gönderilir
      Codex — mesaj kutusuna yazılır
      Codex (terminal) — mesaj doğrudan gönderilir
      Cline — VS Code paneli
      Kilo Code — VS Code paneli
      GitHub Copilot Chat — VS Code sohbeti
      Sadece panoya kopyala — istediğin yere yapıştır
[Ajana gönder]  [Kopyala]
```

---

## 0. Başlangıç durumu (14 Ekim 2026, ölçülen)

| Konu | Bugün | Kaynak |
|---|---|---|
| Yan panel gönderimi | Yalnız `claude-vscode.editor.open` (Claude Code yeni sekme) ya da pano; ajan seçimi yok | [sidebar_view.js:117-125](../vscode/pcbai-vscode/sidebar_view.js#L117-L125) |
| Kart/şematik "Ajana sor" | Yalnız panoya kısa metin | [board_view.js:148](../vscode/pcbai-vscode/board_view.js#L148), [sch_view.js:146](../vscode/pcbai-vscode/sch_view.js#L146) |
| MCP kaydı | `pcbai.addMcp` yalnız çalışma alanı `.mcp.json` (Claude Code) yazar; Codex/Cline/Kilo/Roo/Copilot yok | [extension.js:415-436](../vscode/pcbai-vscode/extension.js#L415-L436) |
| MCP vekili | `PCBAI_PROJECTS` boşsa çalışan servise bağlanır; farklı proje listesiyle çalışan servis varsa hata verir | [client.py:15-40](../mcp_server/client.py#L15-L40) |
| KiCad eklentisi | İki IPC düğmesi (kaydet, ERC/DRC); arayüz yalnız Win32 `MessageBoxW` | [pcbai_kicad.py](../kicad_plugin/pcbai_kicad.py), [plugin.json](../kicad_plugin/plugin.json) |
| KiCad 10.0 Python | `tkinter` **kullanılamaz** (`_tkinter` yok); **wxPython 4.2.2 msw, wxWidgets 3.3.2 var** | `python.exe -I -c "import wx"` ölçümü |
| Eklenti venv'i | `include-system-site-packages = true` → wx eklenti ortamında görünür (impartGUI de aynı düzende) | `%LOCALAPPDATA%\KiCad\10.0\python-environments\org.pcbai.kicad\pyvenv.cfg` |
| VS Code motoru | `engines.vscode ^1.90.0`; yerel MCP API'si (`lm.registerMcpServerDefinitionProvider`) 1.101 ister | [package.json](../vscode/pcbai-vscode/package.json) |
| Kardeş proje | CadAI'da çalışan örnek: `agents.js` (9 ajan, algılama, teslim), `mcp_setup.js` (Claude CLI, Codex TOML, Cline/Kilo/Roo JSON, VS Code `mcp.json`/yerel API), FreeCAD içi sohbet paneli + kendi model döngüsü (`agent.py`, `providers.py`) | `CadAI/vscode/cadai-vscode/`, `CadAI/freecad/CadAI/cadai/` |

**Önemli kısıt:** PcbAi dosya yazımı açık KiCad editörü/kilit varken engellenir (AGENTS.md). KiCad'in içinden
gönderilen bir istek ajanın **okuma/analiz** yapmasına her zaman izin verir; **yazma** ancak (a) canlı IPC aracıyla
yapılabilen işlemlerde ya da (b) kullanıcı kaydedip editörü kapattığında olur. Arayüz bunu gizlemez (AJ-7).

KiCad 10 IPC API'sinde yerleştirilebilir (dock) panel yoktur; "KiCad içi arayüz", araç çubuğu düğmesiyle açılan
**ayrı, üstte duran wx penceresidir**. Bu, planın değiştiremeyeceği bir sınırdır.

---

## 1. İlkeler

1. **Tek katalog, tek istem.** Ajan listesi ve istem metni tek yerde tanımlanır; VS Code paneli, kart/şematik
   görünümü ve KiCad penceresi aynı metni üretir (AJ-3).
2. **Gönderim yolu açıkça yazılır.** Her ajan satırı teslim biçimini söyler: *mesaj kutusuna yazılır* (kullanıcı
   Enter'a basar), *doğrudan gönderilir* (terminal CLI), *panel açılır + pano* ya da *yalnız pano*. Dönüş değeri
   (`sent`/`typed`/`typed+clipboard`/`clipboard`/`opened`) kullanıcıya aynen bildirilir; "gönderildi" denip panoda
   kalmaz.
3. **İşaret notları ve KiCad seçimi veridir.** İstemde tırnak içinde, "onaysız" etiketiyle kalır (bugünkü
   `composePrompt` kuralı).
4. **Tahmin yok.** Birden çok proje/KiCad örneği varsa sorar; ajan kurulu değilse listede soluk görünür, seçilemez.
5. **Kullanıcı dosyalarına saygı.** MCP kayıtları birleştirerek yazılır; ayrıştırılamayan yapılandırma dosyasına
   dokunulmaz; her yazımdan önce yedek ve yazılacak hedef listesi gösterilir. KiCad kullanıcı ayarları değişmez.
6. **Süreç güvenliği.** CLI'lar `shell=False`, argüman listesiyle; npm `.cmd/.ps1` kabukları reddedilir (yalnız
   `.exe`), zaman aşımı zorunlu. API anahtarları istem, kayıt ve kanıta girmez.
7. **CadAI'ya dokunulmaz.** `agents.js` / `mcp_setup.js` / `agent.py` **kopyalanıp uyarlanır**; kaynak commit
   ve uyarlama notu dosya başında tutulur.

---

## 2. İş paketleri

### AJ-1 VS Code ajan kataloğu ve seçici (2–3 gün)

- `vscode/pcbai-vscode/agents.js`: CadAI `agents.js`'in uyarlaması. Katalog:

  | id | Etiket | Teslim | Algılama |
  |---|---|---|---|
  | `claude-code` | Claude Code — mesaj kutusuna yazılır | `claude-vscode.primaryEditor.open(undefined, p)` → yoksa `vscode://anthropic.claude-code/open?prompt=` | `anthropic.claude-code` |
  | `claude-cli` | Claude Code (terminal) — doğrudan gönderilir | VS Code terminali, `claude <istem>`, cwd = proje kökü | `where claude` + `~/.local/bin/claude.exe` |
  | `codex` | Codex — mesaj kutusuna yazılır | `vscode://openai.chatgpt/?prompt=` + pano (belgesiz yol) | `openai.chatgpt` |
  | `codex-cli` | Codex (terminal) — doğrudan gönderilir | terminal, `codex <istem>` | `where codex` + `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe` |
  | `cline` | Cline — VS Code paneli | pano + `cline.focusChatInput` | `saoudrizwan.claude-dev` |
  | `kilo` | Kilo Code — VS Code paneli | pano + `kilo-code.new.plusButtonClicked` | `kilocode.kilo-code` |
  | `roo` | Roo Code — VS Code paneli | pano + `roo-cline.SidebarProvider.focus` | `rooveterinaryinc.roo-cline` |
  | `copilot` | GitHub Copilot Chat — VS Code sohbeti | `workbench.action.chat.open {query, isPartialQuery}` | `github.copilot-chat` |
  | `clipboard` | Sadece panoya kopyala — istediğin yere yapıştır | pano | her zaman |

  Gemini CLI ve Continue **aday**; teslim yolu ölçülmeden kataloğa girmez.
- Yan panel: "Ajana isteğin" üstüne **YAPAY ZEKÂ / Ajan** açılır listesi (kurulu olmayanlar `disabled`, ayrıntıda
  "kurulu değil"). "Claude Code'da aç" düğmesi **"Ajana gönder"** olur; "Kopyala" kalır. Seçim
  `globalState['pcbai.agent']`'ta saklanır; yoksa tercih sırası `claude-code, codex, cline, kilo, copilot, roo,
  claude-cli, codex-cli, clipboard`. `vscode.extensions.onDidChange` ile liste tazelenir.
- Komut `pcbai.chooseAgent` (QuickPick) ve durum çubuğunda seçili ajan.
- Kart/şematik görünümündeki "Ajana sor" aynı `agents.open()`'ı kullanır (pano-yalnız yol kalkar).
- **Uzun istem:** terminal CLI'larında satır sonları/tırnaklar `cliSafe` ile tek satıra iner. İstem ~7000
  karakteri aşarsa CLI'ya argüman yerine `.pcbai-state/prompts/<uuid>.md` yazılır ve ajana kısa bir
  "şu dosyadaki isteği oku" metni verilir (dosya proje kökü içinde; 24 saat sonra silinir).
- **Bitti:** yan panelde 9 satır; kurulu olanlar seçilebiliyor; her ajan için teslim sonucu doğru mesajla
  bildiriliyor (birim testi: `vscode.commands`/`env` sahteleriyle her dal); Claude Code ve Copilot'ta gerçek
  Host'ta istem kutuda görülüyor (elle kabul, ekran görüntüsü `.pcbai-state/`).

### AJ-2 "MCP'yi ajanlara bağla" — tüm ajanlar (2–3 gün)

- `vscode/pcbai-vscode/mcp_setup.js`: CadAI `mcp_setup.js` uyarlaması, ad `pcbai`. Hedefler:
  - Claude Code: çalışma alanı `.mcp.json` (bugünkü davranış, varsayılan) **ya da** `claude mcp add -s user pcbai`.
  - Codex: `~/.codex/config.toml` içinde `[mcp_servers.pcbai]` (birleştirerek; diğer tablolar korunur).
  - Cline / Kilo / Roo: `globalStorage/<ext>/settings/*mcp_settings.json`.
  - VS Code / Copilot: kullanıcı `mcp.json`; VS Code ≥ 1.101'de `lm.registerMcpServerDefinitionProvider` ile yerel
    kayıt (o zaman `mcp.json` kopyası kaldırılmak üzere önerilir). `engines` 1.90'da kalır; API varlığı çalışma
    anında denetlenir.
- **Proje listesi sorunu:** kullanıcı düzeyindeki kayıtlar (Codex, Cline, Kilo, Roo, Copilot, Claude `-s user`)
  çalışma alanından bağımsızdır; sabit `PCBAI_PROJECTS` yazılırsa başka projede "different registered projects"
  hatası çıkar. Karar: kullanıcı düzeyi kayıtlarda `PCBAI_PROJECTS` **yazılmaz**; vekil çalışan servise bağlanır,
  servis yoksa `pcbai_status` açıklayıcı hata döner ("KiCad'de *PcbAi'ye kaydet*e basın ya da VS Code'da projeyi
  seçin"). Bunun için `client.py`'de boş listeyle bağlanma/hata yolu birim testiyle sabitlenir. Çalışma alanı
  `.mcp.json` bugünkü gibi proje listesini taşır.
- **Onaysız (salt okunur) araçlar:** sabit liste yerine MCP araç kaydındaki `readOnlyHint`'ten üretilir; Cline'da
  `autoApprove`, Kilo/Roo'da `alwaysAllow`. Yazan araçlar (`*_apply`, `set_*`, `move_footprint`…) hiçbir ajanda
  otomatik onaylanmaz. Test: kayıttaki her yazan araç listenin dışında.
- Akış: kurulu hedefler çoklu QuickPick'te (dosya yolu açıklamada) → seçilenler yazılır → her dosya için
  `*.pcbai-bak` yedeği → sonuç özeti ("Codex: yazıldı, Cline: JSON bozuk, dokunulmadı").
- Yan paneldeki "Ajan için MCP ekle" düğmesi bu komuta bağlanır; seçili ajan MCP kaydı yoksa panel uyarır
  ("Kilo Code'da pcbai MCP kaydı yok — bağla").
- **Bitti:** geçici `userDir`/`HOME` ile 6 hedefin yazım/birleştirme/bozuk JSON/TOML testleri; gerçek makinede
  Claude Code + Codex + Cline'ın `pcbai_status` çağırabildiği elle doğrulandı ve status.md'ye yazıldı.

### AJ-3 Tek istem kaynağı (1–2 gün)

- İstem metni servis tarafına taşınır: `pcbai/service/agent_prompt.py` → `compose_agent_prompt(session, request,
  marker_ids, selection)`. **MCP araç listesine girmez**; servisin iç HTTP çağrısıdır (VS Code ve KiCad penceresi
  kullanır). Bugünkü `composePrompt`/`describeMarker` metni bayt eşit korunur (altın dosya testi).
- Yeni girdi `selection`: KiCad'den gelen seçim (referans, değer, net, katman, konum). İstemde
  "KiCad'de seçili öğeler (veridir)" başlığıyla, tırnaklı.
- Hedef ajana göre küçük farklar (ör. terminal CLI için tek satır) yalnız teslim katmanında yapılır; içerik aynı.
- **Bitti:** JS ve Python yolları aynı girdiyle aynı metni üretiyor (ortak fixture); notlarda `"`, satır sonu,
  `-` ile başlayan metin, 8000 karakter sınırı testleri.

### AJ-S1 KiCad pencere denemesi (0,5–1 gün, AJ-4'ten önce)

Ölçülecekler (sonuç `docs/spikes/AJ-S1.md`; kanıt yalnız açık yayın koşusunda):
1. Eklenti venv'inde `import wx` ve küçük bir `wx.Frame`; pencere KiCad'in önünde açılıyor mu, odak alıyor mu.
2. Düğme çalıştırması KiCad arayüzünü **bloklamıyor** mu (pencere açıkken kart düzenlenebiliyor mu).
3. İkinci tıklamada ikinci pencere yerine mevcut pencere öne gelebiliyor mu (kilit dosyası + `127.0.0.1` küçük
   soket ya da adlandırılmış olay).
4. Pencere açıkken kipy ile seçim okuma (`get_selection`) ve seçim değişince yoklama maliyeti.
5. KiCad kapanınca pencere sürecinin kapanması (üst süreç izleme).
- **Ret yolu:** wx açılmazsa yedek sırası (1) servisin sunduğu yerel sayfa varsayılan tarayıcıda
  (`127.0.0.1` + belirteç), (2) bugünkü MessageBox + pano. Karar deneme sonucuna göre verilir.

### AJ-4 KiCad içi asistan penceresi (4–5 gün)

- `plugin.json`'a üçüncü düğme: **PcbAi Asistan** (`pcbai.assistant`, `scopes: ["pcb"]`; şematik kapsamı
  KiCad 10 IPC'de yoksa yalnız PCB). Giriş `assistant.py`; tek örnek (AJ-S1/3).
- Pencere içeriği (wx, Türkçe):

  ```text
  ┌ PcbAi Asistan ─────────────────────────────── [üstte tut] ┐
  │ Proje: motor_surucu.kicad_pro  ● servis   KiCad 10.0.7     │
  │ YAPAY ZEKÂ  Ajan [Claude Code (VS Code) — kutuya yazılır v]│
  │ İsteğin                                                    │
  │ [ Q3-Q6 MOSFET'lerin soğutma bakırını büyüt...          ]  │
  │ [x] KiCad seçimini ekle (3 öğe: Q3, Q4, net VBUS)          │
  │ İşaretler  [x] #1 J1 sol kenar  [ ] #2 iz 1 mm  (yenile)   │
  │ [Ajana gönder] [Kopyala] [ERC/DRC] [VS Code'da aç]         │
  │ ▸ Oluşan istem                                             │
  │ ▸ Ajan etkinliği (AJ-7)                                    │
  │ Durum: Claude Code'a yazıldı — VS Code'da Enter'a basın.   │
  └────────────────────────────────────────────────────────────┘
  ```

- **KiCad tarafı katalog** (VS Code dışında çalıştığı için teslim yolları farklı):

  | Satır | Teslim |
  |---|---|
  | VS Code'daki ajan — *(VS Code'da seçili ajan adı)* | AJ-5 devri: PcbAi eklentisinin URI işleyicisi istemi alır, VS Code'da seçili ajana `agents.open()` ile verir |
  | Claude Code (terminal) — doğrudan gönderilir | yeni konsol penceresi, `claude.exe <istem>`, cwd = proje kökü, `CREATE_NEW_CONSOLE`, `shell=False` |
  | Codex (terminal) — doğrudan gönderilir | aynı, `codex.exe` |
  | Yerleşik model — bu pencerede (AJ-6) | pencere içi sohbet |
  | Sadece panoya kopyala | `wx.TheClipboard` |

  Doğrudan Claude Code/Codex VS Code eklentilerine KiCad'den `vscode://anthropic.claude-code/open?prompt=` ile
  gitmek mümkündür, ama uzun istemde URL sınırı ve proje klasörü belirsizliği var; varsayılan yol AJ-5 devridir.
  Derin bağlantı yalnız "VS Code eklentisi kurulu değil ama Claude Code kurulu" durumunda yedektir.
- CLI ve VS Code algılaması pencere açılırken bir kez yapılır (`where.exe`, bilinen yollar,
  `%USERPROFILE%\.vscode\extensions\extensions.json` okuma; zaman aşımı 3 sn).
- ERC/DRC düğmesi bugünkü `check.py` mantığını çağırır; sonuç pencerede listelenir (MessageBox yerine).
- Hata yolu bugünkü `run()` gibi: her hata pencerede görünür; `kipy` kurulumu hatası açıklanır.
- **Bitti:** gerçek KiCad 10'da düğme pencereyi açıyor; seçili 3 öğe istemde; terminal CLI'ya giden istem
  ajan tarafından okunuyor; ikinci tıklama yeni pencere açmıyor; KiCad kapanınca pencere kapanıyor.
  Birim testleri: istem/katalog/algılama (wx'siz), PCM zip'inde yeni dosyalar ve şema kabulü.

### AJ-5 KiCad → VS Code devri (1–2 gün)

- Eklentiye `vscode.window.registerUriHandler`: `vscode://taymur.pcbai-vscode/handoff?id=<uuid>`.
- KiCad penceresi istemi URL'ye koymaz: servise `handoff_create(session, prompt)` iç çağrısıyla yazar
  (`.pcbai-state/handoff/<uuid>.json`, tek kullanımlık, 10 dk ömür, servis belirteciyle), URL yalnız kimliği taşır.
  Eklenti `handoff_take(id)` ile alır; oturum VS Code'un projesiyle eşleşmiyorsa sorar, tahmin etmez.
- Eklenti istemi yan panelin istek kutusuna da doldurur ve seçili ajana gönderir; sonuç mesajı (`typed`,
  `clipboard`…) servise geri yazılır, KiCad penceresi bunu "Durum" satırında gösterir.
- VS Code açık değilse URI VS Code'u açar; proje klasörü çalışma alanında değilse kullanıcıya "klasörü aç"
  önerilir.
- **Bitti:** KiCad penceresinden gönderilen istem VS Code'da Claude Code kutusunda; kullanılmış/süresi geçmiş
  kimlik reddediliyor; başka projenin kimliği sorulmadan uygulanmıyor (testler).

### AJ-6 Yerleşik model (KiCad penceresinde sohbet, 1–1,5 hafta, isteğe bağlı)

- CadAI `agent.py` + `providers.py` uyarlaması, KiCad eklenti sürecinde çalışır; araçları **servis üzerinden**
  çağırır (aynı kayıt, aynı önizle/uygula kapıları; araç yürütme penceresinde değil serviste).
- Sağlayıcılar: Ollama, LM Studio (yerel), Claude (Anthropic API; varsayılan `claude-opus-5-5`), OpenAI uyumlu.
  Anahtar ortam değişkeninden (`ANTHROPIC_API_KEY` vb.); yapılandırma `%APPDATA%\PcbAi\assistant.json`
  (KiCad ayarı değil). SDK'lar eklenti venv'ine `requirements.txt` ile değil, isteğe bağlı kurulumla gelir;
  yoksa sağlayıcı satırı "kurulu değil".
- Küçük yerel modeller için PLAN 5.12'deki küçük araç kümesi.
- **Onay:** yazan her araç çağrısı pencerede çözülmüş argümanlar + önizleme özetiyle onay ister (CadAI güvenlik
  modeli). Aynı hatalı çağrının 3. tekrarında durur.
- Mod: **Planla** (salt okunur araçlar) / **Uygula**.
- **Bitti:** Ollama + bir araç çağıran modelle "R5 değerini oku" ve önizleme/onaylı `set_value`; Claude API ile
  aynı senaryo; anahtar hiçbir kayıtta görünmüyor (test).

### AJ-7 Ajan etkinliği ve KiCad'le eşitleme (2–3 gün)

- Servis her araç çağrısını kısa olay kaydına yazar: zaman, istemci (`mcp:claude-code`, `vscode`, `kicad`,
  `builtin`), araç, sonuç (`ok`/`blocked`/hata), `change_id`. Argüman değerleri değil yalnız özet tutulur.
  İstemci adı MCP `initialize` içindeki `clientInfo.name`'den gelir (veridir, yetki vermez).
- KiCad penceresi ve VS Code paneli son 50 olayı gösterir (CadAI'daki mor ajan satırları gibi).
- **Yazım engeli görünür olur:** ajan dosya yazmak isteyip açık editör yüzünden `blocked` aldığında pencere
  "Ajan değişiklik yapmak istiyor: kartı kaydedip PCB editörünü kapatın, sonra *Devam* deyin" der; canlı IPC
  aracı olan işlemler bu engelden muaftır (S3 sonuçlarına bağlı).
- Değişiklik dosyaya yazıldıktan sonra KiCad'de kartın yeniden yüklenmesi: IPC'de belge yeniden yükleme/geri alma
  çağrısı olup olmadığı AJ-S1'de ayrıca ölçülür; yoksa pencere "Dosya → Geri al (Revert)" talimatı verir.
- **Bitti:** VS Code'daki Claude Code bir `set_value` uyguladığında KiCad penceresinde olay 2 sn içinde
  görünüyor; açık editörle yazım denemesi pencerede açıklamalı `blocked` olarak çıkıyor.

---

## 3. Sıra ve takvim (öneri)

| Sıra | Paket | Süre | Bağımlılık |
|---|---|---|---|
| 1 | AJ-1 VS Code seçici | 2–3 gün | — |
| 2 | AJ-2 MCP'yi tüm ajanlara bağla | 2–3 gün | — (AJ-1 ile paralel olabilir, ayrı dal) |
| 3 | AJ-3 tek istem kaynağı | 1–2 gün | AJ-1 |
| 4 | AJ-S1 wx pencere denemesi | 0,5–1 gün | — |
| 5 | AJ-4 KiCad asistan penceresi | 4–5 gün | AJ-3, AJ-S1 |
| 6 | AJ-5 KiCad → VS Code devri | 1–2 gün | AJ-1, AJ-4 |
| 7 | AJ-7 etkinlik ve eşitleme | 2–3 gün | AJ-4 |
| 8 | AJ-6 yerleşik model | 1–1,5 hafta | AJ-4, AJ-7 (isteğe bağlı) |

İlk kullanılabilir teslim (1–3): VS Code'da ekran görüntüsündeki seçici + bütün ajanlarda MCP. İkinci teslim
(4–7): KiCad'den isteme ve ajanın yaptığını KiCad'de görme. AJ-6 ayrı karar.

Dallar: `ip/aj1-secici`, `ip/aj2-mcp`, `ip/aj4-kicad-pencere`… (AGENTS.md: bir paket = bir ajan = bir dal).

---

## 4. Test ve kabul

- Birim: `vscode/pcbai-vscode/test/agents.test.js`, `mcp_setup.test.js`, `sidebar.test.js` genişler;
  `tests/test_agent_prompt.py`, `tests/test_kicad_assistant.py` (wx olmadan mantık), `tests/test_handoff.py`.
- Gerçek ortam (elle, sonuç status.md'ye): her kurulu ajanda teslim biçimi; KiCad 10'da pencere; AJ-5 devri.
  Bunlar birim testi değildir ve ayrı yazılır; çalıştırılamayan kabul "yapılmadı" olarak kalır.
- Sürüm: VS Code eklentisi her pakette artar; KiCad paketi çekirdek sürümünü `pcbai/__init__.py`'den alır.
- Komutlar: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`, `ruff check .`, eklenti testleri.

## 5. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Claude Code/Codex komut ve URI yolları belgesiz, sürümle değişebilir | Kutuya yazma çalışmaz | Her yol denenir, olmazsa pano + odak; sonuç dürüstçe bildirilir; test sahte komutlarla tüm dalları kapsar |
| Kullanıcı düzeyi MCP kaydında proje bilinmiyor | Yanlış projeye bağlanma | `PCBAI_PROJECTS` yazılmaz; çok oturumda `session` zorunlu, tahmin yok |
| KiCad editörü açıkken yazım engeli | KiCad içinden "yap" isteği yarıda kalır | AJ-7'de açık `blocked` + talimat; canlı IPC araçları genişledikçe azalır |
| wx penceresi KiCad'in arkasında kalır / çift açılır | Kullanım zorluğu | AJ-S1 ölçer; tek örnek kilidi; "üstte tut" |
| Terminal CLI'ları istemi doğrudan çalıştırır | Kullanıcı istemi görmeden ajan başlar | Satır etiketi "doğrudan gönderilir"; pencerede önizleme varsayılan açık |
| Yerleşik modelde anahtar sızıntısı | Güvenlik | Anahtar yalnız ortamdan; kayıt/kanıt filtreleri ve test |

## 6. Açık kararlar (kullanıcı)

1. AJ-6 yerleşik model bu turda mı, sonra mı? (Öneri: AJ-1…AJ-7'den sonra.)
2. Claude Code MCP kaydı varsayılanı: çalışma alanı `.mcp.json` mı, kullanıcı düzeyi mi? (Öneri: çalışma alanı
   varsayılan, kullanıcı düzeyi seçenek.)
3. KiCad penceresinde VS Code'daki ajanlar ayrı ayrı mı listelensin, yoksa tek "VS Code'daki ajan" satırı mı?
   (Öneri: tek satır; seçim VS Code panelinde yapılır, karışıklık azalır.)

---

## 7. Kalan işler (14 Ekim 2026 denetimi, main `cbdb55a`, VS Code 0.1.24)

AJ-1…AJ-7 kodu main'de. Ölçülen: AJ hedefli Python testleri 37 OK, ruff temiz, eklenti testleri `dru.test.js` dışında
geçti. Aşağıdakiler açık; her madde ayrı iş paketi olarak verilebilir.

### 7.1 Elle kabuller (birim testi değildir; sonuç status.md'ye)

- [ ] **AJ-S1:** KiCad 10 içinde wx penceresi öne geliyor ve odak alıyor; pencere açıkken kart düzenlenebiliyor; ikinci
  tıklama mevcut pencereyi öne getiriyor; KiCad kapanınca pencere kapanıyor. Sonuç `docs/spikes/AJ-S1.md`.
- [ ] **AJ-1:** gerçek Extension Host'ta her kurulu ajan için teslim sonucu (Claude Code ve Copilot'ta istem kutuda).
- [ ] **AJ-2:** Claude Code, Codex ve Cline'ın `pcbai_status` çağırabildiği.
- [ ] **AJ-4:** KiCad'de seçili 3 öğenin istemde görünmesi; terminal CLI'ya giden istemin ajan tarafından okunması.
- [ ] **AJ-5:** KiCad penceresinden gönderilen istemin VS Code'da Claude Code kutusuna düşmesi.
- [ ] **AJ-6:** Ollama ile "R5 değerini oku" + onaylı `set_value`; Claude API ile aynı senaryo; KiCad içinde onay
  penceresi. Ön koşul: Ollama/LM Studio, `ANTHROPIC_API_KEY`, `anthropic` paketi (bu makinede yok).
- [ ] **AJ-7:** VS Code'daki Claude Code `set_value` uyguladığında olayın KiCad penceresinde ve VS Code panelinde
  2 sn içinde görünmesi; açık editörle yazımın açıklamalı `blocked` çıkması.

### 7.2 Kod düzeltmeleri (küçük)

- [ ] **Eski olay talimatı:** yan panel ilk açılışta eski olayları da çekiyor; eski bir `ok` + `change_id` olayı
  "Dosya → Geri al" talimatını mesaj satırına düşürebiliyor. İlk yüklemede talimat yalnız son olaydan ya da yalnız
  panel açıldıktan sonraki olaylardan üretilsin (`sidebar_view.js` `pollEvents`/`eventRow`). Test: sidebar.test.js.
- [ ] **Panel yeniden oluşturma:** `resolveWebviewView` yeniden çağrılınca `eventsSince` korunuyor ama liste boş
  başlıyor; yeniden çözümde `eventsSince = null` yapılsın ya da son 50 olay yeniden gönderilsin.
- [ ] **package-lock.json sürümü:** lock 0.1.18'de, package.json 0.1.24; `npm install --package-lock-only` ile hizala.

### 7.3 Ortam ve paketleme

- [ ] `npm ci` ile `vscode-textmate` kurulsun; `dru.test.js` geçsin; `npm test` tamamı yeşil.
- [ ] Node PATH'te değil (testler Playwright'ın `node.exe`'siyle koşuldu); Node LTS kurulumu.
- [ ] VSIX 0.1.24 üretilip kurulsun; PCM ZIP yeni dosyalarla (`assistant*.py`) yeniden üretilip KiCad'e kurulsun.
- [ ] Tam takım (`unittest discover`) birleşmiş main'de koşulup status.md'ye yazılsın.

### 7.4 Depo temizliği

- [ ] Birleşmiş dallar `ip/aj1-secici`, `ip/aj2-mcp`, `ip/aj3-istem`, `ip/aj4-kicad-pencere`, `ip/aj6-yerlesik`,
  `ip/aj7-etkinlik`, `ip/ajs1-wx` ve worktree'leri `PcbAi-aj2`, `-aj3`, `-aj4`, `-aj7`, `-ajs1` kaldırılsın
  (`ip/ajs1-wx`, AJ-S1 elle sonucu yazılana kadar tutulabilir).
