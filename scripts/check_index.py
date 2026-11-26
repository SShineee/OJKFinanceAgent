"""
Tugas 6.6 -- uji indeks dense (ChromaDB) + sparse (BM25).  docs/PANDUAN_MINGGU6.md, Langkah 5.

Jalankan:  python scripts/check_index.py            (semua cek + uji negatif, +-1 menit)
           python scripts/check_index.py --quick    (tanpa uji negatif)

Yang diuji adalah HASIL TERSIMPAN -- folder chroma_db/ dan BM25 yang dibangun dari .jsonl --
dibandingkan dengan data/chunks/*.jsonl (hasil Minggu 5). Kode indexing tidak dipanggil ulang,
kecuali untuk cek idempoten.

A. Isi Chroma = chunk diindeks: per laporan 514 / 540 / 498, id sama dengan load_chunks(), 0 record
   excluded, `document` = `text`.
B. Metadata: `pages` list sama, `unit` ada <=> tidak None, ticker/sector/year = .metadata.json,
   `index_key` = kunci .jsonl SAAT INI (indeks tidak basi).
C. Vektor: dimensi 1.024, norma 1; temu-diri 250 chunk acak -> dirinya sendiri di peringkat 1, atau
   kembarannya yang berteks identik (102 pasang chunk identik antar laporan, jarak +-0).
D. Koleksi: jarak cosine, metadata embed_model = config.EMBED_MODEL.
E. Filter: ticker+year hanya mengembalikan laporan itu; {"pages": {"$contains": 703}} -> chunk
   KPMM 2024; index_document() kedua kali -> dilewati.
F. BM25: jumlah & urutan dokumen = chunk diindeks = isi Chroma; tokenizer mempertahankan angka
   ("1.586.829") dan membuang "%"; "rasio KPMM" 2024 -> hal 703 di peringkat 1.
G. Uji query roadmap 6.6: "laba bersih" 2024 -> kelima hasil dense DAN BM25 memuat "laba".
H. Uji negatif (folder Chroma SEMENTARA): pemeriksaan di atas HARUS gagal kalau koleksi memakai
   jarak L2, kalau record excluded ikut diindeks, atau kalau .jsonl berubah tanpa indeks ulang.
Pratinjau temu-kembali (DICATAT, bukan syarat lulus -- itu GATE 3 Minggu 7): 7 item Ikhtisar 2025
dengan tahun di query -> top-5 memuat angka jawabannya?

Hasil -> results/check_index.json (bahan Bab 4).
"""

import argparse
import json
import random
import shutil
import sys
import tempfile
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import chromadb
import numpy as np
from chromadb.config import Settings
from openpyxl import load_workbook

from src import config
from src.ingest.chunk import load_chunks
from src.retrieval import index, sparse
from src.retrieval.embed import embed_query, embed_texts

# Diukur 26-11-2026, aturan saringan versi 3 (8.0e)
EXPECTED = {2023: 541, 2024: 571, 2025: 519}
TICKER = config.DEV_TICKER
SELF_SAMPLES = 250
# baris xlsx (sheet 1_angka_mentah) -> nama item seperti pertanyaan pengguna; nilai 2025 dalam miliar
PREVIEW = {3: "total aset", 5: "total kredit", 6: "dana pihak ketiga", 7: "total ekuitas",
           8: "pendapatan bunga bersih", 9: "laba sebelum pajak", 10: "laba bersih"}


# ----------------------------------------------------------------- pemeriksaan (dipakai juga oleh uji negatif)

def expected_records(years) -> tuple[dict, set]:
    """(chunk diindeks per id, id record excluded) dari .jsonl."""
    indexed, excluded = {}, set()
    for y in years:
        for r in load_chunks(y, TICKER, include_excluded=True):
            if r["excluded"] is None:
                indexed[r["chunk_id"]] = r
            else:
                excluded.add(r["chunk_id"])
    return indexed, excluded


