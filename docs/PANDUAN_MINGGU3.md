# Panduan Rinci Minggu 3–4 — Pipeline Ingest: Saring → Parse → Simpan

Tujuan dua minggu ini: mengubah PDF laporan tahunan BCA menjadi teks dan tabel yang rapi,
**lengkap dengan nomor halaman aslinya**, dengan cara yang nanti juga dipakai saat pengguna
mengunggah laporan lewat Telegram.

Perkiraan kerja: **6–8 hari** dari 2 minggu. Semua kode dijalankan dari venv
(`(.venv)` harus muncul di prompt).

---

## Status gerbang: bimbingan belum dilakukan

Roadmap mensyaratkan bimbingan sebelum Minggu 3, karena keputusan #5 (ruang lingkup)
memengaruhi desain pipeline. Tapi **sebagian besar minggu ini tidak bergantung pada keputusan
itu** — mengubah PDF BCA jadi teks rapi tetap dibutuhkan, apa pun hasil bimbingannya.

| Langkah | Bergantung pada bimbingan? |
|---|---|
| 1–6, 8, 9 | **Tidak** — kerjakan sekarang |
| 7b (mengenali emiten & sektor) | ~~Ya, keputusan #5~~ — dikerjakan 14-11-2026 dengan rancangan yang berlaku untuk kedua kemungkinan keputusan (lihat Langkah 7) |

Bimbingan tetap diperlukan untuk **mengesahkan** keputusan #5, tapi tidak lagi menahan Minggu 3.

---

## Hasil pengecekan sebelum panduan ini ditulis (28-10-2026)

Rancangan di bawah sudah diuji pada ketiga PDF BCA dan pada Docling yang terpasang:

- **Penyaring halaman** dengan penanda satuan saja **melewatkan tabel rasio resmi** di laporan
  2023 (hal 19) dan 2024 (hal 21) — halaman itu berisi persen, bukan Rupiah, jadi tidak punya
  penanda satuan. Ditambah aturan "≥ 3 istilah rasio", ketujuh kelompok halaman penting
  tertangkap di ketiga laporan, dengan total **35–38%** halaman.
- **Docling hanya bisa memproses rentang halaman berurutan** (`page_range=(awal, akhir)`), bukan
  daftar halaman acak → halaman tersaring dikumpulkan dulu jadi PDF baru (Langkah 2).
- **OCR di Docling menyala secara bawaan.** PDF BCA berbentuk teks, jadi OCR harus dimatikan —
  lebih cepat dan tidak menambah salah baca.
- Model Docling (`docling-layout-heron`, `docling-models`) **sudah ada di cache** — tidak perlu
  mengunduh.

---

## Langkah 1 — Penyaring halaman (3.1) · ½–1 hari  ✅ LULUS (30-10-2026)

**File:** `src/ingest/page_filter.py` · **pemeriksa:** `scripts/check_page_filter.py`

```powershell
python scripts/check_page_filter.py                      # kriteria selesai, ketiga laporan
python -m src.ingest.page_filter data\raw\bbca_2024.pdf   # lihat hasil satu laporan
```

**Tugas:** dari sebuah PDF, kembalikan daftar nomor halaman (asli, mulai 1) yang perlu diproses
Docling, plus satuan laporan yang dominan.

**Aturan — sudah diuji pada ketiga laporan BCA:**

```python
UNIT_MARKERS = {                       # satuan -> penandanya
    "million_idr": ["dalam jutaan rupiah", "in millions of rupiah"],
    "billion_idr": ["dalam miliaran rupiah", "dalam miliar rupiah", "in billions of rupiah"],
    "thousand_usd": [...],             # disiapkan untuk emiten ber-USD (R15), belum diuji
}
RATIO_TERMS = [
    "capital adequacy ratio", "non performing loan", "return on asset",
    "return on equity", "net interest margin", "loan to deposit ratio",
    "beban operasional terhadap pendapatan operasional",
]
# halaman LOLOS kalau: memuat salah satu penanda satuan,
#                      ATAU memuat paling sedikit 3 RATIO_TERMS
# teks dirapikan dulu oleh normalize(); ekstraksi teks pakai pypdf -- 13-21 detik per laporan
```

**`normalize()` — ditambahkan saat implementasi (aturan versi 2).** Sebelum dicocokkan, teks
di-lowercase, tanda hubung di tengah kata diganti spasi, dan semua spasi/ganti baris diringkas
jadi satu spasi. Alasannya: PDF sering memotong frasa di tengah — `Non-⏎Performing Loan`
(2025 hal 95), `dalam jutaan ⏎Rupiah` (2024 hal 372, sebuah tabel). Tanpa ini, lolos-tidaknya
halaman bergantung pada letak ganti baris. Efeknya **+2 halaman per laporan**:

| Laporan | Halaman tambahan | Isinya |
|---|---|---|
| `bbca_2023` | 35, 283 | target rasio tahun berikutnya (ROA, ROE, NIM) |
| `bbca_2024` | 36, 372 | target rasio; tabel bertanda "dalam jutaan ⏎Rupiah" |
| `bbca_2025` | 95, 200 | pembahasan CAR/NPL/LDR; **tinjauan industri perbankan** |

> **Catatan untuk Minggu 9:** halaman target (mis. "ROA 3,4%–3,6%") dan halaman tinjauan
> industri (NPL & LDR *industri*, bukan BCA) ikut lolos — sebagian sudah lolos sejak aturan
> versi 1. Extraction Agent harus mengambil angka dari tabel resmi, bukan dari halaman ini.
> Penyaring sengaja mengutamakan *tidak melewatkan* halaman; memilah halaman mana yang
> benar adalah tugas retrieval dan agent.

