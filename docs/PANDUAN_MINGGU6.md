# Panduan Rinci Minggu 6 — Indexing: chunk → BGE-M3 → ChromaDB + BM25

Tujuan minggu ini adalah mengubah 1.552 chunk hasil Minggu 5 (`data\chunks\*.jsonl`) menjadi dua
indeks yang bisa dicari di Minggu 7:

- **Dense:** embedding BGE-M3 di ChromaDB, dengan metadata `ticker`, `sector`, `year`, `pages`,
  dan `unit`, supaya pencarian bisa (dan wajib) difilter per emiten-tahun.
- **Sparse:** satu indeks BM25 per laporan, untuk istilah persis seperti "KPMM", "NPL", dan
  angka.

Ditambah satu fungsi `add_document(pdf)` yang menjalankan seluruh alur: saring → parse → chunk →
embed → simpan. Fungsi inilah yang nanti dipanggil saat pengguna mengunggah laporan lewat Telegram
(Minggu 16).

Perkiraan kerja: **3–4 hari**. Semua kode dijalankan dari venv (`(.venv)` harus muncul di prompt).

---

## Status gerbang

- **Minggu 5 selesai** (15-11-2026): 514 / 540 / 498 chunk siap diindeks, dan `check_chunks.py`
  LULUS.
- ✅ Sisa Minggu 5 beres: `data\chunks\` di-backup ke Google Drive (15-11-2026).
- Minggu 6 **tidak bergantung** pada bimbingan.
- **Keputusan 6.A disetujui** (15-11-2026): embedding BGE-M3 dalam **fp16**.
- ✅ **MINGGU 6 SELESAI (15-11-2026).**
  - Langkah 0–6 selesai, dan semua butir gerbang lulus. `check_index.py` LULUS.
  - 1.552 chunk terindeks di ChromaDB, ditambah BM25 per laporan.
  - `add_document(pdf)` siap dipakai di Minggu 8 (BMRI) dan Minggu 16 (bot).

---

## Hasil pengecekan sebelum panduan ini ditulis (15-11-2026)

Rancangan di bawah sudah diuji dengan prototipe pada **1.552 chunk sungguhan**, memakai versi
terpasang: sentence-transformers 6.2.0, chromadb 1.5.9, rank-bm25 0.2.2, torch 2.14 + CUDA, di
RTX 3060 Laptop 6 GB. Beberapa rencana di roadmap ternyata perlu dikoreksi.

| Yang dicek | Hasil | Akibatnya |
|---|---|---|
| Model BGE-M3 | **Sudah ada di cache** (4,3 GB), dan bisa dimuat tanpa internet *(Langkah 1: harus dari folder snapshot lokal, karena nama repo tetap memicu 4–5 permintaan ke Hub)* | Langkah "unduh 2,2 GB" di roadmap 6.1 sudah tidak perlu |
| Embedding fp32 vs fp16 | fp32: **193 s**, VRAM puncak 2,6 GB. fp16: **54 s** (3,6× lebih cepat), VRAM 2,2 GB | Keputusan 6.A: fp16 |
| Kualitas fp16 | Kosinus terhadap fp32 **≥ 0,9997** di semua chunk; tetangga top-5 identik di 96% chunk (sisanya bertukar urutan antara chunk yang skornya hampir sama) | Perbedaannya bisa diabaikan |
| Ukuran batch | 16 dan 32 sama cepat (±29 chunk/detik) | `EMBED_BATCH = 16` |
| Tanpa GPU (CPU, fp32) | 0,56 chunk/detik, jadi **±47 menit** untuk 1.552 chunk | Indexing butuh GPU. CPU hanya cadangan, dan cukup untuk embed **query** |
| Model menganggur di GPU | 1,1 GB VRAM; embed satu query ±25–75 ms | Bot (Minggu 16) bisa menyimpan model di GPU |
| ChromaDB: nilai `None` di metadata | **Ditolak** (`TypeError: Cannot convert Python object to MetadataValue`) | `unit = None` harus **dihilangkan** dari metadata, bukan dikirim |
| ChromaDB: metadata berupa list | **Diterima** (chromadb 1.5.9), dan bisa difilter dengan `{"pages": {"$contains": 541}}` | Catatan Minggu 5 "simpan `pages` sebagai teks" dikoreksi: `pages` tetap **list** |
| ChromaDB: `add` dengan id yang sudah ada | **Diabaikan diam-diam**: isi lama tetap, tidak ada error | Cek "`doc_id` sudah ada → lewati" (roadmap 6.3) tidak cukup, karena chunk bisa berubah (Minggu 5 membuat ulang chunk 3× dalam sehari). Lihat Langkah 2 |
| ChromaDB: hapus per `doc_id` lalu tambah ulang | 540 chunk dihapus dalam 0,44 s dan ditambah ulang; total tetap 1.552, tanpa duplikat | Cara memperbarui satu laporan |
| ChromaDB: kecepatan & ukuran | 1.552 chunk ditambahkan dalam **1,4 s**; folder 26 MB | — |
| ChromaDB: jarak | `configuration={"hnsw": {"space": "cosine"}}` → `cosine` (bawaan Chroma L2) | Sesuai roadmap 6.3 |
| ChromaDB: model embedding bawaan | Dengan `embedding_function=None`, Chroma tidak mengunduh model ONNX bawaannya (`~/.cache/chroma` tetap tidak ada) | Embedding selalu dari BGE-M3 kita |
| ChromaDB: telemetri | Aktif secara bawaan (mengirim statistik pemakaian anonim) | Dimatikan: `Settings(anonymized_telemetry=False)` |
| BM25 dibangun dari `.jsonl` | **0,11 detik untuk ketiga laporan** | File `.bm25.pkl` (roadmap 6.4) tidak perlu. Indeks dibangun di memori dari `.jsonl`, sehingga tidak ada dua salinan yang bisa tidak sinkron, dan tidak ada pickle yang dimuat |
| Uji query "rasio KPMM bank" 2024 | Dense dan BM25: chunk hal 703 (tabel KPMM) di **peringkat 1** | — |
| Uji query "laba bersih" 2024 | Dense: analisis manajemen hal 265–268, laba rugi publikasi hal 711–712, catatan hal 647. BM25: catatan hal 646–647 | Masuk akal, tetapi lihat baris berikut |
| Pratinjau temu-kembali, 15 item ground truth (bukan uji GATE 3) | Chunk dari **halaman sumber** masuk top-5: dense 5/15, BM25 5/15, gabungan 7/15. Ketujuh item Ikhtisar hal 15 (2025) tidak ada yang masuk | Kelihatannya buruk, tetapi ukurannya terlalu ketat. Lihat baris berikut |
| … diukur ulang: top-5 **memuat angka jawabannya**, di halaman mana pun | Ketujuh item Ikhtisar 2025: dense **6/7**, BM25 **6/7**. Dengan tahun di query ("total aset tahun 2025"): **7/7** dan **7/7**. Jawabannya ada di narasi analisis manajemen (hal 202–212) dan laporan keuangan (hal 463/465) | **Untuk Minggu 7:** definisi "chunk yang benar" di GATE 3 harus menerima semua chunk yang memuat jawabannya, dan query sebaiknya membawa tahun. Lihat "Dampak ke Minggu 7–9" |
| Waktu `add_document` untuk laporan **baru** (dari angka Minggu 3) | Deteksi metadata 20–30 s, saring 15–40 s, Docling 6,5–8 menit + simpan 1–2 menit, chunk ±10 s, embed ±18 s, Chroma < 1 s. Totalnya **±9–11 menit**, hampir seluruhnya Docling | Laporan yang hash-nya sudah ada: beberapa detik. *Terukur di Langkah 4: 8 menit untuk `bbca_2025` dari nol; 0,2–0,3 s dari cache* |

---

## Keputusan 6.A — presisi embedding: fp16 (disarankan) atau fp32

> ✅ **DISETUJUI 15-11-2026: fp16.**

| | **fp16** (disarankan) | fp32 |
|---|---|---|
| Waktu embed 1.552 chunk | **54 s** | 193 s |
| VRAM puncak | 2,2 GB | 2,6 GB |
| Kemiripan dengan fp32 | kosinus ≥ 0,9997; tetangga top-5 identik 96% | — |

**Saran: fp16.** Hasilnya praktis sama dengan fp32, tetapi 3,6× lebih cepat. Ini penting saat
pengguna mengunggah laporan baru, dan saat indeks dibuat ulang. Di Bab 3 cukup ditulis "BGE-M3,
presisi setengah (fp16) di GPU". Kalau pembimbing meminta fp32, ubah satu konstanta
(`EMBED_DTYPE`), lalu indeks dibuat ulang otomatis (Langkah 2, `index_key`).

Di CPU, fp16 tidak dipakai: kode otomatis memakai fp32.

---

## Langkah 0 — Persiapan · ✅ SELESAI (15-11-2026)

1. **Backup `data\chunks\` ke Google Drive** (sisa Minggu 5).
2. Pastikan GPU tidak sedang dipakai proses lain:

   ```powershell
   nvidia-smi --query-gpu=memory.used,memory.total --format=csv
   ```

   BGE-M3 fp16 butuh ±2,2 GB saat embed.
3. Pastikan chunk masih sesuai kode terakhir:

   ```powershell
   python -m src.ingest.chunk data\markdown\bbca_2023.json data\markdown\bbca_2024.json data\markdown\bbca_2025.json
   ```

   Ketiganya harus tertulis "(cache: tidak dipotong ulang)".

---

## Langkah 1 — Model embedding (6.1) · ✅ SELESAI (15-11-2026)

**File:** `src/retrieval/embed.py`, ditambah konstanta di `src/config.py` · **Cek:**
`python -m src.retrieval.embed`

```python
# ----------------------------------------------------------------- INDEXING (Minggu 6)
EMBED_DTYPE = "float16"   # Keputusan 6.A (15-11-2026): 54 s vs 193 s fp32, kosinus >= 0,9997. CPU -> float32
EMBED_BATCH = 16          # 16 dan 32 sama cepat di RTX 3060 6 GB
EMBED_DEVICE = "cuda"     # jatuh ke "cpu" kalau GPU tidak ada (+-47 menit untuk 1.552 chunk)
```

Pemakaian:

```python
from src.retrieval.embed import embed_texts, embed_query, describe, release
vectors = embed_texts([c["text"] for c in chunks])   # (n, 1024) float32, norma 1
q = embed_query("rasio KPMM bank 2024")             # (1024,)
describe()   # {"model": "BAAI/bge-m3", "dim": 1024, "device": "cuda", "dtype": "float16", ...}
release()    # lepas dari GPU sebelum Docling, KALAU muncul CUDA out of memory (Langkah 4)
```

Inti `embed.py`:

```python
def _model_path() -> str:
    """Folder snapshot lokal model; unduh sekali kalau belum ada di cache."""
    try:
        return snapshot_download(config.EMBED_MODEL, local_files_only=True)
    except LocalEntryNotFoundError:
        SentenceTransformer(config.EMBED_MODEL, device="cpu")       # unduh ke cache (+-2,2 GB)
        return snapshot_download(config.EMBED_MODEL, local_files_only=True)

