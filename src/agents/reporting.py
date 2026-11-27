"""
Langkah 2 Minggu 14 (tugas 14.1-14.3, Keputusan 14.A-14.D) -- Reporting Agent generik
dengan arsitektur hibrida 3-lapis:
  1. Lapis 1 (Python deterministik): merakit tabel rasio & ambang OJK, tabel komponen metrik
     keuangan, tabel tren antar tahun, dan daftar sumber berita/regulasi dengan angka, sitasi
     halaman PDF asli (`hal. ...`), dan tautan URL Tavily terkunci 100%;
  2. Lapis 2 (LLM structured output `ReportNarrative`): menyusun narasi analitis yang menjawab
     pertanyaan pengguna, menghubungkan antar indikator, dan menyintesis konteks pasar
     (dengan fallback deterministik jika LLM gagal);
  3. Lapis 3 (Perakitan Markdown + Audit Post-Generasi): menyusun 5 bagian wajib (14.1),
     menjaga label `belum divalidasi` pada profil non-bank (R17), dan membersihkan otomatis
     tautan tak terverifikasi (anti-halusinasi URL, 14.2), plus helper ringkasan HTML
     siap-Telegram (<= 4.096 karakter, persiapan 16.3d).

ATURAN DISIPLIN LINTAS EMITEN (R10 & R17):
  File ini 100% generik -- TIDAK mem-hardcode nama perusahaan, kode saham, nomor halaman,
  atau nomor Catatan tertentu. Identitas emiten dibaca dinamis dari `metadata.json` / `AgentState`.

CLI smoke test:
  python -m src.agents.reporting --from-results <kode> --out results/sample_report_<kode>.md
"""

import argparse
import html
import json
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src import config
from src import ratio_profiles as rp
from src.agents.analyst import analyze_ratios
from src.agents.state import AgentState, ReportNarrative

REQUIRED_SECTION_HEADINGS: tuple[str, ...] = (
    "## 1. Ringkasan Eksekutif",
    "## 2. Rasio Keuangan & Interpretasi",
    "## 3. Tren Antar Tahun",
    "## 4. Konteks Pasar & Regulasi",
    "## 5. Kesimpulan",
)

_CATEGORY_LABELS: dict[str, str] = {
    "kinerja_emiten": "Kinerja Emiten",
    "regulasi_ojk": "Regulasi OJK/BI",
    "makro_sektor": "Makro & Sektor",
}

_DIRECTION_LABELS: dict[str, str] = {
    "naik": "Naik",
    "turun": "Turun",
    "stabil": "Stabil",
}

_OJK_CATEGORY_LABELS: dict[str, str] = {
    "sangat_kuat": "Sangat Kuat",
    "kuat": "Kuat",
    "memenuhi": "Memenuhi",
    "dibawah_minimum": "Di Bawah Minimum",
    "sangat_sehat": "Sangat Sehat",
    "sehat": "Sehat",
    "cukup_sehat": "Cukup Sehat",
    "kurang_sehat": "Kurang Sehat",
    "sangat_baik": "Sangat Baik",
    "baik": "Baik",
    "cukup": "Cukup",
    "rendah": "Rendah",
    "ideal_ojk": "Ideal OJK",
    "longgar": "Longgar",
    "ketat": "Ketat",
    "tinggi_risiko_likuiditas": "Tinggi (Risiko Likuiditas)",
    "waspada": "Waspada",
    "melebihi_batas_ojk": "Melebihi Batas OJK",
    "belum_divalidasi": "Belum Divalidasi",
}

_URL_MD_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")
_URL_RAW_RE = re.compile(r"(https?://[^\s<>\]\)\"']+)")
_PAGE_CITE_RE = re.compile(r"\bhal\.\s*\d+", re.IGNORECASE)

REPORTING_SYSTEM_PROMPT = """Kamu adalah analis keuangan senior yang menyusun narasi laporan analisis keuangan emiten BEI dalam bahasa Indonesia yang formal, objektif, dan terukur.

ATURAN WAJIB (ANTI-HALUSINASI & KETERLACAKAN):
1. Gunakan HANYA angka, rasio, tren, ambang batas OJK, cuplikan dokumen, dan berita yang tercantum di blok DATA TERVERIFIKASI.
   DILARANG mengarang angka baru, mengubah digit/persentase, mengubah ambang OJK, mengonversi satuan juta/miliar/triliun di kepala (salin persis satuan & nilai setara yang diberikan Python), atau mengisi angka untuk metrik/rasio yang berstatus `tidak tersedia` / `insufficient_data`.
2. Setiap kali menyebut angka metrik atau rasio keuangan di dalam narasi, WAJIB cantumkan sumber halamannya persis sesuai data (contoh: `(hal. 16)` atau `(hal. 594)`).
3. Pada `market_synthesis`, rujuk sumber berita secara rapi dengan nama sumber/domain atau tautan Markdown `[Sumber](URL)` HANYA memakai URL persis dari blok KONTEKS PASAR EKSTERNAL (JANGAN tulis `url=https://...` mentah dan DILARANG mengarang URL baru).
   Jika blok KONTEKS PASAR EKSTERNAL kosong, tulis secara jujur pada `market_synthesis` bahwa konteks pasar eksternal tidak tersedia saat analisis dijalankan.
4. Jika status profil bertanda `validated=False`, WAJIB sebutkan secara eksplisit pada `executive_summary` dan `conclusion` bahwa profil rasio sektor ini berstatus `belum divalidasi`.
5. Hubungkan antar indikator secara analitis (misalnya keterkaitan permodalan, penyaluran kredit/ekspansi aset, kualitas aset, likuiditas, dan profitabilitas) tanpa menyalin ulang isi tabel mentah baris demi baris karena tabel lengkap sudah dirakit otomatis di bawah narasi.
6. Pada `direct_answer`, jawab langsung pertanyaan pengguna secara padat (2-4 kalimat) dengan angka & sitasi halaman yang tepat.
7. Pada `conclusion`, berikan kesimpulan objektif serta keterbatasan analisis; DILARANG memberikan rekomendasi beli/jual saham atau target harga."""


def format_ojk_category(category: str | None) -> str:
    """Ubah kode kategori snake_case (mis. `sangat_kuat`, `ideal_ojk`) menjadi label rapi."""
    raw = (category or "").strip()
    if not raw:
        return "Terhitung"
    return _OJK_CATEGORY_LABELS.get(raw.lower(), raw.replace("_", " ").title())


# ----------------------------------------------------------------- Helper format & identitas


def format_id_number(value: float, decimals: int = 2) -> str:
    """Format angka dengan konvensi Indonesia (titik ribuan, koma desimal)."""
    neg = value < 0
    raw = f"{abs(value):,.{decimals}f}"
    indo = raw.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{indo}" if neg else indo


def format_idr_million(value: float) -> str:
    """Format nilai moneter terstandar (juta Rupiah) agar konsisten & mudah dibaca."""
    decimals = 0 if abs(value) >= 1000 else 2
    return f"Rp {format_id_number(value, decimals)} juta"


def format_idr_for_llm(value_million: float) -> str:
    """Sertakan nilai setara triliun yang dihitung Python agar LLM tidak salah konversi skala."""
    base = format_idr_million(value_million)
    if abs(value_million) >= 1_000_000:
        trillion = value_million / 1_000_000.0
        return f"{base} (setara Rp {format_id_number(trillion, 2)} triliun)"
    return base


