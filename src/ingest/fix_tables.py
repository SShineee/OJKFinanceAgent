"""
Tugas 5.1 -- tabel sebelum chunking.  docs/PANDUAN_MINGGU5.md, Langkah 1 dan 2.

  Langkah 1  perbaiki sel tabel yang berisi dua angka (`fix_document`)
             + pola 3: satu baris cetak yang DIBELAH Docling jadi dua baris -> digabung (`merge_split_row`)
  Langkah 2  tandai tabel tanpa label baris (`is_unlabeled`, `unlabeled_tables`) -- lihat bagian
             "tabel tanpa label baris" di bawah

Docling kadang menggabungkan DUA baris cetak menjadi satu baris tabel, sehingga satu sel berisi
dua angka (mis. `7.296.837 855.233.239`). Agent yang membaca sel seperti itu tidak bisa tahu
angka mana milik baris mana. Ukuran awal (Minggu 3, Langkah 6): 152 / 101 / 111 sel di laporan
2023 / 2024 / 2025.

Perbaikan dijalankan DI MEMORI, pada DoclingDocument yang dimuat dari .json, sebelum chunking.
File .json di data/markdown/ tidak diubah -- itu sumber kebenaran.

Dua cara, dicoba berurutan untuk setiap baris bermasalah:

  pola 1  label baris memuat k sub-label "Pihak berelasi / Pihak ketiga" dan setiap sel angka
          berisi tepat k angka -> pecah per sub-label. Teks sebelum sub-label pertama (mis.
          kalimat CKPN di label kredit Entitas Induk) ikut di setiap baris baru.
  pola 2  posisi teks di PDF: kata di sekitar baris itu diberikan ke sel terdekat (baris r-1,
          r, r+1) lalu dikelompokkan per garis cetak. Angka sel ini yang tercetak di garis milik
          baris tetangga -> dipindah ke sel KOSONG tetangga itu. Garis lain yang berisi angka ->
          baris baru; garis label tanpa angka ikut garis berangka di bawahnya.
          Hanya dilakukan kalau teks PDF di setiap sel cocok PERSIS dengan isi sel Docling --
          kalau tidak (atau garisnya dipakai bersama label baris tetangga, teks berputar, dua
          angka sejajar), baris dibiarkan apa adanya dan DITANDAI.

Baris yang tetap berisi sel dua angka (`merged_rows`) -> chunk-nya diberi metadata
`merged_cells` (Langkah 4), dan Extraction Agent wajib mengecek ulang angkanya.

PDF yang dibaca adalah PDF POTONGAN (data/markdown/<kode>_<tahun>.subset.pdf): nomor halaman
Docling (`page_no`) adalah nomor halaman di PDF itu, dan isinya sudah diverifikasi sama dengan
halaman aslinya (subset_pdf.verify_subset). Kata dibaca dengan docling-parse -- pembaca yang
sama dengan Docling, jadi hurufnya identik dengan isi sel (pypdfium2 kehilangan huruf di
sebagian halaman BCA). Teks tak tampak di luar area halaman (temuan Minggu 3) tidak ikut,
karena hanya kata di sekitar baris yang dipakai.

Cek:  python -m src.ingest.fix_tables data/markdown/bbca_2024.json --show
Uji:  python scripts/check_fix_tables.py
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from docling_core.types.doc import BoundingBox, CoordOrigin, DoclingDocument, TableCell, TableItem

THOUSANDS = re.compile(r"\(?\d{1,3}(?:\.\d{3})+\)?")       # 855.233.239 / (394.843)
SUB_LABEL = re.compile(r"Pihak berelasi|Pihak ketiga", re.I)
VALUE_WORD = re.compile(r"^(?:[(\-]?\d[\d.,]*\)?[*%]?|-)$")  # 1.234 / (394.843) / 8. / 50% / -
ITEM_NUMBER = re.compile(r"^(?:\d{1,3}|[a-z])\.$")             # nomor butir "3." / "a." -- bagian label
LETTERS = re.compile(r"[A-Za-z]{3,}")

DASHES = str.maketrans({"–": "-", "—": "-", "−": "-"})   # en/em dash, minus -> "-"

ROW_PAD = 1.0          # pt -- kelonggaran kotak sel di atas/bawah
MAX_GAP = 4.0          # pt -- jarak maksimum kata ke kotak sel yang memotong ujung teksnya
LINE_TOLERANCE = 3.0   # pt -- selisih pusat vertikal maksimum dalam satu garis cetak
LABEL_SHARE = 0.5      # kolom label = >= 50% sel tak kosongnya berisi kata

PAGE_EDGE = 3.0        # pt -- kotak tabel sejauh ini dari tepi kertas = menempel tepi (tabel dua halaman)
LABEL_GUARD = 0.5      # bagian kanan yang >= 50% baris angkanya diawali label = labelnya diulang
NUM_CELL = re.compile(r"^[\s(\-]*\d[\d.,]*[\s)%]*$")       # sel angka (definisi audit Minggu 3)


# ----------------------------------------------------------------- deteksi

def merged_rows(table: TableItem) -> list[int]:
    """Baris yang punya sel di kolom ke-2 dst. berisi >= 2 angka berformat ribuan.
    Definisi sama dengan pengukuran Minggu 3, Langkah 6, supaya angkanya bisa dibandingkan."""
    return [r for r, row in enumerate(table.data.grid)
            if any(len(THOUSANDS.findall(c.text)) >= 2 for c in row[1:])]


def count_merged_cells(doc: DoclingDocument) -> int:
    """Jumlah sel berisi >= 2 angka (hitungan grid, sama dengan Minggu 3)."""
    return sum(len(THOUSANDS.findall(c.text)) >= 2
               for t in doc.tables for row in t.data.grid for c in row[1:])


def is_sub_row_case(label: str) -> bool:
    return len(SUB_LABEL.findall(label)) >= 2


def _is_value_text(text: str) -> bool:
    words = text.split()
    return bool(words) and all(VALUE_WORD.match(w) for w in words)


# ----------------------------------------------------------------- penulisan ulang sel

def _row_cells(table: TableItem, r: int) -> list[TableCell]:
    return sorted((c for c in table.data.table_cells if c.start_row_offset_idx == r),
                  key=lambda c: c.start_col_offset_idx)


def _row_problem(table: TableItem, r: int) -> str | None:
    for c in table.data.table_cells:
        if c.start_row_offset_idx <= r < c.end_row_offset_idx:
            if c.end_row_offset_idx - c.start_row_offset_idx > 1:
                return "ada sel yang merentang beberapa baris"
            if c.column_header:
                return "baris header kolom"
    return None


def _new_cell(template: TableCell | None, row: int, col: int, text: str,
              bbox: BoundingBox | None) -> TableCell:
    if template is None:
        return TableCell(text=text, bbox=bbox, row_span=1, col_span=1,
                         start_row_offset_idx=row, end_row_offset_idx=row + 1,
                         start_col_offset_idx=col, end_col_offset_idx=col + 1)
    d = template.model_copy(deep=True)
    d.start_row_offset_idx, d.end_row_offset_idx, d.row_span = row, row + 1, 1
    d.text = text
    if bbox is not None:
        d.bbox = bbox
    return d


def _replace_row(table: TableItem, r: int, new_rows: list[dict[int, tuple[str, BoundingBox | None]]]):
    """Ganti baris r dengan len(new_rows) baris. new_rows[i] = {kolom awal sel: (teks, bbox)}.
    Kolom awal = kolom awal sel lama yang menutupi posisi itu (sel lebar tetap lebar), atau
    kolom baru kalau Docling tidak punya sel di sana."""
    k = len(new_rows)
    templates = {c.start_col_offset_idx: c for c in table.data.table_cells if c.start_row_offset_idx == r}
    # buang baris r lama DULU, baru geser baris di bawahnya. Urutan terbalik menghapus baris r+1
    # juga kalau k = 0 (hapus baris, pola 3): baris r+1 tergeser ke r lalu ikut terbuang.
    cells = [c for c in table.data.table_cells if c.start_row_offset_idx != r]
    for c in cells:
        if c.start_row_offset_idx > r:
            c.start_row_offset_idx += k - 1
            c.end_row_offset_idx += k - 1
    new = [_new_cell(templates.get(col), r + i, col, text, bbox)
           for i, contents in enumerate(new_rows)
           for col, (text, bbox) in sorted(contents.items()) if text]
    table.data.table_cells = cells + new
    table.data.num_rows += k - 1


# ----------------------------------------------------------------- pola 1

def split_sub_rows(table: TableItem, r: int) -> bool:
    """Pola 1: label memuat k sub-label dan SETIAP sel berangka berisi tepat k angka -> pecah
    menjadi k baris. Sel tanpa angka (mis. nomor Catatan "2g,2m,12") ikut baris pertama.
    False = syarat tidak terpenuhi, tabel tidak diubah."""
    if _row_problem(table, r):
        return False
    old = _row_cells(table, r)
    if not old or old[0].start_col_offset_idx != 0:
        return False
    label = old[0].text
    subs = [m.group(0) for m in SUB_LABEL.finditer(label)]
    k = len(subs)
    if k < 2:
        return False
    numbers = {c.start_col_offset_idx: THOUSANDS.findall(c.text) for c in old[1:]}
    for c in old[1:]:
        found = numbers[c.start_col_offset_idx]
        if found and (len(found) != k or _squash(" ".join(found)) != _squash(c.text)):
            return False                              # angka bukan k buah, atau ada teks lain
    prefix = label[:SUB_LABEL.search(label).start()].strip()
    new_rows = []
    for i in range(k):
        row = {0: (f"{prefix} - {subs[i]}" if prefix else subs[i], None)}
        for c in old[1:]:
            found = numbers[c.start_col_offset_idx]
            text = found[i] if found else (c.text if i == 0 else "")
            row[c.start_col_offset_idx] = (text, None if found else c.bbox)
        new_rows.append(row)
    _replace_row(table, r, new_rows)
    return True


# ----------------------------------------------------------------- pola 2: teks PDF per garis

@dataclass
class Word:
    """Satu kata/angka dari docling-parse, koordinat origin kiri-bawah (y naik ke atas)."""
    text: str
    left: float
    right: float
    bottom: float
    top: float
    rotated: bool = False     # teks miring/berputar (tabel yang dicetak menyamping)
    column: int = -1          # kolom awal sel Docling tempat kata ini jatuh

    @property
    def cy(self) -> float:
        return (self.bottom + self.top) / 2


class PdfWords:
    """Kata beserta kotaknya per halaman PDF potongan, dibaca dengan docling-parse -- pembaca
    yang SAMA dengan yang dipakai Docling saat parse, jadi hurufnya identik dengan isi sel.
    (pypdfium2 tidak dipakai: di beberapa halaman BCA ia kehilangan huruf, mis. "Obli i b di i"
    untuk "Obligasi subordinasi" dan "(9296)" untuk "(9.296)".)"""

    def __init__(self, pdf_path: str | Path):
        from docling_parse.pdf_parser import DoclingPdfParser
        self._doc = DoclingPdfParser(loglevel="fatal").load(path_or_stream=str(pdf_path))
        self._pages: dict[int, tuple[float, list[Word]]] = {}

    def close(self):
        self._doc.unload()         # Windows: file yang masih dibuka tidak bisa dihapus

    def page(self, page_no: int) -> tuple[float, list[Word]]:
        """(tinggi halaman, kata tampak) untuk page_no Docling (mulai 1)."""
        if page_no not in self._pages:
            from docling_core.types.doc.page import PdfCellRenderingMode, TextCellUnit
            page = self._doc.get_page(page_no)
            words = []
            for cell in page.iterate_cells(unit_type=TextCellUnit.WORD):
                if cell.rendering_mode == PdfCellRenderingMode.INVISIBLE or not cell.text.strip():
                    continue
                rect = cell.rect
                rotated = abs(rect.r_y1 - rect.r_y0) > 0.5 or rect.r_x1 <= rect.r_x0
                b = rect.to_bounding_box()
                if b.coord_origin != CoordOrigin.BOTTOMLEFT:
                    b = b.to_bottom_left_origin(page.dimension.height)
                words.append(Word(cell.text.translate(DASHES), b.l, b.r, b.b, b.t, rotated))
            self._pages[page_no] = (page.dimension.height, words)
        return self._pages[page_no]


def _bottom_left(bbox: BoundingBox, height: float) -> BoundingBox:
    return bbox if bbox.coord_origin == CoordOrigin.BOTTOMLEFT else bbox.to_bottom_left_origin(height)


def _label_columns(table: TableItem) -> set[int]:
    """Kolom yang sebagian besar sel tak kosongnya berisi kata -> kolom label."""
    filled, worded = Counter(), Counter()
    for c in table.data.table_cells:
        if c.column_header or not c.text.strip():
            continue
        filled[c.start_col_offset_idx] += 1
        worded[c.start_col_offset_idx] += bool(LETTERS.search(c.text))
    return {j for j in filled if worded[j] / filled[j] >= LABEL_SHARE}


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text.translate(DASHES))


def _assign_words(table: TableItem, r: int, page_words: list[Word],
                  height: float) -> dict[tuple[int, int], list[Word]] | None:
    """Kata PDF di sekitar baris r, dibagi ke sel baris r-1, r, dan r+1: {(baris, kolom awal
    sel): kata, urut garis lalu x}.

    Hanya kata di rentang tinggi baris r yang dibaca. Setiap kata diberikan ke sel yang
    tingginya memuat kata itu dan yang kotaknya paling bertumpuk dengan kata itu; kalau sama
    (sel tinggi baris r vs sel satu garis baris tetangga di kolom yang sama), sel yang lebih
    pendek menang. Kotak sel Docling kadang memotong ujung teks ("Ban" untuk "Bank"), jadi kata
    yang tidak bertumpuk masih boleh masuk ke sel terdekat dalam jarak MAX_GAP.
    None = ada sel baris r yang berisi teks tetapi tanpa koordinat."""
    boxed = []
    for q in (r - 1, r, r + 1):
        if not 0 <= q < table.data.num_rows:
            continue
        for c in _row_cells(table, q):
            if not c.text.strip():
                continue
            if c.bbox is None:
                if q == r:
                    return None
                continue
            boxed.append((q, c.start_col_offset_idx, _bottom_left(c.bbox, height)))
    own = [b for q, _, b in boxed if q == r]
    if not own:
        return None
    top = max(b.t for b in own) + ROW_PAD
    bottom = min(b.b for b in own) - ROW_PAD
    assigned: dict[tuple[int, int], list[Word]] = {(q, col): [] for q, col, _ in boxed}
    for w in page_words:
        if not bottom <= w.cy <= top:
            continue
        best, best_score = None, None
        for q, col, b in boxed:
            if not b.b - ROW_PAD <= w.cy <= b.t + ROW_PAD:
                continue
            overlap = min(w.right, b.r) - max(w.left, b.l)          # < 0 = jarak
            if overlap < -MAX_GAP:
                continue
            score = (round(overlap * 2) / 2, -(b.t - b.b))           # tumpuk dulu, lalu yang pendek
            if best_score is None or score > best_score:
                best, best_score = (q, col), score
        if best is not None:
            assigned[best].append(Word(w.text, w.left, w.right, w.bottom, w.top, w.rotated, best[1]))
    for key in assigned:
        assigned[key] = [w for line in _word_lines(assigned[key]) for w in line]
    return assigned


def _word_lines(words: list[Word]) -> list[list[Word]]:
    """Kelompokkan kata per garis cetak (pusat vertikal berdekatan), dari atas ke bawah."""
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: -w.cy):
        if lines and lines[-1][0].cy - w.cy <= LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w.left) for line in lines]


def _is_amount(w: Word) -> bool:
    return bool(VALUE_WORD.match(w.text)) and not ITEM_NUMBER.match(w.text)


def split_printed_lines(table: TableItem, r: int, pdf: "PdfWords") -> str | None:
    """Pola 2: susun ulang baris r menurut garis cetak di PDF. None = berhasil; selain itu
    alasan tidak diperbaiki (tabel tidak diubah)."""
    problem = _row_problem(table, r)
    if problem:
        return problem
    page_nos = {p.page_no for p in table.prov}
    if len(page_nos) != 1:
        return "tabel lintas halaman"
    height, page_words = pdf.page(page_nos.pop())

    old = _row_cells(table, r)
    assigned = _assign_words(table, r, page_words, height)
    if assigned is None:
        return "sel tanpa koordinat"
    words_of = {col: ws for (q, col), ws in assigned.items() if q == r}
    if any(w.rotated for ws in assigned.values() for w in ws):
        return "teks berputar (tabel dicetak menyamping)"   # posisi y bukan garis cetak

    # 1. teks PDF di setiap kotak sel harus sama dengan isi sel Docling
    for c in old:
        if not c.text.strip():
            continue
        pdf_words = [w.text for w in words_of[c.start_col_offset_idx]]
        if _is_value_text(c.text):
            if Counter(pdf_words) != Counter(c.text.translate(DASHES).split()):
                return f"angka PDF di kolom {c.start_col_offset_idx} tidak cocok dengan sel Docling"
        elif Counter(_squash(" ".join(pdf_words))) != Counter(_squash(c.text)):
            return f"teks PDF di kolom {c.start_col_offset_idx} tidak cocok dengan sel Docling"

    # 2. garis yang juga berisi kata baris tetangga = garis milik tetangga itu. Yang boleh hanya:
    #    ANGKA sel ini di garis itu, dipindah ke sel KOSONG tetangga di kolom yang sama.
    #    Label sel ini di garis tetangga (label dan angkanya terpisah baris) -> ditandai saja.
    lines = _word_lines([w for ws in words_of.values() for w in ws])
    neighbour_words = {q: [w for (qq, _), ws in assigned.items() if qq == q for w in ws]
                       for q in (r - 1, r + 1)}
    grid = table.data.grid
    value_cells = {c.start_col_offset_idx for c in old if _is_value_text(c.text)}
    kept: list[list[Word]] = []
    moves: list[tuple[int, Word]] = []               # (baris tujuan, kata)
    for words in lines:
        cy = statistics.median(w.cy for w in words)
        shared = [q for q, ws in neighbour_words.items() if any(abs(w.cy - cy) <= LINE_TOLERANCE for w in ws)]
        if not shared:
            kept.append(words)
            continue
        if len(shared) > 1 or _row_problem(table, shared[0]):
            return "garis cetak dipakai bersama baris tetangga"
        home = shared[0]
        for w in words:
            if not _is_amount(w) or w.column not in value_cells or grid[home][w.column].text.strip():
                return "garis cetak dipakai bersama baris tetangga"
            moves.append((home, w))

    # 3. setiap garis berangka -> satu baris baru
    label_cols = _label_columns(table)
    is_value_word = lambda w: _is_amount(w) and w.column not in label_cols
    number_lines = [i for i, words in enumerate(kept) if any(is_value_word(w) for w in words)]
    if not number_lines:
        return "tidak ada garis berangka"
    for i in number_lines:
        per_column = Counter(w.column for w in kept[i] if is_value_word(w))
        if any(n > 1 for n in per_column.values()):
            return "dua angka sebaris dalam satu sel"
    if len(number_lines) == 1 and not moves:
        return "angka dalam satu garis cetak (bukan dua baris yang digabung)"

    # garis tanpa angka (label terlipat / judul sub-baris) ikut garis berangka DI BAWAHNYA:
    # laporan BCA mencetak angka sejajar garis label terakhir. Garis tanpa angka di bawah garis
    # berangka terakhir = awal label baris berikutnya yang salah ditaruh Docling -> ditandai.
    if number_lines[-1] < len(kept) - 1:
        return "label di bawah angka terakhir (milik baris berikutnya)"
    groups: dict[int, list[int]] = {i: [] for i in number_lines}
    for i in range(len(kept)):
        groups[next(n for n in number_lines if n >= i)].append(i)

    templates = {c.start_col_offset_idx: c for c in old}

    def as_bbox(words: list[Word], template: TableCell | None) -> BoundingBox:
        box = BoundingBox(l=min(w.left for w in words), r=max(w.right for w in words),
                          b=min(w.bottom for w in words), t=max(w.top for w in words),
                          coord_origin=CoordOrigin.BOTTOMLEFT)
        origin = template.bbox.coord_origin if template is not None and template.bbox else CoordOrigin.TOPLEFT
        return box.to_top_left_origin(height) if origin == CoordOrigin.TOPLEFT else box

    # 1) angka nyasar -> sel kosong baris tetangga (sebelum baris r diganti: indeks r+1 ikut bergeser)
    for home, w in moves:
        template = templates.get(w.column)
        table.data.table_cells = [c for c in table.data.table_cells
                                  if not (c.start_row_offset_idx == home and c.start_col_offset_idx == w.column
                                          and not c.text.strip())]
        table.data.table_cells.append(_new_cell(template, home, w.column, w.text, as_bbox([w], template)))
    # 2) baris r -> satu baris per garis berangka
    new_rows = []
    for n in number_lines:
        by_column: dict[int, list[Word]] = {}
        for i in groups[n]:
            for w in kept[i]:
                by_column.setdefault(w.column, []).append(w)
        new_rows.append({col: (" ".join(w.text for w in words), as_bbox(words, templates.get(col)))
                         for col, words in by_column.items() if col < table.data.num_cols})
    _replace_row(table, r, new_rows)
    return None


# ----------------------------------------------------------------- pola 3: satu baris cetak, dua baris Docling
#
# Kebalikan pola 2: Docling MEMBELAH satu baris cetak menjadi dua baris tabel (15-11-2026, Minggu 5
# Langkah 6, ditemukan saat inspeksi neraca konsolidasian bbca_2024):
#   a. label + sebagian angka | baris tanpa label berisi angka di kolom yang kosong
#      "JUMLAH LIABILITAS | | | 1.157.675.545" lalu "| | | 1.177.403.108 | |" (hal 541)
#   b. baris angka tanpa label | baris label tanpa angka
#      "| | | 1.449.301.328 | 1.408.107.010" lalu "JUMLAH ASET | | | |" (hal 540)
# Bentuk yang sama jauh lebih sering berarti dua baris cetak yang MEMANG berbeda (subtotal tanpa
# label lalu judul bagian berikutnya): 72 / 75 / 40 kandidat di laporan BCA, hanya 2 / 4 / 1 yang
# label dan angkanya sejajar. Jadi digabung HANYA kalau kotak label tumpang tindih vertikal dengan
# SETIAP kotak angka baris pasangannya di halaman PDF.

NUMERIC_CELL = re.compile(r"^\(?-?\d[\d.,]*\)?%?$|^-$")


def _cells_with_text(table: TableItem, r: int) -> dict[int, TableCell]:
    return {c.start_col_offset_idx: c for c in _row_cells(table, r) if c.text.strip()}


def _vertical_overlap(doc: DoclingDocument, table: TableItem, a: TableCell, b: TableCell) -> float:
    height = doc.pages[table.prov[0].page_no].size.height
    boxes = [c.bbox if c.bbox.coord_origin == CoordOrigin.TOPLEFT else c.bbox.to_top_left_origin(height)
             for c in (a, b)]
    return min(boxes[0].b, boxes[1].b) - max(boxes[0].t, boxes[1].t)


def merge_split_row(doc: DoclingDocument, table: TableItem, r: int) -> str | None:
    """Pola 3: gabungkan baris r dan r+1 kalau keduanya satu baris cetak (lihat di atas).
    Return "a"/"b" (jenis pola) kalau digabung, None kalau tidak (tabel tidak diubah)."""
    if r + 1 >= table.data.num_rows or not table.prov or _row_problem(table, r) or _row_problem(table, r + 1):
        return None
    upper, lower = _cells_with_text(table, r), _cells_with_text(table, r + 1)
    if not upper or not lower or set(upper) & set(lower):
        return None                                   # baris kosong, atau ada kolom yang terisi dua-duanya
    values = lambda cells: [c for col, c in cells.items() if col > 0]
    numeric = lambda cells: all(NUMERIC_CELL.match(c.text.strip()) for c in values(cells))
    if (0 in upper and LETTERS.search(upper[0].text) and values(upper) and numeric(upper)
            and 0 not in lower and numeric(lower)):
        kind, label, numbers = "a", upper[0], values(lower)
    elif 0 not in upper and values(upper) and numeric(upper) and set(lower) == {0} and LETTERS.search(lower[0].text):
        kind, label, numbers = "b", lower[0], values(upper)
    else:
        return None
    if label.bbox is None or any(c.bbox is None for c in numbers):
        return None
    if any(_vertical_overlap(doc, table, label, c) <= 0 for c in numbers):
        return None                                   # tidak sejajar: dua baris cetak yang berbeda
    merged = {col: (c.text, c.bbox) for col, c in {**upper, **lower}.items()}
    _replace_row(table, r + 1, [])                    # hapus baris bawah
    _replace_row(table, r, [merged])
    return kind


# ----------------------------------------------------------------- Langkah 2: tabel tanpa label baris
#
# Tabel Pilar 3 yang lebar dicetak melintasi DUA halaman berhadapan: label baris + kolom pertama di
# halaman kiri, kolom sisanya di halaman kanan. Docling membacanya sebagai dua tabel terpisah, dan
# tabel halaman kanan berisi angka yang tidak jelas milik baris apa -> tidak diindeks (Minggu 6).
#
# Cirinya geometris: tabel dua halaman dicetak sampai ke lipatan, jadi kotak bagian kanannya
# MENEMPEL TEPI KIRI kertas (0-0,3 pt di BCA; tabel biasa >= 20 pt) dan bagian kirinya menempel
# tepi kanan halaman sebelumnya. Pengaman: kalau bagian kanan ternyata mengulang label barisnya
# (>= 50% baris angka diawali teks berhuruf), tabel itu tidak ditandai.
#
# Definisi audit Minggu 3 ("< 20% baris angka berisi huruf") ternyata keliru di 5 tabel per laporan
# (15-11-2026, dicek dengan render PDF): salah tandai tabel CR5 yang utuh (label barisnya "Bobot
# Risiko" `< 40%`, `75%` -- tanpa huruf), dan melewatkan bagian kanan CR4/CR5 + CCR3 kolom f-l yang
# baris judul kolomnya ("Lainnya", "Tagihan Bersih ...") dilebur Docling ke baris data.

def _first_cell_labels(table: TableItem) -> tuple[int, int]:
    """(baris berangka di luar baris judul kolom, yang sel tak kosong pertamanya berhuruf)."""
    header = {c.start_row_offset_idx for c in table.data.table_cells if c.column_header}
    rows = labeled = 0
    for r, row in enumerate(table.data.grid):
        texts = [c.text.strip() for c in row]
        if r in header or not any(NUM_CELL.match(x) for x in texts if x):
            continue
        rows += 1
        labeled += bool(LETTERS.search(next(x for x in texts if x)))
    return rows, labeled


def _touches_edge(doc: DoclingDocument, table: TableItem, side: str) -> bool:
    if not table.prov:
        return False
    prov = table.prov[0]
    if side == "left":
        return prov.bbox.l <= PAGE_EDGE
    return doc.pages[prov.page_no].size.width - prov.bbox.r <= PAGE_EDGE


def is_unlabeled(doc: DoclingDocument, table: TableItem) -> bool:
    """Bagian kanan tabel dua halaman: menempel tepi kiri kertas dan barisnya tanpa label."""
    if not _touches_edge(doc, table, "left"):
        return False
    rows, labeled = _first_cell_labels(table)
    return rows == 0 or labeled / rows < LABEL_GUARD


def unlabeled_tables(doc: DoclingDocument, page_map=None) -> list[dict]:
    """Semua tabel tanpa label baris + kandidat bagian kirinya: tabel di halaman sebelumnya yang
    menempel tepi kanan kertas (kosong kalau tidak ada, mis. halaman kirinya tidak lolos penyaring;
    bisa dua kalau halaman kiri memuat dua tabel lebar)."""
    orig = (lambda p: page_map.to_original(p)) if page_map is not None else (lambda p: p)
    out = []
    for table in doc.tables:
        if not is_unlabeled(doc, table):
            continue
        page_no = table.prov[0].page_no
        left_parts = [t.self_ref for t in doc.tables
                      if t.prov and t.prov[0].page_no == page_no - 1
                      and orig(page_no - 1) == orig(page_no) - 1 and _touches_edge(doc, t, "right")]
        out.append({"page": orig(page_no), "subset_page": page_no, "table": table.self_ref,
                    "shape": [table.data.num_rows, table.data.num_cols], "left_parts": left_parts})
    return out


# ----------------------------------------------------------------- satu dokumen

@dataclass
class FixReport:
    merged_cells_before: int = 0
    merged_cells_after: int = 0
    sub_rows_fixed: int = 0                 # pola 1
    printed_lines_fixed: int = 0            # pola 2
    split_rows_merged: int = 0              # pola 3: satu baris cetak yang dibelah Docling, digabung
    fixed: list[dict] = field(default_factory=list)     # baris yang diperbaiki (untuk cek visual)
    flagged: list[dict] = field(default_factory=list)   # baris yang tetap bermasalah + alasannya
    unlabeled: list[dict] = field(default_factory=list) # Langkah 2: tabel tanpa label baris -> excluded

    def unlabeled_refs(self) -> set[str]:
        return {u["table"] for u in self.unlabeled}

    def to_dict(self) -> dict:
        excluded = self.unlabeled_refs()
        return {
            "merged_cells_before": self.merged_cells_before,
            "merged_cells_after": self.merged_cells_after,
            "sub_rows_fixed": self.sub_rows_fixed,
            "printed_lines_fixed": self.printed_lines_fixed,
            "split_rows_merged": self.split_rows_merged,
            "flagged_rows": len(self.flagged),
            "flagged_rows_in_unlabeled_tables": sum(f["table"] in excluded for f in self.flagged),
            "flagged_reasons": dict(Counter(f["reason"] for f in self.flagged).most_common()),
            "unlabeled_tables": len(self.unlabeled),
            "unlabeled_pages": sorted({u["page"] for u in self.unlabeled}),
        }


def fix_document(doc: DoclingDocument, subset_pdf: str | Path, page_map=None) -> FixReport:
    """Perbaiki semua tabel `doc` DI TEMPAT (Langkah 1), lalu catat tabel tanpa label baris
    (Langkah 2). `page_map` (PageMap) hanya untuk nomor halaman asli di laporan."""
    report = FixReport(merged_cells_before=count_merged_cells(doc))
    pdf = PdfWords(subset_pdf)
    try:
        for table in doc.tables:
            page = table.prov[0].page_no if table.prov else None
            if page is not None and page_map is not None:
                page = page_map.to_original(page)
            # pola 3 lebih dulu (selnya satu angka, jadi tidak menyentuh baris pola 1/2), supaya nomor
            # baris yang dicatat pola 1/2 di bawah tidak bergeser lagi sesudahnya
            for r in reversed(range(table.data.num_rows - 1)):
                kind = merge_split_row(doc, table, r)
                if kind:
                    report.split_rows_merged += 1
                    report.fixed.append({"page": page, "subset_page": table.prov[0].page_no, "table": table.self_ref,
                                         "row": r, "pattern": 3, "kind": kind,
                                         "after": [[c.text for c in table.data.grid[r]]]})
            for r in reversed(merged_rows(table)):     # dari bawah: indeks baris di atas tetap
                before = [c.text for c in table.data.grid[r]]
                rows_before = table.data.num_rows
                boxes = [c.bbox for c in _row_cells(table, r) if c.bbox is not None]
                region = None                          # area baris (origin kiri-atas) -- untuk cek visual
                if boxes and table.prov:
                    h = doc.pages[table.prov[0].page_no].size.height
                    tl = [b if b.coord_origin == CoordOrigin.TOPLEFT else b.to_top_left_origin(h) for b in boxes]
                    region = [min(b.l for b in tl), min(b.t for b in tl), max(b.r for b in tl), max(b.b for b in tl)]
                entry = {"page": page, "subset_page": table.prov[0].page_no if table.prov else None,
                         "table": table.self_ref, "row": r, "cells": before, "region": region}
                after = lambda: [[c.text for c in row] for row in    # baris r-1 .. baris baru terakhir + 1
                                 table.data.grid[max(r - 1, 0): r + table.data.num_rows - rows_before + 2]]
                if is_sub_row_case(before[0]) and split_sub_rows(table, r):
                    report.sub_rows_fixed += 1
                    report.fixed.append({**entry, "pattern": 1, "after": after()})
                    continue
                reason = split_printed_lines(table, r, pdf)
                if reason is None:
                    report.printed_lines_fixed += 1
                    report.fixed.append({**entry, "pattern": 2, "after": after()})
                else:
                    report.flagged.append({**entry, "reason": reason})
    finally:
        pdf.close()
    report.merged_cells_after = count_merged_cells(doc)
    report.unlabeled = unlabeled_tables(doc, page_map)
    return report


def load_fixed(year: int, ticker: str | None = None) -> tuple[DoclingDocument, FixReport]:
    """Muat data/markdown/<kode>_<tahun>.json lalu perbaiki tabelnya di memori."""
    from src import config
    from src.ingest.subset_pdf import PageMap
    ticker = ticker or config.DEV_TICKER
    meta = json.loads(config.parse_meta(year, ticker).read_text(encoding="utf-8"))
    doc = DoclingDocument.load_from_json(config.docling_json(year, ticker))
    report = fix_document(doc, config.subset(year, ticker), PageMap.from_list(meta["page_map"]))
    return doc, report


def main(argv=None):
    import warnings
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    warnings.filterwarnings("ignore", message="Table cell bbox")   # bbox di luar halaman, di-clamp Docling
    from src.ingest.detect_metadata import parse_file_name

    ap = argparse.ArgumentParser(description="Perbaiki sel tabel berisi dua angka & tandai tabel tanpa label (di memori).")
    ap.add_argument("json", type=Path, nargs="+", help="data/markdown/<kode>_<tahun>.json")
    ap.add_argument("--show", action="store_true", help="tampilkan baris & tabel yang ditandai")
    args = ap.parse_args(argv)
    for path in args.json:
        ticker, year = parse_file_name(path)
        _, report = load_fixed(year, ticker)
        d = report.to_dict()
        print(f"{path.name}: sel dua angka {d['merged_cells_before']} -> {d['merged_cells_after']}; "
              f"pola 1 diperbaiki {d['sub_rows_fixed']} baris, pola 2 {d['printed_lines_fixed']} baris, "
              f"pola 3 digabung {d['split_rows_merged']} pasang baris, "
              f"ditandai {d['flagged_rows']} baris")
        for reason, n in d["flagged_reasons"].items():
            print(f"    {n:>3}  {reason}")
        print(f"    tabel tanpa label baris: {d['unlabeled_tables']} di hal {d['unlabeled_pages']} "
              f"({d['flagged_rows_in_unlabeled_tables']} baris ditandai di atas ada di tabel ini)")
        if args.show:
            for f in report.flagged:
                print(f"    hal {f['page']} baris {f['row']}: {f['reason']} | "
                      f"{' | '.join(x[:30] for x in f['cells'])}")
            for u in report.unlabeled:
                print(f"    tanpa label: hal {u['page']} {u['table']} {u['shape'][0]}x{u['shape'][1]}, "
                      f"bagian kiri {u['left_parts']}")


if __name__ == "__main__":
    main()
