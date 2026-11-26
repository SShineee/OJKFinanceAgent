# Panduan Rinci Minggu 5 — Chunking: dari hasil Docling ke potongan siap-indeks

Tujuan minggu ini: memotong hasil parse Minggu 3 (`data\markdown\<kode>_<tahun>.json`) menjadi
**chunk** yang siap di-embed di Minggu 6. Setiap chunk harus:

- membawa **nomor halaman asli**, karena Extraction Agent wajib menyebut sumber setiap angka;
- membawa **kode saham, sektor, tahun, dan satuan**, supaya angka BBCA tidak bocor ke emiten lain
  dan angka miliar tidak tertukar dengan angka juta;
- **tidak memotong tabel di tengah baris**, dan setiap potongan tabel tetap membawa judul kolomnya.

Perkiraan kerja: **5–6 hari**. Semua kode dijalankan dari venv (`(.venv)` harus muncul di prompt).

---

## Status gerbang

- **GATE 2 lulus** (15-11-2026): tabel terbaca benar, ketiga laporan terdeteksi bank, hasil parse
  sudah di-backup.
- Bimbingan belum dilakukan. Minggu 5 **tidak bergantung** pada keputusan #5 (ruang lingkup).
- **Keputusan 5.A disetujui** (15-11-2026): ukuran chunk maks. **1024 token**. Batas Groq akun
  sudah dicek (Langkah 0 ✅).
- ✅ **MINGGU 5 SELESAI (15-11-2026).**
  - Langkah 0–7 selesai; `check_chunks.py` dan `check_fix_tables.py` LULUS;
    `check_parse_output.py` 76/76.
  - Hasilnya **1.552 chunk diindeks** (514 / 540 / 498) di `data\chunks\`.
  - Backup `data\chunks\` ke Google Drive selesai (15-11-2026). **Semua butir gerbang lulus.**

---

## Hasil pengecekan sebelum panduan ini ditulis (15-11-2026)

Rancangan di bawah sudah diuji pada ketiga hasil parse BCA, dengan docling-core 2.104.0 dan
tokenizer BGE-M3 yang terpasang. Beberapa rencana di roadmap ternyata **tidak cocok** dengan data.

| Yang dicek | Hasil | Akibatnya |
|---|---|---|
| Level heading Docling | **805 dari 805** `section_header` (`bbca_2024`) ada di level 1. Tidak ada hierarki. | `MarkdownHeaderTextSplitter` pada `#/##/###` (rencana 5.1) tidak berguna. `header_path` = judul terdekat. |
| Header/footer halaman | 1.160 elemen ditandai *furniture* | otomatis **tidak masuk** chunk, jadi judul navigasi tidak mencemari isi |
| `HybridChunker` (docling-core) | tersedia; memotong mengikuti struktur dokumen, menghitung token dengan tokenizer BGE-M3, dan **mengulang header tabel** di setiap potongan | dipakai sebagai pemotong utama |
| Format tabel: triplet (bawaan) vs Markdown | triplet **2,2× lebih boros** (383.627 vs 172.471 token per laporan); satu tabel triplet 9.639 token, **melebihi batas BGE-M3 (8.192)** | tabel ditulis sebagai **Markdown**; judul kolomnya sudah gabungan, mis. `2024 - Bank` |
| Markdown ringkas (`compact_tables`) | spasi pengisi kolom dibuang: **−13% token** gpt-oss (o200k), −2% token BGE-M3 | dipakai, karena menghemat kuota Groq |
| Chunk < 50 token (`bbca_2024`, maks. 2048) | 184 chunk, **0 berisi tabel**: 162 boilerplate berulang ("(Dalam jutaan Rupiah, kecuali dinyatakan lain)" 156×) + **22 paragraf unik yang bermakna** (mis. hal 701 "Rasio Kredit Usaha Kecil") | aturan roadmap "buang chunk < 50 token" **diganti** dengan "buang teks yang berulang ≥ 3×" |
| Satuan per halaman | 238/261, 239/262, 207/230 halaman tersaring punya penanda satuan; **0 halaman campur**; Ikhtisar 2025 hal 15 = miliar, laporan keuangan = juta | setiap chunk menyimpan **satuan halamannya sendiri**. ✅ Langkah 4: 257 / 257 / 228 halaman, setelah penanda tanpa "dalam" dan warisan satuan bagian kiri tabel dua halaman |
| Sel berisi dua angka, pola 1 (pihak berelasi / pihak ketiga) | prototipe pemecah baris **berhasil** pada hal 704 `bbca_2024` | Langkah 1a |
| Sel berisi dua angka, pola 2 | **bukan satu pola**: dua baris cetak digabung (`Beban syariah Jumlah beban…`), kolom Rupiah/USD digabung, subtotal tanpa label | Langkah 1b — ✅ dibangun & diuji (15-11-2026): 19 / 19 / 5 baris diperbaiki, sisanya ditandai |
| Koordinat sel tabel | ada (origin kiri-atas), tapi kotaknya **tidak selalu** pas dengan teksnya (hal 704: 13 pt untuk dua baris; hal 149 `bbca_2025`: ujung kata terpotong) | pola 2 memberi setiap kata ke kotak sel terdekat, lalu mengecek silang isinya dengan sel Docling |
| 16 tabel tanpa label baris (per laporan) | hanya **5 dari 16** (`bbca_2024`) yang jumlah barisnya sama persis dengan tabel di halaman kirinya | penggabungan otomatis tidak aman; ditandai dan **tidak diindeks** (Langkah 2). ✅ Dikerjakan 15-11-2026: daftarnya ternyata **18 / 17 / 17**, ditemukan lewat posisi tabel yang menempel tepi kiri kertas |
| Batas Groq untuk `gpt-oss-120b` | dokumentasi Groq (dibaca 15-11-2026): **30 permintaan/menit, 8K token/menit, 200K token/hari**; **sama persis** di akun Anda (Langkah 0) | ukuran chunk ikut dibatasi (Keputusan 5.A) |

---

## Keputusan 5.A — ukuran chunk: 1024 (disarankan) atau 2048 token

> ✅ **DISETUJUI 15-11-2026: 1024 token.** Batas akun = 8K token/menit (Langkah 0), jadi alasan di
> bawah berlaku untuk akun Anda.

Diuji pada ketiga laporan (Markdown ringkas):

| | **maks. 1024** (disarankan) | maks. 2048 |
|---|---|---|
| Jumlah chunk | 668 / 722 / 677 | 585 / 632 / 592 *(belum ringkas)* |
| Tabel yang terbelah | 46 / 50 / 44 — **header diulang di setiap potongan** (52/52 dicek) | **0** |
| Tabel kunci yang terbelah | rasio resmi, neraca, laba rugi konsolidasian. KPMM dan Entitas Induk **utuh**. | tidak ada |
| Ukuran chunk (token gpt-oss) | median 220–270, p90 ±930, maks. 1.263 | p90 tabel ±1.550 BGE, maks. ±2.000 |
| 5 chunk teratas (TOP_K_FINAL) ke LLM | ±4.650 token pada p90 | bisa ±10.000 token, **melebihi 8K token/menit** |

**Saran: 1024.** Dengan batas 8K token per menit, lima chunk 2048 token sudah melampaui kuota
satu menit, sebelum prompt dan token penalaran dihitung. Pada 1024, tabel besar dipecah **per
baris**, dan setiap potongan diawali header kolom yang sama, jadi potongannya tetap terbaca utuh.

**Akibatnya, kriteria lolos roadmap "0 tabel keuangan utama yang terpotong" diartikan ulang
menjadi:** tidak ada potongan tabel yang kehilangan header kolom, dan tidak ada baris yang terpotong
di tengah. Kalau Anda memilih 2048, cukup ubah satu konstanta (`CHUNK_MAX_TOKENS`), lalu Minggu 7/9
harus mengurangi jumlah chunk yang dikirim ke LLM.

---

## Langkah 0 — Cek batas Groq akun Anda · 5 menit · ✅ SELESAI (15-11-2026)

Buka **console.groq.com/settings/limits** dan catat angka `openai/gpt-oss-120b` (permintaan per
menit, token per menit, token per hari) di lembar hasil. Tabel di dokumentasi berlabel "base
limits"; batas akun Anda bisa berbeda. Kalau token per menit ternyata jauh di atas 8K, Keputusan
5.A boleh dipertimbangkan ulang.

**Hasil (tangkapan layar halaman limits, 15-11-2026):**

| Model | Permintaan/menit | Permintaan/hari | Token/menit | Token/hari |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | 1K | **8K** | **200K** |
| `openai/gpt-oss-20b` | 30 | 1K | 8K | 200K |

Sama dengan dokumentasi, jadi Keputusan 5.A tidak berubah. Tabel itu mencantumkan batas **per
model**. Kalau Minggu 7/9 kekurangan kuota, tugas LLM yang ringan (mis. penyaring relevansi berita, 13.2) bisa
dipindah ke `gpt-oss-20b`. Ini baru kemungkinan dan **belum diputuskan**: pastikan dulu di
console bahwa kuota kedua model memang terpisah.

