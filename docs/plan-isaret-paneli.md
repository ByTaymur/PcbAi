# Plan — yan panelde işaret silme ve "bitti" işareti (IP)

14 Ekim 2026 · Durum: **IP-1…IP-3 uygulandı** (dal `ip/ip-isaret-paneli`, VS Code 0.1.25); IP-4 elle kabul bekliyor.
Başlangıç: `main/9ba708a`.
Bağlı: [görünüm planı](plan-gorunum.md), [AJ planı](plan-ajan-arayuz.md), [durum](status.md), AGENTS.md.

Kullanıcı isteği (14 Ekim, ekran görüntüsü): yan paneldeki **İşaretler** listesinde

1. işi biten işareti **silme** düğmesi,
2. yapılan işe **tik atma** ("bitti" olarak işaretleme).

## 0. Bugünkü durum (ölçülen)

| Konu | Bugün | Kaynak |
|---|---|---|
| Satırdaki onay kutusu | Yalnız "bu işaret isteme eklensin mi" seçimi; açık işaretlerde varsayılan işaretli | `media/sidebar.js` (`markers` çizimi), `sidebar_view.js` `load()` |
| Bitmiş işaret | Listede soluk, sonunda ` — done`; ayrı görünüm yok | `sidebar.js`, `.marker.closed` |
| Silme | Servis hazır: görünüm kanalında `delete_marker` (önizle → uygula, `markers_revision` kapısı, yazımdan önce kontrol noktası). Yalnız kart/şematik görünümünden çağrılıyor; yan panelde yok | `engine.py` `view_definitions`, `markers.py` `preview(delete=True)`, `board_view.js` `markerPreview` |
| "Bitti" | Yalnız `update_marker_status` (MCP aracı). `done` **kanıt ister**: `evidence_id` gerçek bir değişiklik kanıtına (aynı hedef/revizyon, `changed`, önce/sonra SHA farkı) bağlı olmalı; `reason` zorunlu; onaysız işaret güncellenemez | `markers.py` `preview_status` |

**Önemli karar:** `done` için kanıt kapısı bilerek var; ajanın "yaptım" deyip kanıtsız kapatmasını önler. Kullanıcının
elle "bitti" demesi ayrı bir yoldur ve bu kapıyı **ajanlar için gevşetmez**.

---

## 1. İlkeler

1. **İki ayrı kontrol.** "İsteme ekle" onay kutusu kalır; "bitti" ve "sil" satır sonunda ayrı düğmelerdir. Aynı
   kutuya iki anlam yüklenmez.
2. **Elle "bitti" yalnız kullanıcı kanalında.** Yeni durum değişikliği yalnız görünüm kanalından (`/view/call`,
   `source="view"`) kabul edilir; MCP araç listesinde görünmez. Ajan yine `update_marker_status` + kanıt kullanır.
3. **Kayıt dürüst kalır.** Elle kapatılan işaret `status="done"`, `closed_by="user"`, `reason="Kullanıcı elle
   işaretledi"` ile yazılır; `evidence_id` yoktur. Panel ve `get_markers` bunu "elle bitti" olarak gösterir; ajan
   kanıtlı bitişlerle karıştırmaz.
4. **Mevcut kapılar aynen.** Önizle → uygula, `markers_revision` eşitliği, yazımdan önce kontrol noktası, imza;
   onaysız (içe aktarılmış) işarette önce onay gerekir.
5. **Geri alınabilir.** "Bitti" tekrar basılınca `open`'a döner. Silme onay ister ("#1 silinsin mi?") ve kontrol
   noktası sayesinde geri yüklenebilir.

---

## 2. İş paketleri

### IP-1 Servis: kullanıcı durum değişikliği (0,5 gün)

- `engine.py` `view_definitions`'a `set_marker_status`: `TARGET`, `revision`, `markers_revision`,
  `mode` (preview/apply), `n`, `status` (`open` | `done`), `candidate_id`. Yalnız `source="view"` ile çağrılabilir;
  MCP `/tools` listesinde yok.
- `markers.py`: `preview_status(..., manual=True)` dalı: kanıt istemez, `reason` sabit "Kullanıcı elle işaretledi",
  `closed_by="user"` yazar; `open`'a dönüşte `closed_by`, `reason`, `evidence_id` temizlenir. Onaysız işaret reddedilir.
  `apply` aynı (`action="status"`).
