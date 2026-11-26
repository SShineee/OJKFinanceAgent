"""
Tugas 3.1 -- kriteria selesai penyaring halaman (docs/PANDUAN_MINGGU3.md, Langkah 1).

Jalankan:  python scripts/check_page_filter.py

Untuk ketiga laporan BBCA, script ini memeriksa:
  1. ketujuh kelompok halaman penting lolos saringan -- di halaman-halaman inilah ke-76
     angka ground truth berada (dicek manual di Minggu 1). Satu saja terlewat = angka itu
     tidak akan pernah sampai ke Docling, apalagi ke agent.
  2. satuan dominan = jutaan Rupiah
  3. jumlah halaman lolos sama dengan EXPECTED_TOTAL. Kalau berbeda, berarti aturan
     saringan atau versi pypdf berubah -- periksa halaman yang bertambah/hilang dulu,
     baru perbarui angkanya (juga di PANDUAN_MINGGU3.md dan ROADMAP.md).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config
from src.ingest.page_filter import RULE_VERSION, filter_pages, format_ranges

TICKER = "bbca"

# kelompok -> {tahun: halaman} tempat isinya TAMPAK. Sumber: inspeksi PDF & ground truth Minggu 1.
# KPMM & NPL 2025 dikoreksi 05-11-2026 dari 593 & 589: lapisan teks halaman itu memuat isi
# halaman berikutnya di luar area tampak, sehingga pencarian dengan pypdf meleset satu halaman.
CRITICAL_PAGES = {
    "Ikhtisar + tabel rasio resmi":          {2023: [18, 19],   2024: [20, 21],   2025: [15, 16]},
    "Laporan posisi keuangan konsolidasian": {2023: [576, 577], 2024: [540, 541], 2025: [461, 462]},
    "Laporan laba rugi":                     {2023: [578],      2024: [542],      2025: [463]},
    "Catatan KPMM (Tier 1, ATMR)":           {2023: [727],      2024: [703],      2025: [594]},
    "Catatan NPL":                           {2023: [646],      2024: [701],      2025: [590]},
    "Entitas Induk -- aset":                 {2023: [738],      2024: [704],      2025: [595]},
    "Entitas Induk -- liabilitas":           {2023: [739],      2024: [705],      2025: [596]},
}
EXPECTED_UNIT = "million_idr"
# Diukur 30-10-2026, aturan versi 2, pypdf 6.21.2
EXPECTED_TOTAL = {2023: 261, 2024: 262, 2025: 230}


def main():
    print(f"Aturan saringan versi {RULE_VERSION}\n")
    selections, failures = {}, []

    for year in config.YEARS:
        path = config.pdf(year, TICKER)
        if not path.exists():
            failures.append(f"{path.name} tidak ada")
            continue
        s = selections[year] = filter_pages(path)
        print(f"{s.source}: {len(s.pages)} dari {s.total_pages} halaman ({s.share:.0%}), "
              f"satuan {s.unit}, {s.seconds:.1f} detik")

        if s.unit != EXPECTED_UNIT:
            failures.append(f"{s.source}: satuan dominan {s.unit}, seharusnya {EXPECTED_UNIT}")
        if len(s.pages) != EXPECTED_TOTAL[year]:
            failures.append(f"{s.source}: {len(s.pages)} halaman lolos, tercatat "
                            f"{EXPECTED_TOTAL[year]} -- aturan atau versi pypdf berubah?")

    if selections:
        years = list(selections)
        print(f"\n{'Kelompok halaman':<40}" + "".join(f"{TICKER}_{y:<10}" for y in years))
        for group, by_year in CRITICAL_PAGES.items():
            cells = []
            for year in years:
                passed = set(selections[year].pages)
                missing = [p for p in by_year[year] if p not in passed]
                pages = ", ".join(map(str, by_year[year]))
                cells.append(f"{'OK' if not missing else 'GAGAL'} {pages}")
                if missing:
                    failures.append(f"{TICKER}_{year}: {group} hal {format_ranges(missing)} terlewat")
            print(f"{group:<40}" + "".join(f"{c:<15}" for c in cells))

    print()
    if failures:
        print(f"BELUM LULUS -- {len(failures)} masalah:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("LULUS -- ketujuh kelompok halaman tertangkap di ketiga laporan.")


if __name__ == "__main__":
    main()
