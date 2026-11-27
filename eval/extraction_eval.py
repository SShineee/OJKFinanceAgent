"""
Tugas 9.6-9.7 (GATE 4) -- evaluasi akurasi Extraction Agent: 8 metrik bank x 3 tahun = 24 titik per
emiten, dibandingkan terhadap ground truth terverifikasi visual.  docs/PANDUAN_MINGGU9.md, Langkah 6.

Urutan WAJIB (disiplin data uji R10 & R11):
  Tahap 1  python -m eval.extraction_eval --ticker bbca      # iterasi hanya di BBCA sampai >= 22/24
           -> commit prompt & profil (kunci), catat hash commit;
  Tahap 2  python -m eval.extraction_eval --ticker bmri      # SATU KALI, prompt tidak boleh diubah
  Gabung   python -m eval.extraction_eval --combine          # results/extraction_eval.json & .csv

Pagar Tahap 2: emiten uji hanya boleh dijalankan bila (a) hasil BBCA tersimpan lengkap 24 titik dan
>= 90%, (b) sidik jari (SHA-256) file prompt/profil/parser/tool SAMA dengan saat BBCA dievaluasi, dan
(c) file-file itu sudah ter-commit (tidak ada perubahan lokal). `--force` hanya untuk diagnosis.

Kuota Groq (8K TPM / 200K TPD): hasil disimpan bertahap per tahun. Bila kuota harian habis, jalankan
ulang perintah yang sama nanti -- tahun yang sudah selesai dengan sidik jari sama otomatis dilewati
(`--fresh` untuk mengulang semuanya).

Ketepatan: |hasil - ground_truth| / ground_truth <= 0,5% (ground truth miliar Rp x 1.000 = juta Rp).
"""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import load_workbook

from src import config
from src import ratio_profiles as rp
from src.agents import extraction as ext

DEV_TICKER = "bbca"
DEFAULT_YEARS = (2023, 2024, 2025)
TOLERANCE_PCT = 0.5
GATE4_THRESHOLDS = {"bbca": 0.90}          # emiten pengembangan
GATE4_TEST_THRESHOLD = 0.80                # emiten uji (BMRI)

# 8 metrik GATE 4 -> baris sheet `1_angka_mentah` (tata letak kedua workbook identik, Keputusan 9.D)
GATE4_GT_ROWS = {
    "net_income": 10,
    "tier1_capital_bank": 13,
    "total_assets": 3,
    "gross_loans_bank": 22,
    "deposits_bank": 24,
    "npl_amount_bank": 21,
    "net_interest_income": 8,
    "rwa_bank": 15,
}
GT_YEAR_COL = {2022: 3, 2023: 4, 2024: 5, 2025: 6}
GT_PAGE_COL = 7

# File yang menentukan perilaku agent -> sidik jari kunci prompt
LOCKED_FILES = (
    "src/agents/extraction.py",
    "src/ratio_profiles.py",
    "src/agents/parse_number.py",
    "src/agents/tools.py",
    "src/agents/state.py",
)

CSV_FIELDS = [
    "ticker", "year", "metric_key", "ok", "status", "diagnosis", "value_million_idr",
    "ground_truth_million_idr", "rel_err_pct", "source_pages", "source_chunk_id", "raw_value",
    "components", "original_unit", "chunk_unit", "basis", "gt_source", "notes",
]


def ground_truth_path(ticker: str) -> Path:
    return config.GROUND_TRUTH if ticker == DEV_TICKER else config.DATA / f"ground_truth_{ticker}.xlsx"


def load_ground_truth(ticker: str, years) -> dict[int, dict[str, dict]]:
    ws = load_workbook(ground_truth_path(ticker), data_only=True)["1_angka_mentah"]
    gt: dict[int, dict[str, dict]] = {}
    for y in years:
        gt[y] = {}
        for key, row in GATE4_GT_ROWS.items():
            val = ws.cell(row=row, column=GT_YEAR_COL[y]).value
            if val is None:
                raise ValueError(f"ground truth {ticker} {key} {y} kosong (baris {row})")
            gt[y][key] = {
                "value_million_idr": round(float(val) * 1000.0, 3),
                "label": ws.cell(row=row, column=1).value,
                "source": ws.cell(row=row, column=GT_PAGE_COL).value,
            }
    return gt