def check_contents(col, years) -> list[str]:
    """A + B: isi dan metadata koleksi untuk TICKER = chunk diindeks di .jsonl."""
    out = []
    want, excluded = expected_records(years)
    got = col.get(where={"ticker": TICKER}, include=["metadatas", "documents"])
    ids = got["ids"]
    if len(ids) != len(set(ids)):
        out.append(f"[A] id ganda di Chroma: {len(ids) - len(set(ids))}")
    if leaked := set(ids) & excluded:
        out.append(f"[A] record excluded ikut diindeks: {sorted(leaked)[:5]}")
    if missing := set(want) - set(ids):
        out.append(f"[A] chunk diindeks tidak ada di Chroma: {len(missing)}, mis. {sorted(missing)[:3]}")
    if extra := set(ids) - set(want) - excluded:
        out.append(f"[A] id di Chroma yang tidak ada di .jsonl: {sorted(extra)[:5]}")
    for y in years:
        n = sum(1 for m in got["metadatas"] if m["year"] == y)
        if n != EXPECTED[y]:
            out.append(f"[A] {TICKER}_{y}: {n} chunk di Chroma, seharusnya {EXPECTED[y]}")
    keys = {y: index.index_key(y, TICKER) for y in years}
    metadata = {y: json.loads(config.report_metadata(y, TICKER).read_text(encoding="utf-8")) for y in years}
    bad_doc, bad_meta, stale = [], [], []
    for i, doc, m in zip(ids, got["documents"], got["metadatas"]):
        r = want.get(i)
        if r is None:
            continue
        if doc != r["text"]:
            bad_doc.append(i)
        md = metadata[r["year"]]
        if (m["pages"] != r["pages"] or ("unit" in m) != (r["unit"] is not None) or m.get("unit") != r["unit"]
                or (m["ticker"], m["sector"], m["year"]) != (md["ticker"], md["sector"], md["year"])
                or m["doc_id"] != r["doc_id"] or m["page"] != r["page"]
                or m["headings"] != " > ".join(r["headings"] or [])
                or (m["is_table"], m["merged_cells"], m["n_tokens"]) != (r["is_table"], r["merged_cells"], r["n_tokens"])):
            bad_meta.append(i)
        if m.get("index_key") != keys[r["year"]]:
            stale.append(i)
    if bad_doc:
        out.append(f"[A] document != text .jsonl: {bad_doc[:3]}")
    if bad_meta:
        out.append(f"[B] metadata beda dengan .jsonl: {len(bad_meta)}, mis. {bad_meta[:3]}")
    if stale:
        out.append(f"[B] index_key basi (.jsonl berubah tanpa indeks ulang): {len(stale)} chunk")
    return out


def check_vectors(col, seed: int = 0) -> list[str]:
    """C: dimensi, norma, temu-diri (menerima kembaran berteks identik)."""
    out = []
    got = col.get(include=["embeddings", "documents"])
    ids, docs, E = got["ids"], got["documents"], np.asarray(got["embeddings"], dtype=np.float32)
    if E.shape[1] != config.EMBED_DIM:
        out.append(f"[C] dimensi {E.shape[1]}, seharusnya {config.EMBED_DIM}")
    norms = np.linalg.norm(E, axis=1)
    if not np.allclose(norms, 1, atol=1e-3):
        out.append(f"[C] norma vektor {norms.min():.4f}-{norms.max():.4f}, seharusnya 1")
    position = {i: k for k, i in enumerate(ids)}
    sample = random.Random(seed).sample(range(len(ids)), min(SELF_SAMPLES, len(ids)))
    res = col.query(query_embeddings=E[sample], n_results=1, include=["distances"])
    # BGE-M3 (SentencePiece) menyamakan spasi dan baris baru, jadi dua chunk yang hanya berbeda
    # pemisah baris menghasilkan vektor identik (jarak ~0, mis. bbca_2023_0223 vs bbca_2023_0226).
    same = lambda a, b: " ".join(a.split()) == " ".join(b.split())
    wrong = [ids[s] for r, d, s in zip(res["ids"], res["distances"], sample)
             if not (r[0] == ids[s] or (same(docs[position[r[0]]], docs[s]) and d[0] < 1e-4))]
    if wrong:
        out.append(f"[C] temu-diri gagal {len(wrong)}/{len(sample)}: {wrong[:3]}")
    return out


def check_collection(col) -> list[str]:
    """D: konfigurasi koleksi."""
    out = []
    space = (col.configuration or {}).get("hnsw", {}).get("space")
    if space != "cosine":
        out.append(f"[D] jarak koleksi '{space}', seharusnya cosine")
    if (col.metadata or {}).get("embed_model") != config.EMBED_MODEL:
        out.append(f"[D] embed_model koleksi {(col.metadata or {}).get('embed_model')}, seharusnya {config.EMBED_MODEL}")
    return out


def check_filters(col) -> list[str]:
    """E: filter ticker+year, filter halaman, idempoten."""
    out = []
    q = embed_query("rasio KPMM bank").tolist()
    for y in config.YEARS:
        res = col.query(query_embeddings=[q], n_results=10, include=["metadatas"],
                        where={"$and": [{"ticker": TICKER}, {"year": y}]})
        if any(m["year"] != y or m["ticker"] != TICKER for m in res["metadatas"][0]):
            out.append(f"[E] filter {TICKER}+{y} mengembalikan laporan lain")
    res = col.get(where={"$and": [{"ticker": TICKER}, {"year": 2024}, {"pages": {"$contains": 703}}]},
                  include=["documents", "metadatas"])
    if not res["ids"] or not any("Rasio KPMM" in d for d in res["documents"]):
        out.append("[E] filter {'pages': {'$contains': 703}} 2024 tidak mengembalikan chunk KPMM")
    before = col.count()
    if not all(index.index_document(y, TICKER)["skipped"] for y in config.YEARS) or col.count() != before:
        out.append("[E] index_document() kedua kali tidak dilewati, atau jumlah berubah")
    return out


