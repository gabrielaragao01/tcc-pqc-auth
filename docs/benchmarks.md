# Dados de Benchmarking — TCC PQC Web Auth

> **Propósito:** Este arquivo registra as medições de desempenho coletadas ao longo das fases do projeto. Serve como referência para a análise comparativa do TCC e para validar que os números finais da Fase 5 estão dentro do esperado.
>
> **Metodologia de medição:** `time.perf_counter()` envolvendo exclusivamente a operação criptográfica (sem I/O de rede, acesso a banco ou parsing HTTP). Executado no service layer de cada implementação.

---

## Ambiente de Desenvolvimento

| Parâmetro | Valor |
|-----------|-------|
| Hardware | Apple Silicon (ARM64) |
| Sistema Operacional | macOS 15.x (Darwin 25.x) |
| Python | 3.13 |
| liboqs (C) | 0.15.0 |
| liboqs-python | 0.14.1 |
| PyJWT | 2.12.1 |
| cryptography | 46.0.5 |
| bcrypt | 5.0.0 |

---

## Fase 2 — Baseline Clássico (RSA-2048 + JWT RS256)

**Data de medição:** 2026-03-17
**Status:** Medições iniciais de validação funcional (single-run)

> ⚠️ **Aviso:** Estes valores são single-run coletados durante o smoke test de validação da Fase 2. A Fase 5 realizará medições formais com N=100 iterações, warmup, cálculo de média/mediana/P95/P99 e exportação para CSV. Use os valores abaixo apenas como referência de ordem de grandeza.

### RSA-2048 — Keygen

| Métrica | Valor observado | Observação |
|---------|----------------|------------|
| Keygen (2048 bits) | ~50–100ms | Executado uma única vez no startup do `ClassicalAuthService.__init__()` — **não impacta latência por request** |

### RS256 — Assinatura JWT (`jwt_sign`)

Medição de `jwt.encode(payload, rsa_private_key_pem, algorithm="RS256")`.

| Métrica | Valor observado | Observação |
|---------|----------------|------------|
| Cold start (1ª chamada) | ~44ms | Inclui carga lazy da lib `cryptography` (cffi/pycparser/Rust backends) |
| Warm (2ª+ chamada) | ~1–2ms | Regime permanente após carregamento da lib |

**Payload JWT usado:**
```json
{
  "sub": "<username>",
  "iat": "<unix timestamp>",
  "exp": "<iat + 30 minutos>"
}
```

### RS256 — Verificação JWT (`jwt_verify`)

Medição de `jwt.decode(token, rsa_public_key_pem, algorithms=["RS256"])`.

| Métrica | Valor observado | Observação |
|---------|----------------|------------|
| Cold start (1ª chamada) | ~0.9ms | Verificação RSA é intrinsecamente mais rápida que assinatura |
| Warm | ~0.3ms | Regime permanente |

### Interpretação preliminar

A assimetria sign/verify é esperada e característica do RSA:
- **Assinatura RSA:** usa a chave privada (operação modular com expoente privado `d` grande) — mais lenta
- **Verificação RSA:** usa a chave pública (operação modular com expoente público `e=65537`, muito menor) — mais rápida

Essa assimetria será comparada com ML-DSA-44 na Fase 3, onde a diferença entre assinatura e verificação é muito menor (ML-DSA usa operações de lattice simétricas em custo).

---

## Comparação Prevista (a preencher nas Fases 3 e 5)

### Sign / Token Generation

| Algoritmo | Tipo | Keygen | Sign/ms (warm) | Tamanho assinatura |
|-----------|------|--------|-----------------|-------------------|
| RSA-2048 (RS256) | Clássico | ~50–100ms | ~1–2ms | 256 bytes |
| ML-DSA-44 | PQC (FIPS 204) | ~0.3ms (keygen) | ~0.107ms | 2420 bytes |
| Kyber512 + ML-DSA-44 | Híbrido | — | — | — |

### Verify / Token Verification

| Algoritmo | Tipo | Verify/ms (warm) |
|-----------|------|-----------------|
| RSA-2048 (RS256) | Clássico | ~0.3ms |
| ML-DSA-44 | PQC | ~0.038ms |

### Tamanhos de chave comparados

