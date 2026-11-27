# Panduan Rinci Minggu 13 — Market Observer Agent

Minggu 13 membangun **Agent 3 (Market Observer Agent)**: agen yang mengambil **konteks pasar
eksternal** (berita korporasi terkini emiten, kebijakan/regulasi OJK & BI, serta sentimen sektor)
lewat **Tavily Search API** dengan pembatasan domain terpercaya (`include_domains` dinamis tanpa
hardcode nama emiten), menyaring relevansi hasil secara lapis-2 menggunakan LLM terstruktur, dan
menghasilkan daftar berita/regulasi yang **wajib disertai URL dan tanggal publikasi asli** dari
Tavily (anti-halusinasi tautan).

> **Target kelulusan Minggu 13 (`13.1`–`13.4`):**
> 1. `config.TAVILY_DOMAINS` bersih dari hardcode emiten (`bca.co.id` dihapus) dan domain resmi emiten
>    ditambahkan secara **dinamis** dari metadata dokumen;
> 2. Filter lapis-2 (LLM structured output) menyaring berita tidak relevan (promo/kartu kredit/emiten
>    lain) sambil **mengunci URL & tanggal dari respons mentah Tavily** oleh kode Python;
> 3. Kegagalan/kekosongan Tavily (key belum diisi, timeout, error HTTP, hasil kosong) **tidak pernah
>    membuat sistem crash** — selalu mengembalikan `market_context = []` secara bersih;
> 4. `scripts/check_market.py --offline` **LULUS** (termasuk 4 uji negatif) + uji live pada BBCA &
>    BMRI (setelah `TAVILY_API_KEY` diisi di `.env`).

Perkiraan kerja: **3–4 hari** (termasuk pendaftaran kunci gratis Tavily 1.000 request/bulan). Semua
kode dijalankan dari `.venv` pada branch **`dev`** (jangan langsung ke `main`).

---

## Status gerbang

- **Minggu 11–12 SELESAI 100%** (27-11-2026): **Financial Analyst Agent** (`src/agents/analyst.py`,
  `PythonAstREPLTool` aman di `src/agents/tools.py`, 6 formula SEOJK + ambang OJK & profil `general`
  di `src/ratio_profiles.py`) lulus `check_analyst.py` (`--offline` `0,20 s`, `--live` `4,12 s`) dan
  evaluasi 2 lapis MAE/MAPE (`results/analyst_eval.*`).
- `tavily-python==0.8.5` sudah terpasang di `.venv` (`TavilyClient.search` mendukung `topic`,
  `include_domains`, `max_results`, `search_depth`, `timeout`).
- Git aktif di branch **`dev`** (`origin/dev`), `main` tetap utuh.
- 🔑 **Prasyarat eksternal (Langkah 0):** siapkan **`TAVILY_API_KEY`** gratis (1.000 request/bulan) di
  https://tavily.com lalu simpan di `.env`. Seluruh kode, pengujian offline, dan degradasi mulus
  tetap bisa dibangun & diverifikasi lebih dulu meski `TAVILY_API_KEY` belum terisi.

> **Aturan disiplin lintas emiten (risiko R10):**
> `src/config.py`, `src/agents/tools.py`, dan `src/agents/market.py` **DILARANG** mem-hardcode
> `"bca.co.id"`, `"bankmandiri.co.id"`, atau nama emiten tertentu. Identitas emiten (`company`,
> `ticker`, `sector`, `domain`) dibaca secara dinamis dari `data/markdown/<ticker>_<year>.metadata.json`.

---

## Keputusan rancangan Minggu 13

### Keputusan 13.A — `include_domains` dinamis bebas hardcode (`13.1`)

- **Temuan audit `src/config.py`:** `TAVILY_DOMAINS` yang ditulis pada Minggu 1 masih mencantumkan
  `"bca.co.id"` secara tetap. Ini melanggar desain multi-emiten (`13.1`).
