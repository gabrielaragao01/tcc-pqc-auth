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
