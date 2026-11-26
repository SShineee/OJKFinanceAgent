# Lembar Verifikasi Angka BMRI — Minggu 8 (Tugas 8.5)

Dibuat otomatis dari `data/ground_truth_bmri.xlsx` oleh `scripts/build_verification_sheet_bmri.py`.

**Cara pakai:** buka satu halaman PDF asli BMRI, cocokkan semua angka di bawahnya sekaligus,
lalu centang. Seluruh nilai di tabel ini sudah dinormalisasi ke **miliar Rupiah** (PDF BMRI
mencetak **semua** tabel — Ikhtisar maupun CaLK — dalam **JUTA Rupiah**, jadi dibagi 1.000).
Contoh: PDF menulis `229.932.670` → di sini `229.932,670`.

Total **92 angka** (23 item × 4 tahun), tersebar di **28 halaman PDF**.

---

## 1. `bmri_2023.pdf` — halaman 403  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2022 | `223.271,290` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2022 |
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2023 | `258.956,049` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2023 |

## 2. `bmri_2023.pdf` — halaman 404  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Total Modal - KONSOLIDASIAN | 2022 | `236.470,218` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2022 |
| ✓ | Total Modal - KONSOLIDASIAN | 2023 | `273.922,880` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2023 |

## 3. `bmri_2023.pdf` — halaman 405  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Total ATMR - KONSOLIDASIAN | 2022 | `1.203.506,671` | MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2022 |
| ✓ | Total ATMR - KONSOLIDASIAN | 2023 | `1.245.624,433` | MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2023 |

## 4. `bmri_2023.pdf` — halaman 1501  ⚠️ **PRIORITAS**

Blok: A. Ikhtisar (Aset Produktif Inti Bank)
> HITUNGAN: Penempatan + Efek + Obligasi Pemerintah + Reverse Repo + Kredit bruto (Entitas Induk)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Aset Produktif Inti - BANK (hitung: 5 pos Neraca Induk) | 2022 | `1.324.251,261` | Neraca Entitas Induk (bagian 1), kolom 2022 |
| ✓ | Aset Produktif Inti - BANK (hitung: 5 pos Neraca Induk) | 2023 | `1.439.648,199` | Neraca Entitas Induk (bagian 1), kolom 2023 |

## 5. `bmri_2024.pdf` — halaman 430  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2024 | `286.910,930` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2024 |

## 6. `bmri_2024.pdf` — halaman 431  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Total Modal - KONSOLIDASIAN | 2024 | `304.285,722` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2024 |
| ✓ | Total ATMR - KONSOLIDASIAN | 2024 | `1.461.593,484` | MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2024 |

## 7. `bmri_2024.pdf` — halaman 1713  ⚠️ **PRIORITAS**

Blok: A. Ikhtisar (Aset Produktif Inti Bank)
> HITUNGAN: Penempatan + Efek + Obligasi Pemerintah + Reverse Repo + Kredit bruto (Entitas Induk)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Aset Produktif Inti - BANK (hitung: 5 pos Neraca Induk) | 2024 | `1.606.455,142` | Neraca Entitas Induk (bagian 1), kolom 2024 |

## 8. `bmri_2025.pdf` — halaman 37  ⚠️ **PRIORITAS**

Blok: A. Ikhtisar
> HITUNGAN: Simpanan Nasabah (hal 36) + Dana Syirkah Temporer Simpanan Nasabah (hal 37)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga Konsolidasian (Simpanan + Dana Syirkah) | 2022 | `1.490.844,592` | kolom 2022 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Dana Pihak Ketiga Konsolidasian (Simpanan + Dana Syirkah) | 2023 | `1.576.949,619` | kolom 2023 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Dana Pihak Ketiga Konsolidasian (Simpanan + Dana Syirkah) | 2024 | `1.698.896,916` | kolom 2024 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Dana Pihak Ketiga Konsolidasian (Simpanan + Dana Syirkah) | 2025 | `2.105.764,151` | kolom 2025 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Total Ekuitas | 2022 | `252.245,455` | kolom 2022 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Total Ekuitas | 2023 | `287.494,962` | kolom 2023 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Total Ekuitas | 2024 | `313.474,681` | kolom 2024 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |
| ✓ | Total Ekuitas | 2025 | `327.401,998` | kolom 2025 pada Ikhtisar Neraca Konsolidasian (Liabilitas/Syirkah/Ekuitas) |

