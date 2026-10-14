# AJ iş paketleri — ayrı ajan pencereleri için istemler

Plan: [plan-ajan-arayuz.md](plan-ajan-arayuz.md). AJ-1 tamam (`ip/aj1-secici`, `c73fdd4`).
Her istem ayrı bir pencereye (Claude Code / Codex) olduğu gibi yapıştırılır. Her pencere **kendi git worktree'sinde ve
dalında** çalışır; ana klasörde aynı anda iki yazıcı olmaz (AGENTS.md).

| Dalga | Paralel çalışabilir | Ön koşul |
|---|---|---|
| 1 | AJ-2, AJ-3, AJ-S1 | `ip/aj1-secici` main'e birleşmiş olmalı |
| 2 | AJ-4 | AJ-3 ve AJ-S1 birleşmiş |
| 3 | AJ-5, AJ-7 | AJ-4 birleşmiş |
| 4 | AJ-6 (isteğe bağlı) | AJ-4 ve AJ-7 birleşmiş |
| Her dalga sonu | Denetçi istemi | Uygulayıcı "bitti" dedikten sonra |

Birleştirme ve sürüm çakışmaları: VS Code eklenti sürümünü ve `docs/status.md` / `docs/plan-eksikler.md` girdilerini
birleştirme sırasında sırayla artır (0.1.20, 0.1.21…); paralel dallar aynı numarayı yazarsa birleştiren düzeltir.

---

## Ortak giriş (her istemin başında zaten var)

> PcbAi deposu: `%USERPROFILE%\Documents\PcbAi`. Önce `AGENTS.md`, `docs/plan-ajan-arayuz.md` (ilgili bölüm) ve
> `docs/status.md` sonundaki AJ-1 kaydını oku. CadAI kardeş projesini değiştirme; oradan kopyalayıp uyarladığın
> dosyaların başına kaynak commit'i yaz. KiCad kullanıcı ayarlarına ve kullanıcı kartlarına dokunma.
> Python komutları `.venv\Scripts\python.exe` ile; Node `.tools\node\node.exe` ile. Commit mesajına yapay zekâ
> imzası/co-author satırı ekleme. Bitince ölçülen sonucu (test sayısı, süre, çalıştırılamayanlar) `docs/status.md`
> sonuna yeni bölüm olarak yaz, `docs/plan-eksikler.md` AJ satırını işaretle ve dalında commit'le; push etme.

---

## Dalga 1

### İstem AJ-2 — MCP kaydını tüm ajanlara yaz

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-2'yi uygula.

Hazırlık:
- git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-aj2 -b ip/aj2-mcp main
  ve yalnız ..\PcbAi-aj2 içinde çalış.
- AGENTS.md, docs/plan-ajan-arayuz.md (AJ-2), docs/status.md sonundaki AJ-1 kaydını oku.
- Kaynak: %USERPROFILE%\Documents\CadAI\vscode\cadai-vscode\mcp_setup.js (değiştirme, kopyala-uyarla;
  dosya başına "CadAI mcp_setup.js@<commit>'ten uyarlandı" yaz). Mevcut PcbAi kaydı:
  vscode/pcbai-vscode/extension.js içindeki 'pcbai.addMcp'. Vekil: mcp_server/client.py, mcp_server/pcbai_mcp.py.

