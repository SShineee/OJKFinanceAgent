"""
Tugas 1.5 -- validasi apakah 6 rasio resmi BCA bisa direproduksi dari laporan.

Jalankan:  python scripts/validate_ratios.py

Angka di bawah dibaca manual dari PDF di data/raw/ (lihat kolom `hal` tiap blok).
Script ini membandingkan beberapa kandidat formula terhadap rasio resmi BCA,
lalu melaporkan formula mana yang cocok.

PENTING -- dasar perhitungan resmi BCA (footnote tabel Rasio Keuangan):
  fn5  : "Induk perusahaan saja" -> rasio resmi berbasis BANK, bukan konsolidasi
  fn7  : NPL bruto = kredit bermasalah (KL+D+M) / total kredit
  fn9  : ROA  = laba SETELAH pajak / RATA-RATA total aset
  fn10 : ROE  = laba setelah pajak / RATA-RATA MODAL TIER 1   <-- bukan ekuitas!
  fn11 : NIM  = pendapatan bunga bersih / RATA-RATA aset produktif
"""

# ----------------------------------------------------------------- DATA
# Ikhtisar Data Keuangan 5 tahun (konsolidasi, diaudit), dalam MILIAR Rupiah
# hal: bbca_2024 hal 20 ; bbca_2025 hal 15
HIGHLIGHTS = {
    "total_assets":        {2021: 1_228_345, 2022: 1_314_732, 2023: 1_408_107, 2024: 1_449_301, 2025: 1_586_829},
    "earning_assets":    {2021: 1_125_418, 2022: 1_173_144, 2023: 1_266_223, 2024: 1_354_435, 2025: 1_479_307},
    "total_loans":      {2021:   636_987, 2022:   711_262, 2023:   810_392, 2024:   921_878, 2025:   992_901},
    "deposits":               {2021:   975_949, 2022: 1_039_718, 2023: 1_101_673, 2024: 1_133_612, 2025: 1_249_044},
    "total_equity":     {2021:   202_849, 2022:   221_182, 2023:   242_538, 2024:   262_835, 2025:   281_688},
    "net_interest_income": {2021:    55_987, 2022:    63_863, 2023:    74_938, 2024:    82_264, 2025:    85_548},
    "net_income":       {2021:    31_440, 2022:    40_756, 2023:    48_658, 2024:    54_851, 2025:    57_563},
    "net_income_parent": {2021:    31_423, 2022:    40_736, 2023:    48_639, 2024:    54_836, 2025:    57_537},
    "profit_before_tax":   {2021:    38_841, 2022:    50_467, 2023:    60_180, 2024:    68_218, 2025:    71_261},
}

# Catatan KPMM (Catatan 51f / 45), dalam JUTA Rupiah -> dibagi 1000 jadi miliar
# hal: bbca_2023 hal 727 (2023+2022) ; bbca_2024 hal 703 (2024+2023) ; bbca_2025 hal 594 (2025+2024)
CAPITAL_BANK = {
    "tier1":       {2022: 196_799_387, 2023: 217_686_126, 2024: 239_468_855, 2025: 258_057_396},
    "total_capital": {2022: 204_705_741, 2023: 226_426_139, 2024: 249_056_422, 2025: 268_244_808},
    "rwa":        {2022: 794_395_454, 2023: 769_200_928, 2024: 848_181_552, 2025: 901_270_630},
}
CAPITAL_CONSOLIDATED = {
    "tier1":       {2022: 212_445_689, 2023: 233_701_580, 2024: 255_311_302, 2025: 273_828_527},
    "total_capital": {2022: 220_568_562, 2023: 242_694_176, 2024: 265_198_025, 2025: 284_351_775},
    "rwa":        {2022: 821_723_312, 2023: 825_610_552, 2024: 910_183_696, 2025: 936_368_457},
}
# Kredit basis BANK (Entitas Induk) + nominal NPL, dalam JUTA Rupiah
# hal: Laporan Posisi Keuangan Entitas Induk -- bbca_2023 hal 738, bbca_2024 hal 704, bbca_2025 hal 595
# hal: nominal NPL -- Catatan "Non-Performing Loan": bbca_2023 hal 646, bbca_2024 hal 701, bbca_2025 hal 590
BANK_LOANS = {
    "net_loans": {2022: 657_248_705, 2023: 754_330_898, 2024: 862_530_076, 2025: 932_513_007},
    "loan_loss_allowance":        {2022:  33_892_635, 2023:  33_168_491, 2024:  32_382_006, 2025:  29_390_498},
    "npl_amount": {2022:  11_795_528, 2023:  14_147_246, 2024:  15_498_016, 2025:  15_965_436},
    # Simpanan dari nasabah, Entitas Induk (pihak berelasi + pihak ketiga)
    # hal: bbca_2023 h739, bbca_2024 h705, bbca_2025 h596
    "deposits":         {2022: 1_023_659_603, 2023: 1_081_852_159,
                    2024: 1_108_908_832, 2025: 1_219_567_546},
}
BANK_LOANS["gross_loans"] = {
    t: BANK_LOANS["net_loans"][t] + BANK_LOANS["loan_loss_allowance"][t] for t in BANK_LOANS["loan_loss_allowance"]
}

