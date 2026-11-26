"""
Tugas 3.3 -- parse laporan tahunan dengan Docling.  docs/PANDUAN_MINGGU3.md, Langkah 3.

Alur:  PDF asli -> page_filter (halaman relevan) -> subset_pdf (PDF potongan + peta halaman)
       -> Docling (tata letak + struktur tabel, GPU) -> 3 file di data/markdown/:

  <kode>_<tahun>.json       dokumen Docling lengkap = SUMBER KEBENARAN untuk Minggu 5
                            (struktur tabel, posisi, nomor halaman POTONGAN)
  <kode>_<tahun>.md         untuk dibaca manusia. Tiap halaman diawali
                            "<!-- halaman 703 | potongan 253 -->", jadi bisa dicari dengan
                            nomor halaman ASLI saat inspeksi (Langkah 6)
  <kode>_<tahun>.meta.json  hash SHA-256, hasil saringan, peta halaman, opsi, waktu. Ditulis
                            PALING AKHIR: file ini ada = parse selesai utuh.

Nomor halaman di dalam .json adalah nomor PDF potongan. Ubah ke nomor asli dengan
PageMap.from_list(meta["page_map"]).to_original(page_no).

Cache: kalau .meta.json dengan hash PDF, versi aturan saringan, opsi Docling, dan versi
Docling yang sama sudah ada, parse dilewati -- unggahan ulang file yang sama tidak diproses
lagi.

Jalankan:  python -m src.ingest.parse_pdf data/raw/bbca_2024.pdf
           python -m src.ingest.parse_pdf data/raw/bbca_2024.pdf --max-pages 20   (Langkah 4)
           python -m src.ingest.parse_pdf data/raw/bbca_2024.pdf --pages 20,21,703
Parse sebagian (--max-pages / --pages) disimpan di data/markdown/trial/ dan tidak dipakai
sebagai cache.
"""

import argparse
import gc
import hashlib
import json
import logging
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Callable

import torch
# Docling SENGAJA diimpor di level modul, bukan di dalam fungsi. Saat pertama diimpor, Docling
# mencoba backend opsional (odfdo, arelle) yang tidak terpasang dan MENYIMPAN error-nya beserta
# traceback. Traceback itu menahan semua frame pemanggil selamanya -- kalau impornya terjadi di
# dalam _build_converter, frame itu ikut tertahan bersama variabel `converter`, dan model
# Docling tidak pernah lepas dari GPU (terukur 31-10-2026: 407 MB tertinggal setelah parse).
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.progress import PageCompletedProgress
from docling.document_converter import DocumentConverter, PdfFormatOption

from src import config
from src.ingest.detect_metadata import parse_file_name
from src.ingest.page_filter import RULE_VERSION, filter_pages
from src.ingest.subset_pdf import PageMap, build_subset

def ticker_year_from_name(pdf_path: str | Path) -> tuple[str, int]:
    """'bbca_2024.pdf' -> ('bbca', 2024)."""
    named = parse_file_name(pdf_path)
    if named is None:
        raise ValueError(f"{Path(pdf_path).name}: nama file harus <kode saham>_<tahun>.pdf, "
                         f"mis. bbca_2024.pdf. Kode & tahun bisa dikenali dari isinya: "
                         f"python -m src.ingest.detect_metadata {pdf_path}")
    return named


def output_paths(ticker: str, year: int, partial: bool = False) -> dict[str, Path]:
    paths = {
        "json": config.docling_json(year, ticker),
        "md": config.markdown(year, ticker),
        "subset": config.subset(year, ticker),
        "meta": config.parse_meta(year, ticker),
    }
    if partial:
        paths = {k: config.DATA_PARSE_TRIAL / p.name for k, p in paths.items()}
    return paths


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def parse_options() -> dict:
    """Semua yang memengaruhi hasil parse. Disimpan di .meta.json dan dibandingkan untuk cache."""
    return {
        "rule_version": RULE_VERSION,
        "do_ocr": config.DOCLING_DO_OCR,
        "table_mode": config.DOCLING_TABLE_MODE,
        "do_cell_matching": config.DOCLING_CELL_MATCHING,
        "docling": version("docling"),
        "docling_core": version("docling-core"),
    }


def _cached(paths: dict[str, Path], digest: str, options: dict) -> dict | None:
    try:
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (meta.get("sha256") == digest and meta.get("options") == options
            and paths["json"].exists() and paths["md"].exists()):
        return meta
    return None


