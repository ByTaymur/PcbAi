# İkiz defteri

## IK-20261012-02 — Yerel parça ve şematik yazıcı

Mod: **bir uygulayan + bağımsız salt okunur denetçi**, dal `ip/parts-sch`.
AGENTS.md kullanıcı rol kuralı uygulanır; iki bağımsız plan veya ikinci uygulama yoktur.
İlk Codex denetçisi kendi **9/9** testini çalıştırdı ve somut yeniden üretimler bildirdi;
[denetim kaydı](.pcbai-state/audit-all-plan/parts-sch-review.md). Foreign-project fiziksel sayfa,
common-only PWR_FLAG, kalıtılan index metadata, numbered NPTH ve cold-index süre sınırı
bulguları gerçek kaynak/kurulu kütüphane üzerinde doğrulandı; A tarafından düzeltildi.

Codex denetçisi kullanım sınırına takılınca `ikiz` becerisinin salt okunur kod denetimi yolu
Claude **claude-opus-5**, Read/Grep/Glob ile denendi. Kullanıcı AGENTS.md kuralı nedeniyle
ikinci yazan yoktur; kaynak değiştirme/komut çalıştırma ve MCP erişimi açılmadı.
[Görev](.pcbai-state/parts-review-task.md), [sonuç sınırı](.pcbai-state/parts-review-claude-timeout.txt).
İlk CLI denemesinde boş MCP config biçimi reddedildi, `mcpServers:{}` ile düzeltildi;
asıl denetim **240 sn timeout**, geçerli sonuç yok. Bu bağımsız son fark kabulü değildir.

A çözümü korunur. İlk gerçek yerel/CLI odaklı takım **17/17**, 150,682 sn; sonraki
replacement/global-label/marker ve dağıtım düzeltmeleri ayrıca ölçüldü: tam takım
**209/195 geçti/14 skip**, 326,077 sn; yeni native aday denetimi **1/1**, 4,403 sn.
İlk tam koşudaki çekirdek→geliştirme-eklenti bağımlılığı düzeltildi, iki taze checkout
ve index regresyonları **8/8** geçti. Koşu sırasında açılan kullanıcı KiCad'i yazmayı
reddetti; son koşunun editör skip'leri gerçek yazma kabulü diye sayılmaz.
Soğuk indeks **36,18 sn**, sıcak **0,29 sn**. Faz/katalog/stock/çok dosyalı IR/canlı/üretim
kabulleri ve son bağımsız tekrar açıktır; ayrıntı [status.md](docs/status.md)'de.

**Sonraki aynı paket doğrulaması:** denetçi kotası yeniden kullanılınca üç ek P1 buldu:
sheet/ancestor foreign kayıtları, sibling projelerin ortak boş sayfası ve UUID yazım varyantıyla
gizlenen referans. A düzeltti, B kendi üç yeniden üretiminin artık reddedildiğini ölçtü.
Kapalı-GUI son delta A **61/61** (214,926 sn), B **64/64** (244,967 sn), skip yok;
Ruff/lisans temiz. Bağımsız cold/warm **39,484/0,391 sn**, 22.776 kayıt.
[Son rapor](.pcbai-state/audit-all-plan/parts-sch-final.md). Bu ek kayıt önceki başarısız
Claude koşusunu veya eksik kabulleri silmez; son kod denetimi artık tamamlandı.

## IK-20261012-01 — Rota/yerleşim ve SPICE güvenlik paketi

Mod: **bir uygulayan + bağımsız salt okunur Codex denetçisi** (`auditor`), dal `ip/plan-tamamlama`.
AGENTS.md rol kuralı uygulandı; ikinci yazan uygulama/Claude ikiz koşusu iddia edilmez.
Bağımsız gap incelemesi, kendi test koşuları ve yeniden üretimler
[denetim klasöründe](.pcbai-state/audit-all-plan/), kapsam/kararlar [status.md](docs/status.md)'dedir.

Denetçi nested SPICE include/code-model kaçışı, konkav/iç delik/bbox/courtyard sıra sorunları,
benchmark Markdown hardlink kaçağı ve eski VSIX kaynak farkını buldu. Uygulayan düzeltti;
denetçi bulguları kendi yeniden üretti ve düzeltmeleri tekrar kontrol etti.
Son `.venv` tam takım **191/190 geçti/1 symlink skip**, ayrı CLI **11/11**, son UUID delta **20/20**;
Ruff ve yasak motor paketleme/import denetimi temiz. İlk sistem Python/eskimiş bridge arızalı
koşusu ayrıca korunmuştur. Gerçek motor demo kalite kabulü, WSL/S10 ve kalan ürün fazları açık.

