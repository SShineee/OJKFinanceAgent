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
- ✅ **MINGGU 7 SELESAI (26-11-2026).**
  - Langkah 0–6 selesai, `check_retrieval.py` **LULUS** (termasuk 3 uji negatif), dan **GATE 3
    LULUS** (Hit@5 hybrid + perluasan **13/15 = 86,7%**, Hit@1 **9/15 = 60%**, MRR@5 **0,702**).
  - Hasil eksperimen lengkap tersimpan di `results/retrieval_eval.json` dan `results/retrieval_eval.csv`.

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

## Langkah 3 — Pencarian hybrid (7.1–7.4, 7.7) · ✅ SELESAI (26-11-2026)

**File:** `src/retrieval/hybrid.py`

```powershell
python -m src.retrieval.hybrid "Berapa CAR bank BCA tahun 2024?" --ticker bbca --year 2024
python -m src.retrieval.hybrid "Bagaimana tren NPL BCA?" --ticker bbca -k 2
```

```python
def dense_search(query, ticker, year, k=config.TOP_K_DENSE, expand=False) -> list[tuple[str, int]]:
    """[(chunk_id, peringkat)] dari Chroma, difilter ticker + year."""

def sparse_search(query, ticker, year, k=config.TOP_K_SPARSE, expand=False) -> list[tuple[str, int]]:
    """[(chunk_id, peringkat)] dari BM25 laporan itu (sparse.search, Minggu 6)."""

def rrf_fuse(lists, k=config.RRF_K, top=config.TOP_K_FINAL) -> list[tuple[str, float]]:
    """score(d) = sum 1 / (k + rank_i(d)); urut menurun; seri dipecah oleh chunk_id (deterministik)."""

def hybrid_retrieve(query, ticker, year=None, k=config.TOP_K_FINAL, expand=True, *,
                    dense_k=config.TOP_K_DENSE, sparse_k=config.TOP_K_SPARSE,
                    rrf_k=config.RRF_K) -> list[dict]:
    """API tunggal untuk agen. Mengembalikan chunk lengkap: chunk_id, text, ticker, sector, year,
    pages, headings, unit, merged_cells, is_table, rrf_score, dense_rank, sparse_rank."""
```

Aturan:

- **`ticker` wajib** (7.7). Kalau kosong, atau kode saham itu tidak ada di pustaka (`index.indexed()`),
  fungsi berhenti dengan `ValueError`, **bukan** mencari di semua emiten. Ini pagar utama terhadap
  kontaminasi antar bank (uji di Minggu 8, 8.0d). Untuk pencarian satu tahun, keberadaan laporan
  dicek langsung dengan `col.get(..., limit=1, include=[])` (~10 ms vs 55–180 ms untuk memindai
  seluruh koleksi) dan baru memanggil `index.indexed()` bila tidak ditemukan untuk pesan error.
- **`year` diisi** untuk pertanyaan tentang satu tahun. Agen (Minggu 9) mengambil tahun dari
  pertanyaan.
- **`year=None` atau daftar tahun** (pertanyaan tren): cari **per tahun**, lalu kembalikan `k` chunk
  **per tahun**, dikelompokkan urut tahun (query cukup di-embed sekali). Jangan satu pencarian
  lintas tahun: prototipe menunjukkan 45 dari 75 chunk jatuh ke tahun yang salah.
- **Skor dense dan BM25 tidak dijumlahkan**, karena skalanya berbeda. RRF hanya memakai **peringkat**.
- **Deterministik:** kalau skor seri, urutan dipecah oleh `chunk_id`. Ada 102 pasang chunk identik
  antar laporan, tetapi filter tahun membuat pasangan itu tidak bertemu.

### Uji Langkah 3 (semua ✅)

- `rrf_fuse`: cocok dengan hitung tangan, seri dipecah `chunk_id`, duplikat dalam satu daftar dihitung
  sekali, peringkat tidak valid (`0`, `-1`, `bool`, `float`) ditolak.
- Validasi `ticker` wajib & `year` di `dense_search`, `sparse_search`, dan `hybrid_retrieve`: `""`,
  `None`, `"xxxx"`, tahun tak terindeks (`2020`), `[]`, `bool`, string tahun → `ValueError`.
