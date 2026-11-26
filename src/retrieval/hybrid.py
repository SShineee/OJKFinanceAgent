"""
Tugas 7.1-7.4, 7.7 -- pencarian hybrid (dense + BM25 + RRF).  docs/PANDUAN_MINGGU7.md, Langkah 3.

API tunggal untuk semua agen mulai Minggu 9:

    hybrid_retrieve("Berapa CAR bank BCA tahun 2024?", ticker="bbca", year=2024)

Alur untuk satu laporan (<ticker>, <year>):
  1. validasi `ticker` WAJIB ada dan terdaftar di pustaka (`index.indexed()`) -- pagar utama
     terhadap kontaminasi antar emiten (7.7, diuji lintas bank di Minggu 8.0d);
  2. perluas query dengan istilah perbankan baku (`glossary.expand_query`, Keputusan 7.A) kalau
     `expand=True` -- dipakai bersama oleh dense dan BM25;
  3. ambil top-K kandidat dari ChromaDB (`dense_search`, filter ticker + year) dan dari BM25
     laporan itu (`sparse_search`);
  4. gabungkan PERINGKAT (bukan skor mentah, karena skala cosine dan BM25 berbeda) dengan
     Reciprocal Rank Fusion (`rrf_fuse`): score(d) = sum 1 / (RRF_K + rank_i(d)), seri dipecah
     oleh `chunk_id` supaya selalu deterministik;
  5. ambil chunk lengkap beserta metadata (pages, headings, unit, merged_cells, is_table) +
     jejak peringkat dense & BM25.

Untuk pertanyaan tren (`year=None` atau daftar tahun), pencarian dijalankan PER TAHUN lalu
hasilnya dikelompokkan per tahun (k chunk per tahun). Jangan satu pencarian lintas tahun:
prototipe 15-11-2026 menunjukkan 45 dari 75 chunk top-5 meleset ke tahun lain, dan ada 102
pasang chunk berteks identik antar laporan BCA.

Cek:  python -m src.retrieval.hybrid "Berapa CAR bank BCA tahun 2024?" --ticker bbca --year 2024
      python -m src.retrieval.hybrid "Bagaimana tren NPL BCA?" --ticker bbca
"""

import argparse
import sys
from collections.abc import Iterable, Sequence

from src import config
from src.retrieval import index, sparse
from src.retrieval.embed import embed_query
from src.retrieval.glossary import expand_query, expansions


def _normalize_ticker(ticker: str) -> str:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker wajib diisi (mis. 'bbca'), tidak boleh kosong")
    return ticker.strip().lower()


def _indexed_years(ticker: str) -> tuple[str, list[int]]:
    """Validasi `ticker` wajib & ada di pustaka -> (ticker huruf kecil, daftar tahun urut naik)."""
    code = _normalize_ticker(ticker)
    available = index.indexed()
    years = sorted(y for t, y in available if t == code)
    if not years:
        known = sorted({t for t, _ in available})
        raise ValueError(f"kode saham '{code}' tidak ada di pustaka (tersedia: {known or 'kosong'})")
    return code, years


def _check_year_type(year) -> int:
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError(f"year harus bilangan bulat (mis. 2024), bukan {year!r}")
    return year


def _ensure_report(ticker: str, year: int) -> tuple[str, int]:
    """Pastikan (<ticker>, <year>) ada di pustaka tanpa memindai metadata seluruh koleksi."""
    code = _normalize_ticker(ticker)
    y = _check_year_type(year)
    hit = index.collection().get(where={"$and": [{"ticker": code}, {"year": y}]}, limit=1, include=[])
    if hit["ids"]:
        return code, y
    _, years = _indexed_years(code)                    # kalau kode saham tak ada -> ValueError ticker
    raise ValueError(f"laporan {code}_{y} tidak ada di pustaka (tahun tersedia untuk {code}: {years})")