@lru_cache(maxsize=1)
def embedder() -> SentenceTransformer:
    on_gpu = device() == "cuda"
    kwargs = {"model_kwargs": {"dtype": getattr(torch, config.EMBED_DTYPE)}} if on_gpu else {}
    model = SentenceTransformer(_model_path(), device=device(), **kwargs)
    ...                                                  # dimensi harus = config.EMBED_DIM
    return model

def embed_texts(texts):
    vectors = embedder().encode(texts, batch_size=config.EMBED_BATCH, convert_to_numpy=True,
                                show_progress_bar=False).astype(np.float32)   # fp16 -> float32 dulu
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)           # baru dinormalisasi
```

### Hasil

| | |
|---|---|
| Model | BGE-M3, dimensi 1.024, `cuda` float16, `max_seq_length` 8.192 |
| Waktu muat | 2,6–2,8 s |
| VRAM | model menganggur **1,1 GB**; puncak saat embed **1,5 GB** |
| Embed 1.552 chunk | **47 s** (33 chunk/detik) |
| Keluaran | float32, norma 1,000000 di semua chunk |
| Dibanding prototipe | identik dengan prototipe fp16 (kosinus 1,000000); terhadap fp32 kosinus minimal 0,99992, median 0,999999 |
| Permintaan internet saat memuat | **0** |

Angka VRAM puncak di tabel pengecekan awal (2,2 GB) masih tercampur sisa memori uji fp32 di proses
yang sama. Angka di atas diukur di proses bersih.

### Temuan: model dari nama repo tetap menghubungi internet

Prototipe memuat model dengan `SentenceTransformer("BAAI/bge-m3", local_files_only=True)`. Ternyata
transformers tetap menjalankan pengecekan **konversi safetensors** di latar belakang, karena bobot
di cabang `main` berformat `pytorch_model.bin`.

- Pengecekan itu **mengabaikan `local_files_only`**, dan setiap kali model dimuat ia mengirim 4–5
  permintaan ke huggingface.co: info model, daftar commit, diskusi, dan PR #130. Muncul juga pesan
  "You are sending unauthenticated requests to the HF Hub".
- Yang terkirim hanya nama model publik, bukan data Anda. Tetapi lalu lintas itu tidak perlu, dan
  sedikit memperlambat pemuatan (4,5 s vs 2,9 s).
- `use_safetensors=False` tetap mengirim 5 permintaan. `HF_HUB_OFFLINE=1` menghentikannya, tetapi
  variabel itu dibaca saat huggingface_hub **pertama diimpor**. Di `add_document`, modul lain bisa
  mengimpornya lebih dulu.
- **Solusinya: muat dari folder snapshot lokal** (`snapshot_download(..., local_files_only=True)`).
  Dengan nama folder, tidak ada repo yang bisa dicek. Hasilnya 0 permintaan dan vektor identik.

### Uji (semua ✅)

- `python -m src.retrieval.embed`:
  - bentuk query `(1024,)` float32, norma 1;
  - 64 chunk ber-norma 1;
  - `embedder()` kedua kali mengembalikan model yang sama (tidak dimuat ulang).
- Seluruh 1.552 chunk identik dengan prototipe, dengan 0 permintaan internet (dihitung dengan
  menyadap klien HTTP).
- **Uji arah:** chunk terdekat ke "rasio KPMM bank 2024" dari seluruh pustaka adalah tabel KPMM
  hal 594 `bbca_2025`, yang memuat kolom 2025 dan 2024.

Catatan:

- **BGE-M3 tidak butuh awalan instruksi di query.** Ini berbeda dari BGE v1.5 (bahasa Inggris)
  yang memakai "Represent this sentence…". Chunk dan query di-embed dengan cara yang sama.
- **Yang di-embed adalah `text` dari `.jsonl`**: judul + isi, hasil `contextualize()` Minggu 5.
  Chunk terpanjang 1.024 token, dan batas model 8.192, jadi tidak ada yang terpotong.
- `get_sentence_embedding_dimension()` sudah usang di sentence-transformers 6. Pakai
  `get_embedding_dimension()`.
- Di transformers 5, parameter presisi bernama `dtype`. `torch_dtype` masih diterima, tetapi `dtype`
  adalah nama barunya.

---

## Langkah 2 — ChromaDB (6.2–6.3) · ✅ SELESAI (15-11-2026)

**File:** `src/retrieval/index.py`. Indeks tersimpan di folder `chroma_db\` (diabaikan git).

```powershell
python -m src.retrieval.index                  # ketiga laporan BBCA; idempoten
python -m src.retrieval.index bbca_2024        # satu laporan
python -m src.retrieval.index bbca_2024 --force
```

```python
from src.retrieval.index import collection, index_document, delete_document, indexed
index_document(2024)          # {"skipped": True/False, "chunks": 540, "replaced": ..., "seconds_embed": ...}
indexed()                     # {("bbca", 2023): 514, ("bbca", 2024): 540, ("bbca", 2025): 498}
collection().query(query_embeddings=[embed_query("rasio KPMM bank 2024")], n_results=10,
                   where={"$and": [{"ticker": "bbca"}, {"year": 2024}]})      # dipakai Minggu 7
