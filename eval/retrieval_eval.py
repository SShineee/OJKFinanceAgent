"""
Tugas 7.5-7.6 -- eksperimen pembanding temu-kembali (Dense vs BM25 vs Hybrid RRF, dengan & tanpa
perluasan istilah).  docs/PANDUAN_MINGGU7.md, Langkah 4.

Mengukur Hit@1, Hit@5, dan MRR (@5) pada 15 query uji terkunci (eval/datasets/retrieval_queries.jsonl):
  - 6 konfigurasi: dense / bm25 / hybrid x tanpa / dengan perluasan istilah (Keputusan 7.A);
  - subkelompok query bersingkatan (7) vs tanpa singkatan (8) -- menguji hipotesis proposal;
  - sensitivitas k RRF (10 / 60 / 100, tugas 7.6) dan jumlah kandidat (5 / 10 / 20 / 30) --
    dicatat sebagai analisis, BUKAN dipakai untuk menyetel parameter pada set GATE;
  - latensi rata-rata & median `hybrid_retrieve` (model sudah dimuat);
  - tabel per query + halaman chunk relevan -> bahan Bab 4.

Output:
  results/retrieval_eval.json   ringkasan lengkap + rincian per query + sensitivitas
  results/retrieval_eval.csv    tabel per query untuk Bab 4

Bisa juga dijalankan ulang pada dataset bank uji (BMRI, Minggu 8) dengan `--dataset` dan `--out-prefix`.

Jalankan:  python -m eval.retrieval_eval
           python eval/retrieval_eval.py
"""

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval import retrieval_queries as rq
from src import config
from src.ingest.chunk import load_chunks
from src.retrieval import hybrid

LOCKED_DATASET_SHA256 = "cfab3a1830003cc868ef2c069a2d9364d8dad0d7ce232a6005a3e5ed07246fc2"
GATE3_THRESHOLD = 0.80
RRF_K_VALUES = (10, 60, 100)
CANDIDATE_K_VALUES = (5, 10, 20, 30)
LATENCY_ROUNDS = 3

CONFIGS = (
    ("dense", "Dense saja", "dense", False),
    ("bm25", "BM25 saja", "bm25", False),
    ("hybrid", "Hybrid RRF", "hybrid", False),
    ("dense_expanded", "Dense + perluasan", "dense", True),
    ("bm25_expanded", "BM25 + perluasan", "bm25", True),
    ("hybrid_expanded", "Hybrid RRF + perluasan", "hybrid", True),
)


def first_relevant_rank(chunk_ids: list[str], relevant: set[str], top: int = config.TOP_K_FINAL) -> int | None:
    """Peringkat (mulai 1) chunk relevan pertama di top-`top`, atau None kalau meleset."""
    for rank, chunk_id in enumerate(chunk_ids[:top], start=1):
        if chunk_id in relevant:
            return rank
    return None


def compute_metrics(ranks: list[int | None]) -> dict:
    n = len(ranks)
    if n == 0:
        return {"n": 0, "hit1_count": 0, "hit1": 0.0, "hit5_count": 0, "hit5": 0.0, "mrr": 0.0}
    hit1 = sum(r == 1 for r in ranks)
    hit5 = sum(r is not None and r <= 5 for r in ranks)
    mrr = sum(1.0 / r for r in ranks if r is not None) / n
    return {
        "n": n,
        "hit1_count": hit1,
        "hit1": round(hit1 / n, 4),
        "hit5_count": hit5,
        "hit5": round(hit5 / n, 4),
        "mrr": round(mrr, 4),
    }


def _retrieve_ids(mode: str, query: str, ticker: str, year: int, expand: bool,
                  top_k: int = config.TOP_K_FINAL, dense_k: int = config.TOP_K_DENSE,
                  sparse_k: int = config.TOP_K_SPARSE, rrf_k: int = config.RRF_K) -> list[str]:
    if mode == "dense":
        return [cid for cid, _ in hybrid.dense_search(query, ticker, year, k=max(top_k, dense_k), expand=expand)]
    if mode == "bm25":
        return [cid for cid, _ in hybrid.sparse_search(query, ticker, year, k=max(top_k, sparse_k), expand=expand)]
    if mode == "hybrid":
        return [c["chunk_id"] for c in hybrid.hybrid_retrieve(
            query, ticker, year, k=top_k, expand=expand, dense_k=dense_k, sparse_k=sparse_k, rrf_k=rrf_k)]
    raise ValueError(f"mode tidak dikenal: {mode}")


