# Panduan Rinci Minggu 9–10 — Extraction Agent & GATE 4

Minggu 9–10 adalah **jembatan pertama dari retrieval (RAG) menuju sistem multi-agent (LangGraph)**.
Di sini kita membangun **Agent 1 (Extraction Agent)**: agen yang mengambil potongan laporan tahunan
lewat `hybrid_retrieve`, mengekstrak angka keuangan mentah secara terstruktur (JSON/Pydantic)
beserta sumber halaman dan satuannya, lalu menormalisasi seluruh nominal ke **juta Rupiah** lewat
**kode Python** (bukan oleh LLM).

> **GATE 4:** akurasi ekstraksi **≥ 90% (≥ 22/24)** pada bank pengembangan (**BBCA**) **dan**
> **≥ 80% (≥ 20/24)** pada bank uji (**BMRI**) untuk **8 angka bank × 3 tahun (2023–2025)**.
> Jika ekstraksi meleset, MAPE rasio di Minggu 11 pasti gagal — perbaiki di sini, jangan berharap
> Financial Analyst Agent menutupi angka yang salah.

Perkiraan kerja: **1–2 minggu** (Minggu 9: pondasi parser, state, profil sektor, tool, dan Extraction
Agent pada BBCA; Minggu 10: penyempurnaan prompt pada BBCA, uji ketat + uji negatif, lalu evaluasi
akhir satu kali pada BMRI untuk GATE 4). Semua kode dijalankan dari venv (`(.venv)` aktif) pada
branch **`dev`** (jangan langsung ke `main`).

---

## Status gerbang

- **Minggu 8 SELESAI 100%** (27-11-2026): **GATE 8 LULUS PENUH** — pustaka berisi 6 laporan
  (`bbca` 2023–2025 + `bmri` 2023–2025, total `5.638` chunk, 0% kontaminasi), uji non-bank
  `tlkm_2024.pdf` → `non_financial (belum divalidasi)`, ground truth BMRI terverifikasi visual
  (`v 26/11/26`, 6/6 rasio MAPE < 5%), retrieval BMRI lulus `8/10 (80%)` tanpa penyetelan
  `BANK_TERMS`, dan dataset RAGAS tuntas **30/30** (`eval/datasets/ragas_qa.jsonl`, `--strict-final`
  LULUS).
- Git aktif di branch **`dev`** (`origin/dev`), `main` tetap utuh.
- ⚠️ **Bimbingan 1.6 masih tertunda.** Bawa 6 keputusan Minggu 1 + Keputusan 7.B + temuan perbedaan
  ROA BMRI vs BBCA ke pembimbing sesegera mungkin agar seluruh keputusan metodologis di atas resmi
  dikunci sebelum Minggu 11.

> **Aturan disiplin data uji (risiko R10 & R11 — WAJIB dipatuhi di Minggu 9–10).**
> Seluruh perancangan prompt, daftar query generik, dan iterasi perbaikan Extraction Agent **HANYA
> boleh menggunakan BBCA (`bbca`)**. **Dilarang** menyebut nama emiten (`BCA`, `Bank Mandiri`), nomor
> halaman (`hal 703`, `hal 1425`), nomor Catatan (`Catatan 51f`, `Catatan 58`, `Catatan 65c`), atau
> pola khas BMRI di prompt maupun di `src/ratio_profiles.py`. BMRI baru dijalankan **satu kali**
> setelah BBCA lolos ≥ 90% (Langkah 6).

---

## Keputusan rancangan yang perlu ditetapkan di awal Minggu 9

Empat keputusan ini langsung menjawab temuan nyata dari Minggu 1–8:

### Keputusan 9.A — Konversi angka & penjumlahan komponen dilakukan kode Python, bukan LLM

- **Temuan Minggu 2 (`scripts/check_tool_calling.py`):** `openai/gpt-oss-120b` salah membaca format
  angka Indonesia (`"239.468,855"` dibaca `239.468855`) pada **5 dari 5 percobaan**, dan menyisipkan
  spasi sempit Unicode `U+202F` (`Rp\u202f54.851`).
- **Temuan Minggu 1 & 8 (skala & komponen):** laporan BBCA mencampur **miliar Rupiah** (Ikhtisar)
  dan **juta Rupiah** (LK/KPMM/Entitas Induk), sedangkan BMRI memakai **juta Rupiah** di keduanya.
  Selain itu, di Neraca Entitas Induk BBCA, *Kredit Bruto* tidak tercetak langsung (harus dijumlahkan
  dari `Kredit Neto + CKPN`), dan *DPK Bank 2023–2024* dipecah `Pihak berelasi + Pihak ketiga`;
  sebaliknya di BMRI keduanya tercetak langsung.
- **Aturan:**
  1. LLM **hanya mengutip teks angka persis seperti tercetak di chunk** (`raw_value`, atau daftar
     `components` jika subtotal tidak tercetak langsung) beserta `unit` dan `source_chunk_id`.
  2. **Kode Python (`src/agents/parse_number.py`)** membersihkan `U+202F` / `"Rp"` / tanda kurung,
     mengonversi format Indonesia (titik = ribuan, koma = desimal), menjumlahkan `components` bila
     ada, dan menormalisasi seluruh nominal ke **juta Rupiah** (`billion_idr` × 1.000, `million_idr`
     × 1, `thousand_idr` / 1.000, `idr` / 1.000.000).
  3. **Pagar grounding otomatis:** sebelum diterima, kode Python memastikan setiap angka mentah yang
     dikutip LLM **benar-benar ada di teks chunk sumbernya**. Jika tidak ada → ditolak sebagai
     kandidat halusinasi (tidak boleh diteruskan ke Financial Analyst Agent).

