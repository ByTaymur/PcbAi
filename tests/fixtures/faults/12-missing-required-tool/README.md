# #12 — Zorunlu araç yokken kontrol çalıştırılamıyor

KiCad 10 projesi: boş geçerli şematik ve proje dosyası; komponent/net/PCB yok.
`required-check.json` ERC'yi zorunlu sayar ve `PCBAI_KICAD_CLI` için bilerek bulunmayan
`./intentionally-absent-kicad-cli` dosyasını beyan eder. Program yolu yalnız süreç ortamından verilir;
KiCad kurulumu silinmez, PATH/kullanıcı ayarları kalıcı değiştirilmez.
Ölçüm betiği owned geçici proje içinde aynı eksik yolu süreç ortamına uygular ve `finally` ile geri alır.

13 Ekim 2026, PcbAi 0.1.14 ölçümü:

- Araç mevcutken: ERC **0 hata, 0 uyarı**, `verified=erc_ok`.
- Araç bilerek eksikken `Engine.call('erc', ...)`: **`ok=false`, `verified=not_run`,
  `error.code=missing_dependency`, `measurements=[]`, `changed=false`**.
- Bu sonuç **temiz rapor değildir**; bugünkü tek araç kapısı zaten doğru biçimde reddeder.
  Gerekli kontrolleri birleştiren `checks_run`/`checks_incomplete` ve CLI 0/1/2 sözleşmesi henüz yok.
  Kontrol sonucu olmayan bir tüketicinin bunu temiz sayması gelecekteki regresyonun hedefidir.

Yakalaması gereken: **RD-A2** kapsamın eksikliğini toplam sonuçta korumak;
**RD-I9** zorunlu kontrol yokken CLI exit 2. Bu pakette bu yakalayıcılar eklenmedi.

Yeniden ölç: `python scripts/measure_fault_fixtures.py`.
Kanıt `.pcbai-state/s11/faults/result.json`, `missing_tool_erc` kaydı.
