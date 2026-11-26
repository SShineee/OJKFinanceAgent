"""
Tugas 5.1 -- uji tabel sebelum chunking.  docs/PANDUAN_MINGGU5.md, Langkah 1 dan 2.

Jalankan:  python scripts/check_fix_tables.py

A. Langkah 1, ketiga laporan BCA (data/markdown/bbca_<tahun>.json + PDF potongannya):
   1. tidak ada angka yang hilang/berganda: isi sel angka per tabel sama sebelum & sesudah
   2. semua sel dua angka yang tersisa = baris yang DITANDAI (tidak ada yang lolos diam-diam)
   3. pola 1 (sub-baris pihak berelasi/ketiga) tinggal 0
   4. idempoten: perbaikan kedua kalinya tidak mengubah apa pun
   5. jumlah baris diperbaiki = angka yang tercatat di panduan (regresi), termasuk pola 3 (satu baris
      cetak yang dibelah Docling jadi dua baris -> digabung; 7 penggabungan dicek visual 15-11-2026)
   6. cek titik: baris yang sudah dicek visual dengan render PDF (15-11-2026)
   Langkah 2, tabel tanpa label baris:
   7. halamannya = daftar yang sudah dicek visual (15-11-2026), sama sebelum & sesudah Langkah 1
   8. setiap tabel punya bagian kiri (menempel tepi kanan halaman sebelumnya)
   9. tidak ada di halaman sumber ground truth; tabel CR5 utuh (salah tandai Minggu 3) tidak ditandai
B. Uji negatif sintetis: kalau syarat tidak terpenuhi, tabel TIDAK BOLEH berubah / ditandai.

Hasil ringkas disimpan ke results/fix_tables.json (bahan Bab 4).
"""

import json
import sys
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore", message="Table cell bbox")

from docling_core.types.doc import (BoundingBox, CoordOrigin, DoclingDocument, ProvenanceItem,  # noqa: E402
                                    Size, TableCell, TableData)

import build_verification_sheet as sources  # noqa: E402  -- halaman sumber ground truth
from src import config  # noqa: E402
from src.ingest import fix_tables as ft  # noqa: E402
from src.ingest.subset_pdf import PageMap  # noqa: E402

# hasil 15-11-2026 (pola 1, pola 2) -- berubah = sengaja (perbarui panduan) atau regresi
EXPECTED_FIXED = {2023: (4, 19), 2024: (5, 19), 2025: (0, 5)}
EXPECTED_MERGED = {2023: 2, 2024: 4, 2025: 1}          # pola 3, ketujuhnya dicek visual 15-11-2026

# Langkah 2: halaman tiap tabel tanpa label baris (satu entri per tabel), dicek visual 15-11-2026.
# Dibanding daftar audit Minggu 3: + bagian kanan CR4/CR5 (2 tabel) & CCR3 kolom f-l (1 tabel)
# [+ 2023: sekuritisasi kolom j-q hal 215], - tabel CR5 utuh (2 tabel).
EXPECTED_UNLABELED = {
    2023: [157, 159, 185, 187, 189, 191, 203, 203, 207, 209, 213, 215, 223, 227, 229, 231, 233, 237],
    2024: [155, 157, 183, 185, 187, 189, 201, 201, 205, 207, 211, 221, 225, 227, 229, 231, 235],
    2025: [110, 112, 130, 132, 134, 136, 148, 148, 152, 154, 158, 168, 172, 174, 176, 178, 182],
}
COMPLETE_CR5 = {2023: [210, 211], 2024: [208, 209], 2025: [155, 156]}   # berlabel "Bobot Risiko"


def source_pages(year: int) -> set[int]:
    """Halaman sumber ke-76 angka ground truth + rasio resmi + halaman kunci, di laporan `year`."""
    name = f"bbca_{year}.pdf"
    specs = [sources.HIGHLIGHTS(year)] + [spec for block in (sources.CAPITAL_BANK, sources.CAPITAL_CONSOLIDATED,
                                                             sources.NPL, sources.PARENT_ASSETS,
                                                             sources.PARENT_LIABILITIES)
                                          for spec in block.values()]
    pages = {page for file, page, _ in specs if file == name}
    extra = {2025: {15, 16}, 2024: {21, 540, 541, 542}}   # rasio resmi; halaman kunci Langkah 6
    return pages | extra.get(year, set())

