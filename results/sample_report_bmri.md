# Laporan Analisis Keuangan — PT Bank Mandiri (Persero) Tbk (BMRI)

**Periode:** 2023–2025 | **Sektor:** Perbankan Konvensional (SEOJK No.9/SEOJK.03/2020) | **Status Validasi:** Tervalidasi (OJK/SEOJK)

> **Pertanyaan Pengguna:** Analisis kondisi keuangan, rasio prudensial OJK, tren 2023-2025, serta konteks pasar dan regulasi untuk PT Bank Mandiri (Persero) Tbk (BMRI).
>
> **Jawaban Ringkas:** Bank Mandiri mempertahankan permodalan yang sangat kuat dengan CAR 21,48% pada 2023 menurun menjadi 19,36% pada 2025 (hal. 402, 1701, 1432). Profitabilitas aset meningkat tajam pada 2024 (ROA 2,74%) setelah 2023 yang nol, namun data ROA 2025 tidak tersedia (hal. 1072, 30). NPL menurun dari 1,94% menjadi 0,96% pada 2025, menunjukkan kualitas kredit yang semakin sehat (hal. 380, 428, 354). LDR membaik signifikan dari 136,14% ke 89,40%, mengindikasikan likuiditas yang lebih seimbang (hal. 852, 1714, 1456).

## 1. Ringkasan Eksekutif

Bank Mandiri (BMRI) menunjukkan posisi permodalan yang sangat kuat selama periode 2023‑2025, dengan Capital Adequacy Ratio (CAR) tetap jauh di atas ambang minimum OJK 8% (21,48%‑20,10%‑19,36%). Profitabilitas aset mengalami perbaikan signifikan pada 2024 (ROA 2,74% > ambang 1,5%) namun data ROA 2025 belum tersedia, sementara Return on Equity (ROE) tetap berada di atas 15% sepanjang periode, menandakan pengembalian modal yang baik. Kualitas aset terus membaik, tercermin dari penurunan NPL dari 1,94% ke 0,96%, dan likuiditas membaik dengan penurunan LDR dari 136,14% ke 89,40%, mendekati rentang ideal BI/OJK 78‑92%. NIM tidak tersedia, sehingga analisis profitabilitas margin bunga tidak dapat dilakukan.

## 2. Rasio Keuangan & Interpretasi

CAR tetap jauh di atas batas minimum OJK 8% selama tiga tahun, menegaskan permodalan yang sangat kuat (hal. 402, 1701, 1432). ROA pada 2023 sebesar 0,00% berada jauh di bawah ambang sangat sehat >1,5% (hal. 1072, 1077, 1506, 1507), namun naik menjadi 2,74% pada 2024, melampaui ambang tersebut (hal. 30, 1077, 1718); data ROA 2025 tidak tersedia. ROE berada di atas 15% pada semua tahun, menandakan tingkat pengembalian modal inti yang sangat baik (hal. 402, 1506, 1507, 1701, 1432). NIM tidak tersedia untuk 2023‑2025 (status insufficient_data). NPL menurun dari 1,94% ke 0,96%, tetap jauh di bawah batas maksimum OJK 5% dan mendekati kriteria sangat sehat <2% (hal. 380, 428, 354). LDR menurun signifikan dari 136,14% ke 89,40%, bergerak dari kondisi likuiditas ketat ke dalam rentang ideal BI/OJK 78‑92% (hal. 852, 1714, 1456).

### Tabel Rasio Keuangan & Evaluasi Ambang OJK

