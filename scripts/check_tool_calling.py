"""
Tugas 2.5b -- uji tool calling model sistem (gpt-oss-120b).

Jalankan (di dalam venv):  python scripts/check_tool_calling.py
                           python scripts/check_tool_calling.py 3   (jumlah percobaan)

Kenapa perlu: seluruh arsitektur multi-agent bergantung pada kemampuan model
memanggil tool dengan benar. Kalau goyah di sini, LangGraph akan bermasalah
terus dan penyebabnya susah dilacak. Lebih murah ketahuan di Minggu 2.

Skenario: model diberi 3 tool, lalu diminta menghitung ROE BCA 2024.
  - search_report -> HARUS dipanggil
  - calculator    -> HARUS dipanggil
  - search_news   -> TIDAK boleh dipanggil (pengecoh)

ATURAN DESAIN (temuan 26-10-2026): NAMA TOOL HARUS BAHASA INGGRIS.
Dengan nama `hitung`, gpt-oss-120b memanggil `hitungan` -- tool yang tidak ada --
pada 5 dari 5 percobaan (15 dari 15 termasuk retry; retry tidak menolong karena
temperature=0). Dengan `calculator`/`kalkulator`: 4/4 lulus tanpa retry.
Deskripsi tool boleh tetap bahasa Indonesia; yang harus Inggris hanya NAMA-nya.
Angkanya asli dari ground_truth.xlsx, disajikan dalam format Indonesia
("239.468,855") dan -- seperti laporan asli -- tiap laporan memuat angka tahun
sebelumnya sebagai pembanding.

Jawaban benar: 54.851 / ((217.686,126 + 239.468,855) / 2) x 100 = 23,9967%

Lulus kalau sukses >= 2/3 dari jumlah percobaan (LLM non-deterministik).

Dua hal dicatat TERPISAH karena bukan soal mekanisme tool calling, tapi
penting untuk Extraction Agent (Minggu 9) dan orkestrasi (Minggu 15):
  - halusinasi nama tool: Groq menolak dengan error 400 `tool_use_failed`.
    Di sini di-retry (maks 2x) seperti yang nanti dilakukan sistem sungguhan,
    lalu jumlah retry-nya dilaporkan.
  - salah baca format angka Indonesia: "239.468,855" dibaca 239.468855.
"""

import ast
import operator
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Jawaban gpt-oss memuat karakter Unicode (spasi sempit U+202F, tanda ≈, dll).
# Console Windows default (cp1252) tidak bisa mencetaknya -> UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

from src.config import GROQ_MODEL, REASONING_EFFORT, get_llm  # noqa: E402

ATTEMPTS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MAX_STEPS = 12
MAX_TOOL_NAME_RETRIES = 2
EXPECTED_ANSWER = 54_851 / ((217_686.126 + 239_468.855) / 2) * 100   # 23,9967
TOLERANCE = 0.05
TRUE_VALUES = (54_851, 217_686.126, 239_468.855)                      # untuk cek skala

# Realistis: laporan tahunan selalu memuat angka tahun SEBELUMNYA sebagai pembanding
# (tabel KPMM BCA 2024 berisi kolom 2024 dan 2023).
DOCUMENTS = {
    ("bca", 2024): "Laporan Tahunan BCA 2024. Laba bersih tahun 2024 sebesar Rp 54.851 miliar "
                   "(2023: Rp 48.658 miliar). Modal Inti (Tier 1) basis Bank per 31 Desember 2024 "
                   "sebesar Rp 239.468,855 miliar (31 Desember 2023: Rp 217.686,126 miliar).",
    ("bca", 2023): "Laporan Tahunan BCA 2023. Laba bersih tahun 2023 sebesar Rp 48.658 miliar "
                   "(2022: Rp 40.756 miliar). Modal Inti (Tier 1) basis Bank per 31 Desember 2023 "
                   "sebesar Rp 217.686,126 miliar (31 Desember 2022: Rp 196.799,387 miliar).",
}

TASK = (
    "Berapa ROE BCA tahun 2024? Definisi ROE di sini: laba bersih 2024 dibagi rata-rata "
    "Modal Inti (Tier 1) basis Bank pada akhir tahun 2023 dan akhir tahun 2024, dikali 100. "
    "Ambil angkanya dari dokumen, lalu hitung dengan alat calculator. "
    "Jawab dengan persentase dua desimal."
)

_call_log: list = []


@tool
def search_report(query: str, bank: str, year: int) -> str:
    """Cari potongan teks dari laporan tahunan sebuah bank.

    Args:
        query: apa yang dicari, mis. 'laba bersih' atau 'modal inti tier 1'.
        bank: kode bank huruf kecil, mis. 'bca'.
        year: tahun buku laporan, mis. 2024.
    """
    _call_log.append(("search_report", {"query": query, "bank": bank, "year": year}))
    return DOCUMENTS.get((str(bank).lower().strip(), int(year)), "Tidak ditemukan.")