## 9. `bmri_2025.pdf` — halaman 356  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - KONSOLIDASIAN | 2025 | `304.433,779` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2025 |

## 10. `bmri_2025.pdf` — halaman 357  ⚠️ **PRIORITAS**

Blok: C. KPMM Konsolidasian
> RAWAN: 4 kolom Bank/Konsolidasi berdampingan

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Total Modal - KONSOLIDASIAN | 2025 | `322.895,630` | MD&A Pengungkapan Struktur Permodalan, kolom Konsolidasi 31-Des-2025 |
| ✓ | Total ATMR - KONSOLIDASIAN | 2025 | `1.580.301,328` | MD&A Pengungkapan Struktur Permodalan (ATMR), kolom Konsolidasi 31-Des-2025 |

## 11. `bmri_2025.pdf` — halaman 1455  ⚠️ **PRIORITAS**

Blok: A. Ikhtisar (Aset Produktif Inti Bank)
> HITUNGAN: Penempatan + Efek + Obligasi Pemerintah + Reverse Repo + Kredit bruto (Entitas Induk)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Aset Produktif Inti - BANK (hitung: 5 pos Neraca Induk) | 2025 | `1.821.080,198` | Neraca Entitas Induk (bagian 1), kolom 2025 |

## 12. `bmri_2023.pdf` — halaman 401

Blok: D. Basis Bank
> Tercetak langsung 'NPL gross*)' = KL + Diragukan + Macet

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2022 | `17.443,642` | MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2022 |
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2023 | `10.999,536` | MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2023 |

## 13. `bmri_2023.pdf` — halaman 1425

Blok: B. KPMM Bank
> Sumber utama CAR & ROE (Bank Mandiri saja)
> Sumber utama CAR (Bank Mandiri saja)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - BANK | 2022 | `181.072,852` | Catatan 58 KPMM (Bank Mandiri saja), kolom 2022 |
| ✓ | Modal Inti (Tier 1) - BANK | 2023 | `209.724,274` | Catatan 58 KPMM (Bank Mandiri saja), kolom 2023 |
| ✓ | Total Modal - BANK | 2022 | `191.844,453` | Catatan 58 KPMM (Bank Mandiri saja), kolom 2022 |
| ✓ | Total Modal - BANK | 2023 | `221.988,279` | Catatan 58 KPMM (Bank Mandiri saja), kolom 2023 |
| ✓ | Total ATMR - BANK | 2022 | `986.051,285` | Catatan 58 KPMM (Bank Mandiri saja), kolom 2022 |
| ✓ | Total ATMR - BANK | 2023 | `1.033.407,212` | Catatan 58 KPMM (Bank Mandiri saja), kolom 2023 |

## 14. `bmri_2023.pdf` — halaman 1502

Blok: D. Basis Bank
> Baris 'Dikurangi: cadangan kerugian penurunan nilai' di bawah Kredit
> Baris 'TOTAL ASET' Neraca Entitas Induk
> Subtotal 'Kredit yang diberikan' sebelum dikurangi CKPN

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2022 | `932.639,051` | Neraca Entitas Induk (bagian 2), kolom 2022 |
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2023 | `1.085.787,427` | Neraca Entitas Induk (bagian 2), kolom 2023 |
| ✓ | CKPN Kredit - BANK | 2022 | `54.267,417` | Neraca Entitas Induk (bagian 2), kolom 2022 |
| ✓ | CKPN Kredit - BANK | 2023 | `42.323,522` | Neraca Entitas Induk (bagian 2), kolom 2023 |
| ✓ | Total Aset - BANK (Entitas Induk) | 2022 | `1.570.332,063` | Neraca Entitas Induk (bagian 2), kolom 2022 |
| ✓ | Total Aset - BANK (Entitas Induk) | 2023 | `1.688.850,385` | Neraca Entitas Induk (bagian 2), kolom 2023 |

## 15. `bmri_2023.pdf` — halaman 1503

