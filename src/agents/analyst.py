"""
Langkah 4 Minggu 11-12 (tugas 11.1-11.6, Keputusan 11.A-11.D) -- Financial Analyst Agent generik
berbasis formula eksplisit (`src/ratio_profiles.py`), eksekusi `PythonAstREPLTool` aman
(`src/agents/tools.py`), validasi ketat penolakan input `null`, dan interpretasi ambang batas OJK.
docs/PANDUAN_MINGGU11-12.md, Langkah 4.

ATURAN DISIPLIN LINTAS EMITEN (R10 & R11):
  Modul ini 100% generik -- TIDAK memuat percabangan per emiten, nama perusahaan, nomor halaman,
  atau nomor Catatan. Profil dipilih dari `sector` dokumen:
    - `bank`    (validated=True)  : 6 rasio SEOJK (CAR, ROA, ROE, NIM, NPL, LDR) + ambang OJK;
    - `general` (validated=False) : ROA & ROE dasar dengan label wajib "belum divalidasi".

CLI smoke test:
  python -m src.agents.analyst --ticker bbca --from-gt
  python -m src.agents.analyst --ticker bbca --year 2023 2024 2025
"""

import argparse
import re
import sys
import time
from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src import config
from src import ratio_profiles as rp
from src.agents.state import AgentState, RatioResult
from src.agents.tools import evaluate_formula_python, python_calculator

ANALYST_SYSTEM_PROMPT = """Kamu adalah analis keuangan senior untuk laporan tahunan perusahaan publik Indonesia.
Tugasmu menyusun ringkasan analisis rasio keuangan secara objektif, ringkas, dan faktual.

ATURAN WAJIB:
1. HANYA kutip angka rasio persis sesuai hasil perhitungan Python yang diberikan di bawah ini.
   - DILARANG menghitung ulang, mengubah angka, atau mengarang angka untuk rasio berstatus `insufficient_data`.
2. Jika suatu rasio berstatus `insufficient_data`, sebutkan secara jujur bahwa rasio tersebut tidak dapat dihitung beserta input yang kurang.
3. Untuk sektor perbankan tervalidasi, kaitkan setiap rasio dengan ambang batas prudensial OJK yang diberikan dan jelaskan arah tren antar tahun bila tersedia >= 2 tahun.
4. Jika profil berstatus `validated=False` (sektor non-bank / profil umum), WAJIB sertakan peringatan eksplisit bahwa perhitungan memakai profil umum yang belum divalidasi.
5. Gunakan bahasa Indonesia formal yang rapi (maksimal 2-3 paragraf singkat)."""


def _get_valid_metric(
    year_data: dict[str, dict[str, Any]],
    candidates: Sequence[str],
) -> tuple[str | None, float | None, list[int]]:
    """Cari metrik valid pertama (status=='ok' & value_million_idr!=None) -> (key, val, pages)."""
    for key in candidates:
        item = year_data.get(key)
        if not isinstance(item, dict):
            continue
        if item.get("status") != "ok":
            continue
        val = item.get("value_million_idr")
        if val is None or isinstance(val, bool):
            continue
        return key, float(val), list(item.get("source_pages") or [])
    return None, None, []


def _format_evaluated_expression(expression: str, variables: dict[str, float]) -> str:
    """Ganti nama variabel pada ekspresi formula dengan nilainya untuk jejak audit transparan."""
    expr = expression
    for name in sorted(variables, key=len, reverse=True):
        expr = re.sub(rf"\b{re.escape(name)}\b", f"{variables[name]:.2f}", expr)
    return expr


