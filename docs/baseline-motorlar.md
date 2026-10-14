# Motor kıyası durumu

12 Ekim 2026 · K5 açık. [Karar](decisions/0003-engines.md), [S4](spikes/S4.md), [S10](spikes/S10.md).

- Native Freerouting 2.5.0: ecc83'ta GraalVM serileştirme hatası; zaman aşımında kendi süreç ağacı kapatıldı.
- JAR Freerouting 2.5.0: gerçek DSN/SES hattı çalışıyor; kalite KiCad'in DRC'siyle ayrı ölçülüyor.
- TraceMaker CPU 0.9.0: 13 Ekim WSL2/Ubuntu kuruldu, gerçek derleme ve aşağıdaki rota kıyası ölçüldü.
- Kıyas verisi kullanıcı seçimiyle yalnız beş KiCad demosu. PCBench indirilmedi.

Beş demo, iz/arc/via kaldırılmış özel kopyalar; zonlar korunmuştur. Her motor denemesinde `passes=5`,
`threads=1`, optimizer en çok 5 geçiş, timeout=60+30 sn. DRC önce/sonra doldurulmuş kopyalarda;
bu küçük kıyas Freerouting 2.5.0 JAR + Temurin Java 25 ve KiCad 10.0.4 ile yapılmıştır.

| Demo | İki koşu: açık bağlantı | İki koşu: DRC hata | Via | Motor süresi (sn) | Uygulama |
|---|---|---|---|---|---|
| ecc83-pp | 14 → 0, 14 → 0 | 42 → 48, 42 → 48 | 0 / 0 | 4,365 / 3,993 | Yeni clearance/termal hata; ret |
| pic_programmer | 86 → 2, 86 → 2 | 86 → 4, 86 → 4 | 0 / 0 | 8,515 / 9,826 | Yeni clearance/shorting ve açık bağlantılar; ret |
| video | Ölçülmedi | Ölçülmedi | — | — | Özgün kaynakta yinelenen UUID; motor çağrısından önce ret |
| interf_u | Ölçülmedi | Ölçülmedi | — | — | Özgün kaynakta yinelenen UUID; motor çağrısından önce ret |
| stickhub | Ölçülmedi | Ölçülmedi | — | — | SES köprüsü korunan kök öğeyi değiştirdi; ret |

On koşunun tamamında kurulu kaynak kartın SHA-256'sı korundu. UUID'ler ve kalite kapıları gevşetilmedi;
aday üretilmeyen kartlar temiz karta çevrilmiş sayılmadı. Süre yalnız motor alt sürecidir; DSN/SES/DRC/SVG
dahil kullanıcıya görünen toplam süre değildir. İki koşuda pic_programmer yeni hata türlerinin değişmesi
ve çıktı hashleri Freerouting için determinizm kabulü verilmemesini destekler.

13 Ekim TraceMaker CPU 0.9.0, pinned `c6fcb7b4912bdabefeb7f4191c011b1a086335e0`:
`work=3000000`, `threads=1`, `variants=1`, timeout 120+30 sn; iki koşu, aynı izleri
silinmiş demo türleri. JSON (yerel kayıt `.pcbai-state/tracemaker-exit-bench.json`),
tablo (yerel kayıt `.pcbai-state/tracemaker-exit-bench.md`).

| Demo | Açık bağlantı | DRC hata | Via | Motor sn (iki koşu) | Kalite |
|---|---|---|---|---|---|
| ecc83 | 14→0 | 42→30 | 0 | 2,094 / 12,359 | İki yeni zone clearance; apply bloke |
| pic_programmer | 86→14 | 86→14 | 1 | 8,000 / 6,188 | Yeni hata yok; 14 bağlantı açık |
| video/interf_u | Ölçülmedi | Ölçülmedi | — | — | UUID kapısında ret |
| stickhub | 128→29 | 128→29 | 19 | 6,860 / 5,360 | Yeni hata yok; 29 bağlantı açık |

Üç ölçülen kartın iki raw çıktı SHA-256'sı eşit; beş kartın kaynakları korundu. Genel
K5/üretim kabulü açık. Freerouting pass bütçesi ile TraceMaker expansion bütçesi aynı
iş miktarı değildir; bu farklı timeout'lu yerel koşularla kesin hız üstünlüğü veya
varsayılan motor kararı verilmez. Demo place koşuları no-op; ayrı iki-pad fixture'da
gerçek iki hareket/apply/restore ölçüldü. Yerleşim demo kalite kabulü yok.

Ham sonuç geliştirme kaydı (yerel kayıt `.pcbai-state/s4-current.json`) içindedir. `ok=true`, aday üretildiğini
belirtir; `blockers=[]` ve gerçek ERC/DRC/parite/DFM üretim kabulüyle aynı şey değildir. Varsayılan motor
seçilmedi; TraceMaker'ın ölçülmemiş yerleşimi sebebiyle kendi tavlama iş paketi iptal edilmedi.
