# Ölçülmüş yetenek sınırları

Kontrol atlamak temiz sonuç değildir. Kimlikler `pcbai.verify.limits` ile birebir eşleşir.

| limit_id | Yapılamaz | Neden | Ölçüm/kanıt | Etkilenen araç/kontrol |
|---|---|---|---|---|
| L-IPC-NO-LIVE-SCH | Canlı şematik IPC ölçümü | Desteklenen IPC yüzeyi sınırlı | [Durum](status.md) | Şematik araçları |
| L-UNSAVED-BUFFER | Kaydedilmemiş tampon doğrulama | Dosya modu yalnız diski görür | [Durum](status.md) | ERC/DRC/check |
| L-RENDER-SIZE-10.0.4 | İstenen render boyutunu varsaymak | 10.0.4 gerçek çıktısı ölçülmeli | [Durum](status.md) | render_board |
| L-SYMLINK-WINDOWS | Yetkisiz Windows symlink testi | Hesap yetkisi gerektirir | [Denetim](rd-dalga0-denetim-ozeti.md) | Güvenlik testleri |
| L-KH-LABEL-ALIAS | UUID kapsamını farklı etiket saymak | Sayfa kimliği ile ad karıştırılıyor | [S11](spikes/S11.md) | Label/topoloji dedektörleri |
| L-KH-PIN-MULTIPLICITY | Yinelenen pinleri fiziksel pin saymak | Çoklu birim pinleri yineleniyor | [S11](spikes/S11.md) | Pin sayısı/akım dedektörleri |
| L-KH-SMD-CATEGORY | Connect pad'ı SMD saymak | Pad türü ve parça sınıfı farklı | [S11](spikes/S11.md) | PCB sınıf sayımları |
| L-NO-INTENT-CHECK | DRC/parite ile niyeti kabul etmek | Aynı yanlış model iki kontrolü de geçer | [#1b](../tests/fixtures/faults/01b-schematic-label-merge/README.md) | check/netlist_assert |
| L-EXTERNAL-MODEL-CALIBRATION | Eşleşmeyen modelden kabul üretmek | Sayı ve üyelik ayrı kalibre edilmeli | [#9](../tests/fixtures/faults/09-wrong-net-members/README.md) | Kalibrasyona bağımlı dedektörler |
| L-FAB-CONNECTION-SUBSET | Karmaşık Gerber ve katmanlar arası kaplamalı yolu kabul etmek | İlk okuyucu yalnız pozitif mm doğrusal standart aperture ve yüzey padlarını destekler | [R2-B3](spikes/R2-B3.md) | check_fab_connections / tam RD-C2 açık |
