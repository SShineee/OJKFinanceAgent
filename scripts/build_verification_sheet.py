"""
Tugas 1.5 -- buat lembar verifikasi angka prefill.

Jalankan:  python scripts/build_verification_sheet.py

Membaca data/ground_truth.xlsx lalu menghasilkan docs/lembar_verifikasi.md:
daftar angka yang harus dicek, DIKELOMPOKKAN PER HALAMAN PDF.

Kenapa dikelompokkan per halaman: supaya Anda buka satu halaman PDF sekali
saja lalu cek semua angka yang ada di situ, bukan bolak-balik 10 halaman
untuk 10 angka.

Kalau Anda menemukan angka yang salah, perbaiki di scripts/build_ground_truth.py
(bukan di Excel-nya), jalankan ulang generator, lalu jalankan script ini lagi
supaya lembarnya ikut terbarui.
"""

from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "ground_truth.xlsx"
OUT = ROOT / "docs" / "lembar_verifikasi.md"

COL = {2022: "C", 2023: "D", 2024: "E", 2025: "F"}
COL_IDX = {2022: 3, 2023: 4, 2024: 5, 2025: 6}

# baris xlsx -> (blok, sumber per tahun)
# sumber: (file, halaman, petunjuk kolom di PDF)
HIGHLIGHTS = lambda t: ("bbca_2025.pdf", 15, f"kolom {t} pada tabel Ikhtisar 5 tahun")
CAPITAL_BANK = {
    2025: ("bbca_2025.pdf", 594, "kolom **Bank 2025** (kolom ke-1 dari 4)"),
    2024: ("bbca_2024.pdf", 703, "kolom **Bank 2024** (kolom ke-1 dari 4)"),
    2023: ("bbca_2023.pdf", 727, "kolom **Bank 2023** (kolom ke-1 dari 4)"),
    2022: ("bbca_2023.pdf", 727, "kolom **Bank 2022** (kolom ke-3 dari 4)"),
}
CAPITAL_CONSOLIDATED = {
    2025: ("bbca_2025.pdf", 594, "kolom **Konsolidasian 2025** (kolom ke-2)"),
    2024: ("bbca_2024.pdf", 703, "kolom **Konsolidasian 2024** (kolom ke-2)"),
    2023: ("bbca_2023.pdf", 727, "kolom **Konsolidasian 2023** (kolom ke-2)"),
    2022: ("bbca_2023.pdf", 727, "kolom **Konsolidasian 2022** (kolom ke-4)"),
}
NPL = {
    2025: ("bbca_2025.pdf", 590, "angka pertama di narasi (2025)"),
    2024: ("bbca_2024.pdf", 701, "angka pertama di narasi (2024)"),
    2023: ("bbca_2023.pdf", 646, "angka pertama di narasi (2023)"),
    2022: ("bbca_2023.pdf", 646, "angka kedua di narasi (2022)"),
}
PARENT_ASSETS = {
    2025: ("bbca_2025.pdf", 595, "Laporan Posisi Keuangan **Entitas Induk**, kolom 2025"),
    2024: ("bbca_2024.pdf", 704, "Laporan Posisi Keuangan **Entitas Induk**, kolom 2024"),
    2023: ("bbca_2023.pdf", 738, "Laporan Posisi Keuangan **Entitas Induk**, kolom 2023"),
    2022: ("bbca_2023.pdf", 738, "Laporan Posisi Keuangan **Entitas Induk**, kolom 2022"),
}

ROW_MAP = {}
for r in range(3, 12):
    ROW_MAP[r] = ("A. Ikhtisar", lambda t: HIGHLIGHTS(t), "")
for r in (13, 14, 15):
    ROW_MAP[r] = ("B. KPMM Bank", lambda t: CAPITAL_BANK[t], "RAWAN: 4 kolom berdampingan")
for r in (17, 18, 19):
    ROW_MAP[r] = ("C. KPMM Konsolidasian", lambda t: CAPITAL_CONSOLIDATED[t], "RAWAN: 4 kolom berdampingan")
ROW_MAP[21] = ("D. Kredit & NPL Bank", lambda t: NPL[t], "disebut langsung dalam narasi")
ROW_MAP[22] = ("D. Kredit & NPL Bank", lambda t: PARENT_ASSETS[t],
            "HITUNGAN: kredit neto + CKPN -- cek aritmatikanya juga")
ROW_MAP[23] = ("D. Kredit & NPL Bank", lambda t: PARENT_ASSETS[t], "tertulis di narasi baris kredit")