| Rasio | 2023 | 2024 | 2025 | Ambang OJK | Status Terbaru | Sumber |
|---|---:|---:|---:|---|---|---|
| **CAR** | 21,48% | 20,10% | 19,36% | batas minimum OJK 8% (POJK KPMM) | Sangat Kuat (Memenuhi) | hal. 402, 1432, 1701 |
| **ROA** | 0,00% | 2,74% | Tidak tersedia (*insufficient_data*) | ambang sangat sehat > 1,5% (SEOJK Tingkat Kesehatan Bank) | Data tidak cukup | hal. 30, 1072, 1077, 1506, 1507, 1718 |
| **ROE** | 26,15% | 23,26% | 26,22% | acuan sangat baik > 15% | Sangat Baik (Memenuhi) | hal. 347, 402, 1432, 1506, 1507, 1701, 1718 |
| **NIM** | Tidak tersedia (*insufficient_data*) | Tidak tersedia (*insufficient_data*) | Tidak tersedia (*insufficient_data*) | - | Data tidak cukup | - |
| **NPL** | 1,94% | 0,96% | 0,96% | batas maksimum OJK < 5% (< 2% sangat sehat) | Sangat Sehat (Memenuhi) | hal. 354, 380, 428, 852, 1456, 1714 |
| **LDR** | 136,14% | 98,79% | 89,40% | rentang ideal BI/OJK 78–92% | Ideal OJK (Memenuhi) | hal. 852, 1456, 1457, 1458, 1503, 1714, 1715, 1716 |

**Basis & Formula Perhitungan:**
- **CAR:** Bank saja (Catatan KPMM — saldo akhir)
- **ROA:** Bank saja / Konsolidasian (rata-rata total aset, standar SEOJK PBT)
- **ROE:** Bank saja (rata-rata Modal Inti Tier 1)
- **NIM:** Pendapatan bunga neto dibagi rata-rata aset produktif
- **NPL:** Bank saja (NPL bruto KL+D+Macet dibagi kredit bruto Bank)
- **LDR:** Bank saja (kredit bruto Bank dibagi DPK Bank)

**Catatan Rasio Tidak Dihitung (Transparansi Anti-Halusinasi):**
- **ROA (2025)**: tidak dihitung (input kurang: profit_before_tax_bank[2025]).
- **NIM (2023)**: tidak dihitung (input kurang: earning_assets[2023]).
- **NIM (2024)**: tidak dihitung (input kurang: earning_assets[2024]).
- **NIM (2025)**: tidak dihitung (input kurang: earning_assets[2025]).

### Tabel Komponen Metrik Keuangan Kunci

| Komponen Keuangan | Basis | 2023 | 2024 | 2025 | Sumber |
|---|---|---:|---:|---:|---|
| Total Aset (Konsolidasian) | Konsolidasian | Rp 2.174.219.449 juta | Rp 2.427.223.262 juta | Rp 2.829.948.026 juta | hal. 30, 36, 1077 (catatan: sel gabungan) |
| Pendapatan Bunga Bersih (Konsolidasian) | Konsolidasian | Rp 95.886.574 juta | Tidak tersedia | Rp 106.210.035 juta | hal. 347, 1078 (catatan: sel gabungan) |
| Laba Bersih / Laba Tahun Berjalan (Konsolidasian) | Konsolidasian | Rp 60.051.870 juta | Rp 61.165.121 juta | Rp 61.346.133 juta | hal. 33, 347, 1079 |
| Modal Inti / Tier 1 (Bank) | Bank (Entitas Induk) | Rp 209.724.274 juta | Rp 229.932.670 juta | Rp 238.082.036 juta | hal. 402, 1432, 1701 |
| Total ATMR (Bank) | Bank (Entitas Induk) | Rp 1.033.407.212 juta | Rp 1.215.157.443 juta | Rp 1.308.455.053 juta | hal. 402, 1432, 1701 |
| Kredit yang Diberikan Bruto (Bank) | Bank (Entitas Induk) | Rp 1.691.043.965 juta | Rp 1.310.779.402 juta | Rp 1.497.108.664 juta | hal. 852, 1456, 1714 |
| Dana Pihak Ketiga / Simpanan Nasabah (Bank) | Bank (Entitas Induk) | Rp 1.242.145.598 juta | Rp 1.326.887.854 juta | Rp 1.674.679.144 juta | hal. 1457, 1458, 1503, 1715, 1716 (catatan: sel gabungan) |
| Kredit Bermasalah / NPL Nominal Bruto (Bank) | Bank (Entitas Induk) | Rp 32.749.796 juta | Rp 12.609.239 juta | Rp 14.367.697 juta | hal. 354, 380, 428 |
| Total Modal (Bank) | Bank (Entitas Induk) | Rp 221.988.279 juta | Rp 244.258.632 juta | Rp 253.294.877 juta | hal. 402, 1432, 1701 |
| CKPN Kredit yang Diberikan (Bank) | Bank (Entitas Induk) | Rp 43.486.573 juta | Rp 38.257.611 juta | Rp 36.284.414 juta | hal. 852, 1456, 1714 |
| Total Aset Produktif | Konsolidasian | Tidak tersedia | Tidak tersedia | Tidak tersedia | - |
| Total Aset (Bank / Entitas Induk) | Bank (Entitas Induk) | Tidak tersedia | Tidak tersedia | Rp 2.228.096.582 juta | hal. 1456 |
| Pendapatan Bunga Neto (Bank / Entitas Induk) | Bank (Entitas Induk) | Rp 71.226.722 juta | Rp 75.829.984 juta | Tidak tersedia | hal. 1506, 1507, 1718 (catatan: sel gabungan) |
| Laba Sebelum Pajak (Bank / Entitas Induk) | Bank (Entitas Induk) | Rp 98.094 juta | Rp 63.026.222 juta | Tidak tersedia | hal. 1506, 1507, 1718 (catatan: sel gabungan) |
| Laba Bersih / Laba Tahun Berjalan (Bank / Entitas Induk) | Bank (Entitas Induk) | Rp 51.096.878 juta | Rp 51.135.963 juta | Tidak tersedia | hal. 1506, 1507, 1718 (catatan: sel gabungan) |

