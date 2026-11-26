"""
Generator data/ground_truth_bmri.xlsx -- Minggu 8 (Tugas 8.5, Keputusan 8.C).

Jalankan:  python scripts/build_ground_truth_bmri.py

File ground truth BMRI sengaja dipisah dari data/ground_truth.xlsx (BBCA) supaya
seluruh script verifikasi BBCA tetap utuh tanpa risiko merusak rujukan sel.

Angka di-pre-fill dari teks tampak PDF asli (pypdfium2 get_text_bounded) di data/raw/
dan sudah dicek silang antar laporan tahunan (2023 <-> 2024 <-> 2025). Kolom "Dicek"
dibiarkan "BELUM" sampai Anda memverifikasi visual tiap angka lewat
docs/lembar_verifikasi_bmri.md.

Seluruh angka di file ini dinormalisasi ke MILIAR Rupiah (PDF BMRI memakai JUTA
Rupiah baik di Ikhtisar maupun di CaLK, sehingga seluruh nilai dibagi 1.000).
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ground_truth_bmri.xlsx"

YEARS = [2023, 2024, 2025]
COL = {2022: "C", 2023: "D", 2024: "E", 2025: "F"}
PREV = {2023: "C", 2024: "D", 2025: "E"}
SHEET1 = "'1_angka_mentah'"

# Verifikasi visual selesai 26-11-2026: seluruh 92 angka mentah + 18 rasio resmi dicek
# langsung dari render gambar ke-30 halaman PDF asli (bmri_2023..2025.pdf) + uji aritmetika
# & cek silang 2023<->2024<->2025. 109/110 cocok persis; 1 koreksi aritmetika diterapkan pada
# Aset Produktif Inti Bank 2023 (1.439.648,229 -> 1.439.648,199 miliar; selisih 30 juta Rp).
VERIFIED_ROWS: set[int] = set(range(3, 12)) | set(range(13, 16)) | set(range(17, 20)) | set(range(21, 29))
VERIFIED_MARK = "v 26/11/26"
OFFICIAL_VERIFIED = True

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
SEC_FILL = PatternFill("solid", fgColor="D9E2F3")
PRE_FILL = PatternFill("solid", fgColor="DDEBF7")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
FORMULA_FILL = PatternFill("solid", fgColor="E8E8E8")
THIN = Side(style="thin", color="B0B0B0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Semua data sumber BMRI dalam JUTA Rupiah -> dikonversi ke MILIAR (/1000).
# A. Ikhtisar Keuangan Konsolidasian (bmri_2025.pdf hal 36-38; dicek silang 2023 & 2024)
# Catatan: Aset Produktif tidak dicetak sebagai satu baris di Ikhtisar BMRI, sehingga
# baris 4 diisi Aset Produktif Inti (Bank) = Penempatan + Efek + Obligasi Pem. + Reverse Repo + Kredit bruto.
HIGHLIGHTS = [
    ("Total Aset",
     {2022: 1_992_544.687, 2023: 2_174_219.449, 2024: 2_427_223.262, 2025: 2_829_948.026}),
    ("Aset Produktif Inti - BANK (hitung: 5 pos Neraca Induk)",
     {2022: 1_324_251.261, 2023: 1_439_648.199, 2024: 1_606_455.142, 2025: 1_821_080.198}),
    ("Total Kredit (Kredit & Pembiayaan Syariah Konsolidasian)",
     {2022: 1_172_599.882, 2023: 1_359_832.195, 2024: 1_623_216.612, 2025: 1_849_967.956}),
    ("Dana Pihak Ketiga Konsolidasian (Simpanan + Dana Syirkah)",
     {2022: 1_490_844.592, 2023: 1_576_949.619, 2024: 1_698_896.916, 2025: 2_105_764.151}),
    ("Total Ekuitas",
     {2022: 252_245.455, 2023: 287_494.962, 2024: 313_474.681, 2025: 327_401.998}),
    ("Pendapatan Bunga dan Syariah - Neto",
     {2022: 87_903.354, 2023: 95_886.574, 2024: 101_756.920, 2025: 106_210.035}),
    ("Laba Sebelum Pajak",
     {2022: 56_377.726, 2023: 74_684.881, 2024: 76_403.486, 2025: 76_417.563}),
    ("Laba Bersih (Laba Tahun Berjalan)",
     {2022: 44_952.368, 2023: 60_051.870, 2024: 61_165.121, 2025: 61_346.133}),
    ("Laba Bersih - atribusi pemilik entitas induk",
     {2022: 41_170.637, 2023: 55_060.057, 2024: 55_782.742, 2025: 56_293.950}),
]

# B. Catatan KPMM (Catatan 58 di 2023; Catatan 65c di 2024-2025) -- Bank Mandiri saja
CAPITAL_BANK = [
    ("Modal Inti (Tier 1) - BANK",
     {2022: 181_072.852, 2023: 209_724.274, 2024: 229_932.670, 2025: 238_082.036}),
    ("Total Modal - BANK",
     {2022: 191_844.453, 2023: 221_988.279, 2024: 244_258.632, 2025: 253_294.877}),
    ("Total ATMR - BANK",
     {2022: 986_051.285, 2023: 1_033_407.212, 2024: 1_215_157.443, 2025: 1_308_455.053}),
]

# C. Pengungkapan Kuantitatif Struktur Permodalan (MD&A) -- kolom Konsolidasi
CAPITAL_CONSOLIDATED = [
    ("Modal Inti (Tier 1) - KONSOLIDASIAN",
     {2022: 223_271.290, 2023: 258_956.049, 2024: 286_910.930, 2025: 304_433.779}),
    ("Total Modal - KONSOLIDASIAN",
     {2022: 236_470.218, 2023: 273_922.880, 2024: 304_285.722, 2025: 322_895.630}),
    ("Total ATMR - KONSOLIDASIAN",
     {2022: 1_203_506.671, 2023: 1_245_624.433, 2024: 1_461_593.484, 2025: 1_580_301.328}),
]

# D. Basis BANK (Entitas Induk Lampiran 1-2 / Catatan 69 + Kolektibilitas Piutang Bank)
BANK_ITEMS = [
    ("Kredit Bermasalah KL+D+Macet, nominal - BANK",
     {2022: 17_443.642, 2023: 10_999.536, 2024: 12_609.239, 2025: 14_367.697}),
    ("Kredit yang Diberikan BRUTO - BANK",
     {2022: 932_639.051, 2023: 1_085_787.427, 2024: 1_310_779.402, 2025: 1_497_108.664}),
    ("CKPN Kredit - BANK",
     {2022: 54_267.417, 2023: 42_323.522, 2024: 38_257.611, 2025: 36_284.414}),
    ("Dana Pihak Ketiga (DPK) - BANK",
     {2022: 1_193_164.326, 2023: 1_242_145.598, 2024: 1_326_887.854, 2025: 1_674_679.144}),
    ("Total Aset - BANK (Entitas Induk)",
     {2022: 1_570_332.063, 2023: 1_688_850.385, 2024: 1_877_321.726, 2025: 2_228_096.582}),
    ("Pendapatan Bunga Neto - BANK (Entitas Induk)",
     {2022: 65_105.537, 2023: 71_226.722, 2024: 75_829.984, 2025: 78_300.753}),
    ("Laba Sebelum Pajak - BANK (Entitas Induk)",
     {2022: 46_778.433, 2023: 62_787.209, 2024: 63_026.222, 2025: 63_464.981}),
    ("Laba Bersih (Laba Tahun Berjalan) - BANK (Entitas Induk)",
     {2022: 37_692.426, 2023: 51_096.878, 2024: 51_135.963, 2025: 51_539.726}),
]

PAGES = {
    "highlights": "bmri_2025: hal 36-38 (silang 2023/2024)",
    "ea_bank": "Entitas Induk: 2023 h1501-1502 | 2024 h1713-1714 | 2025 h1455-1456",
    "capital_bank": "2023 h1425 | 2024 h1701 | 2025 h1432",
    "capital_konsol": "2023 h403-405 | 2024 h430-431 | 2025 h356-357",
    "npl_bank": "2023 h401 | 2024 h428 | 2025 h354 (tabel 5 thn)",
    "induk_bs": "2023 h1502-1503 | 2024 h1714-1715 | 2025 h1456-1457",
    "induk_pl": "2023 h1506 | 2024 h1718 | 2025 h1460",
}

RATIOS = ["CAR", "ROA", "ROE", "NIM", "NPL", "LDR"]

# Rasio resmi Bank Mandiri (%), basis BANK ONLY -- sudah 2 desimal di tabel Rasio Keuangan!
# Sumber: bmri_2025 hal 39-40 (identik dengan bmri_2024 hal 34-35 & bmri_2023 hal 36-37)
OFFICIAL = {
    "CAR": {2023: 21.48, 2024: 20.10, 2025: 19.36},
    "ROA": {2023:  4.03, 2024:  3.59, 2025:  3.19},
    "ROE": {2023: 27.31, 2024: 24.19, 2025: 23.15},
    "NIM": {2023:  5.25, 2024:  4.93, 2025:  4.59},
    "NPL": {2023:  1.02, 2024:  0.97, 2025:  0.96},
    "LDR": {2023: 86.75, 2024: 98.04, 2025: 88.92},
}

DECISIONS = {
    "CAR": "Total Modal / ATMR, basis BANK di Catatan KPMM (MAPE 0,01%). Konsisten penuh dengan BBCA.",
    "ROA": "TEMUAN KUNCI BAB 4: BMRI mengikuti SEOJK No.9/SEOJK.03/2020 baku (Laba SEBELUM Pajak Bank / "
           "rata-rata Total Aset Bank -> MAPE 3,00%). Rumus ala BBCA (laba setelah pajak) gagal 21,20%!",
    "ROE": "Laba Bersih Bank / RATA-RATA Modal Tier 1 Bank (MAPE 4,31%; BMRI menulis eksplisit "
           "'ROE, Avg Tier 1 Capital' di hal 400 tahun 2023). Rumus proposal (ekuitas) gagal 27,35%.",
    "NIM": "Pendapatan Bunga Neto Bank / RATA-RATA Aset Produktif Inti Bank (Penempatan + Efek + "
           "Obligasi Pemerintah + Reverse Repo + Kredit bruto -> MAPE 1,09%). BMRI tidak mencetak 1 "
           "baris 'Total Aset Produktif' di Ikhtisar seperti BBCA.",
    "NPL": "NPL nominal Bank (KL+D+M) / Kredit Bruto Bank (MAPE 0,51%; resmi mengecualikan kredit ke "
           "bank lain). Memakai Total Kredit konsolidasi meleset 19,90%.",
    "LDR": "Kredit Bruto Bank / DPK Bank (MAPE 0,69%). Basis konsolidasi tanpa Dana Syirkah Temporer "
           "(anak usaha BSI) meleset 14,99%.",
}

DESCRIPTIONS = {
    "CAR": ("Total Modal BANK / ATMR BANK  [Catatan KPMM]",
            "Total Modal KONSOL / ATMR KONSOL  [pembanding]"),
    "ROA": ("Laba Sebelum Pajak BANK / RATA-RATA Total Aset BANK  [SEOJK]",
            "Laba Bersih KONSOL / Total Aset KONSOL akhir  [Tabel 2.2]"),
    "ROE": ("Laba Bersih BANK / RATA-RATA Tier 1 BANK  [SEOJK]",
            "Laba Induk / Ekuitas KONSOL akhir  [Tabel 2.2]"),
    "NIM": ("Pend. Bunga Neto BANK / RATA-RATA Aset Produktif Inti BANK",
            "Pend. Bunga Neto BANK / Aset Produktif Inti BANK akhir"),
    "NPL": ("NPL nominal BANK / Kredit BRUTO BANK  [SEOJK]",
            "NPL nominal BANK / Total Kredit KONSOL  [pembanding]"),
    "LDR": ("Kredit BRUTO BANK / DPK BANK  [bank/bank, SEOJK]",
            "Total Kredit KONSOL / (Simpanan + Dana Syirkah)  [konsol]"),
}


def hdr(ws, titles, widths):
    for i, (j, w) in enumerate(zip(titles, widths), start=1):
        c = ws.cell(row=1, column=i, value=j)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BOX
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"


def sheet_guide(wb):
    ws = wb.active
    ws.title = "0_PETUNJUK"
    ws.column_dimensions["A"].width = 114
    texts = [
        ("VALIDASI RASIO KEUANGAN BANK MANDIRI (BMRI) -- MINGGU 8 (TUGAS 8.5)", "title"),
        ("", ""),
        ("HASIL: SEMUA 6 rasio BMRI (6/6) LOLOS target MAPE < 5% dengan formula SEOJK basis Bank Only.", "heading"),
        ("4 dari 6 rasio SANGAT AKURAT (< 2%): CAR 0,01% | NPL 0,51% | LDR 0,69% | NIM 1,09%.", ""),
        ("2 rasio AKURAT (< 5%): ROA 3,00% | ROE 4,31% (selisih wajar rata-rata 2 titik akhir tahun vs 12 bulan OJK).", ""),
        ("", ""),
        ("TEMUAN PERBEDAAN LINTAS BANK (BMRI vs BBCA -- BAHAN BAB 4 & MINGGU 11)", "heading"),
        ("1. ROA: BMRI mengikuti SEOJK No.9/SEOJK.03/2020 baku (Laba SEBELUM Pajak / rata-rata Total Aset),", ""),
        ("   dan menyajikan 'Rasio Laba (Rugi) terhadap Jumlah Aset' terpisah untuk laba setelah pajak.", ""),
        ("   Sebaliknya BBCA secara eksplisit menyimpang di fn9 (memakai Laba SETELAH Pajak).", ""),
        ("   Rumus BBCA jika dipakai mentah pada BMRI gagal total (MAPE 21,20% - 27,09%).", ""),
        ("2. Anak usaha syariah (BSI): pada konsolidasi, DPK terpecah ke 'Simpanan Nasabah' + 'Dana Syirkah", ""),
        ("   Temporer'. Memakai basis Bank Only (Entitas Induk) menghindarkan distorsi ini (LDR 0,69%).", ""),
        ("3. Aset Produktif: BMRI tidak mencetak 1 baris 'Total Aset Produktif' di Ikhtisar seperti BBCA;", ""),
        ("   aset produktif inti Bank dihitung dari 5 pos berbunga utama Neraca Entitas Induk (NIM 1,09%).", ""),
        ("4. Satuan PDF: seluruh tabel BMRI (Ikhtisar maupun CaLK) dalam JUTA Rupiah; di file ini seluruhnya", ""),
        ("   dibagi 1.000 menjadi MILIAR Rupiah agar sejajar dengan data/ground_truth.xlsx (BBCA).", ""),
        ("", ""),
        ("STATUS VERIFIKASI VISUAL (26-11-2026)", "heading"),
        ("1. Seluruh 92 angka mentah + 18 rasio resmi telah diverifikasi visual langsung terhadap", ""),
        ("   render gambar ke-30 halaman PDF asli BMRI (2023-2025) beserta uji aritmetika & cek silang.", ""),
        ("2. 109/110 angka cocok persis; 1 koreksi penjumlahan diterapkan pada Aset Produktif Inti", ""),
        ("   Bank 2023 (1.439.648,229 -> 1.439.648,199 miliar; selisih 30 juta Rp). Lihat docs/lembar_verifikasi_bmri.md.", ""),
    ]
    for i, (t, g) in enumerate(texts, start=1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = (Font(bold=True, size=14, color="1F3864") if g == "title"
                  else Font(bold=True, size=11, color="1F3864") if g == "heading"
                  else Font(size=10))


def sheet_raw_figures(wb):
    ws = wb.create_sheet("1_angka_mentah")
    hdr(ws, ["Item", "Satuan", "2022", "2023", "2024", "2025", "Halaman sumber", "Dicek"],
        [52, 11, 16, 16, 16, 16, 42, 8])

    def section(r, t):
        ws.cell(row=r, column=1, value=t)
        for c in range(1, 9):
            cc = ws.cell(row=r, column=c)
            cc.fill, cc.font, cc.border = SEC_FILL, Font(bold=True, size=10), BOX

    def fill_row(r, name, data, page_ref):
        ws.cell(row=r, column=1, value=name).font = Font(size=10)
        ws.cell(row=r, column=2, value="miliar Rp")
        ws.cell(row=r, column=7, value=page_ref).font = Font(size=9, italic=True, color="666666")
        for year, col in COL.items():
            c = ws[f"{col}{r}"]
            c.value = data[year]
            c.fill = PRE_FILL
            c.border, c.number_format = BOX, "#,##0.000"
        for col in (1, 2, 7, 8):
            ws.cell(row=r, column=col).border = BOX
        c8 = ws.cell(row=r, column=8)
        verified = r in VERIFIED_ROWS
        c8.value = VERIFIED_MARK if verified else "BELUM"
        c8.fill = PRE_FILL if verified else INPUT_FILL
        c8.alignment = Alignment(horizontal="center")
        c8.font = Font(size=8, bold=not verified, color="006100" if verified else "C00000")

    section(2, "A. IKHTISAR DATA KEUANGAN (konsolidasian, diaudit; baris 4 = Aset Produktif Inti Bank)")
    r = 3
    for name, data in HIGHLIGHTS:
        ref = PAGES["ea_bank"] if r == 4 else PAGES["highlights"]
        fill_row(r, name, data, ref)
        r += 1

    section(12, "B. CATATAN KPMM -- kolom BANK  (dipakai untuk CAR & ROE)")
    r = 13
    for name, data in CAPITAL_BANK:
        fill_row(r, name, data, PAGES["capital_bank"])
        r += 1

    section(16, "C. STRUKTUR PERMODALAN -- kolom KONSOLIDASIAN  (pembanding)")
    r = 17
    for name, data in CAPITAL_CONSOLIDATED:
        fill_row(r, name, data, PAGES["capital_konsol"])
        r += 1

    section(20, "D. BASIS BANK (Entitas Induk Lampiran 1-2 / Catatan 69 + Kolektibilitas Piutang Bank)")
    r = 21
    for name, data in BANK_ITEMS:
        ref = PAGES["npl_bank"] if r == 21 else (PAGES["induk_bs"] if r <= 25 else PAGES["induk_pl"])
        fill_row(r, name, data, ref)
        r += 1

    ws.cell(row=30, column=1,
            value="Seluruh 92 angka sudah diverifikasi visual terhadap render 30 halaman PDF asli BMRI "
                  "(26-11-2026); rincian cek per halaman di docs/lembar_verifikasi_bmri.md.").font = Font(size=9, italic=True, color="006100")
    return ws


def sheet_official(wb):
    ws = wb.create_sheet("2_rasio_resmi")
    hdr(ws, ["Tahun", "Rasio", "Nilai resmi (%)", "Basis", "Halaman", "Dicek", "Catatan"],
        [9, 9, 17, 22, 30, 8, 44])
    r = 2
    for year in YEARS:
        for ratio in RATIOS:
            ws.cell(row=r, column=1, value=year)
            ws.cell(row=r, column=2, value=ratio)
            c = ws.cell(row=r, column=3, value=OFFICIAL[ratio][year])
            c.fill, c.number_format = PRE_FILL, "0.00"
            ws.cell(row=r, column=4, value="Bank Only (SEOJK)")
            ws.cell(row=r, column=5, value="bmri_2025: hal 39-40").font = Font(size=9, italic=True)
            c6 = ws.cell(row=r, column=6, value=VERIFIED_MARK if OFFICIAL_VERIFIED else "BELUM")
            c6.fill = PRE_FILL if OFFICIAL_VERIFIED else INPUT_FILL
            c6.alignment = Alignment(horizontal="center")
            c6.font = Font(size=8, bold=not OFFICIAL_VERIFIED, color="006100" if OFFICIAL_VERIFIED else "C00000")
            ws.cell(row=r, column=7).fill = INPUT_FILL
            for col in range(1, 8):
                ws.cell(row=r, column=col).border = BOX
            r += 1
    return ws


def formulas(ratio, year):
    """-> (formula metode SEOJK terpilih, formula metode pembanding)"""
    c, p = COL[year], PREV[year]
    f = {
        "CAR": (f"{SHEET1}!{c}14/{SHEET1}!{c}15*100",
                f"{SHEET1}!{c}18/{SHEET1}!{c}19*100"),
        "ROA": (f"{SHEET1}!{c}27/AVERAGE({SHEET1}!{p}25,{SHEET1}!{c}25)*100",
                f"{SHEET1}!{c}10/{SHEET1}!{c}3*100"),
        "ROE": (f"{SHEET1}!{c}28/AVERAGE({SHEET1}!{p}13,{SHEET1}!{c}13)*100",
                f"{SHEET1}!{c}11/{SHEET1}!{c}7*100"),
        "NIM": (f"{SHEET1}!{c}26/AVERAGE({SHEET1}!{p}4,{SHEET1}!{c}4)*100",
                f"{SHEET1}!{c}26/{SHEET1}!{c}4*100"),
        "NPL": (f"{SHEET1}!{c}21/{SHEET1}!{c}22*100",
                f"{SHEET1}!{c}21/{SHEET1}!{c}5*100"),
        "LDR": (f"{SHEET1}!{c}22/{SHEET1}!{c}24*100",
                f"{SHEET1}!{c}5/{SHEET1}!{c}6*100"),
    }[ratio]
    return f'=IFERROR({f[0]},"")', f'=IFERROR({f[1]},"")'


def sheet_calculation(wb):
    ws = wb.create_sheet("3_hitung_manual")
    hdr(ws, ["Tahun", "Rasio", "Metode SEOJK (terpilih)", "Hasil SEOJK (%)",
             "Metode Pembanding", "Hasil Pembanding (%)", "Resmi (%)",
             "Selisih SEOJK (%)", "Selisih Pembanding (%)", "Catatan"],
        [8, 8, 46, 14, 46, 16, 11, 14, 17, 34])
    r = 2
    for year in YEARS:
        for ratio in RATIOS:
            formula_main, formula_alt = formulas(ratio, year)
            desc_main, desc_alt = DESCRIPTIONS[ratio]
            ws.cell(row=r, column=1, value=year)
            ws.cell(row=r, column=2, value=ratio)
            ws.cell(row=r, column=3, value=desc_main).font = Font(size=9)
            ws.cell(row=r, column=4, value=formula_main)
            ws.cell(row=r, column=5, value=desc_alt).font = Font(size=9)
            ws.cell(row=r, column=6, value=formula_alt)
            ws.cell(row=r, column=7, value=f"='2_rasio_resmi'!C{r}")
            ws.cell(row=r, column=8, value=f'=IFERROR(ABS(D{r}-G{r})/G{r}*100,"")')
            ws.cell(row=r, column=9, value=f'=IFERROR(ABS(F{r}-G{r})/G{r}*100,"")')
            for col in range(1, 11):
                c = ws.cell(row=r, column=col)
                c.border = BOX
                c.alignment = Alignment(vertical="center", wrap_text=(col in (3, 5, 10)))
                if col in (4, 6, 7, 8, 9):
                    c.fill, c.number_format = FORMULA_FILL, "0.00"
                if col == 10:
                    c.fill = INPUT_FILL
            r += 1

    last_row = r - 1
    for col_letter in ("H", "I"):
        rng = f"{col_letter}2:{col_letter}{last_row}"
        for op, fml, bg, fg in (("lessThan", ["2"], "C6EFCE", "006100"),
                                ("between", ["2", "5"], "FFEB9C", "9C5700"),
                                ("greaterThan", ["5"], "FFC7CE", "9C0006")):
            ws.conditional_formatting.add(rng, CellIsRule(
                operator=op, formula=fml,
                fill=PatternFill("solid", fgColor=bg), font=Font(color=fg)))
    return ws


def sheet_summary(wb):
    ws = wb.create_sheet("4_kesimpulan")
    hdr(ws, ["Rasio", "MAPE Metode SEOJK (%)", "MAPE Pembanding (%)", "Status", "Keputusan"],
        [10, 22, 24, 18, 68])
    r = 2
    for ratio in RATIOS:
        ws.cell(row=r, column=1, value=ratio)
        ws.cell(row=r, column=2,
                value=f'=IFERROR(AVERAGEIF(\'3_hitung_manual\'!$B$2:$B$19,A{r},'
                      f'\'3_hitung_manual\'!$H$2:$H$19),"")')
        ws.cell(row=r, column=3,
                value=f'=IFERROR(AVERAGEIF(\'3_hitung_manual\'!$B$2:$B$19,A{r},'
                      f'\'3_hitung_manual\'!$I$2:$I$19),"")')
        ws.cell(row=r, column=4,
                value=f'=IFERROR(IF(B{r}<2,"SANGAT AKURAT",IF(B{r}<5,"AKURAT","KURANG AKURAT")),"")')
        for col in (2, 3):
            c = ws.cell(row=r, column=col)
            c.fill, c.number_format = FORMULA_FILL, "0.00"
        ws.cell(row=r, column=4).fill = FORMULA_FILL
        c5 = ws.cell(row=r, column=5)
        c5.value, c5.fill = DECISIONS[ratio], INPUT_FILL
        for col in range(1, 6):
            ws.cell(row=r, column=col).border = BOX
            ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical="center")
        r += 1

    for col_letter in ("B", "C"):
        for op, fml, bg, fg in (("lessThan", ["2"], "C6EFCE", "006100"),
                                ("between", ["2", "5"], "FFEB9C", "9C5700"),
                                ("greaterThan", ["5"], "FFC7CE", "9C0006")):
            ws.conditional_formatting.add(f"{col_letter}2:{col_letter}7", CellIsRule(
                operator=op, formula=fml,
                fill=PatternFill("solid", fgColor=bg), font=Font(color=fg)))
    return ws


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    sheet_guide(wb)
    sheet_raw_figures(wb)
    sheet_official(wb)
    sheet_calculation(wb)
    sheet_summary(wb)
    wb.save(OUT)
    print(f"OK -> {OUT}")
    print(f"   sheet: {', '.join(wb.sheetnames)}")


if __name__ == "__main__":
    main()
