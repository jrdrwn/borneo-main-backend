from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

chat_helpers = r'''
def detect_conversation_answer(question: str):
    q = normalize(question)

    if not q:
        return (
            "Silakan tuliskan pertanyaanmu. Kamu bisa bertanya tentang rekomendasi wisata, "
            "alamat destinasi, rating, kategori wisata, wilayah, atau wisata di sekitar lokasi tertentu."
        )

    greetings = {
        "halo", "hai", "hi", "hello", "helo", "pagi", "siang", "sore", "malam",
        "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
        "assalamualaikum", "assalamu alaikum"
    }

    thanks = [
        "terima kasih", "makasih", "thanks", "thank you", "tq", "sip", "oke makasih"
    ]

    help_words = [
        "kamu bisa apa", "bisa apa", "fitur", "fungsi kamu", "bantuan",
        "help", "panduan", "cara pakai", "contoh pertanyaan"
    ]

    identity_words = [
        "siapa kamu", "kamu siapa", "ini apa", "ai apa", "nama kamu"
    ]

    goodbye_words = [
        "bye", "dadah", "sampai jumpa", "sampai nanti"
    ]

    if q in greetings or (len(q.split()) <= 3 and any(word in q for word in greetings)):
        return (
            "Halo! Aku AI BorneoTrip. Aku bisa membantu mencari rekomendasi wisata "
            "di Kalimantan Tengah, menampilkan alamat destinasi, rating, kontak, "
            "serta rekomendasi wisata di sekitar tempat tertentu."
        )

    if any(word in q for word in thanks):
        return (
            "Sama-sama! Kalau butuh rekomendasi lain, kamu bisa tanya lagi, misalnya "
            "wisata alam di Barito Selatan atau kuliner di sekitar Taman Nasional Sebangau."
        )

    if any(word in q for word in goodbye_words):
        return "Baik, sampai jumpa! Semoga perjalanan wisatamu menyenangkan."

    if any(word in q for word in identity_words):
        return (
            "Aku AI BorneoTrip, asisten wisata berbasis Natural Language Processing dan "
            "Knowledge Graph Neo4j untuk membantu mencari informasi pariwisata Kalimantan Tengah."
        )

    if any(word in q for word in help_words):
        return (
            "Aku bisa membantu beberapa hal, misalnya:\\n"
            "1. Merekomendasikan wisata berdasarkan kategori dan wilayah.\\n"
            "2. Menjawab alamat atau lokasi destinasi.\\n"
            "3. Menampilkan rating dan jumlah ulasan destinasi.\\n"
            "4. Mencari wisata di sekitar destinasi tertentu.\\n"
            "5. Memberikan informasi kontak atau link lokasi jika tersedia.\\n\\n"
            "Contoh pertanyaan:\\n"
            "- Rekomendasikan wisata alam di Barito Selatan\\n"
            "- Di mana alamat Danau Sanggu?\\n"
            "- Berapa rating Batuah Agrowisata?\\n"
            "- Rekomendasikan wisata kuliner di sekitar Taman Nasional Sebangau"
        )

    return None


def expand_natural_language(question: str) -> str:
    q = question or ""
    q_norm = normalize(q)

    replacements = {
        "tempat makan": "Wisata Kuliner",
        "makanan": "Wisata Kuliner",
        "kulineran": "Wisata Kuliner",
        "restoran": "Wisata Kuliner",
        "warung": "Wisata Kuliner",
        "cafe": "Wisata Kuliner",
        "kafe": "Wisata Kuliner",

        "tempat alam": "Wisata Alam",
        "air terjun": "Wisata Alam",
        "hutan": "Wisata Alam",
        "danau": "Wisata Alam",

        "tempat sejarah": "Wisata Sejarah",
        "bersejarah": "Wisata Sejarah",
        "museum": "Wisata Sejarah",
        "monumen": "Wisata Sejarah",

        "tempat ibadah": "Wisata Religi",
        "religi": "Wisata Religi",
        "masjid": "Wisata Religi",
        "gereja": "Wisata Religi",

        "tempat belanja": "Wisata Belanja",
        "belanja": "Wisata Belanja",
        "pasar": "Wisata Belanja",

        "dekat": "sekitar",
        "terdekat": "sekitar",
        "paling dekat": "sekitar",
        "sekitaran": "sekitar",

        "bagus": "rating tinggi",
        "terbaik": "rating tinggi",
        "populer": "rating tinggi"
    }

    expanded = q
    for key, value in replacements.items():
        if key in q_norm:
            expanded += f" {value}"

    return expanded


def has_travel_signal(question: str) -> bool:
    q = normalize(question)
    signals = [
        "wisata", "destinasi", "rekomendasi", "rekomendasikan", "cari",
        "alamat", "lokasi", "rating", "ulasan", "kuliner", "makan",
        "alam", "sejarah", "budaya", "religi", "belanja", "edukasi",
        "sekitar", "dekat", "palangka", "barito", "sukamara",
        "pulang pisau", "katingan", "kotawaringin", "murung raya",
        "gunung mas", "seruyan", "lamandau", "kapuas", "danau", "taman"
    ]
    return any(signal in q for signal in signals)


def is_unclear_question(question: str, entities: dict) -> bool:
    if entities.get("kategori") or entities.get("wilayah") or entities.get("provinsi") or entities.get("destinasi"):
        return False

    if has_travel_signal(question):
        return False

    meaningful_tokens = tokens(question)
    return len(meaningful_tokens) <= 1


def fallback_unclear_answer():
    return (
        "Maaf, saya belum memahami pertanyaanmu. Coba tanyakan dengan lebih jelas, "
        "misalnya nama destinasi, kategori wisata, wilayah, alamat, rating, atau wisata di sekitar lokasi tertentu.\\n\\n"
        "Contoh:\\n"
        "- Rekomendasikan wisata alam di Barito Selatan\\n"
        "- Di mana alamat Danau Sanggu?\\n"
        "- Berapa rating Batuah Agrowisata?\\n"
        "- Rekomendasikan wisata kuliner di sekitar Taman Nasional Sebangau"
    )


def get_destinations_for_qa(kategori=None, wilayah=None, destinasi=None, keywords=None, limit=50):
    entities = {
        "kategori": kategori,
        "wilayah": wilayah,
        "provinsi": None,
        "destinasi": destinasi,
        "keywords": keywords or []
    }

    rows, cypher = fetch_for_qa(entities)

    if limit and isinstance(rows, list):
        rows = rows[:limit]

    return rows, cypher


def rank_destinations(question: str, items: list[dict], top_k=6):
    return rank(question, items, top_k=top_k)

'''

