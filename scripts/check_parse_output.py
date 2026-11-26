"""
Tugas 3.6 (bagian b) -- ketepatan parsing: ke-76 angka ground truth di sel yang benar.
docs/PANDUAN_MINGGU3.md, Langkah 6b.

Jalankan:  python scripts/check_parse_output.py          (hasil Docling + perbaikan sel, Minggu 5)
           python scripts/check_parse_output.py --raw    (hasil Docling apa adanya, seperti Minggu 3)

Untuk setiap angka di data/ground_truth.xlsx (sheet 1_angka_mentah), script ini membuka hasil
Docling (data/markdown/bbca_<tahun>.json) di halaman tempat angka itu diverifikasi pada Minggu 1
-- lokasinya diambil dari scripts/build_verification_sheet.py -- lalu memeriksa LETAKNYA:

  angka TABEL     sel di baris berlabel X dan kolom berjudul Y berisi angka itu, persis
  angka NARASI    kalimatnya terbaca, dan angkanya cocok dengan tahunnya (NPL, CKPN)
  angka HITUNGAN  komponennya ada di sel yang benar dan jumlahnya sama
                  (kredit bruto = kredit neto + CKPN; DPK 2022-2024 = pihak berelasi + ketiga)

Status: TEPAT; CACAT (nilai benar, tapi strukturnya rusak -- mis. dua angka dalam satu sel,
sehingga agent bisa salah baca); SALAH (tidak ada di sel yang seharusnya).

Sejak Minggu 5 (Langkah 1) yang diperiksa adalah dokumen SETELAH perbaikan sel berisi dua angka
(src/ingest/fix_tables.py) -- itulah yang dipotong menjadi chunk. Hasil Minggu 3: 73 tepat,
3 cacat (baris kredit Entitas Induk); target Minggu 5: 76 tepat.

Audit Langkah 5 baru membuktikan angkanya ADA di halaman. Yang diuji di sini: apakah angka itu
berada di baris dan kolom yang benar.
"""

import argparse
import json
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from docling_core.types.doc import DoclingDocument
from openpyxl import load_workbook

import build_verification_sheet as sources   # lokasi sumber tiap angka -- satu sumber kebenaran
from src import config
from src.ingest.fix_tables import fix_document
from src.ingest.subset_pdf import PageMap

YEARS = (2022, 2023, 2024, 2025)
NUMBER = re.compile(r"\(?\d{1,3}(?:\.\d{3})+\)?")

# baris xlsx -> (pola label baris di tabel Ikhtisar, pola baris pembuka atau None).
# Label di PDF tidak selalu sama dengan nama item di xlsx, mis. "Pendapatan Bunga Bersih"
# tercetak "Pendapatan Bunga dan Syariah Bersih"; angka kecil di ujung label = catatan kaki.
HIGHLIGHT_ROWS = {
    3: (r"^Total Aset$", None),
    4: (r"^Total Aset Produktif$", None),
    5: (r"^Total Kredit( \d+)?$", None),
    6: (r"^Dana Pihak Ketiga( \d+)?$", None),
    7: (r"^Total Ekuitas$", None),
    8: (r"^Pendapatan Bunga dan Syariah Bersih$", None),
    9: (r"^Laba Sebelum Pajak Penghasilan$", None),
    10: (r"^Laba Bersih$", None),
    11: (r"^Pemilik Entitas Induk$", r"^Laba Bersih yang Dapat Diatribusikan"),
}
CAPITAL_ROWS = {   # baris xlsx -> (pola label, basis kolom)
    13: (r"^Modal Inti \(Tier 1\)$", "bank"),
    14: (r"^Total Modal$", "bank"),
    15: (r"^Total ATMR$", "bank"),
    17: (r"^Modal Inti \(Tier 1\)$", "konsolidasian"),
    18: (r"^Total Modal$", "konsolidasian"),
    19: (r"^Total ATMR$", "konsolidasian"),
}
NPL_ROW, GROSS_LOANS_ROW, ALLOWANCE_ROW, DEPOSITS_ROW = 21, 22, 23, 24
LOANS_LABEL = re.compile(r"^Kredit yang diberikan")
# "... sebesar Rp 32.382.006 pada tanggal 31 Desember 2024 (31 Desember 2023: Rp 33.168.491)"
AMOUNT = r"Rp ([\d.]*\d)"   # tanpa titik akhir kalimat: "Rp 11.795.528." -> 11.795.528
ALLOWANCE_TEXT = re.compile(rf"sebesar {AMOUNT} pada tanggal 31 Desember (\d{{4}}) "
                            rf"\(31 Desember (\d{{4}}): {AMOUNT}\)")


