"""
Tugas 6.5 -- add_document(pdf): satu pintu masuk pustaka.  docs/PANDUAN_MINGGU6.md, Langkah 4.

Dipanggil oleh tombol unggah bot Telegram (Minggu 16) dan oleh script untuk laporan baru (BMRI,
Minggu 8). Menjalankan seluruh alur; setiap tahap punya cache sendiri, jadi laporan yang sudah
pernah diproses selesai dalam hitungan detik:

  1. identifikasi  hash PDF sudah ada di pustaka (data/markdown/*.meta.json)?
                     ya    -> kode saham & tahun dari situ
                     tidak -> detect_metadata (isi PDF, 20-30 s): kode saham, tahun, sektor, satuan
                   Bot Minggu 16: panggil identify() dulu, tampilkan tebakannya, minta konfirmasi,
                   lalu add_document(pdf, ticker, year) dengan nilai yang dikonfirmasi pengguna.
                   PDF disalin ke data/raw/<kode>_<tahun>.pdf (kalau belum ada).
  2. parse         parse_pdf.parse_report -- saring halaman + Docling; cache per hash PDF.
                   Melepas GPU sesudahnya, sebelum model embedding dimuat.
  3. potong        chunk.build_chunks -- cache per kunci (hash + kode aturan)
  4. indeks        index.index_document (Chroma, idempoten lewat index_key) + BM25 dibangun dari
                   .jsonl (sparse.bm25_index, sekalian memastikan .jsonl terbaca)

Pengaman pustaka: kalau pustaka SUDAH punya <kode>_<tahun> dari PDF yang ISINYA BERBEDA (hash beda,
mis. laporan revisi), add_document BERHENTI dengan pesan jelas -- parse_report sendiri akan
menimpa hasil lama diam-diam. Mengganti laporan = tindakan sengaja (hapus dulu).

`progress(tahap, keterangan)` dipanggil di awal setiap tahap dan per halaman selama Docling
berjalan -> bot mengedit satu pesan (16.3a).

Jalankan:  python -m src.ingest.pipeline data/raw/bbca_2024.pdf
           python -m src.ingest.pipeline unggahan.pdf --ticker bmri --year 2024
"""

import argparse
import json
import shutil
import sys
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src import config

Progress = Callable[[str, str], None] | None


@dataclass
class Identity:
    ticker: str
    year: int
    sector: str | None
    company: str | None
    validated: bool
    sha256: str
    source: str                       # "pustaka" (hash dikenal) / "deteksi" (isi PDF dibaca)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0


