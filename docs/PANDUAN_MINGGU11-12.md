# Panduan Rinci Minggu 11–12 — Financial Analyst Agent

Minggu 11–12 membangun **Agent 2 (Financial Analyst Agent)**: agen yang membaca angka keuangan
terstandar (**juta Rupiah**) dari `state["extracted_data"]` hasil Extraction Agent (Minggu 9–10),
memilih **profil rasio sektor** secara otomatis dari `state["sector"]`, menghitung seluruh rasio
melalui **eksekusi kode Python (`PythonAstREPLTool`)** berdasarkan formula eksplisit (bukan aritmetika
di kepala LLM), menolak menghitung apabila input `null`/tidak valid, lalu menghasilkan interpretasi
terhadap **ambang batas prudensial OJK**.

> **Target kelulusan Minggu 11–12:** seluruh **6 rasio perbankan (CAR, ROA, ROE, NIM, NPL, LDR) ×
> 3 tahun (2023–2025)** pada **BBCA** terhitung deterministik melalui `PythonAstREPLTool` dengan
> **MAPE < 5%** (klasifikasi proposal: `< 2%` sangat akurat, `2–5%` akurat, `> 5%` kurang akurat),
> **0 perhitungan halusinasi** pada uji negatif input `null` / penyebut `0`, profil **`general`
> (non-bank)** mengeluarkan ROA & ROE berlabel *belum divalidasi*, dan uji lintas bank pada **BMRI**
> dicatat terpisah sebagai dasar Skenario 2 (Minggu 19).

Perkiraan kerja: **1–2 minggu** (Minggu 11: lengkapi formula & ambang OJK di `src/ratio_profiles.py`,
setup `PythonAstREPLTool` di `src/agents/tools.py`, bangun `src/agents/analyst.py` beserta validasi
`null` & dukungan saldo pembanding `t-1`; Minggu 12: `scripts/check_analyst.py` + uji negatif,
evaluasi MAE/MAPE 6 rasio × 3 tahun pada BBCA & BMRI, analisis error untuk Bab 4). Semua kode
dijalankan dari `.venv` pada branch **`dev`** (jangan langsung ke `main`).

---

## Status gerbang

