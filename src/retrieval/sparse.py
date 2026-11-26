"""
Tugas 6.4 -- indeks sparse BM25, SATU per laporan.  docs/PANDUAN_MINGGU6.md, Langkah 3.

Kenapa satu per laporan (roadmap 6.4): rank_bm25 tidak bisa menambah dokumen tanpa membangun ulang
seluruh indeks, dan pencarian selalu difilter per emiten-tahun.

Koreksi roadmap 6.4: TANPA file .bm25.pkl. Indeks dibangun di memori dari .jsonl saat pertama
dipakai (0,11 detik untuk ketiga laporan BCA) lalu disimpan di cache proses. Alasannya:
  - tidak ada salinan kedua yang bisa basi setelah chunk dibuat ulang -- kunci cache = waktu ubah
    .jsonl, jadi chunk baru otomatis membangun indeks baru;
  - tidak ada pickle yang dimuat (memuat pickle = menjalankan kode, kalau filenya pernah diganti).

Isi indeks = chunk yang DIINDEKS (`load_chunks()`, excluded = None), urutan chunk_id -- sama
dengan yang masuk Chroma (Langkah 2). Teks yang diindeks = `text` (judul + isi).

Tokenizer: huruf kecil; angka UTUH beserta pemisahnya ("1.586.829", "29,14") dan kata [a-z]+.
Tanda baca, pipa tabel Markdown, dan "%" dibuang -- "29,14%" menjadi "29,14", supaya query
"29,14" / "29,14 persen" tetap cocok. Angka TIDAK dibuang (roadmap 6.4). Tanpa stopword: IDF BM25
sudah menurunkan bobot kata umum, dan membuang kata berisiko menghilangkan "tidak" dalam
"tidak memiliki eksposur".

Catatan untuk Minggu 7: skor BM25 dua laporan TIDAK bisa dibandingkan langsung (IDF-nya beda).
Pencarian tanpa `year` harus menggabungkan PERINGKAT (mis. RRF), bukan skor.

Cek:  python -m src.retrieval.sparse "rasio KPMM" --year 2024
"""

import argparse
import re
import sys
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from src import config

TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@lru_cache(maxsize=32)
def _build(ticker: str, year: int, version: int) -> tuple[BM25Okapi, tuple[str, ...]]:
    from src.ingest.chunk import load_chunks          # impor berat (docling-core) -- baru saat dipakai
    chunks = load_chunks(year, ticker)
    if not chunks:
        raise ValueError(f"{ticker}_{year}: tidak ada chunk yang diindeks")
    return BM25Okapi([tokenize(c["text"]) for c in chunks]), tuple(c["chunk_id"] for c in chunks)


def bm25_index(ticker: str, year: int) -> tuple[BM25Okapi, tuple[str, ...]]:
    """(indeks BM25, chunk_id per dokumen indeks). Dibangun ulang otomatis kalau .jsonl berubah."""
    return _build(ticker, year, config.chunks(year, ticker).stat().st_mtime_ns)


def search(query: str, ticker: str, year: int, k: int = config.TOP_K_SPARSE) -> list[tuple[str, float]]:
    """[(chunk_id, skor)] terbaik lebih dulu. Hanya skor > 0: query tanpa satu pun kata yang cocok
    mengembalikan daftar kosong, bukan k chunk acak."""
    bm25, ids = bm25_index(ticker, year)
    scores = bm25.get_scores(tokenize(query))
    order = np.argsort(-scores, kind="stable")[:k]
    return [(ids[i], float(scores[i])) for i in order if scores[i] > 0]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from src.ingest.chunk import load_chunks

    ap = argparse.ArgumentParser(description="Cari di indeks BM25 satu laporan.")
    ap.add_argument("query")
    ap.add_argument("--ticker", default=config.DEV_TICKER)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args(argv)
    print(f"token query: {tokenize(args.query)}")
    records = {c["chunk_id"]: c for c in load_chunks(args.year, args.ticker)}
    for rank, (chunk_id, score) in enumerate(search(args.query, args.ticker, args.year, args.k), start=1):
        c = records[chunk_id]
        print(f"{rank}. {chunk_id} hal {c['pages']} skor {score:.2f} -- {' > '.join(c['headings'] or [])[:70]}")


if __name__ == "__main__":
    main()
