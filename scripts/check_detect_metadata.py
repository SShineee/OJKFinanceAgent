"""
Kriteria selesai Langkah 7 (tugas 3.2 & 3.7) -- docs/PANDUAN_MINGGU3.md.

A. Ketiga laporan BBCA sungguhan: kode saham, nama, tahun buku, satuan, dan sektor BANK, tanpa
   peringatan.
B. Teks buatan untuk aturan yang tidak bisa diuji dengan BBCA: sektor lain, bank dengan anak
   usaha non-bank, laporan berbahasa Inggris, nama "(Persero)", tahun/kode yang bertentangan.
   Ini menguji LOGIKA aturan, bukan membuktikan penanda sektor lain cocok dengan laporan
   sungguhan -- sektor non-bank tetap "belum divalidasi".
C. Uji negatif pada teks BBCA sungguhan yang dirusak: tanpa halaman "Kode Saham", kode tetap
   ditemukan lewat pola cadangan; tanpa halaman berpenanda prudensial bank, BBCA TIDAK lagi
   terdeteksi bank walaupun "piutang pembiayaan konsumen" tetap ada di puluhan halaman.

Jalankan:  python scripts/check_detect_metadata.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src.ingest.detect_metadata import BANK_MARKERS, SECTORS, detect_metadata  # noqa: E402
from src.ingest.page_filter import extract_page_texts, normalize  # noqa: E402

EXPECTED = {"ticker": "bbca", "company": "PT Bank Central Asia Tbk", "unit": "million_idr",
            "sector": "bank"}

failures = 0


def check(name: str, meta, warn: bool = False, **expected):
    """Bandingkan field; warn=True -> HARUS ada peringatan, False -> TIDAK boleh ada."""
    global failures
    problems = [f"{k}={getattr(meta, k)!r}, seharusnya {v!r}"
                for k, v in expected.items() if getattr(meta, k) != v]
    if meta.sector not in SECTORS:
        problems.append(f"sektor {meta.sector!r} tidak dikenal config")
    if warn and not meta.warnings:
        problems.append("seharusnya ada peringatan")
    if not warn and meta.warnings:
        problems.append(f"peringatan tak terduga: {meta.warnings}")
    status = "LULUS" if not problems else "GAGAL"
    failures += bool(problems)
    note = f"  [{meta.warnings[0]}]" if warn and meta.warnings else ""
    print(f"  {status}  {name}{note}")
    for p in problems:
        print(f"         {p}")


# ---------------------------------------------------------------- teks buatan
FILLER = "Laporan ini disusun sesuai standar akuntansi keuangan yang berlaku di Indonesia."


def page(*parts: str) -> str:
    return f"{FILLER}\n" + "\n".join(parts) + f"\n{FILLER}"


def report(*extra: str, name: str = "PT Contoh Sejahtera Tbk", code: str = "Kode Saham CNTH",
           year: int = 2024, cover: int | None = None) -> list[str]:
    cover = year if cover is None else cover
    statement = page(name, "LAPORAN POSISI KEUANGAN", f"31 Desember {year} dan {year - 1}",
                     "(Dalam jutaan Rupiah)")
    return [page(f"LAPORAN TAHUNAN {cover}", name), page("Tanggal Pencatatan Saham", code),
            statement, statement, *extra]


BANK = [page(*(phrases[0] for phrases in BANK_MARKERS.values()), "non performing loan")] * 2
SUBSIDIARIES = ([page("piutang pembiayaan konsumen", "sewa pembiayaan")] * 30
                + [page("pendapatan premi", "beban klaim", "liabilitas kontrak asuransi")] * 3
                + [page("penjamin emisi efek", "modal kerja bersih disesuaikan")] * 3)


def synthetic_cases():
    print("\nB. Teks buatan")
    m = detect_metadata(report(*BANK, *SUBSIDIARIES), "cnth_2024.pdf")
    check("bank dengan anak usaha pembiayaan/asuransi/sekuritas -> bank", m,
          ticker="cnth", company="PT Contoh Sejahtera Tbk", year=2024, unit="million_idr",
          sector="bank")
    m = detect_metadata(report(*BANK, *[page("NPF", "financing to deposit ratio")] * 5))
    check("bank dengan NPF/FDR lebih sering dari NPL/LDR -> bank syariah", m, sector="islamic_bank")
    m = detect_metadata(report(*[page("risk based capital", "liabilitas kontrak asuransi",
                                      "pendapatan premi")] * 2))
    check("asuransi", m, sector="insurance")
    m = detect_metadata(report(*[page("gearing ratio", "piutang pembiayaan konsumen")] * 2))
    check("perusahaan pembiayaan", m, sector="multifinance")
    m = detect_metadata(report(*[page("modal kerja bersih disesuaikan",
                                      "perantara pedagang efek")] * 2))
    check("sekuritas", m, sector="securities")
    m = detect_metadata(report(*[page("beban pokok penjualan", "persediaan")] * 3))
    check("non-keuangan", m, sector="non_financial")
    m = detect_metadata(report(BANK[0]))
    check("penanda bank hanya di 1 halaman -> bukan bank", m, sector="non_financial")
    m = detect_metadata(report(*[page("kewajiban penyediaan modal minimum",
                                      "aset tertimbang menurut risiko", "giro wajib minimum")] * 2))
    check("hanya 3 dari 6 penanda bank (mis. induk non-bank) -> bukan bank", m,
          sector="non_financial")
    m = detect_metadata(report(*[page("piutang pembiayaan konsumen")] * 40))
    check("'piutang pembiayaan konsumen' 40 hal tanpa gearing/FAR -> bukan pembiayaan", m,
          sector="non_financial")

    english = [page("ANNUAL REPORT 2024", "PT Abadi Dua Tbk"), page("Stock Code: ABDI"),
               page("PT Abadi Dua Tbk", "31 December 2024 and 2023", "(In millions of Rupiah)")] * 2
    check("bahasa Inggris", detect_metadata(english),
          ticker="abdi", company="PT Abadi Dua Tbk", year=2024, unit="million_idr")
    m = detect_metadata(report(name="PT Bank Contoh (Persero) Tbk",
                               code="PT Bank Contoh (Persero) Tbk (IDX: BCTH)"))
    check("nama '(Persero)', kode hanya dari '(IDX: ...)'", m,
          company="PT Bank Contoh (Persero) Tbk", ticker="bcth")
    m = detect_metadata(report(name="PT BANK CONTOH TBK"))
    check("nama hanya HURUF BESAR -> tetap terbaca", m, company="PT BANK CONTOH Tbk")

    check("tahun di isi berbeda dengan nama file", detect_metadata(report(), "cnth_2023.pdf"),
          warn=True, year=2024)
    check("kode di isi berbeda dengan nama file", detect_metadata(report(), "abcd_2024.pdf"),
          warn=True, ticker="cnth")
    check("tahun sampul berbeda dengan laporan keuangan", detect_metadata(report(cover=2025)),
          warn=True, year=2024)
    check("tanpa kode saham", detect_metadata(report(code="Tanggal pencatatan 1 Juli 2001")),
          warn=True, ticker=None)
    check("dua kode saham sama kuat", detect_metadata(report(code="Kode Saham CNTH Kode Saham ZZZZ")),
          warn=True)
    check("hasil scan (hampir tanpa teks)", detect_metadata(report() + [""] * 10),
          warn=True, year=2024)


def real_cases():
    print("A. Laporan BBCA sungguhan")
    texts_2024 = None
    for year in config.YEARS:
        pdf_path = config.pdf(year)
        texts = extract_page_texts(pdf_path)
        meta = detect_metadata(texts, str(pdf_path))
        check(f"{pdf_path.name}: {meta.ticker}, {meta.company}, {meta.year}, {meta.unit}, "
              f"{meta.sector} (deteksi {meta.seconds} s)", meta, year=year, **EXPECTED)
        if year == 2024:
            texts_2024 = texts
    return texts_2024


def perturbed_cases(texts: list[str]):
    print("\nC. Teks BBCA 2024 yang dirusak")
    norm = [normalize(t) for t in texts]
    no_code = [t for t, n in zip(texts, norm) if "kode saham" not in n]
    meta = detect_metadata(no_code)
    check(f"tanpa {len(texts) - len(no_code)} halaman 'Kode Saham' -> kode dari pola cadangan "
          f"({meta.evidence['ticker']})", meta, ticker="bbca")

    phrases = [p for group in BANK_MARKERS.values() for p in group]
    no_bank = [t for t, n in zip(texts, norm) if not any(p in n for p in phrases)]
    left = sum("piutang pembiayaan konsumen" in normalize(t) for t in no_bank)
    meta = detect_metadata(no_bank)
    check(f"tanpa {len(texts) - len(no_bank)} halaman berpenanda prudensial bank "
          f"('piutang pembiayaan konsumen' masih di {left} hal) -> bukan bank", meta,
          sector="non_financial")


def main() -> int:
    texts_2024 = real_cases()
    synthetic_cases()
    perturbed_cases(texts_2024)
    print(f"\nHASIL: {'LULUS' if not failures else f'GAGAL ({failures} kasus)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
