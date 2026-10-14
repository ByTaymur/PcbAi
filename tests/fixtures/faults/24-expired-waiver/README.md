# #24 — süresi dolmuş bulgu muafiyeti

Bu fixture kaydedilmiş devre değildir; muafiyet değerlendirmesinin veri fixture'ıdır.
ERC'nin tek `pin_not_connected` bulgusu (`uuid=a`, konum 1/2 mm) normalleştirilince
`erc:pin_not_connected:50f2962dc332` olur. Muafiyet 2026-10-14 00:00 UTC'de biter.
`WaiverEngineTests.test_fixture24_expired_waiver_is_active` sabit tarihte bulgunun
etkin, muaf listenin boş ve `waiver_expired` uyarısının görünür olduğunu ölçer.

Ayrı `WaiverRealCLITests` gerçek #1 KiCad parite bulgusuyla subprocess exit 0/1/2'yi
ölçer. Bu JSON bir kart simülasyonu veya fiziksel/üretim kabulü değildir.
