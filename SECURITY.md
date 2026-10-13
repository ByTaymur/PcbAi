# Güvenlik sınırları

Servis sadece 127.0.0.1'e bağlanır. Her HTTP çağrısında rastgele Bearer belirteci gerekir;
Origin başlığı taşıyan tarayıcı çağrıları reddedilir. Kimlik dosyası kullanıcıya özel ACL/0600 ile korunur.
CLI ile kaydedilen projeler dışında ajan yeni proje yolu açamaz. Araç argümanı yürütülebilir program seçemez.

Dosya modu kaydedilmiş dosyaları görür. KiCad kilidi varken düzenleme engellenir;
Canlı PCB tamponu ve seçim ayrı salt okunur IPC araçlarıyla okunabilir; canlı şematik okuma yoktur.
Kilit algısı veya canlı/kayıtlı bayt farkı, kaydedilmemiş tampon garantisi değildir.
Bu nedenle `kicad`, `eeschema` ve `pcbnew` süreçlerinden herhangi biri varken yazma reddedilir;
proje yöneticisi içinde çalışan editörler de bu kapsamda engellenir.
Revizyon kontrolü, süreç içi kilit ve PcbAi süreçler arası yazma kilidi kullanılır. KiCad ile
işbirlikçi atomik dosya kilidi bulunmadığı için düzenleme sırasında editör kapalı olmalıdır.
PcbAi yazma kilidi işletim sistemi kilididir; süreç çökerse kendiliğinden serbest kalır.
Kilit dosyası özel durum klasörünün `locks/` dizininde kalır ve varlığı tek başına meşgul durum
anlamına gelmez. Kilit kimliği çözümlenmiş proje kökünden türetilir; Windows'ta harf büyüklüğü
normalleştirilir. Aynı projeye yazan tüm süreçler aynı `PCBAI_STATE_DIR` değerini kullanmalıdır.
0.1.0 servisi yükseltmeden önce durdurulmalıdır: eski sürümün kök kilidi farklıdır.
Önceden kalan `.pcbai-write.lock` otomatik silinmez; yeni sürüm bu dosyayı oluşturmaz.

Hiyerarşik şematikte bir Value, ortak dosyadaki bütün sayfa örneklerini etkiler. Önizleme bu
referansları, yolları ve diğer proje kayıtlarını açıkça listeler; görünen özellikteki eski referans
modern örnek kaydının yerine kullanılmaz. Yeni değerlerde kontrol karakterleri reddedilir.

Mevcut proje dosyasının owner/DACL (Windows) veya owner/grup/mode (POSIX) bilgisi atomik
değiştirmeden önce korunur; izin aktarımı başarısızsa orijinal dosya değişmez.
Durum klasörü mevcut kullanıcıya ait ve boş/yönetilen olmalıdır; bütün mevcut alt nesneler de korunur.

İçe aktarma, keyfi Python, katalog indirme, üretim siparişi ve fab yayınlama araçları sunulmaz.
Rapor çıktıları geçici, izole proje kopyasında üretilir. Eksik rapor/bozuk JSON doğrulanmış sayılmaz.
Özel durum klasöründeki checkpoint/kanıtlar şifrelenmez; kullanıcı hesabı sınırında saklanır.

IPC kanalı yapılandırmadan/yerel keşiften gelir, araç çağrısı program veya kanal URL'si seçemez.
Kayıtlı proje, PCB dosyası ve kanal kimliği eşleşmelidir. Birden çok belge bulunan kanalda ilk kart
seçilmez; hedef reddedilir. Her kipy çağrı dizisi zaman sınırlı ayrı süreçtedir. Canlı save/revert/yazma
sunulmaz. Arka plan işleri yalnız denetim ve çıktı araçlarına açıktır; revizyon değişirse sonuç reddedilir.

VS Code PNG paneli yalnız özel `exports` klasöründeki kanonik dosyaları açar. Webview betikleri
kapalıdır; CSP uzak ağ erişimini kapatır, dosya/proje metinleri HTML olarak yürütülmez.
HTTP Bearer belirteci webview'a verilmez. Gerber/delik ZIP üretimi bir dışa aktarımdır;
üretime hazır olma veya yayınlama/sipariş onayı değildir.
# KiCad kullanıcı ayarları

kicad-cli her çalışmada kullanıcının `kicad_common.json` dosyasına yazar (ölçüldü). PcbAi onu yalnız geçici bir ayar kopyasıyla (`KICAD_CONFIG_HOME`) çalıştırır; kullanıcı ayarları okunur, yazılmaz.

# Simülasyon

ngspice ayrı, zaman sınırlı bir süreçte çalışır. Şematikten gelen netlist veridir: `.control` blokları (ngspice `shell`, dosya yazma) atılır; `.include`/`.lib` yalnız proje kopyası ya da KiCad kurulumu içinden.

# Etkileşimli görünüm ve işaretler — 0.1.4

Kart 2B webview’ı yalnız eklentinin `media` klasörünü ve özel `views` çıktısını okuyabilir.
Betikler nonce ile izinli yerel modüllerdir; `default-src 'none'`, `connect-src 'none'`, uzak içerik
ve HTML olarak basılan dosya metni yoktur. Servis Bearer belirteci eklenti sürecindedir.
SVG yolları kanonik çıktı köküne ve `.svg` uzantısına sınırlandırılır; SVG içinde etkin/uzak içerik reddedilir.
Boş G0 paneli henüz oluşturulmamış servis durum klasörüne yazmaz.
Şematik paneli aynı CSP ve yol sınırlarını kullanır; sayfa seçimi yalnız servisin bildirdiği örnek yollarından
yapılır. Netlist XML’i DOCTYPE/ENTITY içeriyorsa reddedilir; kalibrasyon metni/daireleri yalnız geçici kopyaya yazılır.

Proje notları `pcbai/markers.json` içinde; HMAC anahtarı özel durum klasöründedir. İmza proje köküne
bağlıdır; içe aktarılmış/değiştirilmiş işaret `trusted=false` döner. Notu yeniden imzalamak açık UI
onayı gerektirir. UUID silinirse bağ kopuk gösterilir. Numara tekrar kullanılmaz; yazımlar tasarım
ve işaret dosyası karmasına bağlı önizlenen adayla, checkpoint ve OS yazma kilidi altında yapılır.
KiCad belgeleri işaret yazarken değiştirilmez; şematik değer yazma koruması aynen sürer.

MCP işaret oluşturma/silme araçlarını görmez. `/view/call` aynı yerel kullanıcı/Bearer güven sınırının
UI taşıma yoludur; o kullanıcının ayrıcalıklarıyla çalışan koddan bağımsız bir kullanıcı varlığı kanıtı
değildir. MCP durum güncellemesi yalnız imzalı işaretler içindir; `done` aynı hedef/revizyondaki gerçek
değişiklik kanıtını gerektirir. Onaysız işareti uygulama izni bir proje notundan türetilmez.