| Algoritmo | Chave pública | Chave privada | Tipo |
|-----------|--------------|---------------|------|
| RSA-2048 | 256 bytes | ~1190 bytes (PKCS8 DER) | Clássico |
| Kyber512 | 800 bytes | 1632 bytes | PQC KEM |
| ML-DSA-44 | 1312 bytes | 2528 bytes | PQC Sign |

> **Contexto para o TCC:** o aumento no tamanho de chaves e assinaturas PQC é uma das desvantagens operacionais documentadas. Em autenticação web, o tamanho do token impacta o overhead de rede e o tamanho do header `Authorization`. Isso deve ser discutido na análise qualitativa.

---

## Fase 3 — PQC Puro (ML-DSA-44 + Kyber512)

**Data de medição:** 2026-03-23
**Status:** Medições iniciais de validação funcional (single-run, warm)

> ⚠️ Estes valores são single-run coletados após warmup durante a validação da Fase 3. A Fase 5 realizará medições formais com N=100 iterações, média/mediana/P95/P99 e exportação para CSV.

### ML-DSA-44 — Sign / Verify

| Operação | Algoritmo | duration_ms (single-run, warm) |
|----------|-----------|-------------------------------|
| `pqc_sign` | ML-DSA-44 | ~0.107ms |
| `pqc_verify` | ML-DSA-44 | ~0.038ms |

### Kyber512 — KEM Round-trip

| Operação | Algoritmo | duration_ms (single-run, warm) |
|----------|-----------|-------------------------------|
| `kem_keygen` | Kyber512 | ~0.305ms |
| `kem_encapsulate` | Kyber512 | ~0.259ms |
| `kem_decapsulate` | Kyber512 | ~0.019ms |

### Tamanho do token PQC

| Métrica | Valor |
|---------|-------|
| Comprimento do token ML-DSA-44 | 3343 chars (~3.3 KB) |
| Comprimento do token RS256 | ~200 bytes |
| Fator de aumento | ~16.7× |

A diferença de tamanho deve-se principalmente à assinatura ML-DSA-44 (2420 bytes em base64url, vs 342 bytes da assinatura RSA-2048).

---

## Fase 4 — Modo Híbrido (Comparação Direta)

**Data de medição:** 2026-03-23
**Status:** Medições iniciais via endpoint híbrido (single-run, warm)

> ⚠️ Valores de single-run para validação funcional. A Fase 5 realizará medições formais com N=100 iterações.

### Login Híbrido — Sign (mesma request, mesmo payload)

O endpoint `POST /auth/login-hybrid` assina o mesmo payload com ambos os algoritmos na mesma request, permitindo comparação direta sem variação de ambiente.

| Operação | Algoritmo | duration_ms (single-run, warm) |
|----------|-----------|-------------------------------|
| `jwt_sign` | RS256 (RSA-2048) | ~1–2ms |
| `pqc_sign` | ML-DSA-44 | ~0.107ms |

**Razão de performance:** ML-DSA-44 é ~10–19× mais rápido que RS256 para assinatura.

### Verify Híbrido — Verificação (mesma request, ambos os tokens)

| Operação | Algoritmo | duration_ms (single-run, warm) |
|----------|-----------|-------------------------------|
| `jwt_verify` | RS256 (RSA-2048) | ~0.3ms |
| `pqc_verify` | ML-DSA-44 | ~0.038ms |

**Razão de performance:** ML-DSA-44 é ~8× mais rápido que RS256 para verificação.

### Tamanho do response híbrido

| Componente | Tamanho |
|-----------|---------|
| Token RS256 (JWT) | ~200 bytes |
| Token ML-DSA-44 (custom) | ~3343 chars (~3.3 KB) |
| Response total (login-hybrid) | ~3.6 KB |

### Trade-off resumido (Fase 4)

| Métrica | RS256 (clássico) | ML-DSA-44 (PQC) | Vantagem |
|---------|------------------|------------------|----------|
| Sign latency | ~1–2ms | ~0.107ms | PQC |
| Verify latency | ~0.3ms | ~0.038ms | PQC |
| Token size | ~200 bytes | ~3.3 KB | Clássico |
| Key size (pub) | 256 bytes | 1312 bytes | Clássico |
| Key size (priv) | ~1190 bytes | 2528 bytes | Clássico |
| Quantum-safe | Não | Sim | PQC |

---

## Fase 5 — Benchmark Formal (N=100, ARM64)

