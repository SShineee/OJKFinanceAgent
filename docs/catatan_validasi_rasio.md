# Catatan Validasi — Minggu 1 (GATE 1)

Diisi selama Minggu 1. Dokumen ini jadi **lampiran saat bimbingan** dan nanti
jadi bahan Bab 3 (justifikasi pemilihan formula) + Bab 4 (analisis error).

Tanggal mulai: 21-10-2026
Tanggal bimbingan: `____`

---

## 1.1 Keputusan periode data

Proposal bentrok: Batasan hal.5 = **2021–2023**, Sub-bab 3.2 hal.16 = **2023–2025**.

- Periode yang dipilih: **2023, 2024, 2025**
- Alasan:
  - laporan tahunan BCA ketiga tahun itu sudah terkumpul (`data/raw/`)
  - laporan tahun buku 2025 sudah terbit, jadi ini data paling mutakhir
  - sesuai Sub-bab 3.2 → yang direvisi adalah **Batasan hal.5**
  - rasio yang memakai rata-rata saldo (ROE, ROA) butuh saldo akhir 2022 sebagai saldo awal
    2023 — tersedia sebagai angka pembanding di laporan 2023, jadi tidak perlu PDF tambahan
- Disetujui pembimbing: ☐ ya ☐ belum

---

## 1.2 Inventaris PDF

| Tahun | Nama file | Jumlah hal. | Ukuran | Text-based / Scan | Tanggal unduh |
|---|---|---|---|---|---|
| 2023 | `bbca_2023.pdf` | 747 | 55,6 MB | text-based | 21-10-2026 |
| 2024 | `bbca_2024.pdf` | 714 | 12,4 MB | text-based | 21-10-2026 |
| 2025 | `bbca_2025.pdf` | 605 | 37,0 MB | text-based | 21-10-2026 |

Diperiksa dengan `python scripts/inspect_pdf.py`: rata-rata ±3.000 karakter per halaman, jadi
ketiganya text-based dan **Docling tidak perlu OCR**. Nama file diganti dari `bca_*` ke
`bbca_*` (kode saham) pada 27-10-2026.

> Cara cek text-based atau scan: buka PDF, coba seleksi teks. Kalau tidak bisa
> diseleksi → hasil scan → Docling harus jalan OCR → **3x lebih lama**, dan
> estimasi di Minggu 3 harus disesuaikan.

Catatan tambahan:

- **Laporan Keuangan Konsolidasian yang diaudit termuat di dalam Laporan Tahunan** — tidak
  terbit sebagai file terpisah. Satu PDF per tahun sudah cukup.
- Letak bagian penting (indeks halaman PDF, 2023 / 2024 / 2025):
  - Ikhtisar & tabel Rasio Keuangan resmi: 18–19 / 20–21 / 15–16
  - Laporan Posisi Keuangan Konsolidasian: 576 / 540 / 461
  - Catatan KPMM (Tier 1, Total Modal, ATMR): 727 / 703 / 594
  - Laporan Posisi Keuangan Entitas Induk: 738 / 704 / 595
  - *Koreksi 05-11-2026:* KPMM 2025 semula tercatat hal 593 dan NPL 2025 hal 589. Keduanya meleset satu
    halaman karena pencarian pypdf ikut membaca isi di luar area tampak; nilainya tidak berubah.
- Satuan: laporan keuangan dalam **jutaan Rupiah** (±240 halaman bertanda), sedangkan tabel
  Ikhtisar dalam **miliar Rupiah** — konversi wajib saat mengambil angka.
