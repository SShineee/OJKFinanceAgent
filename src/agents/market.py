"""
Langkah 3 Minggu 13 (tugas 13.1-13.4, Keputusan 13.A-13.D) -- Market Observer Agent generik
berbasis Tavily Search (`include_domains` dinamis dari metadata dokumen) + filter relevansi
lapis-2 menggunakan LLM structured output (`method="json_schema"`) + penguncian URL/tanggal Python.
docs/PANDUAN_MINGGU13.md, Langkah 3.

ATURAN DISIPLIN LINTAS EMITEN (R10 & 13.1):
  File ini 100% generik -- TIDAK mem-hardcode nama perusahaan maupun domain emiten tertentu.
  `company`, `sector`, dan `domain` resmi emiten dibaca dinamis dari `metadata.json`.

Siap paralel (Keputusan 13.D):
  `market_node(state)` hanya membaca `ticker`, `sector`, dan `year` -- TIDAK bergantung pada
  `extracted_data` atau `ratios`, sehingga dapat berjalan paralel di LangGraph Minggu 15.

CLI smoke test:
  python -m src.agents.market --ticker bbca --year 2025
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src import config
from src.agents.state import AgentState, MarketFilterOutput, MarketNewsItem
from src.agents.tools import search_market_news, search_market_raw

MARKET_FILTER_SYSTEM_PROMPT = """Kamu adalah analis pasar modal Indonesia yang menyaring artikel berita hasil pencarian web.
Tugasmu menilai relevansi setiap kandidat artikel (berdasarkan indeks 0..N-1) untuk analisis laporan keuangan emiten target.

ATURAN WAJIB:
1. KELUARKAN satu keputusan pada `decisions` untuk setiap kandidat yang diberikan (sesuai `idx` aslinya).
2. Tandai `relevant=True` HANYA jika artikel membahas salah satu dari:
   - `kinerja_emiten`: kinerja keuangan, laba, kredit/pendapatan, dividen, RUPS, aksi korporasi, atau keterbukaan informasi emiten target;
   - `regulasi_ojk`: kebijakan atau aturan OJK / Bank Indonesia / BEI yang berdampak pada emiten atau sektornya;
   - `makro_sektor`: tren industri, suku bunga acuan, likuiditas, atau sentimen makro sektor emiten.
3. Tandai `relevant=False` (`category="tidak_relevan"`) untuk:
   - halaman produk ritel (promo kartu kredit, KPR, tabungan, diskon, undian, cara buka rekening);
   - lowongan kerja, berita olahraga/gaya hidup, atau berita tentang emiten lain yang tidak relevan.
4. Untuk setiap artikel, tulis `summary` singkat (1-2 kalimat bahasa Indonesia) HANYA berdasarkan fakta pada cuplikan teks yang diberikan — DILARANG mengarang angka atau fakta baru."""


def _normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path.rstrip("/")
    return f"{host}{path}"


def resolve_issuer_context(
    ticker: str,
    years: Sequence[int] | None = None,
    *,
    sector: str | None = None,
    company: str | None = None,
    extra_domains: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Baca `company`, `sector`, dan `domain` resmi emiten secara dinamis dari metadata.json (13.1)."""
    code = ticker.strip().lower()
    if not code:
        raise ValueError("ticker wajib diisi untuk Market Observer Agent")

    candidate_years = sorted({int(y) for y in years}, reverse=True) if years else sorted(config.YEARS, reverse=True)
    meta: dict[str, Any] = {}
    for y in candidate_years:
        p = config.report_metadata(y, code)
        if p.exists():
            meta = json.loads(p.read_text(encoding="utf-8"))
            break
    if not meta:
        # Coba cari file metadata terbaru yang tersedia untuk ticker ini di data/markdown/
        matches = sorted(config.DATA_MARKDOWN.glob(f"{code}_*.metadata.json"), reverse=True)
        if matches:
            meta = json.loads(matches[0].read_text(encoding="utf-8"))

    resolved_company = (company or meta.get("company") or code.upper()).strip()
    resolved_sector = (sector or meta.get("sector") or "general").strip().lower()
    issuer_domain = (meta.get("domain") or "").strip().lower() or None

    domains: list[str] = []
    seen: set[str] = set()
    for d in [*config.TAVILY_DOMAINS, *([issuer_domain] if issuer_domain else []), *(extra_domains or [])]:
        clean = d.strip().lower()
        if clean.startswith("www."):
            clean = clean[4:]
        if clean and clean not in seen:
            seen.add(clean)
            domains.append(clean)

    target_year = max(candidate_years) if candidate_years else max(config.YEARS)
    return {
        "ticker": code,
        "company": resolved_company,
        "sector": resolved_sector,
        "issuer_domain": issuer_domain,
        "domains": domains,
        "target_year": target_year,
    }


