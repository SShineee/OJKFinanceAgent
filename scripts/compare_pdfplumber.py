"""
Tugas 3.9 (opsional) -- pembanding: Docling vs pdfplumber pada 10 halaman bbca_2024 yang sama.
docs/PANDUAN_MINGGU3.md, Langkah 9.  Bahan Bab 4: alasan memakai Docling.

Halaman: tabel rasio resmi (21), tabel Pilar 3 terbelah dua halaman (156-157), laporan posisi
keuangan & laba rugi konsolidasian (540-542), NPL (701), Catatan KPMM (703), Entitas Induk
(704-705).

Docling TIDAK dijalankan ulang: tabelnya diambil dari hasil parse Langkah 5
(data/markdown/bbca_2024.json). pdfplumber diuji dengan dua strategi deteksi tabel:
  garis  bawaan pdfplumber: batas sel dari garis yang tergambar di PDF
  teks   batas sel dari perataan teks (untuk tabel tanpa garis)

Ukuran (fungsi yang sama untuk ketiganya):
  angka tampak masuk tabel  angka berformat ribuan/persen yang TAMPAK di halaman (pypdfium2
                            get_text_bounded) dan ada di sel tabel, dihitung per kemunculan
  angka asing               angka di sel tabel yang tidak tercetak utuh di halaman itu: pecahan
                            angka yang terpotong batas sel, atau isi di luar area tampak
  sel gabungan              sel berisi >= 2 angka
  uji baris+kolom           10 angka terverifikasi Minggu 1: berada di baris berlabel X dan
                            kolom berjudul Y? tepat / cacat (ada, tapi bersama isi lain) / salah
  uji baris                 angka itu utuh di baris berlabel X, kolomnya diabaikan
Label dicocokkan tanpa spasi dan kolom dipilih seluas mungkin, supaya pdfplumber tidak gagal
karena hal kosmetik -- yang dibandingkan adalah struktur baris dan kolomnya.

Jalankan:  python scripts/compare_pdfplumber.py
"""

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pdfplumber  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
from docling_core.types.doc import DoclingDocument  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

import build_verification_sheet as sources  # noqa: E402
from src import config  # noqa: E402
from src.ingest.subset_pdf import PageMap  # noqa: E402

YEAR = 2024
PAGES = [21, 156, 157, 540, 541, 542, 701, 703, 704, 705]
VALUE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+%")   # 855.233.239 / 29,4%
PLUMBER = {
    "pdfplumber (garis)": {},
    "pdfplumber (teks)": {"vertical_strategy": "text", "horizontal_strategy": "text"},
}
RESULTS = config.RESULTS / "parser_comparison.json"


def juta(miliar: float) -> str:
    return f"{round(miliar * 1000):,}".replace(",", ".")


def position_checks() -> list[tuple]:
    """(halaman, pola label, pola baris pembuka, kata wajib di judul kolom, angka)."""
    ws = load_workbook(config.GROUND_TRUTH)["1_angka_mentah"]
    gt = lambda row: juta(ws.cell(row=row, column=sources.COL_IDX[YEAR]).value)
    checks = []
    for row, label in ((13, r"Modal Inti \(Tier 1\)"), (14, r"^Total Modal$"), (15, r"^Total ATMR$")):
        checks.append((703, label, None, ("2024", "bank"), gt(row)))
        checks.append((703, label, None, ("2024", "konsolidasian"), gt(row + 4)))
    # Lembar verifikasi Minggu 1 (PANDUAN_MINGGU3 Langkah 6a)
    checks += [
        (704, r"Pihak ketiga", r"^Kredit yang diberikan", ("2024",), "855.233.239"),
        (705, r"Pihak ketiga", r"^Simpanan dari nasabah", ("2024",), "1.105.647.994"),
        (21, r"^Rasio Kecukupan Modal", None, ("2024",), "29,4%"),
        (21, r"Pengembalian atas Ekuitas", None, ("2024",), "24,6%"),
    ]
    return checks


# ------------------------------------------------------------------ tabel sebagai list baris
def docling_tables() -> dict[int, list[list[list[str]]]]:
    meta = json.loads(config.parse_meta(YEAR).read_text(encoding="utf-8"))
    page_map = PageMap.from_list(meta["page_map"])
    doc = DoclingDocument.load_from_json(config.docling_json(YEAR))
    out = {p: [] for p in PAGES}
    for t in doc.tables:
        for page in {page_map.to_original(p.page_no) for p in t.prov} & set(PAGES):
            out[page].append([[c.text for c in row] for row in t.data.grid])
    return out, meta["seconds"]["convert_per_page"]