def _pages_lookup(queries: list[dict]) -> dict[str, list[int]]:
    pages: dict[str, list[int]] = {}
    for ticker, year in sorted({(q["ticker"], q["year"]) for q in queries}):
        for c in load_chunks(year, ticker):
            pages[c["chunk_id"]] = c["pages"]
    return pages


def _evaluate_configs(queries: list[dict], relevant_by_id: dict[str, set[str]],
                      pages: dict[str, list[int]], top_k: int) -> tuple[dict, list[dict]]:
    per_query = []
    for q in queries:
        rel = relevant_by_id[q["id"]]
        rel_pages = sorted({p for cid in rel for p in pages.get(cid, [])})
        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "ticker": q["ticker"],
            "year": q["year"],
            "abbreviation": bool(q["abbreviation"]),
            "relevant_count": len(rel),
            "relevant_pages": rel_pages,
            "ranks": {},
            "candidate_ranks": {},
            "top5_ids": {},
            "top5_pages": {},
        })

    summary = {}
    for key, label, mode, expand in CONFIGS:
        all_ranks, abbr_ranks, non_abbr_ranks = [], [], []
        for q, row in zip(queries, per_query):
            rel = relevant_by_id[q["id"]]
            ids = _retrieve_ids(mode, q["query"], q["ticker"], q["year"], expand=expand, top_k=top_k)
            rank_top = first_relevant_rank(ids, rel, top=top_k)
            rank_cand = first_relevant_rank(ids, rel, top=len(ids))
            row["ranks"][key] = rank_top
            if mode in ("dense", "bm25"):
                row["candidate_ranks"][key] = rank_cand
            row["top5_ids"][key] = ids[:top_k]
            row["top5_pages"][key] = [pages.get(cid, []) for cid in ids[:top_k]]
            all_ranks.append(rank_top)
            (abbr_ranks if q["abbreviation"] else non_abbr_ranks).append(rank_top)
        summary[key] = {
            "label": label,
            "mode": mode,
            "expand": expand,
            "all": compute_metrics(all_ranks),
            "abbreviation": compute_metrics(abbr_ranks),
            "non_abbreviation": compute_metrics(non_abbr_ranks),
        }
    return summary, per_query


def _measure_sensitivity(queries: list[dict], relevant_by_id: dict[str, set[str]], top_k: int) -> dict:
    rrf_k_results = {}
    for rrf_k in RRF_K_VALUES:
        ranks = [
            first_relevant_rank(
                _retrieve_ids("hybrid", q["query"], q["ticker"], q["year"], expand=True,
                              top_k=top_k, rrf_k=rrf_k),
                relevant_by_id[q["id"]],
                top=top_k,
            )
            for q in queries
        ]
        rrf_k_results[str(rrf_k)] = compute_metrics(ranks)

    cand_results = {}
    for cand in CANDIDATE_K_VALUES:
        ranks = [
            first_relevant_rank(
                _retrieve_ids("hybrid", q["query"], q["ticker"], q["year"], expand=True,
                              top_k=top_k, dense_k=cand, sparse_k=cand),
                relevant_by_id[q["id"]],
                top=top_k,
            )
            for q in queries
        ]
        cand_results[str(cand)] = compute_metrics(ranks)
    return {"rrf_k": rrf_k_results, "candidate_k": cand_results}


def _measure_latency(queries: list[dict], top_k: int, rounds: int = LATENCY_ROUNDS) -> dict:
    # Semua model BGE-M3 & indeks BM25 sudah termuat setelah evaluasi utama (kondisi warm).
    samples_ms = []
    for _ in range(rounds):
        for q in queries:
            t0 = time.perf_counter()
            hybrid.hybrid_retrieve(q["query"], q["ticker"], q["year"], k=top_k, expand=True)
            samples_ms.append((time.perf_counter() - t0) * 1000)
    return {
        "rounds": rounds,
        "queries_per_round": len(queries),
        "mean_ms": round(statistics.mean(samples_ms), 1),
        "median_ms": round(statistics.median(samples_ms), 1),
        "min_ms": round(min(samples_ms), 1),
        "max_ms": round(max(samples_ms), 1),
    }


