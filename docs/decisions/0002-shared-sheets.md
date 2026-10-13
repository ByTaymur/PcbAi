# Ortak sayfa örnekleri ve özel kilit — 11 Ekim 2026

KiCad'de aynı fiziksel sembol, farklı sayfa yollarında farklı referanslarla bulunabilir.
`Reference` özelliği tek görüntüleme değeri taşır; gerçek referanslar `instances/project/path`
kayıtlarındadır. [Resmî biçim](https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/)
her örneğin referansını ve birimini tanımlar; aynı dosyada başka projelerin kayıtları da bulunabilir.

0.1.1 listesi proje adı ve kök şematik UUID'siyle her kayıtlı proje örneğini ayrı gösterir.
Demolarda bulunan boş proje adları yalnız kök UUID eşleşmesiyle mevcut projeye bağlanır.
Düzenleme mevcut projeden seçilir, fakat
ortak dosyanın tüm etki kayıtları önizlemeye alınır. Paylaşılan referansların bütün birimleri
birlikte güncellenir. Aynı proje/kök/referans/birim tekrar ediyorsa veya eski değerler farklıysa
belirsiz düzenleme reddedilir. Yinelenmiş Value/Reference özellikleri reddedilir; okuyucu/editör
farklı alan seçmez. Kök filtresi yalnız kök UUID verilen alt model çağrılarında da uygulanır.
Önizlenen adayı uygulama mevcut onay adımıdır; ek onay kapısı yoktur.
Örnek kaydı olan sembolde eski görüntüleme referansına geri dönmek yanlış hedef seçebileceğinden yasaktır.
Bu çekirdek kayıtlı yolları gösterir; hiyerarşinin kökten erişilebilirliğini yeniden hesaplamaz.

Kontrol karakterlerinin KiCad kaçış uyumu doğrulanmadığı için yeni Value metninde C0/C1 ve
surrogate kodları reddedilir. Var olan dosyalar normalize edilmez.

Kalıcı OS kilidi özel durumun `locks/` klasörüne taşındı. Anahtar kanonik proje köküdür;
Windows harf büyüklüğü normalleştirilir. Yol silinmez: silme/yeni açma farklı inode'larda eşzamanlı
yazma yarışına yol açabilir. Çökme OS kilidini bırakır. Tüm süreçler aynı durum klasörünü kullanır;
eski sürümün servisi yükseltme öncesi durdurulur. Eski proje kilidi otomatik silinmez.

Doğrulama: sentetik proje/çok birim/belirsizlik testleri, önizleme ve uygulamada etki aktarımı,
geçici complex_hierarchy kopyasında R303 düzenlemesi, gerçek KiCad XML netlistinde R203/R303
değerleri ve checkpoint'ten bayt eşit geri dönüş. Kullanıcı projesi ve kurulu demolar değiştirilmez.
