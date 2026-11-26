"""
Tugas 1.2 -- inspeksi PDF laporan tahunan BCA.

Jalankan:  python scripts/inspect_pdf.py

Untuk setiap PDF di data/raw/ script ini melaporkan:
  1. jumlah halaman + ukuran file
  2. text-based atau hasil scan  (penting: scan -> Docling harus OCR -> 3x lebih lama)
  3. di halaman berapa bagian-bagian penting berada

Output bagian (3) dipakai untuk mengisi sheet '1_angka_mentah' dan
'2_rasio_resmi' di data/ground_truth.xlsx -- Anda tidak perlu scroll manual
600 halaman.

CATATAN: nomor halaman yang dilaporkan adalah INDEKS PDF (halaman fisik ke-n),
belum tentu sama dengan nomor halaman yang tercetak di dokumen. Pencariannya memakai
teks pypdf, yang juga membaca isi di luar area tampak -- hasilnya bisa meleset satu
halaman, jadi pastikan lokasi akhir dengan melihat halamannya (temuan 05-11-2026).
"""

import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("pypdf belum terpasang.  ->  pip install pypdf")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# bagian yang dicari -> daftar kata kunci (dicocokkan lowercase, cukup satu kena)
SECTIONS = {
    "Ikhtisar Data Keuangan": ["ikhtisar data keuangan", "ikhtisar keuangan"],
    "Tabel Rasio Keuangan": ["rasio keuangan", "rasio-rasio keuangan"],
    "Laporan Posisi Keuangan (Neraca)": ["laporan posisi keuangan konsolidasian",
                                         "laporan posisi keuangan"],
    "Laporan Laba Rugi": ["laporan laba rugi dan penghasilan komprehensif",
                          "laporan laba rugi konsolidasian"],
    "CaLK - Kredit yang Diberikan": ["kredit yang diberikan"],
    "Tabel Kolektibilitas (utk NPL)": ["dalam perhatian khusus", "kurang lancar"],
    "Simpanan Nasabah (utk DPK)": ["simpanan dari nasabah", "deposito berjangka"],
    "KPMM / CAR / ATMR": ["kewajiban penyediaan modal minimum", "kpmm",
                          "aset tertimbang menurut risiko", "atmr"],
    "Aktiva/Aset Produktif (utk NIM)": ["aset produktif", "aktiva produktif"],
    "Analisis & Pembahasan Manajemen": ["analisis dan pembahasan manajemen",
                                        "tinjauan keuangan"],
    # --- khusus BANK: menentukan apakah bank lain bisa diproses dengan formula &
    #     saringan halaman yang sama dengan BBCA (risiko R11, tugas 2.7)
    "Lap. Entitas Induk (basis Bank)": ["entitas induk saja", "parent entity only"],
    "Fn rasio 'induk perusahaan saja'": ["induk perusahaan saja", "bank only"],
    # --- khusus NON-KEUANGAN: angka untuk profil rasio non-keuangan (tugas 2.8)
    "Aset lancar (utk Current Ratio)": ["jumlah aset lancar", "total aset lancar",
                                        "total current assets"],
    "Pendapatan (utk NPM & TATO)": ["pendapatan bersih", "penjualan bersih",
                                    "jumlah pendapatan", "net revenues", "net sales"],
    # --- SATUAN laporan: beda antar emiten (risiko R15). Saringan halaman di
    #     Minggu 3 bergantung pada penanda ini -- kalau satuannya miliar atau USD,
    #     penanda "dalam jutaan rupiah" saja akan melewatkan seluruh laporan keuangan.
    "Penanda tabel keuangan": ["dalam jutaan rupiah", "in millions of rupiah",
                               "dalam miliaran rupiah", "dalam miliar rupiah",
                               "in billions of rupiah", "dolar amerika serikat",
                               "in thousands of us dollars", "in us dollars"],
    "  satuan: jutaan Rupiah": ["dalam jutaan rupiah", "in millions of rupiah"],
    "  satuan: miliar Rupiah": ["dalam miliaran rupiah", "dalam miliar rupiah",
                                "in billions of rupiah"],
    "  satuan: Dolar AS": ["dolar amerika serikat", "in thousands of us dollars",
                           "in us dollars"],
}