for d in (CAPITAL_BANK, CAPITAL_CONSOLIDATED, BANK_LOANS):
    for k in d:
        d[k] = {t: v / 1000 for t, v in d[k].items()}   # juta -> miliar

# Rasio resmi BCA (%), basis induk/bank -- hal: bbca_2025 hal 15-16
OFFICIAL = {
    "CAR": {2023: 29.4, 2024: 29.4, 2025: 29.8},
    "ROA": {2023: 3.6,  2024: 3.9,  2025: 3.9},
    "ROE": {2023: 23.5, 2024: 24.6, 2025: 23.3},
    "NIM": {2023: 5.5,  2024: 5.8,  2025: 5.7},
    "NPL": {2023: 1.9,  2024: 1.8,  2025: 1.7},
    "LDR": {2023: 70.2, 2024: 78.4, 2025: 76.8},
}

# Acuan PRESISI 2 desimal -- lebih baik dipakai daripada Ikhtisar yang dibulatkan
# 1 desimal, karena pembulatan itu sendiri menimbulkan error semu.
# CAR: Catatan KPMM kolom Bank | NPL: Catatan "Non-Performing Loan"
OFFICIAL_PRECISE = {
    "CAR": {2023: 29.44, 2024: 29.36, 2025: 29.76},
    "NPL": {2023: 1.86, 2024: 1.78, 2025: 1.71},
}
for r, d in OFFICIAL_PRECISE.items():
    OFFICIAL[r] = d

YEARS = [2023, 2024, 2025]
I = HIGHLIGHTS


def average(d, t):
    return (d[t - 1] + d[t]) / 2


# kandidat formula: nama -> fungsi(tahun) -> nilai % atau None
CANDIDATES = {
    "CAR": {
        "A: Total modal / ATMR  [konsolidasi]":
            lambda t: CAPITAL_CONSOLIDATED["total_capital"][t] / CAPITAL_CONSOLIDATED["rwa"][t] * 100,
        "B: Total modal / ATMR  [BANK - Catatan 51f]":
            lambda t: CAPITAL_BANK["total_capital"][t] / CAPITAL_BANK["rwa"][t] * 100,
    },
    "ROA": {
        "A: Laba bersih / Total aset akhir  [Tabel 2.2 proposal]":
            lambda t: I["net_income"][t] / I["total_assets"][t] * 100,
        "B: Laba setelah pajak / RATA-RATA total aset  [fn9 OJK]":
            lambda t: I["net_income"][t] / average(I["total_assets"], t) * 100,
    },
    "ROE": {
        "A: Laba induk / Ekuitas akhir  [Tabel 2.2 proposal]":
            lambda t: I["net_income_parent"][t] / I["total_equity"][t] * 100,
        "B: Laba induk / RATA-RATA ekuitas":
            lambda t: I["net_income_parent"][t] / average(I["total_equity"], t) * 100,
        "C: Laba bersih / RATA-RATA Tier 1 Bank  [fn10 OJK]":
            lambda t: I["net_income"][t] / average(CAPITAL_BANK["tier1"], t) * 100,
    },
    "NIM": {
        "A: Pend. bunga bersih / Aset produktif akhir":
            lambda t: I["net_interest_income"][t] / I["earning_assets"][t] * 100,
        "B: Pend. bunga bersih / RATA-RATA aset produktif  [fn11 OJK]":
            lambda t: I["net_interest_income"][t] / average(I["earning_assets"], t) * 100,
    },
    "LDR": {
        "A: Total kredit / DPK  [konsolidasi/konsolidasi]":
            lambda t: I["total_loans"][t] / I["deposits"][t] * 100,
        "B: Kredit bruto BANK / DPK BANK  [bank/bank, fn5]":
            lambda t: BANK_LOANS["gross_loans"][t] / BANK_LOANS["deposits"][t] * 100,
        "C: Kredit bruto BANK / DPK konsolidasi  [CAMPUR - jangan dipakai]":
            lambda t: BANK_LOANS["gross_loans"][t] / I["deposits"][t] * 100,
    },
    "NPL": {
        "A: NPL nominal / Total kredit ikhtisar  [konsolidasi]":
            lambda t: BANK_LOANS["npl_amount"][t] / I["total_loans"][t] * 100,
        "B: NPL nominal / Kredit BRUTO BANK  [fn7, basis bank]":
            lambda t: BANK_LOANS["npl_amount"][t] / BANK_LOANS["gross_loans"][t] * 100,
    },
}