> **Batas 1K permintaan per hari** juga perlu diingat: satu pertanyaan multi-agent memakai
> beberapa panggilan LLM (empat agen, ditambah tool call berulang di dalam tiap agen), jadi jumlah pertanyaan
> per hari dibatasi oleh **mana yang habis lebih dulu**, permintaan atau token.

> **Batas 200K token per hari juga penting untuk evaluasi** (Minggu 17–20): satu tugas uji tool
> calling memakai ±2.500 token (Minggu 2), jadi satu hari hanya cukup untuk puluhan pertanyaan
> multi-agent. Catat ini sekarang supaya jadwal evaluasi tidak kaget.

---

## Langkah 1 — Perbaiki sel berisi dua angka (5.1) · ✅ SELESAI (15-11-2026)

**File:** `src/ingest/fix_tables.py` · **Uji:** `scripts/check_fix_tables.py` (LULUS) dan
`scripts/check_parse_output.py` (76/76 tepat)

Perbaikan dijalankan **di memori**, pada `DoclingDocument` yang dimuat dari `.json`, sebelum
chunking. File `.json` di `data\markdown\` **tidak diubah**: itu sumber kebenaran, dan sudah
di-backup. Pemakaian di Langkah 3:

```python
from src.ingest.fix_tables import load_fixed, merged_rows
doc, report = load_fixed(2024)   # muat .json + perbaiki tabel; report = statistik + baris yang ditandai
```

### Hasil

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Sel berisi ≥ 2 angka (hitungan Minggu 3) | 152 → **110** | 101 → **58** | 111 → **104** |
| Pola 1 diperbaiki (pihak berelasi / ketiga) | 4 baris (**sisa 0**) | 5 baris (**sisa 0**) | 0 (memang tidak ada) |
| Pola 2 diperbaiki (posisi teks PDF) | 19 baris | 19 baris | 5 baris |
| Pola 3 digabung (satu baris cetak dibelah, Langkah 1d) | 2 pasang | 4 pasang | 1 pasang |
| Ditandai, tidak diperbaiki | 57 baris | 28 baris | 59 baris |
| Baris ditandai di halaman sumber ground truth | **0** | **0** | **0** |
| `check_parse_output.py` | 76/76 tepat (semula 73 + 3 cacat) | | |

Baris yang ditandai terkumpul di beberapa jenis tabel yang **struktur Docling-nya rusak berat**:

- **laporan keuangan publikasi**: hal 745–746 / 711–712 / 602–603, sebanyak 28 / 14 / 23 baris
  (beberapa baris cetak dilebur, label terbelah ke kolom lain);
- **tabel jatuh tempo**: hal 712 / 677 / 569;
- **tabel Pilar 3**: hal 143–208, dua kolom cetak yang digabung Docling menjadi satu kolom
  (`390.380.193 2.856.011` sejajar dalam satu garis);
- **laporan perubahan ekuitas yang dicetak menyamping**: hal 545 / 598.

Ini sesuai rancangan: **lebih baik ditandai daripada ditebak.** Satu angka yang dipasangkan dengan
label yang salah lebih berbahaya daripada sel yang jelas bertanda.

### 1a. Pola 1 — sub-baris "Pihak berelasi / Pihak ketiga"

Aturannya: kalau label baris memuat k sub-label dan **setiap** sel berangka berisi tepat k angka,
baris itu dipecah menjadi k baris. Teks sebelum sub-label pertama ikut di setiap baris baru,
misalnya `Kredit yang diberikan - … sebesar Rp 32.382.006 … - Pihak berelasi`. Kalimat CKPN
sengaja dibawa, karena dibutuhkan untuk menghitung kredit bruto. Sel tanpa angka (nomor Catatan
`2g,2m,12`) ikut baris pertama.

### 1b. Pola 2 — dua baris cetak dalam satu baris Docling

Bentuknya beragam:

- dua baris yang digabung (`Lain-lain` + `Jumlah beban operasional lainnya`);
- subtotal tanpa label (`238.886 297.244`);
- sub-baris `Rupiah / USD`;
- angka milik baris tetangga yang "nyasar" (`521.315` milik baris 23 masuk sel baris 24).

Cara kerjanya:

1. **Teks dibaca dengan docling-parse**, pembaca yang sama dengan yang dipakai Docling saat parse,
   sehingga hurufnya identik dengan isi sel. *pypdfium2 tidak dipakai:* di beberapa halaman BCA
   (mis. hal 569/577 `bbca_2025`) ia kehilangan huruf, misalnya `Obli i b di i` untuk "Obligasi
   subordinasi" dan `(9296)` untuk `(9.296)`.
2. Setiap kata di rentang tinggi baris itu diberikan ke **sel terdekat** di baris r−1, r, atau r+1.
   Kotak sel Docling kadang memotong ujung teks (`Ban` untuk "Bank"), jadi dipakai kotak yang
   paling bertumpuk, dengan toleransi 4 pt.
3. **Cek silang:** teks PDF di setiap sel harus sama persis dengan isi sel Docling (angka per
   angka; huruf per huruf untuk label). Kalau tidak sama, baris **ditandai**.
4. Kata dikelompokkan per **garis cetak**. Garis yang juga berisi kata baris tetangga adalah milik
   tetangga itu. **Angka** di garis tersebut dipindah ke sel tetangga yang **kosong**; selain itu
   baris ditandai.
5. Setiap garis berangka menjadi satu baris baru. Garis label tanpa angka ikut garis berangka **di
   bawahnya**, karena laporan BCA mencetak angka sejajar garis label terakhir. Nomor butir (`3.`)
   dihitung sebagai label, bukan angka.

Ditandai (tabel **tidak diubah**) bila:

- teks PDF tidak cocok dengan sel;
- dua angka sejajar dalam satu sel (kolom cetak yang digabung);
- teks berputar;
- label tersisa di bawah angka terakhir (itu awal label baris berikutnya);
- ada sel yang merentang beberapa baris;
- baris itu header.

### 1c. Yang tidak bisa diperbaiki → ditandai

`merged_rows(table)` mengembalikan baris yang masih berisi sel dua angka. Chunk yang memuat baris
seperti itu diberi metadata `merged_cells = True` (Langkah 4). Extraction Agent (Minggu 9) diberi
aturan: angka dari chunk bertanda ini harus dicek ulang ke tabel lain (mis. laporan keuangan
utama), atau tidak dipakai.

### 1d. Pola 3 — satu baris cetak dibelah menjadi dua baris Docling *(ditambahkan 15-11-2026, Langkah 6)*

Ini kebalikan pola 2, dan ditemukan saat inspeksi manual neraca konsolidasian `bbca_2024`:

- hal 541: `| JUMLAH LIABILITAS |  |  | 1.157.675.545 |`, lalu `|  |  | 1.177.403.108 |  |`.
  Angka 2024 ada di baris tanpa label;
- hal 540: `|  |  | 1.449.301.328 | 1.408.107.010 |`, lalu `| JUMLAH ASET |  |  |  |`.

`merge_split_row` menggabungkan dua baris berurutan kalau:

- (a) baris atas = label + sebagian angka, dan baris bawah = tanpa label + angka di kolom yang
  kosong di baris atas; **atau** (b) baris atas = angka tanpa label, dan baris bawah = label tanpa
  angka;
- **dan** kotak label tumpang tindih secara vertikal dengan **setiap** kotak angka pasangannya di
  halaman PDF.

Syarat sejajar itu penting. Bentuk yang sama jauh lebih sering berarti dua baris cetak yang memang
berbeda, misalnya subtotal tanpa label lalu judul bagian berikutnya: ada 72 / 75 / 40 kandidat,
dan hanya **2 / 4 / 1** yang sejajar.

- **Cek visual:** ketujuh penggabungan benar menurut render PDF.
  - Selain JUMLAH ASET dan JUMLAH LIABILITAS: "Posisi bersih" hal 687 `bbca_2024`, "Estimasi
    kerugian komitmen dan kontinjensi" hal 716 `bbca_2023`, dan 3 baris Pilar 3.
  - Pola 3 dijalankan sebelum pola 1/2 di setiap tabel, supaya nomor baris yang dicatat pola 1/2
    tidak bergeser.
- **Bug yang tertangkap uji:**
  - `_replace_row(table, r, [])` (hapus baris) ikut membuang baris **di bawah** baris yang dihapus,
    karena barisnya digeser dulu baru dibuang.
  - Cek "tidak ada huruf/angka yang hilang" langsung gagal di 5 tabel. JUMLAH ASET lolos hanya karena
    itu baris terakhir tabelnya.
  - Urutannya diperbaiki (buang dulu, baru geser), dan ditambah uji regresi "baris di bawahnya tetap
    ada". Uji itu gagal kalau bug lama disuntikkan kembali.
- **Uji:** `check_fix_tables.py` kini mencakup:
  - jumlah 2 / 4 / 1;
  - cek titik JUMLAH ASET dan JUMLAH LIABILITAS;
  - idempoten;
  - 6 uji sintetis: 3a dan 3b sejajar digabung; tidak sejajar, kolom yang sama terisi di kedua baris,
    dan baris bawah bukan angka tidak digabung; baris di bawahnya tetap ada.

  `check_parse_output.py` tetap 76/76.

### Uji Langkah 1 (semua ✅)

- `scripts/check_fix_tables.py` — **LULUS**. Isinya:
  - tidak ada huruf atau angka yang hilang, berganda, atau pindah kolom di 302 / 302 / 298 tabel;
  - sisa sel dua angka = persis baris yang ditandai;
  - pola 1 tersisa 0;
  - idempoten (perbaikan kedua tidak mengubah apa pun);
  - 9 cek titik yang sudah dicek visual;
  - 6 uji negatif sintetis (tabel tidak berubah bila syarat gagal).
  Ringkasan per laporan, termasuk daftar baris yang ditandai beserta alasannya, ada di
  `results/fix_tables.json`.
- **Uji mutasi:** bug yang sengaja disisipkan tertangkap semua. Bug yang diuji: membuang baris
  baru, mematikan cek silang, dan menghitung nomor butir sebagai angka.
- `scripts/check_parse_output.py` diperbarui. Sekarang ia memeriksa dokumen setelah perbaikan dan
  menjumlahkan sub-baris kredit "Pihak berelasi" + "Pihak ketiga". Hasilnya **76/76 tepat**.
  Dengan `--raw` hasilnya tetap 73 + 3 cacat seperti Minggu 3, sebagai pembanding.
- **Cek visual 20 baris pola 2** dengan render halaman PDF: **20/20 benar**.
  - `bbca_2023`: hal 170, 196, 199, 223, 578, 669, 673, 696, 745
  - `bbca_2024`: hal 157, 542, 614, 626, 643, 687, 711, 712 (2 baris)
  - `bbca_2025`: hal 131, 602

  Pola 1 hal 704 juga dicek. Dalam proses ini dua kesalahan rancangan awal ditemukan lalu
  ditutup sebelum hasil akhir: tabel menyamping hal 545 sempat "dipecah" berdasarkan posisi y,
  dan label "Beban umum dan administrasi" sempat tertempel ke angka milik "Lain-lain" (hal 578
  `bbca_2023`).

---

## Langkah 2 — Tandai tabel tanpa label baris (5.1) · ✅ SELESAI (15-11-2026)

**File:** `src/ingest/fix_tables.py` (`is_unlabeled`, `unlabeled_tables`) · **Uji:**
`scripts/check_fix_tables.py` (LULUS)

Ini tabel Pilar 3 yang lebar, tercetak melintasi **dua halaman berhadapan**. Label baris dan kolom
pertama ada di halaman kiri, sisa kolomnya di halaman kanan. Docling membacanya sebagai dua tabel
terpisah, sehingga tabel halaman kanan berisi angka yang tidak jelas milik baris apa.

`load_fixed()` sekarang juga mencatat tabel-tabel ini:

```python
doc, report = load_fixed(2024)
report.unlabeled          # [{page, subset_page, table, shape, left_parts}, ...]
report.unlabeled_refs()   # {"#/tables/9", ...} -> dipakai Langkah 3
```

### Hasil

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Tabel tanpa label baris | **18** | **17** | **17** |
| Halaman | 157, 159, 185, 187, 189, 191, 203 (2 tabel), 207, 209, 213, 215, 223, 227, 229, 231, 233, 237 | 155, 157, 183, 185, 187, 189, 201 (2 tabel), 205, 207, 211, 221, 225, 227, 229, 231, 235 | 110, 112, 130, 132, 134, 136, 148 (2 tabel), 152, 154, 158, 168, 172, 174, 176, 178, 182 |
| Punya bagian kiri di halaman sebelumnya | semua | semua | semua |
| Di halaman sumber ground truth | 0 | 0 | 0 |
| Baris "ditandai" Langkah 1 yang ada di tabel ini | 1 | 3 | 6 |

### Definisi Minggu 3 diganti

Definisi audit Minggu 3 ("≥ 5 baris berangka, < 20% di antaranya berhuruf") **keliru di 5 tabel
per laporan**. Ini ditemukan dengan render PDF:

- **Salah tandai (2 tabel):** tabel CR5 hal 210–211 / 208–209 / 155–156 adalah tabel **utuh**.
  Label barisnya kolom "Bobot Risiko" (`< 40%`, `40% - 70%`, `75%`), yang tidak memuat huruf.
- **Terlewat (3 tabel):**
  - **bagian kanan CR4/CR5:** hal 207, 209 / 205, 207 / 152, 154. Judul kolomnya (`Lainnya`,
    `Tagihan Bersih Setelah FKK`) dilebur Docling ke baris data, sehingga barisnya terhitung
    "berhuruf" (14 dari 25);
  - **CCR3 kolom f–l:** hal 213 / 211 / 158. Rasionya tepat 20%, jadi tidak di bawah ambang.
- **`bbca_2023` saja:** sekuritisasi kolom j–q hal 215. Isinya `-` semua, dan satu-satunya baris
  "berangka" adalah judul kolom `1.250%`.

Ciri yang dipakai sekarang **geometris**. Tabel dua halaman dicetak sampai ke lipatan kertas, jadi:

1. **kotak bagian kanannya menempel tepi kiri kertas.** Di BCA jaraknya 0–0,3 pt, sedangkan tabel
   biasa ≥ 20 pt. Batasnya `PAGE_EDGE = 3` pt.
2. **Pengaman:** kalau bagian kanan ternyata mengulang label barisnya (≥ 50% baris angka, di luar
   baris judul kolom, diawali teks berhuruf), tabel itu **tidak** ditandai.

   Ukurannya di 52 tabel tepi kiri BCA: maksimal 1 dari 26 baris. Di tabel biasa mediannya
   85–100%.

Bagian kirinya selalu ada: tabel di halaman sebelumnya yang menempel tepi **kanan** kertas. Ini
dicatat sebagai `left_parts`, dan dipakai sebagai bukti di uji, bukan sebagai syarat. Kalau
halaman kirinya tidak lolos penyaring, bagian kanannya tetap tanpa label.

### Cara mengeluarkannya: per item, bukan per chunk

Rancangan awal adalah menandai **chunk** yang berisi tabel ini sebagai `excluded`. Ternyata itu
salah. `HybridChunker` menggabungkan potongan kecil yang berjudul sama, sehingga **6–11 chunk per
laporan** berisi tabel tanpa label **bersama** isi lain:

- bagian kirinya yang berlabel, misalnya tabel 59 + 60 + 61;
- paragraf dan daftar butir;
- caption tabel tetangga.

Kalau chunk-nya dibuang utuh, isi yang baik ikut hilang.

Jadi tabel ini dikeluarkan **sebelum dipotong**, lewat `get_excluded_refs()` milik serializer
(lihat Langkah 3). Dokumen tidak diubah, dan nomor rujukan `#/tables/N` tidak bergeser.
`delete_items` sengaja tidak dipakai, karena menomori ulang tabel.

