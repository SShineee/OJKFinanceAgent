"""
Tugas 7.5 -- 15 query uji temu-kembali + definisi "chunk yang benar".  docs/PANDUAN_MINGGU7.md, Langkah 1.

Dataset: eval/datasets/retrieval_queries.jsonl. DIKUNCI sebelum eksperimen (Minggu 7): jangan
diganti setelah melihat hasil, karena itu membuat Hit@5 terlalu optimistis. Hash SHA-256-nya
dicatat di panduan; eksperimen (Langkah 4) mencetak hash yang dipakai.

Keputusan 7.B (15-11-2026): chunk BENAR = chunk dari laporan <kode>_<tahun> itu yang MEMUAT ANGKA
JAWABANNYA, dalam bentuk mana pun yang tercetak di laporan:
  type "value"      angka ground truth dalam miliar (ground_truth.xlsx, sheet 1_angka_mentah)
                      - miliar dibulatkan "1.586.829", boleh diikuti ".xxx" (bentuk juta di
                        laporan keuangan, mis. "1.586.829.123")
                      - juta persis kalau nilainya berdesimal: 239468.855 -> "239.468.855"
                      - triliun satu desimal: "1.586,8 triliun" / "Rp1.586,8 triliun"
  type "percent"    rasio resmi (sheet 2_rasio_resmi): desimal aslinya + dibulatkan 1 desimal,
                    diikuti "%": 29.36 -> "29,36%" / "29,4%"
  type "component"  komponen yang tercetak kalau totalnya tidak tercetak (DPK bank 2024 = pihak
                    berelasi + pihak ketiga); `of` = total ground truth-nya, untuk dicek
Pola dibatasi tepinya supaya "54.851" tidak cocok dengan "254.851" atau "54.851,5".

Setiap angka MERUJUK sel ground truth (`gt`), dan `verify()` memastikan angkanya sama dengan
ground_truth.xlsx -- tidak ada angka yang diketik ulang tanpa diperiksa.

Cek:  python -m eval.retrieval_queries
"""

import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

from src import config

DATASET = config.EVAL_DATASETS / "retrieval_queries.jsonl"
GT_YEAR_COLUMN = {2022: 3, 2023: 4, 2024: 5, 2025: 6}      # kolom tahun di sheet 1_angka_mentah
# Komposisi set yang dikunci 15-11-2026. Bukan 5/5/5: set ini sudah dijalankan di prototipe, jadi
# menukar query setelah hasilnya diketahui = memilih-milih. Ketidakseimbangan tahun dicatat saja.
COMPOSITION = {2023: 4, 2024: 6, 2025: 5}


def load_queries(path: Path = DATASET) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dataset_sha256(path: Path = DATASET) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _decimal(value: float, places: int) -> str:
    """29.36 -> '29,36'; 1586.829 (1 tempat) -> '1.586,8'."""
    return f"{value:,.{places}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _bounded(text: str) -> str:
    return rf"(?<![\d.,]){re.escape(text)}(?![\d,]|\.\d)"


def answer_patterns(answer: dict) -> list[str]:
    """Regex untuk setiap bentuk tercetak satu jawaban (lihat docstring modul)."""
    kind, value = answer["type"], answer.get("value")
    if kind == "value":
        forms = [rf"(?<![\d.,]){re.escape(_thousands(round(value)))}(?:\.\d{{3}})?(?![\d,]|\.\d)"]
        if value != int(value):
            forms.append(_bounded(_thousands(round(value * 1000))))
        forms.append(rf"(?<![\d.,]){re.escape(_decimal(value / 1000, 1))}\s*triliun")
        return forms
    if kind == "percent":
        places = len(f"{value}".split(".")[1]) if "." in f"{value}" else 0
        texts = dict.fromkeys([_decimal(value, places), _decimal(value, 1)])
        return [rf"(?<![\d.,]){re.escape(t)}\s*%" for t in texts]
    if kind == "component":
        return [_bounded(answer["text"])]
    raise ValueError(f"jenis jawaban tidak dikenal: {kind}")