- **Solusi:**
  1. Bersihkan `config.TAVILY_DOMAINS` agar hanya berisi **domain umum terpercaya**:
     ```python
     TAVILY_DOMAINS = [
         "ojk.go.id", "idx.co.id", "bi.go.id",
         "kontan.co.id", "bisnis.com", "cnbcindonesia.com",
     ]
     ```
  2. Tambahkan deteksi generik **domain situs resmi emiten** (mis. dari baris `Website` / `Situs Web`
     / `www.<domain>` di halaman profil perusahaan PDF, mengecualikan domain regulator, auditor, dan
     media) di `src/ingest/detect_metadata.py` (field opsional `"domain"` di `.metadata.json`, mis.
     `bca.co.id`, `bankmandiri.co.id`, `telkom.co.id`).
  3. Di `src/agents/market.py`, fungsi `resolve_search_domains(ticker, year)` menggabungkan
     `config.TAVILY_DOMAINS` + `metadata.get("domain")` (bila ada dan valid) secara otomatis.

### Keputusan 13.B — Pencarian 2-jalur + Filter Lapis-2 terstruktur + Kunci URL Python (`13.2`, `13.3`)

1. **Lapis-1 (Tavily Search — 2 query generik hemat kuota):**
   - **Query 1 (kinerja & berita emiten):** `"{company} {ticker.upper()} kinerja keuangan laba kredit {year}"`
     (untuk non-bank: `"{company} {ticker.upper()} kinerja keuangan pendapatan laba {year}"`), `max_results=5`.
   - **Query 2 (regulasi & sentimen sektor):**
     - sektor `bank`: `"OJK perbankan CAR NPL LDR suku bunga BI {year} {ticker.upper()}"`, `max_results=5`;
     - sektor non-bank: `"BEI OJK industri {sector} kinerja emiten {ticker.upper()} {year}"`, `max_results=5`.
   - Deduplikasi kandidat berdasarkan URL ternormalisasi → maksimal **8–10 artikel mentah** per run
     (hanya memakai **2 kredit Tavily** per analisis!).
2. **Lapis-2 (Filter relevansi oleh LLM — `effort="low"`, `method="json_schema"`):**
   - LLM diberi daftar bernomor (`idx = 0..N-1`) berisi `title`, `domain`, `published_date`, dan
     cuplikan `content` (maks. 400 karakter per artikel).
   - LLM mengembalikan skema Pydantic `MarketFilterOutput`:
     - `idx: int` *(indeks kandidat dari daftar Tavily)*
     - `relevant: bool` *(buang promosi kartu kredit/KPR, iklan, lowongan, atau berita emiten lain)*
     - `category: Literal["kinerja_emiten", "regulasi_ojk", "makro_sektor", "tidak_relevan"]`
     - `sentiment: Literal["positif", "netral", "negatif"]`
     - `summary: str` *(ringkasan 1–2 kalimat bahasa Indonesia berbasis isi cuplikan, dilarang mengarang angka baru)*
3. **Kunci URL & tanggal oleh kode Python (`13.3` — anti-halusinasi tautan):**
   - LLM **tidak pernah** menulis ulang URL maupun `published_date`.
   - Kode Python memetakan `idx` kembali ke objek mentah Tavily sehingga `url`, `title`, `source_domain`,
     dan `published_date` **100% berasal dari respons asli Tavily** (jika `published_date` kosong dari
     Tavily, dicatat eksplisit sebagai `"tanggal tidak tersedia"` — tidak dikarang!).
   - Jika panggilan LLM filter gagal (jaringan/parsing), lakukan **fallback deterministik** berbasis
     skor Tavily (`score >= 0.4`) agar berita teratas tetap tersedia.

### Keputusan 13.C — Degradasi mulus (*graceful degradation*, `13.4`)

Market Observer Agent **TIDAK BOLEH** menjatuhkan pipeline multi-agent:
- `TAVILY_API_KEY` belum diisi → kembalikan `market_context = []`, `status = "unavailable"`, catatan
  `"TAVILY_API_KEY belum dikonfigurasi"`.
- Timeout / error koneksi / HTTP 401 / 429 / 5xx dari Tavily → tangkap pengecualian secara bersih,
  kembalikan `market_context = []`, `status = "error"`, simpan pesan error singkat di `market_errors`.
