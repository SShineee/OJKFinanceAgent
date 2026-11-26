# Panduan Rinci Minggu 8 — Bank Uji (BMRI), GATE 8, & Mulai Dataset Evaluasi

Minggu ini punya **dua tujuan besar** yang sama pentingnya:

1. **Memasukkan bank uji (Bank Mandiri / `bmri`) ke pustaka dan membuktikan generalisasi sistem (GATE 8).**
   Ini pertama kalinya pipeline ingest, chunking, indexing, dan hybrid retrieval menghadapi laporan
   tahunan di luar BBCA. Ditambah **1 laporan emiten non-bank** (mis. `tlkm`, 1 tahun) untuk
   menguji deteksi sektor non-bank → profil umum (*belum divalidasi*).
2. **Memulai dataset evaluasi — jangan ditunda (risiko R4).**
   - **Ground truth rasio BMRI (`8.5`):** 6 rasio × 3 tahun diverifikasi manual seperti Minggu 1,
     dipakai untuk uji retrieval BMRI, GATE 4 (Minggu 9), dan Skenario 2 (Minggu 19).
   - **Dataset 30 Q&A RAGAS (`eval/datasets/ragas_qa.jsonl`, `8.1`–`8.4`):** mulai dicicil **3
     pertanyaan per hari** sejak minggu ini supaya tidak menumpuk di Minggu 17.

> **GATE 8:** saringan halaman & deteksi sektor bekerja pada BMRI (plus 1 laporan non-bank
> terdeteksi bukan-bank), ketiga laporan BMRI terindeks utuh, dan **nol kontaminasi** antar bank
> pada uji 10 query per bank.

Perkiraan kerja: **5–7 hari** (sebagian waktu menunggu unduhan PDF dan Docling ~25 menit untuk
3 laporan BMRI). Semua kode dijalankan dari venv (`(.venv)` harus muncul di prompt) pada branch
**`dev`** (jangan langsung ke `main`).

---

## Status gerbang

- **Minggu 7 selesai** (26-11-2026): `hybrid_retrieve`, `eval/retrieval_eval.py`, dan
  `scripts/check_retrieval.py` **LULUS**; **GATE 3 LULUS** (Hit@5 hybrid + perluasan **13/15 =
  86,7%**, Hit@1 **60%**, MRR@5 **0,702**).
- Git aktif di branch **`dev`** (`origin/dev`), `main` tetap utuh.
- Minggu 8 **tidak tertahan bimbingan** secara teknis.
- ⚠️ **Bimbingan 1.6 masih tertunda.** Bawa 6 keputusan Minggu 1 + Keputusan 7.B ke pembimbing
  sebelum masuk Minggu 9.

> **Aturan disiplin data uji (risiko R10 & R11).** BMRI adalah **bank uji**. Kalau format BMRI
> memunculkan kegagalan pada pipeline ingest (mis. varian penanda satuan, tabel dwibahasa, label
> bahasa Inggris), perbaikan **boleh dilakukan asalkan generik** dan **dicatat untuk Bab 4**
> (`8.0e`). **Dilarang** menyesuaikan prompt Extraction Agent (Minggu 9) ke letak halaman, nomor
> Catatan, atau kekhasan isi BMRI — klaim utama Skenario 2 bertumpu pada BMRI.

---

## Keputusan yang perlu ditetapkan saat memeriksa BMRI

Tiga keputusan ini bergantung pada hasil inspeksi PDF BMRI di Langkah 1 (`inspect_pdf.py`):

### Keputusan 8.A — Kenaikan `RULE_VERSION = 3` di `page_filter.py`

Dari audit 3.8 (15-11-2026), `UNIT_MARKERS` belum mengenali `"dalam juta rupiah"` (tanpa `-an`),
sehingga BBCA kehilangan 8 / 8 / 1 halaman Pilar 3 Komposisi Permodalan (CC1) — 0 angka ground
truth yang hilang.

- **Aturan:** tunggu hasil Langkah 1–2 pada BMRI terlebih dahulu. Kumpulkan **semua** varian
  penanda satuan yang dibutuhkan (`"dalam juta rupiah"` + varian BMRI bila ada) dalam **satu**
  perubahan `RULE_VERSION = 3`, supaya BBCA tidak perlu di-parse ulang berkali-kali.
- **Konsekuensi kalau `RULE_VERSION` dinaikkan:** parse ulang ketiga laporan BBCA (±15 menit
  GPU) lalu jalankan ulang rantai pemeriksaan BBCA (`check_page_filter.py` → `check_chunks.py` →
  `check_index.py` → `eval.retrieval_eval` → `check_retrieval.py`) untuk membuktikan tidak ada
  regresi dan angka Bab 4 tetap konsisten.

### Keputusan 8.B — Bila laporan BMRI dwibahasa atau LK terpisah (risiko R13)

| Temuan `inspect_pdf.py` pada BMRI | Dampak & penanganan generik |
|---|---|
| **Normal** (LK menyatu di Laporan Tahunan, satuan jutaan/miliar Rp) | Langsung lanjut `page_filter` → `add_document()`. |
| **Laporan dwibahasa** (Indonesia + Inggris di halaman yang sama atau berdampingan) | Cek: (1) apakah `UNIT_MARKERS` sudah menangkap keduanya; (2) apakah `SUB_LABEL` di `src/ingest/fix_tables.py` perlu varian Inggris (`Related parties\|Third parties`); (3) apakah tabel tercetak ganda sehingga jumlah chunk membengkak (catat untuk Bab 4). |
| **Laporan Keuangan terbit terpisah** dari Laporan Tahunan | Saringan pada Laporan Tahunan hanya lolos puluhan halaman. Unduh juga file Laporan Keuangan Auditan BMRI, lalu putuskan apakah keduanya digabung sebelum ingest atau pipeline mendukung 2 PDF per `(ticker, year)` — berdampak ke desain unggah Telegram Minggu 16. |
| **Hasil scan** (rata-rata < 200 karakter/halaman) | Tidak bisa disaring dengan `pypdf`; Docling butuh OCR (±3× lebih lama). Cari dulu PDF digital asli dari situs *Investor Relations* Bank Mandiri sebelum mengaktifkan OCR. |