### Keputusan 9.B — Strategi hemat token menghadapi batas Groq 8.000 TPM (risiko R5)

- **Fakta akun Groq (`gpt-oss-120b`, dicek Minggu 5):** batas gratis **30 RPM / 1K RPD / 8.000 TPM /
  200K TPD**. Satu chunk panjang rata-rata ~400–800 token (`CHUNK_MAX_TOKENS = 1024`).
- **Masalah:** jika satu percakapan ReAct bebas memanggil `search_annual_report` 6–8 kali berturut-
  turut sambil menumpuk semua hasil ke riwayat `messages`, total input cepat melewati **8.000 token**
  dan langsung terkena error `429 Rate limit reached (TPM)`.
- **Solusi:**
  1. Pakai `config.get_llm(effort=config.REASONING_EFFORT_EXTRACTION)` (`reasoning_effort="low"`,
     `temperature=0.0`, `max_tokens=config.MAX_TOKENS`) — cukup untuk ekstraksi tabel dan jauh lebih
     hemat token penalaran.
  2. Ekstraksi satu tahun dipecah menjadi **kelompok metrik yang ringkas** (berdasarkan kelompok
     sumber di `src/ratio_profiles.py`, mis. Kelompok 1: Ikhtisar/Laba-Neraca Konsolidasian;
     Kelompok 2: Permodalan KPMM Bank; Kelompok 3: Kredit, CKPN & DPK Entitas Induk; Kelompok 4:
     Kredit Bermasalah/NPL Bank). Setiap kelompok hanya memuat `k=3..5` chunk fokus (~1.500–3.000
     token input) — tetap memakai tool `search_annual_report` dan jauh di bawah batas 8K TPM.
  3. Tambahkan **penanganan 429 dengan jeda adaptif (*exponential backoff*)** dan **jeda ringan
     antar-kelompok** saat menjalankan batch evaluasi 24 titik (`eval/extraction_eval.py`).

### Keputusan 9.C — Nama tool bahasa Inggris & mode structured output terverifikasi

- **Temuan Minggu 2 (`check_tool_calling.py`):** nama tool bahasa Indonesia (`hitung`) memicu error
  Groq `400 tool_use_failed` pada 5/5 percobaan (model memanggil `hitungan`), sedangkan nama bahasa
  Inggris (`search_report`, `calculator`) **0 retry**.
- **Aturan:** seluruh `@tool` menggunakan **nama bahasa Inggris** (mis. `search_annual_report`),
  sementara docstring/deskripsi boleh bahasa Indonesia. Tetap pasang pemulihan `tool_use_failed`
  (dengan pesan koreksi menyebut nama tool resmi — bukan retry polos karena `temperature=0`).
- **Uji prasyarat Langkah 0:** uji kompatibilitas `with_structured_output(Schema)` pada
  `ChatGroq(model="openai/gpt-oss-120b")` bersama `reasoning_effort="low"` — catat metode paling
  stabil (`json_schema` vs `json_mode` + `Schema.model_validate_json()`).

### Keputusan 9.D — Definisi 8 metrik GATE 4 & keluasan profil untuk Minggu 11

