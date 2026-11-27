"""
Langkah 2 Minggu 9 (tugas 9.1 & 9.4) -- state bersama LangGraph (`AgentState`) dan skema Pydantic
untuk ekstraksi terstruktur.  docs/PANDUAN_MINGGU9-10.md, Langkah 2a.

Dipakai bersama oleh seluruh 4 agent (Minggu 9-15):
  - Extraction Agent (Minggu 9-10) mengisi `extracted_data`, `retrieved_chunks`, `extraction_errors`,
    `extraction_retries`, dan `extraction_stats`;
  - Financial Analyst Agent (Minggu 11-12) mengisi `ratios`;
  - Market Observer Agent (Minggu 13) mengisi `market_context`;
  - Reporting Agent (Minggu 14) mengisi `report`.
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

UnitType = Literal["million_idr", "billion_idr", "thousand_idr", "trillion_idr", "idr", "percent"]
BasisType = Literal["bank_only", "consolidated", "unknown"]
MetricStatus = Literal["ok", "not_found", "ungrounded", "parse_error", "unit_conflict"]


class RawMetricExtraction(BaseModel):
    """Keluaran langsung LLM per metrik -- hanya kutipan teks mentah & sitasi, TANPA konversi skala."""

    metric_key: str = Field(description="Kunci metrik persis sesuai daftar yang diminta.")
    raw_value: str | None = Field(
        default=None,
        description="Teks angka persis seperti tercetak di chunk (mis. '239.468.855'), atau null jika tidak ditemukan.",
    )
    components: list[str] | None = Field(
        default=None,
        description="Daftar teks angka penyusun persis dari chunk bila subtotal tidak tercetak langsung (mis. kredit neto + CKPN).",
    )
    component_operation: Literal["sum", "none"] = Field(
        default="none",
        description="Isi 'sum' jika `components` harus dijumlahkan oleh Python; selain itu 'none'.",
    )
    unit: UnitType | None = Field(
        default=None,
        description="Satuan angka pada chunk sumber (ambil dari header [unit=...] atau judul tabel), atau null jika tak ditemukan.",
    )
    basis: BasisType = Field(
        default="unknown",
        description="Basis pelaporan angka yang dikutip: 'bank_only' (Entitas Induk / Bank saja), 'consolidated', atau 'unknown'.",
    )
    source_chunk_id: str | None = Field(
        default=None,
        description="ID chunk persis dari header [CHUNK ... | id=...], atau null jika tidak ditemukan.",
    )
    source_pages: list[int] = Field(
        default_factory=list,
        description="Daftar nomor halaman PDF asli dari header [hal=...] chunk sumber.",
    )
    source_header: str | None = Field(
        default=None,
        description="Judul tabel/bagian tempat angka ditemukan.",
    )
    notes: str | None = Field(
        default=None,
        description="Catatan singkat jika ada hal penting (mis. alasan null, komponen, atau penyesuaian kolom).",
    )


class GroupExtractionOutput(BaseModel):
    """Keluaran terstruktur LLM untuk satu kelompok metrik."""

    items: list[RawMetricExtraction] = Field(
        description="Daftar hasil ekstraksi, satu entri untuk setiap metrik yang diminta."
    )


class NormalizedMetric(BaseModel):
    """Hasil ekstraksi setelah diverifikasi grounding & dinormalisasi oleh kode Python (Keputusan 9.A)."""

    metric_key: str
    value_million_idr: float | None = None
    value_percent: float | None = None
    raw_value: str | None = None
    components: list[str] | None = None
    original_unit: UnitType | None = None
    chunk_unit: str | None = None
    basis: BasisType = "unknown"
    source_chunk_id: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    source_header: str | None = None
    merged_cells_warning: bool = False
    grounded: bool = False
    status: MetricStatus = "not_found"
    notes: str | None = None


class AgentState(TypedDict, total=False):
    """State bersama LangGraph untuk keempat agent (tugas 9.1)."""

    query: str
    ticker: str                                          # wajib: pagar isolasi antar emiten
    sector: str                                          # dari detect_metadata: 'bank', 'non_financial', dst.
    year: int | list[int] | None                         # tahun target (1 tahun atau daftar tahun)
    extracted_data: dict[int, dict[str, dict[str, Any]]] # {year: {metric_key: NormalizedMetric.model_dump()}}
    retrieved_chunks: list[dict[str, Any]]               # jejak chunk untuk sitasi & RAGAS contexts (Minggu 17)
    extraction_errors: list[str]
    extraction_retries: int
    extraction_stats: dict[str, Any]                     # token, waktu, jumlah panggilan tool/LLM
    ratios: dict[str, Any]                               # diisi Financial Analyst Agent (Minggu 11)
    market_context: list[dict[str, Any]]                 # diisi Market Observer Agent (Minggu 13)
    report: str                                          # diisi Reporting Agent (Minggu 14)
    messages: Annotated[list[AnyMessage], add_messages]