def juta(miliar: float) -> str:
    """239468.855 (miliar, seperti di xlsx) -> '239.468.855' (juta, seperti tercetak di PDF)."""
    return f"{round(miliar * 1000):,}".replace(",", ".")


def thousands(value: float) -> str:
    return f"{round(value):,}".replace(",", ".")


def to_int(text: str) -> int:
    return int(text.strip("()").replace(".", ""))


@dataclass
class Result:
    block: str
    item: str
    year: int
    expected: str
    source: str
    status: str            # "tepat" / "cacat" / "salah"
    detail: str = ""


class Report:
    """Hasil parse satu laporan + penerjemah nomor halaman potongan -> asli.
    raw=False: tabel diperbaiki dulu di memori (fix_tables), seperti sebelum chunking."""

    def __init__(self, year: int, raw: bool = False):
        meta = json.loads(config.parse_meta(year).read_text(encoding="utf-8"))
        self.page_map = PageMap.from_list(meta["page_map"])
        self.doc = DoclingDocument.load_from_json(config.docling_json(year))
        if not raw:
            fix_document(self.doc, config.subset(year), self.page_map)

    def _on(self, item, page: int) -> bool:
        # SEMUA prov: blok teks bisa lintas halaman (audit Langkah 5)
        return any(self.page_map.to_original(p.page_no) == page for p in item.prov)

    def tables(self, page: int):
        return [t for t in self.doc.tables if self._on(t, page)]

    def texts(self, page: int) -> list[str]:
        return [x.text for x in self.doc.texts if self._on(x, page)]


def column_title(table, col: int) -> str:
    """Judul kolom = gabungan semua baris header di kolom itu, mis. '2024 Bank'."""
    parts = []
    for row in table.data.grid:
        if any(c.column_header for c in row):
            text = row[col].text.strip()
            if text and text not in parts:
                parts.append(text)
    return " ".join(parts)


def find_cell(report: Report, page: int, label: str, column_ok, after: str | None = None):
    """Sel di baris berlabel `label` dan kolom yang lolos `column_ok(judul)`. None = tak ada."""
    for table in report.tables(page):
        grid = table.data.grid
        start = 0
        if after:
            start = next((i + 1 for i, row in enumerate(grid) if re.search(after, row[0].text)), len(grid))
        rows = [i for i in range(start, len(grid)) if re.search(label, grid[i][0].text.strip())]
        cols = [j for j in range(1, table.data.num_cols) if column_ok(column_title(table, j))]
        if rows and cols:
            return table, rows[0], cols[0]
    return None


def where_is(report: Report, page: int, value: str) -> str:
    """Untuk pesan SALAH: di mana angka itu sebenarnya berada di halaman tersebut."""
    for table in report.tables(page):
        for i, row in enumerate(table.data.grid):
            for j, cell in enumerate(row):
                if value in cell.text:
                    return f"ada di baris '{row[0].text[:40]}', kolom '{column_title(table, j)}'"
    if any(value in t for t in report.texts(page)):
        return "ada di teks halaman itu, bukan di tabel"
    return "tidak ada di halaman itu"


def source_of(spec) -> tuple[int, int, str]:
    """('bbca_2025.pdf', 594, 'petunjuk') -> (2025, 594, 'bbca_2025 hal 594')."""
    file_name, page, _ = spec
    report_year = int(re.search(r"(\d{4})", file_name).group(1))
    return report_year, page, f"{Path(file_name).stem} hal {page}"


def check_table_value(reports, block, item, year, expected, spec, label, column_ok, after=None):
    report_year, page, where = source_of(spec)
    report = reports[report_year]
    found = find_cell(report, page, label, column_ok, after)
    if found is None:
        return Result(block, item, year, expected, where, "salah",
                      f"baris/kolom tidak ditemukan; angkanya {where_is(report, page, expected)}")
    table, r, c = found
    got = table.data.grid[r][c].text.strip()
    if got == expected:
        return Result(block, item, year, expected, where, "tepat")
    return Result(block, item, year, expected, where, "salah",
                  f"sel berisi '{got}'; angkanya {where_is(report, page, expected)}")


