"""
Langkah 5 Minggu 11-12 -- pemeriksaan otomatis Financial Analyst Agent + uji negatif.
docs/PANDUAN_MINGGU11-12.md, Langkah 5.

Jalankan:
  python scripts/check_analyst.py --offline   # 0 token API, < 5 detik
  python scripts/check_analyst.py             # sama + 1 smoke test ringkasan LLM (opsional via --live)

Pemeriksaan:
  A. `PythonAstREPLTool` (11.1)     : akurasi 4 desimal + penolakan ekspresi berbahaya (AST) & bagi nol.
  B. Formula & basis (11.2, 11.3)   : 6 rasio x 3 tahun dari ground truth BBCA & BMRI -> seluruhnya MAPE < 5%,
                                      plus verifikasi `allow_ending_fallback` eksplisit vs ketat.
  C. Ambang batas OJK (11.6)        : uji seluruh batas kategori CAR, ROA, ROE, NIM, NPL, LDR.
  D. Profil non-bank & node (R17)   : sektor `non_financial` -> hanya ROA & ROE berlabel "belum divalidasi";
                                      kontrak `analyst_node(AgentState)`.
  E. Uji negatif (HARUS ditolak)    : (1) input null (`not_found`) -> `insufficient_data`;
                                      (2) input `ungrounded` -> `insufficient_data`;
                                      (3) penyebut 0 / negatif -> `insufficient_data` (tanpa crash);
                                      (4) audit 0 kebocoran nama emiten / Catatan di `analyst.py`, `tools.py`, `ratio_profiles.py`.
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

from src import ratio_profiles as rp
from src.agents import analyst as an
from src.agents.state import AgentState
from src.agents.tools import evaluate_formula_python, python_calculator

FORBIDDEN_ISSUER_RE = re.compile(
    r"\b(bca|bbca|bank central asia|mandiri|bmri|bbri|tlkm|catatan\s*51|catatan\s*58|catatan\s*65|catatan\s*49)\b",
    re.I,
)


def _strip_cli_examples(source: str) -> str:
    kept = []
    for line in source.splitlines():
        if "python -m src.agents." in line or 'help="kode saham, mis.' in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def check_repl_tool() -> list[str]:
    out = []
    if python_calculator.name != "python_calculator":
        out.append(f"[A] nama tool harus 'python_calculator', bukan {python_calculator.name!r}")

    val = evaluate_formula_python("(total_capital / rwa) * 100", {"total_capital": 249_056_422, "rwa": 848_181_552})
    if not math.isclose(val, 29.3636, rel_tol=1e-4):
        out.append(f"[A] hasil CAR PythonAstREPLTool meleset: {val}")

    tool_out = python_calculator.invoke("(249056422 / 848181552) * 100")
    if tool_out != "29.3636":
        out.append(f"[A] output python_calculator tak sesuai: {tool_out!r}")

    for dangerous in (
        "__import__('os').system('echo pwn')",
        "open('.env').read()",
        "(1).__class__.__bases__",
        "10 / 0",
        "lambda x: x",
    ):
        resp = python_calculator.invoke(dangerous)
        if not resp.startswith("ERROR:"):
            out.append(f"[A] ekspresi berbahaya/cacat tidak ditolak: {dangerous!r} -> {resp!r}")

    for bad_val in (float("nan"), float("inf"), True, None):
        try:
            evaluate_formula_python("a / b", {"a": bad_val, "b": 10.0})  # type: ignore[dict-item]
            out.append(f"[A] nilai variabel tak valid {bad_val!r} tidak ditolak")
        except ValueError:
            pass
    return out


def _mape_from_gt(ticker: str, *, roa_mode: str, nim_use_average: bool) -> dict[str, float]:
    extracted, official = an._load_extracted_from_gt(ticker)
    res = an.analyze_ratios(
        extracted, "bank", years=[2023, 2024, 2025], ticker=ticker,
        roa_mode=roa_mode, nim_use_average=nim_use_average,  # type: ignore[arg-type]
    )
    mapes: dict[str, float] = {}
    for ratio in rp.BANK_PROFILE.ratio_names:
        apes = []
        for y in (2023, 2024, 2025):
            got = res["by_year"][y][ratio]["value"]
            ref = official.get(ratio, {}).get(y)
            if got is None or ref is None:
                mapes[ratio] = float("inf")
                apes = []
                break
            apes.append(abs(got - ref) / ref * 100.0)
        if apes:
            mapes[ratio] = round(sum(apes) / len(apes), 2)
    return mapes


def check_formulas_and_basis() -> list[str]:
    out = []
    # BBCA: validasi GATE 1 (fn9 ROA after-tax & NIM saldo akhir)
    bbca_mapes = _mape_from_gt("bbca", roa_mode="after_tax", nim_use_average=False)
    for r, m in bbca_mapes.items():
        if m >= 5.0:
            out.append(f"[B] BBCA GT {r} MAPE={m:.2f}% >= 5%")

    # BMRI: validasi Minggu 8 (SEOJK PBT ROA & NIM rata-rata)
    bmri_mapes = _mape_from_gt("bmri", roa_mode="seojk_pbt", nim_use_average=True)
    for r, m in bmri_mapes.items():
        if m >= 5.0:
            out.append(f"[B] BMRI GT {r} MAPE={m:.2f}% >= 5%")

    # Cek mode ketat vs fallback eksplisit bila t-1 tidak ada
    single_year = {
        2024: {
            "net_income_bank": {"status": "ok", "value_million_idr": 50_000_000, "source_pages": [10]},
            "tier1_capital_bank": {"status": "ok", "value_million_idr": 200_000_000, "source_pages": [20]},
        }
    }
    strict = an.analyze_ratios(single_year, "bank", years=[2024], allow_ending_fallback=False)
    if strict["by_year"][2024]["ROE"]["status"] != "insufficient_data":
        out.append("[B] mode ketat tidak menolak ROE saat t-1 hilang")

    fb = an.analyze_ratios(single_year, "bank", years=[2024], allow_ending_fallback=True)
    roe_fb = fb["by_year"][2024]["ROE"]
    if roe_fb["status"] != "ok" or roe_fb["value"] != 25.0 or "ending_balance_fallback" not in roe_fb["basis_used"]:
        out.append(f"[B] fallback saldo akhir tidak ditandai eksplisit: {roe_fb}")
    if roe_fb["source_pages"] != [10, 20]:
        out.append(f"[B] source_pages tidak diwarisi dengan benar: {roe_fb['source_pages']}")
    return out


def check_ojk_thresholds() -> list[str]:
    out = []
    cases = [
        ("CAR", 7.5, "di_bawah_minimum_ojk", False),
        ("CAR", 10.0, "memenuhi_minimum", True),
        ("CAR", 13.5, "kuat", True),
        ("CAR", 29.4, "sangat_kuat", True),
        ("ROA", 0.4, "kurang_sehat", False),
        ("ROA", 1.0, "cukup_sehat", True),
        ("ROA", 1.4, "sehat", True),
        ("ROA", 3.9, "sangat_sehat", True),
        ("ROE", 4.0, "rendah", False),
        ("ROE", 12.0, "baik", True),
        ("ROE", 24.6, "sangat_baik", True),
        ("NIM", 1.8, "tertekan", False),
        ("NIM", 4.2, "sehat", True),
        ("NIM", 5.8, "sangat_kuat", True),
        ("NPL", 1.78, "sangat_sehat", True),
        ("NPL", 3.5, "aman_ojk", True),
        ("NPL", 5.2, "melampaui_batas_ojk", False),
        ("LDR", 65.0, "likuiditas_longgar", True),
        ("LDR", 85.0, "ideal_ojk", True),
        ("LDR", 96.0, "likuiditas_ketat", False),
    ]
    for name, val, want_cat, want_ok in cases:
        got = rp.interpret_ratio(name, val, rp.BANK_PROFILE)
        if got["category"] != want_cat or got["meets_ojk"] is not want_ok:
            out.append(f"[C] {name}={val} -> ({got['category']}, {got['meets_ojk']}), seharusnya ({want_cat}, {want_ok})")
    return out


def check_non_bank_and_node() -> list[str]:
    out = []
    d_gen = {
        2023: {
            "net_income": {"status": "ok", "value_million_idr": 24_000_000, "source_pages": [50]},
            "total_assets": {"status": "ok", "value_million_idr": 280_000_000, "source_pages": [51]},
            "total_equity": {"status": "ok", "value_million_idr": 150_000_000, "source_pages": [52]},
        },
        2024: {
            "net_income": {"status": "ok", "value_million_idr": 25_000_000, "source_pages": [60]},
            "total_assets": {"status": "ok", "value_million_idr": 300_000_000, "source_pages": [61]},
            "total_equity": {"status": "ok", "value_million_idr": 160_000_000, "source_pages": [62]},
        },
    }
    node_out = an.analyst_node(AgentState(ticker="nonbank", sector="non_financial", year=[2024], extracted_data=d_gen))
    r = node_out["ratios"]
    if r["profile_validated"] is not False or r["sector"] != "general":
        out.append("[D] sektor non_financial tidak memakai profil general (validated=False)")
    if set(r["by_year"][2024]) != {"ROA", "ROE"}:
        out.append(f"[D] profil general seharusnya hanya ROA & ROE, bukan {set(r['by_year'][2024])}")
    for k in ("ROA", "ROE"):
        item = r["by_year"][2024][k]
        if item["status"] != "ok" or item["meets_ojk"] is not None:
            out.append(f"[D] hasil {k} profil general tidak sesuai: {item}")
        if "belum divalidasi" not in item["interpretation"].lower():
            out.append(f"[D] label 'belum divalidasi' hilang di interpretasi {k}")
    if "belum divalidasi" not in r["analysis_summary"].lower():
        out.append("[D] label 'belum divalidasi' hilang di analysis_summary")

    # Kontrak analyst_node: wajib menolak state tanpa extracted_data
    try:
        an.analyst_node(AgentState(ticker="nonbank", sector="bank"))
        out.append("[D] analyst_node tidak menolak state tanpa extracted_data")
    except ValueError:
        pass
    return out


def check_negative() -> list[str]:
    out = []
    # Negatif 1: input null (not_found) -> wajib ditolak
    d1 = {2024: {
        "gross_loans_bank": {"status": "ok", "value_million_idr": 800_000_000},
        "deposits_bank": {"status": "not_found", "value_million_idr": None},
    }}
    r1 = an.analyze_ratios(d1, "bank", years=[2024])["by_year"][2024]["LDR"]
    ok1 = (r1["status"] == "insufficient_data") and (r1["value"] is None) and bool(r1["missing_inputs"])
    print(f"  {'OK   ' if ok1 else 'GAGAL'} negatif 1: input null (not_found) -> ditolak (status={r1['status']}, val={r1['value']})")
    if not ok1:
        out.append("[E] input null tidak ditolak")

    # Negatif 2: input ungrounded -> wajib ditolak
    d2 = {2024: {
        "npl_amount_bank": {"status": "ungrounded", "value_million_idr": None},
        "gross_loans_bank": {"status": "ok", "value_million_idr": 800_000_000},
    }}
    r2 = an.analyze_ratios(d2, "bank", years=[2024])["by_year"][2024]["NPL"]
    ok2 = (r2["status"] == "insufficient_data") and (r2["value"] is None)
    print(f"  {'OK   ' if ok2 else 'GAGAL'} negatif 2: input ungrounded -> ditolak (status={r2['status']}, val={r2['value']})")
    if not ok2:
        out.append("[E] input ungrounded tidak ditolak")

    # Negatif 3: penyebut nol / negatif -> ditolak tanpa ZeroDivisionError
    d3 = {2024: {
        "total_capital_bank": {"status": "ok", "value_million_idr": 200_000_000},
        "rwa_bank": {"status": "ok", "value_million_idr": 0.0},
        "gross_loans_bank": {"status": "ok", "value_million_idr": 800_000_000},
        "deposits_bank": {"status": "ok", "value_million_idr": -100.0},
    }}
    r3_car = an.analyze_ratios(d3, "bank", years=[2024])["by_year"][2024]["CAR"]
    r3_ldr = an.analyze_ratios(d3, "bank", years=[2024])["by_year"][2024]["LDR"]
    ok3 = (
        r3_car["status"] == "insufficient_data" and r3_car["value"] is None
        and r3_ldr["status"] == "insufficient_data" and r3_ldr["value"] is None
    )
    print(f"  {'OK   ' if ok3 else 'GAGAL'} negatif 3: penyebut 0 / negatif -> ditolak bersih tanpa crash")
    if not ok3:
        out.append("[E] penyebut 0/negatif tidak ditolak bersih")

    # Negatif 4: audit 0 kebocoran nama emiten / nomor Catatan
    leaks = []
    for rel in ("src/agents/analyst.py", "src/agents/tools.py", "src/ratio_profiles.py"):
        text = _strip_cli_examples((ROOT / rel).read_text(encoding="utf-8"))
        hits = FORBIDDEN_ISSUER_RE.findall(text)
        if hits:
            leaks.append(f"{rel}: {sorted(set(hits))}")
    ok4 = not leaks
    print(f"  {'OK   ' if ok4 else 'GAGAL'} negatif 4: audit bebas nama emiten/Catatan (0 kebocoran)")
    if not ok4:
        out.append(f"[E] kebocoran emiten/Catatan: {leaks}")
    return out


def check_live_summary() -> list[str]:
    out = []
    extracted, _ = an._load_extracted_from_gt("bbca")
    res = an.analyze_ratios(
        extracted, "bank", years=[2023, 2024, 2025], ticker="bbca",
        roa_mode="after_tax", nim_use_average=False, use_llm_summary=True,
    )
    st = res["analyst_stats"]
    txt = res["analysis_summary"]
    print(f"  Ringkasan LLM: {len(txt)} karakter | {st['llm_calls']} call, {st['total_tokens']:,} token, {st['seconds']} s")
    if len(txt) < 80 or "CAR" not in txt or "OJK" not in txt:
        out.append("[F] ringkasan LLM terlalu singkat atau tidak menyebut CAR/OJK")
    return out


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Pemeriksaan Financial Analyst Agent (Langkah 5 Minggu 11-12).")
    ap.add_argument("--offline", action="store_true", help="hanya cek deterministik + uji negatif (0 token API)")
    ap.add_argument("--live", action="store_true", help="ikut uji 1 panggilan ringkasan LLM")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()

    failures = []
    checks = [
        ("A. PythonAstREPLTool aman & akurasi 4 desimal (11.1)", check_repl_tool),
        ("B. Formula 6 rasio GT BBCA & BMRI (MAPE < 5%) + fallback basis (11.2, 11.3)", check_formulas_and_basis),
        ("C. Ambang batas prudensial OJK 6 rasio (11.6)", check_ojk_thresholds),
        ("D. Profil non-bank general (belum divalidasi) & analyst_node (R17)", check_non_bank_and_node),
    ]
    print("== Pemeriksaan offline Financial Analyst Agent ==")
    for name, fn in checks:
        probs = fn()
        print(f"  {'OK   ' if not probs else 'GAGAL'} {name}" + (f": {len(probs)} masalah" if probs else ""))
        for p in probs[:5]:
            print(f"         {p}")
        failures += probs

    print("\n== E. Uji negatif (HARUS ditolak — 11.4 & bebas kebocoran) ==")
    failures += check_negative()

    if args.live and not args.offline:
        print("\n== F. Uji live sintesis ringkasan LLM ==")
        failures += check_live_summary()

    print(f"\nSelesai dalam {time.perf_counter() - t0:.2f} s")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
