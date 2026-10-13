# Plan — RD dalga 1: güven temeli

Tarih: 13 Ekim 2026 · Durum: **D1-0 kabul; D1-1…D1-7 tamamlandı: 337 test OK/3 skip, gerçek KiCad 11/11, ek gerçek motor testleri 2/2; bağımsız hedefli denetim tamamlandı** · Takvim: 26 Ekim – 6 Kasım 2026 (PLAN Faz 1)
Bağlı: [plan-referans-depolar.md](plan-referans-depolar.md) bölüm 3, 4-A, RD-I9 · [karar 0004](decisions/0004-referans-depolar.md) ·
[S11](spikes/S11.md) · bağımsız dalga 0 [denetim özeti](rd-dalga0-denetim-ozeti.md)

Uygulayan Codex; bu dalgada bağımsız salt okunur denetçi ayrı Codex ajanı (AGENTS.md).
Claude plan denemesi zaman aşımına uğradı ve sonuç üretmedi; Claude denetimi yapılmış sayılmaz.
Bu belge **ne yapılacağını ve ne zaman bitmiş sayılacağını**
söyler. Kod biçimi uygulayana aittir; sözleşme alanları, durum değerleri ve test adları bağlayıcıdır.

## 0. Amaç

Dalga 1'in tek hedefi: **yeşil sonuç yalan söylemesin.** Dalga sonunda:

- Her ERC/DRC/motor bulgusu tek şemada ve kararlı kimlikle döner (RD-A1).
- Bir kontrol atlandığında, çöktüğünde ya da istenmediğinde sonuç "temiz" yazmaz (RD-A2, RD-I9).
- Dış analiz motoru, KiCad'in sayılarını ve **ad→üye** eşlemesini yeniden üretmeden bulgu veremez (RD-A4).
- Her yazma, diskten bağımsız geri okunmadan "uygulandı" sayılmaz (RD-A3).
- Bilinen sınırlar belgeli ve kimlikli (RD-A5); her araç çağrısı denetim kaydına düşer (RD-A6).

**Kapsam dışı:** `analyze_design` (RD-B2, dalga 2), kicad-happy'nin `vendor/` altına alınması (K16 adım 2),
VS Code'da yeni bulgu paneli (İP-6.5), Gerber doğrulaması (RD-C2), datasheet kapısı (RD-D2).

## 1. Sıra, dal ve süre

