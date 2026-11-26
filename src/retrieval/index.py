"""
Tugas 6.2-6.3 -- indeks dense: embedding BGE-M3 di ChromaDB.  docs/PANDUAN_MINGGU6.md, Langkah 2.

SATU koleksi (`config.CHROMA_COLLECTION`) untuk semua emiten dan tahun, dibedakan lewat metadata.
Pencarian Minggu 7 WAJIB memfilter `ticker` (+ `year`), supaya angka satu bank tidak terambil
untuk bank lain.

Yang masuk hanya chunk yang DIINDEKS (`load_chunks()`, excluded = None). Record tabel tanpa label
baris tetap hanya di .jsonl.

Temuan chromadb 1.5.9 (15-11-2026) yang menentukan rancangan:
  - nilai None di metadata DITOLAK (TypeError) -> kunci `unit` dihilangkan kalau None;
  - list DITERIMA dan bisa difilter: {"pages": {"$contains": 541}} -> `pages` tetap list;
  - `add` dengan id yang sudah ada DIABAIKAN DIAM-DIAM (isi lama tetap) -> "doc_id sudah ada,
    lewati" (roadmap 6.3) membuat indeks basi setelah chunk dibuat ulang. Karena itu setiap chunk
    membawa `index_key` = hash .jsonl + model + presisi. Kunci berbeda (atau jumlah chunk berbeda)
    -> semua chunk laporan itu dihapus (per doc_id) lalu ditambah ulang;
  - jarak bawaan L2 -> koleksi dibuat dengan cosine (embedding sudah bernorma 1);
  - telemetri aktif secara bawaan -> dimatikan;
  - tanpa `embedding_function=None` Chroma memakai (dan mengunduh) model ONNX bawaannya.

Embedding dihitung DULU, baru versi lama dihapus: kalau embed gagal (mis. CUDA out of memory),
indeks lama tetap utuh. Kalau proses mati di antara hapus dan tambah, jumlah chunk tidak cocok ->
laporan itu diindeks ulang pada jalan berikutnya.

Jalankan:  python -m src.retrieval.index                  (ketiga laporan BBCA, idempoten)
           python -m src.retrieval.index bbca_2024        (satu laporan)
           python -m src.retrieval.index bbca_2024 --force
Uji:       python scripts/check_index.py
"""

import argparse
import hashlib
import sys
import time
from collections import Counter
from functools import lru_cache

import chromadb
from chromadb.config import Settings

from src import config
from src.ingest.chunk import load_chunks

MISSING = "-"     # pengganti None di tampilan; TIDAK disimpan ke Chroma


@lru_cache(maxsize=1)
def client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(config.CHROMA_DIR),
                                     settings=Settings(anonymized_telemetry=False))


def collection():
    """Koleksi tunggal pustaka. Berhenti kalau koleksinya dibuat dengan model embedding lain."""
    col = client().get_or_create_collection(
        config.CHROMA_COLLECTION,
        embedding_function=None,                                   # embedding selalu dari BGE-M3
        configuration={"hnsw": {"space": config.CHROMA_SPACE}},    # cosine, bukan L2 bawaan
        metadata={"embed_model": config.EMBED_MODEL, "embed_dim": config.EMBED_DIM})
    meta = col.metadata or {}
    if (meta.get("embed_model"), meta.get("embed_dim")) != (config.EMBED_MODEL, config.EMBED_DIM):
        raise RuntimeError(f"koleksi '{config.CHROMA_COLLECTION}' dibuat dengan {meta.get('embed_model')} "
                           f"(dimensi {meta.get('embed_dim')}), sekarang {config.EMBED_MODEL} -- vektornya tidak "
                           f"bisa dibandingkan. Hapus folder {config.CHROMA_DIR} lalu index ulang.")
    return col


def index_key(year: int, ticker: str) -> str:
    """Berubah setiap .jsonl berubah (chunk dibuat ulang) atau model/presisi embedding berubah."""
    digest = hashlib.sha256()
    digest.update(config.chunks(year, ticker).read_bytes())
    digest.update(f"|{config.EMBED_MODEL}|{config.EMBED_DTYPE}|{config.EMBED_DIM}".encode())
    return digest.hexdigest()


