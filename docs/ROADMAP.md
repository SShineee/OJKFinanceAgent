# ROADMAP SKRIPSI — Agentic AI Multi-Agent + RAG untuk Analisis Laporan Keuangan Emiten

Fransiskus Harris Berliandu — 103012330401
Durasi: 24 minggu (6 bulan). Centang `[x]` kalau selesai.

> **Ruang lingkup (final 27-10-2026).** Sistem menerima laporan tahunan **emiten BEI** yang
> diunggah pengguna lewat **bot Telegram**, menyimpannya ke pustaka, lalu menganalisisnya.
>
> - **Yang divalidasi (diuji MAPE) hanya sektor perbankan.** BBCA = bank pengembangan
>   (ground truth selesai Minggu 1), BMRI = bank uji (BBRI opsional). Bank uji tidak disentuh
>   sampai evaluasi, supaya MAPE tidak optimistis.
> - **Seluruh pembangunan sistem (Minggu 2–7) memakai PDF BCA saja.** PDF BMRI baru diunduh
>   di **Minggu 8** (keputusan 28-10-2026) — lihat tugas 8.0 dan risiko R11/R13.
> - Emiten **non-bank** tetap bisa diunggah, tapi dianalisis dengan **profil umum** (ROA, ROE)
>   dan diberi label *belum divalidasi*. Profil & validasi sektor lain → saran penelitian.
> - Sektor dikenali saat unggah → memilih profil rasio. Menambah sektor nanti = menambah
>   profil, bukan mengubah kode agent.
> - Identitas emiten = **kode saham** huruf kecil (`bbca`, `bmri`) — sama dengan idx.co.id.
> - Antarmuka **Telegram**, menggantikan Chainlit di proposal. Batasan terpenting: bot standar
>   hanya bisa mengunduh file **≤ 20 MB**, sedangkan laporan tahunan bank umumnya 30–60 MB
>   (`bbca_2023.pdf` 55,6 MB) → perlu **Local Bot API Server** lewat Docker. Lihat Minggu 16 & R18.
>
> Parsing dan indexing menjadi **komponen sistem** yang berjalan setiap ada unggahan.

> **Aturan main:** setiap fase punya **GATE**. Jangan lanjut ke fase berikutnya
> sebelum kriteria GATE terpenuhi. Melewati gate = utang teknis yang baru
> ketahuan di Bab 4 saat sudah tidak ada waktu.

---

# BULAN 1

## Minggu 1 — Keputusan & Validasi Kelayakan

Belum ngoding sama sekali. Minggu ini menentukan apakah target di proposal realistis.

- [x] **1.1** Periode data: **2023, 2024, 2025** (PDF sudah terkumpul di `data/raw/`).
      Proposal bentrok: Batasan hal.5 = 2021–2023, Sub-bab 3.2 hal.16 = 2023–2025 →
      **Batasan hal.5 yang direvisi**, menyesuaikan Sub-bab 3.2.
- [x] **1.2** PDF terkumpul & diinspeksi (`python scripts/inspect_pdf.py`): 747/714/605 halaman,
      ketiganya **text-based** → Docling tidak perlu OCR. Peta halaman per dokumen ada di
      `docs/PANDUAN_MINGGU1.md`.
- [x] **1.3** Model Groq diverifikasi. `llama3-70b-8192` **tidak tersedia**, dan tidak ada
      Llama generatif sama sekali di akun. Diganti ke **`openai/gpt-oss-120b`** (open weight
      Apache 2.0, gratis, tetap LPU Groq) — sudah di `src/config.py`.
      ⚠️ gpt-oss adalah **reasoning model**: `MAX_TOKENS` harus besar (4096), dan latensi
      didominasi token penalaran. Lihat `docs/catatan_validasi_rasio.md` bagian 1.3.
      → Sisa: revisi proposal Bab 2.2 + Tabel 3.1.
- [ ] **1.4** API key — **tidak perlu semua sekarang**:
      - [x] **Groq** — wajib sekarang, sudah ada di `.env`
      - [ ] **Google AI Studio** (`GOOGLE_API_KEY`) — fungsinya baru dipakai Minggu 17,
            tapi **daftar sekarang**: keputusan "judge beda penyedia" akan ditulis ke
            Bab 3 saat bimbingan, jadi pastikan dulu free tier-nya bisa diakses.
      - [ ] **Tavily** (`TAVILY_API_KEY`) — tunda ke Minggu 13. Tidak ada keputusan
            metodologis yang bergantung padanya; kalau bermasalah, tool pencarian
            mudah diganti tanpa menyentuh Bab 3.

### 1.5 — VALIDASI RASIO (tugas terpenting minggu ini)

**SUDAH DIJALANKAN.** `data/ground_truth.xlsx` kini **ter-prefill** dari PDF, dan
`python scripts/validate_ratios.py` sudah menghitung hasilnya. Rincian lengkap +
peta halaman: **`docs/PANDUAN_MINGGU1.md`**.

Hasil — dasar perhitungan diambil dari footnote tabel Rasio Keuangan (`bbca_2025.pdf` hal 16):

| Rasio | Metode Proposal (Tabel 2.2) | Metode OJK (footnote) | Verdict |
|---|---|---|---|
| CAR | 0,94% (basis konsolidasi) | **0,01%** (basis bank) | lolos |
| ROE | **14,06%** gagal (laba/ekuitas) | **1,08%** (laba/rata² Tier 1) | lolos setelah formula diperbaiki |
| ROA | 4,65% (saldo akhir) | **1,68%** (rata-rata aset) | lolos |
| NPL | **5,89%** gagal (kredit konsolidasi) | **3,02%** (kredit bruto bank) | lolos |
| LDR | 4,01% (konsolidasi) | **3,11%** (bank/bank) | lolos |
| NIM | **4,59%** (saldo akhir) | 8,63% gagal (rata-rata) | lolos — lihat caveat di panduan |

**Semua 6 lolos MAPE < 5%. Target di proposal tidak perlu diturunkan.**
Pola konsisten: yang menentukan bukan rumusnya, tapi **basisnya** (bank vs konsolidasian).
Temuan terpenting: **fn5** menyatakan rasio resmi berbasis *"induk perusahaan saja"*
(bank), dan **fn10** menyatakan ROE memakai **rata-rata Modal Tier 1** — bukan ekuitas.

- [x] **Verifikasi manual selesai.** Seluruh **76 angka** dicocokkan ke halaman sumbernya lewat
      `docs/lembar_verifikasi.md` — 72 angka pada 22-10-2026, 4 angka DPK Bank pada 26-10-2026.
      **Tidak ada koreksi.**
- [x] `docs/catatan_validasi_rasio.md` bagian 1.5 terisi
- [ ] Review sheet `4_kesimpulan` (usulan keputusan sudah di-prefill, tinggal disetujui/diedit)

- [ ] **1.6** Bawa ke bimbingan — **6 keputusan**, rinciannya di `docs/catatan_validasi_rasio.md` bagian 1.6:
      1. Periode data **2023–2025**; Batasan hal.5 direvisi.
      2. **Tabel 2.2 direvisi** mengikuti footnote OJK (ROE pakai rata-rata Modal Tier 1).
      3. Target MAPE < 5% **dipertahankan** — sudah terbukti tercapai 6/6.
      4. Model **`gpt-oss-120b`** menggantikan Llama 3 70B (tidak lagi tersedia di Groq).
      5. Ruang lingkup: **semua emiten BEI** diterima; **divalidasi pada perbankan** (BBCA, BMRI).
      6. Antarmuka **Telegram** menggantikan Chainlit.

> **GATE 1:** Bimbingan dengan Dr. Kurniawan Nur Ramadhani & Febryanti Sthevanie. Keputusan periode data,
> model LLM, dan definisi ground truth rasio **harus final** sebelum minggu 2.
>
> **Pengecualian (26-10-2026):** Minggu 2 dimulai **sebelum** bimbingan atas keputusan
> sendiri. Aman karena isi Minggu 2 (environment, git, dependensi, uji tool calling) tidak
> bergantung pada keputusan-keputusan di atas.
> **Bimbingan wajib sebelum Minggu 3** — desain pipeline ingest multi-emiten bergantung
> pada keputusan #5. Kalau pembimbing menolak perluasan ruang lingkup, Minggu 3
> kembali ke rancangan BCA saja.
>
> **Status:** validasi sudah dijalankan (`python scripts/validate_ratios.py`) —
> **6 dari 6 rasio lolos MAPE < 5%** asalkan formula mengikuti footnote OJK, bukan
> Tabel 2.2 proposal. Target di proposal **tidak perlu diturunkan**. Temuan terbesar:
> ROE harus pakai **rata-rata Modal Tier 1**, bukan ekuitas (formula lama → MAPE 14,06%).
> Rincian + langkah yang tersisa: `docs/PANDUAN_MINGGU1.md`.

---

## Minggu 2 — Setup Environment & Struktur Proyek

**Langkah rinci, perintah, dan output yang diharapkan: `docs/PANDUAN_MINGGU2.md`.**
Laptop sudah dicek 26-10-2026: GPU **RTX 3060 6 GB**, Python 3.11/3.12/3.13 dan `uv` sudah
terpasang, execution policy & long paths aman.

- [ ] **2.1** ⏸ *ditunda* — `git init` + buktikan `.env` dan PDF diabaikan (`git check-ignore -v`).
      `.gitignore` sudah ada sejak Minggu 1.
- [x] **2.2** **Python 3.12.13** + venv via `uv venv --python 3.12.13 .venv`.
      *Perbaikan 26-10-2026:* venv pertama memakai 3.12.0 (bawaan sistem) dan harus dibuat ulang —
      `multiprocess` butuh `RLock._recursion_count` yang belum ada di 3.12.0.
      *Koreksi:* roadmap awal menulis "3.11, jangan 3.12" — sudah tidak berlaku. Dicek ke PyPI:
      semua paket proyek mendukung ≥ 3.10.
