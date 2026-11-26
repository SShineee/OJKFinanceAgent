# Lembar Verifikasi Angka — Tugas 1.5

Dibuat otomatis dari `data/ground_truth.xlsx` oleh `scripts/build_verification_sheet.py`.

**Cara pakai:** buka satu halaman PDF, cek semua angka di bawahnya sekaligus,
lalu centang. Semua nilai dalam **miliar Rupiah**.

> ⚠️ **Jebakan satuan.** Catatan KPMM dan Entitas Induk di PDF memakai **JUTA**
> Rupiah. Di tabel ini sudah dikonversi ke **miliar** (dibagi 1.000).
> Contoh: PDF menulis `239.468.855` → di sini `239.468,855`. Itu benar.

Total 76 angka, tersebar di 13 halaman PDF.

---

## 1. `bbca_2023.pdf` — halaman 727  ⚠️ **PRIORITAS**

Blok: B. KPMM Bank
> RAWAN: 4 kolom berdampingan

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - BANK | 2022 | `196.799,387` | kolom **Bank 2022** (kolom ke-3 dari 4) |
| ✓ | Modal Inti (Tier 1) - BANK | 2023 | `217.686,126` | kolom **Bank 2023** (kolom ke-1 dari 4) |
| ✓ | Total Modal - BANK | 2022 | `204.705,741` | kolom **Bank 2022** (kolom ke-3 dari 4) |
| ✓ | Total Modal - BANK | 2023 | `226.426,139` | kolom **Bank 2023** (kolom ke-1 dari 4) |
| ✓ | Total ATMR - BANK | 2022 | `794.395,454` | kolom **Bank 2022** (kolom ke-3 dari 4) |
| ✓ | Total ATMR - BANK | 2023 | `769.200,928` | kolom **Bank 2023** (kolom ke-1 dari 4) |
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2022 | `212.445,689` | kolom **Konsolidasian 2022** (kolom ke-4) |
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2023 | `233.701,580` | kolom **Konsolidasian 2023** (kolom ke-2) |
| ✓ | Total Modal - KONSOLIDASIAN | 2022 | `220.568,562` | kolom **Konsolidasian 2022** (kolom ke-4) |
| ✓ | Total Modal - KONSOLIDASIAN | 2023 | `242.694,176` | kolom **Konsolidasian 2023** (kolom ke-2) |
| ✓ | Total ATMR - KONSOLIDASIAN | 2022 | `821.723,312` | kolom **Konsolidasian 2022** (kolom ke-4) |
| ✓ | Total ATMR - KONSOLIDASIAN | 2023 | `825.610,552` | kolom **Konsolidasian 2023** (kolom ke-2) |

## 2. `bbca_2023.pdf` — halaman 738  ⚠️ **PRIORITAS**

Blok: D. Kredit & NPL Bank
> HITUNGAN: kredit neto + CKPN -- cek aritmatikanya juga
> tertulis di narasi baris kredit

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2022 | `691.141,340` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2022 |
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2023 | `787.499,389` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2023 |
| ✓ | CKPN Kredit - BANK | 2022 | `33.892,635` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2022 |
| ✓ | CKPN Kredit - BANK | 2023 | `33.168,491` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2023 |

## 3. `bbca_2023.pdf` — halaman 739  ⚠️ **PRIORITAS**

Blok: D. Kredit & NPL Bank
> HITUNGAN untuk 2022-2024: pihak berelasi + pihak ketiga

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2022 | `1.023.659,603` | Simpanan dari nasabah: pihak berelasi + pihak ketiga, kolom 2022 |
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2023 | `1.081.852,159` | Simpanan dari nasabah: pihak berelasi + pihak ketiga, kolom 2023 |

## 4. `bbca_2024.pdf` — halaman 703  ⚠️ **PRIORITAS**

Blok: B. KPMM Bank
> RAWAN: 4 kolom berdampingan

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - BANK | 2024 | `239.468,855` | kolom **Bank 2024** (kolom ke-1 dari 4) |
| ✓ | Total Modal - BANK | 2024 | `249.056,422` | kolom **Bank 2024** (kolom ke-1 dari 4) |
| ✓ | Total ATMR - BANK | 2024 | `848.181,552` | kolom **Bank 2024** (kolom ke-1 dari 4) |
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2024 | `255.311,302` | kolom **Konsolidasian 2024** (kolom ke-2) |
| ✓ | Total Modal - KONSOLIDASIAN | 2024 | `265.198,025` | kolom **Konsolidasian 2024** (kolom ke-2) |
| ✓ | Total ATMR - KONSOLIDASIAN | 2024 | `910.183,696` | kolom **Konsolidasian 2024** (kolom ke-2) |

## 5. `bbca_2024.pdf` — halaman 704  ⚠️ **PRIORITAS**

