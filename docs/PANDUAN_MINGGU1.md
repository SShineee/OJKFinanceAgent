# Panduan Rinci Minggu 1 — GATE 1

Status per hari ini: **tugas 1.2 dan 1.5 sudah selesai — 6 dari 6 rasio tervalidasi.**
Yang tersisa: verifikasi angka, cek model Groq, dan bimbingan.

---

## Peta halaman PDF (hasil scan otomatis)

Ini yang paling menghemat waktu Anda — tidak perlu scroll 700 halaman.
Semua nomor di bawah adalah **indeks halaman PDF** (halaman fisik), bukan nomor cetak di dokumen.

| Yang dicari | `bbca_2023.pdf` | `bbca_2024.pdf` | `bbca_2025.pdf` |
|---|---|---|---|
| **Ikhtisar Data Keuangan 5 thn** | hal 18 | hal 20 | hal 15 |
| **Tabel Rasio Keuangan resmi** | hal 19 | hal 21 | hal 15–16 |
| **Laporan Posisi Keuangan Konsolidasian** | hal 576–577 | hal 540–541 | hal 461–462 |
| **Laporan Laba Rugi Konsolidasian** | hal 578–580 | hal 542–545 | hal 463–466 |
| **Catatan KPMM (Tier 1, Total Modal, ATMR)** | hal 727 | hal 703 | hal 594 |
| CaLK — Kredit yang Diberikan | hal 168, 171, 263 | hal 166, 169, 261 | hal 117, 204, 210 |
| Tabel kolektibilitas kredit | hal 264–265 | hal 262, 275 | hal 205–206, 219 |
| Total aset produktif | hal 18–19 | hal 20–21 | hal 15–16 |

Regenerate peta ini kapan saja: `python scripts/inspect_pdf.py`

**Hasil inspeksi PDF (tugas 1.2 — sudah selesai):**

| Tahun | File | Hal. | Ukuran | Jenis |
|---|---|---|---|---|
| 2023 | `bbca_2023.pdf` | 747 | 55,6 MB | text-based |
| 2024 | `bbca_2024.pdf` | 714 | 12,4 MB | text-based |
| 2025 | `bbca_2025.pdf` | 605 | 37,0 MB | text-based |

Ketiganya text-based (rata-rata ~3.000 karakter/halaman) → **Docling tidak perlu OCR.**
Estimasi parsing di Minggu 3 pakai jalur normal, tidak perlu dikali 3.

---

## Temuan kunci: dasar perhitungan rasio resmi BCA

Ini jawaban atas risiko R1, dan sumbernya dari dokumen itu sendiri —
footnote di bawah tabel Rasio Keuangan (`bbca_2025.pdf` hal 16):

| Footnote | Isi | Dampak ke proposal |
|---|---|---|
| **fn5** | *"Induk perusahaan saja, rasio keuangan disajikan sesuai SEOJK No.9/SEOJK.03/2020"* | Semua rasio resmi berbasis **BANK**, bukan konsolidasi |
| **fn7** | NPL bruto = kredit bermasalah (KL+D+M) / total kredit | ✅ sama dengan proposal |
| **fn9** | ROA = laba **setelah pajak** / **rata-rata** total aset | ⚠️ proposal pakai saldo akhir |
| **fn10** | ROE = laba setelah pajak / **rata-rata MODAL TIER 1** | ❌ proposal pakai ekuitas — salah |
| **fn11** | NIM = pend. bunga bersih / **rata-rata** aset produktif | ⚠️ proposal pakai saldo akhir |

Bukti tambahan basis bank vs konsolidasi: `bbca_2024.pdf` hal 140 menulis
*"CAR BCA secara konsolidasi sebesar 29,1%"*, sedangkan tabel Ikhtisar hal 21
menulis **29,4%**. Dua angka berbeda untuk tahun yang sama — bedanya basis.
Catatan KPMM (hal 703) memuat keduanya berdampingan: Bank 29,36%, Konsolidasian 29,14%.

---

## Hasil validasi rasio (tugas 1.5)

Dihitung ulang dengan `python scripts/validate_ratios.py`:

| Rasio | Metode Proposal (Tabel 2.2) | Metode OJK (footnote) | Verdict |
|---|---|---|---|
| **CAR** | 0,94% (basis konsolidasi) | **0,01%** (basis bank) | ✅ sangat akurat |
| **ROE** | **14,06%** ❌ (laba/ekuitas) | **1,08%** (laba/rata² Tier 1) | ✅ setelah formula diperbaiki |
| **ROA** | 4,65% (saldo akhir) | **1,68%** (rata-rata aset) | ✅ sangat akurat |
| **NPL** | **5,89%** ❌ (kredit konsolidasi) | **3,02%** (kredit bruto bank) | ✅ akurat |
| **LDR** | 4,01% | 4,01% | ✅ akurat |
| **NIM** | **4,59%** (saldo akhir) | 8,63% (rata-rata) ❌ | ✅ akurat — tapi lihat catatan |

