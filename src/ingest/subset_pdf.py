"""
Tugas 3.3 (bagian 1) -- PDF potongan + peta halaman.  docs/PANDUAN_MINGGU3.md, Langkah 2.

Docling hanya menerima rentang halaman BERURUTAN (page_range=(awal, akhir)), sedangkan
halaman yang lolos penyaring tersebar (mis. 20-22, 36, 104-105, 540-712). Jadi halaman itu
dikumpulkan dulu menjadi satu PDF potongan, dan PDF potongan itulah yang diparse Docling.

Akibatnya nomor halaman di hasil Docling adalah nomor di PDF POTONGAN. PageMap
mengembalikannya ke nomor halaman ASLI. Tanpa itu setiap sumber halaman yang dikutip sistem
salah -- dan salahnya tidak kelihatan, karena nomornya tetap tampak wajar.

Terukur 30-10-2026 pada BCA: 230-262 halaman, 1-2 detik, PDF potongan 2,8-3,7 MB
(asli 13-58 MB).

Kriteria selesai:  python scripts/check_subset_pdf.py
"""

from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfWriter

from src.ingest.page_filter import open_pdf


@dataclass(frozen=True)
class PageMap:
    """Peta PDF potongan -> laporan asli: halaman potongan ke-i = original_pages[i - 1].

    Disimpan di .meta.json sebagai LIST, bukan dict {potongan: asli}. Kunci dict JSON
    selalu string, jadi {1: 18} kembali sebagai {"1": 18} dan pencarian dengan angka
    diam-diam gagal.
    """
    original_pages: tuple[int, ...]

    def __post_init__(self):
        p = self.original_pages
        if not p:
            raise ValueError("peta halaman kosong -- tidak ada halaman yang lolos saringan")
        if p[0] < 1 or any(b <= a for a, b in zip(p, p[1:])):
            raise ValueError("nomor halaman asli harus mulai dari 1 dan urut naik tanpa duplikat")

    def __len__(self) -> int:
        return len(self.original_pages)

    def to_original(self, subset_page: int) -> int:
        """Nomor halaman potongan (mulai 1, sama dengan `page_no` Docling) -> nomor asli."""
        if not 1 <= subset_page <= len(self.original_pages):
            # Sengaja error, bukan menebak: nomor halaman salah lebih berbahaya dari crash.
            raise IndexError(f"halaman potongan {subset_page} di luar 1..{len(self.original_pages)}")
        return self.original_pages[subset_page - 1]

    def to_subset(self, original_page: int) -> int | None:
        """Kebalikannya. None kalau halaman asli itu tidak lolos saringan."""
        i = bisect_left(self.original_pages, original_page)
        if i < len(self.original_pages) and self.original_pages[i] == original_page:
            return i + 1
        return None

    def to_list(self) -> list[int]:
        return list(self.original_pages)

    @classmethod
    def from_list(cls, pages: list[int]) -> "PageMap":
        return cls(tuple(int(p) for p in pages))


def build_subset(source_pdf: str | Path, pages: list[int], out_pdf: str | Path) -> PageMap:
    """Tulis PDF berisi `pages` (nomor ASLI, mulai 1, urut naik) ke `out_pdf`."""
    page_map = PageMap(tuple(pages))
    reader = open_pdf(source_pdf)
    if page_map.original_pages[-1] > len(reader.pages):
        raise ValueError(f"halaman {page_map.original_pages[-1]} tidak ada -- "
                         f"{Path(source_pdf).name} hanya {len(reader.pages)} halaman")

    # Halaman yang memakai font/gambar yang sama tetap berbagi satu objek di PDF potongan
    # (pypdf menyalin tiap objek sekali), jadi ukurannya jauh lebih kecil dari aslinya.
    writer = PdfWriter()
    for number in page_map.original_pages:
        writer.add_page(reader.pages[number - 1])
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    writer.write(out_pdf)
    return page_map


def _render(page) -> bytes:
    """Piksel halaman. Skala kecil cukup -- yang dicari gambar/elemen yang hilang."""
    return page.render(scale=0.75).to_pil().tobytes()


def verify_subset(source_pdf: str | Path, subset_pdf: str | Path, page_map: PageMap) -> list[str]:
    """Bandingkan SETIAP halaman potongan dengan halaman aslinya menurut peta.

    Yang dibandingkan: teks, ukuran halaman (MediaBox & CropBox), rotasi, dan tampilan
    (piksel hasil render). Tampilan perlu karena model layout Docling membaca halaman
    sebagai GAMBAR -- teks yang sama belum menjamin tidak ada gambar/garis tabel yang hilang
    saat PDF menyusut dari 58 MB jadi 3 MB. Render memakai pypdfium2 (dependensi Docling),
    sekitar 2 detik per laporan. Kembalian kosong = PDF potongan dan peta cocok.
    """
    import pypdfium2 as pdfium

    source, subset = open_pdf(source_pdf), open_pdf(subset_pdf)
    if len(subset.pages) != len(page_map):
        return [f"PDF potongan {len(subset.pages)} halaman, peta {len(page_map)} halaman"]

    problems = []
    source_doc, subset_doc = pdfium.PdfDocument(str(source_pdf)), pdfium.PdfDocument(str(subset_pdf))
    try:
        for subset_page, page in enumerate(subset.pages, start=1):
            original_page = page_map.to_original(subset_page)
            original = source.pages[original_page - 1]
            checks = {
                "teks": (page.extract_text(), original.extract_text()),
                "MediaBox": (list(page.mediabox), list(original.mediabox)),
                "CropBox": (list(page.cropbox), list(original.cropbox)),
                "rotasi": (page.rotation, original.rotation),
                "tampilan": (_render(subset_doc[subset_page - 1]),
                             _render(source_doc[original_page - 1])),
            }
            for name, (got, expected) in checks.items():
                if got != expected:
                    problems.append(f"potongan hal {subset_page} (asli {original_page}): {name} berbeda")
    finally:
        # Windows: file yang masih dibuka pdfium tidak bisa dihapus (folder sementara gagal)
        source_doc.close()
        subset_doc.close()
    return problems
