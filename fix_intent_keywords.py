from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")

intent_block = r'''
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

'''

if "INTENT_KEYWORDS =" not in text:
    if "def detect_intent" in text:
        text = text.replace("def detect_intent", intent_block + "def detect_intent", 1)
    else:
        raise SystemExit("Fungsi detect_intent tidak ditemukan di main.py")

path.write_text(text, encoding="utf-8")
print("INTENT_KEYWORDS berhasil ditambahkan.")