def find_by_hash(digest: str) -> tuple[str, int] | None:
    """(kode saham, tahun) laporan di pustaka yang PDF-nya ber-hash `digest`, atau None."""
    for meta_path in sorted(config.DATA_MARKDOWN.glob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("sha256") == digest and not meta.get("partial"):
            return meta["ticker"], meta["year"]
    return None


def _library_hash(ticker: str, year: int) -> str | None:
    """Hash PDF yang sekarang tercatat di pustaka untuk <kode>_<tahun>, atau None kalau belum ada."""
    try:
        return json.loads(config.parse_meta(year, ticker).read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError):
        pass
    if config.pdf(year, ticker).exists():
        from src.ingest.parse_pdf import sha256
        return sha256(config.pdf(year, ticker))
    return None


def identify(pdf_path: str | Path, ticker: str | None = None, year: int | None = None) -> Identity:
    """Kenali laporan: dari pustaka (hash) atau dari isinya. `ticker`/`year` = nilai yang sudah
    dikonfirmasi pengguna (mengalahkan hasil deteksi). Menyimpan .metadata.json kalau belum ada.
    Berhenti (ValueError) kalau kode saham/tahun tidak diketahui, atau bentrok dengan pustaka."""
    from src.ingest import detect_metadata
    from src.ingest.parse_pdf import sha256

    start = time.perf_counter()
    pdf_path = Path(pdf_path)
    digest = sha256(pdf_path)
    known = find_by_hash(digest)
    ticker = ticker.lower() if ticker else None
    notes = []

    if known:
        if (ticker or known[0], year or known[1]) != known:
            raise ValueError(f"{pdf_path.name} sudah ada di pustaka sebagai {known[0]}_{known[1]}, "
                             f"bukan {ticker or known[0]}_{year or known[1]}")
        ticker, year = known
        source = "pustaka"
        metadata_path = config.report_metadata(year, ticker)
        detected = None if metadata_path.exists() else detect_metadata.detect_pdf(pdf_path)
    else:
        source = "deteksi"
        detected = detect_metadata.detect_pdf(pdf_path)
        notes += detected.warnings
        for name, given, found in (("kode saham", ticker, detected.ticker), ("tahun", year, detected.year)):
            if given is not None and found is not None and given != found:
                notes.append(f"{name} dikoreksi pengguna: terdeteksi {found}, dipakai {given}")
        ticker, year = ticker or detected.ticker, year or detected.year
        if ticker is None or year is None:
            raise ValueError(f"{pdf_path.name}: kode saham/tahun buku tidak terdeteksi dari isinya -- "
                             f"isi manual (--ticker / --year). Peringatan deteksi: {detected.warnings}")
        existing = _library_hash(ticker, year)
        if existing and existing != digest:
            raise ValueError(f"pustaka sudah berisi {ticker}_{year} dari PDF yang isinya berbeda "
                             f"(hash {existing[:12]}… vs {digest[:12]}…). Kalau ini laporan revisi, hapus "
                             f"dulu laporan lama dari pustaka; add_document tidak menimpa diam-diam.")

    if detected is not None:                       # simpan metadata dengan nilai yang dipakai
        detected.ticker, detected.year = ticker, year
        detect_metadata.save(detected)
    metadata = json.loads(config.report_metadata(year, ticker).read_text(encoding="utf-8"))
    if not metadata.get("validated"):
        notes.append(f"sektor '{metadata.get('sector')}' belum divalidasi -- hasil analisis diberi label "
                     f"'belum divalidasi' (Minggu 11)")
    return Identity(ticker=ticker, year=year, sector=metadata.get("sector"), company=metadata.get("company"),
                    validated=bool(metadata.get("validated")), sha256=digest, source=source,
                    warnings=notes, seconds=round(time.perf_counter() - start, 1))


def add_document(pdf_path: str | Path, ticker: str | None = None, year: int | None = None,
                 progress: Progress = None) -> dict:
    """Masukkan satu laporan ke pustaka: identifikasi -> parse -> potong -> indeks. Lihat docstring modul."""
    say = progress or (lambda stage, detail: None)
    total_start = time.perf_counter()
    pdf_path = Path(pdf_path)
    steps = {}

    say("identifikasi", pdf_path.name)
    identity = identify(pdf_path, ticker, year)
    ticker, year = identity.ticker, identity.year
    steps["identify"] = {"source": identity.source, "seconds": identity.seconds}
    library_pdf = config.pdf(year, ticker)
    if not library_pdf.exists():
        library_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, library_pdf)
        steps["identify"]["copied_to"] = str(library_pdf)

    say("parse", f"{ticker}_{year}: saring halaman + Docling")
    from src.ingest.parse_pdf import parse_report
    start = time.perf_counter()
    parsed = parse_report(library_pdf, ticker, year,
                          progress=lambda done, total: say("parse", f"halaman {done}/{total}"))
    steps["parse"] = {"cached": bool(parsed.get("cached")), "seconds": round(time.perf_counter() - start, 1),
                      "pages": len(parsed["page_map"]), "source_pages": parsed["source_pages"],
                      "status": parsed["status"]}

    say("potong", f"{ticker}_{year}: perbaikan tabel + chunking")
    from src.ingest.chunk import build_chunks
    start = time.perf_counter()
    chunked = build_chunks(year, ticker)
    steps["chunk"] = {"cached": chunked["cached"], "seconds": round(time.perf_counter() - start, 1),
                      "chunks": chunked["chunks"], "excluded": chunked["excluded"]}

    say("indeks", f"{ticker}_{year}: embedding + ChromaDB + BM25")
    from src.retrieval.index import index_document
    from src.retrieval.sparse import bm25_index
    start = time.perf_counter()
    indexed = index_document(year, ticker)
    bm25, _ = bm25_index(ticker, year)
    steps["index"] = {"skipped": indexed["skipped"], "seconds": round(time.perf_counter() - start, 1),
                      "chunks": indexed["chunks"], "bm25_documents": bm25.corpus_size}

    notes = list(identity.warnings) + list(chunked["stats"].get("warnings", []))
    if parsed["status"] != "success":
        notes.append(f"Docling: status {parsed['status']} {parsed.get('errors', [])}")
    result = {"ticker": ticker, "year": year, "sector": identity.sector, "company": identity.company,
              "validated": identity.validated, "doc_id": identity.sha256, "chunks": indexed["chunks"],
              "steps": steps, "warnings": notes, "seconds": round(time.perf_counter() - total_start, 1)}
    say("selesai", f"{ticker}_{year}: {indexed['chunks']} chunk siap dicari")
    return result


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    warnings.filterwarnings("ignore", message="Table cell bbox")   # bbox di luar halaman, di-clamp Docling
    ap = argparse.ArgumentParser(description="Masukkan laporan tahunan ke pustaka (saring -> parse -> chunk -> indeks).")
    ap.add_argument("pdf", nargs="+", type=Path)
    ap.add_argument("--ticker", help="kode saham (kalau tidak terdeteksi / dikoreksi pengguna)")
    ap.add_argument("--year", type=int, help="tahun buku (kalau tidak terdeteksi / dikoreksi pengguna)")
    args = ap.parse_args(argv)
    last = {"stage": None}

    def show(stage, detail):
        if stage == "parse" and detail.startswith("halaman"):
            done, total = detail.split()[1].split("/")
            if int(done) % 25 and done != total:
                return                                  # cukup tiap 25 halaman di terminal
        print(f"  [{stage}] {detail}")

    failed = 0
    for pdf_path in args.pdf:
        print(f"{pdf_path.name}")
        try:
            r = add_document(pdf_path, args.ticker, args.year, progress=show)
        except (ValueError, FileNotFoundError) as e:
            print(f"  GAGAL: {e}")
            failed += 1
            continue
        s = r["steps"]
        print(f"  -> {r['ticker']}_{r['year']} ({r['company']}, sektor {r['sector']}"
              f"{'' if r['validated'] else ', BELUM divalidasi'}): {r['chunks']} chunk, {r['seconds']} s")
        print(f"     identifikasi {s['identify']['source']} {s['identify']['seconds']} s | "
              f"parse {'cache' if s['parse']['cached'] else 'baru'} {s['parse']['seconds']} s | "
              f"potong {'cache' if s['chunk']['cached'] else 'baru'} {s['chunk']['seconds']} s | "
              f"indeks {'dilewati' if s['index']['skipped'] else 'baru'} {s['index']['seconds']} s")
        for note in r["warnings"]:
            print(f"     PERINGATAN: {note}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
