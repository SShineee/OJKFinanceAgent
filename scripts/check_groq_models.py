"""
Tugas 1.3 -- cek model Groq mana yang masih aktif.

Jalankan:
    python scripts/check_groq_models.py

Key dibaca dari file `.env` lewat src/config.py -- tidak perlu set $env: lagi.

Proposal menyebut "Llama 3 70B". ID lama `llama3-70b-8192` kemungkinan sudah
di-decommission Groq. Script ini menampilkan daftar model yang BENAR-BENAR
tersedia di akun Anda, lalu mencoba memanggil kandidat penggantinya.

Catat hasilnya di docs/catatan_validasi_rasio.md, lalu update:
  - Proposal Bab 2.2  (penjelasan pemilihan LLM)
  - Proposal Tabel 3.1 (Kebutuhan Sistem)
  - src/config.py
"""

import json
import os
import sys
from pathlib import Path
import urllib.error
import urllib.request

API = "https://api.groq.com/openai/v1"
CANDIDATES = [
    "llama3-70b-8192",            # yang ditulis di proposal (diduga sudah mati)
    "llama-3.3-70b-versatile",    # kandidat Llama pengganti
    "openai/gpt-oss-120b",        # PILIHAN SEKARANG -- lihat src/config.py
    "openai/gpt-oss-20b",         # cadangan kalau kena rate limit
    "qwen/qwen3.8-27b",           # alternatif
]


# Groq ada di belakang Cloudflare. User-Agent default urllib ("Python-urllib/3.x")
# diblokir sebagai bot -> HTTP 403 error code 1010. Harus di-set eksplisit.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) skripsi-bca/1.0"


def request_json(path, key, payload=None):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": UA,
            "Accept": "application/json",
        },
        data=json.dumps(payload).encode() if payload else None,
        method="POST" if payload else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def explain_http_error(e):
    body = e.read().decode(errors="replace")[:300]
    hint = {
        401: "API key salah atau belum aktif. Cek ulang di console.groq.com/keys.",
        403: "Ditolak. Kalau body-nya memuat 'error code: 1010' berarti User-Agent "
             "diblokir Cloudflare -- seharusnya sudah ditangani. Kalau bukan, "
             "cek apakah key punya izin yang benar.",
        429: "Rate limit. Tunggu sebentar lalu ulangi.",
    }.get(e.code, "")
    extra = "\n  -> " + hint if hint else ""
    return f"HTTP {e.code}: {body}{extra}"


def main():
    # Baca dari .env lewat src/config.py; kalau gagal, jatuh ke environment biasa
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from src.config import get_secret
        key = get_secret("GROQ_API_KEY")
    except Exception:
        key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        sys.exit("GROQ_API_KEY belum di-set. Isi di file .env (lihat .env.example).")

    try:
        data = request_json("/models", key)
    except urllib.error.HTTPError as e:
        sys.exit(f"Gagal ambil daftar model: {explain_http_error(e)}")
    except urllib.error.URLError as e:
        sys.exit(f"Tidak bisa menghubungi {API} -- {e.reason}. Cek koneksi internet.")

    available = sorted(m["id"] for m in data.get("data", []))
    print(f"\n{len(available)} model tersedia di akun Anda:\n")
    for m in available:
        marker = "  <-- disebut di proposal" if m in CANDIDATES else ""
        print(f"   {m}{marker}")

    print("\n--- uji panggil kandidat ---")
    results = {}
    for m in CANDIDATES:
        if m not in available:
            print(f"  [TIDAK ADA]  {m}")
            results[m] = "tidak tersedia"
            continue
        try:
            # max_tokens harus longgar: gpt-oss adalah reasoning model dan
            # menghabiskan token untuk penalaran SEBELUM mengisi `content`.
            r = request_json("/chat/completions", key, {
                "model": m,
                "messages": [{"role": "user", "content": "Jawab satu kata: halo"}],
                "max_tokens": 512,
            })
            msg = r["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            reasoning = (msg.get("reasoning") or "").strip()
            u = r.get("usage", {})
            tok = u.get("completion_tokens", 0)

            kind = "reasoning" if reasoning else "biasa"
            print(f"  [OK]         {m}")
            print(f"                 jawaban   : {content[:60]!r}")
            print(f"                 jenis     : {kind}"
                  + (f"  (token penalaran terpakai)" if reasoning else ""))
            print(f"                 token out : {tok}")
            if not content:
                print(f"                 PERINGATAN: content kosong walau max_tokens=512")
            results[m] = "aktif" if content else "aktif tapi content kosong"
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:160]
            print(f"  [GAGAL]      {m}  -> HTTP {e.code}: {body}")
            results[m] = f"gagal HTTP {e.code}"

    print("\n--- kesimpulan ---")
    try:
        from src.config import GROQ_MODEL
    except Exception:
        GROQ_MODEL = "openai/gpt-oss-120b"

    if results.get("llama3-70b-8192") == "aktif":
        print("  `llama3-70b-8192` masih hidup -- proposal boleh tetap pakai Llama 3 70B.")
    else:
        print("  `llama3-70b-8192` (model di proposal) TIDAK tersedia.")

    if results.get(GROQ_MODEL) == "aktif":
        print(f"  `{GROQ_MODEL}` AKTIF -- cocok dengan src/config.py, tidak perlu diubah.")
    else:
        active = [m for m, v in results.items() if v == "aktif"]
        print(f"  `{GROQ_MODEL}` di src/config.py TIDAK aktif.")
        print(f"  Yang aktif: {', '.join(active) if active else '(tidak ada)'}")
        print("  -> ganti GROQ_MODEL di src/config.py")

    print("  Kalau model berubah, revisi juga: proposal Bab 2.2 + Tabel 3.1")


if __name__ == "__main__":
    main()