### Keputusan 8.C — File ground truth BMRI terpisah dari BBCA (disarankan)

`data/ground_truth.xlsx` sudah terverifikasi manual 76/76 dan dirujuk langsung oleh
`check_parse_output.py`, `check_chunks.py`, `check_index.py`, dan `eval/retrieval_queries.py`.

- **Saran:** **jangan menimpa `data/ground_truth.xlsx`**. Simpan ground truth BMRI di
  `data/ground_truth_bmri.xlsx` (dan lembar verifikasinya di `docs/lembar_verifikasi_bmri.md`).
  Dengan begitu seluruh script verifikasi BBCA tetap utuh tanpa risiko merusak rujukan sel.

---

## Langkah 0 — Persiapan · 10 menit

Pastikan pustaka BBCA utuh, berada di branch `dev`, dan ruang disk serta GPU siap:

```powershell
git status                                 # harus di branch dev, working tree bersih
python scripts\check_index.py --quick      # indeks BBCA utuh -> LULUS
python scripts\check_retrieval.py --quick  # retrieval BBCA utuh -> LULUS
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv
```

Perkiraan ruang disk tambahan untuk 3 laporan BMRI: ±250–400 MB (PDF mentah + `.json`/`.md` +
`.jsonl` + ChromaDB).

---

## Langkah 1 — Unduh & inspeksi PDF BMRI + 1 emiten non-bank (8.0a) · 1 jam

Langkah unduhan rinci yang dulu disiapkan di `docs/PANDUAN_MINGGU2.md` Langkah 12 dijalankan
sekarang.

### a. Unduh file ke `data\raw\`

1. **Bank uji wajib — Bank Mandiri (`bmri`), 3 tahun:**
   - Sumber: **idx.co.id** → Perusahaan Tercatat → Laporan Keuangan & Tahunan → cari **BMRI**, atau
     halaman *Investor Relations* Bank Mandiri (`bankmandiri.co.id`).
   - Pastikan yang diunduh **Laporan Tahunan (*Annual Report*)**, **bukan** Laporan Keberlanjutan
     (*Sustainability Report*).
   - Simpan dengan pola nama `<kode>_<tahun>.pdf`:
     ```
     data\raw\bmri_2023.pdf
     data\raw\bmri_2024.pdf
     data\raw\bmri_2025.pdf
     ```
   - *(Opsional — BBRI dilepas dulu sesuai risiko R12, kecuali waktu sangat longgar.)*
2. **Emiten non-bank (uji deteksi sektor 8.0c), cukup 1 tahun:**
   - Contoh: Telkom Indonesia (`tlkm_2024.pdf`) atau Astra International (`asii_2024.pdf`).
   - Simpan di `data\raw\tlkm_2024.pdf` (tidak dimasukkan ke Chroma permanen — hanya untuk
     menguji `detect_metadata.py`).

### b. Inspeksi otomatis

```powershell
python scripts\inspect_pdf.py
```

### c. Periksa outputnya

Perhatikan 6 hal utama pada setiap PDF BMRI (catat di **Lembar hasil** dan lengkapi juga tabel
bank uji di `docs/PANDUAN_MINGGU2.md` baris 454):

| Baris output `inspect_pdf.py` | Normal (seperti BBCA) | Tindakan kalau berbeda |
|---|---|---|
| `Ukuran (MB)` | 12–56 MB | Catat untuk risiko R18 (batas unduhan bot Telegram 20 MB). |
| `Jenis PDF` | `TEXT-BASED` | Kalau `SCAN`, cari versi digital asli sebelum mengaktifkan OCR. |
| `Penanda tabel keuangan` | ±200–350 halaman | Kalau hanya puluhan → LK kemungkinan **terbit terpisah** (Keputusan 8.B). |
| `satuan: jutaan / miliar / Dolar AS` | satu satuan jelas mendominasi | Catat satuan dominan; cek apakah muncul `"dalam juta rupiah"` atau frasa lain. |
| `KPMM / CAR / ATMR` & `Lap. Entitas Induk` | ada, masing-masing beberapa halaman | Wajib ada untuk 6 rasio SEOJK (CAR, ROE, NPL, LDR). |
| `Fn rasio 'induk perusahaan saja'` | ada di sekitar tabel Rasio Keuangan | Pastikan basis rasio resmi BMRI sama (SEOJK No.9/SEOJK.03/2020). |

> **Ingat temuan 05-11-2026:** nomor halaman dari `inspect_pdf.py` memakai teks `pypdf` yang
> kadang meleset 1 halaman karena lapisan teks tersembunyi. Untuk menentukan lokasi pasti suatu
> angka di Langkah 6, selalu verifikasi secara visual di PDF atau dengan `pypdfium2`
> (`get_text_bounded`).

---

## Langkah 2 — Uji penyaring halaman pada BMRI & perbaikan generik (8.0b, 8.0e) · ½ hari

```powershell
python -m src.ingest.page_filter data\raw\bmri_2023.pdf data\raw\bmri_2024.pdf data\raw\bmri_2025.pdf
```

### Yang harus dicek per laporan BMRI

Buka PDF di 7 kelompok halaman penting dan pastikan nomor halaman aslinya **ada** di daftar
`halaman lolos` hasil `page_filter`:

1. Ikhtisar Data Keuangan + Tabel Rasio Keuangan resmi
2. Laporan Posisi Keuangan Konsolidasian (Neraca)
3. Laporan Laba Rugi Konsolidasian
4. Catatan KPMM (Modal Inti Tier 1, Total Modal, ATMR — kolom Bank & Konsolidasian)
5. Catatan NPL / kualitas kredit (nominal kredit bermasalah KL+D+M)
6. Laporan Posisi Keuangan Entitas Induk — sisi Aset (kredit neto & CKPN)
7. Laporan Posisi Keuangan Entitas Induk — sisi Liabilitas (simpanan nasabah / DPK)

### Jika ada halaman penting yang terlewat (8.0e)