def build_market_queries(company: str, ticker: str, sector: str, target_year: int) -> list[tuple[str, str, int]]:
    """Bangun 2 query pencarian generik (4 berita kinerja emiten + 3 regulasi/sektor) -- hemat kredit Tavily."""
    short_name = re.sub(r"\([^)]*\)", "", company).replace("PT ", "").replace(" Tbk", "").strip()
    short_name = re.sub(r"\s+", " ", short_name)
    code_up = ticker.upper()
    if sector == "bank":
        return [
            (f"{short_name} {code_up} kinerja keuangan laba kredit {target_year}", "general", 4),
            (f"OJK Bank Indonesia kebijakan perbankan NPL LDR suku bunga {target_year}", "general", 3),
        ]
    return [
        (f"{short_name} {code_up} kinerja keuangan pendapatan laba {target_year}", "general", 4),
        (f"BEI OJK prospek industri sektor emiten {code_up} {target_year}", "general", 3),
    ]


def _deterministic_fallback(candidates: Sequence[dict[str, Any]], max_items: int) -> list[MarketNewsItem]:
    """Fallback deterministik saat LLM filter tidak tersedia: pilih skor Tavily tertinggi (13.4)."""
    ranked = sorted(candidates, key=lambda c: float(c.get("score") or 0.0), reverse=True)
    items: list[MarketNewsItem] = []
    for c in ranked:
        score = c.get("score")
        if score is not None and float(score) < 0.35 and len(items) > 0:
            continue
        snippet = (c.get("content") or "").strip()
        summary = snippet[:220] + ("..." if len(snippet) > 220 else "")
        items.append(
            MarketNewsItem(
                title=c["title"],
                url=c["url"],
                source_domain=c["source_domain"],
                published_date=c["published_date"],
                category="kinerja_emiten",
                sentiment="netral",
                summary=summary or c["title"],
                relevance_score=score,
            )
        )
        if len(items) >= min(3, max_items):
            break
    return items


