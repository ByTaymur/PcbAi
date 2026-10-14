# Plan — "KiCad'e yükle" düğmesi (KR)

14 Ekim 2026 · Durum: **plan, uygulama başlamadı**. Başlangıç: `main/256dd1f`, çekirdek 0.1.27, VS Code 0.1.23.
Bağlı: [AJ planı](plan-ajan-arayuz.md), [eksikler](plan-eksikler.md), [durum](status.md), AGENTS.md.

**Kullanıcı kararı (14 Ekim):** VS Code'da tek bir **"KiCad'e yükle"** düğmesi yeterli. Basınca depodaki güncel
KiCad eklentisi kurulur; **kurulu sürüm ne olursa olsun yenisiyle değiştirilir**, kurulu değilse yeni kurulur.
Sürüm uyarısı, ayrı komut satırı aracı, KiCad içi sürüm satırı bu turda yok.

Neden: 14 Ekim'de VS Code'da 0.1.18, KiCad PCM'de 0.1.14 kuruluydu; paketler (0.1.23 / 0.1.27) bir worktree'nin
`dist/` klasöründeydi ve PCM ekranındaki "İndir" eskisini yeniden kuruyordu. Elle kurulumda yedek yanlışlıkla
eklenti tarama yolunun içine kondu (sonra taşındı).

Kısıt: KiCad 10 PCM'de "dosyadan kur" için komut satırı ya da API **yok**. Düğme, PCM'in yaptığını yapar: paketi
`Documents/KiCad/10.0/3rdparty/plugins/org_pcbai_kicad` altına açar ve `%APPDATA%/kicad/10.0/installed_packages.json`
içindeki PcbAi kaydını (`current_version`, `install_timestamp`, `package` = `metadata.json`) yazar. 14 Ekim'deki
elle kurulum bu yolla yapıldı (`0.1.14 → 0.1.27`); gerçek KiCad'de PCM görünümü ve "Kaldır" uyumu KR-3'te doğrulanır.

---

## 1. Kurallar

1. **KiCad açıkken yazılmaz.** `kicad.exe`, `pcbnew.exe`, `eeschema.exe` çalışıyorsa düğme "KiCad'i kapatın, sonra
   tekrar basın" der ve hiçbir dosyaya dokunmaz (KiCad kapanırken kaydı bellekteki eski haliyle ezer). Zorla kapatma
   yok.
2. **Her zaman değiştir.** Kurulu sürüm daha yeni, aynı ya da eski olsa da klasör tamamen yenisiyle değiştirilir;
   kayıt yoksa eklenir. Önceki sürüm ve yeni sürüm bildirimde yazılır ("0.1.14 → 0.1.27").
3. **Önce yedek, tarama yolunun dışında.** Eski klasör ve kayıt dosyası `Documents/KiCad/10.0/pcbai-backups/<zaman>/`
   altına kopyalanır; son 5 yedek tutulur. Yedek asla `3rdparty/plugins` içine konmaz.
4. **Dar yazım.** Kayıtta yalnız `org.pcbai.kicad` girdisi değişir; diğer paketler aynı kalır; dosya biçimi (4 boşluk,
   CRLF) korunur. Kayıt dosyası ayrıştırılamıyorsa hiçbir şey yazılmaz ve PCM'den "Dosyadan yükle" önerilir.