- Cari tahu **mengapa** terlewat (mis. penanda satuan ditulis `"dalam juta rupiah"`, `"in million
  rupiah"`, atau tabel rasio hanya menyebut singkatan `"CAR"`, `"NPL"`, `"ROA"` tanpa nama
  panjangnya).
- Perbaiki aturan di `src/ingest/page_filter.py` secara **generik** (bukan menuliskan nomor
  halaman atau nama bank) bersama celah `"dalam juta rupiah"` dari 3.8, lalu naikkan
  `RULE_VERSION = 3`.
- Catat setiap perubahan aturan dan alasannya di **Catatan perbaikan generik (8.0e)** di lembar
  hasil bawah untuk Bab 4.
- Jika `RULE_VERSION` naik: perbarui `EXPECTED_TOTAL` di `scripts/check_page_filter.py`, parse
  ulang BBCA, lalu jalankan `check_chunks.py`, `check_index.py`, `eval.retrieval_eval`, dan
  `check_retrieval.py` agar seluruh pustaka memakai versi aturan yang seragam.

---

## Langkah 3 — Uji deteksi metadata & sektor: BMRI + non-bank (8.0c) · ½ hari

```powershell
python -m src.ingest.detect_metadata data\raw\bmri_2023.pdf data\raw\bmri_2024.pdf data\raw\bmri_2025.pdf
python -m src.ingest.detect_metadata data\raw\tlkm_2024.pdf   # ganti sesuai file non-bank yang diunduh
```

Kriteria lolos:

| Laporan | `ticker` | `year` | `sector` | `validated` | Peringatan |
|---|---|---|---|---|---|
| `bmri_2023.pdf` | `bmri` | `2023` | `bank` (≥ 4/6 penanda) | `True` | 0 peringatan tak wajar |
| `bmri_2024.pdf` | `bmri` | `2024` | `bank` (≥ 4/6 penanda) | `True` | 0 peringatan tak wajar |
| `bmri_2025.pdf` | `bmri` | `2025` | `bank` (≥ 4/6 penanda) | `True` | 0 peringatan tak wajar |
| `tlkm_2024.pdf` *(non-bank)* | `tlkm` | `2024` | `non_financial` | `False` (*belum divalidasi*) | 0 peringatan tak wajar |

Hal rawan yang perlu diperhatikan khusus pada BMRI:

- **Nama `(Persero)`:** Bank Mandiri bernama `PT Bank Mandiri (Persero) Tbk` — pola `COMPANY` di
  `detect_metadata.py` sudah disiapkan dan diuji sintetis, tetapi ini pertama kalinya diuji pada
  PDF asli.
- **Anak usaha syariah (BSI / Bank Syariah Indonesia):** BMRI mengonsolidasi anak usaha syariah.
  Periksa bukti `syariah X vs konvensional Y hal` — pastikan konvensional (NPL + LDR) lebih sering
  dari syariah (NPF + FDR) sehingga BMRI terdeteksi `bank`, **bukan** `islamic_bank`.
- **Kode saham:** cek apakah `"Kode Saham BMRI"` / `"(IDX: BMRI)"` tertangkap tanpa ambigu dengan
  kode entitas anak (mis. `BRIS`, `MTEL`, dst.).

Jika ada perbaikan generik pada `detect_metadata.py`, jalankan ulang
`python scripts\check_detect_metadata.py` untuk memastikan 3 laporan BBCA + 18 kasus sintetis +
uji negatif tetap **LULUS**.

---

## Langkah 4 — Masukkan BMRI ke pustaka lewat `add_document()` (8.0d) · ±30–40 menit

Pastikan GPU sedang kosong (`nvidia-smi`), lalu masukkan ketiga laporan BMRI memakai pintu masuk
resmi sistem — sekaligus menguji seluruh alur `identifikasi → parse → potong → indeks` pada
laporan sungguhan di luar BBCA:

```powershell
python -m src.ingest.pipeline data\raw\bmri_2023.pdf
python -m src.ingest.pipeline data\raw\bmri_2024.pdf
python -m src.ingest.pipeline data\raw\bmri_2025.pdf
```

*(Jalankan satu per proses supaya VRAM bersih di antara laporan, sama seperti praktik Minggu 3.)*

### Yang wajib dicek setelah ketiganya masuk

1. **Peringatan dari `chunk.py` (`data\chunks\bmri_*.chunks.meta.json`):**
   - **`split_pieces_without_header` harus 0.** Jika > 0, ada tabel BMRI yang dipecah per kolom
     (temuan Minggu 5) — periksa tabelnya!
   - **`mixed_pages`** dan **`unit_conflicts`** — cek apakah ada halaman campur miliar/juta.
   - **`merged_cells`** & **`unlabeled_tables`** — bandingkan proporsinya dengan BBCA. Jika BMRI
     memakai label bahasa Inggris `"Related parties"` / `"Third parties"` pada sel gabungan,
     pertimbangkan perluasan generik `SUB_LABEL` di `src/ingest/fix_tables.py` (8.0e).
2. **Inspeksi manual cepat pada `.md` & chunk kunci BMRI (`bmri_2024` atau ketiganya):**
   ```powershell
   python -m src.ingest.chunk data\markdown\bmri_2024.json --page <hal_kpmm>
   ```
   Pastikan kolom Bank vs Konsolidasian di tabel KPMM, Neraca, Laba Rugi, Entitas Induk, dan Rasio
   Resmi tidak tertukar dan satuannya (`million_idr` / `billion_idr`) benar.
3. **Verifikasi isi koleksi Chroma:**
   ```powershell
   python -c "from src.retrieval import index; print(index.indexed())"
   ```
   Harus memuat **6 entri**: `bbca` (2023, 2024, 2025) dan `bmri` (2023, 2024, 2025).
4. **Backup ke Google Drive:** salin `data\raw\bmri_*.pdf`, `data\markdown\bmri_*`, dan
   `data\chunks\bmri_*` ke Google Drive (diabaikan git).

---

## Langkah 5 — Uji kontaminasi antar bank & verifikasi GATE 8 (8.0d) · ½ hari

**File yang dibuat:** `scripts/check_contamination.py` → `results/check_contamination.json`