def _pick_device() -> str:
    if config.DOCLING_DEVICE == "cuda" and not torch.cuda.is_available():
        print("PERINGATAN: GPU tidak tersedia -- Docling berjalan di CPU (jauh lebih lambat)")
        return "cpu"
    return config.DOCLING_DEVICE


def _device_label(device: str) -> str:
    return f"cuda ({torch.cuda.get_device_name(0)})" if device == "cuda" else device


def _build_converter(device: str) -> DocumentConverter:
    options = PdfPipelineOptions()
    options.do_ocr = config.DOCLING_DO_OCR                 # bawaannya MENYALA
    options.do_table_structure = True
    options.table_structure_options.mode = TableFormerMode(config.DOCLING_TABLE_MODE)
    options.table_structure_options.do_cell_matching = config.DOCLING_CELL_MATCHING
    options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice(device))

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    converter.initialize_pipeline(InputFormat.PDF)   # muat model sekarang -> waktunya terukur sendiri
    return converter


class _WarningCollector(logging.Handler):
    """Tampung peringatan pustaka selama parse, supaya tersimpan di .meta.json.

    TableFormer melaporkan sel tabel yang DIBUANG hanya lewat log ("1 of 225 pdf cells ...
    dropped from the table"); status hasilnya tetap "success". Di parse penuh pesan itu
    tenggelam, padahal menunjukkan tabel mana yang perlu diperiksa di Langkah 6.
    """

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord):
        self.messages.append(f"{record.name}: {record.getMessage()}")


def _convert(subset_pdf: Path, device: str, progress: Callable[[int, int], None] | None):
    """Jalankan Docling. Converter (model di GPU) hanya hidup di dalam fungsi ini."""
    collector = _WarningCollector()
    logging.getLogger().addHandler(collector)
    try:
        start = time.perf_counter()
        converter = _build_converter(device)
        load_s = time.perf_counter() - start

        def on_event(event):
            if isinstance(event, PageCompletedProgress):
                progress(event.completed_pages, event.total_pages)

        start = time.perf_counter()
        result = converter.convert(subset_pdf, progress_callback=on_event if progress else None)
        convert_s = time.perf_counter() - start
    finally:
        logging.getLogger().removeHandler(collector)

    if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        raise RuntimeError(f"Docling gagal ({result.status.value}): {result.errors}")
    errors = [str(e) for e in result.errors]
    return result.document, result.status.value, errors, collector.messages, load_s, convert_s


def _release_gpu():
    # Model embedding BGE-M3 juga butuh VRAM (2,12 GB dari 6 GB) -- jangan biarkan model
    # Docling tertinggal di GPU setelah parse, terutama di proses yang hidup lama (bot).
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def to_markdown(document, page_map: PageMap) -> str:
    """Markdown per halaman, diberi nomor halaman ASLI supaya bisa dicari saat inspeksi."""
    parts = []
    for subset_page in range(1, len(page_map) + 1):
        original_page = page_map.to_original(subset_page)
        body = document.export_to_markdown(page_no=subset_page)
        parts.append(f"<!-- halaman {original_page} | potongan {subset_page} -->\n\n{body}")
    return "\n\n".join(parts) + "\n"


