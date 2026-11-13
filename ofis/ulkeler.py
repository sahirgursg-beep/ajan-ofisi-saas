"""Ulke tablosu: kayit formu, para birimi, saat dilimi ve icerik dili varsayilanlari (saf veri, web de kullanir).

Her ulke: (kod, ad, para, sembol, saat_dilimi, dil, yuvarlama)
  yuvarlama: urun fiyatlari postlarda bu adima yuvarlanir (or. NGN 1000, USD 1, JPY 100).
Listede olmayan ulke de secilebilir: para/saat/dil alanlari elle yazilir.
"""

U = [
    # Afrika
    ("NG", "Nigeria", "NGN", "₦", "Africa/Lagos", "en", 1000), ("GH", "Ghana", "GHS", "GH₵", "Africa/Accra", "en", 10),
    ("KE", "Kenya", "KES", "KSh", "Africa/Nairobi", "en", 100), ("ZA", "South Africa", "ZAR", "R", "Africa/Johannesburg", "en", 10),
    ("EG", "Egypt", "EGP", "E£", "Africa/Cairo", "ar", 10), ("MA", "Morocco", "MAD", "DH", "Africa/Casablanca", "fr", 10),
    ("TZ", "Tanzania", "TZS", "TSh", "Africa/Dar_es_Salaam", "en", 1000), ("UG", "Uganda", "UGX", "USh", "Africa/Kampala", "en", 1000),
    ("RW", "Rwanda", "RWF", "FRw", "Africa/Kigali", "en", 100), ("ET", "Ethiopia", "ETB", "Br", "Africa/Addis_Ababa", "en", 10),
    ("CI", "Côte d'Ivoire", "XOF", "CFA", "Africa/Abidjan", "fr", 100), ("SN", "Senegal", "XOF", "CFA", "Africa/Dakar", "fr", 100),
    ("CM", "Cameroon", "XAF", "FCFA", "Africa/Douala", "fr", 100), ("TN", "Tunisia", "TND", "DT", "Africa/Tunis", "fr", 1),
    ("DZ", "Algeria", "DZD", "DA", "Africa/Algiers", "fr", 100), ("ZM", "Zambia", "ZMW", "K", "Africa/Lusaka", "en", 10),
    ("ZW", "Zimbabwe", "USD", "$", "Africa/Harare", "en", 1), ("BW", "Botswana", "BWP", "P", "Africa/Gaborone", "en", 10),
    # Avrupa
    ("GB", "United Kingdom", "GBP", "£", "Europe/London", "en", 1), ("IE", "Ireland", "EUR", "€", "Europe/Dublin", "en", 1),
    ("DE", "Germany", "EUR", "€", "Europe/Berlin", "de", 1), ("FR", "France", "EUR", "€", "Europe/Paris", "fr", 1),
    ("ES", "Spain", "EUR", "€", "Europe/Madrid", "es", 1), ("IT", "Italy", "EUR", "€", "Europe/Rome", "it", 1),
    ("PT", "Portugal", "EUR", "€", "Europe/Lisbon", "pt", 1), ("NL", "Netherlands", "EUR", "€", "Europe/Amsterdam", "nl", 1),
    ("BE", "Belgium", "EUR", "€", "Europe/Brussels", "fr", 1), ("AT", "Austria", "EUR", "€", "Europe/Vienna", "de", 1),
    ("CH", "Switzerland", "CHF", "CHF", "Europe/Zurich", "de", 1), ("SE", "Sweden", "SEK", "kr", "Europe/Stockholm", "sv", 10),
    ("NO", "Norway", "NOK", "kr", "Europe/Oslo", "no", 10), ("DK", "Denmark", "DKK", "kr", "Europe/Copenhagen", "da", 10),
    ("FI", "Finland", "EUR", "€", "Europe/Helsinki", "fi", 1), ("PL", "Poland", "PLN", "zł", "Europe/Warsaw", "pl", 1),
    ("CZ", "Czechia", "CZK", "Kč", "Europe/Prague", "cs", 10), ("RO", "Romania", "RON", "lei", "Europe/Bucharest", "ro", 1),
    ("GR", "Greece", "EUR", "€", "Europe/Athens", "el", 1), ("HU", "Hungary", "HUF", "Ft", "Europe/Budapest", "hu", 100),
    ("UA", "Ukraine", "UAH", "₴", "Europe/Kyiv", "uk", 10), ("TR", "Turkey", "TRY", "₺", "Europe/Istanbul", "tr", 10),
    ("CY", "Cyprus", "EUR", "€", "Asia/Nicosia", "el", 1), ("RS", "Serbia", "RSD", "din", "Europe/Belgrade", "sr", 10),
    # Amerika
    ("US", "United States", "USD", "$", "America/New_York", "en", 1), ("CA", "Canada", "CAD", "C$", "America/Toronto", "en", 1),
    ("MX", "Mexico", "MXN", "MX$", "America/Mexico_City", "es", 10), ("BR", "Brazil", "BRL", "R$", "America/Sao_Paulo", "pt", 1),
    ("AR", "Argentina", "ARS", "AR$", "America/Argentina/Buenos_Aires", "es", 100), ("CO", "Colombia", "COP", "COL$", "America/Bogota", "es", 1000),
    ("CL", "Chile", "CLP", "CLP$", "America/Santiago", "es", 100), ("PE", "Peru", "PEN", "S/", "America/Lima", "es", 1),
    ("JM", "Jamaica", "JMD", "J$", "America/Jamaica", "en", 100), ("TT", "Trinidad and Tobago", "TTD", "TT$", "America/Port_of_Spain", "en", 1),
    ("DO", "Dominican Republic", "DOP", "RD$", "America/Santo_Domingo", "es", 10),
    # Orta Dogu
    ("AE", "United Arab Emirates", "AED", "AED", "Asia/Dubai", "en", 1), ("SA", "Saudi Arabia", "SAR", "SAR", "Asia/Riyadh", "ar", 1),
    ("QA", "Qatar", "QAR", "QAR", "Asia/Qatar", "ar", 1), ("KW", "Kuwait", "KWD", "KD", "Asia/Kuwait", "ar", 1),
    ("BH", "Bahrain", "BHD", "BD", "Asia/Bahrain", "ar", 1), ("OM", "Oman", "OMR", "OMR", "Asia/Muscat", "ar", 1),
    ("JO", "Jordan", "JOD", "JD", "Asia/Amman", "ar", 1), ("LB", "Lebanon", "USD", "$", "Asia/Beirut", "ar", 1),
    ("IL", "Israel", "ILS", "₪", "Asia/Jerusalem", "he", 1), ("AZ", "Azerbaijan", "AZN", "₼", "Asia/Baku", "az", 1),
    # Asya - Pasifik
    ("IN", "India", "INR", "₹", "Asia/Kolkata", "en", 10), ("PK", "Pakistan", "PKR", "Rs", "Asia/Karachi", "en", 100),
    ("BD", "Bangladesh", "BDT", "৳", "Asia/Dhaka", "en", 10), ("LK", "Sri Lanka", "LKR", "Rs", "Asia/Colombo", "en", 100),
    ("ID", "Indonesia", "IDR", "Rp", "Asia/Jakarta", "id", 1000), ("MY", "Malaysia", "MYR", "RM", "Asia/Kuala_Lumpur", "en", 1),
    ("SG", "Singapore", "SGD", "S$", "Asia/Singapore", "en", 1), ("PH", "Philippines", "PHP", "₱", "Asia/Manila", "en", 10),
    ("TH", "Thailand", "THB", "฿", "Asia/Bangkok", "th", 10), ("VN", "Vietnam", "VND", "₫", "Asia/Ho_Chi_Minh", "vi", 1000),
    ("JP", "Japan", "JPY", "¥", "Asia/Tokyo", "ja", 100), ("KR", "South Korea", "KRW", "₩", "Asia/Seoul", "ko", 1000),
    ("CN", "China", "CNY", "¥", "Asia/Shanghai", "zh", 1), ("HK", "Hong Kong", "HKD", "HK$", "Asia/Hong_Kong", "en", 1),
    ("AU", "Australia", "AUD", "A$", "Australia/Sydney", "en", 1), ("NZ", "New Zealand", "NZD", "NZ$", "Pacific/Auckland", "en", 1),
    ("KZ", "Kazakhstan", "KZT", "₸", "Asia/Almaty", "ru", 100),
]

