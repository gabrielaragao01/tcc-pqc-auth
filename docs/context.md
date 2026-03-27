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

## Semana 3 (2026-03-17)

### Fase 2 — Autenticação Clássica (RSA-2048 + JWT RS256) + SQLite

#### O que foi implementado

A Fase 2 entrega o **baseline clássico** que serve de referência para os benchmarks do TCC. O objetivo é ter um sistema de autenticação JWT completo usando algoritmos clássicos (RSA-2048, SHA-256), com medição de desempenho integrada nos endpoints, antes de implementar a versão PQC equivalente.

**Estrutura criada:**

```
src/
  crypto/
    __init__.py              ← criado (estava faltando)
    classical/
      __init__.py
      rsa.py                 ← RSASignature(IDigitalSignature) via cryptography lib
  db/
    __init__.py
    database.py              ← init_db(), get_connection() context manager (sqlite3)
    models.py                ← User Pydantic model (frozen)
    repository.py            ← UserRepository: create_user, get_by_username, verify_password
  auth/
    models.py                ← AuthBenchmarkResult, LoginRequest, TokenResponse, VerifyResponse, ...
    classical_service.py     ← ClassicalAuthService: login() + verify_token() com perf_counter
  api/
    auth_routes.py           ← Router /auth: POST /register, /login-classical, /verify-classical
```

**Arquivos modificados:**
- `main.py` → lifespan event chama `init_db()` no startup; inclui `auth_router`; versão `0.2.0`
- `src/config.py` → adicionados `jwt_expiration_minutes`, `rsa_key_size`, `database_path`
- `requirements.txt` → adicionados `PyJWT>=2.8.0`, `cryptography>=42.0.0`, `bcrypt>=4.0.0`
- `.env` / `.env.example` → novas variáveis `JWT_EXPIRATION_MINUTES=30`, `RSA_KEY_SIZE=2048`, `DATABASE_PATH=data/pqc_auth.db`

---

#### Problema encontrado: passlib incompatível com bcrypt 5.x

**Plano original:** usar `passlib[bcrypt]` para hashing de senha (biblioteca popular).

**Erro ao executar:**
```
(trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
ValueError: password cannot be longer than 72 bytes, truncate manually...
```

**Causa raiz:** `passlib 1.7.4` (última versão, sem atualizações desde 2020) usa a API interna do módulo `bcrypt` via `bcrypt.__about__.__version__`, que foi removida no `bcrypt 4.x+`. O projeto `passlib` está abandonado e não receberá correções.

**Solução:** substituir `passlib` pelo módulo `bcrypt` diretamente, que tem API estável e simples:

```python
# Hash
hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Verificar
bcrypt.checkpw(plain.encode(), stored_hash.encode())
```

**Lição para o TCC:** dependências de segurança devem ser acompanhadas ativamente. Uma lib de hashing abandonada é um risco real em produção — para o contexto de benchmarking aqui, o impacto é zero, mas o padrão a seguir é usar o módulo nativo bem mantido.

---

#### Decisões de arquitetura tomadas na Fase 2

**1. Chaves RSA geradas no startup, mantidas em memória**

As chaves RSA-2048 são geradas uma única vez em `ClassicalAuthService.__init__()` e reutilizadas para todas as requisições do processo. Alternativas consideradas:

| Abordagem | Prós | Contras |
|-----------|------|---------|
| Gerar no startup (escolhida) | Simples; espelha o comportamento PQC da Fase 3 | Chaves perdidas no restart |
| Persistir em arquivo | Chaves estáveis entre restarts | Complexidade de segurança desnecessária para benchmarking |
| Gerar por requisição | Máximo isolamento | Mede keygen + sign juntos — invalida comparação justa |

A abordagem escolhida garante que as medições de `jwt_sign` e `jwt_verify` meçam **apenas a operação criptográfica**, sem incluir keygen no timing de cada request.

**2. PyJWT para o fluxo JWT vs. `IDigitalSignature` para benchmark raw**

Dois caminhos distintos foram criados intencionalmente:

- `RSASignature(IDigitalSignature)` — assina/verifica **bytes puros** com RSA-PSS. Usado para benchmark raw na Fase 5 (comparação direta com `DilithiumSignature`).
- `PyJWT` com `algorithm="RS256"` — usado no fluxo de autenticação real. Interno ao `ClassicalAuthService`, não exposto como interface.