def format_pages(pages: Sequence[int] | None) -> str:
    """Format daftar nomor halaman PDF asli (`hal. 16, 594`) tanpa duplikat."""
    clean = sorted({int(p) for p in (pages or []) if isinstance(p, (int, float)) and int(p) > 0})
    if not clean:
        return "sumber tidak tersedia"
    return "hal. " + ", ".join(str(p) for p in clean)


def format_basis(basis: str | None) -> str:
    mapping = {
        "bank_only": "Bank (Entitas Induk)",
        "consolidated": "Konsolidasian",
    }
    return mapping.get((basis or "").strip().lower(), "-")


def _normalize_url_key(url: str) -> str:
    cleaned = url.strip().rstrip(".,;:!?")
    p = urlparse(cleaned)
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path.rstrip("/")
    query = f"?{p.query}" if p.query else ""
    return f"{host}{path}{query}"


def _escape_md_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def resolve_report_identity(
    ticker: str,
    years: Sequence[int] | None = None,
    *,
    sector: str | None = None,
    company: str | None = None,
) -> dict[str, Any]:
    """Baca nama perusahaan & sektor secara dinamis dari metadata.json (bebas hardcode, R10)."""
    code = (ticker or "").strip().lower()
    candidate_years = sorted({int(y) for y in years}, reverse=True) if years else sorted(config.YEARS, reverse=True)
    meta: dict[str, Any] = {}
    if code:
        for y in candidate_years:
            p = config.report_metadata(y, code)
            if p.exists():
                meta = json.loads(p.read_text(encoding="utf-8"))
                break
        if not meta:
            matches = sorted(config.DATA_MARKDOWN.glob(f"{code}_*.metadata.json"), reverse=True)
            if matches:
                meta = json.loads(matches[0].read_text(encoding="utf-8"))

    resolved_company = (company or meta.get("company") or (code.upper() if code else "Emiten")).strip()
    resolved_sector = (sector or meta.get("sector") or "general").strip().lower()
    profile = rp.get_profile(resolved_sector)
    return {
        "ticker": code,
        "company": resolved_company,
        "sector": profile.sector,
        "profile_label": profile.label,
        "profile_validated": profile.validated,
        "profile_warning": profile.warning_label,
    }


def _extract_target_years(
    years: int | Sequence[int] | None,
    ratios: dict[str, Any] | None,
    extracted_data: dict[int, dict[str, Any]] | None,
) -> list[int]:
    if isinstance(years, int) and not isinstance(years, bool):
        return [years]
    if isinstance(years, Sequence) and not isinstance(years, str):
        parsed = sorted({int(y) for y in years})
        if parsed:
            return parsed
    if ratios and ratios.get("years"):
        return sorted({int(y) for y in ratios["years"]})
    if ratios and ratios.get("by_year"):
        return sorted({int(y) for y in ratios["by_year"]})
    if extracted_data:
        return sorted({int(y) for y in extracted_data})
    return []


# ----------------------------------------------------------------- Lapis 1: Tabel & sumber deterministik


def render_ratios_table(ratios: dict[str, Any] | None) -> str:
    """Rakit tabel Markdown rasio keuangan, ambang OJK, & sitasi halaman secara deterministik (14.2, 14.3)."""
    if not ratios or not ratios.get("by_year"):
        return "_Tidak ada data rasio keuangan yang berhasil dihitung._"

    by_year = {int(y): v for y, v in ratios["by_year"].items()}
    years = sorted(by_year)
    profile = rp.get_profile(ratios.get("sector"))
    seen: list[str] = list(profile.ratio_names)
    for y in years:
        for rname in by_year[y]:
            if rname not in seen:
                seen.append(rname)

    header = ["Rasio", *[str(y) for y in years], "Ambang OJK", "Status Terbaru", "Sumber"]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] + ["---:" for _ in years] + ["---", "---", "---"]) + "|",
    ]

    latest_y = years[-1]
    insufficient_notes: list[str] = []
    basis_notes: list[str] = []

    for name in seen:
        row_cells = [f"**{name}**"]
        all_pages: set[int] = set()
        benchmark = "-"
        latest_cat = "-"
        basis_seen: str = ""

        for y in years:
            item = by_year[y].get(name)
            if not item:
                row_cells.append("Tidak tersedia")
                continue
            if item.get("ojk_benchmark") and benchmark == "-":
                benchmark = str(item["ojk_benchmark"])
            if item.get("basis_used") and not basis_seen:
                basis_seen = str(item["basis_used"])

            if item.get("status") == "ok" and item.get("value") is not None:
                row_cells.append(f"{format_id_number(float(item['value']), 2)}%")
                all_pages.update(int(p) for p in (item.get("source_pages") or []) if int(p) > 0)
            else:
                st = item.get("status") or "insufficient_data"
                row_cells.append(f"Tidak tersedia (*{st}*)")
                missing = item.get("missing_inputs") or []
                detail = f"input kurang: {', '.join(missing)}" if missing else (item.get("interpretation") or st)
                insufficient_notes.append(f"- **{name} ({y})**: tidak dihitung ({detail}).")

        latest_item = by_year[latest_y].get(name) or {}
        if latest_item.get("status") == "ok":
            latest_cat = format_ojk_category(latest_item.get("ojk_category"))
            if latest_item.get("meets_ojk") is True:
                latest_cat += " (Memenuhi)"
            elif latest_item.get("meets_ojk") is False:
                latest_cat += " (Perlu Perhatian)"
        else:
            latest_cat = "Data tidak cukup"

        src_cell = format_pages(sorted(all_pages)) if all_pages else "-"
        row_cells.extend([_escape_md_cell(benchmark), _escape_md_cell(latest_cat), _escape_md_cell(src_cell)])
        lines.append("| " + " | ".join(row_cells) + " |")
        clean_basis = re.sub(r"\s*\[(?:saldo akhir|rata-rata)[^\]]*\]\s*$", "", basis_seen).strip()
        if clean_basis:
            basis_notes.append(f"- **{name}:** {clean_basis}")

    out = "\n".join(lines)
    extras: list[str] = []
    if basis_notes:
        extras.append("**Basis & Formula Perhitungan:**\n" + "\n".join(basis_notes))
    if insufficient_notes:
        extras.append("**Catatan Rasio Tidak Dihitung (Transparansi Anti-Halusinasi):**\n" + "\n".join(insufficient_notes))
    if extras:
        out += "\n\n" + "\n\n".join(extras)
    return out