def filter_market_candidates(
    candidates: Sequence[dict[str, Any]],
    company: str,
    ticker: str,
    sector: str,
    stats: dict[str, Any],
    *,
    llm=None,
    max_items: int = config.MARKET_MAX_ITEMS,
) -> list[MarketNewsItem]:
    """Filter relevansi lapis-2 berbasis LLM structured output + penguncian URL/tanggal Python (13.2, 13.3)."""
    if not candidates:
        return []

    lines = [
        f"EMITEN TARGET: {company} ({ticker.upper()}) | SEKTOR: {sector}",
        "",
        "DAFTAR KANDIDAT ARTIKEL:",
    ]
    for i, c in enumerate(candidates):
        snippet = (c.get("content") or "").replace("\n", " ")[:400]
        lines.append(
            f"[{i}] Judul: {c['title']}\n"
            f"    Sumber: {c['source_domain']} | Tanggal: {c['published_date']}\n"
            f"    Cuplikan: {snippet}"
        )

    active_llm = llm or config.get_llm(effort=config.REASONING_EFFORT_EXTRACTION)
    messages = [SystemMessage(MARKET_FILTER_SYSTEM_PROMPT), HumanMessage("\n".join(lines))]

    parsed: MarketFilterOutput | None = None
    for method in ("json_schema", "json_mode"):
        try:
            stats["llm_calls"] += 1
            chain = active_llm.with_structured_output(MarketFilterOutput, method=method, include_raw=True)
            msgs = messages
            if method == "json_mode":
                hint = json.dumps(MarketFilterOutput.model_json_schema(), ensure_ascii=False)
                msgs = [
                    SystemMessage(MARKET_FILTER_SYSTEM_PROMPT + f"\nKeluarkan HANYA JSON valid sesuai skema:\n{hint}"),
                    messages[1],
                ]
            res = chain.invoke(msgs)
            raw_msg = res.get("raw") if isinstance(res, dict) else None
            usage = getattr(raw_msg, "usage_metadata", None) or {}
            stats["input_tokens"] += int(usage.get("input_tokens", 0))
            stats["output_tokens"] += int(usage.get("output_tokens", 0))
            stats["total_tokens"] += int(usage.get("total_tokens", 0))
            parsed = res.get("parsed") if isinstance(res, dict) else res
            if parsed is not None:
                break
        except Exception as e:
            stats["filter_errors"].append(f"LLM filter ({method}) gagal: {e}")
            if "connection" in str(e).lower():
                break

    if parsed is None:
        stats["used_fallback_filter"] = True
        return _deterministic_fallback(candidates, max_items)

    # Pagar 13.3: kunci URL, judul, domain, & tanggal dari `candidates[idx]` (bukan teks LLM)
    kept: list[MarketNewsItem] = []
    seen_urls: set[str] = set()
    for dec in parsed.decisions:
        if not dec.relevant or dec.category == "tidak_relevan":
            continue
        if not (0 <= dec.idx < len(candidates)):
            continue
        src = candidates[dec.idx]
        norm_url = _normalize_url(src["url"])
        if norm_url in seen_urls:
            continue
        seen_urls.add(norm_url)
        kept.append(
            MarketNewsItem(
                title=src["title"],
                url=src["url"],
                source_domain=src["source_domain"],
                published_date=src["published_date"],
                category=dec.category,
                sentiment=dec.sentiment,
                summary=dec.summary.strip() or src["title"],
                relevance_score=src.get("score"),
            )
        )
        if len(kept) >= max_items:
            break
    return kept


