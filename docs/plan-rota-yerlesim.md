# Plan — Dış rota ve yerleşim motorları (TraceMaker + Freerouting)

12 Ekim 2026. Uygulayan: Codex (dal `ip/r-motorlar`, adımlara göre alt dallar). Denetleyen: Claude.
Bu belge PLAN.md 5.7, 5.8, Faz 5 ve K5'i değiştirir; değişen satırlar PLAN.md'de bu belgeye bağlanır.

12 Ekim uygulama: dal `ip/plan-tamamlama`, uygulayan Codex, bağımsız salt okunur Codex denetçisi.
Çekirdek 0.1.7 / VS Code 0.1.16. Aşağıdaki mimari hedeftir; güncel paket durumu bölüm 11'dedir.

## 0. Özet

- **Ne:** PcbAi kendi otorota ve tavlama motorunu yazmak yerine iki dış motoru **ayrı program** olarak çağırır:
  [TraceMaker](https://github.com/DingoOz/TraceMaker) (rota + yerleşim, GPL-3.0, C++20, Linux) ve Freerouting 2.5
  (rota, GPL-3.0, Windows yerel CLI). PcbAi'nin işi motorun etrafındaki güvenlik ve kanıttır: kopya üzerinde çalıştırma,
  motorun yalnız izin verilen öğelere dokunduğunu bayt düzeyinde doğrulama, DRC önce/sonra, ölçüm, önizleme,
  kontrol noktası, onayla uygulama.
- **Neden:** TraceMaker README'si (doğrulanmadı, S10'da ölçülecek) PCBench'te en zor grupta %54,5 temiz kart
  bildiriyor, Freerouting 2.5 %36,4. Yerleşimi var (`auto`, `routable`, `eco`, `--scratch`), kilitli parçaya ve yasak
  alana dokunmuyor, `--work` ile deterministik. Bizim Faz 5b'de yazacağımız tavlama motorunun yerini alabilir.
- **İlk karar noktası:** S10 + S4 denemeleri (2–3 gün). Sonuç K5'i kapatır: hangi motor varsayılan, kendi tavlamamız
  yazılacak mı.

## 1. Başlangıç durumu (12 Ekim 2026, bu makinede ölçüldü)

