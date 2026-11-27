"""
Langkah 2 Minggu 9 (tugas 9.5 & 9.5b) & Langkah 1 Minggu 11 (tugas 11.2 & 11.6) --
profil ekstraksi, formula rasio eksplisit, dan ambang batas prudensial OJK per sektor.
docs/PANDUAN_MINGGU9-10.md & docs/PANDUAN_MINGGU11-12.md.

ATURAN DISIPLIN DATA UJI (9.5 & 11.2):
  File ini TIDAK BOLEH menyebut nama emiten, kode saham, nomor halaman, atau nomor Catatan tertentu.
  Seluruh deskripsi metrik, query retrieval, formula rasio, dan ambang batas bersifat 100% generik
  (semantik standar OJK/PSAK).

Dua profil disediakan sesuai keputusan ruang lingkup (config.VALIDATED_SECTORS):
  - `bank`    (validated=True)  : 8 metrik inti GATE 4 + metrik pelengkap + 6 formula rasio SEOJK
                                  (CAR, ROA, ROE, NIM, NPL, LDR) & ambang batas prudensial OJK;
  - `general` (validated=False) : 3 metrik dasar + 2 formula umum (ROA, ROE) untuk emiten non-bank,
                                  diberi label jelas "belum divalidasi".
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from src import config


@dataclass(frozen=True)
class MetricSpec:
    """Spesifikasi semantik satu angka keuangan yang diekstrak."""

    key: str
    label: str
    basis: str                               # 'bank_only' | 'consolidated'
    description: str
    is_percent: bool = False
    abs_value: bool = False                  # True -> nilai absolut (mis. CKPN / kredit bermasalah)
    gate4: bool = False                      # True -> termasuk 8 metrik wajib GATE 4 (tugas 9.6)
    allow_components: bool = False           # True -> boleh pakai `components` + sum bila total tak tercetak


@dataclass(frozen=True)
class ExtractionGroup:
    """Kelompok metrik sejenis yang diambil dalam 1 batch hemat token (batas Groq 8K TPM)."""

    group_id: str
    title: str
    search_queries: tuple[str, ...]
    metric_keys: tuple[str, ...]
    top_k: int = 4
    prefer_tables: bool = True               # False bila pengungkapan regulasi bisa berupa paragraf teks (mis. NPL)


@dataclass(frozen=True)
class RatioFormula:
    """Formula eksplisit satu rasio keuangan (dieksekusi PythonAstREPLTool, bukan dikarang LLM)."""

    name: str                                # 'CAR', 'ROA', 'ROE', 'NIM', 'NPL', 'LDR'
    label: str
    expression: str                          # ekspresi matematika Python (hasil dalam %)
    inputs: tuple[tuple[str, tuple[str, ...]], ...]  # ((nama_var, (metric_key_utama, fallback...)), ...)
    average_vars: tuple[str, ...] = ()       # nama variabel penyebut yang memakai rata-rata (t-1 + t) / 2
    positive_vars: tuple[str, ...] = ()      # nama variabel yang wajib > 0 (cegah bagi nol / rasio cacat)
    basis_description: str = ""
    notes: str | None = None


@dataclass(frozen=True)
class SectorProfile:
    """Profil ekstraksi, daftar rasio, & formula eksplisit untuk satu sektor emiten."""

    sector: str
    label: str
    validated: bool
    warning_label: str | None
    metrics: dict[str, MetricSpec]
    extraction_groups: tuple[ExtractionGroup, ...]
    ratio_names: tuple[str, ...]
    formulas: dict[str, RatioFormula] = field(default_factory=dict)


# ----------------------------------------------------------------- Profil BANK (tervalidasi)

_BANK_METRICS = {
    m.key: m
    for m in (
        # --- 8 metrik wajib GATE 4 (tugas 9.6) ---
        MetricSpec(
            key="total_assets",
            label="Total Aset (Konsolidasian)",
            basis="consolidated",
            description=(
                "Total Aset / Jumlah Aset pada Ikhtisar Data Keuangan atau Laporan Posisi Keuangan "
                "Konsolidasian pada akhir tahun buku (BUKAN Entitas Induk saja)."
            ),
            gate4=True,
        ),
        MetricSpec(
            key="net_interest_income",
            label="Pendapatan Bunga Bersih (Konsolidasian)",
            basis="consolidated",
            description=(
                "Pendapatan Bunga Bersih atau Pendapatan Bunga dan Syariah - Bersih/Neto pada "
                "Ikhtisar Data Keuangan atau Laporan Laba Rugi Konsolidasian (BUKAN Entitas Induk saja)."
            ),
            gate4=True,
        ),
        MetricSpec(
            key="net_income",
            label="Laba Bersih / Laba Tahun Berjalan (Konsolidasian)",
            basis="consolidated",
            description=(
                "Total Laba Bersih atau Laba Tahun Berjalan konsolidasian pada Ikhtisar Data Keuangan "
                "atau Laporan Laba Rugi Konsolidasian (total keseluruhan sebelum pemisahan ke pemilik "
                "entitas induk dan kepentingan nonpengendali)."
            ),
            gate4=True,
        ),
        MetricSpec(
            key="tier1_capital_bank",
            label="Modal Inti / Tier 1 (Bank)",
            basis="bank_only",
            description=(
                "Modal Inti (Tier 1) pada tabel Kewajiban Penyediaan Modal Minimum (KPMM) atau "
                "Struktur Permodalan, WAJIB kolom Bank / Entitas Induk saja (BUKAN kolom Konsolidasian)."
            ),
            gate4=True,
        ),
        MetricSpec(
            key="rwa_bank",
            label="Total ATMR (Bank)",
            basis="bank_only",
            description=(
                "Total Aset Tertimbang Menurut Risiko (ATMR) untuk risiko kredit, operasional, dan "
                "pasar pada tabel KPMM / Struktur Permodalan, WAJIB kolom Bank / Entitas Induk saja "
                "(BUKAN kolom Konsolidasian)."
            ),
            gate4=True,
        ),
        MetricSpec(
            key="gross_loans_bank",
            label="Kredit yang Diberikan Bruto (Bank)",
            basis="bank_only",
            description=(
                "Total Kredit yang Diberikan BRUTO (SEBELUM dikurangi cadangan kerugian penurunan nilai / "
                "CKPN) pada Laporan Posisi Keuangan Entitas Induk (Bank saja / Parent Entity). "
                "Aturan penting: (a) jika tabel mencetak baris jumlah/subtotal kredit bruto tepat sebelum "
                "baris 'Dikurangi: cadangan kerugian penurunan nilai' / 'Less: allowance for impairment losses' "
                "(meskipun sel label baris subtotal tersebut kosong), kutip langsung angka subtotal itu di "
                "`raw_value` (`component_operation='none'`); "
                "(b) jika baris tabel tertulis 'setelah dikurangi cadangan kerugian penurunan nilai sebesar ...' "
                "(berarti kolom angka adalah Kredit NETO, bukan Bruto!), JANGAN hanya mengutip Kredit Neto — "
                "masukkan seluruh angka Kredit Neto tahun target (mis. Pihak berelasi + Pihak ketiga) "
                "DITAMBAH nilai CKPN tahun target tersebut (cukup SATU KALI walau keterangan baris diulang "
                "di sub-baris) ke dalam `components` dengan `component_operation='sum'` agar Python "
                "menghitung Kredit Bruto = Kredit Neto + CKPN."
            ),
            abs_value=True,
            gate4=True,
            allow_components=True,
        ),
        MetricSpec(
            key="deposits_bank",
            label="Dana Pihak Ketiga / Simpanan Nasabah (Bank)",
            basis="bank_only",
            description=(
                "Total Simpanan dari Nasabah / Dana Pihak Ketiga (DPK) pada sisi Liabilitas Laporan "
                "Posisi Keuangan Entitas Induk (Bank saja), BUKAN Simpanan dari bank lain dan BUKAN "
                "konsolidasian. Jika tidak ada satu baris total dan hanya terpecah menjadi Pihak berelasi "
                "dan Pihak ketiga (atau Giro + Tabungan + Deposito), kutip komponen-komponennya di "
                "`components` dengan `component_operation='sum'`."
            ),
            abs_value=True,
            gate4=True,
            allow_components=True,
        ),
        MetricSpec(
            key="npl_amount_bank",
            label="Kredit Bermasalah / NPL Nominal Bruto (Bank)",
            basis="bank_only",
            description=(
                "Nominal total kredit bermasalah bruto / Non-Performing Loan (kolektibilitas Kurang "
                "Lancar + Diragukan + Macet) basis Bank saja (bukan rasio persen). Jika hanya tersedia "
                "rincian Kurang Lancar, Diragukan, dan Macet tanpa baris total, kutip ketiganya di "
                "`components` dengan `component_operation='sum'`."
            ),
            abs_value=True,
            gate4=True,
            allow_components=True,
        ),
        # --- Metrik pelengkap untuk 6 rasio SEOJK (Minggu 11) ---
        MetricSpec(
            key="total_capital_bank",
            label="Total Modal (Bank)",
            basis="bank_only",
            description=(
                "Total Modal (Modal Inti + Modal Pelengkap) pada tabel KPMM / Struktur Permodalan, "
                "WAJIB kolom Bank / Entitas Induk saja (BUKAN kolom Konsolidasian)."
            ),
        ),
        MetricSpec(
            key="ckpn_loans_bank",
            label="CKPN Kredit yang Diberikan (Bank)",
            basis="bank_only",
            description=(
                "Cadangan Kerugian Penurunan Nilai (CKPN) atas kredit yang diberikan pada Laporan "
                "Posisi Keuangan Entitas Induk (Bank saja)."
            ),
            abs_value=True,
        ),
        MetricSpec(
            key="earning_assets",
            label="Total Aset Produktif",
            basis="consolidated",
            description=(
                "Total Aset Produktif pada tabel Ikhtisar Data Keuangan (jika tercetak sebagai satu baris; "
                "isi null jika tidak tercetak langsung)."
            ),
        ),
        MetricSpec(
            key="total_assets_bank",
            label="Total Aset (Bank / Entitas Induk)",
            basis="bank_only",
            description="Total Aset / Jumlah Aset pada Laporan Posisi Keuangan Entitas Induk (Bank saja).",
        ),
        MetricSpec(
            key="net_interest_income_bank",
            label="Pendapatan Bunga Neto (Bank / Entitas Induk)",
            basis="bank_only",
            description="Pendapatan Bunga Bersih / Neto pada Laporan Laba Rugi Entitas Induk (Bank saja).",
        ),
        MetricSpec(
            key="profit_before_tax_bank",
            label="Laba Sebelum Pajak (Bank / Entitas Induk)",
            basis="bank_only",
            description="Laba Sebelum Beban Pajak Penghasilan pada Laporan Laba Rugi Entitas Induk (Bank saja).",
        ),
        MetricSpec(
            key="net_income_bank",
            label="Laba Bersih / Laba Tahun Berjalan (Bank / Entitas Induk)",
            basis="bank_only",
            description="Laba Bersih / Laba Tahun Berjalan pada Laporan Laba Rugi Entitas Induk (Bank saja).",
        ),
    )
}

_BANK_GROUPS = (
    ExtractionGroup(
        group_id="consolidated_highlights",
        title="Ikhtisar & Laporan Keuangan Konsolidasian",
        search_queries=(
            "ikhtisar data keuangan total aset laporan posisi keuangan konsolidasian jumlah aset",
            "laporan laba rugi konsolidasian pendapatan bunga bersih laba bersih laba tahun berjalan",
        ),
        metric_keys=("total_assets", "net_interest_income", "net_income", "earning_assets"),
        top_k=4,
    ),
    ExtractionGroup(
        group_id="capital_bank",
        title="Permodalan KPMM (Basis Bank)",
        search_queries=(
            "kewajiban penyediaan modal minimum KPMM modal inti tier 1 total modal ATMR bank",
        ),
        metric_keys=("tier1_capital_bank", "total_capital_bank", "rwa_bank"),
        top_k=4,
    ),
    ExtractionGroup(
        group_id="parent_loans_deposits",
        title="Kredit, CKPN, DPK, & Aset Entitas Induk (Basis Bank)",
        search_queries=(
            "laporan posisi keuangan entitas induk aset kas giro pada bank indonesia kredit yang diberikan jumlah aset",
            "laporan posisi keuangan entitas induk liabilitas simpanan dari nasabah deposits from customers parent entity",
        ),
        metric_keys=("gross_loans_bank", "ckpn_loans_bank", "deposits_bank", "total_assets_bank"),
        top_k=4,
    ),
    ExtractionGroup(
        group_id="npl_bank",
        title="Kredit Bermasalah / NPL Nominal (Basis Bank)",
        search_queries=(
            "kredit bermasalah NPL gross kurang lancar diragukan macet kolektibilitas bank",
        ),
        metric_keys=("npl_amount_bank",),
        top_k=4,
        prefer_tables=False,
    ),
    ExtractionGroup(
        group_id="parent_income_bank",
        title="Laba Rugi Entitas Induk (Basis Bank)",
        search_queries=(
            "laporan laba rugi entitas induk pendapatan bunga neto laba sebelum beban pajak laba tahun berjalan parent entity",
        ),
        metric_keys=("net_interest_income_bank", "profit_before_tax_bank", "net_income_bank"),
        top_k=4,
    ),
)

_BANK_FORMULAS: dict[str, RatioFormula] = {
    f.name: f
    for f in (
        RatioFormula(
            name="CAR",
            label="Capital Adequacy Ratio (KPMM)",
            expression="(total_capital / rwa) * 100",
            inputs=(
                ("total_capital", ("total_capital_bank",)),
                ("rwa", ("rwa_bank",)),
            ),
            positive_vars=("rwa",),
            basis_description="Bank saja (Catatan KPMM — saldo akhir)",
        ),
        RatioFormula(
            name="ROA",
            label="Return on Assets (SEOJK — Laba Sebelum Pajak)",
            expression="(profit_before_tax / total_assets) * 100",
            inputs=(
                ("profit_before_tax", ("profit_before_tax_bank", "profit_before_tax")),
                ("total_assets", ("total_assets_bank", "total_assets")),
            ),
            average_vars=("total_assets",),
            positive_vars=("total_assets",),
            basis_description="Bank saja / Konsolidasian (rata-rata total aset, standar SEOJK PBT)",
            notes="Sesuai SEOJK No.9/SEOJK.03/2020 memakai Laba Sebelum Pajak; sebagian bank melaporkan catatan kaki ROA setelah pajak.",
        ),
        RatioFormula(
            name="ROE",
            label="Return on Equity (SEOJK — Modal Inti Tier 1)",
            expression="(net_income / tier1_capital) * 100",
            inputs=(
                ("net_income", ("net_income_bank", "net_income")),
                ("tier1_capital", ("tier1_capital_bank",)),
            ),
            average_vars=("tier1_capital",),
            positive_vars=("tier1_capital",),
            basis_description="Bank saja (rata-rata Modal Inti Tier 1)",
        ),
        RatioFormula(
            name="NIM",
            label="Net Interest Margin",
            expression="(net_interest_income / earning_assets) * 100",
            inputs=(
                ("net_interest_income", ("net_interest_income_bank", "net_interest_income")),
                ("earning_assets", ("earning_assets",)),
            ),
            average_vars=("earning_assets",),
            positive_vars=("earning_assets",),
            basis_description="Pendapatan bunga neto dibagi rata-rata aset produktif",
            notes="Apabila aset produktif tidak tercetak langsung di laporan, rasio ditolak dengan status insufficient_data.",
        ),
        RatioFormula(
            name="NPL",
            label="Non-Performing Loan (Bruto)",
            expression="(npl_amount / gross_loans) * 100",
            inputs=(
                ("npl_amount", ("npl_amount_bank",)),
                ("gross_loans", ("gross_loans_bank",)),
            ),
            positive_vars=("gross_loans",),
            basis_description="Bank saja (NPL bruto KL+D+Macet dibagi kredit bruto Bank)",
        ),
        RatioFormula(
            name="LDR",
            label="Loan to Deposit Ratio",
            expression="(gross_loans / deposits) * 100",
            inputs=(
                ("gross_loans", ("gross_loans_bank",)),
                ("deposits", ("deposits_bank",)),
            ),
            positive_vars=("deposits",),
            basis_description="Bank saja (kredit bruto Bank dibagi DPK Bank)",
        ),
    )
}

# Varian ROA setelah pajak (opsional eksplisit untuk perbandingan bimbingan 1.6 / Bab 4 -- BUKAN per emiten)
BANK_ROA_AFTER_TAX_FORMULA = RatioFormula(
    name="ROA",
    label="Return on Assets (Laba Setelah Pajak)",
    expression="(net_income / total_assets) * 100",
    inputs=(
        ("net_income", ("net_income_bank", "net_income")),
        ("total_assets", ("total_assets_bank", "total_assets")),
    ),
    average_vars=("total_assets",),
    positive_vars=("total_assets",),
    basis_description="Laba setelah pajak dibagi rata-rata total aset",
    notes="Varian ROA setelah pajak (alternatif untuk uji sensitivitas definisi Bab 4).",
)

BANK_PROFILE = SectorProfile(
    sector="bank",
    label="Perbankan Konvensional (SEOJK No.9/SEOJK.03/2020)",
    validated=True,
    warning_label=None,
    metrics=_BANK_METRICS,
    extraction_groups=_BANK_GROUPS,
    ratio_names=("CAR", "ROA", "ROE", "NIM", "NPL", "LDR"),
    formulas=_BANK_FORMULAS,
)


# ----------------------------------------------------------------- Profil UMUM (non-bank, belum divalidasi)

_GENERAL_METRICS = {
    m.key: m
    for m in (
        MetricSpec(
            key="total_assets",
            label="Total Aset (Konsolidasian)",
            basis="consolidated",
            description="Total Aset / Jumlah Aset pada Laporan Posisi Keuangan Konsolidasian.",
        ),
        MetricSpec(
            key="total_equity",
            label="Total Ekuitas (Konsolidasian)",
            basis="consolidated",
            description="Total Ekuitas / Jumlah Ekuitas pada Laporan Posisi Keuangan Konsolidasian.",
        ),
        MetricSpec(
            key="net_income",
            label="Laba Bersih / Laba Tahun Berjalan (Konsolidasian)",
            basis="consolidated",
            description="Laba Bersih / Laba Tahun Berjalan konsolidasian pada Laporan Laba Rugi Konsolidasian.",
        ),
    )
}

_GENERAL_FORMULAS: dict[str, RatioFormula] = {
    f.name: f
    for f in (
        RatioFormula(
            name="ROA",
            label="Return on Assets (Profil Umum — belum divalidasi)",
            expression="(net_income / total_assets) * 100",
            inputs=(
                ("net_income", ("net_income",)),
                ("total_assets", ("total_assets",)),
            ),
            average_vars=("total_assets",),
            positive_vars=("total_assets",),
            basis_description="Konsolidasian (profil umum non-bank, belum divalidasi)",
        ),
        RatioFormula(
            name="ROE",
            label="Return on Equity (Profil Umum — belum divalidasi)",
            expression="(net_income / total_equity) * 100",
            inputs=(
                ("net_income", ("net_income",)),
                ("total_equity", ("total_equity",)),
            ),
            average_vars=("total_equity",),
            positive_vars=("total_equity",),
            basis_description="Konsolidasian (profil umum non-bank, belum divalidasi)",
        ),
    )
}

GENERAL_PROFILE = SectorProfile(
    sector="general",
    label="Profil Umum Non-Bank",
    validated=False,
    warning_label="Profil umum (belum divalidasi — bukan rasio perbankan OJK, hanya ROA & ROE dasar).",
    metrics=_GENERAL_METRICS,
    extraction_groups=(
        ExtractionGroup(
            group_id="general_financials",
            title="Laporan Posisi Keuangan & Laba Rugi Konsolidasian",
            search_queries=(
                "laporan posisi keuangan konsolidasian jumlah aset total aset jumlah ekuitas total ekuitas",
                "laporan laba rugi konsolidasian laba tahun berjalan laba bersih",
            ),
            metric_keys=("total_assets", "total_equity", "net_income"),
            top_k=4,
        ),
    ),
    ratio_names=("ROA", "ROE"),
    formulas=_GENERAL_FORMULAS,
)


# ----------------------------------------------------------------- Ambang batas prudensial OJK (tugas 11.6)

def interpret_ratio(ratio_name: str, value: float, profile: SectorProfile = BANK_PROFILE) -> dict[str, Any]:
    """Interpretasi deterministik rasio terhadap ambang batas prudensial OJK (Tabel 2.2 / SEOJK)."""
    name = ratio_name.strip().upper()
    val_str = f"{value:.2f}%".replace(".", ",")

    if not profile.validated:
        warn = profile.warning_label or "Profil umum (belum divalidasi)."
        return {
            "category": "belum_divalidasi",
            "meets_ojk": None,
            "benchmark": None,
            "summary": f"{name} {val_str} — {warn}",
        }

    if name == "CAR":
        bench = "batas minimum OJK 8% (POJK KPMM)"
        if value >= 15.0:
            cat, ok, desc = "sangat_kuat", True, "jauh di atas batas minimum OJK 8%, permodalan sangat kuat"
        elif value >= 12.0:
            cat, ok, desc = "kuat", True, "di atas batas minimum OJK 8%, permodalan kuat"
        elif value >= 8.0:
            cat, ok, desc = "memenuhi_minimum", True, "memenuhi batas minimum OJK 8%"
        else:
            cat, ok, desc = "di_bawah_minimum_ojk", False, "di bawah batas minimum OJK 8% (permodalan tidak memadai)"
    elif name == "ROA":
        bench = "ambang sangat sehat > 1,5% (SEOJK Tingkat Kesehatan Bank)"
        if value > 1.5:
            cat, ok, desc = "sangat_sehat", True, "di atas ambang sangat sehat > 1,5%, profitabilitas aset sangat kuat"
        elif value > 1.25:
            cat, ok, desc = "sehat", True, "berada pada kategori sehat (1,25–1,5%)"
        elif value > 0.5:
            cat, ok, desc = "cukup_sehat", True, "berada pada kategori cukup sehat (0,5–1,25%)"
        else:
            cat, ok, desc = "kurang_sehat", False, "≤ 0,5%, profitabilitas aset kurang sehat"
    elif name == "ROE":
        bench = "acuan sangat baik > 15%"
        if value > 15.0:
            cat, ok, desc = "sangat_baik", True, "di atas 15%, tingkat pengembalian modal inti sangat baik"
        elif value >= 10.0:
            cat, ok, desc = "baik", True, "berada pada rentang 10–15%, pengembalian modal baik"
        elif value >= 5.0:
            cat, ok, desc = "cukup", True, "berada pada rentang 5–10%, pengembalian modal cukup"
        else:
            cat, ok, desc = "rendah", False, "di bawah 5%, tingkat pengembalian modal rendah"
    elif name == "NIM":
        bench = "acuan sehat > 3% (> 5% sangat kuat)"
        if value > 5.0:
            cat, ok, desc = "sangat_kuat", True, "di atas 5%, margin intermediasi bunga sangat kuat"
        elif value >= 3.0:
            cat, ok, desc = "sehat", True, "berada pada rentang 3–5%, margin bunga sehat"
        elif value >= 2.0:
            cat, ok, desc = "cukup", True, "berada pada rentang 2–3%, margin bunga cukup"
        else:
            cat, ok, desc = "tertekan", False, "di bawah 2%, margin intermediasi bunga tertekan"
    elif name == "NPL":
        bench = "batas maksimum OJK < 5% (< 2% sangat sehat)"
        if value < 2.0:
            cat, ok, desc = "sangat_sehat", True, "jauh di bawah batas maksimum OJK 5% (< 2%), kualitas kredit sangat sehat"
        elif value < 5.0:
            cat, ok, desc = "aman_ojk", True, "berada di bawah batas maksimum OJK 5%, kualitas kredit terkendali"
        else:
            cat, ok, desc = "melampaui_batas_ojk", False, "mencapai/melampaui batas maksimum OJK 5% (risiko kredit tinggi)"
    elif name == "LDR":
        bench = "rentang ideal BI/OJK 78–92%"
        if value < 78.0:
            cat, ok, desc = "likuiditas_longgar", True, "di bawah rentang ideal BI/OJK 78–92%, likuiditas longgar namun intermediasi belum optimal"
        elif value <= 92.0:
            cat, ok, desc = "ideal_ojk", True, "berada dalam rentang ideal BI/OJK 78–92%, intermediasi dan likuiditas seimbang"
        else:
            cat, ok, desc = "likuiditas_ketat", False, "di atas batas atas ideal BI/OJK 92%, likuiditas cenderung ketat"
    else:
        return {
            "category": "tidak_terdefinisi",
            "meets_ojk": None,
            "benchmark": None,
            "summary": f"{name} {val_str}.",
        }

    return {
        "category": cat,
        "meets_ojk": ok,
        "benchmark": bench,
        "summary": f"{name} {val_str} → {desc}.",
    }


def get_profile(sector: str | None) -> SectorProfile:
    """Pilih profil ekstraksi/rasio dari metadata `sector` (hasil detect_metadata.py)."""
    key = (sector or "").strip().lower()
    if key in config.VALIDATED_SECTORS and key == "bank":
        return BANK_PROFILE
    return GENERAL_PROFILE


def gate4_metric_keys(profile: SectorProfile = BANK_PROFILE) -> list[str]:
    """Daftar 8 metrik wajib GATE 4 pada profil bank."""
    return [k for k, spec in profile.metrics.items() if spec.gate4]


def groups_for_metrics(profile: SectorProfile, metric_keys: Sequence[str] | None = None) -> list[tuple[ExtractionGroup, list[MetricSpec]]]:
    """Saring kelompok ekstraksi yang memuat metrik target (agar tidak membuang token pada kelompok tak perlu)."""
    wanted = set(metric_keys) if metric_keys is not None else set(profile.metrics)
    unknown = wanted - set(profile.metrics)
    if unknown:
        raise ValueError(f"metric_key tidak ada di profil '{profile.sector}': {sorted(unknown)}")
    plan = []
    for group in profile.extraction_groups:
        specs = [profile.metrics[k] for k in group.metric_keys if k in wanted]
        if specs:
            plan.append((group, specs))
    return plan
