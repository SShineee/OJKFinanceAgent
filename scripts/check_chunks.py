"""
Tugas 5.3-5.4 -- uji chunk.  docs/PANDUAN_MINGGU5.md, Langkah 5 dan 6a.

Jalankan:  python scripts/check_chunks.py            (semua cek + uji negatif, +-4 menit)
           python scripts/check_chunks.py --quick    (tanpa uji negatif)

Yang diuji adalah FILE data/chunks/bbca_<tahun>.jsonl (hasil Langkah 7) -- yang akan di-embed di
Minggu 6 -- dibandingkan dengan dokumen Docling yang sudah diperbaiki (load_fixed).

A. 76 angka ground truth bisa dibaca dari TEKS CHUNK yang diindeks: di baris tabel Markdown
   berlabel X dan kolom berjudul Y (angka tabel), di kalimatnya (NPL, CKPN), atau komponennya
   (kredit bruto = neto + CKPN; DPK = pihak berelasi + pihak ketiga) -- di chunk yang `pages`-nya
   memuat halaman sumber (build_verification_sheet.py), dengan `unit` yang benar (Ikhtisar = miliar;
   KPMM, NPL, Entitas Induk = juta). Logika lokasinya sama dengan check_parse_output.py, tetapi
   dibaca dari Markdown chunk -- persis yang dibaca LLM.
B. Tabel: setiap potongan tabel memuat header kolomnya; setiap baris badan tabel ada UTUH di
   chunk-chunk tabel itu -- tidak hilang, tidak terbelah (blok header dibuang sekali per potongan:
   hal 569 bbca_2025 punya baris badan yang sama dengan header).
C. Record: 15 field berurutan; chunk_id urut; ticker/sector/year/doc_id dari .metadata.json &
   .meta.json; n_tokens = hitung ulang; tidak ada chunk > CHUNK_MAX_TOKENS (<= 8192 BGE-M3); tidak
   ada boilerplate tersisa (angka diabaikan); .jsonl tidak kedaluwarsa (kunci cache sama).
D. Halaman: `pages` = semua prov semua item (bukan prov[0]); tidak ada chunk yang melompati
   halaman yang dilewati penyaring; tidak ada judul dari sebelum celah; tidak ada item navigasi.
E. Satuan: `unit` = hasil hitung ulang per halaman; tidak ada chunk tanpa satuan yang berisi
   >= 5 angka nominal (kecuali tabel rasio resmi yang memang persen + jumlah rekening/cabang).
F. merged_cells: tepat per baris bersel dua angka.
G. Tabel tanpa label baris: tidak ada di chunk diindeks; angka uniknya tidak muncul di teks chunk
   diindeks tetapi ada di record excluded-nya; tepat 18 / 17 / 17 record; item lain sama dengan
   pemotongan tanpa pengecualian (tidak ada yang ikut hilang).
H. Uji negatif: pemeriksaan di atas HARUS gagal kalau `pages` hanya dari prov[0], kalau satuan
   ditukar, atau kalau tabel tanpa label tidak dikeluarkan.

Distribusi panjang (Langkah 5) + hasil semua cek -> results/check_chunks.json (bahan Bab 4).
"""

import argparse
import copy
import json
import re
import statistics
import sys
import time
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore", message="Table cell bbox")   # bbox di luar halaman, di-clamp Docling

from docling_core.types.doc import RefItem
from openpyxl import load_workbook

import build_verification_sheet as sources
import check_parse_output as gt                     # pola label & format angka ground truth
from src import config
from src.ingest import chunk as ck
from src.ingest.fix_tables import load_fixed
from src.ingest.subset_pdf import PageMap

EXPECTED_EXCLUDED = {2023: 18, 2024: 17, 2025: 17}            # Langkah 2, dicek visual
RATIO_PAGES = {2023: {19}, 2024: {21}, 2025: set()}           # tabel rasio resmi: persen + jumlah rekening/ATM
AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
SEPARATOR = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
UNIT_OF = {"A. Ikhtisar": "billion_idr"}                      # selain itu: million_idr


# ----------------------------------------------------------------- data satu laporan

