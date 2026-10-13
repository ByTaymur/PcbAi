# Motor kıyası durumu

12 Ekim 2026 · K5 açık. [Karar](decisions/0003-engines.md), [S4](spikes/S4.md), [S10](spikes/S10.md).

- Native Freerouting 2.5.0: ecc83'ta GraalVM serileştirme hatası; zaman aşımında kendi süreç ağacı kapatıldı.
- JAR Freerouting 2.5.0: gerçek DSN/SES hattı çalışıyor; kalite KiCad'in DRC'siyle ayrı ölçülüyor.
- TraceMaker route/place: WSL yeniden başlatması + Ubuntu + derleme bekliyor; kıyas sonucu yok.
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

Ham sonuç [geliştirme kaydı](../.pcbai-state/s4-current.json) içindedir. `ok=true`, aday üretildiğini
belirtir; `blockers=[]` ve gerçek ERC/DRC/parite/DFM üretim kabulüyle aynı şey değildir. Varsayılan motor
seçilmedi; TraceMaker'ın ölçülmemiş yerleşimi sebebiyle kendi tavlama iş paketi iptal edilmedi.