```

### Klien dan koleksi

- **`client()`:** `PersistentClient(path=config.CHROMA_DIR)`, dengan
  `Settings(anonymized_telemetry=False)` sehingga telemetri mati. Dibuat sekali per proses.
- **`collection()`:** satu koleksi `annual_reports`, dengan:
  - `embedding_function=None`, sehingga Chroma tidak memakai atau mengunduh model ONNX bawaannya;
  - `configuration={"hnsw": {"space": "cosine"}}`, karena jarak bawaan Chroma adalah L2;
  - `metadata={"embed_model": "BAAI/bge-m3", "embed_dim": 1024}`.
- **Pengaman model:** kalau koleksinya pernah dibuat dengan model lain, `collection()` berhenti
  dengan pesan "hapus `chroma_db\` lalu index ulang". Tanpa pengaman ini, vektor dua model yang
  tidak bisa dibandingkan akan tercampur tanpa peringatan.

### Metadata per chunk

Hanya chunk yang **diindeks** yang masuk (`load_chunks()` → `excluded is None`). Record tabel tanpa
label tetap hanya ada di `.jsonl`.

| Field Chroma | Dari `.jsonl` | Catatan |
|---|---|---|
| id | `chunk_id` | `bbca_2024_0165` |
| document | `text` | yang dikembalikan ke LLM |
| `doc_id`, `ticker`, `sector`, `year`, `page` | sama | filter wajib Minggu 7: `ticker` (+ `year`) |
| `pages` | list int | **tetap list**. Filter halaman: `{"pages": {"$contains": 541}}` |
| `headings` | list → teks `" > "` | untuk tampilan dan sitasi |
| `is_table`, `merged_cells`, `n_tokens` | sama | `merged_cells` dibaca Extraction Agent (Minggu 9) |
| `unit` | sama | **dihilangkan kalau `None`** (25 chunk). Chroma menolak `None`; kunci yang tidak ada = tanpa satuan |
| `index_key` | hash `.jsonl` + model + presisi | lihat di bawah |
| *(tidak disimpan)* `items`, `excluded` | — | `items` tetap ada di `.jsonl`, ditelusuri lewat `chunk_id` |

### Idempoten, versi yang benar

Roadmap 6.3 menulis "kalau `doc_id` sudah ada, lewati". Itu tidak cukup, karena `add` dengan id yang
sudah ada **diabaikan diam-diam**. Setelah chunk dibuat ulang, Chroma akan tetap menyimpan versi
lama. `index_document`:

1. Ambil chunk yang tersimpan untuk `doc_id` laporan itu. Kalau jumlahnya sama dan **semua**
   `index_key`-nya sama dengan kunci sekarang, lewati.
   - `index_key` = SHA-256 dari isi `.jsonl` + `EMBED_MODEL` + `EMBED_DTYPE` + `EMBED_DIM`.
   - Jadi chunk yang dibuat ulang, atau model dan presisi yang diganti, otomatis memicu indeks
     ulang.
2. **Embed dulu**, baru hapus versi lama (`delete(where={"doc_id": …})`), lalu tambah per batch
   (≤ `get_max_batch_size()`, 5.461).
   - Kalau embed gagal (mis. CUDA out of memory), indeks lama tetap utuh.
   - Kalau proses mati di antara hapus dan tambah, jumlah chunk tidak cocok, sehingga laporan itu
     diindeks ulang lengkap pada jalan berikutnya.

### Hasil

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Chunk terindeks | 514 | 540 | 498 |
| Embed / tambah ke Chroma (detik) | 19,0 / 0,4 | 16,7 / 0,5 | 15,0 / 0,5 |
| Jalan kedua | dilewati | dilewati | dilewati |

- **Waktu:** ketiga laporan ±1 menit, termasuk memuat model.
- **Jalan kedua (semua dilewati): ±8 detik**, hampir seluruhnya untuk mengimpor pustaka
  (docling-core dan transformers lewat `chunk.py`). Pengecekannya sendiri hanya sepersekian detik.
  Di bot (Minggu 16), impor ini terjadi sekali saat bot dinyalakan, jadi tidak perlu dioptimalkan.
  Impor model embedding sudah ditunda sampai benar-benar dibutuhkan.
- **Ukuran `chroma_db\`:** 24 MB.

### Uji Langkah 2 (semua ✅)

Pemeriksaan sementara (script di luar repo); versi resminya `scripts/check_index.py` (Langkah 5).

**Isi `chroma_db\` yang asli:**
- jarak cosine;
- 1.552 id, sama dengan chunk diindeks dan tanpa duplikat; 0 dari 52 record `excluded`;
- `document` sama dengan `text`, dan semua metadata sesuai `.jsonl`;
- vektor (1.552, 1.024) bernorma 1;
- filter `ticker`+`year`: "rasio KPMM bank" 2024 → hal 703 di peringkat 1;
- `{"pages": {"$contains": 703}}` → 2 chunk;
- jalan ulang: ketiganya dilewati.

**Uji temu-diri, 250 sampel:** query dengan vektor sebuah chunk harus mengembalikan chunk itu.
Hasilnya **250/250**: 242 mengembalikan dirinya sendiri, dan 8 mengembalikan **kembaran berteks
identik** dari laporan lain.
- Ada **102 pasang chunk identik antar laporan**, misalnya kalimat pembuka Ikhtisar dan paragraf
  kebijakan akuntansi yang sama setiap tahun. Jaraknya sama-sama 0, jadi urutannya seri.
- Percobaan pertama dengan 50 sampel sempat "gagal" karena seri ini. Uji temu-diri sekarang
  menerima kembaran identik. Ini juga berdampak ke Minggu 7 (lihat di bawah).

**Perilaku**, diuji di folder Chroma sementara supaya yang asli tidak tersentuh:
- indeks baru;
- `--force` mengganti 498 chunk tanpa duplikat;
- `index_key` berubah → diindeks ulang;
- 100 chunk dihapus (simulasi proses mati) → diindeks ulang lengkap;
- koleksi bermodel lain → ditolak (`RuntimeError`).

---

## Langkah 3 — BM25 per laporan (6.4) · ✅ SELESAI (15-11-2026)

**File:** `src/retrieval/sparse.py` · **Cek:** `python -m src.retrieval.sparse "rasio KPMM" --year 2024`

```python
from src.retrieval.sparse import tokenize, bm25_index, search
search("rasio KPMM", "bbca", 2024, k=10)   # [("bbca_2024_0540", 15.6), ...] -- skor > 0 saja
bm25_index("bbca", 2024)                  # (BM25Okapi, chunk_id per dokumen); dibangun sekali per proses
```

**Koreksi roadmap 6.4: tanpa file `.bm25.pkl`.** Indeks dibangun di memori dari `.jsonl` saat
pertama dipakai, lalu disimpan di cache proses. Kunci cache-nya waktu ubah `.jsonl`, jadi chunk
yang dibuat ulang otomatis membangun indeks baru. Alasannya:

- tidak ada salinan kedua yang bisa basi;
- tidak ada pickle yang dimuat. Memuat pickle sama dengan menjalankan kode, kalau file itu pernah
  diganti orang lain.

`config.bm25()` (path `.bm25.pkl`) **dihapus** dari `src/config.py`.

Tokenizer:

```python
TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+")    # angka utuh + pemisahnya, kata huruf kecil

