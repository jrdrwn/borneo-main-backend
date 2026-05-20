from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

nearby_code = r'''
def is_nearby_question(question):
    q = normalize(question)
    nearby_words = [
        "sekitar", "di sekitar", "dekat", "terdekat", "sekitaran",
        "tidak jauh", "paling dekat", "nearby"
    ]
    return any(word in q for word in nearby_words)

def get_nearby_recommendations(anchor_id, kategori=None, limit=6):
    query = """
    MATCH (anchor:Destinasi {id: $anchor_id})
    OPTIONAL MATCH (anchor)-[:BERLOKASI_DI]->(anchor_w:Wilayah)

    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)

    WHERE d.id <> anchor.id
      AND ($kategori IS NULL OR toLower(toString(k.nama)) CONTAINS toLower($kategori))

    WITH anchor, anchor_w, d, k, w,
      CASE
        WHEN anchor.latitude IS NOT NULL
          AND anchor.longitude IS NOT NULL
          AND d.latitude IS NOT NULL
          AND d.longitude IS NOT NULL
        THEN point.distance(
          point({latitude: toFloat(anchor.latitude), longitude: toFloat(anchor.longitude)}),
          point({latitude: toFloat(d.latitude), longitude: toFloat(d.longitude)})
        )
        ELSE NULL
      END AS jarak_meter

    WHERE jarak_meter IS NOT NULL
       OR w.nama = anchor_w.nama

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
      d.main_image AS main_image,
      d.gallery_images AS gallery_images,
      k.nama AS kategori,
      w.nama AS wilayah,
      w.provinsi AS provinsi,
      jarak_meter AS jarak_meter

    ORDER BY
      CASE WHEN jarak_meter IS NULL THEN 1 ELSE 0 END ASC,
      jarak_meter ASC,
      d.rating DESC,
      d.jumlah_ulasan DESC

    LIMIT $limit
    """

    return run_query(query, {
        "anchor_id": anchor_id,
        "kategori": kategori,
        "limit": limit
    })

def generate_nearby_answer(question, anchor_destination, kategori, recommendations):
    anchor_name = anchor_destination.get("nama") or "destinasi tersebut"
    kategori_text = kategori or "wisata"

    if not recommendations:
        return (
            f"Maaf, saya belum menemukan rekomendasi {kategori_text} di sekitar {anchor_name} "
            f"berdasarkan data Knowledge Graph yang tersedia."
        )

    names = [item.get("nama") for item in recommendations if item.get("nama")]
    first = recommendations[0]

    answer = (
        f"Berikut rekomendasi {kategori_text} di sekitar {anchor_name}: "
        f"{', '.join(names)}."
    )

    if first:
        answer += f" Rekomendasi paling relevan adalah {first.get('nama')}"

        if first.get("wilayah"):
            answer += f" di wilayah {first.get('wilayah')}"

        if first.get("alamat"):
            answer += f", beralamat di {first.get('alamat')}"

        if first.get("jarak_meter") is not None:
            try:
                jarak_km = float(first.get("jarak_meter")) / 1000
                answer += f", dengan perkiraan jarak sekitar {jarak_km:.1f} km dari {anchor_name}"
            except Exception:
                pass

        answer += "."

    return answer
'''

if "def is_nearby_question(" not in text:
    text = text.replace('@app.post("/api/qa/ask")', nearby_code + '\n\n@app.post("/api/qa/ask")')

old_block = r'''    # 1. Jika user menyebut nama destinasi, jawab spesifik dulu.
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
        }'''

new_block = r'''    # 1. Jika user menyebut nama destinasi, cek dulu apakah konteksnya rekomendasi sekitar.
    entities = extract_entities(question)
    direct_destination = find_destination_in_question(question)
    intent = entities.get("intent") or detect_intent(question)

    if direct_destination and intent == "recommendation" and is_nearby_question(question):
        nearby_recommendations = get_nearby_recommendations(
            anchor_id=direct_destination.get("id"),
            kategori=entities.get("kategori"),
            limit=6
        )

        answer = generate_nearby_answer(
            question=question,
            anchor_destination=direct_destination,
            kategori=entities.get("kategori"),
            recommendations=nearby_recommendations
        )

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "entities": {
                "intent": "nearby_recommendation",
                "kategori": entities.get("kategori"),
                "wilayah": direct_destination.get("wilayah"),
                "provinsi": direct_destination.get("provinsi"),
                "destinasi": direct_destination.get("nama"),
                "keywords": entities.get("keywords", [])
            },
            "recommendations": nearby_recommendations,
            "cypher_used": "MATCH anchor destination, then find nearby destinations by category using coordinates or same wilayah"
        }

    # 2. Jika user menyebut nama destinasi tanpa konteks rekomendasi sekitar, jawab spesifik destinasi itu.
    if direct_destination:
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
        }'''

if old_block in text:
    text = text.replace(old_block, new_block)
else:
    print("Blok lama tidak ditemukan persis. Akan coba patch manual dengan regex.")
    text = re.sub(
        r'    # 1\. Jika user menyebut nama destinasi, jawab spesifik dulu\..*?        \}',
        new_block,
        text,
        count=1,
        flags=re.S
    )

# Karena entities sudah dibuat di atas, hapus duplikasi entities di alur rekomendasi bawah jika ada
text = text.replace(
    '''    # 2. Jika tidak menyebut nama destinasi, gunakan alur rekomendasi.
    entities = extract_entities(question)

    destinations, cypher = get_destinations_for_qa(''',
    '''    # 3. Jika tidak menyebut nama destinasi, gunakan alur rekomendasi umum.
    destinations, cypher = get_destinations_for_qa('''
)

path.write_text(text, encoding="utf-8")
print("AI nearby recommendation berhasil dipasang.")
