# Ajan Ofisi SaaS — geliştirme kopyası

Bu klasör, Furniture Republic'te çalışan ajan ofisinin **ayrı bir kopyası**dır. Canlı ofis
(`Documents\FR-Ajan-Ofisi`) bu klasörden hiçbir şekilde etkilenmez:

- Ayrı klasör, ayrı veri, ayrı Meta bağlantısı. Canlı ofisin `veri/`, `cikti/`, logo ve anahtarları buraya kopyalanmadı.
- Windows Görev Zamanlayıcı dosyaları (`YAYINCI_KUR.bat`, `GUNLUK_CALISTIR.bat`) bu kopyadan **çıkarıldı**;
  aynı görev adını kullanıp canlı ofisin görevinin üzerine yazabilirlerdi. Bulutta zamanlayıcıyı Cloud Scheduler yapacak (Faz 1).
- Ofis ekranı **8780** portunda açılır (canlı ofis 8765). İkisi aynı anda açık olabilir.

Plan: *Ajan Ofisi SaaS — Ticarileştirme Planı* (Claude Doc). Şu an **Faz 0**.

## Müşteri (tenant) yapısı

```
config.json                       ← platform varsayılanları (tüm müşterilerde aynı)
musteriler/
  _sablon/profil.json             ← yeni müşteri şablonu
  ornek-mobilya/profil.json       ← geliştirme için hayali müşteri ("Oak & Ember Living")
  <musteri>/veri/ cikti/ projeler/ marka/   ← çalışınca oluşur, depoya girmez
paylasilan/takvimler/NG.json      ← ülke takvimi (Black Friday, Detty December, Bağımsızlık Günü…)
```

Müşteriye özel her şey `profil.json`'dadır: işletme adı ve tanımı, ülke/şehirler, satış kanalı
(online satıyor mu), hashtag'ler, carousel maddeleri, saat dilimi ve mesai, para birimi ve kur,
ürün kaynağı (site / XML feed), kategoriler, marka renkleri ve logo, rakipler.
Ajanların istemlerindeki "furniture showroom in Nigeria" gibi sabitler artık buradan üretilir.

Hangi müşteriyle çalışılacağı: `AJAN_MUSTERI` ortam değişkeni → `aktif_musteri.txt` → `ornek-mobilya`.

```bat
set AJAN_MUSTERI=ornek-mobilya
.venv\Scripts\python calistir.py --demo --plansiz
```

## Yapay zeka sağlayıcısı

`config.json → yz`: `"saglayici": "ollama"` ya da `"gemini"`, isteğe bağlı `"yedek_saglayici"`.
Gemini anahtarı dosyaya yazılmaz; `GEMINI_API_KEY` ortam değişkeninden okunur.
İkisi de yoksa ajanlar şablon metinlerle çalışmaya devam eder.

## Testler

```bat
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest testler -q
set AJAN_TAM_TEST=1 && .venv\Scripts\python -m pytest testler -q   (tarayıcı + ffmpeg ile uçtan uca üretim de)
```

Testler gerçek müşteri klasörüne ve Meta'ya dokunmaz: geçici bir müşteri klasörü kurar, Meta çağrılarını sahteleriyle değiştirir.

## Faz 0 durumu

- [x] Kodun ayrı kopyası (canlı ofis yerinde)
- [x] Furniture Republic'e özel her şeyi müşteri profiline taşımak
- [x] Yapay zeka katmanını sağlayıcıdan bağımsız yapmak (Ollama + Gemini, yedekli)
- [x] Otomatik testler: üretim, yayın planlama, geri çekme, Meta hata durumları
- [~] Arayüz İngilizce (Türkçe seçenek sağ altta): menüler, butonlar, durumlar ve uyarılar çevrildi.
      Ajanların panodaki konuşmaları ve sayı içeren bazı cümleler hâlâ Türkçe; Faz 1 web panelinde kalıcı çeviri anahtarlarına geçilecek.
- [ ] Müzik, font ve model lisanslarının ticari kullanım için tek tek doğrulanması
- [ ] Özel GitHub deposuna yüklemek (depo açılınca)
