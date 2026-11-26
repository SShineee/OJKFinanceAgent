# Panduan Rinci Minggu 7 — Hybrid Search + RRF

Tujuan minggu ini adalah satu fungsi pencarian yang dipakai semua agen mulai Minggu 9:

```python
hybrid_retrieve("Berapa CAR bank BCA tahun 2024?", ticker="bbca", year=2024)   # -> 5 chunk terbaik
```

Fungsi ini menggabungkan pencarian **dense** (BGE-M3 di ChromaDB) dan **sparse** (BM25) dengan
**Reciprocal Rank Fusion (RRF)**. Kode saham **wajib** diisi, supaya angka satu bank tidak pernah
terambil untuk bank lain. Kualitasnya diukur dengan 15 query uji (eksperimen 7.5, bahan Bab 4).

> **GATE 3:** Hit@5 hybrid ≥ 80% pada 15 query uji BBCA.

Perkiraan kerja: **3–4 hari**. Semua kode dijalankan dari venv (`(.venv)` harus muncul di prompt).

---

## Status gerbang

- **Minggu 6 selesai** (15-11-2026): 1.552 chunk terindeks di ChromaDB + BM25, dan
  `check_index.py` LULUS.
- Minggu 7 **tidak bergantung** pada bimbingan.
- **Keputusan 7.A dan 7.B disetujui** (15-11-2026):
  - 7.A: query diperluas dengan istilah perbankan sebelum mencari;
  - 7.B: "chunk yang benar" = chunk yang memuat angka jawabannya.
- ⚠️ Bimbingan 1.6 masih tertunda. Bawa juga Keputusan 7.B ke sana, karena itu definisi metrik
  evaluasi yang ditulis di Bab 3.

---

## Hasil pengecekan sebelum panduan ini ditulis (15-11-2026)

Rancangan di bawah sudah diuji dengan prototipe pada pustaka Minggu 6 (1.552 chunk) dan 15 query
uji (Langkah 1). Rancangan awal roadmap tidak cukup untuk lulus GATE 3.

| Yang dicek | Hasil | Akibatnya |
|---|---|---|
| Hit@5 **tanpa** perluasan istilah | dense 7/15, BM25 12/15, **hybrid 11/15 (73%)** | **tidak lulus** GATE 3 (≥ 80%) |
| Hit@5 **dengan** perluasan istilah (CKPN → "cadangan kerugian penurunan nilai", dst.) | dense 9/15, BM25 **15/15**, **hybrid 13/15 (87%)** | lulus. Keputusan 7.A |
| … khusus 7 query bersingkatan (DPK, CAR, NPL, CKPN, LDR, ROE) | hybrid **4/7 → 6/7**; BM25 4/7 → 7/7 | hipotesis proposal "singkatan menyulitkan" terbukti, dan perluasan istilah adalah solusinya |
| … 8 query tanpa singkatan | hybrid 7/8, dengan maupun tanpa perluasan | perluasan tidak merugikan query biasa |
| Hybrid vs BM25 saja | **BM25 15/15 > hybrid 13/15**. Dense menaruh chunk yang tidak relevan di peringkat atas, sehingga jawaban di peringkat 4 BM25 (CKPN 2023, total ekuitas 2024) terdorong keluar top-5 | **bertentangan dengan hipotesis proposal** "hybrid unggul". Harus dilaporkan jujur di Bab 4 (lihat "Dampak") |
| Dense pada query angka | 9/15. Contoh: "pendapatan bunga bersih 2025" tidak masuk 10 besar | embedding tabel besar lemah untuk pencarian angka. Bahan pembahasan Bab 4 |
| Nilai `k` RRF: 10, 60, 100 (tugas 7.6) | Hit@5 **sama persis** di ketiganya | `RRF_K = 60` (bawaan literatur) dipertahankan |
| Jumlah kandidat per daftar: 5 / 10 / 20 / 30 | hybrid 12 / **13** / 13 / 13 | `TOP_K_DENSE = TOP_K_SPARSE = 10` dipertahankan |
| **Tanpa filter tahun** (`year=None`), tahun hanya di teks query | hybrid **9/15**, dan **45 dari 75** chunk top-5 berasal dari laporan tahun lain. Laporan 2025 juga memuat kolom pembanding 2024, dan seterusnya | Pertanyaan bertahun **wajib** memakai filter `year`. Pertanyaan lintas tahun dicari **per tahun**, bukan sekaligus (Langkah 3) |
| Latensi `hybrid_retrieve` (dense + BM25 + RRF + perluasan) | **±19 ms per query** (model sudah dimuat) | cepat; bukan hambatan |

