# Diário de Desenvolvimento — TCC PQC Web Auth

> **Projeto:** Implementação e Avaliação de Autenticação Pós-Quântica em Aplicações Web: Comparação de Desempenho entre Algoritmos NIST PQC
> **Autor:** Gabriel Aragão
> **Stack:** Python 3.13 + FastAPI + liboqs-python + Docker

---

## Semana 1 (2026-03-08 a 2026-03-14)

### O que foi feito

**Setup inicial do projeto:**
- Criado repositório com estrutura base do FastAPI (`main.py`, `Dockerfile`, `requirements.txt`)
- Configurado ambiente com Python 3.13 e virtual environment
- Instaladas as dependências principais: `fastapi`, `uvicorn`, `liboqs-python`, `pydantic-settings`
- Criado `.env` com variáveis de configuração (`PQC_ALGORITHM=Kyber512`, `SIG_ALGORITHM=Dilithium2`, etc.)
- Criado `.cursorrules` com diretrizes do projeto para o Cursor IDE

**Primeiros testes com liboqs (smoke tests):**
- Implementado `src/crypto/pqc.py` com dois smoke tests funcionais:
  - `kyber512_kem_smoke_test()`: testou o ciclo completo de KEM (geração de chaves → encapsulamento → desencapsulamento), validando que cliente e servidor chegam ao mesmo shared secret
  - `dilithium2_signature_smoke_test()`: testou o ciclo completo de assinatura digital (geração → assinar → verificar)
- **Resultado:** Ambos os algoritmos funcionando corretamente via liboqs

**Refatoração para Clean Architecture (fim da semana):**
- O `pqc.py` flat foi substituído por uma estrutura limpa e extensível:

```
src/
  config.py                    ← pydantic-settings, lê .env, singleton `settings`
  crypto/
    interfaces.py              ← IKeyEncapsulation e IDigitalSignature (ABCs)
    models.py                  ← Value objects Pydantic frozen
    kem/
      kyber.py                 ← KyberKEM(IKeyEncapsulation)
    signatures/
      dilithium.py             ← DilithiumSignature(IDigitalSignature)
  auth/
    service.py                 ← PQCAuthService (injeta interfaces, não importa oqs)
  api/
    routes.py                  ← GET /pqc/health endpoint
```

---

### Aprendizados técnicos

**liboqs e o padrão context manager:**
- A API do `oqs.KeyEncapsulation` e `oqs.Signature` usa context managers (`with oqs.KeyEncapsulation(...) as kem:`) para garantir que objetos C subjacentes sejam liberados da memória, mesmo em caso de exceção.
- Isso significa que o estado das chaves **não persiste** fora do bloco `with`. Para usar a chave privada depois (ex: desencapsular), é necessário fazer `kem.export_secret_key()` dentro do contexto e salvar os bytes.

**Separação de responsabilidades no KEM:**
- No KEM, há dois lados distintos: quem **gera o keypair** (receptor) e quem **encapsula** (remetente). O encapsulador só precisa da chave pública; não tem acesso à chave privada.
- A função `encap_secret(public_key)` retorna `(ciphertext, shared_secret)` para o remetente. O receptor usa `decap_secret(ciphertext)` com sua chave privada para obter o mesmo shared secret.
- Isso é diferente do RSA: em KEM pós-quântico, não há "criptografia com chave pública" diretamente — é um mecanismo de estabelecimento de chave.

**Por que Kyber (KEM) + Dilithium (assinatura) e não só um deles:**
- **Kyber** é um KEM: serve para estabelecer um segredo compartilhado entre dois lados. Em autenticação web, isso pode substituir o TLS key exchange ou o handshake inicial.
- **Dilithium** é uma assinatura digital: serve para autenticar quem mandou a mensagem (equivalente ao JWT assinado com RS256 no mundo clássico).
- No contexto do TCC, Kyber estabelece a sessão segura; Dilithium assina os tokens de autenticação.

---

### Decisões de arquitetura

**Por que SOLID aqui?**
O projeto vai crescer em fases (clássico → PQC → híbrido → benchmarking). Sem uma estrutura clara, adicionar o modo clássico significaria modificar código que já funciona, aumentando o risco de regressões.