## IK-20261011-03 — E-1/E-2/E-4 ve K-1/K-2

Mod: **paylaşımlı, B salt okunur Codex denetçisi** (`baseline_audit`). Uygulayan ana Codex ajanı;
yalnız uygulayan yazdı. E-1 `ip/e1-baseline`, paket `ip/k-pcm` dalında.
Kullanıcının docs/plan-eksikler.md bölüm 8 rol kuralı uygulandı; ikinci yazan uygulama yok.
Ölçümler ve kapsam sınırları [durum kaydında](docs/status.md).

### 1. Plan karşılaştırması

A planı [yerel plan-A](.ikiz/eksikler-ilk-paket/plan-A.md). Claude Opus 5 salt okunur bağımsız plan
180 sn'de zaman aşımına uğradı; geçerli B planı yok, **karşılaştırma yapılamadı**.
Üç dosyaya daraltılan Claude denetimi de 120 sn'de sonuç vermedi. Yerine geçen Codex ajanı
bağımsız test/kanıt denetçisidir; bağımsız ikinci plan ürettiği iddia edilmiyor.

### 2. Uygulama karşılaştırması

A uygulaması seçildi. B kod değiştirmedi; iki yazan uygulama veya bunların örtüşmesi iddiası yok.
E-1 commit grupları izole staging kopyalarıyla doğrulandı. LGPL kullanıcının açık yanıtıyla seçildi;
gerçek kurulu PCM/API şemaları, ZIP içindeki lisans ve IPC alanı doğrulandı.

### 3. Çapraz kontrol bulguları

