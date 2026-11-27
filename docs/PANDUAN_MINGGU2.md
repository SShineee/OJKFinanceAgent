# Panduan Rinci Minggu 2 — Setup Environment

Total waktu: **±3–4 jam**, sebagian besar menunggu unduhan. Semua perintah dijalankan di
**PowerShell** dari folder `C:\TugasAkhir` (terminal VS Code: `` Ctrl+` ``).

Panduan ini disusun untuk laptop Anda — sudah dicek 26-10-2026:

| Komponen | Kondisi | Artinya |
|---|---|---|
| GPU | **NVIDIA RTX 3060 Laptop, 6 GB**, driver 610 | PyTorch **versi CUDA** wajib — parsing & embedding jauh lebih cepat |
| Python | 3.11, 3.12.0, 3.13 terpasang; **3.12.13** ditambahkan lewat `uv` (26-10-2026) | pakai **3.12.13** — 3.12.0 terlalu awal, lihat Langkah 2 |
| `uv` | 0.11 sudah terpasang | dipakai menggantikan `pip` — jauh lebih cepat |
| git | 2.41, identitas sudah diatur | siap |
| RAM / disk | 15,8 GB / 70 GB kosong | cukup |
| Execution policy, long paths | `RemoteSigned`, aktif | dua sumber error umum Windows sudah aman |

> **Koreksi atas roadmap.** Roadmap awal menulis *"Python 3.11, jangan 3.12/3.13"*. Itu sudah
> tidak berlaku: per Oktober 2026 seluruh paket proyek ini mendukung Python ≥ 3.10 (dicek
> langsung ke PyPI). **Pakai 3.12.13** — paling matang untuk PyTorch dan Docling. Bukan
> 3.12.0 bawaan sistem; alasannya di Langkah 2.

---

## Langkah 1 — Inisialisasi git (2.1) · 10 menit  ⏸ DITUNDA

> Ditunda atas keputusan 26-10-2026, bersama bagian git di Langkah 11. Saat dikerjakan,
> **jalankan Langkah 1 dulu** (bukti `.env` dan PDF diabaikan) sebelum commit apa pun.

```powershell
git init
git branch -M main
```

`.gitignore` sudah ada sejak Minggu 1. **Pastikan** file rahasia dan file besar benar-benar diabaikan:

```powershell
git check-ignore -v .env data/raw/bbca_2024.pdf
```

Harus muncul **dua baris** — satu per file — yang menunjuk ke aturan di `.gitignore`.
Kalau salah satunya tidak muncul, **berhenti** dan jangan lanjut ke commit.

```powershell
git status
```

Yang **boleh** muncul: `docs/`, `scripts/`, `src/`, `data/ground_truth.xlsx`, `.gitignore`,
`.env.example`, `requirements.in`.
Yang **tidak boleh** muncul: `.env`, file `.pdf`, `__pycache__`.

---

## Langkah 2 — Buat virtual environment (2.2) · 5 menit  ✅

```powershell
uv venv --python 3.12.13 .venv
.venv\Scripts\Activate.ps1
python --version
```

Harus keluar **`Python 3.12.13`**, dan prompt terminal diawali `(.venv)`.

> **Kenapa harus 3.12.13, bukan sekadar "3.12".** Python 3.12 yang terpasang di
> `C:\Program Files\Python312` adalah **3.12.0** — rilis paling awal dari seri 3.12.
> Paket `multiprocess` (dependensi `datasets` dan `ragas`) membutuhkan
> `RLock._recursion_count`, yang belum ada di 3.12.0. Gejalanya: error
> `AttributeError: '_thread.RLock' object has no attribute '_recursion_count'` setiap kali
> program selesai. Ditemukan 26-10-2026 saat Langkah 7.

**Kenapa wajib venv:** Python sistem Anda sudah punya `langchain 1.2` dan `langgraph 1.1`
terpasang global — versi lama. Tanpa venv, versi lama dan baru akan bentrok, dan error-nya
susah dilacak.

> Setiap membuka terminal baru, jalankan lagi `.venv\Scripts\Activate.ps1`.
> Tandanya sudah aktif: ada `(.venv)` di awal prompt.

---

## Langkah 3 — Struktur folder (2.3) · 5 menit  ✅ selesai 26-10-2026

```powershell
New-Item -ItemType Directory -Force src\ingest, src\retrieval, src\agents, src\baseline, eval\datasets, results | Out-Null
New-Item -ItemType File src\ingest\__init__.py, src\retrieval\__init__.py, src\agents\__init__.py, src\baseline\__init__.py, eval\__init__.py | Out-Null
New-Item -ItemType File results\.gitkeep, eval\datasets\.gitkeep | Out-Null
```

`.gitkeep` diperlukan karena git tidak menyimpan folder kosong.

Hasilnya:

```
C:\TugasAkhir\
├── data\        raw\  markdown\  chunks\  ground_truth.xlsx
├── docs\
├── eval\        datasets\
├── results\
├── scripts\     (perkakas Minggu 1–2)
└── src\         config.py  ingest\  retrieval\  agents\  baseline\
```

---

## Langkah 4 — PyTorch versi GPU (2.4a) · 10–20 menit  ✅ `2.14.1+cu126 True` (26-10-2026)

**Harus dipasang PERTAMA dan TERPISAH.** Kalau ikut terpasang lewat paket lain, yang terambil
adalah versi CPU dari PyPI dan GPU Anda tidak terpakai sama sekali.

```powershell
uv pip install torch --index-url https://download.pytorch.org/whl/cu126
```

Unduhan ±2,5–3 GB. Lalu cek:

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Harus keluar:

```
2.14.1+cu126 True NVIDIA GeForce RTX 3060 Laptop GPU
```

Kuncinya dua: akhiran **`+cu126`** (bukan `+cpu`) dan **`True`**.

> Kalau muncul `UserWarning: Failed to initialize NumPy: No module named 'numpy'` — **abaikan**.
> PyTorch dari index CUDA tidak ikut memasang NumPy; NumPy masuk di Langkah 5. Setelah
> Langkah 5, peringatan ini harus hilang — kalau masih muncul, berarti Langkah 5 belum lengkap.

> Kenapa `cu126`: untuk torch 2.14.1 di Python 3.12 Windows tersedia `cu126`, `cu130`, `cu132`.
> Driver 610 mendukung ketiganya; `cu126` yang paling lama diuji orang.

---

## Langkah 5 — Paket lainnya (2.4b) · 10–20 menit  ✅ 22 paket (28-10-2026)

```powershell
uv pip install -r requirements.in
```

`requirements.in` berisi 22 paket langsung yang dipakai proyek, dikelompokkan per minggu
pemakaiannya. Buka file itu kalau ingin tahu paket mana untuk apa.

> **Antarmuka berganti ke Telegram (27-10-2026).** `requirements.in` sekarang memuat
> `python-telegram-bot`, bukan `chainlit`. Kalau venv Anda **terlanjur** memasang Chainlit:
>
> ```powershell
> uv pip uninstall chainlit
> uv pip install -r requirements.in
> uv pip freeze | Out-File -Encoding ascii requirements.txt
> ```

> **Satu paket sengaja dikunci: `langchain-community==0.4.1`.** ragas 0.4.3 (rilis terakhir)
> mengimpor modul `chat_models.vertexai` yang dihapus di langchain-community 0.4.2, sehingga
> `import ragas` gagal. Alasan lengkapnya ada di bagian bawah `requirements.in`.

**Lalu cek lagi PyTorch** — ini sering terlewat:

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Harus masih `+cu126 True`. Kalau berubah jadi `+cpu` atau `False`, ada paket yang menimpa
PyTorch — lihat bagian *Kalau ada masalah* di bawah.

---

## Langkah 6 — Kunci versi (2.4c) · 1 menit  ✅ teks biasa, 279 baris (28-10-2026)

```powershell
uv pip freeze | Out-File -Encoding ascii requirements.txt
```

> **Jangan pakai `uv pip freeze > requirements.txt`.** Di Windows PowerShell 5.1 (yang
> terpasang di laptop Anda), tanda `>` menulis file dalam **UTF-16** — git menganggapnya file
> biner dan sebagian alat gagal membacanya. Ini sempat terjadi 26-10-2026 karena panduan versi
> awal memakai `>`. `Out-File -Encoding ascii` menghasilkan teks biasa (sudah diuji).

Dua file dengan peran berbeda:

| File | Isi | Dipakai untuk |
|---|---|---|
| `requirements.in` | 22 paket langsung, **tanpa versi** | dibaca manusia — paket apa & untuk apa |
| `requirements.txt` | ±200 paket termasuk dependensi, **versi persis** | memasang ulang environment yang identik |

`requirements.txt` inilah yang membuat hasil skripsi bisa direproduksi. API LangGraph dan
LangChain sering berubah — tanpa versi terkunci, kode yang jalan hari ini bisa rusak bulan depan.

---

## Langkah 7 — Periksa environment · 2 menit  ✅ ENVIRONMENT SIAP (28-10-2026)

```powershell
python scripts/check_environment.py
```

Script ini memeriksa versi Python, venv aktif, ke-22 paket bisa di-import, PyTorch memakai GPU,
dan API key terbaca. Tidak memanggil API, tidak mengunduh apa pun.

Harus berakhir dengan:

```
============================================================
  ENVIRONMENT SIAP
============================================================
```

Kalau ada baris `[!!]`, perbaiki dulu sebelum lanjut.

---

## Langkah 8 — Uji embedding di GPU · 10 menit  ✅ `cuda:0`, 2,12 GB VRAM (28-10-2026)

Sekalian mengunduh model BGE-M3 (±2,2 GB) supaya Minggu 3 tidak tertahan unduhan.

```powershell
python -c "from sentence_transformers import SentenceTransformer as S; m=S('BAAI/bge-m3', device='cuda'); e=m.encode(['laba bersih bank'], normalize_embeddings=True); print(e.shape, m.device)"
```

Harus keluar:

```
(1, 1024) cuda:0
```

`1024` = dimensi BGE-M3, `cuda:0` = berjalan di GPU. Model tersimpan di
`C:\Users\berli\.cache\huggingface`, jadi unduhan hanya sekali.

> Peringatan soal *symlinks* / *Developer Mode* dari `huggingface_hub` boleh diabaikan —
> hanya berarti cache memakai sedikit lebih banyak ruang disk.

---

## Langkah 9 — Editor memakai venv · 5 menit  ✅ (28-10-2026)

`Ctrl+Shift+P` → **Python: Select Interpreter** → pilih `.\.venv\Scripts\python.exe`.

Berlaku untuk VS Code maupun Kiro. Tanpa ini, editor memakai Python sistem — import akan bergaris merah dan tombol Run memakai
paket yang salah.

---

## Langkah 10 — Uji tool calling (2.5b) · 5 menit  ✅ LULUS 5/5 (28-10-2026)

```powershell
python scripts/check_tool_calling.py
```

Model diberi 3 tool lalu diminta menghitung ROE BCA 2024. Harus berakhir dengan:

```
==================================================================
  LULUS 5/5 (ambang 4)  ->  tool calling LAYAK dipakai
  rata-rata   : ...
  temuan      : retry nama tool 0x total; skala angka salah di 5/5 percobaan
==================================================================
```

Memakai ±13.500 token Groq (±2.700 per percobaan). Kalau kena *rate limit* (HTTP 429),
tunggu sebentar atau jalankan dengan 3 percobaan: `python scripts/check_tool_calling.py 3`.

### Yang sudah diketahui dari tes ini (dijalankan 26-10-2026)

Script ini sudah saya jalankan di environment sementara. Tiga temuan:

**1. `get_llm()` di config sempat rusak — sudah diperbaiki.** `langchain-groq` 1.x menolak
`reasoning_effort` yang dikirim lewat `model_kwargs`. Sekarang jadi parameter langsung.
Anda tidak perlu melakukan apa-apa — tapi ini alasan kenapa tes ini ada.

**2. Nama tool harus bahasa Inggris.** Dengan nama `hitung`, model **selalu** memanggil
`hitungan` — tool yang tidak ada — dan Groq menolak dengan error 400. Terjadi 15 dari 15 kali,
termasuk retry; retry tidak menolong karena `temperature=0` (input sama → output sama).
Dengan `calculator`: 5 dari 5 lulus tanpa retry. **Aturan untuk semua agent nanti: nama tool
bahasa Inggris, deskripsinya boleh bahasa Indonesia.**

**3. Format angka Indonesia salah dibaca — 5 dari 5.** `239.468,855` dibaca `239.468855`.
ROE-nya kebetulan tetap benar karena kedua angka sama-sama terbagi 1.000 dan saling
menghapus. Di sistem sungguhan itu tidak akan terjadi — laba dari Ikhtisar (miliar) dan
Tier 1 dari Catatan KPMM (juta) skalanya berbeda. **Ini masalah Minggu 9**, sudah dicatat
di roadmap.

---

## Langkah 11 — Commit pertama (2.6) · 10 menit  ⏸ bagian git DITUNDA · ✅ backup `data\raw\` (28-10-2026)

> Commit dan GitHub ditunda. **Backup data di luar git (di bawah) tetap dikerjakan** —
> itu tidak bergantung pada git, dan justru lebih penting selama belum ada commit.

```powershell
git add .
git status
```

**Periksa sekali lagi** daftar yang akan di-commit — tidak boleh ada `.env` atau `.pdf`. Lalu:

```powershell
git commit -m "Minggu 1-2: validasi rasio, konfigurasi, environment"
git ls-files | Select-String "\.env"
```

Perintah terakhir hanya boleh menampilkan **`.env.example`**. Kalau `.env` muncul, key Anda
sudah masuk riwayat git — beri tahu Claude sebelum push ke mana pun.

### Opsional: GitHub

Kalau mau disimpan di GitHub, buat repo **Private** (skripsi belum disidangkan — jangan
publik), lalu:

```powershell
git remote add origin https://github.com/<username>/<nama-repo>.git
git push -u origin main
```

### Wajib: backup data di luar git

`.gitignore` sengaja mengabaikan PDF dan hasil parsing, jadi **tidak ikut ke GitHub**.
Salin folder `data\raw\` ke Google Drive atau penyimpanan lain. Hasil parsing Minggu 3
(`data\markdown\`) nanti juga perlu di-backup dengan cara yang sama.

---

## Langkah 12 — Laporan bank uji (2.7) · 45–60 menit  ⏸ DIPINDAH KE MINGGU 8

> Keputusan 28-10-2026: seluruh pembangunan sistem memakai **PDF BCA saja**. BMRI baru diunduh
> di **Minggu 8 (tugas 8.0a)** sebagai data uji. Langkah di bawah tetap berlaku — dikerjakan
> saat itu, bukan sekarang. **Minggu 2 selesai setelah Langkah 11.**

Validasi skripsi dibatasi ke **sektor perbankan** (keputusan final 27-10-2026): BBCA untuk
pengembangan, **BMRI untuk uji**. Langkah ini memastikan pipeline Minggu 3 tidak dirancang
khusus untuk BBCA.

### a. Unduh PDF

Laporan Tahunan **Bank Mandiri (BMRI) 2023, 2024, 2025**. BBRI (BRI) opsional.

- **idx.co.id** → Perusahaan Tercatat → Laporan Keuangan & Tahunan → cari kode **BMRI**
- atau situs *Investor Relations* Bank Mandiri

**Nama file = kode saham huruf kecil + tahun**, sama seperti BCA yang sekarang bernama
`bbca_2024.pdf`:

```
bmri_2023.pdf   bmri_2024.pdf   bmri_2025.pdf
```

Pastikan yang diunduh **Laporan Tahunan** (*Annual Report*), bukan Laporan Keberlanjutan.

> Kenapa kode saham, bukan nama pendek seperti `mandiri`: sistem tetap menerima emiten mana
> pun, dan untuk 900-an emiten nama pendek tidak punya aturan pasti. Kode saham unik, resmi,
> dan sama dengan yang dipakai idx.co.id.

### b. Periksa

```powershell
python scripts/inspect_pdf.py
```

Memproses semua PDF di `data\raw\` (6 file), ±1–2 menit per file.

### c. Yang harus Anda perhatikan

| Baris di output | Normal (seperti BBCA) | Kalau berbeda |
|---|---|---|
| `Jenis PDF` | TEXT-BASED | hasil scan → Docling butuh OCR, Minggu 3 jauh lebih lama |
| `Penanda tabel keuangan` | ±200–250 halaman | **kalau hanya puluhan**: laporan keuangan audited mungkin **terbit terpisah** — unduh juga file Laporan Keuangan-nya |
| `satuan: jutaan / miliar / Dolar AS` | jutaan **jauh mendominasi** (BBCA: jutaan 240 hal, miliar 17, Dolar 9) | kalau satuan dominannya bukan jutaan Rupiah, **laporkan** — saringan halaman Minggu 3 harus menyesuaikan |
| `KPMM / CAR / ATMR` | ada, puluhan halaman | Tier 1 & ATMR tidak bisa diambil → CAR & ROE bermasalah |
| `Lap. Entitas Induk (basis Bank)` | ±8–10 halaman | kredit & DPK basis bank tidak ada → NPL & LDR bermasalah |
| `Fn rasio 'induk perusahaan saja'` | 3–4 halaman | basis rasio resmi BMRI belum tentu sama dengan BBCA |

Baris `Aset lancar` dan `Pendapatan` boleh diabaikan — itu untuk emiten non-bank, dan pada
bank memang hampir 0.

Tiga kemungkinan yang **wajib** dilaporkan ke Claude kalau terjadi:

1. **Laporan keuangan terpisah dari laporan tahunan** → pipeline harus menerima dua file per
   tahun; desain unggah Minggu 16 berubah.
2. **Laporan dwibahasa** — `in millions of rupiah` muncul hampir sebanyak `dalam jutaan rupiah`
   → setiap tabel tercetak dua kali; saringan halaman Minggu 3 harus menanganinya.
3. **Satuan bukan jutaan Rupiah** → saringan & normalisasi angka harus menyesuaikan.

Tempel output `inspect_pdf.py` ke Claude — lebih cepat daripada menafsirkannya sendiri.

> **Catat ukuran file BMRI.** Bot Telegram standar hanya bisa menerima PDF ≤ 20 MB, dan
> `bbca_2023.pdf` sudah 55,6 MB. Ukuran laporan BMRI ikut menentukan seberapa wajib
> Local Bot API Server di Minggu 16 (risiko R18).

---

## ~~Langkah 13 — Validasi profil rasio non-keuangan pada TLKM (2.8)~~ — dibatalkan

Validasi skripsi dibatasi ke sektor perbankan (27-10-2026). Emiten non-bank tetap bisa
diunggah ke bot, tapi dianalisis dengan profil umum (ROA, ROE) berlabel *belum divalidasi*.
Validasi sektor non-keuangan masuk saran penelitian.

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (di laptop Anda seharusnya sudah aman) |
| PyTorch jadi `+cpu` / `cuda False` setelah langkah 5 | ada paket yang menimpa torch | `uv pip install torch --index-url https://download.pytorch.org/whl/cu126 --reinstall-package torch`, lalu cek lagi |
| `check_environment.py`: puluhan paket **BELUM TERPASANG** + *venv aktif: TIDAK* | venv belum diaktifkan — `python` memanggil Python sistem. Tandanya: prompt **tanpa** `(.venv)` | `.venv\Scripts\Activate.ps1`, lalu ulangi. Catatan: perintah `uv pip ...` tetap masuk ke `.venv` walau tidak diaktifkan (uv mencarinya sendiri) — yang butuh aktivasi adalah `python` |
| `uv: command not found` di terminal baru | PATH belum termuat | tutup–buka VS Code |
| `check_environment.py`: paket "gagal di-import" | versi bentrok | kirim output-nya ke Claude |
| `ragas` gagal: `No module named 'langchain_community.chat_models.vertexai'` | langchain-community ≥ 0.4.2 | pastikan `requirements.in` memuat `langchain-community==0.4.1`, lalu `uv pip install -r requirements.in` |
| `Remove-Item ... .venv\Scripts\python.exe: Access to the path is denied` | language server ekstensi Python di editor masih memakai python.exe venv | tutup editor lalu hapus dari PowerShell biasa; atau cari prosesnya: `Get-CimInstance Win32_Process \| ? CommandLine -like '*TugasAkhir\.venv*'` lalu `Stop-Process -Id <PID>` (aman — editor menyalakannya lagi) |
| `AttributeError: '_thread.RLock' object has no attribute '_recursion_count'` saat program selesai | venv memakai Python 3.12.0 | buat ulang venv dengan 3.12.13 — lihat Langkah 2 |
| `check_tool_calling.py`: HTTP 429 | rate limit Groq | tunggu 1 menit, atau jalankan dengan argumen `3` |
| `check_tool_calling.py`: LULUS di bawah ambang | perilaku model berubah | **jangan lanjut ke Minggu 3** — kirim output ke Claude |
| Unduhan BGE-M3 terputus | koneksi | jalankan ulang perintah langkah 8 — unduhan melanjutkan dari cache |

### Memasang ulang environment di komputer lain

`requirements.txt` memuat `torch==2.14.1+cu126`, yang tidak ada di PyPI biasa. Jadi:

```powershell
uv venv --python 3.12.13 .venv
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
```

---

## Minggu 2 selesai kalau

- [ ] ⏸ `git check-ignore` membuktikan `.env` dan PDF diabaikan *(git ditunda)*
- [x] `python scripts/check_environment.py` → **ENVIRONMENT SIAP**
- [x] PyTorch `+cu126` dan `cuda True` — dicek **setelah** semua paket terpasang
- [x] BGE-M3 → `cuda:0`, dimensi 1024
- [x] `python scripts/check_tool_calling.py` → **LULUS** ≥ ambang
- [x] `requirements.txt` dibuat ulang (teks biasa) — *commit-nya ditunda bersama git*
- [x] `data\raw\` di-backup di luar git


Lalu **bimbingan** sebelum Minggu 3 — lihat pengecualian GATE 1 di `docs/ROADMAP.md`.

---

## Lembar hasil — isi sambil jalan

| Item | Hasil |
|---|---|
| Versi torch | `2.14.1+cu126` |
| `torch.cuda.is_available()` setelah langkah 5 | `True` — RTX 3060 Laptop, 6,0 GB |
| BGE-M3 shape & device | `(2, 1024)` `cuda:0`, VRAM terpakai 2,12 GB |
| `check_tool_calling.py` — LULUS | **5 / 5**, retry nama tool 0x, skala angka salah 5/5 (→ Minggu 9) |
| `check_tool_calling.py` — rata-rata token per tugas | 2.527 token, 5,3 detik |
| Commit pertama (hash 7 karakter: `git log --oneline -1`) | ⏸ git ditunda |

**Bank uji (Langkah 12 — diisi di Minggu 8, 26-11-2026):**

| Kode | Tahun | Ukuran (MB) | Hal. | Text/Scan | Satuan dominan | Penanda tabel | KPMM | Entitas Induk | Fn "induk saja" | LK terpisah? | Dwibahasa? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BMRI | 2023 | 23,8 | 1.514 | Text-based | `million_idr` (543 hal.) | 563 hal. tersaring (37%) | hal. 1425–1426 | hal. 1500–1513 | Ya — `RASIO KEUANGAN (BANK ONLY)` (hal. 36–37) | Tidak (hal. 1070–1513) | Ya (ID+EN di LK) |
| BMRI | 2024 | 21,1 | 1.726 | Text-based | `million_idr` (616 hal.) | 633 hal. tersaring (37%) | hal. 1700–1701 | hal. 1712–1725 | Ya — `RASIO KEUANGAN (BANK ONLY)` (hal. 34–35) | Tidak (hal. 1282–1725) | Ya (ID+EN di LK) |
| BMRI | 2025 | 22,9 | 1.467 | Text-based | `million_idr` (579 hal.) | 594 hal. tersaring (40%) | hal. 1431–1433 | hal. 1454–1466 | Ya — `RASIO KEUANGAN (BANK ONLY)` (hal. 39–40) | Tidak (hal. 951–1466) | Ya (ID+EN di LK) |
| TLKM *(non-bank)* | 2024 | 21,0 | 588 | Text-based | `billion_idr` (116 hal.) | 140 hal. tersaring (24%, tak diindeks) | Tidak ada (0/6 bank) | — | — (`non_financial`, *belum divalidasi*) | Tidak (hal. 438–584) | Inggris (IDX/NYSE) |