Tabel pemetaan **8 angka bank × 3 tahun = 24 titik uji** (tugas `9.6`) terhadap kedua workbook ground
truth ([ground_truth.xlsx](file:///c:/TugasAkhir/data/ground_truth.xlsx) &
[ground_truth_bmri.xlsx](file:///c:/TugasAkhir/data/ground_truth_bmri.xlsx)), seluruhnya dibandingkan
dalam satuan **juta Rupiah** (`nilai_xlsx_miliar × 1.000`):

| # | `metric_key` | Deskripsi semantik (generik) | Basis | Baris BBCA (`1_angka_mentah`) | Baris BMRI (`1_angka_mentah`) |
|---:|---|---|---|---|---|
| 1 | `net_income` | Laba bersih / laba tahun berjalan (konsolidasian) | `consolidated` | Baris 10 (`Laba Bersih`) | Baris 10 (`Laba Tahun Berjalan`) |
| 2 | `tier1_capital_bank` | Modal Inti (Tier 1) — kolom Bank (KPMM) | `bank_only` | Baris 13 (`Modal Inti (Tier 1) - BANK`) | Baris 13 (`Modal Inti (Tier 1) - BANK`) |
| 3 | `total_assets` | Total Aset (konsolidasian) | `consolidated` | Baris 3 (`Total Aset`) | Baris 3 (`Total Aset`) |
| 4 | `gross_loans_bank` | Kredit yang diberikan bruto — Entitas Induk (Bank) | `bank_only` | Baris 22 (`Kredit BRUTO - BANK`) | Baris 22 (`Kredit BRUTO - BANK`) |
| 5 | `deposits_bank` | Dana Pihak Ketiga / Simpanan dari nasabah — Entitas Induk (Bank) | `bank_only` | Baris 24 (`DPK - BANK`) | Baris 24 (`DPK - BANK`) |
| 6 | `npl_amount_bank` | Kredit bermasalah bruto nominal (KL+D+Macet) — Bank | `bank_only` | Baris 21 (`NPL nominal - BANK`) | Baris 21 (`NPL nominal - BANK`) |
| 7 | `net_interest_income` | Pendapatan bunga (dan syariah) bersih / neto (konsolidasian) | `consolidated` | Baris 8 (`Pendapatan Bunga Bersih`) | Baris 8 (`Pendapatan Bunga & Syariah - Neto`) |
| 8 | `rwa_bank` | Total ATMR (Aset Tertimbang Menurut Risiko) — kolom Bank (KPMM) | `bank_only` | Baris 15 (`Total ATMR - BANK`) | Baris 15 (`Total ATMR - BANK`) |

**Toleransi ketepatan evaluasi GATE 4:**
- **Tepat** jika `|hasil - ground_truth| / ground_truth ≤ 0,5%` (selisih < 0,05% lazim muncul saat
  angka konsolidasian diambil dari Ikhtisar yang dibulatkan ke miliar penuh vs Laporan Keuangan
  dalam juta, mis. `54.851.000` vs `54.851.274` = `0,0005%`).
- Untuk `net_income` (konsolidasian), catat juga bila model mengutip *Laba atribusi pemilik entitas
  induk* (baris 11) — tetapi acuan baku adalah **baris 10 (`Laba Bersih / Laba Tahun Berjalan`)**
  agar konsisten di BBCA dan BMRI.
- **Catatan transparansi BMRI 2023 (`npl_amount_bank`):** dari audit Minggu 8 (`check_bmri_chunks.py`),
  halaman `bmri_2023.pdf` hal. 401 dilewati `page_filter` v3 karena tabel 2023 tidak mencantumkan
  penanda satuan. Jika Extraction Agent mengembalikan `null` untuk `npl_amount_bank` 2023 saat
  mencari ketat di `year=2023`, itu dicatat jujur sebagai **1 error cakupan penyaring sekaligus
  bukti positif pagar anti-halusinasi** (tidak mengarang angka!). Jangan melonggarkan aturan
  khusus untuk BMRI.
- **Ekstensibilitas Minggu 11:** `src/ratio_profiles.py` langsung merancang slot metrik tambahan yang
  dibutuhkan 6 rasio SEOJK lintas bank (`total_capital_bank`, `profit_before_tax_bank`,
  `net_income_bank`, `total_assets_bank`, `net_interest_income_bank`, `earning_assets`,
  `ckpn_loans_bank`), sehingga Minggu 11 tidak perlu mengubah skema `AgentState` maupun `extraction.py`.

---

## Langkah 0 — Persiapan & uji prasyarat Groq structured output · 20 menit

Pastikan pustaka 6 laporan dan kunci API Groq aktif:

```powershell
git status                                 # harus di branch dev, working tree bersih
python -m src.config                       # GROQ_API_KEY OK, model openai/gpt-oss-120b
python scripts\check_index.py --quick      # 6 laporan utuh -> LULUS
python scripts\check_retrieval.py --quick  # retrieval BBCA utuh -> LULUS
```

Lakukan **1 smoke test kecil** (2–3 panggilan ke Groq, < 5 detik) untuk memastikan metode
`with_structured_output` yang paling andal pada `ChatGroq(model="openai/gpt-oss-120b",
reasoning_effort="low")`:
- Bandingkan `llm.with_structured_output(Schema, method="json_schema")` vs `method="function_calling"`
  vs JSON prompt + `Schema.model_validate_json()`.
- Pastikan field `None` (`null`), `list[str]`, dan `list[int]` ter-parse mulus tanpa error `400` dari
  Groq. Catat pilihan metodenya di **Lembar hasil**.

---

## Langkah 1 — Parser angka Indonesia & normalisasi satuan · ½ hari

**File:** `src/agents/parse_number.py`

Modul murni Python (deterministik, 0 panggilan LLM, sangat mudah diuji menyeluruh):

1. **`clean_numeric_text(raw: str) -> str`:**
   - Hapus karakter tak tampak dan spasi sempit Unicode (`\u202f`, `\u00a0`, `\u2009`, spasi biasa),
     awalan mata uang (`Rp`, `IDR`), dan tanda persen bila ada.
   - Deteksi tanda negatif akuntansi: `"(33.168.491)"` → negatif `-33168491` (atau nilai absolut bila
     metrik seperti CKPN diminta positif — tandai jelas lewat parameter `allow_negative`).
2. **`parse_indonesian_number(raw: str) -> float`:**
   - Aturan eksplisit format laporan Indonesia (`bbca` & `bmri`):
     - `"239.468.855"` (titik diikuti 3 digit berulang, tanpa koma) → `239468855.0`
     - `"239.468,855"` (titik ribuan + koma desimal) → `239468.855`
     - `"54.851"` (titik diikuti tepat 3 digit pada nominal tabel) → `54851.0`
     - `"29,36%"` atau `"29,36"` → `29.36`
     - `"-"`, `"–"`, `"N/A"`, `""`, `None` → `None` (jangan ubah jadi `0` diam-diam!).
   - Waspadai kasus dwibahasa Inggris (`"20.10%"` — titik diikuti 1–2 digit pada persen = desimal
     Inggris, bukan ribuan!).
3. **`normalize_to_million_idr(value: float, unit: str) -> float`:**
   - `million_idr` → `value * 1.0`
   - `billion_idr` → `value * 1_000.0`
   - `thousand_idr` → `value / 1_000.0`
   - `idr` → `value / 1_000_000.0`
   - `trillion_idr` → `value * 1_000_000.0`
   - Satuan tak dikenal / `None` pada nominal uang → raise `ValueError` (paksa ada satuan eksplisit!).
4. **`is_grounded_in_text(raw_value: str, chunk_text: str) -> bool`:**
   - Normalisasi spasi/tanda kurung/awalan `Rp` lalu pastikan token angka persis (dibatasi tepi digit
     agar `"54.851"` tidak cocok di dalam `"254.851"`) muncul di `chunk_text`.
   - Dipakai sebagai **pagar anti-halusinasi**: angka yang tidak ditemukan di chunk sumbernya langsung
     ditolak!

---

## Langkah 2 — `AgentState` & Profil Rasio Awal (`9.1`, `9.5b`) · ½ hari

### a. `src/agents/state.py` (`9.1`)

Definisikan state bersama seluruh 4 agent (dipakai langsung oleh LangGraph di Minggu 15) beserta
skema Pydantic terstruktur (`9.4`):

- **Model Pydantic untuk hasil ekstraksi:**
  - `RawMetricExtraction` (output langsung LLM per item):
    - `metric_key: str`
    - `raw_value: str | None` *(persis seperti tertulis di chunk; `None` jika tidak ditemukan)*
    - `components: list[str] | None` *(opsional, jika angka harus dijumlahkan dari sub-baris)*
    - `component_operation: Literal["sum", "none"] = "none"`
    - `unit: Literal["million_idr", "billion_idr", "thousand_idr", "trillion_idr", "idr", "percent"] | None`
    - `basis: Literal["bank_only", "consolidated", "unknown"]`
    - `source_chunk_id: str | None`
    - `source_pages: list[int]`
    - `source_header: str | None`
    - `notes: str | None`
  - `NormalizedMetric` (hasil pasca-validasi Python):
    - seluruh jejak sumber (`raw_value`, `components`, `original_unit`, `source_chunk_id`,
      `source_pages`, `source_header`, `basis`, `merged_cells_warning`), ditambah
    - `value_million_idr: float | None` *(atau `value_percent: float | None`)*,
    - `grounded: bool` *(apakah `raw_value`/`components` terverifikasi ada di teks chunk sumber)*,
    - `status: Literal["ok", "not_found", "ungrounded", "parse_error", "unit_conflict"]`.
- **`AgentState(TypedDict)`:**
  - `query: str`
  - `ticker: str` *(wajib — pagar anti-kontaminasi lintas bank!)*
  - `sector: str` *(dari metadata dokumen: `"bank"`, `"non_financial"`, dst.)*
  - `year: int | list[int] | None`
  - `extracted_data: dict[int, dict[str, dict]]` *(terindeks `tahun -> metric_key -> NormalizedMetric.model_dump()`, plus jejak `retrieved_chunks` untuk RAGAS `contexts` di Minggu 17!)*
  - `extraction_errors: list[str]`
  - `extraction_retries: int`
  - `ratios: dict` *(diisi Financial Analyst Agent di Minggu 11)*
  - `market_context: list[dict]` *(diisi Market Observer Agent di Minggu 13)*
  - `report: str` *(diisi Reporting Agent di Minggu 14)*
  - `messages: Annotated[list[AnyMessage], add_messages]`

*(Menyimpan `retrieved_chunks` di state sejak Minggu 9 memastikan evaluasi RAGAS Minggu 17 langsung
mempunyai field `contexts` tanpa perlu membongkar ulang agent!)*

### b. `src/ratio_profiles.py` (pondasi `9.5b` — dilanjutkan formula penuh di `11.2`)

Satu sumber kebenaran per sektor:
- **`bank` (`validated=True`):**
  - Mendefinisikan kelompok ekstraksi generik (`ExtractionGroup`: `group_id`, `description`,
    `search_queries` generik yang menyebut basis *konsolidasian* atau *entitas induk / bank saja*,
    serta daftar `MetricSpec` yang harus diambil).
  - Contoh query generik (bebas nama bank & nomor halaman, selaras temuan `m08` Minggu 8):
    - Kelompok `consolidated_highlights`: *"laporan posisi keuangan konsolidasian total aset dan laporan laba rugi pendapatan bunga bersih laba bersih tahun berjalan"*
    - Kelompok `capital_bank`: *"kewajiban penyediaan modal minimum KPMM modal inti tier 1 total modal ATMR bank"*
    - Kelompok `parent_loans_deposits`: *"laporan posisi keuangan entitas induk kredit yang diberikan cadangan kerugian penurunan nilai CKPN simpanan dari nasabah DPK"*
    - Kelompok `npl_bank`: *"kredit bermasalah NPL gross kurang lancar diragukan macet bank"*
  - Mendefinisikan 8 metrik inti GATE 4 (`GATE4_BANK_METRICS`) + metrik pelengkap 6 rasio SEOJK
    Minggu 11.
- **`general` (`validated=False`, dipakai seluruh sektor di `config.UNPROFILED_SECTORS`):**
  - 1 kelompok ringkas: `net_income`, `total_assets`, `total_equity` (untuk ROA & ROE umum berlabel
    *belum divalidasi*).
- Fungsi `get_profile(sector: str) -> SectorProfile` yang selalu mengembalikan `bank` untuk
  `"bank"` dan `general` untuk sektor lain (tidak pernah crash pada emiten baru seperti `tlkm`).

---

## Langkah 3 — Tool Retrieval LangChain (`src/agents/tools.py`, `9.2`) · 2 jam

Bungkus `hybrid_retrieve` dari [hybrid.py](file:///c:/TugasAkhir/src/retrieval/hybrid.py) sebagai
LangChain `@tool`:

- **Nama tool wajib bahasa Inggris:** `search_annual_report(query: str, ticker: str, year: int, k: int = 5) -> str`
  *(parameter `ticker` dan `year` wajib integer/string agar model tidak melakukan pencarian lintas
  emiten atau lintas tahun tanpa sengaja)*.
- **Format teks keluaran tool (kritis untuk akurasi ekstraksi!):**
  Setiap chunk dicetak dalam blok terstruktur yang menonjolkan metadata:
  ```text
  [CHUNK 1 | id=bbca_2024_0512 | hal=[703] | unit=million_idr | merged_cells=False]
  Judul: 51. INFORMASI TAMBAHAN > f. Rasio KPMM
  <teks chunk (tabel Markdown utuh)>
  ```
  Kenapa penting:
  1. LLM langsung melihat `id` dan `hal` untuk mengisi `source_chunk_id` & `source_pages`;
  2. LLM langsung melihat `unit=million_idr` / `unit=billion_idr` sehingga **tidak salah skala**;
  3. Jika `merged_cells=True`, LLM diberi peringatan untuk ekstra hati-hati membaca kolom bersebelahan.
- Simpan juga **recorder/cache chunk yang diambil per panggilan** (terisolasi per run, bukan global
  bocor antar thread) agar kode Python pasca-LLM bisa:
  - memverifikasi `is_grounded_in_text(raw_value, chunk["text"])` secara otomatis;
  - memeriksa kecocokan `unit` dengan `chunk["unit"]`;
  - menyimpan daftar teks `contexts` untuk evaluasi RAGAS di Minggu 17.

---

## Langkah 4 — Extraction Agent (`src/agents/extraction.py`, `9.3`–`9.5`) · 1–2 hari

### a. Aturan prompt generik (`9.3` & `9.5` — wajib diperiksa sebelum uji BMRI)

Prompt sistem Extraction Agent **HARUS**:
1. Menjelaskan **peran & tujuan semantik** tiap metrik yang diminta dari profil sektor (`9.5b`) —
   mis. perbedaan *basis Bank / Entitas Induk saja* vs *Konsolidasian*, dan perbedaan *Kredit Bruto*
   (sebelum dikurangi CKPN) vs *Kredit Neto* (setelah dikurangi CKPN).
2. Mewajibkan **kutipan mentah persis** (`raw_value`) seperti tercetak di chunk:
   - **DILARANG** mengubah skala, membulatkan, atau menghitung di kepala;
   - Jika angka yang diminta tidak tercetak sebagai satu baris total (mis. *Kredit Bruto* hanya ada
     sebagai `Kredit Neto + CKPN`, atau *Simpanan Nasabah* terpecah `Pihak berelasi + Pihak ketiga`),
     isi `components` dengan angka-angka penyusunnya persis dari chunk dan set
     `component_operation="sum"` — Python yang akan menjumlahkan;
   - **Jika angka tidak ditemukan di chunk mana pun → WAJIB isi `raw_value=null`**, dilarang menebak!
3. Menjelaskan **format angka Indonesia** (titik = ribuan, koma = desimal) dan kewajiban mengisi
   `unit` sesuai header `[unit=...]` pada chunk atau judul tabel `"(dalam jutaan/miliar Rupiah)"`.
4. Mewajibkan sitasi `source_chunk_id`, `source_pages`, dan `source_header` untuk setiap angka.
5. **DILARANG KERAS** memuat: nama perusahaan (`BCA`, `Bank Central Asia`, `Mandiri`, `BRI`), nomor
   halaman, atau nomor Catatan (`Catatan 51`, `Catatan 58`, `Catatan 65c`).

### b. Alur kerja fungsi utama `extract_metrics()` & node `extraction_node(state)`

1. Baca `ticker`, `sector`, dan `year` dari `state` (validasi `ticker` terdaftar di `index.indexed()`).
2. Ambil `SectorProfile = get_profile(sector)` dari `src/ratio_profiles.py`.
3. Untuk setiap `year` target dan setiap `ExtractionGroup` pada profil:
   - Panggil tool `search_annual_report` (bisa dipanggil langsung oleh agen atau diawali retrieval
     terarah + kesempatan 1× query tambahan oleh agen bila ada item yang masih `null` pada putaran
     pertama — **dibatasi maks. 2 putaran per kelompok** agar tidak pernah menabrak 8K TPM!).
   - Jalankan panggilan LLM terstruktur (`get_llm(effort=config.REASONING_EFFORT_EXTRACTION)`) dengan
     penanganan retry:
     - `tool_use_failed` (Groq 400): ulangi maks. 1× dengan pesan koreksi nama tool resmi (`15.2b`);
     - `429 Rate limit`: backoff adaptif (baca `Retry-After` bila ada, atau 10–25 s) — jangan crash!
   - Jalankan **post-processing & grounding Python (`parse_number.py`)** pada setiap item:
     - verifikasi `source_chunk_id` ada di chunk yang diambil untuk `(ticker, year)` itu;
     - verifikasi `is_grounded_in_text()` untuk `raw_value` atau setiap elemen `components`;
     - selaraskan `unit` (prioritaskan `chunk["unit"]` bila tidak `None`, tandai `unit_conflict`
       jika berbeda secara mencurigakan);
     - hitung `value_million_idr` (atau `sum` dari `components` → `million_idr`).
4. Catat statistik token (`prompt_tokens`, `completion_tokens`, `total_tokens`) dan waktu per tahun
   (dipakai lagi di Minggu 15 & Skenario 3).
5. Sediakan CLI smoke test:
   ```powershell
   python -m src.agents.extraction --ticker bbca --year 2024
   ```

---

## Langkah 5 — Pemeriksaan otomatis & uji negatif (`scripts/check_extraction.py`) · ½ hari

Buat `scripts/check_extraction.py` yang bisa dijalankan dalam mode `--offline` (0 token Groq, < 5 s)
dan mode penuh (dengan 1 panggilan live BBCA 2024):

- **A. Parser angka (`parse_number.py`):** 20+ kasus uji (ribuan titik `"239.468.855"`, desimal koma
  `"239.468,855"`, spasi sempit `U+202F` `"Rp\u202f54.851"`, kurung negatif `"(33.168.491)"`, tanda
  `"-"` → `None`, konversi `billion_idr`/`million_idr`/`thousand_idr`/`idr` ke juta Rupiah, persen
  ID/EN).
- **B. Grounding & komponen:** angka yang benar-benar ada di chunk → `grounded=True`; angka yang
  diubah 1 digit → `grounded=False`; komponen `[8.803.131, 745.527.767, 33.168.491]` dijumlahkan
  Python tepat `787.499.389` juta.
- **C. Profil sektor & bebas kebocoran (`9.5`, `9.5b`):**
  - `get_profile("bank").validated is True`; `get_profile("non_financial").validated is False` (hanya
    3 metrik umum);
  - **Cek otomatis teks prompt & `ratio_profiles.py`:** TIDAK boleh mengandung string `"bca"`,
    `"mandiri"`, `"bbca"`, `"bmri"`, `"catatan 51"`, `"catatan 58"`, `"catatan 65"`, atau nomor
    halaman tetap!
- **D. Tool `search_annual_report` (`9.2`):** nama tool bahasa Inggris, menolak `ticker` kosong/tak
  terdaftar, mengembalikan header `[CHUNK | id=... | hal=... | unit=...]`, dan tidak pernah
  mencampur bank lain (`bbca` vs `bmri`).
- **E. Uji negatif (HARUS gagal / ditolak):**
  1. **Halusinasi angka:** LLM tiruan mengembalikan `"999.999.999"` yang tidak ada di chunk → wajib
     ditandai `status="ungrounded"` dan `value_million_idr=None`.
  2. **Angka tidak ada (anti-tebak):** diberi chunk yang tidak memuat data target → wajib menghasilkan
     `status="not_found"` (`None`), bukan angka karangan.
  3. **Skala tertukar:** chunk bertanda `billion_idr` dengan teks `"54.851"` harus dinormalisasi ke
     `54.851.000` juta Rp (bukan `54.851` juta Rp).
- **F. Live smoke test (non-`--offline`):** 1 panggilan nyata pada BBCA 2024 → seluruh item terisi
  dalam format `AgentState`, tanpa error `tool_use_failed`, dengan token & latensi tercatat.

---

## Langkah 6 — Evaluasi GATE 4: BBCA (dev) → BMRI (uji) (`9.6`, `9.7`) · 1–2 hari

**File:** `eval/extraction_eval.py` → `results/extraction_eval.json` & `results/extraction_eval.csv`

### Tahap 1 — Evaluasi & iterasi HANYA pada BBCA (`24 titik = 8 metrik × 3 tahun`)

```powershell
python -m eval.extraction_eval --ticker bbca --out-prefix extraction_eval_bbca
```

- Bandingkan tiap titik terhadap `data/ground_truth.xlsx` (`nilai_miliar × 1.000` dalam juta Rp;
  toleransi relatif ≤ 0,5%).
- Jika akurasi BBCA masih < 90% (< 22/24):
  - Diagnosis akar masalah per titik meleset: apakah gagal **retrieval** (chunk tidak masuk top-K),
    salah **kolom/basis** (konsolidasi vs bank, atau tahun pembanding tertukar), salah **komponen**
    (kredit neto belum ditambah CKPN), atau gagal **satuan**?
  - Perbaiki prompt / query generik / parser **hanya berdasarkan temuan BBCA**, tetap jaga cek
    bebas-nama-bank di `check_extraction.py`, lalu uji ulang BBCA sampai **≥ 22/24 (≥ 90%)**.
- Setelah BBCA lulus ≥ 90%, **KUNCI prompt & `ratio_profiles.py`** (commit dulu ke `dev` dan catat
  hash commit-nya di Lembar Hasil!).

### Tahap 2 — Uji generalisasi SATU KALI pada BMRI (`24 titik = 8 metrik × 3 tahun`)

```powershell
python -m eval.extraction_eval --ticker bmri --out-prefix extraction_eval_bmri
```

- Bandingkan terhadap `data/ground_truth_bmri.xlsx` (`nilai_miliar × 1.000` dalam juta Rp; toleransi
  relatif ≤ 0,5%).
- **DILARANG** mengubah prompt setelah melihat hasil BMRI! Jika BMRI gagal < 80%, lakukan diagnosis
  terbuka untuk menentukan apakah kegagalan disebabkan bug **generik** (mis. parser angka atau format
  tabel dwibahasa) — bila dilakukan perbaikan generik, catat hasil **sebelum dan sesudah** secara
  jujur untuk Bab 4.
- Gabungkan ringkasan BBCA & BMRI (tetap dilaporkan **terpisah per emiten**) ke
  `results/extraction_eval.json` & `results/extraction_eval.csv`.

---

## Langkah 7 — Catat, verifikasi, & commit ke branch `dev` · ½ jam

1. Isi **Lembar hasil** di bawah (termasuk akurasi per metrik BBCA vs BMRI, konsumsi token, latensi,
   dan analisis kesalahan untuk Bab 4).
2. Centang butir **Gerbang (GATE 4)** di bawah dan tugas `9.1`–`9.7` di `docs/ROADMAP.md`.
3. Jalankan `python scripts\check_extraction.py --offline` dan pastikan `git status` bersih dari
   file rahasia/data besar, lalu commit & push ke branch **`dev`**.

---

## Dampak ke Minggu 11–19 dan Bab 4

- **Minggu 11–12 (Financial Analyst Agent):**
  - Langsung membaca `state["extracted_data"]` dalam satuan seragam **juta Rupiah**, sehingga tidak
    perlu menebak satuan lagi dan tinggal menjalankan formula SEOJK via `PythonAstREPLTool` dari
    `src/ratio_profiles.py` yang sama.
  - Validasi `11.4` (tolak hitung bila input `null`) langsung terhubung ke `status != "ok"` dari
    Extraction Agent.
- **Minggu 15 (Orkestrasi LangGraph):**
  - `AgentState` (`src/agents/state.py`) dan `extraction_node(state)` langsung dipasang sebagai node
    pertama di `StateGraph(AgentState)`, beserta conditional edge retry 1× (`15.2`) dan penanganan
    `tool_use_failed` (`15.2b`).
- **Minggu 16 (Baseline Single-Agent):**
  - `src/baseline/single_agent.py` memakai tool `search_annual_report` dan `parse_number.py` yang
    sama persis supaya perbandingan Skenario 3 adil (hanya beda arsitektur).
- **Minggu 17 & 19 (Skenario 1 RAGAS & Skenario 2 MAPE):**
  - `retrieved_chunks` yang disimpan di `state` langsung memasok `contexts` untuk RAGAS;
  - Akurasi ekstraksi terpisah BBCA vs BMRI menjadi landasan utama pembahasan MAPE Skenario 2 di
    **Bab 4** (membuktikan apakah agent benar-benar menggeneralisasi atau hanya menghafal format BBCA).

---

## Gerbang (kriteria lolos Minggu 9–10 — GATE 4)

- [ ] **9.1** `src/agents/state.py` (`AgentState` + skema Pydantic `RawMetricExtraction` / `NormalizedMetric`)
- [ ] **9.2** `src/agents/tools.py` — `hybrid_retrieve` dibungkus LangChain `@tool` bernama bahasa Inggris (`search_annual_report`) dengan metadata halaman, satuan, & `merged_cells`
- [ ] **9.3** `src/agents/parse_number.py` + prompt Extraction Agent: output JSON terstruktur, sitasi sumber wajib, `null` bila tak ada, format angka Indonesia + `U+202F` & normalisasi ke juta Rupiah oleh kode Python + pagar grounding
- [ ] **9.4** Structured output Pydantic terverifikasi stabil pada `openai/gpt-oss-120b` (`reasoning_effort="low"`)
- [ ] **9.5** Prompt & `ratio_profiles.py` 100% generik (0 nama emiten, 0 nomor halaman, 0 nomor Catatan — dibuktikan oleh cek otomatis di `scripts/check_extraction.py`)
- [ ] **9.5b** `src/ratio_profiles.py` memuat profil `bank` (`validated=True`) & `general` (`validated=False`), daftar angka ekstraksi diambil dari profil sektor
- [ ] **9.6** Evaluasi ekstraksi 8 angka × 3 tahun (`eval/extraction_eval.py` → `results/extraction_eval.json` & `.csv`) dijalankan pada BBCA lalu BMRI
- [ ] **9.7** Akurasi dicatat **terpisah per emiten** (BBCA vs BMRI) beserta analisis selisih & error untuk Bab 4
- [ ] **GATE 4:** akurasi **BBCA ≥ 90% (≥ 22/24)** **dan** **BMRI ≥ 80% (≥ 20/24)**; `scripts/check_extraction.py` **LULUS** (termasuk uji negatif)

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Groq error `429 Rate limit reached` (8.000 TPM) | Terlalu banyak chunk dalam 1 prompt atau jeda antar panggilan terlalu rapat | Batasi `k=3..5` per kelompok metrik, pakai `reasoning_effort="low"`, pasang jeda & backoff adaptif di `extraction.py` |
| Groq error `400 tool_use_failed` | Model memanggil nama tool yang tidak ada atau argumen bertipe salah | Pastikan nama tool bahasa Inggris, tipe argumen sederhana (`str`/`int`), dan ulangi maks. 1× dengan pesan koreksi menyebut nama tool resmi (`15.2b`) |
| `with_structured_output` gagal / `content` kosong pada `gpt-oss-120b` | `max_tokens` terlalu kecil untuk token penalaran atau mode `json_schema` bentrok dengan tool calling | Pertahankan `MAX_TOKENS = 4096` + `reasoning_effort="low"`; pisahkan fase retrieval (tool) dan fase structured output, atau gunakan JSON mode + `model_validate_json()` |
| Angka meleset tepat `1.000×` (miliar vs juta) | LLM salah memilih `unit` atau membaca tabel Ikhtisar (miliar) lalu melabelinya `million_idr` | Selaraskan `unit` dengan metadata `chunk["unit"]` di Python dan tampilkan `[unit=...]` di baris pertama tiap blok chunk tool |
| Angka kolom tahun pembanding (tahun `t-1`) ikut terambil | Tabel 2 kolom (`2024 \| 2023`) atau 5 kolom (`2021..2025`) dibaca pada kolom salah | Tegaskan di prompt untuk membaca judul kolom tahun `year` secara eksplisit sebelum mengutip angka, dan pertahankan header tabel di setiap chunk (sudah dijamin Minggu 5) |
| Kolom Konsolidasian tertukar dengan kolom Bank (Entitas Induk) | Tabel KPMM 4 kolom (Bank/Konsol × 2 tahun) atau Neraca Konsolidasian vs Induk | Tegaskan `basis` pada deskripsi metrik di `ratio_profiles.py` dan sertakan kata kunci generik *"entitas induk"* / *"bank saja"* di query retrieval (temuan `m08` Minggu 8) |
| Kredit bruto tidak ketemu di BBCA (hanya ada Kredit Neto + CKPN) | BBCA menyajikan kredit bersih + narasi CKPN di baris yang sama | Manfaatkan field `components` + `component_operation="sum"` agar LLM mengutip komponen mentah dan Python menjumlahkannya |
| `npl_amount_bank` BMRI 2023 keluar `null` | Halaman `bmri_2023.pdf` hal. 401 dilewati `page_filter` v3 (tanpa penanda satuan) | **Jangan** memaksa angka atau mengubah prompt untuk BMRI; laporkan jujur sebagai 1 error cakupan saringan sekaligus bukti pagar anti-halusinasi bekerja |

---

## Lembar hasil — isi sambil jalan

### A. Uji prasyarat & pemeriksa otomatis (Langkah 0–5)

| Item | Hasil |
|---|---|
| Metode structured output terpilih pada `openai/gpt-oss-120b` (`effort="low"`) | *(Langkah 0)* |
| `scripts/check_extraction.py --offline` (parser, grounding, bebas-emiten, uji negatif) | *(Langkah 5)* |
| `scripts/check_extraction.py` (dengan live smoke test BBCA 2024) | *(Langkah 5)* |
| Hash commit saat prompt & `ratio_profiles.py` dikunci sebelum uji BMRI | *(Langkah 6 — Tahap 1)* |

### B. Hasil evaluasi GATE 4 — 8 metrik × 3 tahun (terpisah per emiten, Langkah 6)

| # | `metric_key` | BBCA (2023 / 2024 / 2025) | Skor BBCA | BMRI (2023 / 2024 / 2025) | Skor BMRI |
|---:|---|---|---:|---|---:|
| 1 | `net_income` | — / — / — | `/3` | — / — / — | `/3` |
| 2 | `tier1_capital_bank` | — / — / — | `/3` | — / — / — | `/3` |
| 3 | `total_assets` | — / — / — | `/3` | — / — / — | `/3` |
| 4 | `gross_loans_bank` | — / — / — | `/3` | — / — / — | `/3` |
| 5 | `deposits_bank` | — / — / — | `/3` | — / — / — | `/3` |
| 6 | `npl_amount_bank` | — / — / — | `/3` | — / — / — | `/3` |
| 7 | `net_interest_income` | — / — / — | `/3` | — / — / — | `/3` |
| 8 | `rwa_bank` | — / — / — | `/3` | — / — / — | `/3` |
| | **TOTAL** | | **`/24` (`%`)** | | **`/24` (`%`)** |

### C. Efisiensi, keandalan, & diagnosis (bahan Bab 4)

| Item | BBCA (dev) | BMRI (uji) |
|---|---|---|
| Akurasi total (GATE 4: BBCA ≥ 90%, BMRI ≥ 80%) | *(Langkah 6)* | *(Langkah 6)* |
| Selisih akurasi BBCA − BMRI (gap generalisasi) | ← | *(Langkah 6)* |
| Kasus `ungrounded` (ditolak pagar anti-halusinasi) | *(Langkah 6)* | *(Langkah 6)* |
| Kasus `not_found` (`null` jujur) | *(Langkah 6)* | *(Langkah 6)* |
| Retry `tool_use_failed` / HTTP `429` | *(Langkah 6)* | *(Langkah 6)* |
| Rata-rata token & waktu per laporan (tahun) | *(Langkah 6)* | *(Langkah 6)* |
| Ringkasan akar masalah titik meleset | *(Langkah 6)* | *(Langkah 6)* |
| **GATE 4** | *(menunggu Langkah 6)* | ← |
