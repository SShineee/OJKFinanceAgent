"""
Tugas 8.1-8.4 -- pemuat dan validator skema dataset evaluasi RAGAS (`eval/datasets/ragas_qa.jsonl`).
docs/PANDUAN_MINGGU8.md, Langkah 7.

Jalankan:
  python -m eval.ragas_dataset                 # validasi skema, halaman PDF, & cakupan chunk
  python -m eval.ragas_dataset --strict-final  # wajib 30 pasang sesuai komposisi target final

Memeriksa:
  1. Kelengkapan & tipe 8 field wajib: id, ticker, year, type, question, reference, ref_page, source_file.
  2. ID unik & berurutan (qa01..qaNN); ticker terdaftar (bbca/bmri); tipe valid.
  3. Konsistensi `year`, `source_file`, dan `ref_page` (lintas laporan untuk `komparatif`,
     satu laporan untuk `faktual`/`multi_hop`/`kontekstual`).
  4. Rentang halaman `ref_page` valid pada PDF asli di `data/raw/`.
  5. Audit cakupan `page_filter` / chunk terindeks di `data/chunks/<ticker>_<tahun>.jsonl`:
     - `faktual`, `multi_hop`, dan `komparatif` wajib punya minimal 1 chunk terindeks di `ref_page`;
     - `kontekstual` yang halamannya terbuang penyaring dicatat jujur sebagai peringatan
       (bahan analisis context recall di Bab 4), bukan disembunyikan.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config
from src.ingest.chunk import load_chunks

DATASET = config.EVAL_DATASETS / "ragas_qa.jsonl"
REQUIRED_FIELDS = ("id", "ticker", "year", "type", "question", "reference", "ref_page", "source_file")
VALID_TICKERS = ("bbca", "bmri")
VALID_TYPES = ("faktual", "multi_hop", "komparatif", "kontekstual")

# Target akhir 30 pertanyaan (docs/PANDUAN_MINGGU8.md Langkah 7)
FINAL_TARGET_TOTAL = 30
FINAL_TARGET_BY_TICKER = {"bbca": 20, "bmri": 10}
FINAL_TARGET_BY_TYPE = {"faktual": 12, "multi_hop": 8, "komparatif": 6, "kontekstual": 4}
FINAL_TARGET_MATRIX = {
    ("bbca", "faktual"): 8, ("bmri", "faktual"): 4,
    ("bbca", "multi_hop"): 5, ("bmri", "multi_hop"): 3,
    ("bbca", "komparatif"): 4, ("bmri", "komparatif"): 2,
    ("bbca", "kontekstual"): 3, ("bmri", "kontekstual"): 1,
}

ID_RE = re.compile(r"^qa(\d{2})$")
SRC_RE = re.compile(r"^([a-z0-9]+)_(\d{4})\.pdf$")


def load_dataset(path: Path = DATASET) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dataset_sha256(path: Path = DATASET) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_page_pairs(rec: dict) -> tuple[list[tuple[str, int]], list[str]]:
    """Pasangkan (source_file, page) dari satu record + daftar kesalahan struktur."""
    errs = []
    src, rp = rec.get("source_file"), rec.get("ref_page")
    if isinstance(src, str):
        pages = [rp] if isinstance(rp, int) and not isinstance(rp, bool) else rp
        if not isinstance(pages, list) or not pages or not all(isinstance(p, int) and not isinstance(p, bool) and p > 0 for p in pages):
            errs.append(f"{rec.get('id')}: ref_page harus int > 0 atau list[int > 0], dapat {rp!r}")
            return [], errs
        return [(src, p) for p in pages], errs
    if isinstance(src, list) and src and all(isinstance(s, str) for s in src):
        if not isinstance(rp, list) or len(rp) != len(src) or not all(isinstance(p, int) and not isinstance(p, bool) and p > 0 for p in rp):
            errs.append(f"{rec.get('id')}: jika source_file list ({len(src)} file), ref_page harus list[int] dengan panjang sama")
            return [], errs
        return list(zip(src, rp)), errs
    errs.append(f"{rec.get('id')}: source_file harus str atau list[str], dapat {src!r}")
    return [], errs


def _pdf_page_counts(files: set[str]) -> dict[str, int]:
    import pypdfium2 as pdfium
    counts = {}
    for fname in sorted(files):
        p = config.DATA_RAW / fname
        if p.exists():
            doc = pdfium.PdfDocument(str(p))
            counts[fname] = len(doc)
            doc.close()
    return counts


def _indexed_pages_map(tickers_years: set[tuple[str, int]]) -> dict[tuple[str, int], set[int]]:
    out = {}
    for ticker, year in sorted(tickers_years):
        if config.chunks(year, ticker).exists():
            out[(ticker, year)] = {pg for c in load_chunks(year, ticker) for pg in c["pages"]}
        else:
            out[(ticker, year)] = set()
    return out


def validate(records: list[dict], strict_final: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not records:
        return {"errors": ["dataset kosong"], "warnings": [], "coverage": [], "counts": {}}

    seen_ids = set()
    all_files: set[str] = set()
    all_ty: set[tuple[str, int]] = set()
    parsed_pairs: dict[str, list[tuple[str, int]]] = {}

    for idx, rec in enumerate(records, start=1):
        rid = rec.get("id", f"<baris {idx}>")
        missing = [k for k in REQUIRED_FIELDS if k not in rec]
        extra = [k for k in rec if k not in REQUIRED_FIELDS]
        if missing:
            errors.append(f"{rid}: field kurang {missing}")
            continue
        if extra:
            errors.append(f"{rid}: field tak dikenal {extra}")

        if not isinstance(rid, str) or not ID_RE.match(rid):
            errors.append(f"{rid}: format id harus qa01..qa99")
        elif rid in seen_ids:
            errors.append(f"{rid}: id ganda")
        elif rid != f"qa{idx:02d}":
            errors.append(f"{rid}: id tidak berurutan (seharusnya qa{idx:02d})")
        seen_ids.add(rid)

        ticker = rec["ticker"]
        if ticker not in VALID_TICKERS:
            errors.append(f"{rid}: ticker '{ticker}' tidak valid (harus salah satu {VALID_TICKERS})")

        qtype = rec["type"]
        if qtype not in VALID_TYPES:
            errors.append(f"{rid}: type '{qtype}' tidak valid (harus salah satu {VALID_TYPES})")

        yr = rec["year"]
        if qtype == "komparatif":
            if not (isinstance(yr, list) and len(yr) >= 2 and all(isinstance(y, int) and not isinstance(y, bool) and y in config.YEARS for y in yr) and yr == sorted(set(yr))):
                errors.append(f"{rid}: year untuk komparatif harus list tahun terurut dari {config.YEARS}, dapat {yr!r}")
        else:
            if not (isinstance(yr, int) and not isinstance(yr, bool) and yr in config.YEARS):
                errors.append(f"{rid}: year untuk {qtype} harus int dalam {config.YEARS}, dapat {yr!r}")

        q_text = rec["question"]
        if not isinstance(q_text, str) or len(q_text.strip()) < 15 or not q_text.strip().endswith("?"):
            errors.append(f"{rid}: question harus string >= 15 karakter dan diakhiri '?'")

        ref_text = rec["reference"]
        if not isinstance(ref_text, str) or len(ref_text.strip()) < 30:
            errors.append(f"{rid}: reference terlalu pendek (< 30 karakter; harus memuat angka/satuan/konteks)")
        elif len(ref_text.strip()) > 1200:
            warnings.append(f"{rid}: reference cukup panjang ({len(ref_text.strip())} karakter)")

        pairs, p_errs = _source_page_pairs(rec)
        errors.extend(p_errs)
        parsed_pairs[rid] = pairs
        for fname, _ in pairs:
            m = SRC_RE.match(fname)
            if not m:
                errors.append(f"{rid}: nama source_file '{fname}' tidak mengikuti <ticker>_<tahun>.pdf")
                continue
            f_ticker, f_year = m.group(1), int(m.group(2))
            if f_ticker != ticker:
                errors.append(f"{rid}: source_file '{fname}' tidak cocok dengan ticker '{ticker}'")
            expected_years = set(yr) if isinstance(yr, list) else {yr}
            if f_year not in expected_years:
                errors.append(f"{rid}: tahun di source_file '{fname}' tidak ada di year={yr!r}")
            all_files.add(fname)
            all_ty.add((f_ticker, f_year))

        if qtype == "komparatif" and isinstance(yr, list) and isinstance(rec["source_file"], list):
            src_years = [int(SRC_RE.match(f).group(2)) for f in rec["source_file"] if SRC_RE.match(f)]
            if set(src_years) != set(yr):
                errors.append(f"{rid}: tahun source_file {src_years} tidak mencakup seluruh year {yr}")

    pdf_counts = _pdf_page_counts(all_files)
    idx_pages = _indexed_pages_map(all_ty)

    coverage = []
    for rec in records:
        rid = rec.get("id", "?")
        qtype = rec.get("type")
        pairs = parsed_pairs.get(rid, [])
        missing_pdf = []
        out_of_range = []
        kept_pairs = []
        dropped_pairs = []
        for fname, page in pairs:
            if fname not in pdf_counts:
                missing_pdf.append(fname)
            elif page > pdf_counts[fname]:
                out_of_range.append(f"{fname} hal {page} > {pdf_counts[fname]}")
            m = SRC_RE.match(fname)
            if m:
                key = (m.group(1), int(m.group(2)))
                if page in idx_pages.get(key, set()):
                    kept_pairs.append(f"{fname}:{page}")
                else:
                    dropped_pairs.append(f"{fname}:{page}")

        if missing_pdf:
            errors.append(f"{rid}: PDF tidak ditemukan di data/raw/: {sorted(set(missing_pdf))}")
        if out_of_range:
            errors.append(f"{rid}: ref_page di luar rentang PDF: {out_of_range}")
        if dropped_pairs:
            msg = f"{rid} ({qtype}): halaman tidak ada di chunk terindeks: {dropped_pairs}"
            if qtype == "kontekstual":
                warnings.append(msg + " [dicatat untuk analisis context recall]")
            else:
                errors.append(msg)

        coverage.append({
            "id": rid, "ticker": rec.get("ticker"), "type": qtype, "year": rec.get("year"),
            "kept_refs": kept_pairs, "dropped_refs": dropped_pairs,
        })

    by_ticker = Counter(r.get("ticker") for r in records)
    by_type = Counter(r.get("type") for r in records)
    by_matrix = Counter((r.get("ticker"), r.get("type")) for r in records)

    if strict_final:
        if len(records) != FINAL_TARGET_TOTAL:
            errors.append(f"jumlah record {len(records)}, target final harus {FINAL_TARGET_TOTAL}")
        for k, want in FINAL_TARGET_BY_TICKER.items():
            if by_ticker[k] != want:
                errors.append(f"jumlah {k} = {by_ticker[k]}, target final {want}")
        for k, want in FINAL_TARGET_BY_TYPE.items():
            if by_type[k] != want:
                errors.append(f"jumlah tipe {k} = {by_type[k]}, target final {want}")

    return {
        "errors": errors,
        "warnings": warnings,
        "coverage": coverage,
        "counts": {
            "total": len(records),
            "by_ticker": dict(by_ticker),
            "by_type": dict(by_type),
            "by_matrix": {f"{t}_{tp}": by_matrix[(t, tp)] for t in VALID_TICKERS for tp in VALID_TYPES},
        },
    }


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Validasi dataset evaluasi RAGAS (eval/datasets/ragas_qa.jsonl).")
    ap.add_argument("--dataset", type=Path, default=DATASET, help="path file .jsonl")
    ap.add_argument("--strict-final", action="store_true", help="wajib memenuhi target akhir 30 pasang (20 BBCA / 10 BMRI)")
    args = ap.parse_args(argv)

    records = load_dataset(args.dataset)
    res = validate(records, strict_final=args.strict_final)
    rel = args.dataset.relative_to(ROOT) if args.dataset.is_relative_to(ROOT) else args.dataset

    print(f"Dataset : {rel} ({len(records)}/{FINAL_TARGET_TOTAL} pasang)")
    print(f"SHA-256 : {dataset_sha256(args.dataset)}\n")

    print("== Komposisi saat ini vs target final (30 pasang) ==")
    print(f"  {'Tipe':<14} {'BBCA':>10} {'BMRI':>10} {'Total':>10}")
    m = res["counts"].get("by_matrix", {})
    for tp in VALID_TYPES:
        b = m.get(f"bbca_{tp}", 0)
        r = m.get(f"bmri_{tp}", 0)
        wb = FINAL_TARGET_MATRIX[("bbca", tp)]
        wr = FINAL_TARGET_MATRIX[("bmri", tp)]
        print(f"  {tp:<14} {f'{b}/{wb}':>10} {f'{r}/{wr}':>10} {f'{b+r}/{wb+wr}':>10}")
    bt = res["counts"].get("by_ticker", {})
    n_bbca, n_bmri = bt.get("bbca", 0), bt.get("bmri", 0)
    print(f"  {'JUMLAH':<14} {f'{n_bbca}/20':>10} {f'{n_bmri}/10':>10} {f'{len(records)}/30':>10}")

    print("\n== Cakupan halaman rujukan di chunk terindeks ==")
    kept_all = sum(1 for c in res["coverage"] if not c["dropped_refs"])
    print(f"  Lolos seluruh ref_page : {kept_all}/{len(res['coverage'])} pertanyaan")
    for c in res["coverage"]:
        mark = "OK  " if not c["dropped_refs"] else "WARN"
        yr_str = ",".join(map(str, c["year"])) if isinstance(c["year"], list) else str(c["year"])
        print(f"  {mark} {c['id']} [{c['ticker']:4} {yr_str:<14} {c['type']:<11}] kept={c['kept_refs']}"
              + (f" dropped={c['dropped_refs']}" if c["dropped_refs"] else ""))

    if res["warnings"]:
        print("\n== Peringatan ==")
        for w in res["warnings"]:
            print(f"  PERINGATAN: {w}")
    if res["errors"]:
        print("\n== Kesalahan ==")
        for e in res["errors"]:
            print(f"  ERROR: {e}")

    print("\nHASIL:", "LULUS" if not res["errors"] else f"GAGAL ({len(res['errors'])} kesalahan)")
    sys.exit(0 if not res["errors"] else 1)


if __name__ == "__main__":
    main()
