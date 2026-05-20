from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")

stopwords_code = '''
STOPWORDS = {
    "yang", "di", "ke", "dari", "dan", "atau", "untuk", "dengan",
    "saya", "aku", "ingin", "mau", "ada", "apa", "aja", "saja",
    "tolong", "carikan", "rekomendasikan", "rekomendasi", "tempat",
    "wisata", "daerah", "kabupaten", "kota", "provinsi", "kalimantan",
    "tengah", "dong", "berikan", "tampilkan", "cari", "punya",
    "memiliki", "berapa", "rating", "nilai", "ulasan"
}
'''

if "STOPWORDS =" not in text:
    marker = "INTENT_KEYWORDS = {"
    text = text.replace(marker, stopwords_code + "\n" + marker)

path.write_text(text, encoding="utf-8")
print("STOPWORDS berhasil ditambahkan.")