# (tahun, halaman asli, potongan label, isi sel yang wajib ada di baris berlabel itu)
SPOT_CHECKS = [
    (2024, 704, "Pihak berelasi", ["7.296.837", "8.803.131"]),          # pola 1, kredit Entitas Induk
    (2024, 704, "Pihak ketiga", ["855.233.239", "745.527.767"]),
    (2023, 738, "Pihak ketiga", ["745.527.767", "647.699.980"]),
    (2024, 542, "Surplus revaluasi aset tetap", ["238.886", "231.837"]),  # pola 2, subtotal dipisah
    (2024, 614, "Amanah Kelas A", ["10.322", "10.102"]),                 # pola 2, angka pindah ke bawah
    (2023, 196, "Bukan Lapangan Usaha", ["44.302.763", "521.315"]),      # pola 2, angka pindah ke atas
    (2024, 711, "Lain-lain", ["(3.740.411)", "(3.992.898)"]),            # pola 2, dua baris cetak
    (2024, 643, "USD", ["60.000.000", "965.700", "53.558.000", "824.633"]),  # Rupiah / USD
    (2024, 712, "Posisi valas yang akan diserahkan", ["28.755.848", "25.389.401"]),  # nomor butir "3." = label
    (2024, 540, "JUMLAH ASET", ["1.449.301.328", "1.408.107.010"]),      # pola 3b: angka | label
    (2024, 541, "JUMLAH LIABILITAS", ["1.177.403.108", "1.157.675.545"]),  # pola 3a: label+2023 | 2024
]

failures: list[str] = []


def check(ok: bool, message: str):
    print(f"  [{'OK' if ok else 'GAGAL'}] {message}")
    if not ok:
        failures.append(message)


def column_content(table, skip_label_column: bool) -> tuple[Counter, Counter]:
    """(huruf per kolom, angka berformat ribuan per kolom). Pemecahan & pemindahan hanya menata
    ulang isi di dalam kolom yang sama, jadi keduanya harus sama persis sebelum & sesudah.
    Pola 1 sengaja menggandakan awalan label (mis. kalimat CKPN) ke setiap sub-baris -> kolom
    label tabel itu tidak dibandingkan."""
    chars, numbers = Counter(), Counter()
    for c in table.data.table_cells:
        col = c.start_col_offset_idx
        if skip_label_column and col == 0:
            continue
        chars.update((col, ch) for ch in ft._squash(c.text))
        numbers.update((col, n) for n in ft.THOUSANDS.findall(c.text))
    return chars, numbers


def merged_row_count(doc) -> int:
    return sum(len(ft.merged_rows(t)) for t in doc.tables)


def row_with(doc, page_map, page, label_part):
    for t in doc.tables:
        if not any(page_map.to_original(p.page_no) == page for p in t.prov):
            continue
        for row in t.data.grid:
            if any(label_part in c.text for c in row if not ft._is_value_text(c.text)):
                yield [c.text for c in row]


