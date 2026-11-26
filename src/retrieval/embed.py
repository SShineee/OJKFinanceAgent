"""
Tugas 6.1 -- model embedding BGE-M3.  docs/PANDUAN_MINGGU6.md, Langkah 1.

Satu model per proses (`embedder()`), dipakai untuk chunk (indexing, Langkah 2) dan query
(Minggu 7). Chunk dan query di-embed dengan cara yang SAMA: BGE-M3 tidak butuh awalan instruksi di
query, berbeda dengan BGE v1.5 (bahasa Inggris).

Presisi (Keputusan 6.A, 15-11-2026): fp16 di GPU -- 54 s untuk 1.552 chunk vs 193 s fp32,
kosinus terhadap fp32 >= 0,9997. Di CPU otomatis fp32 (+-47 menit untuk 1.552 chunk -> indexing
butuh GPU; untuk query CPU cukup).

Model dimuat dari FOLDER SNAPSHOT LOKAL di cache Hugging Face, bukan dari nama repo. Dengan nama
repo, transformers menjalankan pengecekan "konversi safetensors" di latar belakang yang mengabaikan
local_files_only dan menghubungi huggingface.co setiap kali model dimuat (info model, daftar commit,
diskusi -- diukur 15-11-2026: 4-5 permintaan). Dari folder lokal: 0 permintaan, vektor identik.
Model baru diunduh (sekali) kalau memang belum ada di cache.

Keluaran: numpy float32, ternormalisasi (norma 1) -> cocok untuk jarak cosine di Chroma. Model fp16
mengeluarkan float16; diubah ke float32 dulu, baru dinormalisasi.

Cek:  python -m src.retrieval.embed
"""

import gc
import sys
import time
from functools import lru_cache

import numpy as np
import torch
from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError
from sentence_transformers import SentenceTransformer

from src import config


def _model_path() -> str:
    """Folder snapshot lokal model; unduh sekali kalau belum ada di cache."""
    try:
        return snapshot_download(config.EMBED_MODEL, local_files_only=True)
    except LocalEntryNotFoundError:
        SentenceTransformer(config.EMBED_MODEL, device="cpu")       # unduh ke cache (+-2,2 GB)
        return snapshot_download(config.EMBED_MODEL, local_files_only=True)


def device() -> str:
    return "cuda" if config.EMBED_DEVICE == "cuda" and torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def embedder() -> SentenceTransformer:
    """BGE-M3, dimuat sekali per proses."""
    on_gpu = device() == "cuda"
    kwargs = {"model_kwargs": {"dtype": getattr(torch, config.EMBED_DTYPE)}} if on_gpu else {}
    model = SentenceTransformer(_model_path(), device=device(), **kwargs)
    if model.get_embedding_dimension() != config.EMBED_DIM:
        raise RuntimeError(f"dimensi {config.EMBED_MODEL} = {model.get_embedding_dimension()}, "
                           f"config.EMBED_DIM = {config.EMBED_DIM}")
    return model


def embed_texts(texts: list[str]) -> np.ndarray:
    """(len(texts), EMBED_DIM) float32, setiap baris bernorma 1."""
    if not texts:
        return np.zeros((0, config.EMBED_DIM), dtype=np.float32)
    vectors = embedder().encode(texts, batch_size=config.EMBED_BATCH, convert_to_numpy=True,
                                show_progress_bar=False).astype(np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]


def describe() -> dict:
    """Keterangan model yang dimuat -- dicatat di koleksi Chroma (Langkah 2) dan Bab 4."""
    model = embedder()
    return {"model": config.EMBED_MODEL, "dim": model.get_embedding_dimension(), "device": device(),
            "dtype": str(next(model.parameters()).dtype).replace("torch.", ""),
            "max_seq_length": model.max_seq_length}


def release():
    """Lepas model dari GPU, mis. sebelum Docling mem-parse laporan baru (VRAM 6 GB). Hanya
    berpengaruh kalau tidak ada referensi lain ke model."""
    embedder.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from src.ingest.chunk import load_chunks

    start = time.perf_counter()
    info = describe()
    print(f"{info['model']}: dimensi {info['dim']}, {info['device']} {info['dtype']}, "
          f"max_seq_length {info['max_seq_length']} -- dimuat {time.perf_counter() - start:.1f} s")
    if info["device"] == "cuda":
        print(f"  VRAM terpakai model: {torch.cuda.memory_allocated() / 2**20:.0f} MiB")

    query = embed_query("rasio KPMM bank 2024")
    print(f"  query: bentuk {query.shape}, {query.dtype}, norma {np.linalg.norm(query):.6f}")

    chunks = load_chunks(2024)[:64]
    start = time.perf_counter()
    vectors = embed_texts([c["text"] for c in chunks])
    seconds = time.perf_counter() - start
    norms = np.linalg.norm(vectors, axis=1)
    print(f"  64 chunk bbca_2024: {seconds:.1f} s ({len(chunks) / seconds:.1f} chunk/s), "
          f"norma {norms.min():.6f}-{norms.max():.6f}")
    print(f"  embedder() kedua kali = model yang sama: {embedder() is embedder()}")


if __name__ == "__main__":
    main()