| Bulgu | Kanıt / yeniden üretim | Karar |
|---|---|---|
| G5 karesel scene maliyeti | `pcbai/views.py` öğe döngüsünde `root.all("net")`; 8.000 izde 22,213 sn | Mevcut kod eksikliği; [G5 ölçümüne](docs/spikes/G5.md) alındı, optimizasyon açık |
| S7 rapor değişkeni gölgelemesi | `scripts/spike_svg.py` Path raporu döngüde render dict'iyle değişiyordu; son `write_text` hata veriyordu | `evidence_report` ayrıldı; gerçek S7 koşusu exit 0, B kodu/çıktıyı kontrol etti |
| Installer/config/Python kanıt hardlink kaçışı | Denetçinin izole sentinel'ine bağlı `register.py` ve `.pcbai-state/S7-result.json` yazımı sentinel'i değiştirdi | Çok bağlantılı düzenli dosya reddi; [regresyonlar](tests/test_kicad_plugin.py) ve [kanıt sentinel'i](tests/test_evidence_output.py), B tekrar çalıştırdı |
| Browser kanıt junction kaçışı | `.pcbai-state` yayımlanmış fixture klasörüne junction olabiliyordu; doğrudan JSON/PNG yazımı vardı | [JS hedef denetimi](vscode/pcbai-vscode/test/evidence_output.js), [gerçek junction/hardlink sentinel'i](vscode/pcbai-vscode/test/test_evidence_output.js); B tekrar çalıştırdı |

B ilk denetimde 69 çekirdek testi, düzeltmeler sonrası 14 testi ve güçlendirilmiş iki gerçek kaynak
kopyası/servis testini ayrıca çalıştırdı. Ruff temiz. K-1/K-2 kapsamında son somut engel bildirmedi.
B S7 CLI deneyini kendi çalıştırmadı; A'nın yeniden ürettiği çıktıyı kontrol etti.

### 4. Karar ve açık kalanlar

Paket kodu ve kanıt koruması alındı. E-3/K-3/K-4, G2 ve sonraki işler açık.
Gerçek VS Code ek koşusu başarısız oldu; geçici profil temizliğinde WinError 32/267 oluştu,
kabul sonucu sayılmadı. İki Claude timeout'u bulgusuz denetim değildir.

### 5. Yerel kayıtlar ve maliyet

[Staging sonuçları](.pcbai-state/eksikler-ilk-paket/) ·
[B paket denetimi](.pcbai-state/eksikler-ilk-paket/package-audit.txt) ·
[Claude plan](.ikiz/eksikler-ilk-paket/plan-B.json) ·
[dar Claude denetimi](.ikiz/eksikler-ilk-paket/pcm-denetim-B.json).
Claude: 2 başarısız çağrı, zaman aşımı sınırları 180/120 sn; geçerli maliyet çıktısı yok.
Codex ekip denetçisi: salt okunur görevler; ayrı worktree gerektiren ikinci yazıcı başlatılmadı.

## 2026-10-11 — hierarchy-fix-002

Mod: bağımsız plan + salt okunur denetim. B: Claude Opus 5, `claude -p`, derinlik kilidi 1.
Plan başarılı (`is_error=false`, 100075 ms); ham çıktı yerel `.ikiz/hierarchy-fix/plan-B.json`.

### 1. Plan karşılaştırması

| Bölüm | Doğrulama ve karar |
|---|---|
| Ortak | Örnek kayıtları, proje filtresi, bir kez fiziksel alan düzenleme, çok birim, tüm ortak referansların bildirimi; özel durumdaki kanonik kök kilidi; karakter ve regresyon kontrolleri. |
| Yalnız A | Bağlı çok birimli sembollerin tüm ortak referanslarını genişletme; aday/apply/etkisiz apply/denetim arızasında etki metaverisini koruma; gerçek XML netlist ve bayt eşit geri yükleme. Uygulandı. |
| Yalnız B | Özel property adlarıyla metaveri çakışması: 0.1.0 `dict(props, uuid=...)` üzerine yazmıyor, çift anahtar yüzünden TypeError veriyordu. Türetilmiş üst alanları koruma ve ayrı `properties` sözlüğü uygulandı/test edildi. |
| Çelişki | B görünen property referansını da eşleştirmeyi önerdi. Modern kayıt varken eski property yanlış hedef seçebileceğinden reddedildi. |
| Çelişki | B ortak Value için ek acknowledgement kapısı önerdi. Mevcut preview → candidate → apply zaten somut etki onayıdır; ek kapı eklenmedi. |
| Çelişki | B Cf/bidi/boşluk ve 256+ sınırını alt modele de koymayı önerdi. C0/C1 ve surrogate reddi alındı; araç şeması zaten 256 sınırını uygular. Daha geniş metin yasağı bu düzeltmenin kapsamı değil. |
| Çelişki | B eski kök kilidini silmeyi ve kilit istisnasını kaldırmayı önerdi. Kullanıcı projesindeki eski dosya otomatik silinmedi; yükseltme önce eski servis kapatılarak yapılır. Aynı state namespace gereği belgelendi. |
| Çelişki | B item_count'u fiziksel düğüm olarak tutmayı önerdi. Listeyle tutarlı örnek sayısı seçildi; 0.1.1 araç sözleşmesinde açıkça belgelendi. |
| Sonradan doğrulanan | 115 gerçek şematik taramasında boş proje adları bulundu. Boş ad geçerli kabul edildi; seçim kök UUID ile sınırlanır. Farklı kökler çok birim grafiğinde birleşmez. |

### 2. Uygulama ve denetim kapsamı

A tek yazardır; B ikinci bir uygulama üretmedi. Bu kayıt tam iki uygulamalı ikiz kabulü değildir.
Birleşik plan yerel `.ikiz/hierarchy-fix/plan-ORTAK.md`; karar [0002](docs/decisions/0002-shared-sheets.md).
Model/engine/kilit denetimi 180 saniyede zaman aşımına uğradı; başarısızdır ve onay sayılmaz.
Daraltılmış model denetimi başarılı (`is_error=false`, 203162 ms);
yerel `.ikiz/hierarchy-fix/review-model-B.json`. Üç bulgu ana ajan tarafından yeniden üretildi:

| Bulgu | Doğrulama ve düzeltme |
|---|---|
| root_uuid tek başına scope oluşturmuyordu | `_in_project` project=None durumunda erken True dönüyordu. Kök filtresi modern kayıtlara proje adından bağımsız uygulanıyor; farklı eski değerli iki kök regresyonu eklendi. Servis zaten proje adı veriyordu; bulgu alt model API'sini etkiliyordu. |
| Yinelenmiş Value alanında ilk/son tutarsızlığı | Okuyucu son property'yi, editör ilkini seçiyordu. Yinelenmiş Value/Reference okuma ve düzenlemede invalid_document ile reddedilir; giriş baytları değişmez. |
| Tek projede diğer projeler uyarısı | Ortak sayfa uyarısındaki koşulsuz other projects ifadesi kaldırıldı. Tüm örneklerin etkilenmesi bildirilir; mevcut projeler etki kayıtlarında açıkça bulunur. |

Bu üç düzeltmenin B tarafından tekrar denetimi yapılmadı. Model dışı geniş denetim zaman aşımı
nedeniyle bağımsız kilit/engine onayı yoktur; ana ajan regresyon ve gerçek CLI kontrollerini yürütür.

### 3. Yerel doğrulama

Sentetik ve gerçek testlerin sayıları, gerçek R203/R303 netlist ölçümü ve kalan kapsam
[durum kaydında](docs/status.md). Lisans ve uzak CI doğrulanmış gösterilmedi.

## 2026-10-10 — core-001

Mod: bağımsız plan + salt okunur uygulama denetimi. B: Claude Opus 5, `claude -p`, derinlik kilidi 1.
Plan çağrısı başarılı (`is_error=false`, 211923 ms); ham çıktı yerel `.ikiz/core/plan-B.json`.

### 1. Plan karşılaştırması

| Bölüm | Karar |
|---|---|
| Ortak | Stdlib servis/MCP, açık hedef, dosya modu, bayt koruma, atomik yazım, checkpoint, ERC/DRC, kanıt, gerçek CLI testleri |
| Yalnız A | Önizleme adayına revizyon bağlama; geçerli aday olmadan yazma yok. Birleşik plana alındı. |
| Yalnız B | Şematik netlisti KiCad'den, global kütüphane bağlamı, çok birimli değerler, ihlal çıkış kodları. Birleşik plana alındı. |
| Yalnız B | Argüman onarımı, küçük model araç kümesi, add_label, jobs, render/fab. Mevcut yazma yolunu ölçmeden kapsam artırmamak için sonraki paket. |
| Çelişki | B demo normalizasyonu önerdi. Korunan bayt iddiası mevcut dosyaları kapsamalı; mevcut külliyatı değiştirmeden ölçüyoruz. |

### 2. Uygulama karşılaştırması

A uygulaması ana depodadır. B için ikinci yazan uygulama başlatılmadı; bu kayıt tam iki uygulamalı ikiz
kabulü değildir. B yalnız okur. ikiz becerisi (`~/.codex/skills/ikiz/SKILL.md`) ilk yazma
delegasyonunda ayrıca kullanıcıya sormayı ister; mevcut uygulamayı durdurmadan salt okunur denetim uygulanıyor.
Yeni AGENTS.md ikinci yazan ajan talep etmiyor.

### 3. Çapraz bulgular

Denetim ve doğrulanmış sonuçlar bu kayıt sonuna eklenecek. Henüz bağımsız uygulama onayı yok.

### 3a. Salt okunur denetim sonucu ve düzeltmeler

Geniş denetim 300 saniyede zaman aşımına uğradı; başarısız kayıt olarak tutuldu. Dosya yazımı/ACL odaklı
ikinci denetim başarılı: 186948 ms, `is_error=false`; yerel `.ikiz/core/review-write-B.json`.

| Bulgu | Doğrulama ve karar |
|---|---|
| Mevcut state alt dosyalarında geniş explicit ACL kalabilir | Doğrulandı. Sahip/yönetim işareti kontrolü, reparse reddi ve tüm mevcut alt nesnelerde tek kullanıcı DACL/0600 uygulandı. Geniş Everyone ACE'li dosya regresyon testi eklendi. |
| Checkpoint karması hiç kontrol edilmiyor | B'nin bu alt iddiası yanlıştı: history.py zaten `digest(data) != sha` kontrolü yapıyordu; bozuk blob testinde reddediliyor. Karşı iddia kayıtta bastırılmadı. |
| KiCad proje yöneticisinin barındırdığı editörler kaçabilir | Doğrulandı. `kicad.exe`/`kicad` de yazma engeline eklendi; sahte süreç listesiyle regresyon testi geçti. |
| Atomik replace eski dosyanın ACL/mode/owner bilgisini kaybettirir | Doğrulandı. Mevcut descriptor/mode/owner yeni dosyaya aktarılır; başarısızsa orijinal korunur. Protected ve inherited Windows ACL testi eklendi. |
| Çöken süreç kalıcı O_EXCL kilidi bırakır | Doğrulandı. OS advisory kilidi kullanıldı; kilit dosyası silinmeden tutulur, process exit kilidi bırakır. Gerçek öldürülmüş alt süreç testi geçti. |
| Dizin fsync yok | Kalıcı güç kesintisi garantisi bu sürümde verilmez; veri fsync + atomik replace var. POSIX directory durability ileri sertleştirme işi olarak açık kaldı. |

Tam iki bağımsız uygulama yine yapılmadı. B düzeltmeleri tekrar denetlemedi; düzeltilen davranışlar
ana ajan tarafından gerçek Windows izin/süreç testleri ve KiCad CLI ile doğrulandı.

### 3b. Son doğrulama

49 çekirdek/servis/protokol testi; 5 ayrı gerçek KiCad entegrasyon testi. Bir Windows symlink testi
oluşturma yetkisi nedeniyle skip; Windows junction kaçışı gerçekten test edildi. Son güvenlik düzeltmeleri
sonrası etkilenen gerçek Value/restore ve ERC/DRC testleri tekrar geçti. Ruff temiz.
Geniş denetimin başarısızlığı ve S2'nin bir strict parser tolerans farkı [durum kaydında](docs/status.md) açık.

### 4. Karar

A çekirdeği test kanıtlarıyla değerlendirilir. Tam v0.8, canlı tampon koruması veya fiziksel kart kabulü
iddia edilmez. Durum: [docs/status.md](docs/status.md).

## 12 Ekim 2026 — `ip/ir-bloklar`, çekirdek 0.1.9

AGENTS.md uyarınca tek uygulayan ve bağımsız salt okunur denetçi kullanıldı; ikinci bağımsız
uygulama yapılmış gibi sunulmaz. Denetçinin başlangıç kapsamı
`.pcbai-state/audit-all-plan/ir-bloklar-scope.md`; son inceleme
`.pcbai-state/audit-all-plan/ir-bloklar-review.md`.

Uygulayan: kapalı JSON Schema/SI normalizasyonu, üç olgunluk-0 pasif tarif, sekiz el hesabı,
salt okunur yerel referans/net ön denetimi; gerçek RC transient/AC, servis/MCP ve wheel ölçümleri.
Bağımsız denetçi kendi 42/42 testini, ilave highpass/loaded-divider simülasyonlarını ve
izole dependency/wheel kurulumunu çalıştırdı; kalan maddi bulgu yok. İlk audit helper path
hatası başarısız kayıtta korunuyor; düzeltilmiş izole probe geçiyor. `jsonschema>=4` ilk manifesti
uygulayan tarafından doğrulanan API sürümüne `>=4.26,<5` daraltıldı; denetçi yeniden paketledi.

Elektriksel aşama eksik, olgunluk 0, stok/veri sayfası/AF/fiziksel kabul yok. Birleşik devre
hesabı, 11 olgunluk-1 blok ve çoklu sayfa/UUID compiler tamamlanmadı. Sonraki `add_block`
yazım farkı ayrı candidate/checkpoint/native-topoloji denetimi gerektirir; kapsam notu hazırlanmıştır.

Son uygulayan tam takım: 228 test/227 geçti/1 Windows symlink yetkisi skip, 800,626 sn.
Ayrı gerçek CLI 11/11, 295,993 sn; son odaklı 15/15, 0,520 sn. Ruff/lisans temiz.
Bu tam koşular bağımsız denetçinin kendi 42/42 koşusuyla karıştırılmaz.

## 12 Ekim 2026 — `ip/pasif-blok-yazimi`, çekirdek 0.1.10

Uygulayan tek writer; bağımsız denetçi kaynak değiştirmedi. Başlangıç kapsamı
`.pcbai-state/audit-all-plan/add-block-scope.md`, son rapor `add-block-review.md`.
Üç tarif/altı native varyant tek candidate/checkpoint, exact net üyeleri ve byte-equal restore.
Başlangıç test fixture grid/ref-context/ERC-warning beklentileri düzeltildi; önceki başarısız
çıktılar saklandı. Bağımsız yerleşim P2 görünür fields/free-text/sheet-property ek guard ve
unsupported-root failclosed sınırıyla kapandı. Denetçinin son 41/41; uygulayan ilgili79/79;
Ruff/lisans temiz. Native marker change-evidence ve same-count/new-ERC-identity gate ayrıca ölçüldü.

Önceki full228 bu farkın full237 kabulü gibi sunulmaz; yalnız etkilenen geniş delta çalıştırıldı.
Olgunluk0, dış arayüz singleton uyarıları, çoklu IR compiler/stock/AF/physical açıklığı korunur.
Denetçinin ayrı mevcut nested-state lock P2'si configuration paketine taşınacak; kaynakta
güvenlik gate bypass yapılmadı.

## 13 Ekim 2026 — state/proje sınırı, 0.1.11

Bağımsız kapsam ve final rapor `.pcbai-state/audit-all-plan/state-yapilandirma-*.md`.
Erken iki-yönlü canonical/lexical overlap kontrolü startup ACL/mkdir/marker/singleton ve
Engine history/cache öncesi; alias/iterator/~ handoff köşeleri denetlendi. KiCad kilit kapısı korunur.
Denetçinin final55/54pass/1symlinkskip11,124s; config6/6, gerçekjunction ve retainedownlockprobları
geçti, maddi bulgu yok. İlk B023 loop-capture uygulayan tarafından düzeltildi ve yeniden denetlendi.
Son uygulayan full243/242pass/1skip833,536s ve ayrıCLI11/11 262,264s; Ruff/lisans/wheel temiz.
Kesilen önceki full log korunur; başarısız/yarım koşu tamamlandı gibi sayılmaz. WSL yenidenbaşlatma
gereksinimi ve ürünün açık fiziksel/IR/stock/AF kabulü ayrı sınırdır.

## 13 Ekim 2026 — TraceMaker inventory arayüzü, 0.1.12

Kaynak c6fcb7b4912bdabefeb7f4191c011b1a086335e0: version subcommand/lowercase prefix;
PcbAi --version yanlışını düzeltir, GPL kaynak kopyalamaz. Strict protokol/nonzero-query ve
native/WSL argv farkları uygulayan57/57 145,153s; bağımsız55/55 16,081s ve gerçekfakechild
ayrıca geçti. Ruff/lisans temiz, kalan maddi bulgu yok; rapor `.pcbai-state/audit-all-plan/tracemaker-version-review.md`.
Önceki243full yeni3testi kapsamıyor; gerçekLinux/WSL/boardquality/timeout ölçümü yapılmadı.

## 13 Ekim 2026 — pasif tarif SPICE, 0.1.13

Üç tarif/altı varyant gerçek ngspice; uygulayan final52/52 5,226s, bağımsız48/48 4,651s.
Bağımsız gerçek kısa-devre mutation ve yanlış-ölçüm API mismatch/evidence kontratı ölçüldü.
P2 ACscale boolimag uygulayan tarafından düzeltildi, finalprobe/test kapandı.
Ruff/lisans/wheel/core-only temiz; rapor `.pcbai-state/audit-all-plan/passive-spice-review.md`.
Mutlak taban toleransları açık; tiny/zero uyarım topology acceptance değildir. Olgunluk0,
tarif ERC/CI/stock/hardware ve WSL/Linux motor kabulleri açık kalır.

## 13 Ekim 2026 — gerçek WSL/TraceMaker, 0.1.14

PinnedCPU99/99build,0.9.0ELF;actualLinuxTERM/KILLparent+child temizliği ölçüldü.
Uygulayan ilgili59/59 17,572s, gerçekconfiguredmotor2/2 329,263s; önceki252full bu sonfarkı kapsamıyor.
Actualexit3partial/1fatal protokolü düzeltildi; cp1254stdout ve Processoverride/Userfallback doğrulandı.
Bağımsızprotocol/route24/24 5,130s; tinyroute raw/UUID/geometry repeat +apply/restore geçti.
Beşdemo2repeat allsourcepreserved; üçölçülençift rawsha aynı. Ecc83 yenierror, pic/stickhub incomplete,
video/interfUUIDret; placeno-op. Bunlar K5/fiziksel/yerleşim kabulü değildir; varsayılan seçilmedi.

Son üst-düzey sıfır açı omission P2 düzeltmesi sonrası ilgili60/60 12,933s; sadece izinli at node
eşdeğerliği, diğerprotectedbytes ve lock/route kapıları korunur. Scratchpile0→2URapplyreddi ölçüldü.
FinalwheelSHA45004376b7ec904237e4e148d358f1d4547878dfbbbe49ac3abdd5decae3a171.
Bağımsız final25/25 3,315s; yeniayrık2padfixture moved2/UR2→2/blockers[]/gerçekapply+restore
ölçüldü. Demo sourcekilitleri açılmadı; genelyerleşim kalite kabulü açık.
