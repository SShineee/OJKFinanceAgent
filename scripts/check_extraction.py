"""
Langkah 5 Minggu 9 -- pemeriksaan otomatis Extraction Agent + uji negatif.
docs/PANDUAN_MINGGU9.md, Langkah 5.

Jalankan:
  python scripts/check_extraction.py --offline   # 0 token Groq, < 10 detik
  python scripts/check_extraction.py             # lengkap + 1 live smoke test BBCA 2024 (bukan BMRI!)

Pemeriksaan:
  A. Parser angka (`parse_number.py`)  : format Indonesia/dwibahasa, U+202F, kurung negatif,
                                         konversi ke juta Rp, penjumlahan komponen, penolakan tak valid.
  B. Grounding & normalisasi           : cek keberadaan angka di chunk, penjumlahan komponen,
                                         prioritas `chunk["unit"]`, flag `merged_cells_warning`.
  C. Profil sektor & bebas emiten (9.5): profil `bank` vs `general`; 0 nama bank/halaman/Catatan
                                         terhardcode di `ratio_profiles.py`, `tools.py`, `extraction.py`.
  D. Tool `search_annual_report` (9.2) : nama bahasa Inggris, pagar `ticker` wajib, metadata header,
                                         isolasi bank (`bbca` != `bmri`), `ContextVar` recorder.
  E. Uji negatif (HARUS gagal/ditolak) : (1) halusinasi angka -> `ungrounded` + `None`;
                                         (2) angka tak ada -> `not_found` + `None`;
                                         (3) skala tertukar LLM -> dikoreksi oleh `chunk["unit"]`.
  F. Live smoke test (non-`--offline`) : 1 eksekusi `extraction_node` pada BBCA 2024 (8 metrik GATE 4),
                                         dibandingkan ke `data/ground_truth.xlsx` (toleransi <= 0,5%).
"""

import argparse
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import load_workbook

from src import config
from src import ratio_profiles as rp
from src.agents import extraction as ext
from src.agents import parse_number as pn
from src.agents.state import AgentState, NormalizedMetric, RawMetricExtraction
from src.agents.tools import record_retrieved_chunks, search_annual_report

# Pemetaan 8 metrik GATE 4 -> baris di sheet `1_angka_mentah` data/ground_truth.xlsx (miliar Rp)
GATE4_GT_ROWS = {
    "total_assets": 3,
    "net_interest_income": 8,
    "net_income": 10,
    "tier1_capital_bank": 13,
    "rwa_bank": 15,
    "npl_amount_bank": 21,
    "gross_loans_bank": 22,
    "deposits_bank": 24,
}
GT_YEAR_COL = {2022: 3, 2023: 4, 2024: 5, 2025: 6}

# Kata terlarang di prompt / profil / tool (9.5: nol hardcode emiten atau nomor Catatan)
FORBIDDEN_ISSUER_RE = re.compile(
    r"\b(bca|bbca|bank central asia|mandiri|bmri|bbri|tlkm|catatan\s*51|catatan\s*58|catatan\s*65|catatan\s*49)\b",
    re.I,
)