- [x] **2.3** Struktur folder (dibuat 26-10-2026, `__init__.py` + `.gitkeep` sudah ada):
      ```
      c:\TugasAkhir\
      ├── data\raw\ markdown\ chunks\ ground_truth.xlsx
      ├── src\
      │   ├── config.py          # path, konstanta, nama model
      │   ├── ingest\  parse_pdf.py  chunk.py  build_index.py
      │   ├── retrieval\ hybrid.py  rrf.py
      │   ├── agents\  state.py extraction.py analyst.py market.py reporting.py graph.py
      │   ├── baseline\ single_agent.py
      │   └── telegram_bot.py    # antarmuka Telegram
      ├── eval\ ragas_eval.py  ratio_eval.py  comparison_eval.py  datasets\
      ├── results\               # CSV + grafik hasil
      └── docs\
      ```
- [x] **2.4** Pasang paket, **urutannya penting** *(selesai 28-10-2026)*:
      1. ✅ *(26-10-2026: `2.14.1+cu126`, RTX 3060 terdeteksi)* PyTorch **CUDA dulu, terpisah**: `uv pip install torch --index-url https://download.pytorch.org/whl/cu126`
         — kalau ikut terpasang lewat paket lain, yang terambil versi CPU dan GPU tidak terpakai
      2. sisanya: `uv pip install -r requirements.in` (22 paket langsung, sudah dibuat).
         `langchain-community` **dikunci 0.4.1** — ragas 0.4.3 rusak di 0.4.2 (lihat R14)
      3. **cek ulang** torch masih `+cu126` dan `cuda True`
      4. kunci versi: `uv pip freeze | Out-File -Encoding ascii requirements.txt`
         (**bukan** `>` — di PowerShell 5.1 itu menghasilkan file UTF-16)
- [x] **2.4b** *(28-10-2026: SIAP; BGE-M3 di `cuda:0`, 2,12 GB VRAM — catat untuk Minggu 3: Docling juga
      memakai GPU 6 GB yang sama)* `python scripts/check_environment.py` → **ENVIRONMENT SIAP**, lalu uji BGE-M3 di GPU
      → `(1, 1024) cuda:0` (sekalian mengunduh model 2,2 GB supaya Minggu 3 tidak tertahan).
- [x] **2.5** `.env` + `src/config.py` sudah dibuat lebih awal (bersama tugas 1.3).
      Berisi nama model, path, parameter retrieval, dan `get_llm()`/`get_judge()`.
      Cek: `python -m src.config`. Key ada di `.env` (sudah di-.gitignore).
- [x] **2.5b** *(28-10-2026, venv sungguhan: LULUS 5/5, ±2.500 token & 5,3 s per tugas)*
      Uji **tool calling**: `python scripts/check_tool_calling.py`. Script sudah dibuat dan
      sudah dijalankan di environment sementara (26-10-2026) → **LULUS 5/5**, ±2.700 token
      per tugas. Yang perlu Anda lakukan: menjalankannya sekali lagi di venv sungguhan.
      Tiga temuan dari tes ini:
      - `get_llm()` sempat rusak (`reasoning_effort` ditolak lewat `model_kwargs`) — **sudah diperbaiki**
      - **nama tool harus bahasa Inggris** — nama `hitung` membuat model memanggil `hitungan`
        (tool yang tidak ada) 15 dari 15 kali; `calculator` lulus 5/5. Berlaku untuk semua agent.
      - format angka Indonesia salah dibaca 5/5 (`239.468,855` → `239.468855`) — urusan Minggu 9
- [ ] **2.6** ⏸ *ditunda* — commit awal. ✅ Backup `data/raw/` di luar git sudah (28-10-2026).
- ~~**2.7** Unduh & periksa PDF BMRI~~ — **dipindah ke Minggu 8 (tugas 8.0a)**, keputusan
  28-10-2026: seluruh pembangunan memakai PDF BCA saja.
- ~~**2.8** Validasi profil rasio non-keuangan pada TLKM~~ — **dibatalkan 27-10-2026**: validasi
  dibatasi ke sektor perbankan. Sektor non-keuangan masuk saran penelitian (22.3).

**Kriteria lolos:** `check_environment.py` → SIAP, torch `+cu126 True` setelah semua paket
terpasang, BGE-M3 di `cuda:0`, `check_tool_calling.py` LULUS, `requirements.txt` ter-commit,
`.env` tidak ada di `git ls-files`.
Checklist lengkap di panduan.

---

## Minggu 3–4 — Pipeline Ingest: Saring → Parse → Simpan

Parsing sekarang **komponen sistem**, bukan pekerjaan sekali jalan. Masalah utamanya
waktu: Docling pada 700 halaman di CPU bisa berjam-jam, dan pengguna yang mengunggah
tidak mungkin menunggu selama itu. Solusinya **dua tahap**: saring halaman dulu dengan
ekstraksi teks cepat, baru Docling memproses halaman yang relevan saja.

Terukur di BCA: dengan aturan saringan di 3.1, hanya **230–262 dari 605–747 halaman**
(35–38%) yang perlu diproses Docling.

**Langkah rinci, contoh kode yang sudah diuji, dan daftar periksa: `docs/PANDUAN_MINGGU3.md`.**
Bimbingan belum dilakukan (28-10-2026). Bagian emiten & sektor di 3.2 dan uji 3.7 semula menunggu
keputusan #5; dikerjakan 14-11-2026 dengan rancangan yang berlaku untuk kedua kemungkinan
keputusan (kode saham + bank vs bukan-bank dibutuhkan di keduanya).