Hasil prototipe:

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Chunk sebelum → sesudah | 672 → 656 | 724 → 705 | 678 → 658 |
| Tabel tanpa label yang masih ada di chunk | 0 | 0 | 0 |
| Item lain yang ikut hilang | 0 | 0 | 0 |
| Angka unik tabel ini yang muncul di teks chunk | 0 | 0 | 0 |

Untuk audit, setiap tabel ini tetap ditulis ke `.jsonl` sebagai **record tersendiri** (satu
record per tabel), dengan `excluded = "tabel tanpa label baris"`. Record ini **tidak diindeks** di
Minggu 6: angka tanpa label baris tidak bisa menjawab pertanyaan apa pun, dan hanya akan merebut
tempat di hasil pencarian.

### Uji Langkah 2 (semua ✅)

- `scripts/check_fix_tables.py`, per laporan:
  - halaman = daftar di atas;
  - sama sebelum dan sesudah perbaikan Langkah 1;
  - setiap tabel punya bagian kiri;
  - 0 di halaman sumber ground truth (termasuk rasio resmi hal 15–16 `bbca_2025` dan halaman
    kunci 21, 540–542 `bbca_2024`);
  - tabel CR5 utuh **tidak** ditandai.
- **4 uji sintetis:**
  - menempel tepi dan tanpa label → ditandai;
  - judul kolom berhuruf dan berangka (bentuk hal 215) diabaikan → ditandai;
  - tidak menempel tepi → tidak ditandai;
  - label diulang di bagian kanan → tidak ditandai.
- **Uji mutasi:** ketiga bug yang sengaja disisipkan tertangkap:
  - kembali ke definisi Minggu 3 (11 pemeriksaan gagal);
  - pengaman label dibuang;
  - baris judul kolom ikut dihitung.