**Jangan** memakai pencocokan judul bagian ("ikhtisar data keuangan", "laporan posisi
keuangan"): judul itu tercetak di header navigasi hampir setiap halaman — terbukti cocok di 257
halaman di Minggu 1.

**Satuan dominan:** hitung berapa halaman memuat penanda jutaan vs miliar; yang terbanyak adalah
satuan laporan. BBCA: jutaan 240 halaman, miliar 17 (itu tabel Ikhtisar).

**Kriteria selesai** — ketujuh kelompok halaman ini harus tertangkap:

| Bagian | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Ikhtisar + tabel rasio resmi | 18, 19 | 20, 21 | 15, 16 |
| Laporan posisi keuangan konsolidasian | 576, 577 | 540, 541 | 461, 462 |
| Laporan laba rugi | 578 | 542 | 463 |
| Catatan KPMM (Tier 1, ATMR) | 727 | 703 | 594 |
| Catatan NPL | 646 | 701 | 590 |
| Entitas Induk — aset | 738 | 704 | 595 |
| Entitas Induk — liabilitas | 739 | 705 | 596 |

Total yang tersaring: **261 / 262 / 230 halaman** (35–38%). Angka 259 / 260 / 228 yang tertulis
sebelumnya adalah hasil aturan versi 1, sebelum `normalize()`.

**Hasil (30-10-2026, aturan versi 2, pypdf 6.21.2):**

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Halaman lolos | 261 dari 747 (35%) | 262 dari 714 (37%) | 230 dari 605 (38%) |
| Satuan dominan | jutaan Rp | jutaan Rp (241 hal; miliar 17) | jutaan Rp |
| Ketujuh kelompok | ✅ | ✅ | ✅ |
| Waktu ekstraksi + saring | 21,3 detik | 13,5 detik | 16,9 detik |

Selain itu diuji: PDF tanpa teks (seperti hasil scan) → 0 halaman lolos, satuan `None`, dan
ditandai `looks_scanned` — supaya pipeline tahu harus OCR, bukan diam-diam menghasilkan kosong.

**Kalau angka di `check_page_filter.py` berubah** (mis. setelah pypdf diperbarui): lihat dulu
halaman mana yang bertambah atau hilang, baru perbarui `EXPECTED_TOTAL` dan angka di panduan ini.
Setiap kali aturan diubah, naikkan `RULE_VERSION` — nilainya ikut disimpan di `.meta.json`
(Langkah 3), sehingga hasil parse dengan aturan lama bisa dikenali.

---

## Langkah 2 — PDF potongan + peta halaman · ½ hari  ✅ LULUS (30-10-2026)

**File:** `src/ingest/subset_pdf.py` · **pemeriksa:** `scripts/check_subset_pdf.py`

```powershell
python scripts/check_subset_pdf.py           # PDF potongan dibuat, dicek, lalu dihapus
python scripts/check_subset_pdf.py --keep    # disimpan di data\markdown\ untuk dibuka sendiri
```

Karena Docling hanya menerima rentang berurutan, halaman tersaring dikumpulkan jadi satu PDF
sementara. **Peta halaman wajib disimpan** — tanpa itu, nomor halaman di hasil Docling adalah
nomor di PDF potongan, bukan di laporan asli, dan setiap sumber halaman yang dikutip sistem
akan salah.

```python
from src.ingest.page_filter import filter_pages
from src.ingest.subset_pdf import build_subset, PageMap

selection = filter_pages(source_pdf)
page_map = build_subset(source_pdf, selection.pages, subset_pdf)

page_map.to_original(253)     # -> 703   halaman potongan (page_no Docling) -> halaman asli
page_map.to_subset(703)       # -> 253   kebalikannya; None kalau halaman tidak lolos saringan
page_map.to_list()            # -> [20, 21, 22, 36, ...]   bentuk yang disimpan di .meta.json
PageMap.from_list(meta["page_map"])                      # membaca kembali
```

Peta disimpan sebagai **list**, bukan dict `{potongan: asli}` seperti contoh sebelumnya:
kunci dict JSON selalu jadi string, sehingga `{1: 18}` kembali sebagai `{"1": 18}` dan
pencarian `page_map[1]` diam-diam gagal. `to_original()` sengaja **error** untuk nomor di luar
rentang — nomor halaman yang salah lebih berbahaya daripada program berhenti.

**Pemeriksaan — lebih dari "cek cepat halaman 1":** `verify_subset()` membandingkan *setiap*
halaman potongan dengan halaman aslinya menurut peta: teks, ukuran halaman, rotasi, dan
**tampilan** (piksel hasil render). Tampilan ikut dicek karena model layout Docling membaca
halaman sebagai gambar, dan PDF potongan menyusut drastis — perlu bukti tidak ada gambar atau
garis tabel yang hilang.

**Hasil (30-10-2026):**

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Halaman potongan | 261 | 262 | 230 |
| Ukuran asli → potongan | 55,6 → 3,3 MB | 12,4 → 2,7 MB | 37,0 → 3,5 MB |
| Waktu membuat | 1,3 detik | 1,3 detik | 1,6 detik |
| Halaman identik dengan aslinya | 261/261 | 262/262 | 230/230 |
| Uji titik: Tier 1 BANK di Catatan KPMM | potongan 242 → asli 727 ✅ | potongan 253 → asli 703 ✅ | potongan 221 → asli 594 ✅ |

> **Koreksi 05-11-2026.** Versi pertama baris terakhir menulis "potongan 220 → asli 593 ✅", dan
> itu **keliru**. Uji titiknya memakai teks pypdf, yang ikut membaca isi di luar area halaman
> yang tampak: angka KPMM 2025 ada di lapisan teks hal 593, padahal baru tampil di hal 594.
> Uji titik kini hanya menerima teks yang tampak (`get_text_bounded` dari pypdfium2), dan
> nilainya memang tidak tampak di hal 593. Lihat Langkah 5.

Uji negatif juga dijalankan: peta yang digeser satu halaman menghasilkan 262 masalah
terdeteksi (artinya pemeriksa benar-benar bisa gagal), dan peta kosong, tidak urut, duplikat,
atau mulai dari 0 ditolak.

> Ukurannya mengecil karena sebagian besar isi file BCA adalah foto di halaman non-keuangan.
> Kesimpulannya, file yang dikirim ke Docling kecil — tapi **batas unduh 20 MB bot Telegram
> (R18) tetap berlaku**, karena yang diunggah pengguna adalah file aslinya.

---

## Langkah 3 — Parse dengan Docling (3.3) · 1 hari  ✅ SELESAI (31-10-2026), diuji pada 3 halaman

**File:** `src/ingest/parse_pdf.py` · opsi Docling di `src/config.py` (`DOCLING_*`)

```powershell
python -m src.ingest.parse_pdf data\raw\bbca_2024.pdf                  # laporan penuh (Langkah 5)
python -m src.ingest.parse_pdf data\raw\bbca_2024.pdf --max-pages 20   # Langkah 4
python -m src.ingest.parse_pdf data\raw\bbca_2024.pdf --pages 20,21,703
python -m src.ingest.parse_pdf data\raw\bbca_2024.pdf --force          # abaikan cache
```

Satu perintah menjalankan seluruh alur: saring (Langkah 1) → PDF potongan (Langkah 2) →
Docling → simpan. Parse **sebagian** (`--max-pages`, `--pages`) disimpan di
`data\markdown\trial\` dan tidak pernah dipakai sebagai cache, supaya tidak tertukar dengan
hasil laporan penuh.

**Konfigurasi — sudah diuji di venv Anda** (di kode, nilainya dibaca dari `config.py`):

```python
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice

options = PdfPipelineOptions()
options.do_ocr = False                                   # PDF BCA berbentuk teks
options.do_table_structure = True
options.table_structure_options.mode = TableFormerMode.ACCURATE
options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA)

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
doc = converter.convert(subset_pdf).document
```

**Yang disimpan per laporan**, di `data/markdown/`:

| File | Isi | Kegunaan |
|---|---|---|
| `bbca_2024.json` | `doc.save_as_json(...)` — dokumen Docling lengkap | **sumber kebenaran**: struktur tabel + posisi + nomor halaman (nomor **potongan**) |
| `bbca_2024.md` | markdown per halaman, tiap halaman diawali `<!-- halaman 703 \| potongan 253 -->` | dibaca manusia saat inspeksi — cari dengan nomor halaman **asli** |
| `bbca_2024.meta.json` | SHA-256 PDF, hasil saringan (`selection.to_dict()`, termasuk `rule_version`), peta halaman (`page_map.to_list()`), satuan, opsi & versi Docling, jumlah halaman/tabel, waktu tiap tahap | jejak & cache |
| `bbca_2024.subset.pdf` | PDF potongan yang diberikan ke Docling | debug: halaman ke-N di sini = `page_no` N di `.json` |

`.md` tidak lagi memakai `page_break_placeholder`, karena penanda itu tidak menyebut nomor
halaman. `.meta.json` ditulis **paling akhir** dan dihapus di awal setiap parse, jadi
keberadaannya berarti parse selesai utuh.

**Cache:** parse dilewati kalau `meta.json` sudah ada dengan **hash SHA-256 PDF, versi aturan
saringan, opsi Docling, dan versi Docling yang sama**, dan `.json` serta `.md` masih ada.
Kalau salah satunya berubah, laporan diparse ulang. Diuji 31-10-2026 dengan 5 skenario: file
sama → dilewati (0,0 detik); `--force`, opsi berubah, dan `.md` terhapus → diparse ulang.

**GPU — ditemukan dan diperbaiki saat implementasi.** Contoh `del converter` +
`torch.cuda.empty_cache()` ternyata **tidak** melepas GPU: **407 MB tertinggal** setelah
parse. Penyebabnya bukan kode GPU. Saat pertama diimpor, Docling mencoba backend opsional
(`odfdo`, `arelle`) yang tidak terpasang, lalu menyimpan error-nya beserta *traceback*.
*Traceback* itu menahan frame fungsi pemanggil selamanya, termasuk variabel `converter` di
dalamnya. Perbaikannya: Docling diimpor di **level modul** `parse_pdf.py`, tidak di dalam
fungsi. Hasilnya, sisa VRAM setelah parse **18 MB**, tetap sama di parse kedua dalam proses
yang sama (tidak menumpuk). Ini penting untuk bot Telegram (Minggu 16), yang hidup lama dan
juga memuat BGE-M3 (2,12 GB dari 6 GB). **Aturannya: jangan mengimpor Docling di dalam
fungsi** di file mana pun.

**Uji asap (31-10-2026, `bbca_2024` hal 20, 21, 703):**

| Hal | Isi | Hasil |
|---|---|---|
| 20, 21 | Ikhtisar + tabel rasio resmi (33×6, 45×6) | CAR 29,4%, NPL bruto 1,8%, ROA 3,9%, ROE 24,6%, NIM 5,8%, LDR 78,4% — kolom tahun benar |
| 703 | Catatan KPMM (26×5) | header "2024 - Bank / 2024 - Konsolidasian / 2023 - …" utuh; Tier 1 BANK **239.468.855** di kolom yang benar |

- Waktu: muat model 4,9 detik + parse ~1,9 detik/halaman (3 halaman — angka per halaman
  untuk laporan penuh diukur di Langkah 4). VRAM puncak ~0,6 GB.
- `.json` bisa dibaca ulang (`DoclingDocument.load_from_json`), dan `page_no` 3 → halaman
  asli 703 lewat peta halaman.
- Input salah ditolak dengan pesan singkat: PDF hasil scan, nama file bukan
  `<kode>_<tahun>.pdf`, file tidak ada.

> **Catatan untuk Minggu 9:** nomor catatan kaki menempel di label tabel, mis.
> `Rasio Kecukupan Modal (Capital Adequacy Ratio - CAR) 6` dan `... NPL) - bruto 7`. Angka
> `6`/`7` itu nomor catatan kaki (yang menjelaskan basis "induk perusahaan saja"), **bukan
> nilai**. Extraction Agent harus mengabaikannya; isi catatan kakinya justru berguna untuk
> menentukan basis rasio.

---

## Langkah 4 — Ukur waktu (3.4) · 1 jam  ✅ SELESAI (05-11-2026)

Sebelum memproses laporan penuh, uji **20 halaman tersaring pertama** dari `bbca_2024.pdf`:

```powershell
python -m src.ingest.parse_pdf data\raw\bbca_2024.pdf --max-pages 20
```

Pakai angka `parse ... s/halaman` di keluarannya (waktu muat model dihitung terpisah, sekitar
5 detik, hanya sekali per laporan). Catat waktunya, lalu perkirakan:

```
perkiraan laporan penuh = waktu 20 halaman × (jumlah halaman tersaring ÷ 20)
```

Target kasar: **satu laporan selesai dalam hitungan menit**, karena nanti pengguna menunggu
hasil unggahannya di Telegram. Kalau jauh lebih lama, lihat tabel masalah di bawah.

**Hasil.** 20 halaman pertama semuanya bagian depan laporan, padahal 173 dari 262 halaman
tersaring `bbca_2024` adalah laporan keuangan (hal 540–712). Karena itu diukur juga contoh dari
bagian laporan keuangan:

| Contoh (`bbca_2024`) | Halaman | Tabel | Parse | Per halaman | VRAM puncak |
|---|---|---|---|---|---|
| 20 halaman pertama: 20–22, 36, 104–105, 143, 154–158, 166–171, 174–175 | 20 | 22 | 36,7 detik | **1,83 detik** | — |
| Laporan keuangan: 540–549, 700–709 | 20 | 21 | 40,2 detik | **2,01 detik** | 0,93 GB |

**Perkiraan laporan penuh** (belum termasuk sekitar 25–30 detik untuk saring, potong, dan muat
model). Angka sebenarnya tercatat di `.meta.json` setelah Langkah 5.

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Halaman tersaring | 261 | 262 | 230 |
| Perkiraan parse | 8,0–8,7 menit | 8,0–8,8 menit | 7,0–7,7 menit |

Total ketiga laporan **sekitar 25 menit**, dan `.json` sekitar 30 MB per laporan. Target
"hitungan menit" **tercapai**: tanpa penyaring, `bbca_2024` (714 halaman) akan butuh sekitar
22–24 menit. Tapi 8–9 menit tetap lama bagi pengguna Telegram yang menunggu, jadi bot wajib
menampilkan kemajuan — parameter `progress` di `parse_report()` sudah disediakan (16.3b).

**Temuan dari pesan peringatan.** Keluaran menampilkan `1 of 225 pdf cells ... of the 39x3 grid
and were dropped from the table`, dari tabel LI1 di hal 156:

- **Yang dibuang kemungkinan besar kata "dalam"** di judul kolom a ("...tercantum *dalam*
  publikasi..."). **Tidak ada angka yang hilang.** Judul kolomnya juga terbelah dua baris, sehingga
  "publikasi laporan keuangan" masuk ke baris "Aset". Ini bukan tabel sumber keenam rasio, tapi
  menunjukkan bentuk kesalahan yang harus dicari di Langkah 6.
- **Status parse tetap `success`** meski ada isi yang dibuang, dan log inilah satu-satunya
  tandanya. Karena itu `parse_pdf.py` kini menyimpan semua peringatan di kunci `warnings` pada
  `.meta.json`. Ukuran grid di pesan (39x3) membantu menemukan tabelnya.

---

## Langkah 5 — Parse ketiga laporan BCA (3.5) · tergantung Langkah 4  ✅ SELESAI (terparse 05-11-2026, backup 14-11-2026)

Jalankan untuk `bbca_2023`, `bbca_2024`, `bbca_2025`. Setelah selesai, **salin `data\markdown\`
ke Google Drive** — folder ini tidak ikut git, dan hasil parse adalah aset yang mahal dibuat ulang.

**Hasil:**

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Status | success | success | success |
| Halaman / tabel | 261 / 302 | 262 / 302 | 230 / 298 |
| Parse | 6,3 menit (1,45 s/hal) | 7,7 menit (1,75 s/hal) | 6,5 menit (1,69 s/hal) |
| Simpan | 81 detik | 126 detik | 52 detik |
| **Total** | **8,2 menit** | **10,1 menit** | **8,1 menit** |
| `.json` | 36,7 MB | 37,0 MB | 34,8 MB |
| Warning / sel dibuang | 10 / 25 | 10 / 24 | 18 / 33 |

Total ketiganya **26,4 menit**, dan seluruh folder sekitar 118 MB. Dibanding perkiraan Langkah 4,
parse lebih cepat, tetapi tahap simpan jauh lebih lama (pada 20 halaman kurang dari 1 detik, jadi
tidak ikut diperkirakan). Penyebabnya `to_markdown()` mengekspor per halaman dan setiap ekspor
menelusuri seluruh dokumen: 0,21–0,26 detik × jumlah halaman. Sekali ekspor seluruh dokumen hanya
1 detik, jadi tahap ini masih bisa dipercepat kalau waktu tunggu di Telegram jadi masalah.

**Audit hasil (skrip sementara, tanpa mengubah hasil parse):**

| Yang diperiksa | Hasil |
|---|---|
| Angka berformat ribuan/desimal yang **tampak** di halaman tersaring vs hasil Docling (dihitung per kemunculan) | **33.162 tampak, 0 kurang** |
| Nilai ground truth yang tercetak sebagai satu angka, per laporan (termasuk angka pembanding) | **129 dari 129 terbaca** (32, 43, 54) |
| Warning pada ke-27 halaman penting, diparse tersendiri | **0** |
| Kata yang tampak vs hasil Docling (di luar header navigasi) | kurang 0,12–0,22%; yang terbanyak potongan kata di tepi halaman dan kata yang tertulis menyatu atau terpisah |

Batas audit ini: **hanya membuktikan angkanya ada, bukan berada di baris dan kolom yang benar** —
itu tugas Langkah 6. Ke-82 sel yang dibuang tidak mengurangi angka berformat ribuan/desimal, tapi
audit tidak mencakup angka kecil tanpa pemisah atau tanda `-`. Peringatan `Table cell bbox ...
page 50` di `bbca_2025` adalah hal asli 153: koordinat tabel melewati tepi halaman lalu dipangkas.

**Temuan — lapisan teks memuat isi halaman lain.** Di 36 / 33 / 71 halaman, lapisan teks PDF BCA
berisi minimal 5 angka di luar area yang tampak. Pada 4 halaman yang dicek (2023 hal 578, 2024 hal
156, 2025 hal 593 dan 595), semuanya isi halaman sesudahnya. pypdf ikut membacanya; Docling tidak.

- **Dua nomor halaman ground truth meleset satu halaman**, karena dicari dengan pypdf di Minggu 1:
  KPMM 2025 seharusnya **hal 594** (bukan 593), NPL 2025 seharusnya **hal 590** (bukan 589).
  **Nilainya tidak berubah, jadi rasio dan MAPE tetap.** Rujukan sudah dikoreksi di
  `ground_truth.xlsx` (10 sel kolom G), `lembar_verifikasi.md`, catatan, panduan, dan script.
- **Penyaring sengaja tetap memakai teks pypdf.** Ada 15 / 15 / 16 halaman yang lolos hanya karena
  isi yang tak tampak, dan sebagian besar adalah halaman kiri tabel terbelah: halaman berisi label
  baris yang penanda satuannya baru tercetak di halaman kanan (mis. hal 156). Dengan teks tampak,
  halaman label itu tidak akan ikut diparse. Tidak ada halaman yang lolos hanya dengan teks tampak.
- **Aturan mulai sekarang:** untuk menentukan *letak* sesuatu, pakai teks yang tampak
  (`get_text_bounded` dari pypdfium2), bukan teks pypdf. Pengecualiannya hanya penyaring di atas.

---

## Langkah 6 — Periksa hasil parse (3.6) · 1–2 hari  ✅ SELESAI (14-11-2026)

Bagian terpenting minggu ini. Kesalahan parsing tidak memunculkan error — angkanya tetap tampak
wajar, hanya salah.

### a. Inspeksi manual  ✅ dikerjakan pengguna (14-11-2026)

Buka `.md` dan cocokkan dengan PDF asli. Gunakan angka yang **sudah Anda verifikasi di Minggu 1**
sebagai kunci jawaban (lembar verifikasi), misalnya untuk `bbca_2024`:

| Halaman asli | Yang dicari | Harus terbaca |
|---|---|---|
| 703 — Catatan KPMM | Modal Inti (Tier 1), kolom **Bank 2024** | 239.468.855 |
| 703 — Catatan KPMM | Modal Inti (Tier 1), kolom **Konsolidasian 2024** | 255.311.302 |
| 703 — Catatan KPMM | Total ATMR, kolom **Bank 2024** | 848.181.552 |
| 704 — Entitas Induk, aset | Kredit pihak ketiga 2024 | 855.233.239 |
| 705 — Entitas Induk, liabilitas | Simpanan nasabah pihak ketiga 2024 | 1.105.647.994 |
| 21 — tabel rasio resmi | ROE 2024 / CAR 2024 | 24,6% / 29,4% |

Daftar periksa:

- [x] Tabel KPMM: **4 kolom** (Bank 2024, Konsolidasian 2024, Bank 2023, Konsolidasian 2023) —
      urutannya tidak tertukar. Ini tabel paling rawan.
- [x] Tabel laporan posisi keuangan & laba rugi menjadi tabel Markdown yang valid
      *(tapi ada sel berisi dua angka — lihat temuan di bagian b)*
- [x] Kolom tahun tidak tertukar (2024 vs 2023)
- [x] Angka ribuan utuh: `855.233.239`, bukan `855 233 239` atau terpotong
- [x] Angka CKPN di dalam kalimat (narasi baris kredit) ikut terbaca
- [x] Tabel rasio resmi (hal 21) ikut terbaca, termasuk catatan kakinya

### b. Pengecekan otomatis  ✅ (14-11-2026)

```powershell
python scripts/check_parse_output.py
```

Untuk setiap angka di `ground_truth.xlsx`, script membuka hasil Docling di halaman tempat angka
itu diverifikasi di Minggu 1 (lokasinya diambil dari `build_verification_sheet.py`), lalu
memeriksa **letaknya**:

- **angka tabel:** sel di baris berlabel X dan kolom berjudul Y berisi angka itu, persis;
- **angka narasi** (NPL, CKPN): angkanya cocok dengan tahunnya;
- **angka hitungan** (kredit bruto = neto + CKPN; DPK 2022–2024 = pihak berelasi + pihak ketiga):
  komponennya ada di sel yang benar dan jumlahnya sama.

Statusnya ada tiga: **tepat**; **cacat** (nilai benar, tapi strukturnya rusak sehingga agent bisa
salah baca); **salah** (tidak ada di sel yang seharusnya).

**Hasil:**

| Blok | Halaman sumber | Hasil |
|---|---|---|
| A. Ikhtisar (9 item × 4 tahun) | `bbca_2025` hal 15 | 36 tepat |
| B. KPMM Bank | 727 / 703 / 594 | 12 tepat |
| C. KPMM Konsolidasian | 727 / 703 / 594 | 12 tepat |
| D. NPL, kredit bruto, CKPN, DPK (basis bank) | 646, 738, 739 / 701, 704, 705 / 590, 595, 596 | 13 tepat, 3 cacat |

**76 dari 76 angka berada di baris dan kolom yang benar: 73 tepat, 3 cacat struktur.**

Script ini sudah dibuktikan bisa gagal. Dengan kolom Bank ↔ Konsolidasian ditukar dan kolom tahun
Ikhtisar digeser satu, 60 angka langsung terdeteksi **salah**, lengkap dengan letak angka yang
sebenarnya. Satu kesalahan script sendiri sempat muncul dan sudah diperbaiki: titik akhir kalimat
ikut terbaca sebagai bagian angka (`11.795.528.`).

**Temuan — sel berisi dua angka.** Ketiga yang cacat adalah kredit 2022–2024 di Entitas Induk: di
PDF, pihak berelasi dan pihak ketiga berada di dua baris, tapi Docling menggabungkannya menjadi
satu baris dengan sel `7.296.837 855.233.239`. Pola ini tidak hanya di situ:

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Sel nilai berisi ≥ 2 angka | 152 dari 9.107 (1,67%) | 101 dari 9.415 (1,07%) | 111 dari 8.721 (1,27%) |
| Tabel yang mengandungnya | 28 | 21 | 21 |
| Pola 1 — sub-baris "Pihak berelasi / Pihak ketiga" digabung ke baris induk | 4 baris | 5 baris | 0 |
| Pola 2 — lainnya: baris subtotal tanpa label digabung ke baris di atasnya, baris Pilar 3 yang labelnya hilang | 76 baris | 47 baris | 64 baris |
| Di halaman sumber rasio | 576–578, 738 | 540–542, 704 | tidak ada |

Contoh pola 1: kredit di neraca konsolidasian 2024 (hal 540) berisi `7.174.457 861.511.753`, dan
simpanan nasabah (hal 541) berisi `3.235.633 1.117.378.034`. Contoh pola 2: di laba rugi 2024
(hal 542), sel "Surplus revaluasi aset tetap" berisi `238.886 297.244`, padahal 297.244 adalah
subtotal di baris tanpa label di bawahnya.

- **Tidak ada angka yang salah atau tertukar kolom**, tapi agent bisa mengambil angka yang keliru
  dari sel seperti ini.
- `do_cell_matching = False` (saran di GATE 2) **sudah dicoba di hal 704 dan 738, dan tidak
  mengubah apa pun**. Pengaturan Docling dibiarkan.
- **Rencana — Minggu 5:** perbaikan tabel setelah parse, secara deterministik. Pola 1: kalau label
  memuat k sub-label dan sel berisi k angka, pecah menjadi k baris. Pola 2 perlu dipelajari dulu
  sebelum diputuskan. Sampai itu selesai, sel berisi lebih dari satu angka harus ditandai, supaya
  tidak dipakai mentah-mentah oleh Extraction Agent.

---

## Langkah 7 — Mengenali metadata laporan (3.2) · ½–1 hari  ✅ LULUS (14-11-2026)

**File:** `src/ingest/detect_metadata.py` · **uji:** `python scripts/check_detect_metadata.py` → LULUS

```powershell
python -m src.ingest.detect_metadata data\raw\bbca_2024.pdf           # tampilkan hasil + buktinya
python -m src.ingest.detect_metadata data\raw\bbca_2024.pdf --save    # + simpan data\markdown\bbca_2024.metadata.json
```

Masukannya teks pypdf yang sama dengan penyaring, jadi PDF cukup dibaca sekali. Deteksinya sendiri
hanya 0,7–1,1 detik (pembacaan teks 15–23 detik). Semua aturan deterministik (regex + hitungan
halaman), bukan LLM.

| Field | Aturan | BBCA 2023 / 2024 / 2025 |
|---|---|---|
| tahun buku | "31 Desember A dan A−1" di laporan keuangan → A; dicek silang dengan "Laporan Tahunan A" di 30 halaman awal dan dengan nama file | 2023 / 2024 / 2025 (304–338 kemunculan, 100% sepakat) |
| satuan | penanda dominan dari Langkah 1; rinciannya ikut disimpan (`unit_pages`) | jutaan Rp (210–241 hal), miliar Rp di 17–19 hal |
| nama emiten | "PT … Tbk" terbanyak; huruf besar-kecil disatukan, "(Persero)" didukung | PT Bank Central Asia Tbk (910–1.029×) |
| kode saham | "Kode Saham BBCA" (bobot 5); "(IDX: BBCA)" dan "Tbk (BBCA)" (bobot 1) | `bbca` (hal 46 / 46 / 34) |
| sektor | penanda prudensial, lihat di bawah | **bank**, 6 dari 6 penanda |

**7b dikerjakan sebelum bimbingan.** Keputusan #5 hanya menentukan apakah emiten non-bank
*diterima* (dengan label "belum divalidasi") atau *ditolak*. Kedua pilihan membutuhkan hal yang
sama dari modul ini: kode saham sebagai identitas, dan kemampuan membedakan bank dari bukan-bank.
Kalau pembimbing memilih "bank saja", hasil `sector != "bank"` dipakai untuk menolak unggahan —
tidak ada kode yang terbuang.

**Temuan — kata kunci terbanyak menebak salah.** "Piutang pembiayaan konsumen" (dari anak usaha
BCA Finance) muncul di **28–33 halaman**, lebih banyak daripada "kewajiban penyediaan modal
minimum" (14–16 halaman). Penanda asuransi, sekuritas, dan syariah juga muncul, dari BCA Insurance,
BCA Sekuritas, dan BCA Syariah. Karena itu sektor ditentukan dari **penanda regulasi sektor itu
sendiri**:

1. **bank** — ≥ 4 dari 6 penanda prudensial bank (KPMM, ATMR, GWM, LCR, NSFR, LDR), masing-masing
   di ≥ 2 halaman. BBCA: 6 dari 6.
   → **bank syariah** kalau NPF + FDR lebih sering daripada NPL + LDR (BBCA: 1–2 vs 27–32 halaman).
2. **asuransi / pembiayaan / sekuritas** — ≥ 2 penanda: RBC, liabilitas kontrak asuransi, premi,
   klaim / gearing ratio, FAR, piutang pembiayaan / MKBD, perantara pedagang efek, penjamin emisi efek.
3. selain itu **non_financial**.

**Uji:**
- **A.** Ketiga laporan BBCA tepat, tanpa peringatan.
- **B.** 18 kasus teks buatan: sektor lain, bank dengan anak usaha non-bank, laporan berbahasa
  Inggris, nama "(Persero)", tahun/kode yang bertentangan dengan nama file atau sampul, kode ambigu,
  dan hasil scan.
- **C.** Teks BBCA yang dirusak. Tanpa halaman "Kode Saham", kode tetap ditemukan lewat pola
  cadangan. Tanpa 58 halaman berpenanda prudensial, BBCA **tidak lagi** terdeteksi bank, walaupun
  "piutang pembiayaan konsumen" masih ada di 29 halaman.
- Dua mutasi aturan (ambang dinaikkan ke 7 penanda, pasangan syariah/konvensional dibalik)
  langsung membuat script GAGAL.

**Batas:** yang divalidasi hanya deteksi bank, pada BBCA. Penanda sektor lain diambil dari istilah
regulasinya dan baru diuji pada teks buatan — sesuai label "belum divalidasi". Uji pada bank lain
dilakukan di Minggu 8 (8.0b–8.0c, BMRI). Semua tebakan tetap dikonfirmasi pengguna di Telegram
(Minggu 16).

**Untuk Minggu 5 & 16:**
- `ticker` dan `sector` tiap chunk (5.2) diambil dari `data\markdown\<kode>_<tahun>.metadata.json`.
- Alur bot: ekstrak teks sekali → `select_pages` + `detect_metadata` → konfirmasi pengguna → parse.
  Saat ini `parse_report` mengekstrak teks lagi lewat `filter_pages` (15–23 detik); satukan saat
  membangun bot.

---

## Langkah 8 — Catat untuk Bab 4 (3.8) · ½ hari  ✅ SELESAI (15-11-2026)

Bahan subbab Implementasi Data Pipeline: waktu parse, apa yang terbuang oleh penyaring, dan
ketepatan parsing. Ringkasannya juga ada di lembar hasil di bawah.

### a. Waktu parse dengan vs tanpa saringan

```powershell
python scripts/measure_parse_time.py data\raw\bbca_2023.pdf    # satu laporan per proses -> results\parse_timing.json
```

Docling dijalankan dua kali berturut-turut dengan opsi yang sama: sekali pada PDF potongan, sekali
pada PDF utuh. GPU kosong (0%) sebelum dan sesudah setiap tahap.

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Halaman diproses, dengan / tanpa saringan | 261 / 747 (35%) | 262 / 714 (37%) | 230 / 605 (38%) |
| Penyaring (pypdf) | 23,5 s | 14,9 s | 19,0 s |
| Parse **dengan** saringan | 260 s (1,00 s/hal) | 261 s (1,00 s/hal) | 253 s (1,10 s/hal) |
| Parse **tanpa** saringan | 456 s (0,61 s/hal) | 457 s (0,64 s/hal) | 453 s (0,75 s/hal) |
| **Parse lebih cepat** | **1,75×** | **1,75×** | **1,79×** |
| Total (penyaring + muat model + parse) | 289 s vs 457 s | 281 s vs 480 s | 284 s vs 455 s |

- **Penghematannya ±3 menit per laporan (37–41%), bukan 62–65% seperti jumlah halamannya.**
  Halaman yang dibuang ringan bagi Docling (narasi, foto: rata-rata 0,40–0,53 s/hal), sedangkan
  halaman tabel yang dipertahankan berat (1,0–1,1 s/hal).
- Waktu muat model bervariasi (1,6–23 s, tergantung cache disk), jadi yang dibandingkan adalah
  waktu parse. Tahap simpan `.md` tidak ikut diukur.
- **Kenapa diukur di sesi yang sama.** Pada percobaan pertama, sebuah game memakai GPU selama tahap
  "dengan saringan" `bbca_2023`, sehingga saringan tampak *lebih lambat* (0,94×). Hasil itu
  dibuang. Script sekarang mencatat beban GPU sebelum dan sesudah setiap tahap, dan memberi
  PERINGATAN kalau ≥ 10%.
- Angka Langkah 5 (05-11, 1,45–1,75 s/hal) lebih lambat daripada hari ini (1,0–1,1 s/hal) untuk
  halaman yang sama, padahal kondisi GPU saat itu tidak tercatat. **Untuk Bab 4, pakai tabel di atas.**

### b. Yang terbuang oleh penyaring

Tanpa saringan, Docling menemukan 621 / 626 / 614 tabel. Dari jumlah itu, 319 / 324 / 316 berada
di halaman yang dibuang, dan 43 / 38 / 38 di antaranya berisi ≥ 5 angka ribuan.

- **Tidak ada angka ground truth yang hanya ada di halaman terbuang.** Ada 4 angka KPMM yang juga
  muncul di tabel Pilar 3 yang terbuang, tapi semuanya juga ada di Catatan KPMM yang tersaring.
- Isi tabel berangka yang terbuang: SDM (jumlah karyawan, pelatihan), saham (struktur modal saham,
  pemegang saham, kronologis pencatatan), tata kelola (RUPS, rangkap jabatan, remunerasi, biaya
  audit), transaksi afiliasi, dan **12 / 12 / 6 tabel permodalan Pilar 3 serta formulir KPMM-ATMR**.
- **Celah:** halaman Pilar 3 Komposisi Permodalan (CC1) menulis satuannya "dalam **juta** rupiah",
  yang tidak dikenali penyaring (8 / 8 / 1 halaman). Sebagian formulir KPMM-ATMR bahkan tidak punya
  penanda satuan. Perbaikannya di Minggu 8.0b bersama varian BMRI, karena perubahan aturan berarti
  parse ulang.

### c. Ketepatan parsing (dari Langkah 6 dan 9)

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Tabel | 302 | 302 | 298 |
| **Tabel rapi** (tanpa sel berisi ≥ 2 angka, berlabel baris) | **259 (85,8%)** | **266 (88,1%)** | **261 (87,6%)** |
| … di antara tabel berisi ≥ 5 angka | 209/252 (82,9%) | 212/248 (85,5%) | 207/244 (84,8%) |
| Tabel bersel gabungan / tanpa label baris | 28 / 16 | 21 / 16 | 21 / 16 |
| Warning "sel dibuang" TableFormer | 10 | 10 | 18 |

- **76/76 angka ground truth berada di baris dan kolom yang benar** (73 tepat, 3 cacat struktur).
- Docling vs pdfplumber (10 halaman): 9 tepat + 1 cacat, lawan 0–2.
- "Tabel rapi" didefinisikan dari dua cacat yang bisa diperiksa otomatis; kolom tertukar tidak
  ditemukan sama sekali (Langkah 6). Warning sel dibuang tidak dihitung, karena pemetaannya ke
  tabel ambigu dan audit Langkah 5 menunjukkan tidak ada angka yang hilang.

### d. Deteksi metadata (Langkah 7)

3 dari 3 laporan tepat (kode saham, nama, tahun buku, satuan), sektor bank dengan 6/6 penanda,
waktu deteksi 0,7–1,1 detik.

---

## Langkah 9 — Opsional: pembanding pdfplumber (3.9)  ✅ SELESAI (14-11-2026)

```powershell
python scripts/compare_pdfplumber.py      # hasil juga di results\parser_comparison.json
```

Ada 10 halaman `bbca_2024`: rasio resmi (21), tabel Pilar 3 terbelah (156–157), neraca dan laba
rugi konsolidasian (540–542), NPL (701), KPMM (703), Entitas Induk (704–705). Docling tidak
dijalankan ulang; datanya dari hasil Langkah 5. pdfplumber 0.11.10 ditambahkan ke requirements,
tapi hanya sebagai pembanding, bukan bagian pipeline.

| | Docling | pdfplumber (garis) | pdfplumber (teks) |
|---|---|---|---|
| Tabel ditemukan | 10 (1 per halaman) | 11, **hanya di hal 21, 156, 157** | 10 (1 per halaman) |
| Angka tampak yang masuk tabel | 692/700 (99%) | 34/700 (5%) | 678/700 (97%) |
| Pecahan angka di sel | 0 | 0 | **146** |
| Sel berisi ≥ 2 angka | 30 dari 662 | 0 dari 34 | 0 dari 824 |
| 10 angka terverifikasi: baris **dan** kolom benar | **9 tepat, 1 cacat** | 0 | 2 |
| 10 angka terverifikasi: utuh di baris yang benar | 10 | 0 | 7 |
| Waktu per halaman | 1,75 s (GPU, seluruh tata letak) | 0,24 s (CPU) | 0,38 s (CPU) |

- **Strategi garis** (bawaan pdfplumber) tidak menemukan satu tabel pun di halaman laporan
  keuangan (540–542, 701–705), karena tabel keuangan BCA tidak bergaris vertikal.
- **Strategi teks** membaca hampir semua angka, tapi memotong sel di tengah kata dan angka:
  `255.311.302` jadi `255.3 | 11.302`, dan judul "2024" jadi `202 | 4`. Di tabel KPMM, semua angka
  kolom Konsolidasian terpotong, dan tidak ada kolom yang bisa dikenali sebagai "2024 Bank". Di
  tabel rasio, baris judul tahun tidak ikut masuk tabel.
- **Satu keunggulan pdfplumber (teks):** di hal 704, baris "Pihak ketiga" kredit terbaca terpisah,
  padahal Docling menggabungkannya (temuan sel gabungan, Langkah 6). Perbaikan sel gabungan Docling
  tetap dikerjakan di Minggu 5.
- Harness dibuat seadil mungkin: label dicocokkan tanpa spasi, dan kolom dipilih dari judul yang
  cocok sekaligus berisi angka. Kegagalan pdfplumber di atas tetap terjadi. Satu kesalahan harness
  sempat merugikan Docling (label baris kredit memuat angka CKPN, sehingga ikut terbuang) dan
  sudah diperbaiki.

**Kesimpulan untuk Bab 4:** pdfplumber 4–7× lebih cepat per halaman, tapi struktur tabelnya tidak
bisa dipakai tanpa aturan khusus per tabel. Docling dipilih, dan biaya waktunya ditekan dengan
penyaring halaman (Langkah 8).

---

## Dampak ke Minggu 5

Roadmap Minggu 5 merencanakan pemotongan teks dari file `.md`. Kalau dipotong dari `.md` biasa,
**nomor halaman hilang**, padahal Extraction Agent wajib menyebut sumber halaman setiap angka.
Jalan keluarnya sudah tersedia di Docling yang terpasang: potong dari `.json` — lewat
`export_to_markdown(page_no=...)` per halaman, atau `HybridChunker` dari docling-core — lalu
ubah nomor halaman potongan ke halaman asli dengan peta halaman dari Langkah 2.

**Tabel lebar yang terbelah dua halaman** (ditemukan 05-11-2026). Tabel LI1 di `bbca_2024`
tercetak melintasi dua halaman: hal 156 berisi label baris + kolom a–b, hal 157 berisi kolom c–g
**tanpa label baris**. Docling membacanya sebagai dua tabel terpisah (39×3 dan 38×5). Semua
angkanya ada, tapi potongan dari hal 157 berisi angka yang tidak jelas milik baris apa. Audit
menemukan **16 tabel tanpa label baris di tiap laporan**:

| Laporan | Halaman |
|---|---|
| `bbca_2023` | 157, 159, 185, 187, 189, 191, 203, 210–211, 223, 227, 229, 231, 233, 237 |
| `bbca_2024` | 155, 157, 183, 185, 187, 189, 201, 208–209, 221, 225, 227, 229, 231, 235 |
| `bbca_2025` | 110, 112, 130, 132, 134, 136, 148, 155–156, 168, 172, 174, 176, 178, 182 |

Tidak satu pun berada di halaman sumber rasio yang tercatat. Tapi sebagian memuat angka yang sama
dengan sumber rasio (hal 155 `bbca_2024` memuat Total Modal & ATMR konsolidasian), sehingga bisa
ikut terambil saat retrieval. Di Minggu 5: gabungkan dengan tabel halaman kirinya, atau tandai
supaya tidak dipakai sebagai sumber angka.

> **Koreksi 15-11-2026 (Minggu 5, Langkah 2):** definisi audit di atas ("< 20% baris angka
> berhuruf") keliru di 5 tabel per laporan, sehingga daftar ini **tidak lengkap**. Hasil cek
> visual dengan render PDF:
> - **salah tandai:** tabel CR5 hal 210–211 / 208–209 / 155–156 adalah tabel utuh. Label barisnya
>   "Bobot Risiko" (`< 40%`, `75%`), yang tidak memuat huruf.
> - **terlewat:**
>   - bagian kanan CR4/CR5: hal 207, 209 / 205, 207 / 152, 154. Judul kolomnya dilebur ke baris
>     data, sehingga baris itu terhitung "berhuruf".
>   - CCR3 kolom f–l: hal 213 / 211 / 158.
>   - `bbca_2023` saja: sekuritisasi kolom j–q, hal 215.
>
> Daftar yang benar adalah **18 / 17 / 17 tabel**, dengan ciri geometri: kotak tabelnya menempel
> tepi kiri kertas. Rinciannya ada di `PANDUAN_MINGGU5.md` Langkah 2. Angka "tanpa label baris
> 16" di tabel ringkasan bagian c tetap dibiarkan, sebagai hasil audit Minggu 3 apa adanya.

**Blok teks lintas halaman** (ditemukan 05-11-2026). Docling kadang menggabungkan teks dari dua
halaman menjadi satu blok: 83 / 3 / 0 blok. Contohnya catatan kaki hal 262 `bbca_2024` menyatu
dengan paragraf pembuka NPL di hal 263, dan di `.md` seluruhnya muncul di bawah penanda hal 262.
Di Minggu 5, **baca semua `prov` tiap blok, bukan hanya `prov[0]`** — kalau tidak, paragraf itu
dikutip dari halaman yang salah.

---

## Gerbang (GATE 2)

- [x] Ketujuh kelompok halaman penting tertangkap penyaring di ketiga laporan (30-10-2026)
- [x] Ketiga laporan BBCA terparse; `.json`, `.md`, `.meta.json` tersimpan dan di-backup
      *(terparse & tersimpan 05-11-2026; `data\markdown\` di-backup ke Google Drive 14-11-2026 oleh pengguna)*
- [x] Tabel KPMM, laporan posisi keuangan, laba rugi, Entitas Induk, dan rasio resmi terbaca
      benar — kolom tidak tertukar *(14-11-2026: 76/76 angka di sel yang benar; 3 di sel berisi dua
      angka → perbaikan pasca-parse di Minggu 5)*
- [x] Waktu parse tercatat (05-11-2026)
- [x] Ketiga laporan terdeteksi sebagai bank (14-11-2026, 6/6 penanda; `check_detect_metadata.py`
      LULUS). Bimbingan tetap perlu mengesahkan keputusan #5 — lihat Langkah 7.

Kalau tabel rusak: coba `do_cell_matching = False` di `table_structure_options`; kalau tetap
rusak, ekstrak tabel kunci secara manual ke CSV sebagai cadangan — sah, asal dicatat di
Batasan.

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `CUDA out of memory` | GPU dipakai proses lain (mis. sesi BGE-M3 masih terbuka) | tutup proses itu, jalankan ulang; terakhir, sementara set `DOCLING_DEVICE = "cpu"` di `config.py` (lambat) |
| VRAM tidak turun setelah parse (ratusan MB tertinggal) | Docling diimpor **di dalam fungsi** — *traceback* impor opsional menahan converter | impor Docling di level modul, seperti di `parse_pdf.py` |
| Hasil parse lama terus dipakai | cache: hash, opsi, dan versi sama | `--force` |
| Parse sangat lambat | berjalan di CPU, atau OCR menyala | pastikan log Docling menyebut `cuda`; pastikan `do_ocr = False` |
| Angka ada di PDF tapi tidak ada di `.md` | halamannya tidak tersaring | cek Langkah 1 untuk halaman itu |
| Angka ada di teks pypdf, tapi tidak di hasil Docling halaman itu; atau nomor halaman meleset satu | pypdf juga membaca teks di luar area halaman yang tampak (hal 156 memuat kolom c–g yang baru tampil di hal 157; hal 593 `bbca_2025` memuat angka KPMM yang baru tampil di hal 594) | bandingkan dengan teks tampak (`get_text_bounded` dari pypdfium2) atau tampilan PDF, dan cek halaman sebelahnya |
| Teks tampak di PDF, tapi tidak ada di blok Docling halaman itu | blok lintas halaman: teksnya digabung ke blok yang `prov[0]`-nya di halaman sebelumnya | baca semua `prov` blok; cari juga di bawah penanda halaman sebelumnya di `.md` |
| Log `... dropped from the table` | TableFormer membuang sel yang tidak cocok dengan baris/kolom mana pun; status tetap `success` | cari tabelnya dari ukuran grid di pesan (tersimpan di `warnings` pada `.meta.json`), lalu periksa apakah yang hilang angka atau hanya kata |
| Nomor halaman di hasil tidak cocok dengan PDF | memakai nomor PDF potongan | pakai peta halaman dari Langkah 2 |
| Kolom tabel KPMM tertukar | TableFormer salah membaca header bertingkat | catat; coba `do_cell_matching = False`; cadangan: CSV manual |
| `UnicodeEncodeError` saat mencetak | console Windows cp1252 | `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| Semua paket "tidak ditemukan" | venv tidak aktif | `.venv\Scripts\Activate.ps1` |