Tujuan: membuktikan secara otomatis bahwa tidak ada satu pun angka BBCA yang pernah muncul saat
menganalisis BMRI, dan sebaliknya (risiko R9).

### Rancangan pengujian

- **A. Kelengkapan pustaka:** `index.indexed()` memuat `bbca` (2023–2025) dan `bmri` (2023–2025);
  BM25 untuk keenam laporan berhasil dibangun dan jumlah dokumennya sama dengan Chroma.
- **B. 10 query generik per bank (total 20 panggilan `hybrid_retrieve`):**
  Query sengaja **tidak menyebut nama bank** (mis. `"Berapa modal inti tier 1 bank tahun 2024?"`,
  `"Berapa CAR bank tahun 2025?"`, `"Berapa rasio NPL bruto tahun 2023?"`, `"Bagaimana tren laba
  bersih?"` dengan `year=None`, dst.), sehingga isolasi 100% diuji pada parameter `ticker`:
  - semua chunk untuk `ticker="bbca"` harus ber-`ticker == "bbca"`, `chunk_id` diawali `"bbca_"`,
    dan `doc_id` milik BBCA (**0 chunk BMRI**);
  - semua chunk untuk `ticker="bmri"` harus ber-`ticker == "bmri"`, `chunk_id` diawali `"bmri_"`,
    dan `doc_id` milik BMRI (**0 chunk BBCA**);
  - uji juga `dense_search` dan `sparse_search` secara terpisah untuk kedua bank.
- **C. Regresi BBCA:** jalankan ulang `python scripts\check_retrieval.py` — pastikan setelah BMRI
  masuk koleksi ChromaDB yang sama, **GATE 3 BBCA tetap LULUS 13/15** tanpa degradasi.
- **D. Uji negatif (wajib GAGAL kalau pagar dilepas):**
  Lakukan query generik ke Chroma **tanpa filter `ticker`** (`where={"year": 2024}`) untuk ke-10
  query → buktikan bahwa **chunk kedua bank benar-benar bercampur** di top-5 tanpa pagar `ticker`,
  sehingga membuktikan pemeriksa kontaminasi benar-benar efektif.

> Setelah Langkah 1–5 lulus semua → **GATE 8 LULUS.**

---

## Langkah 6 — Ground truth rasio BMRI + uji retrieval BMRI (8.5) · 1–2 hari

Ulangi disiplin validasi Minggu 1 pada BMRI agar Skenario 2 (Minggu 19) dan GATE 4 (Minggu 9)
punya acuan sekuat BBCA.

### a. Ekstrak & verifikasi angka mentah BMRI

1. **Periksa footnote tabel Rasio Keuangan resmi BMRI** (2023, 2024, 2025):
   - Cek apakah basisnya *"induk perusahaan saja (Bank Only)"* sesuai SEOJK No.9/SEOJK.03/2020.
   - Cek apakah ROE memakai rata-rata Modal Tier 1, ROA memakai rata-rata total aset, NIM memakai
     rata-rata aset produktif, NPL bruto = KL+D+M / total kredit bruto.
   - Catat perbedaan definisi atau penyajian apa pun dibanding BBCA (bahan Bab 4!).
2. **Kumpulkan 15 item angka mentah untuk tahun 2022–2025** (sama dengan blok A–D di
   `scripts/build_ground_truth.py`, semua dinormalisasi ke **miliar Rupiah**):
   - Blok A (Ikhtisar): Total Aset, Total Aset Produktif, Total Kredit, DPK, Total Ekuitas,
     Pendapatan Bunga Bersih, Laba Sebelum Pajak, Laba Bersih, Laba Bersih atribusi pemilik induk.
   - Blok B & C (Catatan KPMM, kolom Bank & Konsolidasian): Modal Inti (Tier 1), Total Modal,
     Total ATMR.
   - Blok D (Basis Bank — Entitas Induk + Catatan NPL): Kredit Bermasalah nominal (KL+D+M),
     Kredit yang Diberikan Bruto (neto + CKPN), CKPN Kredit, DPK Bank (Simpanan nasabah).
   - Ditambah **6 rasio resmi** BMRI (2023–2025), utamakan 2 desimal dari Catatan bila tersedia
     (CAR di Catatan KPMM, NPL di Catatan NPL).
3. **Bangun file & validasi formula:**
   - Tambahkan dukungan `--ticker bmri` (atau modul data terpisah) untuk menghasilkan:
     - `data/ground_truth_bmri.xlsx` (Keputusan 8.C);
     - `docs/lembar_verifikasi_bmri.md`;
     - laporan MAPE 6 rasio BMRI (target sama: **MAPE < 5%** dengan formula SEOJK yang sama).
4. **Verifikasi manual 100% angka** terhadap halaman PDF asli BMRI memakai
   `docs/lembar_verifikasi_bmri.md`. Jangan pernah memakai angka bacaan mesin tanpa cek visual.
5. **Cek keterbacaan di chunk BMRI:** pastikan angka ground truth BMRI benar-benar terbaca di
   `data\chunks\bmri_*.jsonl` pada halaman dan `unit` yang benar.

### b. Uji retrieval BMRI (bekal dari Minggu 7)

Buat **5–10 query uji BMRI** di `eval/datasets/retrieval_queries_bmri.jsonl` (format sama persis
dengan `retrieval_queries.jsonl`, merujuk `data/ground_truth_bmri.xlsx`, campur query bersingkatan
dan biasa, dikunci dengan SHA-256 sebelum dijalankan):

```powershell
python -m eval.retrieval_eval --dataset eval\datasets\retrieval_queries_bmri.jsonl --out-prefix retrieval_eval_bmri
```

Tujuannya: mengukur apakah daftar `BANK_TERMS` (18 kelompok dari Minggu 7) dan `hybrid_retrieve`
tetap bekerja baik pada bank yang belum pernah dilihat, **tanpa** menyetel daftar istilah dari
query uji BMRI. Hasilnya masuk `results/retrieval_eval_bmri.json` & `.csv` (bahan Bab 4).

---

## Langkah 7 — Mulai dataset evaluasi RAGAS 30 Q&A (8.1–8.4) · cicil 3/hari