def render_metrics_table(
    extracted_data: dict[int, dict[str, Any]] | None,
    sector: str | None,
    target_years: Sequence[int] | None = None,
) -> str:
    """Rakit tabel Markdown komponen metrik keuangan terstandar beserta sitasi halaman (14.2)."""
    if not extracted_data:
        return "_Tidak ada data komponen laporan keuangan yang tersedia._"

    norm = {int(y): v for y, v in extracted_data.items()}
    years = sorted(y for y in (target_years or sorted(norm)) if y in norm)
    if not years:
        years = sorted(norm)

    profile = rp.get_profile(sector)
    ordered_keys: list[str] = [k for k in profile.metrics if any(k in norm[y] for y in years)]
    for y in years:
        for k in norm[y]:
            if k not in ordered_keys:
                ordered_keys.append(k)
    if not ordered_keys:
        return "_Tidak ada komponen metrik keuangan yang terekstrak untuk periode target._"

    header = ["Komponen Keuangan", "Basis", *[str(y) for y in years], "Sumber"]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---", "---"] + ["---:" for _ in years] + ["---"]) + "|",
    ]
    has_merged_warn = False

    for key in ordered_keys:
        spec = profile.metrics.get(key)
        label = spec.label if spec else key
        basis_val = spec.basis if spec else None
        all_pages: set[int] = set()
        row_cells: list[str] = []
        merged_flag = False

        for y in years:
            entry = norm[y].get(key)
            if not entry or entry.get("status") != "ok":
                row_cells.append("Tidak tersedia")
                continue
            if not basis_val:
                basis_val = entry.get("basis")
            all_pages.update(int(p) for p in (entry.get("source_pages") or []) if int(p) > 0)
            if entry.get("merged_cells_warning"):
                merged_flag = True
                has_merged_warn = True
            if entry.get("value_percent") is not None:
                row_cells.append(f"{format_id_number(float(entry['value_percent']), 2)}%")
            elif entry.get("value_million_idr") is not None:
                row_cells.append(format_idr_million(float(entry["value_million_idr"])))
            else:
                row_cells.append("Tidak tersedia")

        src_txt = format_pages(sorted(all_pages)) if all_pages else "-"
        if merged_flag:
            src_txt += " (catatan: sel gabungan)"
        lines.append(
            "| "
            + " | ".join([_escape_md_cell(label), _escape_md_cell(format_basis(basis_val)), *row_cells, _escape_md_cell(src_txt)])
            + " |"
        )

    out = "\n".join(lines)
    comp_years = sorted(y for y in norm if y not in years)
    notes: list[str] = []
    if comp_years:
        notes.append(
            f"*Catatan: saldo pembanding tahun {', '.join(map(str, comp_years))} turut digunakan secara internal "
            f"untuk menghitung rata-rata penyebut rasio (ROA, ROE, NIM).*"
        )
    if has_merged_warn:
        notes.append("*Catatan: penanda sel gabungan menunjukkan tabel sumber PDF memiliki baris/sel rapat hasil parsing Docling.*")
    if notes:
        out += "\n\n" + "\n".join(notes)
    return out


def render_trends_table(ratios: dict[str, Any] | None) -> str:
    """Rakit tabel Markdown tren antar tahun dari hasil Financial Analyst Agent."""
    trends = (ratios or {}).get("trends") or {}
    valid_items = [(k, v) for k, v in trends.items() if isinstance(v, dict) and "delta_pp" in v]
    if not valid_items:
        return (
            "_Data pembanding multi-tahun belum tersedia (hanya satu tahun terhitung atau rasio kurang dari dua tahun), "
            "sehingga tabel perubahan tren antar tahun tidak dapat dibentuk._"
        )

    lines = [
        "| Rasio | Periode | Nilai Awal | Nilai Akhir | Perubahan | Arah Tren |",
        "|---|---|---:|---:|---:|---|",
    ]
    for name, tr in valid_items:
        delta = float(tr["delta_pp"])
        sign = "+" if delta > 0 else ""
        direction = _DIRECTION_LABELS.get(str(tr.get("direction", "")), str(tr.get("direction", "-")))
        lines.append(
            f"| **{name}** | {tr['start_year']}–{tr['end_year']} | "
            f"{format_id_number(float(tr['start_value']), 2)}% | "
            f"{format_id_number(float(tr['end_value']), 2)}% | "
            f"{sign}{format_id_number(delta, 2)} pp | {direction} |"
        )
    return "\n".join(lines)


def render_market_sources(
    market_context: Sequence[dict[str, Any]] | None,
    market_errors: Sequence[str] | None = None,
) -> str:
    """Rakit daftar konteks pasar & regulasi dengan URL + tanggal terkunci dari Tavily (13.3, 14.2)."""
    items = [m for m in (market_context or []) if isinstance(m, dict) and m.get("url")]
    if not items:
        msg = (
            "Konteks pasar eksternal tidak tersedia saat analisis dijalankan "
            "(tidak ada artikel relevan yang lolos penyaringan atau layanan pencarian eksternal tidak aktif)."
        )
        if market_errors:
            clean_err = "; ".join(str(e).strip() for e in market_errors if str(e).strip())
            if clean_err:
                msg += f" Catatan sistem: _{clean_err}_."
        return msg

    lines: list[str] = []
    for idx, item in enumerate(items, start=1):
        title = str(item.get("title") or "Artikel Tanpa Judul").strip()
        url = str(item.get("url") or "").strip()
        domain = str(item.get("source_domain") or urlparse(url).netloc).strip()
        pub_date = str(item.get("published_date") or "tanggal tidak tersedia").strip()
        cat = _CATEGORY_LABELS.get(str(item.get("category") or ""), str(item.get("category") or "-"))
        sent = str(item.get("sentiment") or "netral").strip().capitalize()
        summary = str(item.get("summary") or "").strip()
        lines.append(
            f"{idx}. **[{title}]({url})**  \n"
            f"   Sumber: `{domain}` · Tanggal: `{pub_date}` · Kategori: {cat} · Sentimen: {sent}  \n"
            f"   Ringkasan: {summary}"
        )
    return "\n".join(lines)


def render_source_index(
    extracted_data: dict[int, dict[str, Any]] | None,
    ratios: dict[str, Any] | None,
    market_context: Sequence[dict[str, Any]] | None,
    ticker: str,
) -> str:
    """Indeks ringkas seluruh halaman PDF & URL eksternal yang dirujuk laporan (14.2)."""
    pages_by_year: dict[int, set[int]] = {}
    for y, metrics in (extracted_data or {}).items():
        yi = int(y)
        for entry in (metrics or {}).values():
            if not isinstance(entry, dict) or entry.get("status") != "ok":
                continue
            for p in entry.get("source_pages") or []:
                if int(p) > 0:
                    pages_by_year.setdefault(yi, set()).add(int(p))

    for y, rdict in ((ratios or {}).get("by_year") or {}).items():
        yi = int(y)
        for item in (rdict or {}).values():
            if not isinstance(item, dict) or item.get("status") != "ok":
                continue
            for p in item.get("source_pages") or []:
                if int(p) > 0:
                    pages_by_year.setdefault(yi, set()).add(int(p))

    lines: list[str] = []
    code_upper = (ticker or "EMITEN").upper()
    for y in sorted(pages_by_year):
        lines.append(f"- **Laporan Tahunan {code_upper} {y}:** {format_pages(sorted(pages_by_year[y]))}")

    url_items = [m for m in (market_context or []) if isinstance(m, dict) and m.get("url")]
    if url_items:
        lines.append(f"- **Sumber Eksternal Terverifikasi (Tavily):** {len(url_items)} tautan (tercantum pada Bagian 4).")
    else:
        lines.append("- **Sumber Eksternal Terverifikasi (Tavily):** 0 tautan (konteks pasar tidak tersedia).")

    return "\n".join(lines) if lines else "- Tidak ada sumber dokumen yang berhasil diverifikasi."


# ----------------------------------------------------------------- Lapis 2: Narasi LLM + Fallback Deterministik


