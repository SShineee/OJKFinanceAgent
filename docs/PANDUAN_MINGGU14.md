# Panduan Rinci Minggu 14 — Reporting Agent

Minggu 14 membangun **Agent 4 (Reporting Agent)**: agen terakhir dari arsitektur multi-agent yang
menyatukan seluruh keluaran terverifikasi dari tiga agen hulu — angka laporan keuangan terstandar
(`state["extracted_data"]`, Extraction Agent), hasil perhitungan rasio & ambang batas OJK
(`state["ratios"]`, Financial Analyst Agent), serta konteks berita & regulasi eksternal
(`state["market_context"]`, Market Observer Agent) — menjadi **laporan analisis keuangan Markdown
yang terstruktur, bernarasi tajam, dan wajib melampirkan sumber di setiap angka maupun berita**.

> **Target kelulusan Minggu 14 (`14.1`–`14.3`):**
> 1. Laporan mengikuti struktur **5 bagian wajib (`14.1`)**: *Ringkasan Eksekutif → Rasio Keuangan &
>    Interpretasi → Tren Antar Tahun → Konteks Pasar & Regulasi → Kesimpulan*;
> 2. **100% angka keuangan & rasio** menyertakan sitasi halaman PDF asli (`hal. ...`) dan **100%
>    konteks pasar** menyertakan tautan URL + tanggal asli dari Tavily (`14.2`, 0 URL halusinasi);
> 3. Output utama berupa **Markdown valid** (`14.3`) dilengkapi label *belum divalidasi* untuk profil
>    non-bank (R17), helper ringkasan HTML siap-Telegram (`≤ 4.096` karakter, persiapan `16.3d`), dan
>    degradasi mulus saat konteks pasar kosong (`13.4`) atau ekstraksi gagal (`15.2`);
> 4. `scripts/check_reporting.py --offline` **LULUS** (termasuk 5 uji negatif & 0 kebocoran emiten) +
>    uji `--live` menghasilkan laporan lengkap **BBCA 2023–2025** dan **BMRI 2023–2025** yang lolos
>    inspeksi manual 4 dimensi rubrik Skenario 3.

Perkiraan kerja: **3–5 hari**. Semua kode dijalankan dari `.venv` pada branch **`dev`** (jangan
langsung ke `main`).

---

## Status gerbang