def run_evaluation(dataset_path: Path = rq.DATASET, top_k: int = config.TOP_K_FINAL,
                   run_sensitivity: bool = True, measure_latency: bool = True) -> dict:
    """Jalankan eksperimen pembanding lengkap dan kembalikan dict laporan."""
    dataset_path = Path(dataset_path)
    queries = rq.load_queries(dataset_path)
    sha256 = rq.dataset_sha256(dataset_path)
    is_default = dataset_path.resolve() == rq.DATASET.resolve()
    verify_problems = rq.verify(queries) if is_default else []
    if is_default and verify_problems:
        raise RuntimeError(f"dataset uji tidak lolos verifikasi ground truth: {verify_problems}")

    relevant_by_id = {q["id"]: set(rq.relevant_chunk_ids(q)) for q in queries}
    pages = _pages_lookup(queries)

    # Pemanasan 1 panggilan agar model BGE-M3 & Chroma aktif sebelum pengukuran utama
    if queries:
        hybrid.hybrid_retrieve(queries[0]["query"], queries[0]["ticker"], queries[0]["year"], k=top_k, expand=True)

    configs, per_query = _evaluate_configs(queries, relevant_by_id, pages, top_k)
    sensitivity = _measure_sensitivity(queries, relevant_by_id, top_k) if run_sensitivity else {}
    latency = _measure_latency(queries, top_k) if measure_latency else {}

    sys_metrics = configs["hybrid_expanded"]["all"]
    gate3 = {
        "threshold": GATE3_THRESHOLD,
        "hit5_count": sys_metrics["hit5_count"],
        "total": sys_metrics["n"],
        "hit5": sys_metrics["hit5"],
        "passed": sys_metrics["hit5"] >= GATE3_THRESHOLD,
        "failed_queries": [r["id"] for r in per_query if r["ranks"]["hybrid_expanded"] is None],
    }

    return {
        "created": datetime.now().isoformat(timespec="seconds"),
        "dataset": {
            "path": str(dataset_path.relative_to(ROOT)) if dataset_path.is_relative_to(ROOT) else str(dataset_path),
            "sha256": sha256,
            "matches_locked_hash": (sha256 == LOCKED_DATASET_SHA256) if is_default else None,
            "queries": len(queries),
            "abbreviation_queries": sum(bool(q["abbreviation"]) for q in queries),
            "non_abbreviation_queries": sum(not q["abbreviation"] for q in queries),
        },
        "parameters": {
            "top_k_dense": config.TOP_K_DENSE,
            "top_k_sparse": config.TOP_K_SPARSE,
            "top_k_final": top_k,
            "rrf_k": config.RRF_K,
            "embed_model": config.EMBED_MODEL,
            "embed_dtype": config.EMBED_DTYPE,
        },
        "configs": configs,
        "sensitivity": sensitivity,
        "latency": latency,
        "gate3": gate3,
        "per_query": per_query,
    }