# DPK basis BANK -- sisi LIABILITAS Laporan Posisi Keuangan Entitas Induk,
# halaman setelah sisi aset. Ditambahkan 25-10-2026, BELUM diverifikasi.
PARENT_LIABILITIES = {
    2025: ("bbca_2025.pdf", 596, "Simpanan dari nasabah, kolom 2025 (satu baris)"),
    2024: ("bbca_2024.pdf", 705, "Simpanan dari nasabah: pihak berelasi + pihak ketiga, kolom 2024"),
    2023: ("bbca_2023.pdf", 739, "Simpanan dari nasabah: pihak berelasi + pihak ketiga, kolom 2023"),
    2022: ("bbca_2023.pdf", 739, "Simpanan dari nasabah: pihak berelasi + pihak ketiga, kolom 2022"),
}
ROW_MAP[24] = ("D. Kredit & NPL Bank", lambda t: PARENT_LIABILITIES[t],
            "HITUNGAN untuk 2022-2024: pihak berelasi + pihak ketiga")


def main():
    if not XLSX.exists():
        raise SystemExit(f"Belum ada {XLSX}. Jalankan scripts/build_ground_truth.py dulu.")

    ws = load_workbook(XLSX, data_only=False)["1_angka_mentah"]

    # kumpulkan per (file, halaman)
    groups = defaultdict(list)
    values = {}
    for r, (block, source, note) in ROW_MAP.items():
        name = ws.cell(row=r, column=1).value
        if not name:
            continue
        # Centang diambil dari kolom "Dicek" (H) di xlsx -- SATU sumber kebenaran.
        # Dulu lembar ini selalu ditulis ulang dengan kotak kosong, sehingga
        # membangun ulang menghapus centang manual (terjadi 25 & 26-10-2026).
        verified = str(ws.cell(row=r, column=8).value or "").strip()
        mark = "✓" if verified.lower().startswith("v") else "☐"
        for year in (2022, 2023, 2024, 2025):
            v = ws.cell(row=r, column=COL_IDX[year]).value
            if v is None:
                continue
            f, page, column_hint = source(year)
            groups[(f, page)].append((block, r, name, year, v, column_hint, note, mark))
            values[(r, year)] = v

    lines = [
        "# Lembar Verifikasi Angka — Tugas 1.5",
        "",
        "Dibuat otomatis dari `data/ground_truth.xlsx` oleh `scripts/build_verification_sheet.py`.",
        "",
        "**Cara pakai:** buka satu halaman PDF, cek semua angka di bawahnya sekaligus,",
        "lalu centang. Semua nilai dalam **miliar Rupiah**.",
        "",
        "> ⚠️ **Jebakan satuan.** Catatan KPMM dan Entitas Induk di PDF memakai **JUTA**",
        "> Rupiah. Di tabel ini sudah dikonversi ke **miliar** (dibagi 1.000).",
        "> Contoh: PDF menulis `239.468.855` → di sini `239.468,855`. Itu benar.",
        "",
        f"Total {sum(len(v) for v in groups.values())} angka, tersebar di {len(groups)} halaman PDF.",
        "",
        "---",
        "",
    ]

    # urut: yang paling rawan dulu
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
        block = items[0][0]
        lines.append(f"Blok: {block}")
        notes = {it[6] for it in items if it[6]}
        for c in sorted(notes):
            lines.append(f"> {c}")
        lines.append("")
        lines.append("| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |")
        lines.append("|---|---|---|---|---|")
        for _, r, name, year, v, column_hint, _, mark in items:
            shown = f"{v:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")
            lines.append(f"| {mark} | {name} | {year} | `{shown}` | {column_hint} |")
        lines.append("")

    # ---- satu-satunya baris yang butuh hitungan
    lines += [
        "---",
        "",
        "## Satu-satunya angka yang butuh HITUNGAN",
        "",
        "68 dari 72 angka cukup dibandingkan secara visual. Yang di bawah ini",
        "pengecualiannya: PDF menyajikan kredit **NETO** (sudah dikurangi CKPN),",
        "sedangkan NPL butuh **BRUTO**. Jadi harus ditambahkan kembali.",
        "",
        "Angka komponennya sudah saya tulis — Anda cukup (a) cocokkan komponennya",
        "ke PDF, lalu (b) periksa apakah penjumlahan saya benar.",
        "",
        "Semua dalam **JUTA** Rupiah (seperti tertulis di PDF), bukan miliar.",
        "",
        "### 2025 — `bbca_2025.pdf` halaman 595",
        "",
        "```",
        "  kredit neto              932.513.007   <- satu baris, tidak dipecah",
        "  CKPN                   +  29.390.498   <- di narasi baris yang sama",
        "  -----------------------------------",
        "  kredit BRUTO             961.903.505   = 961.903,505 miliar",
        "```",
        "",
        "### 2024 — `bbca_2024.pdf` halaman 704",
        "",
        "```",
        "  Pihak berelasi             7.296.837",
        "  Pihak ketiga           + 855.233.239",
        "  -----------------------------------",
        "  kredit neto              862.530.076",
        "  CKPN                   +  32.382.006",
        "  -----------------------------------",
        "  kredit BRUTO             894.912.082   = 894.912,082 miliar",
        "```",
        "",
        "### 2023 — `bbca_2023.pdf` halaman 738",
        "",
        "```",
        "  Pihak berelasi             8.803.131",
        "  Pihak ketiga           + 745.527.767",
        "  -----------------------------------",
        "  kredit neto              754.330.898",
        "  CKPN                   +  33.168.491",
        "  -----------------------------------",
        "  kredit BRUTO             787.499.389   = 787.499,389 miliar",
        "```",
        "",
        "### 2022 — `bbca_2023.pdf` halaman 738 (kolom pembanding)",
        "",
        "```",
        "  Pihak berelasi             9.548.725",
        "  Pihak ketiga           + 647.699.980",
        "  -----------------------------------",
        "  kredit neto              657.248.705",
        "  CKPN                   +  33.892.635",
        "  -----------------------------------",
        "  kredit BRUTO             691.141.340   = 691.141,340 miliar",
        "```",
        "",
        "> Cross-check mudah: kredit neto 2024 juga tertulis sebagai angka pembanding",
        "> di `bbca_2025.pdf` halaman 595 — harus sama persis dengan 862.530.076.",
        "",
    ]

    # ---- cross-check: angka yang muncul di dua laporan, harus identik
    lines += [
        "---",
        "",
        "## Cross-check gratis",
        "",
        "Angka tahun 2024 dan 2023 muncul di **dua** laporan tahunan (sebagai tahun",
        "berjalan di satu laporan, dan sebagai pembanding di laporan berikutnya).",
        "Kalau Anda sudah mengecek satu, cek silang di yang lain — kalau beda,",
        "berarti ada yang salah baca.",
        "",
        "| Item | Tahun | Sumber utama | Sumber silang |",
        "|---|---|---|---|",
        "| Modal Inti Tier 1 — BANK | 2024 | `bbca_2024.pdf` h703 | `bbca_2025.pdf` h594 kolom Bank 2024 |",
        "| Total Modal — BANK | 2024 | `bbca_2024.pdf` h703 | `bbca_2025.pdf` h594 kolom Bank 2024 |",
        "| Total ATMR — BANK | 2024 | `bbca_2024.pdf` h703 | `bbca_2025.pdf` h594 kolom Bank 2024 |",
        "| Modal Inti Tier 1 — BANK | 2023 | `bbca_2023.pdf` h727 | `bbca_2024.pdf` h703 kolom Bank 2023 |",
        "| NPL nominal — BANK | 2024 | `bbca_2024.pdf` h701 | `bbca_2025.pdf` h590 (angka kedua) |",
        "| NPL nominal — BANK | 2023 | `bbca_2023.pdf` h646 | `bbca_2024.pdf` h701 (angka kedua) |",
        "| Total Aset (ikhtisar) | 2022–2024 | `bbca_2025.pdf` h15 | `bbca_2024.pdf` h20 |",
        "",
        "---",
        "",
        "## Kalau ketemu angka yang salah",
        "",
        "1. **Jangan** perbaiki langsung di Excel — akan tertimpa kalau generator dijalankan ulang.",
        "2. Perbaiki di `scripts/build_ground_truth.py` (blok `HIGHLIGHTS`, `CAPITAL_BANK`,",
        "   `CAPITAL_CONSOLIDATED`, atau `LOAN_ITEMS`) **dan** di `scripts/validate_ratios.py`.",
        "3. Jalankan ulang: `python scripts/build_ground_truth.py` (tutup Excel dulu),",
        "   lalu `python scripts/validate_ratios.py` untuk melihat MAPE yang terkoreksi.",
        "",
        "Atau kirim koreksinya ke Claude — lebih cepat, sekalian dicek dampaknya ke MAPE.",
        "",
        "## Setelah semua tercentang",
        "",
        "- [ ] Centang kolom `Dicek` (kolom H) di sheet `1_angka_mentah`",
        "- [ ] Isi sheet `4_kesimpulan`",
        "- [ ] Tandai 1.5 selesai di `docs/catatan_validasi_rasio.md`",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {OUT}")
    print(f"   {sum(len(v) for v in groups.values())} angka, {len(groups)} halaman PDF")


if __name__ == "__main__":
    main()
