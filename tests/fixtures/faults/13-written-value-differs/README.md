# #13 — Yazılan değer önizlenen niyetten farklı

Bu küçük şematik `tests.test_verify_readback` tarafından yalnız geçici kopyada kullanılır.
Test R1/R2 ekler, R1 için 4k7 önizler; SHA doğru olan adayda 9k9 enjekte ederek bağımsız
niyet kıyasını ölçer. 13 yazma aracında ayrıca disk yazımı bozulur. Beklenti:
`ok=false`, `changed=true`, `verified=readback_mismatch`, checkpoint ve geri yükleme
önerisi; dosya kendiliğinden geri alınmaz. Kaynak fixture yazılmaz.