ULKELER = {k: {"kod": k, "ad": a, "para": p, "sembol": s, "saat_dilimi": tz, "dil": d, "yuvarlama": y}
           for k, a, p, s, tz, d, y in U}

DILLER = {"en": "English", "fr": "French", "es": "Spanish", "pt": "Portuguese", "de": "German", "it": "Italian",
          "nl": "Dutch", "tr": "Turkish", "ar": "Arabic", "sv": "Swedish", "no": "Norwegian", "da": "Danish",
          "fi": "Finnish", "pl": "Polish", "cs": "Czech", "ro": "Romanian", "el": "Greek", "hu": "Hungarian",
          "uk": "Ukrainian", "ru": "Russian", "sr": "Serbian", "he": "Hebrew", "az": "Azerbaijani", "id": "Indonesian",
          "th": "Thai", "vi": "Vietnamese", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "hi": "Hindi",
          "sw": "Swahili", "ha": "Hausa", "yo": "Yoruba", "ms": "Malay", "tl": "Filipino"}


def al(kod):
    return ULKELER.get((kod or "").upper())


def ada_gore(ad):
    a = (ad or "").strip().lower()
    return next((u for u in ULKELER.values() if u["ad"].lower() == a), None)


def liste():
    """Panel icin alfabetik liste."""
    return sorted(ULKELER.values(), key=lambda u: u["ad"])


def dil_adi(kod):
    return DILLER.get((kod or "en").split("-")[0].lower(), "English")
