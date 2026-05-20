from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

helper_code = r'''
def clean_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in ["", "-", "nan", "none", "null"]:
            return None
    return value

def get_all_destination_rows_for_matching():
    query = """
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    RETURN
      d.id AS id,
      d.nama AS nama,
      d.rating AS rating,
      d.jumlah_ulasan AS jumlah_ulasan,
      d.alamat AS alamat,
      d.telepon AS telepon,
      d.website AS website,
      d.url AS url,
      d.latitude AS latitude,
      d.longitude AS longitude,
      d.teks_nlp AS teks_nlp,
      k.nama AS kategori,
      w.nama AS wilayah,
      w.provinsi AS provinsi
    LIMIT 6000
    """
    return run_query(query)

def find_destination_in_question(question):
    q = normalize(question)
    q_tokens = set(q.split())

    best_item = None
    best_score = 0

    for item in get_all_destination_rows_for_matching():
        name = item.get("nama") or ""
        name_norm = normalize(name)
        name_tokens = [t for t in name_norm.split() if len(t) > 2]

        if not name_tokens:
            continue

        if name_norm in q:
            score = 1.0
        else:
            matched = [t for t in name_tokens if t in q_tokens]
            score = len(matched) / len(name_tokens)

        if score > best_score:
            best_score = score
            best_item = item

    if best_score >= 0.60:
        return best_item

    return None

def answer_specific_destination(question, item):
    intent = detect_intent(question)

    nama = clean_value(item.get("nama")) or "Destinasi ini"
    kategori = clean_value(item.get("kategori")) or "kategori belum tersedia"
    wilayah = clean_value(item.get("wilayah")) or "wilayah belum tersedia"
    provinsi = clean_value(item.get("provinsi")) or "Kalimantan Tengah"
    alamat = clean_value(item.get("alamat"))
    rating = clean_value(item.get("rating"))
    jumlah_ulasan = clean_value(item.get("jumlah_ulasan"))
    telepon = clean_value(item.get("telepon"))
    website = clean_value(item.get("website"))
    url = clean_value(item.get("url"))
    latitude = clean_value(item.get("latitude"))
    longitude = clean_value(item.get("longitude"))

    if intent == "location":
        answer = f"{nama} berlokasi di {alamat or wilayah}."
        answer += f" Destinasi ini termasuk {kategori} di wilayah {wilayah}, {provinsi}."
        if latitude is not None and longitude is not None:
            answer += f" Koordinatnya adalah latitude {latitude} dan longitude {longitude}."
        if url:
            answer += f" Link lokasi: {url}"
        return answer

    if intent == "rating":
        if rating is not None:
            answer = f"{nama} memiliki rating {rating}"
            if jumlah_ulasan is not None:
                answer += f" dari {jumlah_ulasan} ulasan"
            answer += "."
            return answer
        return f"Rating untuk {nama} belum tersedia pada data Knowledge Graph."

    if intent == "contact":
        bagian = []
        if telepon:
            bagian.append(f"telepon {telepon}")
        if website:
            bagian.append(f"website {website}")
        if url:
            bagian.append(f"link {url}")

        if bagian:
            return f"Kontak atau tautan untuk {nama}: " + ", ".join(bagian) + "."
        return f"Kontak untuk {nama} belum tersedia pada data Knowledge Graph."

    return (
        f"{nama} adalah destinasi {kategori} yang berada di {wilayah}, {provinsi}. "
        f"Alamatnya {alamat or 'belum tersedia'}."
    )
'''

# Pasang helper sebelum endpoint ask
if "def find_destination_in_question(" not in text:
    text = text.replace('@app.post("/api/qa/ask")', helper_code + '\n\n@app.post("/api/qa/ask")')

new_ask = r'''@app.post("/api/qa/ask")
def ask(payload: AskRequest):
    question = payload.question

    # 1. Jika user menyebut nama destinasi, jawab spesifik dulu.
    direct_destination = find_destination_in_question(question)
    if direct_destination:
        intent = detect_intent(question)
        answer = answer_specific_destination(question, direct_destination)

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "entities": {
                "intent": intent,
                "kategori": direct_destination.get("kategori"),
                "wilayah": direct_destination.get("wilayah"),
                "provinsi": direct_destination.get("provinsi"),
                "destinasi": direct_destination.get("nama"),
                "keywords": []
            },
            "recommendations": [direct_destination],
            "cypher_used": "MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori) MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah) RETURN d, k, w"
        }

    # 2. Jika tidak menyebut nama destinasi, gunakan alur rekomendasi.
    entities = extract_entities(question)

    destinations, cypher = get_destinations_for_qa(
        kategori=entities.get("kategori"),
        wilayah=entities.get("wilayah") or entities.get("provinsi"),
        destinasi=entities.get("destinasi"),
        keywords=entities.get("keywords", []),
        limit=50
    )

    if not destinations and (entities.get("kategori") or entities.get("wilayah")):
        destinations, cypher = get_destinations_for_qa(
            kategori=entities.get("kategori"),
            wilayah=entities.get("wilayah") or entities.get("provinsi"),
            destinasi=entities.get("destinasi"),
            keywords=[],
            limit=50
        )

    recommendations = rank_destinations(question, destinations, top_k=6)
    answer = generate_answer(question, entities, recommendations)

    return {
        "success": True,
        "question": question,
        "answer": answer,
        "entities": entities,
        "recommendations": recommendations,
        "cypher_used": cypher.strip() if cypher else None
    }
'''

text = re.sub(
    r'@app\.post\("/api/qa/ask"\)\s*def ask\(payload: AskRequest\):.*?\Z',
    new_ask,
    text,
    flags=re.S
)

path.write_text(text, encoding="utf-8")
print("AI/QA sudah diperbaiki agar menjawab spesifik berdasarkan nama destinasi.")