def _resolve_target(ticker: str, year: int | Iterable[int] | None) -> tuple[str, list[int]]:
    """Validasi `ticker` + `year` -> (ticker huruf kecil, daftar tahun urut naik)."""
    if year is None:
        return _indexed_years(ticker)
    if isinstance(year, bool):
        raise ValueError("year harus bilangan bulat, daftar tahun, atau None -- bukan bool")
    if isinstance(year, int):
        code, y = _ensure_report(ticker, year)
        return code, [y]
    if isinstance(year, (str, bytes)):
        raise ValueError(f"year harus bilangan bulat atau daftar tahun, bukan teks {year!r}")
    requested = list(year)
    if not requested:
        raise ValueError("daftar tahun tidak boleh kosong")
    code, years = _indexed_years(ticker)
    available = set(years)
    resolved = []
    for y in requested:
        yy = _check_year_type(y)
        if yy not in available:
            raise ValueError(f"laporan {code}_{yy} tidak ada di pustaka (tahun tersedia untuk {code}: {years})")
        resolved.append(yy)
    return code, sorted(set(resolved))


def _query_dense(vector: list[float], ticker: str, year: int, k: int) -> list[tuple[str, int]]:
    if k <= 0:
        return []
    col = index.collection()
    total = col.count()
    if total <= 0:
        return []
    res = col.query(
        query_embeddings=[vector],
        n_results=min(k, total),
        where={"$and": [{"ticker": ticker}, {"year": year}]},
        include=["distances"],
    )
    ids = res["ids"][0] if res["ids"] else []
    distances = res["distances"][0] if res["distances"] else []
    # Pecah jarak seri secara deterministik berdasarkan chunk_id
    ordered = sorted(zip(ids, distances), key=lambda pair: (pair[1], pair[0]))
    return [(chunk_id, rank) for rank, (chunk_id, _) in enumerate(ordered, start=1)]


def dense_search(query: str, ticker: str, year: int, k: int = config.TOP_K_DENSE,
                 expand: bool = False) -> list[tuple[str, int]]:
    """[(chunk_id, peringkat)] dari ChromaDB, difilter ticker + year (peringkat mulai 1)."""
    code, y = _ensure_report(ticker, year)
    if k <= 0 or not query or not query.strip():
        return []
    text = expand_query(query) if expand else query
    return _query_dense(embed_query(text).tolist(), code, y, k)


def sparse_search(query: str, ticker: str, year: int, k: int = config.TOP_K_SPARSE,
                  expand: bool = False) -> list[tuple[str, int]]:
    """[(chunk_id, peringkat)] dari BM25 laporan <ticker>_<year> (peringkat mulai 1)."""
    code, y = _ensure_report(ticker, year)
    if k <= 0 or not query or not query.strip():
        return []
    text = expand_query(query) if expand else query
    hits = sparse.search(text, code, y, k=k)
    return [(chunk_id, rank) for rank, (chunk_id, _) in enumerate(hits, start=1)]