@lru_cache(maxsize=None)
def _compiled(query_id: str, answers_json: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p) for a in json.loads(answers_json) for p in answer_patterns(a))


def is_relevant(text: str, query: dict) -> bool:
    """Keputusan 7.B: teks chunk memuat salah satu bentuk angka jawabannya."""
    patterns = _compiled(query["id"], json.dumps(query["answers"], sort_keys=True))
    return any(p.search(text) for p in patterns)


def relevant_chunk_ids(query: dict) -> list[str]:
    """chunk_id yang BENAR untuk query ini -- hanya dari laporan <ticker>_<year> query itu."""
    from src.ingest.chunk import load_chunks
    return [c["chunk_id"] for c in load_chunks(query["year"], query["ticker"]) if is_relevant(c["text"], query)]


def verify(queries: list[dict]) -> list[str]:
    """Angka = ground_truth.xlsx; setiap query punya >= 1 chunk benar; komposisi sesuai panduan."""
    from openpyxl import load_workbook

    problems = []
    book = load_workbook(config.GROUND_TRUTH, data_only=True)
    ids = [q["id"] for q in queries]
    if len(ids) != len(set(ids)):
        problems.append("id query ganda")
    for q in queries:
        for a in q["answers"]:
            if a["type"] in ("value", "percent"):
                ref = a["gt"]
                sheet = book[ref["sheet"]]
                cell = (sheet.cell(row=ref["row"], column=GT_YEAR_COLUMN[ref["year"]]).value
                        if a["type"] == "value" else sheet.cell(row=ref["row"], column=3).value)
                if a["type"] == "percent" and int(sheet.cell(row=ref["row"], column=1).value) != q["year"]:
                    problems.append(f"{q['id']}: baris {ref['row']} {ref['sheet']} bukan tahun {q['year']}")
                if cell is None or abs(float(cell) - a["value"]) > 1e-6:
                    problems.append(f"{q['id']}: nilai {a['value']} != ground truth {cell} ({ref})")
                if a["type"] == "value" and ref["year"] != q["year"]:
                    problems.append(f"{q['id']}: jawaban merujuk tahun {ref['year']}, query tahun {q['year']}")
            elif a["type"] == "component" and not any(x.get("value") == a["of"] for x in q["answers"]):
                problems.append(f"{q['id']}: komponen merujuk total {a['of']} yang tidak ada di jawaban")
        if not relevant_chunk_ids(q):
            problems.append(f"{q['id']}: tidak ada chunk yang memuat jawabannya")
    years = [q["year"] for q in queries]
    if len(queries) != 15 or {y: years.count(y) for y in config.YEARS} != COMPOSITION:
        problems.append(f"komposisi: {len(queries)} query, per tahun {[years.count(y) for y in config.YEARS]} "
                        f"(terkunci: 15, {COMPOSITION})")
    if sum(q["abbreviation"] for q in queries) != 7:
        problems.append(f"query bersingkatan {sum(q['abbreviation'] for q in queries)}, harus 7")
    return problems


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from src.ingest.chunk import load_chunks

    queries = load_queries()
    pages = {}
    for y in config.YEARS:
        for c in load_chunks(y, config.DEV_TICKER):
            pages[c["chunk_id"]] = c["pages"]
    print(f"{DATASET.relative_to(config.ROOT)}: {len(queries)} query, sha256 {dataset_sha256()[:16]}…")
    for q in queries:
        rel = relevant_chunk_ids(q)
        p = sorted({x for cid in rel for x in pages[cid]})
        print(f"  {q['id']} {q['year']} {'S' if q['abbreviation'] else ' '} {q['query']:<52} "
              f"{len(rel):>2} chunk benar, hal {p[:8]}{' …' if len(p) > 8 else ''}")
    problems = verify(queries)
    for p in problems:
        print(f"  MASALAH: {p}")
    print("HASIL:", "LULUS" if not problems else f"GAGAL ({len(problems)} masalah)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
