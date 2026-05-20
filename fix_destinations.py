from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

new_func = r'''def fetch_destinations(kategori=None, wilayah=None, search=None, limit=24):
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
           coalesce(toString(d.alamat), "") AS alamat,
           coalesce(toString(d.telepon), "") AS telepon,
           coalesce(toString(d.website), "") AS website,
           coalesce(toString(d.url), "") AS url,
           d.latitude AS latitude,
           d.longitude AS longitude,
           coalesce(toString(d.teks_nlp), "") AS teks_nlp,
           k.nama AS kategori,
           w.nama AS wilayah,
           w.provinsi AS provinsi
    ORDER BY safe_rating DESC, safe_ulasan DESC
    LIMIT $limit
    """
    return run_query(query, {"kategori": kategori, "wilayah": wilayah, "search": search, "limit": limit})
'''

pattern = r"def fetch_destinations\(kategori=None, wilayah=None, search=None, limit=24\):.*?\ndef fetch_destination_detail"
text = re.sub(pattern, new_func + "\n\ndef fetch_destination_detail", text, flags=re.S)

path.write_text(text, encoding="utf-8")
print("fetch_destinations berhasil diperbaiki.")
