# Plan — canlı işlem durumu ve günlük, VS Code + KiCad (GE)

14 Ekim 2026 · Durum: **plan, uygulama başlamadı**. Başlangıç: `ip/ip-isaret-paneli/2ac8a68`, VS Code 0.1.25.
Bağlı: [işaret paneli planı](plan-isaret-paneli.md), [AJ planı](plan-ajan-arayuz.md), [durum](status.md), AGENTS.md.

Kullanıcı isteği (14 Ekim): "İşlem devam ediyor / bitti / şu an bu işlem yapılıyor … yani bilgi ekranı iki tarafta da
yok." İstenen öncelikle **canlı durum** (şu an ne çalışıyor, bitti mi, hata mı), hem VS Code'da hem KiCad'de; geçmiş
günlük bunun altında.

## 0. Bugünkü durum (ölçülen)

| Konu | Bugün | Kaynak |
|---|---|---|
| Olay kaydı | Olay **yalnız işlem bitince** yazılır (`engine.call()` sonunda `events.record`). Başlayan/süren işlem hiçbir yerde görünmez | `pcbai/service/events.py`, `engine.py` `call()` |
| Olay içeriği | saat, istemci, araç, sonuç, `change_id`. Belge, işaret no, süre, özet yok. Bellekte 500 olay, servis kapanınca silinir | `events.py` |
| Arka plan işleri | `Jobs` `queued → running → completed/failed` durumunu tutuyor (`job_status`), ama hiçbir ekran göstermiyor | `pcbai/service/jobs.py` |
| Kalıcı kayıt | `<state>/audit.jsonl` (2 × 10 MB): araç, süre, sonuç, hata kodu, belge, revizyon, kanıt, değişiklik, kontrol noktası. Okuyan ekran yok | `pcbai/verify/audit.py` |
| VS Code | Yan panelde katlanır "Ajan etkinliği" (yalnız biten olaylar); durum çubuğunda servis öğesi | `sidebar_view.js`, `extension.js` `statusItem` |
| KiCad | PcbAi Asistan penceresi `/events`'i 2 sn'de bir okuyor, tek satırlık "Durum:" etiketi var | `kicad_plugin/assistant_window.py` `poll_events`, `self.status` |

Sonuç: iki taraf da yalnız **biten** işlemi görebiliyor; "şu an çalışıyor" bilgisini servis hiç yayınlamıyor.

---

## 1. İlkeler

1. **Durumun tek kaynağı servis.** Servis her çağrının başını ve sonunu yayınlar; VS Code ve KiCad aynı uç noktayı
   okur, aynı şeyi gösterir. İstemci tahmin etmez.
2. **Üç hâl, net dil.** `çalışıyor` (⏳ + geçen süre), `bitti` (✓), `hata/engellendi` (✗/⚠ + ne yapılmalı).
   Uzun işte ilerleme biliniyorsa yüzde, bilinmiyorsa yalnız geçen süre; uydurma yüzde yok.
3. **Yalnız okuma.** Ekranlar hiçbir şey yazmaz/geri almaz.
4. **Not/dosya metni ve gizli bilgi girmez.** İşaret notu, istem metni, jeton, API anahtarı kayda girmez; özet 200
   karakterle kesilir; çizim yalnız `textContent` / `wx.StaticText.SetLabel`.
5. **Ucuz.** 1 sn'de bir yalnız yeni olaylar çekilir.

---

## 2. İş paketleri

### GE-1 Servis: başla/bitir olayları ve okuma uç noktaları (0,5–1 gün)

- `engine.call()` başında `events.start(client, tool, document, marker_n)` → `phase="running"` olayı ve bir
  `run_id`; sonunda aynı `run_id` ile `phase="done"` olayı (sonuç, süre, özet, `change_id`, hata kodu ve kullanıcıya
  dönük ipucu). İstisnada da `done` yazılır (`finally`), "sonsuza dek çalışıyor" kalmaz.
- `Jobs`: `queued/running/completed/failed` geçişleri de olay olarak yayınlanır (`job_id`, araç); motor ilerleme
  bildiriyorsa (`progress` 0–1) en çok 1 sn'de bir olay.
- `GET /activity` (yerel jetonla): o an **çalışan** işlemler (`run_id`, istemci, araç, belge, başlangıç) + son 1
  bitmiş işlem. `GET /events?since=` aynen kalır, yeni alanlarla zenginleşir.
- Audit satırına `client`, `summary`, `marker_n` eklenir; `GET /audit?before=&since=&limit=&outcome=&client=`
  kalıcı geçmişi sayfalı okur (döndürülmüş `audit.1.jsonl` dahil, bozuk satır `skipped`).
- `GET /overview`: proje, revizyon (ilk 12), açık/bitmiş/engelli işaret sayısı, son ERC/DRC kanıtı, KiCad editör
  kilidi, servis sürümü/süresi. Mevcut verilerden okunur, yeni ölçüm başlatmaz.
- **Bitti (birim testi):** her çağrı tam bir running + done çifti üretir (hata ve istisnada da); eşzamanlı iki
  çağrı iki ayrı `run_id`; `/activity` çalışanı gösterir, bitince düşer; iş geçişleri olay olur; not/istem/jeton
  kayıtta yok; `/audit` sayfalama ve süzgeç; jetonsuz istek 401.

