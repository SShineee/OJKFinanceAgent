"""
Generator data/ground_truth.xlsx -- Minggu 1 (GATE 1).

Jalankan:  python scripts/build_ground_truth.py

Angka sudah DI-PRE-FILL dari hasil ekstraksi PDF di data/raw/ (lihat kolom
"Halaman"). Tugas Anda: VERIFIKASI tiap angka terhadap halaman yang disebut,
lalu centang kolom "Dicek". Jangan dipakai mentah-mentah untuk skripsi tanpa
dicek -- ini hasil baca otomatis, bisa salah.

Seluruh 15 item sudah terisi, termasuk kredit & NPL basis BANK (Entitas Induk).

AWAS: menjalankan ulang script ini MENIMPA file. Backup kalau sudah diisi.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ground_truth.xlsx"

YEARS = [2023, 2024, 2025]
COL = {2022: "C", 2023: "D", 2024: "E", 2025: "F"}

# Verifikasi manual tugas 1.5 selesai 22-10-2026: seluruh 72 angka dicocokkan
# ke halaman sumbernya lewat docs/lembar_verifikasi.md. TIDAK ADA koreksi.
VERIFIED_MARK = "v 22/10/26"
# Baris 24 (DPK BANK) ditambahkan 25-10-2026 untuk formula LDR bank/bank,
# jadi diverifikasi terpisah pada 26-10-2026.
LATE_VERIFIED_MARK = {24: "v 26/10/26"}
UNVERIFIED_ROWS = set()
PREV = {2023: "C", 2024: "D", 2025: "E"}
SHEET1 = "'1_angka_mentah'"

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
SEC_FILL = PatternFill("solid", fgColor="D9E2F3")
PRE_FILL = PatternFill("solid", fgColor="DDEBF7")   # biru muda = sudah di-prefill, verifikasi
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")   # kuning = Anda isi manual
FORMULA_FILL = PatternFill("solid", fgColor="E8E8E8")
THIN = Side(style="thin", color="B0B0B0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# ---- item: (nama, satuan, {tahun: nilai} atau None, halaman, catatan)
# Ikhtisar Data Keuangan 5 tahun -- konsolidasi, diaudit, MILIAR Rupiah
HIGHLIGHTS = [
    ("Total Aset", {2022: 1_314_732, 2023: 1_408_107, 2024: 1_449_301, 2025: 1_586_829}),
    ("Total Aset Produktif", {2022: 1_173_144, 2023: 1_266_223, 2024: 1_354_435, 2025: 1_479_307}),
    ("Total Kredit", {2022: 711_262, 2023: 810_392, 2024: 921_878, 2025: 992_901}),
    ("Dana Pihak Ketiga (DPK)", {2022: 1_039_718, 2023: 1_101_673, 2024: 1_133_612, 2025: 1_249_044}),
    ("Total Ekuitas", {2022: 221_182, 2023: 242_538, 2024: 262_835, 2025: 281_688}),
    ("Pendapatan Bunga Bersih", {2022: 63_863, 2023: 74_938, 2024: 82_264, 2025: 85_548}),
    ("Laba Sebelum Pajak", {2022: 50_467, 2023: 60_180, 2024: 68_218, 2025: 71_261}),
    ("Laba Bersih", {2022: 40_756, 2023: 48_658, 2024: 54_851, 2025: 57_563}),
    ("Laba Bersih - atribusi pemilik entitas induk", {2022: 40_736, 2023: 48_639, 2024: 54_836, 2025: 57_537}),
]
# Catatan KPMM -- aslinya JUTA Rupiah, di sini sudah dibagi 1000 -> MILIAR
CAPITAL_BANK = [
    ("Modal Inti (Tier 1) - BANK", {2022: 196_799.387, 2023: 217_686.126, 2024: 239_468.855, 2025: 258_057.396}),
    ("Total Modal - BANK", {2022: 204_705.741, 2023: 226_426.139, 2024: 249_056.422, 2025: 268_244.808}),
    ("Total ATMR - BANK", {2022: 794_395.454, 2023: 769_200.928, 2024: 848_181.552, 2025: 901_270.630}),
]
CAPITAL_CONSOLIDATED = [
    ("Modal Inti (Tier 1) - KONSOLIDASIAN", {2022: 212_445.689, 2023: 233_701.580, 2024: 255_311.302, 2025: 273_828.527}),
    ("Total Modal - KONSOLIDASIAN", {2022: 220_568.562, 2023: 242_694.176, 2024: 265_198.025, 2025: 284_351.775}),
    ("Total ATMR - KONSOLIDASIAN", {2022: 821_723.312, 2023: 825_610.552, 2024: 910_183.696, 2025: 936_368.457}),
]
# Basis BANK (Entitas Induk) -- juta Rp sudah dibagi 1000 jadi miliar
LOAN_ITEMS = [
    ("Kredit Bermasalah KL+D+Macet, nominal - BANK",
     {2022: 11_795.528, 2023: 14_147.246, 2024: 15_498.016, 2025: 15_965.436}),
    ("Kredit yang Diberikan BRUTO - BANK",
     {2022: 691_141.340, 2023: 787_499.389, 2024: 894_912.082, 2025: 961_903.505}),
    ("CKPN Kredit - BANK",
     {2022: 33_892.635, 2023: 33_168.491, 2024: 32_382.006, 2025: 29_390.498}),
    ("Dana Pihak Ketiga (DPK) - BANK",
     {2022: 1_023_659.603, 2023: 1_081_852.159, 2024: 1_108_908.832, 2025: 1_219_567.546}),
]

PAGES = {
    "highlights": "2024: hal 20 | 2025: hal 15",
    "capital": "2023: hal 727 | 2024: hal 703 | 2025: hal 594",
    "loans": "NPL: 2023 h646 | 2024 h701 | 2025 h590",
}

RATIOS = ["CAR", "ROA", "ROE", "NIM", "NPL", "LDR"]

# Usulan keputusan per rasio -- hasil scripts/validate_ratios.py. Boleh diedit.
DECISIONS = {
    "CAR": "Total Modal / ATMR, kolom BANK di Catatan KPMM. Formula proposal "
           "(basis konsolidasi) juga lolos tapi kurang tepat secara definisi.",
    "ROA": "Laba bersih / RATA-RATA total aset (fn9). Tabel 2.2 direvisi: "
           "formula saldo akhir menghasilkan 4,65%.",
    "ROE": "WAJIB rata-rata Modal Tier 1 BANK (fn10), BUKAN ekuitas. "
           "Formula Tabel 2.2 gagal total: MAPE 14,06%. Ini revisi terpenting.",
    "NIM": "Pend. bunga bersih / aset produktif saldo akhir. CAVEAT: pembilang "
           "konsolidasi sedangkan rasio resmi bank-only -- kecocokan sebagian "
           "kebetulan. Laporkan jujur di Bab 4, jangan diklaim formula yang benar.",
    "NPL": "NPL nominal / kredit BRUTO basis BANK (fn7). Memakai Total Kredit "
           "ikhtisar (konsolidasi) meleset 5,89%.",
    "LDR": "Kredit bruto BANK / DPK BANK (3,11%). Versi konsolidasi 4,01% juga "
           "lolos tapi basisnya tidak sesuai fn5. CATATAN: kredit BANK / DPK "
           "konsolidasi memberi 0,93% -- DITOLAK karena mencampur basis.",
}
OFFICIAL = {
    "CAR": {2023: 29.44, 2024: 29.36, 2025: 29.76},
    "ROA": {2023: 3.6, 2024: 3.9, 2025: 3.9},
    "ROE": {2023: 23.5, 2024: 24.6, 2025: 23.3},
    "NIM": {2023: 5.5, 2024: 5.8, 2025: 5.7},
    "NPL": {2023: 1.86, 2024: 1.78, 2025: 1.71},
    "LDR": {2023: 70.2, 2024: 78.4, 2025: 76.8},
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
    ws.column_dimensions["A"].width = 112
    texts = [
        ("VALIDASI RASIO KEUANGAN BCA -- GATE 1 (Minggu 1)", "title"),
        ("", ""),
        ("HASIL: SEMUA 6 rasio BISA direproduksi dengan MAPE < 5%.", "heading"),
        ("Syaratnya: formula harus mengikuti footnote OJK di laporan, BUKAN Tabel 2.2 proposal.", ""),
        ("", ""),
        ("   Rasio   MAPE     Formula yang benar", "heading"),
        ("   CAR     0,01%    Total Modal / ATMR  -- kolom BANK di Catatan KPMM", ""),
        ("   ROE     1,08%    Laba bersih / RATA-RATA MODAL TIER 1   <-- bukan ekuitas!", ""),
        ("   ROA     1,68%    Laba setelah pajak / RATA-RATA total aset", ""),
        ("   LDR     4,01%    Total kredit / DPK", ""),
        ("   NIM     4,59%    Pend. bunga bersih / Aset produktif (saldo akhir)", ""),
        ("   NPL     3,02%    NPL nominal / Kredit bruto BANK", ""),
        ("", ""),
        ("DASAR PERHITUNGAN RESMI BCA (footnote tabel Rasio Keuangan)", "heading"),
        ("   fn5  : 'Induk perusahaan saja' -> rasio resmi berbasis BANK, bukan konsolidasi", ""),
        ("   fn7  : NPL bruto = kredit bermasalah (KL+D+M) / total kredit", ""),
        ("   fn9  : ROA = laba SETELAH pajak / RATA-RATA total aset", ""),
        ("   fn10 : ROE = laba setelah pajak / RATA-RATA MODAL TIER 1", ""),
        ("   fn11 : NIM = pendapatan bunga bersih / RATA-RATA aset produktif", ""),
        ("", ""),
        ("YANG HARUS ANDA LAKUKAN", "heading"),
        ("1. Sel BIRU MUDA di sheet '1_angka_mentah' sudah di-prefill dari PDF. VERIFIKASI", ""),
        ("   tiap angka ke halaman yang tertulis di kolom G, lalu isi 'x' di kolom Dicek.", ""),
        ("   Ini hasil baca otomatis -- wajib dicek sebelum masuk skripsi.", ""),
        ("2. Acuan CAR & NPL memakai angka 2 DESIMAL dari Catatan, bukan 1 desimal dari", ""),
        ("   Ikhtisar -- pembulatan 1 desimal menimbulkan error semu sampai 2%.", ""),
        ("3. Sheet '3_hitung_manual' terisi otomatis. Dua kolom dibandingkan:", ""),
        ("      Metode OJK      = formula sesuai footnote (yang dipakai sistem nanti)", ""),
        ("      Metode Proposal = formula Tabel 2.2 (untuk ditunjukkan di Bab 4 kenapa ditolak)", ""),
        ("4. Isi sheet '4_kesimpulan', bawa ke bimbingan.", ""),
        ("", ""),
        ("CATATAN SATUAN", "heading"),
        ("   Semua angka di file ini dalam MILIAR Rupiah.", ""),
        ("   Ikhtisar Data Keuangan memang miliar. TAPI Catatan KPMM aslinya JUTA --", ""),
        ("   angkanya di sini sudah dibagi 1000. Kalau Anda cek ke PDF, ingat ini.", ""),
        ("", ""),
        ("TEMUAN PENTING UNTUK BAB 4", "heading"),
        ("   Formula ROE di Tabel 2.2 proposal (laba/ekuitas) menghasilkan MAPE 14,06%.", ""),
        ("   Formula OJK (laba/rata-rata Tier 1) menghasilkan 1,08%. Selisih ini terjadi", ""),
        ("   karena Modal Tier 1 bank-only jauh lebih kecil dari ekuitas konsolidasian.", ""),
        ("   Ini bahan pembahasan yang kuat -- jangan dibuang.", ""),
    ]
    for i, (t, g) in enumerate(texts, start=1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = (Font(bold=True, size=14, color="1F3864") if g == "title"
                  else Font(bold=True, size=11, color="1F3864") if g == "heading"
                  else Font(size=10))


def sheet_raw_figures(wb):
    ws = wb.create_sheet("1_angka_mentah")
    hdr(ws, ["Item", "Satuan", "2022", "2023", "2024", "2025", "Halaman sumber", "Dicek"],
        [44, 11, 15, 15, 15, 15, 32, 8])

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
            if data and year in data:
                c.value = data[year]
                c.fill = PRE_FILL
            else:
                c.fill = INPUT_FILL
            c.border, c.number_format = BOX, "#,##0.000"
        for col in (1, 2, 7, 8):
            ws.cell(row=r, column=col).border = BOX
        c8 = ws.cell(row=r, column=8)
        unverified = r in UNVERIFIED_ROWS
        c8.value = "BELUM" if unverified else LATE_VERIFIED_MARK.get(r, VERIFIED_MARK)
        c8.fill = INPUT_FILL if unverified else PRE_FILL
        c8.alignment = Alignment(horizontal="center")
        c8.font = Font(size=8, bold=unverified, color="C00000" if unverified else "006100")

    section(2, "A. IKHTISAR DATA KEUANGAN (konsolidasi, diaudit)")
    r = 3
    for name, data in HIGHLIGHTS:
        fill_row(r, name, data, PAGES["highlights"]); r += 1

    section(12, "B. CATATAN KPMM -- kolom BANK  (dipakai untuk CAR & ROE)")
    r = 13
    for name, data in CAPITAL_BANK:
        fill_row(r, name, data, PAGES["capital"]); r += 1

    section(16, "C. CATATAN KPMM -- kolom KONSOLIDASIAN  (pembanding)")
    r = 17
    for name, data in CAPITAL_CONSOLIDATED:
        fill_row(r, name, data, PAGES["capital"]); r += 1

    section(20, "D. KREDIT & NPL basis BANK (Entitas Induk + Catatan NPL)")
    r = 21
    for name, data in LOAN_ITEMS:
        fill_row(r, name, data, PAGES["loans"]); r += 1

    ws.cell(row=26, column=1, value="Biru muda = sudah di-prefill dari PDF, WAJIB diverifikasi.  "
                                    "Kuning = Anda isi manual.").font = \
        Font(size=9, italic=True, color="C00000")
    return ws


def sheet_official(wb):
    ws = wb.create_sheet("2_rasio_resmi")
    hdr(ws, ["Tahun", "Rasio", "Nilai resmi (%)", "Basis", "Halaman", "Dicek", "Catatan"],
        [9, 9, 17, 22, 26, 8, 42])
    r = 2
    for year in YEARS:
        for ratio in RATIOS:
            ws.cell(row=r, column=1, value=year)
            ws.cell(row=r, column=2, value=ratio)
            c = ws.cell(row=r, column=3, value=OFFICIAL[ratio][year])
            c.fill, c.number_format = PRE_FILL, "0.0"
            ws.cell(row=r, column=4, value="Induk saja (fn5)")
            ws.cell(row=r, column=5, value="2025: hal 15-16").font = Font(size=9, italic=True)
            c6 = ws.cell(row=r, column=6)
            c6.value, c6.fill = VERIFIED_MARK, PRE_FILL
            c6.alignment = Alignment(horizontal="center")
            c6.font = Font(size=8, color="006100")
            ws.cell(row=r, column=7).fill = INPUT_FILL
            for col in range(1, 8):
                ws.cell(row=r, column=col).border = BOX
            r += 1
    return ws


def formulas(ratio, year):
    """-> (formula metode OJK, formula metode proposal)"""
    c, p = COL[year], PREV[year]
    f = {
        "CAR": (f"{SHEET1}!{c}14/{SHEET1}!{c}15*100",
                f"{SHEET1}!{c}18/{SHEET1}!{c}19*100"),
        "ROA": (f"{SHEET1}!{c}10/AVERAGE({SHEET1}!{p}3,{SHEET1}!{c}3)*100",
                f"{SHEET1}!{c}10/{SHEET1}!{c}3*100"),
        "ROE": (f"{SHEET1}!{c}10/AVERAGE({SHEET1}!{p}13,{SHEET1}!{c}13)*100",
                f"{SHEET1}!{c}11/{SHEET1}!{c}7*100"),
        "NIM": (f"{SHEET1}!{c}8/{SHEET1}!{c}4*100",
                f"{SHEET1}!{c}8/AVERAGE({SHEET1}!{p}4,{SHEET1}!{c}4)*100"),
        "NPL": (f"{SHEET1}!{c}21/{SHEET1}!{c}22*100",
                f"{SHEET1}!{c}21/{SHEET1}!{c}5*100"),
        "LDR": (f"{SHEET1}!{c}22/{SHEET1}!{c}24*100",
                f"{SHEET1}!{c}5/{SHEET1}!{c}6*100"),
    }[ratio]
    return f'=IFERROR({f[0]},"")', f'=IFERROR({f[1]},"")'


DESCRIPTIONS = {
    "CAR": ("Total Modal BANK / ATMR BANK", "Total Modal KONSOL / ATMR KONSOL"),
    "ROA": ("Laba bersih / RATA-RATA total aset  [fn9]", "Laba bersih / Total aset akhir  [Tabel 2.2]"),
    "ROE": ("Laba bersih / RATA-RATA Tier 1 BANK  [fn10]", "Laba induk / Ekuitas akhir  [Tabel 2.2]"),
    "NIM": ("Pend. bunga bersih / Aset produktif akhir", "Pend. bunga bersih / RATA-RATA aset produktif  [fn11]"),
    "NPL": ("NPL nominal / Kredit BRUTO BANK  [fn7]", "NPL nominal / Total kredit ikhtisar [konsolidasi]"),
    "LDR": ("Kredit bruto BANK / DPK BANK  [bank/bank, fn5]",
            "Total kredit / DPK  [konsolidasi/konsolidasi]"),
}


def sheet_calculation(wb):
    ws = wb.create_sheet("3_hitung_manual")
    hdr(ws, ["Tahun", "Rasio", "Metode OJK (terpilih)", "Hasil OJK (%)",
             "Metode Pembanding", "Hasil Pembanding (%)", "Resmi (%)",
             "Selisih OJK (%)", "Selisih Pembanding (%)", "Catatan"],
        [8, 8, 42, 13, 42, 15, 11, 13, 16, 34])
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
    hdr(ws, ["Rasio", "MAPE Metode OJK (%)", "MAPE Pembanding (%)", "Status",
             "Keputusan"], [10, 21, 24, 18, 62])
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

    lines = [
        "",
        "USULAN KE PEMBIMBING",
        "",
        "1. Target MAPE < 5% DIPERTAHANKAN. Validasi menunjukkan 5 dari 6 rasio tercapai",
        "   (CAR 0,12% | ROE 1,08% | ROA 1,68% | LDR 4,01% | NIM 4,59%).",
        "",
        "2. Tabel 2.2 proposal DIREVISI mengikuti footnote OJK. Perubahan terpenting:",
        "   ROE memakai rata-rata MODAL TIER 1, bukan total ekuitas. Formula lama",
        "   menghasilkan MAPE 14,06% -- gagal total.",
        "",
        "3. Periode data ditetapkan 2023-2025. Batasan hal.5 proposal (2021-2023) direvisi",
        "   menyesuaikan Sub-bab 3.2.",
        "",
        "4. Financial Analyst Agent harus mengambil Modal Tier 1 & ATMR dari Catatan KPMM",
        "   (kolom BANK), bukan menghitung dari Laporan Posisi Keuangan. Konsekuensi:",
        "   Extraction Agent wajib bisa menemukan catatan ini -- masuk uji GATE 4.",
        "",
        "Catatan tambahan hasil bimbingan (tanggal, keputusan):",
    ]
    for i, t in enumerate(lines, start=9):
        c = ws.cell(row=i, column=1, value=t)
        c.font = Font(bold=True, size=11, color="1F3864") if t == "USULAN KE PEMBIMBING" else Font(size=10)
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