def allowance_by_year(report: Report, page: int) -> dict[int, str]:
    """CKPN tertulis di label baris kredit Entitas Induk: {tahun: angka}."""
    found = find_cell(report, page, LOANS_LABEL.pattern, lambda title: True)
    if found is None:
        return {}
    table, r, _ = found
    m = ALLOWANCE_TEXT.search(table.data.grid[r][0].text)
    if not m:
        return {}
    return {int(m.group(2)): m.group(1), int(m.group(3)): m.group(4)}


def check_npl(reports, item, year, expected):
    report_year, page, where = source_of(sources.NPL[year])
    for text in reports[report_year].texts(page):
        if "non-performing" not in text.lower():
            continue
        years = re.search(r"31 Desember (\d{4}) dan (\d{4})", text)
        amounts = re.findall(AMOUNT, text)
        if years and len(amounts) >= 2:
            by_year = {int(years.group(1)): amounts[0], int(years.group(2)): amounts[1]}
            if by_year.get(year) == expected:
                return Result("D. Kredit & NPL Bank", item, year, expected, where, "tepat")
            return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                          f"kalimat NPL terbaca, tapi tahun {year} berisi {by_year.get(year)}")
    return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                  f"kalimat NPL tidak ditemukan; angkanya {where_is(reports[report_year], page, expected)}")


def check_allowance(reports, item, year, expected):
    report_year, page, where = source_of(sources.PARENT_ASSETS[year])
    got = allowance_by_year(reports[report_year], page).get(year)
    status = "tepat" if got == expected else "salah"
    detail = "" if got == expected else f"label baris kredit memberi {got} untuk {year}"
    return Result("D. Kredit & NPL Bank", item, year, expected, where, status, detail)


def check_gross_loans(reports, item, year, expected):
    """Kredit bruto = kredit neto (sel tabel) + CKPN (label baris yang sama).
    Kredit neto = satu baris, atau sub-baris pihak berelasi + pihak ketiga (setelah fix_tables)."""
    report_year, page, where = source_of(sources.PARENT_ASSETS[year])
    report = reports[report_year]
    found = find_cell(report, page, LOANS_LABEL.pattern, lambda title: title == str(year))
    allowance = allowance_by_year(report, page).get(year)
    if found is None or allowance is None:
        return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                      "baris kredit atau CKPN-nya tidak ditemukan")
    table, r, c = found
    grid = table.data.grid
    cells = [grid[r][c].text]
    if re.search(r"Pihak berelasi$", grid[r][0].text.strip()):
        if r + 1 >= len(grid) or not re.search(r"Pihak ketiga$", grid[r + 1][0].text.strip()):
            return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                          "sub-baris 'Pihak ketiga' tidak tepat di bawah 'Pihak berelasi'")
        cells.append(grid[r + 1][c].text)
    parts = [p for cell in cells for p in NUMBER.findall(cell)]
    total = sum(to_int(p) for p in parts) + to_int(allowance)
    if total != to_int(expected):
        return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                      f"komponen {parts} + CKPN {allowance} = {thousands(total)}")
    if any(len(NUMBER.findall(cell)) != 1 for cell in cells):
        return Result("D. Kredit & NPL Bank", item, year, expected, where, "cacat",
                      f"jumlah benar, tapi {len(parts)} angka dalam satu sel ({' '.join(parts)}): "
                      f"baris pihak berelasi & pihak ketiga digabung Docling")
    return Result("D. Kredit & NPL Bank", item, year, expected, where, "tepat")


