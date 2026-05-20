import os
import math
import re
from difflib import SequenceMatcher
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import BaseModel

load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

app = FastAPI(
    title="BorneoTrip Neo4j API",
    description="Backend web utama BorneoTrip berbasis FastAPI, NLP sederhana, TF-IDF ranking, dan Neo4j Knowledge Graph.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str


def is_invalid_text(value):
    if value is None:
        return True

    if not isinstance(value, str):
        return False

    text = value.strip().lower()

    return text in [
        "",
        "-",
        "nan",
        "none",
        "null",
        "undefined",
        "inf",
        "infinity",
        "-inf",
        "-infinity"
    ]


def make_json_safe(value):
    """Membersihkan data dari Neo4j agar aman dikirim sebagai JSON ke frontend.

    Fungsi ini mengubah nilai kosong/tidak valid seperti `nan`, `null`, `-`,
    `inf`, dan string kosong menjadi None. Dengan begitu, frontend dapat
    menampilkan fallback seperti "Belum ada informasi" dan tidak lagi
    menampilkan teks `nan`.
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, str):
        return None if is_invalid_text(value) else value.strip()

    if isinstance(value, dict):
        return {key: make_json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        cleaned_list = [make_json_safe(item) for item in value]
        return [item for item in cleaned_list if item is not None]

    return value

def run_query(query, params=None):
    with driver.session(database=NEO4J_DATABASE) as session:
        rows = [record.data() for record in session.run(query, params or {})]
    return make_json_safe(rows)

def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("kal-teng", "kalimantan tengah").replace("kalteng", "kalimantan tengah")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


STOPWORDS = {
    "yang", "di", "ke", "dari", "dan", "atau", "untuk", "dengan",
    "saya", "aku", "ingin", "mau", "ada", "apa", "aja", "saja",
    "tolong", "carikan", "rekomendasikan", "rekomendasi", "tempat",
    "wisata", "daerah", "kabupaten", "kota", "provinsi", "kalimantan",
    "tengah", "dong", "berikan", "tampilkan", "cari", "punya",
    "memiliki", "berapa", "rating", "nilai", "ulasan", "alamat",
    "lokasi", "dimana", "mana", "danau", "taman", "nasional"
}

def tokens(text: str):
    return [t for t in normalize(text).split() if t not in STOPWORDS and len(t) > 2]

INTENT_KEYWORDS = {
    "recommendation": [
        "rekomendasi", "rekomendasikan", "carikan", "cari", "tampilkan",
        "apa saja", "daftar", "cocok", "terbaik", "pilihan", "wisata"
    ],
    "location": [
        "alamat", "lokasi", "dimana", "di mana", "letak", "maps", "map"
    ],
    "contact": [
        "telepon", "nomor", "kontak", "website", "url", "link"
    ],
    "rating": [
        "rating", "ulasan", "review", "nilai", "bintang"
    ],
    "detail": [
        "detail", "informasi", "deskripsi", "jelaskan", "tentang"
    ]
}

def detect_intent(question: str) -> str:
    q = normalize(question)
    for intent, words in INTENT_KEYWORDS.items():
        if any(w in q for w in words):
            return intent
    return "recommendation"
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()
def best_match(question: str, candidates: list[str], threshold: float = 0.70):
    q = normalize(question)
    best = None
    score = 0.0
    for item in candidates:
        c = normalize(item)
        if c and c in q:
            return item
        s = similarity(q, c)
        if s > score:
            score = s
            best = item
    return best if score >= threshold else None

def list_categories():
    rows = run_query("MATCH (k:Kategori) RETURN k.nama AS nama ORDER BY k.nama ASC")
    return [r["nama"] for r in rows if r.get("nama")]

def list_regions():
    return run_query("MATCH (w:Wilayah) RETURN w.nama AS nama, w.provinsi AS provinsi ORDER BY w.nama ASC")

def list_destination_names():
    rows = run_query("MATCH (d:Destinasi) RETURN d.nama AS nama ORDER BY d.nama ASC")
    return [r["nama"] for r in rows if r.get("nama")]

def destination_return_clause():
    return """
    RETURN d.id AS id,
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
           d.deskripsi AS deskripsi,
           d.description AS description,
           d.short_description AS short_description,

           d.main_image AS main_image,
           d.gallery_images AS gallery_images,
           d.google_photo_names AS google_photo_names,
           d.google_photo_attributions AS google_photo_attributions,
           d.google_photo_source AS google_photo_source,

           d.fasilitas AS fasilitas,
           d.facilities AS facilities,
           d.fasilitas_umum AS fasilitas_umum,

           d.jam_buka AS jam_buka,
           d.opening_hours AS opening_hours,
           d.jam_operasional AS jam_operasional,

           d.harga_tiket AS harga_tiket,
           d.ticket_price AS ticket_price,
           d.tiket AS tiket,

           k.nama AS kategori,
           w.nama AS wilayah,
           w.provinsi AS provinsi
    """

def fetch_destinations(kategori=None, wilayah=None, search=None, limit=24):
    query = """
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    WHERE ($kategori IS NULL OR toLower(coalesce(toString(k.nama), "")) CONTAINS toLower($kategori))
      AND ($wilayah IS NULL OR toLower(coalesce(toString(w.nama), "")) CONTAINS toLower($wilayah) OR toLower(coalesce(toString(w.provinsi), "")) CONTAINS toLower($wilayah))
      AND ($search IS NULL OR toLower(coalesce(toString(d.nama), "")) CONTAINS toLower($search) OR toLower(coalesce(toString(d.alamat), "")) CONTAINS toLower($search) OR toLower(coalesce(toString(d.teks_nlp), "")) CONTAINS toLower($search))
    WITH d, k, w,
         coalesce(toFloatOrNull(toString(d.rating)), 0.0) AS safe_rating,
         coalesce(toIntegerOrNull(toString(d.jumlah_ulasan)), 0) AS safe_ulasan
    RETURN d.id AS id,
           d.nama AS nama,
           safe_rating AS rating,
           safe_ulasan AS jumlah_ulasan,

           d.alamat AS alamat,
           d.telepon AS telepon,
           d.website AS website,
           d.url AS url,

           d.latitude AS latitude,
           d.longitude AS longitude,

           d.teks_nlp AS teks_nlp,
           d.deskripsi AS deskripsi,
           d.description AS description,
           d.short_description AS short_description,

           d.main_image AS main_image,
           d.gallery_images AS gallery_images,
           d.google_photo_names AS google_photo_names,
           d.google_photo_attributions AS google_photo_attributions,
           d.google_photo_source AS google_photo_source,

           d.fasilitas AS fasilitas,
           d.facilities AS facilities,
           d.fasilitas_umum AS fasilitas_umum,

           d.jam_buka AS jam_buka,
           d.opening_hours AS opening_hours,
           d.jam_operasional AS jam_operasional,

           d.harga_tiket AS harga_tiket,
           d.ticket_price AS ticket_price,
           d.tiket AS tiket,

           k.nama AS kategori,
           w.nama AS wilayah,
           w.provinsi AS provinsi
    ORDER BY safe_rating DESC, safe_ulasan DESC
    LIMIT $limit
    """

    return run_query(query, {
        "kategori": kategori,
        "wilayah": wilayah,
        "search": search,
        "limit": limit
    })

def fetch_destination_detail(dest_id: str):
    query = f"""
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    WHERE d.id = $id
    {destination_return_clause()}
    LIMIT 1
    """
    rows = run_query(query, {"id": dest_id})
    return rows[0] if rows else None

def extract_entities(question: str):
    categories = list_categories()
    regions = list_regions()
    region_names = [r["nama"] for r in regions if r.get("nama")]
    province_names = list({r["provinsi"] for r in regions if r.get("provinsi")})
    destination_names = list_destination_names()

    kategori = best_match(question, categories, 0.65)
    wilayah = best_match(question, region_names, 0.65)
    provinsi = best_match(question, province_names, 0.80)
    destinasi = best_match(question, destination_names, 0.80)

    matched = normalize(" ".join([x for x in [kategori, wilayah, provinsi, destinasi] if x]))
    keywords = [t for t in tokens(question) if t not in matched][:8]

    return {
        "intent": detect_intent(question),
        "kategori": kategori,
        "wilayah": wilayah,
        "provinsi": provinsi,
        "destinasi": destinasi,
        "keywords": keywords,
    }

def fetch_for_qa(entities: dict):
    if entities.get("destinasi"):
        cypher = f"""
        MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
        MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
        WHERE toLower(trim(toString(d.nama))) CONTAINS toLower(trim($destinasi))
        {destination_return_clause()}
        ORDER BY coalesce(toFloatOrNull(toString(d.rating)), 0) DESC
        LIMIT 50
        """
        return run_query(cypher, {"destinasi": entities["destinasi"]}), cypher

    wilayah = entities.get("wilayah") or entities.get("provinsi")
    kategori = entities.get("kategori")
    keywords = entities.get("keywords") or []

    cypher = f"""
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    WHERE
      (
        $kategori IS NULL
        OR toLower(trim(toString(k.nama))) = toLower(trim($kategori))
      )
      AND
      (
        $wilayah IS NULL
        OR toLower(trim(toString(w.nama))) = toLower(trim($wilayah))
      )
      AND
      (
        size($keywords) = 0
        OR any(keyword IN $keywords WHERE
             toLower(coalesce(toString(d.nama), "")) CONTAINS toLower(keyword)
          OR toLower(coalesce(toString(d.alamat), "")) CONTAINS toLower(keyword)
          OR toLower(coalesce(toString(d.teks_nlp), "")) CONTAINS toLower(keyword)
        )
      )
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

    if not rows and (kategori or wilayah):
        params["keywords"] = []
        rows = run_query(cypher, params)

    return rows, cypher

def doc(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in ["nama", "kategori", "wilayah", "provinsi", "alamat", "teks_nlp"])

def rank(question: str, items: list[dict], top_k=6):
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


def generate_answer(question: str, entities: dict, recommendations: list[dict]) -> str:
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

def fetch_featured_destinations(kategori=None, limit=6):
    query = """
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    WHERE
      (
        $kategori IS NULL
        AND k.nama STARTS WITH "Wisata"
      )
      OR
      (
        $kategori IS NOT NULL
        AND toLower(trim(toString(k.nama))) = toLower(trim($kategori))
      )
    WITH d, k, w,
         coalesce(toFloatOrNull(toString(d.rating)), 0.0) AS rating_score,
         coalesce(toIntegerOrNull(toString(d.jumlah_ulasan)), 0) AS review_count
    WITH d, k, w, rating_score, review_count,
         (rating_score * 0.6) + (log10(review_count + 1) * 0.4) AS recommendation_score
    RETURN d.id AS id,
           d.nama AS nama,
           rating_score AS rating,
           review_count AS jumlah_ulasan,

           d.alamat AS alamat,
           d.telepon AS telepon,
           d.website AS website,
           d.url AS url,

           d.latitude AS latitude,
           d.longitude AS longitude,

           d.teks_nlp AS teks_nlp,
           d.deskripsi AS deskripsi,
           d.description AS description,
           d.short_description AS short_description,

           d.main_image AS main_image,
           d.gallery_images AS gallery_images,
           d.google_photo_names AS google_photo_names,
           d.google_photo_attributions AS google_photo_attributions,
           d.google_photo_source AS google_photo_source,

           d.fasilitas AS fasilitas,
           d.facilities AS facilities,
           d.fasilitas_umum AS fasilitas_umum,

           d.jam_buka AS jam_buka,
           d.opening_hours AS opening_hours,
           d.jam_operasional AS jam_operasional,

           d.harga_tiket AS harga_tiket,
           d.ticket_price AS ticket_price,
           d.tiket AS tiket,

           k.nama AS kategori,
           w.nama AS wilayah,
           w.provinsi AS provinsi,
           recommendation_score AS recommendation_score
    ORDER BY recommendation_score DESC
    LIMIT $limit
    """

    return run_query(query, {
        "kategori": kategori,
        "limit": limit
    })

@app.get("/api/public/recommendations/featured")
def featured_recommendations(
    kategori: str | None = None,
    limit: int = Query(6, ge=1, le=20)
):
    return {
        "success": True,
        "data": fetch_featured_destinations(kategori, limit)
    }
@app.get("/")
def root():
    return {"success": True, "message": "BorneoTrip Neo4j API aktif", "docs": "/docs"}
@app.get("/api/health")
def health():
    return {"success": True, "message": "API aktif"}

@app.get("/api/public/categories")
def categories():
    return {"success": True, "data": list_categories()}
@app.get("/api/public/regions")
def regions():
    return {"success": True, "data": list_regions()}
@app.get("/api/public/destinations")
def destinations(kategori: str | None = None, wilayah: str | None = None, search: str | None = None, limit: int = Query(24, ge=1, le=100)):
    return {"success": True, "data": fetch_destinations(kategori, wilayah, search, limit)}
@app.get("/api/public/destinations/{destination_id}")
def destination_detail(destination_id: str):
    item = fetch_destination_detail(destination_id)
    if not item:
        raise HTTPException(status_code=404, detail="Destinasi tidak ditemukan")
    return {"success": True, "data": item}


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
      d.deskripsi AS deskripsi,
      d.description AS description,
      d.short_description AS short_description,

      d.main_image AS main_image,
      d.gallery_images AS gallery_images,
      d.google_photo_names AS google_photo_names,
      d.google_photo_attributions AS google_photo_attributions,
      d.google_photo_source AS google_photo_source,

      d.fasilitas AS fasilitas,
      d.facilities AS facilities,
      d.fasilitas_umum AS fasilitas_umum,

      d.jam_buka AS jam_buka,
      d.opening_hours AS opening_hours,
      d.jam_operasional AS jam_operasional,

      d.harga_tiket AS harga_tiket,
      d.ticket_price AS ticket_price,
      d.tiket AS tiket,

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

    WITH anchor, anchor_w,
      CASE
        WHEN anchor.latitude IS NULL
          OR toLower(toString(anchor.latitude)) IN ["", "-", "nan", "none", "null", "inf", "infinity", "-inf", "-infinity"]
        THEN NULL
        ELSE toFloat(anchor.latitude)
      END AS anchor_lat,
      CASE
        WHEN anchor.longitude IS NULL
          OR toLower(toString(anchor.longitude)) IN ["", "-", "nan", "none", "null", "inf", "infinity", "-inf", "-infinity"]
        THEN NULL
        ELSE toFloat(anchor.longitude)
      END AS anchor_lng

    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)

    WITH anchor, anchor_w, anchor_lat, anchor_lng, d, k, w,
      CASE
        WHEN d.latitude IS NULL
          OR toLower(toString(d.latitude)) IN ["", "-", "nan", "none", "null", "inf", "infinity", "-inf", "-infinity"]
        THEN NULL
        ELSE toFloat(d.latitude)
      END AS d_lat,
      CASE
        WHEN d.longitude IS NULL
          OR toLower(toString(d.longitude)) IN ["", "-", "nan", "none", "null", "inf", "infinity", "-inf", "-infinity"]
        THEN NULL
        ELSE toFloat(d.longitude)
      END AS d_lng

    WHERE d.id <> anchor.id
      AND ($kategori IS NULL OR toLower(toString(k.nama)) CONTAINS toLower($kategori))

    WITH anchor, anchor_w, anchor_lat, anchor_lng, d, k, w, d_lat, d_lng,
      CASE
        WHEN anchor_lat IS NOT NULL
          AND anchor_lng IS NOT NULL
          AND d_lat IS NOT NULL
          AND d_lng IS NOT NULL
          AND anchor_lat >= -90 AND anchor_lat <= 90
          AND d_lat >= -90 AND d_lat <= 90
          AND anchor_lng >= -180 AND anchor_lng <= 180
          AND d_lng >= -180 AND d_lng <= 180
        THEN point.distance(
          point({latitude: anchor_lat, longitude: anchor_lng}),
          point({latitude: d_lat, longitude: d_lng})
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
            "Aku bisa membantu beberapa hal, misalnya:\n"
            "1. Merekomendasikan wisata berdasarkan kategori dan wilayah.\n"
            "2. Menjawab alamat atau lokasi destinasi.\n"
            "3. Menampilkan rating dan jumlah ulasan destinasi.\n"
            "4. Mencari wisata di sekitar destinasi tertentu.\n"
            "5. Memberikan informasi kontak atau link lokasi jika tersedia.\n\n"
            "Contoh pertanyaan:\n"
            "- Rekomendasikan wisata alam di Barito Selatan\n"
            "- Di mana alamat Danau Sanggu?\n"
            "- Berapa rating Batuah Agrowisata?\n"
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
        "misalnya nama destinasi, kategori wisata, wilayah, alamat, rating, atau wisata di sekitar lokasi tertentu.\n\n"
        "Contoh:\n"
        "- Rekomendasikan wisata alam di Barito Selatan\n"
        "- Di mana alamat Danau Sanggu?\n"
        "- Berapa rating Batuah Agrowisata?\n"
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
    "Barito Selatan": ["barito selatan", "barsel", "buntok", "dusun selatan", "dusun utara", "gunung bintang awai", "karang rayung", "jenamas"],
    "Barito Timur": ["barito timur", "bartim", "tamiang layang", "awang", "benua lima", "dusun tengah", "dusun timur", "karusen janang", 
                    "paju epat", "paku", "patangkep tutui", "raren batuah"],
    "Barito Utara": ["barito utara", "barut", "muara teweh", "gunung purei", "gunung timang", "lahei", "lahei barat", "montallat", "teweh baru", 
                    "teweh selatan", "teweh tengah", "teweh timur"],
    "Gunung Mas": ["gunung mas", "kuala kurun", "damang batu", "kahayan hulu utara", "kurun", "manuhing", "manuhing raya", "mihing raya", 
                "miri manasa", "rungan", "rungan barat", "rungan hulu", "sepang"],
    "Kapuas": ["kapuas", "kuala kapuas", "basarang", "bataguh", "dadahup", "kapuas barat", "kapuas hilir", "kapuas hulu", "kapuas kuala", 
            "kapuas murung", "kapuas tengah", "kapuas timur", "mandau talawang", "mantangai", "pasak talawang", "pulau petak", "selat", "tamban catur"],
    "Katingan": ["katingan", "kasongan", "bukit raya", "kamipang", "katingan hilir", "katingan hulu", "katingan kuala", "katingan tengah", "marikit", 
                "mendawai", "petak malai", "pulau malan", "sanaman mantikei", "tasik payawan", "tewang sangalang garing"],
    "Kotawaringin Barat": ["kotawaringin barat", "kobar", "pangkalan bun", "arut selatan", "arut utara", "kotawaringin lama", "kumai", 
                "pangkalan banteng", "pangkalan lada"],
    "Kotawaringin Timur": ["kotawaringin timur", "kotim", "sampit", "antang kalang", "baamang", "bukit santuei", "cempaga", "cempaga hulu", 
                "mentawa baru ketapang", "mentaya hilir selatan", "mentaya hilir utara", "mentaya hulu", "parenggean", "pulau hanaut", "seranau", 
                "telaga antang", "telawang", "teluk sampit", "tualan hulu"],
    "Lamandau": ["lamandau", "nanga bulik", "batang kawa", "belantikan raya", "bulik", "bulik timur", "delang", "mentobi raya", "sematu jaya"],
    "Murung Raya": ["murung raya", "puruk cahu", "barito tuhun raya", "laung tuhun", "murung", "permata intan", "seribu riam", "sumber barito", 
                "sungai babuat", "tanah siang", "tanah siang selatan", "ulu rawas"],
    "Pulang Pisau": ["pulang pisau", "pulpis", "banama tingang", "jabiren raya", "kahayan hilir", "kahayan kuala", "kahayan tengah", "maliku", "pandih batu"],
    "Seruyan": ["seruyan", "kuala pembuang", "batu ampar", "danau sembuluh", "hanau", "seruyan hilir", "seruyan hilir timur", "seruyan hulu", 
            "seruyan raya", "seruyan tengah", "suling tambun"],
    "Sukamara": ["sukamara", "balai riam", "jelai", "pantai lunci", "permata kecubung"]
}

