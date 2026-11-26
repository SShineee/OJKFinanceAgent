"""
Tugas 3.2 -- kenali metadata laporan dari isinya.  docs/PANDUAN_MINGGU3.md, Langkah 7.

Masukannya teks per halaman dari page_filter.extract_page_texts(), yaitu teks yang sama dengan
yang dipakai penyaring, jadi PDF cukup dibaca sekali. Semua aturan deterministik (regex +
hitungan halaman), BUKAN LLM, supaya bisa diuji dan diulang. Tebakan dikonfirmasi pengguna di
Telegram (Minggu 16).

  year     tahun buku. "31 Desember 2024 dan 2023" di laporan keuangan: tahun pertama = tahun
           buku. Dicek silang dengan "Laporan Tahunan 2024" di halaman awal dan nama file.
  unit     satuan dominan dari penyaring (Langkah 1). Laporan BCA campur: jutaan Rp di laporan
           keuangan, miliar Rp di Ikhtisar, jadi rinciannya ikut disimpan (unit_pages).
  company  nama emiten: "PT ... Tbk" yang paling sering muncul.
  ticker   kode saham: "Kode Saham BBCA" (tabel identitas perusahaan), "(IDX: BBCA)", "Tbk (BBCA)".
  sector   salah satu dari VALIDATED_SECTORS + UNPROFILED_SECTORS di config.

Sektor ditentukan dari PENANDA REGULASI sektor itu sendiri, bukan dari kata kunci terbanyak.
Laporan bank mengonsolidasi anak usaha dari sektor lain: di laporan BCA "piutang pembiayaan
konsumen" (BCA Finance) muncul di 28-33 halaman, lebih banyak dari "kewajiban penyediaan modal
minimum" (14-16 halaman). Yang khas bank adalah kewajiban prudensial yang hanya berlaku bagi
bank: KPMM, ATMR, GWM, LCR, NSFR, LDR.

  1. bank        >= MIN_BANK_MARKERS dari 6 penanda bank, masing-masing di >= MIN_MARKER_PAGES halaman
     -> bank syariah kalau rasio syariah (NPF, FDR) lebih sering daripada padanannya (NPL, LDR)
  2. asuransi / pembiayaan / sekuritas: >= MIN_OTHER_MARKERS penanda, ambil yang terbanyak
  3. selain itu  non_financial

Yang DIVALIDASI hanya sektor bank (3 laporan BBCA, scripts/check_detect_metadata.py). Penanda
sektor lain diambil dari istilah regulasinya dan baru diuji pada teks buatan -- konsisten dengan
label "belum divalidasi" untuk sektor non-bank.

Jalankan:  python -m src.ingest.detect_metadata data/raw/bbca_2024.pdf
           python -m src.ingest.detect_metadata data/raw/bbca_2024.pdf --save   (-> data/markdown/)
Kriteria selesai:  python scripts/check_detect_metadata.py
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src import config
from src.ingest.page_filter import PageSelection, extract_page_texts, normalize, select_pages

FILE_NAME = re.compile(r"^([a-z0-9]+)_(\d{4})$")   # bbca_2024

# --- tahun buku -------------------------------------------------------------------------
STATEMENT_DATE = re.compile(r"31 (?:desember|december) (\d{4}) (?:dan|and) (\d{4})")
COVER_YEAR = re.compile(r"(?:laporan tahunan|annual report) (\d{4})")
COVER_PAGES = 30

# --- nama emiten & kode saham (teks ASLI, huruf besar-kecil dipertahankan) ---------------
NAME_WORD = r"(?!(?:PT|Tbk|TBK)\b)\(?[A-Z0-9][\w&.'’\-]*\)?,?"   # "Bank", "(Persero)", "Asia,"
COMPANY = re.compile(rf"\bPT\.? ((?:{NAME_WORD} ){{1,8}}?)(?:Tbk|TBK)\b")
TICKER_PATTERNS = (   # (pola, bobot, nama)
    (re.compile(r"(?i:kode saham|kode efek|stock code|ticker code|share code|stock ticker)"
                r" ?:? ?([A-Z]{4})\b"), 5, "kode saham"),
    (re.compile(r"\((?i:idx|bei) ?: ?([A-Z]{4})\)"), 1, "(IDX: kode)"),
    (re.compile(r"(?:Tbk|TBK)\.? ?\(([A-Z]{4})\)"), 1, "Tbk (kode)"),
)

# --- sektor (teks sesudah normalize(): huruf kecil, tanda hubung antar kata = spasi) -------
BANK_MARKERS = {
    "KPMM": ("kewajiban penyediaan modal minimum", "capital adequacy ratio"),
    "ATMR": ("aset tertimbang menurut risiko", "risk weighted assets"),
    "GWM": ("giro wajib minimum", "minimum statutory reserve"),
    "LCR": ("liquidity coverage ratio",),
    "NSFR": ("net stable funding ratio",),
    "LDR": ("loan to deposit ratio", "rasio intermediasi makroprudensial",
            "macroprudential intermediation ratio"),
}
# Rasio padanan (syariah, konvensional). Bank konvensional dengan anak usaha / unit syariah
# juga menyebut NPF -- yang menentukan adalah mana yang LEBIH SERING (BCA: NPF 1-2 halaman,
# NPL 20-23 halaman).
ISLAMIC_PAIRS = (
    (r"\bnpf\b|non performing financing", r"\bnpl\b|non performing loan"),
    (r"\bfdr\b|financing to deposit ratio", r"\bldr\b|loan to deposit ratio"),
)
OTHER_SECTOR_MARKERS = {   # BELUM DIVALIDASI pada laporan sungguhan
    "insurance": {
        "RBC": ("risk based capital", "tingkat solvabilitas", "rasio solvabilitas"),
        "kontrak asuransi": ("liabilitas kontrak asuransi", "insurance contract liabilities"),
        "premi": ("pendapatan premi", "premi bruto", "gross written premium"),
        "klaim": ("beban klaim", "klaim bruto"),
    },
    "multifinance": {
        "gearing": ("gearing ratio", "rasio gearing"),
        "FAR": ("financing to asset ratio",),
        "piutang pembiayaan": ("piutang pembiayaan konsumen", "consumer financing receivables"),
    },
    "securities": {
        "MKBD": ("modal kerja bersih disesuaikan", "net adjusted working capital"),
        "perantara": ("perantara pedagang efek",),
        "penjamin emisi": ("penjamin emisi efek",),
    },
}
MIN_MARKER_PAGES = 2     # penanda yang hanya muncul di 1 halaman tidak dihitung
MIN_BANK_MARKERS = 4     # dari 6 -- BCA: 6 dari 6 di ketiga laporan
MIN_OTHER_MARKERS = 2
NON_FINANCIAL = "non_financial"
SECTORS = [*config.VALIDATED_SECTORS, *config.UNPROFILED_SECTORS]


@dataclass
class ReportMetadata:
    source: str
    ticker: str | None              # huruf kecil, = identitas emiten di seluruh sistem
    company: str | None
    year: int | None
    unit: str | None
    sector: str | None
    unit_pages: dict[str, int] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def validated(self) -> bool:
        return self.sector in config.VALIDATED_SECTORS

    def to_dict(self) -> dict:
        return {**asdict(self), "validated": self.validated}


def parse_file_name(path: str | Path) -> tuple[str, int] | None:
    """'bbca_2024.pdf' -> ('bbca', 2024); nama lain (unggahan Telegram) -> None."""
    m = FILE_NAME.match(Path(path).stem.lower())
    return (m.group(1), int(m.group(2))) if m else None


def _pages_with(texts: list[str], phrases: tuple[str, ...]) -> int:
    return sum(1 for t in texts if any(p in t for p in phrases))


def _pages_matching(texts: list[str], pattern: str) -> int:
    rx = re.compile(pattern)
    return sum(1 for t in texts if rx.search(t))


def detect_year(norm: list[str]) -> tuple[int | None, str, list[str]]:
    statement = Counter(int(a) for t in norm for a, b in STATEMENT_DATE.findall(t)
                        if int(a) == int(b) + 1)
    cover = Counter(int(y) for t in norm[:COVER_PAGES] for y in COVER_YEAR.findall(t))
    cover_year = cover.most_common(1)[0][0] if cover else None
    if statement:
        year, n = statement.most_common(1)[0]
        evidence = (f"'31 Desember {year} dan {year - 1}' {n}x "
                    f"({n / sum(statement.values()):.0%} dari tanggal sejenis)")
        if cover_year is None:
            return year, evidence, []
        evidence += f"; sampul '{cover_year}' {cover[cover_year]}x"
        if cover_year != year:
            return year, evidence, [f"tahun di sampul ({cover_year}) berbeda dengan tahun laporan "
                                    f"keuangan ({year})"]
        return year, evidence, []
    if cover_year is not None:
        return cover_year, f"sampul '{cover_year}' {cover[cover_year]}x", [
            "tanggal laporan keuangan ('31 Desember ... dan ...') tidak ditemukan; tahun dari sampul"]
    return None, "", ["tahun buku tidak ditemukan"]


def detect_company(flat: list[str]) -> tuple[str | None, str, list[str]]:
    variants = Counter(m.group(1).strip().rstrip(",") for t in flat for m in COMPANY.finditer(t))
    if not variants:
        return None, "", ["nama emiten ('PT ... Tbk') tidak ditemukan"]
    groups = Counter()
    for name, n in variants.items():
        groups[name.casefold()] += n
    key, total = groups.most_common(1)[0]
    forms = [(n, name) for name, n in variants.items() if name.casefold() == key]
    # tampilkan bentuk huruf besar-kecil biasa kalau ada, bukan versi HURUF BESAR semua
    forms.sort(key=lambda f: (not f[1].isupper(), f[0]), reverse=True)
    company = f"PT {forms[0][1]} Tbk"
    return company, f"{total}x", []


def detect_ticker(flat: list[str]) -> tuple[str | None, str, list[str]]:
    votes, seen = Counter(), {}
    for page, text in enumerate(flat, 1):
        for pattern, weight, name in TICKER_PATTERNS:
            for code in pattern.findall(text):
                votes[code] += weight
                seen.setdefault(code, {}).setdefault(name, page)
    if not votes:
        return None, "", ["kode saham tidak ditemukan"]
    (code, score), *rest = votes.most_common()
    evidence = ", ".join(f"{name} hal {page}" for name, page in seen[code].items())
    warnings = []
    if rest and rest[0][1] * 2 >= score:
        warnings.append(f"kode saham ambigu: {code} ({score}) vs {rest[0][0]} ({rest[0][1]})")
    return code.lower(), evidence, warnings


def sector_scores(norm: list[str]) -> dict:
    """Jumlah halaman per penanda -- dipisah supaya bisa ditampilkan sebagai bukti."""
    bank = {k: _pages_with(norm, p) for k, p in BANK_MARKERS.items()}
    islamic = [(_pages_matching(norm, s), _pages_matching(norm, c)) for s, c in ISLAMIC_PAIRS]
    other = {sector: {k: _pages_with(norm, p) for k, p in markers.items()}
             for sector, markers in OTHER_SECTOR_MARKERS.items()}
    return {"bank": bank, "islamic_pairs": islamic, "other": other}


def detect_sector(norm: list[str]) -> tuple[str, str, list[str]]:
    scores = sector_scores(norm)
    bank = scores["bank"]
    strong = [k for k, n in bank.items() if n >= MIN_MARKER_PAGES]
    if len(strong) >= MIN_BANK_MARKERS:
        islamic = sum(s for s, _ in scores["islamic_pairs"])
        conventional = sum(c for _, c in scores["islamic_pairs"])
        sector = "islamic_bank" if islamic > conventional else "bank"
        evidence = (f"penanda bank {len(strong)}/{len(bank)} ("
                    + ", ".join(f"{k} {n} hal" for k, n in bank.items())
                    + f"); syariah {islamic} vs konvensional {conventional} hal")
        return sector, evidence, []

    ranked = []
    for sector, markers in scores["other"].items():
        hits = [k for k, n in markers.items() if n >= MIN_MARKER_PAGES]
        if len(hits) >= MIN_OTHER_MARKERS:
            ranked.append((len(hits), sector, hits))
    ranked.sort(reverse=True)
    bank_note = f"penanda bank {len(strong)}/{len(bank)}"
    if not ranked:
        return NON_FINANCIAL, f"{bank_note}; tidak ada sektor keuangan lain yang memenuhi", []
    n, sector, hits = ranked[0]
    warnings = []
    if len(ranked) > 1 and ranked[1][0] == n:
        warnings.append(f"sektor ambigu: {sector} vs {ranked[1][1]} ({n} penanda)")
    return sector, f"{bank_note}; {sector}: {', '.join(hits)}", warnings


def detect_metadata(texts: list[str], source: str = "",
                    selection: PageSelection | None = None) -> ReportMetadata:
    """texts = teks per halaman (indeks 0 = halaman 1), dari extract_page_texts()."""
    start = time.perf_counter()
    selection = selection or select_pages(texts, source)
    norm = [normalize(t) for t in texts]
    flat = [re.sub(r"\s+", " ", t) for t in texts]

    year, year_ev, year_w = detect_year(norm)
    company, company_ev, company_w = detect_company(flat)
    ticker, ticker_ev, ticker_w = detect_ticker(flat)
    sector, sector_ev, sector_w = detect_sector(norm)
    warnings = year_w + company_w + ticker_w + sector_w

    if selection.unit is None:
        warnings.append("satuan tidak ditemukan (tidak ada penanda 'dalam jutaan rupiah' dst.)")
    if selection.looks_scanned:
        warnings.insert(0, f"{selection.empty_pages} dari {selection.total_pages} halaman tanpa "
                           f"teks -- kemungkinan hasil scan, deteksi tidak bisa diandalkan")

    named = parse_file_name(source) if source else None
    if named:
        if ticker and named[0] != ticker:
            warnings.append(f"kode saham di isi ({ticker}) berbeda dengan nama file ({named[0]})")
        if year and named[1] != year:
            warnings.append(f"tahun buku di isi ({year}) berbeda dengan nama file ({named[1]})")

    return ReportMetadata(
        source=Path(source).name if source else "", ticker=ticker, company=company, year=year,
        unit=selection.unit, sector=sector, unit_pages=dict(selection.unit_page_counts),
        evidence={"year": year_ev, "company": company_ev, "ticker": ticker_ev,
                  "unit": ", ".join(f"{u} {n} hal" for u, n in selection.unit_page_counts.items()),
                  "sector": sector_ev},
        warnings=warnings, seconds=round(time.perf_counter() - start, 2))


def detect_pdf(pdf_path: str | Path) -> ReportMetadata:
    start = time.perf_counter()
    texts = extract_page_texts(pdf_path)
    meta = detect_metadata(texts, str(pdf_path))
    meta.seconds = round(time.perf_counter() - start, 1)
    return meta


def save(meta: ReportMetadata) -> Path:
    if meta.ticker is None or meta.year is None:
        raise ValueError("kode saham / tahun buku tidak terdeteksi -- tidak bisa menentukan nama file")
    path = config.report_metadata(meta.year, meta.ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Kenali metadata laporan tahunan dari isinya")
    ap.add_argument("pdf", nargs="+", type=Path)
    ap.add_argument("--save", action="store_true", help="simpan ke data/markdown/<kode>_<tahun>.metadata.json")
    args = ap.parse_args(argv)

    failed = 0
    for pdf_path in args.pdf:
        try:
            meta = detect_pdf(pdf_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"{pdf_path.name}: GAGAL -- {e}")
            failed += 1
            continue
        label = "" if meta.validated else "  (belum divalidasi)"
        print(f"{meta.source}  ({meta.seconds} s)")
        for key in ("ticker", "company", "year", "unit", "sector"):
            value = getattr(meta, key)
            print(f"  {key:<8} {value}{label if key == 'sector' else ''}")
            if meta.evidence.get(key):
                print(f"           {meta.evidence[key]}")
        for w in meta.warnings:
            print(f"  PERINGATAN: {w}")
        if args.save:
            try:
                print(f"  disimpan ke {save(meta).relative_to(config.ROOT)}")
            except ValueError as e:
                print(f"  GAGAL menyimpan -- {e}")
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