def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())
```

| Teks | Token |
|---|---|
| `Rp1.586,8 triliun` | `rp`, `1.586,8`, `triliun` |
| `29,14%` | `29,14` |
| `Non-Performing Loan` | `non`, `performing`, `loan` |
| `Modal Inti (Tier 1)` | `modal`, `inti`, `tier`, `1` |
| `(1.234.567)` | `1.234.567` |
| `\| Kas \| 29.315.878 \|` | `kas`, `29.315.878` |
| `per 31 Desember 2024.` | `per`, `31`, `desember`, `2024` |

- **Perubahan dari rancangan:** tanda `%` **dibuang**, jadi `29,14%` menjadi `29,14`. Kalau `%`
  ikut menjadi bagian token, query "29,14" atau "29,14 persen" tidak akan cocok dengan dokumen yang
  menulis "29,14%".
- **Tanpa daftar stopword.** IDF BM25 sudah menurunkan bobot kata umum seperti "yang" dan "dan".
  Membuang kata berisiko menghilangkan istilah seperti "tidak" dalam "tidak memiliki eksposur".
- **`search()` hanya mengembalikan skor > 0.** Query yang tidak satu pun katanya cocok
  menghasilkan daftar kosong, bukan k chunk acak.

### Hasil

- **Waktu bangun:** ketiga indeks 0,20 detik (termasuk membaca `.jsonl`). Satu pencarian 0,4 ms.
- **Isi:** 514 / 540 / 498 dokumen, sama persis (id dan urutan) dengan chunk diindeks dan dengan
  isi Chroma.

### Uji Langkah 3 (semua ✅)

Pemeriksaan sementara; versi resminya `scripts/check_index.py` (Langkah 5).

- **Tokenizer:** ketujuh contoh di tabel di atas.
- **Isi indeks:** jumlah dan urutan dokumen sama dengan `load_chunks()` dan Chroma.
- **Cache:**
  - panggilan kedua memakai indeks yang sama;
  - salinan `.jsonl` yang diubah (1 chunk dihapus) langsung membangun indeks baru (498 → 497
    dokumen).
- **Pencarian:**
  - "rasio KPMM" 2024 → hal 703 di peringkat 1; 2023 → hal 727 di peringkat 1;
  - "29,14" 2024 → chunk KPMM hal 703, yang teksnya memuat "29,14%";
  - "1.586.829" 2025 → Ikhtisar hal 15;
  - query tanpa kata yang cocok → `[]`.
- **Uji roadmap 6.6:** "laba bersih" 2024 → kelima hasil memuat "laba" (hal 647, 646, 587, 647,
  267).

**Catatan untuk Minggu 7:** skor BM25 dua laporan **tidak bisa dibandingkan langsung**, karena IDF
masing-masing berbeda. Pencarian tanpa `year` harus menggabungkan **peringkat** (mis. RRF), bukan
skor.

---

## Langkah 4 — `add_document(pdf)` (6.5) · ✅ SELESAI (15-11-2026)

**File:** `src/ingest/pipeline.py`. Ini satu pintu masuk pustaka, yang dipanggil oleh tombol unggah
di Minggu 16 dan oleh script untuk BMRI di Minggu 8.

```powershell
python -m src.ingest.pipeline data\raw\bbca_2024.pdf
python -m src.ingest.pipeline unggahan.pdf --ticker bmri --year 2024     # kode/tahun dikoreksi pengguna
```

```python
from src.ingest.pipeline import identify, add_document
identity = identify(pdf)          # Minggu 16: tampilkan tebakan -> pengguna konfirmasi
result = add_document(pdf, identity.ticker, identity.year, progress=lambda tahap, ket: ...)
# result: ticker, year, sector, company, validated, doc_id, chunks, steps{...}, warnings, seconds
```

Alurnya:

```
add_document(pdf, ticker=None, year=None, progress=None)
  1. identifikasi  hash PDF sudah ada di pustaka (data\markdown\*.meta.json)?
                     ya    -> kode saham & tahun dari situ
                     tidak -> detect_metadata (isi PDF): kode saham, tahun, sektor, satuan
                   ticker/year dari pemanggil (dikonfirmasi pengguna) mengalahkan hasil deteksi
                   -> .metadata.json disimpan; PDF disalin ke data\raw\<kode>_<tahun>.pdf
  2. parse         parse_pdf.parse_report        -- cache per hash; melepas GPU sesudahnya
  3. potong        chunk.build_chunks            -- cache per kunci (hash + kode aturan)
  4. indeks        index.index_document (Chroma) -- idempoten (index_key)
                   + sparse.bm25_index           -- dibangun dari .jsonl, sekalian memastikan terbaca
  -> ringkasan per tahap (cache/baru, detik), peringatan (deteksi, chunk, sektor belum divalidasi)
