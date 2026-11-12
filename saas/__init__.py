"""Ajan Ofisi SaaS: cok musterili online hizmet katmani.

Iki parca vardir, ikisi de ayni Docker imajindan calisir:
  web  (saas.web)  -> Cloud Run servisi: panel, giris, musteri API'si, Meta baglantisi, zamanlayici ucu
  isci (saas.isci) -> Cloud Run Job: kuyruktaki isleri (uretim, yayin turu, kaldirma, revize) yapar

Ajanlarin kendisi (ofis/ paketi) degismeden kullanilir: isci her is icin musterinin verisini
veritabani + dosya deposundan gecici bir klasore indirir, ajanlari o klasorde calistirir, sonucu geri yazar.
Web sureci ofis/ paketini HIC ice aktarmaz (o paket surec basina tek musteri calisir).
"""
