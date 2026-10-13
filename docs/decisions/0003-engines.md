# 0003 — Dış motorlar ve ölçümle seçim

12 Ekim 2026 · K12 kabul edilmiş uygulama sınırı; K13 kurulum onaylı, yeniden başlatma bekliyor;
K14 yalnız KiCad demoları; K5 **açık**.

- TraceMaker ve Freerouting yalnız ayrı süreçte çalıştırılır. Kaynak kodu, Python bağlaması ve ikilileri
  PcbAi'nin Python/PCM/VSIX paketlerine girmez. `scripts/check_licenses.py` bunu CI'da denetler.
- Kullanıcı WSL2 + Ubuntu kurulumuna izin verdi. Yükseltilmiş kurulum Windows Subsystem for Linux ve
  VirtualMachinePlatform bileşenlerini etkinleştirdi; çıktı yeniden başlatma istiyor. Ubuntu dağıtımı ve
  TraceMaker'ın cpu-only derlemesi henüz ölçülmedi. Bilgisayar otomatik yeniden başlatılmadı.
- Kullanıcı PCBench indirmesini istemedi. Kıyas beş kurulu KiCad demosuyla sınırlıdır; PCBench başarısı
  veya genel kart sınıflarına üstünlük iddiası yapılmaz.
- Freerouting **2.5.0 Windows native CLI** SHA-256 doğrulanarak `.tools/` altına alındı. Gerçek ecc83
  koşusunda GraalVM `ComponentOutline` serileştirme hatası ve ardından zaman aşımı görüldü.
  Bu ikiliye çalışan motor kabulü verilmedi.
- Aynı sürümün resmi **JAR** dosyası ve ayrı Temurin JRE, SHA-256 doğrulamasıyla `.tools/` altında.
  `PCBAI_FREEROUTING=<jar>` + `PCBAI_JAVA=<java>` açık yapılandırmasıyla çalışır. Native dosyadan
  JAR'a kendiliğinden geçilmez. Java/JAR yedeği de PcbAi dağıtımına girmez.
- Her iki motorun sonucu önce yabancı öğe denetiminden, sonra KiCad DRC/bağlantı/yerleşim kapılarından
  geçer. Yeni hata ekleyen aday uygulanamaz; rotalanmamış bağlantı sayısını azaltmak tek başına kabul değildir.

K5, TraceMaker S10 ölçümü ve aynı bütçeli demo kıyası olmadan kapatılamaz. Kendi tavlama motorunun
iptali de henüz kararlaştırılmadı.

13 Ekim ilerleme: kullanıcı yeniden başlattı; WSL2/PcbAi-Ubuntu 26.04.1 kuruldu,
CPU-only 0.9.0 pinned kaynak derlendi. K13 ortam kapısı ölçüldü. Gerçek süreç timeout,
küçük fixture apply/restore ve beş demo × iki rota koşusu [S10](../spikes/S10.md)'da.
Yeni DRC/eksik bağlantı/UUID retleri nedeniyle K5 ve anlamlı placement kalite kabulü açık;
varsayılan motor veya kendi tavlamamızı iptal kararı verilmedi. K12 paket ayrımı korunur.

Yerel kayıtlar: [native hata](../../.pcbai-state/s4-debug.json),
[WSL kurulumu](../../.pcbai-state/wsl-elevated.txt), [motor kıyası](../../.pcbai-state/s4-current.json).
Resmi CLI bayrakları: [Freerouting 2.5.0 CLI belgesi](https://github.com/freerouting/freerouting/blob/v2.5.0/docs/command_line_arguments.md).