_OP = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OP:
        return _OP[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OP:
        return _OP[type(node.op)](_eval(node.operand))
    raise ValueError("hanya angka dan + - * / ( ) yang diizinkan")


@tool
def calculator(expression: str) -> str:
    """Hitung ekspresi aritmatika.

    Pakai titik sebagai pemisah desimal dan JANGAN pakai pemisah ribuan.
    Contoh: '(10 + 20) / 2 * 100'.
    """
    _call_log.append(("calculator", {"expression": expression}))
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"ERROR: {e}"


@tool
def search_news(query: str) -> str:
    """Cari berita terbaru di internet tentang bank atau kondisi ekonomi."""
    _call_log.append(("search_news", {"query": query}))
    return "Tidak ada berita relevan."


TOOLS = {t.name: t for t in (search_report, calculator, search_news)}


def numbers_in(text: str) -> list:
    results = []
    for m in re.findall(r"\d+(?:[.,]\d+)?", text or ""):
        try:
            results.append(float(m.replace(",", ".")))
        except ValueError:
            pass
    return results


def invoke_with_retry(llm, messages):
    """invoke + retry kalau model memanggil tool yang tidak ada (error 400 Groq)."""
    for attempt in range(MAX_TOOL_NAME_RETRIES + 1):
        try:
            return llm.invoke(messages), attempt
        except Exception as e:
            if "tool_use_failed" in str(e) and attempt < MAX_TOOL_NAME_RETRIES:
                continue
            raise


def run_attempt() -> dict:
    _call_log.clear()
    llm = get_llm().bind_tools(list(TOOLS.values()))
    messages = [
        SystemMessage("Kamu analis keuangan bank. Gunakan alat yang tersedia. "
                      "Jangan pernah menebak angka -- selalu ambil dari dokumen."),
        HumanMessage(TASK),
    ]
    token, retry, start, ai = 0, 0, time.perf_counter(), None
    for _ in range(MAX_STEPS):                       # pagar supaya tidak loop tanpa akhir
        ai, r = invoke_with_retry(llm, messages)
        retry += r
        token += (getattr(ai, "usage_metadata", None) or {}).get("total_tokens", 0)
        messages.append(ai)
        if not ai.tool_calls:
            break
        for tc in ai.tool_calls:
            results = TOOLS[tc["name"]].invoke(tc["args"]) if tc["name"] in TOOLS else "alat tidak dikenal"
            messages.append(ToolMessage(content=str(results), tool_call_id=tc["id"]))
    seconds = time.perf_counter() - start

    answer = (ai.content if ai else "") or ""
    checks = {
        "memanggil tool": bool(_call_log),
        "mengambil angka dari dokumen": any(
            n == "search_report" and str(a["bank"]).lower().strip() == "bca"
            and int(a["year"]) in (2023, 2024) for n, a in _call_log),
        "memakai calculator": any(n == "calculator" for n, _ in _call_log),
        "tidak memakai pengecoh": not any(n == "search_news" for n, _ in _call_log),
        "jawaban ~23,99%": any(abs(x - EXPECTED_ANSWER) <= TOLERANCE for x in numbers_in(answer)),
    }
    expression = " ".join(a["expression"] for n, a in _call_log if n == "calculator")
    scale_ok = None
    if expression:
        scale_ok = any(abs(x - v) / v < 0.005 for x in numbers_in(expression) for v in TRUE_VALUES)
    return {"checks": checks, "trace": list(_call_log), "answer": answer.strip(),
            "seconds": seconds, "token": token, "retry": retry, "scale_ok": scale_ok,
            "passed": all(checks.values())}


def main():
    print(f"Model           : {GROQ_MODEL}   (reasoning_effort={REASONING_EFFORT})")
    print(f"Jawaban benar   : {EXPECTED_ANSWER:.4f}%")
    print(f"Percobaan       : {ATTEMPTS}\n")

    results = []
    for i in range(1, ATTEMPTS + 1):
        print(f"--- percobaan {i} " + "-" * 50)
        try:
            h = run_attempt()
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {str(e)[:220]}\n")
            results.append({"passed": False, "error": True})
            continue
        for name, args in h["trace"]:
            print(f"  -> {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
        print(f"  jawaban : {h['answer'][:160]!r}")
        for name, ok in h["checks"].items():
            print(f"  [{'OK' if ok else 'GAGAL'}] {name}")
        scale_label = {True: "benar", False: "SALAH -- format Indonesia salah dibaca", None: "-"}[h["scale_ok"]]
        print(f"  (obs) skala angka di calculator: {scale_label}")
        print(f"  (obs) retry nama tool       : {h['retry']}x")
        print(f"  waktu {h['seconds']:.1f} s | token {h['token']:,}")
        print()
        results.append(h)

    passed = sum(1 for h in results if h.get("passed"))
    threshold = -(-ATTEMPTS * 2 // 3)                     # 2/3, dibulatkan ke atas
    ok = [h for h in results if not h.get("error")]
    print("=" * 66)
    print(f"  LULUS {passed}/{ATTEMPTS} (ambang {threshold})  ->  " +
          ("tool calling LAYAK dipakai" if passed >= threshold
           else "BERMASALAH -- jangan lanjut ke Minggu 3 sebelum dipahami"))
    if ok:
        with_calc = [h for h in ok if h["scale_ok"] is not None]
        print(f"  rata-rata   : {sum(h['seconds'] for h in ok) / len(ok):.1f} s, "
              f"{sum(h['token'] for h in ok) / len(ok):,.0f} token per tugas")
        print(f"  temuan      : retry nama tool {sum(h['retry'] for h in ok)}x total; "
              f"skala angka salah di {sum(1 for h in with_calc if h['scale_ok'] is False)}"
              f"/{len(with_calc)} percobaan")
    print("=" * 66)
    sys.exit(0 if passed >= threshold else 1)


if __name__ == "__main__":
    main()