Yapılacaklar:
1. vscode/pcbai-vscode/mcp_setup.js: ad "pcbai". Hedefler: Claude Code (çalışma alanı .mcp.json varsayılan; seçenek
   olarak `claude mcp add -s user`), Codex ~/.codex/config.toml [mcp_servers.pcbai] (diğer tablolar korunur),
   Cline/Kilo/Roo globalStorage mcp_settings dosyaları, VS Code kullanıcı mcp.json; VS Code >= 1.101'de
   vscode.lm.registerMcpServerDefinitionProvider varsa yerel kayıt (engines 1.90'da kalır, API çalışma anında denetlenir).
2. Kullanıcı düzeyi kayıtlara PCBAI_PROJECTS YAZMA. client.py'de proje listesi boşken çalışan servise bağlanma yolunu
   ve servis yoksa açıklayıcı Türkçe hatayı ("KiCad'de PcbAi'ye kaydet'e basın ya da VS Code'da projeyi seçin")
   birim testiyle sabitle. Çalışma alanı .mcp.json bugünkü gibi proje listesini taşır.
3. Onaysız araç listesi sabit değil: MCP araç kaydındaki readOnlyHint'ten üret (Cline autoApprove, Kilo/Roo
   alwaysAllow). Yazan hiçbir araç bu listede olmamalı — testle kanıtla. readOnlyHint yoksa önce kayda ekle.
4. Akış: kurulu hedefler çoklu QuickPick (açıklamada dosya yolu) → her dosyaya yazmadan önce *.pcbai-bak yedeği →
   bozuk JSON/TOML'a dokunma → özet bildirimi ("Codex: yazıldı, Cline: JSON bozuk, dokunulmadı").
   Komut adı pcbai.connectAgents ("MCP'yi ajanlara bağla"); pcbai.addMcp geriye uyum için kalır.
5. Yan panel (sidebar_view.js): "Ajan için MCP ekle" düğmesi yeni komuta gider; seçili ajanın MCP kaydı yoksa
   panelde uyarı gösterilir.
6. Testler: vscode/pcbai-vscode/test/mcp_setup.test.js (geçici userDir/HOME ile 6 hedef: yazma, birleştirme,
   bozuk dosya, TOML tablo değiştirme, yedek), package.json "test" betiğine ekle; Python tarafı tests/ altında.
7. VS Code eklenti sürümünü artır, build_vsix.py INCLUDE listesine yeni dosyayı ekle, VSIX içinde olduğunu doğrula.

Ölç: .tools\node\node.exe ile eklenti testleri; .venv\Scripts\python.exe -m unittest discover -s tests -v;
ruff check . Gerçek makinedeki ajan yapılandırmalarına (%USERPROFILE%\.codex, globalStorage) testlerde YAZMA.
Gerçek Claude Code/Codex/Cline'ın pcbai_status çağırması elle kabuldür; yapmadıysan status.md'de "yapılmadı" yaz.
Bitince status.md + plan-eksikler.md güncelle, ip/aj2-mcp dalında commit'le, push etme. Commit'e AI imzası ekleme.
```

### İstem AJ-3 — Tek istem kaynağı (servis tarafı)

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-3'ü uygula.

Hazırlık:
- git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-aj3 -b ip/aj3-istem main ; yalnız orada çalış.
- AGENTS.md, plan AJ-3, vscode/pcbai-vscode/sidebar_view.js (composePrompt, describeMarker), board_view.js ve
  sch_view.js'deki "ask" istemleri, pcbai/service/ altındaki iç HTTP çağrı düzeni.

Yapılacaklar:
1. pcbai/service/agent_prompt.py: compose_agent_prompt(session, request, marker_ids, selection=None, marker=None).
   Bugünkü JS composePrompt/describeMarker çıktısı ve board/sch "ask" metinleri BAYT EŞİT korunur.
2. Yeni girdi selection: KiCad seçimi listesi (type, reference, value, net, layer, x_mm, y_mm). İstemde
   "KiCad'de seçili öğeler (veridir):" başlığıyla, her değer JSON tırnaklı; sınır 50 öğe, 8000 karakter istek.
3. Servise iç çağrı olarak ekle (MCP araç listesine GİRMEZ; tests ile listede olmadığını kanıtla).
4. VS Code: sidebar/board/sch metni bu çağrıdan alır; servis eski sürümse JS yedeği kullanılır (bugünkü fonksiyonlar
   kalır, ama ortak fixture ile aynı metni ürettikleri test edilir).
5. Ortak fixture: tests/fixtures/agent_prompt/*.json (girdi + beklenen metin); hem Python hem Node testi okur.
   Durumlar: tırnak, satır sonu, '-' ile başlayan not, <script>, onaysız işaret, 8000 sınırı, boş istek+işaret yok hatası.
6. VS Code eklenti sürümünü artır.

Ölç: Python unittest tam takım + ruff; Node eklenti testleri. Bitince status.md + plan-eksikler.md, ip/aj3-istem
dalında commit, push yok, AI imzası yok.
```