def main():
    print("=" * 96)
    print("  VALIDASI RASIO BCA -- GATE 1".center(96))
    print("  basis rasio resmi: INDUK PERUSAHAAN SAJA (footnote 5)".center(96))
    print("=" * 96)

    best = {}
    for ratio, formulas in CANDIDATES.items():
        print(f"\n{'-' * 96}\n  {ratio}   (resmi: " +
              ", ".join(f"{t}={OFFICIAL[ratio][t]}%" for t in YEARS) + ")\n" + "-" * 96)
        print(f"  {'Formula':<56} " + "".join(f"{t:>12}" for t in YEARS) + f"{'MAPE':>10}")

        for name, fn in formulas.items():
            errors, row = [], ""
            for t in YEARS:
                try:
                    v = fn(t)
                except (KeyError, TypeError, ZeroDivisionError):
                    v = None
                if v is None:
                    row += f"{'-':>12}"
                else:
                    e = abs(v - OFFICIAL[ratio][t]) / OFFICIAL[ratio][t] * 100
                    errors.append(e)
                    row += f"{v:>11.2f}%"
            mape = sum(errors) / len(errors) if errors else None
            tag = ""
            if mape is not None:
                tag = "  OK" if mape < 2 else ("  ~" if mape < 5 else "  GAGAL")
            m = f"{mape:>9.2f}%" if mape is not None else f"{'-':>10}"
            print(f"  {name:<56} {row}{m}{tag}")
            # Formula yang ditandai "jangan dipakai" dikecualikan dari pemilihan
            # otomatis: ia mungkin paling cocok secara angka, tapi tidak sah
            # secara metodologi (mis. mencampur basis bank dan konsolidasi).
            if mape is not None and "jangan dipakai" not in name.lower():
                prev = best.get(ratio)
                if prev is None or mape < prev[1]:
                    best[ratio] = (name, mape)

        print(f"  {'selisih thd resmi (%)':<56}", end="")
        print()

    print("\n" + "=" * 96)
    print("  KESIMPULAN -- formula terbaik per rasio".center(96))
    print("=" * 96)
    print(f"  {'Rasio':<7}{'MAPE':>9}   {'Status':<14}Formula terpilih")
    for ratio in CANDIDATES:
        if ratio not in best:
            print(f"  {ratio:<7}{'-':>9}   {'BELUM DIUJI':<14}butuh nominal dari CaLK")
            continue
        name, mape = best[ratio]
        status = "SANGAT AKURAT" if mape < 2 else ("AKURAT" if mape < 5 else "KURANG AKURAT")
        print(f"  {ratio:<7}{mape:>8.2f}%   {status:<14}{name}")

    passed = [r for r, (_, m) in best.items() if m < 5]
    failed = [r for r, (_, m) in best.items() if m >= 5]
    untested = [r for r in CANDIDATES if r not in best]
    print(f"\n  Lolos target MAPE < 5% : {', '.join(passed) if passed else '-'}")
    print(f"  Tidak lolos            : {', '.join(failed) if failed else '-'}")
    print(f"  Belum diuji            : {', '.join(untested) if untested else '-'}")


if __name__ == "__main__":
    main()