- **Cek visual dengan render PDF:** **ke-52 tabel** (16 / 16 / 16 halaman) memang bagian kanan
  tabel dua halaman: mulai dari tepi kiri kertas, tanpa kolom label baris. Ditambah:
  - tabel CR5 yang dilepas (hal 208–209 `bbca_2024`, 210–211 `bbca_2023`, 155–156 `bbca_2025`)
    memang tabel utuh berlabel;
  - tabel lain di halaman yang sama (mis. CR3 di bawah hal 203 `bbca_2023`) tidak ikut ditandai.

> Opsional, tidak dikerjakan: menggabungkan bagian kanan dengan bagian kirinya per kolom. Jumlah
> barisnya hanya sama persis di sebagian kecil tabel, karena judul kolom yang dilebur membuat
> jumlah baris Docling berbeda. Jadi penggabungan wajib dicek visual satu per satu. Isinya juga
> tabel Pilar 3, yang bukan sumber rasio skripsi.

---

## Langkah 3 — Pemotong (5.1) · ✅ SELESAI (15-11-2026)

**File:** `src/ingest/chunk.py`, ditambah konstanta di `src/config.py` · **Cek:**
`python -m src.ingest.chunk data\markdown\bbca_2024.json`. Tambahkan `--page 540` untuk melihat isi
semua chunk di halaman asli 540. Belum ada yang disimpan; `.jsonl` baru ditulis di Langkah 7.

```python
from src.ingest.chunk import chunk_report
result = chunk_report(2024)   # load_fixed (Langkah 1 + 2) -> potong -> buang boilerplate
result.chunks                 # record siap diindeks
result.excluded               # record audit tabel tanpa label baris (TIDAK diindeks)
result.stats                  # jumlah, boilerplate, tabel terbelah, waktu, peringatan
```

Setiap record saat ini berisi `text` (judul + isi, hasil `contextualize`), `pages`, `headings`,
`items` (rujukan item Docling), `n_tokens`, dan `excluded`. Langkah 4 menambah metadata lainnya.

Konstanta di `src/config.py`:

```python
# ----------------------------------------------------------------- CHUNKING (Minggu 5)
CHUNK_MAX_TOKENS = 1024        # Keputusan 5.A -- token BGE-M3; tabel lebih besar dipecah per baris
CHUNK_BOILERPLATE_REPEAT = 3   # teks yang muncul >= 3x dalam satu laporan = boilerplate, dibuang
CHUNK_VERSION = 1              # naikkan setiap aturan chunking berubah -> chunk lama dibuat ulang
```

Inti `chunk.py` (konfigurasi yang diuji):

```python
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer, ChunkingSerializerProvider)
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.serializer.markdown import MarkdownParams, MarkdownTableSerializer
from docling_core.types.doc.base import ImageRefMode
from transformers import AutoTokenizer

MARKDOWN = MarkdownParams(image_mode=ImageRefMode.PLACEHOLDER, image_placeholder="",
                          escape_underscores=False, escape_html=False,
                          compact_tables=True)          # tanpa spasi pengisi: -13% token gpt-oss

class SkippingSerializer(ChunkingDocSerializer):
    """Lewati item tertentu (Langkah 2: tabel tanpa label baris) tanpa mengubah dokumen."""
    skip_refs: frozenset[str] = frozenset()

    def get_excluded_refs(self, **kwargs):
        return super().get_excluded_refs(**kwargs) | self.skip_refs

class CompactMarkdownTables(ChunkingSerializerProvider):
    """Tabel sebagai Markdown ringkas, bukan triplet bawaan (2,2x lebih boros token)."""
    def __init__(self, skip_refs=frozenset()):
        self.skip_refs = frozenset(skip_refs)

    def get_serializer(self, doc):
        return SkippingSerializer(doc=doc, table_serializer=MarkdownTableSerializer(),
                                  params=MARKDOWN, skip_refs=self.skip_refs)

document, report = load_fixed(year)                   # Langkah 1 + 2
hf = AutoTokenizer.from_pretrained(config.EMBED_MODEL, local_files_only=True)  # cache HF; unduh kalau belum ada
tokenizer = HuggingFaceTokenizer(tokenizer=hf, max_tokens=config.CHUNK_MAX_TOKENS)
chunker = HybridChunker(tokenizer=tokenizer,
                        serializer_provider=CompactMarkdownTables(report.unlabeled_refs()),
                        repeat_table_header=True)     # bawaannya True; ditulis supaya jelas
for chunk in chunker.chunk(dl_doc=document):
    text = chunker.contextualize(chunk)               # judul + isi = yang di-embed & dibaca LLM
# + satu record excluded per tabel di report.unlabeled (Markdown tabelnya saja), untuk audit
```

Aturan sesudah pemotongan:

- **Halaman asli:** ambil **semua** `prov` dari **semua** `chunk.meta.doc_items`, lalu terjemahkan
  dengan `PageMap.to_original()`. Jangan hanya `prov[0]`, karena ada blok lintas halaman
  (83 / 3 / 0 blok; 80 blok 2023 ternyata pita navigasi, lihat di bawah). Hasil akhirnya chunk
  lintas halaman 34 / 27 / 25.
- **Navigasi/footer yang terbaca sebagai isi** dilewati per item (`margin_furniture`, 346 / 0 / 0
  item). *Ditambahkan saat Langkah 4*, lihat Temuan Langkah 4 no. 2.
- **Judul tidak dibawa melintasi halaman yang dilewati penyaring** (`GapAwareChunker`, 7 / 1 / 7
  potongan). *Ditambahkan saat Langkah 4*, lihat Temuan Langkah 4 no. 1.
- **Boilerplate:** buang chunk yang `chunk.text`-nya muncul ≥ `CHUNK_BOILERPLATE_REPEAT` kali dalam
  satu laporan. Perbandingannya **mengabaikan angka** (`text_shape`, ditambahkan di Langkah 6 untuk
  "Lampiran 5/1", "Lampiran 4/2", … `bbca_2025`). Satuannya tidak hilang, karena dicatat di metadata
  `unit` (Langkah 4).
- **Chunk pendek yang unik tetap disimpan.**
- **Record audit:** satu per tabel tanpa label baris. Isinya Markdown tabel itu, didahului judul
  yang berlaku di posisinya.

### Hasil

Angka akhir, termasuk perbaikan yang ditemukan di Langkah 4 dan 6. Angka di dalam kurung adalah
versi pertama Langkah 3, sebelum perbaikan itu.

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Chunk hasil pemotongan | 656 | 706 (705) | 659 (658) |
| Boilerplate dibuang | 142 | 166 | 161 (138) |
| **Chunk diindeks** | **514** | **540** (539) | **498** (520) |
| Record `excluded` (tabel tanpa label baris) | 18 | 17 | 17 |
| Chunk lintas halaman | 34 (190) | 27 (28) | 25 (26) |
| … yang halamannya kurang kalau hanya `prov[0]` | 1 (74) | 2 | 0 |
| Token BGE-M3 chunk diindeks: median / maks. | 350 / 1.024 | 330 / 1.024 | 306 / 1.024 |
| Tabel terbelah / potongan tanpa header | 44 / **0** | 44 / **0** | 38 / **0** |
| Waktu (detik, mesin tidak sibuk): perbaikan tabel + pemotongan | 6 + 5 | 7 + 5 | 4 + 4,5 |

Median token lebih tinggi dari tabel Langkah 5, karena chunk boilerplate yang pendek sudah dibuang.
Penurunan chunk lintas halaman 2023 (190 → 34) berasal dari pita navigasi yang kini dilewati.
Kenaikan +1 chunk di 2024 / 2025 terjadi karena chunk yang dulu menyatukan isi dari dua sisi celah
halaman kini terpisah. Penurunan 2025 (521 → 498) berasal dari 23 chunk "Lampiran x/y" yang kini
dihitung sebagai boilerplate.

**Boilerplate yang dibuang, seluruhnya** (tidak satu pun berisi tabel):

- `(Dalam jutaan Rupiah, kecuali dinyatakan lain)`: 139 / 157 / 124 kali;
- judul lanjutan, masing-masing 3 kali: `c. Manajemen risiko kredit (lanjutan)` +
  `iii. Analisis risiko kredit (lanjutan)` (2023, 2024), `Kredit yang diberikan terdiri dari:
  (lanjutan)` (2024, 2025);
- kalimat `Informasi tambahan ini disyaratkan oleh regulasi …` (2024: 3 kali; 2025: dua versi,
  8 + 3 kali);
- `Lampiran #/#` (penomoran halaman lampiran, angka diabaikan): 23 kali di 2025.

**Record `excluded`** bisa lebih panjang dari batas (terpanjang 1.969 token), karena tidak di-embed.

**Waktu:** saat mesin tidak sedang menjalankan proses lain, pemotongan 4,5–5 detik (sesuai
rancangan ±5 detik) ditambah perbaikan tabel 4–7 detik (docling-parse membaca PDF potongan). Totalnya
9–13 detik per laporan. Saat mesin sibuk, waktunya bisa 2–3 kali lebih lama: pengukuran awal saat
uji lain berjalan bersamaan mencatat 10–14 + 8–19 detik. Ini hanya terjadi sekali per laporan, karena
hasilnya di-cache (Langkah 7).

