// Arayuz dili. Varsayilan: musteri profili / config "arayuz_dili" (en). Turkce secenek kalir (sag alttaki dugme).
// Ekran Turkce yazilmistir; bu dosya gorunen metni (tam eslesen metin dugumleri, placeholder/title, onay kutulari)
// Ingilizceye cevirir. Degiskenli (sayi/ad iceren) bazi metinler henuz cevrilmez: Faz 1 panelinde t() anahtarlarina gecilecek.
(function () {
  const EN = {
    "Agent Office": "Agent Office",
    "Ajan Ofisi · Sosyal Medya": "Agent Office · Social Media",
    "Genel Bakış": "Overview", "Canlı Ofis": "Live Office", "Haftalık Plan": "Weekly Plan", "Yayın": "Publishing",
    "Öneriler": "Suggestions", "Performans": "Performance", "Kurallar": "Rules", "Sağlık": "Health", "Mesai": "Office hours",
    "Meta": "Meta", "Otomatik yayın": "Auto-publish", "Otomatik yayın ": "Auto-publish ",
    "sabah kontrolü": "morning check", "kontrol ediliyor…": "checking…", "Bağlanıyor…": "Connecting…",
    "Bugün ne paylaşılıyor, nasıl gidiyor": "What's going out today and how it's doing",
    "Ajanlar çalışırken izle": "Watch the agents at work",
    "Önümüzdeki 7 günün ürünleri ve formatları": "Products and formats for the next 7 days",
    "Planlanan, yayındaki ve dikkat bekleyen içerikler": "Scheduled, live and needs-attention content",
    "Ajanların haftalık toplantıdan getirdiği değişiklik önerileri": "Changes the agents propose after their weekly meeting",
    "Rakamlar, satışlar, yorum/DM, rakipler ve raporlar": "Numbers, sales, comments/DMs, competitors and reports",
    "Ajanların her içerikte uyduğu kalıcı kurallar": "Permanent rules the agents follow in every post",
    "▶ Demo günü": "▶ Demo day", "▶ Günü başlat": "▶ Start the day", "Bugün": "Today", "Bu hafta": "This week",
    "Bugünün yayın akışı": "Today's publishing schedule", "Ofisten son haberler": "Latest from the office",
    "Son çıktı": "Latest output", "Ofis panosu": "Office board", "Canlı ofis →": "Live office →",
    "Yayın sekmesi →": "Publishing tab →", "Haftalık plan →": "Weekly plan →", "Şimdi kontrol et →": "Check now →",
    "📊 Şimdi analiz et": "📊 Analyse now", "🩺 Sağlık kontrolü": "🩺 Health check", "Sağlık kontrolü": "Health check",
    "Sistem sağlıklı": "System healthy", "Sistemde uyarı var": "System has warnings",
    "Ekip çalışıyor": "Team is working", "Başka bir iş sürüyor": "Another job is running",
    "✔ Ofis hazır. Bir gün başlat.": "✔ Office ready. Start a day.",
    "Sunucuya bağlanılamadı (sunucu.py açık mı?)": "Can't reach the server (is sunucu.py running?)",
    "Plan ➜ Ürün ➜ Rötuş ➜ Yön ➜ Görsel ➜ Reels ➜ Analiz": "Plan ➜ Product ➜ Retouch ➜ Direction ➜ Visual ➜ Reels ➜ Analysis",
    "BUGÜNÜN İŞİ": "TODAY'S WORK", "Sırada": "Up next", "canlı": "live", "aç": "open",
    "Ofis Müdürü": "Office Manager", "Ürün Sorumlusu": "Product Lead", "Pazarlama Uzmanı": "Marketing Specialist",
    "Metin Yazarı": "Copywriter", "Sanat Yönetmeni": "Art Director", "İletişim Analisti": "Engagement Analyst",
    // plan
    "📅 Yeni hafta planı": "📅 New week plan", "📅 Planı oluştur": "📅 Create plan", "▶ Onaylıları üret": "▶ Produce approved",
    "✓ Günü onayla": "✓ Approve day", "✓ Hepsini onayla": "✓ Approve all", "✓ Onaylı": "✓ Approved", "✓ üretildi": "✓ produced",
    "Plan yükleniyor…": "Loading plan…", "Bu slotun ürününü değiştir": "Change this slot's product",
    "Günlere özel (isteğe bağlı)": "Per-day (optional)", "En az bir kategori seç": "Pick at least one category",
    "Kategoriler yükleniyor… (ilk seferde site feed'i okunur, ~20 sn)": "Loading categories… (first time reads the site feed, ~20 s)",
    "Bu hafta hangi kategorilere odaklanalım? Seçtiğin kategorilerden ürün seçeceğiz. İstersen bazı günlere özel kategori de ata.":
      "Which categories should we focus on this week? We'll pick products from them. You can also assign a category to specific days.",
    "Ajanlar gelecek 7 gün için her gün 3 farklı ürün planlar (12:00 post · 15:00 carousel · 18:30 Reels). Beğenmediğin ürünü 🔄 ile değiştir. \"Onaylıları üret\" haftanın içeriğini şimdiden hazırlar; her sabah 08:00'deki otomatik çalışma da plana göre üretir.":
      "The agents plan 3 different products for each of the next 7 days (12:00 post · 15:00 carousel · 18:30 Reels). Swap any product with 🔄. \"Produce approved\" prepares the week's content now; the automatic 08:00 run also follows the plan.",
    "Henüz plan yok — Haftalık Plan sekmesinden oluştur.": "No plan yet — create one in the Weekly Plan tab.",
    "Henüz plan yok. \"📅 Yeni hafta planı\" ile başlat.": "No plan yet. Start with \"📅 New week plan\".",
    "＋ Şimdi oluştur": "＋ Create now", "▶ Şimdi üret (3 içerik)": "▶ Produce now (3 posts)", "bugün için içerik yok": "no content for today",
    "Üretimde otomatik seçilecek": "Picked automatically at production", "Proje günü:": "Project day:",
    "Henüz proje yok. \"📂 Klasörü aç\" ile klasöre proje ekle.": "No projects yet. Add one with \"📂 Open folder\".",
    "📂 Klasörü aç": "📂 Open folder", "Henüz yok": "None yet",
    // yayin
    "✅ Onayla": "✅ Approve", "Kaldır": "Remove", "Yayından kaldır": "Take down", "Vazgeç": "Cancel", "Kaydet": "Save",
    "✏️ Revize et": "✏️ Request changes", "🔁 Revizyonu başlat": "🔁 Start revision", "▶ Şimdi yayınla": "▶ Publish now",
    "✓ Onaylandı": "✓ Approved", "✓ Senin onayınla": "✓ Approved by you", "🤖 Otomatik yayın": "🤖 Auto-publish",
    "📅 Planlı": "📅 Scheduled", "★ Yayında": "★ Live", "★ Yayınlandı": "★ Published", "★ Üretildi": "★ Produced",
    "📤 Yayınlanıyor…": "📤 Publishing…", "🗑 Kaldırılıyor…": "🗑 Removing…", "🗑 Yayından kaldırıldı": "🗑 Taken down",
    "⚠ Kısmen yayınlandı": "⚠ Partly published", "✖ Yayın hatası": "✖ Publishing error",
    "⚠ Kaldırma tamamlanamadı": "⚠ Removal incomplete", "⏰ Saatinde yayınlanamadı": "⏰ Missed its slot",
    "↻ Hatalıları tekrar dene": "↻ Retry failed", "↻ Kaldırmayı tekrar dene": "↻ Retry removal",
    "boş = hemen": "empty = now", "Bu filtrede içerik yok.": "No content for this filter.", "Henüz içerik yok.": "No content yet.",
    "Her şey": "Everything", "Post": "Post", "Story": "Story", "Reels": "Reels",
    "Ne değişsin?": "What should change?", "🎨 Farklı şablon": "🎨 Different template", "☀️ Daha açık renkler": "☀️ Lighter colours",
    "💰 Fiyatı öne çıkar": "💰 Highlight the price", "🖼️ Farklı fotoğraf": "🖼️ Different photo", "🎵 Farklı müzik": "🎵 Different music",
    "Bir seçenek işaretle ya da not yaz.": "Tick an option or write a note.", "Yeni versiyon listenin üstünde.": "The new version is at the top of the list.",
    "Sanat Yönetmeni notunu ekibe dağıtır; yeni versiyon yine senin onayına gelir.": "The Art Director shares your note with the team; the new version comes back for your approval.",
    "İstersen kendi notunu yaz: örn. 'fiyat yazısı daha büyük olsun', 'arka plan krem rengi olsun', 'başlıkta Detty December geçsin'":
      "Add your own note if you like, e.g. 'bigger price text', 'cream background', 'mention Detty December in the headline'",
    "En az bir yayın yeri seçin": "Pick at least one destination",
    "Bu içerik reddedilsin mi? (yayınlanmaz)": "Reject this content? (it won't be published)",
    "Bu içerik yayınlanmayacak (Meta'daki planı da iptal edilir). Emin misin?": "This content won't be published (its Meta schedule is cancelled too). Are you sure?",
    "Bu içerik Instagram ve Facebook'tan SİLİNECEK (yayında olan kısımlar). Emin misin?": "This content will be DELETED from Instagram and Facebook (the live parts). Are you sure?",
    "Beklemeye aldın; otomatik yayına girmez, istersen elle onayla.": "On hold; it won't auto-publish. Approve it manually if you want.",
    "hiçbir içerik sen Onayla'ya basmadan yayınlanmaz.": "nothing is published until you press Approve.",
    "Otomatik yayın açılsın mı? Kalite kontrolden temiz geçen içerikler saatinde kendiliğinden paylaşılır; istemediğini Kaldır ile durdurursun.":
      "Turn on auto-publish? Content that passes quality control is posted at its time; stop anything with Remove.",
    "Otomatik yayın kapatılsın mı? Bundan sonra her içerik senin Onayla'na kadar bekler.": "Turn off auto-publish? Every post will wait for your Approve.",
    "Mesai içinde": "Within office hours", "Mesai dışı": "Outside office hours", "Aktif": "On", "Kapalı": "Off",
    "🎵 Reels müziği:": "🎵 Reels music:", "Reels formatı": "Reels format", "🎬 Format aç": "🎬 Enable format",
    "Lüks tanıtım": "Luxury showcase", "Fiyatı tahmin et": "Guess the price",
    "Sadece yeni Reels formatları": "Only new Reels formats", "Tüm Reels": "All Reels",
    // meta
    "🔗 Facebook & Instagram bağlantısı": "🔗 Facebook & Instagram connection", "Bağlan": "Connect", "Bağlantıyı kes": "Disconnect",
    "Meta bağlı": "Meta connected", "Meta bağlı değil": "Meta not connected", "Instagram Business bağlı değil": "Instagram Business not linked",
    "bağlı IG Business hesabı yok": "no linked IG Business account", "🔍 Bağlantıyı test et": "🔍 Test connection",
    "yayın yapmaz, sadece hangi iznin çalıştığına bakar": "doesn't post, only checks which permissions work",
    "Meta bağlantısı silinsin mi?": "Remove the Meta connection?", "Bu anahtarla yönetilen sayfa bulunamadı": "No Page is managed with this token",
    "Anahtar geçersiz ya da süresi dolmuş: yeni anahtar oluşturup tekrar bağla.": "Token invalid or expired: create a new token and reconnect.",
    "Bu izin anahtarda yok: META_BAGLANTI.md'deki izinlerle yeni anahtar oluştur.": "This permission is missing from the token: create a new token with the permissions in META_BAGLANTI.md.",
    "Meta bu isteği tanımadı (hesap bağlı değil ya da bu özellik bu hesapta kapalı olabilir).": "Meta didn't recognise this request (account not linked or the feature is off for this account).",
    // oneriler
    "💡 Müdürün önerileri": "💡 Manager's suggestions", "🗣 Toplantıyı şimdi yap": "🗣 Hold the meeting now", "Toplantıyı şimdi yap": "Hold the meeting now",
    "Son toplantı": "Last meeting", "Henüz toplantı yapılmadı.": "No meeting held yet.",
    "Onayladığın öneri ayarlara kendiliğinden işlenir": "Approved suggestions are applied to settings automatically",
    "; reddettiğini 30 gün tekrar önermezler.": "; rejected ones aren't proposed again for 30 days.",
    "Henüz öneri yok. İlk toplantı pazartesi yapılır; istersen \"Toplantıyı şimdi yap\".": "No suggestions yet. The first meeting is on Monday, or press \"Hold the meeting now\".",
    "Her pazartesi 09:00'dan sonra ajanlar geçen haftanın rakamlarını, yorum/DM raporunu, satış kayıtlarını ve rakipleri tartışır; Müdür somut önerileri buraya getirir.":
      "Every Monday after 09:00 the agents discuss last week's numbers, the comments/DM report, sales records and competitors; the Manager brings concrete proposals here.",
    "📦 Kategori önceliği": "📦 Category priority", "📈 Pazarlama Uzmanı soruyor": "📈 Marketing Specialist asks",
    // performans
    "Son 7 gün izlenme": "Views, last 7 days", "Instagram takipçi": "Instagram followers", "Instagram takipçi:": "Instagram followers:",
    " takipçi": " followers", "henüz belirgin değil": "not clear yet", "↻ Şimdi yenile": "↻ Refresh now", "↻ Şimdi tara": "↻ Scan now",
    "🔭 Rakipler ve ilham hesapları": "🔭 Competitors and inspiration accounts", "instagram kullanıcı adları, virgülle": "instagram usernames, comma-separated",
    "Henüz taranmadı. Her pazartesi kendiliğinden taranır.": "Not scanned yet. Scanned automatically every Monday.",
    "📄 Haftalık yönetici raporları": "📄 Weekly management reports", "Her pazartesi kendiliğinden hazırlanır.": "Prepared automatically every Monday.",
    "· tarayıcıda açıp Ctrl+P ile PDF olarak kaydedebilirsin": "· open in the browser and save as PDF with Ctrl+P",
    "Rakamlar (izlenme · beğeni · kaydetme · paylaşım · yorum) 3 saatte bir Meta'dan kendiliğinden gelir; yorumlardaki fiyat/adres soruları \"satın alma ilgisi\" sayılır. Analiz her akşam 18:00'de kendiliğinden çalışır.":
      "Numbers (views · likes · saves · shares · comments) arrive from Meta every 3 hours; price/address questions in comments count as \"purchase interest\". Analysis runs automatically every evening at 18:00.",
    "(ofis cevap yazmaz; cevaplar satış ekibi ve Meta asistanında)": "(the office never replies; replies are handled by the sales team and Meta's assistant)",
    "Henüz mesaj yok.": "No messages yet.", "Durum": "Status",
    // kurallar
    "📝 Kurallarım": "📝 My rules", "Yeni kural yaz…": "Write a new rule…", "Henüz kural yok.": "No rules yet.",
    "Kendi cümlenle yaz. Örn: \"Kırmızı renk kullanma\", \"Başlıklar en fazla 5 kelime olsun\", \"Her caption'da adresimizi hatırlat\".":
      "Write it in your own words, e.g. \"Don't use red\", \"Headlines max 5 words\", \"Mention our address in every caption\".",
    "Buradaki kurallar": "The rules here", "kalıcıdır": "are permanent",
    ": bundan sonraki her içerikte tüm ajanlar uygular. Tek bir içeriği düzeltmek için Yayın kartındaki": ": every agent applies them to all future content. To fix a single post, use the Publishing card's",
    "'i kullan.": ".",
    "🚫 Bunları hiç kullanma": "🚫 Never use these", "Tıkla → kırmızı = yasak. Sanat Yönetmeni bunları bir daha seçemez (kesin kural).": "Click → red = banned. The Art Director can never pick these again (hard rule).",
    "Hepsi yasaklanamaz, en az bir seçenek kalmalı.": "You can't ban them all; at least one option must remain.",
    "Yazı tipi": "Typeface", "Fiyat gösterimi": "Price display", "Fotoğraf filtresi": "Photo filter", "Köşe süsleri": "Corner ornaments",
    "Köşe şeridi": "Corner ribbon", "Altın çizgi": "Gold line", "Çift çerçeve": "Double frame", "Üst foto + alt panel": "Top photo + bottom panel",
    "Cesur (büyük harf)": "Bold (uppercase)", "🏷️ Kampanya bandı (BLACK FRIDAY, NEW IN…)": "🏷️ Campaign banner (BLACK FRIDAY, NEW IN…)",
    "Uygun günlerde kullanılsın": "Use on suitable days", "Hiç kullanılmasın": "Never use",
    "Metinlerde asla geçmez; Kalite Kontrol kontrol eder. Virgülle ayır.": "Never appears in copy; Quality Control checks it. Separate with commas.",
    "💾 Kuralları kaydet": "💾 Save rules", "💾 Değişiklikleri kaydet": "💾 Save changes",
    "✅ Kaydedildi — bundan sonraki tüm içeriklere uygulanacak": "✅ Saved — applies to all future content",
    "Otomatik (seçilenlerden)": "Automatic (from selected)", "⏭ Sıradaki": "⏭ Next", "Yükleniyor…": "Loading…", "Gör": "View",
    // durumlar ve kisa etiketler
    "⏳ Onay bekliyor": "⏳ Awaiting approval", "Dikkat bekleyen": "Needs attention", "takip ediliyor": "tracked",
    "Yayın sekmesinden bağla": "Connect from the Publishing tab", "📅 Otomatik planlandı": "📅 Auto-scheduled",
    "✖ Uygulanamadı": "✖ Couldn't apply", "Henüz rapor yok. Meta bağlıyken her akşam 21:00'den sonra hazırlanır.": "No report yet. Prepared every evening after 21:00 while Meta is connected.",
    "AÇIK": "ON", "açık": "on", "kapalı": "off", "Düzen": "Layout", "Görsel": "Visual", "Süsleme": "Ornament", "Süssüz": "Plain",
    "Sıcak": "Warm", "Çerçeveli": "Framed", "beğeni": "likes", "görüntülenme": "views", "satın alma ilgisi": "purchase interest",
    "otomatik seçilecek": "picked automatically", "Onaylıları üret": "Produce approved", "onayın kayıtlı,": "your approval is saved,",
    "Pazartesi": "Monday", "Salı": "Tuesday", "Çarşamba": "Wednesday", "Perşembe": "Thursday", "Cuma": "Friday",
    "Cumartesi": "Saturday", "Pazar": "Sunday",
    "Meta bu uygulamanın API erişimini durdurmuş. developers.facebook.com → uygulaman → panodaki uyarılar (Veri Kullanımı Kontrolü, kısıtlama, doğrulama) ve business.facebook.com → Hesap Kalitesi / Destek'i kontrol et.":
      "Meta has blocked this app's API access. Check developers.facebook.com → your app → dashboard alerts (Data Use Checkup, restrictions, verification) and business.facebook.com → Account Quality / Support.",
    // satis sayfasi
    "Müşteri kaydı": "Customer record", "Sosyal medyadan müşteri": "Customer from social media", "Ofis PIN'i": "Office PIN",
    "PIN ofis ekranında Performans → Satış bölümünde yazar.": "The PIN is shown in the office screen under Performance → Sales.",
    "Giriş": "Sign in", "PIN hatalı": "Wrong PIN", "Müşteri nereden geldi?": "Where did the customer come from?",
    "Hangi ürün? (son paylaşılanlar)": "Which product? (recently posted)", "ya da ürün ara: soho, dining…": "or search a product: soho, dining…",
    "Satış tutarı (isteğe bağlı)": "Sale amount (optional)", "Satıcı ve not": "Salesperson and note", "Adın": "Your name",
    "Not (isteğe bağlı)": "Note (optional)", "Bir ürün seç ya da yaz": "Pick or type a product",
    "Henüz paylaşılan ürün yok, aşağıdan ara.": "No posted products yet, search below.",
    "Bulunamadı — yazdığın ad olduğu gibi kaydedilir.": "Not found — the name you typed is saved as is.",
  };

  const anahtar = "ajan_dil";
  let dil;
  try { dil = localStorage.getItem(anahtar); } catch (e) { dil = null; }
  dil = dil || ((window.MUSTERI || {}).dil) || "en";
  window.DIL = dil;
  if (dil !== "en") { window.t = (s) => s; return; }

  const cevir = (s) => {
    if (!s) return s;
    const ham = s.trim();
    const k = EN[ham] ?? EN[ham.replace(/\s+/g, " ")];
    return k === undefined ? s : s.replace(ham, k);
  };
  window.t = cevir;

  const ATLA = new Set(["SCRIPT", "STYLE", "TEXTAREA", "PRE", "CODE"]);
  function dugum(n) {
    if (n.nodeType === 3) {
      if (n.parentNode && ATLA.has(n.parentNode.nodeName)) return;
      const y = cevir(n.nodeValue);
      if (y !== n.nodeValue) n.nodeValue = y;
      return;
    }
    if (n.nodeType !== 1 || ATLA.has(n.nodeName)) return;
    for (const a of ["placeholder", "title"]) {
      if (n.hasAttribute && n.hasAttribute(a)) {
        const y = cevir(n.getAttribute(a));
        if (y !== n.getAttribute(a)) n.setAttribute(a, y);
      }
    }
    n.childNodes.forEach(dugum);
  }
  const _confirm = window.confirm.bind(window), _alert = window.alert.bind(window);
  window.confirm = (m) => _confirm(cevir(String(m)));
  window.alert = (m) => _alert(cevir(String(m)));

  function basla() {
    document.documentElement.lang = "en";
    dugum(document.body);
    document.title = cevir(document.title);
    new MutationObserver((ml) => ml.forEach((m) => {
      if (m.type === "characterData") dugum(m.target);
      else m.addedNodes.forEach(dugum);
    })).observe(document.body, {childList: true, subtree: true, characterData: true});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", basla); else basla();
})();

// Dil dugmesi (her iki dilde de gorunur)
document.addEventListener("DOMContentLoaded", () => {
  const b = document.createElement("button");
  b.textContent = window.DIL === "en" ? "TR" : "EN";
  b.title = window.DIL === "en" ? "Türkçe" : "English";
  b.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:9999;padding:4px 10px;font-size:12px;opacity:.75";
  b.onclick = () => { try { localStorage.setItem("ajan_dil", window.DIL === "en" ? "tr" : "en"); } catch (e) {} location.reload(); };
  document.body.appendChild(b);
});