def compute_single_ratio(
    formula: rp.RatioFormula,
    year: int,
    extracted_data: dict[int, dict[str, Any]],
    profile: rp.SectorProfile,
    *,
    allow_ending_fallback: bool = False,
) -> RatioResult:
    """Hitung satu rasio untuk satu tahun lewat `PythonAstREPLTool` dengan validasi input ketat (11.4)."""
    curr_data = extracted_data.get(year) or extracted_data.get(str(year)) or {}  # type: ignore[arg-type]
    prev_data = extracted_data.get(year - 1) or extracted_data.get(str(year - 1)) or {}  # type: ignore[arg-type]

    vars_for_eval: dict[str, float] = {}
    inputs_used: dict[str, float] = {}
    missing_inputs: list[str] = []
    pages_set: set[int] = set()
    notes_parts: list[str] = [formula.notes] if formula.notes else []
    used_average = False
    used_ending_fallback = False

    for var_name, candidates in formula.inputs:
        key_curr, val_curr, pages_curr = _get_valid_metric(curr_data, candidates)
        if key_curr is None or val_curr is None:
            missing_inputs.append(f"{candidates[0]}[{year}]")
            continue

        pages_set.update(int(p) for p in pages_curr if isinstance(p, int))

        if var_name in formula.average_vars:
            # Cari tahun pembanding t-1 memakai key yang sama terlebih dahulu agar basis konsisten
            prev_order = (key_curr, *[k for k in candidates if k != key_curr])
            key_prev, val_prev, pages_prev = _get_valid_metric(prev_data, prev_order)
            if key_prev is not None and val_prev is not None:
                avg_val = evaluate_formula_python(
                    "(prev_val + curr_val) / 2",
                    {"prev_val": val_prev, "curr_val": val_curr},
                    ndigits=6,
                )
                vars_for_eval[var_name] = avg_val
                inputs_used[f"{key_prev}_{year - 1}"] = val_prev
                inputs_used[f"{key_curr}_{year}"] = val_curr
                inputs_used[f"avg_{var_name}"] = avg_val
                pages_set.update(int(p) for p in pages_prev if isinstance(p, int))
                used_average = True
            elif allow_ending_fallback:
                vars_for_eval[var_name] = val_curr
                inputs_used[f"{key_curr}_{year}"] = val_curr
                used_ending_fallback = True
                notes_parts.append(
                    f"tahun pembanding {year - 1} untuk '{key_curr}' tidak tersedia; menggunakan saldo akhir {year}"
                )
            else:
                missing_inputs.append(f"{key_curr}[{year - 1}]")
        else:
            vars_for_eval[var_name] = val_curr
            inputs_used[f"{key_curr}_{year}"] = val_curr

    if used_average:
        basis_used = f"{formula.basis_description} [rata-rata {year - 1}-{year}]"
    elif used_ending_fallback:
        basis_used = f"{formula.basis_description} [ending_balance_fallback]"
    else:
        basis_used = f"{formula.basis_description} [saldo akhir {year}]"

    # Pagar 11.4: tolak menghitung bila ada input null / belum terverifikasi
    if missing_inputs:
        warn_suffix = f" ({profile.warning_label})" if profile.warning_label else ""
        return RatioResult(
            ratio_name=formula.name,
            year=year,
            value=None,
            status="insufficient_data",
            formula=formula.expression,
            basis_used=basis_used,
            inputs_used=inputs_used,
            missing_inputs=missing_inputs,
            source_pages=sorted(pages_set),
            interpretation=(
                f"{formula.name} {year} tidak dapat dihitung karena data berikut tidak tersedia "
                f"atau tidak terverifikasi: {', '.join(missing_inputs)}.{warn_suffix}"
            ),
            notes="; ".join(notes_parts) or None,
        )

    # Pagar penyebut <= 0 (cegah pembagian nol atau rasio cacat)
    for pvar in formula.positive_vars:
        if vars_for_eval.get(pvar, 0.0) <= 0.0:
            return RatioResult(
                ratio_name=formula.name,
                year=year,
                value=None,
                status="insufficient_data",
                formula=formula.expression,
                basis_used=basis_used,
                inputs_used=inputs_used,
                missing_inputs=[f"{pvar}<=0"],
                source_pages=sorted(pages_set),
                interpretation=(
                    f"{formula.name} {year} tidak dapat dihitung karena penyebut '{pvar}' "
                    f"bernilai tidak positif ({vars_for_eval.get(pvar)})."
                ),
                notes="; ".join(notes_parts) or None,
            )

    try:
        val = evaluate_formula_python(formula.expression, vars_for_eval, ndigits=4)
    except ValueError as e:
        return RatioResult(
            ratio_name=formula.name,
            year=year,
            value=None,
            status="calc_error",
            formula=formula.expression,
            basis_used=basis_used,
            inputs_used=inputs_used,
            source_pages=sorted(pages_set),
            interpretation=f"{formula.name} {year} gagal dihitung oleh kalkulator Python: {e}",
            notes="; ".join([*notes_parts, str(e)]),
        )

    ojk = rp.interpret_ratio(formula.name, val, profile)
    if not profile.validated and profile.warning_label and profile.warning_label not in notes_parts:
        notes_parts.append(profile.warning_label)

    return RatioResult(
        ratio_name=formula.name,
        year=year,
        value=val,
        status="ok",
        formula=formula.expression,
        evaluated_expression=_format_evaluated_expression(formula.expression, vars_for_eval),
        basis_used=basis_used,
        inputs_used=inputs_used,
        missing_inputs=[],
        source_pages=sorted(pages_set),
        ojk_category=ojk["category"],
        meets_ojk=ojk["meets_ojk"],
        ojk_benchmark=ojk["benchmark"],
        interpretation=ojk["summary"],
        notes="; ".join(notes_parts) or None,
    )


