"""
Langkah 4 Minggu 9 (tugas 9.3-9.5, Keputusan 9.A-9.C) -- Extraction Agent generik berbasis
hybrid retrieval + Pydantic structured output (`method="json_schema"`) + verifikasi grounding Python.
docs/PANDUAN_MINGGU9-10.md, Langkah 4.

ATURAN DISIPLIN DATA UJI (9.5):
  Prompt dan logika di modul ini 100% generik -- TIDAK menyebut nama perusahaan, kode saham,
  nomor halaman, atau nomor Catatan tertentu. Seluruh definisi metrik dan query diambil dari
  `src/ratio_profiles.py` sesuai sektor dokumen.

Alur per (tahun, kelompok metrik):
  1. Ambil potongan laporan via tool `search_annual_report` (nama bahasa Inggris, `ticker` & `year`
     wajib) secara round-robin lintas query dalam kelompok agar batas kuota Groq 8.000 TPM aman;
  2. Minta LLM (`openai/gpt-oss-120b`, `reasoning_effort="low"`, `method="json_schema"`) mengutip
     teks angka mentah (`raw_value` atau `components`), satuan, dan `source_chunk_id` -- BUKAN
     mengonversi skala atau menghitung di kepala;
  3. Kode Python (`parse_number.py`) memverifikasi grounding setiap angka mentah pada teks chunk,
     menyelaraskan satuan dengan metadata chunk, menjumlahkan `components` bila ada, dan
     menormalisasi seluruh nominal ke JUTA Rupiah (`million_idr`);
  4. Jika ada metrik masih `not_found` atau `ungrounded` dan `allow_followup=True`, lakukan maksimal
     1× pencarian ulang terfokus untuk metrik yang hilang tersebut.

Smoke test CLI (hanya pakai emiten pengembangan saat pengembangan):
  python -m src.agents.extraction --ticker bbca --year 2024 --gate4
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src import config
from src import ratio_profiles as rp
from src.agents import parse_number as pn
from src.agents.state import (
    AgentState,
    GroupExtractionOutput,
    NormalizedMetric,
    RawMetricExtraction,
)
from src.agents.tools import (
    format_chunks_for_llm,
    record_retrieved_chunks,
    retrieve_and_record,
    search_annual_report,
)
from src.ingest.chunk import load_chunks
from src.retrieval import index

MAX_CHUNKS_PER_GROUP = 4
MAX_EXPANDED_CHUNKS = 6
MAX_RATE_LIMIT_RETRIES = 4
MAX_RATE_LIMIT_WAIT_S = 90.0     # jeda lebih lama = batas harian (TPD/RPD) -> hentikan, jangan menunggu
RETRY_AFTER_RE = re.compile(
    r"try again in\s+(?:(\d+)h)?\s*(?:(\d+)m(?!s))?\s*(?:(\d+(?:\.\d+)?)(ms|s))?", re.I
)

# Penanda generik tabel Informasi Segmen vs Laporan Keuangan utama (bebas nama emiten)
SEGMENT_TABLE_RE = re.compile(
    r"\b(informasi\s+segmen|segment\s+information|segmen\s+operasi|operating\s+segment|profitabilitas\s+segmen)\b",
    re.I,
)
STATEMENT_TABLE_RE = re.compile(
    r"(laporan\s+posisi\s+keuangan|statements?\s+of\s+financial\s+position|"
    r"laporan\s+laba\s+rugi|statements?\s+of\s+profit\s+or\s+loss)",
    re.I,
)
PARENT_STATEMENT_RE = re.compile(r"\b(entitas\s+induk|parent\s+entity|tersendiri)\b", re.I)
CONSOLIDATED_STATEMENT_RE = re.compile(r"\b(konsolidasian|consolidated)\b", re.I)


class RateLimitExhausted(RuntimeError):
    """Kuota Groq habis untuk jangka panjang (mis. token per hari) -- evaluasi harus dilanjutkan nanti."""

EXTRACTION_SYSTEM_PROMPT = """Kamu adalah agen ekstraksi angka laporan keuangan tahunan perusahaan publik Indonesia.
Tugasmu mengekstrak angka mentah dari potongan laporan (CHUNK) yang diberikan secara sangat teliti.