def _build_llm_payload(
    *,
    identity: dict[str, Any],
    query: str,
    target_years: list[int],
    extracted_data: dict[int, dict[str, Any]] | None,
    ratios: dict[str, Any] | None,
    market_context: Sequence[dict[str, Any]] | None,
    retrieved_chunks: Sequence[dict[str, Any]] | None,
) -> str:
    """Susun prompt terstruktur ringkas dari data terverifikasi Python untuk narasi LLM."""
    lines = [
        f"EMITEN: {identity['company']} ({identity['ticker'].upper() or '-'})",
        f"SEKTOR: {identity['sector']} ({identity['profile_label']}) | validated={identity['profile_validated']}",
        f"PERIODE TARGET: {', '.join(map(str, target_years)) if target_years else '-'}",
    ]
    if not identity["profile_validated"] and identity.get("profile_warning"):
        lines.append(f"PERINGATAN PROFIL WAJIB: {identity['profile_warning']}")
    if query:
        lines.append(f"\nPERTANYAAN PENGGUNA:\n{query}")

    lines.append("\n=== DATA TERVERIFIKASI: RASIO KEUANGAN & AMBANG OJK ===")
    by_year = {int(y): v for y, v in ((ratios or {}).get("by_year") or {}).items()}
    if by_year:
        for y in sorted(by_year):
            lines.append(f"Tahun {y}:")
            for name, r in by_year[y].items():
                if r.get("status") == "ok" and r.get("value") is not None:
                    bench = f" | ambang={r.get('ojk_benchmark')}" if r.get("ojk_benchmark") else ""
                    lines.append(
                        f"  - {name}: {format_id_number(float(r['value']), 2)}%{bench} | "
                        f"{r.get('interpretation', '')} | ({format_pages(r.get('source_pages'))})"
                    )
                else:
                    missing = ", ".join(r.get("missing_inputs") or [])
                    lines.append(
                        f"  - {name}: TIDAK TERSEDIA (status={r.get('status')}, input kurang={missing or '-'})"
                    )
    else:
        lines.append("  (Tidak ada rasio terhitung)")

    lines.append("\n=== DATA TERVERIFIKASI: TREN ANTAR TAHUN ===")
    trends = (ratios or {}).get("trends") or {}
    trend_lines = []
    for name, tr in trends.items():
        if isinstance(tr, dict) and "delta_pp" in tr:
            d = float(tr["delta_pp"])
            sign = "+" if d > 0 else ""
            trend_lines.append(
                f"  - {name}: {tr['start_year']}={format_id_number(float(tr['start_value']), 2)}% -> "
                f"{tr['end_year']}={format_id_number(float(tr['end_value']), 2)}% "
                f"({tr['direction']} {sign}{format_id_number(d, 2)} pp)"
            )
    lines.extend(trend_lines or ["  (Data tren multi-tahun tidak tersedia)"])

    lines.append("\n=== DATA TERVERIFIKASI: METRIK KEUANGAN KUNCI ===")
    norm_ext = {int(y): v for y, v in (extracted_data or {}).items()}
    profile = rp.get_profile(identity["sector"])
    for y in target_years:
        if y not in norm_ext:
            continue
        lines.append(f"Tahun {y}:")
        for key, entry in norm_ext[y].items():
            if not isinstance(entry, dict):
                continue
            spec = profile.metrics.get(key)
            label = spec.label if spec else key
            if entry.get("status") == "ok":
                if entry.get("value_percent") is not None:
                    vtxt = f"{format_id_number(float(entry['value_percent']), 2)}%"
                elif entry.get("value_million_idr") is not None:
                    vtxt = format_idr_for_llm(float(entry["value_million_idr"]))
                else:
                    vtxt = "tidak tersedia"
                lines.append(f"  - {label}: {vtxt} ({format_pages(entry.get('source_pages'))})")
            else:
                lines.append(f"  - {label}: tidak tersedia (status={entry.get('status')})")

    lines.append("\n=== KONTEKS PASAR EKSTERNAL TERVERIFIKASI ===")
    valid_market = [m for m in (market_context or []) if isinstance(m, dict) and m.get("url")]
    if valid_market:
        for i, m in enumerate(valid_market, start=1):
            lines.append(
                f"  [{i}] {m.get('title')} | domain={m.get('source_domain')} | tanggal={m.get('published_date')} | "
                f"kategori={m.get('category')} | sentimen={m.get('sentiment')} | url={m.get('url')}\n"
                f"      ringkasan={m.get('summary')}"
            )
    else:
        lines.append("  KOSONG (konteks pasar eksternal tidak tersedia saat analisis dijalankan)")

    # Sertakan potongan terbatas chunk dokumen agar pertanyaan kualitatif RAGAS tetap tergrounding
    if retrieved_chunks:
        lines.append("\n=== CUPLIKAN DOKUMEN PENDUKUNG (TERBATAS) ===")
        for ch in list(retrieved_chunks)[:4]:
            if not isinstance(ch, dict):
                continue
            txt = str(ch.get("text") or ch.get("content") or "").replace("\n", " ").strip()[:450]
            if not txt:
                continue
            pgs = format_pages(ch.get("pages") or ch.get("source_pages"))
            hdr = str(ch.get("header_path") or ch.get("source_header") or "").strip()
            lines.append(f"  - [{pgs} | {hdr}]: {txt}")

    return "\n".join(lines)


