"""
Langkah 1 Minggu 9 (Keputusan 9.A, tugas 9.3) -- parser angka Indonesia, normalisasi satuan,
dan verifikasi grounding terhadap teks chunk.  docs/PANDUAN_MINGGU9-10.md, Langkah 1.

Seluruh konversi angka dan penjumlahan komponen dilakukan oleh KODE PYTHON deterministik, BUKAN LLM.
Alasan (temuan uji 2.5b): `openai/gpt-oss-120b` salah membaca format angka Indonesia ("239.468,855"
menjadi 239.468855) pada 5/5 percobaan dan menyisipkan spasi sempit Unicode U+202F ("Rp\\u202f54.851").

Aturan:
  - LLM cukup mengutip teks angka mentah (`raw_value`, atau `components`) persis seperti di chunk;
  - `is_grounded_in_text()` memastikan angka mentah tersebut benar-benar muncul di teks chunk sumber;
  - `parse_indonesian_number()` mengubah string format Indonesia/Inggris menjadi float;
  - `normalize_to_million_idr()` menyamakan seluruh nominal ke JUTA Rupiah (`million_idr`).
"""

import re
from collections.abc import Sequence

# Spasi Unicode (termasuk narrow no-break space U+202F dari gpt-oss) & tanda pemisah tak tampak
INVISIBLE_SPACES = re.compile(r"[\u00a0\u2007\u2009\u200a\u202f\ufeff]")
NULL_TOKENS = frozenset({"", "-", "–", "—", "n/a", "na", "null", "none", "nil", "tidak tersedia", "tidak ada"})

UNIT_TO_MILLION_IDR: dict[str, float] = {
    "idr": 1e-6,
    "thousand_idr": 1e-3,
    "million_idr": 1.0,
    "billion_idr": 1_000.0,
    "trillion_idr": 1_000_000.0,
}

# Token angka inti: boleh titik ribuan / koma desimal, minimal satu digit
CORE_NUMBER_RE = re.compile(r"^\d+(?:[.,]\d+)*$")


def normalize_spaces(text: str) -> str:
    """Ganti spasi Unicode (U+202F, NBSP, dll.) menjadi spasi biasa."""
    return INVISIBLE_SPACES.sub(" ", text)


def extract_numeric_core(raw: str | None) -> tuple[str | None, bool, bool]:
    """Bersihkan string angka mentah -> (token_angka_inti | None, is_negative, has_percent).

    Contoh:
      "Rp\u202f54.851"     -> ("54.851", False, False)
      "(33.168.491)"       -> ("33.168.491", True, False)
      "-1.234,50"          -> ("1.234,50", True, False)
      "29,36%"             -> ("29,36", False, True)
      "-"                  -> (None, False, False)
    """
    if raw is None:
        return None, False, False
    if not isinstance(raw, str):
        raise ValueError(f"raw_value harus string atau None, bukan {type(raw).__name__}")

    s = normalize_spaces(raw).strip()
    if s.lower() in NULL_TOKENS:
        return None, False, False

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()

    # Hapus awalan/akhiran mata uang umum & tanda persen
    has_percent = s.endswith("%")
    if has_percent:
        s = s[:-1].strip()

    s = re.sub(r"(?i)^(?:rp\.?|idr)\s*", "", s).strip()
    s = re.sub(r"(?i)\s*(?:rp\.?|idr)$", "", s).strip()

    if s.startswith(("(",)) and s.endswith((")",)):
        negative = True
        s = s[1:-1].strip()
    if s.startswith(("-", "−", "–")):
        negative = True
        s = s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()

    # Buang spasi yang mungkin terselip di dalam angka ("54 851" hanya bila terpisah spasi biasa
    # tidak digabung diam-diam kecuali spasi tepi sudah dibuang; spasi ribuan bukan standar di PDF IDX)
    s = s.strip()
    if s.lower() in NULL_TOKENS:
        return None, False, has_percent
    if not CORE_NUMBER_RE.match(s):
        raise ValueError(f"format angka tidak valid: {raw!r} (tersisa {s!r})")
    return s, negative, has_percent


