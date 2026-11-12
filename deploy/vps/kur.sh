#!/usr/bin/env bash
# Hostinger VPS ilk kurulum (Ubuntu 24.04 + Docker sablonu). VPS'te root olarak BIR KEZ:
#   curl -fsSL https://raw.githubusercontent.com/<kullanici>/ajan-ofisi-saas/main/deploy/vps/kur.sh -o kur.sh
#   bash kur.sh
# Depo ozel oldugu icin betik bir "deploy key" uretir ve GitHub'a eklemenizi ister.
set -euo pipefail
DEPO="${DEPO:-git@github.com:sahirgursg-beep/ajan-ofisi-saas.git}"
KLASOR=/opt/ajan-ofisi

echo "== Guvenlik guncellemeleri ve guvenlik duvari"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q && apt-get install -yq git ufw unattended-upgrades fail2ban >/dev/null
dpkg-reconfigure -f noninteractive unattended-upgrades
ufw allow OpenSSH >/dev/null && ufw allow 80/tcp >/dev/null && ufw allow 443 >/dev/null && ufw --force enable >/dev/null
command -v docker >/dev/null || { curl -fsSL https://get.docker.com | sh; }

echo "== GitHub erisimi (yalnizca okuma)"
mkdir -p ~/.ssh && chmod 700 ~/.ssh
[[ -f ~/.ssh/ajan_deploy ]] || ssh-keygen -t ed25519 -N "" -C "ajan-vps" -f ~/.ssh/ajan_deploy >/dev/null
grep -q "github.com" ~/.ssh/config 2>/dev/null || cat >> ~/.ssh/config <<CFG
Host github.com
  IdentityFile ~/.ssh/ajan_deploy
  StrictHostKeyChecking accept-new
CFG
if [[ ! -d $KLASOR/.git ]]; then
  echo
  echo "Bu anahtari GitHub > depo > Settings > Deploy keys > Add deploy key kismina ekleyin (Allow write ACIK DEGIL):"
  echo
  cat ~/.ssh/ajan_deploy.pub
  echo
  read -rp "Ekledikten sonra Enter'a basin... " _
  git clone "$DEPO" "$KLASOR"
fi
cd "$KLASOR"

echo "== Ayarlar (.env)"
if [[ ! -f .env ]]; then
  cp .env.example .env
  sor() { local ad=$1 gizli=${2:-}; local d; if [[ -n $gizli ]]; then read -rsp "$ad: " d; echo; else read -rp "$ad: " d; fi
          sed -i "s|^$ad=.*|$ad=$d|" .env; grep -q "^$ad=" .env || echo "$ad=$d" >> .env; }
  ayarla() { sed -i "s|^$1=.*|$1=$2|" .env; grep -q "^$1=" .env || echo "$1=$2" >> .env; }
  read -rp "Panel adresi (or. app.alanadiniz.com): " ALAN
  ayarla SAAS_ALAN_ADI "$ALAN"
  ayarla SAAS_GENEL_ADRES "https://$ALAN"
  ayarla SAAS_ORTAM bulut; ayarla SAAS_DEPO supabase; ayarla SAAS_TETIK surekli; ayarla SAAS_YEREL_GIRIS 0
  ayarla SAAS_SIFRELEME_ANAHTARI "$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  ayarla SAAS_IMZA_ANAHTARI "$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
  sor SUPABASE_URL; sor SUPABASE_ANON_KEY; sor SUPABASE_SERVICE_ROLE_KEY gizli
  sor META_APP_ID; sor META_APP_SECRET gizli; sor GEMINI_API_KEY gizli
  chmod 600 .env
  echo "ONEMLI: .env icindeki SAAS_SIFRELEME_ANAHTARI'ni guvenli bir yere yedekleyin (kaybolursa Meta baglantilari yeniden kurulur)."
fi

echo "== Baslat"
docker compose --env-file .env -f deploy/vps/docker-compose.yml up -d --build
sleep 8
docker compose --env-file .env -f deploy/vps/docker-compose.yml ps
echo
echo "Hazir. DNS kaydi dogruysa birkac dakika icinde: https://$(grep ^SAAS_ALAN_ADI= .env | cut -d= -f2)/saglik"