def check_deposits(reports, item, year, expected):
    """DPK BANK: satu baris (2025), atau pihak berelasi + pihak ketiga (2022-2024)."""
    report_year, page, where = source_of(sources.PARENT_LIABILITIES[year])
    report = reports[report_year]
    column_ok = lambda title: title == str(year)
    first = find_cell(report, page, r"^Simpanan dari nasabah", column_ok)
    if first is None:
        return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                      "baris simpanan dari nasabah tidak ditemukan")
    table, r, c = first
    cells = [table.data.grid[r][c].text.strip()]
    if "pihak berelasi" in table.data.grid[r][0].text.lower():
        nxt = table.data.grid[r + 1] if r + 1 < len(table.data.grid) else None
        if nxt is None or not re.search(r"Pihak ketiga$", nxt[0].text.strip()):
            return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                          "baris 'Pihak ketiga' tidak tepat di bawah 'Pihak berelasi'")
        cells.append(nxt[c].text.strip())
    if any(len(NUMBER.findall(x)) != 1 for x in cells):
        return Result("D. Kredit & NPL Bank", item, year, expected, where, "cacat",
                      f"sel tidak berisi tepat satu angka: {cells}")
    total = sum(to_int(x) for x in cells)
    if total == to_int(expected):
        return Result("D. Kredit & NPL Bank", item, year, expected, where, "tepat")
    return Result("D. Kredit & NPL Bank", item, year, expected, where, "salah",
                  f"{' + '.join(cells)} = {thousands(total)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ketepatan parsing: 76 angka ground truth di sel yang benar.")
    ap.add_argument("--raw", action="store_true", help="tanpa perbaikan sel (hasil Docling apa adanya)")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore", message="Table cell bbox")   # bbox di luar halaman, di-clamp Docling

    ws = load_workbook(config.GROUND_TRUTH, data_only=False)["1_angka_mentah"]
    value = lambda row, year: ws.cell(row=row, column=sources.COL_IDX[year]).value
    name = lambda row: ws.cell(row=row, column=1).value
    reports = {year: Report(year, raw=args.raw) for year in config.YEARS}

    results = []
    for row, (label, after) in HIGHLIGHT_ROWS.items():
        for year in YEARS:
            results.append(check_table_value(
                reports, "A. Ikhtisar", name(row), year, thousands(value(row, year)),
                sources.HIGHLIGHTS(year), label, lambda title, y=year: title == str(y), after))
    for row, (label, basis) in CAPITAL_ROWS.items():
        block = "B. KPMM Bank" if basis == "bank" else "C. KPMM Konsolidasian"
        spec = sources.CAPITAL_BANK if basis == "bank" else sources.CAPITAL_CONSOLIDATED
        for year in YEARS:
            column_ok = lambda title, y=year, b=basis: str(y) in title.split() and b in title.lower().split()
            results.append(check_table_value(
                reports, block, name(row), year, juta(value(row, year)), spec[year], label, column_ok))
    for year in YEARS:
        results.append(check_npl(reports, name(NPL_ROW), year, juta(value(NPL_ROW, year))))
        results.append(check_gross_loans(reports, name(GROSS_LOANS_ROW), year, juta(value(GROSS_LOANS_ROW, year))))
        results.append(check_allowance(reports, name(ALLOWANCE_ROW), year, juta(value(ALLOWANCE_ROW, year))))
        results.append(check_deposits(reports, name(DEPOSITS_ROW), year, juta(value(DEPOSITS_ROW, year))))

    print(f"Ketepatan parsing -- {len(results)} angka ground truth di hasil Docling "
          f"({'apa adanya' if args.raw else 'setelah perbaikan sel'})\n")
    for block in sorted({r.block for r in results}):
        rows = [r for r in results if r.block == block]
        counts = {s: sum(r.status == s for r in rows) for s in ("tepat", "cacat", "salah")}
        pages = sorted({r.source for r in rows})
        print(f"  {block:<24} {counts['tepat']:>2} tepat, {counts['cacat']} cacat, {counts['salah']} salah"
              f"   ({len(rows)} angka; {', '.join(pages)})")

    flagged = [r for r in results if r.status != "tepat"]
    if flagged:
        print("\nPerlu perhatian:")
        for r in flagged:
            print(f"  [{r.status.upper()}] {r.item} {r.year} = {r.expected}  ({r.source})\n          {r.detail}")

    good = sum(r.status != "salah" for r in results)
    exact = sum(r.status == "tepat" for r in results)
    print(f"\nHASIL: {good} dari {len(results)} angka benar di lokasi yang benar "
          f"({exact} tepat, {good - exact} dengan struktur cacat).")
    if any(r.status == "salah" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
