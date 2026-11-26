"""
Tugas 8.5 -- uji keterbacaan angka ground truth BMRI di chunk `data/chunks/bmri_<tahun>.jsonl`.
docs/PANDUAN_MINGGU8.md, Langkah 6a butir 5.

Jalankan:  python scripts/check_bmri_chunks.py

Memeriksa:
  A. Integritas workbook `data/ground_truth_bmri.xlsx` (92 angka mentah + 18 rasio resmi terbaca
     sebagai angka dengan `data_only=True`).
  B. Integritas record chunk BMRI (15 field, chunk_id urut, ticker='bmri', sector='bank',
     n_tokens <= CHUNK_MAX_TOKENS, split_pieces_without_header == 0).
  C. Keterbacaan seluruh angka mentah BMRI (21 item langsung + komponen 2 item hitungan) dan
     18 rasio resmi pada halaman sumber & `unit` yang sesuai di `data/chunks/bmri_*.jsonl`,
     sekaligus memisahkan halaman yang memang dilewati penyaring (`page_filter`) beserta
     keterbacaannya di laporan pembanding tahun berikutnya.

Output: results/check_bmri_chunks.json
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import load_workbook

import build_verification_sheet_bmri as sources
from src import config
from src.ingest import chunk as ck

TICKER = "bmri"
XLSX = config.DATA / "ground_truth_bmri.xlsx"

# Komponen 2 item hitungan (dalam JUTA Rupiah, sesuai lembar verifikasi)
# Catatan: bmri_2025 hal 37 (lanjutan Ikhtisar Neraca) tidak mencantumkan penanda satuan sehingga
# dilewati page_filter, namun kedua komponen DPK Konsolidasian terbaca penuh pada Laporan Posisi
# Keuangan Konsolidasian (Neraca Auditan) masing-masing tahun.
DPK_KONSOL_COMPONENTS = {
    2023: (("bmri_2023.pdf", (1073,), "1.351.448.149"), ("bmri_2023.pdf", (1075,), "225.501.470")),
    2024: (("bmri_2024.pdf", (1285,), "1.446.234.957"), ("bmri_2024.pdf", (1287,), "252.661.959")),
    2025: (("bmri_2025.pdf", (36, 954), "1.816.897.208"), ("bmri_2025.pdf", (956,), "288.866.943")),
}

EARNING_ASSET_COMPONENTS = {
    2022: ("bmri_2023.pdf", (1501, 1502),
           ["78.360.194", "44.932.352", "262.007.141", "6.312.523", "932.639.051"]),
    2023: ("bmri_2023.pdf", (1501, 1502),
           ["55.274.570", "43.134.871", "239.245.751", "16.205.580", "1.085.787.427"]),
    2024: ("bmri_2024.pdf", (1713, 1714),
           ["22.667.518", "44.703.514", "221.138.442", "7.166.266", "1.310.779.402"]),
    2025: ("bmri_2025.pdf", (1455, 1456),
           ["19.689.791", "81.717.307", "219.792.906", "2.771.530", "1.497.108.664"]),
}

# Halaman rasio resmi per laporan (berdasarkan inspeksi visual & pypdfium2)
RATIO_PAGES_BY_REPORT = {
    2023: (36, 37),
    2024: (34, 35),
    2025: (39, 40),
}

# Sumber alternatif (Neraca Auditan / laporan pembanding) untuk halaman yang dilewati page_filter
# karena tidak mengulang penanda satuan "(Dalam Rp Jutaan)".
CROSS_YEAR_FALLBACK = {
    (7, 2023): ("bmri_2023.pdf", 1077),
    (7, 2024): ("bmri_2024.pdf", 1289),
    (7, 2025): ("bmri_2025.pdf", 958),
    (18, 2023): ("bmri_2024.pdf", 431),
    (19, 2023): ("bmri_2024.pdf", 431),
    (21, 2022): ("bmri_2024.pdf", 428),
    (21, 2023): ("bmri_2024.pdf", 428),
}


def fmt_million(val_billion: float) -> str:
    return f"{round(val_billion * 1000):,}".replace(",", ".")


def fmt_pct(val: float) -> str:
    return f"{val:.2f}".replace(".", ",")


def num_pattern(text: str) -> re.Pattern:
    return re.compile(rf"(?<![\d.,]){re.escape(text)}(?![\d,]|\.\d)")


def pct_pattern(val: float) -> re.Pattern:
    txt = fmt_pct(val)
    txt_en = f"{val:.2f}"
    return re.compile(rf"(?<![\d.,])(?:{re.escape(txt)}|{re.escape(txt_en)})\s*%?")


def load_bmri_chunks() -> tuple[dict[int, list[dict]], dict[int, list[dict]], dict[int, set[int]], dict[int, dict]]:
    indexed, all_recs, kept_pages, metas = {}, {}, {}, {}
    for year in config.YEARS:
        recs = ck.load_chunks(year, TICKER, include_excluded=True)
        all_recs[year] = recs
        indexed[year] = [r for r in recs if r["excluded"] is None]
        pm = json.loads(config.parse_meta(year, TICKER).read_text(encoding="utf-8"))
        kept_pages[year] = set(pm["page_map"])
        metas[year] = json.loads(config.chunks_meta(year, TICKER).read_text(encoding="utf-8"))
    return indexed, all_recs, kept_pages, metas


def find_in_pages(chunks: list[dict], pages: tuple[int, ...], pattern: re.Pattern) -> list[dict]:
    page_set = set(pages)
    return [c for c in chunks if (set(c["pages"]) & page_set) and pattern.search(c["text"])]


def check_records(all_recs: dict[int, list[dict]], metas: dict[int, dict]) -> list[str]:
    problems = []
    for year in config.YEARS:
        recs = all_recs[year]
        idx = [r for r in recs if r["excluded"] is None]
        meta = metas[year]
        pmeta = json.loads(config.parse_meta(year, TICKER).read_text(encoding="utf-8"))
        rmeta = json.loads(config.report_metadata(year, TICKER).read_text(encoding="utf-8"))

        if any(list(r) != ck.RECORD_FIELDS for r in recs):
            problems.append(f"bmri_{year}: urutan/nama RECORD_FIELDS tidak sesuai")
        ids = [r["chunk_id"] for r in recs]
        if ids != [f"{TICKER}_{year}_{i:04d}" for i in range(1, len(ids) + 1)]:
            problems.append(f"bmri_{year}: chunk_id tidak urut tanpa celah")
        bad_meta = [
            r["chunk_id"] for r in recs
            if (r["ticker"], r["sector"], r["year"], r["doc_id"])
            != (TICKER, "bank", year, pmeta["sha256"])
            or rmeta["ticker"] != TICKER or rmeta["sector"] != "bank"
            or not r["pages"] or r["page"] != r["pages"][0] or r["pages"] != sorted(set(r["pages"]))
        ]
        if bad_meta:
            problems.append(f"bmri_{year}: metadata/pages bermasalah pada {bad_meta[:5]}")
        big = [r["chunk_id"] for r in idx if r["n_tokens"] > min(config.CHUNK_MAX_TOKENS, 8192)]
        if big:
            problems.append(f"bmri_{year}: chunk > {config.CHUNK_MAX_TOKENS} token: {big[:5]}")
        if meta["stats"].get("split_pieces_without_header", 0) != 0:
            problems.append(f"bmri_{year}: split_pieces_without_header = {meta['stats']['split_pieces_without_header']}")
        if meta["cache"] != ck.cache_key(year, TICKER):
            problems.append(f"bmri_{year}: .jsonl kedaluwarsa (cache key berbeda)")
    return problems


def report_year_of(filename: str) -> int:
    return int(re.search(r"(\d{4})", filename).group(1))


def main():
    wb = load_workbook(XLSX, data_only=True)
    ws1 = wb["1_angka_mentah"]
    ws2 = wb["2_rasio_resmi"]

    indexed, all_recs, kept_pages, metas = load_bmri_chunks()
    rec_problems = check_records(all_recs, metas)

    print("== A & B. Integritas workbook & record chunk BMRI ==")
    for y in config.YEARS:
        st = metas[y]["stats"]
        print(f"  bmri_{y}: {len(indexed[y])} chunk diindeks, {len(all_recs[y]) - len(indexed[y])} excluded, "
              f"split_tables={st['split_tables']}, without_header={st.get('split_pieces_without_header', 0)}")
    if rec_problems:
        for p in rec_problems:
            print(f"  MASALAH: {p}")
    else:
        print("  OK: seluruh record chunk BMRI valid")

    # C1. Angka langsung (21 item x 4 tahun = 84 angka)
    direct_results = []
    xlsx_missing = []
    for row, (block, source_fn, _) in sources.ROW_MAP.items():
        if row in (4, 6):
            continue
        item = ws1.cell(row=row, column=1).value
        for year in (2022, 2023, 2024, 2025):
            val = ws1.cell(row=row, column=sources.COL_IDX[year]).value
            if val is None:
                xlsx_missing.append((row, item, year))
                continue
            fname, page, _ = source_fn(year)
            ry = report_year_of(fname)
            printed = fmt_million(float(val))
            pat = num_pattern(printed)
            hits = find_in_pages(indexed[ry], (page,), pat)
            page_kept = page in kept_pages[ry]
            units = sorted({c["unit"] for c in hits})
            status = "ok"
            fallback_hit = None
            if hits:
                if "million_idr" not in units:
                    status = "wrong_unit"
            elif not page_kept:
                status = "filtered_out"
                fb = CROSS_YEAR_FALLBACK.get((row, year))
                if fb:
                    fb_ry = report_year_of(fb[0])
                    fb_hits = find_in_pages(indexed[fb_ry], (fb[1],), pat)
                    if fb_hits:
                        fallback_hit = {
                            "source": f"{fb[0]} hal {fb[1]}",
                            "chunk_id": fb_hits[0]["chunk_id"],
                            "unit": fb_hits[0]["unit"],
                        }
            else:
                status = "missing_in_chunk"
            direct_results.append({
                "row": row, "block": block, "item": item, "year": year,
                "printed_million": printed, "source": f"{fname} hal {page}",
                "page_kept": page_kept, "status": status,
                "chunk_ids": [c["chunk_id"] for c in hits],
                "units": units, "fallback": fallback_hit,
            })

    # C2. Komponen 2 item hitungan
    comp_results = []
    for year, pair in DPK_KONSOL_COMPONENTS.items():
        for fname, pages, printed in pair:
            ry = report_year_of(fname)
            hits = find_in_pages(indexed[ry], pages, num_pattern(printed))
            units = sorted({c["unit"] for c in hits})
            ok = bool(hits) and "million_idr" in units
            comp_results.append({
                "item": "DPK Konsolidasian (komponen)", "year": year,
                "printed_million": printed, "source": f"{fname} hal {pages}",
                "ok": ok, "chunk_ids": [c["chunk_id"] for c in hits], "units": units,
            })
    for year, (fname, pages, vals) in EARNING_ASSET_COMPONENTS.items():
        ry = report_year_of(fname)
        for printed in vals:
            hits = find_in_pages(indexed[ry], pages, num_pattern(printed))
            units = sorted({c["unit"] for c in hits})
            ok = bool(hits) and "million_idr" in units
            comp_results.append({
                "item": "Aset Produktif Inti Bank (komponen)", "year": year,
                "printed_million": printed, "source": f"{fname} hal {pages}",
                "ok": ok, "chunk_ids": [c["chunk_id"] for c in hits], "units": units,
            })

    # C3. 18 rasio resmi (di bmri_2025 hal 39-40 dan di laporan tahunnya masing-masing)
    ratio_results = []
    for r in range(2, 20):
        yr = int(ws2.cell(row=r, column=1).value)
        rt = ws2.cell(row=r, column=2).value
        val = float(ws2.cell(row=r, column=3).value)
        pat = pct_pattern(val)
        hits_2025 = find_in_pages(indexed[2025], RATIO_PAGES_BY_REPORT[2025], pat)
        hits_own = find_in_pages(indexed[yr], RATIO_PAGES_BY_REPORT[yr], pat)
        ratio_results.append({
            "year": yr, "ratio": rt, "value": val,
            "in_2025_hal39_40": bool(hits_2025),
            "in_own_report": bool(hits_own),
            "own_report_chunks": [c["chunk_id"] for c in hits_own],
        })

    ok_direct = [r for r in direct_results if r["status"] == "ok"]
    filt_direct = [r for r in direct_results if r["status"] == "filtered_out"]
    bad_direct = [r for r in direct_results if r["status"] not in ("ok", "filtered_out")]
    ok_comp = [r for r in comp_results if r["ok"]]
    bad_comp = [r for r in comp_results if not r["ok"]]
    ok_ratios = [r for r in ratio_results if r["in_2025_hal39_40"] and r["in_own_report"]]
    bad_ratios = [r for r in ratio_results if not (r["in_2025_hal39_40"] and r["in_own_report"])]

    print(f"\n== C. Keterbacaan angka ground truth BMRI di chunk (unit='million_idr') ==")
    print(f"  Angka langsung (21 item x 4 thn) : {len(ok_direct)}/{len(direct_results)} terbaca tepat di halaman sumber")
    print(f"    - halaman dilewati page_filter : {len(filt_direct)} (dicatat transparan di bawah)")
    print(f"    - hilang / salah unit          : {len(bad_direct)}")
    for r in filt_direct:
        fb = r["fallback"]
        fb_note = f" -> terbaca di pembanding {fb['source']} ({fb['chunk_id']}, unit={fb['unit']})" if fb else " -> tidak ada di pembanding"
        print(f"      [SKIP page_filter] {r['item']} {r['year']} ({r['printed_million']}) di {r['source']}{fb_note}")
    for r in bad_direct:
        print(f"      [GAGAL:{r['status']}] {r['item']} {r['year']} ({r['printed_million']}) di {r['source']} units={r['units']}")

    print(f"  Komponen 2 item hitungan         : {len(ok_comp)}/{len(comp_results)} terbaca tepat (unit=million_idr)")
    for r in bad_comp:
        print(f"      [GAGAL] {r['item']} {r['year']} ({r['printed_million']}) di {r['source']} units={r['units']}")

    print(f"  Rasio resmi (2_rasio_resmi)      : {len(ok_ratios)}/{len(ratio_results)} terbaca di bmri_2025 hal 39-40 & laporan tahunnya")
    for r in bad_ratios:
        print(f"      [GAGAL] {r['ratio']} {r['year']} ({r['value']}%): in_2025={r['in_2025_hal39_40']}, in_own={r['in_own_report']}")

    # Cek khusus semua angka tahun 2023-2025 di halaman yang lolos page_filter
    failures = list(rec_problems)
    if xlsx_missing:
        failures.append(f"Cell kosong di ground_truth_bmri.xlsx: {xlsx_missing}")
    if bad_direct:
        failures.append(f"{len(bad_direct)} angka langsung gagal/salah unit pada halaman yang lolos saringan")
    if bad_comp:
        failures.append(f"{len(bad_comp)} komponen item hitungan gagal/salah unit")
    if bad_ratios:
        failures.append(f"{len(bad_ratios)} rasio resmi tidak terbaca di chunk")

    out = config.RESULTS / "check_bmri_chunks.json"
    out.parent.mkdir(exist_ok=True)
    report = {
        "ticker": TICKER,
        "record_problems": rec_problems,
        "direct": {
            "total": len(direct_results),
            "ok": len(ok_direct),
            "filtered_out": len(filt_direct),
            "failed": len(bad_direct),
            "items": direct_results,
        },
        "computed_components": {
            "total": len(comp_results),
            "ok": len(ok_comp),
            "failed": len(bad_comp),
            "items": comp_results,
        },
        "official_ratios": {
            "total": len(ratio_results),
            "ok": len(ok_ratios),
            "failed": len(bad_ratios),
            "items": ratio_results,
        },
        "passed": not failures,
        "failures": failures,
    }
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRingkasan -> {out.relative_to(ROOT)}")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