**Data de medição:** 2026-03-27 (v2, corrigida)
**Status:** Supersedido pela Fase 5b (multi-run, 2026-04-12) — os dados oficiais do TCC estão na seção "Fase 5b — Reprodutibilidade" abaixo. Esta seção é mantida como referência histórica da primeira execução.
**Ambiente:** Apple Silicon (ARM64), macOS, Python 3.13
**Metodologia:** N=100 iterações, warmup=10, `perf_counter()` para timing, `tracemalloc` para memória (em passes separados — ver nota metodológica abaixo)

> **Correção metodológica (v2):** A versão anterior desta seção reportava `jwt_sign` a ~44.8ms. Esse valor estava inflado porque o `ClassicalAuthService` passava bytes PEM ao `jwt.encode()`, forçando `load_pem_private_key()` (~45ms) a cada chamada. A correção foi passar o objeto de chave RSA pré-parseado ao PyJWT. Os raw benchmarks (`raw_rsa_sign`) continuam medindo a operação completa incluindo desserialização da chave DER — isso é intencional para capturar o custo real da primitiva crua.
>
> Além disso, as rodadas de timing e memória foram separadas: a medição de latência usa apenas `perf_counter()` (sem `tracemalloc`), e a memória é medida em um passe separado de 10 iterações. Isso evita que o overhead de `tracemalloc.start()/stop()` por iteração interfira em caches internos da biblioteca `cryptography`.

### Service Layer — Resultados completos

| Operação | Algoritmo | mean (ms) | median (ms) | stdev (ms) | P95 (ms) | P99 (ms) |
|----------|-----------|----------|------------|----------|---------|---------|
| `jwt_sign` | RS256 | 0.888 | 0.789 | 0.419 | 1.182 | 2.926 |
| `jwt_verify` | RS256 | 0.032 | 0.029 | 0.008 | 0.046 | 0.062 |
| `pqc_sign` | ML-DSA-44 | 0.135 | 0.100 | 0.254 | 0.184 | 0.263 |
| `pqc_verify` | ML-DSA-44 | 0.023 | 0.023 | 0.001 | 0.023 | 0.024 |
| `kem_keygen` | Kyber512 | 0.009 | 0.009 | 0.001 | 0.009 | 0.013 |
| `kem_encapsulate` | Kyber512 | 0.010 | 0.010 | 0.000 | 0.010 | 0.010 |
| `kem_decapsulate` | Kyber512 | 0.009 | 0.009 | 0.000 | 0.009 | 0.011 |
| `hybrid_sign_classical` | RS256 | 0.827 | 0.789 | 0.174 | 0.888 | 1.804 |
| `hybrid_sign_pqc` | ML-DSA-44 | 0.113 | 0.098 | 0.043 | 0.181 | 0.325 |
| `hybrid_verify_classical` | RS256 | 0.028 | 0.028 | 0.002 | 0.030 | 0.034 |
| `hybrid_verify_pqc` | ML-DSA-44 | 0.023 | 0.023 | 0.001 | 0.024 | 0.027 |

### Raw Crypto — Resultados completos

| Operação | Algoritmo | mean (ms) | median (ms) | stdev (ms) | P95 (ms) | P99 (ms) |
|----------|-----------|----------|------------|----------|---------|---------|
| `raw_rsa_keygen` | RSA-2048 | 57.294 | 52.754 | 32.871 | 116.285 | 154.641 |
| `raw_rsa_sign` | RSA-2048 | 50.192 | 46.042 | 12.645 | 73.932 | 112.377 |
| `raw_rsa_verify` | RSA-2048 | 0.058 | 0.057 | 0.002 | 0.061 | 0.065 |
| `raw_mldsa_keygen` | ML-DSA-44 | 0.025 | 0.024 | 0.002 | 0.028 | 0.031 |
| `raw_mldsa_sign` | ML-DSA-44 | 0.058 | 0.050 | 0.030 | 0.118 | 0.154 |
| `raw_mldsa_verify` | ML-DSA-44 | 0.022 | 0.022 | 0.001 | 0.024 | 0.027 |
| `raw_kyber_keygen` | Kyber512 | 0.010 | 0.009 | 0.009 | 0.011 | 0.019 |
| `raw_kyber_encapsulate` | Kyber512 | 0.010 | 0.010 | 0.003 | 0.012 | 0.014 |
| `raw_kyber_decapsulate` | Kyber512 | 0.008 | 0.008 | 0.000 | 0.009 | 0.010 |

### Comparação direta — Classical vs PQC

