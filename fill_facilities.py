import os
import argparse
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

CATEGORY_DEFAULTS = {
    "Wisata Kuliner": [
        "Area makan",
        "Menu makanan dan minuman",
        "Tempat duduk",
        "Area parkir"
    ],
    "Akomodasi": [
        "Kamar penginapan",
        "Resepsionis",
        "Area parkir",
        "Toilet atau kamar mandi"
    ],
    "Wisata Alam": [
        "Area parkir",
        "Spot foto",
        "Area istirahat",
        "Akses jalan wisata"
    ],
    "Wisata Sejarah": [
        "Area parkir",
        "Spot foto",
        "Area edukasi",
        "Papan informasi"
    ],
    "Wisata Religi": [
        "Area parkir",
        "Tempat ibadah",
        "Toilet",
        "Area istirahat"
    ],
    "Wisata Budaya": [
        "Area parkir",
        "Spot foto",
        "Area edukasi budaya",
        "Papan informasi"
    ],
    "Wisata Belanja": [
        "Area belanja",
        "Tempat parkir",
        "Tenant atau kios",
        "Akses jalan"
    ],
    "Wisata Edukasi": [
        "Area edukasi",
        "Papan informasi",
        "Area parkir",
        "Spot foto"
    ]
}

INVALID_VALUES = {"", "-", "nan", "none", "null", "undefined"}


def is_empty(value):
    if value is None:
        return True
    return str(value).strip().lower() in INVALID_VALUES


def unique_list(values):
    result = []
    seen = set()
    for value in values or []:
        if is_empty(value):
            continue
        text = str(value).strip()
        key = text.lower()
        if key not in seen:
            result.append(text)
            seen.add(key)
    return result


def normalize_facilities(raw_facilities, kategori, nama="", teks=""):
    kategori = (kategori or "").strip()
    nama_lower = (nama or "").lower()
    teks_lower = (teks or "").lower()
    combined = f"{nama_lower} {teks_lower}"

    if isinstance(raw_facilities, list):
        facilities = unique_list(raw_facilities)
    elif isinstance(raw_facilities, str) and not is_empty(raw_facilities):
        facilities = unique_list(raw_facilities.replace(";", ",").replace("|", ",").split(","))
    else:
        facilities = []

    # Buang fasilitas yang tidak relevan dengan kategori.
    if kategori != "Akomodasi":
        facilities = [item for item in facilities if item.lower() not in {"penginapan", "kamar penginapan", "resepsionis"}]

    # Untuk kuliner, hindari label terlalu umum dan jadikan lebih informatif.
    if kategori == "Wisata Kuliner":
        facilities = [item for item in facilities if item.lower() not in {"warung atau tempat makan", "penginapan"}]
        facilities = unique_list(CATEGORY_DEFAULTS["Wisata Kuliner"] + facilities)

    # Untuk akomodasi, pastikan fasilitasnya sesuai konteks penginapan.
    elif kategori == "Akomodasi":
        facilities = [item for item in facilities if item.lower() not in {"warung atau tempat makan"}]
        facilities = unique_list(CATEGORY_DEFAULTS["Akomodasi"] + facilities)

    # Untuk kategori lain, kalau fasilitas terlalu sedikit, gunakan default kategori.
    elif kategori in CATEGORY_DEFAULTS:
        if len(facilities) < 2:
            facilities = unique_list(CATEGORY_DEFAULTS[kategori] + facilities)
        else:
            facilities = unique_list(facilities)

    # Tambahan berbasis kata kunci, hanya jika relevan.
    keyword_facilities = []
    if "toilet" in combined or "wc" in combined:
        keyword_facilities.append("Toilet")
    if "parkir" in combined:
        keyword_facilities.append("Area parkir")
    if "mushola" in combined or "musala" in combined or "masjid" in combined:
        keyword_facilities.append("Mushola")
    if "spot foto" in combined or "foto" in combined:
        keyword_facilities.append("Spot foto")
    if "gazebo" in combined:
        keyword_facilities.append("Gazebo")
    if "warung" in combined and kategori != "Akomodasi":
        keyword_facilities.append("Warung atau tempat makan")

    facilities = unique_list(facilities + keyword_facilities)

    if not facilities:
        facilities = ["Informasi fasilitas belum tersedia"]

    return facilities


def get_rows(driver, limit, only_invalid=False):
    where_clause = ""
    if only_invalid:
        where_clause = """
        WHERE d.fasilitas IS NULL
           OR d.fasilitas = []
           OR toLower(toString(d.fasilitas)) IN ["", "-", "nan", "none", "null", "undefined"]
        """

    query = f"""
    MATCH (d:Destinasi)-[:BERKATEGORI]->(k:Kategori)
    OPTIONAL MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    {where_clause}
    RETURN
      d.id AS id,
      d.nama AS nama,
      d.alamat AS alamat,
      d.teks_nlp AS teks_nlp,
      d.fasilitas AS fasilitas,
      d.facilities AS facilities,
      k.nama AS kategori,
      w.nama AS wilayah,
      w.provinsi AS provinsi
    LIMIT $limit
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return [record.data() for record in session.run(query, {"limit": limit})]


def update_facilities(driver, destination_id, facilities):
    query = """
    MATCH (d:Destinasi {id: $id})
    SET d.fasilitas = $facilities,
        d.facilities = $facilities
    RETURN d.id AS id, d.nama AS nama, d.fasilitas AS fasilitas
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return session.run(query, {"id": destination_id, "facilities": facilities}).single()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=6000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--only-invalid",
        action="store_true",
        help="Hanya proses destinasi yang fasilitasnya masih kosong. Default: proses semua agar fasilitas lama ikut dirapikan."
    )
    args = parser.parse_args()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        rows = get_rows(driver, args.limit, only_invalid=args.only_invalid)
        print(f"Destinasi diproses: {len(rows)}")
        print("Mode:", "DRY RUN" if args.dry_run else "UPDATE DATABASE")
        print("")

        updated = 0

        for index, item in enumerate(rows, start=1):
            raw_facilities = item.get("facilities") or item.get("fasilitas")
            kategori = item.get("kategori")
            nama = item.get("nama")
            teks = " ".join(str(item.get(key) or "") for key in ["alamat", "teks_nlp", "wilayah", "provinsi"])

            new_facilities = normalize_facilities(raw_facilities, kategori, nama=nama, teks=teks)

            print(f"[{index}/{len(rows)}] {nama} | {kategori}")
            print("  Fasilitas:", ", ".join(new_facilities))

            if not args.dry_run:
                update_facilities(driver, item.get("id"), new_facilities)
                updated += 1

        print("")
        if args.dry_run:
            print("Selesai preview. Jika sudah sesuai, jalankan tanpa --dry-run.")
        else:
            print(f"Selesai. Updated: {updated}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