### Uji Langkah 3 (semua ✅)

Pemeriksaan sementara (script di luar repo). Versi resminya `scripts/check_chunks.py` di
Langkah 6. Per laporan:

- **Tabel tanpa label:**
  - 0 yang masuk chunk diindeks;
  - angka unik (5 per tabel) tidak muncul di chunk diindeks, dan semuanya ada di record `excluded`
    tabel itu;
  - judul record `excluded` sama dengan judul chunk tabel itu kalau tidak dikeluarkan;
  - halamannya sama dengan daftar Langkah 2.
- **Dibanding pemotongan tanpa pengecualian:** 0 item lain yang hilang, 0 item tambahan.
- Boilerplate yang dibuang tidak memuat tabel.
- Tidak ada chunk > 1.024 token.
- **Setiap baris badan tabel yang terbelah ada utuh di tepat satu potongan:** 1.383 / 1.377 /
  1.162 baris dicek, 0 rusak.
- Setiap halaman kunci ground truth punya chunk.
- **Uji mutasi:** dengan `repeat_table_header=False`, 43 potongan tanpa header langsung terdeteksi,
  dan peringatan muncul.
- **Dilihat langsung:**
  - hal 540 `bbca_2024`: neraca terbelah dua, dan kedua potongan berheader
    `|  | Catatan | 31 Desember - 2024 | 31 Desember - 2023 |`;
  - hal 704: baris kredit sudah terpecah per pihak, di bawah judul Entitas Induk;
  - record `excluded` hal 155: tabel KM1, angka tanpa label baris.

### Temuan

1. **`HybridChunker` bisa memecah tabel per kolom.** Ini terjadi kalau satu baris ditambah header
   melebihi batas token. Potongan kolom kanan tidak membawa label baris, persis masalah Langkah 2.
   - Di BCA tidak terjadi (0).
   - `chunk.py` menghitung potongan tabel yang tidak memuat header kolomnya, dan memberi
     **PERINGATAN** (`stats["warnings"]`). Dengan begitu laporan emiten uji (BMRI) tidak lolos
     diam-diam.
2. **Baris badan yang isinya sama dengan header**, di tabel jatuh tempo hal 569 `bbca_2025`.
   Pemeriksa baris di Langkah 6 harus membuang blok header **sekali per potongan** sebelum
   menghitung. Kalau tidak, baris itu terhitung berganda dan uji gagal palsu.
3. **Label total terpisah dari angkanya** di hal 540 `bbca_2024`: `|  |  | 1.449.301.328 |
   1.408.107.010 |`, lalu `| JUMLAH ASET |  |  |  |`.
   - Ini hasil parse Docling, bukan ulah pemotong.
   - ✅ **Diperbaiki di Langkah 6** sebagai pola 3 (Langkah 1d), bersama JUMLAH LIABILITAS hal 541
     yang ditemukan saat inspeksi. Totalnya 2 / 4 / 1 pasang baris di ketiga laporan.
4. **Baris satuan bisa ikut tergabung ke chunk tabel.** Contohnya `(Dalam jutaan Rupiah …)` dari
   halaman berikutnya, sehingga potongan terakhir neraca tercatat hal 540–541. Nomor halaman itu
   benar menurut isi chunk-nya.

---

## Langkah 4 — Metadata tiap chunk (5.2) · ✅ SELESAI (15-11-2026)

**File:** `src/ingest/chunk.py` (file yang sama dengan Langkah 3) · **Cek:**
`python -m src.ingest.chunk data\markdown\bbca_2025.json --page 15`. Perintah ini menampilkan
metadata dan isi setiap chunk di hal 15.

`result.records()` mengembalikan semua record, chunk dan `excluded`, urut `chunk_id`. Inilah isi
`.jsonl` di Langkah 7. Urutan field mengikuti `RECORD_FIELDS`, dan `text` diletakkan terakhir
supaya baris `.jsonl` mudah dibaca.

| Field | Isi | Sumber |
|---|---|---|
| `chunk_id` | `bbca_2024_0001`, urut dokumen. Record `excluded` disisipkan di posisi tabelnya. | urutan item Docling |
| `doc_id` | SHA-256 PDF | `.meta.json` |
| `ticker`, `sector`, `year` | `bbca`, `bank`, 2024 | `.metadata.json` (Minggu 3, Langkah 7), **bukan** ditulis tangan. Kalau file itu belum ada, `chunk_report` berhenti dan menyebut perintah `detect_metadata --save`. |
| `page`, `pages` | halaman pertama; semua halaman asli | Langkah 3 |
| `headings` | judul terdekat. `None` kalau judulnya berasal dari sebelum halaman yang dilewati penyaring (lihat Temuan 1). | menggantikan `header_path` |
| `is_table` | ada item tabel (`#/tables/…`) | **bukan** deteksi `\|---` |
| `unit` | `million_idr` / `billion_idr` / `None` | penanda satuan di halaman chunk, lihat di bawah |
| `merged_cells` | `True` kalau chunk memuat **baris** tabel yang masih bersel dua angka | Langkah 1c, dihitung **per potongan** (lihat di bawah) |
| `excluded` | `None` untuk chunk biasa; `"tabel tanpa label baris"` untuk record audit Langkah 2 | Langkah 2 |
| `n_tokens` | token BGE-M3 dari `text` | tokenizer |
| `items` | rujukan item Docling (`#/tables/123`, …), sebagai jejak ke `.json` | Langkah 3 |
| `text` | hasil `contextualize()`: judul + isi | Langkah 3 |

**Satuan per halaman.** Penanda dicari di teks Docling halaman itu, **termasuk sel tabel**
(Ikhtisar menulis "(dalam miliar Rupiah)" di dalam sel). Ada dua tambahan dari rancangan awal,
keduanya ditemukan saat menguji:

1. **Penanda tanpa kata "dalam"** (`UNIT_PHRASES`: `jutaan rupiah`, `juta rupiah`,
   `miliar(an) rupiah`).
   - Di 2 / 2 / 3 halaman Pilar 3, Docling memecah "(dalam jutaan Rupiah)" ke dua sel judul,
     yaitu `(dalam Kontrak` dan `jutaan Rupiah)`.
   - Di BCA, versi longgar ini hanya menambah halaman-halaman itu, tanpa halaman campur.
   - `page_filter.UNIT_MARKERS` **tidak diubah**, karena aturannya menentukan halaman yang di-parse
     di Minggu 3.
2. **Bagian kiri tabel dua halaman mewarisi satuan halaman kanannya.**
   - Penanda tabel Pilar 3 hanya tercetak di halaman kanan, yaitu tabel tanpa label (Langkah 2).
   - Pasangannya diambil dari `left_parts`. Jumlahnya 14 / 14 / 15 halaman, berisi 20–70 angka
     juta per halaman.

Halaman dengan dua satuan diisi `None` dan diberi peringatan (0 di BCA). Chunk yang mencakup
beberapa halaman memakai satuan halaman-halaman itu; halaman tanpa satuan tidak dihitung. Kalau
satuannya berbeda, `unit = None` dan peringatan muncul.

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Halaman bersatuan, penanda `page_filter` saja | 241 / 261 | 241 / 262 | 210 / 230 |
| **Halaman bersatuan, aturan akhir** | **257 / 261** | **257 / 262** | **228 / 230** |
| Halaman miliar (Ikhtisar, analisis manajemen) | 18 | 16 | 18 |
| Chunk diindeks: juta / miliar / `None` | 456 / 51 / 7 | 482 / 47 / 11 | 445 / 46 / 7 |

Halaman yang tetap tanpa satuan hanya dua jenis:

- tabel rasio resmi hal 19 / 21, isinya persen ditambah jumlah rekening, cabang, dan ATM;
- halaman tanpa angka nominal.

**`merged_cells` per potongan, bukan per tabel.** Tabel besar terbelah ke beberapa chunk, jadi
yang ditandai hanya potongan yang memuat **baris** bersel dua angka.

- Baris grid ke-r dipetakan ke baris Markdown-nya.
- Serializer menggabungkan semua baris judul kolom menjadi **satu** baris header Markdown
  (`Harga` + `Tertinggi` menjadi `Harga - Tertinggi`), jadi pemetaannya memperhitungkan jumlah baris
  judul. Pemetaan langsung baris ke-r ke Markdown ke-r gagal di 172 dari 302 tabel.
- Hasilnya 17 / 13 / 19 chunk diindeks ditandai, dari 56 / 25 / 53 baris di tabel yang diindeks.

### Temuan Langkah 4 (mengubah pemotong Langkah 3)