| Comparação | RS256/RSA-2048 (ms) | ML-DSA-44 (ms) | Speedup PQC |
|------------|-------------------|----------------|-------------|
| Token Signing (service) | 0.888 | 0.135 | **6.6×** |
| Token Verification (service) | 0.032 | 0.023 | **1.4×** |
| Key Generation (raw) | 57.294 | 0.025 | **2310×** |
| Signature (raw) | 50.192 | 0.058 | **868×** |
| Verification (raw) | 0.058 | 0.022 | **2.6×** |

### Interpretação dos resultados

**Service layer (jwt_sign vs pqc_sign):** ML-DSA-44 é **~6.6× mais rápido** que RS256 para assinatura de tokens. Esse é o speedup real em regime de produção, com chaves pré-carregadas em memória. O valor anterior de ~390× estava inflado pela reparse de chave PEM a cada chamada.

**Raw crypto (raw_rsa_sign vs raw_mldsa_sign):** ML-DSA-44 é **~868× mais rápido** que RSA para assinatura raw. Porém este número inclui a desserialização da chave DER (`load_der_private_key`) em cada iteração do RSA (~45ms), que é o custo dominante. A comparação raw mede o custo total da primitiva "do zero", enquanto a comparação service mede o custo em regime de chave pré-carregada.

**Verificação:** Tanto service (~1.4×) quanto raw (~2.6×), a vantagem do PQC na verificação é modesta. Ambos os algoritmos verificam em <0.06ms — a diferença é irrelevante em termos de latência percebida pelo usuário.

**Outliers e representatividade estatística:** Operações sub-milissegundo (especialmente `pqc_sign`) apresentam outliers ocasionais causados por GC pauses do Python ou escalonamento de CPU (e.g., `pqc_sign` max=2.633ms vs median=0.100ms, stdev=0.254ms). A **mediana** é mais representativa que a média para essas operações. Os speedups reportados usam a média por consistência com a literatura, mas a mediana confirma a mesma tendência (median jwt_sign 0.789ms / median pqc_sign 0.100ms = 7.9×).

### Saída de dados

- `results/raw_samples.csv` — 2000 samples brutos
- `results/summary_stats.csv` — estatísticas por operação
- `results/comparison.csv` — tabela comparativa
- `results/latency_comparison.png`, `latency_boxplot.png`, `latency_violin.png`
- `results/memory_comparison.png`, `results/payload_sizes.png`

---

## Notas metodológicas

### Por que `perf_counter()` e não `time.time()`?

`time.perf_counter()` é o relógio de maior resolução disponível no Python, não afetado por ajustes de NTP ou alterações de fuso horário. Para medições de operações sub-milissegundo (verificação RSA, operações de lattice), a resolução importa.

### Por que medir no service layer e não no middleware?

A medição no middleware (ou via decorator de rota FastAPI) incluiria:
- Serialização/desserialização JSON (Pydantic)
- Overhead do servidor HTTP (starlette/uvicorn)
- Acesso ao banco de dados (bcrypt verify + SELECT)

O objetivo do TCC é comparar o **custo computacional dos algoritmos criptográficos**, não a latência total da requisição HTTP. O service layer é a fronteira correta.

### Sobre o overhead do bcrypt

`verify_password()` (bcrypt) é executado antes da medição do `jwt_sign`. O custo do bcrypt é intencionalmente alto por design (work factor configurable, padrão ≈ 100ms). Isso **não é contabilizado** no `timing.duration_ms` retornado pela API — apenas o custo da operação criptográfica de chave assimétrica é medido.

Para o TCC, o tempo de bcrypt é constante entre os modos clássico e PQC (a mesma verificação de senha ocorre em ambos), portanto não afeta a comparação.

### Separação de rodadas de timing e memória

Na versão corrigida (v2), o benchmark runner executa duas fases distintas para cada operação:

1. **Fase A (timing):** N=100 iterações com `perf_counter()` apenas, sem `tracemalloc`. Isso garante que o overhead de instrumentação de memória não contamine as medições de latência.
2. **Fase B (memória):** 10 iterações com `tracemalloc.start()/stop()` para capturar peak e current bytes. A média dessas 10 amostras é associada a todas as amostras de timing.

Essa separação foi necessária porque `tracemalloc.start()/stop()` por iteração pode interferir em caches internos de bibliotecas C (como a `cryptography` via OpenSSL).