def plumber_tables(settings: dict) -> tuple[dict, float]:
    out, start = {}, time.perf_counter()
    with pdfplumber.open(config.pdf(YEAR)) as pdf:
        for page in PAGES:
            tables = pdf.pages[page - 1].extract_tables(settings)
            out[page] = [[[c or "" for c in row] for row in t] for t in tables]
    return out, (time.perf_counter() - start) / len(PAGES)


def visible_values() -> dict[int, Counter]:
    doc = pdfium.PdfDocument(str(config.pdf(YEAR)))
    try:
        out = {}
        for page in PAGES:
            tp = doc[page - 1].get_textpage()
            out[page] = Counter(VALUE.findall(tp.get_text_bounded()))
            tp.close()
        return out
    finally:
        doc.close()


# ------------------------------------------------------------------ ukuran
def has_value(text: str) -> bool:
    return bool(VALUE.search(text or ""))


def is_value_cell(text: str) -> bool:
    """Sel yang isinya murni angka. Label boleh memuat angka: label baris kredit Entitas Induk
    menyebut CKPN 'sebesar Rp 32.382.006' di dalam teksnya. Pecahan angka dari pdfplumber
    ('265.1') juga sel nilai, bukan bagian label."""
    return bool(re.search(r"\d", text or "")) and bool(re.fullmatch(r"[\s\d.,()%\-]+", text))


def squash(text: str) -> str:
    """Tanpa spasi: pdfplumber (teks) memotong kata di tengah ('M | odal Inti'). Label dicocokkan
    tanpa spasi untuk ketiga alat, supaya yang dibandingkan hanya struktur baris dan kolom."""
    return re.sub(r"\s+", "", text)


def column_titles(table: list[list[str]]) -> list[str]:
    """Baris sebelum baris berangka pertama = header; sel kosong mewarisi judul di kirinya
    (judul tahun yang membentang dua kolom). Docling sudah mengulang sel bentangan sendiri."""
    width = max(len(r) for r in table)
    titles = [""] * width
    for row in table:
        if any(has_value(c) for c in row):
            break
        last = ""
        for j in range(width):
            cell = (row[j] if j < len(row) else "").strip()
            last = cell or (last if j > 0 else "")
            titles[j] += " " + (cell or last)
    return [t.strip().lower() for t in titles]


def label_of(row: list[str]) -> str:
    return squash("".join(c for c in row if c and not is_value_cell(c)))


def labeled_rows(table, label: str, after: str | None) -> list[list[str]]:
    """Baris berlabel `label`, dimulai dari baris pembuka `after` (inklusif -- Docling bisa
    menggabungkan baris pembuka dengan sub-barisnya)."""
    start = 0
    if after:
        start = next((i for i, r in enumerate(table) if re.search(squash(after), label_of(r))), None)
        if start is None:
            return []
    return [r for r in table[start:] if re.search(squash(label), label_of(r))]


def locate(tables, label, after, needs, expected) -> tuple[str, str]:
    """Uji ketat: angka di baris berlabel benar DAN di kolom yang judulnya memuat `needs`."""
    best = ("salah", "baris/kolom tidak ditemukan")
    for table in tables:
        titles = column_titles(table)
        cols = [j for j, t in enumerate(titles) if all(n in t.split() for n in needs)]
        rows = labeled_rows(table, label, after)
        if not rows:
            continue
        if not cols:
            best = ("salah", f"baris ada, kolom berjudul '{' '.join(needs)}' tidak ada")
            continue
        # dari kolom yang judulnya cocok, pakai yang berisi angka di baris ini: tabel pdfplumber
        # (teks) ikut memuat judul halaman "31 DESEMBER 2024 DAN 2023" di atas kolom label
        row = rows[0]
        filled = [j for j in cols if j < len(row) and is_value_cell(row[j])]
        cell = row[(filled or cols)[0]].strip() if (filled or cols)[0] < len(row) else ""
        if cell == expected:
            return "tepat", ""
        if expected in cell:
            best = ("cacat", f"sel berisi '{cell[:60]}'")
        elif best[0] == "salah":
            best = ("salah", f"sel berisi '{cell[:60]}'")
    return best