ATURAN WAJIB:
1. KUTIP TEKS ANGKA PERSIS seperti tertulis di dalam chunk pada field `raw_value` (misalnya "239.468.855" atau "54.851").
   - DILARANG mengubah skala (misalnya mengubah miliar ke juta), DILARANG membulatkan, dan DILARANG menghitung di kepala.
   - Format angka laporan Indonesia: titik (.) adalah pemisah ribuan, koma (,) adalah pemisah desimal. Tanda kurung (...) berarti negatif.
2. PERHATIKAN KOLOM TAHUN TARGET, BASIS PELAPORAN, DAN JENIS TABEL:
   - Banyak tabel memuat kolom tahun pembanding (tahun sebelumnya) di sebelah kolom tahun target. Periksa judul kolom tahun secara eksplisit dan ambil HANYA angka pada kolom tahun target yang diminta.
   - Bedakan secara ketat antara basis `bank_only` (Entitas Induk / Bank saja / Parent Entity) dan basis `consolidated` (Konsolidasian). Jangan pernah menukar kedua kolom tersebut!
   - ABAIKAN tabel Informasi Segmen (segmen operasi seperti Corporate/Retail Banking atau segmen geografis) — selalu prioritaskan Laporan Keuangan utama (Laporan Posisi Keuangan / Laporan Laba Rugi) atau Ikhtisar Data Keuangan total perusahaan.
   - Untuk metrik `basis='bank_only'`, JANGAN mengambil angka dari tabel Konsolidasian atau ringkasan MD&A tanpa keterangan eksplisit Bank saja / Entitas Induk / Parent Entity — jika chunk basis Bank yang sesuai tidak ada, isi `raw_value=null` agar sistem mencari ulang.
3. KOMPONEN (hanya bila subtotal tidak tercetak langsung di tabel):
   - Jika metrik mengizinkan komponen dan totalnya TIDAK tercetak sebagai satu baris (misalnya baris tabel bertuliskan 'setelah dikurangi cadangan kerugian penurunan nilai sebesar Rp X pada tanggal ...' — angka X pada teks baris tersebut ADALAH nilai CKPN, sehingga Kredit Bruto = seluruh sub-baris Kredit Neto + nilai CKPN tahun target [dimasukkan satu kali saja]; atau Simpanan Nasabah terpecah menjadi Pihak berelasi dan Pihak ketiga), biarkan `raw_value=null`, kutip seluruh angka penyusun persis dari chunk ke `components`, dan isi `component_operation="sum"`. Kode Python yang akan menjumlahkannya.
   - Jika subtotal/total SUDAH tercetak langsung di tabel, cukup isi `raw_value` dan set `component_operation="none"` (`components=null`).
4. DILARANG MENEBAK (ANTI-HALUSINASI):
   - Jika angka untuk tahun target dan basis yang diminta tidak tersedia di chunk mana pun, WAJIB isi `raw_value=null`, `components=null`, `unit=null`, `source_chunk_id=null`, dan jelaskan singkat di `notes`.
5. SATUAN & SITASI SUMBER:
   - Isi `unit` sesuai header `[unit=...]` pada chunk atau judul tabel (mis. "dalam jutaan Rupiah" -> `million_idr`, "dalam miliar Rupiah" -> `billion_idr`).
   - Isi `source_chunk_id` persis dari header `[CHUNK ... | id=...]` dan `source_pages` dari `[hal=...]`.
6. Keluarkan satu entri pada `items` untuk SETIAP `metric_key` yang diminta, persis sesuai urutan dan nama kuncinya."""


def _build_group_user_prompt(
    year: int,
    specs: Sequence[rp.MetricSpec],
    chunks_text: str,
) -> str:
    lines = [
        f"TAHUN TARGET: {year}",
        "",
        "DAFTAR METRIK YANG HARUS DIEKSTRAK:",
    ]
    for i, s in enumerate(specs, start=1):
        comp_note = " (boleh pakai `components` + `component_operation='sum'` jika total tidak tercetak)" if s.allow_components else ""
        lines.append(
            f"  {i}. metric_key={s.key!r} | basis={s.basis} | {s.label}: {s.description}{comp_note}"
        )
    lines += [
        "",
        "POTONGAN LAPORAN TAHUNAN (HANYA GUNAKAN DATA DI BAWAH INI):",
        chunks_text,
    ]
    return "\n".join(lines)


def _is_segment_chunk(chunk: dict[str, Any]) -> bool:
    head = f"{chunk.get('headings', '')}\n{chunk.get('text', '')[:320]}"
    return bool(SEGMENT_TABLE_RE.search(head))


def _is_primary_statement_chunk(chunk: dict[str, Any], target_basis: str | None = None) -> bool:
    if _is_segment_chunk(chunk):
        return False
    head = f"{chunk.get('headings', '')}\n{chunk.get('text', '')[:400]}"
    if not STATEMENT_TABLE_RE.search(head):
        return False
    if target_basis == "bank_only":
        return bool(PARENT_STATEMENT_RE.search(head))
    if target_basis == "consolidated":
        return bool(CONSOLIDATED_STATEMENT_RE.search(head)) and not bool(PARENT_STATEMENT_RE.search(head))
    return True


@lru_cache(maxsize=16)
def _doc_chunks(ticker: str, year: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Muat daftar chunk terindeks untuk satu dokumen (untuk ekspansi tabel multi-halaman)."""
    if not config.chunks(year, ticker).exists():
        return [], {}
    rows = load_chunks(year, ticker, include_excluded=False)
    by_id = {c["chunk_id"]: i for i, c in enumerate(rows)}
    return rows, by_id