5. **Paket hep güncel üretilir.** Düğme önce KiCad paketini depo kökünde yeniden üretir (`build_pcm.py`, sürüm
   `pcbai/__init__.py`'den); worktree `dist/` yollarına bakılmaz.
6. **Ölçülen sonuç.** Yazımdan sonra kayıt ve klasör yeniden okunur; sürüm ve dosya listesi eşleşmezse "kurulum
   doğrulanamadı" denir ve yedeğin yolu gösterilir.
7. Testler gerçek KiCad klasörlerine yazmaz; geçici `APPDATA`/`Documents` ile çalışır (AGENTS.md).

---

## 2. İş paketleri

### KR-1 Kurulum çekirdeği `pcbai/install/kicad.py` (1 gün)

- `install_kicad(zip_path, *, documents, appdata, running=process_list)` → `{previous, installed, backup, files}`.
  Adımlar: KiCad süreç denetimi (`tasklist`, `shell=False`, zaman aşımı) → zip doğrulama (`metadata.json` kimliği
  `org.pcbai.kicad`, yalnız `plugins/` altı, yol kaçışı yok) → yedek → klasör değiştirme → kayıt yazımı → geri okuma.
- Yol kökleri: KiCad'in `kicad_common.json` içindeki `KICAD10_3RD_PARTY` değişkeni varsa o, yoksa Windows varsayılanı.
- CLI karşılığı (aynı fonksiyon): `python -m pcbai install-kicad` — düğmenin arka ucu ve elle kullanım için.
- **Bitti (birim testi, geçici klasörler):** ilk kurulum (kayıt yok → eklenir), güncelleme (0.1.14 → yeni), aynı ya da
  daha yeni sürümün de değiştirilmesi, KiCad açıkken ret ve dosya SHA-256'larının değişmemesi, bozuk kayda dokunmama,
  diğer paketlerin eşitliği, CRLF/4 boşluk korunması, yedeğin tarama yolu dışında olması ve 5 yedek sınırı, zip'te
  `../` girdisinin reddi.

### KR-2 VS Code düğmesi (0,5 gün)

- Yan paneldeki eylemlere **"KiCad'e yükle"** düğmesi ve komut **PcbAi: Eklentiyi KiCad'e yükle**.
- Akış: paketi üret → `python -m pcbai install-kicad --json` (servis gerekmez, `.venv` Python'u, zaman aşımı 120 sn) →
  sonuç bildirimi: "PcbAi KiCad eklentisi 0.1.14 → 0.1.27 kuruldu. KiCad'i açın; araç çubuğunda üç düğme olmalı." /
  "KiCad açık: kapatıp tekrar basın." / hata + yedek yolu. Ayrıntı PcbAi çıktı kanalına yazılır.
- VS Code eklentisi sürümü artırılır.
- **Bitti:** sahte arka uç çıktılarıyla üç bildirim dalı; düğme ve komut kayıtlı.

### KR-3 Gerçek ortam kabulü (elle, 0,5 gün)

1. KiCad kapalı → düğme → KiCad aç → PCM'de PcbAi yeni sürüm; araç çubuğunda üç düğme; Asistan penceresi açılır.
2. Aynı sürüm kuruluyken düğmeye tekrar bas → yine değiştirilir, bildirim "0.1.27 → 0.1.27".
3. KiCad açıkken düğme → ret; eklenti klasörü ve kayıt değişmez.
4. PCM'den "Kaldır" → klasör ve kayıt temiz; ardından düğme → yeniden kurulur.
- Sonuçlar `docs/status.md`'ye; çalıştırılamayan adım "yapılmadı" kalır.

## 3. Sıra

| Sıra | Paket | Süre |
|---|---|---|
| 1 | KR-1 kurulum çekirdeği + CLI | 1 gün |
| 2 | KR-2 VS Code düğmesi | 0,5 gün |
| 3 | KR-3 gerçek ortam kabulü | 0,5 gün |

Dal: `ip/kr-kicad-yukle` (tek ajan).

## 4. Riskler

| Risk | Önlem |
|---|---|
| PCM kayıt biçimi KiCad sürümüyle değişir | Bilinmeyen biçimde yazmadan durur; KR-3'te doğrulama |
| PCM'in "Kaldır"ı taklit kurulumu tanımaz | KR-3 adım 4; tanımazsa düğme "PCM'den Dosyadan yükle" talimatına döner |
| Kullanıcı KiCad açıkken basar | Ret ve açık mesaj; hiçbir dosya değişmez |

## 5. Bu turda yok

VS Code eklentisinin kendini güncellemesi, sürüm uyarı satırları, KiCad penceresinde sürüm satırı, deneme
eklentilerinin (`org.pcbai.ajs1`) otomatik kaldırılması.
