"""Render measured S11 development evidence and the implementer's manual labels."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.spike_kicad_happy import hashes  # noqa: E402


def main():
    work = ROOT / ".pcbai-state/s11"
    result = json.loads((work / "result.json").read_text(encoding="utf-8"))
    labels = json.loads((work / "manual-review.json").read_text(encoding="utf-8"))
    for item in labels:
        result["manual_sample"][item["index"] - 1].update(label=item["label"], reason=item["reason"])
    result["manual_review_counts"] = dict(Counter(x["label"] for x in labels))
    for record in result["records"]:
        source = Path(result["cli"]).parent.parent / "share/kicad/demos" / record["demo"]
        record["source_final"] = hashes(source)
        record["source_preserved"] = record["source_before"] == record["source_after"] == record["source_final"]
        if not record["source_preserved"]:
            raise RuntimeError("Demo source changed: " + record["demo"])
    (work / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# S11 — kicad-happy salt okunur ölçümü", "",
        "13 Ekim 2026 · RD-B1 · uygulayan ölçümü; bağımsız Claude denetimi bekleniyor.", "",
        f"Upstream: `aklofas/kicad-happy`, commit `{result['commit']}` (detached HEAD); MIT.",
        f"Lisans SHA-256: `{result['license_sha256']}`.",
        f"KiCad CLI **{result['cli_version']}**, KiCad Python **{result['python_version']}**.", "",
        "Klon `.pcbai-state/s11/kicad-happy` altında. PcbAi paketine upstream kodu, şema veya şablon alınmadı.",
        "Her analiz KiCad Python ile `-I -X utf8`, `shell=False`, 120 saniye timeout ve klon dışındaki",
        "özel geçici demo kopyasında çalıştı. Çıktılar stdout dosyasına; hata akışları ayrı dosyalara kaydedildi.",
        "`--lifecycle` kullanılmadı; ağdan katalog/distribütör verisi indirilmedi. Kullanıcı ayarları CLI'de",
        "PcbAi'nin mevcut özel yapılandırma kopyasıyla korunur. Beş demo klasörünün bütün dosyalarında önce/sonra/son",
        "SHA-256 eşit; kaynak hash haritaları sonuç JSON'unda. Kaynaklar değiştirilmedi.", "",
        "Kanıt: [geliştirme JSON'u](../../.pcbai-state/s11/result.json),",
        "[koşu](../../.pcbai-state/s11/run.txt), [kalibrasyon](../../.pcbai-state/s11/calibration-corrected-run.txt).",
        "`docs/spikes/S11-result.json` yazılmadı; bu bir yayın koşusu değildir.", "",
        "Yeniden üretim (depo kökünde, program yolları yapılandırma/ortam/PATH üzerinden):", "",
        "```text", "python scripts/spike_kicad_happy.py", "python scripts/summarize_s11.py",
        "python scripts/report_s11.py", "python scripts/measure_fault_fixtures.py", "```", "",
        "Klon commit'i raporlanan SHA'ya `git checkout --detach <SHA>` ile sabitlenmelidir. Elle etiketler",
        "`.pcbai-state/s11/manual-review.json` içindedir; aşağıdaki tablo aynı gerekçeleri kalıcı olarak içerir.", "",
        "## Süre, bellek, determinizm", "",
        "20/20 analiz exit 0; timeout yok. Peak bellek Windows GetProcessMemoryInfo **PeakWorkingSetSize**:",
        "yalnız analiz sürecinin tepe çalışma kümesi, süreç ağacının toplamı veya Python heap'i değil.",
        "İlk koşu/ikinci koşu süreleri soğuk/sıcak cache ve eşzamanlı test yükünü içerebilir; performans garantisi değildir.", "",
        "| Demo | Analiz | Süre 1/2 (sn) | Peak 1/2 (MiB) | Bulgu | ID kümesi / liste / çıktı baytı eşit |",
        "|---|---|---|---|---|---|",
    ]
    for record in result["records"]:
        for kind in ("schematic", "pcb"):
            runs = [r for r in record["runs"] if r["kind"] == kind]
            det = record["determinism"][kind]
            lines.append(f"| {record['demo']} | {kind} | {runs[0]['seconds']:.3f}/{runs[1]['seconds']:.3f} | "
                         f"{runs[0]['peak_working_set_bytes']/1048576:.2f}/{runs[1]['peak_working_set_bytes']/1048576:.2f} | "
                         f"{runs[0]['findings']} | {' / '.join('evet' if x else 'hayır' for x in det.values())} |")
    lines += ["", "İki tekrarın her biri aynı geçici girdi yolu ve aynı baytları kullandı. Upstream cwd altında",
              "`analysis/capability_mode.json` oluşturuyor; iki tekrar bu özel geçici çalışma bağlamını paylaşıyor.",
              "Ham çıktı eşitliği aynı provenance bağlamındadır; yeni/boş cache bağlamında ölçülmedi.",
              "Bu ölçüm farklı dizin,",
              "Python sürümü veya işletim sistemi arasında ID kararlılığı kanıtı değildir.", "",
              "| Demo / analiz / tekrar | Çıktı SHA-256 |", "|---|---|"]
    for record in result["records"]:
        for r in record["runs"]:
            lines.append(f"| {record['demo']} / {r['kind']} / {r['repetition']} | `{r['output_sha256']}` |")
    lines += ["", "## Kalibrasyon", "",
              "Şematik oracle: gerçek `kicad-cli sch export netlist --format kicadxml`. Bileşen referansları",
              "ve sayfa **örnekleri** karşılaştırıldı; sadece fiziksel dosya sayısı kabul edilmedi. KiCad'in",
              "netliste çıkarmadığı grafik güç/#FLG sembolleri üye kıyasından açıkça ayrılır (referans listesi JSON'da).",
              "Adsız ağ ve hiyerarşi adları korunur; ad eşitliği ve pin üyeliği ayrı raporlanır.", "",
              "| Demo | Bileşen dış/KiCad | Sayfa örneği dış/KiCad | Net dış/KiCad | Üye listesi birebir | Üye kümesi birebir | Farklı ad, üyeler aynı |",
              "|---|---|---|---|---|---|---|"]
    for record in result["records"]:
        c = record["calibration"]
        lines.append(f"| {record['demo']} | {'/'.join(map(str,c['components']))} | {'/'.join(map(str,c['sheets']))} | "
                     f"{'/'.join(map(str,c['nets']))} | {'evet' if c['net_members_equal'] else 'hayır'} | "
                     f"{'evet' if c['net_member_sets_equal'] else 'hayır'} | {len(c['net_name_differences'])} |")
    lines += ["", "Bütün bileşen referans kümeleri eşit. **pic_programmer 19 ağda pinleri yineliyor**:",
              "KiCad listesi ile çokluk korunan liste birebir değil; tekrarlar kaldırılınca beş demoda da",
              "bağlantı kümeleri eşit. Bu, farklı fiziksel bağlantı bulunduğu iddiası değildir; çoklu birim",
              "temsili normalize edilmeden pin sayısı/akıma bağlı dedektör kabulü verilemez.", "",
              "| pic_programmer dış ağ adı | Yinelenen gerçek pin ve dış çokluğu (KiCad'de 1) |", "|---|---|"]
    pic = json.loads((work / "pic_programmer-schematic-1.json").read_text(encoding="utf-8"))
    for name, net in pic["nets"].items():
        counts = Counter((p["component"], p["pin_number"]) for p in net["pins"] if not p["component"].startswith("#"))
        duplicates = [f"{r}.{p} ×{count}" for (r, p), count in counts.items() if count > 1]
        if duplicates:
            lines.append(f"| `{name}` | {', '.join(duplicates)} |")
    lines += ["", "Ad farkı örnekleri: ecc83 `__unnamed_0` yerine KiCad `Net-(U1A-G)`; stickhub `U1D+`",
              "yerine `/U1D+`; video UUID kapsamı yerine KiCad'in sayfa adı kapsamı. 901 eşleşmiş ağda ad farkı",
              "var; 19 yinelenen ağın ad eşlemesi yalnız küme üzerinden ayrıca gerekir. Ham ad farkı detayları JSON'da.", "",
              "PCB oracle: gerçek `board_stats` CLI + ayrı KiCad Python `pcbnew` okuması.",
              "`statistics.track_segments` upstream'de yayları da içerir; `tracks.segment_count` düz izdir.",
              "İlk oracle yanlışlıkla via'ları PCB_TRACK alt sınıfı olarak saydı. Düzeltildi; ilk log",
              "`calibration-run.txt`, düzeltilmiş log ve oracle JSON'ları ayrı tutuldu. İlk fark motor kusuru sayılmadı.", "",
              "| Demo | Footprint | Pad | Düz iz | Yay | Via | Zone | PCB net | Boyut mm |",
              "|---|---|---|---|---|---|---|---|---|"]
    for record in result["records"]:
        p = record["calibration"]["pcb_counts"]
        lines.append(f"| {record['demo']} | {p['footprints'][0]} | {p['pads'][0]} | {p['straight_segments'][0]} | "
                     f"{p['arcs'][0]} | {p['vias'][0]} | {p['zones'][0]} | {p['nets'][0]} | "
                     f"{p['width_mm'][0]}×{p['height_mm'][0]} |")
    lines += ["", "Tablodaki tüm toplamlar eşit. CLI pad/via kategori toplamları ve footprint ön/arka toplamları da eşit.",
              "**SMD kategori farkı:** video dış 144 / CLI 143; interf_u dış 1 / CLI 0. İkisinde de `BUS1`,",
              "`attr smd` taşımayan `pad ... connect rect` kenar konnektörüdür; upstream bunu SMD sayıyor, CLI",
              "belirtilmemiş sayıyor. THT toplamları eşit. Katman kullanım sayısı, kurulu bakır katman sayısı",
              "ve bounding-box alanı aynı tanım değildir; polygon alanı, delik grupları ve bütün geometri",
              "üretim kabulü olarak kalibre edilmedi. CLI stats'ın tam dökümü JSON'dadır.", "",
              "## Dedektör ve confidence dağılımı", "",
              "Tek tekrar üzerinden **474 bulgu**: şematik 225, PCB 249; **439 deterministic, 35 heuristic,",
              "0 datasheet-backed**. Tekrarlar aynı bulguları iki kere saymaz. Etiketler upstream beyanıdır;",
              "deterministic etiketi fiziksel doğruluk veya üretici kanıtı değildir. Sıfır bulgulu dedektörün",
              "çalıştığı/atlandığı bu sayaçlardan çıkarılamaz.", "",
              "| Dedektör | Şematik bulgu | PCB bulgu |", "|---|---|---|"]
    counters = {k: Counter() for k in ("schematic", "pcb")}
    for record in result["records"]:
        for r in record["runs"]:
            if r["repetition"] == 1:
                counters[r["kind"]].update(r["detectors"])
    for detector in sorted(set(counters["schematic"]) | set(counters["pcb"])):
        lines.append(f"| `{detector}` | {counters['schematic'][detector]} | {counters['pcb'][detector]} |")
    lines += ["", "Demo/analiz başına confidence ve dedektör ayrıntısı `result.json` içindedir.", "",
              "## 20 bulgunun elle dosya incelemesi", "",
              "Tohum **11013**; nüfus tek tekrardaki 474 bulgu; `(demo, kind, finding_id)` ile sıralı nüfustan",
              "Python 3.11 `random.Random(11013).sample(..., 20)`, değiştirmesiz seçim. Örnek seçimi sonradan ayıklanmadı.",
              "Uygulayan kaynak `.kicad_sch`/`.kicad_pcb` alanlarını, literal değerleri, etiketleri ve koordinatları",
              "okudu; bağlantılarda KiCad netlisti, D25'te bağımsız filled-polygon Contains ölçümü yardımcı kanıttır.",
              "Bu bağımsız ajan denetimi veya donanım testi değildir. Doğru etiketi satırdaki sınırlı dosya iddiasınadır.", "",
              "| # | Demo / analiz / finding_id | Etiket | Gerekçe ve kaynak alanı |", "|---|---|---|---|"]
    for i, sample in enumerate(result["manual_sample"], 1):
        lines.append(f"| {i} | {sample['demo']} / {sample['kind']} / `{sample['finding']['finding_id']}` | "
                     f"{sample['label']} | {sample['reason']} |")
    lines += ["", "**14 doğru, 2 yanlış, 4 belirsiz.** Gözlenen yanlış oranı 2/20=%10; belirsizleri çıkarınca",
              "2/16=%12,5. Küçük ve CP-002 ağırlıklı bu örnek tüm dedektörlere genellenmez. İki yanlış,",
              "`detect_label_aliases` UUID kapsamını farklı ad gibi sunmasından kaynaklanıyor.", "",
              "## Sınırlar ve K16 önerisi", "",
              "Ölçülenler: kurulu beş R7 demosu, varsayılan şematik/PCB analizleri, iki tekrar, Windows süreç belleği,",
              "native netlist üyeleri ve PCB sayımları. Dosyalar KiCad 10.0.4 ile okunmuştur; demoların çoğu",
              "eski generator/file-version taşır. Bu bütün KiCad 10 özelliklerinin veya yeni hiyerarşi örneklerinin kabulü değildir.",
              "Çevrimdışı default analiz lifecycle kontrolünü atladığını ayrıca bulgu olarak bildirir; datasheet/",
              "termal/EMC/SPICE/cross/fab motorları, başarısızlık izolasyonu, gerçek üretim ve donanım ölçülmedi.", "",
              "**K16 için öneri: sabit commit ile ayrı süreçte kalın; şimdilik vendor almayın.** 20/20 çalışabilirlik",
              "ve 10/10 tekrar determinismi olumlu; buna rağmen pin çokluğu, kategori tanımı ve alias yanlışları",
              "adaptör + RD-A4 kalibrasyonu gerektiriyor. Karar kullanıcıya aittir, burada entegrasyon kararı uygulanmadı.",
              "İlk seçili adaylar: `detect_protection_devices`, `audit_esd_protection` (yalnız sembol/topoloji iddiası),",
              "`analyze_current_capacity` (yalnız ölçülen iz geometrisi), `analyze_placement` (avlu/outline",
              "yaklaşımları ve belirsiz niyet açıkça belirtilerek). Bunlar hâlâ üretici/elektriksel yeterlilik kabulü değildir.",
              "`detect_label_aliases` kabul dışı; `detect_rc_filters`, derating/DFM/thermal ve çoklu birimli pin sayısına",
              "bağlı kurallar kalibrasyon/alan kanıtı gelmeden güven kapısından geçmemeli. `analyze_copper_presence`",
              "yalnız ilgili karşı katmandaki **zone** iddiasıyla sunulabilir; iç düzlemler veya pad/iz bakırı hakkında",
              "geniş bir yokluk iddiasına dönüşmemeli.", ""]
    (ROOT / "docs/spikes/S11.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