def check_bm25(col) -> list[str]:
    """F: isi indeks BM25 dan tokenizer."""
    out = []
    for y in config.YEARS:
        bm25, ids = sparse.bm25_index(TICKER, y)
        chunks = load_chunks(y, TICKER)
        chroma_ids = set(col.get(where={"doc_id": chunks[0]["doc_id"]}, include=[])["ids"])
        if bm25.corpus_size != len(chunks) or list(ids) != [c["chunk_id"] for c in chunks] or set(ids) != chroma_ids:
            out.append(f"[F] BM25 {TICKER}_{y}: dokumen tidak sama dengan chunk diindeks / isi Chroma")
    for text, want in (("Rp1.586,8 triliun", ["rp", "1.586,8", "triliun"]), ("29,14%", ["29,14"]),
                       ("| Kas | 29.315.878 |", ["kas", "29.315.878"]), ("Non-Performing Loan", ["non", "performing", "loan"])):
        if sparse.tokenize(text) != want:
            out.append(f"[F] tokenize({text!r}) = {sparse.tokenize(text)}, seharusnya {want}")
    top = sparse.search("rasio KPMM", TICKER, 2024, 1)
    pages = load_chunks(2024, TICKER)
    page_of = {c["chunk_id"]: c["pages"] for c in pages}
    if not top or page_of[top[0][0]] != [703]:
        out.append(f"[F] 'rasio KPMM' 2024 peringkat 1 bukan hal 703: {top}")
    return out


def check_smoke(col) -> tuple[list[str], dict]:
    """G: uji query roadmap 6.6."""
    out = []
    q = "laba bersih"
    texts = {c["chunk_id"]: c for c in load_chunks(2024, TICKER)}
    res = col.query(query_embeddings=[embed_query(q).tolist()], n_results=5, include=["documents", "metadatas"],
                    where={"$and": [{"ticker": TICKER}, {"year": 2024}]})
    dense = [(i, m["pages"], "laba" in d.lower()) for i, d, m in zip(res["ids"][0], res["documents"][0], res["metadatas"][0])]
    bm = [(i, texts[i]["pages"], "laba" in texts[i]["text"].lower()) for i, _ in sparse.search(q, TICKER, 2024, 5)]
    if not all(ok for *_, ok in dense) or len(dense) != 5:
        out.append(f"[G] '{q}' dense: tidak semua top-5 memuat 'laba': {dense}")
    if not all(ok for *_, ok in bm) or len(bm) != 5:
        out.append(f"[G] '{q}' BM25: tidak semua top-5 memuat 'laba': {bm}")
    return out, {"query": q, "dense_pages": [p for _, p, _ in dense], "bm25_pages": [p for _, p, _ in bm]}


def preview(col) -> dict:
    """Pratinjau temu-kembali -- DICATAT, bukan syarat lulus."""
    ws = load_workbook(config.GROUND_TRUTH, data_only=True)["1_angka_mentah"]
    texts = {c["chunk_id"]: c["text"] for c in load_chunks(2025, TICKER)}
    rows, dense_hits, bm25_hits = [], 0, 0
    for row, item in PREVIEW.items():
        value = ws.cell(row=row, column=6).value                       # kolom 2025, miliar
        forms = [f"{round(value):,}".replace(",", "."),                 # 1.586.829 (miliar, tabel)
                 f"{value / 1000:,.1f}".replace(",", "#").replace(".", ",").replace("#", ".")]  # 1.586,8 (triliun)
        query = f"{item} tahun 2025"
        res = col.query(query_embeddings=[embed_query(query).tolist()], n_results=5, include=["documents"],
                        where={"$and": [{"ticker": TICKER}, {"year": 2025}]})
        d_ok = any(any(f in doc for f in forms) for doc in res["documents"][0])
        s_ok = any(any(f in texts[i] for f in forms) for i, _ in sparse.search(query, TICKER, 2025, 5))
        dense_hits += d_ok
        bm25_hits += s_ok
        rows.append({"query": query, "answer": forms, "dense": d_ok, "bm25": s_ok})
    return {"dense": f"{dense_hits}/{len(PREVIEW)}", "bm25": f"{bm25_hits}/{len(PREVIEW)}", "rows": rows}


# ----------------------------------------------------------------- uji negatif

