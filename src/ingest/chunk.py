"""
Tugas 5.1-5.5 -- pemotong (chunker), metadata, dan penyimpanan chunk.
docs/PANDUAN_MINGGU5.md, Langkah 3, 4, dan 7.

Alur:  data/markdown/<kode>_<tahun>.json
       -> load_fixed: sel dua angka diperbaiki (Langkah 1), tabel tanpa label baris dicatat
          (Langkah 2) -- di memori, .json tidak diubah
       -> HybridChunker (docling-core):
            - token dihitung dengan tokenizer BGE-M3 (model embedding Minggu 6), maks.
              config.CHUNK_MAX_TOKENS (Keputusan 5.A = 1024)
            - tabel ditulis sebagai Markdown ringkas, bukan triplet bawaan (2,2x lebih boros token;
              satu tabel triplet 9.639 token, melebihi batas BGE-M3)
            - tabel yang lebih besar dari batas dipecah PER BARIS, dan header kolomnya diulang di
              setiap potongan
            - potongan kecil yang judulnya sama digabung (merge_peers, bawaan)
            - tabel tanpa label baris DILEWATI PER ITEM lewat get_excluded_refs. Dokumen tidak
              diubah, jadi rujukan #/tables/N tidak bergeser. Menandai per chunk tidak bisa:
              HybridChunker menggabungkan tabel ini dengan bagian kirinya yang berlabel, paragraf,
              dan daftar (6-11 chunk per laporan), sehingga isi yang baik ikut terbuang.
       -> halaman ASLI dari SEMUA prov semua item. Ada blok lintas halaman, jadi prov[0] saja
          kurang; nomor di .json adalah nomor PDF potongan, diterjemahkan dengan PageMap.
       -> boilerplate dibuang: chunk yang teksnya (angka diabaikan) muncul >= CHUNK_BOILERPLATE_REPEAT kali
          dalam satu laporan (di BCA: "(Dalam jutaan Rupiah, kecuali dinyatakan lain)", judul
          "(lanjutan)", kalimat disclaimer, "Lampiran 5/97"). Chunk pendek yang unik TETAP disimpan.
       +  satu record audit per tabel tanpa label baris (excluded). Record ini TIDAK diindeks di
          Minggu 6: angka tanpa label baris tidak menjawab pertanyaan apa pun.
       -> metadata (Langkah 4), lihat RECORD_FIELDS.

Heading Docling di laporan BCA datar (semua level 1), jadi `headings` = judul terdekat.
Header/footer halaman berlabel furniture, sehingga otomatis tidak ikut; navigasi/footer yang
Docling labeli sebagai isi (bbca_2023) dilewati lewat margin_furniture(). Judul TIDAK dibawa
melintasi halaman yang dilewati penyaring (GapAwareChunker): PDF potongan menyambung halaman yang
tidak bersebelahan, mis. hal 219 -> 316 `bbca_2025`.

SATUAN dicatat per HALAMAN, bukan per laporan: Ikhtisar BCA dalam miliar, laporan keuangan dalam
juta. Penandanya dicari di teks Docling halaman itu, termasuk sel tabel. Dua tambahan, keduanya
dari pengecekan 15-11-2026:
  - penandanya lebih longgar dari page_filter (tanpa kata "dalam"), karena Docling kadang memecah
    "(dalam jutaan Rupiah)" ke dua sel judul: "(dalam Kontrak" + "jutaan Rupiah)";
  - bagian KIRI tabel dua halaman (Langkah 2) mewarisi satuan halaman kanannya, karena penanda
    tabel itu hanya tercetak di halaman kanan.
Halaman tanpa penanda (mis. tabel rasio resmi, isinya persen) -> unit None.

Simpan (Langkah 7): data/chunks/<kode>_<tahun>.jsonl, satu record per baris, urut chunk_id,
termasuk record excluded (Minggu 6 hanya meng-embed yang excluded = None -> load_chunks()).
.chunks.meta.json berisi kunci cache + statistik, ditulis PALING AKHIR. Kalau kuncinya sama (hash
PDF, hash .json Docling, hash .metadata.json, CHUNK_VERSION, versi docling-core, model & batas
token, hash kode aturannya), pemotongan dilewati.

Jalankan:  python -m src.ingest.chunk data/markdown/bbca_2024.json            (simpan, pakai cache)
           python -m src.ingest.chunk data/markdown/bbca_2024.json --force    (buat ulang)
           python -m src.ingest.chunk data/markdown/bbca_2024.json --page 540 (isi record hal 540)
Uji:       python scripts/check_chunks.py
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer, ChunkingSerializerProvider)
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.serializer.markdown import MarkdownParams, MarkdownTableSerializer
from docling_core.types.doc import (ContentLayer, DoclingDocument, SectionHeaderItem, TableItem,
                                    TextItem, TitleItem)
from docling_core.types.doc.base import ImageRefMode

from src import config
from src.ingest.fix_tables import FixReport, load_fixed, merged_rows
from src.ingest.page_filter import UNIT_MARKERS, normalize
from src.ingest.subset_pdf import PageMap

EXCLUDED_UNLABELED = "tabel tanpa label baris"     # alasan record audit Langkah 2

# urutan field di .jsonl -- `text` terakhir supaya baris mudah dibaca
RECORD_FIELDS = ["chunk_id", "doc_id", "ticker", "sector", "year", "page", "pages", "headings",
                 "is_table", "unit", "merged_cells", "excluded", "n_tokens", "items", "text"]

# Penanda satuan per halaman. Sengaja LEBIH LONGGAR dari page_filter.UNIT_MARKERS (tanpa "dalam"):
# Docling memecah "(dalam jutaan Rupiah)" ke dua sel judul di 2 / 2 / 3 halaman Pilar 3 BCA. Di BCA
# versi longgar hanya menambah halaman itu, tanpa halaman campur. page_filter TIDAK diubah, karena
# aturannya menentukan halaman yang di-parse (dan cache-nya) di Minggu 3.
UNIT_PHRASES = {
    "million_idr": ["jutaan rupiah", "juta rupiah", "rp juta", "rp jutaan",
                    "millions of rupiah", "million rupiah"],
    "billion_idr": ["miliaran rupiah", "miliar rupiah", "rp miliar", "rp miliaran",
                    "billions of rupiah", "billion rupiah"],
    "thousand_usd": UNIT_MARKERS["thousand_usd"],    # belum diuji pada laporan sungguhan (R15)
}

MARKDOWN = MarkdownParams(image_mode=ImageRefMode.PLACEHOLDER, image_placeholder="",
                          escape_underscores=False, escape_html=False,
                          compact_tables=True)      # tanpa spasi pengisi kolom: -13% token gpt-oss

# Pita tepi atas & bawah halaman (fraksi tinggi) tempat navigasi dan footer dicetak. Di bbca_2023
# Docling melabeli pita navigasi sebagai ISI, bukan furniture: 356 item di pita 5%, semuanya
# navigasi, footer "Laporan Tahunan 2023 ... Tbk 275", atau nomor halaman (2024: 0; 2025: 1, catatan
# kaki unik). Lihat margin_furniture().
MARGIN_BAND = 0.05


# ----------------------------------------------------------------- pemotong (Langkah 3)

class SkippingSerializer(ChunkingDocSerializer):
    """Serializer chunking yang melewati item tertentu tanpa mengubah dokumen."""
    skip_refs: frozenset[str] = frozenset()

    def get_excluded_refs(self, **kwargs) -> set[str]:
        return super().get_excluded_refs(**kwargs) | self.skip_refs


class CompactMarkdownTables(ChunkingSerializerProvider):
    """Tabel sebagai Markdown ringkas (bukan triplet bawaan), dengan item `skip_refs` dilewati."""

    def __init__(self, skip_refs=frozenset()):
        self.skip_refs = frozenset(skip_refs)

    def get_serializer(self, doc: DoclingDocument) -> SkippingSerializer:
        return SkippingSerializer(doc=doc, table_serializer=MarkdownTableSerializer(),
                                  params=MARKDOWN, skip_refs=self.skip_refs)


@lru_cache(maxsize=1)
def tokenizer() -> HuggingFaceTokenizer:
    """Tokenizer BGE-M3 dengan batas CHUNK_MAX_TOKENS. Dari cache HF dulu, supaya tidak perlu
    internet; baru mengunduh kalau modelnya memang belum pernah diunduh."""
    from transformers import AutoTokenizer
    try:
        hf = AutoTokenizer.from_pretrained(config.EMBED_MODEL, local_files_only=True)
    except OSError:
        hf = AutoTokenizer.from_pretrained(config.EMBED_MODEL)
    return HuggingFaceTokenizer(tokenizer=hf, max_tokens=config.CHUNK_MAX_TOKENS)


def text_shape(text: str) -> str:
    """Teks dengan setiap deret angka diganti '#'. Dua teks yang hanya beda angka = teks yang sama
    untuk aturan boilerplate & navigasi (nomor halaman "Lampiran 5/97", "Lampiran 4/2", ...)."""
    return re.sub(r"\d+", "#", text.strip())


def item_pages(items, page_map: PageMap) -> list[int]:
    """Halaman ASLI dari semua prov semua item -- bukan prov[0] (ada blok lintas halaman)."""
    return sorted({page_map.to_original(p.page_no) for item in items for p in item.prov})


def skips_pages(page_map: PageMap, start: int, end: int) -> bool:
    """Ada halaman asli di antara `start` dan `end` yang dilewati penyaring (tidak di PDF potongan)?"""
    return any(page_map.to_subset(p) is None for p in range(start + 1, end))


def heading_context(doc: DoclingDocument, page_map: PageMap) -> dict[str, tuple[list[str] | None, int | None]]:
    """Per item: (judul yang berlaku, halaman asli judul terakhir). Judul mengikuti aturan
    HierarchicalChunker: judul level >= level judul baru hilang dari jangkauan."""
    by_level: dict[int, str] = {}
    page = None
    out = {}
    for item, _ in doc.iterate_items(with_groups=True, included_content_layers=MARKDOWN.layers):
        if isinstance(item, TitleItem | SectionHeaderItem):
            level = item.level if isinstance(item, SectionHeaderItem) else 0
            for k in [k for k in by_level if k >= level]:
                del by_level[k]
            by_level[level] = item.text
            page = page_map.to_original(item.prov[0].page_no) if item.prov else page
        else:
            out[item.self_ref] = ([by_level[k] for k in sorted(by_level)] or None, page)
    return out


def margin_furniture(doc: DoclingDocument) -> set[str]:
    """Teks ISI yang sebenarnya navigasi/footer halaman: seluruhnya di pita MARGIN_BAND teratas atau
    terbawah halamannya, DAN
      - berulang >= CHUNK_BOILERPLATE_REPEAT kali di pita itu (angka diabaikan, supaya nomor
        halaman ikut), ATAU
      - tercatat di >= 2 halaman (Docling menyambung footer halaman A dengan pita navigasi halaman
        B; paragraf sungguhan yang bersambung tidak pernah seluruhnya di pita tepi).
    Syarat itu menjaga catatan kaki unik di tepi bawah. Judul tidak disentuh (mengubah konteks
    judul). Dilewati per item, sama seperti tabel tanpa label baris; tanpanya 80 blok navigasi
    bbca_2023 yang melintasi dua halaman ikut menambah halaman ke chunk-nya."""
    def in_margin(prov) -> bool:
        height = doc.pages[prov.page_no].size.height
        box = prov.bbox.to_top_left_origin(height)
        return box.b / height <= MARGIN_BAND or box.t / height >= 1 - MARGIN_BAND

    groups = defaultdict(list)
    spanning = set()
    for item, _ in doc.iterate_items(included_content_layers=MARKDOWN.layers):
        if (isinstance(item, TextItem) and not isinstance(item, TitleItem | SectionHeaderItem)
                and item.prov and all(in_margin(p) for p in item.prov)):
            groups[text_shape(item.text)].append(item.self_ref)
            if len({p.page_no for p in item.prov}) > 1:
                spanning.add(item.self_ref)
    return spanning | {ref for refs in groups.values() if len(refs) >= config.CHUNK_BOILERPLATE_REPEAT
                       for ref in refs}


# Satu-satunya titik kait ke bagian dalam HybridChunker. Kalau versi docling-core baru mengganti
# namanya, gagal di sini -- jangan sampai pengaman judul di bawah diam-diam tidak berjalan.
assert hasattr(HybridChunker, "_merge_chunks_with_matching_metadata"), "docling-core berubah: cek GapAwareChunker"


class GapAwareChunker(HybridChunker):
    """HybridChunker yang tidak membawa judul melintasi halaman yang DILEWATI penyaring.

    PDF potongan menyambung halaman yang tidak bersebelahan (mis. hal 219 langsung hal 316
    `bbca_2025`), sehingga judul terakhir sebelum celah ikut menempel ke isi sesudah celah, dan
    penggabungan potongan kecil (merge_peers) menyatukan isi dua bagian laporan yang berbeda.
    Potongan yang judulnya berasal dari sebelum celah dilepas judulnya (None) SEBELUM
    penggabungan -- karena judulnya berbeda, ia juga tidak tergabung dengan isi sebelum celah."""

    page_map: PageMap | None = None
    context: dict = {}                  # heading_context(); kosong = tidak ada pengecekan
    stale_headings: int = 0             # jumlah potongan yang judulnya dilepas

    def _merge_chunks_with_matching_metadata(self, chunks):
        if self.page_map is not None:
            for chunk in chunks:
                items = chunk.meta.doc_items
                if not chunk.meta.headings or not items or not items[0].prov:
                    continue
                _, head_page = self.context.get(items[0].self_ref, (None, None))
                first = min(self.page_map.to_original(p.page_no) for it in items for p in it.prov)
                if head_page is not None and skips_pages(self.page_map, head_page, first):
                    chunk.meta.headings = None
                    self.stale_headings += 1
        return super()._merge_chunks_with_matching_metadata(chunks)


def make_chunker(skip_refs=frozenset(), page_map: PageMap | None = None, context=None) -> GapAwareChunker:
    return GapAwareChunker(tokenizer=tokenizer(),
                           serializer_provider=CompactMarkdownTables(skip_refs),
                           repeat_table_header=True,     # bawaannya True; ditulis supaya jelas
                           page_map=page_map, context=context or {})


def table_lines(serializer: ChunkingDocSerializer, table: TableItem) -> tuple[str, list[str | None]]:
    """(blok header + pemisah, baris Markdown untuk SETIAP baris grid).

    Serializer menggabungkan semua baris judul kolom menjadi SATU baris header Markdown
    ("Harga" + "Tertinggi" -> "Harga - Tertinggi"), lalu satu baris per baris grid sisanya. Jadi
    jumlah baris judul = baris grid - baris badan, dan baris judul dipetakan ke baris header."""
    header, body = serializer.table_serializer.get_header_and_body_lines(
        table_text=serializer.serialize(item=table).text)
    body = [line.rstrip("\n") for line in body if line.strip()]
    n_header = table.data.num_rows - len(body)
    if n_header < 0:
        raise ValueError(f"{table.self_ref}: {len(body)} baris Markdown > {table.data.num_rows} baris grid")
    header_line = header[0].rstrip("\n") if header else None
    return "".join(header), [header_line] * n_header + body


def split_tables(records: list[dict], doc: DoclingDocument, serializer: ChunkingDocSerializer) -> dict:
    """Tabel yang terbelah ke >= 2 chunk -> jumlah potongan dan potongan yang TIDAK memuat
    header kolomnya (harus 0; HybridChunker memecah tabel yang baris lebarnya tidak muat bersama
    header per KOLOM, dan potongan seperti itu kehilangan label baris -- 0 di laporan BCA)."""
    tables = {t.self_ref: t for t in doc.tables}
    pieces = defaultdict(list)
    for record in records:
        for ref in record["items"]:
            if ref in tables:
                pieces[ref].append(record)
    out = {}
    for ref, recs in pieces.items():
        if len(recs) > 1:
            head, _ = table_lines(serializer, tables[ref])
            out[ref] = {"pieces": len(recs), "without_header": sum(head not in r["text"] for r in recs)}
    return out


# ----------------------------------------------------------------- metadata (Langkah 4)

def page_units(doc: DoclingDocument, page_map: PageMap, report: FixReport) -> tuple[dict[int, str | None], dict]:
    """Satuan setiap halaman asli: million_idr / billion_idr / thousand_usd / None.
    Halaman dengan dua satuan berbeda -> None (dan dicatat). Lihat docstring modul."""
    texts = defaultdict(list)
    for item, _ in doc.iterate_items(included_content_layers=set(ContentLayer)):
        cells = [c.text for c in item.data.table_cells] if isinstance(item, TableItem) else [getattr(item, "text", "")]
        for prov in item.prov:
            texts[page_map.to_original(prov.page_no)].extend(cells)
    found = {}
    for subset_page in range(1, len(page_map) + 1):
        page = page_map.to_original(subset_page)
        text = normalize(" ".join(texts.get(page, [])))
        found[page] = sorted(u for u, phrases in UNIT_PHRASES.items() if any(p in text for p in phrases))

    # bagian kiri tabel dua halaman: penandanya tercetak di halaman kanan (tabel tanpa label)
    tables = {t.self_ref: t for t in doc.tables}
    inherited = {}
    for entry in report.unlabeled:
        for ref in entry["left_parts"]:
            page = page_map.to_original(tables[ref].prov[0].page_no)
            if not found[page] and found[entry["page"]]:
                inherited[page] = found[entry["page"]]
    found.update(inherited)

    mixed = {p: u for p, u in found.items() if len(u) > 1}
    units = {p: (u[0] if len(u) == 1 else None) for p, u in found.items()}
    summary = {"pages": len(units), "with_unit": sum(u is not None for u in units.values()),
               "by_unit": dict(Counter(u for u in units.values() if u)),
               "inherited_pages": sorted(inherited), "mixed_pages": mixed}
    return units, summary


def merged_lines(doc: DoclingDocument, serializer: ChunkingDocSerializer) -> dict[str, set[str]]:
    """Per tabel: baris Markdown yang masih berisi sel dua angka (Langkah 1c, `merged_rows`)."""
    out = {}
    for table in doc.tables:
        if rows := merged_rows(table):
            _, lines = table_lines(serializer, table)
            out[table.self_ref] = {lines[r] for r in rows} - {None}
    return out


def chunk_unit(pages: list[int], units: dict[int, str | None]) -> tuple[str | None, set[str]]:
    """Satuan chunk = satuan halaman-halamannya; halaman tanpa satuan tidak dihitung.
    Dua satuan berbeda -> None (dikembalikan juga himpunannya, untuk peringatan)."""
    found = {units[p] for p in pages} - {None}
    return (found.pop() if len(found) == 1 else None), found


# ----------------------------------------------------------------- satu laporan

@dataclass
class ChunkResult:
    chunks: list[dict]                  # siap diindeks (excluded = None)
    excluded: list[dict]                # record audit Langkah 2, TIDAK diindeks
    stats: dict = field(default_factory=dict)

    def records(self) -> list[dict]:
        """Semua record urut chunk_id (= urutan dokumen) -- isi .jsonl (Langkah 7)."""
        return sorted(self.chunks + self.excluded, key=lambda r: r["chunk_id"])


def chunk_document(doc: DoclingDocument, report: FixReport, page_map: PageMap, *,
                   ticker: str, sector: str, year: int, doc_id: str) -> ChunkResult:
    """Potong dokumen yang sudah diperbaiki (`load_fixed`) menjadi record (lihat docstring modul)."""
    context = heading_context(doc, page_map)
    furniture = margin_furniture(doc)
    chunker = make_chunker(report.unlabeled_refs() | furniture, page_map, context)
    start = time.perf_counter()
    raw = list(chunker.chunk(dl_doc=doc))
    seconds = time.perf_counter() - start

    repeats = Counter(text_shape(c.text) for c in raw)
    boilerplate = Counter(text_shape(c.text) for c in raw
                          if repeats[text_shape(c.text)] >= config.CHUNK_BOILERPLATE_REPEAT)
    serializer = CompactMarkdownTables().get_serializer(doc)       # tanpa item yang dilewati
    tables = {t.self_ref: t for t in doc.tables}

    # (posisi item pertama di dokumen, record) -- record excluded disisipkan di posisi tabelnya
    order = {item.self_ref: i for i, (item, _) in enumerate(
        doc.iterate_items(with_groups=True, included_content_layers=set(ContentLayer)))}
    placed = []
    for c in raw:
        if text_shape(c.text) in boilerplate:
            continue
        items = list(dict.fromkeys(it.self_ref for it in c.meta.doc_items))
        placed.append((order[items[0]], 0, {
            "text": chunker.contextualize(c), "pages": item_pages(c.meta.doc_items, page_map),
            "headings": c.meta.headings, "items": items, "excluded": None}))

    # record audit: Markdown tabelnya saja, didahului judul yang berlaku di posisinya (aturan celah
    # halaman sama dengan GapAwareChunker)
    for entry in report.unlabeled:
        table = tables[entry["table"]]
        headings, head_page = context.get(table.self_ref, (None, None))
        if head_page is not None and skips_pages(page_map, head_page, entry["page"]):
            headings = None
        placed.append((order[table.self_ref], 1, {
            "text": chunker.delim.join([*(headings or []), serializer.serialize(item=table).text]),
            "pages": item_pages([table], page_map), "headings": headings, "items": [table.self_ref],
            "excluded": EXCLUDED_UNLABELED}))
    placed.sort(key=lambda p: (p[0], p[1]))         # stabil: potongan satu tabel tetap berurutan

    units, unit_summary = page_units(doc, page_map, report)
    merged = merged_lines(doc, serializer)
    unit_conflicts = []
    records = []
    for n, (_, _, rec) in enumerate(placed, start=1):
        unit, found = chunk_unit(rec["pages"], units)
        lines = set(rec["text"].splitlines())
        rec.update(
            chunk_id=f"{ticker}_{year}_{n:04d}", doc_id=doc_id, ticker=ticker, sector=sector,
            year=year, page=rec["pages"][0], is_table=any(r in tables for r in rec["items"]),
            unit=unit,
            merged_cells=any(lines & merged.get(r, set()) for r in rec["items"]),
            n_tokens=tokenizer().count_tokens(rec["text"]))
        if len(found) > 1:
            unit_conflicts.append(f"{rec['chunk_id']} hal {rec['pages']}: {sorted(found)}")
        records.append({k: rec[k] for k in RECORD_FIELDS})

    chunks = [r for r in records if r["excluded"] is None]
    excluded = [r for r in records if r["excluded"] is not None]
    split = split_tables(chunks, doc, serializer)
    tokens = [c["n_tokens"] for c in chunks]
    stats = {
        "chunks_raw": len(raw),
        "boilerplate_dropped": sum(boilerplate.values()),
        "boilerplate_texts": [[text, n] for text, n in boilerplate.most_common()],
        "chunks": len(chunks),
        "excluded": len(excluded),
        "multi_page": sum(len(c["pages"]) > 1 for c in chunks),
        "tokens_median": statistics.median(tokens),
        "tokens_max": max(tokens),
        "split_tables": len(split),
        "split_pieces_without_header": sum(s["without_header"] for s in split.values()),
        "is_table": sum(c["is_table"] for c in chunks),
        "units": dict(Counter(str(c["unit"]) for c in chunks).most_common()),
        "page_units": unit_summary,
        "merged_cells": sum(c["merged_cells"] for c in chunks),
        "merged_lines": sum(len(v) for v in merged.values()),
        "stale_headings": chunker.stale_headings,
        "margin_furniture": len(furniture),
        "seconds_chunking": round(seconds, 1),
        "warnings": [],
    }
    if stats["split_pieces_without_header"]:
        stats["warnings"].append(
            f"{stats['split_pieces_without_header']} potongan tabel tanpa header kolom -- "
            f"repeat_table_header mati, atau tabel dipecah per KOLOM (satu baris + header > "
            f"{config.CHUNK_MAX_TOKENS} token) sehingga potongannya tanpa label baris. "
            f"Cek tabelnya: {[r for r, s in split.items() if s['without_header']]}")
    if unit_summary["mixed_pages"]:
        stats["warnings"].append(f"halaman dengan dua satuan (unit chunk-nya None): {unit_summary['mixed_pages']}")
    if unit_conflicts:
        stats["warnings"].append(f"chunk lintas halaman dengan satuan berbeda (unit None): {unit_conflicts}")
    return ChunkResult(chunks=chunks, excluded=excluded, stats=stats)


def chunk_report(year: int, ticker: str | None = None) -> ChunkResult:
    """Muat + perbaiki data/markdown/<kode>_<tahun>.json, lalu potong. Kode saham, sektor, dan tahun
    diambil dari .metadata.json (Minggu 3, Langkah 7), hash PDF dari .meta.json -- bukan ditulis tangan."""
    ticker = ticker or config.DEV_TICKER
    metadata_path = config.report_metadata(year, ticker)
    if not metadata_path.exists():
        raise FileNotFoundError(f"{metadata_path} belum ada -- jalankan dulu "
                                f"python -m src.ingest.detect_metadata {config.pdf(year, ticker)} --save")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    meta = json.loads(config.parse_meta(year, ticker).read_text(encoding="utf-8"))
    start = time.perf_counter()
    doc, report = load_fixed(year, ticker)
    fixing = time.perf_counter() - start
    result = chunk_document(doc, report, PageMap.from_list(meta["page_map"]),
                            ticker=metadata["ticker"], sector=metadata["sector"],
                            year=metadata["year"], doc_id=meta["sha256"])
    result.stats["seconds_fixing"] = round(fixing, 1)
    result.stats["fix"] = report.to_dict()            # Langkah 1: sel diperbaiki vs ditandai (Bab 4)
    return result


# ----------------------------------------------------------------- simpan + cache (Langkah 7)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_key(year: int, ticker: str) -> dict:
    """Semua yang menentukan isi .jsonl. Satu saja berbeda -> chunk dibuat ulang.
    Termasuk hash KODE aturannya (chunk.py, fix_tables.py, page_filter.py): perubahan aturan
    langsung membatalkan cache tanpa harus ingat menaikkan CHUNK_VERSION (15-11-2026: pola 3
    fix_tables mengubah isi tabel, padahal hash PDF dan .json tetap). CHUNK_VERSION tetap dinaikkan
    untuk perubahan yang perlu dicatat di record/Bab 4."""
    from src.ingest import fix_tables, page_filter
    code = hashlib.sha256()
    for module_file in (__file__, fix_tables.__file__, page_filter.__file__):
        code.update(Path(module_file).read_bytes())
    meta = json.loads(config.parse_meta(year, ticker).read_text(encoding="utf-8"))
    return {"doc_id": meta["sha256"],                                  # PDF
            "docling_json_sha256": _sha256(config.docling_json(year, ticker)),   # hasil parse
            "metadata_json_sha256": _sha256(config.report_metadata(year, ticker)),
            "chunk_version": config.CHUNK_VERSION,
            "code_sha256": code.hexdigest(),
            "docling_core": version("docling-core"),
            "embed_model": config.EMBED_MODEL,
            "max_tokens": config.CHUNK_MAX_TOKENS,
            "boilerplate_repeat": config.CHUNK_BOILERPLATE_REPEAT}


def build_chunks(year: int, ticker: str | None = None, force: bool = False) -> dict:
    """Potong + simpan ke data/chunks/<kode>_<tahun>.jsonl (satu record per baris, urut chunk_id),
    kecuali sudah ada dengan cache_key yang sama. Mengembalikan isi .chunks.meta.json.

    .chunks.meta.json ditulis PALING AKHIR: file itu ada = .jsonl selesai ditulis utuh."""
    ticker = ticker or config.DEV_TICKER
    jsonl, meta_path = config.chunks(year, ticker), config.chunks_meta(year, ticker)
    key = cache_key(year, ticker)
    if not force and jsonl.exists() and meta_path.exists():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if old.get("cache") == key:
            return {**old, "cached": True}

    start = time.perf_counter()
    result = chunk_report(year, ticker)
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    meta_path.unlink(missing_ok=True)                 # tanpa meta = belum selesai
    tmp = jsonl.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for record in result.records():
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(jsonl)
    meta = {"cache": key, "file": jsonl.name, "records": len(result.chunks) + len(result.excluded),
            "chunks": len(result.chunks), "excluded": len(result.excluded),
            "stats": result.stats, "seconds_total": round(time.perf_counter() - start, 1),
            "created": datetime.now().isoformat(timespec="seconds")}
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**meta, "cached": False}


def load_chunks(year: int, ticker: str | None = None, include_excluded: bool = False) -> list[dict]:
    """Record dari .jsonl. Bawaannya hanya yang DIINDEKS (excluded = None) -- yang dipakai Minggu 6."""
    ticker = ticker or config.DEV_TICKER
    if not config.chunks_meta(year, ticker).exists():
        raise FileNotFoundError(f"chunk {ticker}_{year} belum dibuat utuh -- jalankan "
                                f"python -m src.ingest.chunk {config.docling_json(year, ticker)}")
    with open(config.chunks(year, ticker), encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return records if include_excluded else [r for r in records if r["excluded"] is None]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    warnings.filterwarnings("ignore", message="Table cell bbox")   # bbox di luar halaman, di-clamp Docling
    from src.ingest.detect_metadata import parse_file_name

    ap = argparse.ArgumentParser(description="Potong hasil parse Docling menjadi chunk -> data/chunks/<kode>_<tahun>.jsonl")
    ap.add_argument("json", type=Path, nargs="+", help="data/markdown/<kode>_<tahun>.json")
    ap.add_argument("--force", action="store_true", help="buat ulang walaupun cache masih berlaku")
    ap.add_argument("--page", type=int, help="tampilkan isi record yang memuat halaman ASLI ini")
    args = ap.parse_args(argv)
    for path in args.json:
        ticker, year = parse_file_name(path)
        meta = build_chunks(year, ticker, force=args.force)
        s = meta["stats"]
        print(f"{path.name} -> {meta['file']}{'  (cache: tidak dipotong ulang)' if meta['cached'] else ''}")
        print(f"    {s['chunks_raw']} chunk, boilerplate dibuang {s['boilerplate_dropped']} "
              f"-> {s['chunks']} chunk diindeks; {s['excluded']} record excluded ({EXCLUDED_UNLABELED})")
        print(f"    lintas halaman {s['multi_page']}; token BGE-M3 median {s['tokens_median']:g}, "
              f"maks. {s['tokens_max']}; tabel terbelah {s['split_tables']} "
              f"(potongan tanpa header: {s['split_pieces_without_header']})")
        pu = s["page_units"]
        print(f"    chunk tabel {s['is_table']}; satuan chunk {s['units']}; halaman bersatuan "
              f"{pu['with_unit']}/{pu['pages']} (diwarisi dari halaman kanan: {len(pu['inherited_pages'])})")
        print(f"    merged_cells {s['merged_cells']} chunk ({s['merged_lines']} baris tabel bersel dua angka); "
              f"judul dilepas karena melintasi halaman yang dilewati penyaring: {s['stale_headings']} potongan")
        print(f"    navigasi/footer di tepi halaman yang terbaca sebagai isi, dilewati: {s['margin_furniture']} item")
        print(f"    waktu: perbaikan tabel {s['seconds_fixing']} s, pemotongan {s['seconds_chunking']} s, "
              f"total {meta['seconds_total']} s")
        for text, n in s["boilerplate_texts"]:
            print(f"    boilerplate {n:>4}x  {text[:90]!r}")
        for message in s["warnings"]:
            print(f"    PERINGATAN: {message}")
        if args.page:
            for record in load_chunks(year, ticker, include_excluded=True):
                if args.page in record["pages"]:
                    shown = {k: record[k] for k in RECORD_FIELDS if k not in ("text", "items", "doc_id")}
                    print(f"\n--- {shown}")
                    print(record["text"])


if __name__ == "__main__":
    main()
