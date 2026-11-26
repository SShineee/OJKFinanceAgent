"""
Konfigurasi terpusat.

SEMUA nama model, path, dan parameter ada di sini -- tidak boleh di-hardcode
di file lain. Alasannya: kalau Groq mematikan sebuah model (seperti yang terjadi
pada `llama3-70b-8192`), Anda cukup mengubah satu baris di file ini.

API key dibaca dari `.env`, yang TIDAK ikut ter-commit. Lihat `.env.example`.

Cek konfigurasi:  python -m src.config
"""

import os
from pathlib import Path

# ----------------------------------------------------------------- .env
ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:                                  # fallback tanpa dependensi
    _env = ROOT / ".env"
    if _env.exists():
        for _line in _env.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def get_secret(name: str, required: bool = True) -> str:
    """Ambil API key dari environment. Pesan errornya menyebut cara memperbaiki."""
    v = os.environ.get(name, "").strip()
    if not v or v.startswith(("isi_disini", "gsk_isi", "tvly-isi")):
        if required:
            raise RuntimeError(
                f"{name} belum di-set.\n"
                f"  1. copy .env.example .env\n"
                f"  2. isi {name} di file .env"
            )
        return ""
    return v


# ----------------------------------------------------------------- MODEL
# Keputusan Minggu 1 (tugas 1.3): `llama3-70b-8192` yang ditulis di proposal
# sudah tidak tersedia di Groq. Diganti ke gpt-oss-120b -- tetap open weight
# (Apache 2.0), tetap gratis, tetap di LPU Groq, jadi justifikasi Bab 2.2 utuh.
GROQ_MODEL = "openai/gpt-oss-120b"          # model utama semua agent
GROQ_MODEL_FAST = "openai/gpt-oss-20b"     # cadangan kalau kena rate limit
TEMPERATURE = 0.0                            # analisis keuangan: jangan kreatif

# gpt-oss adalah REASONING MODEL: ia memakai token untuk penalaran sebelum
# mengisi `content`. Kalau MAX_TOKENS terlalu kecil, jawaban keluar KOSONG.
# Dibuktikan di Minggu 1: max_tokens=10 -> content = ''.
MAX_TOKENS = 4096
# low / medium / high. Ekstraksi angka tidak butuh penalaran dalam -> "low"
# lebih hemat token & lebih cepat. Analisis rasio -> "medium".
REASONING_EFFORT = "medium"
REASONING_EFFORT_EXTRACTION = "low"

# Embedding untuk knowledge base (lokal, tidak perlu API)
EMBED_MODEL = "BAAI/bge-m3"
EMBED_DIM = 1024

# LLM judge RAGAS -- SENGAJA beda penyedia dengan GROQ_MODEL untuk menghindari
# bias self-preference. Jangan diganti ke model OpenAI tanpa alasan kuat.
JUDGE_MODEL = "gemini-2.5-flash"
JUDGE_EMBED_MODEL = "models/text-embedding-004"

# ----------------------------------------------------------------- DATA
YEARS = [2023, 2024, 2025]                   # keputusan Minggu 1 (tugas 1.1)

# Ruang lingkup (27-10-2026): sistem menganalisis laporan tahunan EMITEN BEI mana pun
# yang diunggah pengguna. Identitas emiten = KODE SAHAM huruf kecil -- unik, dan sama
# dengan yang dipakai idx.co.id.
#
# Yang DIVALIDASI hanya sektor perbankan (keputusan final 27-10-2026). Emiten
# PENGEMBANGAN dipakai merancang & men-tuning; emiten UJI tidak boleh disentuh saat
# merancang prompt -- hanya untuk evaluasi akhir, supaya MAPE tidak optimistis karena
# sistem "hafal" satu format. "opsional" dilepas lebih dulu kalau waktu mepet (R12).
VALIDATED_SECTORS = {
    "bank": {
        "development": "bbca",                 # BCA -- ground truth selesai Minggu 1
        "test": ["bmri"],                        # Mandiri -- PDF baru diunduh Minggu 8
        "optional": ["bbri"],                   # BRI
    },
}
# Emiten non-bank tetap bisa diunggah, tapi memakai profil "umum" (ROA, ROE) dan
# diberi label "belum divalidasi" -- lihat Minggu 11. Validasinya = saran penelitian.
UNPROFILED_SECTORS = ["non_financial", "islamic_bank", "insurance", "multifinance", "securities"]

