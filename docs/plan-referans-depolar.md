# Plan — referans depolardan gelen geliştirmeler

Tarih: 12 Ekim 2026 · Durum: **plan, uygulanmadı** · Bağlı: [plan-eksikler.md](plan-eksikler.md), [status.md](status.md)

Sekiz açık kaynak depo README düzeyinde incelendi (kod okunmadı; iddialar depoların kendi anlatımıdır).
Amaç: fikir ve yöntem almak. **Kod kopyalanmaz** — ilk iki depo ticari kullanıma kapalı lisanslı.

## 1. İncelenen depolar

| Depo | Ne | Lisans | Kullanım |
|---|---|---|---|
| aklofas/kicad-happy | KiCad için 11 skill; saf Python şematik/PCB/Gerber ayrıştırma, güç ağacı, EMC (44 kural), SPICE, fab çıkış kapısı | MIT | **En yakın eşleşme.** Fikir + gerekirse kod |
| salitronic/eda-agent | Altium/KiCad/EasyEDA MCP; toplu işlem, 31 kontrollük lint, `minimal` mod (`tool_catalog`+`tool_invoke`), doctor | Apache-2.0 | Araç yüzeyi tasarımı |
| zhoushoujianwork/easyeda-agent | Tipli eylemler, yazma öncesi guard + yazma sonrası readback, katmanlı kontrol, belgelenmiş yetenek sınırları | MIT | Güvenlik deseni |
| daishuge/pcb-skill | Fikirden siparişe kapılı akış; salt okunur karşıt inceleme, bağımsız Gerber doğrulama, ödeme insanda | MIT | Kapı + inceleme protokolü |
| Shaurya-Sethi/circuitron | Planla → onay → SKiDL üret → ERC döngüsü; kütüphaneye karşı halüsinasyon kontrolü (arşivlenmiş) | MIT | Plan onayı, uydurma-API kontrolü |
| autonomous-ai/openharness | Ajanı sarmadan çoklu ajan yönetimi, oturum başına worktree, `harness.json` alan paketi | MIT | Orkestrasyon (Faz 7) |
| Zane456/PCB-Agent-Teams | 10 skill, kapı + rollback, MPN yalnız distribütör API'sinden, çift doğrulama, `USER.md` profili | PolyForm NC | **Yalnız fikir** |
| assalas/pcb-designer-ai-agent | Gereksinim→BOM→netlist→footprint→.kicad_pcb, JSON-RPC, datasheet'ten footprint ölçüm seti | Özel (ticari yasak) | **Yalnız fikir** |

## 2. Geliştirme paketleri (öncelik sırasıyla)

Her paket: Codex uygular, Claude denetler; bitince ölçülen sonuç status.md'ye, burada işaret.

- [ ] **D-1 `checks_run` manifesti** (kicad-happy). Her ERC/DRC/analiz çıktısı hangi kontrolün çalıştığını,
  hangisinin atlandığını ve nedenini JSON'da listeler. Atlanan kontrol "temiz" sayılmaz.
  **Bitti:** testte kasıtlı atlanan kontrol çıktıda görünüyor; araç özetinde "temiz" yalnız tüm kontroller çalıştıysa.
- [ ] **D-2 Yazma guard'ı + readback** (easyeda-agent). Her yazma araçı önce hedef proje/sayfa/UUID'yi doğrular,
  yazdıktan sonra değeri geri okuyup ölçer; uyuşmazlıkta durur, körlemesine yeniden denemez.
  Mevcut preview/apply/checkpoint üstüne eklenir. **Bitti:** sahte uyuşmazlık enjekte eden test apply'ı durduruyor.
- [ ] **D-3 Güç ağacı + alt devre tespiti + şematik lint** (kicad-happy, eda-agent). Salt okunur `analyze_power_tree`,
  `lint_schematic` (açık pin, köprüsüz güç netleri, eksik decoupling, ESD…). **Bitti:** 5 KiCad demosunda
  çalışıyor, bulgular kaynak öğe UUID'siyle; yanlış pozitif oranı ölçülüp yazıldı.
- [ ] **D-4 Datasheet kaynak kapısı** (Zane456, kicad-happy, eda-agent fikri). Parça değeri/pin/footprint verisi
  modelin hafızasından değil, `pcbai/parts` içindeki doğrulanmış kaynaktan gelir; bulgu "datasheet-backed" etiketini
  yalnız doğrulanmış çıkarımdan alır. **Bitti:** kaynaksız MPN/pin ataması reddediliyor (test).