- Tavily mengembalikan 0 hasil atau semua tersaring tidak relevan → kembalikan `market_context = []`,
  `status = "empty"`.
- Dengan pola ini, Reporting Agent (Minggu 14) tetap menghasilkan laporan keuangan & rasio OJK utuh
  meski layanan berita eksternal sedang terganggu.

### Keputusan 13.D — Siap eksekusi paralel di LangGraph (Minggu 15)

`market_node(state)` hanya membaca `state["ticker"]`, `state.get("sector")`, dan `state.get("year")`
(serta `company`/`domain` dari `metadata.json`). Node ini **tidak bergantung** pada `extracted_data`
maupun `ratios`, sehingga di Minggu 15 (`15.1`) dapat langsung dijalankan **paralel** dengan cabang
`extraction → analyst` untuk mengurangi latensi total sistem multi-agent (Skenario 3).

---

## Langkah 0 — Daftar & verifikasi `TAVILY_API_KEY` · 10 menit

1. Daftar akun gratis di https://tavily.com (1.000 request/bulan, tidak butuh kartu kredit).
2. Salin API key (`tvly-...`) ke file `.env` lokal (**jangan** di-commit atau ditempel ke chat):
   ```env
   TAVILY_API_KEY=tvly-tempel_key_kamu_disini
   ```
3. Cek konfigurasi dan paket:
   ```powershell
   python -m src.config                       # TAVILY_API_KEY OK
   python -c "from tavily import TavilyClient; print('TavilyClient OK')"
   ```

*(Langkah 1–4 tetap bisa dikerjakan dan diuji `--offline` meski `TAVILY_API_KEY` belum diisi.)*

---

## Langkah 1 — Bersihkan `TAVILY_DOMAINS` & deteksi domain emiten dinamis (`13.1`) · 1–2 jam

1. **`src/config.py`:**
   - Hapus `"bca.co.id"` dari `TAVILY_DOMAINS` sehingga hanya memuat domain umum:
     `["ojk.go.id", "idx.co.id", "bi.go.id", "kontan.co.id", "bisnis.com", "cnbcindonesia.com"]`.
   - Tambahkan konstanta `TAVILY_MAX_RESULTS = 5`, `TAVILY_TIMEOUT = 25`, `MARKET_MAX_ITEMS = 5`.
2. **`src/ingest/detect_metadata.py`:**
   - Tambahkan helper generik `detect_domain(pages_text)` untuk mengekstrak domain situs web resmi
     emiten dari halaman profil perusahaan (pola `website` / `situs web` / `www.<domain>` dengan
     pengecualian domain regulator `ojk.go.id`, `idx.co.id`, `bi.go.id`, kantor akuntan, dan media
     sosial).
   - Simpan field `"domain"` (opsional, `str | None`) ke `.metadata.json` dan pastikan
     `scripts/check_detect_metadata.py` tetap **LULUS**.

---

## Langkah 2 — Tool Pencarian Pasar & Skema Pydantic (`src/agents/tools.py`, `src/agents/state.py`) · 2 jam

1. **`src/agents/state.py`:**
   - Tambahkan skema Pydantic:
     - `MarketCandidateDecision(BaseModel)`: `idx: int`, `relevant: bool`, `category`, `sentiment`, `summary: str`.
     - `MarketFilterOutput(BaseModel)`: `decisions: list[MarketCandidateDecision]`.
     - `MarketNewsItem(BaseModel)`:
       - `title: str`
       - `url: str` *(wajib, terverifikasi dari Tavily)*
       - `source_domain: str`
       - `published_date: str` *(dari Tavily, atau `"tidak tersedia"`)*
       - `category: Literal["kinerja_emiten", "regulasi_ojk", "makro_sektor"]`
       - `sentiment: Literal["positif", "netral", "negatif"]`
       - `summary: str`
       - `relevance_score: float | None`
   - Pastikan `AgentState` tetap kompatibel (`market_context: list[dict[str, Any]]`, plus tambahkan
     `market_errors: list[str]` dan `market_stats: dict[str, Any]`).