1. **Judul terbawa melintasi halaman yang dilewati penyaring.**
   - PDF potongan menyambung halaman yang tidak bersebelahan. Contohnya hal 219 langsung disambung
     hal 316 di `bbca_2025`, sehingga tabel saham lockup hal 316 berjudul "Ringkasan Dampak
     Perubahan Peraturan" dari hal 219. Potongan kecil berjudul sama juga digabung, jadi satu chunk
     berisi dua bagian laporan, dengan satuan miliar dan juta sekaligus.
   - `GapAwareChunker` melepas judul seperti itu (`None`) **sebelum** penggabungan, sehingga
     potongannya juga tidak tergabung dengan isi sebelum celah.
   - Jumlahnya 7 / 1 / 7 potongan. Chunk yang menyatukan dua bagian laporan turun dari 3 / 1 / 1
     menjadi 0.
   - Ini satu-satunya kaitan ke bagian dalam `HybridChunker` (`_merge_chunks_with_matching_metadata`).
     Kalau versi docling-core baru mengganti nama metode itu, `chunk.py` langsung gagal saat
     diimpor, sehingga pengaman ini tidak bisa diam-diam tidak berjalan.
2. **Navigasi dan footer terbaca sebagai isi** (`bbca_2023` saja).
   - Docling melabeli pita navigasi sebagai isi, bukan furniture. Contohnya
     "Ikhtisar Data Keuangan Laporan Manajemen Profil Perusahaan …" (84 kali), footer "Laporan
     Tahunan 2023 … Tbk 275", dan nomor halaman. Sebanyak 80 dari 83 blok lintas halaman 2023 adalah
     pita navigasi ini.
   - Akibatnya teks navigasi menyusup ke chunk, dan halamannya ikut bertambah.
   - `margin_furniture()` melewati teks yang seluruhnya berada di pita 5% teratas atau terbawah
     halaman, **dan** memenuhi salah satu syarat:
     - berulang ≥ 3 kali (angka diabaikan); atau
     - tercatat di dua halaman.
   - Hasilnya 346 / 0 / 0 item.
   - Aturan "teks berulang ≥ 3×" per item **tidak** dipakai. Daftarnya memuat isi bermakna, misalnya
     `Stage 1/2/3`, `Saldo, awal tahun`, dan "Manajemen berkeyakinan bahwa jumlah cadangan … telah
     memadai". Syarat pita tepi menjaga isi itu, dan juga satu catatan kaki unik di tepi bawah
     (`bbca_2025`).

### Uji Langkah 4 (semua ✅)

Pemeriksaan sementara (script di luar repo); versi resminya `scripts/check_chunks.py` (Langkah 6).
Per laporan:

- **Field dan urutan:**
  - 15 field berurutan di setiap record;
  - `chunk_id` urut tanpa celah;
  - `ticker`, `sector`, `year`, dan `doc_id` sama dengan `.metadata.json` / `.meta.json`;
  - `page` = halaman pertama;
  - `is_table` sesuai item;
  - chunk urut dokumen, dan record `excluded` ada di posisi tabelnya.
- **Satuan:**
  - satuan semua chunk di halaman sumber ground truth benar (Ikhtisar miliar; KPMM, NPL, dan
    Entitas Induk juta);
  - 3 chunk Ikhtisar 2025 hal 15 = `billion_idr`;
  - tidak ada chunk tanpa satuan yang berisi ≥ 5 angka nominal, selain tabel rasio;
  - 0 halaman campur.
- **`merged_cells`:**
  - pemetaan baris grid ke baris Markdown benar di 4.464 / 4.572 / 4.299 baris;
  - setiap baris bersel dua angka ada di record bertanda (57/57, 28/28, 59/59);
  - tidak ada tanda tanpa baris seperti itu.
- **Celah dan navigasi:**
  - tidak ada chunk yang melompati halaman yang dilewati penyaring;
  - tidak ada judul dari sebelum celah;
  - tidak ada teks navigasi 2023 di record mana pun;
  - dibanding pemotongan tanpa pengecualian, 0 item lain yang hilang.
- Semua uji Langkah 3 tetap lulus.
- **Uji mutasi**, ketiganya tertangkap:
  - judul tanpa cek celah → 6 pemeriksaan gagal (chunk hal 20+35, 273+277, 269+275, 219+316);
  - penanda satuan `page_filter` yang ketat → chunk Pilar 3 hal 192/205, 203, 137/138/150 tanpa
    satuan;
  - tanpa warisan satuan bagian kiri → 22–32 chunk Pilar 3 per laporan tanpa satuan.

> **Untuk Minggu 6:** ~~metadata ChromaDB hanya menerima nilai tunggal, jadi simpan `pages` sebagai
> teks~~. *Dikoreksi 15-11-2026 (PANDUAN_MINGGU6):* chromadb 1.5.9 **menerima list** dan bisa
> memfilternya (`{"pages": {"$contains": 541}}`), tetapi **menolak `None`**, jadi `unit = None`
> harus dihilangkan dari metadata.

---

## Langkah 5 — Distribusi panjang (5.3) · ✅ SELESAI (15-11-2026)

Diukur oleh `scripts/check_chunks.py` (Langkah 6) pada `.jsonl` yang tersimpan, dan dicatat di
`results/check_chunks.json`. Yang diukur hanya chunk yang **diindeks**.

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Chunk hasil pemotongan / boilerplate dibuang | 656 / 142 | 706 / 166 | 659 / 161 |
| **Chunk diindeks** | **514** | **540** | **498** |
| Record `excluded` (tidak diindeks) | 18 | 17 | 17 |
| Token BGE-M3: median / p90 / maks. | 350 / 973 / 1.024 | 330 / 972 / 1.024 | 306 / 961 / 1.024 |
| Token gpt-oss (o200k): median / p90 / maks. | 370 / 959 / 1.187 | 356 / 963 / 1.263 | 336 / 957 / 1.191 |
| Token gpt-oss seluruh chunk diindeks | 229.293 | 236.534 | 214.795 |
| Chunk pendek unik (< 50 token BGE-M3) yang **disimpan** | 34 | 32 | 31 |
| Tabel terbelah (header diulang) | 44 | 44 | 38 |

Pembanding: rancangan awal, sebelum Langkah 1 dan sebelum boilerplate dibuang, mencatat
668 / 722 / 677 chunk, median BGE-M3 239 / 205 / 196, dan tabel terbelah 46 / 50 / 44. Median kini
lebih tinggi karena chunk pendek yang berulang sudah dibuang.

Aturan roadmap 5.3 yang berubah:
- "chunk > 8192 token → pecah lagi": tidak terjadi, karena batasnya 1024. `check_chunks.py` tetap
  memeriksanya.
- "chunk < 50 token → buang" **diganti** dengan aturan boilerplate (Langkah 3). Sebanyak 31–34 chunk
  pendek yang unik tetap disimpan, misalnya "BCA tidak memiliki eksposur sekuritisasi" dan "Tidak
  ada shares option yang diterima Direksi".
- **Anggaran token Groq:** lima chunk teratas pada p90 berjumlah ±4.800 token gpt-oss.

---

## Langkah 6 — Pemeriksaan (5.4) · ✅ SELESAI (15-11-2026)

### a. Otomatis — `scripts/check_chunks.py` · **LULUS**

```powershell
python scripts\check_chunks.py           # semua cek + uji negatif (±1–3 menit)
python scripts\check_chunks.py --quick   # tanpa uji negatif
```

Yang diuji adalah **file** `data\chunks\*.jsonl` yang akan di-embed di Minggu 6, dibandingkan
dengan dokumen Docling yang sudah diperbaiki. Uji ini tidak memanggil ulang pemotong, kecuali
sebagai pembanding.

| Cek | Isi | Hasil |
|---|---|---|
| **A. Ground truth** | 76 angka **terbaca dari teks chunk yang diindeks**. Angka tabel harus ada di baris Markdown berlabel X dan kolom berjudul Y; angka narasi (NPL, CKPN) di kalimatnya; angka hitungan (kredit bruto, DPK) dari komponennya, dan baris "Pihak ketiga" harus ada di chunk yang sama. Semuanya di chunk yang `pages`-nya memuat halaman sumber, dengan `unit` yang benar. Logikanya sama dengan `check_parse_output.py`, tetapi dibaca dari Markdown yang dilihat LLM. | **76 / 76** |
| B. Tabel | Setiap potongan memuat header kolomnya, dan setiap baris badan ada **utuh** (tidak hilang, tidak terbelah). | 0 masalah |
| C. Record | 15 field berurutan; `chunk_id` urut; `ticker`, `sector`, `year`, `doc_id` dari file metadata; `n_tokens` sama dengan hitung ulang; ≤ 1.024 token; tidak ada boilerplate tersisa; `.jsonl` tidak kedaluwarsa (kunci cache sama). | 0 masalah |
| D. Halaman | `pages` = semua `prov` semua item; tidak melompati halaman yang dilewati penyaring; tidak ada judul dari sebelum celah; tidak ada item navigasi. | 0 masalah |
| E. Satuan | `unit` = hasil hitung ulang per halaman; tidak ada chunk tanpa satuan yang berisi ≥ 5 angka nominal (kecuali tabel rasio hal 19/21); 0 halaman campur. | 0 masalah |
| F. `merged_cells` | Tepat per baris bersel dua angka. | 0 masalah |
| G. Tabel tanpa label | Tidak ada di chunk diindeks; angka uniknya tidak muncul di teks chunk diindeks, tetapi ada di record `excluded`-nya; tepat 18 / 17 / 17 record; tidak ada item lain yang ikut hilang. | 0 masalah |
| **H. Uji negatif** | Pemeriksaan **harus gagal** kalau: (1) `pages` hanya dari `prov[0]`; (2) satuan ditukar; (3) tabel tanpa label tidak dikeluarkan. | gagal di 2 / 3 / 3 laporan, sesuai harapan |

