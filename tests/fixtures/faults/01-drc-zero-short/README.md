# #1 — DRC sıfır ama iki şematik net bakırda kısa

KiCad 10 projesi: 15×10 mm kart, iki tek-pin konnektör, iki pad ve tek 0.25 mm iz.
Şematik `J1.1=/LEFT`, `J2.1=/RIGHT`; PCB iki padı `/LEFT` olarak atar ve iz fiziksel olarak birleştirir.
DRC kendi yanlış net modeline göre temizdir. Exclusion, severity ignore veya özel DRC kuralı kullanılmaz.

13 Ekim 2026, PcbAi 0.1.14 / gerçek KiCad CLI 10.0.4 ölçümü:

- Normal `drc`: `ok=true`, `verified=drc_ok`, **0 hata, 0 uyarı**, gerçek KiCad exit 0.
- `drc(parity=true)`: `ok=true`, `verified=drc_findings`, **0 hata, 1 uyarı**;
  `net_conflict`: J2.1 kartta `/LEFT`, şematikte `/RIGHT`.
- ERC: 0 hata, 2 tek-pin-net uyarısı. Bu kasıtlı en küçük projenin ek sınırıdır.
- `board_stats`: 2 footprint, 2 SMD pad, 0 via, 15×10 mm; ölçülen, üretim kabulü değil.

Yakalaması gereken: **RD-C2** geometriden pad/net uzlaştırma + `netlist_assert`, **RD-A4** bağımsız kalibrasyon.
Mevcut PcbAi'nin isteğe bağlı paritesi bunu zaten yakalar; normal DRC yeşili tasarım doğruluğu değildir.
Bu paket yeni yakalayıcı eklemez. Gerber bakırından bağımsız short doğrulaması henüz yapılmadı.

Yeniden ölç: depo kökünde `python scripts/measure_fault_fixtures.py` (fixture dosyalarına yazmaz).
Kanıt `.pcbai-state/s11/faults/result.json` ve `01-drc-zero-short-netlist.xml`;
yayın sonucu `docs/spikes/*-result.json` oluşturulmaz. `--generate` sadece owned fixture'ları yeniden üretmek içindir.
