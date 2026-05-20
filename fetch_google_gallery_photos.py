import os
import json
import time
import argparse
import urllib.parse
import urllib.request
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

if not GOOGLE_MAPS_API_KEY:
    raise SystemExit("GOOGLE_MAPS_API_KEY belum ada di .env")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

def google_text_search(query):
    url = "https://places.googleapis.com/v1/places:searchText"

    body = {
        "textQuery": query,
        "languageCode": "id",
        "regionCode": "ID",
        "pageSize": 1
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.photos"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

def google_photo_uri(photo_name, max_width=1200):
    safe_name = urllib.parse.quote(photo_name, safe="/")
    params = urllib.parse.urlencode({
        "maxWidthPx": max_width,
        "skipHttpRedirect": "true",
        "key": GOOGLE_MAPS_API_KEY
    })

    url = f"https://places.googleapis.com/v1/{safe_name}/media?{params}"

    with urllib.request.urlopen(url, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data.get("photoUri")

def extract_attribution(photo):
    attributions = photo.get("authorAttributions") or []
    names = []

    for item in attributions:
        name = item.get("displayName")
        uri = item.get("uri")

        if name and uri:
            names.append(f"{name} ({uri})")
        elif name:
            names.append(name)

    return "; ".join(names)

def get_destinations_for_gallery(limit, force=False):
    if force:
        where_clause = ""
    else:
        where_clause = """
        WHERE d.gallery_images IS NULL
           OR size(d.gallery_images) < 2
        """

    query = f"""
    MATCH (d:Destinasi)
    OPTIONAL MATCH (d)-[:BERLOKASI_DI]->(w:Wilayah)
    {where_clause}
    RETURN
      d.id AS id,
      d.nama AS nama,
      d.alamat AS alamat,
      d.main_image AS main_image,
      d.gallery_images AS gallery_images,
      w.nama AS wilayah,
      w.provinsi AS provinsi
    LIMIT $limit
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        return [record.data() for record in session.run(query, {"limit": limit})]

def build_search_query(item):
    parts = [
        item.get("nama"),
        item.get("alamat"),
        item.get("wilayah"),
        item.get("provinsi"),
        "Kalimantan Tengah",
        "Indonesia"
    ]

    return " ".join([
        str(part) for part in parts
        if part and str(part).lower() not in ["nan", "none", "null", "-"]
    ])

def save_gallery_to_neo4j(destination_id, place_id, photo_names, photo_uris, attributions):
    query = """
    MATCH (d:Destinasi {id: $id})
    SET d.google_place_id = $place_id,
        d.google_photo_names = $photo_names,
        d.google_photo_attributions = $attributions,
        d.gallery_images = $photo_uris,
        d.google_photo_source = "Google Places API",
        d.main_image =
          CASE
            WHEN d.main_image IS NULL
              OR toLower(toString(d.main_image)) IN ["", "-", "nan", "none", "null"]
            THEN $first_photo
            ELSE d.main_image
          END
    RETURN d.id AS id, d.nama AS nama, d.main_image AS main_image, d.gallery_images AS gallery_images
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        return session.run(query, {
            "id": destination_id,
            "place_id": place_id,
            "photo_names": photo_names,
            "photo_uris": photo_uris,
            "attributions": attributions,
            "first_photo": photo_uris[0] if photo_uris else None
        }).single()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-photos", type=int, default=4)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--force", action="store_true", help="Isi ulang gallery_images meskipun sudah ada")
    args = parser.parse_args()

    destinations = get_destinations_for_gallery(args.limit, force=args.force)

    print(f"Destinasi yang akan diproses: {len(destinations)}")

    success = 0
    failed = 0

    for index, item in enumerate(destinations, start=1):
        destination_id = item.get("id")
        nama = item.get("nama")
        search_query = build_search_query(item)

        print(f"[{index}/{len(destinations)}] Cari galeri: {nama}")

        try:
            result = google_text_search(search_query)
            places = result.get("places") or []

            if not places:
                print("  - Tidak ditemukan di Google Places")
                failed += 1
                continue

            place = places[0]
            photos = place.get("photos") or []

            if not photos:
                print("  - Tempat ditemukan, tapi tidak ada foto")
                failed += 1
                continue

            photo_uris = []
            photo_names = []
            attributions = []

            for photo in photos[:args.max_photos]:
                photo_name = photo.get("name")
                if not photo_name:
                    continue

                photo_uri = google_photo_uri(photo_name)
                if not photo_uri:
                    continue

                photo_names.append(photo_name)
                photo_uris.append(photo_uri)
                attributions.append(extract_attribution(photo))

                time.sleep(0.15)

            if not photo_uris:
                print("  - Tidak ada photo URI yang berhasil diambil")
                failed += 1
                continue

            save_gallery_to_neo4j(
                destination_id=destination_id,
                place_id=place.get("id"),
                photo_names=photo_names,
                photo_uris=photo_uris,
                attributions=attributions
            )

            print(f"  + Berhasil simpan {len(photo_uris)} foto")
            success += 1

        except Exception as error:
            print(f"  ! Error: {error}")
            failed += 1

        time.sleep(args.sleep)

    print("")
    print(f"Selesai. Berhasil: {success}, Gagal: {failed}")

if __name__ == "__main__":
    main()
