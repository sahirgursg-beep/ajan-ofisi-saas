#!/usr/bin/env bash
# Ajan Ofisi SaaS -> Google Cloud (Cloud Run servis + Cloud Run Job + Cloud Scheduler).
# Bir kez: Cloud Shell'de (tarayicidan, kurulum gerektirmez) bu klasorde calistirin:
#   PROJE=<gcp-proje-id> ADRES=https://app.<alan-adiniz> bash deploy/kur.sh
# Tekrar calistirmak guvenlidir: var olan kaynaklari gunceller.
set -euo pipefail

PROJE="${PROJE:?PROJE=<gcp proje kimligi> verin}"
BOLGE="${BOLGE:-europe-west1}"
ADRES="${ADRES:-}"                       # panelin dis adresi (alan adi baglanana kadar bos: Cloud Run adresi kullanilir)
IMAJ="$BOLGE-docker.pkg.dev/$PROJE/ajan/ajan-ofisi:$(date +%Y%m%d-%H%M%S)"
HESAP="ajan-ofisi@$PROJE.iam.gserviceaccount.com"

gcloud config set project "$PROJE" >/dev/null
echo "== API'ler"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudscheduler.googleapis.com generativelanguage.googleapis.com

echo "== Servis hesabi ve imaj deposu"
gcloud iam service-accounts describe "$HESAP" >/dev/null 2>&1 || \
  gcloud iam service-accounts create ajan-ofisi --display-name "Ajan Ofisi"
gcloud artifacts repositories describe ajan --location "$BOLGE" >/dev/null 2>&1 || \
  gcloud artifacts repositories create ajan --repository-format docker --location "$BOLGE"

echo "== Sirlar (Secret Manager). Eksik olanlari soracak; degerler ekranda gorunmez."
SIRLAR=(SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY SAAS_SIFRELEME_ANAHTARI SAAS_IMZA_ANAHTARI
        SAAS_ZAMANLAYICI_ANAHTARI META_APP_ID META_APP_SECRET GEMINI_API_KEY)
for S in "${SIRLAR[@]}"; do
  ad=$(echo "$S" | tr '_' '-' | tr 'A-Z' 'a-z')
  if ! gcloud secrets describe "$ad" >/dev/null 2>&1; then
    if [[ "$S" == SAAS_SIFRELEME_ANAHTARI ]]; then
      deger=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    elif [[ "$S" == SAAS_IMZA_ANAHTARI || "$S" == SAAS_ZAMANLAYICI_ANAHTARI ]]; then
      deger=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
    else
      read -rsp "$S: " deger; echo
    fi
    printf '%s' "$deger" | gcloud secrets create "$ad" --data-file=- --replication-policy automatic >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$ad" --member "serviceAccount:$HESAP" \
    --role roles/secretmanager.secretAccessor >/dev/null
done
SIR_BAGLA=$(for S in "${SIRLAR[@]}"; do printf '%s=%s:latest,' "$S" "$(echo "$S" | tr '_' '-' | tr 'A-Z' 'a-z')"; done)
SIR_BAGLA=${SIR_BAGLA%,}

echo "== Imaj (Cloud Build)"
gcloud builds submit --tag "$IMAJ" .

ORTAK="SAAS_ORTAM=bulut,SAAS_DEPO=supabase,GCP_PROJE=$PROJE,GCP_BOLGE=$BOLGE,SAAS_ISCI_IS_ADI=ajan-isci"

echo "== Isci (Cloud Run Job)"
gcloud run jobs deploy ajan-isci --image "$IMAJ" --region "$BOLGE" --service-account "$HESAP" \
  --command python --args=-m,saas.isci --cpu 2 --memory 4Gi --task-timeout 3600 --max-retries 0 \
  --set-env-vars "$ORTAK,SAAS_TETIK=yok" --set-secrets "$SIR_BAGLA"

echo "== Web (Cloud Run servis)"
gcloud run deploy ajan-web --image "$IMAJ" --region "$BOLGE" --service-account "$HESAP" \
  --allow-unauthenticated --cpu 1 --memory 1Gi --min-instances 0 --max-instances 4 --concurrency 40 \
  --set-env-vars "$ORTAK,SAAS_TETIK=cloudrun,SAAS_GENEL_ADRES=${ADRES:-https://placeholder}" \
  --set-secrets "$SIR_BAGLA"
SERVIS_ADRESI=$(gcloud run services describe ajan-web --region "$BOLGE" --format 'value(status.url)')
if [[ -z "$ADRES" ]]; then
  ADRES="$SERVIS_ADRESI"
  gcloud run services update ajan-web --region "$BOLGE" --update-env-vars "SAAS_GENEL_ADRES=$ADRES" >/dev/null
fi

echo "== Web servisinin isciyi baslatma izni"
gcloud run jobs add-iam-policy-binding ajan-isci --region "$BOLGE" \
  --member "serviceAccount:$HESAP" --role roles/run.invoker >/dev/null

echo "== Zamanlayici (her 10 dakika)"
ZK=$(gcloud secrets versions access latest --secret saas-zamanlayici-anahtari)
if gcloud scheduler jobs describe ajan-zamanlayici --location "$BOLGE" >/dev/null 2>&1; then
  gcloud scheduler jobs update http ajan-zamanlayici --location "$BOLGE" --schedule "*/10 * * * *" \
    --uri "$SERVIS_ADRESI/ic/zamanlayici" --http-method POST --update-headers "X-Zamanlayici-Anahtari=$ZK"
else
  gcloud scheduler jobs create http ajan-zamanlayici --location "$BOLGE" --schedule "*/10 * * * *" \
    --uri "$SERVIS_ADRESI/ic/zamanlayici" --http-method POST --headers "X-Zamanlayici-Anahtari=$ZK"
fi

echo
echo "Hazir: $ADRES"
echo "Meta uygulamasinda 'Valid OAuth Redirect URIs' kismina ekleyin: $ADRES/meta/geri"
echo "Saglik: $SERVIS_ADRESI/saglik"