def build_deterministic_narrative(
    *,
    identity: dict[str, Any],
    query: str,
    target_years: list[int],
    ratios: dict[str, Any] | None,
    market_context: Sequence[dict[str, Any]] | None,
) -> ReportNarrative:
    """Narasi deterministik bebas halusinasi (dipakai mode offline & fallback jika LLM gagal)."""
    by_year = {int(y): v for y, v in ((ratios or {}).get("by_year") or {}).items()}
    trends = (ratios or {}).get("trends") or {}
    latest_y = max(by_year) if by_year else (max(target_years) if target_years else None)
    period_txt = (
        f"{min(target_years)}–{max(target_years)}"
        if len(target_years) > 1
        else (str(target_years[0]) if target_years else "-")
    )

    ok_latest: list[str] = []
    missing_latest: list[str] = []
    if latest_y is not None and latest_y in by_year:
        for name, item in by_year[latest_y].items():
            if item.get("status") == "ok" and item.get("value") is not None:
                ok_latest.append(
                    f"{name} sebesar {format_id_number(float(item['value']), 2)}% ({format_pages(item.get('source_pages'))})"
                )
            else:
                missing_latest.append(name)

    unval_prefix = ""
    if not identity["profile_validated"]:
        unval_prefix = (
            f"Catatan penting: profil rasio sektor {identity['profile_label']} berstatus belum divalidasi "
            f"(validasi penelitian ini difokuskan pada sektor perbankan). "
        )

    if ok_latest:
        direct_answer = (
            f"{unval_prefix}Berdasarkan laporan keuangan {identity['company']} ({identity['ticker'].upper()}) "
            f"periode {period_txt}, indikator utama pada tahun {latest_y} mencakup {', '.join(ok_latest[:4])}."
        )
        if missing_latest:
            direct_answer += f" Sementara itu, rasio {', '.join(missing_latest)} tidak dihitung karena data komponen tidak lengkap."
    else:
        direct_answer = (
            f"{unval_prefix}Data rasio keuangan {identity['company']} ({identity['ticker'].upper()}) "
            f"untuk periode {period_txt} belum dapat dihitung karena komponen keuangan yang diperlukan tidak tersedia."
        )

    exec_summary = (
        f"{unval_prefix}Analisis keuangan {identity['company']} ({identity['ticker'].upper()}) mencakup periode "
        f"{period_txt} dengan profil sektor {identity['profile_label']}. "
    )
    if ok_latest:
        exec_summary += f"Pada tahun terbaru ({latest_y}), rasio terverifikasi meliputi {', '.join(ok_latest)}."
    else:
        exec_summary += "Tidak terdapat rasio keuangan yang dapat diverifikasi sepenuhnya pada periode ini."

    ratio_parts: list[str] = []
    if latest_y is not None and latest_y in by_year:
        for name, item in by_year[latest_y].items():
            if item.get("status") == "ok" and item.get("value") is not None:
                ratio_parts.append(
                    f"{item.get('interpretation', name)} ({format_pages(item.get('source_pages'))})."
                )
            else:
                missing = ", ".join(item.get("missing_inputs") or [])
                ratio_parts.append(
                    f"{name} tidak dihitung karena keterbatasan komponen data ({missing or item.get('status')})."
                )
    ratio_analysis = (
        " ".join(ratio_parts)
        if ratio_parts
        else "Perhitungan rasio terhadap ambang batas tidak dapat dilakukan karena data masukan tidak mencukupi."
    )

    trend_parts: list[str] = []
    for name, tr in trends.items():
        if isinstance(tr, dict) and "delta_pp" in tr:
            d = float(tr["delta_pp"])
            sign = "+" if d > 0 else ""
            trend_parts.append(
                f"{name} bergerak {tr['direction']} sebesar {sign}{format_id_number(d, 2)} pp "
                f"dari {format_id_number(float(tr['start_value']), 2)}% ({tr['start_year']}) "
                f"menjadi {format_id_number(float(tr['end_value']), 2)}% ({tr['end_year']})."
            )
    trend_analysis = (
        " ".join(trend_parts)
        if trend_parts
        else "Analisis tren multi-tahun belum dapat dilakukan karena hanya satu tahun data yang tersedia."
    )

    valid_market = [m for m in (market_context or []) if isinstance(m, dict) and m.get("url")]
    if valid_market:
        domains = sorted({str(m.get("source_domain") or "") for m in valid_market if m.get("source_domain")})
        market_synthesis = (
            f"Terdapat {len(valid_market)} sumber konteks pasar dan regulasi terverifikasi dari "
            f"{', '.join(domains)} yang relevan dengan {identity['company']} dan sektornya. "
            f"Sorotan utama meliputi: {valid_market[0].get('summary') or valid_market[0].get('title')} "
            f"(rincian tautan tercantum pada daftar sumber di bawah)."
        )
    else:
        market_synthesis = (
            "Konteks pasar eksternal tidak tersedia saat analisis dijalankan, sehingga pembahasan ini "
            "berfokus sepenuhnya pada data terverifikasi dari laporan tahunan emiten."
        )

    conclusion = (
        f"{unval_prefix}Secara keseluruhan, evaluasi {identity['company']} ({identity['ticker'].upper()}) "
        f"periode {period_txt} telah disusun berdasarkan angka laporan tahunan terverifikasi dan perhitungan "
        f"rasio deterministik. Hasil ini bersifat informatif untuk analisis akademis/fundamental dan bukan "
        f"merupakan rekomendasi beli atau jual saham."
    )
    return ReportNarrative(
        direct_answer=direct_answer,
        executive_summary=exec_summary,
        ratio_analysis=ratio_analysis,
        trend_analysis=trend_analysis,
        market_synthesis=market_synthesis,
        conclusion=conclusion,
    )


def generate_narrative(
    *,
    identity: dict[str, Any],
    query: str,
    target_years: list[int],
    extracted_data: dict[int, dict[str, Any]] | None,
    ratios: dict[str, Any] | None,
    market_context: Sequence[dict[str, Any]] | None,
    retrieved_chunks: Sequence[dict[str, Any]] | None,
    stats: dict[str, Any],
    use_llm: bool = True,
    llm=None,
) -> tuple[ReportNarrative, bool]:
    """Hasilkan narasi analitis terstruktur lewat LLM (fallback deterministik bila gagal)."""
    if not use_llm:
        stats["used_fallback_narrative"] = True
        return (
            build_deterministic_narrative(
                identity=identity,
                query=query,
                target_years=target_years,
                ratios=ratios,
                market_context=market_context,
            ),
            True,
        )

    payload = _build_llm_payload(
        identity=identity,
        query=query,
        target_years=target_years,
        extracted_data=extracted_data,
        ratios=ratios,
        market_context=market_context,
        retrieved_chunks=retrieved_chunks,
    )
    active_llm = llm or config.get_llm(
        effort=config.REASONING_EFFORT,
        max_tokens=max(config.MAX_TOKENS, 6144),
    )
    messages = [SystemMessage(REPORTING_SYSTEM_PROMPT), HumanMessage(payload)]

    parsed: ReportNarrative | None = None
    for method in ("json_schema", "json_mode"):
        try:
            stats["llm_calls"] += 1
            chain = active_llm.with_structured_output(ReportNarrative, method=method, include_raw=True)
            msgs = messages
            if method == "json_mode":
                hint = json.dumps(ReportNarrative.model_json_schema(), ensure_ascii=False)
                msgs = [
                    SystemMessage(REPORTING_SYSTEM_PROMPT + f"\nKeluarkan HANYA JSON valid sesuai skema:\n{hint}"),
                    messages[1],
                ]
            res = chain.invoke(msgs)
            raw_msg = res.get("raw") if isinstance(res, dict) else None
            usage = getattr(raw_msg, "usage_metadata", None) or {}
            stats["input_tokens"] += int(usage.get("input_tokens", 0))
            stats["output_tokens"] += int(usage.get("output_tokens", 0))
            stats["total_tokens"] += int(usage.get("total_tokens", 0))
            cand = res.get("parsed") if isinstance(res, dict) else res
            if cand is not None and isinstance(cand, ReportNarrative):
                if cand.executive_summary.strip() and cand.conclusion.strip():
                    parsed = cand
                    break
        except Exception as e:
            stats["narrative_errors"].append(f"LLM narasi ({method}) gagal: {e}")
            if "connection" in str(e).lower():
                break

    if parsed is None:
        stats["used_fallback_narrative"] = True
        return (
            build_deterministic_narrative(
                identity=identity,
                query=query,
                target_years=target_years,
                ratios=ratios,
                market_context=market_context,
            ),
            True,
        )
    return parsed, False


# ----------------------------------------------------------------- Lapis 3: Audit Anti-Halusinasi & Perakitan


