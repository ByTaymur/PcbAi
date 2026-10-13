# #9 — Sayıları doğru, net üyelerini yanlış bildiren analiz girdisi

KiCad 10 projesi: iki tek-pin konnektör, iki ayrı net, iki pad; birleştiren bakır yok.
Gerçek netlist `J1.1=/LEFT`, `J2.1=/RIGHT`.
`reported-net-members.json` bilinçli olarak üyeleri ters bildirir:
`/LEFT=[J2.1]`, `/RIGHT=[J1.1]`. Net ve pin toplamları yine 2 ve 2'dir.
Bu JSON yürütülecek kod değildir; gelecekteki kalibrasyon aracının dış analiz girdisidir.

13 Ekim 2026, PcbAi 0.1.14 / gerçek KiCad CLI 10.0.4 ölçümü:

- Normal DRC ve şematik parite: `ok=true`, `verified=drc_ok`, **0 hata, 0 uyarı**.
- ERC: 0 hata, 2 tek-pin-net uyarısı; `verified=erc_findings`.
- `board_stats`: 2 footprint, 2 SMD pad, 0 via, 15×10 mm.
- Gerçek `kicad-cli sch export netlist` exit 0; native XML üyeleri yukarıdaki doğru eşlemeyi verir.
- PcbAi bugün dış `reported-net-members.json` girdisini kabul eden bir kalibrasyon aracı sunmuyor.
  DRC/parite yanlış JSON'u tüketmediği için bu yanlış raporu yakaladığı iddia edilmez;
  olmayan denetim temiz sayılmaz. Bu pakette yakalayıcı kod yazılmadı.

Yakalaması gereken: **RD-A4** ad anahtarına göre gerçek netlist üyeleriyle kalibrasyon;
**RD-A2** çalıştırılmamış kontrolün toplam kabulüne dönüşmesini engellemeli.
Salt topolojik üye-partition kıyası isim anahtarlarını atarsa bu swap kusurunu kaçırabilir;
bu fixture ad→üye eşlemesini de zorunlu kılar.

Yeniden ölç: `python scripts/measure_fault_fixtures.py`.
Kanıt `.pcbai-state/s11/faults/result.json` ve `09-wrong-net-members-netlist.xml`.