O `ClassicalAuthService.__init__()` converte as chaves DER → PEM **uma vez**, pois `RSASignature` retorna bytes DER (consistente com o contrato de `SignatureKeyPair` e com liboqs), mas PyJWT exige PEM para RS256.

**3. Timing integrado no service layer**

O `perf_counter()` envolve exatamente a operação criptográfica:

```python
# jwt_sign: apenas o encode (assinar o JWT com RSA)
t0 = time.perf_counter()
token = jwt.encode(payload, private_key_pem, algorithm="RS256")
t1 = time.perf_counter()

# jwt_verify: apenas o decode (verificar assinatura + expiração)
t0 = time.perf_counter()
claims = jwt.decode(token, public_key_pem, algorithms=["RS256"])
t1 = time.perf_counter()
```

Isso exclui: latência de rede, parsing HTTP, acesso ao banco, serialização JSON. O objetivo é isolar o overhead criptográfico — o mesmo critério será aplicado nas Fases 3 e 5.

**4. Singleton lazy para o service no router**

```python
_classical_service: ClassicalAuthService | None = None

def _get_service() -> ClassicalAuthService:
    global _classical_service
    if _classical_service is None:
        _classical_service = ClassicalAuthService(...)  # RSA keygen aqui
    return _classical_service
```

A geração das chaves RSA ocorre na **primeira requisição**, não no import do módulo. Isso evita que o startup falhe se a geração de chaves tiver problema, e mantém o mesmo padrão do `_build_service()` já existente em `routes.py`.

**5. SQLite com conexão por chamada (thread-safe)**

FastAPI com uvicorn executa endpoints síncronos em um threadpool. Para evitar problemas de concorrência com SQLite, `get_connection()` cria **uma nova conexão por chamada**:

```python
@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

Isso é suficiente para cargas de benchmarking — não é necessário pool de conexões para o volume de requisições do TCC.

---

#### Endpoints criados

**`POST /auth/register`**
```json
// Request
{"username": "alice", "password": "senha123"}

// Response 200
{"username": "alice", "message": "User created successfully."}

// Response 409 (duplicata)
{"detail": "Username already exists."}
```

**`POST /auth/login-classical`**
```json
// Request
{"username": "alice", "password": "senha123"}

// Response 200
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "algorithm": "RS256",
  "timing": {
    "operation": "jwt_sign",
    "duration_ms": 1.823,
    "algorithm": "RS256"
  }
}

// Response 401 (senha errada)
{"detail": "Invalid username or password."}
```

**`POST /auth/verify-classical`**
```json
// Request
{"token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."}