def rrf_fuse(lists: Sequence[Sequence[tuple[str, int]]], k: int = config.RRF_K,
             top: int | None = config.TOP_K_FINAL) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum 1 / (k + rank_i(d)).
    Urut skor menurun; seri dipecah oleh chunk_id (deterministik). Hanya memakai PERINGKAT."""
    if k < 0:
        raise ValueError(f"k RRF tidak boleh negatif: {k}")
    if top is not None and top <= 0:
        return []
    scores: dict[str, float] = {}
    for ranked in lists:
        seen: set[str] = set()
        for chunk_id, rank in ranked:
            if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
                raise ValueError(f"peringkat RRF harus bilangan bulat >= 1, bukan {rank!r}")
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:top] if top is not None else ordered


def _hydrate(fused: list[tuple[str, float]], dense_ranks: dict[str, int],
             sparse_ranks: dict[str, int]) -> list[dict]:
    """Lengkapi hasil RRF dengan teks & metadata chunk dari Chroma, menjaga urutan RRF."""
    if not fused:
        return []
    ids = [chunk_id for chunk_id, _ in fused]
    got = index.collection().get(ids=ids, include=["documents", "metadatas"])
    by_id = {cid: (doc, meta) for cid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"])}
    records = []
    for chunk_id, score in fused:
        doc, meta = by_id[chunk_id]
        records.append({
            "chunk_id": chunk_id,
            "text": doc,
            "ticker": meta["ticker"],
            "sector": meta["sector"],
            "year": meta["year"],
            "pages": list(meta["pages"]),
            "headings": meta.get("headings", ""),
            "unit": meta.get("unit"),
            "merged_cells": bool(meta["merged_cells"]),
            "is_table": bool(meta["is_table"]),
            "rrf_score": score,
            "dense_rank": dense_ranks.get(chunk_id),
            "sparse_rank": sparse_ranks.get(chunk_id),
        })
    return records


def hybrid_retrieve(query: str, ticker: str, year: int | Iterable[int] | None = None,
                    k: int = config.TOP_K_FINAL, expand: bool = True, *,
                    dense_k: int = config.TOP_K_DENSE, sparse_k: int = config.TOP_K_SPARSE,
                    rrf_k: int = config.RRF_K) -> list[dict]:
    """API tunggal pencarian hybrid untuk agen.

    `ticker` WAJIB ada di pustaka (gagal dengan ValueError kalau kosong atau tidak terdaftar).
    `year` = satu tahun (int), daftar tahun, atau None (semua tahun terindeks untuk `ticker`).
    Untuk banyak tahun, pencarian dijalankan PER TAHUN dan dikembalikan `k` chunk per tahun,
    dikelompokkan urut tahun.
    """
    code, target_years = _resolve_target(ticker, year)
    if k <= 0 or not query or not query.strip():
        return []

    search_text = expand_query(query) if expand else query
    # Embed query sekali saja walau mencari beberapa tahun sekaligus
    vector = embed_query(search_text).tolist() if dense_k > 0 else []

    results: list[dict] = []
    for y in target_years:
        dense_list = _query_dense(vector, code, y, dense_k) if dense_k > 0 else []
        sparse_hits = sparse.search(search_text, code, y, k=sparse_k) if sparse_k > 0 else []
        sparse_list = [(cid, rank) for rank, (cid, _) in enumerate(sparse_hits, start=1)]
        fused = rrf_fuse([dense_list, sparse_list], k=rrf_k, top=k)
        results.extend(_hydrate(fused, dict(dense_list), dict(sparse_list)))
    return results


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Pencarian hybrid (BGE-M3 + BM25 + RRF).")
    ap.add_argument("query")
    ap.add_argument("--ticker", required=True, help="kode saham wajib, mis. bbca")
    ap.add_argument("--year", type=int, nargs="*", help="satu atau beberapa tahun (kosong = semua tahun per tahun)")
    ap.add_argument("-k", type=int, default=config.TOP_K_FINAL, help="jumlah chunk per tahun")
    ap.add_argument("--no-expand", action="store_true", help="matikan perluasan istilah perbankan")
    args = ap.parse_args(argv)

    year_arg = None if not args.year else (args.year[0] if len(args.year) == 1 else args.year)
    expand = not args.no_expand
    added = expansions(args.query) if expand else []
    print(f"query  : {args.query}")
    if added:
        print(f"ekspansi: {'; '.join(added)}")
    try:
        chunks = hybrid_retrieve(args.query, ticker=args.ticker, year=year_arg, k=args.k, expand=expand)
    except ValueError as e:
        sys.exit(f"GAGAL: {e}")

    current_year = None
    rank = 0
    for c in chunks:
        if c["year"] != current_year:
            current_year = c["year"]
            rank = 0
            print(f"\n== {c['ticker']}_{current_year} ==")
        rank += 1
        d = f"d#{c['dense_rank']}" if c["dense_rank"] is not None else "d-"
        s = f"s#{c['sparse_rank']}" if c["sparse_rank"] is not None else "s-"
        flags = " [tabel]" if c["is_table"] else ""
        flags += " [merged]" if c["merged_cells"] else ""
        unit = c["unit"] or "-"
        head = c["headings"][:70] if c["headings"] else "(tanpa judul)"
        print(f"  {rank}. {c['chunk_id']} hal {c['pages']} ({unit}) rrf={c['rrf_score']:.5f} "
              f"({d}, {s}){flags} -- {head}")


if __name__ == "__main__":
    main()