*Catatan: saldo pembanding tahun 2022 turut digunakan secara internal untuk menghitung rata-rata penyebut rasio (ROA, ROE, NIM).*
*Catatan: penanda sel gabungan menunjukkan tabel sumber PDF memiliki baris/sel rapat hasil parsing Docling.*

## 3. Tren Antar Tahun

CAR menunjukkan penurunan bertahap sebesar 2,12 poin persentase (21,48% → 19,36%) antara 2023‑2025, menandakan penurunan moderat dalam permodalan meskipun masih kuat. ROA melompat +2,73 pp pada 2024 (0,00% → 2,74%) namun tidak tersedia untuk 2025, sehingga tren jangka panjang tidak dapat dipastikan. ROE sedikit naik sebesar 0,07 pp (26,15% → 26,22%) menunjukkan stabilitas pengembalian modal. NPL turun -0,98 pp, memperkuat kualitas kredit. LDR turun drastis -46,74 pp, memperbaiki likuiditas bank. NIM tidak tersedia, sehingga tidak dapat dianalisis trennya.

| Rasio | Periode | Nilai Awal | Nilai Akhir | Perubahan | Arah Tren |
|---|---|---:|---:|---:|---|
| **CAR** | 2023–2025 | 21,48% | 19,36% | -2,12 pp | Turun |
| **ROA** | 2023–2024 | 0,00% | 2,74% | +2,73 pp | Naik |
| **ROE** | 2023–2025 | 26,15% | 26,22% | +0,07 pp | Naik |
| **NPL** | 2023–2025 | 1,94% | 0,96% | -0,98 pp | Turun |
| **LDR** | 2023–2025 | 136,14% | 89,40% | -46,74 pp | Turun |

## 4. Konteks Pasar & Regulasi

