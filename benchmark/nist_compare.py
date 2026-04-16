"""
benchmark/nist_compare.py

Compara os resultados experimentais do TCC (Python/liboqs, ARM64 Apple Silicon)
com os valores de referência oficiais das especificações NIST PQC:
  - CRYSTALS-Dilithium: Algorithm Specifications v3.1 (Ducas et al., fev. 2021)
    Table 1, Section 5.8 — Intel Core i7-6600U (Skylake) @ 2.6 GHz
    Mediana de 1.000 execuções; mensagens de 32 bytes
  - CRYSTALS-Kyber: Algorithm Specifications v3.02 (Avanzi et al., 2021)
    Table 2, Section 2.2 — Intel Core i7-4770K (Haswell) @ 3.492 GHz
    Mediana de 10.000 execuções

Uso:
    python -m benchmark.nist_compare
"""

from __future__ import annotations
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Conversão ciclos → milissegundos
# ---------------------------------------------------------------------------

def kcy_to_ms(kcy: float, freq_ghz: float) -> float:
    """Converte kilo-ciclos para milissegundos à frequência dada."""
    return (kcy * 1_000) / (freq_ghz * 1_000_000_000) * 1_000


def ratio(our_ms: float, nist_ms: float) -> float:
    """Razão our/nist. < 1 = somos mais rápidos; > 1 = somos mais lentos."""
    return our_ms / nist_ms


# ---------------------------------------------------------------------------
# Dados de referência NIST
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NistEntry:
    name: str
    platform: str
    freq_ghz: float
    keygen_kcy: float
    sign_or_encaps_kcy: float
    verify_or_decaps_kcy: float

    @property
    def keygen_ms(self) -> float:
        return kcy_to_ms(self.keygen_kcy, self.freq_ghz)

    @property
    def sign_ms(self) -> float:
        return kcy_to_ms(self.sign_or_encaps_kcy, self.freq_ghz)

    @property
    def verify_ms(self) -> float:
        return kcy_to_ms(self.verify_or_decaps_kcy, self.freq_ghz)


NIST_DATA: dict[str, NistEntry] = {
    "dilithium2_ref": NistEntry(
        name="Dilithium2 ref (sem AVX2)",
        platform="Intel Core i7-6600U (Skylake)",
        freq_ghz=2.6,
        keygen_kcy=300.751,
        sign_or_encaps_kcy=1081.174,   # mediana
        verify_or_decaps_kcy=327.362,
    ),
    "dilithium2_avx2": NistEntry(
        name="Dilithium2 AVX2",
        platform="Intel Core i7-6600U (Skylake)",
        freq_ghz=2.6,
        keygen_kcy=124.031,
        sign_or_encaps_kcy=259.172,    # mediana
        verify_or_decaps_kcy=118.412,
    ),
    "kyber512_ref": NistEntry(
        name="Kyber512 ref (sem AVX2)",
        platform="Intel Core i7-4770K (Haswell)",
        freq_ghz=3.492,
        keygen_kcy=122.684,
        sign_or_encaps_kcy=154.524,
        verify_or_decaps_kcy=187.960,
    ),
    "kyber512_avx2": NistEntry(
        name="Kyber512 AVX2",
        platform="Intel Core i7-4770K (Haswell)",
        freq_ghz=3.492,
        keygen_kcy=33.856,
        sign_or_encaps_kcy=45.200,
        verify_or_decaps_kcy=34.572,
    ),
}


# ---------------------------------------------------------------------------
# Nossos resultados (Phase 5b grand means — ARM64 Apple Silicon)
# ---------------------------------------------------------------------------

OUR_RESULTS: dict[str, dict[str, float]] = {
    "mldsa44": {
        "keygen_ms": 0.049,
        "sign_ms": 0.106,
        "verify_ms": 0.044,
    },
    "kyber512": {
        "keygen_ms": 0.018,
        "encaps_ms": 0.018,
        "decaps_ms": 0.016,
    },
}


# ---------------------------------------------------------------------------
# Tabelas de comparação
# ---------------------------------------------------------------------------

_SEP = "=" * 78


def print_dilithium_comparison() -> None:
    ref = NIST_DATA["dilithium2_ref"]
    avx2 = NIST_DATA["dilithium2_avx2"]
    our = OUR_RESULTS["mldsa44"]

    print(f"\n{_SEP}")
    print("ML-DSA-44 (Dilithium2) — Comparação com Referência NIST")
    print(_SEP)
    print(f"  Ref C:    {ref.platform} @ {ref.freq_ghz} GHz (sem AVX2)")
    print(f"  AVX2:     {avx2.platform} @ {avx2.freq_ghz} GHz (AVX2 otimizado)")
    print(f"  Nosso:    Apple Silicon ARM64, Python 3.13 / liboqs 0.15.0")
    print(f"  Fonte:    CRYSTALS-Dilithium v3.1, Table 1, Sec. 5.8 — medianas de 1.000 execuções")
    print()
    print(f"  {'Operação':<10} {'NIST ref (ms)':>14} {'NIST AVX2 (ms)':>15} {'Nosso ARM64 (ms)':>17} {'vs ref':>8} {'vs AVX2':>9}")
    print(f"  {'-'*10} {'-'*14} {'-'*15} {'-'*17} {'-'*8} {'-'*9}")

    rows = [
        ("KeyGen", ref.keygen_ms, avx2.keygen_ms, our["keygen_ms"]),
        ("Sign *", ref.sign_ms,   avx2.sign_ms,   our["sign_ms"]),
        ("Verify", ref.verify_ms, avx2.verify_ms, our["verify_ms"]),
    ]
    for name, r_ms, a_ms, o_ms in rows:
        r_ref  = ratio(o_ms, r_ms)
        r_avx2 = ratio(o_ms, a_ms)
        print(
            f"  {name:<10} {r_ms:>14.4f} {a_ms:>15.4f} {o_ms:>17.4f}"
            f" {r_ref:>7.2f}× {r_avx2:>8.2f}×"
        )

    print()
    print("  * Sign NIST = mediana (rejeição amostral gera alta variância; média ref ~25% maior)")
    print("  Nota: ratio < 1.0 = nosso ARM64 é mais rápido que a referência NIST")


