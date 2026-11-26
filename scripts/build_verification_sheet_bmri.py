"""
Tugas 8.5 -- buat lembar verifikasi angka pre-fill BMRI (docs/lembar_verifikasi_bmri.md).

Jalankan:  python scripts/build_verification_sheet_bmri.py

Membaca data/ground_truth_bmri.xlsx lalu mengelompokkan seluruh angka per halaman PDF
agar mudah diverifikasi visual satu per satu (sama dengan pola BBCA di Minggu 1).
"""

from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "ground_truth_bmri.xlsx"
OUT = ROOT / "docs" / "lembar_verifikasi_bmri.md"

COL_IDX = {2022: 3, 2023: 4, 2024: 5, 2025: 6}

# Sumber utama per baris (file PDF, halaman indeks PDF asli tampak, petunjuk kolom)
HIGHLIGHTS_BS_ASSET = lambda t: ("bmri_2025.pdf", 36, f"kolom {t} pada Ikhtisar Neraca Konsolidasian (Aset)")
HIGHLIGHTS_BS_EQ    = lambda t: ("bmri_2025.pdf", 37, f"kolom {t} pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas)")
HIGHLIGHTS_PL       = lambda t: ("bmri_2025.pdf", 38, f"kolom {t} pada Ikhtisar Laba Rugi Konsolidasian")

