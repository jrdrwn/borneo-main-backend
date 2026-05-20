from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

new_fetch_for_qa = r'''def fetch_for_qa(entities: dict):
    if entities.get("destinasi"):
        cypher = f"""
        MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
        MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
        WHERE toLower(d.nama) CONTAINS toLower($destinasi)
        {destination_return_clause()}
        ORDER BY coalesce(toFloatOrNull(toString(d.rating)), 0) DESC
        LIMIT 50
        """
        return run_query(cypher, {"destinasi": entities["destinasi"]}), cypher

    wilayah = entities.get("wilayah") or entities.get("provinsi")
    kategori = entities.get("kategori")
    keywords = entities.get("keywords") or []

    # Query utama: kategori dan wilayah wajib tetap dihormati.
    cypher = f"""
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    WHERE ($kategori IS NULL OR toLower(toString(k.nama)) CONTAINS toLower($kategori))
      AND ($wilayah IS NULL OR toLower(toString(w.nama)) CONTAINS toLower($wilayah))
      AND (size($keywords) = 0 OR any(keyword IN $keywords WHERE
           toLower(coalesce(toString(d.nama), "")) CONTAINS toLower(keyword)
        OR toLower(coalesce(toString(d.alamat), "")) CONTAINS toLower(keyword)
        OR toLower(coalesce(toString(d.teks_nlp), "")) CONTAINS toLower(keyword)))
    {destination_return_clause()}
    ORDER BY coalesce(toFloatOrNull(toString(d.rating)), 0) DESC,
             coalesce(toIntegerOrNull(toString(d.jumlah_ulasan)), 0) DESC
    LIMIT 50
    """

    params = {
        "kategori": kategori,
        "wilayah": wilayah,
        "keywords": keywords
    }

    rows = run_query(cypher, params)

    # Fallback 1: jika keyword terlalu membatasi, hapus keyword,
    # tetapi kategori dan wilayah tetap wajib.
    if not rows and (kategori or wilayah):
        params["keywords"] = []
        rows = run_query(cypher, params)

    return rows, cypher
'''

new_rank = r'''def rank(question: str, items: list[dict], top_k=6):
    if not items:
        return []

    expected_category = None
    expected_region = None

    try:
        expected_category = infer_category_from_keywords(question)
    except Exception:
        expected_category = None

    try:
        expected_region = infer_region_from_keywords(question)
    except Exception:
        expected_region = None

    def safe_float(value, default=0.0):
        try:
            if value is None:
                return default
            value = float(value)
            if math.isnan(value) or math.isinf(value):
                return default
            return value
        except Exception:
            return default

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [question] + [doc(i) for i in items]
        matrix = TfidfVectorizer().fit_transform(corpus)
        sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten().tolist()

        ranked = []
        for item, sim in zip(items, sims):
            rating = safe_float(item.get("rating")) / 5
            review_factor = min(safe_float(item.get("jumlah_ulasan")) / 500.0, 1.0)

            category_match = 0.0
            region_match = 0.0

            if expected_category and normalize(item.get("kategori") or "") == normalize(expected_category):
                category_match = 1.0

            if expected_region and normalize(item.get("wilayah") or "") == normalize(expected_region):
                region_match = 1.0

            score = (
                (sim * 0.45)
                + (category_match * 0.25)
                + (region_match * 0.20)
                + (rating * 0.07)
                + (review_factor * 0.03)
            )

            ranked.append({**item, "relevance_score": round(score, 4)})

        return sorted(ranked, key=lambda x: x["relevance_score"], reverse=True)[:top_k]

    except Exception:
        q = set(tokens(question))
        ranked = []

        for item in items:
            d_tokens = set(tokens(doc(item)))
            base = len(q.intersection(d_tokens)) / max(len(q), 1)

            category_match = 0.0
            region_match = 0.0

            if expected_category and normalize(item.get("kategori") or "") == normalize(expected_category):
                category_match = 1.0

            if expected_region and normalize(item.get("wilayah") or "") == normalize(expected_region):
                region_match = 1.0

            rating = safe_float(item.get("rating")) / 5

            score = (
                (base * 0.45)
                + (category_match * 0.25)
                + (region_match * 0.20)
                + (rating * 0.10)
            )

            ranked.append({**item, "relevance_score": round(score, 4)})

        return sorted(ranked, key=lambda x: x["relevance_score"], reverse=True)[:top_k]
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

    names = [x["nama"] for x in recommendations if x.get("nama")]

    label = "destinasi wisata"
    if kategori:
        label = kategori

    lokasi_text = f" di {wilayah}" if wilayah else ""
    keyword_text = ""

    clean_keywords = [
        k for k in entities.get("keywords", [])
        if normalize(k) not in {
            "makan", "tempat", "populer", "bagus", "terbaik",
            "rekomendasi", "rekomendasikan", "cari", "carikan"
        }
    ]

    if clean_keywords:
        keyword_text = f" dengan kata kunci {', '.join(clean_keywords[:3])}"

    answer = f"Berikut rekomendasi {label}{lokasi_text}{keyword_text}: {', '.join(names)}."

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
        "rating", "tinggi", "makan", "makanan", "kuliner", "tempat makan",
        "warung", "restoran", "restaurant", "rumah", "rumah makan", "kafe",
        "cafe"
    }

    region_words = set()
    for region, aliases in REGION_KEYWORD_MAP.items():
        region_words.add(normalize(region))
        for alias in aliases:
            region_words.add(normalize(alias))

    category_words = set()
    for category, aliases in CATEGORY_KEYWORD_MAP.items():
        category_words.add(normalize(category))
        for alias in aliases:
            category_words.add(normalize(alias))

    entities["keywords"] = [
        k for k in entities.get("keywords", [])
        if normalize(k) not in noisy_keywords
        and normalize(k) not in region_words
        and normalize(k) not in category_words
    ][:8]

    return entities
'''

def replace_func(text, name, new_code):
    pattern = rf"def {name}\(.*?\n(?=def |@app\.|# =+|\Z)"
    if re.search(pattern, text, flags=re.S):
        return re.sub(pattern, new_code + "\n\n", text, flags=re.S)
    raise SystemExit(f"Fungsi {name} tidak ditemukan.")

text = replace_func(text, "fetch_for_qa", new_fetch_for_qa)
text = replace_func(text, "rank", new_rank)
text = replace_func(text, "generate_answer", new_generate_answer)
text = replace_func(text, "strengthen_entities_with_natural_keywords", new_strengthen)

path.write_text(text, encoding="utf-8")
print("Relevansi rekomendasi kategori/wilayah berhasil diperbaiki.")