- Filter & pengelompokan: `year=2024` → 5 chunk 2024; `year=None` → 15 chunk dikelompokkan
  `2023/2024/2025` (5 per tahun); `year=[2025, 2023]` → 6 chunk urut `2023` lalu `2025`.
- Deterministik: dua panggilan identik memberi urutan `chunk_id` dan `rrf_score` sama persis;
  `dense_rank` & `sparse_rank` cocok dengan `dense_search` & `sparse_search`.
- **Hasil 15 query uji cocok persis dengan prototipe:**
  - tanpa perluasan: dense 7/15, BM25 12/15, hybrid 11/15 (singkatan 4/7, non-singkatan 7/8);
  - dengan perluasan: dense 9/15, BM25 15/15, **hybrid 13/15 (87%)** (singkatan 6/7, non-singkatan
    7/8; gagal di `q08` dan `q09`);
  - RRF `k` 10 / 60 / 100: semua 13/15; kandidat 5 / 10 / 20 / 30: 12 / 13 / 13 / 13.
- CLI: `"Berapa CAR bank BCA tahun 2024?"` → hal 21 (#1) dan KPMM hal 703 (#2); `"Bagaimana tren
  NPL BCA?"` → hal 265 & 646 (2023), 262–263 & 701 (2024), 590 & 95 (2025); `--ticker xxxx` gagal
  dengan pesan jelas (exit code 1).

---

## Langkah 4 — Eksperimen pembanding (7.5–7.6) · ✅ SELESAI (26-11-2026)

**File:** `eval/retrieval_eval.py` → `results/retrieval_eval.json` + `results/retrieval_eval.csv`. Kode
evaluasi ditaruh di `eval/`, sejalan dengan `eval/ragas_eval.py` dan `eval/ratio_eval.py` di
roadmap. Mendukung argumen `--dataset` dan `--out-prefix` untuk dijalankan ulang pada BMRI di
Minggu 8.

```powershell
python -m eval.retrieval_eval
```

Hash dataset terkunci terverifikasi:
`cfab3a1830003cc868ef2c069a2d9364d8dad0d7ce232a6005a3e5ed07246fc2`.

| Konfigurasi | Hit@1 | Hit@5 | MRR@5 | Singkatan (7) | Tanpa singkatan (8) |
|---|---|---|---|---|---|
| Dense saja | 6/15 (40%) | 7/15 (47%) | 0,433 | 3/7 (43%) | 4/8 (50%) |
| BM25 saja | 6/15 (40%) | 12/15 (80%) | 0,550 | 4/7 (57%) | 8/8 (100%) |
| Hybrid RRF | 7/15 (47%) | 11/15 (73%) | 0,556 | 4/7 (57%) | 7/8 (88%) |
| Dense + perluasan | 8/15 (53%) | 9/15 (60%) | 0,567 | 4/7 (57%) | 5/8 (62%) |
| BM25 + perluasan | 6/15 (40%) | **15/15 (100%)** | 0,604 | 7/7 (100%) | 8/8 (100%) |
| **Hybrid RRF + perluasan** (sistem) | **9/15 (60%)** | **13/15 (87%)** | **0,702** | **6/7 (86%)** | **7/8 (88%)** |

Temuan tambahan (bahan Bab 4):

- **Hybrid RRF + perluasan unggul di peringkat teratas:** meski BM25 + perluasan unggul di Hit@5
  (15/15 vs 13/15), **Hybrid + perluasan tertinggi di Hit@1 (60% vs BM25 40% & Dense 53%) dan MRR@5
  (0,702 vs BM25 0,604 & Dense 0,567)**. Pada `q01`, `q02`, `q03`, `q06`, dan `q11`, kesepakatan
  dense dan BM25 mengangkat chunk jawaban ke peringkat 1.
- **Sensitivitas parameter (7.6 — dicatat, bukan penyetelan):**
  - RRF `k` = 10 / 60 / 100 → identik di ketiganya: Hit@5 **13/15**, Hit@1 **9/15**, MRR@5 **0,702**.
  - Jumlah kandidat = 5 / 10 / 20 / 30 → Hit@5 **12 / 13 / 13 / 13** (MRR 0,661 / 0,702 / 0,702 / 0,702).
- **Latensi `hybrid_retrieve` (warm, 3×15 query):** rata-rata **26,4 ms**, median **25,3 ms**
  (min 20,1 ms, maks 51,4 ms).
- **Tabel per query lengkap** tersimpan di `results/retrieval_eval.csv` (termasuk peringkat di
  keenam konfigurasi dan halaman relevan).

---

## Langkah 5 — Pemeriksaan · ✅ SELESAI (26-11-2026)

### a. Otomatis — `scripts/check_retrieval.py` · **LULUS** (8,3 s)

```powershell
python scripts\check_retrieval.py
python scripts\check_retrieval.py --quick   # tanpa uji negatif
```

| Cek | Isi | Hasil |
|---|---|---|
| A. RRF | hitung tangan 2 daftar kecil, seri dipecah `chunk_id`, komutatif, duplikat dihitung sekali, daftar kosong, peringkat tidak valid ditolak | OK |
| B. `ticker` wajib | `""`, `"   "`, `None`, `"xxxx"` ditolak `ValueError` di `hybrid_retrieve`, `dense_search`, `sparse_search`; `"BBCA"` dinormalisasi | OK |
| C. Filter tahun | `year=2023/2024/2025` terisolasi; `year=None` → 5 chunk per tahun (15 total); `year=[2025, 2023]` terurut; tahun tak valid ditolak | OK |
| D. Perluasan istilah | 7 singkatan diperluas, query biasa & `"Carrefour card scar"` tak berubah, idempoten, `expand=False` mengubah hasil CKPN | OK |
| E. Deterministik & skema | 5 query dijalankan 2× urutan & skor identik; 13 field lengkap; `dense_rank` & `sparse_rank` cocok | OK |
| F. GATE 3 | SHA-256 cocok hash terkunci; Hit@5 hybrid + perluasan **13/15 (86,7%) ≥ 80%**; `results/retrieval_eval.json` & `.csv` sinkron | OK |
| **G. Uji negatif** | (1) filter tahun dimatikan → tertangkap (**38/75** chunk top-5 dari tahun salah); (2) RRF skor mentah → tertangkap; (3) `ticker` boleh kosong → tertangkap (4 pelanggaran) | **3/3 tertangkap** |

### b. Manual · semua ✅

- [x] **Baca top-5 hybrid untuk ke-15 query & diagnosis 2 query meleset (`q08`, `q09`):**
  - **`q08` ("Berapa CKPN kredit yang diberikan BCA tahun 2023?"):** chunk relevan `bbca_2023_0517`
    (Entitas Induk hal 738–739, memuat CKPN Bank `33.168.491` juta) ada di **BM25 peringkat 4**,
    tetapi tidak masuk top-15 dense sehingga jatuh ke **peringkat 7 RRF** (`0,015625`). Top-2
    terisi Catatan 12 Kredit yang Diberikan konsolidasian hal 644–645 (`d=1/s=1`, `d=7/s=2`), dan
    slot #3–#4 terambil chunk dense-only (`d=2`, `d=3`). Catatan: query uji juga tidak menyebut
    "entitas induk" secara eksplisit; di Minggu 9 Extraction Agent menyertakan basis bank.
  - **`q09` ("Berapa total ekuitas BCA tahun 2024?"):** chunk relevan `bbca_2024_0135` (hal 265,
    ringkasan posisi keuangan) ada di **BM25 peringkat 4** (tidak masuk top-15 dense → **peringkat 7
    RRF**), sedangkan `bbca_2024_0171` (hal 544–545, Laporan Perubahan Ekuitas) ada di **dense
    peringkat 6** (tidak masuk BM25 → **peringkat 11 RRF**). Top-5 terisi narasi kinerja/entitas
    anak/rasio utama yang sering menyebut "BCA", "2024", dan "ekuitas".
- [x] **5 pertanyaan bebas di luar set uji (pemeriksaan kewajaran — 5/5 tepat di top-2):**

| Pertanyaan bebas | Top hasil relevan | Jawaban terverifikasi di chunk |
|---|---|---|
| `rasio BOPO BCA 2024` | #2 `bbca_2024_0148` hal 269 (`d=2, s=1`) | Tabel Rasio Keuangan Utama: **BOPO 41,7%** |
| `jumlah kantor cabang dan ATM BCA 2025` | #2 `bbca_2025_0005` hal 16; #3 `bbca_2025_0180` hal 470 | Ikhtisar & Catatan 1: **1.270 cabang**, **20.163 ATM** |
| `rasio LCR BCA tahun 2024` | #1 `bbca_2024_0106` hal 220 (`d=1, s=1`); #2 `bbca_2024_0005` hal 21 | Laporan LCR Triwulanan & Ikhtisar: **LCR 323,0%** |
| `laba bersih yang diatribusikan kepada pemilik entitas induk 2023` | #1 `bbca_2023_0171` hal 578–580 (`d=2, s=1`); #2–#3 hal 272 | Laporan Laba Rugi Konsolidasian & segmen |
| `dividen tunai per saham BCA tahun 2025` | #1 `bbca_2025_0389` hal 547 (`d=2, s=2`); #2 hal 548 | Catatan 36 Penggunaan Laba Bersih: **Rp 300/saham** + dividen interim |

---

## Langkah 6 — Catat · ✅ SELESAI (26-11-2026)

Lembar hasil di bawah terisi lengkap. Bahan Bab 4 (4.3 Implementasi RAG) tersedia di tabel Langkah
4, `results/retrieval_eval.json`, dan `results/retrieval_eval.csv`.

---

## Dampak ke Minggu 8–9 dan Bab 4

- **Bab 4 — hybrid vs BM25.** Pada 15 query angka, BM25 + perluasan (15/15) mengungguli hybrid
  (13/15) di **Hit@5**, tetapi **hybrid + perluasan unggul jelas di Hit@1 (60% vs 40%) dan MRR@5
  (0,702 vs 0,604)**. Ini **tidak membatalkan** arsitektur hybrid, dan justru memberi pembahasan
  yang berimbang:
  - query uji berisi istilah persis dan angka, yang memang kekuatan BM25;
  - kesepakatan dense + BM25 di RRF memperbaiki peringkat teratas (Hit@1 & MRR);
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
- [x] `hybrid_retrieve` dengan `ticker` wajib, filter tahun, `year=None` per tahun, dan perluasan istilah *(26-11-2026)*
- [x] `eval/retrieval_eval.py`: tabel 6 konfigurasi + subkelompok singkatan tersimpan di `results/` *(26-11-2026: `results/retrieval_eval.json` & `.csv`)*
- [x] **GATE 3: Hit@5 hybrid ≥ 80%** *(26-11-2026: **13/15 = 86,7% LULUS**)*
- [x] `check_retrieval.py` LULUS, termasuk uji negatif *(26-11-2026: A–F OK, 3/3 uji negatif tertangkap, 8,3 s)*

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
| Hit@5 dense / BM25 / hybrid (tanpa perluasan) | 7/15 (47%) / 12/15 (80%) / 11/15 (73%) |
| Hit@5 dense / BM25 / hybrid (dengan perluasan) | 9/15 (60%) / **15/15 (100%)** / **13/15 (87%)** |
| Hit@5 hybrid: query bersingkatan / tanpa singkatan | 6/7 (86%) / 7/8 (88%) *(tanpa perluasan: 4/7 vs 7/8)* |
| Hit@1 dan MRR hybrid | **Hit@1 9/15 (60%)**, **MRR@5 0,702** *(tertinggi dari 6 konfigurasi; BM25+ Hit@1 40%, MRR@5 0,604)* |
| RRF k 10 / 60 / 100 | sama persis: **13/15** (Hit@1 9/15, MRR@5 0,702); kandidat 5/10/20/30: 12/13/13/13 |
| Latensi `hybrid_retrieve` (ms) | rata-rata **26,4 ms**, median **25,3 ms** (warm, 3×15 query) |
| `check_retrieval.py` | **LULUS** (A–F OK, 3/3 uji negatif tertangkap, 8,3 s) |
| GATE 3 | **LULUS** — Hit@5 hybrid + perluasan 13/15 (**86,7%** ≥ 80%) |
| Catatan | **Minggu 7 selesai 26-11-2026.** Gagal di `q08` (CKPN 2023) & `q09` (total ekuitas 2024) — keduanya peringkat 4 BM25 tapi tidak masuk top-15 dense sehingga jatuh ke #7 RRF. 5 pertanyaan bebas (BOPO, cabang/ATM, LCR, laba induk, dividen) 5/5 tepat di top-2. `results/retrieval_eval.json` & `.csv` tersimpan. |