def _strip_docstrings_and_cli_help(source: str) -> str:
    """Periksa teks prompt & kode aktual (abaikan baris contoh CLI `--ticker bbca` di argparse/docstring)."""
    kept = []
    for line in source.splitlines():
        if "python -m src.agents.extraction" in line or 'help="kode saham, mis.' in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def check_parser() -> list[str]:
    out = []
    cases = [
        ("239.468.855", False, 239468855.0),
        ("239.468,855", False, 239468.855),
        ("54.851", False, 54851.0),
        ("Rp\u202f54.851", False, 54851.0),
        ("IDR 1.586.829", False, 1586829.0),
        ("(33.168.491)", False, -33168491.0),
        ("(Rp\u00a042.323.522)", False, -42323522.0),
        ("-1.234,50", False, -1234.5),
        ("29,36%", True, 29.36),
        ("20.10%", True, 20.10),
        ("20.10", True, 20.10),
        ("0.500", False, 0.5),
        ("1,234,567.89", False, 1234567.89),
        ("-", False, None),
        ("–", False, None),
        ("N/A", False, None),
        (None, False, None),
    ]
    for raw, pct, want in cases:
        got = pn.parse_indonesian_number(raw, is_percent=pct)
        if want is None and got is not None:
            out.append(f"[A] {raw!r} -> {got!r}, seharusnya None")
        elif want is not None and (got is None or not math.isclose(got, want, rel_tol=1e-9)):
            out.append(f"[A] {raw!r} -> {got!r}, seharusnya {want!r}")

    for bad in ("1.2.3", "abc", "54.851 miliar"):
        try:
            pn.parse_indonesian_number(bad)
            out.append(f"[A] format rusak {bad!r} tidak ditolak")
        except ValueError:
            pass

    if pn.normalize_to_million_idr(54851.0, "billion_idr") != 54_851_000.0:
        out.append("[A] konversi billion_idr -> million_idr salah")
    if pn.normalize_to_million_idr(239_468_855.0, "million_idr") != 239_468_855.0:
        out.append("[A] konversi million_idr -> million_idr salah")
    if pn.normalize_to_million_idr(2500.0, "thousand_idr") != 2.5:
        out.append("[A] konversi thousand_idr -> million_idr salah")
    try:
        pn.normalize_to_million_idr(100.0, None)
        out.append("[A] satuan None tidak ditolak")
    except ValueError:
        pass
    return out


def check_grounding_and_postprocess() -> list[str]:
    out = []
    chunk_kredit = {
        "chunk_id": "test_2023_0500",
        "text": (
            "| Kredit yang diberikan - setelah dikurangi cadangan kerugian penurunan nilai sebesar "
            "Rp\u202f33.168.491 | 2023 |\n"
            "| Pihak berelasi | 8.803.131 |\n"
            "| Pihak ketiga | 745.527.767 |"
        ),
        "pages": [738],
        "unit": "million_idr",
        "headings": "LAPORAN POSISI KEUANGAN ENTITAS INDUK",
        "merged_cells": True,
    }
    spec = rp.BANK_PROFILE.metrics["gross_loans_bank"]
    raw = RawMetricExtraction(
        metric_key="gross_loans_bank",
        raw_value=None,
        components=["8.803.131", "745.527.767", "(33.168.491)"],
        component_operation="sum",
        unit="million_idr",
        basis="bank_only",
        source_chunk_id="test_2023_0500",
        source_pages=[738],
    )
    res = ext.verify_and_normalize(raw, spec, {"test_2023_0500": chunk_kredit})
    if res.status != "ok" or res.value_million_idr != 787_499_389.0 or not res.grounded:
        out.append(f"[B] penjumlahan komponen kredit bruto gagal: {res.model_dump()}")
    if not res.merged_cells_warning:
        out.append("[B] merged_cells_warning tidak diteruskan dari metadata chunk")

    # Cek batas digit grounding ("54.851" tidak boleh cocok di "254.851" atau "54.851.274")
    if pn.is_grounded_in_text("54.851", "| Total | 254.851 |"):
        out.append("[B] grounding false positive pada 254.851")
    if pn.is_grounded_in_text("54.851", "| Laba | 54.851.274 |"):
        out.append("[B] grounding false positive pada 54.851.274")
    return out