- **Minggu 9–10 SELESAI 100%** (27-11-2026): **GATE 4 LULUS PENUH** — Extraction Agent generik
  ([extraction.py](file:///c:/TugasAkhir/src/agents/extraction.py)) + parser & grounding Python
  ([parse_number.py](file:///c:/TugasAkhir/src/agents/parse_number.py)) lulus **BBCA `23/24 (95,8%)`**
  dan **BMRI `21/24 (87,5%)`** pada commit terkunci `34ac9eb` (gap generalisasi `8,33` pp), 0 kebocoran
  emiten/Catatan, serta 3/3 uji negatif lulus.
- **OpenRouter prabayar aktif** di [config.py](file:///c:/TugasAkhir/src/config.py) (`openai/gpt-oss-120b`,
  `~11–14 s`/laporan tanpa jeda 8K TPM Groq).
- Git aktif di branch **`dev`** (`origin/dev`), `main` tetap utuh.
- ⚠️ **Bimbingan 1.6 masih tertunda — SANGAT PENTING sebelum mengunci formula ROA/NIM final.**
  Bawa hasil validasi GATE 1 ([catatan_validasi_rasio.md](file:///c:/TugasAkhir/docs/catatan_validasi_rasio.md))
  dan temuan Minggu 8 (perbedaan ROA **BMRI** berbasis *Laba Sebelum Pajak* SEOJK vs **BBCA** fn9
  berbasis *Laba Setelah Pajak*) agar formula final resmi disetujui pembimbing.

> **Aturan disiplin lintas emiten (risiko R10 & R11 — tetap berlaku di Minggu 11–12).**
> Formula rasio dan ambang batas di `src/ratio_profiles.py` serta prompt Financial Analyst Agent
> **DILARANG** memuat percabangan per emiten (`if ticker == "bbca": ...`). Satu profil `bank`
> berlaku seragam untuk seluruh bank konvensional Indonesia (BBCA, BMRI, maupun bank baru yang
> diunggah pengguna). Jika ada perbedaan konvensi antar bank (mis. ROA PBT SEOJK vs PAT fn9),
> tangani lewat definisi standar OJK yang konsisten dan dokumentasikan selisihnya secara jujur di
> Bab 4.

---

## Keputusan rancangan Minggu 11–12

### Keputusan 11.A — Formula ditulis eksplisit di kode (`src/ratio_profiles.py`), dieksekusi lewat `PythonAstREPLTool` (`11.1`, `11.2`)

- **Prinsip:** LLM **TIDAK PERNAH** mengarang rumus rasio maupun menghitung pembagian di kepala.
  Seluruh rumus resmi disimpan sebagai struktur data eksplisit (`RatioSpec`) di
  [ratio_profiles.py](file:///c:/TugasAkhir/src/ratio_profiles.py).
- **Peran `PythonAstREPLTool`** (dari `langchain_experimental.tools`, sudah terpasang di `.venv`
  lewat `langchain-experimental==0.4.1`):
  - Dibungkus dengan nama tool bahasa Inggris (mis. `python_repl_ast` / `calculate_financial_ratio`,
    selaras Keputusan 9.C agar `0` error `tool_use_failed`).
  - Sandbox evaluasi terbatas hanya untuk ekspresi matematika aman (angka float, operator aritmetika,
    `round`, `abs`) — tanpa akses filesystem/os.
  - Setiap hasil rasio menyimpan **jejak perhitungan persis** (`expression`, `inputs_used`,
    `source_pages` yang diwarisi dari `extracted_data`), sehingga Reporting Agent (Minggu 14) bisa
    menampilkan rumus, angka pembilang/penyebut, serta sitasi halamannya.
- **Peran LLM di `analyst.py` (`config.get_llm(effort=config.REASONING_EFFORT)` = `"medium"`):**
  - Membaca hasil hitungan rasio yang **sudah pasti benar secara matematis**, membandingkannya
    terhadap ambang batas OJK (`11.6`) dan tren antar tahun (`2023 → 2024 → 2025`), lalu menyusun
    ringkasan interpretasi analitis yang faktual tanpa boleh mengubah angka hasil Python.

### Keputusan 11.B — Formula 6 rasio sektor `bank` vs 2 rasio sektor `general` (`11.2`, `11.3`)

#### 1. Profil `bank` (`validated=True`, mengacu SEOJK No.9/SEOJK.03/2020 & validasi GATE 1 + Minggu 8)

Seluruh nominal sudah seragam dalam **juta Rupiah** dari Extraction Agent. Untuk rasio berbasis
**rata-rata** (`avg(x, t) = (x[t-1] + x[t]) / 2`), lihat Keputusan 11.C tentang cara memperoleh saldo
`t-1`:

| # | Rasio | Formula utama (`RatioSpec`) | Input metrik (`extracted_data`) | Basis | Acuan MAPE (GT) |
|---:|---|---|---|---|---|
| 1 | **CAR** | `total_capital_bank / rwa_bank * 100` | `total_capital_bank`, `rwa_bank` | `bank_only` (saldo akhir) | BBCA `0,01%` · BMRI `0,01%` |
| 2 | **NPL** *(Bruto)* | `npl_amount_bank / gross_loans_bank * 100` | `npl_amount_bank`, `gross_loans_bank` | `bank_only` (saldo akhir) | BBCA `3,02%` · BMRI `0,51%` |
| 3 | **LDR** | `gross_loans_bank / deposits_bank * 100` | `gross_loans_bank`, `deposits_bank` | `bank_only` (saldo akhir) | BBCA `3,11%` · BMRI `0,69%` |
| 4 | **ROE** | `net_income_bank / avg(tier1_capital_bank) * 100` *(fallback pembilang `net_income` bila `net_income_bank` tidak tersedia)* | `net_income_bank` (atau `net_income`), `tier1_capital_bank` (`t` & `t-1`) | `bank_only` (rata-rata Tier 1) | BBCA `1,08%` · BMRI `4,31%` |
| 5 | **ROA** | **Formula SEOJK (utama):** `profit_before_tax_bank / avg(total_assets_bank) * 100` · *(catatan: BBCA fn9 melaporkan ROA setelah pajak `net_income / avg(total_assets) * 100` — lihat kotak di bawah!)* | `profit_before_tax_bank`, `total_assets_bank` (`t` & `t-1`) | `bank_only` (rata-rata aset) | BMRI `3,00%` (SEOJK) · BBCA `1,68%` (fn9 PAT) |
| 6 | **NIM** | `net_interest_income_bank / avg(earning_assets) * 100` *(atau `net_interest_income / earning_assets * 100` bila hanya tersedia aset produktif konsolidasian saldo akhir — lihat caveat GATE 1)* | `net_interest_income` / `net_interest_income_bank`, `earning_assets` | konsisten sesuai ketersediaan laporan | BBCA `4,59%` · BMRI `1,09%` |

> **⚠️ Catatan penting ROA & NIM (bahan bimbingan `1.6` & Bab 4):**
> - **ROA:** SEOJK No.9/SEOJK.03/2020 mendefinisikan ROA bank menggunakan **Laba Sebelum Pajak ÷ rata-rata Total Aset** (dipakai resmi oleh BMRI → MAPE `3,00%`), sedangkan BBCA pada catatan kaki 9 tabel rasionya secara khusus melaporkan **Laba Setelah Pajak ÷ rata-rata Total Aset** (`1,68%`; memakai PBT pada BBCA menghasilkan ROA ~4,6% vs angka cetak BBCA 3,9%). **Jangan** mem-hardcode `if ticker == "bbca"`. Gunakan **satu formula baku** sesuai keputusan pembimbing di `1.6` (bawa keduanya saat bimbingan: (a) baku SEOJK PBT untuk konsistensi regulasi + catat selisih fn9 BBCA di Bab 4, atau (b) hitung juga `roa_after_tax` sebagai metrik informasi tambahan yang dicatat transparan).
> - **NIM:** BBCA mencetak baris *"Total Aset Produktif"* di Ikhtisar (`earning_assets`, MAPE `4,59%` saldo akhir), sedangkan BMRI tidak mencetak satu baris *"Total Aset Produktif"* sehingga di Minggu 8 dihitung dari 5 pos aset produktif inti Neraca Induk (`MAPE 1,09%`). Pastikan `extract_metrics` + `analyst.py` menangani kasus `earning_assets` tersedia langsung vs `null` (menolak menghitung secara jujur jika penyebut tidak tersedia, bukan mengarang!).

#### 2. Profil `general` (`validated=False`, untuk seluruh emiten non-bank — risiko R17)

Dipilih otomatis bila `state["sector"] != "bank"` (mis. `tlkm` / `non_financial`, `insurance`, dll.):
- **ROA:** `net_income / total_assets * 100` *(atau `avg(total_assets)` bila `t-1` tersedia)*
- **ROE:** `net_income / total_equity * 100` *(atau `avg(total_equity)` bila `t-1` tersedia)*
- **Wajib menempelkan label:** `"Profil umum (belum divalidasi — bukan rasio perbankan OJK)"` pada
  setiap entri rasio dan ringkasan interpretasi.

### Keputusan 11.C — Penanganan saldo awal `t-1` untuk rasio rata-rata (`11.3`)

Rasio rata-rata (`ROA`, `ROE`, `NIM`) membutuhkan angka akhir tahun `t-1` dan tahun `t`:
1. **Tahun `2024` & `2025` (saat menganalisis 2023–2025):** angka `t-1` (`2023` & `2024`) sudah ada di
   `state["extracted_data"][t - 1]` — langsung dipakai untuk `avg = (val[t-1] + val[t]) / 2`.
2. **Tahun pertama dalam rentang (mis. `2023`, butuh saldo akhir `2022`):**
   - Laporan tahunan `2023` (`bbca_2023.pdf` & `bmri_2023.pdf`) **sudah memuat kolom pembanding `2022`**
     di tabel Ikhtisar, KPMM, dan Entitas Induk (tanpa perlu PDF tahun 2022!).
   - Sediakan helper opsional di Extraction Agent (mis. `extract_metrics(..., doc_year=2023, years=2022)`
     atau parameter `source_doc_year`) agar saldo pembanding `t-1` untuk rasio rata-rata bisa diekstrak
     dari dokumen tahun `t` saat dibutuhkan.
3. **Fallback transparan (bila pengguna hanya mengunggah 1 tahun tanpa pembanding yang berhasil diekstrak):**
   - **Pilihan tegas:** jika `allow_ending_fallback=False` (mode ketat) → tandai `status="insufficient_data"`
     karena `t-1` hilang; jika `allow_ending_fallback=True` (mode interaktif pengguna) → gunakan saldo
     akhir tahun `t` **dengan peringatan eksplisit** `basis_used="ending_balance_fallback"` di output
     (tidak pernah menyamar sebagai rata-rata!).

### Keputusan 11.D — Validasi input ketat (`11.4`) & Ambang Batas Prudensial OJK (`11.6`)

1. **Validasi sebelum menghitung (`11.4` — pagar anti-halusinasi):**
   - Setiap metrik input wajib memiliki `status == "ok"` dan `value_million_idr is not None`.
   - Penyebut wajib `> 0` (cegah `ZeroDivisionError` dan rasio tak bermakna).
   - Jika satu saja input `null` / `ungrounded` / `not_found` / `parse_error`:
     - **TOLAK menghitung** → kembalikan `value=None`, `status="insufficient_data"`,
       `missing_inputs=[...]`, `interpretation="Tidak dapat dihitung karena data <...> tidak tersedia."`.
     - **DILARANG** mengganti `null` dengan `0`, rata-rata tahun lain, atau estimasi LLM!
2. **Ambang batas prudensial OJK (Tabel 2.2 / POJK KPMM & SEOJK Tingkat Kesehatan Bank — `11.6`):**

| Rasio | Kategori OJK / Prudensial | Ambang | Contoh Interpretasi Baku |
|---|---|---|---|
| **CAR** | Sangat Kuat / Kuat / Minimum / Di bawah minimum | `≥ 15%` sangat kuat · `12–15%` kuat · `8–12%` memenuhi minimum · `< 8%` **di bawah minimum OJK** | *"CAR 29,4% → jauh di atas batas minimum OJK 8%, permodalan sangat kuat."* |
| **ROA** | Sangat Sehat (PK-1) / Sehat / Cukup / Kurang | `> 1,5%` sangat sehat · `1,25–1,5%` sehat · `0,5–1,25%` cukup sehat · `≤ 0,5%` kurang sehat | *"ROA 3,9% → jauh di atas ambang sangat sehat > 1,5%, profitabilitas aset sangat kuat."* |
| **ROE** | Sangat Baik / Baik / Cukup / Rendah | `> 15%` sangat baik · `10–15%` baik · `5–10%` cukup · `< 5%` rendah | *"ROE 24,6% → di atas 15%, tingkat pengembalian modal inti sangat baik."* |
| **NIM** | Sangat Kuat / Sehat / Cukup / Tertekan | `> 5%` sangat kuat · `3–5%` sehat · `2–3%` cukup · `< 2%` tertekan | *"NIM 5,8% → di atas 5%, margin intermediasi bunga sangat kuat."* |
| **NPL** *(Bruto)* | Sangat Sehat / Aman OJK / Melampaui batas OJK | `< 2%` sangat sehat · `2–5%` aman (di bawah batas 5%) · `≥ 5%` **melampaui batas maksimum OJK 5%** | *"NPL 1,78% → jauh di bawah batas maksimum OJK 5% (< 2%), kualitas kredit sangat sehat."* |
| **LDR** | Longgar / Ideal BI–OJK / Ketat | `< 78%` likuiditas longgar · `78–92%` **rentang ideal BI/OJK** · `> 92%` likuiditas ketat | *"LDR 78,4% → berada dalam rentang ideal BI/OJK 78–92%, intermediasi dan likuiditas seimbang."* |

---

## Langkah 0 — Persiapan & cek paket `PythonAstREPLTool` · 15 menit

Pastikan `langchain_experimental.tools.PythonAstREPLTool` dapat diimpor dan diuji aman pada `.venv`:

```powershell
git status                                 # pastikan di branch dev, working tree bersih
python -m src.config                       # OPENROUTER_API_KEY / GROQ_API_KEY OK
python scripts\check_extraction.py --offline  # regresi Minggu 9-10 tetap LULUS
python -c "from langchain_experimental.tools import PythonAstREPLTool; t = PythonAstREPLTool(); print(t.name, t.invoke('round(249056422 / 848181552 * 100, 2)'))"
```

Pastikan keluaran mencetak `python_repl_ast 29.36` tanpa error.

---

## Langkah 1 — Lengkapi `src/ratio_profiles.py` dengan Formula & Ambang OJK (`11.2`, `11.6`) · ½ hari

Perluas [ratio_profiles.py](file:///c:/TugasAkhir/src/ratio_profiles.py) (tanpa merusak `MetricSpec` &
`ExtractionGroup` yang sudah lulus GATE 4!) dengan dua struktur baru:

1. **`OJKThreshold` & `interpret_ratio(ratio_name: str, value: float, profile: SectorProfile) -> dict`:**
   - Fungsi deterministik murni Python untuk memetakan nilai persen rasio ke:
     - `category` (mis. `"sangat_kuat"`, `"ideal"`, `"melampaui_batas_ojk"`),
     - `meets_ojk` (`True` / `False` / `None` untuk profil `general`),
     - `benchmark_text` (mis. `"batas minimum OJK 8%"`, `"rentang ideal BI/OJK 78–92%"`),
     - `summary` (kalimat interpretasi baku bahasa Indonesia, siap dibaca pengguna maupun diperkaya LLM).
2. **`RatioFormula` (terlampir di `SectorProfile.formulas: dict[str, RatioFormula]`):**
   - `name`: `"CAR"`, `"ROA"`, `"ROE"`, `"NIM"`, `"NPL"`, `"LDR"` (untuk `bank`); `"ROA"`, `"ROE"` (untuk `general`).
   - `expression`: ekspresi Python eksplisit (mis. `"(total_capital_bank / rwa_bank) * 100"`).
   - `required_metrics`: tuple `metric_key` tahun `t` yang wajib hadir.
   - `average_metrics`: tuple `metric_key` yang memakai rata-rata `(t-1 + t) / 2` (mis. `("tier1_capital_bank",)` untuk ROE, `("total_assets_bank",)` untuk ROA).
   - `fallback_metrics`: pemetaan opsional bila metrik alternatif sah dipakai (dicatat eksplisit di `notes`).
   - `basis_description`: keterangan basis (*"Bank saja (Entitas Induk)"*, *"Konsolidasian"*, dst.).
   - Tetap **0 nama emiten / halaman / Catatan** (lulus audit `FORBIDDEN_ISSUER_RE` di `check_extraction.py`!).

---

## Langkah 2 — Tool Kalkulator Python (`PythonAstREPLTool`) di `src/agents/tools.py` (`11.1`) · 2 jam

Tambahkan wrapper aman `PythonAstREPLTool` di [tools.py](file:///c:/TugasAkhir/src/agents/tools.py)
(tetap di dalam `src/agents/` sesuai preferensi struktur proyek):

- **Fungsi `evaluate_formula_python(expression: str, variables: dict[str, float]) -> float`:**
  - Menggunakan `PythonAstREPLTool(locals=safe_locals)` dengan variabel float tervalidasi (hanya angka
    terbatas & bukan `NaN`/`Inf`, tanpa akses `import`/`open`/`__builtins__` berbahaya).
  - Menolak ekspresi yang mengandung karakter/kata kunci terlarang sebelum dieksekusi.
  - Mengembalikan `round(float(result), 4)` (nilai persen 4 desimal untuk perhitungan MAPE akurat,
    ditampilkan 2 desimal di laporan).
- **Ekspor LangChain tool `python_calculator`** (nama bahasa Inggris!) untuk dipakai baik oleh
  Financial Analyst Agent maupun Baseline Single-Agent (Minggu 16) agar perbandingan Skenario 3 adil.

---

## Langkah 3 — Skema Output Rasio di `src/agents/state.py` · 1 jam

Tambahkan model Pydantic terstruktur di [state.py](file:///c:/TugasAkhir/src/agents/state.py) (tanpa
mengubah field `AgentState` yang sudah dipakai Extraction Agent):

- **`RatioResult(BaseModel)`:**
  - `ratio_name: str` (`"CAR"`, `"ROA"`, dst.)
  - `year: int`
  - `value: float | None` *(persen, mis. `29.36`; `None` jika ditolak karena input kurang)*
  - `unit: Literal["percent"] = "percent"`
  - `status: Literal["ok", "insufficient_data", "calc_error"]`
  - `formula: str` *(ekspresi eksplisit yang dieksekusi `PythonAstREPLTool`)*
  - `basis_used: str` *(mis. `"bank_only_ending"`, `"bank_only_average"`, `"ending_balance_fallback"`)*
  - `inputs_used: dict[str, float]` *(nilai juta Rupiah yang masuk ke perhitungan)*
  - `missing_inputs: list[str]` *(diisi jika `status == "insufficient_data"`)*
  - `source_pages: list[int]` *(gabungan halaman sumber dari seluruh input — rantai sitasi utuh!)*
  - `ojk_category: str | None`
  - `meets_ojk: bool | None`
  - `ojk_benchmark: str | None`
  - `interpretation: str` *(interpretasi terhadap ambang OJK + label belum divalidasi jika `general`)*
  - `notes: str | None`
- Struktur `state["ratios"]`:
  ```python
  {
      "sector": "bank",
      "profile_validated": True,
      "profile_warning": None,           # terisi jelas bila profil general!
      "by_year": {2023: {"CAR": {...}, ...}, 2024: {...}, 2025: {...}},
      "trends": {"CAR": {"2023_to_2025_pp": +0.32, "direction": "naik"}, ...},
      "analysis_summary": "...",         # ringkasan lintas rasio & tren (diisi LLM / deterministik)
      "analyst_stats": {"llm_calls": ..., "total_tokens": ..., "seconds": ...},
  }
  ```

---

## Langkah 4 — Financial Analyst Agent (`src/agents/analyst.py`, `11.1`–`11.6`) · 1–2 hari

### a. Alur deterministik + interpretasi analitis (`analyze_ratios()` & `analyst_node(state)`)

1. **Baca profil sektor** via `profile = rp.get_profile(state.get("sector"))`.
   - Jika `profile.validated is False` (`general`): tempelkan `profile.warning_label` (*"belum
     divalidasi"*) pada setiap rasio dan ringkasan.
2. **Validasi input ketat per `(year, ratio)` (`11.4`):**
   - Periksa seluruh `required_metrics` pada `extracted_data[year]`: wajib `status == "ok"` dan
     `value_million_idr is not None`.
   - Untuk metrik di `average_metrics` (`11.3`):
     - Cari `extracted_data[year - 1][key]` (harus `status == "ok"` dan tidak `None`).
     - Jika ada → hitung `avg_val` via `PythonAstREPLTool` (`(prev + curr) / 2`).
     - Jika tidak ada → ikuti kebijakan `allow_ending_fallback` (mode ketat evaluasi: tolak / catat
       `missing_inputs`; mode fallback eksplisit: pakai saldo akhir dengan `basis_used="ending_balance_fallback"`).
   - Periksa penyebut `> 0`. Jika gagal validasi → kembalikan `RatioResult(status="insufficient_data", value=None, ...)`.
3. **Eksekusi formula lewat `PythonAstREPLTool` (`11.1`):**
   - Panggil `evaluate_formula_python(formula.expression, vars_dict)`.
   - Kumpulkan `source_pages` dari semua metrik input secara otomatis (sorted, unik).
4. **Interpretasi ambang batas OJK (`11.6`):**
   - Hitung kategori, status `meets_ojk`, dan kalimat interpretasi baku secara deterministik lewat
     `rp.interpret_ratio()`.
   - Hitung tren antar tahun (`delta` dalam poin persen dan arah: `naik` / `turun` / `stabil`) bila
     tersedia ≥ 2 tahun.
   - *(Opsional / saat `use_llm_summary=True`)* Panggil `config.get_llm(effort=config.REASONING_EFFORT)`
     (`reasoning_effort="medium"`) untuk menyusun `analysis_summary` lintas rasio & tren — dengan
     aturan ketat di prompt: **hanya boleh mengutip angka yang sudah dihitung Python**, dilarang
     menghitung ulang atau mengubah angka, dan wajib menyertakan peringatan `profile_warning` jika
     profil `general`.
5. **Integrasi LangGraph (`analyst_node(state)`):**
   - Menerima `AgentState` langsung dari output `extraction_node`, mengisi `ratios` dan menambahkan
     ringkasan `AIMessage` ke `messages`.
6. **CLI smoke test:**
   ```powershell
   python -m src.agents.analyst --ticker bbca --from-gt         # tes deterministik dari ground truth
   python -m src.agents.analyst --ticker bbca --year 2023 2024 2025  # end-to-end dengan Extraction Agent
   ```

---

## Langkah 5 — Pemeriksaan otomatis & uji negatif (`scripts/check_analyst.py`) · ½ hari

Buat `scripts/check_analyst.py` (mode `--offline` = 0 token API, `< 5 s`):

- **A. `PythonAstREPLTool` (`11.1`):** evaluasi ekspresi rasio bank akurat sampai 4 desimal; menolak
  input berbahaya (mis. `__import__('os')`, `open(...)`).
- **B. Formula & basis rata-rata (`11.2`, `11.3`):** hitung 6 rasio × 3 tahun dari angka mentah
  `data/ground_truth.xlsx` BBCA → verifikasi seluruh 6 rasio **MAPE < 5%** cocok dengan hasil GATE 1.
- **C. Ambang OJK (`11.6`):** uji nilai batas setiap rasio (`CAR 7,5%` → di bawah minimum OJK;
  `CAR 29,4%` → sangat kuat; `NPL 5,2%` → melampaui batas OJK; `LDR 85%` → ideal; `LDR 65%` → longgar;
  `LDR 96%` → ketat).
- **D. Profil non-bank `general` (R17):** masukkan data dummy sektor `"non_financial"` (seperti TLKM)
  → hanya menghitung **ROA & ROE**, `profile_validated=False`, dan label *"belum divalidasi"* wajib
  muncul di setiap interpretasi.
- **E. Uji negatif (HARUS ditolak — `11.4`):**
  1. **Input `null` (`status="not_found"`):** salah satu metrik pembilang/penyebut `None` → wajib
     menghasilkan `status="insufficient_data"` dan `value=None` (tidak boleh `0` atau crash!).
  2. **Input `ungrounded`:** metrik ditolak pagar grounding Extraction Agent → wajib ditolak di
     Financial Analyst (`status="insufficient_data"`, `value=None`).
  3. **Penyebut nol atau negatif (`rwa_bank = 0`):** wajib ditolak bersih (`status="insufficient_data"`
     atau `calc_error`, `value=None`, tanpa `ZeroDivisionError`).
  4. **Bebas kebocoran emiten:** audit regex memastikan `analyst.py` & `ratio_profiles.py` tetap 0
     hardcode nama bank / nomor halaman / nomor Catatan.

---

## Langkah 6 — Evaluasi MAE & MAPE 6 Rasio × 3 Tahun: BBCA & BMRI (`11.5`) · 1 hari

**File:** `eval/ratio_analyst_eval.py` → `results/analyst_eval_bbca.json/.csv` & `results/analyst_eval_bmri.json/.csv`

Jalankan **dua lapis evaluasi** yang sangat berguna untuk analisis error Bab 4 (memisahkan error
*formula* dari error *ekstraksi*!):

1. **Lapis 1 — Evaluasi Formula (input dari Ground Truth mentah, 0 token LLM):**
   - Mengukur batas atas teoritis ketepatan formula `src/ratio_profiles.py` terhadap rasio resmi di
     `ground_truth.xlsx` (BBCA) dan `ground_truth_bmri.xlsx` (BMRI) (`sheet 2_rasio_resmi`).
   - Memverifikasi bahwa setiap perbedaan sisa murni berasal dari beda konvensi pelaporan (mis. rata-rata
     bulanan OJK vs 2-titik tahunan, atau ROA PBT vs PAT), **bukan** bug kode.
2. **Lapis 2 — Evaluasi End-to-End (`Extraction Agent → Financial Analyst Agent`, 1 run per emiten di
   Minggu 12; nanti diperluas menjadi 5 run di Skenario 2 Minggu 19):**
   - Jalankan ekstraksi 15 metrik bank (termasuk saldo pembanding `2022` dari laporan `2023` untuk
     rasio rata-rata!) pada **BBCA 2023–2025** → hitung MAE & MAPE per rasio (`< 2%` sangat akurat,
     `2–5%` akurat, `> 5%` kurang akurat).
   - Catat juga evaluasi terpisah pada **BMRI 2023–2025** untuk memetakan dampak error ekstraksi
     terhadap MAPE rasio sebelum masuk Minggu 13–15.
   - Simpan tabel rinci per `(ticker, year, ratio)`: `nilai_sistem | nilai_resmi | AE | APE (%) | kategori_OJK | status`.

---

## Langkah 7 — Catat, verifikasi, & commit ke branch `dev` · ½ jam

1. Isi **Lembar hasil** di bawah (MAE & MAPE Lapis 1 & Lapis 2 terpisah untuk BBCA dan BMRI).
2. Centang butir **Gerbang Minggu 11–12** di bawah dan tugas `11.1`–`11.6` di [ROADMAP.md](file:///c:/TugasAkhir/docs/ROADMAP.md).
3. Jalankan `python scripts\check_analyst.py --offline` dan `python scripts\check_extraction.py --offline`,
   pastikan keduanya **LULUS**, lalu commit & push ke branch **`dev`**.

---

## Dampak ke Minggu 13–19 dan Bab 4

- **Minggu 14 (Reporting Agent):** langsung mengonsumsi `state["ratios"]` yang sudah memuat angka
  presisi, rumus, `source_pages`, tren 2023–2025, kategori OJK, dan `profile_warning` (untuk non-bank).
- **Minggu 15 (Orkestrasi LangGraph):** `analyst_node(state)` langsung disambungkan setelah
  `extraction_node(state)` di `StateGraph(AgentState)`.
- **Minggu 16 (Baseline Single-Agent):** memakai tool `python_calculator` yang sama agar perbandingan
  Skenario 3 adil (beda arsitektur, bukan beda alat).
- **Minggu 19 (Skenario 2 — 5× run MAE/MAPE):** `eval/ratio_eval.py` tinggal mengulang pipeline
  `Extraction → Financial Analyst` sebanyak **5 run** pada BBCA & BMRI dan menghitung `mean ± std`,
  MAE, MAPE, serta grafik bar chart ambang 5%.

---

## Gerbang (kriteria lolos Minggu 11–12)

- [ ] **11.1** `PythonAstREPLTool` dibungkus aman di `src/agents/tools.py` (nama tool bahasa Inggris, menolak ekspresi berbahaya)
- [ ] **11.2** `src/ratio_profiles.py` memuat formula eksplisit & ambang OJK untuk `bank` (6 rasio SEOJK, `validated=True`) dan `general` (ROA & ROE, `validated=False` + label *belum divalidasi*), 0 hardcode nama emiten
- [ ] **11.3** Basis perhitungan rata-rata vs saldo akhir konsisten dengan GATE 1 (dukungan saldo pembanding `t-1` dari dokumen tahun `t` + penandaan eksplisit bila fallback)
- [ ] **11.4** Validasi ketat: menolak menghitung jika input `null` / `ungrounded` / penyebut `≤ 0` (dibuktikan 3/3 uji negatif di `scripts/check_analyst.py`)
- [ ] **11.5** Tes 6 rasio × 3 tahun pada **BBCA** (dan uji lintas bank **BMRI**): MAE & MAPE tersimpan di `results/analyst_eval_*.csv/.json`
- [ ] **11.6** Interpretasi otomatis terhadap ambang batas OJK (Tabel 2.2) + tren antar tahun aktif di `src/agents/analyst.py` (`analyst_node`)
- [ ] **Kriteria lolos Minggu 11–12:** `scripts/check_analyst.py --offline` **LULUS**; MAPE formula Lapis 1 & end-to-end BBCA **< 5%** (setiap rasio > 5% terdiagnosis akar masalahnya untuk Bab 4)

---

## Kalau ada masalah

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `PythonAstREPLTool` mengembalikan string bukan float, atau error sintaks | Ekspresi memakai koma desimal Indonesia atau variabel `None` | Pastikan seluruh input sudah dikonversi `float` juta Rupiah oleh `parse_number.py` dan divalidasi sebelum masuk ke `PythonAstREPLTool` |
| MAPE ROA BBCA ~20% saat memakai formula SEOJK (PBT) | BBCA fn9 melaporkan ROA setelah pajak (PAT), sedangkan BMRI memakai Laba Sebelum Pajak (PBT SEOJK) | Jangan buat `if ticker == "bbca"`; pastikan keputusan formula baku dikunci bersama pembimbing (1.6) dan laporkan selisih definisi ini secara transparan di Bab 4 |
| Rasio rata-rata tahun `2023` tidak bisa dihitung (`t-1` = 2022 hilang) | Extraction Agent baru menarik kolom tahun `2023`, belum menarik kolom pembanding `2022` | Tarik saldo pembanding `2022` dari dokumen `2023` (kolom pembanding sudah ada di PDF `2023`) atau tandai eksplisit `ending_balance_fallback` |
| NIM BMRI keluar `insufficient_data` | BMRI tidak mencetak satu baris *"Total Aset Produktif"* di Ikhtisar (harus dari pos Aset Produktif Inti Neraca Induk) | Periksa apakah penyebut NIM bisa disusun generik dari pos aset produktif Neraca Induk atau catat jujur sebagai keterbatasan ketersediaan baris (tidak boleh mengarang angka!) |
| LLM mengubah angka rasio saat menyusun `analysis_summary` | Prompt interpretasi terlalu bebas sehingga LLM membulatkan ulang atau salah salin | Kunci angka rasio pada struktur `RatioResult` hasil Python; jadikan `analysis_summary` murni narasi pendamping dan validasi bahwa setiap persen yang disebut sesuai hasil Python |

---

## Lembar hasil — isi sambil jalan

### A. Pemeriksaan otomatis & uji negatif (Langkah 5)

| Item | Hasil |
|---|---|
| `scripts/check_analyst.py --offline` (REPL aman, formula GT, ambang OJK, non-bank, 3 uji negatif) | *(Langkah 5)* |
| `scripts/check_extraction.py --offline` (regresi 0 kebocoran emiten di `ratio_profiles.py`) | *(Langkah 5)* |

### B. Evaluasi MAE & MAPE — 6 rasio × 3 tahun (terpisah per emiten, Langkah 6)

| # | Rasio | BBCA MAPE (Lapis 1 GT) | BBCA MAPE (Lapis 2 E2E) | Klasifikasi BBCA | BMRI MAPE (Lapis 1 GT) | BMRI MAPE (Lapis 2 E2E) | Klasifikasi BMRI |
|---:|---|---:|---:|---|---:|---:|---|
| 1 | **CAR** | `%` | `%` | — | `%` | `%` | — |
| 2 | **ROA** | `%` | `%` | — | `%` | `%` | — |
| 3 | **ROE** | `%` | `%` | — | `%` | `%` | — |
| 4 | **NIM** | `%` | `%` | — | `%` | `%` | — |
| 5 | **NPL** | `%` | `%` | — | `%` | `%` | — |
| 6 | **LDR** | `%` | `%` | — | `%` | `%` | — |
| | **Rata-rata** | **`%`** | **`%`** | — | **`%`** | **`%`** | — |

*(Klasifikasi proposal: `< 2%` sangat akurat · `2–5%` akurat · `> 5%` kurang akurat.)*

### C. Diagnosis error & catatan untuk Bab 4

| Item | Catatan |
|---|---|
| Keputusan formula ROA final (SEOJK PBT vs PAT fn9) | *(isi setelah bimbingan 1.6)* |
| Rasio dengan MAPE > 5% & akar masalah (ekstraksi vs definisi vs rata-rata bulanan) | *(Langkah 6)* |
| Uji profil non-bank (`general`) + label *belum divalidasi* | *(Langkah 5)* |
| Catatan kesiapan menuju Minggu 13 (Market Observer) & Minggu 19 (Skenario 2 5× run) | *(Langkah 7)* |
