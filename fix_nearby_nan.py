from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

new_func = r'''def get_nearby_recommendations(anchor_id, kategori=None, limit=6):
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
'''

pattern = r"def get_nearby_recommendations\(anchor_id, kategori=None, limit=6\):.*?\ndef generate_nearby_answer"

if re.search(pattern, text, flags=re.S):
    text = re.sub(pattern, new_func + "\n\ndef generate_nearby_answer", text, flags=re.S)
else:
    raise SystemExit("Fungsi get_nearby_recommendations tidak ditemukan. Cek nama fungsi di main.py.")

path.write_text(text, encoding="utf-8")
print("get_nearby_recommendations berhasil diperbaiki agar aman dari koordinat NaN.")
