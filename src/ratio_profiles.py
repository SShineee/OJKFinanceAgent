"""
Langkah 2 Minggu 9 (tugas 9.5 & 9.5b; dilanjutkan formula rasio di Minggu 11 tugas 11.2) --
profil ekstraksi & rasio per sektor.  docs/PANDUAN_MINGGU9.md, Langkah 2b.

ATURAN DISIPLIN DATA UJI (9.5):
  File ini TIDAK BOLEH menyebut nama emiten, kode saham, nomor halaman, atau nomor Catatan tertentu.
  Seluruh deskripsi metrik dan query retrieval bersifat 100% generik (semantik standar OJK/PSAK).

Dua profil disediakan sesuai keputusan ruang lingkup (config.VALIDATED_SECTORS):
  - `bank`    (validated=True)  : 8 metrik inti GATE 4 + metrik pelengkap 6 rasio SEOJK (CAR, ROA,
                                  ROE, NIM, NPL, LDR);
  - `general` (validated=False) : 3 metrik dasar (laba bersih, total aset, total ekuitas) untuk
                                  emiten non-bank, diberi label jelas "belum divalidasi".
"""

from collections.abc import Sequence
from dataclasses import dataclass

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
class SectorProfile:
    """Profil ekstraksi & daftar rasio untuk satu sektor emiten."""

    sector: str
    label: str
    validated: bool
    warning_label: str | None
    metrics: dict[str, MetricSpec]
    extraction_groups: tuple[ExtractionGroup, ...]
    ratio_names: tuple[str, ...]


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

BANK_PROFILE = SectorProfile(
    sector="bank",
    label="Perbankan Konvensional (SEOJK No.9/SEOJK.03/2020)",
    validated=True,
    warning_label=None,
    metrics=_BANK_METRICS,
    extraction_groups=_BANK_GROUPS,
    ratio_names=("CAR", "ROA", "ROE", "NIM", "NPL", "LDR"),
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

GENERAL_PROFILE = SectorProfile(
    sector="general",
    label="Profil Umum Non-Bank",
    validated=False,
    warning_label="Profil umum (belum divalidasi — hanya rasio dasar ROA & ROE).",
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
)


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
