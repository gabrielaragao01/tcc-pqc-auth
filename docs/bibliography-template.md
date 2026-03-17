# Revisão Bibliográfica — TCC PQC Web Auth

> **Nota:** Este arquivo é um template estruturado. Preencha cada seção com as referências bibliográficas reais. As subseções indicam os tópicos que precisam ser cobertos na revisão.

---

## 1. Criptografia Pós-Quântica: Contexto e Motivação

- Ameaça do computador quântico ao RSA/ECDSA (algoritmo de Shor, complexidade polinomial)
- Cronograma NIST PQC: chamada 2016, rounds 1-4, finalização agosto 2024
- NIST FIPS 203 — ML-KEM (Module-Lattice-Based Key-Encapsulation Mechanism Standard)
- NIST FIPS 204 — ML-DSA (Module-Lattice-Based Digital Signature Standard)
- NIST FIPS 205 — SLH-DSA (Stateless Hash-Based Digital Signature Standard)

**Referências sugeridas:**
- NIST SP 800-208 / FIPS 203, 204, 205 (documentos oficiais)
- Bernstein & Lange, "Post-quantum cryptography" (Nature, 2017)
- Chen et al., "Report on Post-Quantum Cryptography" (NISTIR 8105, 2016)

---

## 2. Algoritmos Implementados

### ML-KEM-512 (Kyber512)
- Fundamentos de lattice: Module Learning With Errors (MLWE)
- Parâmetros de segurança: nível 1 (equivalente a AES-128)
- Tamanho de artefatos: chave pública 800 B, chave privada 1632 B, ciphertext 768 B

### ML-DSA-44 (Dilithium2)
- Fundamentos: Module Learning With Errors (MLWE) + Module Short Integer Solution (MSIS)
- Parâmetros de segurança: nível 2 (equivalente a AES-128)
- Tamanho de artefatos: chave pública 1312 B, chave privada 2528 B, assinatura 2420 B

**Referências sugeridas:**
- Ducas et al., "CRYSTALS-Dilithium: A Lattice-Based Digital Signature Scheme" (TCHES 2018)
- Bos et al., "CRYSTALS - Kyber: a CCA-secure module-lattice-based KEM" (EuroS&P 2018)

---

## 3. Autenticação Web Clássica (Baseline)

- JWT — JSON Web Tokens (RFC 7519)
- JWS — JSON Web Signature (RFC 7515)
- RSA-PSS com SHA-256: mecanismo, vantagens sobre PKCS#1 v1.5
- Tamanho de token JWT RS256 e overhead em cabeçalhos HTTP

**Referências sugeridas:**
- Jones et al., RFC 7519 — JSON Web Token (JWT)
- Jones et al., RFC 7515 — JSON Web Signature (JWS)

---

## 4. PQC em Autenticação Web

- Desafios de adoção: tamanho de chave/assinatura, compatibilidade com TLS/HTTP
- PQC-TLS: experimentos NIST/IETF com CRYSTALS em TLS 1.3
- PQC-JWT: trabalhos acadêmicos sobre tokens pós-quânticos

**Referências sugeridas:**
- Paquin et al., "Benchmarking Post-Quantum Cryptography in TLS" (PQCrypto 2020)
- Bindel et al., "Transitioning to a Quantum-Resistant Public Key Infrastructure" (PQCrypto 2017)

---

## 5. Ferramentas e Bibliotecas

- Open Quantum Safe (OQS) / liboqs: arquitetura, algoritmos suportados, linguagens
- liboqs-python: wrapper Python, limitações de versão
- FastAPI: framework ASGI, adequação para benchmarking de latência
- PyJWT + cryptography: implementação RSA em Python

**Referências sugeridas:**
- Stebila & Mosca, "Post-quantum key exchange for the Internet and the Open Quantum Safe project" (SAC 2016)
- Documentação oficial liboqs: https://github.com/open-quantum-safe/liboqs

---

## 6. Métricas de Desempenho em Criptografia

- Latência de operação criptográfica vs latência HTTP end-to-end
- Benchmarking com `time.perf_counter()` vs profiling de sistema
- Estudos comparativos RSA vs PQC em ambientes de produção
- Overhead de memória: alocações por operação lattice vs operação RSA

**Referências sugeridas:**
- Sikeridis et al., "Post-Quantum Authentication in TLS 1.3: A Performance Study" (NDSS 2020)
- Campagna et al., "Security of Cryptographic Primitives" (NIST, 2019)