CAPITAL_BANK = {
    2025: ("bmri_2025.pdf", 1432, "Catatan 65c KPMM (Bank Mandiri saja), kolom 2025"),
    2024: ("bmri_2024.pdf", 1701, "Catatan 65c KPMM (Bank Mandiri saja), kolom 2024"),
    2023: ("bmri_2023.pdf", 1425, "Catatan 58 KPMM (Bank Mandiri saja), kolom 2023"),
    2022: ("bmri_2023.pdf", 1425, "Catatan 58 KPMM (Bank Mandiri saja), kolom 2022"),
}
CAPITAL_KONSOL_T1 = {
    2025: ("bmri_2025.pdf", 356, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2025"),
    2024: ("bmri_2024.pdf", 430, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2024"),
    2023: ("bmri_2023.pdf", 403, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2023"),
    2022: ("bmri_2023.pdf", 403, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2022"),
}
CAPITAL_KONSOL_TOT = {
    2025: ("bmri_2025.pdf", 357, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2025"),
    2024: ("bmri_2024.pdf", 431, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2024"),
    2023: ("bmri_2023.pdf", 404, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2023"),
    2022: ("bmri_2023.pdf", 404, "MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2022"),
}
CAPITAL_KONSOL_RWA = {
    2025: ("bmri_2025.pdf", 357, "MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2025"),
    2024: ("bmri_2024.pdf", 431, "MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2024"),
    2023: ("bmri_2023.pdf", 405, "MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2023"),
    2022: ("bmri_2023.pdf", 405, "MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2022"),
}
NPL_BANK = {
    2025: ("bmri_2025.pdf", 354, "MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2025"),
    2024: ("bmri_2024.pdf", 428, "MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2024"),
    2023: ("bmri_2023.pdf", 401, "MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2023"),
    2022: ("bmri_2023.pdf", 401, "MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2022"),
}
PARENT_ASSETS_1 = {
    2025: ("bmri_2025.pdf", 1455, "Neraca Entitas Induk (bagian 1), kolom 2025"),
    2024: ("bmri_2024.pdf", 1713, "Neraca Entitas Induk (bagian 1), kolom 2024"),
    2023: ("bmri_2023.pdf", 1501, "Neraca Entitas Induk (bagian 1), kolom 2023"),
    2022: ("bmri_2023.pdf", 1501, "Neraca Entitas Induk (bagian 1), kolom 2022"),
}
PARENT_ASSETS_2 = {
    2025: ("bmri_2025.pdf", 1456, "Neraca Entitas Induk (bagian 2), kolom 2025"),
    2024: ("bmri_2024.pdf", 1714, "Neraca Entitas Induk (bagian 2), kolom 2024"),
    2023: ("bmri_2023.pdf", 1502, "Neraca Entitas Induk (bagian 2), kolom 2023"),
    2022: ("bmri_2023.pdf", 1502, "Neraca Entitas Induk (bagian 2), kolom 2022"),
}
PARENT_LIAB = {
    2025: ("bmri_2025.pdf", 1457, "Neraca Entitas Induk (Liabilitas), baris 'Total simpanan dari nasabah', kolom 2025"),
    2024: ("bmri_2024.pdf", 1715, "Neraca Entitas Induk (Liabilitas), baris 'Total simpanan nasabah', kolom 2024"),
    2023: ("bmri_2023.pdf", 1503, "Neraca Entitas Induk (Liabilitas), baris 'Total simpanan nasabah', kolom 2023"),
    2022: ("bmri_2023.pdf", 1503, "Neraca Entitas Induk (Liabilitas), baris 'Total simpanan nasabah', kolom 2022"),
}
PARENT_PL = {
    2025: ("bmri_2025.pdf", 1460, "Laba Rugi Entitas Induk, kolom 2025"),
    2024: ("bmri_2024.pdf", 1718, "Laba Rugi Entitas Induk, kolom 2024"),
    2023: ("bmri_2023.pdf", 1506, "Laba Rugi Entitas Induk, kolom 2023"),
    2022: ("bmri_2023.pdf", 1506, "Laba Rugi Entitas Induk, kolom 2022"),
}

ROW_MAP = {
    3:  ("A. Ikhtisar", HIGHLIGHTS_BS_ASSET, ""),
    4:  ("A. Ikhtisar (Aset Produktif Inti Bank)", lambda t: PARENT_ASSETS_1[t],
         "HITUNGAN: Penempatan + Efek + Obligasi Pemerintah + Reverse Repo + Kredit bruto (Entitas Induk)"),
    5:  ("A. Ikhtisar", HIGHLIGHTS_BS_ASSET, ""),
    6:  ("A. Ikhtisar", HIGHLIGHTS_BS_EQ,
         "HITUNGAN: Simpanan Nasabah (hal 36) + Dana Syirkah Temporer Simpanan Nasabah (hal 37)"),
    7:  ("A. Ikhtisar", HIGHLIGHTS_BS_EQ, ""),
    8:  ("A. Ikhtisar", HIGHLIGHTS_PL, ""),
    9:  ("A. Ikhtisar", HIGHLIGHTS_PL, ""),
    10: ("A. Ikhtisar", HIGHLIGHTS_PL, ""),
    11: ("A. Ikhtisar", HIGHLIGHTS_PL, ""),
    13: ("B. KPMM Bank", lambda t: CAPITAL_BANK[t], "Sumber utama CAR & ROE (Bank Mandiri saja)"),
    14: ("B. KPMM Bank", lambda t: CAPITAL_BANK[t], "Sumber utama CAR (Bank Mandiri saja)"),
    15: ("B. KPMM Bank", lambda t: CAPITAL_BANK[t], "Sumber utama CAR (Bank Mandiri saja)"),
    17: ("C. KPMM Konsolidasian", lambda t: CAPITAL_KONSOL_T1[t], "RAWAN: 4 kolom Bank/Konsolidasi berdampingan"),
    18: ("C. KPMM Konsolidasian", lambda t: CAPITAL_KONSOL_TOT[t], "RAWAN: 4 kolom Bank/Konsolidasi berdampingan"),
    19: ("C. KPMM Konsolidasian", lambda t: CAPITAL_KONSOL_RWA[t], "RAWAN: 4 kolom Bank/Konsolidasi berdampingan"),
    21: ("D. Basis Bank", lambda t: NPL_BANK[t], "Tercetak langsung 'NPL gross*)' = KL + Diragukan + Macet"),
    22: ("D. Basis Bank", lambda t: PARENT_ASSETS_2[t], "Subtotal 'Kredit yang diberikan' sebelum dikurangi CKPN"),
    23: ("D. Basis Bank", lambda t: PARENT_ASSETS_2[t], "Baris 'Dikurangi: cadangan kerugian penurunan nilai' di bawah Kredit"),
    24: ("D. Basis Bank", lambda t: PARENT_LIAB[t], "Tercetak langsung 'Total simpanan nasabah'"),
    25: ("D. Basis Bank", lambda t: PARENT_ASSETS_2[t], "Baris 'TOTAL ASET' Neraca Entitas Induk"),
    26: ("D. Basis Bank", lambda t: PARENT_PL[t], "Baris 'PENDAPATAN BUNGA - NETO'"),
    27: ("D. Basis Bank", lambda t: PARENT_PL[t], "Baris 'LABA SEBELUM BEBAN PAJAK' (dipakai untuk ROA SEOJK)"),
    28: ("D. Basis Bank", lambda t: PARENT_PL[t], "Baris 'LABA TAHUN BERJALAN' (dipakai untuk ROE SEOJK)"),
}


def main():
    if not XLSX.exists():
        raise SystemExit(f"Belum ada {XLSX}. Jalankan scripts/build_ground_truth_bmri.py dulu.")

    wb = load_workbook(XLSX, data_only=False)
    ws = wb["1_angka_mentah"]

    groups = defaultdict(list)
    for r, (block, source, note) in ROW_MAP.items():
        name = ws.cell(row=r, column=1).value
        verified = str(ws.cell(row=r, column=8).value or "").strip()
        mark = "✓" if verified.lower().startswith("v") else "☐"
        for year in (2022, 2023, 2024, 2025):
            v = ws.cell(row=r, column=COL_IDX[year]).value
            if v is None:
                continue
            f, page, hint = source(year)
            groups[(f, page)].append((block, r, name, year, v, hint, note, mark))

    lines = [
        "# Lembar Verifikasi Angka BMRI — Minggu 8 (Tugas 8.5)",
        "",
        "Dibuat otomatis dari `data/ground_truth_bmri.xlsx` oleh `scripts/build_verification_sheet_bmri.py`.",
        "",
        "**Cara pakai:** buka satu halaman PDF asli BMRI, cocokkan semua angka di bawahnya sekaligus,",
        "lalu centang. Seluruh nilai di tabel ini sudah dinormalisasi ke **miliar Rupiah** (PDF BMRI",
        "mencetak **semua** tabel — Ikhtisar maupun CaLK — dalam **JUTA Rupiah**, jadi dibagi 1.000).",
        "Contoh: PDF menulis `229.932.670` → di sini `229.932,670`.",
        "",
        f"Total **{sum(len(v) for v in groups.values())} angka** (23 item × 4 tahun), tersebar di **{len(groups)} halaman PDF**.",
        "",
        "---",
        "",
    ]

    def priority(page_key):
        items = groups[page_key]
        risky = any("RAWAN" in it[6] or "HITUNGAN" in it[6] for it in items)
        return (0 if risky else 1, page_key[0], page_key[1])

    for i, page_key in enumerate(sorted(groups, key=priority), start=1):
        f, page = page_key
        items = sorted(groups[page_key], key=lambda x: (x[1], x[3]))
        risky = any("RAWAN" in it[6] or "HITUNGAN" in it[6] for it in items)

        lines.append(f"## {i}. `{f}` — halaman {page}" + ("  ⚠️ **PRIORITAS**" if risky else ""))
        lines.append("")
        lines.append(f"Blok: {items[0][0]}")
        for c in sorted({it[6] for it in items if it[6]}):
            lines.append(f"> {c}")
        lines.append("")
        lines.append("| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |")
        lines.append("|---|---|---|---|---|")
        for _, _, name, year, v, hint, _, mark in items:
            shown = f"{v:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")
            lines.append(f"| {mark} | {name} | {year} | `{shown}` | {hint} |")
        lines.append("")

    # Rasio resmi (sheet 2_rasio_resmi)
    ws2 = wb["2_rasio_resmi"]
    lines += [
        "---",
        "",
        "## Verifikasi 18 Rasio Resmi (`2_rasio_resmi`) — `bmri_2025.pdf` hal. 39–40",
        "",
        "*(Tercetak 2 desimal langsung di tabel `RASIO KEUANGAN (BANK ONLY)` dan identik di `bmri_2024.pdf` hal. 34–35 serta `bmri_2023.pdf` hal. 36–37.)*",
        "",
        "| ✓ | Tahun | Rasio | Nilai resmi (%) | Sumber silang |",
        "|---|---|---|---|---|",
    ]
    for r in range(2, 20):
        yr = ws2.cell(row=r, column=1).value
        rt = ws2.cell(row=r, column=2).value
        val = ws2.cell(row=r, column=3).value
        vmark = "✓" if str(ws2.cell(row=r, column=6).value or "").lower().startswith("v") else "☐"
        shown = f"{val:.2f}".replace(".", ",")
        cross = "Catatan 58/65c KPMM" if rt == "CAR" else ("MD&A Kolektibilitas & Cat. 12/65" if rt == "NPL" else "MD&A Rentabilitas/Likuiditas")
        lines.append(f"| {vmark} | {yr} | {rt} | `{shown}%` | {cross} |")

    lines += [
        "",
        "---",
        "",
        "## Rincian 2 Item Hitungan (dalam JUTA Rupiah seperti tertulis di PDF)",
        "",
        "### 1. Dana Pihak Ketiga Konsolidasian (`bmri_2025.pdf` hal. 36 & 37)",
        "",
        "BMRI mengonsolidasi Bank Syariah Indonesia (BSI), sehingga dana nasabah konsolidasi terdiri dari **Simpanan Nasabah** (hal. 36) + **Dana Syirkah Temporer — Simpanan Nasabah** (hal. 37):",
        "",
        "```",
        "  Tahun   Simpanan Nasabah      + Dana Syirkah Nasabah   = DPK Konsolidasian (juta Rp)",
        "  2022    1.295.575.929         +   195.268.663          = 1.490.844.592",
        "  2023    1.351.448.149         +   225.501.470          = 1.576.949.619",
        "  2024    1.446.234.957         +   252.661.959          = 1.698.896.916",
        "  2025    1.816.897.208         +   288.866.943          = 2.105.764.151",
        "```",
        "",
        "### 2. Aset Produktif Inti — BANK (Neraca Entitas Induk: hal. 1501–1502 / 1713–1714 / 1455–1456)",
        "",
        "BMRI tidak mencetak 1 baris ringkasan 'Total Aset Produktif' di Ikhtisar. Aset produktif berbunga inti Bank = Penempatan (neto) + Efek-efek (neto) + Obligasi Pemerintah + Reverse Repo + Kredit yang Diberikan (bruto):",
        "",
        "```",
        "  Tahun   Penempatan    + Efek-efek     + Obligasi Pem.  + Reverse Repo  + Kredit Bruto    = Total (juta Rp)",
        "  2022    78.360.194    + 44.932.352    + 262.007.141    +  6.312.523    +   932.639.051   = 1.324.251.261",
        "  2023    55.274.570    + 43.134.871    + 239.245.751    + 16.205.580    + 1.085.787.427   = 1.439.648.199",
        "  2024    22.667.518    + 44.703.514    + 221.138.442    +  7.166.266    + 1.310.779.402   = 1.606.455.142",
        "  2025    19.689.791    + 81.717.307    + 219.792.906    +  2.771.530    + 1.497.108.664   = 1.821.080.198",
        "```",
        "",
        "---",
        "",
        "## Cross-check Gratis Antar Laporan Tahunan",
        "",
        "Angka tahun 2023 dan 2024 muncul di **dua** laporan tahunan (tahun berjalan & pembanding tahun berikutnya) — seluruhnya sudah dicek otomatis identik 100%:",
        "",
        "| Item | Tahun | Sumber utama | Sumber silang |",
        "|---|---|---|---|",
        "| Modal Inti, Total Modal, ATMR — BANK | 2024 | `bmri_2024.pdf` h1701 | `bmri_2025.pdf` h1432 (kolom 2024) |",
        "| Modal Inti, Total Modal, ATMR — BANK | 2023 | `bmri_2023.pdf` h1425 | `bmri_2024.pdf` h1701 (kolom 2023) |",
        "| Kredit Bruto, CKPN, DPK, Total Aset — BANK | 2024 | `bmri_2024.pdf` h1714–1715 | `bmri_2025.pdf` h1456–1457 (kolom 2024) |",
        "| Kredit Bruto, CKPN, DPK, Total Aset — BANK | 2023 | `bmri_2023.pdf` h1502–1503 | `bmri_2024.pdf` h1714–1715 (kolom 2023) |",
        "| Pendapatan Bunga Neto, PBT, Laba Bersih — BANK | 2024 | `bmri_2024.pdf` h1718 | `bmri_2025.pdf` h1460 (kolom 2024) |",
        "| Pendapatan Bunga Neto, PBT, Laba Bersih — BANK | 2023 | `bmri_2023.pdf` h1506 | `bmri_2024.pdf` h1718 (kolom 2023) |",
        "| NPL nominal — BANK (`KL+D+M`) | 2022–2024 | `bmri_2024.pdf` h428 | `bmri_2025.pdf` h354 (tabel 5 tahun) |",
        "| Ikhtisar Konsolidasian & Rasio Resmi | 2022–2024 | `bmri_2025.pdf` h36–40 | `bmri_2024.pdf` h30–35 & `bmri_2023.pdf` h35–37 |",
        "",
        "## Status verifikasi (26-11-2026)",
        "",
        "- [x] Seluruh 92 angka mentah + 18 rasio resmi diverifikasi visual terhadap render gambar 30 halaman PDF asli BMRI (`bmri_2023..2025.pdf`) + uji aritmetika & cross-check antar laporan",
        "- [x] 1 koreksi penjumlahan diterapkan (`Aset Produktif Inti Bank 2023`: `1.439.648,229` → `1.439.648,199` miliar, selisih 30 juta Rp)",
        "- [x] `VERIFIED_ROWS` & `OFFICIAL_VERIFIED` diperbarui di `scripts/build_ground_truth_bmri.py` (`v 26/11/26`) dan `data/ground_truth_bmri.xlsx` dibangun ulang",
        "- [x] Verifikasi dicatat di `docs/PANDUAN_MINGGU8.md` & `docs/ROADMAP.md`",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {OUT}")
    print(f"   {sum(len(v) for v in groups.values())} angka mentah + 18 rasio resmi, {len(groups)} halaman PDF")


if __name__ == "__main__":
    main()
