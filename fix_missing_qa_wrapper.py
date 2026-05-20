from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")

wrapper_code = r'''
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

# Tambahkan wrapper sebelum endpoint AI jika belum ada
if "def get_destinations_for_qa(" not in text:
    marker = '@app.post("/api/qa/ask")'
    if marker in text:
        text = text.replace(marker, wrapper_code + "\n" + marker, 1)
    else:
        raise SystemExit('Marker @app.post("/api/qa/ask") tidak ditemukan.')

# Tambahkan rank_destinations jika belum ada
if "def rank_destinations(" not in text:
    marker = '@app.post("/api/qa/ask")'
    text = text.replace(marker, "\ndef rank_destinations(question: str, items: list[dict], top_k=6):\n    return rank(question, items, top_k=top_k)\n\n" + marker, 1)

path.write_text(text, encoding="utf-8")
print("Wrapper get_destinations_for_qa dan rank_destinations berhasil ditambahkan.")