def compute_trends(by_year: dict[int, dict[str, dict[str, Any]]], ratio_names: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Hitung tren perubahan antar tahun (poin persen & arah) untuk setiap rasio."""
    years = sorted(by_year)
    trends: dict[str, dict[str, Any]] = {}
    for name in ratio_names:
        series = {
            y: by_year[y][name]["value"]
            for y in years
            if name in by_year[y] and by_year[y][name]["status"] == "ok" and by_year[y][name]["value"] is not None
        }
        if len(series) < 2:
            trends[name] = {"available_years": list(series), "direction": "data_tunggal" if len(series) == 1 else "tidak_tersedia"}
            continue
        y0, y1 = min(series), max(series)
        delta = round(series[y1] - series[y0], 2)
        if abs(delta) < 0.05:
            direction = "stabil"
        elif delta > 0:
            direction = "naik"
        else:
            direction = "turun"
        trends[name] = {
            "start_year": y0,
            "end_year": y1,
            "start_value": round(series[y0], 2),
            "end_value": round(series[y1], 2),
            "delta_pp": delta,
            "direction": direction,
            "series": {y: round(v, 2) for y, v in series.items()},
        }
    return trends


def build_deterministic_summary(
    by_year: dict[int, dict[str, dict[str, Any]]],
    trends: dict[str, dict[str, Any]],
    profile: rp.SectorProfile,
    ticker: str = "",
) -> str:
    """Ringkasan deterministik bebas halusinasi dari hasil perhitungan PythonAstREPLTool."""
    years = sorted(by_year)
    header = f"Analisis Rasio Keuangan ({profile.label})"
    if ticker:
        header += f" — Emiten {ticker.upper()} ({', '.join(map(str, years))})"
    lines = [header]
    if not profile.validated and profile.warning_label:
        lines.append(f"PERINGATAN: {profile.warning_label}")

    latest_y = max(years) if years else None
    if latest_y is not None:
        for name in profile.ratio_names:
            item = by_year[latest_y].get(name)
            if not item:
                continue
            t = trends.get(name, {})
            trend_txt = ""
            if "delta_pp" in t:
                sign = "+" if t["delta_pp"] > 0 else ""
                trend_txt = f" (tren {t['start_year']}->{t['end_year']}: {t['direction']} {sign}{t['delta_pp']:.2f} pp)"
            lines.append(f"- [{latest_y}] {item['interpretation']}{trend_txt}")
    return "\n".join(lines)


def _summarize_with_llm(
    by_year: dict[int, dict[str, dict[str, Any]]],
    trends: dict[str, dict[str, Any]],
    profile: rp.SectorProfile,
    ticker: str,
    stats: dict[str, Any],
    llm=None,
) -> str:
    """Sintesis narasi analitis lewat LLM berdasarkan angka yang sudah pasti benar dari Python."""
    active_llm = llm or config.get_llm(effort=config.REASONING_EFFORT)
    lines = [
        f"Emiten: {ticker.upper() or '-'} | Sektor: {profile.sector} | Validated: {profile.validated}",
    ]
    if profile.warning_label:
        lines.append(f"Peringatan profil: {profile.warning_label}")
    lines.append("\nHASIL RASIO (dihitung PythonAstREPLTool, JANGAN diubah):")
    for y in sorted(by_year):
        lines.append(f"Tahun {y}:")
        for name in profile.ratio_names:
            r = by_year[y].get(name)
            if not r:
                continue
            if r["status"] == "ok":
                lines.append(
                    f"  - {name}: {r['value']:.2f}% | status=ok | {r['interpretation']} | hal={r['source_pages']}"
                )
            else:
                lines.append(f"  - {name}: None | status={r['status']} | {r['interpretation']}")
    lines.append("\nTREN ANTAR TAHUN:")
    for name, tr in trends.items():
        if "delta_pp" in tr:
            lines.append(
                f"  - {name}: {tr['start_year']}={tr['start_value']:.2f}% -> {tr['end_year']}={tr['end_value']:.2f}% "
                f"({tr['direction']} {tr['delta_pp']:+.2f} pp)"
            )
    stats["llm_calls"] += 1
    resp = active_llm.invoke([SystemMessage(ANALYST_SYSTEM_PROMPT), HumanMessage("\n".join(lines))])
    usage = getattr(resp, "usage_metadata", None) or {}
    stats["input_tokens"] += int(usage.get("input_tokens", 0))
    stats["output_tokens"] += int(usage.get("output_tokens", 0))
    stats["total_tokens"] += int(usage.get("total_tokens", 0))
    text = str(getattr(resp, "content", "") or "").strip()
    if not text:
        return build_deterministic_summary(by_year, trends, profile, ticker=ticker)
    if not profile.validated and profile.warning_label and "belum divalidasi" not in text.lower():
        text = f"[{profile.warning_label}]\n\n{text}"
    return text


def _select_formulas(
    profile: rp.SectorProfile,
    *,
    roa_mode: Literal["seojk_pbt", "after_tax"] = "seojk_pbt",
    nim_use_average: bool = True,
) -> dict[str, rp.RatioFormula]:
    """Ambil kamus formula dari profil dengan saklar metodologi eksplisit (bukan per emiten)."""
    formulas = dict(profile.formulas)
    if profile.sector == "bank":
        if roa_mode == "after_tax":
            formulas["ROA"] = rp.BANK_ROA_AFTER_TAX_FORMULA
        if not nim_use_average and "NIM" in formulas:
            nim = formulas["NIM"]
            formulas["NIM"] = rp.RatioFormula(
                name=nim.name,
                label=nim.label,
                expression=nim.expression,
                inputs=nim.inputs,
                average_vars=(),
                positive_vars=nim.positive_vars,
                basis_description="Pendapatan bunga neto dibagi aset produktif (saldo akhir)",
                notes=nim.notes,
            )
    return formulas


def analyze_ratios(
    extracted_data: dict[int, dict[str, Any]],
    sector: str | None,
    *,
    years: Sequence[int] | None = None,
    ticker: str = "",
    allow_ending_fallback: bool = False,
    roa_mode: Literal["seojk_pbt", "after_tax"] = "seojk_pbt",
    nim_use_average: bool = True,
    use_llm_summary: bool = False,
    llm=None,
) -> dict[str, Any]:
    """Hitung seluruh rasio pada profil sektor untuk tahun target dan hasilkan interpretasi OJK."""
    t0 = time.perf_counter()
    profile = rp.get_profile(sector)
    formulas = _select_formulas(profile, roa_mode=roa_mode, nim_use_average=nim_use_average)

    norm_data: dict[int, dict[str, Any]] = {int(k): v for k, v in extracted_data.items()}
    target_years = sorted(int(y) for y in years) if years is not None else sorted(norm_data)

    by_year: dict[int, dict[str, dict[str, Any]]] = {}
    ok_count = 0
    total_count = 0

    for y in target_years:
        by_year[y] = {}
        for name in profile.ratio_names:
            formula = formulas[name]
            res = compute_single_ratio(
                formula, y, norm_data, profile, allow_ending_fallback=allow_ending_fallback
            )
            by_year[y][name] = res.model_dump()
            total_count += 1
            if res.status == "ok":
                ok_count += 1

    trends = compute_trends(by_year, profile.ratio_names)
    stats: dict[str, Any] = {
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "ratios_ok": ok_count,
        "ratios_total": total_count,
        "seconds": 0.0,
    }

    if use_llm_summary:
        summary = _summarize_with_llm(by_year, trends, profile, ticker, stats, llm=llm)
    else:
        summary = build_deterministic_summary(by_year, trends, profile, ticker=ticker)

    stats["seconds"] = round(time.perf_counter() - t0, 3)
    return {
        "ticker": ticker.strip().lower(),
        "sector": profile.sector,
        "profile_label": profile.label,
        "profile_validated": profile.validated,
        "profile_warning": profile.warning_label,
        "roa_mode": roa_mode if profile.sector == "bank" else "general",
        "years": target_years,
        "by_year": by_year,
        "trends": trends,
        "analysis_summary": summary,
        "analyst_stats": stats,
    }


def analyst_node(state: AgentState) -> dict[str, Any]:
    """Node LangGraph untuk Financial Analyst Agent (disambungkan setelah extraction_node di Minggu 15)."""
    extracted = state.get("extracted_data")
    if not extracted:
        raise ValueError("AgentState['extracted_data'] kosong -- jalankan extraction_node lebih dulu")

    raw_year = state.get("year")
    if isinstance(raw_year, int) and not isinstance(raw_year, bool):
        target_years: list[int] | None = [raw_year]
    elif isinstance(raw_year, Sequence) and not isinstance(raw_year, str):
        target_years = [int(y) for y in raw_year]
    else:
        target_years = None

    # Bila hanya 1 tahun diekstrak tanpa t-1, aktifkan fallback eksplisit agar tidak mati total
    norm_keys = {int(k) for k in extracted}
    allow_fallback = len(norm_keys) <= 1

    result = analyze_ratios(
        extracted_data=extracted,
        sector=state.get("sector"),
        years=target_years,
        ticker=state.get("ticker", ""),
        allow_ending_fallback=allow_fallback,
        use_llm_summary=False,
    )
    st = result["analyst_stats"]
    msg = (
        f"Analisis rasio selesai ({result['sector']}, validated={result['profile_validated']}): "
        f"{st['ratios_ok']}/{st['ratios_total']} rasio terhitung via {python_calculator.name} "
        f"dalam {st['seconds']} s."
    )
    return {
        "ratios": result,
        "messages": [AIMessage(content=msg)],
    }


def _load_extracted_from_gt(ticker: str) -> tuple[dict[int, dict[str, Any]], dict[str, dict[int, float]]]:
    """Muat angka mentah terverifikasi dari workbook ground truth untuk uji deterministik formula."""
    from openpyxl import load_workbook

    code = ticker.strip().lower()
    path = config.GROUND_TRUTH if code == config.DEV_TICKER else config.DATA / f"ground_truth_{code}.xlsx"
    wb = load_workbook(path, data_only=True)
    ws_raw = wb["1_angka_mentah"]

    # Pemetaan label baris yang konsisten pada sheet 1_angka_mentah -> metric_key
    row_map = {
        3: "total_assets",
        4: "earning_assets",
        7: "total_equity",
        8: "net_interest_income",
        9: "profit_before_tax",
        10: "net_income",
        13: "tier1_capital_bank",
        14: "total_capital_bank",
        15: "rwa_bank",
        21: "npl_amount_bank",
        22: "gross_loans_bank",
        23: "ckpn_loans_bank",
        24: "deposits_bank",
    }
    # Tambahan baris opsional bila workbook memuat angka Entitas Induk spesifik (mis. total aset / laba bank)
    for r in range(25, ws_raw.max_row + 1):
        lbl = str(ws_raw.cell(row=r, column=1).value or "").lower()
        if "total aset" in lbl and "bank" in lbl:
            row_map[r] = "total_assets_bank"
        elif "laba sebelum pajak" in lbl and "bank" in lbl:
            row_map[r] = "profit_before_tax_bank"
        elif ("laba bersih" in lbl or "laba tahun berjalan" in lbl) and "bank" in lbl:
            row_map[r] = "net_income_bank"
        elif "pendapatan bunga" in lbl and "bank" in lbl:
            row_map[r] = "net_interest_income_bank"

    year_cols = {2022: 3, 2023: 4, 2024: 5, 2025: 6}
    extracted: dict[int, dict[str, Any]] = {y: {} for y in year_cols}
    for row_idx, key in row_map.items():
        for y, col in year_cols.items():
            v = ws_raw.cell(row=row_idx, column=col).value
            if v is not None:
                extracted[y][key] = {
                    "metric_key": key,
                    "value_million_idr": round(float(v) * 1000.0, 3),
                    "status": "ok",
                    "grounded": True,
                    "source_pages": [],
                }

    official: dict[str, dict[int, float]] = {}
    if "2_rasio_resmi" in wb.sheetnames:
        ws_off = wb["2_rasio_resmi"]
        for r in range(2, ws_off.max_row + 1):
            y_val = ws_off.cell(row=r, column=1).value
            rname = str(ws_off.cell(row=r, column=2).value or "").strip().upper()
            v_val = ws_off.cell(row=r, column=3).value
            if isinstance(y_val, (int, float)) and rname in ("CAR", "ROA", "ROE", "NIM", "NPL", "LDR") and isinstance(v_val, (int, float)):
                official.setdefault(rname, {})[int(y_val)] = float(v_val)
    return extracted, official


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Smoke test Financial Analyst Agent (Minggu 11-12).")
    ap.add_argument("--ticker", required=True, help="kode saham, mis. bbca")
    ap.add_argument("--year", type=int, nargs="*", default=[2023, 2024, 2025], help="tahun target")
    ap.add_argument("--from-gt", action="store_true", help="pakai angka mentah ground truth (0 token API)")
    ap.add_argument("--roa-mode", choices=("seojk_pbt", "after_tax"), default="seojk_pbt")
    ap.add_argument("--nim-ending", action="store_true", help="pakai saldo akhir untuk NIM")
    ap.add_argument("--llm-summary", action="store_true", help="sintesis ringkasan dengan LLM")
    args = ap.parse_args(argv)

    if args.from_gt:
        extracted, official = _load_extracted_from_gt(args.ticker)
        sector = "bank"
    else:
        from src.agents.extraction import extract_metrics

        years = sorted(set(args.year))
        ext_res = extract_metrics(ticker=args.ticker, years=years)
        extracted = ext_res["extracted_data"]
        sector = ext_res["sector"]
        official = {}

    res = analyze_ratios(
        extracted_data=extracted,
        sector=sector,
        years=args.year,
        ticker=args.ticker,
        allow_ending_fallback=not args.from_gt,
        roa_mode=args.roa_mode,
        nim_use_average=not args.nim_ending,
        use_llm_summary=args.llm_summary,
    )
    print(f"Emiten: {res['ticker']} | sektor: {res['sector']} | validated={res['profile_validated']} | roa_mode={res['roa_mode']}")
    for y in res["years"]:
        print(f"\n== {res['ticker']}_{y} ==")
        for name, item in res["by_year"][y].items():
            v_str = f"{item['value']:.2f}%" if item["value"] is not None else "None"
            ref = official.get(name, {}).get(y)
            ref_str = ""
            if ref is not None and item["value"] is not None:
                ape = abs(item["value"] - ref) / ref * 100
                ref_str = f" | resmi={ref:.2f}% (APE {ape:.2f}%)"
            print(f"  {name:<5} [{item['status']:<17}] {v_str:>8}{ref_str} | {item['ojk_category']}")
    print("\n" + res["analysis_summary"])


if __name__ == "__main__":
    main()
