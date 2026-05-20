from pathlib import Path
import re

path = Path("main.py")
text = path.read_text(encoding="utf-8")

if "import math" not in text:
    text = text.replace("import os", "import os\nimport math")

safe_code = r'''
def make_json_safe(value):
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, dict):
        return {key: make_json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [make_json_safe(item) for item in value]

    return value

def run_query(query, params=None):
    with driver.session(database=NEO4J_DATABASE) as session:
        rows = [record.data() for record in session.run(query, params or {})]
    return make_json_safe(rows)
'''

pattern = r"def run_query\(query.*?\n(?=def )"

if re.search(pattern, text, flags=re.S):
    text = re.sub(pattern, safe_code + "\n", text, flags=re.S)
else:
    raise SystemExit("Fungsi run_query tidak ditemukan. Kirim isi awal main.py kalau ini gagal.")

path.write_text(text, encoding="utf-8")
print("Patch JSON safe berhasil.")
