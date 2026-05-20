from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")

helper_code = r'''
# =========================
# CATEGORY SYNONYM & NATURAL KEYWORD LAYER
# =========================

CATEGORY_KEYWORD_MAP = {
    "Wisata Kuliner": [
        "tempat makan", "makan", "makanan", "kuliner", "kulineran",
        "warung", "restoran", "restaurant", "rumah makan", "cafe", "kafe",
        "kopi", "bakso", "soto", "sate", "nasi", "mie", "minuman",
        "jajanan", "oleh oleh makanan"
    ],
    "Wisata Alam": [
        "pantai", "hutan", "taman", "taman nasional", "danau", "air terjun",
        "bukit", "gunung", "sungai", "pulau", "riam", "goa", "gua",
        "pemandian", "agrowisata", "alam", "view", "pemandangan"
    ],
    "Wisata Sejarah": [
        "sejarah", "bersejarah", "museum", "monumen", "tugu", "situs",
        "makam", "keramat", "candi", "benteng", "betang", "balai",
        "peninggalan", "pahlawan"
    ],
    "Wisata Religi": [
        "religi", "ibadah", "masjid", "gereja", "pura", "vihara",
        "kelenteng", "ziarah", "tempat ibadah"
    ],
    "Wisata Budaya": [
        "budaya", "adat", "tradisi", "sanggar", "rumah adat",
        "kesenian", "festival budaya"
    ],
    "Wisata Belanja": [
        "belanja", "pasar", "mall", "pusat belanja", "toko",
        "oleh oleh", "souvenir"
    ],
    "Wisata Edukasi": [
        "edukasi", "pendidikan", "belajar", "pengetahuan",
        "wisata edukasi"
    ],
    "Akomodasi": [
        "hotel", "penginapan", "losmen", "homestay", "resort",
        "tempat menginap", "menginap"
    ]
}


REGION_KEYWORD_MAP = {
    "Palangka Raya": ["palangka raya", "palangkaraya", "palangka"],
    "Barito Selatan": ["barito selatan", "barsel", "buntok"],
    "Barito Timur": ["barito timur", "bartim", "tamiang layang"],
    "Barito Utara": ["barito utara", "barut", "muara teweh"],
    "Gunung Mas": ["gunung mas", "kuala kurun"],
    "Kapuas": ["kapuas", "kuala kapuas"],
    "Katingan": ["katingan", "kasongan"],
    "Kotawaringin Barat": ["kotawaringin barat", "kobar", "pangkalan bun"],
    "Kotawaringin Timur": ["kotawaringin timur", "kotim", "sampit"],
    "Lamandau": ["lamandau", "nanga bulik"],
    "Murung Raya": ["murung raya", "puruk cahu"],
    "Pulang Pisau": ["pulang pisau", "pulpis"],
    "Seruyan": ["seruyan", "kuala pembuang"],
    "Sukamara": ["sukamara"]
}


def contains_phrase(q: str, phrase: str) -> bool:
    q_pad = f" {normalize(q)} "
    phrase_pad = f" {normalize(phrase)} "
    return phrase_pad in q_pad


def infer_category_from_keywords(question: str):
    q = normalize(question)

    # Prioritas penting: kalau user bilang "tempat makan di sekitar taman nasional",
    # target kategori tetap kuliner, bukan wisata alam.
    category_priority = [
        "Wisata Kuliner",
        "Akomodasi",
        "Wisata Alam",
        "Wisata Sejarah",
        "Wisata Religi",
        "Wisata Budaya",
        "Wisata Belanja",
        "Wisata Edukasi"
    ]

    for category in category_priority:
        keywords = CATEGORY_KEYWORD_MAP.get(category, [])
        for keyword in keywords:
            if contains_phrase(q, keyword):
                return category

    return None


def infer_region_from_keywords(question: str):
    q = normalize(question)

    for region, keywords in REGION_KEYWORD_MAP.items():
        for keyword in keywords:
            if contains_phrase(q, keyword):
                return region

    return None


def infer_recommendation_intent(question: str) -> bool:
    q = normalize(question)

    recommendation_words = [
        "rekomendasi", "rekomendasikan", "carikan", "cari", "kasih",
        "tampilkan", "apa saja", "daftar", "pilihan", "yang bagus",
        "terbaik", "populer", "cocok", "ingin ke", "mau ke"
    ]

    if any(word in q for word in recommendation_words):
        return True

    if infer_category_from_keywords(question):
        return True

    return False


def strengthen_entities_with_natural_keywords(question: str, entities: dict):
    entities = dict(entities or {})

    natural_category = infer_category_from_keywords(question)
    natural_region = infer_region_from_keywords(question)

    if natural_category:
        entities["kategori"] = natural_category

    if natural_region:
        entities["wilayah"] = natural_region

    if infer_recommendation_intent(question):
        entities["intent"] = "recommendation"

    # Bersihkan keyword umum agar tidak mengganggu pencarian Neo4j.
    noisy_keywords = {
        "aku", "saya", "ingin", "mau", "pergi", "ke", "di", "sekitar",
        "dekat", "tempat", "yang", "bagus", "populer", "rekomendasikan",
        "rekomendasi", "carikan", "cari", "wisata", "rating", "tinggi"
    }

    entities["keywords"] = [
        k for k in entities.get("keywords", [])
        if normalize(k) not in noisy_keywords
    ][:8]

    return entities


def should_ignore_direct_destination(question: str, direct_destination, entities: dict, intent: str) -> bool:
    if not direct_destination:
        return False

    name = normalize(direct_destination.get("nama") or "")
    q = normalize(question)

    generic_destination_names = {
        "wisata", "alam", "kuliner", "sejarah", "budaya", "religi",
        "edukasi", "belanja", "tempat", "makan", "destinasi",
        "pariwisata", "objek wisata"
    }

    if name in generic_destination_names:
        return True

    # Kalau user meminta rekomendasi kategori/wilayah, jangan mudah menganggap
    # kata umum sebagai nama destinasi.
    if intent == "recommendation" and (entities.get("kategori") or entities.get("wilayah") or entities.get("provinsi")):
        name_tokens = name.split()

        if len(name_tokens) <= 1:
            return True

        # Jika nama destinasi tidak disebut persis dalam pertanyaan,
        # anggap bukan direct destination.
        if name not in q:
            return True

    return False

'''

if "def infer_category_from_keywords(" not in text:
    text = text.replace('@app.post("/api/qa/ask")', helper_code + "\n\n@app.post(\"/api/qa/ask\")", 1)

old_block = '''    # 2. Perluas bahasa natural pengguna.
    question = expand_natural_language(original_question)

    entities = extract_entities(question)
    direct_destination = find_destination_in_question(question)
    intent = entities.get("intent") or detect_intent(question)
'''

new_block = '''    # 2. Perluas bahasa natural pengguna dan perkuat entity dengan kamus sinonim.
    question = expand_natural_language(original_question)

    entities = extract_entities(question)
    entities = strengthen_entities_with_natural_keywords(original_question, entities)

    direct_destination = find_destination_in_question(question)
    intent = entities.get("intent") or detect_intent(question)

    if should_ignore_direct_destination(original_question, direct_destination, entities, intent):
        direct_destination = None
'''

if old_block in text:
    text = text.replace(old_block, new_block)
else:
    print("Blok ask lama tidak ditemukan persis. Cek manual bagian setelah expand_natural_language.")

path.write_text(text, encoding="utf-8")
print("Keyword kategori dan filter direct destination berhasil ditambahkan.")