def sanitize_and_audit_urls(text: str, allowed_urls: Sequence[str]) -> tuple[str, list[str]]:
    """Hapus URL tak terverifikasi yang dikarang LLM di luar whitelist `market_context` (14.2)."""
    allowed_keys = {_normalize_url_key(u) for u in allowed_urls if u}
    stripped: list[str] = []

    def _replace_md(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if _normalize_url_key(url) in allowed_keys:
            return match.group(0)
        stripped.append(url)
        return f"{label} [tautan tidak terverifikasi dihapus]"

    cleaned = _URL_MD_RE.sub(_replace_md, text)

    def _replace_raw(match: re.Match[str]) -> str:
        raw_url = match.group(1)
        trimmed = raw_url.rstrip(".,;:!?")
        suffix = raw_url[len(trimmed):]
        if _normalize_url_key(trimmed) in allowed_keys:
            return raw_url
        stripped.append(trimmed)
        return f"[tautan tidak terverifikasi dihapus]{suffix}"

    # Lindungi link Markdown valid yang sudah lolos agar tidak diganti ulang
    protected: list[str] = []

    def _stash_md(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"__VALID_MD_LINK_{len(protected) - 1}__"

    cleaned = _URL_MD_RE.sub(_stash_md, cleaned)
    cleaned = _URL_RAW_RE.sub(_replace_raw, cleaned)
    for idx, orig in enumerate(protected):
        cleaned = cleaned.replace(f"__VALID_MD_LINK_{idx}__", orig)

    return cleaned, stripped


def audit_report(
    markdown: str,
    *,
    ratios: dict[str, Any] | None,
    market_context: Sequence[dict[str, Any]] | None,
    profile_validated: bool,
    stripped_urls: Sequence[str],
    is_failure_report: bool = False,
) -> dict[str, Any]:
    """Audit otomatis pasca-generasi atas struktur 5 bagian, sitasi halaman, R17, & URL (14.1-14.3)."""
    sections_present = {h: (h in markdown) for h in REQUIRED_SECTION_HEADINGS}
    all_sections_present = all(sections_present.values())

    has_unvalidated_label = True if profile_validated else ("belum divalidasi" in markdown.lower())
    page_citations = _PAGE_CITE_RE.findall(markdown)

    allowed_keys = {
        _normalize_url_key(str(m["url"]))
        for m in (market_context or [])
        if isinstance(m, dict) and m.get("url")
    }
    found_urls = [u.rstrip(".,;:!?") for u in _URL_RAW_RE.findall(markdown)]
    unauthorized_remaining = [u for u in found_urls if _normalize_url_key(u) not in allowed_keys]
    verified_urls = {
        _normalize_url_key(u) for u in found_urls if _normalize_url_key(u) in allowed_keys
    }

    ratios_ok = 0
    ratios_total = 0
    for rdict in ((ratios or {}).get("by_year") or {}).values():
        for item in (rdict or {}).values():
            ratios_total += 1
            if isinstance(item, dict) and item.get("status") == "ok":
                ratios_ok += 1

    citations_ok = True if (is_failure_report or ratios_ok == 0) else (len(page_citations) > 0)
    passed = (
        all_sections_present
        and has_unvalidated_label
        and citations_ok
        and len(unauthorized_remaining) == 0
    )

    return {
        "passed": passed,
        "all_sections_present": all_sections_present,
        "sections_present": sections_present,
        "profile_validated": profile_validated,
        "has_unvalidated_label": has_unvalidated_label,
        "page_citation_count": len(page_citations),
        "verified_url_count": len(verified_urls),
        "stripped_urls": list(stripped_urls),
        "unauthorized_urls_remaining": unauthorized_remaining,
        "ratios_ok": ratios_ok,
        "ratios_total": ratios_total,
        "is_failure_report": is_failure_report,
        "markdown_chars": len(markdown),
    }


def _render_extraction_failure_report(
    *,
    identity: dict[str, Any],
    query: str,
    target_years: list[int],
    extraction_errors: Sequence[str] | None,
    market_context: Sequence[dict[str, Any]] | None,
    market_errors: Sequence[str] | None,
) -> str:
    """Laporan kegagalan yang jujur & terstruktur 5 bagian jika ekstraksi gagal total (15.2)."""
    period_txt = ", ".join(map(str, target_years)) if target_years else "-"
    err_lines = [f"- {e}" for e in (extraction_errors or []) if str(e).strip()]
    err_block = "\n".join(err_lines) if err_lines else "- Data keuangan terverifikasi tidak ditemukan pada pustaka laporan."
    warn_banner = ""
    if not identity["profile_validated"] and identity.get("profile_warning"):
        warn_banner = f"\n> **PERINGATAN (Profil Belum Divalidasi):** {identity['profile_warning']}\n"

    parts = [
        f"# Laporan Analisis Keuangan — {identity['company']} ({identity['ticker'].upper() or '-'})",
        f"**Periode:** {period_txt} | **Sektor:** {identity['profile_label']} | **Status:** Ekstraksi Tidak Lengkap",
        warn_banner.strip(),
        f"> **Pertanyaan Pengguna:** {query}\n>\n> **Jawaban Ringkas:** Analisis keuangan belum dapat diselesaikan karena data laporan keuangan yang dibutuhkan gagal diekstrak secara terverifikasi."
        if query
        else "",
        "## 1. Ringkasan Eksekutif\n\n"
        f"Sistem tidak dapat menyusun analisis kuantitatif untuk **{identity['company']} ({identity['ticker'].upper() or '-'})** "
        f"periode {period_txt} karena tahap ekstraksi data laporan keuangan tidak menghasilkan angka yang terverifikasi. "
        "Sesuai prinsip anti-halusinasi, sistem menolak menebak angka atau menghitung rasio dari data kosong.\n\n"
        f"**Rincian kendala ekstraksi:**\n{err_block}",
        "## 2. Rasio Keuangan & Interpretasi\n\n"
        "_Tidak ada rasio keuangan yang dapat dihitung karena seluruh data masukan tidak tersedia._",
        "## 3. Tren Antar Tahun\n\n"
        "_Analisis tren antar tahun tidak dapat dilakukan karena data rasio tidak tersedia._",
        "## 4. Konteks Pasar & Regulasi\n\n"
        + render_market_sources(market_context, market_errors),
        "## 5. Kesimpulan\n\n"
        "Pastikan dokumen laporan tahunan emiten dan tahun buku yang diminta telah diunggah serta terindeks dengan "
        "benar di pustaka sistem sebelum mengulangi permintaan analisis. Laporan ini bukan merupakan rekomendasi "
        "investasi.",
    ]
    return "\n\n".join(p for p in parts if p)


def format_telegram_summary(
    *,
    identity: dict[str, Any],
    query: str,
    target_years: list[int],
    direct_answer: str,
    ratios: dict[str, Any] | None,
    market_context: Sequence[dict[str, Any]] | None,
    is_failure_report: bool = False,
    max_chars: int = 3800,
) -> str:
    """Ringkasan HTML siap-Telegram (<= 4.096 karakter, bebas tabel Markdown, persiapan 16.3d)."""
    cap = min(max_chars, config.TELEGRAM_MAX_MESSAGE_CHARS - 200)
    esc = lambda s: html.escape(str(s), quote=True)
    period_txt = (
        f"{min(target_years)}–{max(target_years)}"
        if len(target_years) > 1
        else (str(target_years[0]) if target_years else "-")
    )

    lines: list[str] = [
        f"<b>Laporan Analisis Keuangan — {esc(identity['company'])} ({esc(identity['ticker'].upper() or '-')})</b>",
        f"<i>Periode: {esc(period_txt)} | Sektor: {esc(identity['profile_label'])}</i>",
    ]
    if not identity["profile_validated"] and identity.get("profile_warning"):
        lines.append(f"⚠️ <b>Perhatian (Belum Divalidasi):</b> {esc(identity['profile_warning'])}")

    if query:
        lines.append(f"\n<b>Pertanyaan:</b> {esc(query[:220])}")

    if is_failure_report:
        lines.append(
            "\n<b>Status:</b> Analisis rasio tidak dapat diselesaikan karena data keuangan gagal diekstrak secara terverifikasi."
        )
    else:
        if direct_answer:
            lines.append(f"\n<b>Ringkasan:</b>\n{esc(direct_answer)}")

        by_year = {int(y): v for y, v in ((ratios or {}).get("by_year") or {}).items()}
        trends = (ratios or {}).get("trends") or {}
        if by_year:
            latest_y = max(by_year)
            lines.append(f"\n<b>Rasio Keuangan ({latest_y}):</b>")
            for name, item in by_year[latest_y].items():
                if item.get("status") == "ok" and item.get("value") is not None:
                    val_txt = f"{format_id_number(float(item['value']), 2)}%"
                    cat = format_ojk_category(item.get("ojk_category")) if item.get("ojk_category") else ""
                    tr = trends.get(name) or {}
                    tr_txt = ""
                    if "delta_pp" in tr:
                        d = float(tr["delta_pp"])
                        sign = "+" if d > 0 else ""
                        tr_txt = f" | tren {sign}{format_id_number(d, 2)} pp"
                    pgs = format_pages(item.get("source_pages"))
                    lines.append(
                        f"• <b>{esc(name)}</b>: <code>{esc(val_txt)}</code>"
                        f"{f' ({esc(cat)})' if cat else ''}{esc(tr_txt)} [{esc(pgs)}]"
                    )
                else:
                    lines.append(f"• <b>{esc(name)}</b>: <i>data tidak cukup</i>")

    valid_market = [m for m in (market_context or []) if isinstance(m, dict) and m.get("url")]
    if valid_market:
        lines.append(f"\n<b>Konteks Pasar &amp; Regulasi ({len(valid_market)} sumber):</b>")
        for m in valid_market[:3]:
            title = esc(str(m.get("title") or "Sumber")[:90])
            url = esc(str(m.get("url")))
            dom = esc(str(m.get("source_domain") or ""))
            lines.append(f"• <a href=\"{url}\">{title}</a> (<i>{dom}</i>)")
    else:
        lines.append("\n<b>Konteks Pasar:</b> <i>tidak tersedia saat analisis dijalankan.</i>")

    footer = (
        "\n<i>Laporan lengkap beserta tabel &amp; sitasi terlampir sebagai file Markdown (.md). "
        "Analisis ini bersifat informatif dan bukan rekomendasi investasi.</i>"
    )

    body = "\n".join(lines)
    if len(body) + len(footer) <= cap:
        return body + footer

    # Potong rapi per baris agar tidak mematahkan tag HTML
    budget = cap - len(footer) - 20
    kept: list[str] = []
    used = 0
    for ln in lines:
        add_len = len(ln) + (1 if kept else 0)
        if used + add_len > budget:
            break
        kept.append(ln)
        used += add_len
    return "\n".join(kept) + "\n..." + footer


def generate_report(
    *,
    ticker: str,
    sector: str | None = None,
    company: str | None = None,
    query: str = "",
    years: int | Sequence[int] | None = None,
    extracted_data: dict[int, dict[str, Any]] | None = None,
    ratios: dict[str, Any] | None = None,
    market_context: Sequence[dict[str, Any]] | None = None,
    market_errors: Sequence[str] | None = None,
    extraction_errors: Sequence[str] | None = None,
    retrieved_chunks: Sequence[dict[str, Any]] | None = None,
    use_llm: bool = True,
    llm=None,
) -> dict[str, Any]:
    """API utama Reporting Agent: susun laporan Markdown 5 bagian + audit + ringkasan Telegram."""
    t0 = time.perf_counter()
    target_years = _extract_target_years(years, ratios, extracted_data)
    identity = resolve_report_identity(
        ticker,
        target_years,
        sector=sector or (ratios or {}).get("sector"),
        company=company,
    )

    stats: dict[str, Any] = {
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "used_fallback_narrative": False,
        "narrative_errors": [],
        "seconds": 0.0,
    }

    has_extracted = bool(extracted_data) and any(
        isinstance(v, dict) and any(isinstance(m, dict) and m.get("status") == "ok" for m in v.values())
        for v in (extracted_data or {}).values()
    )
    has_ratios = bool(ratios) and bool((ratios or {}).get("by_year"))

    if not has_extracted and not has_ratios:
        markdown = _render_extraction_failure_report(
            identity=identity,
            query=query,
            target_years=target_years,
            extraction_errors=extraction_errors,
            market_context=market_context,
            market_errors=market_errors,
        )
        audit = audit_report(
            markdown,
            ratios=ratios,
            market_context=market_context,
            profile_validated=identity["profile_validated"],
            stripped_urls=[],
            is_failure_report=True,
        )
        tg_summary = format_telegram_summary(
            identity=identity,
            query=query,
            target_years=target_years,
            direct_answer="",
            ratios=ratios,
            market_context=market_context,
            is_failure_report=True,
        )
        stats["seconds"] = round(time.perf_counter() - t0, 3)
        return {
            "status": "extraction_failed",
            "ticker": identity["ticker"],
            "company": identity["company"],
            "sector": identity["sector"],
            "years": target_years,
            "profile_validated": identity["profile_validated"],
            "report": markdown,
            "telegram_summary": tg_summary,
            "report_audit": audit,
            "report_stats": stats,
        }

    narrative, _ = generate_narrative(
        identity=identity,
        query=query,
        target_years=target_years,
        extracted_data=extracted_data,
        ratios=ratios,
        market_context=market_context,
        retrieved_chunks=retrieved_chunks,
        stats=stats,
        use_llm=use_llm,
        llm=llm,
    )

    allowed_urls = [
        str(m["url"]) for m in (market_context or []) if isinstance(m, dict) and m.get("url")
    ]
    stripped_urls: list[str] = []
    sanitized: dict[str, str] = {}
    for field_name in (
        "direct_answer",
        "executive_summary",
        "ratio_analysis",
        "trend_analysis",
        "market_synthesis",
        "conclusion",
    ):
        clean_txt, removed = sanitize_and_audit_urls(getattr(narrative, field_name), allowed_urls)
        sanitized[field_name] = clean_txt.strip()
        stripped_urls.extend(removed)

    period_txt = (
        f"{min(target_years)}–{max(target_years)}"
        if len(target_years) > 1
        else (str(target_years[0]) if target_years else "-")
    )
    val_status = "Tervalidasi (OJK/SEOJK)" if identity["profile_validated"] else "Profil Umum — Belum Divalidasi"

    header_blocks = [
        f"# Laporan Analisis Keuangan — {identity['company']} ({identity['ticker'].upper() or '-'})",
        f"**Periode:** {period_txt} | **Sektor:** {identity['profile_label']} | **Status Validasi:** {val_status}",
    ]
    if not identity["profile_validated"] and identity.get("profile_warning"):
        header_blocks.append(f"> **PERINGATAN (Belum Divalidasi):** {identity['profile_warning']}")
    if query:
        header_blocks.append(
            f"> **Pertanyaan Pengguna:** {query}\n>\n> **Jawaban Ringkas:** {sanitized['direct_answer']}"
        )

    ratios_tbl = render_ratios_table(ratios)
    metrics_tbl = render_metrics_table(extracted_data, identity["sector"], target_years)
    trends_tbl = render_trends_table(ratios)
    market_block = render_market_sources(market_context, market_errors)
    source_idx = render_source_index(extracted_data, ratios, market_context, identity["ticker"])

    sections = [
        "\n\n".join(header_blocks),
        f"## 1. Ringkasan Eksekutif\n\n{sanitized['executive_summary']}",
        (
            f"## 2. Rasio Keuangan & Interpretasi\n\n"
            f"{sanitized['ratio_analysis']}\n\n"
            f"### Tabel Rasio Keuangan & Evaluasi Ambang OJK\n\n{ratios_tbl}\n\n"
            f"### Tabel Komponen Metrik Keuangan Kunci\n\n{metrics_tbl}"
        ),
        f"## 3. Tren Antar Tahun\n\n{sanitized['trend_analysis']}\n\n{trends_tbl}",
        f"## 4. Konteks Pasar & Regulasi\n\n{sanitized['market_synthesis']}\n\n### Daftar Sumber Berita & Regulasi\n\n{market_block}",
        (
            f"## 5. Kesimpulan\n\n{sanitized['conclusion']}\n\n"
            f"### Catatan Keterbatasan & Penafian\n\n"
            f"- Seluruh angka laporan keuangan dan rasio dihitung secara deterministik dari laporan tahunan "
            f"terverifikasi; metrik atau rasio yang tidak memiliki komponen lengkap dilaporkan jujur sebagai *tidak tersedia*.\n"
            f"- Laporan ini disusun untuk tujuan analisis informatif/akademis dan **bukan merupakan rekomendasi beli atau jual saham**.\n\n"
            f"### Indeks Sumber Data\n\n{source_idx}"
        ),
    ]
    markdown = "\n\n".join(sections).strip() + "\n"

    audit = audit_report(
        markdown,
        ratios=ratios,
        market_context=market_context,
        profile_validated=identity["profile_validated"],
        stripped_urls=stripped_urls,
        is_failure_report=False,
    )
    tg_summary = format_telegram_summary(
        identity=identity,
        query=query,
        target_years=target_years,
        direct_answer=sanitized["direct_answer"],
        ratios=ratios,
        market_context=market_context,
        is_failure_report=False,
    )
    stats["seconds"] = round(time.perf_counter() - t0, 3)

    return {
        "status": "ok",
        "ticker": identity["ticker"],
        "company": identity["company"],
        "sector": identity["sector"],
        "years": target_years,
        "profile_validated": identity["profile_validated"],
        "report": markdown,
        "telegram_summary": tg_summary,
        "report_audit": audit,
        "report_stats": stats,
    }


def reporting_node(state: AgentState) -> dict[str, Any]:
    """Node LangGraph untuk Reporting Agent (fan-in dari analyst_node & market_node di Minggu 15)."""
    result = generate_report(
        ticker=state.get("ticker", ""),
        sector=state.get("sector"),
        query=state.get("query", ""),
        years=state.get("year"),
        extracted_data=state.get("extracted_data"),
        ratios=state.get("ratios"),
        market_context=state.get("market_context"),
        market_errors=state.get("market_errors"),
        extraction_errors=state.get("extraction_errors"),
        retrieved_chunks=state.get("retrieved_chunks"),
        use_llm=True,
    )
    aud = result["report_audit"]
    st = result["report_stats"]
    msg = (
        f"Laporan Markdown selesai (status={result['status']}, audit_passed={aud['passed']}, "
        f"sitasi_hal={aud['page_citation_count']}, url={aud['verified_url_count']}, "
        f"chars={aud['markdown_chars']}, fallback={st['used_fallback_narrative']}) "
        f"dalam {st['seconds']} s."
    )
    return {
        "report": result["report"],
        "report_audit": aud,
        "report_stats": st,
        "messages": [AIMessage(content=msg)],
    }


# ----------------------------------------------------------------- Loader hasil tersimpan & CLI


def load_saved_inputs(ticker: str, years: Sequence[int] | None = None) -> dict[str, Any]:
    """Muat data ekstraksi & konteks pasar nyata dari `results/` lalu hitung rasio via Analyst Agent."""
    code = ticker.strip().lower()
    eval_path = config.RESULTS / f"analyst_eval_{code}.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"Hasil evaluasi tidak ditemukan: {eval_path}")

    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    raw_extracted = eval_data.get("e2e_extracted") or {}
    extracted = {int(y): metrics for y, metrics in raw_extracted.items()}
    target_years = list(years) if years else [int(y) for y in (eval_data.get("meta") or {}).get("years") or config.YEARS]

    identity = resolve_report_identity(code, target_years)
    ratios = analyze_ratios(
        extracted_data=extracted,
        sector=identity["sector"],
        years=target_years,
        ticker=code,
        use_llm_summary=False,
    )

    market_context: list[dict[str, Any]] = []
    market_errors: list[str] = []
    market_path = config.RESULTS / "check_market.json"
    if market_path.exists():
        mdata = json.loads(market_path.read_text(encoding="utf-8"))
        entry = (mdata.get("results") or {}).get(code) or {}
        market_context = list(entry.get("market_context") or [])
        market_errors = list(entry.get("market_errors") or [])

    return {
        "ticker": code,
        "sector": identity["sector"],
        "company": identity["company"],
        "years": target_years,
        "extracted_data": extracted,
        "ratios": ratios,
        "market_context": market_context,
        "market_errors": market_errors,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Reporting Agent (Minggu 14) -- penyusun laporan analisis Markdown.")
    ap.add_argument("--from-results", required=True, metavar="TICKER", help="Kode saham yang datanya sudah ada di results/.")
    ap.add_argument("--query", default="", help="Pertanyaan pengguna opsional.")
    ap.add_argument("--offline", action="store_true", help="Pakai narasi deterministik (0 token LLM).")
    ap.add_argument("--out", default="", help="Path opsional untuk menyimpan laporan Markdown (.md).")
    args = ap.parse_args()

    bundle = load_saved_inputs(args.from_results)
    q = args.query or (
        f"Analisis kinerja keuangan, rasio prudensial, tren antar tahun, dan konteks pasar "
        f"{bundle['company']} ({bundle['ticker'].upper()}) periode {min(bundle['years'])}-{max(bundle['years'])}."
    )
    res = generate_report(
        ticker=bundle["ticker"],
        sector=bundle["sector"],
        company=bundle["company"],
        query=q,
        years=bundle["years"],
        extracted_data=bundle["extracted_data"],
        ratios=bundle["ratios"],
        market_context=bundle["market_context"],
        market_errors=bundle["market_errors"],
        use_llm=not args.offline,
    )

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(res["report"], encoding="utf-8")
        print(f"Tersimpan -> {out_p}")
    else:
        print(res["report"])

    aud = res["report_audit"]
    st = res["report_stats"]
    print(
        f"\n[Audit] passed={aud['passed']} | 5_bagian={aud['all_sections_present']} | "
        f"sitasi_hal={aud['page_citation_count']} | url={aud['verified_url_count']} | "
        f"stripped_url={len(aud['stripped_urls'])} | md_chars={aud['markdown_chars']} | "
        f"tg_chars={len(res['telegram_summary'])} | llm={st['llm_calls']} ({st['total_tokens']} tok) | {st['seconds']} s"
    )


if __name__ == "__main__":
    main()