def to_metadata(record: dict, key: str) -> dict:
    """Record .jsonl -> metadata Chroma. Tanpa None (ditolak Chroma); `items` & `excluded` tidak ikut."""
    meta = {"doc_id": record["doc_id"], "ticker": record["ticker"], "sector": record["sector"],
            "year": record["year"], "page": record["page"], "pages": record["pages"],
            "headings": " > ".join(record["headings"] or []), "is_table": record["is_table"],
            "merged_cells": record["merged_cells"], "n_tokens": record["n_tokens"], "index_key": key}
    if record["unit"] is not None:
        meta["unit"] = record["unit"]
    return meta


def index_document(year: int, ticker: str | None = None, force: bool = False) -> dict:
    """Masukkan chunk diindeks satu laporan ke Chroma. Idempoten: dilewati kalau semua chunk-nya
    sudah ada dengan index_key yang sama."""
    ticker = ticker or config.DEV_TICKER
    chunks = load_chunks(year, ticker)
    if not chunks:
        raise ValueError(f"{ticker}_{year}: tidak ada chunk yang diindeks")
    doc_id, key = chunks[0]["doc_id"], index_key(year, ticker)
    col = collection()
    stored = col.get(where={"doc_id": doc_id}, include=["metadatas"])
    result = {"ticker": ticker, "year": year, "doc_id": doc_id, "chunks": len(chunks),
              "replaced": len(stored["ids"])}
    if (not force and len(stored["ids"]) == len(chunks)
            and all(m.get("index_key") == key for m in stored["metadatas"])):
        return {**result, "skipped": True, "replaced": 0}

    from src.retrieval.embed import describe, embed_texts   # baru di sini: impor torch +-5 s, tak perlu kalau dilewati
    start = time.perf_counter()
    vectors = embed_texts([c["text"] for c in chunks])               # dulu: kalau gagal, indeks lama utuh
    embed_s = time.perf_counter() - start

    start = time.perf_counter()
    if stored["ids"]:
        col.delete(where={"doc_id": doc_id})
    size = client().get_max_batch_size()
    for i in range(0, len(chunks), size):
        part = chunks[i:i + size]
        col.add(ids=[c["chunk_id"] for c in part], embeddings=vectors[i:i + size],
                documents=[c["text"] for c in part], metadatas=[to_metadata(c, key) for c in part])
    add_s = time.perf_counter() - start
    return {**result, "skipped": False, "seconds_embed": round(embed_s, 1), "seconds_add": round(add_s, 1),
            "embedder": describe()}


def delete_document(doc_id: str) -> int:
    """Keluarkan satu laporan dari indeks dense. Mengembalikan jumlah chunk yang dihapus."""
    col = collection()
    n = len(col.get(where={"doc_id": doc_id}, include=[])["ids"])
    if n:
        col.delete(where={"doc_id": doc_id})
    return n


def indexed() -> dict[tuple[str, int], int]:
    """Isi pustaka dense: {(kode saham, tahun): jumlah chunk} -- bahan /pustaka (Minggu 16)."""
    metas = collection().get(include=["metadatas"])["metadatas"]
    return dict(sorted(Counter((m["ticker"], m["year"]) for m in metas).items()))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Masukkan chunk diindeks ke ChromaDB (idempoten).")
    ap.add_argument("reports", nargs="*", help="<kode>_<tahun>, mis. bbca_2024 (bawaan: semua tahun DEV_TICKER)")
    ap.add_argument("--force", action="store_true", help="index ulang walaupun index_key sama")
    args = ap.parse_args(argv)
    targets = ([(name.split("_")[0].lower(), int(name.split("_")[1])) for name in args.reports]
               or [(config.DEV_TICKER, y) for y in config.YEARS])
    for ticker, year in targets:
        r = index_document(year, ticker, force=args.force)
        if r["skipped"]:
            print(f"{ticker}_{year}: sudah terindeks ({r['chunks']} chunk, index_key sama) -- dilewati")
        else:
            print(f"{ticker}_{year}: {r['chunks']} chunk -> Chroma (embed {r['seconds_embed']} s, "
                  f"tambah {r['seconds_add']} s; versi lama dihapus: {r['replaced']} chunk)")
    total = indexed()
    print(f"isi koleksi '{config.CHROMA_COLLECTION}': "
          + ", ".join(f"{t}_{y} {n}" for (t, y), n in total.items()) + f" -- total {sum(total.values())} chunk")


if __name__ == "__main__":
    main()