def _normalize_doc_chunk(c: dict[str, Any]) -> dict[str, Any]:
    headings = c.get("headings") or []
    return {
        "chunk_id": c["chunk_id"],
        "text": c["text"],
        "ticker": c.get("ticker", ""),
        "sector": c.get("sector", ""),
        "year": c.get("year"),
        "pages": list(c.get("pages") or []),
        "unit": c.get("unit"),
        "headings": " > ".join(headings) if isinstance(headings, list) else str(headings),
        "is_table": bool(c.get("is_table", False)),
        "merged_cells": bool(c.get("merged_cells", False)),
        "score": 0.0,
    }


def _pages_adjacent(pages_a: Sequence[int], pages_b: Sequence[int]) -> bool:
    if not pages_a or not pages_b:
        return False
    return min(abs(a - b) for a in pages_a for b in pages_b) <= 1


def _expand_split_statement_chunks(
    selected: list[dict[str, Any]],
    ticker: str,
    year: int,
    max_total: int = MAX_EXPANDED_CHUNKS,
    target_basis: str | None = None,
) -> list[dict[str, Any]]:
    """Sisipkan chunk tabel tetangga (±1 halaman) tanpa pernah membuang chunk hasil retrieval asli."""
    rows, by_id = _doc_chunks(ticker, year)
    budget = max(0, max_total - len(selected))
    if not rows or budget == 0:
        return selected
    seen = {c["chunk_id"] for c in selected}
    result: list[dict[str, Any]] = []
    added = 0
    for chunk in selected:
        result.append(chunk)
        if added >= budget or not _is_primary_statement_chunk(chunk, target_basis):
            continue
        idx = by_id.get(chunk["chunk_id"])
        if idx is None:
            continue
        base_pages = chunk.get("pages") or []
        for step in (-1, 1):
            if added >= budget:
                break
            j = idx + step
            scanned = 0
            while 0 <= j < len(rows) and scanned < 4:
                cand = rows[j]
                scanned += 1
                if not _pages_adjacent(base_pages, cand.get("pages") or []):
                    break
                if cand.get("is_table") and len(cand.get("text") or "") >= 500:
                    cid = cand["chunk_id"]
                    if cid not in seen:
                        norm = _normalize_doc_chunk(cand)
                        if not _is_segment_chunk(norm):
                            seen.add(cid)
                            result.append(norm)
                            added += 1
                    break
                j += step
    return result


def _chunk_priority(chunk: dict[str, Any], prefer_tables: bool = True) -> int:
    """Taruh tabel segmen di belakang; bila prefer_tables=True, utamakan tabel (0) di atas prosa (1)."""
    if _is_segment_chunk(chunk):
        return 2
    if prefer_tables:
        return 0 if chunk.get("is_table") else 1
    return 0