- [x] **3.1** `src/ingest/page_filter.py` — pypdf (13–21 detik per dokumen) · ✅ 30-10-2026,
      `scripts/check_page_filter.py` LULUS: ketujuh kelompok tertangkap, 261/262/230 halaman,
      satuan jutaan Rp. Ditambah `normalize()` (istilah terpotong ganti baris tetap cocok):
      - ambil halaman bertanda satuan laporan keuangan: "dalam **jutaan** rupiah" (BBCA), tapi juga
        "dalam **miliar** rupiah", "ribuan dolar AS", dan versi Inggrisnya — **satuan berbeda
        antar emiten** (lihat R15). Penanda yang ditemukan sekaligus memberi tahu satuan laporan.
      - **plus halaman yang memuat ≥ 3 istilah rasio** ("capital adequacy ratio", "return on
        equity", "loan to deposit ratio", dst.). Tanpa aturan ini **tabel rasio resmi terlewat**
        di laporan 2023 (hal 19) dan 2024 (hal 21) — isinya persen, jadi tidak punya penanda
        satuan (diuji 28-10-2026). Dengan aturan ini ketujuh kelompok halaman penting tertangkap.
      - **jangan** pakai pencocokan kata kunci biasa — header navigasi mencetak judul bagian
        di hampir setiap halaman (terbukti: "Ikhtisar Data Keuangan" cocok di 257 halaman)
      - output: daftar nomor halaman
- [x] **3.2** `src/ingest/detect_metadata.py` — tebak **nama emiten, kode saham, tahun buku,
      satuan, dan sektor** — **bukan oleh LLM**, supaya bisa diuji dan diulang. Semua tebakan
      dikonfirmasi pengguna di UI (Minggu 16). ✅ 14-11-2026, `scripts/check_detect_metadata.py`
      LULUS (3 laporan BBCA + 18 kasus buatan + uji negatif); hasil di `data/markdown/<kode>_<tahun>.metadata.json`.
      - ⚠️ *Koreksi rancangan:* "piutang pembiayaan konsumen → pembiayaan" **salah menebak BCA** —
        istilah itu muncul di 28–33 halaman (anak usaha BCA Finance), lebih banyak dari KPMM (14–16).
        Sektor kini ditentukan dari **penanda prudensial sektor itu sendiri**: bank = ≥ 4 dari 6
        (KPMM, ATMR, GWM, LCR, NSFR, LDR) di ≥ 2 halaman; syariah kalau NPF+FDR > NPL+LDR;
        asuransi/pembiayaan/sekuritas dari RBC, gearing ratio/FAR, MKBD, dst.
      - satuan tidak seragam dalam satu laporan (jutaan Rp di LK, miliar Rp di Ikhtisar, 17–19 hal)
        → rinciannya ikut disimpan (`unit_pages`); normalisasi tetap di 9.3
- [x] **3.3** `src/ingest/parse_pdf.py` · ✅ 31-10-2026, diuji pada 3 halaman (tabel rasio resmi
      & KPMM terbaca benar); cache diuji 5 skenario; kebocoran VRAM 407 MB ditemukan & diperbaiki
      (Docling diimpor di level modul) — rincian di PANDUAN_MINGGU3 Langkah 3:
      - [x] Docling hanya menerima **rentang halaman berurutan** → halaman tersaring dikumpulkan
        jadi PDF potongan (pypdf) + **peta halaman potongan → asli** disimpan. Tanpa peta itu,
        semua nomor halaman yang dikutip sistem salah. ✅ 30-10-2026: `src/ingest/subset_pdf.py`
        (`build_subset`, `PageMap`); `scripts/check_subset_pdf.py` LULUS — setiap halaman
        potongan identik dengan aslinya (teks, ukuran, rotasi, piksel), PDF potongan 2,7–3,5 MB
      - **`do_ocr = False`** (bawaannya menyala; PDF BCA berbentuk teks), TableFormer ACCURATE, GPU
      - kunci cache = **hash SHA-256 file PDF** → unggahan ulang file yang sama tidak diparse lagi
      - simpan ke `data/markdown/`: `<kode>_<tahun>.json` (dokumen Docling lengkap — sumber
        kebenaran, termasuk posisi halaman), `.md` (untuk dibaca), `.meta.json` (hash, peta
        halaman, satuan, waktu proses)
- [x] **3.4** Ukur waktu pada **20 halaman**, lalu estimasi untuk halaman tersaring. ✅ 05-11-2026:
      1,83–2,01 detik/halaman → perkiraan 7–9 menit per laporan, sekitar 25 menit ketiganya.
      Target kasar: satu laporan selesai dalam hitungan **menit**, bukan jam. Kalau masih
      terlalu lama → pertimbangkan GPU, atau saring lebih ketat.
- [x] **3.5** Isi awal pustaka: parse **3 laporan BBCA**. Backup hasil `.md` ke cloud.
      ✅ Terparse 05-11-2026 (753 halaman, 902 tabel, 26,4 menit); audit: 33.162 angka tampak, 0
      kurang. Rujukan KPMM & NPL 2025 dikoreksi ke hal 594 & 590 (dicek visual 14-11-2026); nilai
      tetap. Backup `data/markdown/` ke Google Drive 14-11-2026.
- [x] **3.6** **Inspeksi manual hasil** — ini bukan opsional: ✅ 14-11-2026 — inspeksi manual oleh
      pengguna + `scripts/check_parse_output.py`: **76/76 angka di sel yang benar** (73 tepat, 3 di sel
      berisi dua angka). 1–1,7% sel nilai berisi ≥ 2 angka → perbaikan pasca-parse di 5.1.
      - [x] Buka `.md`, cari "LAPORAN POSISI KEUANGAN KONSOLIDASIAN"
      - [x] Cek apakah tabelnya jadi tabel Markdown valid (pipe rapi, kolom tahun tidak tertukar)
      - [x] Cek tabel Laporan Laba Rugi
      - [x] Cek 2–3 tabel di Catatan atas Laporan Keuangan (biasanya paling rusak)
      - [x] Cek apakah angka ribuan terbaca benar (`54.836` vs `54836` vs `54 836`)
      - [x] Cek **tabel Catatan KPMM** — 4 kolom (Bank/Konsolidasian × 2 tahun), paling rawan tertukar
      - [x] *(disarankan)* `scripts/check_parse_output.py`: cari 76 angka terverifikasi Minggu 1 di hasil
            parse → "X dari 76 ditemukan" = ukuran ketepatan parsing untuk Bab 4
- [x] **3.7** Uji deteksi sektor pada ketiga laporan BBCA → harus terdeteksi **bank**.
      ✅ 14-11-2026: ketiganya **bank, 6/6 penanda**; tanpa halaman berpenanda prudensial BBCA tidak
      lagi terdeteksi bank (uji negatif). Uji generalisasi saringan & deteksi pada bank lain dipindah
      ke **Minggu 8 (8.0b–8.0c)**.
- [x] **3.8** Dokumentasikan: % tabel rapi, waktu parse sebelum vs sesudah saringan.
      **Keduanya data Bab 4.** ✅ 15-11-2026 (`scripts/measure_parse_time.py`, `results/parse_timing.json`):
      tabel rapi **85,8 / 88,1 / 87,6%**; parse dengan saringan **1,75–1,79× lebih cepat** (253–261 s
      vs 453–457 s, GPU kosong) — bukan 2,6–2,9× seperti rasio halaman, karena halaman yang dibuang
      ringan. 0 angka ground truth hanya ada di halaman terbuang; celah "dalam juta rupiah" → 8.0b.
- [x] **3.9** *(opsional — kandidat pertama untuk dipotong kalau waktu mepet)* bandingkan
      dengan `pdfplumber` pada 10 halaman yang sama. ✅ 14-11-2026, `scripts/compare_pdfplumber.py`:
      10 angka terverifikasi di baris + kolom benar — Docling 9 tepat + 1 cacat, pdfplumber 0 (garis:
      tak ada tabel di halaman LK) dan 2 (teks: memotong angka & judul tahun). pdfplumber 4–7× lebih cepat.

> **GATE 2:** (a) tabel neraca, laba rugi, dan Catatan KPMM BBCA terbaca benar di Markdown;
> (b) ketiga laporan BBCA terdeteksi sebagai bank. Uji pada bank lain → GATE 8.
> Kalau tabel rusak: coba `TableFormerMode.ACCURATE`, atau ekstrak tabel kunci manual ke
> CSV sebagai fallback (sah, asal didokumentasikan di Batasan).
>
> **Status (14-11-2026):** (a) ✅ 76/76 angka di sel yang benar (3 di sel berisi dua angka → 5.1);
> (b) ✅ bank, 6/6 penanda; backup ✅. **GATE 2 LULUS. Minggu 3–4 SELESAI (15-11-2026).**

---

# BULAN 2

## Minggu 5 — Chunking

**Langkah rinci, contoh kode yang sudah diuji, dan daftar periksa: `docs/PANDUAN_MINGGU5.md`.**
Dicek 15-11-2026 pada ketiga hasil parse BCA — beberapa rencana di bawah **dikoreksi**:
- heading Docling datar (805/805 di level 1) → `MarkdownHeaderTextSplitter` tak berguna; pemotong =
  **`HybridChunker`** (docling-core) dengan tokenizer BGE-M3, tabel sebagai **Markdown ringkas**
  (triplet bawaan 2,2× lebih boros; satu tabel 9.639 token > batas BGE-M3)
- **Keputusan 5.A — DISETUJUI 15-11-2026:** maks. **1024 token** + header tabel diulang tiap
  potongan — karena Groq `gpt-oss-120b` dibatasi **8K token/menit** (dicek di console akun
  15-11-2026: 30 RPM / 1K RPD / 8K TPM / 200K TPD, sama dengan dokumentasi); 2048 menjaga semua
  tabel utuh tapi 5 chunk bisa ±10K token

- [x] **5.1** `src/ingest/chunk.py` ~~dengan `MarkdownHeaderTextSplitter`, split pada `#`, `##`, `###`~~
      → `HybridChunker` (lihat atas)
      ⚠️ Memotong dari `.md` biasa **menghilangkan nomor halaman**, padahal setiap angka wajib
      disertai sumber halaman (9.3). Potong dari `.json` hasil Minggu 3: per halaman lewat
      `export_to_markdown(page_no=...)`, atau `HybridChunker` dari docling-core — keduanya sudah
      tersedia di versi terpasang — lalu ubah ke halaman asli dengan peta halaman (3.3).
      ⚠️ Dari audit 05-11-2026: baca **semua `prov`** tiap blok (ada blok lintas halaman), dan
      tangani **16 tabel per laporan tanpa label baris** — daftar di `PANDUAN_MINGGU3.md`
      *(dikoreksi di Minggu 5 menjadi 18 / 17 / 17 tabel, lihat di bawah)*.
      ⚠️ Dari 3.6: **perbaiki sel berisi dua angka** sebelum chunking — sub-baris "Pihak berelasi /
      Pihak ketiga" yang digabung Docling (pecah jadi baris terpisah), dan subtotal tanpa label yang
      menempel ke baris di atasnya. Uji pada hal 540–542 & 704 (`bbca_2024`) dan 576–578 & 738 (`bbca_2023`).
      ✅ **Perbaikan sel selesai 15-11-2026** (`src/ingest/fix_tables.py`, di memori):
      - pola 1 tersisa 0;
      - pola 2 diperbaiki 19 / 19 / 5 baris lewat posisi kata docling-parse, dengan cek silang ke
        isi sel;
      - 57 / 28 / 59 baris yang struktur Docling-nya rusak berat (laporan publikasi, tabel jatuh
        tempo, Pilar 3, tabel menyamping) **ditandai**, dengan 0 di halaman sumber ground truth;
      - `check_parse_output.py` **76/76 tepat** (semula 73 + 3 cacat);
      - `check_fix_tables.py` LULUS;
      - cek visual 20/20 benar;
      - pola 3 (ditambahkan saat 5.4): satu baris cetak yang dibelah Docling menjadi dua baris
        digabung **hanya kalau label dan angkanya sejajar di PDF**, 2 / 4 / 1 pasang (JUMLAH ASET
        dan JUMLAH LIABILITAS konsolidasian 2024), ketujuhnya dicek visual.
      ✅ **Tabel tanpa label selesai 15-11-2026** (`is_unlabeled` di `fix_tables.py`):
      - **18 / 17 / 17 tabel**, semuanya bagian kanan tabel Pilar 3 dua halaman;
      - ciri: kotaknya menempel tepi kiri kertas, dan baris angkanya tanpa label;
      - semuanya dicek visual;
      - definisi audit Minggu 3 (rasio label) keliru di 5 tabel per laporan, jadi daftar 16 halaman
        dikoreksi;
      - dikeluarkan **per item** saat pemotongan (`get_excluded_refs`), bukan per chunk. Prototipe:
        0 tabel bocor ke chunk, dan 0 item lain yang ikut hilang.
      ✅ **Pemotong selesai 15-11-2026** (`src/ingest/chunk.py`):
      - **514 / 540 / 498 chunk diindeks** (angka akhir setelah perbaikan di 5.2 dan 5.4), ditambah
        18 / 17 / 17 record `excluded` untuk audit;
      - boilerplate yang dibuang 142 / 166 / 161, tidak satu pun berisi tabel. Angka diabaikan saat
        membandingkan, supaya 23 chunk "Lampiran x/y" 2025 ikut terbuang;
      - halaman asli diambil dari semua `prov`;
      - tabel terbelah 44 / 44 / 38, dengan **0 potongan tanpa header** dan 0 baris yang rusak;
      - 0 tabel tanpa label bocor ke chunk diindeks, dan 0 isi lain yang ikut hilang.
      Dibuktikan `check_chunks.py` (5.4).
- [x] **5.2** Tambah metadata tiap chunk: **`ticker`** (kode saham), **`sector`**, `year`, `doc_id`
      (hash PDF), `header_path`, `chunk_id`, `is_table` (deteksi: mengandung `|---`).
      *Koreksi:* `is_table` dari label `doc_items`, `header_path` = judul terdekat (heading datar);
      **tambah `pages` dan `unit` per halaman** (laporan campur miliar/juta; 0 halaman campur di BCA),
      `merged_cells`, `excluded`.
      Tanpa `ticker`, angka BBCA bisa bocor ke analisis emiten lain — lihat GATE 3.
      `ticker` & `sector` diambil dari `data/markdown/<kode>_<tahun>.metadata.json` (3.2), bukan
      ditulis tangan.
      ✅ **Selesai 15-11-2026** (`src/ingest/chunk.py`):
      - 15 field per record; `chunk_id` urut dokumen, dan record `excluded` disisipkan di posisi
        tabelnya;
      - `unit` per halaman: 257 / 257 / 228 halaman bersatuan (semula 241 / 241 / 210). Dua tambahan:
        bagian kiri tabel dua halaman mewarisi satuan halaman kanannya, dan penanda tanpa kata
        "dalam" (Docling memecah "(dalam jutaan Rupiah)" ke dua sel);
      - `merged_cells` per **baris**, bukan per tabel: 17 / 13 / 19 chunk;
      - dua perbaikan pemotong yang ditemukan di sini:
        - judul tidak dibawa melintasi halaman yang dilewati penyaring (7 / 1 / 7 potongan);
        - navigasi/footer yang terbaca sebagai isi dilewati (346 item `bbca_2023`).
- [x] **5.3** **Cek distribusi panjang chunk**:
      - chunk > 8192 token → melebihi limit BGE-M3, harus dipecah lagi (`RecursiveCharacterTextSplitter` sebagai lapis kedua, tapi **jangan pecah di tengah tabel**)
      - chunk < 50 token → sampah, buang
      *Koreksi:* dari 184 chunk < 50 token (`bbca_2024`), 162 boilerplate berulang tapi **22 paragraf
      unik bermakna** (mis. hal 701 rasio kredit usaha kecil) → yang dibuang = **teks berulang ≥ 3×**,
      bukan yang pendek.
      ✅ **Selesai 15-11-2026:**
      - token BGE-M3 median 350 / 330 / 306, maks. 1.024 (tidak ada yang > 8192);
      - token gpt-oss median 370 / 356 / 336, p90 ±960;
      - 31–34 chunk pendek yang unik tetap disimpan.
- [x] **5.4** Inspeksi manual 30 chunk acak + **semua chunk `is_table=True`**. Kriteria: tidak ada tabel yang terpotong di tengah.
      *Penyesuaian:* ±230 chunk tabel per laporan → manual untuk halaman kunci + 30 acak; sisanya
      `scripts/check_chunks.py` (76 angka ground truth di chunk & halaman & satuan yang benar).
      ✅ **Selesai 15-11-2026.** `check_chunks.py` **LULUS**:
      - 76/76 angka ground truth terbaca dari teks chunk (baris + kolom + halaman + satuan);
      - tabel, halaman, satuan, `merged_cells`, dan tabel tanpa label 0 masalah;
      - 3 uji negatif gagal sesuai harapan.
      Manual:
      - semua chunk di halaman kunci cocok dengan PDF (48 chunk ≥ 99%);
      - 30 chunk acak 30/30.
      Inspeksi menemukan dan memperbaiki pola 3 (JUMLAH ASET/LIABILITAS) dan boilerplate
      "Lampiran x/y".
- [x] **5.5** Simpan **per dokumen** ke `data/chunks/<kode>_<tahun>.jsonl`. Catat jumlah chunk
      per dokumen → masuk Bab 4.
      ✅ **Selesai 15-11-2026:**
      - `.jsonl` + `.chunks.meta.json` tersimpan;
      - kunci cache memuat hash PDF, hash `.json`, dan **hash kode aturan**;
      - `load_chunks()` untuk Minggu 6;
      - angka Bab 4 ada di lembar hasil `PANDUAN_MINGGU5.md`, `results/check_chunks.json`, dan
        `results/fix_tables.json`.
      ✅ `data/chunks/` di-backup ke Google Drive 15-11-2026.

**Kriteria lolos:** 0 tabel keuangan utama yang terpotong. ✅ **LULUS 15-11-2026**: 0 potongan
tanpa header, 0 baris terbelah (`check_chunks.py` cek B). **Minggu 5 SELESAI** (backup `data/chunks/` 15-11-2026).
*(Dengan Keputusan 5.A = 1024: tidak ada potongan tabel tanpa header kolom dan tidak ada baris
yang terbelah. Tabel rasio resmi, neraca, dan laba rugi memang dipecah per baris dengan header
diulang; KPMM dan Entitas Induk tetap utuh.)*

---

## Minggu 6 — Indexing (Dense + Sparse)

**Langkah rinci, hasil prototipe, dan daftar periksa: `docs/PANDUAN_MINGGU6.md`.**
Dicek 15-11-2026 pada 1.552 chunk sungguhan. Koreksi atas rencana di bawah:
- **6.1:** model BGE-M3 sudah ada di cache, jadi tidak perlu diunduh. Presisi **fp16** (Keputusan
  6.A, **disetujui 15-11-2026**): 54 s vs 193 s untuk fp32, dengan kosinus ≥ 0,9997.
- **6.3:** chromadb 1.5.9 **menolak `None`** di metadata, tetapi **menerima list** (`pages`
  difilter dengan `$contains`). `add` dengan id yang sudah ada **diabaikan diam-diam**, jadi
  idempotensi memakai `index_key` (hash `.jsonl`) + hapus per `doc_id`, bukan sekadar "`doc_id`
  sudah ada". Telemetri Chroma dimatikan.
- **6.4:** BM25 dibangun di memori dari `.jsonl` (0,11 s untuk 3 laporan); **tanpa `.bm25.pkl`**.
- Pratinjau: top-5 memuat angka jawaban item Ikhtisar 7/7 (dense & BM25, query bertahun), tetapi
  hanya 7/15 kalau "benar" = halaman sumber saja, jadi definisi GATE 3 perlu disesuaikan (7.5).

✅ **MINGGU 6 SELESAI 15-11-2026.** 6.1–6.6 selesai, `check_index.py` LULUS, dan ringkasan untuk
Bab 4 ada di PANDUAN_MINGGU6 Langkah 6. Tiga bekal untuk Minggu 7:
- filter tahun wajib (ada 102 pasang chunk identik antar laporan);
- perluasan istilah perbankan ("CKPN" tidak tertulis di laporan);
- definisi "chunk benar" = memuat angka jawabannya.

- [x] **6.1** Load BGE-M3 (`BAAI/bge-m3`, dim 1024) via `sentence-transformers`. Download ~2.2GB, sekali saja.
      ✅ **Selesai 15-11-2026** (`src/retrieval/embed.py`):
      - fp16 di GPU: 1.552 chunk dalam 47 s, VRAM 1,1 GB (puncak 1,5 GB);
      - vektor float32 bernorma 1;
      - dimuat dari **folder snapshot lokal**. Lewat nama repo, transformers tetap mengirim 4–5
        permintaan ke huggingface.co (pengecekan konversi safetensors yang mengabaikan
        `local_files_only`); dari folder lokal 0 permintaan.
- [x] **6.2** Embed semua chunk (batch 8–16, `normalize_embeddings=True`). Catat waktunya.
      ✅ 15-11-2026: 19,0 / 16,7 / 15,0 s per laporan (fp16, batch 16).
- [x] **6.3** Simpan ke ChromaDB persistent:
      - `PersistentClient(path="./chroma_db")`
      - **`metadata={"hnsw:space": "cosine"}`** — default Chroma itu L2, kurang tepat untuk embedding ternormalisasi
      - sertakan metadata `ticker`, `sector`, `year`, `doc_id` (`where={"$and": [{"ticker": "bbca"}, {"year": 2024}]}`)
      - **idempoten**: kalau `doc_id` sudah ada di koleksi, lewati — jangan menggandakan chunk
      ✅ **Selesai 15-11-2026** (`src/retrieval/index.py`):
      - 1.552 chunk, cosine, telemetri mati, 24 MB;
      - idempoten memakai `index_key` (hash `.jsonl` + model + presisi) + hapus per `doc_id`,
        karena `add` id lama diabaikan diam-diam;
      - pengaman koleksi bermodel lain;
      - uji temu-diri 250/250. Ada 102 pasang chunk identik antar laporan, jadi Minggu 7 wajib
        memfilter tahun.
- [x] **6.4** BM25 (`rank_bm25.BM25Okapi`) **satu index per dokumen**, bukan satu index global:
      - alasannya: `rank_bm25` tidak bisa menambah dokumen baru tanpa membangun ulang
        seluruh index, dan pencarian selalu difilter per emiten-tahun anyway
      - tokenizer: lowercase + split + buang tanda baca; **jangan buang angka**
      - ~~simpan ke `data/chunks/<kode>_<tahun>.bm25.pkl`~~
      ✅ **Selesai 15-11-2026** (`src/retrieval/sparse.py`):
      - indeks dibangun di memori dari `.jsonl` (0,20 s untuk 3 laporan) dan otomatis dibangun
        ulang kalau `.jsonl` berubah; **tanpa pickle**, dan `config.bm25()` dihapus;
      - tokenizer mempertahankan angka utuh (`1.586.829`), sedangkan `%` dibuang (`29,14%` →
        `29,14`);
      - "rasio KPMM" → hal 703 / 727 di peringkat 1.
- [x] **6.5** Fungsi `add_document(pdf)` yang menjalankan seluruh pipeline: saring → parse →
      chunk → embed → simpan. Ini yang nanti dipanggil tombol upload.
      ✅ **Selesai 15-11-2026** (`src/ingest/pipeline.py`):
      - identifikasi dari hash pustaka atau dari isi PDF, lalu `identify()` untuk konfirmasi bot;
      - **pengaman**: PDF berbeda isi untuk kode+tahun yang sudah ada ditolak (tidak menimpa
        diam-diam);
      - laporan baru dari nol (`bbca_2025`, pustaka sementara) selesai dalam **8 menit** dengan
        hasil **identik 515/515 record** dengan pustaka asli;
      - dari cache 0,2–0,3 s.
- [x] **6.6** Smoke test: query "laba bersih" ke Chroma dan ke BM25 — keduanya harus mengembalikan chunk masuk akal.
      ✅ **Selesai 15-11-2026** — `scripts/check_index.py` **LULUS**:
      - isi, metadata, vektor, temu-diri, filter, BM25 0 masalah; 3 uji negatif tertangkap;
      - "laba bersih" 5/5 (dense & BM25); pratinjau Ikhtisar 2025: 7/7 & 7/7.
      ⚠️ **Temuan untuk Minggu 7:** singkatan yang tidak tertulis di laporan tidak ditemukan.
      "CKPN" → hal 738 tidak masuk 10 besar, sedangkan "cadangan kerugian penurunan nilai" →
      BM25 peringkat 1. Jadi tambahkan **perluasan istilah perbankan** di `hybrid_retrieve`
      (lihat PANDUAN_MINGGU6, Dampak).

---

## Minggu 7 — Hybrid Search + RRF

**Langkah rinci, hasil prototipe, dan daftar periksa: `docs/PANDUAN_MINGGU7.md`.**
Diuji 15-11-2026 dengan prototipe pada 15 query uji (dari ground truth; 7 bersingkatan). Koreksi atas
rencana di bawah:
- **Tanpa perluasan istilah, GATE 3 tidak lulus:** hybrid 11/15 (73%). **Dengan perluasan**
  (CKPN → "cadangan kerugian penurunan nilai", dst., Keputusan 7.A, **disetujui 15-11-2026**):
  **13/15 (87%)**.
- **Hipotesis proposal sebagian terbantah:** BM25 + perluasan (15/15) mengungguli hybrid (13/15) pada
  query angka. Dilaporkan jujur di Bab 4.
- **Filter tahun wajib.** Pencarian lintas tahun (`year=None`) sekaligus: 45 dari 75 chunk dari
  tahun yang salah, jadi dicari per tahun.
- `k` RRF 10/60/100 tidak berpengaruh (7.6 sudah diuji); kandidat 10 per daftar sudah cukup.
- "Chunk benar" = chunk yang memuat angka jawabannya (Keputusan 7.B, **disetujui 15-11-2026**;
  dibawa juga ke bimbingan karena definisi metrik).

- [x] **7.1** `dense_search(query, ticker, year, k=10)` → list `(chunk_id, rank)` *(26-11-2026, `src/retrieval/hybrid.py`)*
- [x] **7.2** `sparse_search(query, ticker, year, k=10)` → list `(chunk_id, rank)` *(26-11-2026, `src/retrieval/hybrid.py`)*
- [x] **7.3** `rrf_fuse(lists, k=60)` → `score(d) = Σ 1/(k + rank_i(d))`, sort desc, ambil top-5 *(26-11-2026, `src/retrieval/hybrid.py`)*
- [x] **7.4** `hybrid_retrieve(query, ticker, year=None, k=5)` sebagai API tunggal *(26-11-2026, `src/retrieval/hybrid.py`)*.
      `ticker` **wajib**, bukan opsional — tidak boleh ada pencarian lintas emiten tanpa sengaja.
- [x] **7.5** **Eksperimen pembanding** (bahan Bab 4, `eval/retrieval_eval.py` → `results/retrieval_eval.json` & `.csv`, ✅ 26-11-2026): 15 query uji terkunci (SHA-256 `cfab3a18…46fc2`):

      | Konfigurasi | Hit@1 | Hit@5 | MRR@5 |
      |---|---|---|---|
      | Dense only (Chroma) — tanpa / + perluasan | 40% / 53% | 7/15 (47%) / 9/15 (60%) | 0,433 / 0,567 |
      | Sparse only (BM25) — tanpa / + perluasan | 40% / 40% | 12/15 (80%) / **15/15 (100%)** | 0,550 / 0,604 |
      | **Hybrid + RRF** — tanpa / **+ perluasan** | 47% / **60%** | 11/15 (73%) / **13/15 (87%)** | 0,556 / **0,702** |

      Temuan: pada query angka, BM25+ unggul di Hit@5 (15/15 vs 13/15), tetapi **Hybrid+ unggul di
      Hit@1 (60% vs 40%) dan MRR@5 (0,702 vs 0,604)**; pada subkelompok singkatan, perluasan
      menaikkan Hybrid dari 4/7 → 6/7. Latensi warm median 25,3 ms.
- [x] **7.6** *(opsional)* uji sensitivitas `k` RRF: 10, 60, 100 ✅ 26-11-2026 (`eval/retrieval_eval.py`:
      ketiganya identik — Hit@5 13/15, Hit@1 9/15, MRR@5 0,702; kandidat 5/10/20/30 = 12/13/13/13).

- [x] **7.7** Pastikan `ticker` sudah jadi parameter **wajib** di semua fungsi retrieval *(26-11-2026: `dense_search`, `sparse_search`, `hybrid_retrieve` menolak `ticker` kosong/tak terdaftar dengan `ValueError`)*.
      Uji kontaminasi antar bank butuh dua bank di pustaka → dipindah ke **Minggu 8 (8.0d)**.

> **GATE 3:** Hit@5 hybrid ≥ 80% pada 15 query uji (BBCA). Uji kontaminasi → GATE 8.
> Kalau (a) gagal, masalahnya di chunking (balik ke Minggu 5), bukan di retrieval.
>
> **Status (26-11-2026):** ✅ **GATE 3 LULUS — Minggu 7 SELESAI.** Hit@5 hybrid + perluasan
> **13/15 (86,7%)**, Hit@1 **9/15 (60%)**, MRR@5 **0,702**, `scripts/check_retrieval.py` **LULUS**
> (A–F OK, 3/3 uji negatif tertangkap). Detail & diagnosis 2 query meleset (`q08`, `q09`) di
> `docs/PANDUAN_MINGGU7.md`.

---

## Minggu 8 — Mulai Dataset Evaluasi (JANGAN DITUNDA)

**Langkah rinci, skema dataset, dan daftar periksa: `docs/PANDUAN_MINGGU8.md`.**
Ini penyebab nomor 1 skripsi molor. Cicil dari sekarang: **3 pertanyaan per hari**.

### 8.0 — Bank uji (BMRI) masuk ke pustaka

Pertama kalinya data selain BCA disentuh. Langkah rinci unduhan & pemeriksaan ada di
`docs/PANDUAN_MINGGU2.md` Langkah 12 (disusun di Minggu 2, dipakai sekarang).

- [x] **8.0a** Unduh laporan tahunan **BMRI** 2023–2025 ke `data/raw/bmri_<tahun>.pdf`, lalu
      `python scripts/inspect_pdf.py`. Catat satuan, ukuran file, dwibahasa / LK terpisah. BBRI opsional.
      ✅ **26-11-2026:** ketiganya text-based (`23,8 / 21,1 / 22,9 MB` — semua > 20 MB, menguatkan R18; `1.514 / 1.726 / 1.467` hal.), satuan dominan `million_idr`, LK menyatu & dwibahasa ID+EN.
- [x] **8.0b** Uji saringan halaman pada BMRI: apakah Catatan KPMM, Entitas Induk, dan Catatan
      NPL ikut tersaring? Kalau tidak, saringan terlalu khas BBCA.
      ✅ **26-11-2026 (`RULE_VERSION = 3`):** ditambah varian penanda satuan (`dalam juta rupiah`, `dalam rp juta/jutaan`, `in million rupiah`, beserta `miliar/miliaran`) + 7 kelompok sinonim rasio ID/EN (`RATIO_TERMS`), sekaligus menutup celah 3.8 Pilar 3 CC1 BBCA. BMRI lolos `563 / 633 / 594` hal. (37–40%) mencakup seluruh 7 kelompok halaman penting; BBCA di-parse ulang (`273 / 274 / 235` hal., `541 / 571 / 519` chunk) dan seluruh regresi (`check_page_filter`, `check_parse_output` 76/76, `check_fix_tables`, `check_chunks`, `check_index`, `check_retrieval`) **LULUS**.
- [x] **8.0c** Uji deteksi sektor: BMRI → bank; **1 laporan non-bank apa saja** (cukup 1 tahun,
      mis. TLKM) → bukan bank → profil umum.
      ✅ **26–27-11-2026:** BMRI 3/3 → `ticker=bmri`, `PT Bank Mandiri (Persero) Tbk`, `sector=bank` (6/6 penanda, `validated=True`, 0 peringatan); `tlkm_2024.pdf` (21,0 MB, 588 hal., Inggris) → `ticker=tlkm`, `PT Telekomunikasi Indonesia Tbk`, `2024`, `billion_idr`, `sector=non_financial` (`validated=False` / *belum divalidasi*, penanda bank `0/6`, 0 peringatan; tidak diindeks ke Chroma). `scripts/check_detect_metadata.py` **LULUS**.
- [x] **8.0d** Masukkan BMRI ke pustaka, lalu **uji kontaminasi**: 10 query per bank, **tidak
      boleh ada satu pun chunk bank lain** di hasil. Tier 1 BBCA yang terselip ke analisis BMRI
      tidak akan terlihat salah — tapi hasilnya salah.
      ✅ **26–27-11-2026:** 3 laporan BMRI masuk via `add_document()` (`1.219 / 1.358 / 1.430` chunk, `0` potongan tabel tanpa header; total koleksi `5.638` chunk, `chroma_db` `101,3 MB`) + backup Google Drive selesai. `scripts/check_contamination.py` **LULUS** (`results/check_contamination.json`): **0/120 bocor** (20 panggilan `hybrid_retrieve` + `dense`/`sparse`), uji negatif tanpa filter `ticker` mencampur **10/10 query** (`bbca` 53 vs `bmri` 47), regresi GATE 3 BBCA tetap **13/15 (86,7%)**.
- [x] **8.0e** Kalau pipeline perlu diperbaiki karena format BMRI: perbaikan harus **generik**
      (mis. menangani laporan dwibahasa), bukan menyesuaikan prompt ke isi BMRI — dan dicatat
      untuk Bab 4. Prompt Extraction Agent tetap dirancang dengan BBCA saja.
      ✅ **26–27-11-2026:** 3 perbaikan generik terdokumentasi di `docs/PANDUAN_MINGGU8.md` (`page_filter.py` v3 + `chunk.py` untuk varian satuan & rasio ID/EN; `detect_metadata.py` untuk mencegah kode saham anak usaha mengalahkan induk + tabel identitas 2 kolom + pola `idx/bei ticker` & `(IDX): KODE` pada laporan bahasa Inggris).

> **GATE 8:** saringan & deteksi sektor bekerja pada BMRI; **nol kontaminasi** antar bank.
>
> **Status (27-11-2026):** ✅ **GATE 8 LULUS PENUH — MINGGU 8 SELESAI 100%** (saringan v3, deteksi sektor `bank` 3/3 BMRI + `non_financial` `tlkm_2024.pdf`, ingest penuh 3/3 BMRI + backup Google Drive, 0 kontaminasi BBCA↔BMRI, regresi BBCA utuh, ground truth & retrieval BMRI 8.5 selesai & terverifikasi visual, serta dataset RAGAS 8.1–8.4 selesai penuh 30/30).

- [x] **8.1** Buat `eval/datasets/ragas_qa.jsonl`, target **30 pasang**, format:
      `{"question": "...", "reference": "...", "ref_page": 112, "type": "faktual"}`
      ✅ **Selesai penuh 26-11-2026:** **30/30 pasang** (`qa01–qa30`), `python -m eval.ragas_dataset --strict-final` **LULUS** (SHA-256 `fe67bb42…4723`).
- [x] **8.2** Komposisi yang disarankan:
      - 12 faktual 1-hop ("Berapa laba bersih BCA 2024?") ✅ `12/12` (8 BBCA + 4 BMRI)
      - 8 multi-hop ("Berapa ROE 2024?" → butuh laba bersih + ekuitas) ✅ `8/8` (5 BBCA + 3 BMRI)
      - 6 komparatif antar tahun ("Bagaimana tren NPL 2022–2024?") ✅ `6/6` (4 BBCA + 2 BMRI, periode final 2023–2025)
      - 4 kontekstual/kualitatif ("Apa penyebab kenaikan pendapatan bunga bersih?") ✅ `4/4` (3 BBCA + 1 BMRI)
- [x] **8.3** Setiap `reference` **wajib** ditulis dari PDF, dengan nomor halaman. Ini yang dipakai `context_recall`. ✅ Seluruh 30 `reference` ditulis dari teks tampak PDF asli (`pypdfium2`), **30/30** `ref_page` terverifikasi hadir di `data/chunks/*.jsonl`.
- [x] **8.4** Sebar 30 pertanyaan: ±20 BBCA, ±10 BMRI — jangan semuanya bank pengembangan. ✅ Tepat **20 BBCA + 10 BMRI**.
- [x] **8.5** **Ground truth rasio BMRI** — ulangi langkah Minggu 1: ekstrak angka mentah,
      cocokkan ke rasio resmi, verifikasi manual. Perkakasnya sudah ada (`validate_ratios.py`,
      `build_ground_truth.py`, `build_verification_sheet.py`), tinggal diberi parameter emiten.
      Rasio resmi BMRI mengikuti SEOJK yang sama dengan BBCA → acuannya sama kuat.
      ✅ **Selesai 26-11-2026:** `data/ground_truth_bmri.xlsx`, `docs/lembar_verifikasi_bmri.md`, & `results/validate_ratios_bmri.json` terverifikasi visual pada render gambar seluruh 30 halaman PDF asli (`v 26/11/26`: 109/110 cocok persis, 1 koreksi penjumlahan 30 juta Rp pada `Aset Produktif Inti Bank 2023` → `1.439.648,199` miliar) — **6/6 rasio lolos MAPE < 5%** (CAR 0,01%, NPL 0,51%, LDR 0,69%, NIM 1,09%, ROA 3,00% [SEOJK Laba Sebelum Pajak — beda dari fn9 BBCA!], ROE 4,31%); `scripts/check_bmri_chunks.py` **LULUS**; uji retrieval BMRI `results/retrieval_eval_bmri.json` **8/10 = 80,0%**, Hit@1 **80%**, MRR@5 **0,800** tanpa penyetelan `BANK_TERMS` (SHA-256 `8b0840dc…98c4`).

> **Koreksi atas proposal:** Sub-bab 3.6.1 menyebut RAGAS "tanpa memerlukan ground truth".
> Itu tidak akurat — `context_recall` **membutuhkan** reference answer. Perbaiki kalimat ini di Bab 3.

---

# BULAN 3

## Minggu 9–10 — Extraction Agent

**Langkah rinci, keputusan rancangan (9.A–9.D), dan daftar periksa: `docs/PANDUAN_MINGGU9.md`.**

- [x] **9.1** `src/agents/state.py` — `AgentState(TypedDict)`:
      `query, year, extracted_data, ratios, market_context, report, messages` *(+ `ticker`, `sector`, `retrieved_chunks`, skema Pydantic `RawMetricExtraction` / `NormalizedMetric`; 27-11-2026)*
- [x] **9.2** Bungkus `hybrid_retrieve` jadi LangChain `@tool` *(27-11-2026: `src/agents/tools.py`, `search_annual_report` bahasa Inggris + metadata halaman/satuan/`merged_cells` + `ContextVar` recorder)*
- [x] **9.3** Prompt Extraction Agent *(27-11-2026: `src/agents/parse_number.py` + `src/agents/extraction.py` — output terstruktur, sitasi wajib, `null` jujur, konversi angka ID + `U+202F` + penjumlahan komponen + normalisasi ke juta Rp + pagar grounding oleh Python; `scripts/check_extraction.py` LULUS termasuk 3 uji negatif & live BBCA 2024 **8/8 = 100%** error `0,000%`)*. Aturan wajib:
      - output **JSON terstruktur**, bukan prose
      - setiap angka wajib disertai `sumber` (halaman/header)
      - kalau angka tidak ditemukan → `null`, **dilarang menebak**
      - normalisasi satuan ke **juta Rupiah** (laporan BCA campur: miliar di ikhtisar, juta di LK)
      - **format angka Indonesia** dijelaskan eksplisit: titik = pemisah ribuan, koma = desimal.
        Terbukti di uji 2.5b: tanpa itu `239.468,855` dibaca `239.468855` pada 5 dari 5 percobaan.
        Di ROE kebetulan saling menghapus; di sistem sungguhan tidak — laba (miliar, Ikhtisar)
        dan Tier 1 (juta, KPMM) skalanya beda. Lebih aman lagi: konversi angka dilakukan
        **kode Python**, bukan LLM — LLM cukup mengutip teks angka apa adanya.
      - jawaban gpt-oss memuat spasi sempit `U+202F` di dalam angka (`Rp 54.851`) — parser
        angka harus membuangnya
- [x] **9.4** Pakai structured output (Pydantic) supaya tidak perlu parsing string *(27-11-2026: `method="json_schema"` pada `openai/gpt-oss-120b` `effort="low"` + fallback `json_mode` + backoff 429 di `src/agents/extraction.py` & `extraction_node`)*
- [x] **9.5** Prompt **tidak boleh** memuat hal khas emiten tertentu: nomor halaman, nomor Catatan
      ("Catatan 51f"), atau nama perusahaan. Jelaskan *apa* yang dicari secara semantik
      ("tabel KPMM, kolom basis Bank"), bukan *di mana* letaknya di laporan BBCA. *(27-11-2026: audit otomatis `check_extraction.py` lulus 0 kebocoran di `ratio_profiles.py`, `tools.py`, `extraction.py`, dan `EXTRACTION_SYSTEM_PROMPT`)*
- [x] **9.5b** **Daftar angka yang diekstrak diambil dari profil rasio sektor** (lihat 11.2), bukan
      ditulis tetap di prompt. Bank butuh Tier 1, ATMR, kredit bruto; profil umum (non-bank)
      cukup laba, total aset, dan ekuitas. *(27-11-2026: `src/ratio_profiles.py` — profil `bank` 15 metrik / 8 GATE 4 & `general` 3 metrik, 0 kebocoran nama emiten)*
- [x] **9.6** Tes ekstraksi: 8 angka bank (laba bersih, Tier 1, total aset, kredit bruto, DPK,
      kredit bermasalah, pendapatan bunga bersih, ATMR) × 3 tahun, untuk **BBCA dan BMRI**.
      *(27-11-2026: `eval/extraction_eval.py` → `results/extraction_eval.json` & `.csv`; dukungan OpenRouter prabayar di `src/config.py` untuk `openai/gpt-oss-120b`)*
- [x] **9.7** Catat akurasi ekstraksi **per emiten, terpisah** → masuk Bab 4. Selisih emiten
      pengembangan vs emiten uji adalah ukuran seberapa jauh agent hanya "hafal" format.
      *(27-11-2026, dicatat jujur sebelum & sesudah perbaikan generik di `docs/PANDUAN_MINGGU9.md`: v1 `6d325d9` BBCA `22/24 = 91,7%` vs BMRI `16/24 = 66,7%`, gap `25,0` pp → setelah perbaikan generik fragmentasi tabel multi-halaman, anti-segmen, & query dwibahasa v2 `34ac9eb`: **BBCA `23/24 = 95,8%`** [`7/8`, `8/8`, `8/8`] vs **BMRI `21/24 = 87,5%`** [`5/8`, `8/8`, `8/8`], **gap turun ke `8,33` pp**; rata-rata `11,2–14,3 s`/tahun via OpenRouter)*

> **GATE 4:** akurasi ekstraksi ≥ 90% (≥22/24) pada BBCA **dan** ≥ 80% pada BMRI. Kalau meleset, MAPE rasio pasti gagal —
> perbaiki di sini, jangan berharap agent berikutnya menutupi.
>
> **Status (27-11-2026):** ✅ **GATE 4 LULUS PENUH — MINGGU 9–10 SELESAI 100%.** BBCA **23/24 (95,8%)**, BMRI **21/24 (87,5%)** pada commit terkunci `34ac9eb` (sidik jari `3874399a9a48…`), `scripts/check_extraction.py` **LULUS** (termasuk 3/3 uji negatif & 0 kebocoran emiten). Rincian v1 vs v2 untuk Bab 4 ada di `docs/PANDUAN_MINGGU9.md`.

---

## Minggu 11–12 — Financial Analyst Agent

- [ ] **11.1** Setup `PythonAstREPLTool` (dari `langchain_experimental.tools`)
- [ ] **11.2** **Profil rasio** di `src/ratio_profiles.py`: satu entri per sektor berisi daftar angka
      yang harus diekstrak + formula eksplisit. Agent memilih profil dari metadata `sector`
      dokumen (hasil 3.2), bukan menebak sendiri.
      - `bank`: 6 rasio tervalidasi Minggu 1 (CAR, ROA, ROE, NIM, NPL, LDR)
      - `general` (semua emiten non-bank): hanya ROA & ROE, **dengan label jelas** *belum
        divalidasi* di setiap jawaban
      Formula tetap ditulis di kode, jangan biarkan LLM mengarang formula.
- [ ] **11.3** Implementasi basis perhitungan sesuai keputusan GATE 1 (rata-rata vs saldo akhir — harus konsisten)
- [ ] **11.4** Validasi: agent harus menolak menghitung kalau input `null` (cegah halusinasi)
- [ ] **11.5** Tes 6 rasio × 3 tahun pada BBCA, bandingkan ke ground truth, hitung MAE & MAPE
- [ ] **11.6** Tambah interpretasi terhadap ambang batas OJK (Tabel 2.2) → "CAR 29,4% → jauh di atas
      minimum 8%, permodalan sangat kuat"

---

# BULAN 4

## Minggu 13 — Market Observer Agent

- [ ] **13.1** Tavily tool dengan `include_domains` = domain umum (`ojk.go.id`, `idx.co.id`,
      `kontan.co.id`, `bisnis.com`, `cnbcindonesia.com`) **ditambah domain emiten yang sedang
      dianalisis** — diambil dari metadata dokumen, bukan di-hardcode `bca.co.id`.
      Daftar domain umum ada di `src/config.py` (`TAVILY_DOMAINS`).
- [ ] **13.2** Filter lapis-2: LLM menyaring relevansi hasil pencarian
- [ ] **13.3** Output wajib menyertakan URL + tanggal (agar bisa ditelusuri di laporan)
- [ ] **13.4** Handling kalau Tavily gagal/kosong → jangan crash, kembalikan list kosong

## Minggu 14 — Reporting Agent

- [ ] **14.1** Prompt: susun laporan terstruktur (Ringkasan Eksekutif → Rasio & Interpretasi → Tren Antar Tahun → Konteks Pasar → Kesimpulan)
- [ ] **14.2** Wajib mencantumkan sumber setiap angka
- [ ] **14.3** Output Markdown

## Minggu 15 — Orkestrasi LangGraph

- [ ] **15.1** `StateGraph(AgentState)`, 4 node, alur: `START → extraction → analyst → market → reporting → END`
      *(Market Observer bisa paralel dengan extraction+analyst — nilai plus, dan memperkuat argumen "lebih cepat" di Skenario 3)*
- [ ] **15.2** Conditional edge: kalau extraction gagal → retry sekali → kalau tetap gagal, lapor ke user (jangan lanjut menghitung dari data kosong)
- [ ] **15.2b** Tangani error 400 `tool_use_failed` dari Groq (model memanggil tool yang tidak ada).
      Retry polos **tidak menolong** pada `temperature=0` — input sama, output sama. Yang
      menolong: semua nama tool bahasa Inggris (temuan 2.5b), dan kalau tetap terjadi, ulangi
      dengan pesan tambahan yang menyebut nama tool yang benar.
- [ ] **15.3** Tambah `recursion_limit` supaya tidak infinite loop
- [ ] **15.4** Instrumentasi: catat timestamp masuk/keluar tiap node → `results/timing.csv`
- [ ] **15.5** Export diagram graph (`graph.get_graph().draw_mermaid_png()`) → **gambar untuk Bab 4**
- [ ] **15.6** End-to-end test: 1 query lengkap dari awal sampai laporan jadi

## Minggu 16 — Baseline Single-Agent + Bot Telegram

- [ ] **16.1** `src/baseline/single_agent.py` — **satu** agent, semua tool (retrieve + python + tavily), satu prompt panjang berisi seluruh instruksi.
      Harus pakai LLM, tool, dan knowledge base **yang sama persis** — hanya arsitekturnya yang beda. Kalau tidak, perbandingan Skenario 3 tidak valid.
- [ ] **16.2** Instrumentasi waktu yang sama
- [ ] **16.3** `src/telegram_bot.py` dengan `python-telegram-bot`:
      - token dari @BotFather di `.env` (`TELEGRAM_BOT_TOKEN`)
      - **allowlist user ID** (`TELEGRAM_ALLOWED_USERS`) — bot Telegram bisa ditemukan siapa
        saja; tanpa allowlist, orang lain bisa menghabiskan kuota Groq Anda (R19)
      - mode **polling**: tidak butuh server atau domain publik, cukup laptop menyala + internet
- [ ] **16.3a** Progres langkah agent: **satu pesan yang di-edit** per tahap (mengekstrak →
      menghitung → mencari berita → menyusun laporan), paling sering ±1 edit per detik — batas
      Telegram per chat.
- [ ] **16.3b** **Unggah laporan**: terima PDF → tampilkan tebakan emiten, tahun, satuan & sektor →
      pengguna konfirmasi lewat tombol → jalankan `add_document()` dengan progres per tahap.
      Kalau hash sudah ada di pustaka, langsung pakai tanpa parse ulang.
      **Batas 20 MB (R18):** jalankan **Local Bot API Server** lewat Docker (sudah terpasang) →
      unduhan tanpa batas ukuran. Butuh `api_id` & `api_hash` dari my.telegram.org, disimpan di
      `.env`. Kalau tidak berhasil disiapkan: unggahan dibatasi ≤ 20 MB, laporan yang lebih
      besar dimasukkan lewat script `add_document` — dicatat sebagai keterbatasan di Bab 4.
- [ ] **16.3c** Perintah `/pustaka` menampilkan isi pustaka (emiten × tahun × sektor) supaya
      pengguna tahu apa yang bisa dianalisis.
- [ ] **16.3d** Keluaran: pesan Telegram maksimal 4.096 karakter dan **tidak mendukung tabel** →
      ringkasan di pesan (parse mode **HTML** — MarkdownV2 rawan error escape), laporan lengkap
      dikirim sebagai **file**, grafik rasio sebagai gambar (matplotlib).
- [ ] **16.4** Screenshot percakapan Telegram (butuh 3–4 untuk Bab 4): unggah, progres, laporan, `/pustaka`

> **GATE 5:** Sistem multi-agent DAN baseline single-agent dua-duanya jalan end-to-end.
> Mulai sini **freeze fitur** — tidak ada penambahan fitur baru lagi, fokus pengujian.

---

# BULAN 5 — PENGUJIAN

## Minggu 17–18 — Skenario 1: RAGAS

- [ ] **17.1** Lengkapi 30 Q&A (harusnya sudah ~75% dari cicilan Minggu 8)
- [ ] **17.2** Jalankan sistem untuk 30 pertanyaan, simpan `question, answer, contexts, reference`
- [ ] **17.3** `eval/ragas_eval.py` — metrik: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`
- [ ] **17.4** Judge LLM: **`gemini-2.5-flash`** (sudah di `src/config.py`) — sengaja beda penyedia
      dengan model sistem. Embedding judge: `text-embedding-004` dari Google, **bukan** BGE-M3
      yang dipakai sistem. Model non-OpenAI perlu dibungkus `LangchainLLMWrapper` dan
      `LangchainEmbeddingsWrapper` — RAGAS default-nya OpenAI.
- [ ] **17.5** Simpan skor **per-pertanyaan** ke `results/ragas_scores.csv` (bukan cuma rata-rata)
- [ ] **17.6** Analisis: pertanyaan tipe apa yang skornya rendah? → bahan pembahasan Bab 4
- [ ] **17.7** Grafik: bar chart 4 metrik + garis target 0,8

## Minggu 19 — Skenario 2: Akurasi Rasio (MAPE)

- [ ] **19.1** `eval/ratio_eval.py`: 6 rasio × 3 tahun × **5 run** (LLM non-deterministik — 1 run
      tidak sah secara metodologis), untuk **BBCA dan BMRI** (+ BBRI kalau diunduh).
      Evaluasi dijalankan lewat script, **bukan lewat Telegram** — antarmuka tidak memengaruhi hasil.
- [ ] **19.1b** Laporkan **terpisah**: MAPE BBCA (pengembangan) vs MAPE BMRI (uji). Klaim utama
      skripsi didasarkan pada **BMRI** — BBCA dipakai merancang, jadi hasilnya cenderung
      optimistis. Kalau BMRI jauh lebih buruk, itu temuan yang harus dibahas.
- [ ] **19.2** Hitung per rasio: mean, std, MAE, MAPE
- [ ] **19.3** Tabel: `rasio | tahun | nilai_sistem (mean±std) | nilai_referensi | AE | APE`
- [ ] **19.4** Klasifikasi sesuai proposal: <2% sangat akurat, 2–5% akurat, >5% kurang akurat
- [ ] **19.5** **Analisis error**: untuk setiap rasio dengan MAPE>5%, telusuri — salah ekstraksi? salah basis (rata-rata vs akhir)? beda definisi? Ini bagian yang paling dinilai penguji.
- [ ] **19.6** Grafik: bar chart MAPE per rasio + garis ambang 5%

## Minggu 20 — Skenario 3: Multi-Agent vs Single-Agent

- [ ] **20.1** Siapkan 10 query identik (campuran: faktual, analisis rasio, komparatif, komprehensif)
- [ ] **20.2** Jalankan di kedua sistem, **3 run masing-masing**, catat semua output + waktu
- [ ] **20.3** Metrik otomatis:
      - waktu eksekusi (detik)
      - jumlah rasio berhasil dihitung
      - jumlah sumber/sitasi dalam laporan
      - jumlah panggilan LLM & total token — **termasuk token penalaran**

      ⚠️ **Penting karena gpt-oss reasoning model.** Latensi didominasi penalaran,
      bukan orkestrasi. Kalau hanya melaporkan waktu, selisih multi vs single agent
      bisa tertutup noise dan klaim "lebih cepat" jadi lemah. Laporkan waktu DAN token
      berdampingan, dan sebutkan `reasoning_effort` yang dipakai (harus sama di kedua sistem).
- [ ] **20.4** Metrik kualitas — **buat rubrik dulu**, 4 dimensi skala 1–5:
      akurasi faktual | kelengkapan | struktur & keterbacaan | kedalaman analisis
- [ ] **20.5** **Minta 2–3 penilai independen** (teman seangkatan / asisten lab / dosen) menilai secara *blind* (output diacak, tidak diberi label sistem mana)
- [ ] **20.6** Hitung kesepakatan antar-penilai (Cohen kappa / rata-rata + catat variasi)
- [ ] **20.7** Simpan ke `results/comparison.csv`

> **Catatan metodologis:** "dinilai kualitatif oleh penguji" (proposal hal. 21) akan dikritik
> saat sidang karena bias peneliti. Rubrik + penilai blind menutup celah itu.

---

# BULAN 6 — PENULISAN

## Minggu 21 — Bab 4

- [ ] **21.1** 4.1 Implementasi: lingkungan, spesifikasi hardware, versi library
- [ ] **21.2** 4.2 Implementasi Data Pipeline (efek saringan halaman pada waktu parse, statistik
      parsing, jumlah chunk per dokumen, waktu ingest per unggahan)
- [ ] **21.3** 4.3 Implementasi RAG (+ tabel Dense/Sparse/Hybrid dari Minggu 7)
- [ ] **21.4** 4.4 Implementasi Multi-Agent (potongan kode kunci, diagram LangGraph, screenshot bot Telegram)
- [ ] **21.5** 4.5 Hasil Skenario 1 + pembahasan
- [ ] **21.6** 4.6 Hasil Skenario 2 + **analisis error** (bagian paling penting)
- [ ] **21.7** 4.7 Hasil Skenario 3 + pembahasan
- [ ] **21.8** 4.8 Pembahasan Umum: dikaitkan ke Han et al. [1] & Lumer et al. [3] — temuan sejalan atau berbeda? kenapa?

## Minggu 22 — Bab 5 + Revisi Bab 1–3

- [ ] **22.1** Bab 5 Kesimpulan — **jawab persis 3 rumusan masalah** di 1.2, satu paragraf per rumusan, sertakan angka hasil
- [ ] **22.2** Keterbatasan penelitian (jujur: apa yang tidak tercapai)
- [ ] **22.3** Saran penelitian lanjutan (profil rasio & validasi untuk emiten non-keuangan —
      Current Ratio, DER, NPM, TATO; bank syariah — FDR/NPF; asuransi — RBC; pembiayaan —
      NPF/gearing; sekuritas — MKBD; deteksi fraud yang
      di-exclude di Batasan no.5; agent debate ala FinDebate)
- [ ] **22.4** Revisi Bab 1: ruang lingkup jadi **emiten BEI, divalidasi pada sektor perbankan**;
      antarmuka Telegram; update periode data; update model LLM
- [ ] **22.4b** Revisi Bab 2 & 3: Tabel 2.2 ke formula SEOJK + catatan profil umum (ROA, ROE)
      untuk non-bank; Tabel 3.1 — Chainlit diganti `python-telegram-bot` + Local Bot API Server
- [ ] **22.5** Revisi Bab 2: tambah subbab BM25 & RRF (saat ini belum ada penjelasan formal RRF), tambah subbab RAGAS
- [ ] **22.6** Revisi Bab 3: ubah *future tense* → *past tense*; perbaiki kalimat "RAGAS tanpa ground truth"; perbaiki typo `stru,ktur` (hal.16)
- [ ] **22.7** Tulis **Abstrak** sekarang (paling akhir), isi angka hasil sebenarnya — bukan target

## Minggu 23 — Finalisasi Dokumen

- [ ] **23.1** Halaman depan, lembar pengesahan, pernyataan orisinalitas, kata pengantar
- [ ] **23.2** Daftar Isi / Gambar / Tabel / Singkatan (auto-generate)
- [ ] **23.3** Abstrak Indonesia + Inggris
- [ ] **23.4** Cek konsistensi penomoran gambar & tabel, pastikan semua dirujuk di teks
- [ ] **23.5** Cek sitasi IEEE: semua [1]–[18] dirujuk, tidak ada yang yatim
- [ ] **23.6** Turnitin → target < 25%
- [ ] **23.7** Rapikan repo GitHub + README (cara reproduksi hasil)
- [ ] **23.8** Kirim draf lengkap ke pembimbing — **sisakan minimal 1 minggu untuk revisi mereka**

## Minggu 24 — Sidang

- [ ] **24.1** Slide 15–20 halaman: Latar belakang (2) → Rumusan & Tujuan (1) → Metode/Arsitektur (4) → Implementasi (3) → Hasil 3 skenario (5) → Kesimpulan (2)
- [ ] **24.2** Siapkan **demo live** + video cadangan. Bot jalan di laptop: pastikan Docker (Local
      Bot API Server), bot, dan koneksi internet hidup sebelum sidang; pakai laporan yang
      **sudah ada di pustaka** supaya demo tidak menunggu parsing
- [ ] **24.3** Latihan presentasi, target 15 menit
- [ ] **24.4** Antisipasi pertanyaan penguji:
      - "Kenapa hybrid search, bukan dense saja?" → tunjuk tabel Minggu 7.5
      - "Kenapa MAPE rasio X besar?" → analisis error Minggu 19.5
      - "Bagaimana memastikan laporan tidak halusinasi?" → faithfulness RAGAS + sitasi per angka
      - "Apa bedanya dengan FinRobot?" → PSAK/OJK, bahasa Indonesia, hybrid RAG
      - "Kenapa yakin multi-agent lebih baik, bukan cuma karena promptnya lebih panjang?" → siapkan jawabannya, ini pertanyaan tersulit
      - "Kenapa Llama 3 70B, bukan GPT-4?" → open source, biaya, kecepatan LPU
- [ ] **24.5** Sidang
- [ ] **24.6** Revisi pasca-sidang

---

## Daftar Risiko & Mitigasi

| # | Risiko | Dampak | Mitigasi | Deadline deteksi |
|---|---|---|---|---|
| R1 | ~~Rasio resmi tidak bisa direproduksi dari LK konsolidasian~~ | — | **Selesai**: 6/6 lolos dengan formula basis bank | Minggu 1 ✓ |
| R2 | Docling gagal/rusak pada tabel keuangan | Tinggi | TableFormer ACCURATE; fallback ekstraksi manual ke CSV | Minggu 4 |
| R3 | Docling terlalu lambat — **kini dirasakan pengguna** saat unggah | ~~Tinggi~~ **Sedang** | **GPU RTX 3060 tersedia** (torch CUDA, Minggu 2); saring halaman dulu (±1/3 dokumen); cache per hash | Minggu 3 |
| R4 | Dataset 30 Q&A tidak selesai | Tinggi | cicil 3/hari sejak Minggu 8 | Minggu 17 |
| R5 | Model Groq di-deprecate di tengah jalan | Sedang | abstraksi LLM di `config.py`, 1 baris ganti model | Minggu 1 |
| R6 | Rate limit Groq saat evaluasi 5x run | Sedang | retry + backoff; cache hasil; jalankan bertahap | Minggu 19 |
| R7 | Multi-agent ternyata **lebih lambat** dari single-agent | Sedang | itu temuan sah — laporkan jujur, menangkan di 2 aspek lain (kualitas & kelengkapan) sesuai target Tabel 3.2 | Minggu 20 |
| R8 | Pembimbing lambat merespons draf | Sedang | kirim per bab, jangan tunggu lengkap | terus-menerus |
| R9 | Angka satu emiten bocor ke analisis emiten lain | **Tinggi** | metadata `ticker` wajib; `ticker` parameter wajib di retrieval; uji kontaminasi | Minggu 7 |
| R10 | Sistem hanya "hafal" format emiten pengembangan, gagal di emiten lain | **Tinggi** | prompt tanpa petunjuk khas emiten; uji emiten uji sejak Minggu 3 | Minggu 3 & 9 |
| R11 | Bank uji menyajikan Catatan KPMM / Entitas Induk dengan format berbeda | Sedang | **diterima (28-10-2026)**: BMRI baru diperiksa di Minggu 8, jadi perbedaan format baru ketahuan setelah pipeline dibangun. Perbaikan harus generik & dicatat (8.0e) | Minggu 8 |
| R12 | Pekerjaan tambahan (unggah via Telegram, multi-emiten) melebihi 24 minggu | Sedang | validasi dibatasi ke perbankan (27-10-2026); potong opsional: 3.9, 7.6, paralelisasi Market Observer di 15.1; BBRI dilepas lebih dulu | Minggu 8 |
| R15 | Satuan laporan berbeda antar emiten (jutaan / miliar Rupiah, ribuan USD) → saringan halaman "dalam jutaan rupiah" gagal, angka tidak sebanding | Sedang | penanda multi-satuan di 3.1; satuan dicatat di metadata (3.2); angka dinormalisasi oleh **kode**, bukan LLM | Minggu 2–3 |
| R16 | ~~Rasio emiten non-bank tidak punya definisi baku~~ | — | **Tidak berlaku lagi**: validasi dibatasi ke perbankan (SEOJK). Tetap disebut di Bab 3 sebagai alasan profil umum non-bank tidak divalidasi | — |
| R17 | Pengguna mengunggah emiten non-bank | Rendah | profil `general` (ROA, ROE) + label *belum divalidasi* di setiap jawaban; masuk saran | Minggu 11 |
| R18 | Bot Telegram standar hanya bisa mengunduh file **≤ 20 MB**; laporan tahunan bank 30–60 MB | **Tinggi** | Local Bot API Server via Docker (unduhan tanpa batas); cadangan: unggah ≤ 20 MB + script `add_document` untuk file besar | Minggu 16 |
| R19 | Bot Telegram publik → orang lain memakai bot dan menghabiskan kuota Groq | Sedang | allowlist user ID di `.env`; tolak semua chat di luar daftar | Minggu 16 |
| R14 | **ragas tidak terawat** (rilis terakhir Jan 2026) dan rusak dengan langchain-community ≥ 0.4.2 | Sedang | `langchain-community==0.4.1` dikunci; kalau sampai Minggu 17 kunci ini menghambat paket lain, pindahkan evaluasi RAGAS ke venv terpisah — evaluasi hanya butuh data tersimpan, bukan kode sistem | Minggu 17 |
| R13 | Laporan keuangan bank uji terbit **terpisah** dari laporan tahunan, atau **dwibahasa** | Sedang | **diterima (28-10-2026)**: dideteksi `inspect_pdf.py` di tugas 8.0a; kalau terjadi, saringan & desain unggah disesuaikan di Minggu 8 | Minggu 8 |

---

## Aturan yang bikin tidak molor

1. **Commit setiap hari**, sekecil apa pun.
2. **Simpan semua hasil mentah ke CSV**, jangan cuma di-print ke terminal. Minggu 21 akan butuh.
3. **Tulis Bab 4 sambil mengerjakan**, bukan setelah semua selesai. Tiap selesai eksperimen, langsung tulis 2 paragraf.
4. **Jangan tambah fitur setelah GATE 5.** Godaan "sekalian tambah reranker" = molor 3 minggu.
5. **Bimbingan rutin 2 minggu sekali**, bawa progres konkret.
6. **Kode berbahasa Inggris, teks boleh Indonesia** (keputusan 30-10-2026). Nama file kode, fungsi,
   variabel, konstanta, parameter, kunci data, dan nama tool agent → **Inggris**. Komentar,
   docstring, pesan yang dicetak, teks di Excel, dan dokumen di `docs/` → boleh Indonesia.
   Nama tool **wajib** Inggris juga karena alasan teknis (temuan uji 2.5b).
