# 0004 — Referans depolar: lisans ve entegrasyon kararları

13 Ekim 2026 · K15, K16 (adım 1), K20, K21 **kabul**; K16 adım 2, K17, K18, K19 **açık**.
Kaynak: [plan-referans-depolar.md](../plan-referans-depolar.md) bölüm 2 ve 8, [S11](../spikes/S11.md),
bağımsız [denetim özeti](../rd-dalga0-denetim-ozeti.md) (ham rapor yerel `.pcbai-state/audit-rd-dalga0/claude-review.md`).
Kullanıcı öneriler olduğu gibi kabul edildi.

- **K15 — eda-agent (Apache-2.0) kodu alınmaz.** Fikirler ve kamu kaynaklı sayılar (IPC-7351, KLC) atıfla,
  temiz yeniden yazımla kullanılır. Uygulayan ajan eda-agent dosyalarını açıp kopyalamaz; kaynak olarak yalnız
  plan belgesindeki fikir satırı gösterilir. BLPL (Apache-2.0) için de aynı kural geçerlidir. Dağıtım LGPL-2.1-or-later kalır.
- **K16 adım 1 — kicad-happy ayrı süreçte, sabit commit ile.** Commit `06840467ad0f5d76af45f64449b1f5ecb10f052f`.
  Kod, şema ya da şablon `pcbai/` paketine alınmaz. Çalıştırma deseni `pcbai/external.py` ile aynıdır: yol
  yapılandırma/ortam üzerinden, KiCad Python `-I`, `shell=False`, zaman aşımı, özel geçici kopya.
  `doctor` sürüm ve commit'i gösterir. Dedektörler yalnızca RD-A4 kalibrasyonunu geçtikten sonra bulgu üretir.
- **K16 adım 2 — `vendor/` altına alma ayrı karardır, şimdi verilmedi.** RD-A4 kalibrasyonu ve RD-B2 ölçümü
  sonrası, dedektör bazında yeniden sorulur. S11'e göre `detect_label_aliases` kabul dışıdır.
- **K20 — RD-I'nin kesilebilir paketleri (I3, I4, I8, I11, I12) "zaman kalırsa".** Zorunlular: I1, I2, I5, I6,
  I7, I9, I10, I13. Kesme sırası plan bölüm 6'daki gibidir.
- **K21 — GPL ayrı programlar (KLC denetçisi, uConfig) isteğe bağlı.** PcbAi paketine girmez (K12 deseni).
  Kurulu değilse `doctor` eksikliği ve etkisini gösterir; ilgili kontrol `skipped` olur, "temiz" sayılmaz.

Açık kalanlar ilgili dalgadan önce sorulur: K17 (geniş korpus) RD-G3'ten, K18 (distribütör API'leri) dalga 2
RD-D'den, K19 (skill dağıtımı) dalga 6 RD-H1'den önce.