def contains_phrase(q: str, phrase: str) -> bool:
    q_pad = f" {normalize(q)} "
    phrase_pad = f" {normalize(phrase)} "
    return phrase_pad in q_pad


def detect_region_with_alias(question: str):
    q = normalize(question)

    for region, aliases in REGION_KEYWORD_MAP.items():
        for alias in aliases:
            if contains_phrase(q, alias):
                return {
                    "region": region,
                    "matched_alias": alias,
                    "aliases": aliases
                }

    return None


def infer_category_from_keywords(question: str):
    q = normalize(question)

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
    detected_region = detect_region_with_alias(question)

    if natural_category:
        entities["kategori"] = natural_category

    if detected_region:
        entities["wilayah"] = detected_region["region"]
        entities["matched_region_alias"] = detected_region["matched_alias"]
        entities["region_aliases"] = detected_region["aliases"]

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




def fetch_exact_recommendation(question: str):
    kategori = infer_category_from_keywords(question)
    detected_region = detect_region_with_alias(question)

    if not kategori or not detected_region:
        return None

    wilayah = detected_region["region"]

    cypher = f"""
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    WHERE toLower(trim(toString(k.nama))) = toLower(trim($kategori))
      AND toLower(trim(toString(w.nama))) = toLower(trim($wilayah))
    {destination_return_clause()}
    ORDER BY coalesce(toFloatOrNull(toString(d.rating)), 0) DESC,
             coalesce(toIntegerOrNull(toString(d.jumlah_ulasan)), 0) DESC
    LIMIT 6
    """

    rows = run_query(cypher, {
        "kategori": kategori,
        "wilayah": wilayah
    })

    entities = {
        "intent": "recommendation",
        "kategori": kategori,
        "wilayah": wilayah,
        "provinsi": None,
        "destinasi": None,
        "keywords": [],
        "matched_region_alias": detected_region["matched_alias"],
        "region_aliases": detected_region["aliases"]
    }

    return rows, cypher, entities

@app.post("/api/qa/ask")
def ask(payload: AskRequest):
    original_question = payload.question or ""
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
    exact_result = fetch_exact_recommendation(original_question)

    if exact_result:
        recommendations, cypher, entities = exact_result
        answer = generate_answer(original_question, entities, recommendations)

        return {
            "success": True,
            "question": original_question,
            "answer": answer,
            "entities": entities,
            "recommendations": recommendations,
            "cypher_used": cypher.strip()
        }

    # 2. Perluas bahasa natural pengguna dan perkuat entity dengan kamus sinonim.
    question = expand_natural_language(original_question)

    entities = extract_entities(question)
    entities = strengthen_entities_with_natural_keywords(original_question, entities)

    direct_destination = find_destination_in_question(question)
    intent = entities.get("intent") or detect_intent(question)

    if should_ignore_direct_destination(original_question, direct_destination, entities, intent):
        direct_destination = None

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