def save_results(report: dict, json_path: Path, csv_path: Path):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    fieldnames = [
        "id", "ticker", "year", "abbreviation", "query", "relevant_count", "relevant_pages",
        "dense_rank", "bm25_rank", "hybrid_rank",
        "dense_expanded_rank", "bm25_expanded_rank", "hybrid_expanded_rank",
        "dense_expanded_cand_rank", "bm25_expanded_cand_rank",
        "hybrid_expanded_hit5", "hybrid_expanded_top5_pages",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["per_query"]:
            r = row["ranks"]
            cr = row["candidate_ranks"]
            top_pages = "; ".join("/".join(map(str, ps)) for ps in row["top5_pages"]["hybrid_expanded"])
            writer.writerow({
                "id": row["id"],
                "ticker": row["ticker"],
                "year": row["year"],
                "abbreviation": row["abbreviation"],
                "query": row["query"],
                "relevant_count": row["relevant_count"],
                "relevant_pages": "; ".join(map(str, row["relevant_pages"])),
                "dense_rank": r["dense"] or "-",
                "bm25_rank": r["bm25"] or "-",
                "hybrid_rank": r["hybrid"] or "-",
                "dense_expanded_rank": r["dense_expanded"] or "-",
                "bm25_expanded_rank": r["bm25_expanded"] or "-",
                "hybrid_expanded_rank": r["hybrid_expanded"] or "-",
                "dense_expanded_cand_rank": cr.get("dense_expanded") or "-",
                "bm25_expanded_cand_rank": cr.get("bm25_expanded") or "-",
                "hybrid_expanded_hit5": r["hybrid_expanded"] is not None,
                "hybrid_expanded_top5_pages": top_pages,
            })


def _fmt_ratio(m: dict, key: str) -> str:
    return f"{m[key + '_count']}/{m['n']} ({m[key]:.0%})"


def print_report(report: dict):
    ds = report["dataset"]
    print(f"Dataset : {ds['path']} ({ds['queries']} query; singkatan {ds['abbreviation_queries']}, "
          f"biasa {ds['non_abbreviation_queries']})")
    lock_note = ""
    if ds["matches_locked_hash"] is True:
        lock_note = "  [cocok dengan hash terkunci]"
    elif ds["matches_locked_hash"] is False:
        lock_note = "  [PERINGATAN: BERBEDA DARI HASH TERKUNCI]"
    print(f"SHA-256 : {ds['sha256']}{lock_note}\n")

    print("== Perbandingan 6 konfigurasi (Hit@1, Hit@5, MRR@5) ==")
    print(f"  {'Konfigurasi':<26} {'Hit@1':>12} {'Hit@5':>12} {'MRR@5':>8}   "
          f"{'Singkatan (Hit@5)':>18} {'Biasa (Hit@5)':>15}")
    for key, *_ in CONFIGS:
        c = report["configs"][key]
        a, ab, nb = c["all"], c["abbreviation"], c["non_abbreviation"]
        print(f"  {c['label']:<26} {_fmt_ratio(a, 'hit1'):>12} {_fmt_ratio(a, 'hit5'):>12} "
              f"{a['mrr']:>8.3f}   {_fmt_ratio(ab, 'hit5'):>18} {_fmt_ratio(nb, 'hit5'):>15}")

    if report["sensitivity"]:
        print("\n== Sensitivitas parameter (Hybrid + perluasan; dicatat, bukan penyetelan) ==")
        rrf_str = " | ".join(
            f"k={k}: {m['hit5_count']}/{m['n']} (Hit@1 {m['hit1_count']}, MRR {m['mrr']:.3f})"
            for k, m in report["sensitivity"]["rrf_k"].items()
        )
        cand_str = " | ".join(
            f"cand={c}: {m['hit5_count']}/{m['n']} (MRR {m['mrr']:.3f})"
            for c, m in report["sensitivity"]["candidate_k"].items()
        )
        print(f"  RRF k    : {rrf_str}")
        print(f"  Kandidat : {cand_str}")

    print("\n== Peringkat chunk relevan pertama per query (top-5; '-' = tidak masuk top-5) ==")
    print(f"  {'ID':<4} {'Thn':<4} {'S'} {'Query':<48} {'D':>3} {'B':>3} {'H':>3} | "
          f"{'D+':>3} {'B+':>3} {'H+':>3}   Hal relevan")
    for row in report["per_query"]:
        r = row["ranks"]
        fmt = lambda v: str(v) if v is not None else "-"
        pages_str = ",".join(map(str, row["relevant_pages"][:6])) + ("…" if len(row["relevant_pages"]) > 6 else "")
        print(f"  {row['id']:<4} {row['year']:<4} {'S' if row['abbreviation'] else ' '} "
              f"{row['query'][:48]:<48} {fmt(r['dense']):>3} {fmt(r['bm25']):>3} {fmt(r['hybrid']):>3} | "
              f"{fmt(r['dense_expanded']):>3} {fmt(r['bm25_expanded']):>3} {fmt(r['hybrid_expanded']):>3}   {pages_str}")

    if report["latency"]:
        lat = report["latency"]
        print(f"\nLatensi hybrid_retrieve (warm, {lat['rounds']}x{lat['queries_per_round']} query): "
              f"rata-rata {lat['mean_ms']} ms, median {lat['median_ms']} ms "
              f"(min {lat['min_ms']}, maks {lat['max_ms']} ms)")

    g = report["gate3"]
    status = "LULUS" if g["passed"] else "BELUM LULUS"
    print(f"\nGATE 3 (Hit@5 hybrid + perluasan >= {g['threshold']:.0%}): "
          f"{g['hit5_count']}/{g['total']} ({g['hit5']:.1%}) -> {status}")
    if g["failed_queries"]:
        print(f"  Query meleset: {', '.join(g['failed_queries'])}")


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Eksperimen pembanding Dense / BM25 / Hybrid RRF (Minggu 7).")
    ap.add_argument("--dataset", type=Path, default=rq.DATASET, help="file dataset query .jsonl")
    ap.add_argument("--out-prefix", default="retrieval_eval",
                    help="nama dasar file output di results/ (bawaan: retrieval_eval)")
    ap.add_argument("--no-sensitivity", action="store_true", help="lewati uji sensitivitas k RRF & kandidat")
    args = ap.parse_args(argv)

    report = run_evaluation(args.dataset, run_sensitivity=not args.no_sensitivity)
    json_path = config.RESULTS / f"{args.out_prefix}.json"
    csv_path = config.RESULTS / f"{args.out_prefix}.csv"
    save_results(report, json_path, csv_path)
    print_report(report)
    print(f"\nTersimpan -> {json_path.relative_to(ROOT)} & {csv_path.relative_to(ROOT)}")
    sys.exit(0 if report["gate3"]["passed"] else 1)


if __name__ == "__main__":
    main()
