# Hostinger VPS kurulumu

Her şey tek sunucuda, Docker içinde çalışır: web paneli, işçi (ajanlar) ve HTTPS (Caddy).
Veriler, girişler ve dosyalar Supabase'de durur; sunucu bozulsa bile müşteri verisi kaybolmaz.
Güncellemeler GitHub'dan otomatik gelir: `main` dalına gönderilen değişiklik testlerden geçerse
VPS kendini günceller, geçmezse canlıya çıkmaz; yeni sürüm açılmazsa eskisine döner.

## Sıra
1. **VPS:** Hostinger → VPS → **KVM 2** (2 vCPU, 8 GB), işletim sistemi **Ubuntu 24.04 with Docker**,
   konum Avrupa (Frankfurt ya da UK). Root şifresi belirleyin.
2. **DNS:** Hostinger → Domains → DNS: `A` kaydı, ad `app`, değer = VPS'in IP adresi.
3. **Supabase:** proje (Free plan yeterli), SQL Editor'de `sql/001_sema.sql`, Storage'da `ajan-ofisi`
   kovası (public kapalı), Authentication → URL Configuration → Site URL `https://app.alanadiniz.com`.
4. **Kurulum:** Hostinger panelinde VPS → Browser terminal → `deploy/vps/kur.sh` (birlikte çalıştıracağız).
   Betik bir "deploy key" gösterir → GitHub → depo → Settings → Deploy keys → ekleyin.
   Sonra Supabase ve Meta bilgilerini sorar; şifreleme anahtarlarını kendisi üretir.
5. **Otomatik güncelleme:** GitHub → depo → Settings → Secrets and variables → Actions:
   Variables: `VPS_HOST` = VPS IP adresi · Secrets: `VPS_SSH_KEY` (adımı birlikte yapacağız).

## Günlük işletme
- Durum: `https://app.alanadiniz.com/saglik`
- Kayıtlar: `cd /opt/ajan-ofisi && docker compose --env-file .env -f deploy/vps/docker-compose.yml logs -f isci`
- Güvenlik güncellemeleri kendiliğinden kurulur; yalnızca 22, 80, 443 portları açık.
