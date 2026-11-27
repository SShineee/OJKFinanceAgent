"""
Langkah 4-5 Minggu 13 -- pemeriksaan otomatis Market Observer Agent + uji negatif degradasi mulus
+ uji live Tavily & filter lapis-2 pada BBCA & BMRI.  docs/PANDUAN_MINGGU13.md, Langkah 4-5.

Jalankan:
  python scripts/check_market.py --offline   # 0 kuota Tavily, 0 token LLM, < 3 detik
  python scripts/check_market.py --live      # sama + uji live BBCA & BMRI -> results/check_market.json

Pemeriksaan:
  A. Domain dinamis & bebas hardcode (13.1) : `config.TAVILY_DOMAINS` bebas emiten; domain emiten
                                              digabung dinamis dari `metadata.json`; 0 kebocoran kode.
  B. Filter lapis-2 & kunci URL (13.2, 13.3): buang berita promo/duplikat, kunci URL & tanggal asli
                                              dari respons Tavily, tolak `idx` di luar batas.
  C. Tool & kontrak `market_node` (13.D)    : nama tool bahasa Inggris `search_market_news`; node
                                              berjalan independen tanpa `extracted_data`/`ratios`.
  D. Uji negatif degradasi mulus (13.4)     : (1) TAVILY_API_KEY kosong -> `[]` (`unavailable`);
                                              (2) Tavily timeout/error -> `[]` (`error`, 0 crash);
                                              (3) Tavily hasil kosong -> `[]` (`empty`);
                                              (4) LLM filter error -> fallback deterministik aman.
  E. Uji live (--live)                      : BBCA 2025 & BMRI 2025 via Tavily + LLM filter lapis-2.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config
from src.agents import market as mkt
from src.agents.state import AgentState, MarketCandidateDecision, MarketFilterOutput
from src.agents.tools import search_market_news, search_market_raw

FORBIDDEN_ISSUER_RE = re.compile(
    r"\b(bca\.co\.id|bankmandiri\.co\.id|bbca|bmri|bbri|tlkm|bank central asia|bank mandiri)\b",
    re.I,
)


def _strip_cli_examples(source: str) -> str:
    kept = []
    for line in source.splitlines():
        if "python -m src.agents." in line or 'help="kode saham, mis.' in line:
            continue
        kept.append(line)
    return "\n".join(kept)


class _FakeStructuredChain:
    def __init__(self, parsed: MarketFilterOutput | None, fail: bool = False):
        self._parsed = parsed
        self._fail = fail

    def invoke(self, _messages):
        if self._fail:
            raise RuntimeError("simulasi kegagalan LLM filter")
        return {"parsed": self._parsed, "raw": None}


class _FakeLLM:
    def __init__(self, parsed: MarketFilterOutput | None = None, fail: bool = False):
        self._parsed = parsed
        self._fail = fail

    def with_structured_output(self, *_args, **_kwargs):
        return _FakeStructuredChain(self._parsed, fail=self._fail)


def check_domains_and_leakage() -> list[str]:
    out = []
    for d in config.TAVILY_DOMAINS:
        if "bca" in d.lower() or "mandiri" in d.lower() or "bri" in d.lower() or "telkom" in d.lower():
            out.append(f"[A] config.TAVILY_DOMAINS masih mengandung hardcode emiten: {d!r}")
    for req in ("ojk.go.id", "idx.co.id", "kontan.co.id"):
        if req not in config.TAVILY_DOMAINS:
            out.append(f"[A] domain wajib {req!r} hilang dari config.TAVILY_DOMAINS")

    ctx = mkt.resolve_issuer_context("bbca", [2025], extra_domains=["contohbank.co.id"])
    if not ctx["company"] or ctx["sector"] != "bank":
        out.append(f"[A] resolve_issuer_context gagal membaca metadata: {ctx}")
    if "contohbank.co.id" not in ctx["domains"]:
        out.append("[A] extra_domains tidak tergabung dinamis")
    if len(ctx["domains"]) != len(set(ctx["domains"])):
        out.append("[A] terdapat domain duplikat")

    for rel in ("src/agents/market.py", "src/agents/tools.py"):
        text = _strip_cli_examples((ROOT / rel).read_text(encoding="utf-8"))
        hits = FORBIDDEN_ISSUER_RE.findall(text)
        if hits:
            out.append(f"[A] kebocoran nama/domain emiten di {rel}: {sorted(set(hits))}")
    return out


def check_filter_and_url_lock() -> list[str]:
    out = []
    fake_tavily_items = [
        {
            "title": "Laba Bersih Bank Tumbuh 12% pada 2025",
            "url": "https://keuangan.kontan.co.id/news/laba-bank-2025",
            "source_domain": "keuangan.kontan.co.id",
            "published_date": "2025-02-15",
            "content": "Laba bersih bank naik 12% ditopang pertumbuhan kredit dan rasio NPL terjaga di bawah 2%.",
            "score": 0.91,
        },
        {
            "title": "Promo Diskon Kartu Kredit Akhir Pekan 50%",
            "url": "https://contohbank.co.id/promo-kartu-kredit",
            "source_domain": "contohbank.co.id",
            "published_date": "2025-03-01",
            "content": "Nikmati diskon restoran 50% menggunakan kartu kredit khusus akhir pekan.",
            "score": 0.55,
        },
        {
            "title": "OJK Terbitkan Aturan Penguatan Permodalan Perbankan",
            "url": "https://www.ojk.go.id/id/regulasi/pojk-kpmm-2025",
            "source_domain": "ojk.go.id",
            "published_date": "2025-01-20",
            "content": "OJK menegaskan batas minimum KPMM 8% serta buffer permodalan bank konvensional.",
            "score": 0.87,
        },
        # Duplikat URL item 0 (harus dibuang sebelum filter)
        {
            "title": "Duplikat Laba Bersih Bank",
            "url": "https://www.keuangan.kontan.co.id/news/laba-bank-2025/",
            "source_domain": "keuangan.kontan.co.id",
            "published_date": "2025-02-15",
            "content": "Duplikat konten.",
            "score": 0.60,
        },
    ]

    def mock_search(_query, **_kwargs):
        return fake_tavily_items, None

    fake_decisions = MarketFilterOutput(decisions=[
        MarketCandidateDecision(idx=0, relevant=True, category="kinerja_emiten", sentiment="positif",
                                summary="Laba bersih bank tumbuh 12% pada 2025 dengan NPL di bawah 2%."),
        MarketCandidateDecision(idx=1, relevant=False, category="tidak_relevan", sentiment="netral",
                                summary="Promo kartu kredit ritel."),
        MarketCandidateDecision(idx=2, relevant=True, category="regulasi_ojk", sentiment="netral",
                                summary="OJK menegaskan batas minimum KPMM 8% bagi bank konvensional."),
        # Indeks liar di luar batas -> harus diabaikan aman
        MarketCandidateDecision(idx=99, relevant=True, category="kinerja_emiten", sentiment="positif",
                                summary="Kandidat palsu di luar daftar."),
    ])

    res = mkt.observe_market(
        ticker="bbca", years=2025, search_fn=mock_search, llm=_FakeLLM(fake_decisions)
    )
    items = res["market_context"]
    if res["status"] != "ok" or len(items) != 2:
        out.append(f"[B] jumlah item lolos filter seharusnya 2, dapat {len(items)} (status={res['status']})")
        return out
    if items[0]["url"] != fake_tavily_items[0]["url"] or items[0]["published_date"] != "2025-02-15":
        out.append(f"[B] URL/tanggal tidak terkunci dari Tavily asli: {items[0]}")
    if any("promo" in it["url"] for it in items):
        out.append("[B] berita promo tidak terbuang oleh filter lapis-2")
    if res["market_stats"]["raw_candidates"] != 3:
        out.append(f"[B] deduplikasi URL gagal: raw_candidates={res['market_stats']['raw_candidates']} (seharusnya 3)")
    return out


def check_tool_and_node() -> list[str]:
    out = []
    if search_market_news.name != "search_market_news":
        out.append(f"[C] nama tool harus 'search_market_news', bukan {search_market_news.name!r}")
    try:
        mkt.market_node(AgentState(year=2025))
        out.append("[C] market_node tidak menolak state tanpa ticker")
    except ValueError:
        pass
    return out


def check_negative() -> list[str]:
    out = []

    # Negatif 1: TAVILY_API_KEY kosong -> tidak crash, market_context=[] (unavailable)
    old_key = os.environ.pop("TAVILY_API_KEY", None)
    try:
        items_raw, err_raw = search_market_raw("OJK perbankan", include_domains=config.TAVILY_DOMAINS)
        res1 = mkt.observe_market("bbca", years=2025, use_llm_filter=False)
    finally:
        if old_key is not None:
            os.environ["TAVILY_API_KEY"] = old_key
    ok1 = (items_raw == []) and bool(err_raw) and (res1["market_context"] == []) and (res1["status"] == "unavailable")
    print(f"  {'OK   ' if ok1 else 'GAGAL'} negatif 1: TAVILY_API_KEY kosong -> aman (status={res1['status']}, items=0)")
    if not ok1:
        out.append(f"[D] kegagalan uji negatif 1: {res1['status']}, err={err_raw}")

    # Negatif 2: Tavily melempar TimeoutError -> tidak crash, market_context=[] (error)
    def broken_search(_q, **_kw):
        raise TimeoutError("simulasi timeout jaringan Tavily")

    res2 = mkt.observe_market("bbca", years=2025, search_fn=broken_search, use_llm_filter=False)
    ok2 = (res2["market_context"] == []) and (res2["status"] == "error") and bool(res2["market_errors"])
    print(f"  {'OK   ' if ok2 else 'GAGAL'} negatif 2: Tavily TimeoutError -> aman tanpa crash (status={res2['status']}, items=0)")
    if not ok2:
        out.append(f"[D] kegagalan uji negatif 2: {res2}")

    # Negatif 3: Tavily mengembalikan hasil kosong -> tidak crash, market_context=[] (empty)
    res3 = mkt.observe_market("bbca", years=2025, search_fn=lambda _q, **_kw: ([], None), use_llm_filter=False)
    ok3 = (res3["market_context"] == []) and (res3["status"] == "empty")
    print(f"  {'OK   ' if ok3 else 'GAGAL'} negatif 3: Tavily hasil kosong -> aman (status={res3['status']}, items=0)")
    if not ok3:
        out.append(f"[D] kegagalan uji negatif 3: {res3}")

    # Negatif 4: LLM filter gagal -> jatuh mulus ke fallback deterministik tanpa crash
    sample = [{
        "title": "Berita Kinerja Bank 2025",
        "url": "https://bisnis.com/bank-2025",
        "source_domain": "bisnis.com",
        "published_date": "2025-04-01",
        "content": "Kinerja kredit dan permodalan tetap solid sepanjang tahun.",
        "score": 0.85,
    }]
    res4 = mkt.observe_market(
        "bbca", years=2025, search_fn=lambda _q, **_kw: (sample, None), llm=_FakeLLM(fail=True)
    )
    ok4 = (
        res4["status"] == "ok"
        and len(res4["market_context"]) == 1
        and res4["market_stats"]["used_fallback_filter"] is True
        and res4["market_context"][0]["url"] == "https://bisnis.com/bank-2025"
    )
    print(f"  {'OK   ' if ok4 else 'GAGAL'} negatif 4: LLM filter gagal -> fallback deterministik menjaga URL asli")
    if not ok4:
        out.append(f"[D] kegagalan uji negatif 4: {res4}")

    return out


def check_live() -> list[str]:
    out = []
    saved: dict[str, Any] = {"timestamp": datetime.now().isoformat(timespec="seconds"), "results": {}}
    for ticker in ("bbca", "bmri"):
        res = mkt.observe_market(ticker=ticker, years=2025, use_llm_filter=True)
        saved["results"][ticker] = res
        st = res["market_stats"]
        print(
            f"  [{ticker.upper()}] status={res['status']} | domain_emiten={res['issuer_domain']} | "
            f"{st['raw_candidates']} -> {st['filtered_items']} item | "
            f"{st['llm_calls']} LLM call ({st['total_tokens']:,} tok) | {st['seconds']} s"
        )
        for i, it in enumerate(res["market_context"], 1):
            print(f"    {i}. [{it['category']}|{it['sentiment']}] {it['title'][:75]}")
            print(f"       {it['source_domain']} | {it['published_date']} | {it['url']}")
            if not it["url"].startswith("http"):
                out.append(f"[E] URL tidak valid pada {ticker}: {it['url']!r}")
        if res["status"] != "ok" or not res["market_context"]:
            out.append(f"[E] uji live {ticker} gagal mengembalikan konteks pasar: status={res['status']} err={res['market_errors']}")

    out_path = config.RESULTS / "check_market.json"
    out_path.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Disimpan: {out_path.relative_to(ROOT)}")
    return out


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Pemeriksaan Market Observer Agent (Minggu 13).")
    ap.add_argument("--offline", action="store_true", help="hanya cek deterministik + uji negatif (0 kuota Tavily)")
    ap.add_argument("--live", action="store_true", help="ikut jalankan uji live Tavily + LLM filter BBCA & BMRI")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()

    failures = []
    checks = [
        ("A. Domain dinamis & audit bebas hardcode emiten (13.1)", check_domains_and_leakage),
        ("B. Filter lapis-2, deduplikasi, & kunci URL/tanggal Tavily (13.2, 13.3)", check_filter_and_url_lock),
        ("C. Tool search_market_news & kontrak market_node (13.D)", check_tool_and_node),
    ]
    print("== Pemeriksaan offline Market Observer Agent ==")
    for name, fn in checks:
        probs = fn()
        print(f"  {'OK   ' if not probs else 'GAGAL'} {name}" + (f": {len(probs)} masalah" if probs else ""))
        for p in probs[:5]:
            print(f"         {p}")
        failures += probs

    print("\n== D. Uji negatif — degradasi mulus (13.4, HARUS aman tanpa crash) ==")
    failures += check_negative()

    if args.live and not args.offline:
        print("\n== E. Uji live Tavily + Filter Lapis-2 (BBCA 2025 & BMRI 2025) ==")
        failures += check_live()

    print(f"\nSelesai dalam {time.perf_counter() - t0:.2f} s")
    print("HASIL:", "LULUS" if not failures else f"GAGAL ({len(failures)} masalah)")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