def observe_market(
    ticker: str,
    years: int | Sequence[int] | None = None,
    *,
    sector: str | None = None,
    company: str | None = None,
    extra_domains: Sequence[str] | None = None,
    use_llm_filter: bool = True,
    llm=None,
    search_fn: Callable[..., tuple[list[dict[str, Any]], str | None]] | None = None,
) -> dict[str, Any]:
    """Ambil & saring konteks pasar eksternal secara tangguh (degradasi mulus -> [] bila gagal, 13.4)."""
    t0 = time.perf_counter()
    year_list = [years] if isinstance(years, int) and not isinstance(years, bool) else (list(years) if years else None)
    ctx = resolve_issuer_context(
        ticker, year_list, sector=sector, company=company, extra_domains=extra_domains
    )
    queries = build_market_queries(ctx["company"], ctx["ticker"], ctx["sector"], ctx["target_year"])
    runner = search_fn or search_market_raw

    stats: dict[str, Any] = {
        "search_calls": 0,
        "raw_candidates": 0,
        "filtered_items": 0,
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "used_fallback_filter": False,
        "filter_errors": [],
        "seconds": 0.0,
    }
    errors: list[str] = []
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    unavailable = False

    for q_text, topic, q_limit in queries:
        stats["search_calls"] += 1
        try:
            items, err = runner(
                q_text,
                include_domains=ctx["domains"],
                max_results=q_limit,
                topic=topic,
            )
        except Exception as e:
            items, err = [], f"pengecualian pencarian pasar: {e}"

        if err:
            errors.append(err)
            if "belum dikonfigurasi" in err.lower():
                unavailable = True
                break
            continue

        for it in items:
            url = str(it.get("url") or "").strip()
            if not url:
                continue
            norm_u = _normalize_url(url)
            if norm_u in seen_urls:
                continue
            seen_urls.add(norm_u)
            candidates.append(it)

    stats["raw_candidates"] = len(candidates)

    if unavailable:
        status = "unavailable"
        filtered: list[MarketNewsItem] = []
    elif not candidates and errors:
        status = "error"
        filtered = []
    elif not candidates:
        status = "empty"
        filtered = []
    else:
        if use_llm_filter:
            filtered = filter_market_candidates(
                candidates, ctx["company"], ctx["ticker"], ctx["sector"], stats, llm=llm
            )
        else:
            filtered = _deterministic_fallback(candidates, config.MARKET_MAX_ITEMS)
        status = "ok" if filtered else "empty"

    stats["filtered_items"] = len(filtered)
    stats["seconds"] = round(time.perf_counter() - t0, 2)
    return {
        "ticker": ctx["ticker"],
        "company": ctx["company"],
        "sector": ctx["sector"],
        "target_year": ctx["target_year"],
        "status": status,
        "domains_used": ctx["domains"],
        "issuer_domain": ctx["issuer_domain"],
        "queries": [q for q, _, _ in queries],
        "market_context": [m.model_dump() for m in filtered],
        "market_errors": errors + stats["filter_errors"],
        "market_stats": stats,
    }


def market_node(state: AgentState) -> dict[str, Any]:
    """Node LangGraph untuk Market Observer Agent (independen, siap paralel di Minggu 15)."""
    ticker = state.get("ticker", "")
    if not ticker:
        raise ValueError("AgentState['ticker'] wajib diisi sebelum menjalankan market_node")

    res = observe_market(
        ticker=ticker,
        years=state.get("year"),
        sector=state.get("sector"),
    )
    st = res["market_stats"]
    summary = (
        f"Observasi pasar selesai untuk {res['ticker'].upper()} (status={res['status']}): "
        f"{st['filtered_items']} berita relevan dari {st['raw_candidates']} kandidat "
        f"({len(res['domains_used'])} domain, {st['seconds']} s; tool={search_market_news.name})."
    )
    return {
        "market_context": res["market_context"],
        "market_errors": res["market_errors"],
        "market_stats": st,
        "messages": [AIMessage(content=summary)],
    }


def main(argv: list[str] | None = None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Smoke test Market Observer Agent (Minggu 13).")
    ap.add_argument("--ticker", required=True, help="kode saham, mis. bbca")
    ap.add_argument("--year", type=int, default=2025, help="tahun acuan pencarian")
    ap.add_argument("--no-llm-filter", action="store_true", help="pakai filter skor Tavily tanpa LLM")
    args = ap.parse_args(argv)

    res = observe_market(ticker=args.ticker, years=args.year, use_llm_filter=not args.no_llm_filter)
    print(f"Emiten : {res['company']} ({res['ticker'].upper()}) | sektor: {res['sector']} | status: {res['status']}")
    print(f"Domain : {', '.join(res['domains_used'])}")
    if res["market_errors"]:
        print(f"Catatan: {res['market_errors']}")
    for i, it in enumerate(res["market_context"], 1):
        print(f"\n  [{i}] [{it['category']} | {it['sentiment']}] {it['title']}")
        print(f"      {it['source_domain']} | {it['published_date']} | {it['url']}")
        print(f"      {it['summary']}")
    st = res["market_stats"]
    print(f"\nStatistik: {st['search_calls']} query Tavily, {st['raw_candidates']} -> {st['filtered_items']} item, "
          f"{st['llm_calls']} LLM call ({st['total_tokens']:,} token), {st['seconds']} s")


if __name__ == "__main__":
    main()