| Konu | Durum |
|---|---|
| WSL | `wsl.exe` var, **kurulu dağıtım yok** (yalnızca kullanım metni dönüyor) |
| Docker, cmake, gcc/g++, clang, MSVC `cl`, ninja | **Yok** |
| Java | Yok (Freerouting 2.5 Windows CLI'si Java istemiyor — PLAN 2.1) |
| KiCad | 10.0.4; `bin/python.exe` ve `_pcbnew.dll` var (DSN dışa aktarma için) |
| `doctor` | `freerouting`'i yalnız PATH'te arıyor; TraceMaker girdisi yok |
| PcbAi kart düzenleme | `move_footprint`, `set_track_width`, `add_zone`, `set_netclass`: önizle/uygula, DRC önce/sonra, `new_violations` engeli, kontrol noktası (`pcbai/tools/engine.py` `PCB_EDITS`) |
| Arka plan işleri | `start_job` yalnız salt okunur araçlar için (`job_tools` listesi) |

TraceMaker hakkında bildiklerimiz yalnızca README ve commit listesinden: sürüm 0.9.0, 346 commit, son commit
11 Ekim 2026; Windows/MSVC/MinGW anılmıyor; çıktı her örnekte ayrı dosyaya (`-o`); çıkış kodları ve özet biçimi
belgelenmemiş; derleme bağımlılıkları (Boost, Eigen, oneTBB, fmt, spdlog, FlatBuffers, SQLite, Catch2, pybind11,
Clipper2) eksikse CMake indirip derliyor. Bunların hepsi S10'da ölçülür.

## 2. Kararlar

| Kod | Karar | Öneri | Durum |
|---|---|---|---|
| K5 (güncellendi) | Yerleşim/rota motoru | Aday: TraceMaker-place, TraceMaker route, Freerouting 2.5, kicad-tools; kendi tavlamamız **yalnızca** adaylar 6. bölümdeki ölçütü tutturamazsa yazılır | S10 + S4 sonrası |
| K12 | TraceMaker'ın lisans sınırı | GPL-3.0: kod alınmaz, bağlanmaz (pybind11 bağlaması dahil), ikili dosya PcbAi paketlerine konmaz. Kullanıcı kendisi kurar, PcbAi yapılandırılmış yolu çağırır (KiCad ve Freerouting ile aynı) | Uygulandı; [0003](decisions/0003-engines.md) |
| K13 | TraceMaker'ın çalışma ortamı | **WSL2 + Ubuntu**, `cpu-only` ön ayarı, `--no-gpu` | Kullanıcı onayladı; Windows bileşenleri kuruldu, yeniden başlatma + Ubuntu bekliyor |
| K14 | Kıyas seti | KiCad demoları (lisanslı, kurulumdan); PCBench indirilmez | Kullanıcı **yalnız KiCad demolarını** seçti |

## 3. Mimari

### 3.1 Motor bağdaştırıcısı — `pcbai/pcb/engines/`

```
engines/
  __init__.py     ENGINES = {"tracemaker": ..., "freerouting": ...}; available(), describe()
  base.py         EngineRun(argv, input, output, budget) → RunResult{returncode, seconds, stdout_tail,
                  stderr_tail, output_path, engine, version, args}
  tracemaker.py   route(), place(); seçenek izin listesi; sürüm/commit okuma
  freerouting.py  DSN dışa aktarma (KiCad python + pcbnew, ayrı süreç) → CLI → SES içe aktarma (aynı yol)
  wsl.py          Windows yolu ↔ /mnt/<sürücü>/… dönüşümü; wsl.exe argv kurucu
```

- **Program yolları yalnız ortam/yapılandırmadan** (AGENTS.md): `PCBAI_TRACEMAKER`, `PCBAI_TRACEMAKER_PLACE`,
  `PCBAI_FREEROUTING`. Değer ya Windows dosya yolu ya da `wsl:<dağıtım>:<mutlak linux yolu>`. Araç argümanı olarak
  program yolu **asla** kabul edilmez. `pcbai.external`'a `find_tracemaker()`, `find_freerouting()` eklenir.
- **WSL çağrısı:** `["wsl.exe", "-d", dağıtım, "--exec", linux_yolu, …]`, `shell=False`. `--exec` WSL tarafında da
  kabuk açmaz; argümanlar tek tek geçer. Yol dönüşümü bizde yapılır (`wslpath` çağrılmaz). Dağıtım adı ve yol
  `[A-Za-z0-9._/-]` dışında karakter içeriyorsa reddedilir.
- **Zaman aşımı zorunlu:** bütçe + 30 sn pay. Zaman aşımında süreç ağacı öldürülür. `wsl.exe` istemcisini öldürmenin
  Linux tarafındaki süreci sonlandırıp sonlandırmadığı **S10'da ölçülür**; sonlandırmıyorsa `wsl.exe -d … --exec
  pkill -f <geçici klasör adı>` yedeği eklenir (adı geçici klasörün rastgele adından kurulur).
- **Determinizm:** varsayılan `--work N` (sabit arama bütçesi). `--time` yalnız kullanıcı açıkça isterse ve kanıtta
  `deterministic: false` yazılır. Her koşuda motor sürümü, git commit'i, tam argv ve girdi/çıktı SHA-256 kanıta yazılır.
- **Seçenek izin listesi (TraceMaker route):** `--work`, `--time`, `--threads`, `--variants`, `--no-gpu` (her zaman
  açık), `--diff-pairs`, `--reroute`, `--component-rules`, `--no-tracks-on`, `--widen-power`, `--stitch-vias`.
  **Yasak:** `--view`/`--hold` (localhost:8766'da sunucu açar), `--config`, `--rules-override`, `--kb` (dosya yolu alır;
  gerekirse ileride proje kökü içine çözülerek eklenir), `--bus*` ve `--stitch-return` (proje kendisi deneysel diyor).
- **Yerleşim seçenekleri:** `--mode auto|routable|eco`, `--scratch` yalnızca kartta yerleşim yoksa, `--route-check`.

### 3.2 Kopya üzerinde çalıştırma

1. Kayıtlı kart dosyası belirtilen revizyonda okunur (mevcut hedef/revizyon denetimi).
2. Özel geçici klasöre kopyalanır: `.pcbai-state/engine-runs/<rastgele>/in.kicad_pcb`. Proje klasöründe hiçbir şey
   oluşmaz. WSL'de `/mnt/c` üzerinden okuma/yazma hızı S10'da ölçülür; yavaşsa girdi Linux tarafındaki geçici
   klasöre kopyalanır ve sonuç geri alınır.
3. Motor `in` → `out` yazar. Çıktı yoksa, boşsa, ayrıştırılamıyorsa → `engine_failed` + stderr'in son 4 KB'ı.
4. **Yabancı değişiklik denetimi** (3.3) → ölçüm (3.4) → aday.

### 3.3 Yabancı değişiklik denetimi — `pcbai/pcb/engine_guard.py`

TraceMaker "kendi oluşturmadığı hiçbir şeyi değiştirmez" diyor. Buna güvenilmez, **ölçülür**:

- Bizim bayt koruyan s-expr ayrıştırıcımızla `in` ve `out` kök çocukları UUID'ye göre eşlenir.
- **Rota adayında izin verilenler:** yeni `segment`, `arc`, `via`; zonlarda yalnızca `filled_polygon` ve
  `filled_areas_thickness` değişikliği; `--reroute` açıksa mevcut `segment`/`arc`/`via` silinmesi. Başlık `(version …)`
  ve `(generator …)` dahil diğer her düğüm **bayt bayt aynı** olmalı.
- **Yerleşim adayında izin verilenler:** footprint'in `at` düğümü; yüz değişiminde (`--scratch`/`eco`) PcbAi'nin
  `_toggle_mirror` ile aynı kurallarla değişen katman/ayna alanları. Kilitli (`locked`) footprint'te **hiçbir** değişiklik.
  İzler ve via'lar dokunulmadan kalmalı.
- Bunun dışındaki her fark → aday üretilmez, `engine_touched_foreign_items` + fark listesi (en çok 50 öğe, UUID +
  düğüm türü). Bu, motor sürümü değiştiğinde ilk kırılacak yerdir; testi vardır (bölüm 8).
- Yeni öğelerin UUID'leri benzersiz mi, net numarası/adı karttaki net tablosunda var mı — denetlenir.

### 3.4 Ölçüm ve önizleme

Her aday için kopyalarda (mevcut `kicad-cli` yolu, özel `KICAD_CONFIG_HOME` ile):

| Ölçü | Kaynak |
|---|---|
| Rotalanmamış bağlantı önce/sonra | `kicad-cli pcb drc` JSON `unconnected_items` |
| DRC hatası önce/sonra, **yeni** hatalar | mevcut `new_violations` mantığı (UUID + tür + konum) |
| Via sayısı, toplam iz uzunluğu (mm), katman başına uzunluk | kendi s-expr okuyucumuz |
| Yerleşimde: taşınan parça sayısı, kart dışına konan parçalar, avlu çakışması | okuyucu + DRC `courtyards_overlap` |
| Süre, motor sürümü, argv, deterministik mi | RunResult |
| Görüntü | mevcut kart SVG'si (G5 yolu) önce/sonra; 3B isteğe bağlı |

**Uygulama engelleri:** yeni DRC hatası (mevcut kural), kart dışına konmuş parça, yabancı değişiklik. Rotalanmamış
bağlantının artması da engeldir (motor hiçbir zaman eskisinden kötü sonuç uygulatmaz).

### 3.5 Araçlar (MCP)

| Araç | Ne yapar | Biçim |
|---|---|---|
| `autoroute` | Seçilen motorla rota adayı | önizleme = arka plan işi (dakikalar sürebilir), sonucu `candidate_id` + 3.4 ölçüleri; uygulama = mevcut PCB_EDITS akışı (aynı revizyon, kapalı editör, kontrol noktası, kanıt) |
| `autoplace` | Seçilen kipte yerleşim adayı | aynı |
| `route_engines` | Kurulu motorlar, sürümleri, deterministik destek, ortam (yerel/WSL) | salt okunur |

- `engine` argümanı yalnız `tracemaker` / `freerouting`; kurulu değilse `missing_dependency` + `doctor` önerisi.
- `start_job` bugün yalnız salt okunur araçları kabul ediyor. `autoroute`/`autoplace` **önizleme** kipi projeye
  yazmaz, adayı bellekte tutar; bu yüzden iş listesine yalnız `mode: "preview"` ile eklenir. İş bittiğinde sonuç
  `candidate_id` taşır; adayın ömrü iş bitişinden başlar. Uygulama iş olarak çalıştırılamaz.
- Kart dışına konan parça, rotalanamayan bağlantılar ve yeni DRC konumları **işaret** olarak görünüme düşer
  (mevcut işaret biçimi, `source: "engine"`, `trusted: true`, durum `open`).

### 3.6 VS Code

- Kenar çubuğu eylem listesine "Otomatik rota (önizle)" ve "Otomatik yerleşim (önizle)". Motor seçimi, bütçe.
- İş ilerlemesi (job_status yoklaması), bitince önce/sonra görünüm yan yana + ölçü tablosu + "Uygula" / "Vazgeç".
- Uygulama yine ajan/servis üzerinden aynı aday kimliğiyle; görünüm doğrudan dosyaya yazmaz.

### 3.7 doctor

`tracemaker`: `{available, path, via: "wsl"|"native", distro, version, commit, cpu_only, tested: false}`.
`freerouting`: `PCBAI_FREEROUTING` ya da PATH; `--version`. `wsl`: dağıtım listesi (`wsl.exe -l -q`, UTF-16 çıktısı
çözülerek). Hiçbiri ölçülmeden `tested: true` yazılmaz.

## 4. Lisans sınırı (K12)

- TraceMaker ve Freerouting GPL-3.0: **yalnızca ayrı süreç**, dosya üzerinden veri alışverişi. Kod kopyalanmaz,
  pybind11 bağlamaları (`bindings/`) içe aktarılmaz, ikili dosya PcbAi'nin PCM ya da VS Code paketine konmaz.
- PLAN 2.5 lisans tablosuna satır eklenir; CI'daki lisans denetimi `bindings`/`tracemaker` Python paketlerini de
  yasak listesine alır.
- TraceMaker'ın kendi KiCad eklentisi PcbAi tarafından kurulmaz ya da çağrılmaz; kullanıcı isterse ayrıca kurar.
  İkisi aynı anda yüklüyse araç çubuğunda iki ayrı düğme olur — README'de not.

## 5. Denemeler

### S10 — TraceMaker (WSL) — 1,5 gün, K13 kabul edildikten sonra

1. Ubuntu'da `cpu-only` ön ayarıyla derleme; süre, disk, derleyici sürümü. Derlenen commit sabitlenir
   (`docs/spikes/S10.md`'ye hash).
2. Beş demo kart (ecc83, pic_programmer, video, interf_u, stickhub) için **izleri kaldırılmış kopyalar**: segment, arc,
   via silinir, zonlar kalır (küçük betik `scripts/strip_tracks.py`, bizim s-expr yazıcımızla).
3. Her kart: `tracemaker route in -o out --work N --no-gpu` (N S10'da seçilir), ardından **Windows'taki**
   `kicad-cli pcb drc` (KiCad 10.0.4). Ölçüler 3.4'teki tablo.
4. Aynı N ile iki koşu → çıktı SHA-256 aynı mı (determinizm iddiası).
5. Yabancı değişiklik denetiminin ilk sürümü elle: `in`/`out` farkı yalnız izin verilen düğümlerde mi.
6. `tracemaker-place` `--mode routable` ve `--scratch` (footprint'leri kart dışına yığılmış kopyada).
7. Zaman aşımı: `wsl.exe` istemcisi öldürülünce Linux süreci kalıyor mu.
8. `/mnt/c` ile Linux içi geçici klasör arasında süre farkı.
9. Çıkış kodları ve stdout özeti: makineyle okunur bir özet var mı (yoksa ölçüleri kendimiz çıkarırız — zaten plan bu).

**Bitti:** `docs/spikes/S10.md` + `S10-result.json` (yayın koşusu); her soru için ölçülen değer ya da "ölçülemedi + neden".

### S4 — Freerouting 2.5 (Windows yerel) — 1 gün, hemen yapılabilir

PLAN'daki tanım aynen: KiCad python + `pcbnew` ile DSN → `freerouting` CLI → SES → içe aktarma → DRC. S10 ile
**aynı beş kart, aynı ölçüler**, böylece doğrudan karşılaştırılır. Freerouting IPC kipi API kapalı olduğu için şimdilik
dışarıda; S3/S1 sonrası ayrıca.

## 6. Kıyas ve benimseme ölçütü (K5'i kapatır)

`scripts/bench_engines.py`: kart listesi × motor × bütçe → `.pcbai-state/bench/<tarih>/results.json` + Markdown tablo.
Kartlar: beş KiCad demosu + K14 kabul edilirse PCBench'ten 20 kart (4 gruptan beşer; 2,4 GB'ın tamamı indirilmez).

Bir motor **varsayılan** olur, eğer:
- demolarda yeni DRC hatası 0 ve rotalanmamış bağlantı 0 (ya da nedeni ölçülmüş: kart dışı bağlantı, yetersiz alan);
- PCBench alt kümesinde temiz kart oranı diğer adaydan düşük değil;
- yabancı değişiklik denetimi hiçbir kartta tetiklenmedi;
- aynı bütçede iki koşu aynı çıktı.

Yerleşim için TraceMaker-place, kicad-tools ve "mevcut yerleşim" karşılaştırılır; ölçüt: rota sonrası temiz kart oranı +
PLAN 5.7 sonundaki ölçülen denetimler (dekuplaj–pin mesafesi, konnektör–kenar, kristal–MCU). TraceMaker-place
bunları tutturursa **İP-5.6 (kendi tavlamamız) iptal edilir**; yerine "blok `layout.json` kısıtlarını TraceMaker'a
kilitli parça/yasak alan olarak verme" işi gelir.

## 7. İş paketleri ve sıra

| # | İş | Dal | Bağımlılık | Bitti tanımı |
|---|---|---|---|---|
| R0 | **Kullanıcı:** K12, K13, K14 kararları; K13 kabulse `wsl --install -d Ubuntu` | — | — | `wsl.exe -l -q` Ubuntu'yu listeliyor |
| R1 | S4 Freerouting denemesi | `ip/s4-freerouting` | yok | `docs/spikes/S4.md` + result JSON |
| R2 | S10 TraceMaker denemesi + `scripts/strip_tracks.py` | `ip/s10-tracemaker` | R0 | `docs/spikes/S10.md` + result JSON |
| R3 | `pcbai/pcb/engines/` (base, wsl, tracemaker, freerouting) + `external.find_*` + doctor | `ip/r-motorlar` | R1, R2 | birim testleri (bölüm 8); doctor iki motoru gösteriyor |
| R4 | `engine_guard.py` yabancı değişiklik denetimi | `ip/r-motorlar` | R3 | sentetik bozulmaların hepsi yakalanıyor |
| R5 | `autoroute` (önizleme işi + uygulama) + `route_engines` | `ip/r-motorlar` | R4 | demo kartta önizle → uygula → kontrol noktasından geri yükle uçtan uca |
| R6 | `autoplace` | `ip/r-yerlesim` | R5 | kilitli parça hiç oynamıyor; kart dışı parça uygulamayı engelliyor |
| R7 | `scripts/bench_engines.py` + `docs/baseline-motorlar.md` + K5 kararı (`docs/decisions/0003-engines.md`) | `ip/r-kiyas` | R5, R6 | tablo yayımlandı; K5 kapandı |
| R8 | VS Code eylemleri ve önce/sonra görünümü (sürüm artışı) | `ip/r-vscode` | R5 | Chromium testi: önizle → tablo → uygula |
| R9 | Belgeler: PLAN.md, status.md, plan-eksikler.md, README "isteğe bağlı motorlar" kurulumu | her dalın sonu | — | AGENTS.md kayıt kuralı |

Tahmini süre: R1 1 gün, R2 1,5 gün, R3–R5 4–5 gün, R6 2 gün, R7 1,5 gün, R8 2 gün → **~2,5 hafta**. Bu, PLAN
Faz 5b'deki 2 haftalık tavlama işini (İP-5.6) ve Faz 5c'deki İP-5.8'in büyük kısmını karşılar; Faz 5'i öne çekmez,
ama Faz 5'in süresini kısaltması beklenir. R1 ortam gerektirmediği için hemen başlayabilir.

## 8. Testler

- **Birim (motor gerektirmez):** yol dönüşümü (`C:\a b\x.kicad_pcb` → `/mnt/c/a b/x.kicad_pcb`, UNC ve ağ sürücüsü
  reddi); argv kurucu izin listesi (yasak seçenek → `invalid_arguments`); `PCBAI_TRACEMAKER` biçim doğrulaması;
  zaman aşımında süreç öldürme (sahte uzun süren program).
- **Bekçi:** gerçek demo kartın kopyası üzerinde sentetik "motor çıktıları": (a) yalnız via ekli → kabul; (b) bir
  footprint'in değeri değişmiş → ret; (c) zon çerçevesi değişmiş → ret; (d) kilitli footprint taşınmış → ret;
  (e) `(version)` değişmiş → ret; (f) yinelenen UUID → ret; (g) olmayan net → ret.
- **Sahte motor:** `tests/fixtures/fake_engine.py` (KiCad python ile çalışan, girdiye bilinen bir via ekleyen) →
  `autoroute` önizle/uygula/geri yükle akışı CI'da motor olmadan.
- **Entegrasyon (`tests/test_engines_integration.py`):** motor yapılandırılmamışsa açıkça skip; yapılandırılmışsa
  ecc83 izsiz kopyası → rotalanmamış 0, yeni DRC 0, bekçi temiz.
- Kullanıcının KiCad ayar klasörü SHA-256'sı takımdan önce/sonra aynı (mevcut regresyon testi kapsamına girer).

## 9. Riskler

| Risk | Önlem |
|---|---|
| TraceMaker genç ve hızlı değişiyor (dün 20 commit); CLI/çıktı kırılabilir | Commit sabitlenir; doctor sürümü yazar; bekçi + entegrasyon testi ilk kırılan yer |
| Yalnız Linux → Windows kullanıcısı için WSL ağır bir ön koşul | Motor isteğe bağlı; Freerouting yerel yol varsayılan kalabilir; README'de kurulum |
| GPL bulaşması | K12: ayrı süreç, paketleme yok, CI lisans denetimi |
| Motor kartta yabancı öğeye dokunur | Bekçi; uygulama engeli |
| Fazla via (README: Freerouting'den %43 fazla) | Kıyasta via sayısı ölçülür; varsayılan seçimi etkiler |
| `--time` ile tekrarlanamayan sonuç | Varsayılan `--work`; kanıtta `deterministic` alanı |
| PCBench kartlarının lisansı belirsiz | Depoya girmez; yalnız sonuç tablosu |
| KiCad 10.0.4 ile TraceMaker'ın yazdığı dosya sürümü uyumsuz | S10 madde 3; `(version)` bekçide sabit |

## 10. Kararlar ve ortam

Kullanıcı WSL + TraceMaker + Freerouting ile ilerlemeyi onayladı ve PCBench'i istemedi.
13 Ekim kullanıcı yeniden başlattı; WSL2/PcbAi-Ubuntu ve pinned CPU motor derlemesi tamamlandı.
[S10 ortam kaydı](spikes/S10.md). K12 sınırı ve Java/JAR yedeği [0003](decisions/0003-engines.md)'tedir.

## 11. 12 Ekim uygulama durumu

13 Ekim farkı: R3 envanter sorgusunda TraceMaker 0.9.0'ın gerçek `version` alt komutu ve
lowercase semver arayüzü düzeltildi. Uygulayan 57/57, bağımsız 55/55 ilgili test;
[S10](spikes/S10.md). Yeniden başlatma/CPU derlemesi tamamlandı; R2/S10 kalite kabulü açık.

| Paket | Yazılım / ölçüm durumu | Açık kabul |
|---|---|---|
| R0 | WSL2/PcbAi-Ubuntu 26.04.1 çalışıyor; pinned CPU 0.9.0 ELF derlendi; PCBench indirilmedi | Ortam kapısı ölçüldü; motor kalite kabulü ayrı |
| R1 | Gerçek native hata + JAR DSN/SES denemesi; [S4](spikes/S4.md) | Demo kalite kapıları geçmedi; yayın sonucu yok |
| R2 | `strip_tracks.py`, gerçek CPU derleme/sürüm, WSL argv/timeout, [S10](spikes/S10.md) | Temiz demo kalite ve yerleşim kabulleri |
| R3 | `engines/`, `external.find_*`, doctor (env/PATH, native/WSL, JAR) | TraceMaker sürüm/commit ve Linux süreç ölçümü |
| R4 | Korunan düğüm baytları, UUID/net/katman, kilit, geçerli kontur, yeni DRC kimlikleri | Gerçek TraceMaker çıktıları |
| R5 | `autoroute`, `route_engines`, preview işleri, immutable aday, checkpoint/restore, önce/sonra SVG | Beş demoda temiz motor kabulü |
| R6 | `autoplace`, kilit/izinli flip/scratch/dışhat kapısı; gerçek fake subprocess testli | TraceMaker-place gerçek kart kıyası, blok layout kısıt aktarımı |
| R7 | `bench_engines.py`, yerel JSON/MD, [baseline](baseline-motorlar.md), [0003](decisions/0003-engines.md) | K5 seçimi; TraceMaker + yerleşim kıyası |
| R8 | VS Code komutları ve önce/sonra aday paneli, Chromium UI testi; 0.1.16 yüklendi | Gerçek Extension Host'ta motor komutu ve kullanıcının elle kabulü |
| R9 | PLAN/status/eksikler/tools/README/karar/deneme kayıtları güncellendi | Her paketin ölçümüyle faz kabulleri ayrıca kapanır |

13 Ekim gerçek motor farkı: CPU 0.9.0 ve WSL process-group timeout ölçüldü;
route exit 3 kısmi kart protokolü düzeltildi. Gerçek tiny preview/apply/render/checkpoint/restore
geçti; beş demo × iki koşu [S10](spikes/S10.md)'da. Ecc83 14→0 fakat yeni clearance,
pic 86→14, stickhub 128→29; video/interf_u UUID kapısında reddedildi. Üç ölçülen çiftte
raw motor çıktısı eşit. Demo yerleşimi no-op; ayrı iki-pad fixture gerçek iki hareket,
frozen apply/checkpoint/restore geçti. K5/temiz beş demo ve yerleşim kalite kabulü açık.

Freerouting'in native 2.5.0 ikilisi ölçülen GraalVM hatası nedeniyle kullanılabilir kabul edilmedi; açık
Java 25/JAR yapılandırması desteklenir. `tested=true` ve varsayılan motor seçimi uydurulmaz.
Lisans CI denetimi yasak motor import/bağımlılık/binary paketlemesini kapsar; tüm transitif paketlerin
SPDX lisans taraması PLAN'da hâlâ ayrı iştir. Aday panelindeki `diagnostic_markers` geçici ölçüm
işaretleridir; kalıcı `markers.json` notlarına kendiliğinden yazılmaz.