- Ukuran file relevan untuk bot Telegram (keputusan #6): dua dari tiga file > 20 MB, batas
  unduhan bot standar.

---

## 1.3 Verifikasi model Groq — SELESAI

Dijalankan `python scripts/check_groq_models.py`. Hasil: akun hanya punya **11 model**,
dan **tidak ada satu pun Llama generatif**.

| Model kandidat | Status |
|---|---|
| `llama3-70b-8192` (ditulis di proposal) | **TIDAK TERSEDIA** |
| `llama-3.3-70b-versatile` | TIDAK TERSEDIA |
| `openai/gpt-oss-120b` | aktif |
| `openai/gpt-oss-20b` | aktif |
| `qwen/qwen3.8-27b` | aktif |

Sisa daftar bukan model generatif: `whisper-large-v3*` (speech-to-text),
`canopylabs/orpheus-*` (text-to-speech), `meta-llama/llama-prompt-guard-2-*`
dan `openai/gpt-oss-safeguard-20b` (classifier keamanan), `allam-2-7b` (fokus Arab).

### Keputusan

| Peran | Model | Alasan |
|---|---|---|
| Sistem (4 agent + baseline) | `openai/gpt-oss-120b` | open weight (Apache 2.0), gratis, tetap di LPU Groq |
| Cadangan rate limit | `openai/gpt-oss-20b` | |
| LLM judge RAGAS | `gemini-2.5-flash` | **beda penyedia** dengan model sistem, menghindari bias self-preference |

Ketiga justifikasi di proposal Bab 2.2 tetap berlaku: open source, biaya nol,
inferensi cepat via LPU. Yang berubah hanya nama modelnya.

### Temuan tambahan: gpt-oss adalah reasoning model

Saat diuji dengan `max_tokens=10`, `content` keluar **kosong** sementara
`qwen3.8-27b` menjawab normal. Penyebabnya: gpt-oss memakai token untuk
penalaran sebelum mengisi `content`.

Konsekuensi yang sudah ditangani di `src/config.py`:

- `MAX_TOKENS = 4096` — kalau terlalu kecil, jawaban kosong
- `REASONING_EFFORT = "medium"` untuk analisis, `"low"` untuk ekstraksi angka
- Konsumsi token jauh lebih besar → rate limit lebih cepat kena di Minggu 19
- **Latensi didominasi penalaran, bukan orkestrasi** → di Skenario 3 (Minggu 20),
  waktu eksekusi saja tidak cukup; wajib laporkan jumlah token berdampingan

### Checklist revisi

- [x] `src/config.py`
- [ ] Proposal Bab 2.2 — penjelasan pemilihan LLM
- [ ] Proposal Tabel 3.1 — Kebutuhan Sistem
- [ ] Bab 3 — tambahkan alasan judge beda penyedia

## 1.4 Status API key

| Layanan | Status | Dipakai sejak | Catatan |
|---|---|---|---|
| Groq | ☑ aktif | sekarang | `GROQ_API_KEY` di `.env`, terverifikasi lewat `python -m src.config` |
| Google AI Studio | ☑ aktif | Minggu 17 | `GOOGLE_API_KEY`, untuk LLM judge RAGAS (`gemini-2.5-flash`) |
| Tavily | ☐ belum | Minggu 13 | **sengaja ditunda** — tidak ada keputusan metodologis yang bergantung padanya; kalau bermasalah, tool pencarian mudah diganti tanpa menyentuh Bab 3 |

Key disimpan di `.env` (sudah masuk `.gitignore`), nama model di `src/config.py`.

---

## 1.5 Hasil validasi rasio — SELESAI

**Verifikasi manual tuntas.** Seluruh **76 angka** di `data/ground_truth.xlsx`
dicocokkan ke halaman sumbernya lewat `docs/lembar_verifikasi.md`.
**Tidak ada koreksi** — semua angka hasil ekstraksi terbukti benar.

| Tahap | Tanggal | Cakupan |
|---|---|---|
| Verifikasi utama | 22 Okt 2026 | 72 angka — Ikhtisar, KPMM Bank & Konsolidasian, kredit & NPL |
| Verifikasi susulan | 26 Okt 2026 | 4 angka — DPK basis BANK, ditambahkan untuk formula LDR bank/bank |

### Hasil per rasio

| Rasio | Metode Proposal (Tabel 2.2) | Metode OJK (footnote) | Status |
|---|---|---|---|
| CAR | 0,94% (basis konsolidasi) | **0,01%** (basis bank) | sangat akurat |
| ROE | **14,06%** gagal (laba/ekuitas) | **1,08%** (laba/rata² Tier 1) | sangat akurat |
| ROA | 4,65% (saldo akhir) | **1,68%** (rata-rata aset) | sangat akurat |
| NPL | **5,89%** gagal (kredit konsolidasi) | **3,02%** (kredit bruto bank) | akurat |
| LDR | 4,01% (konsolidasi/konsolidasi) | **3,11%** (bank/bank) | akurat |
| NIM | **4,59%** (saldo akhir) | 8,63% gagal (rata-rata) | akurat, dengan caveat |

**6 dari 6 lolos target MAPE < 5%.** Target di proposal tidak perlu diturunkan.

### Pola temuan

Yang menentukan akurasi **bukan rumusnya, tapi basisnya** — bank-only vs
konsolidasian. Terlihat konsisten di empat rasio:

| Rasio | Basis konsolidasi | Basis bank |
|---|---|---|
| ROE | 14,06% (ekuitas) | **1,08%** (Tier 1) |
| NPL | 5,89% (total kredit) | **3,02%** (kredit bruto bank) |
| LDR | 4,01% | **3,11%** |
| CAR | 0,98% | **0,01%** |

Berlaku di **empat** rasio. Semakin dekat basisnya ke definisi resmi
("induk perusahaan saja", fn5), semakin kecil errornya.

**Satu godaan yang ditolak.** Untuk LDR, kombinasi kredit BANK ÷ DPK
konsolidasi memberi MAPE **0,93%** — paling kecil dari semua opsi. Tapi
kombinasi itu **mencampur basis** (pembilang bank, penyebut konsolidasi) dan
tidak bisa dipertahankan saat ditanya. Dipilih yang 3,11% karena konsisten.
Ini contoh bagus untuk Bab 4: *angka paling cocok belum tentu angka yang benar.*

Contoh paling jelas, tahun 2024 punya **tiga** angka "kredit" yang berbeda:
Total Kredit ikhtisar 921.878 | kredit bruto konsolidasian 901.311 |
kredit bruto BANK 894.912. Ketiganya sah, ketiganya di dokumen yang sama,
dan dua di antaranya membuat NPL salah.

### Caveat NIM — harus jujur di Bab 4

Footnote 11 menyebut penyebutnya **rata-rata** aset produktif, tapi secara
empiris **saldo akhir** (4,59%) justru lebih dekat ke angka resmi daripada
rata-rata (8,63%). Dugaan penyebab: pembilang yang tersedia di Ikhtisar
bersifat konsolidasi, sedangkan rasio resmi NIM berbasis bank-only.
Jadi kecocokan 4,59% itu sebagian kebetulan. **Jangan diklaim sebagai formula
yang benar** — sebut sebagai pendekatan terbaik yang tersedia dari data publik.

### Catatan metodologis

Acuan CAR dan NPL memakai angka **2 desimal** dari Catatan (29,44% / 1,86%),
bukan 1 desimal dari Ikhtisar (29,4% / 1,9%). Pembulatan 1 desimal menimbulkan
error semu — CAR tampak 0,12% padahal sebenarnya 0,01%.

### Konsekuensi arsitektur

Modal Tier 1 dan ATMR **tidak ada di Laporan Posisi Keuangan**. Angkanya hanya
di Catatan KPMM di bagian belakang dokumen (hal 727 / 703 / 594), dalam tabel
**4 kolom** (Bank × Konsolidasian × 2 tahun). Artinya:

- Minggu 3–4: Docling wajib memparse sampai Catatan, bukan hanya LK utama
- Minggu 5: chunk yang memuat tabel KPMM harus utuh
- Minggu 9: Tier 1, Total Modal, ATMR masuk daftar uji GATE 4

## 1.6 Keputusan yang dibawa ke bimbingan

> Opsi A/B/C yang disiapkan di awal (menurunkan target MAPE) **tidak jadi
> diperlukan** — validasi menunjukkan 6 dari 6 rasio tercapai di bawah 5%.
> Yang perlu disetujui sekarang adalah enam hal berikut.

### 1. Periode data: 2023, 2024, 2025

Proposal bentrok — Batasan hal.5 menulis 2021–2023, Sub-bab 3.2 menulis 2023–2025.
PDF yang terkumpul 2023–2025, jadi **Batasan hal.5 yang direvisi.**

### 2. Tabel 2.2 direvisi mengikuti footnote OJK

Yang terpenting: **ROE memakai rata-rata Modal Tier 1 basis bank**, bukan ekuitas.
Formula lama menghasilkan MAPE 14,06%; formula OJK 1,08%. Sumbernya footnote 10
di tabel Rasio Keuangan laporan BCA sendiri, bukan asumsi.

| Rasio | Formula final |
|---|---|
| CAR | Total Modal ÷ ATMR, kolom **Bank** (Catatan KPMM) |
| ROA | Laba setelah pajak ÷ **rata-rata** total aset |
| ROE | Laba setelah pajak ÷ **rata-rata Modal Tier 1 Bank** |
| NIM | Pend. bunga bersih ÷ aset produktif (saldo akhir) |
| NPL | Kredit bermasalah ÷ kredit **bruto Bank** |
| LDR | Kredit bruto **Bank** ÷ DPK **Bank** |

### 3. Target MAPE < 5% dipertahankan

Sudah terbukti tercapai pada keenam rasio (0,01%–4,59%). Tidak perlu diturunkan,
dan tidak perlu mengubah rumusan masalah no.3 maupun Tabel 3.2.

### 4. Model LLM: `openai/gpt-oss-120b`

`llama3-70b-8192` yang ditulis di proposal sudah tidak tersedia di Groq, dan tidak
ada Llama generatif lain di akun. Penggantinya tetap open weight (Apache 2.0),
gratis, dan tetap berjalan di LPU Groq — ketiga justifikasi Bab 2.2 utuh.
LLM judge RAGAS memakai `gemini-2.5-flash`, sengaja beda penyedia.

### 5. Ruang lingkup: emiten BEI diterima, divalidasi pada sektor perbankan

Proposal menulis analisis laporan keuangan **BCA**. Sistem yang dibangun menerima laporan
tahunan **emiten BEI** yang diunggah pengguna, menyimpannya ke pustaka, lalu menganalisisnya.

| | Profil rasio | Status |
|---|---|---|
| **Bank** | CAR, ROA, ROE, NIM, NPL, LDR — formula SEOJK | **divalidasi**: BBCA (pengembangan, selesai di 1.5), BMRI (uji) |
| **Non-bank** | profil umum: ROA & ROE saja | diterima, diberi label *belum divalidasi* |

Kenapa hanya perbankan yang divalidasi:

- Rasio bank punya **definisi baku** dari OJK (SEOJK No.9/SEOJK.03/2020) — acuan pembanding
  paling kuat. Rasio emiten non-bank tidak punya definisi baku; tiap perusahaan bisa
  menghitung ROE dengan caranya sendiri.
- Ketiga rumusan masalah (kualitas RAG, akurasi rasio, multi- vs single-agent) tidak
  membahas jumlah sektor. Menambah sektor menambah ±2–3 minggu kerja tanpa membuat satu pun
  rumusan masalah terjawab lebih baik.
- Arsitektur tetap mendukung banyak sektor lewat profil rasio, jadi perluasan ke sektor lain
  menjadi saran penelitian yang konkret.

*(Riwayat: 26-10-2026 bank umum saja → 27-10-2026 sempat diperluas ke bank + non-keuangan →
27-10-2026 final: validasi perbankan saja.)*

Dampak ke proposal:

- **Judul** — tidak lagi menyebut BCA; BCA menjadi studi kasus pengembangan
- **Batasan hal.5** — emiten BEI diterima; akurasi divalidasi pada sektor perbankan
- **Bab 3** — tambahkan deteksi sektor, profil rasio, dan pipeline unggah
  (saring halaman → parse → index)
- **Skenario 2** — MAPE dilaporkan terpisah untuk BBCA (pengembangan) dan BMRI (uji);
  klaim utama didasarkan pada BMRI
- **Saran** — profil & validasi untuk emiten non-keuangan, bank syariah, asuransi, dst.

### 6. Antarmuka: bot Telegram menggantikan Chainlit

Proposal (Tabel 3.1) menyebut Chainlit. Antarmuka diganti menjadi **bot Telegram**
(`python-telegram-bot`).

Yang perlu disampaikan ke pembimbing — dua batasan yang memengaruhi desain:

- **Bot standar hanya bisa menerima file ≤ 20 MB** (FAQ resmi Telegram), sedangkan laporan
  tahunan bank umumnya 30–60 MB (`bbca_2023.pdf` 55,6 MB). Solusinya **Local Bot API Server**
  yang dijalankan lewat Docker, yang menghapus batas unduhan itu. Kalau tidak berhasil
  disiapkan, unggahan dibatasi ≤ 20 MB dan laporan besar dimasukkan lewat script — dicatat
  sebagai keterbatasan.
- **Satu pesan maksimal 4.096 karakter dan tidak bisa menampilkan tabel.** Ringkasan analisis
  dikirim sebagai pesan, laporan lengkap sebagai file, grafik rasio sebagai gambar.

Evaluasi (Skenario 1–3) dijalankan lewat script, bukan lewat Telegram — pergantian antarmuka
tidak memengaruhi hasil pengujian.

---

**Keputusan pembimbing:**

- Tanggal: `____`
- Disetujui / revisi: `____`
- Catatan: `____`

## Status GATE 1

☑ Periode data final — 2023, 2024, 2025
☑ Model LLM final — `openai/gpt-oss-120b` (judge: `gemini-2.5-flash`)
☑ Definisi ground truth rasio final — 6/6 tervalidasi, 76 angka diverifikasi manual
☐ **Disetujui pembimbing** ← satu-satunya yang tersisa

**Boleh lanjut ke Minggu 2 hanya kalau keempatnya tercentang.**

> **Pengecualian (26-10-2026):** Minggu 2 dimulai sebelum bimbingan, karena isinya tidak
> bergantung pada keputusan di atas. **Bimbingan wajib sebelum Minggu 3.**
