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
| ML-DSA-44 | PQC (FIPS 204) | — | — | 2420 bytes |
| Kyber512 + ML-DSA-44 | Híbrido | — | — | — |

### Verify / Token Verification

| Algoritmo | Tipo | Verify/ms (warm) |
|-----------|------|-----------------|
| RSA-2048 (RS256) | Clássico | ~0.3ms |
| ML-DSA-44 | PQC | — |

### Tamanhos de chave comparados

| Algoritmo | Chave pública | Chave privada | Tipo |
|-----------|--------------|---------------|------|
| RSA-2048 | 256 bytes | ~1190 bytes (PKCS8 DER) | Clássico |
| Kyber512 | 800 bytes | 1632 bytes | PQC KEM |
| ML-DSA-44 | 1312 bytes | 2528 bytes | PQC Sign |

> **Contexto para o TCC:** o aumento no tamanho de chaves e assinaturas PQC é uma das desvantagens operacionais documentadas. Em autenticação web, o tamanho do token impacta o overhead de rede e o tamanho do header `Authorization`. Isso deve ser discutido na análise qualitativa.

---

## Fase 3 — PQC Puro (a preencher)

**Data de medição:** —
**Status:** Planejado

| Operação | Algoritmo | duration_ms (avg) | duration_ms (P95) |
|----------|-----------|------------------|------------------|
| `pqc_sign` | ML-DSA-44 | — | — |
| `pqc_verify` | ML-DSA-44 | — | — |
| `kem_keygen` | Kyber512 | — | — |
| `kem_encapsulate` | Kyber512 | — | — |
| `kem_decapsulate` | Kyber512 | — | — |

---

## Fase 5 — Benchmark Formal (a preencher)

**Metodologia planejada:**

```python
# Pseudocódigo do loop de benchmark (Phase 5)
results = []
warmup_iterations = 10
measure_iterations = 100

# Warmup — não contabilizado
for _ in range(warmup_iterations):
    service.login(username, password)

# Medição formal
for _ in range(measure_iterations):
    t0 = perf_counter()
    response = service.login(username, password)
    t1 = perf_counter()
    results.append((t1 - t0) * 1000)

stats = {
    "mean_ms": statistics.mean(results),
    "median_ms": statistics.median(results),
    "stdev_ms": statistics.stdev(results),
    "p95_ms": numpy.percentile(results, 95),
    "p99_ms": numpy.percentile(results, 99),
    "min_ms": min(results),
    "max_ms": max(results),
}
```

**Saída esperada:** CSV em `results/` + gráficos comparativos (matplotlib/seaborn).

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