Blok: D. Basis Bank
> Tercetak langsung 'Total simpanan nasabah'

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2022 | `1.193.164,326` | Neraca Entitas Induk (Liabilitas), baris 'Total simpanan nasabah', kolom 2022 |
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2023 | `1.242.145,598` | Neraca Entitas Induk (Liabilitas), baris 'Total simpanan nasabah', kolom 2023 |

## 16. `bmri_2023.pdf` — halaman 1506

Blok: D. Basis Bank
> Baris 'LABA SEBELUM BEBAN PAJAK' (dipakai untuk ROA SEOJK)
> Baris 'LABA TAHUN BERJALAN' (dipakai untuk ROE SEOJK)
> Baris 'PENDAPATAN BUNGA - NETO'

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Pendapatan Bunga Neto - BANK (Entitas Induk) | 2022 | `65.105,537` | Laba Rugi Entitas Induk, kolom 2022 |
| ✓ | Pendapatan Bunga Neto - BANK (Entitas Induk) | 2023 | `71.226,722` | Laba Rugi Entitas Induk, kolom 2023 |
| ✓ | Laba Sebelum Pajak - BANK (Entitas Induk) | 2022 | `46.778,433` | Laba Rugi Entitas Induk, kolom 2022 |
| ✓ | Laba Sebelum Pajak - BANK (Entitas Induk) | 2023 | `62.787,209` | Laba Rugi Entitas Induk, kolom 2023 |
| ✓ | Laba Bersih (Laba Tahun Berjalan) - BANK (Entitas Induk) | 2022 | `37.692,426` | Laba Rugi Entitas Induk, kolom 2022 |
| ✓ | Laba Bersih (Laba Tahun Berjalan) - BANK (Entitas Induk) | 2023 | `51.096,878` | Laba Rugi Entitas Induk, kolom 2023 |

## 17. `bmri_2024.pdf` — halaman 428

Blok: D. Basis Bank
> Tercetak langsung 'NPL gross*)' = KL + Diragukan + Macet

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2024 | `12.609,239` | MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2024 |

## 18. `bmri_2024.pdf` — halaman 1701

Blok: B. KPMM Bank
> Sumber utama CAR & ROE (Bank Mandiri saja)
> Sumber utama CAR (Bank Mandiri saja)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - BANK | 2024 | `229.932,670` | Catatan 65c KPMM (Bank Mandiri saja), kolom 2024 |
| ✓ | Total Modal - BANK | 2024 | `244.258,632` | Catatan 65c KPMM (Bank Mandiri saja), kolom 2024 |
| ✓ | Total ATMR - BANK | 2024 | `1.215.157,443` | Catatan 65c KPMM (Bank Mandiri saja), kolom 2024 |

## 19. `bmri_2024.pdf` — halaman 1714

Blok: D. Basis Bank
> Baris 'Dikurangi: cadangan kerugian penurunan nilai' di bawah Kredit
> Baris 'TOTAL ASET' Neraca Entitas Induk
> Subtotal 'Kredit yang diberikan' sebelum dikurangi CKPN

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2024 | `1.310.779,402` | Neraca Entitas Induk (bagian 2), kolom 2024 |
| ✓ | CKPN Kredit - BANK | 2024 | `38.257,611` | Neraca Entitas Induk (bagian 2), kolom 2024 |
| ✓ | Total Aset - BANK (Entitas Induk) | 2024 | `1.877.321,726` | Neraca Entitas Induk (bagian 2), kolom 2024 |

## 20. `bmri_2024.pdf` — halaman 1715

Blok: D. Basis Bank
> Tercetak langsung 'Total simpanan nasabah'

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2024 | `1.326.887,854` | Neraca Entitas Induk (Liabilitas), baris 'Total simpanan nasabah', kolom 2024 |

## 21. `bmri_2024.pdf` — halaman 1718

Blok: D. Basis Bank
> Baris 'LABA SEBELUM BEBAN PAJAK' (dipakai untuk ROA SEOJK)
> Baris 'LABA TAHUN BERJALAN' (dipakai untuk ROE SEOJK)
> Baris 'PENDAPATAN BUNGA - NETO'

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Pendapatan Bunga Neto - BANK (Entitas Induk) | 2024 | `75.829,984` | Laba Rugi Entitas Induk, kolom 2024 |
| ✓ | Laba Sebelum Pajak - BANK (Entitas Induk) | 2024 | `63.026,222` | Laba Rugi Entitas Induk, kolom 2024 |
| ✓ | Laba Bersih (Laba Tahun Berjalan) - BANK (Entitas Induk) | 2024 | `51.135,963` | Laba Rugi Entitas Induk, kolom 2024 |