- [ ] **D-5 Üretim öncesi kapı** (kicad-happy "release gate", pcb-skill). Gerber/delik/BOM/CPL çıktısını **üretici araçtan
  bağımsız** ayrıştırıp kart ölçüsü, katman, delik sayısı, ağ sayısı ile karşılaştırır. Satın alma BOM'u ile montaj BOM'u ayrı.
  **Bitti:** bozuk çıktıyı (eksik katman, kaymış delik) yakalayan negatif testler.
- [ ] **D-6 Salt okunur karşıt inceleme** (pcb-skill). Her faz sonunda ikinci ajan yalnız okuyarak inceler;
  durma kriteri faz başlamadan yazılır. Mevcut ikiz protokolüyle birleşir. **Bitti:** AGENTS.md'de kural + bir fazda uygulanmış kayıt.
- [ ] **D-7 Araç yüzeyi: toplu işlem + `minimal` mod** (eda-agent). `batch` aracı (tek turda çoklu düzenleme, tek checkpoint),
  tek çağrıda okuma özeti (`design_review_snapshot`), istemci araç limiti için `tool_catalog`+`tool_invoke` modu;
  aynı tekil aracı tekrar çağıran modele yanıtta toplu alternatif ipucu. **Bitti:** araç sayısı ölçümü + tur sayısı karşılaştırması.
- [ ] **D-8 Yetenek sınırları belgesi** (easyeda-agent). `docs/tools.md`'ye "yapılamaz ve neden" bölümü
  (ör. IPC'de undo yok, kaydedilmemiş değişiklik ölçümü). **Bitti:** her sınır ölçüm/kaynakla bağlı.
- [ ] **D-9 Plan onayı + uydurma-API kontrolü** (circuitron). Şematik yazma işi önce plan olarak gösterilir, kullanıcı onayı
  sonrası uygulanır; üretilen sembol/footprint/kütüphane adları gerçek kütüphaneye karşı doğrulanır. **Bitti:** var olmayan sembol adı reddediliyor.
- [ ] **D-10 Katmanlı regresyon** (kicad-happy). Mevcut testlere çıktı taban çizgisi (golden JSON, deterministik) ve sabit
  beklenti katmanı eklenir; CI'da sürüklenme kontrolü. **Bitti:** taban çizgisi bozulunca test kırılıyor.
- [ ] **D-11 Kullanıcı profili `USER.md`** (Zane456). Bölge, üretici, elle/oven lehim, stok kısıtları; parça önerisi bunlara göre süzülür.
- [ ] **D-12 Orkestrasyon** (openharness; Faz 7). Paralel ajanlar için oturum başına git worktree, ajanı sarmadan
  transcript/hook okuma. Önce yalnız araştırma spike'ı.
- [ ] **D-13 Datasheet footprint benchmark** (assalas "Reef"). PDF'ten footprint parametresi çıkarma doğruluğunu ölçen
  küçük, etiketli set; model/yöntem seçimi bu ölçüme dayanır.

## 3. Kurallar ve riskler

- Lisans: PolyForm NC ve özel lisanslı depolardan **kod, metin, şablon alınmaz**; yalnız genel fikir. MIT/Apache kodu
  alınırsa NOTICE'e yazılır (LGPL-2.1+ ile uyum önceden kontrol edilir).
- İncelenen README'ler iddiadır; her fikir PcbAi'de **ölçülerek** kabul edilir. Depolarda doğrulanmamış model adları var.
- Ödeme/sipariş adımları ajana verilmez (pcb-skill ilkesi); mevcut "yalnız preview, uygulama açık onayla" çizgisi korunur.
- Kapsam: D-1…D-5 mevcut Faz 5 (DFM/üretim) ve doğrulama işini besler; D-12 Faz 7'dir. Şimdiki R1/R2 motor kabulünün önüne geçmez.

## 4. Önerilen sıra

D-1 → D-2 → D-3 → D-5 → D-4 → D-7 → D-10 → D-6/D-8/D-9 → D-11 → D-13 → D-12.
Gerekçe: önce "yeşil yalan söylemesin" (D-1/D-2), sonra yeni analiz değeri (D-3/D-5).

## 5. Sonraki adım

Uygulamadan önce kicad-happy ve eda-agent'ın **kaynak kodu** (README değil) okunup D-1/D-3/D-7 için spike yazılır
(`docs/spikes/`), lisans ve yeniden kullanılabilirlik ölçülür.