**Semua 6 rasio lolos target MAPE < 5%.** Target di proposal **tidak perlu diturunkan.**

Pola yang konsisten di 4 rasio (CAR, ROE, NPL, dan sebagian ROA): **yang menentukan
bukan rumusnya, tapi basisnya.** Angka bank-only vs konsolidasian. Salah basis →
error 6–14%; basis benar → error di bawah 3%.

Tiga hal yang perlu Anda perhatikan:

1. **ROE adalah temuan terpenting.** Formula Tabel 2.2 (laba bersih / ekuitas) menghasilkan
   MAPE 14,06% — gagal total. Penyebabnya: Modal Tier 1 bank-only (Rp 239 T pada 2024)
   jauh lebih kecil dari ekuitas konsolidasian (Rp 263 T). Setelah diganti ke rata-rata
   Tier 1, MAPE jadi 1,08%. **Ini bahan pembahasan Bab 4 yang kuat — jangan dibuang.**

2. **Pakai acuan 2 desimal, bukan 1 desimal.** Tabel Ikhtisar membulatkan rasio ke
   1 desimal (CAR 29,4%). Catatan KPMM memberi 2 desimal (29,36%). Memakai yang
   dibulatkan menimbulkan **error semu** — CAR jadi tampak 0,12% padahal sebenarnya
   0,01%. Acuan presisi: CAR di Catatan KPMM, NPL di Catatan *Non-Performing Loan*.

3. **NIM agak janggal.** Footnote 11 bilang pakai *rata-rata* aset produktif, tapi
   secara empiris saldo akhir (4,59%) justru lebih dekat ke angka resmi daripada
   rata-rata (8,63%). Dugaan penyebab: pembilang (pend. bunga bersih) yang tersedia
   di Ikhtisar bersifat konsolidasi, sedangkan angka resmi NIM bank-only. Jadi kecocokan
   4,59% itu sebagian kebetulan. **Jujur saja soal ini di Bab 4** — jangan diklaim
   sebagai formula yang benar, sebut sebagai pendekatan terbaik yang tersedia.

---

## Yang masih harus Anda kerjakan

### Langkah 1 — Verifikasi angka yang sudah di-prefill (±2 jam)

Buka `data/ground_truth.xlsx` → sheet `1_angka_mentah`.
Sel **biru muda** sudah terisi otomatis dari PDF. Semuanya **wajib dicek**, karena
ini hasil baca mesin.

Cara cek, per blok:

| Blok | Buka | Bandingkan |
|---|---|---|
| A. Ikhtisar (9 item) | `bbca_2025.pdf` hal 15 | kolom 2021–2025 sekaligus — satu tabel memuat 5 tahun |
| B. KPMM kolom **BANK** (3 item) | `bbca_2025.pdf` hal 594 → 2025 & 2024<br>`bbca_2024.pdf` hal 703 → 2024 & 2023<br>`bbca_2023.pdf` hal 727 → 2023 & 2022 | perhatikan: ada 4 kolom (Bank 2025, Konsol 2025, Bank 2024, Konsol 2024) — **ambil kolom Bank** |
| C. KPMM kolom Konsolidasian | sama | untuk pembanding di Bab 4 |

⚠️ **Jebakan satuan.** Ikhtisar pakai **miliar** Rupiah. Catatan KPMM pakai **juta**
Rupiah. Di xlsx semuanya sudah saya samakan ke **miliar** (angka KPMM sudah dibagi 1000).
Jadi di PDF Anda akan lihat `239.468.855` sementara di xlsx tertulis `239.468,855`.
Itu benar, bukan salah.

Centang kolom `Dicek` (H) tiap baris yang sudah Anda verifikasi.

### Langkah 2 — Verifikasi angka NPL & kredit basis BANK (±30 menit)

Sudah terisi (baris 21–23 sheet `1_angka_mentah`). Sumbernya:

| Baris | Item | Letaknya |
|---|---|---|
| 21 | Kredit Bermasalah KL+D+Macet, nominal — BANK | Catatan *Non-Performing Loan*: `bbca_2023.pdf` hal 646, `bbca_2024.pdf` hal 701, `bbca_2025.pdf` hal 590. Nominalnya disebut langsung dalam narasi, tidak perlu menjumlah tabel kolektibilitas |
| 22 | Kredit yang Diberikan BRUTO — BANK | Laporan Posisi Keuangan **Entitas Induk** (Lampiran 6): `bbca_2023.pdf` hal 738, `bbca_2024.pdf` hal 704, `bbca_2025.pdf` hal 595 — hitung: kredit neto + CKPN |
| 23 | CKPN Kredit — BANK | di narasi baris kredit pada halaman yang sama |

Catatan: angka ini **basis Bank**, bukan konsolidasian — sengaja, supaya setara dengan
acuan resmi (fn5). Memakai Total Kredit dari Ikhtisar (konsolidasi) membuat NPL meleset
5,89%.

