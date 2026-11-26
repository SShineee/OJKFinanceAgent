"""
Tugas 8.0d -- uji kontaminasi antar bank & verifikasi GATE 8.  docs/PANDUAN_MINGGU8.md, Langkah 5.

Jalankan:  python scripts/check_contamination.py

Membuktikan bahwa ketika dua bank (BBCA & BMRI) berada di SATU koleksi ChromaDB yang sama,
tidak ada satu pun chunk bank lain yang bocor ke hasil pencarian:

  A. Kelengkapan pustaka: index.indexed() memuat ke-6 laporan (bbca & bmri, 2023-2025),
     doc_id kedua bank saling lepas, dan jumlah serta daftar chunk BM25 == Chroma.
  B. 10 query generik (tanpa menyebut nama bank) x 2 bank = 20 panggilan hybrid_retrieve
     (+ dense_search & sparse_search): 0 chunk lintas-bank berdasarkan ticker, awalan
     chunk_id, dan doc_id; filter tahun tetap utuh termasuk year=None.
  C. Regresi BBCA: evaluasi GATE 3 pada BBCA tetap LULUS >= 80% setelah BMRI masuk ke
     koleksi ChromaDB yang sama.
  D. Uji negatif: query generik ke Chroma TANPA filter ticker (hanya where={"year": y})
     HARUS mencampur chunk BBCA dan BMRI, membuktikan pemeriksa kontaminasi efektif.

Hasil disimpan ke results/check_contamination.json (bahan Bab 4).
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from eval import retrieval_eval as reval
from src import config
from src.ingest.chunk import load_chunks
from src.retrieval import glossary, hybrid, index, sparse
from src.retrieval.embed import embed_query

TICKERS = ("bbca", "bmri")
YEARS = tuple(config.YEARS)

# 10 query generik: SENGAJA tidak menyebut nama atau kode bank apa pun, sehingga isolasi
# 100% bertumpu pada filter ticker. Mencakup single-year (2023-2025), singkatan, & year=None.
GENERIC_QUERIES = [
    ("c01", 2024, "Berapa modal inti tier 1 bank tahun 2024?"),
    ("c02", 2025, "Berapa rasio CAR atau KPMM bank tahun 2025?"),
    ("c03", 2023, "Berapa rasio NPL bruto dan kredit bermasalah tahun 2023?"),
    ("c04", 2024, "Berapa total laba bersih konsolidasian tahun 2024?"),
    ("c05", 2025, "Berapa dana pihak ketiga DPK simpanan nasabah tahun 2025?"),
    ("c06", 2023, "Berapa CKPN cadangan kerugian penurunan nilai kredit tahun 2023?"),
    ("c07", 2024, "Berapa rasio ROA, ROE, NIM, dan BOPO bank tahun 2024?"),
    ("c08", 2025, "Berapa total aset dan total ekuitas tahun 2025?"),
    ("c09", 2024, "Berapa rasio LDR kredit terhadap simpanan tahun 2024?"),
    ("c10", None, "Bagaimana tren laba bersih dan NPL selama 2023 sampai 2025?"),
]


def check_library() -> tuple[list[str], dict, dict[str, set[str]], dict[str, str]]:
    """A. Kelengkapan 6 laporan di Chroma + BM25 serta pemetaan chunk_id -> doc_id."""
    out = []
    col = index.collection()
    indexed = index.indexed()
    doc_ids_by_ticker: dict[str, set[str]] = {t: set() for t in TICKERS}
    chunk_doc_id: dict[str, str] = {}
    counts: dict[str, int] = {}

    for t in TICKERS:
        for y in YEARS:
            key = f"{t}_{y}"
            if (t, y) not in indexed:
                out.append(f"[A] {key} belum ada di koleksi Chroma")
                continue
            chunks = load_chunks(y, t)
            bm25, bm25_ids = sparse.bm25_index(t, y)
            chroma_ids = set(col.get(where={"$and": [{"ticker": t}, {"year": y}]}, include=[])["ids"])
            doc_id = chunks[0]["doc_id"]
            doc_ids_by_ticker[t].add(doc_id)
            for c in chunks:
                chunk_doc_id[c["chunk_id"]] = c["doc_id"]
            counts[key] = len(chunks)
            if indexed[(t, y)] != len(chunks) or bm25.corpus_size != len(chunks) or set(bm25_ids) != chroma_ids:
                out.append(f"[A] {key}: jumlah/isi Chroma ({indexed[(t, y)]}) != .jsonl ({len(chunks)}) "
                           f"!= BM25 ({bm25.corpus_size})")

    if doc_ids_by_ticker["bbca"] & doc_ids_by_ticker["bmri"]:
        out.append("[A] doc_id bbca dan bmri tumpang tindih")

    summary = {"chroma_total": col.count(), "reports": counts,
               "expected_reports": len(TICKERS) * len(YEARS), "found_reports": len(counts)}
    return out, summary, doc_ids_by_ticker, chunk_doc_id


def check_isolation(doc_ids_by_ticker: dict[str, set[str]],
                    chunk_doc_id: dict[str, str]) -> tuple[list[str], dict]:
    """B. 10 query generik x 2 bank = 20 panggilan hybrid_retrieve (+ dense & sparse)."""
    out = []
    details = []
    total_chunks = 0
    leaks = 0
    dense_leaks = 0
    sparse_leaks = 0

    for qid, year, query in GENERIC_QUERIES:
        per_bank_ids: dict[str, set[str]] = {}
        for ticker in TICKERS:
            res = hybrid.hybrid_retrieve(query, ticker=ticker, year=year, k=5, expand=True)
            want_n = 5 * len(YEARS) if year is None else 5
            if len(res) != want_n:
                out.append(f"[B] {qid} ({ticker}, year={year}): dapat {len(res)} chunk, seharusnya {want_n}")

            bad_ticker = [c["chunk_id"] for c in res if c["ticker"] != ticker]
            bad_prefix = [c["chunk_id"] for c in res if not c["chunk_id"].startswith(f"{ticker}_")]
            bad_doc = [c["chunk_id"] for c in res
                       if chunk_doc_id.get(c["chunk_id"]) not in doc_ids_by_ticker[ticker]]
            if year is None:
                want_years = [y for y in sorted(YEARS) for _ in range(5)]
                bad_year = [c["year"] for c in res] != want_years
            else:
                bad_year = any(c["year"] != year for c in res)

            q_leaks = len(set(bad_ticker) | set(bad_prefix) | set(bad_doc))
            leaks += q_leaks
            total_chunks += len(res)
            if q_leaks:
                out.append(f"[B] {qid} ({ticker}): kontaminasi {q_leaks} chunk "
                           f"(ticker={bad_ticker[:3]}, prefix={bad_prefix[:3]}, doc={bad_doc[:3]})")
            if bad_year:
                out.append(f"[B] {qid} ({ticker}, year={year}): urutan/filter tahun salah "
                           f"{[c['year'] for c in res]}")

            # Uji primitif dense_search & sparse_search secara terpisah
            probe_year = year if year is not None else 2024
            d_ids = [cid for cid, _ in hybrid.dense_search(query, ticker=ticker, year=probe_year, k=10)]
            s_ids = [cid for cid, _ in hybrid.sparse_search(query, ticker=ticker, year=probe_year, k=10)]
            d_bad = [cid for cid in d_ids if not cid.startswith(f"{ticker}_")
                     or chunk_doc_id.get(cid) not in doc_ids_by_ticker[ticker]]
            s_bad = [cid for cid in s_ids if not cid.startswith(f"{ticker}_")
                     or chunk_doc_id.get(cid) not in doc_ids_by_ticker[ticker]]
            dense_leaks += len(d_bad)
            sparse_leaks += len(s_bad)
            if d_bad:
                out.append(f"[B] {qid} ({ticker}) dense_search bocor: {d_bad[:3]}")
            if s_bad:
                out.append(f"[B] {qid} ({ticker}) sparse_search bocor: {s_bad[:3]}")

            per_bank_ids[ticker] = {c["chunk_id"] for c in res}
            details.append({
                "id": qid, "ticker": ticker, "year": year, "returned": len(res),
                "leaks": q_leaks, "top1_id": res[0]["chunk_id"] if res else None,
                "top1_pages": res[0]["pages"] if res else None,
            })

        overlap = per_bank_ids["bbca"] & per_bank_ids["bmri"]
        if overlap:
            out.append(f"[B] {qid}: chunk_id tumpang tindih antara bbca dan bmri: {sorted(overlap)[:3]}")

    summary = {
        "queries_per_bank": len(GENERIC_QUERIES),
        "total_calls": len(GENERIC_QUERIES) * len(TICKERS),
        "total_chunks_checked": total_chunks,
        "hybrid_leaks": leaks,
        "dense_leaks": dense_leaks,
        "sparse_leaks": sparse_leaks,
        "details": details,
    }
    return out, summary


def check_bbca_regression() -> tuple[list[str], dict]:
    """C. Regresi GATE 3 BBCA setelah BMRI masuk koleksi Chroma yang sama."""
    out = []
    report = reval.run_evaluation(run_sensitivity=False, measure_latency=False)
    ds = report["dataset"]
    g = report["gate3"]
    if not ds["matches_locked_hash"]:
        out.append(f"[C] hash dataset BBCA berubah: {ds['sha256']}")
    if not g["passed"]:
        out.append(f"[C] GATE 3 BBCA gagal setelah BMRI masuk: {g['hit5_count']}/{g['total']} ({g['hit5']:.1%})")
    summary = {
        "dataset_matches_locked_hash": ds["matches_locked_hash"],
        "hit5_count": g["hit5_count"],
        "total": g["total"],
        "hit5": g["hit5"],
        "mrr5": report["configs"]["hybrid_expanded"]["all"]["mrr"],
        "passed": g["passed"],
    }
    return out, summary


def check_negative_unfiltered() -> tuple[list[str], dict]:
    """D. Uji negatif: query Chroma TANPA filter ticker HARUS mencampur chunk BBCA & BMRI."""
    out = []
    col = index.collection()
    mixed_queries = 0
    total_counts: Counter = Counter()
    per_query = []

    for qid, year, query in GENERIC_QUERIES:
        probe_year = year if year is not None else 2024
        vec = embed_query(glossary.expand_query(query)).tolist()
        res = col.query(query_embeddings=[vec], n_results=10,
                        where={"year": probe_year}, include=["metadatas"])
        tickers = [m["ticker"] for m in res["metadatas"][0]]
        c = Counter(tickers)
        total_counts.update(c)
        is_mixed = len(c) >= 2
        mixed_queries += is_mixed
        per_query.append({"id": qid, "year": probe_year, "counts": dict(c), "mixed": is_mixed})

    # Tanpa filter ticker, kalau pencarian dipakai untuk BBCA maka chunk BMRI = bocor, dan sebaliknya.
    leaked_for_bbca = total_counts["bmri"]
    leaked_for_bmri = total_counts["bbca"]
    ok = mixed_queries > 0 and leaked_for_bbca > 0 and leaked_for_bmri > 0
    if not ok:
        out.append(f"[D] uji negatif tidak mencampur kedua bank: mixed={mixed_queries}/10, "
                   f"distribusi={dict(total_counts)}")
    summary = {
        "queries_tested": len(GENERIC_QUERIES),
        "top_k": 10,
        "mixed_queries": mixed_queries,
        "ticker_distribution": dict(total_counts),
        "leaked_if_querying_bbca": leaked_for_bbca,
        "leaked_if_querying_bmri": leaked_for_bmri,
        "detected": ok,
        "per_query": per_query,
    }
    return out, summary


def main() -> int:
    start = time.perf_counter()
    failures: list[str] = []

    print("== Uji kontaminasi antar bank (BBCA vs BMRI) -- GATE 8 ==")
    lib_fail, lib_sum, doc_ids, chunk_doc = check_library()
    print(f"  {'OK   ' if not lib_fail else 'GAGAL'} A. Kelengkapan pustaka: "
          f"{lib_sum['found_reports']}/{lib_sum['expected_reports']} laporan, "
          f"total {lib_sum['chroma_total']} chunk ({lib_sum['reports']})")
    for p in lib_fail[:5]:
        print(f"         {p}")
    failures += lib_fail

    if not lib_fail:
        iso_fail, iso_sum = check_isolation(doc_ids, chunk_doc)
        print(f"  {'OK   ' if not iso_fail else 'GAGAL'} B. Isolasi {iso_sum['total_calls']} panggilan "
              f"hybrid_retrieve ({iso_sum['total_chunks_checked']} chunk): "
              f"bocor hybrid={iso_sum['hybrid_leaks']}, dense={iso_sum['dense_leaks']}, "
              f"sparse={iso_sum['sparse_leaks']}")
        for p in iso_fail[:5]:
            print(f"         {p}")
        failures += iso_fail

        reg_fail, reg_sum = check_bbca_regression()
        print(f"  {'OK   ' if not reg_fail else 'GAGAL'} C. Regresi GATE 3 BBCA: "
              f"Hit@5 {reg_sum['hit5_count']}/{reg_sum['total']} ({reg_sum['hit5']:.1%}), "
              f"MRR@5 {reg_sum['mrr5']:.3f}")
        for p in reg_fail[:5]:
            print(f"         {p}")
        failures += reg_fail

        neg_fail, neg_sum = check_negative_unfiltered()
        print(f"  {'OK   ' if not neg_fail else 'GAGAL'} D. Uji negatif tanpa filter ticker: "
              f"{neg_sum['mixed_queries']}/{neg_sum['queries_tested']} query bercampur "
              f"(distribusi top-10: {neg_sum['ticker_distribution']})")
        for p in neg_fail[:5]:
            print(f"         {p}")
        failures += neg_fail
    else:
        iso_sum = reg_sum = neg_sum = {}

    summary = {
        "library": lib_sum,
        "isolation": iso_sum,
        "bbca_regression": reg_sum,
        "negative_unfiltered": neg_sum,
        "failures": failures,
        "passed": not failures,
        "seconds": round(time.perf_counter() - start, 1),
    }
    out = config.RESULTS / "check_contamination.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRingkasan -> {out.relative_to(ROOT)} ({summary['seconds']} s)")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
