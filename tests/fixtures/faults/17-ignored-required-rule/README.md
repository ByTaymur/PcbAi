# #17 — yoksayılan zorunlu ERC/DRC kuralı

İki farklı nete ait 1 × 1 mm padin merkezleri (5, 5) ve (6,1, 5) mm;
bakır aralığı 0,1 mm, proje alt sınırı 0,2 mm. `clearance=ignore` bu ihlali gizler.
Şematikte iki tek-pin konektörün etiketleri kaldırılmıştır; `pin_not_connected=ignore`
iki açık pin bulgusunu gizler.

Kaynak: #9 fixture'ından türetilmiş bağımsız test projesi. Kullanıcı kartı değildir.
Testler özel kopyada çalışır; kayıtlı kaynak fixture'a yazmaz. Proje ayarları error olarak
yalnız KiCad kontrol kopyasında override edildiğinde her iki kuralın bulgusu geri gelir.

Beklenen PcbAi sonucu: tek ERC/DRC ve `check` kapsamlarında `checks_incomplete`;
her kural için `required=true`, `status=skipped`, `reason=rule_ignored_in_project`.
Gerçek CLI `sch`, `pcb`, `all` kapsamlarında exit 2; girdi revizyonu değişmez.
Avlu/maske veya başka bulgular bu fixture'da bulunabilir; sıfır diğer hata iddia edilmez.