- `get_markers` çıktısı `closed_by` alanını taşır.
- **Bitti (birim testi):** görünüm kanalından done/open önizle-uygula; MCP kanalından `set_marker_status` bilinmeyen
  araç; `update_marker_status` ile kanıtsız `done` hâlâ reddediliyor; onaysız işaret reddi; bayat `markers_revision`
  reddi; kontrol noktası oluşuyor; imza geçerli.

### IP-2 Yan panel: düğmeler ve görünüm (0,5–1 gün)

- Satır düzeni: `[isteme ekle ☐]  #1 [kart · …] "not"  [✓ Bitti] [🗑]` (düğmeler metin + `title` ipucuyla; simgeler
  VS Code codicon).
- **Bitti:** `sidebar_view.js` → `viewCall('set_marker_status', preview)` → `apply`; ardından liste yenilenir. Bitmiş
  satır yeşil tik ve üstü çizili not; `closed_by="user"` ise "(elle)" etiketi; ajan kanıtıyla bitmişse kanıt kimliği
  `title`'da. Bitmiş satırın "isteme ekle" kutusu kapalı ve devre dışı.
- **Sil:** VS Code onay penceresi ("#1 silinsin mi? Kontrol noktası alınır.") → `delete_marker` önizle → uygula.
- **Toplu:** liste başında "Bitenleri gizle" anahtarı (yalnız görünüm, `vscode.setState`) ve "Bitenleri sil" düğmesi
  (onaylı; her işaret için aynı önizle/uygula, ilk hatada durur ve kaçının silindiğini söyler).
- Yarış: başka bir istemci işaretleri değiştirdiyse (`stale_markers`) "İşaretler değişti, yenilendi" deyip listeyi
  tazeler; işlemi tekrar etmez.
- Panel `viewCall` için extension'daki mevcut `/view/call` yardımcısını kullanır (kart/şematik görünümüyle aynı).
- **Bitti (birim testi, `test/sidebar.test.js`):** bitti → servis çağrı sırası (preview, apply) ve yenileme; ikinci
  basışta `open`; sil → onay reddedilirse çağrı yok, onayda preview+apply; `stale_markers` mesajı; bitmiş satırda kutu
  devre dışı; "Bitenleri sil" kısmi hata raporu; not metni yine yalnız `textContent` ile çizilir.

### IP-3 Kart/şematik görünümü ve ajan istemi uyumu (0,5 gün)

- Kart ve şematik görünümündeki işaret listesinde aynı "Bitti/Sil" düğmeleri (aynı servis çağrıları).
- AJ-3 istemi: elle bitmiş işaretler isteme girmez (bugün de yalnız seçilen açık işaretler giriyor; testle sabitlenir).
- KiCad Asistan penceresi zaten yalnız `open` işaretleri listeliyor; değişiklik yok.

### IP-4 Gerçek ortam kabulü (elle)

1. Ekran görüntüsündeki #1 işaretinde **Bitti** → satır tikli, "(elle)"; VS Code yeniden yüklenince de öyle.
2. Tekrar **Bitti** → açık duruma döner.
3. **Sil** → onay → listeden kalkar; kart görünümünde de kalkar.
4. Claude Code `get_markers` çağırınca #1'i `closed_by: "user"` ile görür; kanıtsız `update_marker_status done`
   hâlâ reddedilir.
- Sonuçlar `docs/status.md`'ye; yapılamayan adım "yapılmadı" kalır.

## 3. Sıra

| Sıra | Paket | Süre |
|---|---|---|
| 1 | IP-1 servis | 0,5 gün |
| 2 | IP-2 yan panel | 0,5–1 gün |
| 3 | IP-3 görünümler + istem | 0,5 gün |
| 4 | IP-4 elle kabul | kısa |

Dal: `ip/ip-isaret-paneli` (tek ajan). VS Code eklenti sürümü artırılır.

## 4. Kararlar (uygulamada önerilenler seçildi; kullanıcı değiştirebilir)

1. "Bitti" olan işaretler listede kalsın mı (tikli, soluk) yoksa varsayılan gizlensin mi? Öneri: kalsın, "Bitenleri
   gizle" anahtarı olsun.
2. Ajan kanıtla `done` yazdığında panel kullanıcıya ayrıca bildirim göstersin mi? Öneri: hayır, satır tiklenir;
   ajan etkinliği listesinde zaten görünür.