def real_reports() -> dict:
    summary = {}
    for year in config.YEARS:
        print(f"\nbbca_{year}")
        meta = json.loads(config.parse_meta(year).read_text(encoding="utf-8"))
        page_map = PageMap.from_list(meta["page_map"])
        raw = DoclingDocument.load_from_json(config.docling_json(year))
        doc = DoclingDocument.load_from_json(config.docling_json(year))
        report = ft.fix_document(doc, config.subset(year), page_map)

        sub_row_tables = {f["table"] for f in report.fixed if f["pattern"] == 1}
        lost = [t.self_ref for t0, t in zip(raw.tables, doc.tables)
                if column_content(t0, t.self_ref in sub_row_tables) != column_content(t, t.self_ref in sub_row_tables)]
        check(not lost, f"tidak ada huruf/angka yang hilang, berganda, atau pindah kolom di {len(doc.tables)} tabel"
                        + (f" -- berubah: {lost[:5]}" if lost else ""))
        check(merged_row_count(doc) == len(report.flagged),
              f"sisa baris dua angka ({merged_row_count(doc)}) = baris yang ditandai ({len(report.flagged)})")
        sub_rows_left = sum(ft.is_sub_row_case(t.data.grid[r][0].text)
                            for t in doc.tables for r in ft.merged_rows(t))
        check(sub_rows_left == 0, f"pola 1 tersisa {sub_rows_left} baris")
        again = ft.fix_document(doc, config.subset(year), page_map)
        check(again.sub_rows_fixed + again.printed_lines_fixed + again.split_rows_merged == 0
              and len(again.flagged) == len(report.flagged),
              "idempoten: perbaikan kedua tidak mengubah apa pun")
        got = (report.sub_rows_fixed, report.printed_lines_fixed)
        check(got == EXPECTED_FIXED[year], f"baris diperbaiki pola 1/pola 2 = {got} (tercatat {EXPECTED_FIXED[year]})")
        check(report.split_rows_merged == EXPECTED_MERGED[year],
              f"pola 3 digabung {report.split_rows_merged} pasang baris (tercatat {EXPECTED_MERGED[year]})")
        for spot_year, page, label, values in SPOT_CHECKS:
            if spot_year != year:
                continue
            rows = list(row_with(doc, page_map, page, label))
            ok = any(all(v in row for v in values) for row in rows)
            check(ok, f"hal {page} baris '{label}' berisi {values}")

        # Langkah 2
        pages = sorted(u["page"] for u in report.unlabeled)
        check(pages == EXPECTED_UNLABELED[year],
              f"tabel tanpa label baris: {len(pages)} tabel di halaman yang sudah dicek visual"
              + ("" if pages == EXPECTED_UNLABELED[year] else f" -- dapat {pages}"))
        raw_pages = sorted(u["page"] for u in ft.unlabeled_tables(raw, page_map))
        check(raw_pages == pages, "sama sebelum & sesudah perbaikan Langkah 1")
        orphans = [u["page"] for u in report.unlabeled if not u["left_parts"]]
        check(not orphans, "setiap tabel punya bagian kiri yang menempel tepi kanan halaman sebelumnya"
                           + (f" -- tanpa pasangan: {orphans}" if orphans else ""))
        on_sources = sorted(set(pages) & source_pages(year))
        check(not on_sources, f"tidak ada di {len(source_pages(year))} halaman sumber ground truth"
                              + (f" -- ADA di {on_sources}" if on_sources else ""))
        wrong = sorted(set(pages) & set(COMPLETE_CR5[year]))
        check(not wrong, f"tabel CR5 utuh hal {COMPLETE_CR5[year]} tidak ditandai")

        summary[f"bbca_{year}"] = {**report.to_dict(),
                                   "flagged": [{k: f[k] for k in ("page", "row", "reason", "cells")}
                                               for f in report.flagged],
                                   "unlabeled": report.unlabeled}
    return summary


# ----------------------------------------------------------------- B. uji negatif sintetis

class FakePdf:
    """Pengganti PdfWords: kata-kata buatan di satu halaman (origin kiri-bawah, tinggi 800)."""

    def __init__(self, words):
        self.words = [ft.Word(text, l, r, b, t, rotated) for text, l, r, b, t, rotated in words]

    def page(self, page_no):
        return 800.0, self.words


def tl_box(l, t, r, b):
    """Kotak origin kiri-atas (seperti sel Docling) dari koordinat kiri-bawah halaman tinggi 800."""
    return BoundingBox(l=l, t=800 - t, r=r, b=800 - b, coord_origin=CoordOrigin.TOPLEFT)


def table_doc(label: str, values: list[str], label_box, value_boxes):
    """Satu tabel 2 baris: baris 0 = baris bermasalah, baris 1 = baris penutup tanpa isi."""
    doc = DoclingDocument(name="sintetis")
    doc.add_page(page_no=1, size=Size(width=600, height=800))
    cells = [TableCell(text=label, bbox=label_box, row_span=1, col_span=1, start_row_offset_idx=0,
                       end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1)]
    for j, (v, box) in enumerate(zip(values, value_boxes), start=1):
        cells.append(TableCell(text=v, bbox=box, row_span=1, col_span=1, start_row_offset_idx=0,
                               end_row_offset_idx=1, start_col_offset_idx=j, end_col_offset_idx=j + 1))
    data = TableData(num_rows=2, num_cols=len(values) + 1, table_cells=cells)
    prov = ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=700, r=600, b=600, coord_origin=CoordOrigin.BOTTOMLEFT),
                          charspan=(0, 0))
    doc.add_table(data=data, prov=prov)
    return doc