Blok: D. Kredit & NPL Bank
> HITUNGAN: kredit neto + CKPN -- cek aritmatikanya juga
> tertulis di narasi baris kredit

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2024 | `894.912,082` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2024 |
| ✓ | CKPN Kredit - BANK | 2024 | `32.382,006` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2024 |

## 6. `bbca_2024.pdf` — halaman 705  ⚠️ **PRIORITAS**

Blok: D. Kredit & NPL Bank
> HITUNGAN untuk 2022-2024: pihak berelasi + pihak ketiga

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2024 | `1.108.908,832` | Simpanan dari nasabah: pihak berelasi + pihak ketiga, kolom 2024 |

## 7. `bbca_2025.pdf` — halaman 594  ⚠️ **PRIORITAS**

Blok: B. KPMM Bank
> RAWAN: 4 kolom berdampingan

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - BANK | 2025 | `258.057,396` | kolom **Bank 2025** (kolom ke-1 dari 4) |
| ✓ | Total Modal - BANK | 2025 | `268.244,808` | kolom **Bank 2025** (kolom ke-1 dari 4) |
| ✓ | Total ATMR - BANK | 2025 | `901.270,630` | kolom **Bank 2025** (kolom ke-1 dari 4) |
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2025 | `273.828,527` | kolom **Konsolidasian 2025** (kolom ke-2) |
| ✓ | Total Modal - KONSOLIDASIAN | 2025 | `284.351,775` | kolom **Konsolidasian 2025** (kolom ke-2) |
| ✓ | Total ATMR - KONSOLIDASIAN | 2025 | `936.368,457` | kolom **Konsolidasian 2025** (kolom ke-2) |

## 8. `bbca_2025.pdf` — halaman 595  ⚠️ **PRIORITAS**

Blok: D. Kredit & NPL Bank
> HITUNGAN: kredit neto + CKPN -- cek aritmatikanya juga
> tertulis di narasi baris kredit

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2025 | `961.903,505` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2025 |
| ✓ | CKPN Kredit - BANK | 2025 | `29.390,498` | Laporan Posisi Keuangan **Entitas Induk**, kolom 2025 |

## 9. `bbca_2025.pdf` — halaman 596  ⚠️ **PRIORITAS**

Blok: D. Kredit & NPL Bank
> HITUNGAN untuk 2022-2024: pihak berelasi + pihak ketiga

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2025 | `1.219.567,546` | Simpanan dari nasabah, kolom 2025 (satu baris) |

## 10. `bbca_2023.pdf` — halaman 646

Blok: D. Kredit & NPL Bank
> disebut langsung dalam narasi

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2022 | `11.795,528` | angka kedua di narasi (2022) |
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2023 | `14.147,246` | angka pertama di narasi (2023) |

## 11. `bbca_2024.pdf` — halaman 701

Blok: D. Kredit & NPL Bank
> disebut langsung dalam narasi

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2024 | `15.498,016` | angka pertama di narasi (2024) |

## 12. `bbca_2025.pdf` — halaman 15

Blok: A. Ikhtisar

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Total Aset | 2022 | `1.314.732,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset | 2023 | `1.408.107,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset | 2024 | `1.449.301,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset | 2025 | `1.586.829,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset Produktif | 2022 | `1.173.144,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset Produktif | 2023 | `1.266.223,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset Produktif | 2024 | `1.354.435,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Aset Produktif | 2025 | `1.479.307,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Kredit | 2022 | `711.262,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Kredit | 2023 | `810.392,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Kredit | 2024 | `921.878,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Kredit | 2025 | `992.901,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Dana Pihak Ketiga (DPK) | 2022 | `1.039.718,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Dana Pihak Ketiga (DPK) | 2023 | `1.101.673,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Dana Pihak Ketiga (DPK) | 2024 | `1.133.612,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Dana Pihak Ketiga (DPK) | 2025 | `1.249.044,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Ekuitas | 2022 | `221.182,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Ekuitas | 2023 | `242.538,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Ekuitas | 2024 | `262.835,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Total Ekuitas | 2025 | `281.688,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Pendapatan Bunga Bersih | 2022 | `63.863,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Pendapatan Bunga Bersih | 2023 | `74.938,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Pendapatan Bunga Bersih | 2024 | `82.264,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Pendapatan Bunga Bersih | 2025 | `85.548,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Sebelum Pajak | 2022 | `50.467,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Sebelum Pajak | 2023 | `60.180,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Sebelum Pajak | 2024 | `68.218,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Sebelum Pajak | 2025 | `71.261,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih | 2022 | `40.756,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih | 2023 | `48.658,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih | 2024 | `54.851,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih | 2025 | `57.563,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2022 | `40.736,000` | kolom 2022 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2023 | `48.639,000` | kolom 2023 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2024 | `54.836,000` | kolom 2024 pada tabel Ikhtisar 5 tahun |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2025 | `57.537,000` | kolom 2025 pada tabel Ikhtisar 5 tahun |