## 22. `bmri_2025.pdf` — halaman 36

Blok: A. Ikhtisar

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Total Aset | 2022 | `1.992.544,687` | kolom 2022 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Aset | 2023 | `2.174.219,449` | kolom 2023 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Aset | 2024 | `2.427.223,262` | kolom 2024 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Aset | 2025 | `2.829.948,026` | kolom 2025 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Kredit (Kredit & Pembiayaan Syariah Konsolidasian) | 2022 | `1.172.599,882` | kolom 2022 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Kredit (Kredit & Pembiayaan Syariah Konsolidasian) | 2023 | `1.359.832,195` | kolom 2023 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Kredit (Kredit & Pembiayaan Syariah Konsolidasian) | 2024 | `1.623.216,612` | kolom 2024 pada Ikhtisar Neraca Konsolidasian (Aset) |
| ✓ | Total Kredit (Kredit & Pembiayaan Syariah Konsolidasian) | 2025 | `1.849.967,956` | kolom 2025 pada Ikhtisar Neraca Konsolidasian (Aset) |

## 23. `bmri_2025.pdf` — halaman 38

Blok: A. Ikhtisar

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Pendapatan Bunga dan Syariah - Neto | 2022 | `87.903,354` | kolom 2022 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Pendapatan Bunga dan Syariah - Neto | 2023 | `95.886,574` | kolom 2023 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Pendapatan Bunga dan Syariah - Neto | 2024 | `101.756,920` | kolom 2024 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Pendapatan Bunga dan Syariah - Neto | 2025 | `106.210,035` | kolom 2025 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Sebelum Pajak | 2022 | `56.377,726` | kolom 2022 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Sebelum Pajak | 2023 | `74.684,881` | kolom 2023 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Sebelum Pajak | 2024 | `76.403,486` | kolom 2024 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Sebelum Pajak | 2025 | `76.417,563` | kolom 2025 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih (Laba Tahun Berjalan) | 2022 | `44.952,368` | kolom 2022 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih (Laba Tahun Berjalan) | 2023 | `60.051,870` | kolom 2023 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih (Laba Tahun Berjalan) | 2024 | `61.165,121` | kolom 2024 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih (Laba Tahun Berjalan) | 2025 | `61.346,133` | kolom 2025 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2022 | `41.170,637` | kolom 2022 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2023 | `55.060,057` | kolom 2023 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2024 | `55.782,742` | kolom 2024 pada Ikhtisar Laba Rugi Konsolidasian |
| ✓ | Laba Bersih - atribusi pemilik entitas induk | 2025 | `56.293,950` | kolom 2025 pada Ikhtisar Laba Rugi Konsolidasian |

## 24. `bmri_2025.pdf` — halaman 354

Blok: D. Basis Bank
> Tercetak langsung 'NPL gross*)' = KL + Diragukan + Macet

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit Bermasalah KL+D+Macet, nominal - BANK | 2025 | `14.367,697` | MD&A Kolektibilitas Piutang Bank (Bank saja), baris 'NPL gross*)', kolom 2025 |

## 25. `bmri_2025.pdf` — halaman 1432

Blok: B. KPMM Bank
> Sumber utama CAR & ROE (Bank Mandiri saja)
> Sumber utama CAR (Bank Mandiri saja)

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Modal Inti (Tier 1) - BANK | 2025 | `238.082,036` | Catatan 65c KPMM (Bank Mandiri saja), kolom 2025 |
| ✓ | Total Modal - BANK | 2025 | `253.294,877` | Catatan 65c KPMM (Bank Mandiri saja), kolom 2025 |
| ✓ | Total ATMR - BANK | 2025 | `1.308.455,053` | Catatan 65c KPMM (Bank Mandiri saja), kolom 2025 |

## 26. `bmri_2025.pdf` — halaman 1456