- **Minggu 9–10 SELESAI 100%** (27-11-2026): **GATE 4 LULUS PENUH** — Extraction Agent
  ([extraction.py](file:///c:/TugasAkhir/src/agents/extraction.py)) lulus BBCA `23/24 (95,8%)` & BMRI
  `21/24 (87,5%)`, hasil tersimpan di `results/extraction_eval.json`.
- **Minggu 11–12 SELESAI 100%** (27-11-2026): **Financial Analyst Agent**
  ([analyst.py](file:///c:/TugasAkhir/src/agents/analyst.py)) lulus `check_analyst.py` (`--offline`
  & `--live`) dan evaluasi 2 lapis MAE/MAPE (`results/analyst_eval.json`).
- **Minggu 13 SELESAI 100%** (27-11-2026): **Market Observer Agent**
  ([market.py](file:///c:/TugasAkhir/src/agents/market.py)) lulus `check_market.py` (`--offline` &
  `--live`, BBCA `7 -> 5` item & BMRI `7 -> 5` item di `results/check_market.json`).
- **OpenRouter prabayar aktif** (`openai/gpt-oss-120b` di [config.py](file:///c:/TugasAkhir/src/config.py))
  dan **`TAVILY_API_KEY` aktif** di `.env`.
- Git aktif di branch **`dev`** (`origin/dev`), `main` tetap utuh.

> **Aturan disiplin lintas emiten (risiko R10 & R17):**
> `src/agents/reporting.py` **DILARANG** mem-hardcode nama emiten (`BBCA`, `BCA`, `BMRI`, `Mandiri`),
> nomor halaman, atau nomor Catatan. Semua identitas emiten dibaca dinamis dari `metadata.json` /
> `AgentState`, dan profil non-bank (`profile_validated == False`) **wajib** memuat peringatan jelas
> *belum divalidasi* pada laporan akhir maupun ringkasan Telegram.

---

## Keputusan rancangan Minggu 14

### Keputusan 14.A — Arsitektur Hibrida: Tabel & Sitasi Terkunci oleh Python + Narasi Analitis oleh LLM (`14.1`, `14.2`, `14.3`)

Jika seluruh laporan (termasuk tabel 6 rasio × 3 tahun dan 15 metrik keuangan) diserahkan penuh ke
teks bebas LLM, ada tiga risiko yang merusak **RAGAS `faithfulness` (Minggu 17)** dan **rubrik
akurasi faktual Skenario 3 (Minggu 20)**:
1. LLM salah menyalin digit desimal (`29,40%` → `29,14%`) atau menghilangkan sitasi halaman `(hal. 594)`;
2. LLM menebak nilai untuk metrik `not_found` / rasio `insufficient_data` atau mengarang berita saat
   `market_context` kosong;
3. LLM lupa menuliskan label *belum divalidasi* pada emiten non-bank (R17).

**Solusi 3-lapis yang dikunci untuk Minggu 14:**

1. **Lapis 1 — Perakitan Tabel & Daftar Sumber oleh Kode Python (100% deterministik):**
   - Membaca `state["extracted_data"]`, `state["ratios"]`, dan `state["market_context"]` secara langsung:
     - **Banner identitas & validasi profil:** nama emiten, kode saham, sektor, periode tahun, serta
       peringatan eksplisit `> [!WARNING] Profil Umum — Belum Divalidasi` bila `profile_validated == False`.
     - **Tabel Rasio Keuangan & Interpretasi OJK:** baris per rasio (`CAR`, `ROA`, `ROE`, `NIM`, `NPL`,
       `LDR` untuk `bank`; `ROA`, `ROE` untuk `general`), kolom tiap tahun, ambang OJK, status, dan
       **kolom Sumber Halaman wajib** (`hal. ...`). Rasio `insufficient_data` dicetak jujur (`Data tidak
       cukup: <missing_inputs>`).
     - **Tabel Komponen Metrik Keuangan Kunci:** nilai dalam juta Rp (diformat rapi dengan pemisah
       ribuan Indonesia, mis. `Rp 54.836.305 juta`) atau persen, basis pelaporan (`Bank` / `Konsolidasian`),
       dan **kolom Sumber Halaman wajib**. Metrik `not_found`/`ungrounded` dicetak `Tidak tersedia`.
     - **Tabel Tren Antar Tahun:** nilai tahun awal → akhir, perubahan (`±X,XX pp`), dan arah tren
       (`naik` / `turun` / `stabil`); bila hanya 1 tahun tersedia, cetak catatan transparan bahwa data
       pembanding multi-tahun belum tersedia.
     - **Daftar Sumber Konteks Pasar & Regulasi:** butir terstruktur berisi judul, tautan `[Judul](URL)`
       terkunci dari `market_context`, domain, tanggal asli Tavily, kategori, sentimen, dan ringkasan
       singkat. Bila `market_context == []`, tulis keterangan jujur sesuai degradasi mulus `13.4`.
2. **Lapis 2 — Sintesis Narasi Analitis oleh LLM (`openai/gpt-oss-120b`, `effort="medium"`, `method="json_schema"`):**
   - LLM menerima ringkasan data terverifikasi dari Python + `state["query"]` + potongan teratas
     `state["retrieved_chunks"]` (dibatasi maks. 4 chunk × 500 karakter agar hemat token sekaligus
     mendukung pertanyaan **kualitatif/kontekstual** di dataset RAGAS Minggu 17, mis. *"Apa penyebab
     kenaikan pendapatan bunga bersih?"*).
   - LLM mengisi skema Pydantic **`ReportNarrative`**:
     - `direct_answer: str` *(jawaban langsung 2–4 kalimat atas `query` pengguna — sangat penting bagi
       metrik `answer_relevancy` RAGAS Minggu 17)*
     - `executive_summary: str` *(Ringkasan Eksekutif — 1–2 paragraf menyintesis kinerja utama + sitasi halaman)*
     - `ratio_analysis: str` *(Analisis rasio terhadap ambang OJK & keterkaitan antar indikator: permodalan,
       profitabilitas, kualitas aset, likuiditas)*
     - `trend_analysis: str` *(Analisis dinamika tren antar tahun atau catatan jujur bila hanya 1 tahun)*
     - `market_synthesis: str` *(Sintesis konteks berita & regulasi OJK/BI terhadap posisi emiten; jika
       `market_context` kosong, wajib menyatakan tidak tersedia tanpa mengarang)*
     - `conclusion: str` *(Kesimpulan menyeluruh & keterbatasan data secara objektif — bukan rekomendasi
       beli/jual saham)*
   - Jika panggilan LLM gagal/timeout → jatuh mulus ke **narasi fallback deterministik** agar laporan
     tetap terbit lengkap tanpa crash.
3. **Lapis 3 — Perakitan Markdown Final + Pagar Audit Post-Generasi (`audit_report`):**
   - Menggabungkan narasi Lapis 2 + tabel deterministik Lapis 1 ke dalam **5 bagian wajib `14.1`**:
     - Header laporan + Jawaban Langsung *(bila `query` spesifik)* + Banner Peringatan R17 *(bila non-bank)*
     - `## 1. Ringkasan Eksekutif`
     - `## 2. Rasio Keuangan & Interpretasi` *(narasi + tabel rasio + tabel komponen metrik bersitasi)*
     - `## 3. Tren Antar Tahun` *(narasi + tabel tren)*
     - `## 4. Konteks Pasar & Regulasi` *(narasi + daftar tautan berita/regulasi asli Tavily)*
     - `## 5. Kesimpulan` *(narasi kesimpulan + catatan transparansi keterbatasan & disclaimer non-rekomendasi investasi + lampiran indeks halaman PDF & URL sumber)*
   - **Audit otomatis `audit_report()`** memeriksa dan mengamankan:
     - Kelima heading wajib (`14.1`) lengkap;
     - Label *belum divalidasi* hadir bila `not profile_validated` (R17);
     - **Anti-halusinasi URL (`14.2`):** setiap URL `http(s)://...` yang ditulis LLM di luar whitelist
       URL `state["market_context"]` **dideteksi dan dibuang/dibersihkan** secara otomatis oleh Python;
     - Menghitung statistik keterlacakan: jumlah sitasi halaman PDF (`hal. ...`), jumlah URL terverifikasi,
       jumlah rasio `ok` vs `insufficient_data`, dan panjang karakter Markdown.

### Keputusan 14.B — Wajib Sitasi per Angka & Kejujuran Data Kosong (`14.2`)

- **Angka laporan tahunan:** sumber halaman diambil langsung dari `NormalizedMetric.source_pages` dan
  `RatioResult.source_pages` (nomor halaman PDF asli hasil `PageMap` Minggu 3), diformat konsisten
  seperti `hal. 16` atau `hal. 590, 594`.
- **Konteks pasar:** URL dan `published_date` dikunci dari `MarketNewsItem` hasil Market Observer
  (Minggu 13). Bila tanggal kosong dari Tavily, ditampilkan jujur sebagai `tanggal tidak tersedia`.
- **Kejujuran data kosong (`11.4` & `13.4`):**
  - Rasio `insufficient_data` (contoh nyata pada BMRI: `NIM` tidak punya komponen aset produktif bank
    tersedia di hasil ekstraksi) ditampilkan secara transparan — **tidak pernah** diisi angka perkiraan;
  - Bila `market_context == []`, bagian 4 tetap ada dan secara eksplisit menyatakan konteks pasar
    eksternal tidak tersedia saat analisis dijalankan;
  - Bila `extracted_data` & `ratios` keduanya kosong (cabang kegagalan ekstraksi `15.2` di LangGraph),
    Reporting Agent tidak crash dan menyusun **laporan kegagalan terstruktur** yang mencantumkan
    `extraction_errors` agar pengguna tahu penyebabnya.

### Keputusan 14.C — Output Markdown Lengkap + Helper Ringkasan HTML Siap-Telegram (`14.3` & persiapan `16.3d`)

- `state["report"]` menyimpan **Markdown standar (`.md`)** lengkap 5 bagian + tabel (`14.3`), yang
  dipakai langsung oleh:
  - Evaluasi RAGAS (Minggu 17) & perbandingan Skenario 3 (Minggu 20);
  - Lampiran dokumen `.md` pada bot Telegram (`16.3d`).
- Karena pesan teks Telegram dibatasi **4.096 karakter** (`config.TELEGRAM_MAX_MESSAGE_CHARS`) dan
  **tidak merender tabel Markdown**, `src/agents/reporting.py` juga menyediakan fungsi ringan
  **`format_telegram_summary(...) -> str`**:
  - Format **HTML aman** (`<b>`, `<i>`, `<code>`, `<a href="...">`, escape karakter `<`, `>`, `&` via
    `html.escape`) — bebas error escape `MarkdownV2`;
  - Berisi: identitas emiten & tahun, banner R17 (bila non-bank), jawaban ringkas, daftar rasio kunci
    berbentuk bullet singkat (bukan tabel), status konteks pasar, dan catatan *"Laporan lengkap terlampir
    sebagai file `.md`."*
  - Dijamin panjangnya `≤ 3.800` karakter (`< 4.096`).

### Keputusan 14.D — Kontrak State & Parameter Konfigurasi

- Di `src/agents/state.py`:
  - Pertahankan `report: str` (persis seperti kontrak 9.1);
  - Tambahkan skema Pydantic `ReportNarrative` serta 2 field opsional audit/telemetri di `AgentState`:
    `report_audit: dict[str, Any]` dan `report_stats: dict[str, Any]` (untuk pencatatan token, waktu,
    dan jumlah sitasi pada Skenario 3 `20.3`!).
- Tidak ada tambahan dependensi eksternal baru (hanya pustaka standar Python `html`, `re`, `time` +
  `pydantic` + `langchain_core` yang sudah terpasang di `.venv`).

---

## Langkah 1 — Skema Pydantic & Field State (`src/agents/state.py`) · 1 jam

Tambahkan ke [state.py](file:///c:/TugasAkhir/src/agents/state.py):

1. **`ReportNarrative(BaseModel)`:**
   - `direct_answer: str`
   - `executive_summary: str`
   - `ratio_analysis: str`
   - `trend_analysis: str`
   - `market_synthesis: str`
   - `conclusion: str`
2. Pada `AgentState(TypedDict, total=False)`:
   - Pastikan `report: str` tetap ada;
   - Tambahkan `report_audit: dict[str, Any]` dan `report_stats: dict[str, Any]`.

---

## Langkah 2 — Bangun Reporting Agent (`src/agents/reporting.py`, `14.1`–`14.3`) · ½–1 hari

Bangun [reporting.py](file:///c:/TugasAkhir/src/agents/reporting.py) (100% generik, 0 hardcode emiten):

1. **Helper format angka & sitasi deterministik:**
   - `format_id_number(value: float, decimals: int = 2) -> str` (format Indonesia: titik ribuan, koma
     desimal, mis. `54.836.305` atau `29,40%`).
   - `format_pages(pages: Sequence[int]) -> str` (`[590, 594]` → `"hal. 590, 594"`, `[]` → `"sumber tidak tersedia"`).
   - `resolve_report_identity(ticker, sector, years, ratios)` — membaca `company` & `sector` dari
     `data/markdown/<ticker>_<year>.metadata.json` dengan fallback aman ke `ticker.upper()`.
2. **Perakit tabel & bagian deterministik (Lapis 1):**
   - `render_ratios_table(ratios) -> str` — tabel Markdown rasio per tahun + ambang OJK + **kolom Sumber**.
   - `render_metrics_table(extracted_data, sector) -> str` — tabel Markdown metrik keuangan kunci
     terstandar (juta Rp / %) + basis + **kolom Sumber**.
   - `render_trends_table(ratios) -> str` — tabel Markdown perubahan antar tahun (`delta_pp`, arah tren).
   - `render_market_sources(market_context, market_errors) -> str` — daftar sumber berita/regulasi
     dengan URL & tanggal terkunci (atau catatan jujur bila kosong).
   - `render_source_index(extracted_data, ratios, market_context) -> str` — indeks ringkas seluruh
     halaman PDF dan URL yang dirujuk laporan.
3. **Narasi LLM terstruktur + fallback deterministik (Lapis 2):**
   - `REPORTING_SYSTEM_PROMPT`: tegas melarang mengarang angka, melarang mengubah nilai dari Python,
     melarang mengarang URL, mewajibkan penyebutan sumber halaman `(hal. X)` saat menyebut angka di
     narasi, mewajibkan label *belum divalidasi* bila `validated=False`, dan melarang rekomendasi
     beli/jual saham.
   - `generate_narrative(payload, *, llm=None, stats=None) -> tuple[ReportNarrative, bool]`:
     - Memakai `config.get_llm(effort=config.REASONING_EFFORT)` (`"medium"`), `method="json_schema"` +
       fallback `json_mode` + retry ringan;
     - Mencatat `llm_calls`, `input_tokens`, `output_tokens`, `total_tokens` (untuk Skenario 3 `20.3`);
     - Jika `llm` error / output kosong → jatuh mulus ke `build_deterministic_narrative(payload)` (`used_fallback=True`).
4. **Perakitan Markdown + Audit Anti-Halusinasi (`14.1`–`14.3`):**
   - `sanitize_and_audit_urls(text, allowed_urls) -> tuple[str, list[str]]` — menangkap URL apa pun di
     teks narasi LLM yang tidak ada dalam `allowed_urls` (dari `market_context`), menggantinya dengan
     penanda `[tautan dihapus: tidak terverifikasi]`, dan mencatatnya di `report_audit["stripped_urls"]`.
   - `audit_report(markdown, *, ratios, market_context, profile_validated, stripped_urls) -> dict[str, Any]` —
     memvalidasi 5 heading wajib, label R17, jumlah sitasi halaman (`hal.`), jumlah URL valid, dan
     status lolos audit (`passed: bool`).
   - `generate_report(...) -> dict[str, Any]` — API utama yang mengembalikan `report` (Markdown),
     `telegram_summary` (HTML), `report_audit`, dan `report_stats`.
   - `format_telegram_summary(...) -> str` — ringkasan HTML siap-Telegram (`≤ 3.800` karakter, tanpa
     tabel Markdown, aman `html.escape`).
5. **Node LangGraph & CLI:**
   - `reporting_node(state: AgentState) -> dict[str, Any]` — siap dihubungkan di `StateGraph` Minggu 15
     (termasuk menangani kondisi darurat bila `extracted_data` & `ratios` kosong setelah retry `15.2`).
   - CLI smoke test:
     ```powershell
     python -m src.agents.reporting --from-results bbca --out results/sample_report_bbca.md
     python -m src.agents.reporting --from-results bmri --out results/sample_report_bmri.md
     ```

---

## Langkah 3 — Pemeriksaan Otomatis & Uji Negatif (`scripts/check_reporting.py`) · 2–3 jam

Buat `scripts/check_reporting.py` dengan mode `--offline` (`0` token LLM, `< 1 s`) dan mode `--live`
(1 panggilan LLM per bank pada BBCA & BMRI menggunakan hasil nyata Minggu 9–13):

- **A. Struktur 5 bagian wajib & validitas Markdown (`14.1`, `14.3`):**
  - Kelima heading wajib (`Ringkasan Eksekutif`, `Rasio Keuangan & Interpretasi`, `Tren Antar Tahun`,
    `Konteks Pasar & Regulasi`, `Kesimpulan`) hadir berurutan;
  - Semua tabel Markdown memiliki baris pemisah `|---` dan jumlah kolom konsisten per baris.
- **B. Keterlacakan sitasi per angka & URL terkunci (`14.2`):**
  - Setiap rasio `ok` dan metrik `ok` pada tabel memuat rujukan halaman (`hal. ...`) persis sesuai
    `source_pages` input;
  - Setiap item `market_context` tampil dengan URL dan `published_date` asli dari Tavily.
- **C. Profil non-bank (R17) & audit bebas hardcode emiten (R10):**
  - Input sektor `non_financial` (`profile_validated=False`) menghasilkan laporan & ringkasan Telegram
    yang memuat label **belum divalidasi** dan hanya menampilkan ROA & ROE;
  - Audit regex memastikan **0 kebocoran nama emiten / nomor Catatan** di `src/agents/reporting.py`.
- **D. Ringkasan Telegram (`16.3d`) & kontrak `reporting_node`:**
  - `format_telegram_summary` panjangnya `≤ 4.096` karakter, tidak mengandung tabel Markdown (`|---`),
    dan tag HTML seimbang (aman dari karakter `<`, `>`, `&` pada nama perusahaan/berita);
  - `reporting_node(state)` mengisi `report`, `report_audit`, `report_stats`, dan 1 `AIMessage`.
- **E. Uji negatif (5 kasus — HARUS aman & akurat):**
  1. **`market_context = []` (`13.4`):** tidak crash, bagian 4 menyatakan konteks pasar tidak tersedia
     secara jujur, 0 tautan karangan.
  2. **LLM mengarang URL palsu (`https://berita-palsu.example/hoax`):** terdeteksi dan dibersihkan oleh
     `sanitize_and_audit_urls()`, dicatat di `report_audit["stripped_urls"]`, URL palsu tidak muncul
     di laporan akhir.
  3. **Ekstraksi & rasio kosong (kegagalan `15.2`):** `reporting_node` tidak crash dan menghasilkan
     laporan kegagalan jujur lengkap dengan daftar `extraction_errors`.
  4. **Metrik `not_found` / rasio `insufficient_data`:** tercetak eksplisit sebagai data tidak cukup /
     tidak tersedia (tidak diubah jadi `0,00%` atau angka perkiraan).
  5. **LLM error / timeout (`RuntimeError`):** jatuh mulus ke fallback deterministik (`used_fallback=True`)
     dan laporan 5 bagian tetap lulus `audit_report()["passed"] == True`.
- **F. Uji live (`--live`, 2 panggilan LLM pada data nyata BBCA & BMRI):**
  - Membaca data ekstraksi, rasio, dan konteks pasar nyata dari `results/extraction_eval.json`,
    `results/analyst_eval.json`, dan `results/check_market.json`;
  - Menghasilkan `results/sample_report_bbca.md` dan `results/sample_report_bmri.md` beserta metadata
    audit & telemetri token/latensi di `results/check_reporting.json`.

---

## Langkah 4 — Inspeksi Manual Kualitas Laporan BBCA & BMRI · 1 jam

Buka `results/sample_report_bbca.md` dan `results/sample_report_bmri.md`, lalu periksa langsung
berdasarkan **4 dimensi rubrik Skenario 3** (persiapan Minggu 20):

1. **Akurasi faktual:** cocokan 5–6 angka rasio & metrik di narasi dengan tabel deterministik —
   pastikan 0 angka meleset atau bertentangan, dan kasus `NIM` BMRI (`insufficient_data`) dilaporkan
   jujur.
2. **Kelengkapan:** cek kehadiran kelima bagian wajib, sitasi halaman per angka, URL + tanggal berita,
   dan disclaimer non-rekomendasi investasi.
3. **Struktur & keterbacaan:** buka di preview Markdown (VS Code) — pastikan seluruh tabel rapi,
   heading konsisten, dan bahasa Indonesia formal-analitis enak dibaca.
4. **Kedalaman analisis:** cek apakah narasi menghubungkan antar rasio (mis. permodalan CAR vs
   ekspansi kredit LDR & kualitas aset NPL) serta mengaitkannya dengan konteks pasar/OJK secara wajar.

---

## Langkah 5 — Catat, Verifikasi Regresi 4 Agent, & Commit ke Branch `dev` · ½ jam

1. Isi **Lembar hasil** di bawah.
2. Centang butir **Gerbang Minggu 14** di bawah dan `14.1`–`14.3` di [ROADMAP.md](file:///c:/TugasAkhir/docs/ROADMAP.md).
3. Jalankan pemeriksaan offline seluruh 4 agent sekaligus — pastikan semuanya **LULUS**:
   ```powershell
   .venv\Scripts\python.exe scripts\check_reporting.py --offline
   .venv\Scripts\python.exe scripts\check_market.py --offline
   .venv\Scripts\python.exe scripts\check_analyst.py --offline
   .venv\Scripts\python.exe scripts\check_extraction.py --offline
   ```
4. Commit & push ke branch **`dev`** (jangan pernah ke `main`, dan pastikan `.env` tidak pernah
   ter-commit).

---

## Dampak ke Minggu 15–20 dan Bab 4

- **Minggu 15 (Orkestrasi LangGraph):** `reporting_node` menjadi titik pertemuan (*fan-in*) cabang
  `extraction → analyst` dan cabang paralel `market` menuju `END`, sekaligus menangani jalur error
  ketika retry ekstraksi (`15.2`) gagal.
- **Minggu 16 (Bot Telegram & Baseline):** `format_telegram_summary()` langsung dipakai untuk pesan
  ringkas HTML (`16.3d`), sementara `state["report"]` dikirim sebagai lampiran file `.md`.
- **Minggu 17–18 (RAGAS — Skenario 1):** `direct_answer` + potongan `retrieved_chunks` + tabel
  terkunci Python melindungi skor **`faithfulness`** dan **`answer_relevancy`** di atas target `0,80`.
- **Minggu 20 (Skenario 3 — Multi-Agent vs Single-Agent):** `report_stats` (token, panggilan LLM,
  waktu) dan `report_audit` (jumlah sitasi halaman & URL terverifikasi) menjadi metrik otomatis
  langsung untuk `20.3`, sedangkan struktur 5 bagian yang rapi menguatkan skor rubrik penilai blind.

---

## Gerbang (kriteria lolos Minggu 14)

- [ ] **14.1** Prompt & perakit laporan menyusun 5 bagian wajib (*Ringkasan Eksekutif → Rasio & Interpretasi → Tren Antar Tahun → Konteks Pasar → Kesimpulan*) di `src/agents/reporting.py`
- [ ] **14.2** Setiap angka laporan keuangan/rasio wajib menyertakan sumber halaman PDF asli (`hal. ...`) dan setiap berita pasar menyertakan URL + tanggal asli Tavily (dilindungi audit anti-halusinasi URL)
- [ ] **14.3** Output Markdown valid (`state["report"]`) + label *belum divalidasi* untuk profil non-bank (R17) + helper ringkasan HTML siap-Telegram (`≤ 4.096` karakter)
- [ ] **Kriteria lolos Minggu 14:** `scripts/check_reporting.py --offline` (termasuk 5 uji negatif & 0 kebocoran emiten) dan `--live` (BBCA & BMRI → `results/sample_report_{bbca,bmri}.md`) **LULUS**, serta inspeksi manual 4 dimensi lolos

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Narasi LLM memotong kalimat atau keluar kosong | `openai/gpt-oss-120b` menghabiskan jatah `MAX_TOKENS` (4096) untuk token penalaran saat menyusun laporan panjang | Pastikan input prompt ke LLM ringkas (kirim ringkasan tabel terformat, bukan dump JSON mentah); bila masih terpotong, naikkan `max_tokens=6144` khusus Reporting Agent atau turunkan `effort="low"` |
| LLM menulis angka sedikit berbeda dari tabel Python | Penalaran LLM membulatkan ulang angka atau tertukar tahun saat menyusun narasi | Instruksikan tegas di prompt untuk menyalin angka persis dari blok `DATA TERVERIFIKASI`, dan pertahankan tabel deterministik Python sebagai sumber kebenaran utama |
| LLM menyisipkan tautan eksternal yang tidak ada di `market_context` | Pengetahuan pra-latih LLM menebak URL situs berita/OJK | Tangkap otomatis lewat `sanitize_and_audit_urls()` terhadap whitelist `market_context` agar 0 URL tak terverifikasi lolos ke output akhir |
| Error parse HTML di Telegram (Minggu 16) | Karakter `<`, `>`, `&` di judul berita / nama perusahaan tidak di-escape | Selalu lewatkan semua teks dinamis melalui `html.escape()` di `format_telegram_summary()` sebelum dibungkus tag `<b>` / `<a>` |

---

## Lembar hasil — isi sambil jalan

### A. Pemeriksaan otomatis & uji negatif (Langkah 3)

| Item | Hasil |
|---|---|
| `scripts/check_reporting.py --offline` (struktur 5 bagian, sitasi halaman/URL, R17 non-bank, Telegram HTML, 5 uji negatif) | *(isi setelah Langkah 3)* |
| Regresi 4 agent offline (`check_reporting`, `check_market`, `check_analyst`, `check_extraction`) | *(isi setelah Langkah 5)* |

### B. Uji live Laporan Lengkap BBCA & BMRI (Langkah 3–4 — `results/check_reporting.json`)

| Emiten | Audit 5 bagian & URL | Rasio terhitung | Sitasi halaman / URL | Panjang Markdown / Telegram HTML | Latensi & token |
|---|---|---:|---|---|---|
| **BBCA** (2023–2025) | *(isi)* | *(isi)* | *(isi)* | *(isi)* | *(isi)* |
| **BMRI** (2023–2025) | *(isi)* | *(isi)* | *(isi)* | *(isi)* | *(isi)* |

### C. Catatan inspeksi manual & bahan Bab 4 (Langkah 4)

| Dimensi | Catatan |
|---|---|
| Akurasi faktual (kesesuaian narasi vs tabel Python & kejujuran `insufficient_data`) | *(isi)* |
| Kelengkapan & keterlacakan sumber (`hal.` + URL Tavily) | *(isi)* |
| Struktur & keterbacaan Markdown | *(isi)* |
| Kedalaman analisis & sintesis konteks pasar/OJK | *(isi)* |