def synthetic():
    print("\nUji sintetis")
    # dua garis cetak: "Beban A 1.000" di y 680-686 dan "Jumlah B 2.000" di y 670-676
    label_box = tl_box(10, 687, 100, 669)
    value_box = tl_box(300, 687, 340, 669)
    good_words = [("Beban", 10, 35, 680, 686, False), ("A", 37, 42, 680, 686, False),
                  ("1.000", 320, 340, 680, 686, False),
                  ("Jumlah", 10, 40, 670, 676, False), ("B", 42, 47, 670, 676, False),
                  ("2.000", 320, 340, 670, 676, False)]

    def run(words, label="Beban A Jumlah B", values=("1.000 2.000",)):
        doc = table_doc(label, list(values), label_box, [value_box] * len(values))
        before = doc.tables[0].data.model_dump()
        reason = ft.split_printed_lines(doc.tables[0], 0, FakePdf(words))
        return reason, doc.tables[0], before

    reason, table, _ = run(good_words)
    rows = [[c.text for c in row] for row in table.data.grid]
    check(reason is None and rows[:2] == [["Beban A", "1.000"], ["Jumlah B", "2.000"]],
          f"kasus benar dipecah jadi dua baris: {rows[:2]} ({reason})")

    cases = {
        "angka PDF beda dengan sel": [w if w[0] != "2.000" else ("3.000",) + w[1:] for w in good_words],
        "dua angka sebaris": [w if w[0] != "2.000" else ("2.000", 300, 318, 680, 686, False) for w in good_words],
        "teks berputar": [w if w[0] != "1.000" else w[:5] + (True,) for w in good_words],
        "label di bawah angka terakhir": good_words + [("Lanjutan", 10, 45, 660, 666, False)],
    }
    for name, words in cases.items():
        if name == "label di bawah angka terakhir":           # kotak label ikut memanjang ke bawah
            doc = table_doc("Beban A Jumlah B Lanjutan", ["1.000 2.000"], tl_box(10, 687, 100, 659), [value_box])
        else:
            doc = table_doc("Beban A Jumlah B", ["1.000 2.000"], label_box, [value_box])
        before = doc.tables[0].data.model_dump()
        reason = ft.split_printed_lines(doc.tables[0], 0, FakePdf(words))
        check(reason is not None and doc.tables[0].data.model_dump() == before,
              f"{name}: ditandai, tabel tidak berubah ({reason})")

    # pola 1: dua sub-label tapi tiga angka -> tidak dipecah
    doc = table_doc("Kredit Pihak berelasi Pihak ketiga", ["1.000 2.000 3.000"], label_box, [value_box])
    before = doc.tables[0].data.model_dump()
    ok = not ft.split_sub_rows(doc.tables[0], 0) and doc.tables[0].data.model_dump() == before
    check(ok, "pola 1 dengan jumlah angka tak cocok: tidak dipecah, tabel tidak berubah")
    doc = table_doc("Kredit Pihak berelasi Pihak ketiga", ["1.000 2.000"], label_box, [value_box])
    ok = ft.split_sub_rows(doc.tables[0], 0)
    rows = [[c.text for c in row] for row in doc.tables[0].data.grid][:2]
    check(ok and rows == [["Kredit - Pihak berelasi", "1.000"], ["Kredit - Pihak ketiga", "2.000"]],
          f"pola 1 benar: {rows}")

    # pola 3: satu baris cetak dibelah Docling jadi dua baris -> digabung HANYA kalau sejajar di PDF
    def two_rows(upper, lower, upper_y, lower_y, below=None):
        doc = DoclingDocument(name="sintetis")
        doc.add_page(page_no=1, size=Size(width=600, height=800))
        cells = []
        rows = [(upper, upper_y), (lower, lower_y)] + ([(below, (130, 140))] if below else [])
        for r, (texts, (top, bottom)) in enumerate(rows):
            for j, text in enumerate(texts):
                if text:
                    cells.append(TableCell(text=text, bbox=BoundingBox(l=10 + 150 * j, t=top, r=140 + 150 * j, b=bottom,
                                                                       coord_origin=CoordOrigin.TOPLEFT),
                                           row_span=1, col_span=1, start_row_offset_idx=r, end_row_offset_idx=r + 1,
                                           start_col_offset_idx=j, end_col_offset_idx=j + 1))
        prov = ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=700, r=600, b=600, coord_origin=CoordOrigin.BOTTOMLEFT),
                              charspan=(0, 0))
        doc.add_table(data=TableData(num_rows=len(rows), num_cols=3, table_cells=cells), prov=prov)
        return doc
    same_line, next_line = (100, 110), (115, 125)
    cases = [
        ("3a sejajar (JUMLAH LIABILITAS)", ["JUMLAH", "", "1.157"], ["", "1.177", ""], same_line, same_line, "a"),
        ("3b sejajar (JUMLAH ASET)", ["", "1.449", "1.408"], ["JUMLAH", "", ""], same_line, same_line, "b"),
        ("tidak sejajar: subtotal lalu judul bagian berikutnya", ["", "238", "297"], ["Pos-pos", "", ""],
         same_line, next_line, None),
        ("kolom yang sama terisi di kedua baris", ["Kas", "1.000", ""], ["", "2.000", ""], same_line, same_line, None),
        ("baris bawah bukan angka", ["Kas", "", "1.000"], ["", "lihat Catatan", ""], same_line, same_line, None),
    ]
    for name, upper, lower, upper_y, lower_y, expected in cases:
        doc = two_rows(upper, lower, upper_y, lower_y)
        before = doc.tables[0].data.model_dump()
        got = ft.merge_split_row(doc, doc.tables[0], 0)
        rows = [[c.text for c in row] for row in doc.tables[0].data.grid]
        ok = got == expected and (rows == [[a or b for a, b in zip(upper, lower)]] if expected
                                  else doc.tables[0].data.model_dump() == before)
        check(ok, f"pola 3, {name}: {'digabung ' + str(rows) if got else 'tidak digabung, tabel tidak berubah'}")
    # baris di BAWAH pasangan yang digabung harus tetap ada (bug 15-11-2026: _replace_row ikut membuangnya)
    doc = two_rows(["JUMLAH", "", "1.157"], ["", "1.177", ""], same_line, same_line, below=["Dana", "9.063", "7.893"])
    ft.merge_split_row(doc, doc.tables[0], 0)
    rows = [[c.text for c in row] for row in doc.tables[0].data.grid]
    check(rows == [["JUMLAH", "1.177", "1.157"], ["Dana", "9.063", "7.893"]],
          f"pola 3, baris di bawahnya tetap ada: {rows}")

    # Langkah 2: tabel tanpa label baris
    numbers = [["1.000", "2.000"], ["3.000", "-"], ["4.000", "5.000"], ["6.000", "7.000"], ["8.000", "9.000"]]
    labels = [["Kas"] + r for r in [["1.000"], ["2.000"], ["3.000"], ["4.000"], ["5.000"]]]
    header = [["IRB RBA", "SA/ SSFA", "1.250%"]]           # judul kolom hal 215 bbca_2023, isinya "-" semua
    cases = [
        ("menempel tepi kiri, tanpa label", grid_doc(numbers, left=0.2), True),
        ("judul kolom berhuruf+angka diabaikan", grid_doc(header + [["-", "-", "-"]] * 3, left=0.2, header_rows=1), True),
        ("tidak menempel tepi (tabel CR5 utuh: label '< 40%')", grid_doc(numbers, left=41), False),
        ("menempel tepi kiri tapi label diulang", grid_doc(labels, left=0.2), False),
    ]
    for name, doc, expected in cases:
        got = ft.is_unlabeled(doc, doc.tables[0])
        check(got == expected, f"{name}: {'ditandai' if got else 'tidak ditandai'}")