### GE-2 VS Code (1 gün)

- **Durum çubuğu** (sol alt, her zaman görünür): boşta `PcbAi ✓ hazır`; çalışırken
  `$(sync~spin) Claude Code: set_value · R5 (3 sn)`; birden fazlaysa `… +1`; bitince 5 sn `✓ set_value bitti`,
  hata/engelde kırmızı/sarı `⚠ editör açık — kaydedip kapatın`. Tıklayınca günlük ekranı açılır.
- **Yan panel üstü canlı şerit:** aynı bilgi + çalışan arka plan işleri (`autoroute — 40 sn`, yüzde varsa yüzde).
  "Ajan etkinliği" listesi kalır (son 10) ve "Tümünü gör" bağlantısı.
- **Günlük ekranı** (`PcbAi: Günlük`, editör sekmesi):
  - Üst bilgi şeridi: proje · revizyon · servis · işaretler "3 açık · 2 bitti" · son DRC/ERC · editör uyarısı.
  - Tablo: saat · istemci · araç · belge · işaret · durum · süre · özet; çalışan satır en üstte dönen simgeyle,
    bitince yerinde ✓/✗'e döner. Satıra tıklayınca revizyon önce → sonra, kanıt/değişiklik/kontrol noktası
    (kopyala).
  - Süzgeçler (yalnız hatalar, yalnız ajan, yalnız yazanlar), Duraklat, aşağı kaydırınca eski sayfa, CSV dışa aktar
    (CSV enjeksiyonuna karşı `=,+,-,@` ile başlayan hücreye `'`).
- **Bitti (birim testi):** durum çubuğu metinleri (boş/çalışıyor/çoklu/bitti/hata); running → done aynı satırda
  güncellenir; servis kapalıyken "PcbAi kapalı", hata atmaz; CSP/nonce; `textContent` dışı çizim yok; CSV kaçışı.

### GE-3 KiCad: PcbAi Asistan penceresinde canlı durum (0,5 gün)

- Mevcut "Durum:" satırı canlı olur: `⏳ Claude Code: set_value · R5 çalışıyor (3 sn)` → `✓ bitti — Dosya → Geri al
  (Revert) ile yeniden yükleyin` / `⚠ engellendi — kartı kaydedip editörü kapatın` / `✗ hata: …`.
- Altına kısa **etkinlik listesi** (`wx.ListCtrl`, son 20 satır: saat · kim · araç · durum) ve tek satır bilgi şeridi
  (servis · revizyon · "3 açık · 2 bitti" işaret · son DRC). Satıra çift tıkla → ayrıntı iletişim kutusu.
  "VS Code'da günlüğü aç" düğmesi (mevcut `vscode://` yolu).
- Yoklama 1 sn; pencere kapalıyken yoklama yok. Servis kapalıysa "PcbAi servisi kapalı" der, hata penceresi açmaz.
- **Bitti (birim testi, `tests/test_kicad_assistant.py`):** sahte servisle running → done etiket dizisi; liste 20'de
  kırpılır; engel/hata metinleri; servis kapalı; not metni kod olarak yorumlanmaz.

### GE-4 Gerçek ortam kabulü (elle)

1. VS Code + KiCad pencereleri açık; Claude Code'a `set_value` yaptır → iki tarafta da 1–2 sn içinde
   "çalışıyor", sonra "bitti" + değişiklik kimliği.
2. KiCad şematik editörü açıkken yazma dene → iki tarafta "⚠ engellendi — editörü kapatın".
3. `autoroute` önizle → iki tarafta süren iş ve geçen süre; bitince ✓.
4. Yan panelde bir işarete ✓ → `vscode · set_marker_status · #n · bitti`.
5. Servisi durdur/başlat → günlük ekranında eski satırlar yerinde; iki tarafta "kapalı" → "hazır".
- Sonuçlar `docs/status.md`'ye; yapılamayan adım "yapılmadı" kalır.

## 3. Sıra

| Sıra | Paket | Süre |
|---|---|---|
| 1 | GE-1 servis | 0,5–1 gün |
| 2 | GE-2 VS Code | 1 gün |
| 3 | GE-3 KiCad | 0,5 gün |
| 4 | GE-4 elle kabul | kısa |

Dal: `ip/ge-durum` (tek ajan, `ip/ip-isaret-paneli` birleştikten sonra). VS Code eklenti sürümü ve KiCad eklenti
sürümü (`kicad_plugin/plugin.json`) artırılır.

## 4. Açık kararlar (kullanıcı)

1. VS Code günlüğü editör sekmesi mi, alt panelde (Terminal/Çıktı yanında) mı? Öneri: **editör sekmesi**; canlı
   durum zaten durum çubuğunda ve yan panelde her zaman görünür.
2. Bir işlem bitince bildirim balonu çıksın mı? Öneri: yalnız **hata/engel** için (VS Code bildirimi; KiCad'de
   durum satırı kırmızı), başarılı işlemde balon yok.
3. Kayıt süresi: bugün 2 × 10 MB (≈ 50 bin satır). Öneri: aynen.