def parse_report(pdf_path: str | Path, ticker: str | None = None, year: int | None = None, *,
                 max_pages: int | None = None, pages: list[int] | None = None,
                 force: bool = False,
                 progress: Callable[[int, int], None] | None = None) -> dict:
    """Saring -> potong -> Docling -> simpan. Mengembalikan isi .meta.json.

    max_pages : hanya N halaman lolos pertama (pengukuran waktu, Langkah 4)
    pages     : hanya halaman ASLI ini, lolos saringan atau tidak (untuk debug)
    progress  : dipanggil (halaman selesai, total) setiap satu halaman selesai diparse
    Kembalian dari cache diberi kunci tambahan "cached": True (tidak ikut disimpan).
    """
    pdf_path = Path(pdf_path)
    if ticker is None or year is None:
        ticker, year = ticker_year_from_name(pdf_path)
    partial = bool(max_pages or pages)
    paths = output_paths(ticker, year, partial)

    digest = sha256(pdf_path)
    options = parse_options()
    if not (partial or force):
        meta = _cached(paths, digest, options)
        if meta:
            return {**meta, "cached": True}
    # .meta.json = penanda selesai. Hapus dulu, supaya parse yang terhenti di tengah jalan
    # tidak meninggalkan meta lama yang menunjuk ke .json baru yang setengah jadi.
    paths["meta"].unlink(missing_ok=True)

    selection = filter_pages(pdf_path)
    if selection.looks_scanned:
        raise ValueError(f"{pdf_path.name}: {selection.empty_pages} dari {selection.total_pages} "
                         f"halaman tanpa teks -- kemungkinan PDF hasil scan, belum didukung")
    if not selection.pages:
        raise ValueError(f"{pdf_path.name}: tidak ada halaman lolos saringan -- penanda satuan "
                         f"laporan tidak dikenali (lihat UNIT_MARKERS di page_filter.py)")
    if pages:
        chosen = sorted(set(pages))
    elif max_pages:
        chosen = selection.pages[:max_pages]
    else:
        chosen = selection.pages

    start = time.perf_counter()
    page_map = build_subset(pdf_path, chosen, paths["subset"])
    subset_s = time.perf_counter() - start

    device = _pick_device()
    document, status, errors, warnings, load_s, convert_s = _convert(paths["subset"], device, progress)
    _release_gpu()

    start = time.perf_counter()
    document.save_as_json(paths["json"])
    paths["md"].write_text(to_markdown(document, page_map), encoding="utf-8")
    export_s = time.perf_counter() - start

    # Halaman yang tidak menghasilkan apa pun di Docling -- dicatat dengan nomor ASLI
    missing = [page_map.to_original(p) for p in range(1, len(page_map) + 1)
               if p not in document.pages]

    meta = {
        "source": pdf_path.name,
        "ticker": ticker,
        "year": year,
        "sha256": digest,
        "source_pages": selection.total_pages,
        "partial": partial,
        "unit": selection.unit,
        "page_map": page_map.to_list(),
        "selection": selection.to_dict(),
        "options": options,
        "device": _device_label(device),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "pages_missing": missing,
        "counts": {
            "pages": len(document.pages),
            "tables": len(document.tables),
            "texts": len(document.texts),
            "pictures": len(document.pictures),
        },
        "seconds": {
            "filter": selection.seconds,
            "subset": round(subset_s, 1),
            "model_load": round(load_s, 1),
            "convert": round(convert_s, 1),
            "convert_per_page": round(convert_s / len(page_map), 2),
            "export": round(export_s, 1),
        },
        "files": {k: p.name for k, p in paths.items() if k != "meta"},
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    paths["meta"].write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # console Windows cp1252
    ap = argparse.ArgumentParser(description="Parse laporan tahunan dengan Docling (Minggu 3, Langkah 3).")
    ap.add_argument("pdf", nargs="+", type=Path, help="mis. data/raw/bbca_2024.pdf")
    ap.add_argument("--max-pages", type=int, help="hanya N halaman lolos pertama (Langkah 4)")
    ap.add_argument("--pages", help="hanya halaman asli tertentu, mis. 20,21,703")
    ap.add_argument("--force", action="store_true", help="abaikan cache, parse ulang")
    args = ap.parse_args(argv)
    pages = [int(p) for p in args.pages.split(",")] if args.pages else None

    def show(done: int, total: int):
        print(f"  Docling: {done}/{total} halaman", end="\n" if done == total else "\r", flush=True)

    failed = 0
    for path in args.pdf:
        print(f"\n{path.name}")
        try:
            meta = parse_report(path, max_pages=args.max_pages, pages=pages, force=args.force,
                                progress=show)
        except (ValueError, FileNotFoundError) as e:   # input salah: pesan singkat, bukan traceback
            print(f"  GAGAL: {e}")
            failed += 1
            continue
        folder = config.DATA_PARSE_TRIAL if meta["partial"] else config.DATA_MARKDOWN
        if meta.get("cached"):
            print(f"  dari cache (diparse {meta['created']}) -- pakai --force untuk parse ulang")
        s, c = meta["seconds"], meta["counts"]
        print(f"  {c['pages']} halaman, {c['tables']} tabel, status {meta['status']}, {meta['device']}")
        print(f"  waktu: saring {s['filter']} s, potong {s['subset']} s, muat model {s['model_load']} s, "
              f"parse {s['convert']} s ({s['convert_per_page']} s/halaman), simpan {s['export']} s")
        print(f"  file : {folder}\\{meta['files']['json']}, .md, .meta.json")
        if meta["errors"] or meta["pages_missing"]:
            print(f"  PERHATIAN: error {meta['errors']}; halaman kosong di Docling {meta['pages_missing']}")
        if meta.get("warnings"):
            print(f"  PERHATIAN: {len(meta['warnings'])} peringatan pustaka (semua ada di .meta.json):")
            for w in meta["warnings"][:5]:
                print(f"    {w}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