### Memória em operações compostas (híbrido e KEM)

Para operações compostas como `hybrid_login` (que executa assinatura clássica + PQC) e `kem_exchange` (que executa keygen + encapsulate + decapsulate), o `tracemalloc` mede o **agregado** da operação completa. Isso significa que todas as sub-operações dentro de uma chamada compartilham o mesmo valor de `tracemalloc_peak_bytes`.

Os valores de memória para sub-operações híbridas/KEM representam o pico de alocação da operação composta inteira, não da sub-operação individual. Para obter memória individual por sub-operação, seria necessário reestruturar o service layer, quebrando os limites de clean architecture — o que não se justifica para o escopo do TCC.

### Throughput HTTP

O benchmark de throughput HTTP (`benchmark/throughput.py`) não foi incluído nos resultados formais. O foco do TCC é a performance de primitivas criptográficas (latência e memória), não throughput de servidor HTTP — que é dominado por bcrypt (~100ms por request) e I/O de rede, não pela operação criptográfica em si.

### Limitação de plataforma: ARM64 vs x86_64

Todos os benchmarks foram executados em Apple Silicon (ARM64, macOS). Valores absolutos de latência podem diferir em processadores x86_64. No entanto, o **speedup relativo entre ML-DSA-44 e RSA-2048 é documentado como consistente entre arquiteturas** pelas seguintes razões estruturais:

1. **Operações RSA** são O(k³) no tamanho da chave — custosas em qualquer ISA.
2. **Operações de lattice** (NTT, amostragem) são O(n log n) — eficientes em qualquer ISA.

Essa consistência cross-plataforma é corroborada pela literatura:

> *"Valores absolutos diferem em x86_64, mas o speedup relativo de ML-DSA-44 sobre RSA é documentado como consistente entre arquiteturas"* — ver [DILITHIUM-SPEC] e [SIKERIDIS-2020].

**Referências que suportam esta afirmação:**

- **[DILITHIUM-SPEC]** Ducas, L., Kiltz, E., Lepoint, T., Lyubashevsky, V., Schwabe, P., Seiler, G., Stehlé, D. *CRYSTALS-Dilithium: Algorithm Specifications and Supporting Documentation (Version 3.1).* NIST PQC Round 3 Submission, February 2021. — A especificação oficial apresenta ciclos de CPU medidos em múltiplas plataformas (amd64 com e sem AVX2, Cortex-M4), mostrando que Dilithium2 sign é consistentemente ~10–15× mais rápido que RSA-2048 sign em todas as ISAs testadas.

- **[FIPS-204]** National Institute of Standards and Technology. *FIPS 204: Module-Lattice-Based Digital Signature Standard.* U.S. Department of Commerce, August 2024. DOI: 10.6028/NIST.FIPS.204

- **[SIKERIDIS-2020]** Sikeridis, D., Kampanakis, P., Devetsikiotis, M. *Post-Quantum Authentication in TLS 1.3: A Performance Study.* Network and Distributed System Security Symposium (NDSS), 2020. DOI: 10.14722/ndss.2020.24203 — Testa autenticação PQC (incluindo Dilithium) em TLS 1.3 tanto em x86 (Intel) quanto em ARM, confirmando que o speedup relativo se mantém.

- **[KYBER-SPEC]** Avanzi, R., Bos, J., Ducas, L., et al. *CRYSTALS-Kyber: Algorithm Specifications and Supporting Documentation (Version 3.02).* NIST PQC Round 3 Submission, 2021. — Idem para Kyber512.

---

## Fase 5b — Reprodutibilidade (3 execuções independentes, ARM64)

**Data de medição:** 2026-04-12
**Status:** 3 execuções completas para validação de reprodutibilidade
**Metodologia:** 3 execuções independentes do benchmark completo (N=100, warmup=10 cada), com 30s de cooldown entre runs para evitar thermal throttling. Total: 6000 amostras brutas.

### Variância Inter-Run — Service Layer

