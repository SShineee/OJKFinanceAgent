"""
Tugas 3.1 -- penyaring halaman: pilih halaman PDF yang perlu diproses Docling.

Docling pada 700 halaman terlalu lama untuk pengguna yang mengunggah lewat Telegram,
jadi halaman disaring dulu dengan ekstraksi teks cepat (pypdf, belasan detik per laporan).
Hanya halaman yang lolos yang diteruskan ke Docling (Langkah 2-3).

Halaman LOLOS kalau:
  1. memuat salah satu penanda satuan tabel keuangan ("dalam jutaan rupiah", dst.), ATAU
  2. memuat paling sedikit MIN_RATIO_TERMS istilah rasio. Tabel rasio resmi berisi
     persen, bukan Rupiah, jadi tidak punya penanda satuan -- tanpa aturan ini tabel itu
     terlewat di laporan 2023 (hal 19) dan 2024 (hal 21).

Sengaja TIDAK mencocokkan judul bagian ("ikhtisar data keuangan", "laporan posisi
keuangan"): header navigasi BCA mencetak judul itu di hampir setiap halaman (cocok di
257 halaman, Minggu 1).

Nomor halaman = indeks PDF mulai 1 (halaman fisik ke-n), belum tentu sama dengan nomor
yang tercetak di dokumen.

Jalankan:  python -m src.ingest.page_filter                          (semua PDF di data/raw)
           python -m src.ingest.page_filter data/raw/bbca_2024.pdf
Kriteria selesai:  python scripts/check_page_filter.py
"""

import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PdfReader

# Naikkan setiap aturan di bawah berubah. Disimpan di .meta.json (Langkah 3), jadi hasil
# parse yang dibuat dengan aturan lama bisa dikenali dan diparse ulang.
#   1 (28-10-2026) penanda satuan + >= 3 istilah rasio, teks hanya di-lowercase
#   2 (30-10-2026) + normalize(): istilah yang terpotong ganti baris / tanda hubung tetap cocok
RULE_VERSION = 2

# satuan -> penandanya. Kunci satuan dipakai juga oleh detect_metadata & .meta.json.
UNIT_MARKERS = {
    "million_idr": ["dalam jutaan rupiah", "in millions of rupiah"],
    "billion_idr": ["dalam miliaran rupiah", "dalam miliar rupiah", "in billions of rupiah"],
    # Untuk emiten berlaporan Dolar AS (risiko R15). BELUM DIUJI pada laporan sungguhan --
    # di ketiga laporan BCA penanda ini muncul di 0 halaman.
    "thousand_usd": ["dalam ribuan dolar amerika serikat", "in thousands of us dollars",
                     "in thousands of united states dollars"],
}
RATIO_TERMS = [
    "capital adequacy ratio", "non performing loan", "return on asset",
    "return on equity", "net interest margin", "loan to deposit ratio",
    "beban operasional terhadap pendapatan operasional",
]
MIN_RATIO_TERMS = 3

MIN_TEXT_CHARS = 50   # halaman dengan teks lebih sedikit dianggap kosong / berupa gambar


@dataclass
class PageSelection:
    source: str                        # nama file PDF
    total_pages: int
    pages: list[int]                   # halaman lolos: nomor ASLI mulai 1, urut naik
    reasons: dict[int, str]            # halaman -> "unit" / "ratio" / "unit+ratio"
    unit: str | None                   # satuan dominan, mis. "million_idr"; None = tanpa penanda
    unit_page_counts: dict[str, int]   # satuan -> jumlah halaman yang memuat penandanya
    empty_pages: int                   # halaman (hampir) tanpa teks; banyak = PDF hasil scan
    seconds: float = 0.0               # waktu ekstraksi teks + penyaringan
    rule_version: int = field(default=RULE_VERSION)

    @property
    def share(self) -> float:
        """Porsi halaman yang lolos, 0-1."""
        return len(self.pages) / self.total_pages if self.total_pages else 0.0

    @property
    def looks_scanned(self) -> bool:
        # PDF hasil scan tidak punya lapisan teks -> penyaring tidak bisa bekerja, dan
        # Docling harus OCR seluruh dokumen (sekitar 3x lebih lama).
        return self.empty_pages > self.total_pages / 2

    def to_dict(self) -> dict:
        """Untuk .meta.json. Kunci JSON harus string, jadi nomor halaman di `reasons` diubah."""
        d = asdict(self)
        d["reasons"] = {str(k): v for k, v in self.reasons.items()}
        return d


def normalize(text: str) -> str:
    """Lowercase + rapikan, supaya istilah yang terpotong di PDF tetap cocok.

    PDF memotong frasa di tengah, mis. "Non-<ganti baris>Performing Loan" (2025 hal 95)
    dan "dalam jutaan <ganti baris>Rupiah" (2024 hal 372, sebuah tabel). Tanpa ini,
    lolos-tidaknya halaman bergantung pada letak ganti baris.
    """
    text = text.lower().replace("­", "")                 # soft hyphen
    text = re.sub(r"(?<=\w)-\s*(?=\w)", " ", text)             # non-performing -> non performing
    return re.sub(r"\s+", " ", text)                           # termasuk U+00A0, U+202F