```

### Pengaman pustaka (tambahan dari rancangan)

| Kasus | Perilaku |
|---|---|
| PDF yang sama dengan nama lain (unggahan Telegram) | dikenali dari **hash**; tidak dideteksi ulang dan tidak disalin ulang |
| Pengguna mengoreksi kode/tahun, padahal PDF itu sudah ada di pustaka dengan kode/tahun lain | **ditolak**: "sudah ada di pustaka sebagai bbca_2024, bukan bmri_2024" |
| PDF **berbeda isi** untuk kode+tahun yang sudah ada (mis. laporan revisi) | **ditolak**, termasuk kalau kode/tahun diisi eksplisit. `parse_report` sendiri akan menimpa hasil lama diam-diam; mengganti laporan harus tindakan sengaja (hapus dulu) |
| Kode saham atau tahun tidak terdeteksi dari isi | berhenti dengan pesan "isi manual (`--ticker` / `--year`)" |
| Sektor di luar perbankan | tetap diproses, dengan peringatan "belum divalidasi" (label Minggu 11) |

Semua penolakan terjadi **sebelum** apa pun ditulis ke pustaka.

`progress(tahap, keterangan)` dipanggil di awal setiap tahap (`identifikasi`, `parse`, `potong`,
`indeks`, `selesai`) dan **per halaman** selama Docling berjalan. Bot Minggu 16 mengedit satu pesan
dari situ (16.3a).

### Hasil

| Kasus | Waktu | Keterangan |
|---|---|---|
| Ketiga PDF BCA, sudah di pustaka | 0,2–0,3 s per laporan (+ ±14 s impor pustaka sekali per proses) | semua tahap cache; indeks dilewati |
| **Laporan baru dari nol** (`bbca_2025.pdf` → pustaka sementara) | **481 s (8 menit)** | identifikasi dari isi 37 s, parse 418 s (saring + Docling 230 halaman + simpan), potong 11 s, indeks 14 s |

**Uji laporan baru dari nol.** `bbca_2025.pdf` diberi nama sembarang, lalu dimasukkan ke **pustaka
sementara** (folder terpisah; pustaka asli tidak disentuh). Pipeline harus mengenalinya dari isi,
mem-parse, memotong, dan mengindeks sendiri.

- **Dikenali dari isinya:** `bbca`, 2025, sektor bank, divalidasi, tanpa peringatan. PDF-nya disalin
  ke `raw\bbca_2025.pdf` di pustaka sementara.
- **Hasilnya identik dengan pustaka asli:** ke-515 record `.jsonl` sama persis (teks **dan**
  metadata), dan `doc_id` sama. Pipeline ini deterministik, dan seluruh hasil Minggu 3–5 bisa
  direproduksi dari PDF mentah dengan satu perintah.
- **Indeks:** 498 chunk di Chroma sementara, BM25 498 dokumen.
- **Progres:** kelima tahap muncul berurutan, ditambah 230 panggilan per halaman. Docling memproses
  4 halaman sekaligus, jadi progres maju per 4 halaman.
- **Catatan untuk bot (Minggu 16):** ±2 menit pertama tahap parse belum ada progres per halaman.
  Waktu itu dipakai menyaring halaman (±40 s), memuat model Docling, dan memproses batch pertama.
  Selama itu, tampilkan "menyaring halaman & memuat model…".
- **Jalan kedua dengan file yang sama:** 0,1 s, semua tahap cache.
- Folder pustaka sementara (123 MB) dihapus sesudah uji.

### Uji Langkah 4 (semua ✅)

- Ketiga PDF BCA: semua tahap memakai cache; panggilan kedua tidak embed ulang.
- PDF yang sama dengan nama lain dikenali dari hash, dan semua tahap memakai cache.
- Koreksi kode saham yang bertentangan → ditolak.
- PDF potongan 120 halaman dari `bbca_2024.pdf` tetap dikenali sebagai `bbca_2024` dari isinya
  (3,7 s), lalu **ditolak** karena isinya berbeda. Dengan `ticker`/`year` eksplisit juga tetap
  ditolak.
- **Pustaka asli tidak berubah sama sekali** selama semua uji penolakan: 18 file di `data\raw\`,
  `data\markdown\*.json`, dan `data\chunks\` dicek waktu ubahnya.
- Laporan baru dari nol: lihat tabel Hasil.

Hal yang perlu diperhatikan:

- **GPU 6 GB.** Docling dan BGE-M3 sama-sama memakai GPU. `parse_report` sudah melepas Docling
  sebelum kembali, dan di uji laporan baru, embedding berjalan normal sesudahnya. Kalau bot
  menyimpan BGE-M3 di GPU (1,1 GB) lalu menerima unggahan baru, panggil `embed.release()` sebelum
  parse **hanya kalau** muncul `CUDA out of memory`. Ukur dulu di Minggu 16.
- **Opsional (hemat 15–40 detik per laporan baru):** `detect_metadata` dan `page_filter` sama-sama
  mengekstrak teks seluruh PDF dengan pypdf. Hasil ekstraksi pertama bisa diteruskan ke yang kedua.
  Kerjakan hanya kalau waktu unggah terasa lama di Minggu 16.
- **Menghapus laporan dari pustaka** (untuk mengganti dengan revisi) belum dibuat.
  `index.delete_document(doc_id)` sudah ada untuk Chroma; file di `data\` dihapus manual. Buat
  perintahnya kalau memang dibutuhkan di Minggu 16.

---

## Langkah 5 — Pemeriksaan (6.6) · ✅ SELESAI (15-11-2026)

### a. Otomatis — `scripts/check_index.py` · **LULUS**

```powershell
python scripts\check_index.py            # semua cek + uji negatif (±20 detik)
python scripts\check_index.py --quick    # tanpa uji negatif
```

Sama seperti `check_chunks.py`, uji ini memeriksa **hasil yang tersimpan** (`chroma_db\` dan BM25
yang dibangun dari `.jsonl`), dibandingkan dengan `data\chunks\*.jsonl`. Kode indexing tidak
dipanggil ulang, kecuali untuk cek idempoten. Ringkasannya disimpan di `results/check_index.json`.

| Cek | Isi | Hasil |
|---|---|---|
| A. Isi | per laporan 514 / 540 / 498; id = `load_chunks()`; tanpa id ganda; 0 record `excluded`; `document` = `text` | 0 masalah |
| B. Metadata | `pages` list sama; `unit` ada ⇔ tidak `None`; `ticker`/`sector`/`year` = `.metadata.json`; `doc_id`, `page`, `headings`, `is_table`, `merged_cells`, `n_tokens` sama; **`index_key` = kunci `.jsonl` saat ini** | 0 masalah |
| C. Vektor | dimensi 1.024, norma 1; **temu-diri 250 chunk**: dirinya sendiri di peringkat 1, atau kembarannya yang berteks identik | 0 masalah |
| D. Koleksi | jarak cosine; `embed_model` = `BAAI/bge-m3` | 0 masalah |
| E. Filter | `ticker`+`year` hanya mengembalikan laporan itu (ketiga tahun); `{"pages": {"$contains": 703}}` → chunk KPMM 2024; `index_document()` kedua kali → dilewati, jumlah tetap | 0 masalah |
| F. BM25 | jumlah dan urutan dokumen = chunk diindeks = isi Chroma; tokenizer (4 contoh); "rasio KPMM" 2024 → hal 703 peringkat 1 | 0 masalah |
| G. Uji query roadmap 6.6 | "laba bersih" 2024 → **kelima** hasil dense **dan** BM25 memuat "laba" | dense hal 267, 268, 711–712, 265, 647; BM25 hal 647, 646, 587, 647, 267 |
| **H. Uji negatif** | koleksi **sementara** berisi data asli `bbca_2025` yang sengaja dirusak; pemeriksaan harus gagal | kontrol (utuh) lolos; **jarak L2**, **record `excluded` bocor**, dan **`index_key` basi** semuanya tertangkap |

**Pratinjau temu-kembali** (dicatat, **bukan** syarat lulus; itu GATE 3 Minggu 7). Untuk 7 item
Ikhtisar 2025 dengan tahun di query ("total aset tahun 2025", …), apakah top-5 memuat angka
jawabannya (miliar `1.586.829` atau triliun `1.586,8`)? Hasilnya **dense 7/7, BM25 7/7**.

Ukuran `chroma_db\`: 23,9 MB. Waktu: ±17 detik termasuk memuat pustaka, atau 5,5 detik untuk
pemeriksaannya saja.

### b. Manual · ✅

- [x] **Top-5 dense dan top-5 BM25 untuk 5 query:**

| Query | Dense | BM25 | Penilaian |
|---|---|---|---|
| "laba bersih 2024" | analisis manajemen hal 268 (Laba Bersih 54.851 miliar), 265; laba rugi konsolidasian hal 542–543; Entitas Induk hal 706; catatan laba per saham hal 647 | hal 647, 661 (segmen), 711 (laporan publikasi), 646, 542–543 | ✅ dense tepat. BM25 lebih bising karena frasa "laba rugi" ada di banyak catatan |
| "rasio KPMM 2024" | **tabel KPMM hal 703** di peringkat 1; manajemen modal hal 689; rasio resmi hal 21; rasio utama hal 269 | **hal 703** di peringkat 1; hal 689, 688; rasio gaji hal 372; rasio kredit usaha kecil hal 701 | ✅ BM25 ikut menyertakan "rasio" lain |
| "kredit bermasalah 2024" | tabel kolektibilitas hal 262–263 (memuat nominal kredit bermasalah), restrukturisasi, penghapusbukuan | rasio resmi hal 21, catatan restrukturisasi hal 577, kolektibilitas hal 262–263 | ✅ memuat jawabannya, tetapi narasi NPL hal 701 (sumber ground truth) tidak masuk top-5 |
| "dana pihak ketiga 2025" | **komposisi DPK hal 207** di peringkat 1, liabilitas hal 206, Ikhtisar hal 16 | **hal 207** di peringkat 1, hal 200, 590, Ikhtisar hal 16 | ✅ "Simpanan dari nasabah" Entitas Induk (hal 596) tidak muncul |
| "CKPN kredit entitas induk 2023" | tabel Pilar 3 hal 180, 201, komposisi kredit hal 263 | tabel Pilar 3 hal 201, 180; laba rugi hal 578–580 | ❌ **meleset**: hal 738 (CKPN Entitas Induk) tidak ditemukan |

- [x] Tidak ada folder model ONNX Chroma di `%USERPROFILE%\.cache\chroma`. Ukuran `chroma_db\`
      23,9 MB.

### Temuan: singkatan dan istilah sehari-hari tidak ada di teks laporan

Query yang meleset tadi ditelusuri. Halaman 738 menulis **"cadangan kerugian penurunan nilai"**,
bukan "CKPN". Singkatan itu hanya ada di 27 chunk lain, kebanyakan Pilar 3.

| Query | Halaman yang dicari | Dense | BM25 |
|---|---|---|---|
| "**CKPN** kredit entitas induk 2023" | 738 | tidak masuk 10 besar | tidak masuk 10 besar |
| "**cadangan kerugian penurunan nilai** kredit yang diberikan entitas induk 2023" | 738 | peringkat 8 | **peringkat 1** |
| "**dana pihak ketiga** entitas induk 2025" | 596 | peringkat 7 | tidak masuk 10 besar |
| "**simpanan dari nasabah** entitas induk 2025" | 596 | **peringkat 2** | peringkat 5 |

Ini memperkuat hipotesis proposal bahwa singkatan seperti NPL, CAR, dan DPK menyulitkan pencarian.
Bedanya, masalahnya **tidak hilang hanya dengan hybrid**: singkatan yang tidak tertulis di dokumen
tidak bisa ditemukan oleh BM25 sekalipun. Lihat "Dampak ke Minggu 7–9".

---

## Langkah 6 — Catat · ✅ SELESAI (15-11-2026)

Lembar hasil di bawah sudah terisi lengkap. Ringkasan hasil `check_index.py` ada di
`results/check_index.json`.

### Ringkasan untuk Bab 4 (4.3 Implementasi RAG)

| Komponen | Implementasi | Angka |
|---|---|---|
| Model embedding | BGE-M3 (`BAAI/bge-m3`), dimensi 1.024, **fp16** di GPU RTX 3060 6 GB (Keputusan 6.A); dimuat dari cache lokal tanpa internet | embed 1.552 chunk: 47 s (33 chunk/detik); VRAM 1,1 GB menganggur, 1,5 GB puncak; fp16 vs fp32 kosinus ≥ 0,9997 |
| Indeks dense | ChromaDB 1.5.9, satu koleksi, jarak **cosine**, metadata `ticker`/`sector`/`year`/`pages`/`unit`/`merged_cells` | 1.552 chunk (514 / 540 / 498); 24 MB; tambah 0,4–0,5 s per laporan; query ±25–75 ms |
| Indeks sparse | BM25Okapi (`rank_bm25`), **satu indeks per laporan**, dibangun di memori dari `.jsonl` (tanpa pickle); tokenizer mempertahankan angka utuh | 3 indeks dalam 0,20 s; satu pencarian 0,4 ms |
| Pintu masuk pustaka | `add_document(pdf)`: identifikasi (hash/isi) → parse → potong → indeks, dengan cache di setiap tahap | laporan baru dari nol **8 menit** (Docling 7 menit); laporan yang sudah ada 0,2–0,3 s; hasil dari nol **identik** dengan pustaka (515/515 record) |
| Pengujian | `check_index.py`: isi, metadata, vektor, temu-diri, filter, BM25, uji negatif | LULUS; 3 uji negatif tertangkap |

### Temuan yang layak dibahas di Bab 4

1. **Presisi setengah (fp16) cukup untuk temu-kembali**: 3,6× lebih cepat, dengan kosinus
   ≥ 0,9997 terhadap fp32 dan tetangga top-5 identik di 96% chunk.
2. **Idempotensi indeks tidak bisa mengandalkan `doc_id`**: ChromaDB mengabaikan diam-diam `add`
   dengan id yang sudah ada. Diselesaikan dengan `index_key` (hash `.jsonl` + model + presisi).
3. **102 pasang chunk identik antar laporan** (kalimat pembuka Ikhtisar, kebijakan akuntansi):
   pencarian **wajib** difilter per tahun.
4. **Singkatan yang tidak tertulis di laporan tidak ditemukan**, baik oleh dense maupun BM25:
   "CKPN" → hal 738 tidak masuk 10 besar, sedangkan "cadangan kerugian penurunan nilai" → BM25
   peringkat 1. Ini dasar perluasan istilah di Minggu 7, dan pembahasan hipotesis "hybrid unggul
   pada singkatan".
5. **Ukuran "chunk benar" menentukan angka Hit@5**: halaman sumber saja 7/15, sedangkan "memuat
   angka jawabannya" 7/7 untuk item Ikhtisar. Definisinya harus ditulis eksplisit di Bab 3/4.
6. **Pipeline dapat direproduksi**: PDF mentah → pustaka dengan satu perintah, hasil identik.

**Backup:** `chroma_db\` **tidak perlu** di-backup. Isinya bisa dibangun ulang dalam ±1 menit dari
`data\chunks\` (sudah di-backup) dengan `python -m src.retrieval.index`.

---

## Dampak ke Minggu 7–9

- **Minggu 7 — definisi "chunk yang benar" untuk GATE 3 (Hit@5 ≥ 80%):**
  - jangan hanya halaman sumber ground truth. Pratinjau menunjukkan jawabannya sering ada di
    **halaman lain** (narasi analisis manajemen, laporan keuangan), dengan angka yang sama;
  - dengan definisi "halaman sumber saja", hasilnya 7/15. Dengan "memuat angka jawabannya", item
    Ikhtisar 7/7;
  - tulis daftar relevan per query: semua chunk yang memuat angka jawabannya, dalam satuan apa pun
    (miliar di Ikhtisar/analisis, juta di laporan keuangan).
- **Minggu 7 — tahun di query:**
  - menambahkan "tahun 2025" menaikkan hasil dari 6/7 menjadi 7/7;
  - `hybrid_retrieve` sebaiknya selalu memfilter `year`, dan menyertakan tahun di teks query untuk
    BM25 dan dense;
  - alasan tambahan: ada **102 pasang chunk berteks identik antar laporan** (Langkah 2). Tanpa
    filter tahun, top-5 bisa terisi kembaran dari tahun lain, dan angka tahun yang salah ikut
    terbaca.
- **Minggu 7/9 — perluasan istilah perbankan (penting untuk GATE 3):**
  - laporan menulis istilah lengkap, bukan singkatan atau istilah sehari-hari. Bukti Langkah 5:
    "CKPN" tidak menemukan hal 738 sama sekali (dense maupun BM25), sedangkan "cadangan kerugian
    penurunan nilai" menemukannya di **peringkat 1 BM25**. "dana pihak ketiga entitas induk" →
    dense peringkat 7, sedangkan "simpanan dari nasabah entitas induk" → **peringkat 2**;
  - jadi `hybrid_retrieve` (Minggu 7) sebaiknya **menambahkan istilah lengkap** ke query sebelum
    mencari, lewat daftar istilah tetap di `config.py`, misalnya:
    - CKPN → cadangan kerugian penurunan nilai;
    - DPK → dana pihak ketiga, simpanan dari nasabah;
    - NPL → kredit bermasalah, non performing loan;
    - KPMM/CAR → kewajiban penyediaan modal minimum, rasio kecukupan modal;
    - ATMR → aset tertimbang menurut risiko;
    - LDR → loan to deposit ratio, rasio kredit terhadap dana pihak ketiga;
  - daftar ini deterministik dan murah (tanpa panggilan LLM). Agent di Minggu 9 tetap boleh
    merumuskan ulang query;
  - eksperimen 7.5 sebaiknya mencatat Hit@5 **dengan dan tanpa** perluasan istilah, sebagai bahan
    Bab 4.
- **Minggu 8 (BMRI):** `add_document` dipakai pertama kali untuk laporan yang belum pernah dilihat.
  Catat waktunya, dan cek peringatan chunk, khususnya "potongan tabel tanpa header kolom" (Minggu 5
  Langkah 3).
- **Minggu 16 (bot):**
  - simpan BGE-M3 di GPU (1,1 GB) supaya query cepat;
  - `add_document(progress=...)` untuk pesan progres. ±2 menit pertama parse belum ada progres per
    halaman (saring + memuat model), jadi tampilkan pesan tunggu;
  - alur unggah: `identify(pdf)` → tampilkan tebakan → konfirmasi → `add_document(pdf, ticker,
    year)`;
  - laporan dengan hash yang sama langsung terpakai.

---

## Gerbang (kriteria lolos Minggu 6)

- [x] `data\chunks\` di-backup ke Google Drive (sisa Minggu 5) *(15-11-2026)*
- [x] 1.552 chunk terindeks di `chroma_db\` (514 / 540 / 498), jarak cosine, 0 record `excluded`
      *(15-11-2026, Langkah 2)*
- [x] BM25 per laporan dibangun dari `.jsonl` (tanpa pickle), dan tokenizer mempertahankan angka
      *(15-11-2026, Langkah 3)*
- [x] `add_document()` jalan untuk ketiga PDF BCA; panggilan kedua tidak embed ulang *(15-11-2026)*
- [x] Laporan baru dari nol lewat `add_document()` menghasilkan pustaka yang identik (515/515 record)
      *(15-11-2026)*
- [x] `check_index.py` LULUS, termasuk uji negatif *(15-11-2026)*
- [x] Uji query manual dicatat (bahan Minggu 7) *(15-11-2026: 4 masuk akal, 1 meleset karena singkatan "CKPN")*

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `TypeError: Cannot convert Python object to MetadataValue` | ada nilai `None` di metadata (mis. `unit`) | hilangkan kuncinya kalau nilainya `None` |
| Jumlah chunk di Chroma benar, tetapi isinya versi lama | `add` dengan id yang sudah ada diabaikan diam-diam | hapus per `doc_id` dulu, baru tambah (`index_key`, Langkah 2) |
| Skor jarak aneh (> 1), atau hasil pencarian acak | koleksi dibuat dengan jarak L2 bawaan, atau embedding tidak dinormalisasi | `configuration={"hnsw": {"space": "cosine"}}` + `normalize_embeddings=True`; hapus `chroma_db\` lalu index ulang |
| Chroma mengunduh `all-MiniLM-L6-v2` / `onnx` | koleksi dibuat tanpa `embedding_function=None`, atau query memakai `query_texts=` | selalu `embedding_function=None` dan `query_embeddings=` |
| `RuntimeError: koleksi dibuat dengan model embedding lain` | `EMBED_MODEL` diganti setelah indeks dibuat | hapus `chroma_db\` lalu index ulang ketiga laporan |
| Embedding ±47 menit, bukan ±1 menit | jalan di CPU: CUDA tidak terdeteksi, atau `EMBED_DEVICE` salah | `python -c "import torch; print(torch.cuda.is_available())"` harus `True` (torch cu126, lihat Minggu 1) |
| `CUDA out of memory` saat `add_document` | Docling dan BGE-M3 di GPU bersamaan | `embed.release()` sebelum parse (Langkah 4) |
| "Could not reach the Hub … offline mode" | `HF_HUB_OFFLINE=1` diset | bukan error: model diambil dari cache |
| "You are sending unauthenticated requests to the HF Hub" saat memuat BGE-M3 | model dimuat lewat nama repo, sehingga pengecekan konversi safetensors menghubungi Hub (mengabaikan `local_files_only`) | muat dari folder snapshot lokal (`embed._model_path()`, Langkah 1) |
| BM25 tidak menemukan angka seperti "1.586.829" | tokenizer memecah angka di titik | pakai regex `TOKEN` di Langkah 3 |
| BM25 tidak menemukan "29,14" padahal dokumen menulis "29,14%" | `%` ikut menjadi bagian token | `TOKEN` tanpa `%?` (Langkah 3) |
| Hasil BM25 berbeda setelah chunk dibuat ulang | cache proses lama | `bm25_index` memakai waktu ubah `.jsonl` sebagai kunci, jadi otomatis dibangun ulang; kalau ragu, mulai ulang proses |

---

## Lembar hasil — isi sambil jalan

| | `bbca_2023` | `bbca_2024` | `bbca_2025` |
|---|---|---|---|
| Keputusan 6.A (presisi embedding) | **fp16**, disetujui 15-11-2026 — berlaku untuk semua laporan | | |
| Chunk terindeks di Chroma | 514 | 540 | 498 |
| Model embedding | BGE-M3 cuda fp16; muat 2,8 s; VRAM 1,1 GB (puncak 1,5 GB); 0 permintaan internet | | |
| Waktu embed / tambah ke Chroma (detik) | 19,0 / 0,4 | 16,7 / 0,5 | 15,0 / 0,5 |
| Waktu `add_document`: dari cache / laporan baru | 0,2–0,3 s / — | 0,2–0,3 s / — | 0,2–0,3 s / **481 s** (identifikasi 37 + parse 418 + potong 11 + indeks 14) |
| Ukuran `chroma_db\` (MB) | 24 MB untuk ketiga laporan | | |
| BM25: jumlah dokumen | 514 | 540 | 498 |
| BM25: waktu bangun ketiga indeks / satu pencarian | 0,20 s / 0,4 ms | | |
| Uji query "laba bersih" 2024 (dense / BM25) | 5/5 dan 5/5 memuat "laba" (dense hal 267, 268, 711–712, 265, 647) | | |
| Pratinjau temu-kembali Ikhtisar 2025 (dense / BM25) | — | — | **7/7 / 7/7** (top-5 memuat angka jawaban, query bertahun) |
| `check_index.py` | **LULUS**: A–G 0 masalah, 3 uji negatif tertangkap; ±17 s | | |
| Catatan | **Minggu 6 selesai 15-11-2026.** Temuan utama: `add` Chroma mengabaikan id lama (→ `index_key`); 102 pasang chunk identik antar laporan (→ filter tahun wajib); singkatan seperti "CKPN" tidak tertulis di laporan (→ perluasan istilah di Minggu 7); model dimuat tanpa internet. `chroma_db\` tidak perlu di-backup (dibangun ulang ±1 menit dari `data\chunks\`). | | |