def negative_tests(real_col) -> list[str]:
    """Koleksi SEMENTARA berisi data asli bbca_2025 yang sengaja dirusak -> pemeriksaan harus gagal."""
    out = []
    doc_id = load_chunks(2025, TICKER)[0]["doc_id"]
    data = real_col.get(where={"doc_id": doc_id}, include=["embeddings", "metadatas", "documents"])
    excluded = [r for r in load_chunks(2025, TICKER, include_excluded=True) if r["excluded"] is not None]
    tmp = tempfile.mkdtemp(prefix="check_index_")
    client = chromadb.PersistentClient(path=tmp, settings=Settings(anonymized_telemetry=False))

    def make(name, space="cosine", extra=None, key=None):
        col = client.create_collection(name, embedding_function=None, configuration={"hnsw": {"space": space}},
                                       metadata={"embed_model": config.EMBED_MODEL, "embed_dim": config.EMBED_DIM})
        metas = [dict(m, index_key=key) if key else m for m in data["metadatas"]]
        col.add(ids=data["ids"], embeddings=data["embeddings"], metadatas=metas, documents=data["documents"])
        if extra:
            r = extra
            col.add(ids=[r["chunk_id"]], embeddings=embed_texts([r["text"]]), documents=[r["text"]],
                    metadatas=[index.to_metadata(r, index.index_key(2025, TICKER))])
        return col

    try:
        cases = [
            ("koleksi utuh (kontrol, harus LOLOS)", make("kontrol"), True),
            ("jarak L2", make("jarak_l2", space="l2"), False),
            ("record excluded ikut diindeks", make("bocor", extra=excluded[0]), False),
            (".jsonl berubah tanpa indeks ulang (index_key basi)", make("basi", key="kunci-lama"), False),
        ]
        for name, col, should_pass in cases:
            problems = check_collection(col) + check_contents(col, [2025])
            ok = (not problems) if should_pass else bool(problems)
            print(f"  {'OK   ' if ok else 'GAGAL'} {name}: {'lolos' if not problems else problems[0][:90]}")
            if not ok:
                out.append(f"[H] {name}: {'tidak terdeteksi' if not should_pass else problems}")
    finally:
        del client
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# ----------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Uji indeks ChromaDB + BM25 (Langkah 5 Minggu 6).")
    ap.add_argument("--quick", action="store_true", help="tanpa uji negatif")
    args = ap.parse_args(argv)
    start = time.perf_counter()
    col = index.collection()
    summary = {"chroma_count": col.count(), "indexed": {f"{t}_{y}": n for (t, y), n in index.indexed().items()}}
    failures = []
    groups = [("A+B. isi & metadata", lambda: check_contents(col, config.YEARS)),
              ("C. vektor & temu-diri", lambda: check_vectors(col)),
              ("D. koleksi", lambda: check_collection(col)),
              ("E. filter & idempoten", lambda: check_filters(col)),
              ("F. BM25", lambda: check_bm25(col))]
    print(f"== Chroma: {summary['chroma_count']} chunk ({summary['indexed']})")
    for name, run in groups:
        problems = run()
        print(f"  {'OK   ' if not problems else 'GAGAL'} {name}" + (f": {len(problems)} masalah" if problems else ""))
        for p in problems[:5]:
            print(f"         {p}")
        failures += problems
    problems, smoke = check_smoke(col)
    print(f"  {'OK   ' if not problems else 'GAGAL'} G. uji query 'laba bersih' 2024 -- dense hal {smoke['dense_pages']}, "
          f"BM25 hal {smoke['bm25_pages']}")
    failures += problems
    summary["smoke"] = smoke

    if not args.quick:
        print("\n== H. uji negatif (folder Chroma sementara)")
        failures += negative_tests(col)

    print("\n== Pratinjau temu-kembali (dicatat, BUKAN syarat lulus -- GATE 3 Minggu 7)")
    summary["preview"] = preview(col)
    for r in summary["preview"]["rows"]:
        print(f"  {r['query']:<36} jawaban {r['answer'][0]:>10}: dense {'ada' if r['dense'] else '-  '}  "
              f"BM25 {'ada' if r['bm25'] else '-'}")
    print(f"  top-5 memuat angka jawaban: dense {summary['preview']['dense']}, BM25 {summary['preview']['bm25']}")

    size = sum(p.stat().st_size for p in config.CHROMA_DIR.rglob("*") if p.is_file()) / 2**20
    summary.update(failures=failures, passed=not failures, chroma_mb=round(size, 1),
                   seconds=round(time.perf_counter() - start, 1))
    out = config.RESULTS / "check_index.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nchroma_db {size:.1f} MB. Ringkasan -> {out.relative_to(ROOT)} ({summary['seconds']} s)")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