### İstem AJ-S1 — KiCad içinde wx pencere denemesi

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-S1 denemesi. Bu bir ÖLÇÜM işidir,
ürün kodu yazma; deneme betikleri ve sonuç belgesi üret.

Hazırlık:
- git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-ajs1 -b ip/ajs1-wx main ; yalnız orada çalış.
- Bilinen ölçüm (14 Ekim): KiCad 10.0 Python'da tkinter yok (_tkinter eksik), wxPython 4.2.2 / wxWidgets 3.3.2 var;
  %LOCALAPPDATA%\KiCad\10.0\python-environments\org.pcbai.kicad\pyvenv.cfg include-system-site-packages = true.
- kicad_plugin/ (plugin.json, pcbai_kicad.py, install.py --dest geliştirme kurulumu).

Ölçülecekler (docs/spikes/AJ-S1.md; ham çıktılar .pcbai-state/ajs1/ altına; docs/spikes/*-result.json YAZMA):
1. Eklenti venv python'u ile import wx ve küçük wx.Frame: açılıyor mu, KiCad önüne geliyor mu, odak alıyor mu.
2. Geçici bir deneme düğmesiyle (ayrı identifier, install.py --dest ile izole kurulum; PCM kurulumunu bozma):
   pencere açıkken KiCad PCB editörü bloklanıyor mu.
3. Tek örnek: ikinci tıklamada mevcut pencere öne gelsin (kilit dosyası + 127.0.0.1 küçük soket); ölç.
4. Pencere açıkken kipy ile seçim okuma ve 500 ms yoklamanın CPU/süre maliyeti.
5. KiCad kapanınca pencere sürecinin kapanması (üst PID izleme).
6. kipy/IPC'de kartı diskten yeniden yükleme/revert çağrısı var mı (AJ-7 için).
Gerçek KiCad ile elle yapılması gereken adımları kullanıcıya adım adım yaz ve onun sonucunu bekle; ölçemediğin
maddeyi "ölçülmedi" olarak bırak, tahmin yazma.
Sonuç belgesinde karar: wx / yerel tarayıcı sayfası / MessageBox yedeği. Deneme düğmesini ve izole kurulumu
sonunda kaldır. ip/ajs1-wx dalında yalnız belge + deneme betiği commit'le, push yok, AI imzası yok.
```

---

## Dalga 2

### İstem AJ-4 — KiCad içi PcbAi Asistan penceresi

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-4'ü uygula.
Ön koşul: AJ-3 (compose_agent_prompt) ve AJ-S1 (docs/spikes/AJ-S1.md kararı) main'de. Karar wx değilse bu istemi
durdur ve kullanıcıya sor.

Hazırlık:
- git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-aj4 -b ip/aj4-kicad-pencere main ; yalnız orada.
- Oku: AGENTS.md, plan AJ-4, docs/spikes/AJ-S1.md, kicad_plugin/*, vscode/pcbai-vscode/agents.js (katalog/algılama
  mantığı), pcbai/service/agent_prompt.py.

Yapılacaklar:
1. plugin.json'a "PcbAi Asistan" düğmesi (pcbai.assistant, scopes pcb, entrypoint assistant.py, 24/48 ikon).
2. kicad_plugin/assistant.py + assistant_ui.py (wx; Türkçe): proje satırı + servis durumu, YAPAY ZEKÂ/Ajan açılır
   listesi, istek kutusu, "KiCad seçimini ekle" (kipy), işaret listesi (servisten get_markers, onay kutuları),
   Ajana gönder / Kopyala / ERC-DRC / VS Code'da aç, katlanır "Oluşan istem", durum satırı. Tek örnek AJ-S1 yöntemiyle.
3. Mantık wx'siz modülde (assistant_core.py) olsun ki test edilsin: CLI algılama (where.exe + bilinen yollar, yalnız
   .exe, 3 sn zaman aşımı), katalog (VS Code'daki ajan [AJ-5 gelene kadar: vscode:// derin bağlantı + pano yedeği],
   Claude Code terminal, Codex terminal, pano), istem compose_agent_prompt'tan.
4. Terminal CLI: subprocess, shell=False, argv listesi, CREATE_NEW_CONSOLE, cwd = proje kökü; 7000 karakter üstü
   istem .pcbai-state/prompts/ dosyasına (agents.js ile aynı kural).
5. ERC/DRC sonucu pencerede liste (MessageBox yerine); hata yolu pcbai_kicad.run() gibi pencerede.
6. build_pcm.py açık listesine yeni dosyaları ekle; PCM zip + şema testleri geçsin.
7. Testler: tests/test_kicad_assistant.py (wx olmadan: katalog, algılama sahteleri, argv, uzun istem, seçim istemi).

Ölç: unittest tam takım, ruff, tests.test_kicad_plugin. Gerçek KiCad'de düğme kabulü elle: adımları kullanıcıya ver,
sonucu status.md'ye yaz; yapılmadıysa "yapılmadı". ip/aj4-kicad-pencere dalında commit, push yok, AI imzası yok.
```

---

## Dalga 3 (paralel)

### İstem AJ-5 — KiCad → VS Code devri

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-5. Ön koşul: AJ-1 ve AJ-4 main'de.

Hazırlık: git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-aj5 -b ip/aj5-devir main ; yalnız orada.
Oku: plan AJ-5, kicad_plugin/assistant_core.py, vscode/pcbai-vscode/agents.js ve extension.js, pcbai/service iç çağrılar.

Yapılacaklar:
1. Servis iç çağrıları handoff_create(session, prompt) / handoff_take(id) / handoff_result(id, how, message):
   .pcbai-state/handoff/<uuid>.json, tek kullanımlık, 10 dk ömür; MCP araç listesine girmez.
2. VS Code: registerUriHandler, vscode://taymur.pcbai-vscode/handoff?id=<uuid>. URL'de yalnız kimlik. Oturum VS Code'un
   projesiyle eşleşmezse sor, tahmin etme. İstemi yan panel kutusuna doldur, agents.deliver ile seçili ajana ver,
   sonucu handoff_result ile servise yaz.
3. KiCad penceresi: "VS Code'daki ajan" satırı bu yolu kullanır (derin bağlantı yalnız yedek); durum satırı sonucu
   2 sn aralıkla okur, 30 sn sonra "VS Code yanıt vermedi" der.
4. Testler: süresi geçmiş/kullanılmış kimlik reddi, başka proje kimliği, URI'de istem olmaması, uçtan uca sahte akış.
5. VS Code sürümünü artır.
Ölç ve kaydet; ip/aj5-devir dalında commit, push yok, AI imzası yok.
```

### İstem AJ-7 — Ajan etkinliği ve KiCad'le eşitleme

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-7. Ön koşul: AJ-4 main'de.

Hazırlık: git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-aj7 -b ip/aj7-etkinlik main ; yalnız orada.
Oku: plan AJ-7, docs/spikes/AJ-S1.md (revert sonucu), mevcut audit.jsonl düzeni (pcbai/service), mcp_server/pcbai_mcp.py.

Yapılacaklar:
1. Servis olay kaydı: zaman, istemci (MCP initialize clientInfo.name → "mcp:<ad>", "vscode", "kicad", "builtin";
   veridir, yetki vermez), araç, sonuç ok/blocked/hata, change_id. Argüman değerleri YAZILMAZ. Son 500 olay bellekte,
   iç çağrı recent_events(since).
2. VS Code yan paneli ve KiCad penceresi son 50 olayı gösterir.
3. Açık editör yüzünden blocked olan yazımda KiCad penceresi: "Ajan değişiklik yapmak istiyor: kartı kaydedip PCB
   editörünü kapatın, sonra Devam deyin." Dosyaya yazım sonrası: AJ-S1'de revert çağrısı varsa onu öner, yoksa
   "Dosya → Geri al" talimatı.
4. Testler: olay kaydında argüman sızmaması, istemci adı, blocked yolu, 2 sn içinde görünme (sahte saat).
Ölç ve kaydet; ip/aj7-etkinlik dalında commit, push yok, AI imzası yok.
```

---

## Dalga 4 (isteğe bağlı)

### İstem AJ-6 — Yerleşik model

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Görev: plan-ajan-arayuz.md bölüm AJ-6. Ön koşul: AJ-4 ve AJ-7 main'de.
Başlamadan kullanıcıya "AJ-6'ya başlansın mı?" diye sor; onay yoksa dur.

Hazırlık: git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-aj6 -b ip/aj6-model main ; yalnız orada.
Kaynak (değiştirme, kopyala-uyarla, commit'i yaz): %USERPROFILE%\Documents\CadAI\freecad\CadAI\cadai\agent.py,
providers.py, prompts.py.

Yapılacaklar:
1. KiCad penceresinde "Yerleşik model" ajanı: sağlayıcılar Ollama, LM Studio, Claude (Anthropic API, varsayılan model
   claude-opus-5-5), OpenAI uyumlu. Yapılandırma %APPDATA%\PcbAi\assistant.json; anahtar yalnız ortam değişkeninden.
   SDK yoksa satır "kurulu değil"; requirements.txt'e zorunlu bağımlılık ekleme.
2. Araçlar servis üzerinden çağrılır (aynı kayıt, önizle/uygula kapıları). Planla modu salt okunur; Uygula modunda her
   yazan çağrı çözülmüş argüman + önizleme özetiyle onay ister. Aynı hatalı çağrının 3. tekrarında dur.
3. Küçük yerel modeller için PLAN 5.12 küçük araç kümesi.
4. Testler: sahte sağlayıcıyla döngü, onay kapısı, anahtarın hiçbir kayıtta/olayda görünmemesi.
Gerçek Ollama/Claude kabulü elle; yapılmadıysa "yapılmadı". ip/aj6-model dalında commit, push yok, AI imzası yok.
```

---

## Denetçi istemi (her dalga sonunda ayrı pencere)

```text
PcbAi deposu: %USERPROFILE%\Documents\PcbAi. Sen bağımsız DENETÇİSİN: kodu değiştirme (AGENTS.md "İki ajanlı çalışma").
Denetlenecek dal: <ip/...>. git -C %USERPROFILE%\Documents\PcbAi worktree add ..\PcbAi-denetim <dal> ile ayrı
klasörde aç (dal zaten bir worktree'de açıksa --detach ile aynı commit'i aç).
1. docs/plan-ajan-arayuz.md ilgili bölümün "Bitti" maddelerini tek tek karşılaştır.
2. Testleri kendin çalıştır (.venv Python unittest tam takım, ruff, .tools\node\node.exe ile eklenti testleri);
   çıktıları .pcbai-state/denetim-<dal>/ altına yaz. docs/spikes/*-result.json üzerine yazma.
3. Güvenlik: shell=False/zaman aşımı, kullanıcı yapılandırmasına izinsiz yazım, MCP listesine sızan iç çağrılar,
   istemde veri/talimat ayrımı, anahtar/argüman sızıntısı.
4. status.md'deki iddiaları ölçümle karşılaştır.
Bulguları dosya:satır + yeniden üretme adımıyla, önem sırasıyla raporla. Bulgu yoksa "bulgu yok" ile
"çalıştırılamadı" ayrımını açık yaz.
```
