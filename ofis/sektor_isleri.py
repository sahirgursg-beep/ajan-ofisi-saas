"""Kayit formundaki "Ne yapiyorsunuz?" onerileri: her sektorde isletmelerin sundugu urun/hizmetler.

Musteri onerilerden secer ya da kendisi yazar; secimler profil.isletme.hizmetler'e gider ve tum ajanlarin
istemlerinde "isletmenin sunduklari" olarak kullanilir. Bu modul saf veridir (web servisi de ice aktarir).
"""
import re

from .sektor_bilgi import SEKTORLER

ISLER = {
    "mobilya": ["Sofas & living room sets", "Beds & bedroom furniture", "Dining tables & chairs", "Wardrobes",
                "Kitchen cabinets", "Office furniture", "Home decor & accessories", "Curtains & blinds",
                "Custom-made furniture", "Interior design service", "Outdoor furniture", "Delivery & installation"],
    "emlak": ["Houses for sale", "Apartments for rent", "Land & plots", "Short-let apartments",
              "Commercial property", "Property management", "Off-plan estates", "Property valuation",
              "Mortgage guidance", "Inspection tours"],
    "insaat": ["Building construction", "Renovation & remodelling", "Roofing", "Tiles & flooring",
               "Plumbing", "Electrical works", "Painting & finishing", "Building materials supply",
               "Architectural drawings", "POP ceilings", "Interlocking & paving", "Project management"],
    "temizlik": ["Home cleaning", "Office cleaning", "Post-construction cleaning", "Laundry & dry cleaning",
                 "Fumigation & pest control", "Carpet & upholstery cleaning", "Facility management",
                 "Handyman repairs", "Car wash", "Pickup & delivery laundry"],
    "restoran": ["Local & traditional dishes", "Fast food & grills", "Finger food & catering", "Cakes & pastries",
                 "Coffee & breakfast", "Wraps, burgers & street food", "Seafood", "Food delivery", "Event catering",
                 "Lunch packs for offices", "Drinks & mocktails", "Private dining"],
    "otel": ["Hotel rooms", "Short-let apartments", "Event halls", "Restaurant & bar", "Pool & lounge",
             "Airport pickup", "Conference rooms", "Weekend packages", "Long-stay rates"],
    "etkinlik": ["Wedding planning", "Event decoration", "Event hall rental", "Catering", "DJ & MC",
                 "Photography & video", "Ushering", "Rentals (chairs, tents, lights)", "Birthday parties",
                 "Corporate events", "Cakes & desserts"],
    "moda": ["Women's clothing", "Men's clothing", "Traditional & cultural wear", "Bespoke tailoring",
             "Shoes", "Bags", "Jewellery & accessories", "Fabrics & traditional attire", "Kids' clothing",
             "Bridal & occasion wear", "Thrift / pre-loved", "Online orders & delivery"],
    "guzellik": ["Hair styling & braids", "Barbing", "Wigs & hair extensions", "Nails", "Makeup",
                 "Lashes & brows", "Skincare & facials", "Spa & massage", "Beauty products", "Training academy",
                 "Bridal glam", "Home service"],
    "saglik": ["General consultation", "Dental care", "Eye care & glasses", "Pharmacy & drugs",
               "Laboratory tests", "Maternity & antenatal", "Physiotherapy", "Home care / nursing",
               "Health checks & screening", "Telemedicine", "Wellness & nutrition advice"],
    "spor": ["Gym membership", "Personal training", "Group classes", "Weight-loss programmes", "Yoga & pilates",
             "Martial arts", "Sports academy for kids", "Supplements", "Sportswear & equipment",
             "Online coaching"],
    "egitim": ["Primary school", "Secondary school", "Nursery & creche", "Tutoring & lessons",
               "Exam preparation", "Professional courses", "Coding & tech training",
               "Language classes", "Vocational skills", "Online courses", "Study abroad advice"],
    "market": ["Groceries", "Fresh produce", "Meat & fish", "Beverages", "Household items", "Toiletries",
               "Baby products", "Bulk / wholesale", "Home delivery", "Bakery"],
    "elektronik": ["Phones & tablets", "Laptops & computers", "Accessories", "Home appliances", "TVs & audio",
                   "Phone & laptop repair", "Solar & power banks", "Gaming", "CCTV & security",
                   "Pay in instalments"],
    "otomotiv": ["Car sales", "Used cars", "Auto parts", "Mechanic & repairs", "Car rental",
                 "Car wash & detailing", "Tyres & batteries", "Car tracking", "Car paint & body work",
                 "Driving school"],
    "tarim": ["Fresh farm produce", "Poultry & eggs", "Fish farming", "Livestock", "Processed foods",
              "Farm inputs & fertiliser", "Farm equipment", "Agro consulting", "Export", "Farm tours"],
    "finans": ["Savings & investments", "Loans", "Insurance", "Payments & transfers", "Business accounts",
               "Currency exchange", "Accounting & tax", "Financial advice", "Savings groups & cooperatives"],
    "hukuk": ["Legal advice", "Property & land law", "Company registration", "Contracts",
              "Litigation", "Immigration & visas", "Business consulting", "HR & recruitment", "Audit & tax",
              "Training & workshops"],
    "teknoloji": ["Website design", "App development", "Software (SaaS)", "IT support", "Cloud & hosting",
                  "Cybersecurity", "Digital marketing", "Social media management", "Data & AI services",
                  "Tech training", "Hardware supply", "Automation"],
    "lojistik": ["Courier & dispatch", "Interstate haulage", "International shipping", "Freight forwarding",
                 "Clearing & customs", "Warehousing", "Moving / relocation", "Travel agency & flights",
                 "Visa assistance", "Tours & holidays"],
    "uretim": ["Manufacturing", "Packaging", "Printing", "Plastics", "Food processing", "Chemicals & cleaning products",
               "Furniture production", "Metal fabrication", "Water production", "Private label / OEM"],
    "enerji": ["Solar installation", "Inverters & batteries", "Generators", "Electrical installation",
               "Gas supply", "Fuel supply", "Energy audits", "Maintenance contracts", "Street lights"],
    "fotograf": ["Portrait photography", "Wedding photography & video", "Product photography",
                 "Event coverage", "Studio rental", "Drone shots", "Video editing", "Brand content",
                 "Photography training"],
    "dini": ["Weekly services & prayers", "Study groups", "Youth programmes", "Outreach & charity",
             "Counselling", "Events & conventions", "Choir & music", "Live streams"],
    "stk": ["Community programmes", "Education support", "Health outreach", "Women & youth empowerment",
            "Donations & fundraising", "Volunteering", "Advocacy", "Relief work"],
    "evcil": ["Pet food", "Pet accessories", "Vet clinic", "Grooming", "Pet boarding", "Dog training",
              "Puppies & breeding", "Pet pharmacy"],
    "sanat_el": ["Paintings & art", "Handmade crafts", "Beads & jewellery", "Custom gifts", "Candles & soaps",
                 "Art classes", "Framing", "Pottery", "Workshops"],
    "icecek": ["Soft drinks", "Juices & smoothies", "Water", "Wines & spirits", "Local & traditional drinks",
               "Distribution / wholesale", "Event bar service", "Coffee & tea"],
    "eticaret": ["Online store", "Nationwide delivery", "Pay on delivery", "Gift boxes", "Pre-orders",
                 "Wholesale", "Subscriptions", "Marketplace seller"],
    "medya": ["Music", "Podcasts", "Video content", "Content creation", "Influencer marketing",
              "Event hosting / MC", "Radio / TV", "Talent management", "Social media management",
              "Advertising & PR"],
    "genel": ["Products", "Services", "Delivery", "Consultation", "Training", "Repairs & maintenance",
              "Wholesale", "Custom orders"],
}


