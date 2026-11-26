"""
Tugas 7 -- pemeriksaan pencarian hybrid + RRF.  docs/PANDUAN_MINGGU7.md, Langkah 5.

Jalankan:  python scripts/check_retrieval.py
           python scripts/check_retrieval.py --quick   (tanpa uji negatif lintas-tahun)

Pemeriksaan:
  A. RRF          cocok dengan contoh hitung tangan (2 daftar kecil), seri dipecah chunk_id,
                  duplikat dalam satu daftar tidak dihitung ganda, peringkat tidak valid ditolak.
  B. ticker wajib hybrid_retrieve / dense_search / sparse_search menolak "" / None / "xxxx" dengan
                  ValueError; huruf besar dinormalisasi.
  C. Filter tahun year=2023/2024/2025 hanya mengembalikan laporan tahun itu; year=None dikelompokkan
                  per tahun dengan k per tahun; daftar tahun diurutkan & dikelompokkan; tahun tak
                  terindeks ditolak.
  D. Perluasan    singkatan perbankan diperluas, query biasa & kata mirip ("Carrefour", "card") tidak
                  berubah, idempoten, dan expand=False mematikannya.
  E. Deterministik & skema: dua panggilan identik memberi urutan & skor sama; 13 field lengkap;
                  dense_rank & sparse_rank cocok dengan dense_search & sparse_search.
  F. GATE 3       dataset 15 query cocok dengan hash terkunci & ground truth, Hit@5 hybrid + perluasan
                  >= 80%, dan results/retrieval_eval.json + .csv konsisten.
  G. Uji negatif  pemeriksaan HARUS GAGAL kalau:
                    1. filter tahun dimatikan (pencarian lintas tahun);
                    2. RRF memakai skor mentah, bukan peringkat;
                    3. ticker boleh kosong.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from eval import retrieval_eval as reval
from eval import retrieval_queries as rq
from src import config
from src.retrieval import glossary, hybrid, index
from src.retrieval.embed import embed_query

EXPECTED_FIELDS = {
    "chunk_id", "text", "ticker", "sector", "year", "pages", "headings",
    "unit", "merged_cells", "is_table", "rrf_score", "dense_rank", "sparse_rank",
}


# ----------------------------------------------------------------- A. RRF

def check_rrf(fuse_fn=hybrid.rrf_fuse) -> list[str]:
    out = []
    # Contoh hitung tangan 2 daftar kecil:
    #   list1: b (#1), a (#2), c (#3)
    #   list2: a (#1), b (#2), d (#3)
    #   a = 1/62 + 1/61, b = 1/61 + 1/62 (seri -> 'a' dulu karena chunk_id), c = 1/63, d = 1/63 ('c' dulu)
    list1 = [("b", 1), ("a", 2), ("c", 3)]
    list2 = [("a", 1), ("b", 2), ("d", 3)]
    fused = fuse_fn([list1, list2], k=60, top=5)
    want_ids = ["a", "b", "c", "d"]
    if [cid for cid, _ in fused] != want_ids:
        out.append(f"[A] urutan RRF {fused}, seharusnya {want_ids}")
    else:
        want_ab = 1 / 61 + 1 / 62
        want_cd = 1 / 63
        if not (math.isclose(fused[0][1], want_ab, rel_tol=1e-12)
                and math.isclose(fused[1][1], want_ab, rel_tol=1e-12)
                and math.isclose(fused[2][1], want_cd, rel_tol=1e-12)
                and math.isclose(fused[3][1], want_cd, rel_tol=1e-12)):
            out.append(f"[A] nilai skor RRF tidak cocok hitung tangan: {fused}")

    # Invarian terhadap urutan daftar input (komutatif)
    rev = fuse_fn([list2, list1], k=60, top=5)
    if rev != fused:
        out.append(f"[A] RRF tidak komutatif terhadap urutan daftar: {rev} vs {fused}")

    # Duplikat di satu daftar & batas `top`
    dup = fuse_fn([[("x", 1), ("x", 2), ("y", 3)]], k=60, top=2)
    if len(dup) != 2 or dup[0][0] != "x" or not math.isclose(dup[0][1], 1 / 61, rel_tol=1e-12):
        out.append(f"[A] duplikat/top gagal: {dup}")

    # Daftar kosong
    if fuse_fn([], k=60, top=5) != [] or fuse_fn([[], []], k=60, top=5) != []:
        out.append("[A] daftar kosong tidak mengembalikan []")

    # Peringkat tidak valid harus ditolak
    for bad in (0, -1, True, 1.5):
        try:
            fuse_fn([[("x", bad)]], k=60, top=5)
            out.append(f"[A] peringkat tidak valid {bad!r} tidak ditolak")
        except ValueError:
            pass
    return out


# ----------------------------------------------------------------- B. ticker wajib

def check_ticker_required(retrieve_fn=hybrid.hybrid_retrieve, check_primitives: bool = True) -> list[str]:
    out = []
    targets = [("hybrid_retrieve", lambda t: retrieve_fn("Berapa CAR 2024?", ticker=t, year=2024))]
    if check_primitives:
        targets += [
            ("dense_search", lambda t: hybrid.dense_search("Berapa CAR 2024?", ticker=t, year=2024)),
            ("sparse_search", lambda t: hybrid.sparse_search("Berapa CAR 2024?", ticker=t, year=2024)),
        ]
    for name, call in targets:
        for bad in ("", "   ", None, "xxxx"):
            try:
                call(bad)
                out.append(f"[B] {name} menerima ticker={bad!r} (seharusnya ValueError)")
            except ValueError:
                pass
    if check_primitives:
        upper = retrieve_fn("Berapa CAR bank BCA tahun 2024?", ticker="BBCA", year=2024, k=3)
        if len(upper) != 3 or any(c["ticker"] != "bbca" for c in upper):
            out.append("[B] normalisasi huruf besar ticker='BBCA' gagal")
    return out


# ----------------------------------------------------------------- C. filter tahun

def check_year_filter(retrieve_fn=hybrid.hybrid_retrieve) -> list[str]:
    out = []
    for y in config.YEARS:
        res = retrieve_fn(f"Berapa laba bersih BCA tahun {y}?", ticker="bbca", year=y, k=5)
        if len(res) != 5:
            out.append(f"[C] year={y} mengembalikan {len(res)} chunk, seharusnya 5")
        wrong = [c["year"] for c in res if c["year"] != y or c["ticker"] != "bbca"]
        if wrong:
            out.append(f"[C] year={y} bocor ke tahun/emiten lain: {wrong}")

    # year=None -> dikelompokkan per tahun, k per tahun
    grouped = retrieve_fn("Bagaimana tren NPL BCA?", ticker="bbca", year=None, k=5)
    want_years = [y for y in sorted(config.YEARS) for _ in range(5)]
    if [c["year"] for c in grouped] != want_years:
        out.append(f"[C] year=None tidak dikelompokkan 5/tahun: {[c['year'] for c in grouped]}")

    # daftar tahun -> terurut & dikelompokkan
    subset = retrieve_fn("Bagaimana tren NPL BCA?", ticker="bbca", year=[2025, 2023], k=3)
    if [c["year"] for c in subset] != [2023] * 3 + [2025] * 3:
        out.append(f"[C] year=[2025, 2023] salah: {[c['year'] for c in subset]}")

    # tahun tidak valid ditolak
    for bad in (2020, [], True, "2024"):
        try:
            retrieve_fn("CAR", ticker="bbca", year=bad)
            out.append(f"[C] year={bad!r} diterima (seharusnya ValueError)")
        except ValueError:
            pass
    return out


# ----------------------------------------------------------------- D. perluasan istilah

def check_expansion() -> list[str]:
    out = []
    for abbr, fragment in (
        ("CKPN", "cadangan kerugian penurunan nilai"),
        ("DPK", "simpanan dari nasabah"),
        ("CAR", "kewajiban penyediaan modal minimum"),
        ("KPMM", "capital adequacy ratio"),
        ("NPL", "kredit bermasalah"),
        ("LDR", "loan to deposit ratio"),
        ("ROE", "return on equity"),
    ):
        q = f"Berapa {abbr} BCA 2024?"
        exp = glossary.expand_query(q)
        if fragment not in exp.lower():
            out.append(f"[D] {abbr} tidak diperluas dengan '{fragment}': {exp!r}")
        if glossary.expand_query(exp) != exp:
            out.append(f"[D] expand_query tidak idempoten untuk {abbr}")

    for plain in ("Berapa total aset BCA 2025?", "Carrefour card scar", "Modal Inti Tier 1"):
        if glossary.expand_query(plain) != plain:
            out.append(f"[D] query biasa berubah: {plain!r} -> {glossary.expand_query(plain)!r}")

    # expand=False mematikan perluasan (terbukti mengubah hasil CKPN 2023)
    q = "Berapa CKPN kredit yang diberikan BCA tahun 2023?"
    a = [c["chunk_id"] for c in hybrid.hybrid_retrieve(q, ticker="bbca", year=2023, expand=False)]
    b = [c["chunk_id"] for c in hybrid.hybrid_retrieve(q, ticker="bbca", year=2023, expand=True)]
    if a == b:
        out.append("[D] expand=False menghasilkan urutan identik dengan expand=True pada query CKPN")
    return out


# ----------------------------------------------------------------- E. deterministik & skema

def check_determinism_and_schema() -> list[str]:
    out = []
    sample = rq.load_queries()[:5]
    for q in sample:
        r1 = hybrid.hybrid_retrieve(q["query"], ticker=q["ticker"], year=q["year"], k=5, expand=True)
        r2 = hybrid.hybrid_retrieve(q["query"], ticker=q["ticker"], year=q["year"], k=5, expand=True)
        sig = lambda rs: [(c["chunk_id"], c["rrf_score"], c["dense_rank"], c["sparse_rank"]) for c in rs]
        if sig(r1) != sig(r2):
            out.append(f"[E] tidak deterministik pada {q['id']}: {sig(r1)} vs {sig(r2)}")
        d_map = dict(hybrid.dense_search(q["query"], q["ticker"], q["year"], expand=True))
        s_map = dict(hybrid.sparse_search(q["query"], q["ticker"], q["year"], expand=True))
        for c in r1:
            if set(c.keys()) != EXPECTED_FIELDS:
                out.append(f"[E] field chunk tidak sesuai pada {q['id']}: {sorted(c.keys())}")
                break
            if c["dense_rank"] != d_map.get(c["chunk_id"]) or c["sparse_rank"] != s_map.get(c["chunk_id"]):
                out.append(f"[E] dense_rank/sparse_rank tidak cocok pada {q['id']} {c['chunk_id']}")
                break
    return out


# ----------------------------------------------------------------- F. GATE 3

def check_gate3() -> tuple[list[str], dict]:
    out = []
    report = reval.run_evaluation(run_sensitivity=False, measure_latency=False)
    ds = report["dataset"]
    if not ds["matches_locked_hash"]:
        out.append(f"[F] SHA-256 dataset berubah: {ds['sha256']} != {reval.LOCKED_DATASET_SHA256}")
    g = report["gate3"]
    if not g["passed"]:
        out.append(f"[F] GATE 3 GAGAL: Hit@5 hybrid + perluasan {g['hit5_count']}/{g['total']} "
                   f"({g['hit5']:.1%}) < {g['threshold']:.0%}")

    # Pastikan hasil tersimpan di results/ sudah dibuat dan sinkron
    json_path = config.RESULTS / "retrieval_eval.json"
    csv_path = config.RESULTS / "retrieval_eval.csv"
    if not json_path.exists() or not csv_path.exists():
        out.append("[F] results/retrieval_eval.json atau .csv belum ada -- jalankan python -m eval.retrieval_eval")
    else:
        saved = json.loads(json_path.read_text(encoding="utf-8"))
        if saved.get("dataset", {}).get("sha256") != ds["sha256"]:
            out.append("[F] results/retrieval_eval.json memakai hash dataset berbeda")
        for key, cfg in report["configs"].items():
            if saved.get("configs", {}).get(key, {}).get("all") != cfg["all"]:
                out.append(f"[F] results/retrieval_eval.json tidak sinkron pada konfigurasi '{key}'")
                break
    return out, report


# ----------------------------------------------------------------- G. uji negatif

def check_negative() -> list[str]:
    """Ketiga mutasi HARUS membuat pemeriksaan yang bersangkutan GAGAL."""
    out = []

    # 1. Filter tahun dimatikan (pencarian lintas tahun di Chroma)
    def leaky_year_retrieve(query, ticker, year=None, k=5, expand=True):
        col = index.collection()
        text = glossary.expand_query(query) if expand else query
        res = col.query(query_embeddings=[embed_query(text).tolist()], n_results=k,
                        where={"ticker": ticker.lower()}, include=["metadatas"])
        return [{"chunk_id": cid, "ticker": m["ticker"], "year": m["year"]}
                for cid, m in zip(res["ids"][0], res["metadatas"][0])]

    # Cek pada pemeriksa filter tahun + ukur berapa dari 75 chunk (15 query x 5) meleset tahun
    leaked_problems = check_year_filter(retrieve_fn=leaky_year_retrieve)
    queries = rq.load_queries()
    wrong_year_chunks = sum(
        c["year"] != q["year"]
        for q in queries
        for c in leaky_year_retrieve(q["query"], q["ticker"], q["year"], k=5, expand=True)
    )
    ok1 = bool(leaked_problems) and wrong_year_chunks > 0
    print(f"  {'OK   ' if ok1 else 'GAGAL'} negatif 1: filter tahun dimatikan -> tertangkap "
          f"({wrong_year_chunks}/{len(queries) * 5} chunk top-5 dari tahun salah)")
    if not ok1:
        out.append("[G] filter tahun dimatikan tidak terdeteksi")

    # 2. RRF memakai skor mentah (bukan peringkat)
    # Dokumen 'a' peringkat 1 di dense (cosine 0.85) & peringkat 1 di BM25 (skor 12.0) -> RRF harus #1.
    # Dokumen 'b' tidak ada di dense & peringkat 2 di BM25 tapi skor mentah raksasa (25.0) -> skor mentah
    # salah menempatkan 'b' di atas 'a'.
    def raw_score_fuse(lists, k=60, top=5):
        scores = {}
        for ranked in lists:
            for cid, score_or_rank in ranked:
                scores[cid] = scores.get(cid, 0.0) + float(score_or_rank)
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:top]

    raw_problems = check_rrf(fuse_fn=raw_score_fuse)
    # Juga cek skenario skala berbeda langsung (dense ~0.85 vs BM25 ~25.0)
    raw_vs_rank = raw_score_fuse([[("a", 0.85)], [("b", 25.0), ("a", 12.0)]], top=2)
    rank_correct = hybrid.rrf_fuse([[("a", 1)], [("b", 1), ("a", 2)]], k=60, top=2)
    ok2 = bool(raw_problems) and raw_vs_rank[0][0] == "b" and rank_correct[0][0] == "a"
    print(f"  {'OK   ' if ok2 else 'GAGAL'} negatif 2: RRF memakai skor mentah -> tertangkap "
          f"(skor mentah pilih '{raw_vs_rank[0][0]}', RRF peringkat pilih '{rank_correct[0][0]}')")
    if not ok2:
        out.append("[G] RRF berbasis skor mentah tidak terdeteksi")

    # 3. ticker boleh kosong (tanpa pagar ticker)
    def no_ticker_guard(query, ticker="", year=None, k=5, expand=True):
        return [{"chunk_id": "dummy", "ticker": "bbca", "year": year or 2024}]

    guard_problems = check_ticker_required(retrieve_fn=no_ticker_guard, check_primitives=False)
    ok3 = bool(guard_problems)
    print(f"  {'OK   ' if ok3 else 'GAGAL'} negatif 3: ticker boleh kosong -> tertangkap "
          f"({len(guard_problems)} pelanggaran)")
    if not ok3:
        out.append("[G] ketiadaan pagar ticker tidak terdeteksi")

    return out


# ----------------------------------------------------------------- main

def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Pemeriksaan hybrid retrieval + RRF (Langkah 5 Minggu 7).")
    ap.add_argument("--quick", action="store_true", help="lewati uji negatif")
    args = ap.parse_args(argv)
    start = time.perf_counter()

    failures = []
    checks = [
        ("A. RRF (hitung tangan, seri, validasi)", check_rrf),
        ("B. ticker wajib (hybrid, dense, sparse)", check_ticker_required),
        ("C. filter tahun & year=None per tahun", check_year_filter),
        ("D. perluasan istilah & expand=False", check_expansion),
        ("E. deterministik & skema output", check_determinism_and_schema),
    ]
    print("== Pemeriksaan src/retrieval/hybrid.py ==")
    for name, fn in checks:
        problems = fn()
        print(f"  {'OK   ' if not problems else 'GAGAL'} {name}"
              + (f": {len(problems)} masalah" if problems else ""))
        for p in problems[:5]:
            print(f"         {p}")
        failures += problems

    gate_problems, report = check_gate3()
    g = report["gate3"]
    print(f"  {'OK   ' if not gate_problems else 'GAGAL'} F. GATE 3: Hit@5 hybrid + perluasan "
          f"{g['hit5_count']}/{g['total']} ({g['hit5']:.1%}, ambang {g['threshold']:.0%})")
    for p in gate_problems[:5]:
        print(f"         {p}")
    failures += gate_problems

    if not args.quick:
        print("\n== G. Uji negatif (harus GAGAL kalau aturannya dilanggar) ==")
        failures += check_negative()

    print(f"\nSelesai dalam {time.perf_counter() - start:.1f} s")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