**File:** `eval/datasets/ragas_qa.jsonl` (+ validator skema ringan `eval/ragas_dataset.py`)

> **Koreksi proposal (ROADMAP Minggu 8):** Sub-bab 3.6.1 menyebut RAGAS *"tanpa memerlukan ground
> truth"*. Itu tidak akurat — metrik **`context_recall` membutuhkan `reference` answer** yang
> diverifikasi dari PDF. Catat ini untuk revisi Bab 3 (tugas 22.6).

### Format per baris `.jsonl`

```json
{"id": "qa01", "ticker": "bbca", "year": 2024, "type": "faktual", "question": "Berapa laba bersih BCA tahun 2024?", "reference": "Laba bersih konsolidasian BCA tahun 2024 sebesar Rp 54.851 miliar (atau Rp 54.851.274 juta pada Laporan Laba Rugi Konsolidasian).", "ref_page": [15, 542], "source_file": "bbca_2024.pdf"}
```

Catatan field:
- `id`: `qa01` .. `qa30`.
- `ticker`: `"bbca"` atau `"bmri"`.
- `year`: satu `int` (`2024`) untuk 1-hop / multi-hop / kontekstual, atau daftar `[2023, 2024, 2025]` untuk komparatif lintas tahun.
- `type`: salah satu dari `"faktual"`, `"multi_hop"`, `"komparatif"`, `"kontekstual"`.
- `question`: pertanyaan alami pengguna dalam bahasa Indonesia.
- `reference`: **wajib ditulis dari PDF**, memuat angka, satuan, dan konteks secukupnya (jangan sekadar satu angka mentah tanpa satuan; jangan pula salin-tempel 1 halaman penuh).
- `ref_page`: nomor halaman **indeks PDF asli** (integer atau list integer) tempat jawaban diverifikasi.
- `source_file`: nama file PDF sumber (atau list file untuk pertanyaan komparatif lintas laporan).

### Target komposisi 30 pertanyaan (20 BBCA + 10 BMRI)

| Tipe | Total | BBCA | BMRI | Contoh pola pertanyaan |
|---|---:|---:|---:|---|
| `faktual` (1-hop) | **12** | 8 | 4 | "Berapa total aset / laba bersih / DPK / ATMR Bank X tahun 2024?" |
| `multi_hop` | **8** | 5 | 3 | "Berapa ROE / CAR / NPL bruto / LDR Bank X tahun 2024 dan apa komponennya?" |
| `komparatif` (antar tahun) | **6** | 4 | 2 | "Bagaimana tren NPL / laba bersih / DPK Bank X periode 2023–2025?" *(periode final 2023–2025, bukan 2022–2024)* |
| `kontekstual` (kualitatif) | **4** | 3 | 1 | "Apa penyebab utama kenaikan pendapatan bunga bersih / beban operasional Bank X tahun 2024?" |
| **Jumlah** | **30** | **20** | **10** | |

### Strategi cicilan supaya tidak molor

- **Target akhir Minggu 8:** minimal **12–15 pertanyaan** sudah terisi, diverifikasi langsung dari
  PDF (mis. 9–10 BBCA + 3–5 BMRI), dan lolos validasi skema.
- **Minggu 9–16:** tambah **3 pertanyaan/hari** (atau 3–5 pertanyaan per minggu) sehingga 30/30
  selesai jauh sebelum Minggu 17.
- **Jangan pakai output LLM untuk menulis `reference`** — seluruh `reference` harus bersumber dari
  PDF asli agar bebas dari halusinasi dan bias model.
- Cek bahwa setiap `ref_page` pada pertanyaan faktual/multi-hop memang lolos `page_filter` (ada di
  `data/chunks/*.jsonl`), atau catat secara jujur bila ada pertanyaan kontekstual yang halamannya
  terbuang oleh penyaring (itu bahan evaluasi *context recall* yang nyata!).

---

## Langkah 8 — Catat, verifikasi, & commit ke branch `dev` · ½ jam

1. Isi **Lembar hasil** di bawah (plus tabel bank uji di `docs/PANDUAN_MINGGU2.md`).
2. Centang butir **Gerbang (GATE 8)** di bawah dan tugas Minggu 8 di `docs/ROADMAP.md`.
3. Pastikan `.env` dan seluruh `data/raw/*.pdf`, `data/markdown/*`, `data/chunks/*`, `chroma_db/`
   tetap diabaikan (`git status`), lalu commit & push ke branch **`dev`**.

---

## Dampak ke Minggu 9–19 dan Bab 4

- **Bab 4 (4.2 & 4.3 — Generalisasi ke bank uji):**
  - Tabel perbandingan BBCA vs BMRI: ukuran PDF, porsi halaman tersaring, waktu ingest
    `add_document()`, jumlah chunk, `split_pieces_without_header`, dan catatan perbaikan generik
    (`8.0e`).
  - Bukti **0% kontaminasi antar bank** (`results/check_contamination.json`) beserta uji negatifnya.
  - Tabel Hit@5 retrieval BMRI (`results/retrieval_eval_bmri.json`) dibanding BBCA — menunjukkan
    apakah `BANK_TERMS` dan RRF berlaku lintas bank.
- **Minggu 9 (Extraction Agent — GATE 4):**
  - Prompt tetap dirancang memakai BBCA saja; **BMRI dipakai untuk menguji GATE 4** (target ≥ 90%
    pada BBCA **dan** ≥ 80% pada BMRI) menggunakan `data/ground_truth_bmri.xlsx` dari Langkah 6.
- **Minggu 11 (Financial Analyst Agent):**
  - Jika ada perbedaan kecil penyajian rasio BMRI (mis. satuan atau istilah tabel), profil `bank`
    di `src/ratio_profiles.py` tetap satu profil SEOJK yang generik.
- **Minggu 16 (Bot Telegram — risiko R18):**
  - Ukuran file `bmri_*.pdf` yang dicatat di Langkah 1 memastikan kebutuhan Local Bot API Server
    via Docker (bila > 20 MB).
- **Minggu 17 & 19 (Skenario 1 & 2):**
  - `eval/datasets/ragas_qa.jsonl` langsung menjadi masukan Skenario 1 (RAGAS);
    `data/ground_truth_bmri.xlsx` menjadi acuan utama Skenario 2 (MAPE BMRI dilaporkan terpisah
    dari BBCA).

