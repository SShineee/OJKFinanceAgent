"""
Langkah 3 Minggu 9 (tugas 9.2, Keputusan 9.C) & Langkah 2 Minggu 11 (tugas 11.1, Keputusan 11.A) --
tool LangChain bersama bernama bahasa Inggris:
  - `search_annual_report` : pembungkus `hybrid_retrieve` dengan pagar `ticker` & `year` wajib;
  - `python_calculator`    : pembungkus aman `PythonAstREPLTool` untuk perhitungan rasio keuangan.
docs/PANDUAN_MINGGU9-10.md (Langkah 3) & docs/PANDUAN_MINGGU11-12.md (Langkah 2).

Aturan desain:
  1. NAMA tool bahasa Inggris (`search_annual_report`, `python_calculator`) -- temuan Minggu 2
     (`check_tool_calling.py`): nama tool bahasa Indonesia memicu error 400 `tool_use_failed`.
  2. Parameter `ticker` dan `year` WAJIB pada retrieval -- meneruskan pagar anti-kontaminasi.
  3. Format keluaran chunk menyertakan `[CHUNK i | id=... | hal=... | unit=... | merged_cells=...]`.
  4. `record_retrieved_chunks()` memakai `ContextVar` untuk verifikasi grounding & RAGAS Minggu 17.
  5. `evaluate_formula_python()` memvalidasi AST sebelum mengeksekusi `PythonAstREPLTool` sehingga
     hanya ekspresi aritmetika aman (tanpa import/file/atribut) yang diizinkan.
"""

import ast
import math
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from langchain_core.tools import tool
from langchain_experimental.tools import PythonAstREPLTool

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


# ----------------------------------------------------------------- Kalkulator Python aman (11.1)

_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
)
_ALLOWED_FUNCS = {"round": round, "abs": abs, "min": min, "max": max}


def validate_math_expression(expression: str, allowed_names: set[str] | None = None) -> None:
    """Validasi AST ekspresi matematika sebelum dijalankan di `PythonAstREPLTool` (cegah eksekusi berbahaya)."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("ekspresi matematika kosong")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"sintaks ekspresi tidak valid: {e.msg}") from e

    permitted = set(_ALLOWED_FUNCS) | (allowed_names or set())
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ValueError(f"konstruksi tidak diizinkan dalam ekspresi kalkulator: {type(node).__name__}")
        if isinstance(node, ast.Constant) and (isinstance(node.value, bool) or not isinstance(node.value, (int, float))):
            raise ValueError(f"hanya konstanta numerik yang diizinkan, bukan {type(node.value).__name__}")
        if isinstance(node, ast.Name) and node.id not in permitted:
            raise ValueError(f"variabel/fungsi tidak dikenali: {node.id!r}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("hanya fungsi matematika dasar (round, abs, min, max) yang diizinkan")


def evaluate_formula_python(
    expression: str,
    variables: dict[str, float] | None = None,
    *,
    ndigits: int = 4,
) -> float:
    """Eksekusi ekspresi matematika aman lewat `PythonAstREPLTool` dan kembalikan float terbulatkan."""
    safe_vars: dict[str, Any] = {}
    for k, v in (variables or {}).items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError(f"nilai variabel '{k}' harus bilangan finite, bukan {v!r}")
        safe_vars[k] = float(v)

    validate_math_expression(expression, allowed_names=set(safe_vars))
    repl = PythonAstREPLTool(locals={**_ALLOWED_FUNCS, **safe_vars})
    raw_out = repl.invoke(expression.strip())

    if isinstance(raw_out, (int, float)) and not isinstance(raw_out, bool):
        val = float(raw_out)
    elif isinstance(raw_out, str):
        text = raw_out.strip()
        if any(err in text for err in ("ZeroDivisionError", "Error", "Exception")):
            raise ValueError(f"eksekusi kalkulator gagal: {text}")
        try:
            val = float(text)
        except ValueError as e:
            raise ValueError(f"keluaran kalkulator bukan angka: {text!r}") from e
    else:
        raise ValueError(f"tipe keluaran kalkulator tak terduga: {type(raw_out).__name__}")

    if not math.isfinite(val):
        raise ValueError(f"hasil perhitungan tidak finite: {val}")
    return round(val, ndigits)


@tool
def python_calculator(expression: str) -> str:
    """Hitung ekspresi aritmetika angka keuangan secara eksak menggunakan PythonAstREPLTool.

    Gunakan tool ini untuk setiap pembagian, rata-rata, atau persentase agar tidak ada kesalahan
    hitung. Hanya menerima angka (titik desimal standar Python), operator +-*/, dan fungsi
    round/abs/min/max. Contoh: '(249056422 / 848181552) * 100'.

    Args:
        expression: Ekspresi aritmetika Python yang valid.
    """
    try:
        val = evaluate_formula_python(expression)
    except ValueError as e:
        return f"ERROR: {e}"
    return f"{val:.4f}"