Com a arquitetura SOLID escolhida:
- **Fase 2 (clássico):** criar `src/crypto/classical/rsa.py` implementando `IDigitalSignature` → zero mudanças nos arquivos existentes
- **Fase 4 (híbrido):** `PQCAuthService` já está preparado para receber dois providers diferentes via injeção de dependência
- **Fase 5 (benchmark):** pode decorar qualquer método de `IKeyEncapsulation` ou `IDigitalSignature` sem tocar nas implementações

**Por que `oqs` só aparece em dois arquivos?**
`kyber.py` e `dilithium.py` são os únicos arquivos que importam `oqs`. O resto da aplicação depende de `IKeyEncapsulation` e `IDigitalSignature`. Isso significa que:
1. Trocar de biblioteca PQC (ex: de liboqs para outra) requer mudança em apenas dois arquivos
2. Testar `PQCAuthService` pode ser feito com mocks que implementam as interfaces, sem chamar código criptográfico real

**Por que `verify()` retorna bool e não lança exceção?**
Por contrato definido em `IDigitalSignature`: assinatura inválida = `False`, erro de biblioteca = exception. Isso evita o padrão frágil de `try/except` para controle de fluxo em quem chama o verificador.

---

### Endpoint criado

```
GET /pqc/health
```

Resposta de sucesso (200):
```json
{
  "all_passed": true,
  "results": [
    {"algorithm": "kem", "passed": true, "error": null},
    {"algorithm": "signature", "passed": true, "error": null}
  ]
}
```

Útil para:
- Verificar que liboqs está instalado corretamente no ambiente
- CI/CD health check antes de rodar benchmarks
- Confirmar que os nomes de algoritmos no `.env` são válidos

---

### Conclusões da semana

- liboqs-python está maduro e funcional para Kyber512 e Dilithium2
- A maior barreira de entrada não é o código criptográfico (a biblioteca abstrai bem), mas entender **como** e **onde** cada algoritmo se encaixa no fluxo de autenticação
- A decisão de usar Clean Architecture desde a Fase 1 adiciona um custo inicial de estrutura mas vai pagar dividendos nas Fases 3 e 4

---

### Próximos passos (Semana 2)

- **Fase 2:** Implementar autenticação clássica (RSA/ECDSA + JWT) como baseline
  - Criar `src/crypto/classical/rsa.py` implementando `IDigitalSignature`
  - Criar endpoints `POST /auth/login-classical` e `POST /auth/verify-classical`
  - Instalar `pyjwt` e `cryptography`
- Criar `src/db/` com SQLite para persistir usuários de teste (necessário para os endpoints de login)
- Rodar servidor localmente e testar endpoints manualmente

---

## Semana 2 (2026-03-16)

### Ambiente — Correções de instalação e migração de nomes de algoritmos

#### Problema 1: liboqs-python instalado mas `import oqs` falhava

Ao tentar rodar o servidor pela primeira vez, o erro foi:

```
ModuleNotFoundError: No module named 'oqs'
```

O `liboqs-python` constava no `requirements.txt` mas não estava instalado no venv. Após instalar via `pip install liboqs-python`, o import ainda falhava com:

```
RuntimeError: No oqs shared libraries found
```

**Causa raiz:** o `liboqs-python` é apenas um wrapper Python — ele precisa da biblioteca C `liboqs` compilada como shared library (`.dylib` no macOS). O Homebrew instala o `liboqs` apenas como biblioteca estática (`liboqs.a`), que não serve para binding dinâmico via `ctypes`.

**Solução:** compilar o liboqs do fonte com `BUILD_SHARED_LIBS=ON`:

```bash
git clone https://github.com/open-quantum-safe/liboqs.git
cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=/opt/homebrew
cmake --build build --parallel 4
cmake --install build
```

Isso gerou `/opt/homebrew/lib/liboqs.dylib`, que o wrapper Python consegue carregar.

**Versões resultantes:**
- `liboqs` (C): **0.15.0** (latest do repositório)
- `liboqs-python` (wrapper): **0.14.1** (única versão disponível no PyPI)