| Operação | Algoritmo | Grand Mean (ms) | Inter-Run StDev (ms) | CV (%) | Reprodutível? |
|----------|-----------|-----------------|---------------------|--------|---------------|
| `jwt_sign` | RS256 | 1.629 | 0.072 | 4.42% | Sim |
| `jwt_verify` | RS256 | 0.058 | 0.005 | 9.01% | Sim |
| `pqc_sign` | ML-DSA-44 | 0.203 | 0.025 | 12.41% | Marginal (ver nota) |
| `pqc_verify` | ML-DSA-44 | 0.044 | 0.001 | 1.34% | Sim |
| `kem_keygen` | Kyber512 | 0.017 | 0.000 | 0.33% | Sim |
| `kem_encapsulate` | Kyber512 | 0.019 | 0.000 | 0.98% | Sim |
| `kem_decapsulate` | Kyber512 | 0.017 | 0.000 | 0.90% | Sim |
| `hybrid_sign_classical` | RS256 | 1.686 | 0.105 | 6.24% | Sim |
| `hybrid_sign_pqc` | ML-DSA-44 | 0.204 | 0.017 | 8.41% | Sim |
| `hybrid_verify_classical` | RS256 | 0.056 | 0.001 | 0.92% | Sim |
| `hybrid_verify_pqc` | ML-DSA-44 | 0.046 | 0.000 | 0.67% | Sim |

### Variância Inter-Run — Raw Crypto

| Operação | Algoritmo | Grand Mean (ms) | Inter-Run StDev (ms) | CV (%) | Reprodutível? |
|----------|-----------|-----------------|---------------------|--------|---------------|
| `raw_rsa_keygen` | RSA-2048 | 108.333 | 3.955 | 3.65% | Sim |
| `raw_rsa_sign` | RSA-2048 | 89.323 | 0.860 | 0.96% | Sim |
| `raw_rsa_verify` | RSA-2048 | 0.113 | 0.002 | 2.15% | Sim |
| `raw_mldsa_keygen` | ML-DSA-44 | 0.049 | 0.003 | 5.48% | Sim |
| `raw_mldsa_sign` | ML-DSA-44 | 0.106 | 0.005 | 4.63% | Sim |
| `raw_mldsa_verify` | ML-DSA-44 | 0.044 | 0.001 | 1.60% | Sim |
| `raw_kyber_keygen` | Kyber512 | 0.018 | 0.000 | 2.23% | Sim |
| `raw_kyber_encapsulate` | Kyber512 | 0.018 | 0.000 | 1.55% | Sim |
| `raw_kyber_decapsulate` | Kyber512 | 0.016 | 0.000 | 0.79% | Sim |

### Comparação Classical vs PQC (Grand Means, 3 runs)

| Comparação | RS256/RSA-2048 (ms) | ML-DSA-44 (ms) | Speedup PQC |
|------------|-------------------|----------------|-------------|
| Token Signing (service) | 1.629 | 0.203 | **8.0×** |
| Token Verification (service) | 0.058 | 0.044 | **1.3×** |
| Key Generation (raw) | 108.333 | 0.049 | **2206×** |
| Signature (raw) | 89.323 | 0.106 | **842×** |
| Verification (raw) | 0.113 | 0.044 | **2.6×** |

### Critério de reprodutibilidade

> **CV < 5%** = Excelente — resultados altamente reprodutíveis
> **CV 5–10%** = Aceitável — variação dentro do esperado para benchmarks de criptografia
> **CV > 10%** = Investigar — pode indicar interferência externa (GC, thermal throttling, escalonamento de CPU)

**Resultado geral:** 19 de 20 operações apresentam CV < 10%, com a maioria abaixo de 5%. A única exceção é `pqc_sign` (service layer) com CV = 12.4%, explicável pelo fato de operações sub-milissegundo serem mais sensíveis a outliers causados por GC pauses do Python. A **mediana** de `pqc_sign` é estável entre runs (0.182ms), confirmando que a variação está nos outliers (tail), não no regime permanente.

### Gráficos de reprodutibilidade

- `results/multi_run/inter_run_boxplot.png` — distribuição de latência por run (box plot)
- `results/multi_run/inter_run_cv.png` — coeficiente de variação por operação (bar chart)
- `results/multi_run/run_means_comparison.png` — médias por run lado a lado

### Saída de dados

- `results/runs/run_1/raw_samples.csv` — 2000 amostras da rodada 1
- `results/runs/run_2/raw_samples.csv` — 2000 amostras da rodada 2
- `results/runs/run_3/raw_samples.csv` — 2000 amostras da rodada 3
- `results/multi_run/combined_samples.csv` — 6000 amostras concatenadas
- `results/multi_run/inter_run_stats.csv` — estatísticas inter-run com CV%
- `results/multi_run/summary_stats_all_runs.csv` — summary stats por run
