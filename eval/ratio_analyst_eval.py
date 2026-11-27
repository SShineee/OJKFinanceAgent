"""
Langkah 6 Minggu 11-12 (tugas 11.5) -- evaluasi MAE & MAPE 6 rasio x 3 tahun (2023-2025)
secara dua lapis untuk memisahkan error FORMULA dari error EKSTRAKSI:
  - Lapis 1 (Formula GT, 0 token)   : input angka mentah ground truth -> `analyze_ratios()`
  - Lapis 2 (End-to-End, 1 run)     : `extract_metrics()` (15 metrik + pembanding 2022) -> `analyze_ratios()`

Hasil dilaporkan TERPISAH per emiten (BBCA pengembangan vs BMRI uji) dengan formula tunggal baku
SEOJK (`roa_mode="seojk_pbt"`), ditambah analisis sensitivitas transparan (`after_tax` ROA & NIM
saldo akhir) untuk pembahasan Bab 4 & bimbingan 1.6.

Output:
  results/analyst_eval_bbca.json & .csv
  results/analyst_eval_bmri.json & .csv
  results/analyst_eval.json & .csv   (ringkasan gabungan terpisah per emiten)

Jalankan:
  python -m eval.ratio_analyst_eval --ticker bbca --layer1-only
  python -m eval.ratio_analyst_eval --all
  python -m eval.ratio_analyst_eval --combine
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config
from src import ratio_profiles as rp
from src.agents import analyst as an
from src.agents import extraction as ext

YEARS = (2023, 2024, 2025)
COMPARATIVE_2022_METRICS = ("total_assets", "total_assets_bank", "tier1_capital_bank", "earning_assets")

CSV_FIELDS = [
    "ticker", "layer", "mode", "year", "ratio", "status", "value_pct", "official_pct",
    "ae_pp", "ape_pct", "classification", "ojk_category", "meets_ojk", "basis_used",
    "source_pages", "missing_inputs", "notes",
]


def classify_mape(mape: float | None) -> str:
    """Klasifikasi proposal (Tabel 3.2): <2% sangat akurat, 2-5% akurat, >5% kurang akurat."""
    if mape is None:
        return "tidak_terhitung"
    if mape < 2.0:
        return "sangat_akurat"
    if mape <= 5.0:
        return "akurat"
    return "kurang_akurat"


def score_analysis(
    ticker: str,
    layer: str,
    mode_label: str,
    analysis: dict[str, Any],
    official: dict[str, dict[int, float]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_ratio: dict[str, dict[str, Any]] = {}

    for rname in rp.BANK_PROFILE.ratio_names:
        aes: list[float] = []
        apes: list[float] = []
        ok_n = 0
        for y in YEARS:
            item = analysis["by_year"][y][rname]
            val = item["value"]
            ref = official.get(rname, {}).get(y)
            ae = round(abs(val - ref), 4) if (val is not None and ref is not None) else None
            ape = round(ae / ref * 100.0, 4) if (ae is not None and ref) else None
            if item["status"] == "ok" and ae is not None and ape is not None:
                ok_n += 1
                aes.append(ae)
                apes.append(ape)
            rows.append({
                "ticker": ticker,
                "layer": layer,
                "mode": mode_label,
                "year": y,
                "ratio": rname,
                "status": item["status"],
                "value_pct": round(val, 4) if val is not None else None,
                "official_pct": ref,
                "ae_pp": ae,
                "ape_pct": ape,
                "classification": classify_mape(ape),
                "ojk_category": item["ojk_category"],
                "meets_ojk": item["meets_ojk"],
                "basis_used": item["basis_used"],
                "source_pages": " ".join(map(str, item.get("source_pages") or [])),
                "missing_inputs": "; ".join(item.get("missing_inputs") or []),
                "notes": item.get("notes"),
            })
        mae = round(sum(aes) / len(aes), 4) if aes else None
        mape = round(sum(apes) / len(apes), 2) if apes else None
        by_ratio[rname] = {
            "n_ok": ok_n,
            "n_total": len(YEARS),
            "mae_pp": mae,
            "mape_pct": mape,
            "classification": classify_mape(mape),
            "passed_5pct": (ok_n == len(YEARS)) and (mape is not None) and (mape < 5.0),
        }

    valid_mapes = [v["mape_pct"] for v in by_ratio.values() if v["mape_pct"] is not None]
    summary = {
        "layer": layer,
        "mode": mode_label,
        "ratios_passed_5pct": sum(1 for v in by_ratio.values() if v["passed_5pct"]),
        "ratios_computed_all_years": sum(1 for v in by_ratio.values() if v["n_ok"] == len(YEARS)),
        "avg_mape_pct": round(sum(valid_mapes) / len(valid_mapes), 2) if valid_mapes else None,
        "by_ratio": by_ratio,
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in CSV_FIELDS})


def print_summary_table(ticker: str, title: str, summary: dict[str, Any]) -> None:
    print(f"\n  [{ticker.upper()} | {title}]")
    print(f"    {'Rasio':<6} {'Terhitung':>9} {'MAE (pp)':>10} {'MAPE (%)':>10}  Klasifikasi")
    for rname, s in summary["by_ratio"].items():
        mae_s = f"{s['mae_pp']:.3f}" if s["mae_pp"] is not None else "-"
        mape_s = f"{s['mape_pct']:.2f}%" if s["mape_pct"] is not None else "-"
        tag = "OK" if s["passed_5pct"] else "--"
        print(f"    {rname:<6} {s['n_ok']}/{s['n_total']:>7} {mae_s:>10} {mape_s:>10}  {s['classification']:<15} {tag}")
    avg_s = f"{summary['avg_mape_pct']:.2f}%" if summary["avg_mape_pct"] is not None else "-"
    print(f"    Rata-rata MAPE: {avg_s} | Lolos <5%: {summary['ratios_passed_5pct']}/6")


def eval_ticker(ticker: str, *, layer1_only: bool = False, delay: float = 0.5, fresh: bool = False) -> dict[str, Any]:
    code = ticker.strip().lower()
    json_path = config.RESULTS / f"analyst_eval_{code}.json"
    csv_path = config.RESULTS / f"analyst_eval_{code}.csv"

    gt_extracted, official = an._load_extracted_from_gt(code)
    all_rows: list[dict[str, Any]] = []

    # --- Lapis 1: Formula pada Ground Truth mentah (0 token) ---
    l1_seojk = an.analyze_ratios(
        gt_extracted, "bank", years=YEARS, ticker=code, roa_mode="seojk_pbt", nim_use_average=True
    )
    rows_l1_seojk, sum_l1_seojk = score_analysis(code, "layer1_gt", "seojk_unified", l1_seojk, official)
    all_rows.extend(rows_l1_seojk)

    # Sensitivitas definisi (fn9 ROA after-tax & NIM saldo akhir, bahan Bab 4 & bimbingan 1.6)
    l1_fn9 = an.analyze_ratios(
        gt_extracted, "bank", years=YEARS, ticker=code, roa_mode="after_tax", nim_use_average=False
    )
    rows_l1_fn9, sum_l1_fn9 = score_analysis(code, "layer1_gt", "after_tax_nim_ending", l1_fn9, official)
    all_rows.extend(rows_l1_fn9)

    print(f"\n==================== {code.upper()} ====================")
    print_summary_table(code, "Lapis 1 GT — SEOJK Baku (PBT, NIM rata-rata)", sum_l1_seojk)
    print_summary_table(code, "Lapis 1 GT — Sensitivitas (ROA PAT, NIM saldo akhir)", sum_l1_fn9)

    e2e_extracted: dict[int, dict[str, Any]] | None = None
    e2e_stats: dict[str, Any] | None = None
    e2e_errors: list[str] = []
    sum_l2_seojk = None
    sum_l2_fn9 = None

    if not layer1_only:
        # Gunakan kembali ekstraksi tersimpan bila bukan --fresh
        if json_path.exists() and not fresh:
            prev = json.loads(json_path.read_text(encoding="utf-8"))
            if prev.get("e2e_extracted"):
                e2e_extracted = {int(k): v for k, v in prev["e2e_extracted"].items()}
                e2e_stats = prev.get("e2e_extraction_stats")
                e2e_errors = prev.get("e2e_extraction_errors", [])
                print(f"  [Lapis 2] Memakai hasil ekstraksi tersimpan di {json_path.name} (gunakan --fresh untuk ulang).")

        if e2e_extracted is None:
            print(f"  [Lapis 2] Menjalankan Extraction Agent (15 metrik x 2023-2025 + pembanding 2022)...", flush=True)
            res_main = ext.extract_metrics(
                ticker=code, years=list(YEARS), gate4_only=False, delay_between_groups=delay
            )
            res_2022 = ext.extract_metrics(
                ticker=code,
                years=2022,
                source_doc_year=2023,
                metric_keys=COMPARATIVE_2022_METRICS,
                delay_between_groups=delay,
            )
            e2e_extracted = {2022: res_2022["extracted_data"][2022], **res_main["extracted_data"]}
            s1, s2 = res_main["extraction_stats"], res_2022["extraction_stats"]
            e2e_stats = {
                "llm_calls": s1["llm_calls"] + s2["llm_calls"],
                "tool_calls": s1["tool_calls"] + s2["tool_calls"],
                "total_tokens": s1["total_tokens"] + s2["total_tokens"],
                "rate_limit_retries": s1["rate_limit_retries"] + s2["rate_limit_retries"],
                "tool_error_retries": s1["tool_error_retries"] + s2["tool_error_retries"],
                "seconds": round(s1["seconds"] + s2["seconds"], 2),
            }
            e2e_errors = [*res_2022["extraction_errors"], *res_main["extraction_errors"]]
            print(
                f"  [Lapis 2] Ekstraksi selesai: {e2e_stats['llm_calls']} LLM call, "
                f"{e2e_stats['total_tokens']:,} token, {e2e_stats['seconds']} s",
                flush=True,
            )

        l2_seojk = an.analyze_ratios(
            e2e_extracted, "bank", years=YEARS, ticker=code,
            allow_ending_fallback=True, roa_mode="seojk_pbt", nim_use_average=True,
        )
        rows_l2_seojk, sum_l2_seojk = score_analysis(code, "layer2_e2e", "seojk_unified", l2_seojk, official)
        all_rows.extend(rows_l2_seojk)
        print_summary_table(code, "Lapis 2 E2E — SEOJK Baku (PBT, NIM rata-rata)", sum_l2_seojk)

        l2_fn9 = an.analyze_ratios(
            e2e_extracted, "bank", years=YEARS, ticker=code,
            allow_ending_fallback=True, roa_mode="after_tax", nim_use_average=False,
        )
        rows_l2_fn9, sum_l2_fn9 = score_analysis(code, "layer2_e2e", "after_tax_nim_ending", l2_fn9, official)
        all_rows.extend(rows_l2_fn9)
        print_summary_table(code, "Lapis 2 E2E — Sensitivitas (ROA PAT, NIM saldo akhir)", sum_l2_fn9)

    payload = {
        "meta": {
            "task": "11.5 Financial Analyst Agent MAE/MAPE evaluation",
            "ticker": code,
            "role": "pengembangan" if code == config.DEV_TICKER else "uji",
            "years": list(YEARS),
            "provider": config.get_llm_provider(),
            "model": config.GROQ_MODEL,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        },
        "layer1_gt": {
            "seojk_unified": sum_l1_seojk,
            "after_tax_nim_ending": sum_l1_fn9,
        },
        "layer2_e2e": {
            "seojk_unified": sum_l2_seojk,
            "after_tax_nim_ending": sum_l2_fn9,
        } if sum_l2_seojk is not None else None,
        "e2e_extraction_stats": e2e_stats,
        "e2e_extraction_errors": e2e_errors,
        "e2e_extracted": {str(k): v for k, v in e2e_extracted.items()} if e2e_extracted is not None else None,
        "rows": all_rows,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(csv_path, all_rows)
    print(f"  Disimpan: {json_path.relative_to(ROOT)} & {csv_path.relative_to(ROOT)}")
    return payload


def combine() -> int:
    parts = {}
    all_rows = []
    for t in ("bbca", "bmri"):
        p = config.RESULTS / f"analyst_eval_{t}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            parts[t] = {
                "meta": d["meta"],
                "layer1_gt": d["layer1_gt"],
                "layer2_e2e": d["layer2_e2e"],
                "e2e_extraction_stats": d.get("e2e_extraction_stats"),
            }
            all_rows.extend(d.get("rows", []))
    if not parts:
        print("Belum ada hasil analyst_eval per emiten.")
        return 1
    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "per_ticker": parts,
    }
    (config.RESULTS / "analyst_eval.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(config.RESULTS / "analyst_eval.csv", all_rows)
    print("Digabungkan ke results/analyst_eval.json & results/analyst_eval.csv")
    return 0


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Evaluasi MAE/MAPE Financial Analyst Agent (Minggu 11-12).")
    ap.add_argument("--ticker", help="bbca atau bmri")
    ap.add_argument("--all", action="store_true", help="jalankan BBCA lalu BMRI dan gabungkan")
    ap.add_argument("--layer1-only", action="store_true", help="hanya Lapis 1 GT (0 token API)")
    ap.add_argument("--delay", type=float, default=0.5, help="jeda antar kelompok ekstraksi")
    ap.add_argument("--fresh", action="store_true", help="abaikan hasil ekstraksi tersimpan di JSON")
    ap.add_argument("--combine", action="store_true", help="gabungkan hasil BBCA & BMRI")
    args = ap.parse_args(argv)

    if args.combine:
        sys.exit(combine())
    if args.all:
        for t in ("bbca", "bmri"):
            eval_ticker(t, layer1_only=args.layer1_only, delay=args.delay, fresh=args.fresh)
        sys.exit(combine())
    if not args.ticker:
        ap.error("--ticker, --all, atau --combine wajib diisi")
    eval_ticker(args.ticker, layer1_only=args.layer1_only, delay=args.delay, fresh=args.fresh)


if __name__ == "__main__":
    main()