def check_profiles_and_leakage() -> list[str]:
    out = []
    bank = rp.get_profile("bank")
    gen = rp.get_profile("non_financial")
    if not bank.validated or len(rp.gate4_metric_keys(bank)) != 8:
        out.append("[C] profil bank tidak memiliki tepat 8 metrik GATE 4")
    if gen.validated or not gen.warning_label or set(gen.metrics) != {"total_assets", "total_equity", "net_income"}:
        out.append("[C] profil general tidak sesuai spesifikasi non-bank")
    if rp.get_profile("insurance") is not rp.GENERAL_PROFILE or rp.get_profile(None) is not rp.GENERAL_PROFILE:
        out.append("[C] sektor non-bank tidak jatuh ke GENERAL_PROFILE")

    # Audit bebas nama emiten / nomor Catatan (9.5)
    for rel in ("src/ratio_profiles.py", "src/agents/tools.py", "src/agents/extraction.py"):
        text = _strip_docstrings_and_cli_help((ROOT / rel).read_text(encoding="utf-8"))
        hits = FORBIDDEN_ISSUER_RE.findall(text)
        if hits:
            out.append(f"[C] kebocoran emiten/Catatan di {rel}: {sorted(set(hits))}")
    if FORBIDDEN_ISSUER_RE.findall(ext.EXTRACTION_SYSTEM_PROMPT):
        out.append("[C] kebocoran emiten di EXTRACTION_SYSTEM_PROMPT")
    return out


def check_tool() -> list[str]:
    out = []
    if search_annual_report.name != "search_annual_report":
        out.append(f"[D] nama tool harus bahasa Inggris 'search_annual_report', bukan {search_annual_report.name!r}")
    for bad in ("", "xxxx"):
        resp = search_annual_report.invoke({"query": "CAR", "ticker": bad, "year": 2024})
        if not resp.startswith("ERROR:"):
            out.append(f"[D] ticker tidak valid {bad!r} tidak ditolak: {resp[:80]}")

    with record_retrieved_chunks() as rec:
        txt = search_annual_report.invoke({"query": "KPMM modal inti tier 1 ATMR bank", "ticker": "bbca", "year": 2024, "k": 4})
    if "[CHUNK 1 |" not in txt or "unit=million_idr" not in txt:
        out.append("[D] format header chunk tool tidak lengkap")
    if not rec or any(c["ticker"] != "bbca" or c["year"] != 2024 for c in rec.values()):
        out.append("[D] recorder menangkap chunk salah ticker/tahun")
    return out


def check_negative() -> list[str]:
    out = []
    chunk_ikhtisar = {
        "chunk_id": "test_2024_0001",
        "text": "| Pos | 2024 | 2023 |\n|---|---:|---:|\n| Laba Bersih | 54.851 | 48.658 |",
        "pages": [20],
        "unit": "billion_idr",
        "headings": "Ikhtisar Data Keuangan",
        "merged_cells": False,
    }
    spec_ni = rp.BANK_PROFILE.metrics["net_income"]

    # Negatif 1: halusinasi angka yang tidak ada di chunk -> HARUS ditolak (ungrounded, None)
    hallucinated = RawMetricExtraction(
        metric_key="net_income", raw_value="999.999", unit="billion_idr",
        basis="consolidated", source_chunk_id="test_2024_0001", source_pages=[20],
    )
    r1 = ext.verify_and_normalize(hallucinated, spec_ni, {"test_2024_0001": chunk_ikhtisar})
    ok1 = (r1.status == "ungrounded") and (r1.value_million_idr is None) and (not r1.grounded)
    print(f"  {'OK   ' if ok1 else 'GAGAL'} negatif 1: angka halusinasi -> ditolak (status={r1.status}, val={r1.value_million_idr})")
    if not ok1:
        out.append("[E] angka halusinasi tidak ditolak pagar grounding")

    # Negatif 2: metrik tidak ada di chunk -> HARUS not_found & None
    absent = RawMetricExtraction(metric_key="npl_amount_bank", raw_value=None)
    r2 = ext.verify_and_normalize(absent, rp.BANK_PROFILE.metrics["npl_amount_bank"], {"test_2024_0001": chunk_ikhtisar})
    ok2 = (r2.status == "not_found") and (r2.value_million_idr is None)
    print(f"  {'OK   ' if ok2 else 'GAGAL'} negatif 2: metrik tidak ada -> null jujur (status={r2.status}, val={r2.value_million_idr})")
    if not ok2:
        out.append("[E] metrik kosong tidak menghasilkan not_found/None")

    # Negatif 3: LLM salah menyebut satuan (million_idr padahal chunk billion_idr) -> dikoreksi chunk["unit"]
    wrong_unit = RawMetricExtraction(
        metric_key="net_income", raw_value="54.851", unit="million_idr",
        basis="consolidated", source_chunk_id="test_2024_0001", source_pages=[20],
    )
    r3 = ext.verify_and_normalize(wrong_unit, spec_ni, {"test_2024_0001": chunk_ikhtisar})
    ok3 = (r3.status == "ok") and (r3.value_million_idr == 54_851_000.0)
    print(f"  {'OK   ' if ok3 else 'GAGAL'} negatif 3: skala LLM tertukar -> dikoreksi metadata chunk ({r3.value_million_idr:,.0f} jt Rp)")
    if not ok3:
        out.append(f"[E] skala tertukar tidak dikoreksi chunk_unit: {r3.value_million_idr}")

    return out