def open_pdf(pdf_path: str | Path) -> PdfReader:
    """Buka PDF; yang dikunci tanpa kata sandi baca dibuka dengan kata sandi kosong."""
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted and not reader.decrypt(""):
        # Banyak laporan dikunci "owner password" (cegah edit/cetak) tapi tetap bisa
        # dibaca dengan kata sandi kosong. Yang ini benar-benar butuh kata sandi.
        raise ValueError(f"{pdf_path.name}: PDF terkunci kata sandi, tidak bisa dibaca")
    return reader


def extract_page_texts(pdf_path: str | Path) -> list[str]:
    """Teks mentah tiap halaman, urut dari halaman 1. Halaman yang gagal dibaca -> ''.

    pypdf ikut membaca isi di luar area halaman yang tampak, dan itu SENGAJA dipakai di sini.
    Tabel lebar BCA terbelah dua halaman: halaman kiri berisi label baris, penanda satuannya
    baru tercetak di halaman kanan. Dengan teks tampak saja, 15-16 halaman per laporan
    (kebanyakan halaman label seperti itu) tidak akan lolos. Untuk menentukan LETAK suatu angka,
    pakai teks tampak (pypdfium2 get_text_bounded) -- lihat PANDUAN_MINGGU3, Langkah 5.
    """
    texts = []
    for page in open_pdf(pdf_path).pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:                 # satu halaman rusak jangan menggagalkan laporan
            texts.append("")
    return texts


def select_pages(texts: list[str], source: str = "") -> PageSelection:
    """Terapkan aturan saringan pada teks per halaman (texts[0] = halaman 1)."""
    reasons, unit_counts, empty = {}, Counter(), 0
    for number, raw in enumerate(texts, start=1):
        if len(raw.strip()) < MIN_TEXT_CHARS:
            empty += 1
        text = normalize(raw)
        units = [u for u, markers in UNIT_MARKERS.items() if any(m in text for m in markers)]
        unit_counts.update(units)
        has_ratio_terms = sum(term in text for term in RATIO_TERMS) >= MIN_RATIO_TERMS
        reason = "+".join(name for name, hit in (("unit", units), ("ratio", has_ratio_terms)) if hit)
        if reason:
            reasons[number] = reason

    # Satuan dominan = satuan yang penandanya muncul di halaman terbanyak. BCA: jutaan
    # ~240 halaman (seluruh laporan keuangan), miliar ~18 (hanya tabel Ikhtisar).
    unit = unit_counts.most_common(1)[0][0] if unit_counts else None
    return PageSelection(
        source=source,
        total_pages=len(texts),
        pages=sorted(reasons),
        reasons=reasons,
        unit=unit,
        unit_page_counts=dict(unit_counts),
        empty_pages=empty,
    )


def filter_pages(pdf_path: str | Path) -> PageSelection:
    """Ekstrak teks lalu saring. Pintu masuk untuk parse_pdf.py dan bot Telegram."""
    pdf_path = Path(pdf_path)
    start = time.perf_counter()
    selection = select_pages(extract_page_texts(pdf_path), source=pdf_path.name)
    selection.seconds = round(time.perf_counter() - start, 1)
    return selection


def format_ranges(pages: list[int]) -> str:
    """[18, 19, 20, 25] -> '18-20, 25' -- supaya ratusan nomor halaman tetap terbaca."""
    parts, start = [], None
    for i, p in enumerate(pages):
        if start is None:
            start = p
        if i + 1 == len(pages) or pages[i + 1] != p + 1:
            parts.append(f"{start}-{p}" if p != start else str(p))
            start = None
    return ", ".join(parts)


def main(args: list[str]):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # console Windows cp1252
    if args:
        paths = [Path(a) for a in args]
    else:
        from src import config
        paths = sorted(config.DATA_RAW.glob("*.pdf"))
    if not paths:
        sys.exit("Tidak ada PDF. Taruh di data/raw/ atau sebut path-nya.")

    for path in paths:
        s = filter_pages(path)
        print(f"\n{s.source}: {len(s.pages)} dari {s.total_pages} halaman lolos "
              f"({s.share:.0%})   {s.seconds:.1f} detik")
        print(f"  satuan dominan : {s.unit or 'TIDAK ADA PENANDA SATUAN'}   "
              f"(halaman per satuan: {s.unit_page_counts or '-'})")
        ratio_only = [p for p, r in s.reasons.items() if r == "ratio"]
        print(f"  lolos karena istilah rasio saja: {format_ranges(ratio_only) or '-'}")
        print(f"  halaman lolos  : {format_ranges(s.pages)}")
        if s.looks_scanned:
            print(f"  PERHATIAN: {s.empty_pages} halaman tanpa teks -- kemungkinan PDF hasil "
                  f"scan. Penyaring tidak bisa dipakai; Docling harus OCR semua halaman.")


if __name__ == "__main__":
    main(sys.argv[1:])