def _interleave_chunks(
    lists: Sequence[list[dict[str, Any]]],
    max_chunks: int,
    *,
    prefer_tables: bool = True,
) -> list[dict[str, Any]]:
    """Gabungkan hasil beberapa query secara round-robin tanpa duplikat."""
    ordered_lists = [sorted(xs, key=lambda c: _chunk_priority(c, prefer_tables)) for xs in lists]
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    max_len = max((len(xs) for xs in ordered_lists), default=0)
    for pos in range(max_len):
        for xs in ordered_lists:
            if pos >= len(xs):
                continue
            cid = xs[pos]["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            merged.append(xs[pos])
            if len(merged) >= max_chunks:
                return merged
    return merged


def _resolve_chunk_for_values(
    values: Sequence[str],
    preferred_id: str | None,
    chunks_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, bool, str | None]:
    """Cari chunk yang memuat semua `values` secara tergrounding -> (chunk, all_grounded, note)."""
    if not values:
        return None, False, None

    if preferred_id and preferred_id in chunks_by_id:
        pref = chunks_by_id[preferred_id]
        if all(pn.is_grounded_in_text(v, pref["text"]) for v in values):
            return pref, True, None

    # Fallback: periksa apakah semua nilai muncul di satu chunk lain dalam batch yang sama
    for cid, chunk in chunks_by_id.items():
        if cid == preferred_id:
            continue
        if all(pn.is_grounded_in_text(v, chunk["text"]) for v in values):
            note = f"source_chunk_id disesuaikan dari {preferred_id!r} ke {cid!r} (terverifikasi grounding)"
            return chunk, True, note

    # Untuk multi-komponen, izinkan komponen tersebar lintas chunk ber-satuan sama dalam batch tahun itu
    if len(values) > 1:
        matched_chunks = []
        for v in values:
            found = next((c for c in chunks_by_id.values() if pn.is_grounded_in_text(v, c["text"])), None)
            if found is None:
                return chunks_by_id.get(preferred_id or ""), False, "salah satu komponen tidak ditemukan di teks chunk"
            matched_chunks.append(found)
        units = {c.get("unit") for c in matched_chunks if c.get("unit")}
        if len(units) <= 1:
            return matched_chunks[0], True, "komponen terverifikasi lintas chunk pada batch yang sama"
        return matched_chunks[0], False, f"komponen berasal dari chunk bersatuan berbeda: {sorted(units)}"

    return chunks_by_id.get(preferred_id or ""), False, "angka tidak ditemukan persis di teks chunk sumber"


def verify_and_normalize(
    raw: RawMetricExtraction,
    spec: rp.MetricSpec,
    chunks_by_id: dict[str, dict[str, Any]],
) -> NormalizedMetric:
    """Verifikasi grounding, selaraskan satuan, dan normalisasi ke juta Rupiah oleh kode Python (9.A)."""
    notes_parts = [raw.notes] if raw.notes else []

    use_components = bool(raw.components) and raw.component_operation == "sum"
    has_raw = raw.raw_value is not None and raw.raw_value.strip() != ""

    if not has_raw and not use_components:
        return NormalizedMetric(
            metric_key=spec.key,
            basis=raw.basis,
            source_chunk_id=raw.source_chunk_id,
            source_pages=list(raw.source_pages),
            source_header=raw.source_header,
            grounded=False,
            status="not_found",
            notes="; ".join(notes_parts) or None,
        )

    values_to_check = list(raw.components) if use_components else [raw.raw_value]  # type: ignore[list-item]
    # Pastikan teks bukan sekadar tanda kosong "-" / "N/A"
    try:
        non_empty = [v for v in values_to_check if pn.extract_numeric_core(v)[0] is not None]
    except ValueError as e:
        return NormalizedMetric(
            metric_key=spec.key,
            raw_value=raw.raw_value,
            components=list(raw.components) if raw.components else None,
            original_unit=raw.unit,
            basis=raw.basis,
            source_chunk_id=raw.source_chunk_id,
            source_pages=list(raw.source_pages),
            source_header=raw.source_header,
            grounded=False,
            status="parse_error",
            notes="; ".join([*notes_parts, str(e)]),
        )

    if not non_empty:
        return NormalizedMetric(
            metric_key=spec.key,
            raw_value=raw.raw_value,
            basis=raw.basis,
            source_chunk_id=raw.source_chunk_id,
            source_pages=list(raw.source_pages),
            source_header=raw.source_header,
            grounded=False,
            status="not_found",
            notes="; ".join(notes_parts) or None,
        )

    chunk, grounded, g_note = _resolve_chunk_for_values(values_to_check, raw.source_chunk_id, chunks_by_id)
    if g_note:
        notes_parts.append(g_note)

    if not grounded or chunk is None:
        return NormalizedMetric(
            metric_key=spec.key,
            raw_value=raw.raw_value,
            components=list(raw.components) if raw.components else None,
            original_unit=raw.unit,
            chunk_unit=chunk.get("unit") if chunk else None,
            basis=raw.basis,
            source_chunk_id=raw.source_chunk_id,
            source_pages=list(chunk["pages"]) if chunk else list(raw.source_pages),
            source_header=raw.source_header or (chunk.get("headings") if chunk else None),
            merged_cells_warning=bool(chunk.get("merged_cells", False)) if chunk else False,
            grounded=False,
            status="ungrounded",
            notes="; ".join(notes_parts) or "angka tidak terverifikasi di chunk sumber",
        )

    chunk_unit = chunk.get("unit")
    if spec.is_percent:
        effective_unit: str | None = "percent"
    elif chunk_unit in pn.UNIT_TO_MILLION_IDR:
        effective_unit = chunk_unit
        if raw.unit and raw.unit != chunk_unit:
            notes_parts.append(f"satuan LLM ({raw.unit}) diselaraskan ke metadata chunk ({chunk_unit})")
    elif raw.unit in pn.UNIT_TO_MILLION_IDR:
        effective_unit = raw.unit
    else:
        return NormalizedMetric(
            metric_key=spec.key,
            raw_value=raw.raw_value,
            components=list(raw.components) if raw.components else None,
            original_unit=raw.unit,
            chunk_unit=chunk_unit,
            basis=raw.basis,
            source_chunk_id=chunk["chunk_id"],
            source_pages=list(chunk["pages"]),
            source_header=raw.source_header or chunk.get("headings") or None,
            merged_cells_warning=bool(chunk.get("merged_cells", False)),
            grounded=True,
            status="unit_conflict",
            notes="; ".join([*notes_parts, f"satuan nominal tidak diketahui (llm={raw.unit}, chunk={chunk_unit})"]),
        )

    try:
        norm_val = pn.normalize_extraction(
            raw.raw_value if not use_components else None,
            effective_unit,
            components=raw.components if use_components else None,
            operation="sum" if use_components else "none",
            is_percent=spec.is_percent,
            abs_value=spec.abs_value,
        )
    except ValueError as e:
        return NormalizedMetric(
            metric_key=spec.key,
            raw_value=raw.raw_value,
            components=list(raw.components) if raw.components else None,
            original_unit=raw.unit,
            chunk_unit=chunk_unit,
            basis=raw.basis,
            source_chunk_id=chunk["chunk_id"],
            source_pages=list(chunk["pages"]),
            source_header=raw.source_header or chunk.get("headings") or None,
            merged_cells_warning=bool(chunk.get("merged_cells", False)),
            grounded=True,
            status="parse_error",
            notes="; ".join([*notes_parts, str(e)]),
        )

    return NormalizedMetric(
        metric_key=spec.key,
        value_million_idr=None if spec.is_percent else norm_val,
        value_percent=norm_val if spec.is_percent else None,
        raw_value=raw.raw_value,
        components=list(raw.components) if raw.components else None,
        original_unit=raw.unit,
        chunk_unit=chunk_unit,
        basis=raw.basis,
        source_chunk_id=chunk["chunk_id"],
        source_pages=list(chunk["pages"]),
        source_header=raw.source_header or chunk.get("headings") or None,
        merged_cells_warning=bool(chunk.get("merged_cells", False)),
        grounded=True,
        status="ok",
        notes="; ".join(notes_parts) or None,
    )


def _retry_delay_seconds(err_msg: str, attempt: int) -> float:
    """Baca 'try again in 1h2m3.5s' / '7m12s' / '850ms' dari pesan Groq; fallback backoff bertahap."""
    m = RETRY_AFTER_RE.search(err_msg)
    if m and any(m.group(i) for i in (1, 2, 3)):
        hours = float(m.group(1) or 0)
        minutes = float(m.group(2) or 0)
        secs = float(m.group(3) or 0)
        if m.group(4) and m.group(4).lower() == "ms":
            secs /= 1000.0
        return max(1.0, hours * 3600 + minutes * 60 + secs + 1.5)
    return min(45.0, 12.0 * (attempt + 1))


def _invoke_structured_group(
    llm,
    system_prompt: str,
    user_prompt: str,
    stats: dict[str, Any],
) -> GroupExtractionOutput:
    """Jalankan structured output `method='json_schema'` dengan backoff 429 & fallback `json_mode`."""
    primary = llm.with_structured_output(GroupExtractionOutput, method="json_schema", include_raw=True)
    messages = [SystemMessage(system_prompt), HumanMessage(user_prompt)]

    last_err: Exception | None = None
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            stats["llm_calls"] += 1
            res = primary.invoke(messages)
            raw_msg = res.get("raw") if isinstance(res, dict) else None
            usage = getattr(raw_msg, "usage_metadata", None) or {}
            stats["input_tokens"] += int(usage.get("input_tokens", 0))
            stats["output_tokens"] += int(usage.get("output_tokens", 0))
            stats["total_tokens"] += int(usage.get("total_tokens", 0))

            parsed = res.get("parsed") if isinstance(res, dict) else res
            if parsed is not None:
                return parsed
            raise ValueError(f"parsing_error: {res.get('parsing_error') if isinstance(res, dict) else 'kosong'}")
        except Exception as e:
            last_err = e
            msg = str(e)
            is_rate_limit = ("429" in msg) or ("rate_limit" in msg.lower()) or ("rate limit" in msg.lower())
            if is_rate_limit:
                wait_s = _retry_delay_seconds(msg, attempt)
                if wait_s > MAX_RATE_LIMIT_WAIT_S or "per day" in msg.lower():
                    raise RateLimitExhausted(f"kuota Groq habis (tunggu ±{wait_s / 60:.1f} menit): {msg[:300]}") from e
                if attempt < MAX_RATE_LIMIT_RETRIES:
                    stats["rate_limit_retries"] += 1
                    time.sleep(wait_s)
                    continue
            if "tool_use_failed" in msg.lower() and attempt < 1:
                stats["tool_error_retries"] += 1
                continue
            # Fallback sekali ke json_mode jika json_schema bermasalah
            if attempt == 0 and not is_rate_limit:
                try:
                    stats["llm_calls"] += 1
                    fallback = llm.with_structured_output(GroupExtractionOutput, method="json_mode", include_raw=True)
                    schema_hint = json.dumps(GroupExtractionOutput.model_json_schema(), ensure_ascii=False)
                    fb_msgs = [
                        SystemMessage(system_prompt + f"\nKeluarkan HANYA JSON valid sesuai skema:\n{schema_hint}"),
                        HumanMessage(user_prompt),
                    ]
                    fb_res = fallback.invoke(fb_msgs)
                    fb_raw = fb_res.get("raw") if isinstance(fb_res, dict) else None
                    usage = getattr(fb_raw, "usage_metadata", None) or {}
                    stats["input_tokens"] += int(usage.get("input_tokens", 0))
                    stats["output_tokens"] += int(usage.get("output_tokens", 0))
                    stats["total_tokens"] += int(usage.get("total_tokens", 0))
                    if isinstance(fb_res, dict) and fb_res.get("parsed") is not None:
                        return fb_res["parsed"]
                except Exception as fb_err:
                    last_err = fb_err
            break
    raise RuntimeError(f"ekstraksi LLM gagal: {last_err}")


def _extract_group_once(
    llm,
    ticker: str,
    year: int,
    queries: Sequence[str],
    specs: Sequence[rp.MetricSpec],
    top_k: int,
    stats: dict[str, Any],
    recorder: dict[str, dict[str, Any]] | None = None,
    *,
    prefer_tables: bool = True,
) -> dict[str, NormalizedMetric]:
    chunk_lists = []
    for q in queries:
        stats["tool_calls"] += 1
        # Panggil fungsi retrieval terpadu (juga dipakai @tool `search_annual_report`)
        chunk_lists.append(retrieve_and_record(q, ticker=ticker, year=year, k=top_k, expand=True))

    bases = {s.basis for s in specs}
    target_basis = next(iter(bases)) if len(bases) == 1 else None
    selected = _interleave_chunks(chunk_lists, max_chunks=MAX_CHUNKS_PER_GROUP, prefer_tables=prefer_tables)
    selected = _expand_split_statement_chunks(
        selected, ticker=ticker, year=year, max_total=MAX_EXPANDED_CHUNKS, target_basis=target_basis
    )
    if recorder is not None:
        for c in selected:
            recorder.setdefault(c["chunk_id"], c)
    chunks_by_id = {c["chunk_id"]: c for c in selected}
    chunks_text = format_chunks_for_llm(selected)

    user_prompt = _build_group_user_prompt(year, specs, chunks_text)
    parsed = _invoke_structured_group(llm, EXTRACTION_SYSTEM_PROMPT, user_prompt, stats)

    by_key = {item.metric_key: item for item in parsed.items}
    results: dict[str, NormalizedMetric] = {}
    for spec in specs:
        raw_item = by_key.get(spec.key) or RawMetricExtraction(
            metric_key=spec.key, raw_value=None, notes="metrik tidak dikembalikan oleh LLM"
        )
        results[spec.key] = verify_and_normalize(raw_item, spec, chunks_by_id)
    return results


def _detect_sector_for_ticker(ticker: str, years: Sequence[int]) -> str:
    code = ticker.strip().lower()
    for y in years:
        meta_path = config.report_metadata(y, code)
        if meta_path.exists():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if data.get("sector"):
                return str(data["sector"])
    hit = index.collection().get(where={"ticker": code}, limit=1, include=["metadatas"])
    if hit["metadatas"]:
        return str(hit["metadatas"][0].get("sector", "general"))
    return "general"


def _resolve_years(ticker: str, year: int | Sequence[int] | None) -> list[int]:
    code = ticker.strip().lower()
    available = sorted(y for t, y in index.indexed() if t == code)
    if not available:
        raise ValueError(f"kode saham '{code}' belum terindeks di pustaka")
    if year is None:
        return available
    if isinstance(year, int) and not isinstance(year, bool):
        if year not in available:
            raise ValueError(f"tahun {year} tidak tersedia untuk '{code}' (tersedia: {available})")
        return [year]
    years = sorted({int(y) for y in year})
    missing = [y for y in years if y not in available]
    if missing:
        raise ValueError(f"tahun {missing} tidak tersedia untuk '{code}' (tersedia: {available})")
    return years


def extract_metrics(
    ticker: str,
    years: int | Sequence[int] | None = None,
    *,
    sector: str | None = None,
    metric_keys: Sequence[str] | None = None,
    gate4_only: bool = False,
    allow_followup: bool = True,
    delay_between_groups: float = 0.0,
    llm=None,
) -> dict[str, Any]:
    """Ekstrak metrik keuangan untuk satu emiten (1 atau beberapa tahun) secara terstruktur & tergrounding."""
    t0 = time.perf_counter()
    code = ticker.strip().lower()
    target_years = _resolve_years(code, years)
    resolved_sector = sector or _detect_sector_for_ticker(code, target_years)
    profile = rp.get_profile(resolved_sector)

    if metric_keys is None and gate4_only and profile.sector == "bank":
        wanted_keys: Sequence[str] | None = rp.gate4_metric_keys(profile)
    else:
        wanted_keys = metric_keys

    plan = rp.groups_for_metrics(profile, wanted_keys)
    active_llm = llm or config.get_llm(effort=config.REASONING_EFFORT_EXTRACTION)

    stats: dict[str, Any] = {
        "llm_calls": 0,
        "tool_calls": 0,
        "followup_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "rate_limit_retries": 0,
        "tool_error_retries": 0,
        "seconds": 0.0,
    }
    extracted_data: dict[int, dict[str, dict[str, Any]]] = {}
    errors: list[str] = []

    with record_retrieved_chunks() as recorder:
        for y in target_years:
            extracted_data[y] = {}
            for g_idx, (group, specs) in enumerate(plan):
                if g_idx > 0 and delay_between_groups > 0:
                    time.sleep(delay_between_groups)
                try:
                    group_res = _extract_group_once(
                        active_llm, code, y, group.search_queries, specs, group.top_k, stats, recorder,
                        prefer_tables=group.prefer_tables,
                    )
                except RateLimitExhausted:
                    raise
                except Exception as e:
                    err = f"{code}_{y}/{group.group_id}: {e}"
                    errors.append(err)
                    for spec in specs:
                        extracted_data[y][spec.key] = NormalizedMetric(
                            metric_key=spec.key, status="parse_error", notes=str(e)
                        ).model_dump()
                    continue

                # Pencarian ulang terfokus (maks. 1x) bila ada metrik belum ditemukan / tidak tergrounding
                if allow_followup:
                    missing_specs = [s for s in specs if group_res[s.key].status != "ok"]
                    if missing_specs:
                        stats["followup_calls"] += 1
                        followup_queries = tuple(
                            f"{s.label} {'entitas induk bank' if s.basis == 'bank_only' else 'konsolidasian'}"
                            for s in missing_specs
                        )
                        if delay_between_groups > 0:
                            time.sleep(delay_between_groups)
                        try:
                            retry_res = _extract_group_once(
                                active_llm, code, y, followup_queries, missing_specs, top_k=5, stats=stats,
                                recorder=recorder, prefer_tables=group.prefer_tables,
                            )
                            for s in missing_specs:
                                if retry_res[s.key].status == "ok":
                                    group_res[s.key] = retry_res[s.key]
                        except RateLimitExhausted:
                            raise
                        except Exception as e:
                            errors.append(f"{code}_{y}/{group.group_id}/followup: {e}")

                for spec in specs:
                    item = group_res[spec.key]
                    extracted_data[y][spec.key] = item.model_dump()
                    if item.status != "ok":
                        errors.append(f"{code}_{y}/{spec.key}: status={item.status} ({item.notes or '-'})")

        retrieved_chunks = list(recorder.values())

    stats["seconds"] = round(time.perf_counter() - t0, 2)
    return {
        "ticker": code,
        "sector": resolved_sector,
        "profile_validated": profile.validated,
        "profile_warning": profile.warning_label,
        "years": target_years,
        "extracted_data": extracted_data,
        "retrieved_chunks": retrieved_chunks,
        "extraction_errors": errors,
        "extraction_stats": stats,
    }


def extraction_node(state: AgentState) -> dict[str, Any]:
    """Node LangGraph untuk Extraction Agent (siap dihubungkan di Minggu 15)."""
    ticker = state.get("ticker", "")
    if not ticker:
        raise ValueError("AgentState['ticker'] wajib diisi sebelum menjalankan extraction_node")
    result = extract_metrics(
        ticker=ticker,
        years=state.get("year"),
        sector=state.get("sector"),
    )
    ok_count = sum(
        1 for ym in result["extracted_data"].values() for m in ym.values() if m["status"] == "ok"
    )
    tot_count = sum(len(ym) for ym in result["extracted_data"].values())
    summary = (
        f"Ekstraksi selesai untuk {result['ticker']} tahun {result['years']}: "
        f"{ok_count}/{tot_count} metrik terverifikasi grounding "
        f"({result['extraction_stats']['total_tokens']} token, {result['extraction_stats']['seconds']} s)."
    )
    return {
        "sector": result["sector"],
        "extracted_data": result["extracted_data"],
        "retrieved_chunks": result["retrieved_chunks"],
        "extraction_errors": result["extraction_errors"],
        "extraction_retries": int(state.get("extraction_retries", 0)) + result["extraction_stats"]["followup_calls"],
        "extraction_stats": result["extraction_stats"],
        "messages": [AIMessage(content=summary)],
    }


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Smoke test Extraction Agent (Minggu 9).")
    ap.add_argument("--ticker", required=True, help="kode saham, mis. bbca")
    ap.add_argument("--year", type=int, nargs="*", help="tahun target (kosong = semua tahun)")
    ap.add_argument("--gate4", action="store_true", help="hanya ekstrak 8 metrik GATE 4")
    ap.add_argument("--no-followup", action="store_true", help="matikan pencarian ulang terfokus")
    ap.add_argument("--delay", type=float, default=1.0, help="jeda detik antar kelompok metrik")
    args = ap.parse_args(argv)

    year_arg = None if not args.year else (args.year[0] if len(args.year) == 1 else args.year)
    res = extract_metrics(
        ticker=args.ticker,
        years=year_arg,
        gate4_only=args.gate4,
        allow_followup=not args.no_followup,
        delay_between_groups=args.delay,
    )
    print(f"Emiten : {res['ticker']} | sektor: {res['sector']} | validated={res['profile_validated']}")
    if res["profile_warning"]:
        print(f"Catatan: {res['profile_warning']}")
    for y, metrics in res["extracted_data"].items():
        print(f"\n== {res['ticker']}_{y} ==")
        for k, m in metrics.items():
            val_str = f"{m['value_million_idr']:,.3f} jt Rp" if m["value_million_idr"] is not None else "None"
            raw_str = m["raw_value"] if m["raw_value"] is not None else (f"sum({m['components']})" if m["components"] else "None")
            print(f"  {k:<24} [{m['status']:<11}] {val_str:>22}  | raw={raw_str} | hal={m['source_pages']} ({m['source_chunk_id']})")
    st = res["extraction_stats"]
    print(f"\nStatistik: {st['llm_calls']} panggilan LLM, {st['tool_calls']} tool call, "
          f"{st['total_tokens']:,} token, {st['seconds']} s, "
          f"retry 429={st['rate_limit_retries']}x, tool_err={st['tool_error_retries']}x")
    print(f"Tools terdaftar: {search_annual_report.name}")


if __name__ == "__main__":
    main()