def tahmin(metin):
    """Tek cumleden en yakin sektor anahtari ('genel' = bulunamadi). Yapay zekasiz, aninda."""
    m = (metin or "").lower()
    kelimeler = set(re.findall(r"[a-z]{4,}", m))
    tekil = {w[:-2] if w.endswith("es") else w[:-1] if w.endswith("s") else w for w in kelimeler} | kelimeler
    en_iyi, puan = "genel", 0
    for k, s in SEKTORLER.items():
        p = sum(len(w) for w in s["kelimeler"]
                if re.search(r"(?<![a-z])" + re.escape(w.lower()) + r"(?:s|es)?(?![a-z])", m))
        p += sum(len(w) for w in ISLER.get(k, []) if w.lower() in m)
        is_kelime = {x for i in ISLER.get(k, []) for x in re.findall(r"[a-z]{4,}", i.lower())}
        p += 0.5 * sum(len(w) for w in tekil & {x[:-1] if x.endswith("s") else x for x in is_kelime} | (tekil & is_kelime))
        if p > puan:
            en_iyi, puan = k, p
    return en_iyi


def liste():
    """Panel icin: [{anahtar, ad, isler}] (genel en sonda)."""
    out = [{"anahtar": k, "ad": v["ad"], "isler": ISLER.get(k, ISLER["genel"])} for k, v in SEKTORLER.items()
           if k != "genel"]
    out.sort(key=lambda x: x["ad"])
    return out + [{"anahtar": "genel", "ad": SEKTORLER["genel"]["ad"], "isler": ISLER["genel"]}]