def fingerprint() -> dict:
    """SHA-256 gabungan file agent (akhir baris dinormalkan agar CRLF/LF tidak berpengaruh)."""
    h = hashlib.sha256()
    per_file = {}
    for rel in LOCKED_FILES:
        data = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
        per_file[rel] = hashlib.sha256(data).hexdigest()
        h.update(rel.encode() + b"\0" + data + b"\0")
    return {"sha256": h.hexdigest(), "files": per_file}


def git_info() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return ""
    # `git diff` (bukan `status`) -> hanya perubahan isi nyata; beda akhir baris CRLF/LF diabaikan
    dirty = run("diff", "--name-only", "HEAD", "--", *LOCKED_FILES)
    untracked = run("ls-files", "--others", "--exclude-standard", "--", *LOCKED_FILES)
    return {
        "head": run("rev-parse", "--short", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "locked_files_dirty": [ln.strip() for ln in (dirty + "\n" + untracked).splitlines() if ln.strip()],
    }


def diagnose(m: dict, gt_val: float, rel_err: float | None) -> str:
    """Kategori kesalahan untuk analisis Bab 4."""
    if m["status"] != "ok":
        return m["status"]                                   # not_found / ungrounded / parse_error / unit_conflict
    if rel_err is not None and rel_err <= TOLERANCE_PCT:
        return "tepat"
    v = m["value_million_idr"] or 0.0
    ratio = v / gt_val if gt_val else 0.0
    if 900 <= ratio <= 1100 or 0.0009 <= ratio <= 0.0011:
        return "skala_1000x"
    if m.get("components"):
        return "komponen_salah"
    if m.get("basis") not in ("unknown", rp.BANK_PROFILE.metrics[m["metric_key"]].basis):
        return "basis_tertukar"
    return "nilai_salah"                                     # kolom tahun / baris / basis keliru


def score_year(ticker: str, year: int, extracted: dict, gt_year: dict) -> list[dict]:
    points = []
    for key in GATE4_GT_ROWS:
        m = extracted.get(key) or {"metric_key": key, "status": "not_found", "value_million_idr": None}
        g = gt_year[key]["value_million_idr"]
        v = m.get("value_million_idr")
        rel_err = abs(v - g) / g * 100 if (v is not None and g) else None
        ok = m.get("status") == "ok" and rel_err is not None and rel_err <= TOLERANCE_PCT
        points.append({
            "ticker": ticker,
            "year": year,
            "metric_key": key,
            "ok": ok,
            "status": m.get("status"),
            "diagnosis": diagnose({**m, "metric_key": key}, g, rel_err),
            "value_million_idr": v,
            "ground_truth_million_idr": g,
            "rel_err_pct": round(rel_err, 4) if rel_err is not None else None,
            "source_pages": m.get("source_pages", []),
            "source_chunk_id": m.get("source_chunk_id"),
            "raw_value": m.get("raw_value"),
            "components": m.get("components"),
            "original_unit": m.get("original_unit"),
            "chunk_unit": m.get("chunk_unit"),
            "basis": m.get("basis"),
            "gt_source": gt_year[key]["source"],
            "notes": m.get("notes"),
        })
    return points


def summarize(ticker: str, years, per_year: dict) -> dict:
    points = [p for y in years if str(y) in per_year for p in per_year[str(y)]["points"]]
    n_expected = len(years) * len(GATE4_GT_ROWS)
    hits = sum(p["ok"] for p in points)
    threshold = GATE4_THRESHOLDS.get(ticker, GATE4_TEST_THRESHOLD)
    by_metric = {
        k: {"hits": sum(p["ok"] for p in points if p["metric_key"] == k),
            "n": sum(1 for p in points if p["metric_key"] == k)}
        for k in GATE4_GT_ROWS
    }
    by_year = {str(y): {"hits": sum(p["ok"] for p in per_year[str(y)]["points"]), "n": len(per_year[str(y)]["points"])}
               for y in years if str(y) in per_year}
    diag: dict[str, int] = {}
    for p in points:
        diag[p["diagnosis"]] = diag.get(p["diagnosis"], 0) + 1
    stats_keys = ("llm_calls", "tool_calls", "followup_calls", "input_tokens", "output_tokens", "total_tokens",
                  "rate_limit_retries", "tool_error_retries", "seconds")
    totals = {k: round(sum(per_year[str(y)]["stats"].get(k, 0) for y in years if str(y) in per_year), 2)
              for k in stats_keys}
    done_years = [y for y in years if str(y) in per_year]
    return {
        "n_expected": n_expected,
        "n_scored": len(points),
        "complete": len(points) == n_expected,
        "hits": hits,
        "accuracy": round(hits / n_expected, 4) if n_expected else 0.0,
        "threshold": threshold,
        "passed": len(points) == n_expected and hits / n_expected >= threshold,
        "by_metric": by_metric,
        "by_year": by_year,
        "diagnosis_counts": diag,
        "totals": totals,
        "avg_tokens_per_year": round(totals["total_tokens"] / len(done_years)) if done_years else 0,
        "avg_seconds_per_year": round(totals["seconds"] / len(done_years), 2) if done_years else 0.0,
    }


def write_csv(path: Path, points: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for p in points:
            row = {k: p.get(k) for k in CSV_FIELDS}
            row["source_pages"] = " ".join(map(str, p.get("source_pages") or []))
            row["components"] = " + ".join(p.get("components") or [])
            w.writerow(row)


def guard_test_ticker(ticker: str, fp: dict, git: dict, force: bool):
    """Tahap 2 hanya boleh jalan setelah prompt dikunci pada emiten pengembangan (R10 & R11)."""
    dev_path = config.RESULTS / f"extraction_eval_{DEV_TICKER}.json"
    problems = []
    if not dev_path.exists():
        problems.append(f"{dev_path.name} belum ada -- jalankan Tahap 1 ({DEV_TICKER}) dulu")
    else:
        dev = json.loads(dev_path.read_text(encoding="utf-8"))
        s = dev["summary"]
        if not s["complete"] or not s["passed"]:
            problems.append(f"hasil {DEV_TICKER} belum lulus: {s['hits']}/{s['n_expected']} (butuh >= {s['threshold']:.0%})")
        if dev["meta"]["fingerprint"]["sha256"] != fp["sha256"]:
            changed = [f for f, h in fp["files"].items() if dev["meta"]["fingerprint"]["files"].get(f) != h]
            problems.append(f"prompt/profil berubah sejak evaluasi {DEV_TICKER}: {changed}")
    if git["locked_files_dirty"]:
        problems.append(f"file terkunci belum di-commit: {git['locked_files_dirty']}")
    if problems:
        print("PAGAR TAHAP 2 MENOLAK menjalankan emiten uji:")
        for p in problems:
            print(f"  - {p}")
        if not force:
            sys.exit(2)
        print("  (--force: tetap dijalankan HANYA untuk diagnosis, hasil ditandai tidak sah)")


def run_eval(args) -> int:
    ticker = args.ticker.strip().lower()
    years = tuple(args.years or DEFAULT_YEARS)
    out_prefix = args.out_prefix or f"extraction_eval_{ticker}"
    json_path = config.RESULTS / f"{out_prefix}.json"
    csv_path = config.RESULTS / f"{out_prefix}.csv"

    fp = fingerprint()
    git = git_info()
    if ticker != DEV_TICKER:
        guard_test_ticker(ticker, fp, git, args.force)

    gt = load_ground_truth(ticker, years)

    per_year: dict[str, dict] = {}
    if json_path.exists() and not args.fresh:
        prev = json.loads(json_path.read_text(encoding="utf-8"))
        if prev["meta"]["fingerprint"]["sha256"] == fp["sha256"]:
            # Tahun dengan kegagalan panggilan LLM (koneksi/parsing) tidak dianggap selesai -> diulang
            per_year = {y: v for y, v in prev.get("per_year", {}).items()
                        if int(y) in years and not v.get("llm_failures")}
            if per_year:
                print(f"Melanjutkan: tahun {sorted(per_year)} sudah dievaluasi dengan sidik jari sama (lewati).")
        else:
            print("Sidik jari prompt/profil berubah -> evaluasi diulang dari awal.")

    meta = {
        "task": "9.6-9.7 GATE 4 extraction eval",
        "ticker": ticker,
        "years": list(years),
        "role": "pengembangan" if ticker == DEV_TICKER else "uji",
        "model": config.GROQ_MODEL,
        "reasoning_effort": config.REASONING_EFFORT_EXTRACTION,
        "tolerance_pct": TOLERANCE_PCT,
        "ground_truth": ground_truth_path(ticker).name,
        "fingerprint": fp,
        "git": git,
        "forced": bool(args.force and ticker != DEV_TICKER),
    }

    def save():
        meta["timestamp"] = datetime.now().isoformat(timespec="seconds")
        summary = summarize(ticker, years, per_year)
        payload = {"meta": meta, "summary": summary, "per_year": per_year}
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        write_csv(csv_path, [p for y in years if str(y) in per_year for p in per_year[str(y)]["points"]])
        return summary

    print(f"== Evaluasi ekstraksi GATE 4: {ticker} {list(years)} | sidik jari {fp['sha256'][:12]}… | git {git['head']} ==")
    stopped = None
    for i, y in enumerate(years):
        if str(y) in per_year:
            continue
        if i > 0 and args.year_delay > 0 and per_year:
            time.sleep(args.year_delay)
        print(f"\n-- {ticker}_{y} --", flush=True)
        try:
            res = ext.extract_metrics(ticker=ticker, years=y, gate4_only=True, delay_between_groups=args.delay)
        except ext.RateLimitExhausted as e:
            stopped = str(e)
            print(f"  BERHENTI: {e}")
            break
        points = score_year(ticker, y, res["extracted_data"][y], gt[y])
        per_year[str(y)] = {
            "points": points,
            "stats": res["extraction_stats"],
            "errors": res["extraction_errors"],
            "llm_failures": sum("ekstraksi LLM gagal" in e for e in res["extraction_errors"]),
            "retrieved_chunk_ids": [(c["chunk_id"], c.get("pages")) for c in res["retrieved_chunks"]],
        }
        for p in points:
            err = f"{p['rel_err_pct']:.3f}%" if p["rel_err_pct"] is not None else "-"
            val = f"{p['value_million_idr']:,.0f}" if p["value_million_idr"] is not None else "None"
            print(f"  {'OK  ' if p['ok'] else 'MISS'} {p['metric_key']:<22} {val:>17} | gt {p['ground_truth_million_idr']:>17,.0f}"
                  f" | err {err:<8} | {p['diagnosis']:<14} | hal {p['source_pages']}")
        st = res["extraction_stats"]
        print(f"  {sum(p['ok'] for p in points)}/8 | {st['llm_calls']} LLM call, {st['total_tokens']:,} token, "
              f"{st['seconds']} s, retry429={st['rate_limit_retries']}x", flush=True)
        save()

    summary = save()
    print(f"\n== RINGKASAN {ticker} ({meta['role']}) ==")
    for k, v in summary["by_metric"].items():
        print(f"  {k:<22} {v['hits']}/{v['n']}")
    print(f"  per tahun: " + ", ".join(f"{y}: {v['hits']}/{v['n']}" for y, v in summary["by_year"].items()))
    print(f"  diagnosis: {summary['diagnosis_counts']}")
    print(f"  token total {summary['totals']['total_tokens']:,} (rata-rata {summary['avg_tokens_per_year']:,}/tahun), "
          f"waktu {summary['totals']['seconds']} s, retry429={summary['totals']['rate_limit_retries']}x, "
          f"tool_err={summary['totals']['tool_error_retries']}x")
    print(f"  AKURASI: {summary['hits']}/{summary['n_expected']} = {summary['accuracy']:.1%} "
          f"(ambang {summary['threshold']:.0%}) -> {'LULUS' if summary['passed'] else ('BELUM LENGKAP' if not summary['complete'] else 'GAGAL')}")
    print(f"  Disimpan: {json_path.relative_to(ROOT)} & {csv_path.relative_to(ROOT)}")
    if stopped:
        print("  Kuota Groq habis -- jalankan ulang perintah yang sama nanti untuk melanjutkan tahun tersisa.")
        return 3
    return 0 if summary["passed"] else 1


def combine() -> int:
    parts = {}
    for t in ("bbca", "bmri"):
        p = config.RESULTS / f"extraction_eval_{t}.json"
        if p.exists():
            parts[t] = json.loads(p.read_text(encoding="utf-8"))
    if not parts:
        print("Belum ada hasil per emiten.")
        return 1
    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "tolerance_pct": TOLERANCE_PCT,
        "per_ticker": {t: {"meta": d["meta"], "summary": d["summary"]} for t, d in parts.items()},
    }
    if "bbca" in parts and "bmri" in parts:
        a, b = parts["bbca"]["summary"]["accuracy"], parts["bmri"]["summary"]["accuracy"]
        out["generalization_gap_pct_points"] = round((a - b) * 100, 2)
        out["gate4_passed"] = parts["bbca"]["summary"]["passed"] and parts["bmri"]["summary"]["passed"] \
            and not parts["bmri"]["meta"].get("forced")
    (config.RESULTS / "extraction_eval.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(config.RESULTS / "extraction_eval.csv",
              [p for d in parts.values() for y in d["meta"]["years"] if str(y) in d["per_year"]
               for p in d["per_year"][str(y)]["points"]])
    for t, d in parts.items():
        s = d["summary"]
        print(f"  {t}: {s['hits']}/{s['n_expected']} = {s['accuracy']:.1%} (ambang {s['threshold']:.0%}) "
              f"-> {'LULUS' if s['passed'] else 'GAGAL'}")
    if "gate4_passed" in out:
        print(f"  gap generalisasi: {out['generalization_gap_pct_points']} poin persen")
        print(f"  GATE 4: {'LULUS' if out['gate4_passed'] else 'GAGAL'}")
    print("  Disimpan: results/extraction_eval.json & results/extraction_eval.csv")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Evaluasi GATE 4 Extraction Agent (Minggu 9-10).")
    ap.add_argument("--ticker", help="bbca (Tahap 1, pengembangan) atau bmri (Tahap 2, uji satu kali)")
    ap.add_argument("--years", type=int, nargs="*", help="default 2023 2024 2025")
    ap.add_argument("--out-prefix", help="default extraction_eval_<ticker>")
    ap.add_argument("--delay", type=float, default=2.0, help="jeda detik antar kelompok metrik (TPM)")
    ap.add_argument("--year-delay", type=float, default=20.0, help="jeda detik antar tahun (TPM)")
    ap.add_argument("--fresh", action="store_true", help="abaikan hasil tersimpan, ulang semua tahun")
    ap.add_argument("--force", action="store_true", help="lewati pagar Tahap 2 (diagnosis saja, hasil tidak sah)")
    ap.add_argument("--combine", action="store_true", help="gabung hasil per emiten ke results/extraction_eval.*")
    args = ap.parse_args(argv)
    if args.combine:
        sys.exit(combine())
    if not args.ticker:
        ap.error("--ticker wajib (atau --combine)")
    sys.exit(run_eval(args))


if __name__ == "__main__":
    main()