---

## Lembar hasil — isi sambil jalan

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Halaman asli | 747 | 714 | 605 |
| Halaman tersaring | 261 (35%) | 262 (37%) | 230 (38%) |
| Satuan dominan | jutaan Rp | jutaan Rp | jutaan Rp |
| Ketujuh kelompok tertangkap? | ✅ | ✅ | ✅ |
| Waktu parse 20 halaman (detik) | — | 36,7 (bagian depan); 40,2 (lap. keuangan) | — |
| Waktu parse penuh (menit), 05-11, kondisi GPU tak tercatat | 6,3 (total 8,2) | 7,7 (total 10,1) | 6,5 (total 8,1) |
| **Parse dengan / tanpa saringan (s), 15-11, GPU kosong** | **260 / 456 (1,75×)** | **261 / 457 (1,75×)** | **253 / 453 (1,79×)** |
| Jumlah tabel terbaca | 302 | 302 | 298 |
| Tabel rapi | 259 (85,8%) | 266 (88,1%) | 261 (87,6%) |
| Tabel berangka di halaman terbuang / angka ground truth yang hilang | 43 / 0 | 38 / 0 | 38 / 0 |
| Metadata terdeteksi (kode, tahun, satuan, sektor) | ✅ bbca, 2023, jutaan, bank | ✅ bbca, 2024, jutaan, bank | ✅ bbca, 2025, jutaan, bank |
| Angka ditemukan (dari 76) — dikelompokkan per laporan sumber | 20/20 (2 cacat struktur) | 10/10 (1 cacat struktur) | 46/46 |
| Tabel KPMM kolom benar? | ✅ | ✅ | ✅ |
| Catatan | 10 warning, 83 blok lintas halaman | 10 warning, 3 blok lintas halaman | 18 warning; KPMM & NPL dikoreksi ke hal 594 & 590 |