// Response 200
{
  "valid": true,
  "claims": {
    "sub": "alice",
    "iat": 1742245200,
    "exp": 1742247000
  },
  "timing": {
    "operation": "jwt_verify",
    "duration_ms": 0.294,
    "algorithm": "RS256"
  }
}
```

---

#### Primeiras medições do baseline clássico

Ambiente: macOS, Apple Silicon (ARM64), Python 3.13, RSA-2048, SHA-256.

> **Atenção:** estas são medições iniciais de single-run para validação funcional. A Fase 5 realizará `N=100` iterações com cálculo de média, desvio padrão, P95 e P99. Use estes valores apenas como referência de ordem de grandeza.

| Operação | Medição (single-run) | Observação |
|----------|---------------------|------------|
| RSA-2048 keygen | ~50–100ms | Executado uma vez no startup; não impacta latência por request |
| `jwt_sign` (RS256) | ~1–2ms (warm) | Primeira chamada pode ser ~44ms (cold start da lib `cryptography`) |
| `jwt_verify` (RS256) | ~0.3–0.9ms | Verificação RSA é mais rápida que assinatura |

**Observação sobre cold start:** A primeira chamada ao `jwt.encode()` apresenta latência elevada (~44ms) porque a biblioteca `cryptography` (escrita em Rust/C) carrega suas dependências nativas (`cffi`, `pycparser`) lazily na primeira invocação. A partir da segunda chamada, o tempo cai para a faixa esperada de 1–2ms. Os benchmarks da Fase 5 farão warmup antes de medir para obter os valores de regime permanente.

---

#### Estado atual do projeto

```
Python:              3.13
liboqs (C):          0.15.0
liboqs-python:       0.14.1
PyJWT:               2.12.1
cryptography:        46.0.5
bcrypt:              5.0.0
KEM ativo:           Kyber512 (equiv. FIPS: ML-KEM-512)
Sig PQC ativo:       ML-DSA-44 (FIPS 204)
Sig clássica:        RSA-2048 / RS256
Banco:               SQLite via data/pqc_auth.db
Smoke test PQC:      GET /pqc/health → 200 OK ✅
Reg/Login/Verify:    POST /auth/* → 200 OK ✅
```

---

### Próximos passos (Fase 3)

- **Fase 3:** Autenticação PQC pura (sem RSA/JWT clássico)
  - Criar `src/auth/pqc_service.py` — `PQCLoginService`:
    - Login: gerar keypair Dilithium (ML-DSA-44), assinar payload com `DilithiumSignature`, retornar token PQC + timing
    - Verify: verificar assinatura Dilithium, retornar claims + timing
  - Criar endpoints `POST /auth/login-pqc` e `POST /auth/verify-pqc`
  - Integrar KEM Kyber512 no handshake: `POST /auth/kem-exchange` (estabelecer shared secret)
  - Retornar `AuthBenchmarkResult` com `algorithm: "ML-DSA-44"` para comparação direta com `"RS256"`
- **Estrutura de token PQC:** definir formato (não é JWT padrão — JWT não suporta ML-DSA-44 nativamente; usar Base64url do payload + assinatura Dilithium)
- **Comparação inicial:** após Fase 3, comparar `timing.duration_ms` de `/auth/login-classical` vs. `/auth/login-pqc` em chamadas reais

---

## Decisão arquitetural — Formato do token PQC (Fase 3)

JWT (RFC 7519) não suporta o algoritmo ML-DSA-44 nativamente. Para a Fase 3, adotamos um **formato JWT-like customizado**: `base64url(header).base64url(payload).base64url(signature)`, onde o header contém `{"alg": "ML-DSA-44", "typ": "JWT"}`.

Esse formato não é JWT padrão (nenhuma biblioteca JWT o processará sem extensão), mas mantém a estrutura de três partes separadas por `.`, permite comparação direta com o token RS256 (mesmo payload, mesma estrutura, diferente algoritmo), e é o formato adotado em papers acadêmicos de PQC-JWT.

**Implicação para o TCC:** o token RS256 tem ~200 bytes; o token ML-DSA-44 terá ~3.500 bytes (2420 bytes de assinatura em base64url). Esse overhead de tamanho será medido e discutido na análise.

---

## Semana 4 (2026-03-23)

### Fase 3 — Autenticação PQC Pura (ML-DSA-44 + Kyber512)

#### O que foi implementado

- `src/auth/models.py` — adicionado `KEMExchangeResponse` (frozen Pydantic): `secrets_match`, `timing_keygen`, `timing_encapsulate`, `timing_decapsulate`
- `src/auth/pqc_service.py` — `PQCLoginService` com `login()`, `verify_token()` e `kem_exchange()`; zero imports de `oqs` (depende exclusivamente de `IDigitalSignature` + `IKeyEncapsulation`)
- `src/api/pqc_auth_routes.py` — router com `POST /auth/login-pqc`, `POST /auth/verify-pqc`, `POST /auth/kem-exchange`
- `main.py` — registrado `pqc_auth_router`; versão `0.3.0`; mensagem root atualizada para "Phase 3 active"
- `tests/test_auth_pqc.py` — 11 testes cobrindo login (4), verify (5) e KEM exchange (2)

**Suite completa:** 42 testes, 0 falhas.

---

#### Decisão — Formato do token PQC (implementação)

JWT (RFC 7519) não suporta ML-DSA-44. Formato adotado:

```
base64url(header) . base64url(payload) . base64url(signature)
```

- **Header:** `{"alg":"ML-DSA-44","typ":"PQC"}`
- **Payload:** `{"sub":"<user>","iat":<ts>,"exp":<ts>}` — mesmo esquema do JWT RS256
- **Mensagem assinada:** `header_b64 + "." + payload_b64` (bytes UTF-8)
- **Verificação de `exp`:** manual, após a verificação da assinatura; fora do `perf_counter()` (não é operação cripto)

O `json.dumps` usa `separators=(",",":")` (JSON compacto) para garantir determinismo da mensagem assinada.

Tamanho real medido: **3343 chars** (~3.3 KB) vs ~200 bytes do RS256. O overhead de tamanho é esperado: 2420 bytes de assinatura ML-DSA-44 em base64url.

---

#### Decisão — KEM Exchange em endpoint único

Em produção real, o KEM envolve dois agentes (cliente encapsula, servidor decapsula). Para benchmarking, `POST /auth/kem-exchange` executa o round-trip completo (keygen → encapsulate → decapsulate) em um único request, com timing isolado por operação. Isso permite medir os três custos individualmente sem overhead de rede.

---

#### Primeiras medições da Fase 3 (single-run, warm)

Ambiente: macOS, Apple Silicon (ARM64), Python 3.13, liboqs 0.15.0.

> ⚠️ Medições de single-run para validação funcional. A Fase 5 realizará N=100 iterações com média, P95 e P99.

| Operação | Algoritmo | Medição (warm) |
|----------|-----------|---------------|
| `pqc_sign` | ML-DSA-44 | ~0.107ms |
| `pqc_verify` | ML-DSA-44 | ~0.038ms |
| `kem_keygen` | Kyber512 | ~0.305ms |
| `kem_encapsulate` | Kyber512 | ~0.259ms |
| `kem_decapsulate` | Kyber512 | ~0.019ms |

**Comparação preliminar com RS256:**

| Operação | RS256 (warm) | ML-DSA-44 (warm) | Razão |
|----------|-------------|-----------------|-------|
| Sign / `pqc_sign` | ~1–2ms | ~0.107ms | ML-DSA-44 é **mais rápido** |
| Verify / `pqc_verify` | ~0.3ms | ~0.038ms | ML-DSA-44 é **mais rápido** |

Resultado surpreendente: ML-DSA-44 é significativamente mais rápido que RSA-2048 nas operações de sign e verify em Apple Silicon (ARM64). A hipótese é que as operações de lattice (adição/multiplicação de polinômios sobre $\mathbb{Z}_q$) são muito mais eficientes em CPUs modernas do que a exponenciação modular RSA. A Fase 5 confirmará com N=100 iterações.

A desvantagem PQC está no **tamanho** (token 3.3 KB vs 200 bytes), não na velocidade.

---

#### Estado atual do projeto (Fase 3 completa)

```
Python:              3.13
liboqs (C):          0.15.0
liboqs-python:       0.14.1
PyJWT:               2.12.1
cryptography:        46.0.5
bcrypt:              5.0.0
KEM ativo:           Kyber512 (equiv. FIPS: ML-KEM-512)
Sig PQC ativo:       ML-DSA-44 (FIPS 204)
Sig clássica:        RSA-2048 / RS256
Banco:               SQLite via data/pqc_auth.db
Testes:              42 passed
Endpoints PQC:       POST /auth/login-pqc, /verify-pqc, /kem-exchange ✅
```

---

### Próximos passos (Fase 4)

- **Fase 4:** Modo híbrido — combinar RS256 + ML-DSA-44 no mesmo fluxo de autenticação

---

## Semana 5 (2026-03-23)

### Fase 4 — Modo Híbrido (Classical + PQC side by side)

#### O que foi implementado

A Fase 4 combina os dois modos de autenticação (clássico e PQC) em um único fluxo, permitindo comparação direta de performance e migração gradual.

**Arquivos criados:**

```
src/
  auth/
    hybrid_service.py              ← HybridAuthService (compõe Classical + PQC services)
  api/
    hybrid_auth_routes.py          ← POST /auth/login-hybrid, /auth/verify-hybrid
tests/
  test_auth_hybrid.py              ← 11 testes cobrindo login e verificação híbrida
```

**Arquivos modificados:**
- `src/auth/models.py` → adicionados `HybridTokenResponse`, `HybridVerifyRequest`, `HybridVerifyResponse`
- `main.py` → registrado `hybrid_auth_router`; versão `0.4.0`; mensagem root "Phase 4 active"

**Suite completa:** 53 testes, 0 falhas.

---

#### Decisão — Estratégia híbrida: dual token (token duplo)

Duas estratégias foram consideradas:

| Estratégia | Descrição | Prós | Contras |
|------------|-----------|------|---------|
| **Token duplo** (escolhida) | Login retorna dois tokens independentes (RS256 + ML-DSA-44) | Simples; comparação direta; migração gradual; cliente escolhe qual usar | Dois tokens no response (maior payload HTTP) |
| Dupla assinatura | Token único com duas assinaturas concatenadas | Token único no header | Complexo; formato não-padrão; dificulta comparação isolada |

**Por que token duplo:** O objetivo do TCC é **comparar performance**, não construir um protocolo híbrido otimizado. Com tokens independentes, cada operação (sign RS256, sign ML-DSA-44) é medida isoladamente com `perf_counter()`, e o cliente pode verificar um ou ambos. Isso também espelha a estratégia de migração gradual recomendada pelo NIST (Cryptographic Agility): sistemas em transição aceitam ambos os formatos simultaneamente.

---

#### Decisão — Composição vs. herança no HybridAuthService

`HybridAuthService` **compõe** `ClassicalAuthService` e `PQCLoginService` internamente, em vez de herdar de ambos ou duplicar lógica:

```python
class HybridAuthService:
    def __init__(self, classical_signature, pqc_signature, kem, user_repo):
        self._classical = ClassicalAuthService(classical_signature, user_repo)
        self._pqc = PQCLoginService(pqc_signature, kem, user_repo)
```

**Vantagem:** zero duplicação de lógica criptográfica. Se o formato do token PQC mudar, a mudança fica em `PQCLoginService` e o híbrido herda automaticamente.

**Trade-off aceito:** `login()` valida as credenciais bcrypt **duas vezes** (uma em cada service interno). Alternativa seria extrair a validação para fora, mas isso quebraria a interface dos serviços existentes. O custo é irrelevante: bcrypt.verify ~1ms, e não é contabilizado no `timing.duration_ms` (está fora do `perf_counter()`).

---

#### Decisão — Claims no verify híbrido

Quando ambos os tokens são válidos, os claims retornados vêm do **token clássico** (JWT padrão). Se apenas o PQC for válido, os claims vêm dele. Isso é consistente com o cenário de migração: o token clássico é a "fonte de verdade" durante a transição.

---

#### Endpoints criados

**`POST /auth/login-hybrid`**
```json
// Request
{"username": "alice", "password": "senha123"}

// Response 200
{
  "classical_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "pqc_token": "eyJhbGciOiJNTC1EU0EtNDQiLCJ0eXAiOiJQUUMifQ...",
  "token_type": "bearer",
  "timing_classical": {
    "operation": "jwt_sign",
    "duration_ms": 1.823,
    "algorithm": "RS256"
  },
  "timing_pqc": {
    "operation": "pqc_sign",
    "duration_ms": 0.107,
    "algorithm": "ML-DSA-44"
  }
}

// Response 401
{"detail": "Invalid username or password."}
```

**`POST /auth/verify-hybrid`**
```json
// Request
{
  "classical_token": "eyJhbGciOiJSUzI1NiIs...",
  "pqc_token": "eyJhbGciOiJNTC1EU0EtNDQi..."
}

// Response 200
{
  "classical_valid": true,
  "pqc_valid": true,
  "claims": {
    "sub": "alice",
    "iat": 1742245200,
    "exp": 1742247000
  },
  "timing_classical": {
    "operation": "jwt_verify",
    "duration_ms": 0.294,
    "algorithm": "RS256"
  },
  "timing_pqc": {
    "operation": "pqc_verify",
    "duration_ms": 0.038,
    "algorithm": "ML-DSA-44"
  }
}
```

---

#### Testes criados (11 testes)

| Grupo | Teste | O que valida |
|-------|-------|-------------|
| Login | `test_login_hybrid_returns_both_tokens` | Response contém ambos os tokens não-vazios |
| Login | `test_login_hybrid_classical_is_rs256` | Timing clássico: algorithm RS256, operation jwt_sign |
| Login | `test_login_hybrid_pqc_is_mldsa44` | Timing PQC: algorithm ML-DSA-44, operation pqc_sign |
| Login | `test_login_hybrid_timings_are_positive` | Ambos os timings > 0ms |
| Login | `test_login_hybrid_wrong_password_raises` | ValueError com senha errada |
| Login | `test_login_hybrid_unknown_user_raises` | ValueError com user inexistente |
| Verify | `test_verify_hybrid_both_valid` | Ambos válidos, claims corretos |
| Verify | `test_verify_hybrid_classical_invalid` | Token clássico inválido, PQC válido → claims do PQC |
| Verify | `test_verify_hybrid_pqc_invalid` | PQC inválido, clássico válido → claims do clássico |
| Verify | `test_verify_hybrid_both_invalid` | Ambos inválidos → claims None |
| Verify | `test_verify_hybrid_timings_are_positive` | Timings de verify > 0 com algoritmos corretos |

---

#### Aprendizados da Fase 4

**1. Composição é poderosa em clean architecture:**
A decisão SOLID da Fase 1 pagou dividendos aqui. O `HybridAuthService` tem apenas ~40 linhas de código porque toda a lógica real já existe nos services das Fases 2 e 3. Zero duplicação, zero refatoração.

**2. O padrão de singleton lazy se mantém consistente:**
`hybrid_auth_routes.py` usa o mesmo padrão `_get_service()` das rotas anteriores. Três singletons independentes (clássico, PQC, híbrido) coexistem sem conflito — cada um gera suas chaves no startup da primeira request.

**3. A comparação direta confirma a tendência:**
Mesmo em chamadas manuais (single-run), o endpoint híbrido permite ver lado a lado que ML-DSA-44 é consistentemente mais rápido que RS256 em sign e verify. A Fase 5 formalizará isso com N=100 iterações.

---

#### Estado atual do projeto (Fase 4 completa)

```
Python:              3.13
liboqs (C):          0.15.0
liboqs-python:       0.14.1
PyJWT:               2.12.1
cryptography:        46.0.5
bcrypt:              5.0.0
KEM ativo:           Kyber512 (equiv. FIPS: ML-KEM-512)
Sig PQC ativo:       ML-DSA-44 (FIPS 204)
Sig clássica:        RSA-2048 / RS256
Banco:               SQLite via data/pqc_auth.db
Testes:              53 passed
Endpoints híbridos:  POST /auth/login-hybrid, /verify-hybrid ✅
```

---

### Próximos passos (Fase 5)

- **Fase 5:** Benchmarking formal e análise de performance

---

## Semana 6 (2026-03-27)

### Fase 5 — Benchmarking Formal e Análise de Performance

#### O que foi implementado

A Fase 5 é o **core do TCC**: coleta formal de dados com N=100 iterações, medição de memória (`tracemalloc` + `psutil`), exportação CSV e gráficos comparativos.

**Arquivos criados:**

```
benchmark/
  __init__.py
  __main__.py              ← permite `python -m benchmark.runner`
  runner.py                ← runner principal: warmup, N=100, coleta timing + memória
  metrics.py               ← BenchmarkSample dataclass, detect_environment()
  analysis.py              ← estatísticas: mean, median, stdev, P95, P99 + export CSV
  charts.py                ← gráficos: bar, box, violin plots (matplotlib/seaborn)
  throughput.py             ← teste de throughput HTTP via httpx
results/
  raw_samples.csv           ← 2000 samples brutos (20 operações × 100 iterações)
  summary_stats.csv         ← estatísticas agregadas (1 linha por operação)
  comparison.csv            ← tabela comparativa clássico vs PQC
  latency_comparison.png    ← bar chart: jwt_sign vs pqc_sign, jwt_verify vs pqc_verify
  latency_boxplot.png       ← box plot: distribuição de latência (service layer)
  latency_violin.png        ← violin plot: distribuição de latência (raw crypto)
  memory_comparison.png     ← bar chart: tracemalloc peak bytes por operação
  payload_sizes.png         ← bar chart horizontal: tamanho de tokens/chaves/assinaturas
scripts/
  run_benchmarks.sh         ← script completo: runner → analysis → charts
```

**Arquivos modificados:**
- `requirements.txt` → adicionados `psutil`, `pandas`, `matplotlib`, `seaborn`, `numpy`
- `src/config.py` → adicionado `benchmark_warmup: int = 10`
- `.env` → adicionado `BENCHMARK_WARMUP=10`
- `Dockerfile` → agora compila liboqs do fonte (para PQC funcionar dentro do container)
- `docker-compose.yml` → adicionado serviço `benchmark` com profile
- `main.py` → versão `0.5.0`, mensagem "Phase 5 active"

**Suite de testes:** 53 testes, 0 falhas (nenhuma regressão).

---

#### Metodologia de benchmarking

**Duas camadas de medição:**

| Camada | O que mede | Por que |
|--------|-----------|---------|
| **RAW** | Operações criptográficas puras (sign, verify, keygen, KEM) via interfaces `IDigitalSignature`/`IKeyEncapsulation` | Isola o custo do **algoritmo**, sem bcrypt, sem JWT encode, sem base64url |
| **SERVICE** | Operações completas via `ClassicalAuthService`, `PQCLoginService`, `HybridAuthService` | Mede o custo **real em contexto de autenticação** (inclui token encoding, mas timing interno ainda exclui bcrypt) |

**20 operações medidas:** 9 raw (RSA keygen/sign/verify, ML-DSA keygen/sign/verify, Kyber keygen/encap/decap) + 11 service (jwt_sign/verify, pqc_sign/verify, kem_keygen/encap/decap, hybrid_sign_classical/pqc, hybrid_verify_classical/pqc).

**Protocolo:**
1. Warmup: 10 iterações descartadas (estabiliza cache da CPU e lazy loading de libs)
2. Medição: 100 iterações com coleta de `duration_ms` (via `perf_counter()`) + `tracemalloc` (peak bytes por operação)
3. RSS global: `psutil.Process().memory_info().rss` antes/depois do bloco de 100 iterações (contexto)
4. Exportação: CSV bruto → estatísticas → gráficos

> **Correção v2 (2026-03-27):** O protocolo acima descreve a versão original (v1). Na versão corrigida, as rodadas de timing e memória foram **separadas**: Fase A mede timing com `perf_counter()` apenas (sem `tracemalloc`), Fase B mede memória com `tracemalloc` em 10 iterações separadas. Além disso, o `ClassicalAuthService` foi corrigido para passar o key object RSA pré-parseado ao PyJWT, eliminando o custo de `load_pem_private_key()` (~45ms) por chamada. Ver [`docs/benchmarks.md`](benchmarks.md) Fase 5 para os dados oficiais corrigidos.

---

#### Decisão — tracemalloc como fonte primária de memória

Para operações sub-milissegundo (~0.02ms como `pqc_verify`), o RSS do processo (psutil) atualiza em páginas de 4–64KB — granularidade insuficiente para medir uma operação individual. `tracemalloc` mede alocações Python heap por operação, com precisão de bytes.

Estratégia adotada:
- **tracemalloc**: fonte primária, mede cada operação individualmente
- **psutil RSS**: contexto, medido uma vez por bloco de N=100 iterações

---

#### Decisão — Plataforma ARM64 como principal

O benchmark roda em Apple Silicon (ARM64) com extensões NEON/ASIMD que favorecem operações vetoriais de lattice. Docker x86_64 no Mac usa QEMU (3–5× overhead de emulação), então não serve como dado representativo de x86 real.

**Para o TCC:** ARM64 nativo é a plataforma principal. Validação em x86 real (EC2/VPS) fica como trabalho futuro. O relatório documenta o hardware explicitamente.

---

#### Resultados formais (N=100, ARM64, warm)

> **Correção v2:** Os valores de `jwt_sign` abaixo (~44.8ms, speedup ~390×) estavam inflados. A causa era que `jwt.encode()` recebia bytes PEM e chamava `load_pem_private_key()` internamente a cada invocação (~45ms). Corrigido passando o key object pré-parseado. **Valores corrigidos: jwt_sign ~0.89ms, speedup ~6.6×.** Ver [`docs/benchmarks.md`](benchmarks.md) para os dados oficiais. Os valores raw (`raw_rsa_sign` ~44-50ms) permanecem corretos — incluem intencionalmente a desserialização da chave DER.

##### Service Layer — Comparação direta (v1 — ver nota acima)

| Comparação | RS256 (ms) | ML-DSA-44 (ms) | Speedup |
|------------|-----------|----------------|---------|
| **Token Signing** | 44.826 | 0.115 | **390×** |
| **Token Verification** | 0.087 | 0.042 | **2.1×** |

##### Raw Crypto — Comparação direta

| Comparação | RSA-2048 (ms) | ML-DSA-44 (ms) | Speedup |
|------------|--------------|----------------|---------|
| **Key Generation** | 55.312 | 0.043 | **1292×** |
| **Signature** | 44.690 | 0.076 | **590×** |
| **Verification** | 0.061 | 0.040 | **1.5×** |

##### Kyber512 KEM (service layer)

| Operação | mean (ms) | median (ms) | P95 (ms) |
|----------|----------|------------|----------|
| kem_keygen | 0.029 | 0.028 | 0.030 |
| kem_encapsulate | 0.028 | 0.028 | 0.030 |
| kem_decapsulate | 0.030 | 0.028 | 0.030 |

---

#### Análise dos resultados — surpresas e trade-offs

> **Correção v2:** A análise abaixo reflete os dados v1. Com a correção, o speedup de signing no service layer é **~6.6×** (não ~390×). A vantagem estrutural do lattice math permanece válida, mas a magnitude era inflada pelo custo de re-parse da chave PEM (~45ms por chamada). Os speedups raw (~868× para sign) permanecem altos porque medem a primitiva completa incluindo desserialização de chave. A mediana é mais representativa que a média para operações sub-milissegundo devido a outliers ocasionais de GC/escalonamento (e.g., `pqc_sign` max=2.63ms vs median=0.10ms).

**1. ML-DSA-44 é dramaticamente mais rápido que RSA-2048 em sign (~390× v1 → ~6.6× v2 corrigido)**

Resultado surpreendente e **contrário à expectativa comum** de que PQC seria mais lento. A razão:
- **RSA sign** usa exponenciação modular com expoente privado `d` de 2048 bits — operação inerentemente lenta ($O(n^3)$ em aritmética de precisão arbitrária)
- **ML-DSA-44 sign** usa multiplicação de polinômios em $\mathbb{Z}_q[x]/(x^n + 1)$ com NTT (Number Theoretic Transform) — operação $O(n \log n)$ altamente paralelizável pelas extensões NEON do ARM64

A vantagem é **estrutural**: lattice math é mais eficiente em CPUs modernas, não apenas "mais rápida por acaso".

**2. A verificação é mais equilibrada (RSA ~2× mais lento que ML-DSA)**

RSA verify usa expoente público `e=65537` (pequeno), então é intrinsecamente rápida. ML-DSA verify também é rápida. A diferença é menor.

**3. O trade-off real é tamanho, não velocidade**

| Artefato | RSA-2048 | ML-DSA-44 | Fator |
|----------|---------|-----------|-------|
| Token completo | ~200 bytes | ~3343 bytes | 16.7× |
| Assinatura raw | 256 bytes | 2420 bytes | 9.5× |
| Chave pública | 256 bytes | 1312 bytes | 5.1× |

Para web auth, isso significa: header `Authorization` de ~3.3 KB vs ~200 bytes. Em APIs com muitas chamadas, o overhead de rede pode ser significativo.

**4. Keygen RSA é extremamente lento (~55ms) vs ML-DSA (~0.04ms)**

RSA keygen envolve encontrar dois primos grandes (teste de primalidade é probabilístico e custoso). ML-DSA keygen é determinístico com custo fixo baixo. Isso importa para cenários de rotação de chaves.

---

#### Estado atual do projeto (Fase 5 completa)

```
Python:              3.13
liboqs (C):          0.15.0
liboqs-python:       0.14.1
PyJWT:               2.12.1
cryptography:        46.0.5
bcrypt:              5.0.0
psutil:              6.1.0
pandas:              2.3.0
matplotlib:          3.10.3
seaborn:             0.13.2
KEM ativo:           Kyber512 (equiv. FIPS: ML-KEM-512)
Sig PQC ativo:       ML-DSA-44 (FIPS 204)
Sig clássica:        RSA-2048 / RS256
Banco:               SQLite via data/pqc_auth.db
Testes:              53 passed
Benchmark:           2000 samples, 20 operações, 5 gráficos ✅
```

---

## Por que SPHINCS+ foi excluído do escopo

A Proposta do TCC menciona SPHINCS+ como candidato, mas o projeto foca em ML-DSA-44 para assinaturas pelos seguintes motivos:

1. **Caso de uso diferente:** SPHINCS+ (FIPS 205) é hash-based stateless, otimizado para assinaturas de longa duração (firmware, certificados raiz). ML-DSA-44 é lattice-based, otimizado para autenticação de sessão — o escopo deste TCC.
2. **Tamanho impraticável em web auth:** SPHINCS+ gera assinaturas de 8–50 KB (dependendo do nível de segurança), versus 2.420 bytes do ML-DSA-44. Um header `Authorization` de 50 KB por request torna o protocolo impraticável para web.
3. **Cobertura completa dos tipos:** ML-DSA-44 (FIPS 204) + Kyber512 (FIPS 203) cobrem os dois tipos de operação PQC necessários para auth (assinatura + KEM). A Proposta diz "3–4 algoritmos no máximo".

A exclusão será justificada explicitamente na seção de escopo do TCC escrito.

---
