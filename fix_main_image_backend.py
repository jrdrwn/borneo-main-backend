from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
'''coalesce(toString(d.teks_nlp), "") AS teks_nlp,
           k.nama AS kategori,''',
'''coalesce(toString(d.teks_nlp), "") AS teks_nlp,
           coalesce(toString(d.main_image), "") AS main_image,
           d.gallery_images AS gallery_images,
           k.nama AS kategori,''')

text = text.replace(
'''d.teks_nlp AS teks_nlp,
      k.nama AS kategori,''',
'''d.teks_nlp AS teks_nlp,
      d.main_image AS main_image,
      d.gallery_images AS gallery_images,
      k.nama AS kategori,''')

text = text.replace(
'''d.teks_nlp AS teks_nlp,
           k.nama AS kategori,''',
'''d.teks_nlp AS teks_nlp,
           d.main_image AS main_image,
           d.gallery_images AS gallery_images,
           k.nama AS kategori,''')

path.write_text(text, encoding="utf-8")
print("Backend utama sudah ditambahkan main_image dan gallery_images.")
