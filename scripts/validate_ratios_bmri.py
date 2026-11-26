"""
Tugas 8.5 -- validasi 6 rasio resmi Bank Mandiri (BMRI) terhadap formula SEOJK & pembanding.

Jalankan:  python scripts/validate_ratios_bmri.py

Sumber angka: data/ground_truth_bmri.xlsx (dibangun oleh scripts/build_ground_truth_bmri.py
dari teks tampak PDF asli via pypdfium2 get_text_bounded).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts import build_ground_truth_bmri as gt
from src import config

YEARS = gt.YEARS

# Ambil langsung dari satu sumber kebenaran (build_ground_truth_bmri.py), dalam MILIAR Rupiah
H = {
    "total_assets":        gt.HIGHLIGHTS[0][1],
    "ea_bank":             gt.HIGHLIGHTS[1][1],
    "total_loans":         gt.HIGHLIGHTS[2][1],
    "deposits_total":      gt.HIGHLIGHTS[3][1],
    "total_equity":        gt.HIGHLIGHTS[4][1],
    "net_interest_income": gt.HIGHLIGHTS[5][1],
    "profit_before_tax":   gt.HIGHLIGHTS[6][1],
    "net_income":          gt.HIGHLIGHTS[7][1],
    "net_income_parent":   gt.HIGHLIGHTS[8][1],
}
CAP_BANK = {
    "tier1":         gt.CAPITAL_BANK[0][1],
    "total_capital": gt.CAPITAL_BANK[1][1],
    "rwa":           gt.CAPITAL_BANK[2][1],
}
CAP_KONSOL = {
    "tier1":         gt.CAPITAL_CONSOLIDATED[0][1],
    "total_capital": gt.CAPITAL_CONSOLIDATED[1][1],
    "rwa":           gt.CAPITAL_CONSOLIDATED[2][1],
}
BANK = {
    "npl_amount":          gt.BANK_ITEMS[0][1],
    "gross_loans":         gt.BANK_ITEMS[1][1],
    "ckpn":                gt.BANK_ITEMS[2][1],
    "deposits":            gt.BANK_ITEMS[3][1],
    "total_assets":        gt.BANK_ITEMS[4][1],
    "net_interest_income": gt.BANK_ITEMS[5][1],
    "profit_before_tax":   gt.BANK_ITEMS[6][1],
    "net_income":          gt.BANK_ITEMS[7][1],
}
OFFICIAL = gt.OFFICIAL


def average(d, t):
    return (d[t - 1] + d[t]) / 2


CANDIDATES = {
    "CAR": {
        "A: Total modal / ATMR  [BANK - Catatan KPMM]":
            lambda t: CAP_BANK["total_capital"][t] / CAP_BANK["rwa"][t] * 100,
        "B: Total modal / ATMR  [konsolidasi]":
            lambda t: CAP_KONSOL["total_capital"][t] / CAP_KONSOL["rwa"][t] * 100,
    },
    "ROA": {
        "A: Laba sebelum pajak BANK / RATA-RATA aset BANK  [SEOJK]":
            lambda t: BANK["profit_before_tax"][t] / average(BANK["total_assets"], t) * 100,
        "B: Laba sebelum pajak KONSOL / RATA-RATA aset KONSOL":
            lambda t: H["profit_before_tax"][t] / average(H["total_assets"], t) * 100,
        "C: Laba bersih BANK / RATA-RATA aset BANK  [gaya fn9 BCA]":
            lambda t: BANK["net_income"][t] / average(BANK["total_assets"], t) * 100,
        "D: Laba bersih KONSOL / Total aset akhir  [Tabel 2.2]":
            lambda t: H["net_income"][t] / H["total_assets"][t] * 100,
    },
    "ROE": {
        "A: Laba bersih BANK / RATA-RATA Tier 1 BANK  [SEOJK]":
            lambda t: BANK["net_income"][t] / average(CAP_BANK["tier1"], t) * 100,
        "B: Laba induk KONSOL / RATA-RATA Tier 1 BANK  [CAMPUR - jangan dipakai]":
            lambda t: H["net_income_parent"][t] / average(CAP_BANK["tier1"], t) * 100,
        "C: Laba induk KONSOL / Ekuitas KONSOL akhir  [Tabel 2.2]":
            lambda t: H["net_income_parent"][t] / H["total_equity"][t] * 100,
    },
    "NIM": {
        "A: Pend. bunga neto BANK / RATA-RATA Aset Prod. Inti BANK":
            lambda t: BANK["net_interest_income"][t] / average(H["ea_bank"], t) * 100,
        "B: Pend. bunga neto BANK / Aset Prod. Inti BANK akhir":
            lambda t: BANK["net_interest_income"][t] / H["ea_bank"][t] * 100,
        "C: Pend. bunga neto KONSOL / RATA-RATA Aset KONSOL":
            lambda t: H["net_interest_income"][t] / average(H["total_assets"], t) * 100,
    },
    "NPL": {
        "A: NPL nominal BANK / Kredit BRUTO BANK  [SEOJK]":
            lambda t: BANK["npl_amount"][t] / BANK["gross_loans"][t] * 100,
        "B: NPL nominal BANK / Total kredit KONSOL  [pembanding]":
            lambda t: BANK["npl_amount"][t] / H["total_loans"][t] * 100,
    },
    "LDR": {
        "A: Kredit BRUTO BANK / DPK BANK  [bank/bank, SEOJK]":
            lambda t: BANK["gross_loans"][t] / BANK["deposits"][t] * 100,
        "B: Total kredit KONSOL / (Simpanan + Syirkah)  [konsol]":
            lambda t: H["total_loans"][t] / H["deposits_total"][t] * 100,
    },
}


def main():
    print("=" * 100)
    print("  VALIDASI RASIO BANK MANDIRI (BMRI) -- MINGGU 8 (TUGAS 8.5)".center(100))
    print("  basis rasio resmi: BANK ONLY (SEOJK No.9/SEOJK.03/2020)".center(100))
    print("=" * 100)

    best = {}
    summary = {"ticker": "bmri", "years": YEARS, "ratios": {}}

    for ratio, formulas in CANDIDATES.items():
        print(f"\n{'-' * 100}\n  {ratio}   (resmi: "
              + ", ".join(f"{t}={OFFICIAL[ratio][t]:.2f}%" for t in YEARS) + ")\n" + "-" * 100)
        print(f"  {'Formula':<60} " + "".join(f"{t:>10}" for t in YEARS) + f"{'MAPE':>10}")
        ratio_rows = []
        for name, fn in formulas.items():
            vals, errors = {}, []
            row_str = ""
            for t in YEARS:
                v = fn(t)
                e = abs(v - OFFICIAL[ratio][t]) / OFFICIAL[ratio][t] * 100
                vals[str(t)] = round(v, 4)
                errors.append(e)
                row_str += f"{v:>9.2f}%"
            mape = sum(errors) / len(errors)
            tag = "  OK" if mape < 2 else ("  ~" if mape < 5 else "  GAGAL")
            print(f"  {name:<60} {row_str}{mape:>9.2f}%{tag}")
            ratio_rows.append({"formula": name, "values": vals, "mape": round(mape, 2)})
            if "jangan dipakai" not in name.lower():
                prev = best.get(ratio)
                if prev is None or mape < prev[1]:
                    best[ratio] = (name, mape)
        summary["ratios"][ratio] = {
            "official": {str(t): OFFICIAL[ratio][t] for t in YEARS},
            "selected": {"formula": best[ratio][0], "mape": round(best[ratio][1], 2)},
            "candidates": ratio_rows,
        }

    print("\n" + "=" * 100)
    print("  KESIMPULAN -- formula terbaik per rasio (BMRI)".center(100))
    print("=" * 100)
    print(f"  {'Rasio':<7}{'MAPE':>9}   {'Status':<14}Formula terpilih")
    for ratio in CANDIDATES:
        name, mape = best[ratio]
        status = "SANGAT AKURAT" if mape < 2 else ("AKURAT" if mape < 5 else "KURANG AKURAT")
        print(f"  {ratio:<7}{mape:>8.2f}%   {status:<14}{name}")

    passed = [r for r, (_, m) in best.items() if m < 5]
    failed = [r for r, (_, m) in best.items() if m >= 5]
    print(f"\n  Lolos target MAPE < 5% : {len(passed)}/{len(CANDIDATES)} ({', '.join(passed)})")
    print(f"  Tidak lolos            : {', '.join(failed) if failed else '-'}")

    out = config.RESULTS / "validate_ratios_bmri.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRingkasan disimpan -> {out.relative_to(ROOT)}")
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
