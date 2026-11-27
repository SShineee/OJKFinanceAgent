"""
Langkah 3 Minggu 14 -- pemeriksaan otomatis & uji negatif Reporting Agent (tugas 14.1-14.3).
docs/PANDUAN_MINGGU14.md, Langkah 3.

Jalankan:
  python scripts/check_reporting.py --offline    # cepat (< 1 s), 0 token LLM, + 5 uji negatif
  python scripts/check_reporting.py --live       # offline + laporan penuh live BBCA & BMRI (2 LLM call)
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config
from src.agents import reporting as rep
from src.agents.analyst import analyze_ratios
from src.agents.state import AgentState, ReportNarrative


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _sample_bank_extracted() -> dict[int, dict[str, Any]]:
    """Data uji sintetis 2 tahun (+ pembanding t-1) dengan nomor halaman terverifikasi."""
    return {
        2023: {
            "total_assets": {"status": "ok", "value_million_idr": 1_000_000_000.0, "basis": "consolidated", "source_pages": [12]},
            "total_assets_bank": {"status": "ok", "value_million_idr": 950_000_000.0, "basis": "bank_only", "source_pages": [410]},
            "tier1_capital_bank": {"status": "ok", "value_million_idr": 200_000_000.0, "basis": "bank_only", "source_pages": [510]},
            "earning_assets_bank": {"status": "ok", "value_million_idr": 820_000_000.0, "basis": "bank_only", "source_pages": [411]},
        },
        2024: {
            "total_assets": {"status": "ok", "value_million_idr": 1_100_000_000.0, "basis": "consolidated", "source_pages": [14]},
            "total_assets_bank": {"status": "ok", "value_million_idr": 1_040_000_000.0, "basis": "bank_only", "source_pages": [420]},
            "net_interest_income": {"status": "ok", "value_million_idr": 55_000_000.0, "basis": "consolidated", "source_pages": [15]},
            "net_interest_income_bank": {"status": "ok", "value_million_idr": 50_000_000.0, "basis": "bank_only", "source_pages": [422]},
            "net_income": {"status": "ok", "value_million_idr": 38_000_000.0, "basis": "consolidated", "source_pages": [15]},
            "profit_before_tax_bank": {"status": "ok", "value_million_idr": 46_000_000.0, "basis": "bank_only", "source_pages": [422]},
            "net_income_bank": {"status": "ok", "value_million_idr": 36_000_000.0, "basis": "bank_only", "source_pages": [422]},
            "tier1_capital_bank": {"status": "ok", "value_million_idr": 220_000_000.0, "basis": "bank_only", "source_pages": [520]},
            "total_capital_bank": {"status": "ok", "value_million_idr": 230_000_000.0, "basis": "bank_only", "source_pages": [520]},
            "rwa_bank": {"status": "ok", "value_million_idr": 900_000_000.0, "basis": "bank_only", "source_pages": [520]},
            "gross_loans_bank": {"status": "ok", "value_million_idr": 700_000_000.0, "basis": "bank_only", "source_pages": [420]},
            "deposits_bank": {"status": "ok", "value_million_idr": 860_000_000.0, "basis": "bank_only", "source_pages": [421]},
            "npl_amount_bank": {"status": "ok", "value_million_idr": 12_600_000.0, "basis": "bank_only", "source_pages": [518]},
            "earning_assets_bank": {"status": "ok", "value_million_idr": 880_000_000.0, "basis": "bank_only", "source_pages": [421]},
        },
        2025: {
            "total_assets": {"status": "ok", "value_million_idr": 1_210_000_000.0, "basis": "consolidated", "source_pages": [16]},
            "total_assets_bank": {"status": "ok", "value_million_idr": 1_140_000_000.0, "basis": "bank_only", "source_pages": [430]},
            "net_interest_income": {"status": "ok", "value_million_idr": 60_500_000.0, "basis": "consolidated", "source_pages": [17]},
            "net_interest_income_bank": {"status": "ok", "value_million_idr": 55_000_000.0, "basis": "bank_only", "source_pages": [432]},
            "net_income": {"status": "ok", "value_million_idr": 42_000_000.0, "basis": "consolidated", "source_pages": [17]},
            "profit_before_tax_bank": {"status": "ok", "value_million_idr": 51_000_000.0, "basis": "bank_only", "source_pages": [432]},
            "net_income_bank": {"status": "ok", "value_million_idr": 40_000_000.0, "basis": "bank_only", "source_pages": [432]},
            "tier1_capital_bank": {"status": "ok", "value_million_idr": 240_000_000.0, "basis": "bank_only", "source_pages": [530]},
            "total_capital_bank": {"status": "ok", "value_million_idr": 252_000_000.0, "basis": "bank_only", "source_pages": [530]},
            "rwa_bank": {"status": "ok", "value_million_idr": 960_000_000.0, "basis": "bank_only", "source_pages": [530]},
            "gross_loans_bank": {"status": "ok", "value_million_idr": 770_000_000.0, "basis": "bank_only", "source_pages": [430]},
            "deposits_bank": {"status": "ok", "value_million_idr": 930_000_000.0, "basis": "bank_only", "source_pages": [431]},
            "npl_amount_bank": {"status": "ok", "value_million_idr": 13_090_000.0, "basis": "bank_only", "source_pages": [528]},
            "earning_assets_bank": {"status": "not_found", "value_million_idr": None, "basis": "bank_only", "source_pages": []},
        },
    }


def _sample_market() -> list[dict[str, Any]]:
    return [
        {
            "title": "Kinerja Kredit Perbankan Tumbuh Sehat 2025",
            "url": "https://www.kontan.co.id/news/kinerja-kredit-perbankan-2025",
            "source_domain": "kontan.co.id",
            "published_date": "2025-11-10",
            "category": "kinerja_emiten",
            "sentiment": "positif",
            "summary": "Pertumbuhan kredit tetap terjaga di atas rata-rata industri dengan kualitas aset solid.",
            "relevance_score": 0.85,
        },
        {
            "title": "Laporan Surveillance Perbankan Indonesia OJK",
            "url": "https://www.ojk.go.id/id/kanal/perbankan/surveillance-2025.pdf",
            "source_domain": "ojk.go.id",
            "published_date": "tanggal tidak tersedia",
            "category": "regulasi_ojk",
            "sentiment": "netral",
            "summary": "OJK menekankan ketahanan permodalan dan pengelolaan likuiditas perbankan nasional.",
            "relevance_score": 0.78,
        },
    ]


class _FakeStructuredLLM:
    """Mock LLM untuk menguji sanitasi URL & fallback tanpa panggilan API."""

    def __init__(self, narrative: ReportNarrative | None = None, fail: bool = False):
        self.narrative = narrative
        self.fail = fail

    def with_structured_output(self, schema, method="json_schema", include_raw=True):
        parent = self

        class _Chain:
            def invoke(self, msgs):
                if parent.fail:
                    raise RuntimeError("Simulated LLM timeout")
                return {"raw": None, "parsed": parent.narrative}

        return _Chain()


def _check_markdown_tables_valid(md: str) -> None:
    """Pastikan semua tabel Markdown memiliki baris pemisah valid & kolom konsisten."""
    lines = md.splitlines()
    i = 0
    table_count = 0
    while i < len(lines):
        if lines[i].startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            table_count += 1
            ncols = lines[i].count("|") - 1
            j = i + 1
            while j < len(lines) and lines[j].startswith("|"):
                # Hitung kolom sambil mengabaikan pipe ter-escape \|
                clean = lines[j].replace("\\|", "")
                _assert(clean.count("|") - 1 == ncols, f"Jumlah kolom tabel tidak konsisten di baris: {lines[j]}")
                j += 1
            i = j
        else:
            i += 1
    _assert(table_count >= 3, f"Minimal 3 tabel Markdown (rasio, metrik, tren), ditemukan {table_count}")


def check_a_structure_and_markdown() -> dict[str, Any]:
    ext = _sample_bank_extracted()
    ratios = analyze_ratios(ext, sector="bank", years=[2024, 2025], ticker="demo", use_llm_summary=False)
    res = rep.generate_report(
        ticker="demo",
        sector="bank",
        company="PT Bank Contoh Tbk",
        query="Bagaimana kinerja CAR, ROA, dan tren rasio 2024-2025?",
        years=[2024, 2025],
        extracted_data=ext,
        ratios=ratios,
        market_context=_sample_market(),
        use_llm=False,
    )
    md = res["report"]
    aud = res["report_audit"]
    _assert(aud["passed"], f"Audit laporan gagal: {aud}")
    _assert(aud["all_sections_present"], f"5 bagian wajib tidak lengkap: {aud['sections_present']}")

    # Verifikasi urutan 5 bagian persis sesuai 14.1
    positions = [md.index(h) for h in rep.REQUIRED_SECTION_HEADINGS]
    _assert(positions == sorted(positions), f"Urutan 5 bagian tidak berurutan: {positions}")
    _check_markdown_tables_valid(md)
    return res


def check_b_citations_and_urls(res: dict[str, Any]) -> None:
    md = res["report"]
    aud = res["report_audit"]
    _assert(aud["page_citation_count"] >= 10, f"Sitasi halaman terlalu sedikit: {aud['page_citation_count']}")
    _assert("hal. 520" in md and "hal. 530" in md, "Sitasi halaman KPMM tidak muncul di laporan")
    _assert(aud["verified_url_count"] == 2, f"Harusnya 2 URL terverifikasi, dapat {aud['verified_url_count']}")
    _assert("2025-11-10" in md, "Tanggal publikasi asli Tavily tidak muncul")
    _assert("tanggal tidak tersedia" in md, "Fallback tanggal jujur tidak muncul")
    _assert(len(aud["unauthorized_urls_remaining"]) == 0, f"Ada URL tak terverifikasi: {aud['unauthorized_urls_remaining']}")
    tril = rep.format_idr_for_llm(1_408_107_000.0)
    _assert("1.408,11 triliun" in tril, f"Konversi setara triliun oleh Python salah: {tril}")


def check_c_nonbank_and_no_leakage() -> None:
    # Profil non-bank (R17)
    ext_nb = {
        2024: {
            "net_income": {"status": "ok", "value_million_idr": 15_000_000.0, "basis": "consolidated", "source_pages": [55]},
            "total_assets": {"status": "ok", "value_million_idr": 200_000_000.0, "basis": "consolidated", "source_pages": [54]},
            "total_equity": {"status": "ok", "value_million_idr": 100_000_000.0, "basis": "consolidated", "source_pages": [54]},
        }
    }
    ratios_nb = analyze_ratios(ext_nb, sector="non_financial", years=[2024], ticker="nonbk", allow_ending_fallback=True)
    res_nb = rep.generate_report(
        ticker="nonbk",
        sector="non_financial",
        company="PT Contoh Non-Bank & Tbk <Test>",
        query="Berapa ROA dan ROE 2024?",
        years=[2024],
        extracted_data=ext_nb,
        ratios=ratios_nb,
        market_context=[],
        use_llm=False,
    )
    _assert(res_nb["report_audit"]["passed"], f"Audit non-bank gagal: {res_nb['report_audit']}")
    _assert("belum divalidasi" in res_nb["report"].lower(), "Label 'belum divalidasi' hilang di Markdown non-bank")
    _assert("belum divalidasi" in res_nb["telegram_summary"].lower(), "Label 'belum divalidasi' hilang di Telegram non-bank")
    _assert("ROA" in res_nb["report"] and "ROE" in res_nb["report"], "ROA/ROE hilang di laporan non-bank")
    _assert("| **CAR**" not in res_nb["report"], "Rasio bank (CAR) bocor ke profil non-bank")

    # Audit bebas kebocoran nama emiten / Catatan di src/agents/reporting.py (R10)
    src_text = (ROOT / "src" / "agents" / "reporting.py").read_text(encoding="utf-8")
    leak_pat = re.compile(r"\b(bbca|bmri|bbri|tlkm|bank central asia|bank mandiri|bca\.co\.id|bankmandiri\.co\.id|catatan\s+51f?)\b", re.IGNORECASE)
    leaks = leak_pat.findall(src_text)
    _assert(not leaks, f"Kebocoran nama emiten/Catatan di src/agents/reporting.py: {leaks}")


def check_d_telegram_and_node(res: dict[str, Any]) -> None:
    tg = res["telegram_summary"]
    _assert(len(tg) <= config.TELEGRAM_MAX_MESSAGE_CHARS, f"Ringkasan Telegram melebihi 4096 char: {len(tg)}")
    _assert("|---" not in tg, "Ringkasan Telegram tidak boleh berisi tabel Markdown")
    _assert("<b>" in tg and "</b>" in tg, "Ringkasan Telegram harus berformat HTML")

    # Uji escape karakter khusus HTML (<, >, &)
    tg_esc = rep.format_telegram_summary(
        identity={
            "ticker": "demo",
            "company": "PT A & B <Holdings>",
            "sector": "bank",
            "profile_label": "Perbankan",
            "profile_validated": True,
            "profile_warning": None,
        },
        query="Cek ROE > 15% & NPL < 5%",
        target_years=[2025],
        direct_answer="ROE > 15% & NPL < 2% (hal. 16).",
        ratios=None,
        market_context=[],
    )
    _assert("&amp;" in tg_esc and "&lt;" in tg_esc and "&gt;" in tg_esc, "Karakter khusus HTML tidak di-escape aman")

    # Uji kontrak reporting_node (siap Minggu 15) menggunakan state sintetis (pakai monkeypatch lokal)
    ext = _sample_bank_extracted()
    ratios = analyze_ratios(ext, sector="bank", years=[2024, 2025], ticker="demo", use_llm_summary=False)
    orig_gen = rep.generate_report
    try:
        rep.generate_report = lambda **kw: orig_gen(**{**kw, "use_llm": False})
        state: AgentState = {
            "query": "Ringkas kinerja bank",
            "ticker": "demo",
            "sector": "bank",
            "year": [2024, 2025],
            "extracted_data": ext,
            "ratios": ratios,
            "market_context": _sample_market(),
        }
        out = rep.reporting_node(state)
    finally:
        rep.generate_report = orig_gen

    _assert(bool(out.get("report")) and out["report_audit"]["passed"], "reporting_node gagal menghasilkan laporan valid")
    _assert(len(out.get("messages") or []) == 1, "reporting_node harus mengembalikan 1 AIMessage")


def check_e_negative_tests() -> None:
    ext = _sample_bank_extracted()
    ratios = analyze_ratios(ext, sector="bank", years=[2024, 2025], ticker="demo", use_llm_summary=False)

    # Negatif 1: market_context kosong (13.4) -> aman & jujur
    r1 = rep.generate_report(
        ticker="demo",
        sector="bank",
        company="PT Bank Contoh Tbk",
        years=[2024, 2025],
        extracted_data=ext,
        ratios=ratios,
        market_context=[],
        market_errors=["Tavily timeout"],
        use_llm=False,
    )
    _assert(r1["report_audit"]["passed"], "Negatif 1 gagal audit")
    _assert("tidak tersedia" in r1["report"].lower() and r1["report_audit"]["verified_url_count"] == 0, "Negatif 1 salah menangani market kosong")
    print("  OK    negatif 1: market_context=[] -> aman & jujur tanpa tautan karangan")

    # Negatif 2: LLM mengarang URL palsu -> terdeteksi & dibersihkan audit anti-halusinasi (14.2)
    hoax_url = "https://berita-palsu.example/hoax-laba-2025"
    fake_nar = ReportNarrative(
        direct_answer="CAR kuat sebesar 26,25% (hal. 530).",
        executive_summary=f"Kinerja solid, lihat [berita palsu]({hoax_url}) dan https://ojk-palsu.example/aturan.",
        ratio_analysis="CAR memenuhi syarat OJK (hal. 530).",
        trend_analysis="CAR meningkat +0,69 pp.",
        market_synthesis=f"Berita resmi di https://www.kontan.co.id/news/kinerja-kredit-perbankan-2025 dan {hoax_url}.",
        conclusion="Kesimpulan objektif bukan rekomendasi investasi.",
    )
    r2 = rep.generate_report(
        ticker="demo",
        sector="bank",
        company="PT Bank Contoh Tbk",
        years=[2024, 2025],
        extracted_data=ext,
        ratios=ratios,
        market_context=_sample_market(),
        use_llm=True,
        llm=_FakeStructuredLLM(narrative=fake_nar),
    )
    _assert(hoax_url not in r2["report"] and "ojk-palsu.example" not in r2["report"], "Negatif 2: URL palsu masih lolos!")
    _assert(len(r2["report_audit"]["stripped_urls"]) >= 2, f"Negatif 2: stripped_urls harus >= 2, dapat {r2['report_audit']['stripped_urls']}")
    _assert(r2["report_audit"]["passed"], "Negatif 2: laporan setelah sanitasi URL harus lulus audit")
    print(f"  OK    negatif 2: LLM mengarang URL palsu -> dibersihkan ({len(r2['report_audit']['stripped_urls'])} URL dibuang)")

    # Negatif 3: extracted_data & ratios kosong (kegagalan ekstraksi 15.2) -> tidak crash
    r3 = rep.generate_report(
        ticker="demo",
        sector="bank",
        company="PT Bank Contoh Tbk",
        query="Analisis 2025",
        years=[2025],
        extracted_data={},
        ratios={},
        extraction_errors=["PDF tahun 2025 belum terindeks di pustaka"],
        market_context=[],
        use_llm=False,
    )
    _assert(r3["status"] == "extraction_failed" and r3["report_audit"]["passed"], "Negatif 3 gagal menghasilkan laporan kegagalan valid")
    _assert("PDF tahun 2025 belum terindeks" in r3["report"], "Negatif 3 tidak mencantumkan alasan kegagalan ekstraksi")
    print("  OK    negatif 3: ekstraksi & rasio kosong -> laporan kegagalan jujur tanpa crash")

    # Negatif 4: metrik not_found / rasio insufficient_data (NIM 2025 di sample) -> jujur tidak diubah jadi 0%
    _assert("Tidak tersedia (*insufficient_data*)" in r1["report"], "Negatif 4: rasio insufficient_data tidak dicetak jujur")
    _assert("NIM (2025)" in r1["report"] and "earning_assets_bank" in r1["report"], "Negatif 4: komponen kurang tidak dijelaskan")
    print("  OK    negatif 4: metrik not_found & rasio insufficient_data -> dilaporkan jujur")

    # Negatif 5: LLM error/timeout -> fallback deterministik mulus
    r5 = rep.generate_report(
        ticker="demo",
        sector="bank",
        company="PT Bank Contoh Tbk",
        years=[2024, 2025],
        extracted_data=ext,
        ratios=ratios,
        market_context=_sample_market(),
        use_llm=True,
        llm=_FakeStructuredLLM(fail=True),
    )
    _assert(r5["report_stats"]["used_fallback_narrative"] is True, "Negatif 5 harus memicu fallback deterministik")
    _assert(r5["report_audit"]["passed"], "Negatif 5: fallback deterministik harus lulus audit")
    print("  OK    negatif 5: LLM error/timeout -> fallback deterministik lulus audit tanpa crash")


def run_live() -> dict[str, Any]:
    print("\n== F. Uji live Reporting Agent pada data nyata BBCA & BMRI (2023-2025) ==")
    live_summary: dict[str, Any] = {}
    for code in ("bbca", "bmri"):
        bundle = rep.load_saved_inputs(code)
        q = (
            f"Analisis kondisi keuangan, rasio prudensial OJK, tren 2023-2025, serta konteks pasar dan "
            f"regulasi untuk {bundle['company']} ({code.upper()})."
        )
        res = rep.generate_report(
            ticker=bundle["ticker"],
            sector=bundle["sector"],
            company=bundle["company"],
            query=q,
            years=bundle["years"],
            extracted_data=bundle["extracted_data"],
            ratios=bundle["ratios"],
            market_context=bundle["market_context"],
            market_errors=bundle["market_errors"],
            use_llm=True,
        )
        out_md = config.RESULTS / f"sample_report_{code}.md"
        out_md.write_text(res["report"], encoding="utf-8")

        aud = res["report_audit"]
        st = res["report_stats"]
        _assert(aud["passed"], f"Audit live {code} gagal: {aud}")
        _assert(not st["used_fallback_narrative"], f"Live {code} jatuh ke fallback: {st['narrative_errors']}")
        _assert(len(res["telegram_summary"]) <= config.TELEGRAM_MAX_MESSAGE_CHARS, f"Telegram {code} > 4096 char")

        live_summary[code] = {
            "ticker": code,
            "company": res["company"],
            "years": res["years"],
            "sample_report_path": str(out_md.relative_to(ROOT)).replace("\\", "/"),
            "report_audit": aud,
            "report_stats": st,
            "telegram_summary_chars": len(res["telegram_summary"]),
        }
        print(
            f"  OK    {code.upper()}: passed={aud['passed']} | rasio={aud['ratios_ok']}/{aud['ratios_total']} | "
            f"sitasi_hal={aud['page_citation_count']} | url={aud['verified_url_count']} | "
            f"stripped_url={len(aud['stripped_urls'])} | md={aud['markdown_chars']} ch | "
            f"tg={len(res['telegram_summary'])} ch | {st['total_tokens']} tok | {st['seconds']} s -> {out_md.name}"
        )

    out_json = config.RESULTS / "check_reporting.json"
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider": config.get_llm_provider(),
        "model": config.GROQ_MODEL,
        "reasoning_effort": config.REASONING_EFFORT,
        "results": live_summary,
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Tersimpan -> {out_json.relative_to(ROOT)}")
    return payload


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Pemeriksaan otomatis Reporting Agent (Minggu 14).")
    ap.add_argument("--offline", action="store_true", help="Jalankan pemeriksaan offline saja (0 token LLM).")
    ap.add_argument("--live", action="store_true", help="Jalankan offline + uji live BBCA & BMRI.")
    args = ap.parse_args()
    if not args.offline and not args.live:
        args.offline = True

    t0 = time.perf_counter()
    print("== Pemeriksaan offline Reporting Agent ==")
    res = check_a_structure_and_markdown()
    print("  OK    A. Struktur 5 bagian wajib & validitas tabel Markdown (14.1, 14.3)")
    check_b_citations_and_urls(res)
    print("  OK    B. Sitasi halaman per angka & penguncian URL/tanggal (14.2)")
    check_c_nonbank_and_no_leakage()
    print("  OK    C. Profil non-bank belum divalidasi (R17) & audit bebas emiten (R10)")
    check_d_telegram_and_node(res)
    print("  OK    D. Ringkasan HTML Telegram (<= 4096 char, 16.3d) & kontrak reporting_node")

    print("\n== E. Uji negatif (5 kasus — HARUS aman & akurat) ==")
    check_e_negative_tests()

    if args.live:
        run_live()

    print(f"\nSelesai dalam {time.perf_counter() - t0:.2f} s")
    print("HASIL: LULUS")


if __name__ == "__main__":
    main()
