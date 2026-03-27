# PQC Web Auth — TCC

Sistema de autenticacao web com Criptografia Pos-Quantica (PQC) para benchmarking comparativo entre algoritmos classicos e pos-quanticos. Trabalho de Conclusao de Curso (TCC).

## Algoritmos

| Algoritmo | Tipo | Padrao |
|-----------|------|--------|
| RSA-2048 (RS256) | Classico | PKCS#1 |
| ML-DSA-44 | PQC Assinatura | FIPS 204 |
| Kyber512 | PQC KEM | FIPS 203 |

## Pre-requisitos

- Python 3.13+
- liboqs 0.15.0 (compilado do source)
- liboqs-python 0.14.1
- Docker (opcional)

## Quick Start

```bash
# Criar e ativar virtualenv
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Criar .env (copiar do exemplo abaixo)
cat > .env << 'EOF'
APP_ENV=development
PQC_ALGORITHM=Kyber512
SIG_ALGORITHM=ML-DSA-44
CLASSICAL_ALGORITHM=RS256
BENCHMARK_ITERATIONS=100
BENCHMARK_WARMUP=10
JWT_EXPIRATION_MINUTES=30
RSA_KEY_SIZE=2048
DATABASE_PATH=data/pqc_auth.db
EOF

# Rodar servidor
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/pqc/health` | Health check + smoke test PQC |
| GET | `/docs` | Swagger UI |
| POST | `/auth/register` | Registro de usuario |
| POST | `/auth/login-classical` | Login com RS256 |
| POST | `/auth/verify-classical` | Verificar token RS256 |
| POST | `/auth/login-pqc` | Login com ML-DSA-44 |
| POST | `/auth/verify-pqc` | Verificar token ML-DSA-44 |
| POST | `/auth/kem-exchange` | Kyber512 KEM handshake |
| POST | `/auth/login-hybrid` | Login hibrido (RS256 + ML-DSA-44) |
| POST | `/auth/verify-hybrid` | Verificar ambos tokens |

## Benchmarks

```bash
# Pipeline completo (~2 min)
./scripts/run_benchmarks.sh

# Ou passo a passo
python -m benchmark.runner --environment arm64-macos
python -m benchmark.analysis
python -m benchmark.charts
```

Resultados em `results/` (CSVs + PNGs). Analise detalhada em [`docs/benchmarks.md`](docs/benchmarks.md).

## Docker

```bash
docker build -t pqc-auth .
docker run -p 8000:8000 pqc-auth

# Com benchmark
docker compose --profile benchmark run benchmark
```

## Estrutura

```
src/
  crypto/          Wrappers criptograficos (interfaces + implementacoes)
  auth/            Service layer (classical, pqc, hybrid)
  api/             Endpoints FastAPI
  db/              SQLite + repository pattern
benchmark/         Runner, analysis, charts, throughput
results/           Dados gerados (CSV, PNG)
docs/              Documentacao tecnica
```

## Documentacao

- [`docs/benchmarks.md`](docs/benchmarks.md) — Dados formais de benchmark (N=100)
- [`docs/context.md`](docs/context.md) — Diario de desenvolvimento com decisoes de arquitetura
