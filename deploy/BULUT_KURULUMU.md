# Buluta kurulum (bir kez, yaklaşık 1 saat)

Sunucu yok, bakım yok: web paneli ve işçi Google Cloud Run'da, veriler Supabase'de çalışır.
Kullanılmadığında Cloud Run sıfıra iner; ödeme kullanım kadardır.

## 1. Supabase (veritabanı, giriş, dosyalar)
1. supabase.com → New project (bölge: **West EU (London)** ya da **Central EU (Frankfurt)**), Pro plan.
2. SQL Editor → `sql/001_sema.sql` dosyasının tamamını yapıştırıp çalıştırın.
3. Storage → New bucket → ad: `ajan-ofisi`, **Public kapalı**.
4. Authentication → Providers → Email açık. URL Configuration → Site URL: panelin adresi (`https://app.alanadiniz.com`).
5. Project Settings → API: `Project URL`, `anon` ve `service_role` anahtarlarını bir kenara alın.
   `service_role` anahtarı tam yetkilidir: yalnızca Secret Manager'a girer, hiçbir yere yapıştırılmaz.

## 2. Meta uygulaması (tüm müşteriler için tek uygulama)
1. developers.facebook.com → Create app → **Business** türü → yeni şirketin Business hesabına bağlayın.
2. Products: **Facebook Login for Business** ve **Instagram Graph API**.
3. Facebook Login → Settings → Valid OAuth Redirect URIs: `https://app.alanadiniz.com/meta/geri`
4. App Settings → Basic: App ID ve App Secret; gizlilik politikası ve kullanım şartları adresleri.
5. Geliştirme modunda yalnızca uygulamaya rol verilen hesaplar bağlanabilir (bizim test hesaplarımız).
   Müşterilere açmak için **App Review**: istenen izinler `pages_manage_posts`, `pages_read_engagement`,
   `pages_show_list`, `read_insights`, `instagram_basic`, `instagram_content_publish`,
   `instagram_manage_insights`, `instagram_manage_comments`, `business_management`.
   Öncesinde **Business Verification** tamamlanmış olmalı.

## 3. Gemini anahtarı
aistudio.google.com → Get API key → Google Cloud projesini seçin.

## 4. Google Cloud
1. console.cloud.google.com → yeni proje → faturalandırmayı bağlayın.
2. Sağ üstte **Cloud Shell** (tarayıcıda terminal) açın, kodu yükleyin (GitHub deposundan `git clone`).
3. Çalıştırın:
   ```
   PROJE=<proje-kimligi> ADRES=https://app.alanadiniz.com bash deploy/kur.sh
   ```
   Betik eksik sırları tek tek sorar (ekranda görünmez), şifreleme ve imza anahtarlarını kendisi üretir,
   imajı derler, web servisini, işçiyi ve 10 dakikalık zamanlayıcıyı kurar.
4. Alan adı: Cloud Run → ajan-web → Manage custom domains → `app.alanadiniz.com`.

## 5. Kontrol
- `https://app.alanadiniz.com/saglik` → `"eksik": []` olmalı.
- Panelde hesap açın → işletme bilgilerini girin → Instagram & Facebook → Connect.
- "Generate today's content" → birkaç dakika sonra 3 içerik gelir.

## Güncelleme
Kod değişince Cloud Shell'de aynı komut: yeni imaj derlenir, servis ve işçi güncellenir, veriler yerinde kalır.

## Maliyet notu
Web servisi en az 0 örnekle çalışır (boşta ücret yok). Her üretim işi işçide birkaç dakika 2 CPU / 4 GB kullanır.
Gerçek rakamları pilotta ölçüp plan belgesindeki tabloyu güncelleyeceğiz.
