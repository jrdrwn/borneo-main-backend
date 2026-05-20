from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")

stopwords_block = r'''
STOPWORDS = {
    "yang", "di", "ke", "dari", "dan", "atau", "untuk", "dengan",
    "saya", "aku", "ingin", "mau", "ada", "apa", "aja", "saja",
    "tolong", "carikan", "rekomendasikan", "rekomendasi", "tempat",
    "wisata", "daerah", "kabupaten", "kota", "provinsi", "kalimantan",
    "tengah", "dong", "berikan", "tampilkan", "cari", "punya",
    "memiliki", "berapa", "rating", "nilai", "ulasan", "alamat",
    "lokasi", "dimana", "mana", "danau", "taman", "nasional"
}

'''

# Hapus STOPWORDS lama kalau ada tapi posisinya salah
if "STOPWORDS = {" in text:
    start = text.find("STOPWORDS = {")
    end = text.find("\n}\n", start)
    if end != -1:
        text = text[:start] + text[end+3:]

# Masukkan STOPWORDS tepat sebelum fungsi tokens()
if "def tokens(" in text:
    text = text.replace("def tokens(", stopwords_block + "def tokens(", 1)
else:
    raise SystemExit("Fungsi tokens() tidak ditemukan di main.py")

path.write_text(text, encoding="utf-8")
print("STOPWORDS sudah dipasang tepat sebelum tokens().")
