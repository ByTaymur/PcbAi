# RD dalga 0 — bağımsız denetim özeti

13 Ekim 2026 · Denetlenen commit: `70ddc62` · Bağımsız denetim.

Bu belge, yerel `.pcbai-state/audit-rd-dalga0/claude-review.md` raporunun kısa,
depoda erişilebilir özetidir. Denetçi kodu değiştirmedi; uygulayanın kanıtlarının
üzerine yazmadı. Bu özet yeni bir koşu veya S11 yayın sonuç JSON'u değildir.

- Proje `.venv` ortamıyla **255 test, OK, 3 skip, 762,7 sn**. Atlananlar Windows
  symlink yetkisi ve ortamda bulunmayan iki motor (`PCBAI_FREEROUTING/TRACEMAKER`).
- Gerçek KiCad entegrasyonu **11/11**, Ruff temiz.
- Sabit kicad-happy commit'i, 10/10 analiz çiftinin bayt eşitliği, 474 bulgu,
  pic_programmer'daki 19 ağın pin yinelemesi yeniden doğrulandı.
- İki alias yanlış pozitifinin UUID kapsamından kaynaklandığı ve ecc83-pp P4
  geometrik taşma iddiası kaynak dosyalar üzerinden doğrulandı.
- #1, #9 ve #12 fixture davranışları gerçek KiCad 10.0.4 ile yeniden üretildi.
  Uygulayanın ölçüm iddialarını çürüten bulgu yok.

İki belge eksiği: S11 sonuç JSON'u yalnız yerel durum klasöründe; raporlanan ecc83
projesinin adı belirtilmemiş. Üç öneri: paritenin de temiz kaldığı #1b niyet
fixture'ı, mevcut fixture davranışlarını sabitleyen testler ve `.venv` komutlarının
AGENTS.md'ye eklenmesi. Bunlar [D1-0](plan-rd-dalga1.md#d1-0-dalga-0-kapanışı)
kapsamına alındı; yayın JSON'u yalnız açık yayın koşusunda yazılacak, RD-B1 açık kalacak.

Ölçüm salt dosya analizine ve raporda belirtilen örneklere aittir; canlı IPC,
SPICE, fiziksel kart veya üretim doğrulaması değildir. Ham denetim raporu ve
geliştirme günlükleri `.pcbai-state/` altında yereldir, Git dağıtımına girmez.

## D1-0 kabulü

13 Ekim 2026 · Denetlenen commit: `ef05261` · Bağımsız denetim; kod değiştirilmedi.
Kaynak: yerel `.pcbai-state/audit-rd-dalga0/d1-0-review.md`.

- KiCad editörleri kapalıyken `.venv` ile **259 test, OK (256 geçti, 3 skip), 693,0 sn**, Python exit 0.
  Skip'ler Windows symlink yetkisi ve bu kabukta tanımlı olmayan iki motor (Freerouting, TraceMaker).
- Yeni dört karakterizasyon testi ve şematik yazım entegrasyonu geçti; Ruff/lisans exit 0.
  Uygulayanın `0xC000013A` kesintileri tekrarlanmadı; ürün hatası kanıtı bulunmadı.
- #1b fixture'ı, `intent.json`, S11 `ecc83-pp` notu, AGENTS.md `.venv` komutları ve denetim özeti tarifle uyumlu.
  Commit mesajında araç imzası yok.
- Engel olmayan not: fixture SHA kontrolünün `finally` içinde assert edilmesi asıl test hatasını gölgeleyebilir.

**Sonuç: D1-0 kabul.** Tam takım doğrulaması kapandı; S11 yayın JSON'u ve RD-B1 açık kalır.
Bu kayıt yeni koşu veya S11 yayın JSON'u değildir; D1-1…D1-7 henüz uygulanmadı.