Pada mutasi 1, laporan 2025 tidak terpengaruh karena chunknya tidak punya blok lintas halaman.
Pada mutasi 2, ke-76 angka ground truth gagal. Selain itu, cek B diuji dengan mutasi terpisah:
baris badan yang sengaja dibelah tertangkap di 10 dari 10 tabel, dan header yang dibuang juga
tertangkap.

Dua koreksi pada pemeriksanya sendiri:

- Cek B semula mensyaratkan setiap baris muncul **tepat** sekali. Itu gagal palsu di 44 tabel:
  tabel lain di chunk yang sama bisa punya baris identik, misalnya `| No. | Keterangan | Sumatera | …`
  di tabel 45 dan 46 `bbca_2024`. Syaratnya kini "tidak kurang dari seharusnya". Pemotong tidak
  pernah menggandakan baris selain header.
- Blok header dibuang **sekali per potongan** sebelum menghitung baris, karena tabel hal 569
  `bbca_2025` punya baris badan yang sama dengan headernya.

### b. Manual · semua ✅

- [x] **Semua chunk di halaman kunci `bbca_2024`** (21, 540–542, 703–705) dicocokkan dengan render
      PDF.
  - Hal 703 KPMM: keempat kolom Bank/Konsolidasian × 2024/2023 dan semua baris utuh dalam satu
    chunk.
  - Hal 704–705 Entitas Induk: semua baris cocok, termasuk JUMLAH LIABILITAS 1.153.262.200.
  - Hal 21 rasio resmi: NPL bruto 1,8%, ROA 3,9%, ROE 24,6%, NIM 5,8%, BOPO 41,7%, dan LDR 78,4%
    cocok.
  - Hal 542 laba rugi: pendapatan bunga bersih 82.264.164, laba sebelum pajak 68.217.850, dan laba
    bersih 54.851.274 cocok.
  - Tambahan: **semua 48 chunk di halaman kunci ketiga laporan** cocok ≥ 99% dengan teks tampak
    PDF (dibaca dengan docling-parse). Satu-satunya kata yang tidak ditemukan adalah "Ikhtisar", dari
    judul bagian di halaman sebelumnya.
- [x] Neraca hal 540 terbelah dua, dan kedua potongan berheader
      `|  | Catatan | 31 Desember - 2024 | 31 Desember - 2023 |`.
  - Inspeksi ini menemukan cacat parse "satu baris cetak dibelah dua". Contohnya JUMLAH ASET hal
    540 dan JUMLAH LIABILITAS hal 541, yang angka 2024-nya ada di baris tanpa label.
  - Diperbaiki sebagai **pola 3** di Langkah 1 (lihat 1d). Sekarang barisnya
    `| JUMLAH ASET |  | 1.449.301.328 | 1.408.107.010 |`.
- [x] Baris kredit hal 704 sudah terpecah (pola 1): Pihak berelasi 7.296.837, Pihak ketiga
      855.233.239.
- [x] **30 chunk acak** (10 per laporan, seed tetap):
  - judulnya masuk akal;
  - 30/30 cocok ≥ 97% dengan teks tampak halaman yang diklaim.
  - Pemeriksaan ini menemukan 23 chunk "Lampiran 5/1", "Lampiran 4/2", dan seterusnya di
    `bbca_2025`. Isinya hanya penomoran lampiran, dan lolos aturan boilerplate karena angkanya
    berbeda-beda. Aturan boilerplate kini **mengabaikan angka**. Diukur dulu: aturan baru ini hanya
    menambah 23 chunk itu, tanpa tabel atau isi lain.
- [x] Chunk Ikhtisar 2025 (hal 15–17, 7 chunk): `unit = billion_idr`.
  - Catatan: hal 17 juga memuat harga saham "(dalam Rupiah)" dan volume "(dalam ribuan)". Satuan
    dicatat per halaman, jadi **satuan yang tertulis di judul kolom atau baris harus mengalahkan
    metadata `unit`** (aturan Minggu 9).
- [x] 5 record `excluded` acak: memang tabel tanpa label baris, isinya angka atau nomor kolom
      `(9) … (17)` tanpa label.

---

## Langkah 7 — Simpan & catat (5.5) · ✅ SELESAI (15-11-2026)

```powershell
python -m src.ingest.chunk data\markdown\bbca_2024.json            # -> data\chunks\bbca_2024.jsonl
python -m src.ingest.chunk data\markdown\bbca_2024.json --force    # buat ulang walau cache berlaku
python -m src.ingest.chunk data\markdown\bbca_2024.json --page 540 # isi record hal 540
```

- **`data\chunks\<kode>_<tahun>.jsonl`**:
  - satu record per baris, urut `chunk_id`, dengan 15 field Langkah 4;
  - record `excluded` **ikut disimpan**, untuk audit;
  - ukurannya 0,9–1,0 MB per laporan.
- **Pemakaian di Minggu 6:**
  - `load_chunks(year)` mengembalikan hanya chunk yang **diindeks** (`excluded is None`);
  - `load_chunks(year, include_excluded=True)` mengembalikan semuanya.
- **`<kode>_<tahun>.chunks.meta.json`** berisi kunci cache, statistik lengkap (bahan Bab 4), waktu,
  dan tanggal. File ini ditulis **paling akhir**, jadi keberadaannya berarti `.jsonl` selesai ditulis
  utuh. `.jsonl` juga ditulis ke file sementara dulu, baru diganti namanya.
- **Kunci cache:** hash PDF, hash `.json` Docling, hash `.metadata.json`, `CHUNK_VERSION`, versi
  docling-core, model dan batas token, aturan boilerplate, **dan hash kode aturannya** (`chunk.py`,
  `fix_tables.py`, `page_filter.py`).
  - Hash kode ditambahkan setelah pola 3 mengubah isi tabel, sementara hash PDF dan `.json` tetap.
    Tanpa hash kode, `.jsonl` lama akan tetap dianggap berlaku. Mengandalkan ingatan untuk
    menaikkan `CHUNK_VERSION` terlalu rawan.
  - Hasilnya, jalan kedua tidak memotong ulang. Waktunya ±15 detik, hampir seluruhnya untuk memuat
    pustaka Python.
- **Waktu pemotongan** saat mesin tidak sedang menjalankan proses lain: **9–13 detik per
  laporan**. Rinciannya: perbaikan tabel 4–7 detik, pemotongan 4,5–5 detik, sisanya menghitung hash
  dan menulis file. Saat mesin sibuk, waktunya bisa 2–3 kali lebih lama.
- Angka untuk Bab 4 ada di lembar hasil di bawah, di `results/check_chunks.json`, dan di
  `results/fix_tables.json`.
