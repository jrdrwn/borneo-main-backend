from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

new_strengthen = r'''def strengthen_entities_with_natural_keywords(question: str, entities: dict):
    entities = dict(entities or {})

    natural_category = infer_category_from_keywords(question)
    natural_region = infer_region_from_keywords(question)

    if natural_category:
        entities["kategori"] = natural_category

    if natural_region:
        entities["wilayah"] = natural_region

    if infer_recommendation_intent(question):
        entities["intent"] = "recommendation"

    noisy_keywords = {
        "aku", "saya", "ingin", "mau", "pergi", "ke", "di", "sekitar",
        "dekat", "tempat", "yang", "bagus", "populer", "terbaik",
        "rekomendasikan", "rekomendasi", "carikan", "cari", "wisata",
        "rating", "tinggi", "makan", "makanan", "kuliner", "warung",
        "restoran", "restaurant", "rumah", "kafe", "cafe", "dan",
        "atau", "dengan", "untuk", "berikan", "tampilkan"
    }

    region_words = set()
    for region, aliases in REGION_KEYWORD_MAP.items():
        region_norm = normalize(region)
        region_words.add(region_norm)

        for token in region_norm.split():
            region_words.add(token)

        for alias in aliases:
            alias_norm = normalize(alias)
            region_words.add(alias_norm)

            for token in alias_norm.split():
                region_words.add(token)

    category_words = set()
    for category, aliases in CATEGORY_KEYWORD_MAP.items():
        category_norm = normalize(category)
        category_words.add(category_norm)

        for token in category_norm.split():
            category_words.add(token)

        for alias in aliases:
            alias_norm = normalize(alias)
            category_words.add(alias_norm)

            for token in alias_norm.split():
                category_words.add(token)

    cleaned_keywords = []

    for keyword in entities.get("keywords", []):
        keyword_norm = normalize(keyword)

        if not keyword_norm:
            continue

        if keyword_norm in noisy_keywords:
            continue

        if keyword_norm in region_words:
            continue

        if keyword_norm in category_words:
            continue

        cleaned_keywords.append(keyword)

    entities["keywords"] = cleaned_keywords[:8]

    return entities
'''

new_generate_answer = r'''def generate_answer(question: str, entities: dict, recommendations: list[dict]) -> str:
    kategori = entities.get("kategori")
    wilayah = entities.get("wilayah") or entities.get("provinsi")

    if not recommendations:
        if kategori and wilayah:
            return f"Maaf, saya belum menemukan data {kategori} di {wilayah} pada Knowledge Graph. Coba gunakan wilayah lain atau kata kunci yang lebih umum."
        if kategori:
            return f"Maaf, saya belum menemukan data {kategori} yang sesuai pada Knowledge Graph."
        if wilayah:
            return f"Maaf, saya belum menemukan destinasi yang sesuai di {wilayah} pada Knowledge Graph."
        return "Maaf, saya belum menemukan destinasi yang sesuai di Knowledge Graph. Coba tuliskan nama kategori, wilayah, atau destinasi dengan lebih spesifik."

    top = recommendations[0]
    intent = entities.get("intent")

    if intent == "location":
        return f"{top['nama']} berlokasi di {top.get('alamat') or top.get('wilayah')}. Destinasi ini termasuk kategori {top.get('kategori')} di wilayah {top.get('wilayah')}."

    if intent == "contact":
        return f"Informasi kontak {top['nama']}: telepon {top.get('telepon') or 'belum tersedia'}, website/link {top.get('website') or top.get('url') or 'belum tersedia'}."

    if intent == "rating":
        return f"{top['nama']} memiliki rating {top.get('rating') or 'belum tersedia'} dengan jumlah ulasan sekitar {top.get('jumlah_ulasan') or 0}."

    if intent == "detail" and entities.get("destinasi"):
        return f"{top['nama']} adalah destinasi kategori {top.get('kategori')} di {top.get('wilayah')}. Alamatnya {top.get('alamat')}. Ratingnya {top.get('rating') or 'belum tersedia'}."

    label = kategori or "destinasi wisata"
    lokasi_text = f" di {wilayah}" if wilayah else ""

    names = [x["nama"] for x in recommendations if x.get("nama")]
    names_text = ", ".join(names)

    answer = f"Berikut rekomendasi {label}{lokasi_text}: {names_text}."

    answer += f" Rekomendasi paling relevan adalah {top['nama']}"

    if top.get("wilayah"):
        answer += f" di {top.get('wilayah')}"

    if top.get("alamat"):
        answer += f", beralamat di {top.get('alamat')}"

    if top.get("rating"):
        answer += f", dengan rating {top.get('rating')}"

    answer += "."

    return answer
'''

def replace_func(source, name, replacement):
    pattern = rf"def {name}\(.*?\n(?=def |@app\.|# =+|\Z)"
    if re.search(pattern, source, flags=re.S):
        return re.sub(pattern, replacement + "\n\n", source, flags=re.S)
    raise SystemExit(f"Fungsi {name} tidak ditemukan di main.py")

text = replace_func(text, "strengthen_entities_with_natural_keywords", new_strengthen)
text = replace_func(text, "generate_answer", new_generate_answer)

path.write_text(text, encoding="utf-8")
print("Keyword wilayah/kategori sudah dibersihkan dan jawaban AI dirapikan.")