DEV_TICKER = VALIDATED_SECTORS["bank"]["development"]   # default path di bawah

DATA = ROOT / "data"
DATA_RAW = DATA / "raw"
DATA_MARKDOWN = DATA / "markdown"
DATA_CHUNKS = DATA / "chunks"
GROUND_TRUTH = DATA / "ground_truth.xlsx"

CHROMA_DIR = ROOT / "chroma_db"
CHROMA_COLLECTION = "annual_reports"      # SATU koleksi, dibedakan metadata `ticker` & `sector`
# BM25: satu indeks per laporan, dibangun di memori dari .jsonl (src/retrieval/sparse.py, Minggu 6)

RESULTS = ROOT / "results"
EVAL_DATASETS = ROOT / "eval" / "datasets"

# Nama file: <kode saham>_<tahun>, mis. data/raw/bbca_2024.pdf
def pdf(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_RAW / f"{ticker}_{year}.pdf"

def markdown(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_MARKDOWN / f"{ticker}_{year}.md"

def subset(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_MARKDOWN / f"{ticker}_{year}.subset.pdf"   # PDF potongan = input Docling

def docling_json(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_MARKDOWN / f"{ticker}_{year}.json"         # dokumen Docling = sumber kebenaran

def parse_meta(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_MARKDOWN / f"{ticker}_{year}.meta.json"    # hash, peta halaman, waktu; = cache

def report_metadata(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_MARKDOWN / f"{ticker}_{year}.metadata.json"  # kode saham, sektor, dst. (Langkah 7)

DATA_PARSE_TRIAL = DATA_MARKDOWN / "trial"   # parse sebagian (--max-pages / --pages), bukan cache


# ----------------------------------------------------------------- PARSING (Minggu 3)
DOCLING_DEVICE = "cuda"           # jatuh ke "cpu" (jauh lebih lambat) kalau GPU tidak ada
DOCLING_TABLE_MODE = "accurate"   # TableFormer: "accurate" / "fast"
DOCLING_DO_OCR = False            # PDF BCA berbentuk teks; OCR hanya perlu untuk hasil scan
DOCLING_CELL_MATCHING = True      # bawaan Docling; coba False kalau kolom tabel tertukar

# ----------------------------------------------------------------- CHUNKING (Minggu 5)
CHUNK_MAX_TOKENS = 1024        # Keputusan 5.A -- token BGE-M3; tabel lebih besar dipecah per baris
CHUNK_BOILERPLATE_REPEAT = 3   # teks yang muncul >= 3x dalam satu laporan = boilerplate, dibuang
CHUNK_VERSION = 1              # naikkan setiap aturan chunking berubah -> chunk lama dibuat ulang

def chunks(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_CHUNKS / f"{ticker}_{year}.jsonl"

def chunks_meta(year: int, ticker: str = DEV_TICKER) -> Path:
    return DATA_CHUNKS / f"{ticker}_{year}.chunks.meta.json"   # kunci cache + statistik; = cache

# ----------------------------------------------------------------- INDEXING (Minggu 6)
EMBED_DTYPE = "float16"   # Keputusan 6.A (15-11-2026): 54 s vs 193 s fp32, kosinus >= 0,9997. CPU -> float32
EMBED_BATCH = 16          # 16 dan 32 sama cepat di RTX 3060 6 GB
EMBED_DEVICE = "cuda"     # jatuh ke "cpu" kalau GPU tidak ada (+-47 menit untuk 1.552 chunk)


# ----------------------------------------------------------------- RETRIEVAL
TOP_K_DENSE = 10          # kandidat dari ChromaDB
TOP_K_SPARSE = 10         # kandidat dari BM25
TOP_K_FINAL = 5           # hasil akhir setelah RRF
RRF_K = 60                # konstanta Reciprocal Rank Fusion
CHROMA_SPACE = "cosine"   # JANGAN "l2" -- embedding BGE-M3 sudah dinormalisasi

# ----------------------------------------------------------------- AGENT
MAX_EXTRACTION_RETRIES = 1   # extraction gagal -> coba sekali lagi, lalu lapor
RECURSION_LIMIT = 25      # pagar LangGraph supaya tidak infinite loop

# ----------------------------------------------------------------- TELEGRAM (Minggu 16)
# Bot standar hanya bisa MENGUNDUH file <= 20 MB (FAQ resmi Telegram), padahal laporan
# tahunan bank 30-60 MB. Local Bot API Server (Docker) menghapus batas itu -- risiko R18.
TELEGRAM_DOWNLOAD_LIMIT_MB = 20                       # tanpa Local Bot API Server
TELEGRAM_LOCAL_API_URL = "http://localhost:8081"   # Local Bot API Server; None = server Telegram
TELEGRAM_MAX_MESSAGE_CHARS = 4096                      # panjang maksimal satu pesan

TAVILY_DOMAINS = [
    "bca.co.id", "ojk.go.id", "idx.co.id",
    "kontan.co.id", "bisnis.com", "cnbcindonesia.com",
]


# ----------------------------------------------------------------- LLM lazy
# Dibuat di dalam fungsi, BUKAN di level modul, supaya config.py tetap bisa
# diimpor sebelum langchain terpasang (Minggu 2).
def get_llm(fast: bool = False, effort: str = None, **kw):
    """LLM untuk agent. `effort` mengatur kedalaman penalaran gpt-oss."""
    from langchain_groq import ChatGroq
    # langchain-groq >= 1.x menolak reasoning_effort lewat model_kwargs
    # ("should be specified explicitly") -- harus parameter langsung.
    return ChatGroq(
        model=GROQ_MODEL_FAST if fast else GROQ_MODEL,
        temperature=kw.pop("temperature", TEMPERATURE),
        max_tokens=kw.pop("max_tokens", MAX_TOKENS),
        reasoning_effort=effort or REASONING_EFFORT,
        api_key=get_secret("GROQ_API_KEY"),
        **kw,
    )


def get_judge(**kw):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=JUDGE_MODEL, temperature=0.0,
        google_api_key=get_secret("GOOGLE_API_KEY"), **kw,
    )


# ----------------------------------------------------------------- self-check
if __name__ == "__main__":
    print(f"ROOT          : {ROOT}")
    print(f"Model sistem  : {GROQ_MODEL}  (reasoning model)")
    print(f"  max_tokens  : {MAX_TOKENS}   reasoning_effort: {REASONING_EFFORT}")
    print(f"Model cadangan: {GROQ_MODEL_FAST}")
    print(f"Embedding     : {EMBED_MODEL} (dim {EMBED_DIM})")
    print(f"LLM judge     : {JUDGE_MODEL}")
    print(f"Periode data  : {YEARS}")
    for sector, e in VALIDATED_SECTORS.items():
        print(f"Sektor {sector:<13}: dev {e['development']}   uji {', '.join(e['test'])}"
              f"   (opsional {', '.join(e['optional'])})")

    print("\nAPI key:")
    for name, required_now in (("GROQ_API_KEY", True),
                                 ("TAVILY_API_KEY", False),
                                 ("GOOGLE_API_KEY", False),
                                 ("TELEGRAM_BOT_TOKEN", False),
                                 ("TELEGRAM_ALLOWED_USERS", False)):
        try:
            v = get_secret(name, required=required_now)
            print(f"  {name:<24} OK     ({v[:7]}...{v[-4:]})" if v
                  else f"  {name:<24} belum  (belum dibutuhkan)")
        except RuntimeError:
            print(f"  {name:<24} BELUM DI-SET  <-- wajib")

    print("\nPDF (emiten pengembangan & uji wajib):")
    for e in VALIDATED_SECTORS.values():
        for ticker in [e["development"], *e["test"]]:
            for t in YEARS:
                p = pdf(t, ticker)
                status = "ada" if p.exists() else ("belum (diunduh Minggu 8)" if ticker in e["test"] else "BELUM")
                print(f"  {p.name:<16} {status}"
                      f"{f'  ({p.stat().st_size / 1_048_576:.1f} MB)' if p.exists() else ''}")
