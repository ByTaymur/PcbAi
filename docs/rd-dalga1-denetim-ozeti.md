# RD dalga 1 — bağımsız hedefli denetim özeti

13 Ekim 2026. Uygulayan Codex; bağımsız salt okunur denetçi ayrı Codex ajanı.
Claude plan çağrısı 900 saniyede sonuç üretmeden zaman aşımına uğradı; Claude planı,
uygulaması veya denetimi yapılmış sayılmaz. AGENTS.md gereği kaynakta tek yazıcı vardı.
Ham günlükler ve iki ajan defteri yerel `.pcbai-state/rd-wave1/` altında tutulur.

| Kapsam | Bağımsız ölçüm | Sonuç |
|---|---|---|
| D1-1…D1-4 | 30 test, 35,249 sn | A2 hata manifestinde istenen parite ve hashler eksikti; uygulayan düzeltti |
| A2 düzeltmesi, D1-5 | 13 test, 9,813 sn | OK; açık engelleyici bulgu yok |
| D1-6 | 10 test, 39,804 sn; beş gerçek demo, skip yok | OK; dört ek adversarial model kontrolü geçti |
| D1-7 | 45 test, 41,845 sn, skip yok | OK; kayıp belge ve farklı proje referansı bulguları düzeltildi |
| Son connect değişikliği | 4 test, 17,322 sn, skip yok | Tam üyelik kıyası, SHA doğru fazladan üye ve kayıp belge regresyonları OK |
| Son niyet/sınır ekleri | 5 test, 8,999 sn, skip yok | Sembol değeri, bağımsız checkpoint SHA ve farklı proje R1 kapsamı OK |
| Son sayfa provenance eklemesi | Beş bağımsız metadata probe | Eksik metadata incomplete; yalnız açık tek kaynak sayfa sayısı 1 |

Bu sayılar ayrı koşuların ölçümleridir; benzersiz test toplamı diye toplanmaz. Denetçi kodu değiştirmedi;
bulguları uygulayan giderdi ve denetçi kendi tekrar üretimleriyle kapattı. Tam dalga uygulayan ölçümü
[status.md](status.md) içinde ayrıca raporlanır; hedefli denetim bağımsız tam takım veya ürün kabulü değildir.
Son güçlendirilmiş 10 kalibrasyon testinin denetçi sonucu kullanım sınırı kesintisinden sonra
alındı: 10 test OK, 106,442 sn, beş gerçek demo, skip yok; beş bağımsız provenance probe da geçti.
Uygulayan aynı son testleri tamamladı: 10 test OK, 115,085 sn, skip yok.

Yeniden üretim: `.venv` ile `python -m unittest tests.test_verify_readback tests.test_engine -v`;
kalibrasyon için `python -m unittest tests.test_verify_calibrate -v`. Gerçek dış model koşusunda
`PCBAI_KICAD_HAPPY`, S11'deki pinned `06840467ad0f5d76af45f64449b1f5ecb10f052f` klonuna işaret eder.
KiCad yazım testleri kapalı editörler ve yalnız geçici proje kopyalarıyla yapılır.

Kalibrasyonda beş demo bölümlemesi eşit olsa da pic_programmer/video ad seçimi farkları örtülmez;
pic_programmer'ın 19 pin tekrar farkı ve bağımlı dedektör kapıları açıkça kalır.
KiCad 10.0.4 CLI iz toplamı sunmadığından segment/arc kaynağı `saved_geometry` olarak belirtilir.
S11 yayın JSON'u yazılmadı; RD-B1, main birleştirmesi ve geçmiş imza temizliği bu kabulün kapsamı değildir.

## Kullanıcının ilettiği Claude incelemesi ve takip düzeltmeleri

Kullanıcının ilettiği 0.1.21 incelemesi yedi paketin tarif uyumunu, gerçek kalibrasyon 10/10,
CLI 0/1/2 ve 13 yazıcının niyet geri okumasını doğruladı. Engelleyici olmayan CLI kod sayfası,
audit ek taraması ve PCM başlığı bulguları 0.1.22'de düzeltildi. Eski servisin yeniden başlatılması
çalışan oturuma ait bir kullanıcı adımıdır; testler kullanıcı kartını veya servisini değiştirmedi.

Takip düzeltmesinde bağımsız CLI testleri Unicode/cp1252 strict ve 0/1/2 çıkışlarını doğruladı.
İlk audit testindeki yanlış sabit hash sayısı beklentisi, araç iç işiyle audit sarmalayıcısını
kıyaslayacak şekilde giderildi; mevcut güvenlik kontrolleri korundu. Son bağımsız audit
6 test/0,365 sn OK, skip yok; nested hedef ve gizlilik probe'ları temiz. Uygulayan son
76 hedefli test/100,030 sn OK, skip yok. Bu 0.1.22 hedefli doğrulamadır; bağımsız tam takım iddiası değildir.
