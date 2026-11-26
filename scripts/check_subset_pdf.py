"""
Tugas 3.3 (bagian 1) -- kriteria selesai PDF potongan + peta halaman
(docs/PANDUAN_MINGGU3.md, Langkah 2).

Jalankan:  python scripts/check_subset_pdf.py           (PDF potongan dihapus setelah dicek)
           python scripts/check_subset_pdf.py --keep    (disimpan di data/markdown/ untuk dibuka)

Untuk ketiga laporan BBCA, script ini memeriksa:
  1. SETIAP halaman PDF potongan sama dengan halaman aslinya menurut peta -- teks, ukuran,
     rotasi, dan tampilan (piksel). Ini versi lengkap dari "cek cepat halaman 1" di panduan.
  2. uji titik: nilai Modal Inti (Tier 1) BANK dari ground truth TAMPAK di halaman potongan
     yang menurut peta adalah halaman Catatan KPMM.
  3. peta halaman utuh setelah disimpan ke JSON dan dibaca lagi (seperti di .meta.json).
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pypdfium2 as pdfium

from src import config
from src.ingest.page_filter import filter_pages
from src.ingest.subset_pdf import PageMap, build_subset, verify_subset

TICKER = "bbca"

# tahun -> (halaman asli Catatan KPMM, Modal Inti Tier 1 BANK dalam juta Rp seperti tercetak).
# Sumber: data/ground_truth.xlsx, diverifikasi manual di Minggu 1.
KNOWN_VALUES = {
    2023: (727, "217.686.126"),
    2024: (703, "239.468.855"),
    2025: (594, "258.057.396"),
}


def visible_text(pdf_path: Path, page_no: int) -> str:
    """Teks yang TAMPAK di halaman itu saja.

    Jangan pakai pypdf untuk ini: lapisan teks PDF BCA bisa memuat isi halaman berikutnya di
    luar area tampak. Angka KPMM 2025 ada di lapisan teks hal 593, padahal baru tampil di
    hal 594 -- versi lama uji titik ini lolos pada halaman yang salah.
    """
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        textpage = doc[page_no - 1].get_textpage()
        text = textpage.get_text_bounded()
        textpage.close()
        return text
    finally:
        doc.close()


def check_year(year: int, out_dir: Path) -> list[str]:
    source = config.pdf(year, TICKER)
    if not source.exists():
        return [f"{source.name} tidak ada"]

    selection = filter_pages(source)
    out_pdf = out_dir / config.subset(year, TICKER).name
    start = time.perf_counter()
    page_map = build_subset(source, selection.pages, out_pdf)
    seconds = time.perf_counter() - start
    print(f"\n{source.name}: {len(page_map)} halaman -> {out_pdf.name}   "
          f"{source.stat().st_size / 1_048_576:.1f} MB -> {out_pdf.stat().st_size / 1_048_576:.1f} MB, "
          f"{seconds:.1f} detik")

    # 1. setiap halaman
    problems = verify_subset(source, out_pdf, page_map)
    bad_pages = {p.split(":")[0] for p in problems}          # "potongan hal 5 (asli 22)"
    print(f"  {len(page_map) - len(bad_pages)} dari {len(page_map)} halaman sama persis "
          f"dengan aslinya (teks, ukuran, rotasi, tampilan)")
    failures = [f"{source.name}: {p}" for p in problems]
    if page_map.to_original(1) != selection.pages[0]:        # "cek cepat" di panduan
        failures.append(f"{source.name}: halaman potongan 1 bukan halaman lolos pertama")

    # 2. uji titik
    original_page, value = KNOWN_VALUES[year]
    subset_page = page_map.to_subset(original_page)
    if subset_page is None:
        failures.append(f"{source.name}: hal {original_page} (KPMM) tidak ada di PDF potongan")
    else:
        found = value in visible_text(out_pdf, subset_page)
        print(f"  Tier 1 BANK {value}: potongan hal {subset_page} -> asli hal "
              f"{page_map.to_original(subset_page)}   {'tampak' if found else 'TIDAK TAMPAK'}")
        if not found:
            failures.append(f"{source.name}: {value} tidak tampak di potongan hal {subset_page}")

    # 3. simpan-baca JSON
    restored = PageMap.from_list(json.loads(json.dumps(page_map.to_list())))
    if restored != page_map:
        failures.append(f"{source.name}: peta halaman berubah setelah simpan-baca JSON")
    return failures


def main():
    keep = "--keep" in sys.argv[1:]
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = config.DATA_MARKDOWN if keep else Path(tmp)
        for year in config.YEARS:
            failures += check_year(year, out_dir)

    print()
    if keep:
        print(f"PDF potongan disimpan di {config.DATA_MARKDOWN}\n")
    if failures:
        print(f"BELUM LULUS -- {len(failures)} masalah:")
        for f in failures[:20]:
            print(f"  - {f}")
        if len(failures) > 20:
            print(f"  ... dan {len(failures) - 20} lainnya")
        sys.exit(1)
    print("LULUS -- setiap halaman PDF potongan cocok dengan halaman aslinya menurut peta.")


if __name__ == "__main__":
    main()
