"""
Tugas 3.8 -- waktu parse SEBELUM vs SESUDAH saringan halaman.  docs/PANDUAN_MINGGU3.md, Langkah 8.

Untuk satu laporan, Docling dijalankan dua kali berturut-turut dengan opsi yang sama
(parse_pdf._convert):
  1. dengan saringan  : PDF potongan dari Langkah 2 (data/markdown/<kode>_<tahun>.subset.pdf)
  2. tanpa saringan   : PDF asli, semua halaman
Keduanya diukur di sesi yang sama, supaya beban GPU dari aplikasi lain mengenai keduanya.

Juga dihitung tabel yang ditemukan Docling di halaman yang DIBUANG penyaring, dan berapa yang
berisi angka berformat ribuan -- bahan untuk menilai apa yang hilang karena saringan.

Hasil ditambahkan ke results/parse_timing.json (kunci = nama file). Jalankan satu laporan per
proses supaya memori lepas di antaranya:
    python scripts/measure_parse_time.py data/raw/bbca_2023.pdf
    python scripts/measure_parse_time.py data/raw/bbca_2023.pdf --save-dir <folder>   (simpan .json Docling tanpa saringan)
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src.ingest.page_filter import filter_pages  # noqa: E402
from src.ingest.parse_pdf import (_convert, _device_label, _pick_device, _release_gpu,  # noqa: E402
                                  parse_options, ticker_year_from_name)
from src.ingest.subset_pdf import PageMap  # noqa: E402

RESULTS = config.RESULTS / "parse_timing.json"
NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")   # 855.233.239 / 1.234,5
MIN_NUMERIC_CELLS = 5


def gpu_snapshot() -> str:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "tidak terbaca"


def gpu_busy(snapshot: str) -> bool:
    """Utilisasi >= 10% saat Docling TIDAK berjalan = ada proses lain di GPU. Terbukti
    15-11-2026: game yang berjalan saat tahap 'dengan saringan' bbca_2023 membuat saringan
    tampak lebih lambat daripada tanpa saringan (0,94x)."""
    m = re.match(r"\s*(\d+)\s*%", snapshot)
    return bool(m) and int(m.group(1)) >= 10


def numeric_cells(table) -> int:
    return sum(1 for row in table.data.grid for cell in row if NUMBER.search(cell.text or ""))


def table_pages(table, to_original=lambda p: p) -> set[int]:
    return {to_original(p.page_no) for p in table.prov}


def progress_printer(label: str):
    def show(done: int, total: int):
        if done == total or done % 50 == 0:
            print(f"  {label}: {done}/{total} halaman", flush=True)
    return show


def run(pdf_path: Path, save_dir: Path | None) -> dict:
    ticker, year = ticker_year_from_name(pdf_path)
    meta = json.loads(config.parse_meta(year, ticker).read_text(encoding="utf-8"))
    page_map = PageMap.from_list(meta["page_map"])
    subset_pdf = config.subset(year, ticker)
    device = _pick_device()

    print(f"{pdf_path.name}: {meta['source_pages']} halaman, {len(page_map)} tersaring, "
          f"{_device_label(device)}; GPU sebelum mulai: {gpu_snapshot()}", flush=True)

    start = time.perf_counter()
    selection = filter_pages(pdf_path)
    filter_s = time.perf_counter() - start
    if selection.pages != list(page_map.original_pages):
        raise RuntimeError("hasil saringan sekarang berbeda dengan .meta.json -- parse ulang dulu")

    measured = {}
    for label, source in (("filtered", subset_pdf), ("unfiltered", pdf_path)):
        gpu_before = gpu_snapshot()
        document, status, errors, warnings, load_s, convert_s = _convert(
            source, device, progress_printer(label))
        pages = len(document.pages)
        entry = {
            "pages": pages, "status": status, "errors": len(errors),
            "model_load_s": round(load_s, 1), "convert_s": round(convert_s, 1),
            "convert_per_page_s": round(convert_s / pages, 2),
            "tables": len(document.tables),
            "dropped_cell_warnings": sum("dropped from the table" in w for w in warnings),
            "gpu_before": gpu_before,
        }
        if label == "unfiltered":
            kept = set(page_map.original_pages)
            excluded = [t for t in document.tables if not table_pages(t) & kept]
            numeric = [t for t in excluded if numeric_cells(t) >= MIN_NUMERIC_CELLS]
            entry["tables_on_excluded_pages"] = len(excluded)
            entry["numeric_tables_on_excluded_pages"] = len(numeric)
            entry["numeric_table_pages_excluded"] = sorted({p for t in numeric for p in table_pages(t)})
            entry["tables_on_kept_pages"] = len(document.tables) - len(excluded)
            if save_dir:
                save_dir.mkdir(parents=True, exist_ok=True)
                document.save_as_json(save_dir / f"{ticker}_{year}.unfiltered.json")
        measured[label] = entry
        print(f"  {label}: {pages} halaman, {entry['tables']} tabel, model {load_s:.1f} s, "
              f"parse {convert_s:.1f} s ({entry['convert_per_page_s']} s/halaman)", flush=True)
        del document
        _release_gpu()
        entry["gpu_after"] = gpu_snapshot()
        if gpu_busy(entry["gpu_before"]) or gpu_busy(entry["gpu_after"]):
            print(f"  PERINGATAN: GPU dipakai proses lain (sebelum {entry['gpu_before']}, sesudah "
                  f"{entry['gpu_after']}) -- tutup aplikasi itu dan ukur ulang", flush=True)

    f, u = measured["filtered"], measured["unfiltered"]
    return {
        "measured": datetime.now().isoformat(timespec="seconds"),
        "device": _device_label(device),
        "options": parse_options(),
        "source_pages": meta["source_pages"],
        "filter_s": round(filter_s, 1),
        **measured,
        "summary": {
            "pages_share": round(f["pages"] / u["pages"], 3),
            "convert_speedup": round(u["convert_s"] / f["convert_s"], 2),
            "with_filter_total_s": round(filter_s + f["model_load_s"] + f["convert_s"], 1),
            "without_filter_total_s": round(u["model_load_s"] + u["convert_s"], 1),
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--save-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    result = run(args.pdf, args.save_dir)
    data = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    data[args.pdf.stem] = result
    RESULTS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    s = result["summary"]
    print(f"  RINGKAS: dengan saringan {s['with_filter_total_s']} s, tanpa saringan "
          f"{s['without_filter_total_s']} s; parse {s['convert_speedup']}x lebih cepat; "
          f"tabel di halaman terbuang: {result['unfiltered']['tables_on_excluded_pages']} "
          f"({result['unfiltered']['numeric_tables_on_excluded_pages']} berisi angka)")
    print(f"  disimpan ke {RESULTS.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