| Adım | Paket | Dal | Bağımlılık | Süre |
|---|---|---|---|---|
| D1-0 | Dalga 0 kapanışı | `ip/rd-dalga0` (mevcut) | — | 0,5 gün |
| D1-1 | RD-A1 ortak bulgu şeması | `ip/rd-a1-bulgu` | D1-0 | 3 gün |
| D1-2 | RD-A5 yetenek sınırları | `ip/rd-a5-sinir` | — (A2'den önce bitmeli) | 1 gün |
| D1-3 | RD-A2 `checks_run` manifesti | `ip/rd-a2-manifest` | A1, A5 | 2 gün |
| D1-4 | RD-I9 `pcbai check` CLI | `ip/rd-i9-cli` | A2 | 1 gün |
| D1-5 | RD-A6 denetim kaydı | `ip/rd-a6-kayit` | — | 1 gün |
| D1-6 | RD-A4 motor kalibrasyonu | `ip/rd-a4-kalibrasyon` | A1, A2 | 3 gün |
| D1-7 | RD-A3 yazma sonrası geri okuma | `ip/rd-a3-geriokuma` | A1 | 4 gün |

Toplam ~15,5 iş günü; takvimdeki 10 iş günü için **sıkışık**. Gecikmede kesme sırası: önce A6 dalga 2'ye kayar,
sonra A3'ün motor (autoroute/autoplace) kısmı. A1, A2, A4, I9 kesilmez (plan bölüm 6). Her paket ayrı commit ve
ayrı bağımsız denetimle kapanır; bir sonraki paket denetim sonucu beklenmeden başlayabilir ama birleşmez.

## 2. Ortak kurallar (AGENTS.md'ye ek)

- Testler proje sanal ortamıyla: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`. PATH'teki
  Python 3.14'te `jsonschema` yok; o yorumlayıcıyla alınan sonuç geçersizdir (dalga 0 denetimi bulgu 5).
- Kabuk çıkış kodu kanıt değildir; testler alt süreç çıkışını `subprocess` ile `shell=False` okur.
- **Geriye uyumluluk:** mevcut `verified` değerlerinin anlamı değişmez (`erc_ok`, `drc_ok`, `*_findings`,
  `not_run`, `verification_failed`, `stats_measured`, `simulated`, `pin_pad_inspected`). Yeni değerler eklenir.
  Ham KiCad bulgu alanları (`description`, `type`, `group`, `severity`, `items[].uuid`, `items[].pos`) korunur;
  [kicad_plugin/check.py](../kicad_plugin/check.py) ve VS Code görünümleri değişmeden çalışmalı.
- Yeni modüller [bölüm 3](plan-referans-depolar.md#3-mimari-yeni-denetim-katmanı) yerleşimine uyar: `pcbai/verify/`.
- Upstream kod alınmaz (K15, K16 adım 1). kicad-happy yalnızca ayrı süreçte ve yalnız gerçek koşu testlerinde;
  yol `PCBAI_KICAD_HAPPY` ortamından, yoksa test açıkça skip.
- Ürün davranışını değiştiren her paket çekirdek yama sürümünü bir artırır (`pcbai/__init__.py` + `pyproject.toml`).
- Paket sonunda: test/lint sonucu ve sınırları [status.md](status.md)'ye, işaret [plan-eksikler.md](plan-eksikler.md)'ye
  ve [plan-referans-depolar.md](plan-referans-depolar.md)'deki maddeye.

---

## D1-0 Dalga 0 kapanışı

**Uygulama durumu (13 Ekim):** dört karakterizasyon testi ve #1b fixture'ı eklendi, gerçek KiCad ile geçti;
S11.md proje adı ve AGENTS.md `.venv` komutları düzeltildi. RD-G2 4/16. Yayın JSON'u yazılmadı, RD-B1 açık.
**Bağımsız kabul:** Claude `ef05261` commit'ini denetledi; kapalı KiCad editörleriyle `.venv` tam takım
259 test OK, 3 skip, 693,0 sn, Python exit 0; Ruff ve lisans denetimi temiz.
Önceki kesintiler denetimde tekrarlanmadı; [sonuçlar ve sınırlar](status.md#d1-0-kapanış-uygulaması--13-ekim-2026).
Aşağıdaki tarif ve bitti ölçütleri korunur; sıradaki paket D1-1'dir.

1. [S11.md](spikes/S11.md)'ye ölçülen ecc83 projesinin adını yaz: `ecc83-pp` (aynı klasördeki `ecc83-pp_v2` ölçülmedi).
2. **Yayın sonucu:** `docs/spikes/S11-result.json` yalnız kullanıcı açıkça "S11 yayın koşusu" derse yazılır.
   İçerik `.pcbai-state/s11/result.json` + `manual-review.json` özetidir (ham demo çıktıları değil). Yazılınca
   S11.md, status.md ve fixture README'lerindeki `.pcbai-state/...` bağlantıları yayın dosyasına çevrilir ve RD-B1
   `[x]` olur. Yazılmazsa RD-B1 açık kalır; dalga 1'i engellemez.
3. AGENTS.md test satırlarına `.venv` yorumlayıcısını ekle.
4. **Karakterizasyon testi** `tests/test_fault_fixtures.py` (gerçek KiCad yoksa skip). Bugünkü davranışı sabitler;
   ilgili paket davranışı bilerek değiştirdiğinde beklenti aynı commit'te güncellenir:
   - `test_01_plain_drc_green_parity_conflict`: düz DRC `drc_ok` 0/0; `parity=true` bir `net_conflict` (J2.1).
   - `test_09_native_members_disagree_with_reported_json`: DRC+parite `drc_ok`; native netlist `/LEFT=[J1.1]`,
     `/RIGHT=[J2.1]`; `reported-net-members.json` bunun tersi.
   - `test_12_missing_cli_is_not_run`: eksik `PCBAI_KICAD_CLI` ile `erc` → `ok=false`, `not_run`, `missing_dependency`.
   Fixture'lar özel geçici kopyada çalışır; kaynak SHA-256 önce/sonra eşitliği assert edilir.
5. **Fixture #1b** `tests/fixtures/faults/01b-schematic-label-merge/`: pcb-skill vakasının zor hali. Şematikte niyet
   olarak ayrı iki net (`/SENSE_A`, `/SENSE_B`) aynı yerel etiket adını taşıdığı için KiCad'de tek nettir; PCB şematikle
   tutarlıdır. Düz DRC **ve** parite temiz. `intent.json` niyetteki ayrı netleri ve üyelerini verir (veri, kod değil).
   README: yakalaması gereken **RD-C2 `netlist_assert` + IR niyet kıyası**; bugün hiçbir araç yakalamaz.
   Karakterizasyon testi `test_01b_parity_clean_but_intent_violated` bunu sabitler (kaçak olarak, "geçti" diye değil).

**Bitti:** dört test yeşil, S11.md düzeltildi, AGENTS.md güncellendi; RD-G2 sayacı 4/16 (#1, #1b, #9, #12; #1b
katalogda #1'in alt satırı olarak eklenir).

---

## D1-1 RD-A1 Ortak bulgu şeması

**Uygulama durumu (13 Ekim, `ip/rd-a1-bulgu`):** çekirdek 0.1.15; 15 yeni test, tam takım 274 test OK/3 skip,
gerçek KiCad 11/11 skip yok, Ruff/lisans temiz. Bağımsız denetim bekleniyor; [sonuç ve sınırlar](status.md).
Yinelenen bulgularda `#n` rapor satırını ayırır; hata kıyası temel kimlik ve Counter çokluğunu kullanır,
böylece 1→2 geçişi bir ek hata verir. Ham rapor korunur; `exclusion`/`ignore` ayrıca `raw_severity` içinde kalır.

**Dosyalar:** `pcbai/verify/__init__.py`, `pcbai/verify/findings.py`, `pcbai/verify/finding.schema.json`.
**Değişen:** [engine.py:846](../pcbai/tools/engine.py#L846) `_check_result`, [engine_metrics.py:11](../pcbai/pcb/engine_metrics.py#L11)
`finding_key`/`added_errors`, motor önizlemesindeki `new_findings`.

**Şema** (bölüm 3'teki taslağın dalga 1 alt kümesi; zorunlular kalın):

| Alan | Değer |
|---|---|
| **`finding_id`** | `"{source}:{rule_id}:{h12}"` veya çakışmada `…#n` |
| **`source`** | `erc` · `drc` · `parity` · `engine` · `calibration` · `readback` (dalga 1'de bunlar) |
| **`rule_id`** | KiCad `type` (ör. `clearance`, `net_conflict`, `pin_not_connected`); diğer kaynaklarda kendi kodu |
| **`severity`** | `error` · `warning` · `info` |
| **`confidence`** | KiCad/okuma/geri okuma için `deterministic` |
| **`evidence_source`** | `kicad` · `topology` · `geometry` · `calculation` |
| **`excluded`** | bool; KiCad `exclusion`/`ignore` veya `excluded:true` |
| **`items`** | KiCad item'ları aynen + varsa `reference`, `pin`, `net`, `sheet` |
| `position_mm` | ilk item'ın `pos`'u `[x, y]` |
| `message` | KiCad `description` (aynı alan ayrıca korunur) |
| `evidence_id` | kanıt kaydı |

- **Kimlik:** `h12` = SHA-256 ilk 12 hex; girdisi `(source, rule_id, group, sıralı item uuid'leri)`. UUID'siz item
  varsa 0,001 mm'ye yuvarlanmış `pos` eklenir. **Konum, UUID'li item'larda kimliğe girmez** (taşınan footprint
  aynı bulgudur). Aynı anahtar birden çok kez çıkarsa deterministik sıralamayla `#1`, `#2`.
- `severity` eşlemesi: KiCad `error`/`warning` aynen; `exclusion`/`ignore` → özgün severity bilinmiyorsa `warning`
  + `excluded=true`. Bilinmeyen severity bugünkü gibi `invalid_report`.
- `added_errors` kimlik karşılaştırması `finding_id` çokluğuna taşınır. **Uyumluluk testi:** mevcut motor ve PCB
  düzenleme testlerinde eski ve yeni yöntemin "eklenen hata" kümeleri aynı.
- Tool çıktısında `findings` artık normalize listedir; ham rapor zaten kanıt kaydında (`report`) durur.

**Testler:** `tests/test_verify_findings.py`
- `test_every_finding_validates_against_schema` (ERC, DRC, parite, motor örnekleri; `jsonschema`).
- `test_same_input_same_ids_real_kicad`: ecc83-pp özel kopyasında iki ayrı DRC koşusu aynı `finding_id` kümesi.
- `test_moved_item_keeps_id`, `test_duplicate_keys_get_stable_suffix`, `test_uuidless_item_uses_rounded_pos`.
- `test_added_errors_equivalence` (eski/yeni).
- `test_kicad_plugin_describe_still_renders` ([kicad_plugin/check.py](../kicad_plugin/check.py) normalize bulguyla).

**Bitti:** yukarıdakiler + mevcut ERC/DRC/motor/VS Code testleri değişmeden geçiyor.

---

## D1-2 RD-A5 Yetenek sınırları

**Dosyalar:** `docs/limits.md`, `pcbai/verify/limits.py`.

- `limits.md` tablosu: `limit_id | yapılamaz | neden | hangi ölçümle görüldü (bağlantı) | etkilenen araç/kontrol`.
- `limits.py`: `LIMITS = {limit_id: kısa metin}`; `require(limit_id)` bilinmeyen kimlikte hata verir.
- İlk satırlar (kanıtı status.md/spikes'ta olanlar): `L-IPC-NO-LIVE-SCH` (IPC'de canlı şematik yok),
  `L-UNSAVED-BUFFER` (kaydedilmemiş tampon ölçülemez), `L-RENDER-SIZE-10.0.4`, `L-SYMLINK-WINDOWS` (test yetkisi),
  `L-KH-LABEL-ALIAS` (S11: UUID kapsamı ad sanılıyor), `L-KH-PIN-MULTIPLICITY` (S11: çoklu birim pin yinelemesi),
  `L-KH-SMD-CATEGORY` (S11: connect pad SMD sayılıyor), `L-NO-INTENT-CHECK` (#1b: niyet kıyası yok, RD-C2'ye kadar).

**Testler:** `tests/test_limits.py` — `limits.py` kimlik kümesi ile `limits.md` tablosu birebir; her satırda kanıt
bağlantısı var ve hedef dosya mevcut.
**Bitti:** testler + A2 ve A4'ün `skipped` gerekçeleri yalnızca bu kimliklere başvurabiliyor.

---

## D1-3 RD-A2 `checks_run` manifesti

**Dosyalar:** `pcbai/verify/manifest.py`. **Değişen:** `_check_result`, yeni `check` aracı (engine + MCP tanımı).

**Kayıt:** `{check_id, required, status, reason, limit_id?, inputs_sha256, tool, tool_version, seconds}`
- `status`: `ran` · `skipped` · `failed` · `not_applicable`. `skipped`/`failed` için `reason` zorunlu.
- `inputs_sha256`: kontrol edilen belge baytları (ve varsa override) — kanıt kaydındaki revizyonla aynı.

**Tekil araçlar (erc, drc):** çıktıya `checks_run` eklenir; `verified` anlamı değişmez. Düz `drc` çağrısında
`{check_id: "schematic_parity", required: false, status: "skipped", reason: "not_requested"}` kaydı görünür ve
özet metni kapsamı söyler: `"DRC (parite istenmedi): 0 hata, 0 uyarı"`. Fixture #1 dersinin kullanıcıya yansıması budur.

**Yeni `check` aracı** (salt okunur, `session` + `scope`):

| scope | zorunlu kontroller |
|---|---|
| `sch` | `erc` |
| `pcb` | `drc`, `schematic_parity`, `board_stats` |
| `all` | hepsi (varsayılan) |

- Her kontrol ayrı yürür; biri çökerse diğerleri yine koşar ve çöken `failed` olur (araç hatası yutulmaz, `reason`'a
  `error.code` yazılır). Belge yoksa (`pcb` scope'ta `.kicad_pcb` yok) → `not_applicable` **değil**, `skipped`
  (`reason=document_missing`): kullanıcı scope'u istedi.
- **Yeni `verified` değerleri:** `checks_ok` (bütün zorunlular `ran`, excluded dahil sıfır bulgu) · `checks_findings`
  (bütün zorunlular `ran`, ≥1 bulgu) · `checks_incomplete` (≥1 zorunlu `skipped`/`failed`). Öncelik:
  `checks_incomplete` > `checks_findings` > `checks_ok`. `ok=true` kalır; sonuç içeriği karar verir.
- Bulgular A1 şemasında, kontrol başına ve toplam; tek kanıt kaydı (`evidence_id`) + her kontrolün kendi kaydı.

**Testler:** `tests/test_verify_manifest.py`
- `test_plain_drc_records_parity_not_requested`.
- `test_fixture12_missing_cli_is_checks_incomplete` (asla `checks_ok`; `erc` kaydı `failed`, `reason=missing_dependency`).
- `test_fixture01_scope_pcb_is_checks_findings` (parite bulgusu).
- `test_excluded_finding_blocks_checks_ok`, `test_one_check_crash_others_still_run`, `test_missing_pcb_is_skipped`.
- `test_unknown_limit_id_rejected`.
- Karakterizasyon testi `test_12_…` beklentisi bu commit'te `checks_incomplete`'e genişletilir.

**Bitti:** testler + RD-A2 plan maddesindeki ölçüt: kasıtlı atlanan kontrol çıktıda görünüyor ve "temiz" yazılmıyor.

---

## D1-4 RD-I9 `pcbai check` CLI

**Değişen:** [pcbai/__main__.py](../pcbai/__main__.py). `python -m pcbai check <proje.kicad_pro> [--scope sch|pcb|all] [--json]`.

- Yeni `check` aracını servis olmadan yerel Engine ile çağırır (bugünkü `inspect` deseni).
- **Çıkış kodu yalnızca `verified`'dan türer:** `checks_ok` → 0, `checks_findings` → 1, `checks_incomplete`,
  araç hatası, geçersiz argüman, proje bulunamadı, beklenmeyen istisna → 2. argparse'ın kendi hatası da 2 (varsayılan).
- Varsayılan çıktı kısa insan özeti (kontrol başına durum + sayı); `--json` tam araç yanıtı.

**Testler:** `tests/test_cli_check.py` (alt süreç, `shell=False`, gerçek KiCad yoksa skip)
- `test_exit0_clean_sch`: fixture #12, araç mevcut, `--scope sch`.
- `test_exit1_findings`: fixture #1, `--scope pcb`.
- `test_exit2_missing_tool`: fixture #12, ortamda eksik `PCBAI_KICAD_CLI`.
- `test_exit2_bad_project_path`, `test_json_output_parses`.

**Bitti:** üç durumun her biri için CLI testi; status.md'de PowerShell kabuk çıkışı yerine alt süreç çıkışı raporlanır.

---

## D1-5 RD-A6 Denetim kaydı

**Değişen:** [engine.py:274](../pcbai/tools/engine.py#L274) `Engine.call` (tek giriş noktası). **Dosya:** `<state>/audit.jsonl`.

- Satır başına: `time, tool, source (tool|view|job), seconds, input_bytes, output_bytes, ok, verified, error_code,
  session, document, revision_before, revision_after, evidence_id, change_id, checkpoint_id`.
- **Argüman değerleri ve dosya metni yazılmaz** (yalnızca boyut ve `inputs_sha256`); dosya metni güvenilmeyen veridir.
- Kilitli ekleme; 10 MB'ta `audit.1.jsonl`'e döner (tek yedek). Yazma hatası aracı **düşürmez**, yanıta uyarı ekler.
- Konum `state_directory`; kayıtlı proje klasörüne yazılmaz (0.1.11 durum sınırı).

**Testler:** `tests/test_audit_log.py` — her çağrı tek satır; hata yanıtı da kaydedilir; argüman değeri sızmıyor
(gizli bir değer verip dosyada aranır); döndürme; yazılamaz durum klasöründe araç yine yanıt veriyor; eşzamanlı
iki iş parçacığında satırlar bozulmuyor.
**Bitti:** testler + `evidence_id`/`change_id` kayıtla kanıt arasında çift yönlü bulunabiliyor.

---

## D1-6 RD-A4 Motor kalibrasyonu

**Dosyalar:** `pcbai/verify/calibrate.py`, `pcbai/verify/adapters/kicad_happy.py` (yalnızca JSON okuma; upstream kodu yok).

- **Yerel gerçek:** `kicad-cli sch export netlist --format kicadxml` (mevcut [engine.py:808](../pcbai/tools/engine.py#L808)
  `_netlist`) + `board_stats` CLI. SWIG/pcbnew kullanılmaz (KiCad 11'de kalkıyor).
- **Dış model girdisi:** `{components, sheet_instances, nets: {ad: [[ref, pin], …]}, footprints, pads, vias, segments}`.
  kicad-happy adaptörü bu biçime çevirir; fixture #9'un JSON'u doğrudan bu biçimdedir.
- **Karşılaştırmalar** (her biri ayrı sonuç): bileşen referans kümesi; sayfa örneği sayısı; net sayısı;
  **üye kümesi bölümlemesi** (adlardan bağımsız); **ad→üye eşlemesi** (yalnızca kullanıcı adlı netler; KiCad'in
  `Net-(…)`/`unconnected-…` ve dış motorun `__unnamed_*` adları bölümleme üzerinden eşlenir, adla değil);
  **çokluk** (tekrarlar kaldırılmadan); PCB footprint/pad/via/iz toplamları.
- Ad normalizasyonu açık ve dar: baştaki `/`, sayfa UUID öneki → KiCad sayfa yolu. Her kural testle belgelenir;
  eşleşmeyen ad sessizce "aynı" sayılmaz.
- **Çıktı:** uyuşmazlıklar `source=calibration` bulguları (A1 şeması; `rule_id` ör. `net_members_mismatch`,
  `net_name_member_swap`, `pin_multiplicity`, `count_mismatch`) + manifest kayıtları: bağımlı dedektör grupları
  `skipped(reason=calibration_failed, limit_id=…)`. Bağımlılık tablosu `calibrate.py`'de: üyelik uyuşmazlığı →
  bütün topoloji dedektörleri; yalnız çokluk → pin sayısına/akıma bağlı dedektörler (`L-KH-PIN-MULTIPLICITY`).
- Bu dalgada ürün aracı **yoktur**; `calibrate()` kütüphane fonksiyonudur ve RD-B2'de `analyze_design`'a bağlanır.

**Testler:** `tests/test_verify_calibrate.py`
- `test_fixture09_name_swap_detected` (bölümleme eşit, ad→üye ters → `net_name_member_swap`, iki net).
- `test_missing_member_fails` (bilerek bir üye eksik model → `net_members_mismatch`; plan ölçütü).
- `test_multiplicity_only_skips_pin_count_detectors` (pic_programmer biçiminde sentetik model).
- `test_unnamed_nets_matched_by_partition_not_name`, `test_count_mismatch`.
- `test_real_kicad_happy_five_demos` (yalnız `PCBAI_KICAD_HAPPY` varsa; demolar özel kopyada): S11 ile tutarlı —
  beş demoda bölümleme eşit, pic_programmer'da 19 çokluk bulgusu. Ölçülen ad seçimi farkları
  pic_programmer ve video'da ayrıca raporlanır; eşit bölümleme ad eşitliği yerine geçmez.
- KiCad 10.0.4 `board_stats` iz sayısı vermediğinden segment/arc toplamı bağımsız kaydedilmiş
  geometri okuyucusundan gelir (`count_sources.segments=saved_geometry`); diğer PCB toplamları CLI'dandır.
- Tek dosyalı kicad-happy çıktısında `sheets` yoksa yalnız açık `inputs.source_files` tek dosya bildiriyorsa
  sayfa sayısı 1 alınır; bu alanlar yoksa sayı bilinmez ve kontrol atlanır. Gerçek beş demoda sayı/üye
  kontrollerinin tamamı ayrıca doğrulandı; ad ve çokluk farkları başarı sayılmaz.
- Karakterizasyon testi `test_09_…` beklentisi kalibrasyonun yakaladığı yönünde güncellenir.

**Bitti:** testler + S11'deki iki alias yanlış pozitifinin kaynağı (UUID kapsamı) ad normalizasyonu testinde gösterilmiş.

---

## D1-7 RD-A3 Yazma sonrası bağımsız geri okuma

**Dosyalar:** `pcbai/verify/readback.py`. **Değişen:** önizleme planlayıcıları (`_plan_sch`, `_plan_pcb`, `_plan_engine`)
adaya `intent` ekler; [engine.py:859](../pcbai/tools/engine.py#L859) `_apply` yazımdan sonra geri okur.

- **Kapsam (kodda yazan bütün araçlar):** `set_value`, `add_symbol`, `connect`, `add_label`, `replace_part`,
  `add_block`, `move_footprint`, `set_track_width`, `add_zone`, `set_netclass`, `autoroute`, `autoplace`,
  **`restore_checkpoint`** (plan listesinde yoktu; o da yazar).
- **Sıra:** `atomic_write` → dosyayı **diskten yeniden oku** (aday nesnesi veya önbellek kullanılmaz) → (1) bayt
  SHA-256 = aday SHA-256 → (2) yeni ayrıştırmayla niyet ölçümü → (3) mevcut son ERC/DRC.
- **Niyet ölçümleri:**

| Araç | Ölçülen |
|---|---|
| set_value | referansın alanı = istenen metin |
| add_symbol, replace_part | referans, lib_id, konum (0,001 mm), UUID |
| add_label | ad, konum |
| connect, add_block | native netlistte beklenen üye kümeleri (kicad-cli, kaydedilmiş dosya) |
| move_footprint | konum, açı, katman |
| set_track_width | hedef UUID'lerin genişliği; diğer izler değişmemiş |
| add_zone | net, katman, köşe noktaları |
| set_netclass | netclass parametreleri ve net atamaları (proje dosyası) |
| autoroute, autoplace | SHA eşitliği + önizlemedeki iz/via/footprint sayıları |
| restore_checkpoint | SHA = checkpoint baytları |

- **Sonuç:** `readback: {checked: [...], mismatches: [...]}` her yazma yanıtında ve değişiklik kanıt kaydında.
  Uyuşmazlıkta yanıt `ok=false`, `changed=true`, `verified="readback_mismatch"`, `error.code="readback_mismatch"`,
  `checkpoint` ve önerilen `restore_checkpoint` hedefi. **Kendiliğinden geri alma ve yeniden deneme yok.**
  Uyuşmazlıklar A1 bulgusu olarak da döner (`source=readback`).
- Geri okuma ayrıştırıcısı yazıcıdan bağımsız yol izler: aynı `pcbai.sexpr` okuyucusu kullanılabilir ama planlayıcının
  ara nesneleri değil (RD-I6 bağımsız yazıcı kıyası dalga 2'de).
- `connect` niyeti önceki pin netleri ve açık kapsamlı mevcut net adından dondurulur; önizleme üyeleri
  bu bağımsız beklentiyle eşleşmezse `ambiguous_intent` ile yazım öncesi reddedilir. Böylece çözülemeyen
  mevcut etiket alias'ları sessizce beklenen üyelere eklenmez. Blok port adları da recipe/instance üzerinden ölçülür.
- Yazımdan sonra hedef kaybolursa `changed=true`, checkpoint, bulgu ve mümkünse değişiklik kanıtı korunur;
  `target=null`, `target_before` eski hedefi belirtir. Geri yükleme önizlemesi önce güncel hedefi yeniden edinmeyi gerektirir.

**Testler:** `tests/test_verify_readback.py`
- Her araç için `test_<araç>_readback_ok` ve **hata enjeksiyonlu** `test_<araç>_mismatch_detected`: `atomic_write`
  testte bozuk bayt yazacak şekilde değiştirilir (değer harfi, konum 0,01 mm, eksik üye, yanlış genişlik…).
  Beklenen: `readback_mismatch`, checkpoint var, dosya bozuk haliyle kalmış, otomatik geri alma yok.
- `test_sha_ok_but_intent_wrong` (aday kendisi yanlışsa da yakalanır: niyet ölçümü SHA'dan bağımsız).
- Gerçek KiCad ile `connect` ve `add_block` için native netlist geri okuması (kurulu değilse skip).
- **Fixture #13** `tests/fixtures/faults/13-written-value-differs/` (README + küçük şematik); enjeksiyon testi bu
  fixture üzerinde. RD-G2 sayacı 5/16.

**Bitti:** plan RD-A3 ölçütü — her yazma aracında hata enjeksiyonlu test uyuşmazlığı yakalıyor.

---

## 3. Dalga sonu kabulü

- Tam takım `.venv` ile yeşil; gerçek KiCad entegrasyonu skip'siz; Ruff ve lisans denetimi temiz.
- Hata kataloğu durumu (plan bölüm 5 "Bugün" sütunu güncellenir):
  - **#1** `pcbai check --scope pcb` → exit 1 (parite); #1b bilinen kaçak, `L-NO-INTENT-CHECK`.
  - **#9** kalibrasyon `net_name_member_swap` yakalar.
  - **#12** `check` → `checks_incomplete`, CLI exit 2.
  - **#13** geri okuma `readback_mismatch` yakalar.
- Kıyas yeniden koşulur (plan bölüm 7 "kapsam şişmesi" önlemi): R7 beş demo tablosunda gerileme yok.
- status.md'ye dalga özeti, plan-referans-depolar.md'de A1–A6 ve I9 işaretleri.

## 4. Claude denetiminde bakılacaklar (paket başına)

- Testleri `.venv` ile kendim koşarım; gerçek KiCad testlerini ayrıca.
- A1: iki koşu kimlik eşitliğini farklı geçici dizinle de denerim (dizin yolu kimliğe sızıyor mu).
- A2: bir kontrolü elle bozup (`PCBAI_KICAD_CLI`, kilitli dosya) `checks_ok` çıkıp çıkmadığına bakarım.
- I9: çıkış kodlarını PowerShell'den değil alt süreçten okurum.
- A4: fixture #9'u ad anahtarını atan bir "kolay" karşılaştırmaya karşı denerim; bölümleme eşitliğinin yetmediğini görmeliyim.
- A3: her araç için kendi bozma senaryomu yazarım (scratchpad'de); planlayıcının ara nesnesine güvenen geri okuma bulgu sayılır.
- A6: denetim kaydında dosya metni veya argüman değeri arar, bulursam bulgu.

## 5. Açık noktalar

- `checks_incomplete`'in VS Code ve KiCad eklentisinde nasıl gösterileceği İP-6.5'e kadar yalnız özet metniyle olur.
- `readback_mismatch`'te `ok=false` + `changed=true` sözleşmede yeni bir birleşimdir; MCP istemci talimatı
  ([mcp_server/pcbai_mcp.py](../mcp_server/pcbai_mcp.py)) "değişiklik kaydedildi ama doğrulanamadı; checkpoint'i öner" diye güncellenmeli.
- Takvim sıkışık (bölüm 1); 30 Ekim'de ilerleme kontrolü, gerekirse A6 dalga 2'ye.