@dataclass
class Report:
    year: int
    records: list[dict]
    doc: object
    report: object
    page_map: PageMap
    meta: dict
    metadata: dict

    @property
    def chunks(self):
        return [r for r in self.records if r["excluded"] is None]

    @property
    def excluded(self):
        return [r for r in self.records if r["excluded"] is not None]


def load(year: int) -> Report:
    meta = json.loads(config.parse_meta(year).read_text(encoding="utf-8"))
    doc, report = load_fixed(year)
    return Report(year, ck.load_chunks(year, include_excluded=True), doc, report,
                  PageMap.from_list(meta["page_map"]), meta,
                  json.loads(config.report_metadata(year).read_text(encoding="utf-8")))


def resolve(doc, ref: str):
    return RefItem(cref=ref).resolve(doc)


# ----------------------------------------------------------------- Markdown di teks chunk

def md_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def md_tables(text: str):
    """(judul kolom, baris) untuk setiap tabel Markdown di teks chunk."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if i and SEPARATOR.match(line) and lines[i - 1].startswith("|"):
            rows, j = [], i + 1
            while j < len(lines) and lines[j].startswith("|") and not SEPARATOR.match(lines[j]):
                rows.append(md_cells(lines[j]))
                j += 1
            yield md_cells(lines[i - 1]), rows


def on_page(rep: Report, page: int) -> list[dict]:
    return [c for c in rep.chunks if page in c["pages"]]


def find_row(chunks, label: str, column_ok, after: str | None = None):
    """(chunk, baris, kolom, baris berikutnya) -- sel di baris berlabel `label`, kolom lolos `column_ok`."""
    for chunk in chunks:
        for titles, rows in md_tables(chunk["text"]):
            start = 0
            if after:
                start = next((i + 1 for i, row in enumerate(rows) if re.search(after, row[0])), len(rows))
            hits = [i for i in range(start, len(rows)) if re.search(label, rows[i][0])]
            cols = [j for j in range(1, len(titles)) if column_ok(titles[j])]
            if hits and cols:
                i = hits[0]
                return chunk, rows[i], cols[0], rows[i + 1] if i + 1 < len(rows) else None
    return None


# ----------------------------------------------------------------- A. ground truth

def check_ground_truth(reports: dict[int, Report]) -> tuple[list[str], list[dict]]:
    ws = load_workbook(config.GROUND_TRUTH, data_only=False)["1_angka_mentah"]
    value = lambda row, year: ws.cell(row=row, column=sources.COL_IDX[year]).value
    name = lambda row: ws.cell(row=row, column=1).value
    results = []

    def record(block, item, year, expected, spec, chunk, ok, detail=""):
        report_year, page, where = gt.source_of(spec)
        want_unit = UNIT_OF.get(block, "million_idr")
        if ok and chunk["unit"] != want_unit:
            ok, detail = False, f"angka ada di {chunk['chunk_id']}, tetapi unit {chunk['unit']} (harus {want_unit})"
        results.append({"block": block, "item": item, "year": year, "expected": expected, "source": where,
                        "chunk_id": chunk["chunk_id"] if chunk else None, "ok": ok, "detail": detail})

    def table_value(block, item, year, expected, spec, label, column_ok, after=None):
        report_year, page, _ = gt.source_of(spec)
        found = find_row(on_page(reports[report_year], page), label, column_ok, after)
        if found is None:
            return record(block, item, year, expected, spec, None, False, "baris/kolom tidak ada di chunk halaman itu")
        chunk, row, col, _ = found
        got = row[col] if col < len(row) else ""
        record(block, item, year, expected, spec, chunk, got == expected, "" if got == expected else f"sel '{got}'")

    for row, (label, after) in gt.HIGHLIGHT_ROWS.items():
        for year in gt.YEARS:
            table_value("A. Ikhtisar", name(row), year, gt.thousands(value(row, year)), sources.HIGHLIGHTS(year),
                        label, lambda title, y=year: title == str(y), after)
    for row, (label, basis) in gt.CAPITAL_ROWS.items():
        block = "B. KPMM Bank" if basis == "bank" else "C. KPMM Konsolidasian"
        spec = sources.CAPITAL_BANK if basis == "bank" else sources.CAPITAL_CONSOLIDATED
        for year in gt.YEARS:
            column_ok = lambda title, y=year, b=basis: str(y) in title.split() and b in title.lower().split()
            table_value(block, name(row), year, gt.juta(value(row, year)), spec[year], label, column_ok)

    block = "D. Kredit & NPL Bank"
    for year in gt.YEARS:
        # NPL: kalimat narasi
        spec = sources.NPL[year]
        report_year, page, _ = gt.source_of(spec)
        expected = gt.juta(value(gt.NPL_ROW, year))
        hit = None
        for chunk in on_page(reports[report_year], page):
            for line in chunk["text"].splitlines():
                years = re.search(r"31 Desember (\d{4}) dan (\d{4})", line)
                amounts = re.findall(gt.AMOUNT, line)
                if "non-performing" in line.lower() and years and len(amounts) >= 2:
                    by_year = {int(years.group(1)): amounts[0], int(years.group(2)): amounts[1]}
                    if by_year.get(year) == expected:
                        hit = chunk
        record(block, name(gt.NPL_ROW), year, expected, spec, hit, hit is not None,
               "" if hit else "kalimat NPL dengan angka itu tidak ada di chunk halaman itu")

        # CKPN (di label baris kredit) dan kredit bruto (neto + CKPN)
        spec = sources.PARENT_ASSETS[year]
        report_year, page, _ = gt.source_of(spec)
        chunks = on_page(reports[report_year], page)
        found = find_row(chunks, gt.LOANS_LABEL.pattern, lambda title, y=year: title == str(y))
        allowance = None
        if found:
            m = gt.ALLOWANCE_TEXT.search(found[1][0])
            if m:
                allowance = {int(m.group(2)): m.group(1), int(m.group(3)): m.group(4)}.get(year)
        expected = gt.juta(value(gt.ALLOWANCE_ROW, year))
        record(block, name(gt.ALLOWANCE_ROW), year, expected, spec, found[0] if found else None,
               allowance == expected, "" if allowance == expected else f"CKPN terbaca {allowance}")
        expected = gt.juta(value(gt.GROSS_LOANS_ROW, year))
        if found is None or allowance is None:
            record(block, name(gt.GROSS_LOANS_ROW), year, expected, spec, None, False, "baris kredit / CKPN tidak ada")
        else:
            chunk, row, col, nxt = found
            cells = [row[col]]
            if re.search(r"Pihak berelasi$", row[0]):
                cells.append(nxt[col] if nxt and re.search(r"Pihak ketiga$", nxt[0]) else None)
            ok = None not in cells and all(len(gt.NUMBER.findall(c)) == 1 for c in cells)
            total = sum(gt.to_int(c) for c in cells) + gt.to_int(allowance) if ok else None
            ok = ok and total == gt.to_int(expected)
            record(block, name(gt.GROSS_LOANS_ROW), year, expected, spec, chunk, ok,
                   "" if ok else f"komponen {cells} + CKPN {allowance} (baris pihak ketiga harus di chunk yang sama)")

        # DPK bank: satu baris atau pihak berelasi + pihak ketiga
        spec = sources.PARENT_LIABILITIES[year]
        report_year, page, _ = gt.source_of(spec)
        expected = gt.juta(value(gt.DEPOSITS_ROW, year))
        found = find_row(on_page(reports[report_year], page), r"^Simpanan dari nasabah",
                         lambda title, y=year: title == str(y))
        if found is None:
            record(block, name(gt.DEPOSITS_ROW), year, expected, spec, None, False, "baris simpanan tidak ada")
        else:
            chunk, row, col, nxt = found
            cells = [row[col]]
            if "pihak berelasi" in row[0].lower():
                cells.append(nxt[col] if nxt and re.search(r"Pihak ketiga$", nxt[0]) else None)
            ok = None not in cells and all(len(gt.NUMBER.findall(c)) == 1 for c in cells)
            ok = ok and sum(gt.to_int(c) for c in cells) == gt.to_int(expected)
            record(block, name(gt.DEPOSITS_ROW), year, expected, spec, chunk, ok, "" if ok else f"komponen {cells}")

    failures = [f"[A] {r['item']} {r['year']} = {r['expected']} ({r['source']}): {r['detail']}"
                for r in results if not r["ok"]]
    return failures, results


# ----------------------------------------------------------------- B-G per laporan

def check_tables(rep: Report) -> list[str]:
    ser = ck.CompactMarkdownTables().get_serializer(rep.doc)
    tables = {t.self_ref: t for t in rep.doc.tables}
    by_table = defaultdict(list)
    for c in rep.chunks:
        for ref in c["items"]:
            if ref in tables:
                by_table[ref].append(c)
    out = []
    for ref, chunks in by_table.items():
        head, body = ser.table_serializer.get_header_and_body_lines(
            table_text=ser.serialize(item=tables[ref]).text)
        block = "".join(head)
        missing = [c["chunk_id"] for c in chunks if block not in c["text"]]
        if missing:
            out.append(f"[B] {ref}: potongan tanpa header kolom {missing}")
        # baris yang hilang atau terbelah = muncul lebih sedikit dari seharusnya. Lebih banyak boleh:
        # tabel lain di chunk yang sama bisa punya baris identik (mis. "| No. | Keterangan | ..." di
        # tabel 45 dan 46 bbca_2024), dan pemotong tidak pernah menggandakan baris selain header.
        got = Counter(line for c in chunks for line in c["text"].replace(block, "", 1).splitlines())
        want = Counter(line.rstrip("\n") for line in body if line.strip())
        broken = [line for line, n in want.items() if got[line] < n]
        if broken:
            out.append(f"[B] {ref}: {len(broken)} baris badan hilang/terbelah, mis. {broken[0][:80]!r}")
    return out


def body_of(record: dict) -> str:
    """Teks chunk tanpa judul di depannya (contextualize = judul + isi)."""
    if record["headings"]:
        return record["text"][len("\n".join(record["headings"])) + 1:]
    return record["text"]


def check_records(rep: Report) -> list[str]:
    out = []
    y = rep.year
    if any(list(r) != ck.RECORD_FIELDS for r in rep.records):
        out.append("[C] ada record yang field-nya tidak sama/berurutan dengan RECORD_FIELDS")
    ids = [r["chunk_id"] for r in rep.records]
    if ids != [f"{rep.metadata['ticker']}_{y}_{i:04d}" for i in range(1, len(ids) + 1)]:
        out.append("[C] chunk_id tidak urut tanpa celah")
    bad = [r["chunk_id"] for r in rep.records
           if (r["ticker"], r["sector"], r["year"], r["doc_id"])
           != (rep.metadata["ticker"], rep.metadata["sector"], rep.metadata["year"], rep.meta["sha256"])
           or not r["pages"] or r["page"] != r["pages"][0] or r["pages"] != sorted(set(r["pages"]))]
    if bad:
        out.append(f"[C] ticker/sector/year/doc_id/pages tidak sesuai: {bad[:5]}")
    tok = ck.tokenizer()
    wrong = [r["chunk_id"] for r in rep.records if tok.count_tokens(r["text"]) != r["n_tokens"]]
    if wrong:
        out.append(f"[C] n_tokens beda dengan hitung ulang: {wrong[:5]}")
    big = [r["chunk_id"] for r in rep.chunks if r["n_tokens"] > min(config.CHUNK_MAX_TOKENS, 8192)]
    if big:
        out.append(f"[C] chunk > {config.CHUNK_MAX_TOKENS} token: {big[:5]}")
    repeated = [t[:60] for t, n in Counter(ck.text_shape(body_of(r)) for r in rep.chunks).items()
                if n >= config.CHUNK_BOILERPLATE_REPEAT]
    if repeated:
        out.append(f"[C] boilerplate tersisa: {repeated[:3]}")
    tables = {t.self_ref for t in rep.doc.tables}
    flag = [r["chunk_id"] for r in rep.records if r["is_table"] != any(i in tables for i in r["items"])]
    if flag:
        out.append(f"[C] is_table salah: {flag[:5]}")
    meta = json.loads(config.chunks_meta(y).read_text(encoding="utf-8"))
    if meta["cache"] != ck.cache_key(y, rep.metadata["ticker"]):
        out.append("[C] .jsonl kedaluwarsa (kunci cache beda) -- jalankan ulang python -m src.ingest.chunk")
    return out


def check_pages(rep: Report) -> list[str]:
    out = []
    pm = rep.page_map
    wrong = [r["chunk_id"] for r in rep.records
             if r["pages"] != ck.item_pages([resolve(rep.doc, i) for i in r["items"]], pm)]
    if wrong:
        out.append(f"[D] pages bukan semua prov semua item: {len(wrong)} record, mis. {wrong[:3]}")
    crossing = [r["pages"] for r in rep.chunks if ck.skips_pages(pm, r["pages"][0], r["pages"][-1])
                and not any(len({p.page_no for p in resolve(rep.doc, i).prov}) > 1 for i in r["items"])]
    if crossing:
        out.append(f"[D] chunk melompati halaman yang dilewati penyaring: {crossing[:5]}")
    ctx = ck.heading_context(rep.doc, pm)
    stale = [r["chunk_id"] for r in rep.chunks if r["headings"]
             and ctx[r["items"][0]][1] is not None and ck.skips_pages(pm, ctx[r["items"][0]][1], r["page"])]
    if stale:
        out.append(f"[D] judul dari sebelum celah halaman: {stale[:5]}")
    nav = ck.margin_furniture(rep.doc) & {i for r in rep.records for i in r["items"]}
    if nav:
        out.append(f"[D] item navigasi/footer masuk record: {sorted(nav)[:5]}")
    return out


def check_units(rep: Report) -> list[str]:
    out = []
    units, summary = ck.page_units(rep.doc, rep.page_map, rep.report)
    wrong = [r["chunk_id"] for r in rep.records if r["unit"] != ck.chunk_unit(r["pages"], units)[0]]
    if wrong:
        out.append(f"[E] unit beda dengan hitung ulang per halaman: {len(wrong)} record, mis. {wrong[:3]}")
    blank = [(r["chunk_id"], r["pages"]) for r in rep.chunks if r["unit"] is None
             and len(AMOUNT.findall(r["text"])) >= 5 and not set(r["pages"]) & RATIO_PAGES[rep.year]]
    if blank:
        out.append(f"[E] chunk tanpa satuan berisi >= 5 angka nominal: {blank[:5]}")
    if summary["mixed_pages"]:
        out.append(f"[E] halaman bersatuan campur: {summary['mixed_pages']}")
    return out


def check_merged(rep: Report) -> list[str]:
    out = []
    merged = ck.merged_lines(rep.doc, ck.CompactMarkdownTables().get_serializer(rep.doc))
    wrong = [r["chunk_id"] for r in rep.records
             if r["merged_cells"] != any(set(r["text"].splitlines()) & merged.get(i, set()) for i in r["items"])]
    if wrong:
        out.append(f"[F] merged_cells salah: {wrong[:5]}")
    lost = [(ref, line[:60]) for ref, lines in merged.items() for line in lines
            if not any(ref in r["items"] and line in r["text"].splitlines() for r in rep.records)]
    if lost:
        out.append(f"[F] baris bersel dua angka tidak ada di record mana pun: {lost[:3]}")
    return out


def check_unlabeled(rep: Report, deep: bool = True) -> list[str]:
    out = []
    bad = rep.report.unlabeled_refs()
    tables = {t.self_ref: t for t in rep.doc.tables}
    leaked = bad & {i for r in rep.chunks for i in r["items"]}
    if leaked:
        out.append(f"[G] tabel tanpa label di chunk diindeks: {sorted(leaked)[:5]}")
    if len(rep.excluded) != EXPECTED_EXCLUDED[rep.year] or {r["items"][0] for r in rep.excluded} != bad:
        out.append(f"[G] record excluded {len(rep.excluded)} (harus {EXPECTED_EXCLUDED[rep.year]}, satu per tabel)")
    indexed_text = "\n".join(r["text"] for r in rep.chunks)
    other = "\n".join(c.text for t in rep.doc.tables if t.self_ref not in bad for row in t.data.grid for c in row)
    by_ref = {r["items"][0]: r for r in rep.excluded}
    for ref in sorted(bad):
        nums = [x for row in tables[ref].data.grid for c in row for x in re.findall(r"\d{1,3}(?:\.\d{3}){2,}", c.text)]
        unique = [n for n in dict.fromkeys(nums) if n not in other][:5]
        if any(n in indexed_text for n in unique):
            out.append(f"[G] angka unik {ref} muncul di chunk diindeks")
        if ref in by_ref and not all(n in by_ref[ref]["text"] for n in unique):
            out.append(f"[G] record excluded {ref} tidak memuat angka tabelnya")
    if deep:   # pembanding: pemotongan TANPA pengecualian -> tidak ada item lain yang ikut hilang
        furniture = ck.margin_furniture(rep.doc)
        plain = {it.self_ref for c in ck.make_chunker().chunk(dl_doc=rep.doc) for it in c.meta.doc_items}
        chunker = ck.make_chunker(bad | furniture, rep.page_map, ck.heading_context(rep.doc, rep.page_map))
        raw = list(chunker.chunk(dl_doc=rep.doc))
        skipped = {it.self_ref for c in raw for it in c.meta.doc_items}
        if plain - bad - furniture != skipped:
            out.append(f"[G] item lain ikut hilang/bertambah: {len(plain - bad - furniture - skipped)} / "
                       f"{len(skipped - plain)}")
        repeats = Counter(ck.text_shape(c.text) for c in raw)
        kept = {it.self_ref for c in raw if repeats[ck.text_shape(c.text)] < config.CHUNK_BOILERPLATE_REPEAT for it in c.meta.doc_items}
        if kept != {i for r in rep.chunks for i in r["items"]}:
            out.append("[G] item di chunk diindeks beda dengan pemotongan ulang (.jsonl tidak cocok)")
    return out


def run_checks(rep: Report, deep: bool = True) -> dict[str, list[str]]:
    return {"B. tabel": check_tables(rep), "C. record": check_records(rep), "D. halaman": check_pages(rep),
            "E. satuan": check_units(rep), "F. merged_cells": check_merged(rep),
            "G. tabel tanpa label": check_unlabeled(rep, deep)}


# ----------------------------------------------------------------- Langkah 5: distribusi

def distribution(rep: Report) -> dict:
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")          # tokenizer gpt-oss -> anggaran kuota Groq
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
    bge = [r["n_tokens"] for r in rep.chunks]
    oss = [len(enc.encode(r["text"])) for r in rep.chunks]
    stats = json.loads(config.chunks_meta(rep.year).read_text(encoding="utf-8"))["stats"]
    return {"chunks_raw": stats["chunks_raw"], "boilerplate_dropped": stats["boilerplate_dropped"],
            "indexed": len(rep.chunks), "excluded": len(rep.excluded),
            "bge_median": statistics.median(bge), "bge_p90": q(bge, .9), "bge_max": max(bge),
            "oss_median": statistics.median(oss), "oss_p90": q(oss, .9), "oss_max": max(oss),
            "oss_total": sum(oss), "short_under_50_bge": sum(n < 50 for n in bge),
            "split_tables": stats["split_tables"], "is_table": stats["is_table"],
            "multi_page": stats["multi_page"], "units": stats["units"], "merged_cells": stats["merged_cells"],
            "fix": {k: stats["fix"][k] for k in ("sub_rows_fixed", "printed_lines_fixed", "flagged_rows")},
            "seconds_fixing": stats["seconds_fixing"], "seconds_chunking": stats["seconds_chunking"]}


# ----------------------------------------------------------------- H. uji negatif

def negative_tests(reports: dict[int, Report]) -> list[str]:
    """Setiap mutasi HARUS membuat pemeriksaan yang bersangkutan gagal."""
    out = []

    # 1. pages hanya dari prov[0]
    hits = 0
    for rep in reports.values():
        mutated = copy.copy(rep)
        mutated.records = [dict(r, pages=(p := sorted({rep.page_map.to_original(resolve(rep.doc, i).prov[0].page_no)
                                                       for i in r["items"]})), page=p[0])
                           for r in rep.records]
        hits += bool(check_pages(mutated))
    print(f"  {'OK   ' if hits else 'GAGAL'} negatif 1: pages hanya prov[0] -> cek halaman gagal di {hits} laporan")
    if not hits:
        out.append("[H] pemakaian prov[0] tidak terdeteksi")

    # 2. satuan ditukar juta <-> miliar
    swap = {"million_idr": "billion_idr", "billion_idr": "million_idr"}
    mutated = {}
    for y, rep in reports.items():
        mutated[y] = copy.copy(rep)
        mutated[y].records = [dict(r, unit=swap.get(r["unit"], r["unit"])) for r in rep.records]
    failures, _ = check_ground_truth(mutated)
    unit_fail = sum(bool(check_units(m)) for m in mutated.values())
    ok = bool(failures) and unit_fail == len(mutated)
    print(f"  {'OK   ' if ok else 'GAGAL'} negatif 2: satuan ditukar -> {len(failures)} angka ground truth gagal, "
          f"cek satuan gagal di {unit_fail} laporan")
    if not ok:
        out.append("[H] satuan tertukar tidak terdeteksi")

    # 3. tabel tanpa label TIDAK dikeluarkan (dipotong ulang tanpa daftar Langkah 2)
    hits = 0
    for y, rep in reports.items():
        no_skip = copy.copy(rep.report)
        no_skip.unlabeled = []
        result = ck.chunk_document(rep.doc, no_skip, rep.page_map, ticker=rep.metadata["ticker"],
                                   sector=rep.metadata["sector"], year=y, doc_id=rep.meta["sha256"])
        mutated = copy.copy(rep)
        mutated.records = result.records()
        hits += bool(check_unlabeled(mutated, deep=False))
    print(f"  {'OK   ' if hits == len(reports) else 'GAGAL'} negatif 3: tabel tanpa label tidak dikeluarkan -> "
          f"cek tabel tanpa label gagal di {hits} laporan")
    if hits != len(reports):
        out.append("[H] tabel tanpa label yang tidak dikeluarkan tidak terdeteksi")
    return out


# ----------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Uji chunk data/chunks/bbca_<tahun>.jsonl (Langkah 5-6).")
    ap.add_argument("--quick", action="store_true", help="tanpa uji negatif dan pembanding pemotongan ulang")
    args = ap.parse_args(argv)
    start = time.perf_counter()
    failures = []
    summary = {"reports": {}}

    reports = {}
    for y in config.YEARS:
        rep = reports[y] = load(y)
        print(f"== bbca_{y}: {len(rep.chunks)} chunk diindeks + {len(rep.excluded)} record excluded")
        for name, problems in run_checks(rep, deep=not args.quick).items():
            print(f"  {'OK   ' if not problems else 'GAGAL'} {name}" + (f": {len(problems)} masalah" if problems else ""))
            for p in problems[:5]:
                print(f"         {p}")
            failures += problems
        summary["reports"][f"bbca_{y}"] = distribution(rep)

    print("\n== A. 76 angka ground truth di teks chunk (baris + kolom + halaman + satuan)")
    gt_failures, gt_results = check_ground_truth(reports)
    for block in sorted({r["block"] for r in gt_results}):
        rows = [r for r in gt_results if r["block"] == block]
        print(f"  {block:<24} {sum(r['ok'] for r in rows):>2} / {len(rows)}")
    for p in gt_failures:
        print(f"         {p}")
    failures += gt_failures
    summary["ground_truth"] = {"ok": sum(r["ok"] for r in gt_results), "total": len(gt_results),
                               "results": gt_results}

    if not args.quick:
        print("\n== H. uji negatif (harus GAGAL kalau aturannya dilanggar)")
        failures += negative_tests(reports)

    print("\n== Langkah 5: distribusi panjang chunk diindeks")
    print(f"  {'':<10} {'chunk':>6} {'boiler':>6} {'excl':>5} {'BGE med/p90/maks':>18} "
          f"{'gpt-oss med/p90/maks':>22} {'<50 tok':>8} {'terbelah':>9}")
    for name, d in summary["reports"].items():
        print(f"  {name:<10} {d['indexed']:>6} {d['boilerplate_dropped']:>6} {d['excluded']:>5} "
              f"{d['bge_median']:>6g}/{d['bge_p90']}/{d['bge_max']:>5} {d['oss_median']:>8g}/{d['oss_p90']}/{d['oss_max']:>5} "
              f"{d['short_under_50_bge']:>8} {d['split_tables']:>9}")

    summary["failures"] = failures
    summary["passed"] = not failures
    summary["seconds"] = round(time.perf_counter() - start, 1)
    out = config.RESULTS / "check_chunks.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRingkasan -> {out.relative_to(ROOT)}  ({summary['seconds']} s)")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
