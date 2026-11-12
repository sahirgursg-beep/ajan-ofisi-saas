# Facebook & Instagram bağlantısı (bir kez yapılır)

Ajan ofisinin Facebook Sayfanıza ve Instagram hesabınıza yayın yapabilmesi, rakamları ve yorum/mesaj raporunu çekebilmesi için Meta'dan bir
**erişim anahtarı** gerekiyor. Anahtar sadece bu bilgisayarda (`veri/meta.json`) saklanır.

> Not: Meta menü adlarını zaman zaman değiştirir; birebir aynı değilse en yakın seçeneği izleyin
> ya da ekran görüntüsünü Claude'a gönderin.

## Ön koşullar
- Instagram hesabı **Business** ya da **Creator** olmalı ve **Facebook Sayfanıza bağlı** olmalı
  (Instagram → Ayarlar → Hesap türü; Facebook Sayfası → Ayarlar → Bağlı hesaplar → Instagram).
- Sayfada **tam yetkili** (admin) olmalısınız.

## Önerilen yol: Sistem Kullanıcısı anahtarı (süresi dolmaz)
1. **business.facebook.com/settings** → sol menü **Kullanıcılar → Sistem kullanıcıları** → **Ekle**
   (ad: `Ajan Ofisi`, rol: **Yönetici**).
2. Önce bir uygulama gerekir: **developers.facebook.com/apps** → **Uygulama oluştur** → tür: **İşletme (Business)**
   → işletme portföyünüzü seçin. Uygulamaya **Instagram Graph API** / **Facebook Login for Business** ürünlerini ekleyin.
3. Business ayarlarına dönün → **Hesaplar → Uygulamalar** → uygulamanın işletmenize bağlı olduğundan emin olun.
4. Sistem kullanıcısını seçin → **Varlık ata** → **Sayfalar**: işletmenin Facebook sayfası (**Tam kontrol**)
   ve **Instagram hesapları**: hesabınız (**Tam kontrol**).
5. **Yeni belirteç oluştur** → uygulamayı seçin → süre: **Hiçbir zaman** → şu izinleri işaretleyin:
   - `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `business_management`
   - `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `read_insights`
   - Yorum/DM raporu için (sadece okuma): `pages_read_user_content`, `instagram_manage_comments`,
     `pages_messaging`, `instagram_manage_messages`
   - Instagram'dan "Kaldır" ile silebilmek için listede varsa: `instagram_manage_contents`
   > Daha önce bağladıysanız: bu yeni izinlerle **yeni bir anahtar** oluşturup Onay sekmesinde tekrar bağlayın.
   > Eksik izin olursa ofis çökmez; raporda "Okunamayanlar (Meta izni eksik olabilir)" diye yazar.
6. Çıkan uzun anahtarı (`EAA...` ile başlar) kopyalayın.

## Daha hızlı ama süreli yol: Graph API Explorer
1. **developers.facebook.com/tools/explorer** → sağda uygulamanızı seçin → **Kullanıcı erişim belirteci**.
2. Yukarıdaki izinleri ekleyin → **Generate Access Token** → sayfanızı ve Instagram hesabınızı seçip onaylayın.
3. Anahtarı **developers.facebook.com/tools/debug/accesstoken** sayfasında yapıştırıp **Erişim belirtecini uzat**'a basın
   (60 günlük). Bundan türetilen sayfa anahtarının süresi dolmaz.

## Ofis ekranına bağlama
1. `BASLAT.bat` → **📤 Onay** sekmesi → anahtarı yapıştırın → **Bağlan**.
2. Listeden işletmenin sayfasını seçin. Instagram hesabı yanında görünmeli.
3. Bitti. Yayın sekmesinde otomatik yayın anahtarı ve her içerikte **Kaldır** düğmesi görünür.

## Güvenlik ve otomatik yayın
- **Otomatik yayın açıkken** kalite kontrolden temiz geçen içerik saatinde kendiliğinden paylaşılır; Facebook
  gönderileri önceden Meta planlayıcısına (Business Suite) düşer. İstemediğinizi Yayın sekmesinde **Kaldır**:
  planlıysa iptal edilir, yayındaysa Facebook ve Instagram'dan silinir.
- Kalite kontrol uyarısıyla geçen, "Beklemeye al" dediğiniz ya da saati geçmiş içerik otomatik yayınlanmaz.
- Otomatik yayını aynı sekmedeki anahtarla kapatabilirsiniz; kapalıyken hiçbir şey **Onayla** olmadan yayınlanmaz.
- Ofis yorumlara ve mesajlara **cevap yazmaz**, sadece okuyup raporlar.
- Anahtarı kimseyle paylaşmayın. Bağlantıyı kaldırmak için Onay sekmesinde **Bağlantıyı kes**.
- Instagram'ın API'sinde planlama olmadığı için Instagram paylaşımları saatinde bu bilgisayardan gider:
  bilgisayar açık ve internete bağlı olmalı. `YAYINCI_KUR.bat`'ı bir kez çalıştırırsanız ofis ekranı kapalıyken de
  (10 dakikada bir) yayıncı çalışır. Bilgisayar 2 saatten fazla kapalı kaldıysa geç kalan içerik kendiliğinden
  paylaşılmaz, "Şimdi yayınla" ile siz karar verirsiniz.