def in_row(tables, label, after, expected) -> bool:
    """Uji longgar: angka itu UTUH di baris berlabel benar, kolomnya diabaikan."""
    return any(expected in VALUE.findall(" ".join(rows[0]))
               for table in tables if (rows := labeled_rows(table, label, after)))


def measure(name: str, tables: dict, visible: dict, checks: list, seconds: float) -> dict:
    found = hidden = shown = cells = merged = n_tables = 0
    per_page = {}
    for page in PAGES:
        in_tables = Counter()
        for table in tables[page]:
            for row in table:
                for cell in row:
                    values = VALUE.findall(cell or "")
                    in_tables.update(values)
                    cells += bool(values)
                    merged += len(values) >= 2
        page_found = sum((in_tables & visible[page]).values())
        found += page_found
        shown += sum(visible[page].values())
        hidden += sum((in_tables - visible[page]).values())
        n_tables += len(tables[page])
        per_page[page] = {"tables": len(tables[page]), "found": page_found,
                          "visible": sum(visible[page].values())}
    located = [(c, *locate(tables[c[0]], *c[1:])) for c in checks]
    rows_ok = [in_row(tables[c[0]], c[1], c[2], c[4]) for c in checks]
    return {
        "tool": name, "seconds_per_page": round(seconds, 2), "tables": n_tables,
        "visible_values": shown, "found_in_tables": found, "foreign_values": hidden,
        "value_cells": cells, "merged_cells": merged,
        "checks": {s: sum(r[1] == s for r in located) for s in ("tepat", "cacat", "salah")},
        "row_checks": sum(rows_ok),
        "check_detail": [{"page": c[0], "label": c[1], "column": " ".join(c[3]), "expected": c[4],
                          "status": s, "detail": d, "intact_in_row": ok}
                         for (c, s, d), ok in zip(located, rows_ok)],
        "per_page": per_page,
    }


def main():
    checks = position_checks()
    visible = visible_values()
    results = []
    tables, per_page = docling_tables()
    results.append(measure("Docling (TableFormer ACCURATE, GPU)", tables, visible, checks, per_page))
    for name, settings in PLUMBER.items():
        tables, per_page = plumber_tables(settings)
        results.append(measure(name, tables, visible, checks, per_page))

    print(f"Docling vs pdfplumber -- bbca_{YEAR}, {len(PAGES)} halaman: "
          f"{', '.join(map(str, PAGES))}\n")
    head = (f"  {'':<38}{'tabel':>6}{'angka tampak':>16}{'angka asing':>13}{'sel gabungan':>14}"
            f"{'baris+kolom (10)':>24}{'baris (10)':>12}{'s/hal':>7}")
    print(head)
    for r in results:
        cover = f"{r['found_in_tables']}/{r['visible_values']} ({r['found_in_tables'] / r['visible_values']:.0%})"
        merged = f"{r['merged_cells']}/{r['value_cells']}" if r["value_cells"] else "-"
        c = r["checks"]
        print(f"  {r['tool']:<38}{r['tables']:>6}{cover:>16}{r['foreign_values']:>13}{merged:>14}"
              f"{c['tepat']:>6} tepat {c['cacat']} cacat {c['salah']} salah{r['row_checks']:>8}"
              f"{r['seconds_per_page']:>9}")
    print("  angka asing = angka di sel yang tidak tercetak utuh di halaman (pecahan angka, atau isi\n"
          "  di luar area tampak); baris = angka utuh di baris berlabel benar, kolom diabaikan")
    print("\n  Tabel per halaman:")
    print("  " + " " * 38 + "".join(f"{p:>6}" for p in PAGES))
    for r in results:
        print(f"  {r['tool']:<38}" + "".join(f"{r['per_page'][p]['tables']:>6}" for p in PAGES))
    print("\n  Uji letak:")
    for i, check in enumerate(checks):
        statuses = "  ".join(f"{r['check_detail'][i]['status']:<6}"
                             f"{'/baris' if r['check_detail'][i]['intact_in_row'] else '/-    '}"
                             for r in results)
        print(f"  hal {check[0]} {check[1][:28]:<28} {' '.join(check[3]):<20} {check[4]:>14}   {statuses}")
    print("  (kolom status: " + " | ".join(r["tool"] for r in results) + ")")
    print("\n  Catatan s/hal: Docling = waktu parse di GPU dari .meta.json (termasuk tata letak "
          "seluruh halaman); pdfplumber = CPU, hanya ekstraksi tabel.")
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  disimpan ke {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