**Catatan metodologi.** Parameter (`k` RRF, jumlah kandidat) **tidak disetel** memakai 15 query
GATE. Yang diuji hanya nilai bawaan dan beberapa nilai pembanding, dan semua hasilnya dicatat. Daftar
istilah (7.A) disusun dari istilah perbankan baku, **bukan** dari query yang gagal. Dengan begitu
angka 87% tidak terlalu optimistis.

---

## Keputusan 7.A — perluasan istilah perbankan: ya (disarankan) atau tidak

> ✅ **DISETUJUI 15-11-2026: pakai perluasan istilah.** Eksperimen 7.5 tetap melaporkan hasil
> dengan dan tanpa perluasan.

Sebelum mencari, query diberi tambahan istilah lengkap dari daftar tetap, misalnya
`"Berapa CKPN kredit BCA 2023?"` → `"Berapa CKPN kredit BCA 2023? (cadangan kerugian penurunan nilai)"`.

| | **Dengan perluasan** (disarankan) | Tanpa |
|---|---|---|
| Hit@5 hybrid | **13/15 (87%)**, lulus | 11/15 (73%), tidak lulus |
| Query bersingkatan | 6/7 | 4/7 |
| Biaya | tanpa panggilan LLM, deterministik, < 1 ms | — |

**Saran: pakai perluasan.** Laporan keuangan menulis istilah lengkap ("cadangan kerugian penurunan
nilai", "simpanan dari nasabah"), sedangkan pengguna dan agen menulis singkatan. Di Bab 4,
eksperimen 7.5 melaporkan **keduanya** (dengan dan tanpa perluasan), sehingga kontribusinya
terukur.

Daftarnya **khusus perbankan** (profil sektor yang divalidasi). Untuk sektor lain, istilah
perbankan tidak muncul di query, jadi tidak berpengaruh.

---

## Keputusan 7.B — definisi "chunk yang benar" untuk Hit@5

> ✅ **DISETUJUI 15-11-2026: (a) chunk yang memuat angka jawabannya**, dalam satuan apa pun, dari
> laporan tahun itu. Ditulis eksplisit di Bab 3 dan dibawa ke bimbingan.

| Definisi | Hasil prototipe (hybrid + perluasan) | Catatan |
|---|---|---|
| **(a) Chunk memuat angka jawabannya**, dalam bentuk mana pun (juta, miliar, triliun, persen), dari laporan tahun itu (disarankan) | **13/15** | sesuai kebutuhan agen: yang penting angkanya bisa dibaca. Dicek **otomatis** lewat pola angka |
| (b) Chunk berasal dari halaman sumber ground truth saja | jauh lebih rendah (pratinjau Minggu 6: 7/15) | terlalu ketat. Angka yang sama tercetak juga di Ikhtisar, analisis manajemen, dan laporan keuangan |

**Saran: (a).** Contohnya, total aset 2025 tercetak di Ikhtisar hal 15 (`1.586.829` miliar) dan di
analisis manajemen hal 202 (`Rp1.586,8 triliun`). Keduanya sama benarnya untuk agen. Definisi ini
ditulis eksplisit di Bab 3, termasuk bentuk angka yang dihitung. Pola angka dibatasi supaya
`54.851` tidak cocok dengan `254.851`.

---

## Langkah 0 — Persiapan · ✅ SELESAI (15-11-2026, `check_index.py --quick` LULUS)

```powershell
python scripts\check_index.py --quick      # indeks Minggu 6 masih utuh -> LULUS
```

---

## Langkah 1 — 15 query uji (7.5) · ✅ SELESAI (15-11-2026)

**File:**
- `eval/datasets/retrieval_queries.jsonl`: dataset, satu baris per query.
- `eval/retrieval_queries.py`: pembaca dataset, pola angka, dan definisi "chunk benar" (Keputusan
  7.B). Dipakai bersama oleh eksperimen (Langkah 4) dan pemeriksaan (Langkah 5).

**Cek:** `python -m eval.retrieval_queries`

Set ini **dikunci** dengan SHA-256
`cfab3a1830003cc868ef2c069a2d9364d8dad0d7ce232a6005a3e5ed07246fc2`. Jangan diganti setelah melihat
hasil, karena itu membuat Hit@5 terlalu optimistis. Eksperimen di Langkah 4 mencetak hash yang
dipakai, jadi perubahan akan terlihat.

```json
{"id": "q04", "query": "Berapa CAR bank BCA tahun 2024?", "ticker": "bbca", "year": 2024, "abbreviation": true,
 "answers": [{"type": "percent", "value": 29.36, "gt": {"sheet": "2_rasio_resmi", "row": 8}}]}
```

- **Setiap angka merujuk sel ground truth** (`gt`: sheet + baris + tahun), dan `verify()` memastikan
  angkanya **sama** dengan `ground_truth.xlsx`. Tidak ada angka yang diketik ulang tanpa diperiksa.
- **Jenis jawaban:**
  - `value`: angka dalam miliar dari `1_angka_mentah`;
  - `percent`: rasio resmi dari `2_rasio_resmi`;
  - `component`: dipakai kalau totalnya tidak tercetak. Contohnya DPK bank 2024 = pihak berelasi
    3.260.838 + pihak ketiga 1.105.647.994 (hal 705); `of` merujuk totalnya.
- **Pola pencocokan dibuat oleh kode** (`answer_patterns`):
  - miliar `1.586.829`, boleh diikuti `.xxx` (bentuk juta di laporan keuangan);
  - juta persis kalau nilainya berdesimal, mis. `239.468.855`;
  - triliun satu desimal, `1.586,8 triliun`;
  - persen dengan desimal aslinya dan dibulatkan satu desimal, `29,36%` / `29,4%`.

  Tepinya dibatasi: `54.851` **tidak** cocok dengan `254.851`, `1.054.851`, `54.851,5`, atau
  "Rp54,9 miliar", tetapi cocok dengan `54.851.274` dan "Rp54,9 triliun". Ke-16 kasus batas sudah
  diuji, semuanya benar.

| id | Query | Tahun | Jawaban (GT) | Singkatan | Chunk relevan (prototipe) |
|---|---|---|---|---|---|
| q01 | Berapa total aset BCA tahun 2025? | 2025 | 1.586.829 miliar | – | 2 (hal 15, 202) |
| q02 | Berapa laba bersih BCA tahun 2024? | 2024 | 54.851 miliar | – | 8 |
| q03 | Berapa DPK BCA tahun 2023? | 2023 | 1.101.673 miliar (konsolidasi) / 1.081.852 (bank) | DPK | 3 |
| q04 | Berapa CAR bank BCA tahun 2024? | 2024 | 29,36% / 29,4% | CAR | 5 |
| q05 | Berapa modal inti tier 1 BCA tahun 2025? | 2025 | 258.057.396 (bank) / 273.828.527 (konsol.) juta | – | 10 |
| q06 | Berapa total ATMR konsolidasian BCA tahun 2023? | 2023 | 825.610.552 juta | – | 3 |
| q07 | Berapa nominal NPL BCA tahun 2024? | 2024 | 15.498.016 juta | NPL | 2 (hal 199, 701) |
| q08 | Berapa CKPN kredit yang diberikan BCA tahun 2023? | 2023 | 33.168.491 juta | CKPN | 2 (hal 180, 738–739) |
| q09 | Berapa total ekuitas BCA tahun 2024? | 2024 | 262.835 miliar | – | 4 |
| q10 | Berapa pendapatan bunga bersih BCA tahun 2025? | 2025 | 85.548 miliar | – | 6 |
| q11 | Berapa laba sebelum pajak BCA tahun 2023? | 2023 | 60.180 miliar | – | 2 |
| q12 | Berapa LDR BCA tahun 2024? | 2024 | 78,4% | LDR | 3 |
| q13 | Berapa ROE BCA tahun 2025? | 2025 | 23,3% | ROE | 2 |
| q14 | Berapa total kredit yang diberikan BCA tahun 2025? | 2025 | 992.901 miliar | – | 5 |
| q15 | Berapa DPK entitas induk BCA tahun 2024? | 2024 | 1.105.647.994 (pihak ketiga) juta | DPK | 1 (hal 705) |

- **Komposisi:**
  - 7 query bersingkatan, 8 tidak;
  - **4 / 6 / 5 per tahun** (2023 / 2024 / 2025);
  - mencakup Ikhtisar, KPMM, NPL, CKPN, Entitas Induk, dan rasio resmi.
- **Koreksi:** rancangan awal panduan ini menulis "5 / 5 / 5". `verify()` menangkap kekeliruan itu.
  Query-nya **tidak ditukar**: set ini sudah dijalankan di prototipe, jadi menukar query setelah
  hasilnya diketahui sama dengan memilih-milih. Ketidakseimbangan tahun cukup dicatat.
- Ke-21 angka jawaban **sama** dengan `ground_truth.xlsx`, yang sudah diverifikasi manual di
  Minggu 1.
- Setiap query punya 1–10 chunk benar, tidak ada yang 0. Jumlahnya persis sama dengan prototipe.

---

## Langkah 2 — Perluasan istilah (Keputusan 7.A) · ✅ SELESAI (15-11-2026)

**File:** `src/retrieval/glossary.py`

```python
from src.retrieval.glossary import expand_query, expansions
expand_query("Berapa CKPN kredit yang diberikan BCA tahun 2023?")
# -> "Berapa CKPN kredit yang diberikan BCA tahun 2023? (cadangan kerugian penurunan nilai)"
expansions(query)      # daftar istilah yang ditambahkan, untuk log/jejak agen
```

**Daftar istilah** (`BANK_TERMS`): **18 kelompok, 19 singkatan**, semuanya istilah perbankan baku
(OJK/SEOJK, dan nama rasio di laporan tahunan bank). Daftar ini **tidak** disusun dari query uji
yang gagal.

| Singkatan | Istilah lengkap yang ditambahkan |
|---|---|
| CKPN | cadangan kerugian penurunan nilai |
| DPK | dana pihak ketiga, simpanan dari nasabah |
| NPL | kredit bermasalah, non performing loan |
| CAR, KPMM *(satu kelompok)* | kewajiban penyediaan modal minimum, capital adequacy ratio, rasio kecukupan modal |
| ATMR | aset tertimbang menurut risiko |
| LDR | loan to deposit ratio, rasio kredit terhadap dana pihak ketiga |
| ROE / ROA | return on equity / asset, tingkat pengembalian atas ekuitas / aset |
| NIM | net interest margin, marjin bunga bersih |
| BOPO | beban operasional terhadap pendapatan operasional |
| CASA, LCR, NSFR, GWM, PDN, BMPK, CIR, LAR | istilah lengkap masing-masing *(tambahan; tidak ada di 15 query uji)* |

**Aturan:**
- Singkatan dicocokkan sebagai **kata utuh**, tanpa membedakan huruf besar dan kecil. "Carrefour",
  "card", dan "scar" tidak memicu CAR.
- Satu kelompok ditambahkan **sekali**, dan dilewati kalau teks lengkapnya sudah ada di query.
- **Perubahan dari prototipe: daftar disusun per kelompok sinonim.**
  - Di prototipe, perluasan "CAR" berisi kata "kpmm", yang juga singkatan dalam daftar.
  - Akibatnya, memperluas query yang sudah diperluas (mis. agen memanggil ulang) menambah teks
    baru setiap kali.
  - Sekarang CAR dan KPMM satu kelompok, dan teks sebuah kelompok tidak memuat singkatan kelompok
    lain. Jadi `expand_query` **idempoten**.
- Query yang diperluas dipakai untuk dense **dan** BM25.

### Uji Langkah 2 (semua ✅)

- Teks setiap kelompok hanya memuat singkatan kelompoknya sendiri.
- Ke-19 singkatan diperluas tepat ke kelompoknya.
- Query tanpa singkatan tidak berubah ("total aset", "laba bersih", "Modal Inti (Tier 1)").
- Batas kata: "Carrefour", "card", dan "scar" tidak memicu CAR.
- Sinonim dan duplikat ditambahkan sekali ("CAR dan KPMM serta NPL, npl").
- **Idempoten:** memperluas dua kali menghasilkan teks yang sama, dan istilah lengkap yang sudah
  ada di query tidak ditambahkan lagi.
- **Hasil 15 query uji tetap sama dengan prototipe** walaupun teks kelompok CAR/KPMM berubah: dense
  9/15, BM25 15/15, hybrid 13/15. Gagalnya juga di dua query yang sama: q08 CKPN 2023 dan q09
  total ekuitas 2024. Ini pemeriksaan bahwa perubahan tidak merusak, bukan penyetelan.

---

## Langkah 3 — Pencarian hybrid (7.1–7.4, 7.7) · 1 hari

**File:** `src/retrieval/hybrid.py`

```python
def dense_search(query, ticker, year, k=config.TOP_K_DENSE) -> list[tuple[str, int]]:
    """[(chunk_id, peringkat)] dari Chroma, difilter ticker + year."""

def sparse_search(query, ticker, year, k=config.TOP_K_SPARSE) -> list[tuple[str, int]]:
    """[(chunk_id, peringkat)] dari BM25 laporan itu (sparse.search, Minggu 6)."""

def rrf_fuse(lists, k=config.RRF_K, top=config.TOP_K_FINAL) -> list[tuple[str, float]]:
    """score(d) = sum 1 / (k + rank_i(d)); urut menurun; seri dipecah oleh chunk_id (deterministik)."""

def hybrid_retrieve(query, ticker, year=None, k=config.TOP_K_FINAL, expand=True) -> list[dict]:
    """API tunggal untuk agen. Mengembalikan chunk lengkap: chunk_id, text, ticker, year, pages,
    headings, unit, merged_cells, is_table, skor RRF, peringkat dense & BM25."""
```

Aturan:

- **`ticker` wajib** (7.7). Kalau kosong, atau kode saham itu tidak ada di pustaka (`index.indexed()`),
  fungsi berhenti dengan `ValueError`, **bukan** mencari di semua emiten. Ini pagar utama terhadap
  kontaminasi antar bank (uji di Minggu 8, 8.0d).
- **`year` diisi** untuk pertanyaan tentang satu tahun. Agen (Minggu 9) mengambil tahun dari
  pertanyaan.
- **`year=None` atau daftar tahun** (pertanyaan tren): cari **per tahun**, lalu kembalikan `k` chunk
  **per tahun**, dikelompokkan per tahun. Jangan satu pencarian lintas tahun: prototipe
  menunjukkan 45 dari 75 chunk jatuh ke tahun yang salah.
- **Skor dense dan BM25 tidak dijumlahkan**, karena skalanya berbeda. RRF hanya memakai **peringkat**.
- **Deterministik:** kalau skor seri, urutan dipecah oleh `chunk_id`. Ada 102 pasang chunk identik
  antar laporan, tetapi filter tahun membuat pasangan itu tidak bertemu.

---

## Langkah 4 — Eksperimen pembanding (7.5–7.6) · ½ hari

**File:** `eval/retrieval_eval.py` → `results/retrieval_eval.json` + `results/retrieval_eval.csv`. Kode
evaluasi ditaruh di `eval/`, sejalan dengan `eval/ragas_eval.py` dan `eval/ratio_eval.py` di
roadmap.

Untuk setiap query dan setiap konfigurasi, catat **peringkat chunk relevan pertama**. Dari situ
dihitung **Hit@1, Hit@5, dan MRR**.

| Konfigurasi | Hit@5 (prototipe) |
|---|---|
| Dense saja | 7/15 |
| BM25 saja | 12/15 |
| Hybrid RRF | 11/15 |
| Dense saja + perluasan | 9/15 |
| BM25 saja + perluasan | **15/15** |
| **Hybrid RRF + perluasan** (konfigurasi sistem) | **13/15** |

Tambahan:

- **Subkelompok bersingkatan vs tidak:** 7 vs 8 query, untuk menguji hipotesis proposal.
- **7.6 (opsional, sudah diuji):** `k` RRF 10 / 60 / 100 sama persis. Jumlah kandidat 5 / 10 / 20 /
  30. Dicatat, **bukan** dipakai untuk memilih parameter.
- **Tabel per query untuk Bab 4:** query, peringkat di tiap konfigurasi, dan halaman chunk relevan.

---

## Langkah 5 — Pemeriksaan · ½ hari

**File:** `scripts/check_retrieval.py`

- **RRF:** perhitungan cocok dengan contoh hitung tangan (2 daftar kecil), dan seri dipecah oleh
  `chunk_id`.
- **`ticker` wajib:** `hybrid_retrieve(q, ticker="")` dan `ticker="xxxx"` (tidak ada di pustaka) →
  `ValueError`.
- **Filter:** semua hasil `year=2024` berasal dari laporan 2024. Hasil `year=None` dikelompokkan per
  tahun, dengan `k` per tahun.
- **Perluasan:** query bersingkatan diperluas, query biasa tidak berubah. `expand=False` mematikannya.
- **Deterministik:** query yang sama dua kali menghasilkan urutan yang sama.
- **GATE 3:** Hit@5 hybrid + perluasan ≥ 80% (dari `eval/retrieval_eval.py`).
- **Uji negatif.** Script harus GAGAL kalau:
  - filter tahun dimatikan (hasil lintas tahun);
  - RRF memakai skor mentah, bukan peringkat;
  - `ticker` boleh kosong.

**Manual:**
- [ ] Baca top-5 hybrid untuk ke-15 query. Untuk 2 query yang gagal, catat sebabnya (bahan Bab 4).
- [ ] Coba 5 pertanyaan bebas di luar set uji (mis. "rasio BOPO 2024", "jumlah kantor cabang
      2025"). Jawabannya masuk akal? Ini bukan angka evaluasi, hanya pemeriksaan kewajaran.

---

## Langkah 6 — Catat · ½ jam

Isi lembar hasil. Untuk Bab 4 (4.3), yang dibutuhkan adalah tabel Dense / Sparse / Hybrid, dengan
dan tanpa perluasan, plus pembahasan hybrid vs BM25.

---

## Dampak ke Minggu 8–9 dan Bab 4

- **Bab 4 — hybrid vs BM25.** Pada 15 query angka, BM25 + perluasan (15/15) mengungguli hybrid
  (13/15). Ini **tidak membatalkan** arsitektur hybrid, tetapi harus dibahas jujur:
  - query uji berisi istilah persis dan angka, yang memang kekuatan BM25;
  - dense membantu pertanyaan **berparafrase** atau naratif, yang tidak terwakili di set ini;
  - RAGAS (Minggu 17) memakai 30 pertanyaan yang lebih beragam.

  Kalau ingin menguji pembobotan RRF (mis. BM25 lebih berat), lakukan pada **set query lain**
  (mis. pertanyaan RAGAS Minggu 8), **bukan** pada 15 query GATE.
- **Minggu 8 (8.0d) — uji kontaminasi:** pakai `hybrid_retrieve` dengan `ticker` berbeda. Hasil
  untuk `bbca` tidak boleh memuat satu pun chunk BMRI, dan sebaliknya. Pagar `ticker` wajib dari
  Langkah 3 adalah dasarnya.
- **Minggu 8 — BMRI:** jalankan ulang `eval/retrieval_eval.py` dengan 5–10 query BMRI (angka dari ground
  truth BMRI, 8.5) untuk melihat apakah daftar istilah tetap berlaku di bank lain.
- **Minggu 9 — Extraction Agent:**
  - tool `retrieve` memanggil `hybrid_retrieve(query, ticker, year)` dengan **tahun dari
    pertanyaan**;
  - pertanyaan tren memakai `year=None`, sehingga hasil dikelompokkan per tahun;
  - agen membaca `unit`, `merged_cells`, dan `pages` untuk sitasi.

---

## Gerbang (kriteria lolos Minggu 7)

- [x] Keputusan 7.A (perluasan istilah) dan 7.B (definisi chunk benar) disetujui *(15-11-2026)*
- [x] 15 query uji dikunci di `eval/datasets/retrieval_queries.jsonl` sebelum eksperimen
      *(15-11-2026; SHA-256 `cfab3a18…46fc2`, angka diverifikasi terhadap ground truth)*
- [ ] `hybrid_retrieve` dengan `ticker` wajib, filter tahun, `year=None` per tahun, dan perluasan istilah
- [ ] `eval/retrieval_eval.py`: tabel 6 konfigurasi + subkelompok singkatan tersimpan di `results/`
- [ ] **GATE 3: Hit@5 hybrid ≥ 80%** (prototipe: 13/15 = 87%)
- [ ] `check_retrieval.py` LULUS, termasuk uji negatif

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Hit@5 hybrid jauh di bawah prototipe | perluasan istilah tidak terpasang, atau filter `year` tidak terkirim | cek `expand=True` dan `where` berisi `ticker` + `year` |
| Hasil berisi chunk tahun lain | `year=None` dicari sekaligus, bukan per tahun | cari per tahun, kelompokkan hasilnya (Langkah 3) |
| Urutan hasil berubah-ubah antar jalan | seri skor RRF tidak dipecah | pecah seri dengan `chunk_id` |
| "CKPN" / "DPK" tidak menemukan apa pun | singkatan tidak tertulis di laporan | `BANK_TERMS` (Langkah 2) |
| Ingin menyetel `k` RRF atau bobot supaya Hit@5 naik | — | **jangan** pada 15 query GATE; pakai set query lain dan laporkan keduanya |
| `ValueError: ticker` | kode saham kosong atau tidak ada di pustaka | memang disengaja; isi kode saham yang ada (`index.indexed()`) |

---

## Lembar hasil — isi sambil jalan

| | Nilai |
|---|---|
| Keputusan 7.A (perluasan istilah) | **pakai**, disetujui 15-11-2026 |
| Keputusan 7.B (definisi chunk benar) | **chunk yang memuat angka jawabannya**, disetujui 15-11-2026 |
| Hit@5 dense / BM25 / hybrid (tanpa perluasan) | |
| Hit@5 dense / BM25 / hybrid (dengan perluasan) | |
| Hit@5 hybrid: query bersingkatan / tanpa singkatan | |
| Hit@1 dan MRR hybrid | |
| RRF k 10 / 60 / 100 | |
| Latensi `hybrid_retrieve` (ms) | |
| `check_retrieval.py` | |
| GATE 3 | |
| Catatan | |