---

## Gerbang (kriteria lolos Minggu 8 — GATE 8)

- [ ] **8.0a** `bmri_2023.pdf`, `bmri_2024.pdf`, `bmri_2025.pdf` ✅ diunduh & diinspeksi (26-11-2026); ⏸ tinggal 1 PDF non-bank (mis. `tlkm_2024.pdf`)
- [x] **8.0b** Saringan halaman menangkap 7 kelompok halaman penting di ketiga laporan BMRI (`RULE_VERSION = 3`, 26-11-2026; BBCA di-parse ulang & seluruh regresi LULUS)
- [ ] **8.0c** Deteksi sektor: ketiga laporan BMRI → `bank` (`validated=True`, 6/6 penanda, 0 peringatan) ✅; ⏸ tinggal 1 laporan non-bank → bukan-bank (`validated=False`)
- [x] **8.0d** Ketiga laporan BMRI terindeks via `add_document()` (`1.219 / 1.358 / 1.430` chunk, total koleksi `5.638` chunk) dan **`scripts/check_contamination.py` LULUS (nol kontaminasi 20/20 panggilan / 120 chunk + uji negatif tertangkap 10/10)** *(⏸ backup manual ke Google Drive)*
- [x] **8.0e** Seluruh perbaikan generik karena format BMRI (`page_filter.py` v3, `chunk.py`, `detect_metadata.py`) terdokumentasi di lembar hasil; regresi BBCA (`check_parse_output`, `check_fix_tables`, `check_chunks`, `check_index`, `check_retrieval`) tetap **LULUS**
- [x] **8.5** Ground truth rasio BMRI (`data/ground_truth_bmri.xlsx`, 6/6 rasio lolos MAPE < 5%, `scripts/check_bmri_chunks.py` LULUS) + verifikasi visual 30 halaman render PDF asli (`docs/lembar_verifikasi_bmri.md`, `v 26/11/26`: 109/110 cocok, 1 koreksi penjumlahan 30 juta Rp pada `Aset Produktif Inti Bank 2023`) + uji retrieval BMRI (`results/retrieval_eval_bmri.json`: Hybrid+ **8/10 = 80,0%**, Hit@1 **80%**, MRR@5 **0,800** tanpa penyetelan `BANK_TERMS`) *(26-11-2026)*
- [x] **8.1–8.4** `eval/datasets/ragas_qa.jsonl` sudah dimulai — **15/30 pasang terverifikasi dari PDF** (10 BBCA + 5 BMRI; 6 `faktual`, 4 `multi_hop`, 3 `komparatif` 2023–2025, 2 `kontekstual`), lolos validator skema + cakupan chunk 15/15 lewat `eval/ragas_dataset.py` (26-11-2026; sisa 15 pasang dicicil Minggu 9–16)

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `inspect_pdf.py`: penanda tabel keuangan BMRI hanya puluhan halaman | Laporan Keuangan Auditan terbit sebagai file terpisah dari Laporan Tahunan (R13) | Unduh juga file LK Auditan BMRI; lihat Keputusan 8.B |
| BMRI terdeteksi `islamic_bank` oleh `detect_metadata.py` | Anak usaha syariah (BSI) membuat jumlah halaman NPF+FDR melampaui NPL+LDR | Cek output `evidence["sector"]`; perbaiki aturan secara generik (mis. hitung di bagian rasio utama / entitas induk) dan uji regresi di `check_detect_metadata.py` |
| BMRI `ticker` terdeteksi kode anak usaha atau `ambigu` | Kode anak usaha (`BRIS`, dll.) ikut cocok pola cadangan | Cek halaman bukti di `evidence["ticker"]`; pastikan pola identitas utama (`Kode Saham`) punya bobot cukup tanpa hardcode `BMRI` |
| Halaman penting BMRI terlewat `page_filter.py` | Penanda satuan memakai frasa berbeda (mis. `"dalam juta rupiah"` / `"dalam jutaan rp"`) atau tabel rasio memakai singkatan | Tambah varian generik ke `UNIT_MARKERS` / `RATIO_TERMS`, naikkan `RULE_VERSION = 3`, parse ulang & jalankan regresi BBCA |
| `PERINGATAN: ... potongan tabel tanpa header kolom` saat `add_document` BMRI | Tabel BMRI terlalu lebar (1 baris + header > 1024 token) sehingga `HybridChunker` memecah per kolom | Inspeksi tabel terkait; pertimbangkan `omit_header_on_overflow=True` (catatan `PANDUAN_MINGGU5.md`) |
| `CUDA out of memory` saat `add_document` BMRI | Proses lain memakai GPU, atau BGE-M3 & Docling aktif bersamaan | Jalankan satu laporan per proses; pastikan `nvidia-smi` kosong sebelum mulai |
| Angka di `bmri_*.pdf` meleset 1 halaman dari `inspect_pdf.py` | `pypdf` membaca teks di luar area tampak (temuan 05-11-2026) | Selalu cek tampilan PDF atau `pypdfium2` (`get_text_bounded`) untuk lokasi halaman final |
| `check_contamination.py` menemukan chunk bank lain | Bug filter `where` di Chroma atau salah indeks `ticker` | Cek metadata `ticker` di `bmri_*.metadata.json` dan filter `$and` di `src/retrieval/hybrid.py` |

---

## Lembar hasil — isi sambil jalan

### A. Inventaris & inspeksi BMRI + non-bank (Langkah 1–3)

