# EK-0 — kaynak ve uyumluluk incelemesi

13 Ekim 2026; başlangıç `main/2cd413a`, çekirdek 0.1.22, eklenti 0.1.16.
Bu paket kaynak metadatasını **veri** olarak okur; upstream uygulama kodu alınmadı,
dört eklenti kurulmadı. Deneyler özel demo kopyaları ve özel durum dizininde yapıldı.

## Sabit kaynak matrisi

| Kaynak / sabit commit | Lisans | Manifest alt sınırı | Biçim / bağımlılık | Karar |
|---|---|---|---|---|
| [Cimos/vscode-kicad-dru](https://github.com/Cimos/vscode-kicad-dru/tree/04da401cb4e448319ecc2a6834a63a4ab4a1d7a7) `04da401` | MIT, metin kaydedildi | ^1.80.0 | .kicad_dru; statik JSON, runtime bağımlılığı yok | EK-1 özgün grammar/snippets/configuration; doğrulayıcı iddiası yok |
| [ashergarland/skidl-vscode](https://github.com/ashergarland/skidl-vscode/tree/c9b1c0bb735ba0e8584354bd41bcf8e7c62f5dfe) `c9b1c0b` | MIT, metin kaydedildi | ^1.101.0 | SKiDL Python, vscode-languageclient ^9.0.1; Python LSP/MCP bağımlılıkları | Fikir alınır; SKiDL/LSP kurulmaz; mevcut PcbAi IR/parça araçları kullanılır |
| [lukas-lang/kicad-viewer](https://github.com/lukas-lang/kicad-viewer/tree/f74a30e24185341c056032249b142cd1a354b65b) `f74a30e` | LICENSE.md MIT; manifest lisans alanı yok | ^1.129.0 | .kicad_sch/.kicad_pcb, KiCad CLI SVG; custom diff API | EK-3 kendi webview'ı; minimum sürüm artırılmaz |
| [Argmaster/vscode-gerber-format-support](https://github.com/Argmaster/vscode-gerber-format-support/tree/93c1417243134b84f825c1f6f0b0275e02264bbf) `93c1417` | MIT, metin kaydedildi | ^1.90.0 | Gerber X2/X3; fs-extra, ovsx, semver, languageclient, textdocument, Python extension | EK-4 özgün panel; global Python/eklenti kurulumu yok |
| [Argmaster/pygerber](https://github.com/Argmaster/pygerber/tree/5446d44d424897e1b1a68c48c160ed9b4e828f44) `5446d44` | MIT, metin kaydedildi | Python ^3.8 | Git main 3.0.0a4; API stable PyPI sürümüyle aynı değil | Deneyde PyPI **2.4.3** sabitlendi; ileride API sürümü açık seçilmeli |

PyPI 2.4.3 metadata: Python >=3.8,<4; click, pyparsing, pydantic, Pillow, numpy;
SVG için drawsvg, LSP için lsprotocol/pygls optional extras. Deney yalnız özel
`pygerber-env` ortamında core paketle yapıldı. Ürün bağımlılığı eklenmedi;
SVG/LSP extras zincirinin lisans ve uyumluluk kabulü EK-4/5'te ayrıca gerekir.
Kaynak manifest/lisans dosyalarının SHA-256'ları `sources.json` içindedir;
bu inceleme vendoring veya bağımlılık zincirinin yayın lisans kabulü değildir.

## PcbAi API ve paketleme kararı

- Minimum manifest `^1.90.0` korunur. EK-1 statik `languages`, `grammars`,
  `snippets` katkıları; EK-2 stable completion/hover provider, MarkdownString
  `appendText`, URI/version/cancellation ve yerel `jsonValidation` kullanır.
  Custom diff provider API kullanılmaz; EK-3 mevcut webview'dan ilerler.
- Kurulu VS Code **1.141.0**, package.json'dan okundu. Gerçek kurulu Host
  girişimi `vscode-updating` mutex nedeniyle **çalıştırılamadı**; kabul sayılmaz.
  Resmî arşiv metadata SHA-256'sı doğrulanmış, yalıtılmış **1.90.2 portable
  gerçek Extension Host** eklentiyi açtı; iki provider API'si ve appendText
  doğrulandı (`host-result.json`, `portable-code-source.json`). Dil/IR kabulü
  bu API keşif deneyiyle tamamlanmış sayılmaz.
- Paketleyici sabit JS listesi+media dizini kullanıyor: EK-1 dil dosyaları,
  EK-2 part_assist ve IR schema özellikle VSIX'e eklenmeli. ZIP içerik denetimi
  ve paketten açılan yalıtılmış gerçek Host kabulü teslimlerin parçasıdır.
- IR alanı `parts[].symbol`; araç `lib_id` alanına eşlenir. Yeni arama UI ve
  adaptör yapılır; mevcut panel varsayılmaz. Seçici `*.pcbai-ir.json` ve
  `*.pcbai.json`; genel JSON dosyası servis çağrısı başlatmaz.
- Buffer veri sınırları, kısmi JSON string bağlamı, literal 01/1 ve ortak/çok
  birimli pinler; eski URI/version/session/revision yanıtı reddi; SHA yenileme;
  düz metin, trusted=false/supportHtml=false hover kabul testlerine girer.
- 150 ms sıcak hedefi henüz karşılanmış değildir: mevcut full-library
  hash/search ön ölçümü 299–321 ms. Doğrudan indeks sorgusu ve gerçek Host
  latency'si ayrı raporlanır; güncellik denetimi performans için gevşetilmez.

## Özel kabul korpusu ve gerçek PyGerber deneyi

KiCad CLI **10.0.4**, `.venv` Python **3.11.5**. R7'nin beş demosu
ecc83/interf_u/pic_programmer/stickhub/video ve complex_hierarchy özel kopyalara
alındı. Alt süreçlerde shell=False, timeout 45 s; gerçek export_fab yalnız
bu kopyalarda yürüdü; export öncesi/sonrası revizyon eşitliği altı projede geçti.

| Girdi | PyGerber 2.4.3 / strict Raise sonucu |
|---|---|
| ecc83, interf_u, pic_programmer, stickhub | Her biri 7 Gerber parse+bbox; 1 Excellon skipped |
| video | 9 Gerber parse+bbox; 1 Excellon skipped |
| complex_hierarchy | 7 Gerber parse+bbox; 1 Excellon skipped; hiyerarşik şematikler strict PcbAi parse |
| küçük mm / inch | İki fixture parse+bbox |
| yay + negatif polarity | Fixture parse+bbox; görüntü/doğruluk kalibrasyonu değildir |
| bilerek bozuk Gerber | Rejected |

Toplam **44 gerçek Gerber parse+bbox**, **6 Excellon skipped**. Pinned API'de
Excellon API yok; Gerber parserına drill girdisi verme deneyi destek kanıtı
sayılmadı. Default parse davranışı hatayı ignore edebildiğinden ileride adaptör
`OnParserErrorEnum.Raise` kullanmalı. Raster/SVG render, PyGerber SVG'nin mevcut
güvenlik filtresinden geçmesi, aperture/flash/yay sayımı ve iki okuyucu kalibrasyonu
bu spike'ta ölçülmedi; RD-C2/I2 ve EK-4/5 kapanmadı.

Geliştirme kanıtları `.pcbai-state/eklenti-ozellikleri/`: sources/source-summary,
pypi-summary, pygerber-install, corpus-result/corpus-log ve host-log.
Yayın `*-result.json` dosyası yazılmadı. Yeni ürün kodu yok; çekirdek/eklenti
sürümü değişmedi. Plan denetimindeki snapshot bütçe boşluğu ayrı RD-B8s ile
tanımlandı; süresi henüz tahminlenmedi.