def print_kyber_comparison() -> None:
    ref = NIST_DATA["kyber512_ref"]
    avx2 = NIST_DATA["kyber512_avx2"]
    our = OUR_RESULTS["kyber512"]

    print(f"\n{_SEP}")
    print("ML-KEM-512 (Kyber512) — Comparação com Referência NIST")
    print(_SEP)
    print(f"  Ref C:    {ref.platform} @ {ref.freq_ghz} GHz (sem AVX2)")
    print(f"  AVX2:     {avx2.platform} @ {avx2.freq_ghz} GHz (AVX2 otimizado)")
    print(f"  Nosso:    Apple Silicon ARM64, Python 3.13 / liboqs 0.15.0")
    print(f"  Fonte:    CRYSTALS-Kyber v3.02, Table 2, Sec. 2.2 — medianas de 10.000 execuções")
    print(f"  Atenção:  Processador de referência diferente do Dilithium (Haswell vs Skylake)")
    print()
    print(f"  {'Operação':<10} {'NIST ref (ms)':>14} {'NIST AVX2 (ms)':>15} {'Nosso ARM64 (ms)':>17} {'vs ref':>8} {'vs AVX2':>9}")
    print(f"  {'-'*10} {'-'*14} {'-'*15} {'-'*17} {'-'*8} {'-'*9}")

    rows = [
        ("KeyGen", ref.keygen_ms, avx2.keygen_ms, our["keygen_ms"]),
        ("Encaps", ref.sign_ms,   avx2.sign_ms,   our["encaps_ms"]),
        ("Decaps", ref.verify_ms, avx2.verify_ms, our["decaps_ms"]),
    ]
    for name, r_ms, a_ms, o_ms in rows:
        r_ref  = ratio(o_ms, r_ms)
        r_avx2 = ratio(o_ms, a_ms)
        print(
            f"  {name:<10} {r_ms:>14.4f} {a_ms:>15.4f} {o_ms:>17.4f}"
            f" {r_ref:>7.2f}× {r_avx2:>8.2f}×"
        )

    print()
    print("  Nota: ratio < 1.0 = nosso ARM64 é mais rápido que a referência NIST")


def print_overhead_analysis() -> None:
    print(f"\n{_SEP}")
    print("Análise de Overhead — Python/ARM64 vs C/x86_64")
    print(_SEP)
    print("""
  RESULTADO INESPERADO:
  Python/liboqs em Apple Silicon ARM64 é mais rápido do que a implementação
  C de referência (sem AVX2) em Intel Skylake/Haswell para todos os algoritmos.

  EXPLICAÇÃO:

  1. Apple Silicon — alta performance por ciclo (IPC)
     Os chips M-series possuem unidades de execução largas, execução fora de
     ordem agressiva, e caches L1/L2 muito rápidos. Para operações de lattice
     (NTT, amostragem de polinômios), o ARM64 Apple Silicon executa
     consideravelmente mais trabalho por ciclo que Skylake @ 2.6 GHz.

  2. liboqs 0.15.0 inclui otimizações para ARM64
     liboqs não usa a implementação de referência C genérica — inclui
     variantes otimizadas com instrinsics NEON e AES-NI do ARM. Isso
     significa que "Python via CFFI" chama código ARM64 otimizado,
     não C portável sem vetorização.

  3. Overhead Python/CFFI: fixo e pequeno em termos relativos
     Cada chamada via liboqs-python incorre em ~1–5 µs de overhead CFFI
     (marshalling de argumentos bytes↔C buffer, troca de contexto Python↔C).
     Para ML-DSA-44 Sign (~106 µs) isso representa < 5% do tempo total.
     Para Kyber512 (~16–18 µs) representa ~5–30% — maior proporcionalmente
     mas ainda tolerável em contexto web.

  4. Comparação com AVX2
     vs AVX2 otimizado (SIMD 256-bit x86), nosso ARM64 fica em paridade ou
     levemente mais lento (~1.0–1.9×), o que é competitivo considerando:
     - Estamos em Python (não C nativo)
     - ARM64 NEON é 128-bit vs AVX2 256-bit por instrução

  IMPLICAÇÃO PARA O TCC:
  O overhead Python/CFFI é compensado pela performance bruta do Apple Silicon.
  A comparação relativa ML-DSA-44 vs RSA-2048 continua válida: ambos sofrem
  o mesmo overhead CFFI, logo o speedup de 8× (service) e 842× (raw sign)
  reflete a diferença real dos algoritmos, não artefato do ambiente Python.
""")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_dilithium_comparison()
    print_kyber_comparison()
    print_overhead_analysis()
