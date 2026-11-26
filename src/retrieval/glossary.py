"""
Tugas 7 (Keputusan 7.A) -- perluasan istilah perbankan untuk query.  docs/PANDUAN_MINGGU7.md, Langkah 2.

Laporan keuangan menulis istilah LENGKAP ("cadangan kerugian penurunan nilai", "simpanan dari
nasabah"), sedangkan pengguna dan agen menulis singkatan ("CKPN", "DPK"). Singkatan yang tidak
tertulis di laporan tidak ditemukan oleh dense maupun BM25 (Minggu 6 Langkah 5: "CKPN" -> hal 738
tidak masuk 10 besar; "cadangan kerugian penurunan nilai" -> BM25 peringkat 1). Prototipe Minggu 7:
Hit@5 hybrid 11/15 -> 13/15 dengan perluasan.

Daftar disusun dari istilah perbankan BAKU (OJK/SEOJK, nama rasio di laporan tahunan bank), BUKAN
dari query uji yang gagal. Khusus perbankan (sektor yang divalidasi); di query sektor lain
istilahnya tidak muncul, jadi tidak berpengaruh.

Satu KELOMPOK = beberapa singkatan bersinonim + satu teks istilah lengkap. Aturannya:
  - singkatan dicocokkan sebagai KATA UTUH, huruf besar/kecil sama saja ("car" tidak cocok dengan
    "Carrefour" atau "card");
  - satu kelompok ditambahkan sekali saja, dan dilewati kalau teksnya sudah ada di query;
  - teks sebuah kelompok tidak memuat singkatan kelompok lain.
  Akibatnya expand_query IDEMPOTEN: memperluas query yang sudah diperluas tidak mengubah apa pun
  (agen boleh memanggilnya berulang).

Format sama dengan prototipe: query + " (istilah; istilah)". Query yang diperluas dipakai untuk
dense DAN BM25.
"""

import re

# (singkatan, istilah lengkap seperti tertulis di laporan)
BANK_TERMS: list[tuple[tuple[str, ...], str]] = [
    (("ckpn",), "cadangan kerugian penurunan nilai"),
    (("dpk",), "dana pihak ketiga simpanan dari nasabah"),
    (("npl",), "kredit bermasalah non performing loan"),
    (("car", "kpmm"), "kewajiban penyediaan modal minimum kpmm capital adequacy ratio car rasio kecukupan modal"),
    (("atmr",), "aset tertimbang menurut risiko"),
    (("ldr",), "loan to deposit ratio rasio kredit terhadap dana pihak ketiga"),
    (("roe",), "return on equity tingkat pengembalian atas ekuitas"),
    (("roa",), "return on asset tingkat pengembalian atas aset"),
    (("nim",), "net interest margin marjin bunga bersih"),
    (("bopo",), "beban operasional terhadap pendapatan operasional"),
    (("casa",), "current account saving account giro dan tabungan"),
    (("lcr",), "liquidity coverage ratio rasio kecukupan likuiditas"),
    (("nsfr",), "net stable funding ratio rasio pendanaan stabil bersih"),
    (("gwm",), "giro wajib minimum"),
    (("pdn",), "posisi devisa neto"),
    (("bmpk",), "batas maksimum pemberian kredit"),
    (("cir",), "cost to income ratio"),
    (("lar",), "loan at risk"),
]

WORD = re.compile(r"[a-z]+")


def expansions(query: str) -> list[str]:
    """Istilah lengkap yang akan ditambahkan ke `query` (kosong = query tidak berubah)."""
    lowered = query.lower()
    words = set(WORD.findall(lowered))
    return [text for keys, text in BANK_TERMS if words & set(keys) and text not in lowered]


def expand_query(query: str) -> str:
    """query + " (istilah lengkap; ...)" untuk setiap singkatan perbankan di query. Idempoten."""
    found = expansions(query)
    return f"{query} ({'; '.join(found)})" if found else query