| Kode | Tahun | Ukuran (MB) | Hal. | Text/Scan | Satuan dominan | Hal. tersaring (%) | Sektor terdeteksi | LK terpisah? | Dwibahasa? |
|---|---|---|---|---|---|---|---|---|---|
| `bmri` | 2023 | 23,8 | 1.514 | Text-based | `million_idr` (543 hal.) | 563 (37%) | `bank` (6/6 penanda, `validated=True`) | Tidak (hal. 1070–1513) | Ya (ID+EN berdampingan di LK) |
| `bmri` | 2024 | 21,1 | 1.726 | Text-based | `million_idr` (616 hal.) | 633 (37%) | `bank` (6/6 penanda, `validated=True`) | Tidak (hal. 1282–1725) | Ya (ID+EN berdampingan di LK) |
| `bmri` | 2025 | 22,9 | 1.467 | Text-based | `million_idr` (579 hal.) | 594 (40%) | `bank` (6/6 penanda, `validated=True`) | Tidak (hal. 951–1466) | Ya (ID+EN berdampingan di LK) |
| *(non-bank)* | *(belum diunggah)* | — | — | — | — | *(tidak diindeks)* | *(menunggu 1 PDF non-bank)* | — | — |

*(Catatan risiko R18: seluruh 3 PDF BMRI > 20 MB — bersama 2 PDF BBCA, 5 dari 6 laporan pustaka melampaui batas unduhan 20 MB Bot API Telegram standar sehingga Local Bot API Server via Docker terkonfirmasi dibutuhkan di Minggu 16.)*

### B. Ingest, chunking, indexing, & kontaminasi (Langkah 4–5)

| | `bmri_2023` | `bmri_2024` | `bmri_2025` |
|---|---|---|---|
| Waktu `add_document()` total (identifikasi / parse / potong / indeks) | 1.296,0 s (68,3 / 1.117,9 / 70,3 / 30,9 s) | 1.856,7 s (59,2 / 1.695,9 / 57,6 / 34,1 s) | 1.069,2 s (31,0 / 963,7 / 27,5 / 35,6 s) |
| Jumlah tabel Docling | 564 | 644 | 531 |
| Chunk diindeks / `excluded` / `merged_cells` | 1.219 / 39 / 83 | 1.358 / 73 / 91 | 1.430 / 12 / 61 |
| Tabel terbelah / potongan tanpa header | 63 / **0** | 71 / **0** | 73 / **0** |
| `data\markdown\bmri_*` & `data\chunks\bmri_*` di-backup ke Google Drive | ⏸ belum (backup manual) | ⏸ belum (backup manual) | ⏸ belum (backup manual) |
| `scripts/check_contamination.py` (20 query + uji negatif) | **LULUS** (26-11-2026, `results/check_contamination.json`): 6/6 laporan (`5.638` chunk, `chroma_db` `101,3 MB`), 20 panggilan `hybrid_retrieve` (120 chunk) → **0 bocor** (`hybrid=0`, `dense=0`, `sparse=0`); uji negatif tanpa filter `ticker` mencampur **10/10 query** (distribusi top-10: `bbca` 53 vs `bmri` 47) | ← | ← |
| Regresi `scripts/check_retrieval.py` (BBCA setelah BMRI masuk) | **LULUS** (26-11-2026): GATE 3 BBCA tetap **13/15 (86,7%)**, MRR@5 **0,658**, Hit@1 **8/15 (53%)**, median latensi `28,5 ms`, 3/3 uji negatif tertangkap; `check_index.py` **LULUS**, `check_chunks.py` **LULUS** (76/76), `check_parse_output.py` **76/76 tepat**, `check_fix_tables.py` **LULUS** | ← | ← |
| **GATE 8** | **LULUS** (saringan, deteksi sektor `bank` 3/3, ingest penuh 3/3, & 0 kontaminasi BBCA↔BMRI; tinggal 1 PDF non-bank untuk melengkapi separuh non-bank 8.0c) | ← | ← |

### C. Validasi rasio BMRI, retrieval BMRI, & progres RAGAS (Langkah 6–7)