def check_live_bbca_2024() -> list[str]:
    """Smoke test 1 tahun pada emiten pengembangan (BBCA 2024, 8 metrik GATE 4) -- TIDAK menyentuh BMRI."""
    out = []
    ws = load_workbook(config.GROUND_TRUTH, data_only=True)["1_angka_mentah"]
    res = ext.extract_metrics(ticker="bbca", years=2024, gate4_only=True, delay_between_groups=1.0)
    got = res["extracted_data"][2024]

    hits = 0
    for key, row in GATE4_GT_ROWS.items():
        gt_million = float(ws.cell(row=row, column=GT_YEAR_COL[2024]).value) * 1000.0
        m = got[key]
        val = m["value_million_idr"]
        rel_err = abs(val - gt_million) / gt_million * 100 if val is not None else None
        ok = (m["status"] == "ok") and (rel_err is not None) and (rel_err <= 0.5)
        hits += int(ok)
        err_s = f"{rel_err:.3f}%" if rel_err is not None else "MISS"
        val_s = f"{val:,.1f}" if val is not None else "None"
        print(f"  {'OK   ' if ok else 'MISS '} {key:<22} dapat={val_s:>16} | gt={gt_million:>16,.1f} | err={err_s:<8} | hal={m['source_pages']}")

    st = res["extraction_stats"]
    print(f"  Ringkas BBCA 2024: {hits}/8 tepat | {st['llm_calls']} LLM call, {st['total_tokens']:,} token, "
          f"{st['seconds']} s, retry429={st['rate_limit_retries']}x, tool_err={st['tool_error_retries']}x")
    if hits < 7:
        out.append(f"[F] smoke test live BBCA 2024 hanya {hits}/8 (minimal 7/8 sebelum masuk Langkah 6)")
    if not res["retrieved_chunks"]:
        out.append("[F] retrieved_chunks kosong (dibutuhkan RAGAS Minggu 17)")
    return out


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Pemeriksaan Extraction Agent (Langkah 5 Minggu 9).")
    ap.add_argument("--offline", action="store_true", help="hanya jalankan cek deterministik + uji negatif (0 token Groq)")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()

    failures = []
    checks = [
        ("A. Parser angka Indonesia & normalisasi satuan", check_parser),
        ("B. Grounding & penjumlahan komponen Python", check_grounding_and_postprocess),
        ("C. Profil sektor & audit bebas nama emiten (9.5)", check_profiles_and_leakage),
        ("D. Tool search_annual_report & isolasi bank (9.2)", check_tool),
    ]
    print("== Pemeriksaan offline Extraction Agent ==")
    for name, fn in checks:
        probs = fn()
        print(f"  {'OK   ' if not probs else 'GAGAL'} {name}" + (f": {len(probs)} masalah" if probs else ""))
        for p in probs[:5]:
            print(f"         {p}")
        failures += probs

    print("\n== E. Uji negatif (HARUS ditolak/dikoreksi) ==")
    failures += check_negative()

    if not args.offline:
        print("\n== F. Live smoke test BBCA 2024 (8 metrik GATE 4 -- tanpa menyentuh BMRI) ==")
        failures += check_live_bbca_2024()

    print(f"\nSelesai dalam {time.perf_counter() - t0:.1f} s")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()