def grid_doc(rows: list[list[str]], left: float, header_rows: int = 0):
    """Satu tabel dari daftar baris; kotaknya mulai `left` pt dari tepi kiri kertas (lebar 600)."""
    doc = DoclingDocument(name="sintetis")
    doc.add_page(page_no=1, size=Size(width=600, height=800))
    cells = [TableCell(text=text, row_span=1, col_span=1, start_row_offset_idx=r, end_row_offset_idx=r + 1,
                       start_col_offset_idx=j, end_col_offset_idx=j + 1, column_header=r < header_rows)
             for r, row in enumerate(rows) for j, text in enumerate(row)]
    data = TableData(num_rows=len(rows), num_cols=max(len(r) for r in rows), table_cells=cells)
    prov = ProvenanceItem(page_no=1, bbox=BoundingBox(l=left, t=700, r=550, b=600, coord_origin=CoordOrigin.BOTTOMLEFT),
                          charspan=(0, 0))
    doc.add_table(data=data, prov=prov)
    return doc


def main():
    summary = real_reports()
    synthetic()
    out = config.RESULTS / "fix_tables.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRingkasan disimpan ke {out.relative_to(config.ROOT)}")
    if failures:
        print(f"\nGAGAL: {len(failures)} pemeriksaan")
        sys.exit(1)
    print("\nLULUS")


if __name__ == "__main__":
    main()