| Item | Hasil |
|---|---|
| Formula & MAPE BMRI (CAR / ROA / ROE / NIM / NPL / LDR) | **6/6 lolos target MAPE < 5%** (`results/validate_ratios_bmri.json`, 26-11-2026, basis Bank Only SEOJK No.9/SEOJK.03/2020): **CAR 0,01%** (`Total Modal Bank / ATMR Bank`), **NPL 0,51%** (`NPL nominal Bank / Kredit Bruto Bank`), **LDR 0,69%** (`Kredit Bruto Bank / DPK Bank`), **NIM 1,09%** (`Pend. Bunga Neto Bank / rata-rata Aset Produktif Inti Bank`), **ROA 3,00%** (`Laba Sebelum Pajak Bank / rata-rata Total Aset Bank`), **ROE 4,31%** (`Laba Bersih Bank / rata-rata Tier 1 Bank`). **Temuan kunci lintas bank (Bab 4 & Minggu 11):** (1) **ROA** BMRI mengikuti SEOJK baku (*Laba Sebelum Pajak*) sedangkan BBCA menyimpang di fn9 (*Laba Setelah Pajak*) — memakai rumus BBCA pada BMRI gagal total (MAPE **21,20%–27,09%**); (2) anak usaha syariah (BSI) memecah DPK konsolidasi ke *Simpanan Nasabah + Dana Syirkah Temporer* (LDR konsolidasi tanpa Syirkah meleset 14,99%); (3) BMRI tidak mencetak satu baris *Total Aset Produktif* di Ikhtisar sehingga dihitung dari 5 pos berbunga utama Neraca Entitas Induk; (4) rumus proposal Tabel 2.2 gagal berat pada BMRI (ROA 31,11%, ROE 27,35%). |
| Verifikasi visual `docs/lembar_verifikasi_bmri.md` | ✅ **SELESAI (26-11-2026, `v 26/11/26`)**: seluruh **92 angka mentah + 18 rasio resmi** diverifikasi visual langsung terhadap render gambar ke-**30 halaman PDF asli** (`bmri_2023..2025.pdf`) beserta uji aritmetika 2 item hitungan dan cross-check antar laporan 2023↔2024↔2025. Hasil: **109/110 angka cocok 100%**; ditemukan & diperbaiki **1 koreksi penjumlahan** pada `Aset Produktif Inti Bank 2023` (`1.439.648,229` → `1.439.648,199` miliar, selisih 30 juta Rp = `0,000002%`, tidak mengubah MAPE NIM 1,09%). Seluruh baris di `data/ground_truth_bmri.xlsx` (`1_angka_mentah` & `2_rasio_resmi`) tercentang `v 26/11/26`. **Keterbacaan chunk (`scripts/check_bmri_chunks.py`) LULUS** (`results/check_bmri_chunks.json`): 74/74 angka langsung pada halaman lolos saringan + 26/26 komponen item hitungan + 18/18 rasio resmi terbaca tepat dengan `unit="million_idr"` (`0` hilang/salah unit; 4 halaman tanpa penanda satuan yang dilewati `page_filter` — `bmri_2025` hal. 37 & `bmri_2023` hal. 401/404/405 — seluruh angkanya untuk 2023–2025 terbaca di Neraca Auditan / laporan pembanding). |
| Retrieval BMRI (`eval/retrieval_eval.py`, 10 query): Dense / BM25 / Hybrid (+ perluasan) | **LULUS ambang 80% tanpa penyetelan `BANK_TERMS`** (`results/retrieval_eval_bmri.json` & `.csv`, 26-11-2026; `eval/datasets/retrieval_queries_bmri.jsonl`, 10 query = 5 singkatan + 5 biasa, SHA-256 terkunci `8b0840dc96dd695f6ab0e43ac43b83727991067c69339c651acc8a814e9098c4`): Dense `40% / 60% / 0,500`, Dense+ `40% / 60% / 0,500`, BM25 `50% / 80% / 0,603`, BM25+ `60% / 80% / 0,670`, Hybrid `60% / 70% / 0,633`, **Hybrid+ `Hit@1 80% (8/10) / Hit@5 80% (8/10) / MRR@5 0,800`** (Singkatan 4/5, Biasa 4/5; semua 8 hit berada di peringkat #1). Sensitivitas: `RRF k=10/60/100` identik (`8/10, MRR 0,800`), `cand=5/10/20/30` = `7/8/8/8`; median latensi warm `51,0 ms` (korpus BMRI ~2,5× lebih besar dari BBCA). **Diagnosis 2 query meleset:** `m02` (*laba bersih 2024*, seluruh 6 konfigurasi meleset — BMRI memakai label *"Laba tahun berjalan"* dan MD&A/Induk mendominasi top-5) dan `m08` (*CKPN 2023*, query tidak menyebut *"entitas induk"* sehingga CKPN konsolidasian mendominasi top-5 — masukan langsung bagi query Extraction Agent Minggu 9). Perbaikan generik kecil di `eval/retrieval_queries.py`: pola persen kini juga mencocokkan 2 desimal berekor nol (mis. `20,10%`); regresi `check_retrieval.py` BBCA tetap **LULUS** (13/15). |
| Progres `eval/datasets/ragas_qa.jsonl` (jumlah / 30; sebaran BBCA vs BMRI) | **15/30 pasang — target tahap Minggu 8 tercapai** (`eval/datasets/ragas_qa.jsonl`, SHA-256 `f6949282…b19f`, 26-11-2026): **10 BBCA / 5 BMRI** (`faktual` 4+2=6/12, `multi_hop` 3+1=4/8, `komparatif` 2023–2025 2+1=3/6, `kontekstual` 1+1=2/4). Seluruh `reference` ditulis dari teks tampak PDF asli (`pypdfium2`), tanpa output LLM. Validator `python -m eval.ragas_dataset` **LULUS**: 0 kesalahan skema, **15/15** seluruh `ref_page` lolos `page_filter` dan terindeks di `data/chunks/*.jsonl`. Sisa 15 pasang dicicil Minggu 9–16 (mode `--strict-final` siap untuk cek 30/30). |
| Catatan perbaikan generik (`8.0e`, bahan Bab 4) | **2 perbaikan generik ditemukan saat menguji BMRI (26-11-2026):** (1) `src/ingest/page_filter.py` (`RULE_VERSION = 3`) & `src/ingest/chunk.py`: menambah varian frasa satuan (`dalam juta rupiah`, `dalam rp juta/jutaan`, `in million rupiah`, beserta varian `miliar/miliaran`) — sekaligus menutup celah 3.8 Pilar 3 CC1 BBCA — dan mengubah `RATIO_TERMS` menjadi 7 kelompok sinonim ID/EN + singkatan dalam tanda kurung (CAR/KPMM, NPL, ROA, ROE, NIM, LDR, BOPO) agar tabel rasio berbahasa Indonesia seperti `"Imbal Hasil Aktiva (ROA)"` ikut tersaring. (2) `src/ingest/detect_metadata.py`: memperbaiki `detect_ticker()` yang semula salah mendeteksi `bris` (entitas anak BSI) pada ketiga laporan BMRI karena `(ticker code: BRIS)` & `PT Bank BRIsyariah Tbk. (BRIS)` sementara tabel identitas BMRI 2024–2025 memisahkan label `"Kode Saham"` dan `"BMRI"` lintas kolom; diperbaiki generik dengan (a) `PT ... Tbk (KODE)` hanya berbobot bila cocok dengan nama emiten induk, (b) pola `saham/stock/ticker <KODE>`, dan (c) deteksi kode pada tabel identitas 2 kolom. Tanpa hardcode nama bank/entitas anak/nomor halaman. Regresi BBCA pasca `RULE_VERSION = 3` (`541 / 571 / 519` chunk = `1.631` chunk) seluruhnya LULUS. |
| Catatan umum Minggu 8 | Aturan `fix_tables.py` (Pola 1/2/3 & `unlabeled_tables`) yang dibangun pada BBCA otomatis bekerja pada BMRI (`sub_rows_fixed` 14/6/5, `printed_lines_fixed` 45/35/30, `split_rows_merged` 5/5/2, `unlabeled_tables` 39/73/12) dengan `split_pieces_without_header = 0` di ketiga tahun. Aturan pengaman `mixed_pages` (`unit=None`) juga terpicu tepat sasaran pada halaman BMRI yang sungguh memuat dua tabel bersatuan berbeda (mis. `bmri_2024` hal. 389: Rp Juta & Rp Miliar di halaman yang sama). `scripts/check_index.py` turut diperbarui agar memfilter `ticker` pada koleksi multi-bank dan menyamakan pemisah baris/spasi saat cek temu-diri BGE-M3. |
