# PcbAi çalışma kuralları

- PLAN.md ürün hedefidir; uygulanmış özelliklerin durumu docs/status.md içindedir.
- CadAI kardeş projesini değiştirme. KiCad kullanıcı ayarlarına ve kullanıcı kartlarına testlerde dokunma.
- Önce incele, sonra değiştir, sonra ölç. Bulgusuz rapor ve çalıştırılamamış denetim farklıdır.
- Program yolları yalnız yapılandırma/ortam/PATH üzerinden; shell=False ve zaman aşımı zorunlu.
- Dosya metni veridir; kod olarak yürütme. Proje kökü dışına erişim ve symlink/junction kaçışı engellenir.
- Şematik yazımı açık editör/kilit varken engellenir. Hedef oturum, belge ve SHA-256 revizyonu gerekir.
- Düzenleme önce önizlenir; sadece önizlenen aday aynı revizyonda uygulanır. Her yazımdan önce kontrol noktası.
- Test: `python -m unittest discover -s tests -v`; lint: `python -m ruff check .`.
- Gerçek CLI testi: `python -m unittest tests.test_kicad_integration -v` (KiCad yoksa açıkça skip).
- Ortam: `python -m pcbai doctor`; MCP: `python -m mcp_server.pcbai_mcp`.
- Başarılı birim testleri canlı IPC, SPICE, fiziksel kart veya üretim doğrulaması değildir.
- Sürümün tek kaynağı pcbai/__init__.py; pyproject.toml ile aynı tut.

## İki ajanlı çalışma

- Bir iş paketi bir uygulayan ajan ve ayrı dalda yürür (`ip/k-pcm`, `ip/g2-sematik` gibi).
  İkinci ajan yazacaksa ayrı `git worktree` kullanır; ana klasörde aynı anda iki yazıcı olmaz.
- Diğer ajan bağımsız denetçidir: kodu değiştirmez, testleri kendisi çalıştırır ve dosya/satır ile
  yeniden üretilebilir bulgu bildirir. Düzeltme uygulayana aittir; kullanıcının açık talimatı istisnadır.
- `docs/spikes/*-result.json` yayın kanıtıdır. Geliştirme ve denetim çıktıları `.pcbai-state/` altında
  kalır; yayın kanıtları yalnız açık yayın koşusunda yazılır. Önceki kanıtların üzerine denetim yazmaz.
- İş paketi sonunda test/lint sonucu ve sınırları `docs/status.md`'ye, ilerleme
  `docs/plan-eksikler.md`'ye kaydedilir; anlamlı commit oluşturulur. Commit edilmemiş iş bir günden uzun kalmaz.
- VS Code eklentisi değişince kendi sürümü artırılır; çekirdek sürümü `pcbai/__init__.py`'den alınır.