# Hapus helper lama jika ada agar tidak dobel
patterns_to_remove = [
    r'\ndef detect_conversation_answer\(question: str\):.*?\n(?=def expand_natural_language)',
    r'\ndef expand_natural_language\(question: str\) -> str:.*?\n(?=def has_travel_signal)',
    r'\ndef has_travel_signal\(question: str\) -> bool:.*?\n(?=def is_unclear_question)',
    r'\ndef is_unclear_question\(question: str, entities: dict\) -> bool:.*?\n(?=def fallback_unclear_answer)',
    r'\ndef fallback_unclear_answer\(\):.*?\n(?=def get_destinations_for_qa)',
    r'\ndef get_destinations_for_qa\(kategori=None, wilayah=None, destinasi=None, keywords=None, limit=50\):.*?\n(?=def rank_destinations)',
    r'\ndef rank_destinations\(question: str, items: list\[dict\], top_k=6\):.*?\n(?=@app\.post)'
]

for pattern in patterns_to_remove:
    text = re.sub(pattern, "\n", text, flags=re.S)

new_ask = r'''@app.post("/api/qa/ask")
def ask(payload: AskRequest):
    original_question = payload.question or ""

    # 1. Jawab percakapan umum dulu: halo, terima kasih, bantuan, identitas AI.
    conversation_answer = detect_conversation_answer(original_question)
    if conversation_answer:
        return {
            "success": True,
            "question": original_question,
            "answer": conversation_answer,
            "entities": {
                "intent": "conversation",
                "kategori": None,
                "wilayah": None,
                "provinsi": None,
                "destinasi": None,
                "keywords": []
            },
            "recommendations": [],
            "cypher_used": None
        }

    # 2. Perluas bahasa natural pengguna.
    question = expand_natural_language(original_question)

    entities = extract_entities(question)
    direct_destination = find_destination_in_question(question)
    intent = entities.get("intent") or detect_intent(question)

    # 3. Kalau pertanyaan terlalu tidak jelas, jangan dipaksa menjadi rekomendasi.
    if is_unclear_question(original_question, entities):
        return {
            "success": True,
            "question": original_question,
            "answer": fallback_unclear_answer(),
            "entities": {
                "intent": "fallback",
                "kategori": None,
                "wilayah": None,
                "provinsi": None,
                "destinasi": None,
                "keywords": tokens(original_question)
            },
            "recommendations": [],
            "cypher_used": None
        }

    # 4. Jika user menyebut nama destinasi dan konteksnya rekomendasi sekitar.
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
            "question": original_question,
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

    # 5. Jika user menyebut nama destinasi tanpa konteks rekomendasi sekitar.
    if direct_destination:
        answer = answer_specific_destination(question, direct_destination)

        return {
            "success": True,
            "question": original_question,
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

    # 6. Jika tidak menyebut nama destinasi, gunakan alur rekomendasi umum.
    destinations, cypher = get_destinations_for_qa(
        kategori=entities.get("kategori"),
        wilayah=entities.get("wilayah") or entities.get("provinsi"),
        destinasi=entities.get("destinasi"),
        keywords=entities.get("keywords", []),
        limit=50
    )

    if not destinations and (entities.get("kategori") or entities.get("wilayah") or entities.get("provinsi")):
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
        "question": original_question,
        "answer": answer,
        "entities": entities,
        "recommendations": recommendations,
        "cypher_used": cypher.strip() if cypher else None
    }
'''

# Pasang helper tepat sebelum endpoint ask
text = re.sub(
    r'@app\.post\("/api/qa/ask"\)\s*def ask\(payload: AskRequest\):.*?\Z',
    chat_helpers + "\n\n" + new_ask,
    text,
    flags=re.S
)

path.write_text(text, encoding="utf-8")
print("AI chat layer berhasil diperbaiki. Input seperti 'halo' tidak akan dianggap keyword wisata lagi.")