- **Backup:** `data\chunks\` diabaikan git (`.gitignore`). **Salin ke Google Drive**, sama seperti
  `data\markdown\` di Minggu 3. Ini satu-satunya butir gerbang yang harus Anda kerjakan sendiri.

---

## Dampak ke Minggu 6–9

- **Minggu 6:**
  - embed hanya hasil `load_chunks()` (`excluded is None`): 514 + 540 + 498 = **1.552 chunk**;
  - `pages` tetap list di Chroma (didukung chromadb 1.5.9; dikoreksi di PANDUAN_MINGGU6);
  - BM25 per dokumen tetap dari `text` yang sama.
- **Minggu 7/9 — anggaran token:**
  - pada p90, lima chunk berjumlah ±4.800 token gpt-oss. Ditambah prompt dan token penalaran,
    jumlah itu dekat dengan batas 8K token per menit;
  - ukur token sebenarnya saat Minggu 9, dan siapkan `TOP_K_FINAL = 3–4` kalau kuota habis.
- **Minggu 9 (9.3), aturan untuk Extraction Agent:**
  - satuan diambil dari metadata `unit`, bukan ditebak dari teks. **Kecuali** judul kolom atau baris
    menyebut satuannya sendiri, misalnya "(dalam Rupiah)", "(dalam ribuan)", atau persen: judul itu
    yang berlaku;
  - angka dari chunk bertanda `merged_cells` harus dicek ulang;
  - sub-baris seperti "Pihak ketiga" di bawah "Simpanan dari nasabah Pihak berelasi" adalah bagian
    pos yang sama.

---

## Gerbang (kriteria lolos Minggu 5)

- [x] Pola 1 sel gabungan = 0; sisanya diperbaiki (pola 2) atau ditandai *(15-11-2026)*
- [x] `check_parse_output.py` (diperbarui) **76/76**, 3 yang semula cacat menjadi tepat *(15-11-2026)*
- [x] Tabel tanpa label terdeteksi: 18 / 17 / 17 tabel, dicek visual, 0 di halaman sumber
      *(15-11-2026; daftar 16 halaman Minggu 3 dikoreksi, lihat Langkah 2)*
- [x] Pemotong `src/ingest/chunk.py` selesai: 514 / 540 / 498 chunk diindeks + 18 / 17 / 17
      record `excluded` *(15-11-2026)*
- [x] Metadata lengkap (15 field), `unit` per halaman benar di semua halaman sumber ground truth,
      `merged_cells` per baris *(15-11-2026)*
- [x] … dan tidak satu pun tabel tanpa label masuk chunk yang diindeks *(`check_chunks.py` cek G,
      15-11-2026)*
- [x] `check_chunks.py` **LULUS**: 76/76 angka ground truth terbaca dari teks chunk, termasuk
      3 uji negatif *(15-11-2026)*
- [x] Tidak ada potongan tabel tanpa header, dan tidak ada baris tabel yang terbelah
      *(kriteria "0 tabel keuangan utama terpotong" setelah Keputusan 5.A; `check_chunks.py` cek B,
      15-11-2026)*
- [x] Inspeksi manual (Langkah 6b) selesai *(15-11-2026)*
- [x] `data\chunks\bbca_2023/2024/2025.jsonl` tersimpan *(15-11-2026)*
- [x] … dan **di-backup** ke Google Drive *(oleh pengguna, 15-11-2026)*

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `OSError` / mencoba mengunduh saat memuat tokenizer | tidak ada internet, padahal model BGE-M3 sudah ada di cache | `$env:HF_HUB_OFFLINE = "1"` sebelum menjalankan |
| Chunk tabel tanpa baris header | `repeat_table_header` mati, atau tabel ditulis sebagai triplet | pakai `CompactMarkdownTables` dan `repeat_table_header=True` |
| Token per tabel jauh lebih besar dari tabel di atas | provider bawaan (triplet) yang terpakai | pastikan `serializer_provider=CompactMarkdownTables()` |
| Nomor halaman chunk meleset / kurang | hanya `prov[0]`, atau nomor PDF potongan | ambil semua `prov` + `PageMap.to_original()` |
| Ribuan chunk berisi "(Dalam jutaan Rupiah …)" | boilerplate belum dibuang | aturan `CHUNK_BOILERPLATE_REPEAT` |
| Angka miliar dibaca sebagai juta | `unit` diambil per laporan, bukan per halaman | satuan per halaman (Langkah 4) |
| Setelah pemecahan pola 1, cek kredit bruto jadi "salah" | pemeriksa lama menjumlahkan angka dalam satu sel | perbarui `check_parse_output.py` (Langkah 1) |
| Chunk berisi angka tabel tanpa label, atau paragraf di sekitar tabel itu ikut hilang | tabel tanpa label ditandai `excluded` **per chunk**, padahal `HybridChunker` menggabungkannya dengan isi lain | keluarkan **per item** lewat `SkippingSerializer` (`report.unlabeled_refs()`), lalu tulis record audit terpisah (Langkah 2) |
| `PERINGATAN: … potongan tabel tanpa header kolom` dari `chunk.py` | `repeat_table_header` mati, atau satu baris tabel ditambah header > `CHUNK_MAX_TOKENS`, sehingga `HybridChunker` memecah tabel itu **per kolom** dan potongan kanannya tanpa label baris (0 di BCA) | buka tabel yang disebut. Kalau barisnya memang sepanjang itu, pertimbangkan `omit_header_on_overflow=True`: baris itu keluar tanpa header, tetapi tetap berlabel |
| Chunk bagian kiri tabel Pilar 3 ber-`unit = None`, padahal isinya angka juta | penanda "(dalam jutaan Rupiah)" hanya tercetak di halaman kanan (tabel tanpa label), atau Docling memecahnya ke dua sel judul | warisan satuan dari halaman kanan (`left_parts`) dan penanda tanpa kata "dalam" (`UNIT_PHRASES`), Langkah 4 |
| Judul chunk tidak cocok dengan isinya, atau satu chunk berisi dua bagian laporan | judul terbawa melintasi halaman yang dilewati penyaring (PDF potongan menyambung hal 219 → 316) | `GapAwareChunker` melepas judul itu; cek `stats["stale_headings"]` |
| Teks navigasi ("Ikhtisar Data Keuangan Laporan Manajemen …") atau nomor halaman muncul di chunk | Docling melabeli pita navigasi sebagai isi, bukan furniture (`bbca_2023`) | `margin_furniture()`: teks di pita 5% tepi yang berulang ≥ 3× atau melintasi dua halaman dilewati per item |
| Label total di satu baris tabel, angkanya di baris tanpa label di atas/bawahnya (JUMLAH ASET, JUMLAH LIABILITAS) | Docling membelah satu baris cetak menjadi dua baris tabel | pola 3 (`merge_split_row`) menggabungkannya, **hanya** kalau label dan angkanya sejajar di PDF (Langkah 1d) |
| Chunk kecil berisi "Lampiran 5/1", "Lampiran 4/2", … | penomoran halaman lampiran lolos aturan boilerplate karena angkanya beda-beda | aturan boilerplate mengabaikan angka (`text_shape`) |
| `.jsonl` tidak berubah padahal aturan `fix_tables.py`/`chunk.py` sudah diubah | cache hanya melihat hash PDF/`.json` | kunci cache memuat hash kode aturan (sudah); kalau ragu, `--force` |
| Uji baris tabel melaporkan baris "berganda" di tabel terbelah | baris badan sama persis dengan header, sehingga ikut terhitung setiap kali header diulang (hal 569 `bbca_2025`) | buang blok header sekali per potongan sebelum menghitung |
| Tabel CR5 "Bobot Risiko" hilang dari indeks, atau tabel kolom f–l ikut terindeks | definisi lama ("< 20% baris berhuruf") yang terpakai | pakai `is_unlabeled(doc, table)`, yang berbasis tepi kiri kertas |
| Pola 2 menandai hampir semua baris di satu halaman | koordinat sel dibaca dengan origin yang salah, atau PDF yang dibuka bukan PDF potongan | kotak sel Docling origin kiri-atas, kata docling-parse kiri-bawah (`_bottom_left`); buka `.subset.pdf` dengan `page_no` Docling apa adanya |

---

## Lembar hasil — isi sambil jalan

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Batas Groq akun (RPM / TPM / TPD) | 30 / 8K / 200K (`gpt-oss-120b`, 1K permintaan/hari) — berlaku untuk semua laporan | | |
| Keputusan 5.A (ukuran chunk) | **1024 token**, disetujui 15-11-2026 | | |
| Sel gabungan: pola 1 diperbaiki | 4 baris (sisa 0) | 5 baris (sisa 0) | 0 |
| Sel gabungan: pola 2 diperbaiki / ditandai | 19 / 57 baris | 19 / 28 baris | 5 / 59 baris |
| Baris cetak terbelah: pola 3 digabung | 2 pasang | 4 pasang (JUMLAH ASET, JUMLAH LIABILITAS) | 1 pasang |
| Tabel tanpa label (`excluded`) | 18 | 17 | 17 |
| Chunk total / boilerplate dibuang / diindeks | 656 / 142 / 514 | 706 / 166 / 540 | 659 / 161 / 498 |
| Chunk lintas halaman | 34 | 27 | 25 |
| Token BGE-M3 median / p90 / maks. (chunk diindeks) | 350 / 973 / 1.024 | 330 / 972 / 1.024 | 306 / 961 / 1.024 |
| Token gpt-oss median / p90 / maks. (chunk diindeks) | 370 / 959 / 1.187 | 356 / 963 / 1.263 | 336 / 957 / 1.191 |
| Tabel terbelah / potongan tanpa header | 44 / 0 | 44 / 0 | 38 / 0 |
| Chunk tabel (`is_table`) | 285 | 287 | 286 |
| Satuan chunk: juta / miliar / `None` | 456 / 51 / 7 | 482 / 47 / 11 | 445 / 46 / 7 |
| Halaman bersatuan (dari halaman tersaring) | 257 / 261 | 257 / 262 | 228 / 230 |
| Chunk `merged_cells` | 17 | 13 | 19 |
| Judul dilepas (celah halaman) / navigasi dilewati | 7 / 346 | 1 / 0 | 7 / 0 |
| Waktu chunking (detik, mesin tidak sibuk): perbaikan tabel + pemotongan / total | 6 + 5 / 13 | 7 + 5 / 13 | 4 + 4,5 / 9 |
| `check_parse_output.py` (diperbarui) | 76/76 tepat (ketiga laporan sekaligus) | | |
| `check_fix_tables.py` | LULUS (termasuk pola 3 dan 6 uji sintetisnya) | | |
| `check_chunks.py` | **LULUS**: 76/76 angka ground truth di teks chunk, cek B–G 0 masalah, 3 uji negatif gagal sesuai harapan | | |
| Catatan | Minggu 5 selesai 15-11-2026. Total 1.552 chunk diindeks + 52 record `excluded`. `data\chunks\` di-backup ke Google Drive 15-11-2026. | | |