2. **`src/agents/tools.py`:**
   - Tambahkan fungsi inti `search_market_raw(query: str, include_domains: Sequence[str], max_results: int = 5, topic: str = "news") -> tuple[list[dict], str | None]` yang memanggil `TavilyClient(api_key=...).search(...)` dengan penanganan error lengkap (`13.4`: key kosong, timeout, exception → `([], error_msg)`).
   - Bungkus sebagai LangChain `@tool` bernama bahasa Inggris **`search_market_news`** (dipakai juga
     oleh Baseline Single-Agent di Minggu 16 agar Skenario 3 adil!).

---

## Langkah 3 — Market Observer Agent (`src/agents/market.py`, `13.1`–`13.4`) · ½ hari

Bangun [market.py](file:///c:/TugasAkhir/src/agents/market.py) (100% generik, 0 hardcode emiten):

1. **`resolve_issuer_context(ticker: str, years: Sequence[int] | None) -> dict`:**
   - Baca `company`, `sector`, `domain` dari `data/markdown/<ticker>_<year>.metadata.json` (fallback
     aman ke `ticker.upper()` & `sector="general"` bila metadata tidak ada).
   - Susun `include_domains = [*config.TAVILY_DOMAINS]` + `[domain]` jika tersedia dan belum ada di daftar.
2. **`build_market_queries(company: str, ticker: str, sector: str, target_year: int) -> list[tuple[str, str]]`:**
   - Kembalikan 2 query `(query_text, topic)` generik: 1 berita kinerja emiten + 1 regulasi/sektor.
3. **`filter_market_candidates(candidates, company, ticker, sector, stats, llm=None) -> list[MarketNewsItem]`:**
   - Jalankan filter lapis-2 dengan `config.get_llm(effort=config.REASONING_EFFORT_EXTRACTION)`
     (`"low"`, `method="json_schema"` + fallback `json_mode`).
   - Validasi setiap `idx` terhadap list `candidates` asli; kunci `url`, `title`, `source_domain`, dan
     `published_date` dari `candidates[idx]` (bukan dari teks LLM!).
   - Deduplikasi URL, urutkan berdasarkan relevansi, batasi maks. `config.MARKET_MAX_ITEMS` (5 item).
   - Jika LLM filter gagal → fallback deterministik memakai kandidat dengan `score >= 0.4` (maks. 3 item).
4. **`observe_market(ticker, years=None, *, sector=None, company=None, extra_domains=None, use_llm_filter=True, llm=None, search_fn=None) -> dict`:**
   - Parameter `search_fn` memungkinkan injeksi mock saat uji offline (0 kuota Tavily!).
   - Tidak pernah melempar exception ke pemanggil bila Tavily gagal — selalu mengembalikan struktur
     rapi (`status`: `"ok" | "empty" | "unavailable" | "error"`, `market_context`, `domains_used`,
     `market_errors`, `market_stats`).
5. **`market_node(state: AgentState) -> dict`:**
   - Node LangGraph siap paralel di Minggu 15; mengisi `market_context`, `market_errors`, `market_stats`,
     dan 1 `AIMessage` ringkas.
6. **CLI smoke test:**
   ```powershell
   python -m src.agents.market --ticker bbca --year 2025
   python -m src.agents.market --ticker bmri --year 2025
   ```

---

## Langkah 4 — Pemeriksaan otomatis & uji negatif (`scripts/check_market.py`) · 2 jam

Buat `scripts/check_market.py` dengan mode `--offline` (0 kuota Tavily & 0 token LLM, `< 3 s`) dan
mode `--live` (2 panggilan Tavily nyata pada BBCA & BMRI):

- **A. Domain dinamis & bebas hardcode (`13.1`):**
  - `config.TAVILY_DOMAINS` tidak mengandung `"bca.co.id"` atau nama emiten mana pun;
  - `resolve_issuer_context` memuat `company` & `sector` dari `metadata.json` dan menggabungkan domain
    emiten secara dinamis tanpa duplikat;
  - Audit regex **0 kebocoran nama emiten** di `src/config.py` (`TAVILY_DOMAINS`), `src/agents/market.py`,
    dan `src/agents/tools.py`.
- **B. Filter lapis-2 & kunci URL/tanggal (`13.2`, `13.3`):**
  - Menggunakan mock `search_fn` (campuran berita kinerja relevan, regulasi OJK, berita promo kartu
    kredit, dan duplikat URL) + mock LLM filter → hanya item relevan yang lolos, duplikat dibuang,
    dan `url` serta `published_date` **100% cocok dengan input Tavily asli** (meski LLM mencoba
    mengembalikan indeks di luar batas).
- **C. Nama tool & kontrak `market_node`:**
  - `search_market_news.name == "search_market_news"` (bahasa Inggris);
  - `market_node(AgentState(ticker="bbca", sector="bank", year=2025))` berjalan tanpa membutuhkan
    `extracted_data` maupun `ratios` (terbukti siap paralel untuk Minggu 15!).
- **D. Uji negatif — degradasi mulus (`13.4`, HARUS lulus tanpa crash):**
  1. **`TAVILY_API_KEY` kosong:** mengembalikan `market_context == []`, `status == "unavailable"`, 0 exception.
  2. **Tavily melempar `TimeoutError` / `RuntimeError`:** mengembalikan `market_context == []`,
     `status == "error"`, pesan error tercatat di `market_errors`, 0 crash.
  3. **Tavily mengembalikan daftar kosong `[]`:** mengembalikan `market_context == []`, `status == "empty"`.
  4. **LLM filter gagal/error:** jatuh mulus ke fallback deterministik tanpa crash dan tetap menjaga
     URL & tanggal asli dari Tavily.
- **E. Uji live (`--live`, butuh `TAVILY_API_KEY`):**
  - Jalankan `observe_market("bbca", years=2025)` & `observe_market("bmri", years=2025)` → verifikasi
    setiap item punya `url` valid (`https://...`), `published_date`, domain termasuk daftar terpercaya,
    dan 0 berita promo/sampah.

---

## Langkah 5 — Uji live & evaluasi ringkas konteks pasar (BBCA & BMRI) · 1 jam

Setelah `TAVILY_API_KEY` terisi di `.env`:
1. Jalankan `python scripts\check_market.py --live` dan inspeksi manual 3–5 item berita yang lolos
   untuk **BBCA** dan **BMRI** (apakah benar relevan, berasal dari domain terpercaya, dan memuat URL
   serta tanggal valid).
2. Simpan contoh output terstruktur ke `results/check_market.json` untuk dokumentasi Bab 4 (jumlah
   kandidat mentah Tavily vs lolos filter lapis-2, rasio penyaringan, latensi, dan token).

---

## Langkah 6 — Catat, verifikasi regresi, & commit ke branch `dev` · ½ jam

1. Isi **Lembar hasil** di bawah.
2. Centang butir **Gerbang Minggu 13** di bawah dan `13.1`–`13.4` di [ROADMAP.md](file:///c:/TugasAkhir/docs/ROADMAP.md).
3. Jalankan seluruh pemeriksaan offline (`check_market.py --offline`, `check_analyst.py --offline`,
   `check_extraction.py --offline`, `check_detect_metadata.py`) — pastikan semuanya **LULUS**.
4. Commit & push ke branch **`dev`** (pastikan `.env` tidak pernah ikut ter-commit).

---

## Dampak ke Minggu 14–16 dan Bab 4

- **Minggu 14 (Reporting Agent):** membaca `state["market_context"]` untuk menyusun bagian *Konteks
  Pasar & Regulasi* lengkap dengan sitasi `[Judul](URL) (tanggal)` — dan bila kosong, menulis
  catatan transparan tanpa mengarang berita.
- **Minggu 15 (Orkestrasi LangGraph):** `market_node` disambungkan **paralel** dengan cabang
  `extraction → analyst` sebelum bergabung di `reporting_node`.
- **Minggu 16 (Baseline Single-Agent):** memakai `@tool search_market_news` yang sama persis untuk
  kesetaraan Skenario 3.
- **Bab 4:** rasio penyaringan lapis-1 → lapis-2 (mis. 9 kandidat mentah → 4 berita relevan) menjadi
  bukti efektivitas arsitektur filter 2-lapis Market Observer Agent.

---

## Gerbang (kriteria lolos Minggu 13)

- [ ] **13.1** Tool Tavily memakai `include_domains` = domain umum (`config.TAVILY_DOMAINS`, bebas hardcode `bca.co.id`) + domain resmi emiten dinamis dari metadata dokumen
- [ ] **13.2** Filter lapis-2 berbasis LLM (`method="json_schema"`) menyaring relevansi berita & mengklasifikasikan kategori/sentimen (dengan fallback deterministik bila LLM gagal)
- [ ] **13.3** Setiap item `market_context` wajib memuat `url` dan `published_date` yang dikunci dari respons asli Tavily (anti-halusinasi tautan)
- [ ] **13.4** Degradasi mulus: Tavily gagal / timeout / key kosong / hasil kosong → tidak crash, mengembalikan `market_context = []` secara bersih
- [ ] **Kriteria lolos Minggu 13:** `scripts/check_market.py --offline` **LULUS** (termasuk 4/4 uji negatif & 0 kebocoran emiten), `market_node` siap paralel, dan uji live BBCA & BMRI menghasilkan konteks pasar relevan dengan URL + tanggal terverifikasi

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `TAVILY_API_KEY belum di-set` | Key belum dimasukkan ke `.env` | Daftar gratis di https://tavily.com (1.000 req/bln), taruh `TAVILY_API_KEY=tvly-...` di `.env`; mode `--offline` tetap bisa diuji tanpa key |
| Tavily mengembalikan 0 hasil saat `include_domains` ketat | Beberapa situs berita memblokir indeks pada query terlalu panjang atau tahun spesifik terlalu sempit | Pendekkan query ke 4–6 kata kunci utama, atau gunakan `include_domains_mode="prefer"` bila hasil `restrict` kosong (tetap filter di lapis-2) |
| Field `published_date` kosong (`None`) pada hasil Tavily | Halaman profil/siaran pers korporasi atau regulasi OJK sering tidak memasang meta tanggal | Gunakan `"tanggal tidak tersedia"` secara jujur dari kode Python — jangan pernah meminta LLM menebak tanggal |
| Berita promo kartu kredit / KPR ikut masuk dari domain bank | Situs web emiten banyak memuat halaman produk ritel | Filter lapis-2 LLM secara eksplisit diarahkan menolak halaman produk/promo ritel dan hanya meloloskan berita kinerja keuangan / keterbukaan informasi / regulasi |

---

## Lembar hasil — isi sambil jalan

### A. Pemeriksaan otomatis & uji negatif (Langkah 4)

| Item | Hasil |
|---|---|
| `scripts/check_market.py --offline` (domain dinamis, filter lapis-2, kunci URL, 4 uji negatif) | *(Langkah 4)* |
| `scripts/check_detect_metadata.py` (regresi setelah tambah deteksi `domain`) | *(Langkah 1)* |
| `scripts/check_analyst.py --offline` & `check_extraction.py --offline` (regresi) | *(Langkah 6)* |

### B. Uji live Tavily + Filter Lapis-2 (Langkah 5)

| Emiten | Domain dipakai | Kandidat mentah (Lapis-1) | Lolos filter (Lapis-2) | URL & tanggal valid | Latensi & token |
|---|---|---:|---:|---|---|
| **BBCA** (2025) | — | — | — | — | — |
| **BMRI** (2025) | — | — | — | — | — |

### C. Catatan untuk Bab 4

| Item | Catatan |
|---|---|
| Contoh berita tidak relevan yang berhasil dibuang filter lapis-2 | *(Langkah 5)* |
| Perilaku degradasi mulus saat Tavily tidak tersedia (`13.4`) | *(Langkah 4)* |
| Kesiapan eksekusi paralel `market_node` di LangGraph (Minggu 15) | *(Langkah 4)* |