Blok: D. Basis Bank
> Baris 'Dikurangi: cadangan kerugian penurunan nilai' di bawah Kredit
> Baris 'TOTAL ASET' Neraca Entitas Induk
> Subtotal 'Kredit yang diberikan' sebelum dikurangi CKPN

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Kredit yang Diberikan BRUTO - BANK | 2025 | `1.497.108,664` | Neraca Entitas Induk (bagian 2), kolom 2025 |
| ✓ | CKPN Kredit - BANK | 2025 | `36.284,414` | Neraca Entitas Induk (bagian 2), kolom 2025 |
| ✓ | Total Aset - BANK (Entitas Induk) | 2025 | `2.228.096,582` | Neraca Entitas Induk (bagian 2), kolom 2025 |

## 27. `bmri_2025.pdf` — halaman 1457

Blok: D. Basis Bank
> Tercetak langsung 'Total simpanan nasabah'

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Dana Pihak Ketiga (DPK) - BANK | 2025 | `1.674.679,144` | Neraca Entitas Induk (Liabilitas), baris 'Total simpanan dari nasabah', kolom 2025 |

## 28. `bmri_2025.pdf` — halaman 1460

Blok: D. Basis Bank
> Baris 'LABA SEBELUM BEBAN PAJAK' (dipakai untuk ROA SEOJK)
> Baris 'LABA TAHUN BERJALAN' (dipakai untuk ROE SEOJK)
> Baris 'PENDAPATAN BUNGA - NETO'

| ✓ | Item | Tahun | Nilai di xlsx (miliar Rp) | Lihat di PDF |
|---|---|---|---|---|
| ✓ | Pendapatan Bunga Neto - BANK (Entitas Induk) | 2025 | `78.300,753` | Laba Rugi Entitas Induk, kolom 2025 |
| ✓ | Laba Sebelum Pajak - BANK (Entitas Induk) | 2025 | `63.464,981` | Laba Rugi Entitas Induk, kolom 2025 |
| ✓ | Laba Bersih (Laba Tahun Berjalan) - BANK (Entitas Induk) | 2025 | `51.539,726` | Laba Rugi Entitas Induk, kolom 2025 |

---

## Verifikasi 18 Rasio Resmi (`2_rasio_resmi`) — `bmri_2025.pdf` hal. 39–40

*(Tercetak 2 desimal langsung di tabel `RASIO KEUANGAN (BANK ONLY)` dan identik di `bmri_2024.pdf` hal. 34–35 serta `bmri_2023.pdf` hal. 36–37.)*

| ✓ | Tahun | Rasio | Nilai resmi (%) | Sumber silang |
|---|---|---|---|---|
| ✓ | 2023 | CAR | `21,48%` | Catatan 58/65c KPMM |
| ✓ | 2023 | ROA | `4,03%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2023 | ROE | `27,31%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2023 | NIM | `5,25%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2023 | NPL | `1,02%` | MD&A Kolektibilitas & Cat. 12/65 |
| ✓ | 2023 | LDR | `86,75%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2024 | CAR | `20,10%` | Catatan 58/65c KPMM |
| ✓ | 2024 | ROA | `3,59%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2024 | ROE | `24,19%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2024 | NIM | `4,93%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2024 | NPL | `0,97%` | MD&A Kolektibilitas & Cat. 12/65 |
| ✓ | 2024 | LDR | `98,04%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2025 | CAR | `19,36%` | Catatan 58/65c KPMM |
| ✓ | 2025 | ROA | `3,19%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2025 | ROE | `23,15%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2025 | NIM | `4,59%` | MD&A Rentabilitas/Likuiditas |
| ✓ | 2025 | NPL | `0,96%` | MD&A Kolektibilitas & Cat. 12/65 |
| ✓ | 2025 | LDR | `88,92%` | MD&A Rentabilitas/Likuiditas |

---

## Rincian 2 Item Hitungan (dalam JUTA Rupiah seperti tertulis di PDF)

### 1. Dana Pihak Ketiga Konsolidasian (`bmri_2025.pdf` hal. 36 & 37)

BMRI mengonsolidasi Bank Syariah Indonesia (BSI), sehingga dana nasabah konsolidasi terdiri dari **Simpanan Nasabah** (hal. 36) + **Dana Syirkah Temporer — Simpanan Nasabah** (hal. 37):