O wrapper exibe um aviso de versão (`UserWarning: liboqs version 0.15.0 differs from liboqs-python version 0.14.1`), mas é cosmético — a API usada (`KeyEncapsulation`, `Signature`, context managers) é compatível entre as duas versões.

---

#### Problema 2: nomes de funções da API do wrapper mudaram

Com a biblioteca funcionando, o smoke test retornou 503:

```json
{"error": "module 'oqs' has no attribute 'get_enabled_kems'"}
{"error": "module 'oqs' has no attribute 'get_enabled_sigs'"}
```

**Causa:** o código foi escrito com base em uma versão antiga da API. Os nomes das funções mudaram:

| Nome antigo (usado no código) | Nome correto (versão 0.14.1) |
|-------------------------------|------------------------------|
| `oqs.get_enabled_kems()` | `oqs.get_enabled_kem_mechanisms()` |
| `oqs.get_enabled_sigs()` | `oqs.get_enabled_sig_mechanisms()` |

**Correção:** renomear as chamadas em `kyber.py` e `dilithium.py`.

---

#### Problema 3: `Dilithium2` não existe mais no liboqs 0.15.0

Após corrigir os nomes de função, o KEM passou mas a assinatura falhou:

```
RuntimeError: Signature algorithm 'Dilithium2' is not enabled in this liboqs build.
```

**Causa:** o NIST finalizou a padronização dos algoritmos PQC em 2024 e publicou os padrões oficiais. O liboqs 0.15.0 adotou os nomes dos padrões e removeu os nomes usados durante a competição.

**Mapeamento completo (Dilithium → ML-DSA):**

| Nome de competição | Padrão NIST | Nível de segurança |
|--------------------|-------------|-------------------|
| Dilithium2 | **ML-DSA-44** (FIPS 204) | Nível 2 ≈ AES-128 |
| Dilithium3 | **ML-DSA-65** (FIPS 204) | Nível 3 ≈ AES-192 |
| Dilithium5 | **ML-DSA-87** (FIPS 204) | Nível 5 ≈ AES-256 |

O algoritmo matemático é **idêntico** — apenas o nome mudou para refletir o padrão publicado. O Kyber512 ainda está disponível na 0.15.0 por compatibilidade, mas seu nome oficial é `ML-KEM-512` (FIPS 203).

**Correções aplicadas:**
- `.env`: `SIG_ALGORITHM=Dilithium2` → `SIG_ALGORITHM=ML-DSA-44`
- `dilithium.py`: default do construtor `"Dilithium2"` → `"ML-DSA-44"`

---

### Impacto nos resultados do TCC

Nenhuma mudança afeta a validade dos benchmarks:

- As métricas coletadas (tempo via `perf_counter`, memória via `psutil`) dependem da **implementação matemática do algoritmo**, não do número de versão da biblioteca
- ML-DSA-44 e Dilithium2 são o mesmo algoritmo — mesmos parâmetros, mesma estrutura de lattice, mesmo custo computacional
- Usar os nomes FIPS (`ML-DSA-44`, `ML-KEM-512`) no texto do TCC é academicamente mais forte do que citar os nomes de competição, pois demonstra alinhamento com os padrões publicados

---

### Estado atual do ambiente

```
Python:         3.13
liboqs (C):     0.15.0  ← compilado do fonte com shared libs
liboqs-python:  0.14.1  ← wrapper PyPI
KEM ativo:      Kyber512  (equivalente FIPS: ML-KEM-512)
Sig ativo:      ML-DSA-44 (FIPS 204, ex-Dilithium2)
Smoke test:     GET /pqc/health → 200 OK ✅
```

---

### Próximos passos (Semana 3)

- **Fase 2:** Implementar autenticação clássica (RSA/ECDSA + JWT) como baseline
  - Criar `src/crypto/classical/rsa.py` implementando `IDigitalSignature`
  - Criar endpoints `POST /auth/login-classical` e `POST /auth/verify-classical`
  - Instalar `pyjwt` e `cryptography`
- Criar `src/db/` com SQLite para persistir usuários de teste
- Considerar migrar `PQC_ALGORITHM` de `Kyber512` para `ML-KEM-512` para consistência com nomenclatura FIPS

---
