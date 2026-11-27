"""
Langkah 3 Minggu 9 (tugas 9.2, Keputusan 9.C) -- pembungkus `hybrid_retrieve` sebagai LangChain
`@tool` bernama bahasa Inggris (`search_annual_report`).  docs/PANDUAN_MINGGU9-10.md, Langkah 3.

Aturan desain:
  1. NAMA tool bahasa Inggris (`search_annual_report`) -- temuan Minggu 2 (`check_tool_calling.py`):
     nama tool bahasa Indonesia memicu error 400 `tool_use_failed` pada 5/5 percobaan gpt-oss-120b.
  2. Parameter `ticker` dan `year` WAJIB -- meneruskan pagar anti-kontaminasi antar bank & antar tahun
     dari `src/retrieval/hybrid.py`.
  3. Format keluaran menyertakan header metadata `[CHUNK i | id=... | hal=... | unit=... | merged_cells=...]`
     secara eksplisit agar LLM selalu melihat satuan & halaman sumber, dan menandai sel gabungan.
  4. `record_retrieved_chunks()` memakai `ContextVar` sehingga aman untuk merekam chunk mentah
     per eksekusi (dipakai untuk verifikasi grounding Python & pasokan `contexts` RAGAS Minggu 17).
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from langchain_core.tools import tool

from src import config
from src.retrieval.hybrid import hybrid_retrieve

_ACTIVE_RECORDER: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "active_chunk_recorder", default=None
)


@contextmanager
def record_retrieved_chunks():
    """Context manager untuk merekam seluruh chunk mentah yang diambil selama satu sesi ekstraksi."""
    store: dict[str, dict[str, Any]] = {}
    token = _ACTIVE_RECORDER.set(store)
    try:
        yield store
    finally:
        _ACTIVE_RECORDER.reset(token)


def _record(chunks: list[dict[str, Any]]) -> None:
    store = _ACTIVE_RECORDER.get()
    if store is None:
        return
    for chunk in chunks:
        store.setdefault(chunk["chunk_id"], chunk)


def format_chunks_for_llm(chunks: list[dict[str, Any]]) -> str:
    """Format daftar chunk hasil `hybrid_retrieve` menjadi teks terstruktur dengan metadata jelas."""
    if not chunks:
        return "Tidak ada potongan laporan yang ditemukan untuk query tersebut."
    blocks = []
    for idx, c in enumerate(chunks, start=1):
        unit = c.get("unit") or "tidak_terdeteksi"
        merged = bool(c.get("merged_cells", False))
        pages = c.get("pages") or []
        header = (
            f"[CHUNK {idx} | id={c['chunk_id']} | ticker={c['ticker']} | year={c['year']} "
            f"| hal={pages} | unit={unit} | merged_cells={merged}]"
        )
        lines = [header]
        if c.get("headings"):
            lines.append(f"Judul: {c['headings']}")
        if merged:
            lines.append("PERHATIAN: chunk ini memuat sel gabungan; periksa batas kolom tahun dan basis dengan cermat.")
        lines.append(c["text"])
        blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)


def retrieve_and_record(
    query: str,
    ticker: str,
    year: int,
    k: int = config.TOP_K_FINAL,
    expand: bool = True,
) -> list[dict[str, Any]]:
    """Panggil `hybrid_retrieve` satu tahun, rekam ke ContextVar aktif bila ada, dan kembalikan chunk."""
    clamped_k = min(max(int(k), 1), 10)
    chunks = hybrid_retrieve(query, ticker=ticker, year=int(year), k=clamped_k, expand=expand)
    _record(chunks)
    return chunks


@tool
def search_annual_report(query: str, ticker: str, year: int, k: int = 5) -> str:
    """Cari potongan tabel dan teks relevan dari laporan tahunan suatu emiten untuk satu tahun buku.

    Gunakan tool ini untuk mengambil angka keuangan beserta nomor halaman dan satuannya.
    Sertakan basis pelaporan pada query bila relevan (mis. 'entitas induk', 'bank', atau 'konsolidasian').

    Args:
        query: Kata kunci pencarian dalam bahasa Indonesia/Inggris (mis. 'KPMM modal inti tier 1 ATMR bank').
        ticker: Kode saham emiten huruf kecil (wajib, 4 huruf kode saham BEI).
        year: Tahun buku laporan (bilangan bulat, mis. 2024).
        k: Jumlah potongan chunk yang diambil (1-10, bawaan 5).
    """
    try:
        chunks = retrieve_and_record(query=query, ticker=ticker, year=year, k=k, expand=True)
    except ValueError as e:
        return f"ERROR: {e}"
    return format_chunks_for_llm(chunks)