Berita resmi Bank Mandiri menyatakan bahwa fundamental keuangan tetap solid hingga 2025 dengan total aset tumbuh 16,6% YoY menjadi Rp2,829,9 triliun [Bank Mandiri News](https://www.bankmandiri.co.id/en/news-detail?primaryKey=543173597&backUrl=%2Fnews). Pada akhir November 2025, kredit bank meningkat 13,1% YoY menjadi Rp1.452 triliun, menegaskan pertumbuhan kredit yang kuat [Press Release 2025](https://www.bankmandiri.co.id/in/web/guest/press-detail?primaryKey=522668354&backUrl=%2Fin%2Fpress%3Fp_p_id%3DPressReleasePortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_PressReleasePortlet_year=2025). Laporan OJK Triwulan II 2025 mencatat LDR rata‑rata perbankan sebesar 86,40%, sejalan dengan penurunan LDR BMRI menjadi 89,40% pada 2025, menunjukkan perbaikan likuiditas di sektor (OJK Surveillance).

### Daftar Sumber Berita & Regulasi

1. **[news-detail](https://www.bankmandiri.co.id/en/news-detail?primaryKey=543173597&backUrl=%2Fnews)**  
   Sumber: `bankmandiri.co.id` · Tanggal: `tanggal tidak tersedia` · Kategori: Kinerja Emiten · Sentimen: Positif  
   Ringkasan: Bank Mandiri mempertahankan fundamental keuangan solid hingga 2025 dengan total aset tumbuh 16,6% YoY menjadi Rp2.829,9 triliun.
2. **[Press Detail](https://www.bankmandiri.co.id/in/web/guest/press-detail?primaryKey=522668354&backUrl=%2Fin%2Fpress%3Fp_p_id%3DPressReleasePortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_PressReleasePortlet_year=2025)**  
   Sumber: `bankmandiri.co.id` · Tanggal: `tanggal tidak tersedia` · Kategori: Kinerja Emiten · Sentimen: Positif  
   Ringkasan: Bank Mandiri mencatat pertumbuhan kredit 13,1% YoY menjadi Rp1.452 triliun pada akhir November 2025, menunjukkan kinerja positif.
3. **[Book1](https://www.bankmandiri.co.id/documents/38265486/0/Publikasi+Koran+per+31+Desember+2025.pdf/db1dbfc0-cb20-ca02-47a8-1d835122639e?t=1770282672378)**  
   Sumber: `bankmandiri.co.id` · Tanggal: `tanggal tidak tersedia` · Kategori: Kinerja Emiten · Sentimen: Netral  
   Ringkasan: Laporan laba rugi dan penghasilan komprehensif PT Bank Mandiri tahun 2025 dan 2024 disajikan dalam format audit konsolidasi.
4. **[Press Detail](https://www.bankmandiri.co.id/en/web/guest/press-detail?primaryKey=588901355&backUrl=%2Fen%2Fpress)**  
   Sumber: `bankmandiri.co.id` · Tanggal: `tanggal tidak tersedia` · Kategori: Kinerja Emiten · Sentimen: Positif  
   Ringkasan: Bank Mandiri memperkuat ekosistem bisnis, UMKM, dan ekonomi kreatif, dengan total aset mencapai Rp2.245 triliun dan tumbuh 16,2%.
5. **[Laporan Surveillance Perbankan Indonesia - Triwulan II 2025. ...](https://www.ojk.go.id/id/kanal/perbankan/data-dan-statistik/laporan-profil-industri-perbankan/Documents/Laporan%20Surveillance%20Perbankan%20Indonesia%20-%20Triwulan%20II%202025.pdf)**  
   Sumber: `ojk.go.id` · Tanggal: `tanggal tidak tersedia` · Kategori: Makro & Sektor · Sentimen: Netral  
   Ringkasan: Laporan OJK Triwulan II 2025 mencatat LDR perbankan 86,40% dan penurunan suku bunga yang mengindikasikan kebutuhan dana short‑term.

## 5. Kesimpulan

Bank Mandiri menunjukkan permodalan yang kuat, profitabilitas aset yang membaik, kualitas kredit yang semakin sehat, dan likuiditas yang kembali ke dalam rentang ideal. Namun, analisis terbatas oleh tidak tersedianya data NIM sepanjang periode dan ROA tahun 2025, sehingga penilaian lengkap atas profitabilitas margin bunga tidak dapat dilakukan.

### Catatan Keterbatasan & Penafian

- Seluruh angka laporan keuangan dan rasio dihitung secara deterministik dari laporan tahunan terverifikasi; metrik atau rasio yang tidak memiliki komponen lengkap dilaporkan jujur sebagai *tidak tersedia*.
- Laporan ini disusun untuk tujuan analisis informatif/akademis dan **bukan merupakan rekomendasi beli atau jual saham**.

### Indeks Sumber Data

- **Laporan Tahunan BMRI 2022:** hal. 402, 1072
- **Laporan Tahunan BMRI 2023:** hal. 380, 402, 852, 1072, 1077, 1078, 1079, 1503, 1506, 1507
- **Laporan Tahunan BMRI 2024:** hal. 30, 33, 402, 428, 1077, 1701, 1714, 1715, 1716, 1718
- **Laporan Tahunan BMRI 2025:** hal. 36, 347, 354, 1432, 1456, 1457, 1458, 1701
- **Sumber Eksternal Terverifikasi (Tavily):** 5 tautan (tercantum pada Bagian 4).