## 13. `bbca_2025.pdf` — halaman 590

Blok: D. Kredit & NPL Bank
> disebut langsung dalam narasi

| ✓ | Item | Tahun | Nilai di xlsx | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2025 | `15.965,436` | angka pertama di narasi (2025) |

---

## Satu-satunya angka yang butuh HITUNGAN

68 dari 72 angka cukup dibandingkan secara visual. Yang di bawah ini
pengecualiannya: PDF menyajikan kredit **NETO** (sudah dikurangi CKPN),
sedangkan NPL butuh **BRUTO**. Jadi harus ditambahkan kembali.

Angka komponennya sudah saya tulis — Anda cukup (a) cocokkan komponennya
ke PDF, lalu (b) periksa apakah penjumlahan saya benar.

Semua dalam **JUTA** Rupiah (seperti tertulis di PDF), bukan miliar.

### 2025 — `bbca_2025.pdf` halaman 595

```
  kredit neto              932.513.007   <- satu baris, tidak dipecah
  CKPN                   +  29.390.498   <- di narasi baris yang sama
  -----------------------------------
  kredit BRUTO             961.903.505   = 961.903,505 miliar
```

### 2024 — `bbca_2024.pdf` halaman 704

```
  Pihak berelasi             7.296.837
  Pihak ketiga           + 855.233.239
  -----------------------------------
  kredit neto              862.530.076
  CKPN                   +  32.382.006
  -----------------------------------
  kredit BRUTO             894.912.082   = 894.912,082 miliar
```

### 2023 — `bbca_2023.pdf` halaman 738

```
  Pihak berelasi             8.803.131
  Pihak ketiga           + 745.527.767
  -----------------------------------
  kredit neto              754.330.898
  CKPN                   +  33.168.491
  -----------------------------------
  kredit BRUTO             787.499.389   = 787.499,389 miliar
```

### 2022 — `bbca_2023.pdf` halaman 738 (kolom pembanding)

```
  Pihak berelasi             9.548.725
  Pihak ketiga           + 647.699.980
  -----------------------------------
  kredit neto              657.248.705
  CKPN                   +  33.892.635
  -----------------------------------
  kredit BRUTO             691.141.340   = 691.141,340 miliar
```

> Cross-check mudah: kredit neto 2024 juga tertulis sebagai angka pembanding
> di `bbca_2025.pdf` halaman 595 — harus sama persis dengan 862.530.076.

---

## Cross-check gratis

Angka tahun 2024 dan 2023 muncul di **dua** laporan tahunan (sebagai tahun
berjalan di satu laporan, dan sebagai pembanding di laporan berikutnya).
Kalau Anda sudah mengecek satu, cek silang di yang lain — kalau beda,
berarti ada yang salah baca.

| Item | Tahun | Sumber utama | Sumber silang |
|---|---|---|---|
| Modal Inti Tier 1 — BANK | 2024 | `bbca_2024.pdf` h703 | `bbca_2025.pdf` h594 kolom Bank 2024 |
| Total Modal — BANK | 2024 | `bbca_2024.pdf` h703 | `bbca_2025.pdf` h594 kolom Bank 2024 |
| Total ATMR — BANK | 2024 | `bbca_2024.pdf` h703 | `bbca_2025.pdf` h594 kolom Bank 2024 |
| Modal Inti Tier 1 — BANK | 2023 | `bbca_2023.pdf` h727 | `bbca_2024.pdf` h703 kolom Bank 2023 |
| NPL nominal — BANK | 2024 | `bbca_2024.pdf` h701 | `bbca_2025.pdf` h590 (angka kedua) |
| NPL nominal — BANK | 2023 | `bbca_2023.pdf` h646 | `bbca_2024.pdf` h701 (angka kedua) |
| Total Aset (ikhtisar) | 2022–2024 | `bbca_2025.pdf` h15 | `bbca_2024.pdf` h20 |

---

## Kalau ketemu angka yang salah

1. **Jangan** perbaiki langsung di Excel — akan tertimpa kalau generator dijalankan ulang.
2. Perbaiki di `scripts/build_ground_truth.py` (blok `HIGHLIGHTS`, `CAPITAL_BANK`,
   `CAPITAL_CONSOLIDATED`, atau `LOAN_ITEMS`) **dan** di `scripts/validate_ratios.py`.
3. Jalankan ulang: `python scripts/build_ground_truth.py` (tutup Excel dulu),
   lalu `python scripts/validate_ratios.py` untuk melihat MAPE yang terkoreksi.

Atau kirim koreksinya ke Claude — lebih cepat, sekalian dicek dampaknya ke MAPE.

## Setelah semua tercentang

- [ ] Centang kolom `Dicek` (kolom H) di sheet `1_angka_mentah`
- [ ] Isi sheet `4_kesimpulan`
- [ ] Tandai 1.5 selesai di `docs/catatan_validasi_rasio.md`