def parse_indonesian_number(raw: str | None, *, is_percent: bool = False) -> float | None:
    """Konversi teks angka laporan Indonesia/dwibahasa menjadi float (atau None untuk tanda kosong).

    Aturan pemisah:
      - Ada '.' dan ',' : pemisah yang paling kanan adalah desimal
          ("239.468,855" -> 239468.855; "239,468.855" -> 239468.855)
      - Hanya ','       : koma ganda ("1,234,567") = ribuan Inggris; koma tunggal ("29,36") = desimal
      - Hanya '.'       : titik ganda ("239.468.855") = ribuan Indonesia;
                          titik tunggal: pada persen = desimal ("20.10" -> 20.10);
                          pada nominal dengan pola 1..3 digit + '.' + 3 digit dan bagian kiri != '0'
                          ("54.851", "992.901") = ribuan Indonesia; selain itu desimal ("54.8", "0.500").
    """
    core, negative, has_pct = extract_numeric_core(raw)
    if core is None:
        return None

    pct = is_percent or has_pct
    has_dot = "." in core
    has_comma = "," in core

    if has_dot and has_comma:
        if core.rfind(",") > core.rfind("."):
            # Indonesia: 1.234.567,89
            int_part, dec_part = core.rsplit(",", 1)
            groups = int_part.split(".")
            if any(len(g) != 3 for g in groups[1:]):
                raise ValueError(f"pengelompokan ribuan Indonesia tidak valid: {raw!r}")
            num_str = "".join(groups) + "." + dec_part
        else:
            # Inggris: 1,234,567.89
            int_part, dec_part = core.rsplit(".", 1)
            groups = int_part.split(",")
            if any(len(g) != 3 for g in groups[1:]):
                raise ValueError(f"pengelompokan ribuan Inggris tidak valid: {raw!r}")
            num_str = "".join(groups) + "." + dec_part
    elif has_comma:
        if core.count(",") > 1:
            groups = core.split(",")
            if any(len(g) != 3 for g in groups[1:]):
                raise ValueError(f"pengelompokan koma tidak valid: {raw!r}")
            num_str = "".join(groups)
        else:
            num_str = core.replace(",", ".")
    elif has_dot:
        if core.count(".") > 1:
            groups = core.split(".")
            if any(len(g) != 3 for g in groups[1:]):
                raise ValueError(f"pengelompokan ribuan titik tidak valid: {raw!r}")
            num_str = "".join(groups)
        else:
            left, right = core.split(".")
            if not pct and len(right) == 3 and 1 <= len(left) <= 3 and left != "0":
                num_str = left + right
            else:
                num_str = core
    else:
        num_str = core

    val = float(num_str)
    return -val if negative else val


def normalize_to_million_idr(value: float, unit: str | None) -> float:
    """Normalisasi nominal uang ke satuan standar JUTA Rupiah (`million_idr`)."""
    if unit not in UNIT_TO_MILLION_IDR:
        raise ValueError(f"satuan nominal tidak dikenal atau kosong: {unit!r} "
                         f"(didukung: {sorted(UNIT_TO_MILLION_IDR)})")
    return round(float(value) * UNIT_TO_MILLION_IDR[unit], 6)


def is_grounded_in_text(raw_value: str | None, chunk_text: str) -> bool:
    """Pastikan token angka mentah benar-benar muncul di teks chunk sumber (pagar anti-halusinasi).

    Tepi angka dibatasi supaya "54.851" tidak cocok secara palsu di dalam "254.851" atau "54.851.274".
    """
    if not chunk_text:
        return False
    try:
        core, _, _ = extract_numeric_core(raw_value)
    except ValueError:
        return False
    if core is None:
        return False
    clean_text = normalize_spaces(chunk_text)
    pat = re.compile(rf"(?<![\d.,]){re.escape(core)}(?![\d,]|\.\d)")
    return bool(pat.search(clean_text))


def normalize_extraction(
    raw_value: str | None,
    unit: str | None,
    *,
    components: Sequence[str] | None = None,
    operation: str = "none",
    is_percent: bool = False,
    abs_value: bool = False,
) -> float | None:
    """Ubah `raw_value` atau daftar `components` (penjumlahan Python) ke nilai terstandar.

    - Jika `is_percent=True` (atau `unit == 'percent'`): kembalikan nilai persen (float).
    - Jika nominal uang: kembalikan nilai dalam **juta Rupiah** (`million_idr`).
    - Jika `components` terisi & `operation == 'sum'`: parse tiap komponen lalu jumlahkan di Python.
    """
    pct = is_percent or (unit == "percent")
    if components and operation == "sum":
        parsed = []
        for item in components:
            v = parse_indonesian_number(item, is_percent=pct)
            if v is None:
                raise ValueError(f"komponen tidak boleh kosong/null: {item!r}")
            parsed.append(abs(v) if abs_value else v)
        total = sum(parsed)
        return round(total, 6) if pct else normalize_to_million_idr(total, unit)

    val = parse_indonesian_number(raw_value, is_percent=pct)
    if val is None:
        return None
    if abs_value:
        val = abs(val)
    return round(val, 6) if pct else normalize_to_million_idr(val, unit)