```
  Tahun   Simpanan Nasabah      + Dana Syirkah Nasabah   = DPK Konsolidasian (juta Rp)
  2022    1.295.575.929         +   195.268.663          = 1.490.844.592
  2023    1.351.448.149         +   225.501.470          = 1.576.949.619
  2024    1.446.234.957         +   252.661.959          = 1.698.896.916
  2025    1.816.897.208         +   288.866.943          = 2.105.764.151
```

### 2. Aset Produktif Inti — BANK (Neraca Entitas Induk: hal. 1501–1502 / 1713–1714 / 1455–1456)

BMRI tidak mencetak 1 baris ringkasan 'Total Aset Produktif' di Ikhtisar. Aset produktif berbunga inti Bank = Penempatan (neto) + Efek-efek (neto) + Obligasi Pemerintah + Reverse Repo + Kredit yang Diberikan (bruto):

```
  Tahun   Penempatan    + Efek-efek     + Obligasi Pem.  + Reverse Repo  + Kredit Bruto    = Total (juta Rp)
  2022    78.360.194    + 44.932.352    + 262.007.141    +  6.312.523    +   932.639.051   = 1.324.251.261
  2023    55.274.570    + 43.134.871    + 239.245.751    + 16.205.580    + 1.085.787.427   = 1.439.648.199
  2024    22.667.518    + 44.703.514    + 221.138.442    +  7.166.266    + 1.310.779.402   = 1.606.455.142
  2025    19.689.791    + 81.717.307    + 219.792.906    +  2.771.530    + 1.497.108.664   = 1.821.080.198
```

---

## Cross-check Gratis Antar Laporan Tahunan

Angka tahun 2023 dan 2024 muncul di **dua** laporan tahunan (tahun berjalan & pembanding tahun berikutnya) — seluruhnya sudah dicek otomatis identik 100%:

| Item | Tahun | Sumber utama | Sumber silang |
|---|---|---|---|
| Modal Inti, Total Modal, ATMR — BANK | 2024 | `bmri_2024.pdf` h1701 | `bmri_2025.pdf` h1432 (kolom 2024) |
| Modal Inti, Total Modal, ATMR — BANK | 2023 | `bmri_2023.pdf` h1425 | `bmri_2024.pdf` h1701 (kolom 2023) |
| Kredit Bruto, CKPN, DPK, Total Aset — BANK | 2024 | `bmri_2024.pdf` h1714–1715 | `bmri_2025.pdf` h1456–1457 (kolom 2024) |
| Kredit Bruto, CKPN, DPK, Total Aset — BANK | 2023 | `bmri_2023.pdf` h1502–1503 | `bmri_2024.pdf` h1714–1715 (kolom 2023) |
| Pendapatan Bunga Neto, PBT, Laba Bersih — BANK | 2024 | `bmri_2024.pdf` h1718 | `bmri_2025.pdf` h1460 (kolom 2024) |
| Pendapatan Bunga Neto, PBT, Laba Bersih — BANK | 2023 | `bmri_2023.pdf` h1506 | `bmri_2024.pdf` h1718 (kolom 2023) |
| NPL nominal — BANK (`KL+D+M`) | 2022–2024 | `bmri_2024.pdf` h428 | `bmri_2025.pdf` h354 (tabel 5 tahun) |
| Ikhtisar Konsolidasian & Rasio Resmi | 2022–2024 | `bmri_2025.pdf` h36–40 | `bmri_2024.pdf` h30–35 & `bmri_2023.pdf` h35–37 |

## Status verifikasi (26-11-2026)

- [x] Seluruh 92 angka mentah + 18 rasio resmi diverifikasi visual terhadap render gambar 30 halaman PDF asli BMRI (`bmri_2023..2025.pdf`) + uji aritmetika & cross-check antar laporan
- [x] 1 koreksi penjumlahan diterapkan (`Aset Produktif Inti Bank 2023`: `1.439.648,229` → `1.439.648,199` miliar, selisih 30 juta Rp)
- [x] `VERIFIED_ROWS` & `OFFICIAL_VERIFIED` diperbarui di `scripts/build_ground_truth_bmri.py` (`v 26/11/26`) dan `data/ground_truth_bmri.xlsx` dibangun ulang
- [x] Verifikasi dicatat di `docs/PANDUAN_MINGGU8.md` & `docs/ROADMAP.md`