MIN_CHARS_PER_PAGE = 200   # di bawah ini dianggap kemungkinan hasil scan


def inspect(path: Path):
    print(f"\n{'=' * 78}\n  {path.name}   ({path.stat().st_size / 1_048_576:.1f} MB)\n{'=' * 78}")

    try:
        reader = PdfReader(str(path))
    except Exception as e:
        print(f"  GAGAL dibuka: {e}")
        return None

    n = len(reader.pages)
    if reader.is_encrypted:
        print("  PDF terenkripsi -- coba decrypt dulu, ekstraksi teks mungkin gagal.")

    print(f"  Jumlah halaman : {n}")
    print(f"  Mengekstrak teks ... (bisa 1-2 menit untuk dokumen besar)")

    texts, total_chars = [], 0
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        texts.append(t.lower())
        total_chars += len(t)
        if n > 100 and (i + 1) % 100 == 0:
            print(f"      {i + 1}/{n} halaman", end="\r")

    avg_chars = total_chars / n if n else 0
    empty_pages = sum(1 for t in texts if len(t.strip()) < 50)
    kind = "TEXT-BASED (bagus)" if avg_chars >= MIN_CHARS_PER_PAGE else "kemungkinan SCAN / gambar"

    print(f"  {' ' * 30}")
    print(f"  Rata-rata karakter/halaman : {avg_chars:,.0f}")
    print(f"  Halaman (hampir) tanpa teks: {empty_pages} dari {n}")
    print(f"  Jenis PDF : {kind}")
    if avg_chars < MIN_CHARS_PER_PAGE:
        print("    -> Docling perlu OCR. Estimasi waktu parsing di Minggu 3 dikali ~3.")

    print(f"\n  Lokasi bagian penting (indeks halaman PDF):")
    findings = {}
    for name, keywords in SECTIONS.items():
        hits = [i + 1 for i, t in enumerate(texts) if any(k in t for k in keywords)]
        findings[name] = hits
        if not hits:
            print(f"    {name:<34} TIDAK DITEMUKAN")
        else:
            shown = ", ".join(map(str, hits[:8]))
            more = f"  (+{len(hits) - 8} halaman lain)" if len(hits) > 8 else ""
            print(f"    {name:<34} hal. {shown}{more}")

    return {"file": path.name, "pages": n, "mb": path.stat().st_size / 1_048_576,
            "avg_chars": avg_chars, "kind": kind, "findings": findings}


def main():
    if not RAW.exists():
        sys.exit(f"Folder tidak ada: {RAW}")

    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"Belum ada PDF di {RAW}\n"
                 f"Taruh file dengan nama: bbca_2022.pdf, bbca_2023.pdf, bbca_2024.pdf")

    results = [h for h in (inspect(p) for p in pdfs) if h]

    print(f"\n\n{'=' * 78}\n  TABEL INVENTARIS -- tempel ke docs/catatan_validasi_rasio.md\n{'=' * 78}\n")
    print("| Tahun | Nama file | Jumlah hal. | Ukuran | Text-based / Scan | Tanggal unduh |")
    print("|---|---|---|---|---|---|")
    for h in results:
        year = "".join(c for c in h["file"] if c.isdigit())[:4] or "?"
        print(f"| {year} | `{h['file']}` | {h['pages']} | {h['mb']:.1f} MB | {h['kind']} | |")

    print(f"\n  {len(results)} PDF diperiksa.")
    likely_scanned = [h["file"] for h in results if h["avg_chars"] < MIN_CHARS_PER_PAGE]
    if likely_scanned:
        print(f"  PERHATIAN -- kemungkinan hasil scan: {', '.join(likely_scanned)}")


if __name__ == "__main__":
    main()
