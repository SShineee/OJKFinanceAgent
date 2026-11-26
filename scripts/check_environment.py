"""
Minggu 2 -- periksa apakah environment siap.

Jalankan (di dalam venv):  python scripts/check_environment.py

Memeriksa: versi Python, venv aktif, semua paket di requirements.in bisa
di-import, PyTorch memakai GPU (bukan versi CPU), dan API key terbaca.
Tidak memanggil API dan tidak mengunduh model -- aman dijalankan kapan saja.
"""

import _thread
import importlib
import importlib.metadata as md
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# nama di PyPI -> nama modul untuk import
PACKAGES = {
    "torch": "torch", "docling": "docling", "pypdf": "pypdf",
    "sentence-transformers": "sentence_transformers", "chromadb": "chromadb",
    "rank-bm25": "rank_bm25", "langchain": "langchain", "langchain-core": "langchain_core",
    "langchain-groq": "langchain_groq", "langchain-community": "langchain_community",
    "langchain-experimental": "langchain_experimental",
    "langchain-text-splitters": "langchain_text_splitters", "langgraph": "langgraph",
    "tavily-python": "tavily", "langchain-google-genai": "langchain_google_genai",
    "ragas": "ragas", "datasets": "datasets", "pandas": "pandas", "openpyxl": "openpyxl",
    "matplotlib": "matplotlib", "python-telegram-bot": "telegram", "python-dotenv": "dotenv",
}

problems = []


def report(ok, text):
    print(f"  [{'OK' if ok else '!!'}] {text}")
    if not ok:
        problems.append(text)


print("=== Python ===")
v = sys.version_info
report(v[:2] == (3, 12), f"Python {v.major}.{v.minor}.{v.micro}  (yang direncanakan: 3.12.13)")
# Python 3.12.0 terlalu awal: RLock belum punya _recursion_count, sedangkan paket
# `multiprocess` (dependensi datasets/ragas) membutuhkannya -> error saat keluar,
# dan multiprocessing di datasets bisa ikut bermasalah.
report(hasattr(_thread.RLock(), "_recursion_count"),
      "patch Python cukup baru untuk multiprocess" if hasattr(_thread.RLock(), "_recursion_count")
      else "Python terlalu lama untuk multiprocess -- buat ulang venv: uv venv --python 3.12.13 .venv")
in_venv = sys.prefix != sys.base_prefix
report(in_venv and Path(sys.prefix).resolve() == (ROOT / ".venv").resolve(),
      f"venv aktif: {sys.prefix if in_venv else 'TIDAK -- jalankan .venv\\Scripts\\Activate.ps1'}")

print("\n=== Paket ===")
for pypi, module in PACKAGES.items():
    try:
        version = md.version(pypi)
    except md.PackageNotFoundError:
        report(False, f"{pypi:<26} BELUM TERPASANG")
        continue
    try:
        importlib.import_module(module)
        report(True, f"{pypi:<26} {version}")
    except Exception as e:
        report(False, f"{pypi:<26} {version} -- terpasang tapi gagal di-import: {e!s:.80}")

print("\n=== GPU ===")
try:
    import torch
    cuda = torch.cuda.is_available()
    report("+cpu" not in torch.__version__, f"build torch: {torch.__version__}"
          + ("  <-- versi CPU! pasang ulang dari index CUDA" if "+cpu" in torch.__version__ else ""))
    report(cuda, "CUDA tersedia: " + (f"{torch.cuda.get_device_name(0)}, "
                                     f"{torch.cuda.get_device_properties(0).total_memory / 2**30:.1f} GB"
                                     if cuda else "TIDAK"))
except ImportError:
    report(False, "torch belum terpasang")

print("\n=== Konfigurasi & API key ===")
try:
    from src.config import GROQ_MODEL, get_secret
    report(True, f"src.config terbaca, model sistem: {GROQ_MODEL}")
    for name, required in (("GROQ_API_KEY", True), ("GOOGLE_API_KEY", True), ("TAVILY_API_KEY", False)):
        try:
            present = bool(get_secret(name, required=False))
        except Exception:
            present = False
        if required or present:
            report(present, f"{name}: {'ada' if present else 'BELUM di .env'}")
        else:
            print(f"  [--] {name}: belum (baru dibutuhkan Minggu 13)")
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"):
        try:
            present = bool(get_secret(name, required=False))
        except Exception:
            present = False
        print(f"  [{'OK' if present else '--'}] {name}: {'ada' if present else 'belum (baru dibutuhkan Minggu 16)'}")
except Exception as e:
    report(False, f"src.config gagal dimuat: {e}")

print("\n" + "=" * 60)
if problems:
    print(f"  {len(problems)} MASALAH -- lihat baris bertanda [!!] di atas")
    print("  Bagian 'Kalau ada masalah' di docs/PANDUAN_MINGGU2.md")
else:
    print("  ENVIRONMENT SIAP")
print("=" * 60)
sys.exit(1 if problems else 0)
