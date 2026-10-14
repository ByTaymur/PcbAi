# AJ-S1 — KiCad eklenti venv'inde wx pencere denemesi

Tarih: 14 Ekim 2026. Dal: `ip/ajs1-wx`. Ürün kodu değişmedi; yalnız deneme betikleri
(`scripts/spikes/ajs1/`) ve bu belge. Ham çıktılar: `.pcbai-state/ajs1/` (depoya girmez).
Bu koşuda KiCad **çalışmıyordu**; gerçek KiCad isteyen her ölçüm aşağıda "ölçülmedi — elle adım bekliyor".

## Ortam (ölçüldü)

- Eklenti venv'i: `%USERPROFILE%\AppData\Local\KiCad\10.0\python-environments\org.pcbai.kicad`,
  Python 3.11.5, `include-system-site-packages = true` (taban `C:\Program Files\KiCad\10.0\bin`).
- `import wx` → `4.2.2 msw (phoenix) wxWidgets 3.3.2`. tkinter yok (`_tkinter` eksik; önceki ölçüm).
- `kicad-python` (kipy) 0.8.0.

## Deneme betikleri

| Dosya | Görev |
|---|---|
| `scripts/spikes/ajs1/ajs1_window.py` | wx.Frame; tek örnek (kilit dosyası `ajs1.lock` = pid+port+belirteç, `127.0.0.1` soket, "raise <belirteç>"); `--parent-pid` izleme (OpenProcess/WaitForSingleObject, 250 ms); `--poll-ms` kipy `get_selection` yoklaması, her çağrı süresi + süreç CPU'su loga |
| `scripts/spikes/ajs1/plugin/` | Geçici düğme `org.pcbai.ajs1` / `pcbai.ajs1.window`; giriş `ajs1_action.py` pencereyi `DETACHED_PROCESS` ile başlatıp hemen döner, `ppid`, `KICAD_API*` ortamı ve dönüş süresini `action.jsonl`'e yazar |
| `scripts/spikes/ajs1/install_ajs1.py` | İzole kurulum/kaldırma (`--remove`); `kicad_plugin/install.py` ikon üreticisini kullanır. Sabit `org.pcbai.kicad` kimliğini kopyalayan `install.py --dest` ayrı identifier veremediği için ayrı betik yazıldı |
| `scripts/spikes/ajs1/run_ajs1_offline.py` | KiCad'siz betik düzeyi ölçüm (sahte üst süreç ile) |

İzole kurulum yerinde: `%USERPROFILE%\Documents\KiCad\10.0\plugins\org.pcbai.ajs1` (PCM kurulumu
`3rdparty\plugins\org_pcbai_kicad` dokunulmadı). Elle adımlar bitince kaldırma:
`.venv\Scripts\python.exe scripts\spikes\ajs1\install_ajs1.py --dest %USERPROFILE%\Documents\KiCad\10.0\plugins --remove`.

## Sonuçlar

| # | Madde | Durum | Ölçüm |
|---|---|---|---|
| 1 | venv python'u ile wx.Frame açılır, öne gelir, odak alır | **betik düzeyi ölçüldü**; KiCad önünde: ölçülmedi — elle adım bekliyor | Başlatmadan `shown`'a 0,535 s; `GetForegroundWindow == HWND` true, odak var (KiCad kapalı, üst süreç sahte) |
| 2 | Pencere açıkken PCB editörü bloklanıyor mu | ölçülmedi — elle adım bekliyor | Tasarım: giriş betiği ayrık süreç açıp döner; dönüş süresi `action.jsonl` `ms_to_return` |
| 3 | İkinci tıklamada mevcut pencere öne gelir | **betik düzeyi ölçüldü**; KiCad düğmesinden: ölçülmedi — elle adım bekliyor | İkinci süreç sinyal + çıkış 0,247 s toplam (süreç başlatma dahil), soket gidiş-dönüş < 5 ms; ilk pencere `is_foreground` true, ikinci pencere açılmadı. Not: Windows ön plan kısıtı KiCad'den başlatılan ayrık süreçte farklı davranabilir |
| 4 | kipy seçim okuma + 500 ms yoklama maliyeti | **yalnız bağlantısız yol ölçüldü**; gerçek `get_selection`: ölçülmedi — elle adım bekliyor | KiCad yokken 12 yoklama: ilk 175,7 ms (kipy import + bağlantı reddi), sonrakiler medyan 0,94 ms; toplam CPU 78 ms. Hata `ConnectionError('Failed to connect to KiCad: Connection refused')` pencerede gösterildi, pencere çökmedi |
| 5 | KiCad kapanınca pencere kapanır | **betik düzeyi ölçüldü** (sahte üst süreç); gerçek KiCad: ölçülmedi — elle adım bekliyor | Üst süreç öldürüldükten 0,287 s sonra pencere süreci çıktı, kilit dosyası silindi. Açık: düğme sürecinin `os.getppid()`'i gerçekten KiCad mı — `action.jsonl` `ppid` ile doğrulanacak |
| 6 | kipy/IPC'de diskten yeniden yükleme/revert | **API incelemesi ölçüldü**; çalışma anı: ölçülmedi | kipy 0.8.0 `Board.revert()` ("Reverts the board to the last saved state") → `editor_commands_pb2.RevertDocument`; `Schematic.revert()` da var. KiCad 10 sunucusunun bu komutu kabul edip etmediği canlı denenmedi (AJ-7 için kart değiştirmeyen bir kopyada denenmeli) |

## Elle adımlar (KiCad 10 açıkken)

1. KiCad'i başlat, bir kopya kartı PCB editöründe aç; Tercihler → Eklentiler'de API açık olmalı. Araç çubuğunda
   "AJ-S1 pencere denemesi" düğmesi görünüyor mu (KiCad ilk kullanımda `org.pcbai.ajs1` venv'ini kurar).
2. Düğmeye bas: pencere KiCad'in önünde mi, odakta mı (yazı yazılabiliyor mu)?
3. Pencere açıkken kartta bir öğeyi taşı/seç, menüleri kullan: editör donuyor mu?
4. Birkaç öğe seç: penceredeki "Seçim: N öğe" 500 ms içinde değişiyor mu? Görev Yöneticisi'nde pythonw CPU'su.
5. Düğmeye ikinci kez bas: yeni pencere açılmamalı, mevcut öne gelmeli (KiCad'i önce öne getirip dene).
6. KiCad'i kapat: pencere 1 sn içinde kapanıyor mu?
7. (İsteğe bağlı, kopya kartta) kipy `KiCad().get_board().revert()` çalıştır: kart diskteki hâline dönüyor mu?
8. Kanıt: `.pcbai-state/ajs1/action.jsonl` ve `window.jsonl` dosyalarını (worktree kökü
   `%USERPROFILE%\Documents\PcbAi-ajs1`) bu belgeye işle; sonra kaldırma komutunu çalıştır.

## Ön karar

Eldeki veriye göre **wx** (ayrı süreç, `DETACHED_PROCESS`, tek örnek soket, üst PID izleme): venv'de wx var,
açılış/ön plan/tek örnek/üst süreç kapanışı betik düzeyinde çalıştı, tkinter yok. Kesin karar elle adımlar 1–6'ya
bağlı. Ret koşulları: KiCad önünde açılmıyor/odak almıyor veya editörü blokluyorsa yedek (1) servisin
`127.0.0.1` + belirteçli yerel sayfası varsayılan tarayıcıda, (2) bugünkü MessageBox + pano.