**Catatan penting soal kredit bruto.** Di Laporan Posisi Keuangan, baris kredit
disajikan **NETO** — nilai CKPN-nya ditulis di narasi baris yang sama, jadi harus
ditambahkan kembali. Contoh dari Entitas Induk `bbca_2024.pdf` hal 704:

```
Kredit yang diberikan - setelah dikurangi cadangan kerugian
 penurunan nilai sebesar Rp 32.382.006 pada tanggal 31 Desember 2024
 Pihak berelasi        7.296.837
 Pihak ketiga        855.233.239
```

Jadi kredit bruto Bank 2024 = 7.296.837 + 855.233.239 + 32.382.006 = **894.912.082 juta**
(= 894.912 miliar).

Bandingkan tiga angka yang mirip tapi berbeda untuk tahun yang sama:

| Angka | 2024 (miliar Rp) | Sumber |
|---|---|---|
| Total Kredit (ikhtisar, konsolidasi) | 921.878 | termasuk pembiayaan konsumen & syariah (fn1) |
| Kredit bruto **konsolidasian** | 901.311 | Lap. Posisi Keuangan Konsolidasian hal 540 |
| Kredit bruto **BANK** ← dipakai | 894.912 | Lap. Posisi Keuangan Entitas Induk hal 704 |

Yang benar untuk NPL adalah yang ketiga, karena acuan resmi berbasis bank (fn5).
Ini contoh paling jelas dari pelajaran "angka yang mirip belum tentu angka yang sama" —
dan **persisnya jenis kesalahan yang akan dibuat Extraction Agent** kalau promptnya
tidak menyebut basis secara eksplisit.

### Langkah 3 — Baca hasil & isi kesimpulan (±30 menit)

Sheet `3_hitung_manual` → cek warna kolom Selisih (hijau <2%, kuning 2–5%, merah >5%).
Lalu sheet `4_kesimpulan` → MAPE per rasio terhitung otomatis, isi kolom Keputusan.

### Langkah 4 — Isi catatan & bimbingan

Lengkapi `docs/catatan_validasi_rasio.md` (sudah sebagian terisi), lalu bawa ke
kedua pembimbing (Dr. Kurniawan Nur Ramadhani, Febryanti Sthevanie) bersama printout sheet `4_kesimpulan`.

**Empat hal yang perlu keputusan mereka:**

1. **Periode data → 2023, 2024, 2025.** Batasan hal.5 proposal (2021–2023) direvisi
   menyesuaikan Sub-bab 3.2.
2. **Tabel 2.2 direvisi** mengikuti footnote OJK — khususnya ROE memakai rata-rata
   Modal Tier 1, bukan ekuitas.
3. **Target MAPE < 5% dipertahankan** (tidak perlu diturunkan — sudah terbukti tercapai).
4. **Konsekuensi arsitektur:** Financial Analyst Agent harus mengambil Tier 1 & ATMR
   dari **Catatan KPMM**, bukan dari Laporan Posisi Keuangan. Artinya Extraction Agent
   wajib bisa menemukan catatan yang letaknya di ~hal 594–727 — ini masuk uji GATE 4
   di Minggu 9.

### Langkah 5 — Verifikasi model Groq (±15 menit)

```
$env:GROQ_API_KEY="gsk_xxx"
python scripts/check_groq_models.py
```

Tempel hasilnya ke `docs/catatan_validasi_rasio.md` bagian 1.3.

---

## Checklist GATE 1

- [x] PDF terkumpul & diinspeksi (text-based, tidak perlu OCR)
- [x] Peta halaman tersusun
- [x] Angka mentah diekstrak dari PDF
- [x] Validasi selesai — **6/6 lolos MAPE < 5%**
- [ ] Angka prefill diverifikasi manual
- [ ] Model Groq diverifikasi
- [ ] Keputusan pembimbing didapat

**Boleh lanjut ke Minggu 2 setelah 3 item terakhir tercentang.**

---

## Dampak ke rencana selanjutnya

Satu hal berubah dari roadmap awal. Angka Tier 1 dan ATMR hanya ada di **Catatan atas
Laporan Keuangan** di bagian paling belakang dokumen (hal 594–727), bukan di laporan
keuangan utama. Konsekuensinya:

- **Minggu 3–4 (Docling):** jangan parse hanya laporan keuangan utama. Catatan KPMM
  wajib ikut terparse, dan tabelnya 4 kolom (Bank/Konsolidasian × 2 tahun) — tipe tabel
  yang paling mudah rusak saat parsing. Jadikan ini salah satu checkpoint inspeksi 3.5.
- **Minggu 5 (chunking):** chunk yang memuat tabel KPMM harus utuh. Kalau terpotong,
  CAR dan ROE langsung gagal.
- **Minggu 9 (Extraction Agent):** tambahkan Tier 1, Total Modal, dan ATMR ke daftar
  angka yang diuji di GATE 4. Angka-angka ini yang paling menentukan.
