# Sequências de Acordes Customizadas — Design Document

## Current Context

- O backend é um único arquivo Flask (`main.py`) que carrega
  `data/top/dataset_final.csv` em memória no startup: 67.585 músicas e 9
  colunas, sem banco de dados (`main.py:49-98`).
- A busca por sequência é um lookup exato em um dicionário de 6 chaves
  hardcoded (`main.py:40-45`). O endpoint recebe `sequencia=Bm,G,D,A`, remove
  as vírgulas (`main.py:190-194`) e filtra músicas pela tag pré-computada
  `SEQ_FAMOSA` (`main.py:203-223`).
- Sequência desconhecida ou com caixa diferente retorna `[]` com HTTP 200.
- As 6 sequências originais usam a tag do CSV. A regra que gerou essa tag está
  em `scripts/generate_data_set.py:7-24`: acordes da música em minúsculas,
  todos contidos no conjunto da sequência e sequência como trecho contíguo.
- O frontend tem 4 sequências hardcoded em
  `static/assets/js/controllers/sequencia.js:2-37`; o backend tem 6. A página
  `#/porsequencia` não tem formulário de cadastro.
- Músicas e gêneros continuam vindo do CSV em memória. Só o catálogo de
  sequências passa a ser persistido.
- O deploy é local-only, em um único container Docker
  (`docs/adr/0001-local-only-docker-deploy.md`), sem volume atualmente.
- Não existem migrations, suíte de testes nem endpoints de escrita.

## Requirements

### Functional Requirements

- Qualquer visitante, sem login, pode cadastrar uma sequência com nome e lista
  ordenada de acordes.
- O catálogo de sequências é persistido em banco e sobrevive a reinícios do
  servidor e à recriação do container quando usado volume nomeado.
- `GET /sequencias` retorna o catálogo real para o frontend, substituindo a
  lista hardcoded.
- `GET /similares?sequencia=...` aceita qualquer sequência do catálogo
  (original ou nova) e mantém o formato de resposta atual.
- As 6 sequências originais retornam exatamente o mesmo conjunto de músicas de
  hoje.
- `POST /sequencias` retorna o total de músicas encontradas no momento do
  cadastro; zero resultados é permitido, mas sinalizado no frontend.
- Todos os endpoints continuam retornando `json.dumps(...)`, não `jsonify`.
- A aplicação continua em um único container Docker local.
- Fora do escopo: autenticação, moderação, edição/remoção de sequências,
  migração de músicas/gêneros para o banco e mudança da stack frontend.

### Non-Functional Requirements

- Usar apenas `sqlite3` da biblioteca padrão; não adicionar serviço externo nem
  dependência de runtime.
- Seed do catálogo original idempotente: reiniciar não duplica as 6 entradas
  nem sobrescreve sequências de visitantes.
- Matching e contagem percorrem 67.585 músicas em memória; o custo deve ser
  medido e aceitável para uso local.
- Normalização explícita e única para sequência e música: `strip().lower()`.
- `normalized_key` única no banco para impedir duplicatas por caixa/espaços.
- Respostas e erros continuam em JSON serializado como string.
- Entrada anônima deve ser validada e limitada para evitar payloads abusivos.
- Ordem dos resultados continua como hoje; a comparação de regressão deve usar
  conjuntos ordenados de `id_unico_musica`, pois `generos` vem de um `set`
  (`main.py:38`, `main.py:92`).

## Design Decisions

### 1. Persistência do catálogo

Usar SQLite em arquivo, via `sqlite3` da stdlib, com caminho padrão
`instance/sequences.db` (no container, `/app/instance/sequences.db`).

- Rationale: cabe no container único, não exige serviço adicional e atende à
  persistência necessária.
- Rationale: `sqlite3` já está disponível no Python 3.9; não altera
  `requirements.txt`.
- Trade-off: sem framework de migration; o schema é criado com
  `CREATE TABLE IF NOT EXISTS` e o seed é idempotente.

### 2. Matching unificado

Todas as sequências usam a mesma regra da tag `SEQ_FAMOSA`, sobre
`Musica.cifra`:

- normalizar sequência e cada acorde da música com a mesma função;
- exigir que todos os acordes da música pertençam ao conjunto da sequência;
- exigir que a sequência seja uma fatia contígua de `musica.cifra`, na ordem e
  com as repetições originais.

Rationale: replica `scripts/generate_data_set.py:7-24` e preserva exatamente o
resultado das 6 originais.

Trade-off: a regra é restritiva e pode gerar zero resultados para sequências
novas. O contador no cadastro torna isso visível imediatamente.

### 3. Chave normalizada

Manter o formato atual de concatenação sem separador, agora normalizado para
minúsculas: `["Bm","G","D","A"]` → `bmgda`.

- Rationale: hoje o backend já remove as vírgulas e usa `BmGDA` como chave
  (`main.py:190-194`); o formato sem delimitador é preservado.
- Rationale: uma única função `chave_normalizada` evita divergência entre
  seed, `POST` e busca.
- Trade-off: a chave persistida deixa de preservar a caixa original; a grafia
  original fica em `nome` e `acordes_json`.

### 4. Contrato da API

Adicionar `GET /sequencias` e `POST /sequencias`, mantendo
`GET /similares?sequencia=...` como caminho de busca.

- `GET /sequencias` lista o catálogo.
- `POST /sequencias` valida, grava e devolve `total_musicas` calculado com o
  matcher.
- `201` para criação, `400` para payload inválido e `409` para duplicata
  normalizada.
- Rationale: reaproveita o fluxo de busca existente e concentra a contagem no
  cadastro, sem exigir uma chamada extra do frontend.

### 5. Frontend orientado pelo backend

Substituir a lista hardcoded por carregamento de `GET /sequencias` e adicionar
formulário de cadastro.

- Rationale: o catálogo passa a ter uma única fonte de verdade.
- Rationale: exibir `total_musicas` no retorno do `POST` resolve o principal
  risco da semântica restrita: o usuário vê zero resultados antes de confiar na
  sequência.
- Trade-off: o carregamento do catálogo e o cadastro passam a depender do
  backend; a busca existente não muda.

## Technical Design

### 1. Core Components

Novo módulo `sequencias.py`, responsável por normalização, chave, matcher,
schema, seed e acesso ao SQLite:

```python
import sqlite3
from typing import Optional

from musica import Musica


def normalizar_acorde(acorde: str) -> str:
    """Remove espaços nas bordas e normaliza a caixa."""

def chave_normalizada(acordes: list[str]) -> str:
    """Concatena os acordes normalizados, sem separador."""

def aparece_na_musica(
    sequencia_normalizada: list[str],
    musica: Musica,
) -> bool:
    """Aplica a regra estrita sobre musica.cifra."""

def init_db(caminho: str) -> sqlite3.Connection:
    """Cria o arquivo, o schema e garante o diretório."""

def seed_sequencias_originais(conn: sqlite3.Connection) -> None:
    """Insere as 6 sequências com is_builtin=1, sem duplicar."""

def listar_sequencias(conn: sqlite3.Connection) -> list[dict]:
    """Retorna o catálogo para GET /sequencias."""

def buscar_por_chave(
    conn: sqlite3.Connection,
    chave: str,
) -> Optional[dict]:
    """Resolve uma sequência pela normalized_key."""

def criar_sequencia(
    conn: sqlite3.Connection,
    nome: str,
    acordes: list[str],
) -> dict:
    """Valida, persiste e retorna a sequência criada."""
```

O matcher deve usar `Musica.cifra` (`musica.py:16`), nunca
`Musica.acordes` (`musica.py:17`), porque o segundo é `list(set(cifra))` e
perde ordem/repetições.

### 2. Data Models

Uma única tabela:

```sql
CREATE TABLE IF NOT EXISTS sequences (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nome           TEXT NOT NULL,
    acordes_json   TEXT NOT NULL,
    normalized_key TEXT NOT NULL UNIQUE,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    is_builtin     INTEGER NOT NULL DEFAULT 0
);
```

- `acordes_json` guarda a lista ordenada na grafia original.
- `normalized_key` guarda a concatenação minúscula sem separador.
- `is_builtin=1` identifica as 6 originais sem criar um caminho de busca
  separado.
- Seed usa `INSERT OR IGNORE` pela `normalized_key` para ser idempotente.

### 3. Integration Points

- **Startup:** após carregar o CSV, abrir/criar o SQLite e executar o seed.
  O diretório do banco deve ser criado se não existir.
- **Busca:** em `/similares`, ramo `sequencia` (`main.py:190-197`):
  - dividir `sequencia_tag` por vírgula;
  - normalizar cada acorde;
  - gerar `normalized_key`;
  - buscar no SQLite;
  - se não existir, retornar `[]` como hoje;
  - se existir, filtrar com `apply_filtro` (`main.py:266-272`), aplicar o
    matcher e paginar com `get_pagina` (`main.py:226-228`).
- **Formato da resposta:** manter o mesmo dicionário de
  `get_similares_por_sequencia` (`main.py:210-220`), sem `diferenca`.
- **Cadastro:** `POST /sequencias` lê JSON, valida, verifica duplicata pela
  chave, grava e calcula `total_musicas` percorrendo todas as músicas.
- **Catálogo:** `GET /sequencias` retorna `id`, `nome`, `acordes`,
  `normalized_key`, `is_builtin` e `created_at`.
- **Frontend → backend:** `#/porsequencia` chama `GET /sequencias` ao carregar,
  envia `POST /sequencias` no formulário e mantém
  `similares?sequencia=...` na busca (`sequencia.js:63-90`).
- **Docker → SQLite:** montar volume nomeado em `/app/instance` para que o
  arquivo sobreviva à remoção/recontrução do container.

### 4. Files Changes

| Arquivo | Mudança |
|---|---|
| `main.py` | Importar o novo módulo; inicializar banco/seed; trocar o lookup do dicionário pelo SQLite; adicionar `GET /sequencias` e `POST /sequencias`. |
| `sequencias.py` (novo) | Normalização, chave, matcher, schema, seed e funções de acesso ao SQLite. |
| `static/assets/js/controllers/sequencia.js` | Remover as 4 sequências hardcoded; carregar catálogo do backend; adicionar cadastro e exibição de `total_musicas`. |
| `static/templates/sequencia.html` | Adicionar formulário (nome + acordes ordenados) e área de aviso/contador. |
| `Dockerfile` | Declarar `VOLUME /app/instance`. |
| `README.md` | Documentar execução com `-v deciframe-data:/app/instance`. |
| `.gitignore` | Ignorar `instance/`. |
| `.dockerignore` | Ignorar `instance/` para não copiar banco local para a imagem. |
| `tests/test_sequencias.py` (novo) | Testes unitários e de integração com `unittest` e `Flask.test_client`. |
| `docs/features/sequencias-customizadas/04-test-report.md` | Registrar cobertura e resultado da regressão obrigatória. |

Nenhum outro arquivo deve ser alterado nesta implementação. Em particular,
`musica.py` permanece como está e o CSV não é migrado.

## Implementation Plan

1. Phase 1: Persistência e regra de matching
   - Criar `sequencias.py` com `init_db`, schema, seed idempotente,
     normalização, chave e matcher.
   - Definir o caminho padrão `instance/sequences.db` e criar o diretório.
   - Semear as 6 originais com `is_builtin=1`.
   - Timeline: sem prazo rígido; concluir antes de alterar os endpoints.

2. Phase 2: Backend
   - Inicializar banco e seed no startup de `main.py`.
   - Alterar o ramo `sequencia` de `/similares` para resolver no SQLite e
     aplicar o matcher.
   - Manter o mesmo formato de resposta e o comportamento `[]` para sequência
     inexistente.
   - Adicionar `GET /sequencias` e `POST /sequencias` com validação,
     `total_musicas` e `json.dumps`.
   - Timeline: sem prazo rígido.

3. Phase 3: Frontend
   - Remover `sequencia1..4` e carregar `GET /sequencias`.
   - Adicionar formulário com nome e acordes em ordem.
   - Enviar `POST /sequencias`; exibir o total retornado e aviso destacado
     quando for zero.
   - Atualizar a lista local após o cadastro, sem quebrar a busca existente.
   - Timeline: sem prazo rígido.

4. Phase 4: Empacotamento e documentação
   - Adicionar volume ao Dockerfile, ignorar `instance/` e atualizar o comando
     de execução no README.
   - Documentar que sem volume o banco não sobrevive a `docker rm`.
   - Timeline: sem prazo rígido.

5. Phase 5: Validação
   - Implementar os testes da seção Testing Strategy.
   - Capturar/preparar o baseline das 6 originais e rodar a regressão.
   - Registrar cobertura e resultado em
     `docs/features/sequencias-customizadas/04-test-report.md`.
   - Subir a aplicação com Docker + volume e validar cadastro, busca e
     persistência após recriar o container.
   - Timeline: sem prazo rígido.

## Testing Strategy

### Unit Tests

- `normalizar_acorde`: caixa, espaços nas bordas e token vazio.
- `chave_normalizada`: `Bm,G,D,A` e `bm,g,d,a` geram `bmgda`.
- `aparece_na_musica`:
  - trecho contíguo presente;
  - mesma sequência fora de ordem;
  - acorde da música fora do conjunto da sequência;
  - `cifra` vazia;
  - acordes repetidos;
  - sequência de um único acorde;
  - caixa diferente entre sequência e música.
- `init_db`/`seed_sequencias_originais`: seed idempotente, 6 registros e
  `is_builtin=1`.
- `criar_sequencia`: duplicata normalizada, payload inválido e persistência.

Usar `unittest`; não adicionar `pytest`.

### Integration Tests

- **Regressão obrigatória:** para cada um dos 6 ids originais, comparar o
  resultado do matcher com `str(id) in musica.seqs_famosas` em todas as 67.585
  músicas. Comparar conjuntos ordenados de `id_unico_musica`, não a ordem bruta.
- Comparar o endpoint novo com o baseline capturado antes da mudança, incluindo
  paginação e filtro por gênero.
- `POST /sequencias` seguido de `GET /sequencias` e de
  `/similares?sequencia=...` para uma sequência nova.
- `POST` com `total_musicas == 0` deve retornar `201` e manter o cadastro.
- Verificar que `total_musicas` é igual ao tamanho da lista completa e não
  paginada da busca correspondente.
- Persistência: fechar e reabrir o banco; recriar o container Docker usando o
  volume nomeado.
- Testar sequência inexistente e caixa diferente retornando o mesmo resultado
  normalizado.

## Observability

Não se aplica: o projeto não possui logging estruturado nem métricas, e esta
mudança não introduz essa infraestrutura. Os logs padrão do gunicorn/Flask são
suficientes para o ambiente local.

## Future Considerations

### Potential Enhancements

- Cache ou índice em memória para evitar varrer 67.585 músicas em cada busca e
  em cada cadastro.
- Normalização mais rica de acordes (`C#`/`Db`, barras, extensões).
- Moderação/edição/remoção de sequências e limites de abuso.
- Exibir contagem também no catálogo, não só no retorno do cadastro.

### Known Limitations

- A semântica estrita pode produzir poucos ou nenhum resultado para sequências
  novas.
- O cadastro faz uma varredura completa adicional para calcular
  `total_musicas`.
- Não há autenticação, rate limiting ou moderação; o catálogo é aberto por
  requisito.
- A ordem dos resultados continua dependente da ordem dos gêneros, que não é
  determinística entre processos.

## Dependencies

### Development Dependencies

- Python 3.9 e `sqlite3` da stdlib.
- Flask 3.1.3 e gunicorn 23.0.0 já existentes em `requirements.txt`.
- `unittest` da stdlib para os testes.
- Docker para validar volume e recriação do container.

Nenhuma dependência nova de runtime deve ser adicionada.

## Security Considerations

- O cadastro é anônimo por requisito; não introduzir login nesta mudança.
- Validar tipo e tamanho de `nome` e `acordes`; rejeitar listas vazias,
  elementos não textuais e payloads excessivos.
- Usar consultas SQL parametrizadas; nunca concatenar entrada do usuário na
  query.
- A `normalized_key` com `UNIQUE` evita duplicatas e reduz crescimento
  acidental do catálogo.
- O endpoint de cadastro executa uma varredura completa; limitar quantidade de
  acordes e tamanho do nome para reduzir abuso simples.
- Rate limiting, moderação e autenticação ficam fora do escopo desta mudança.

## Rollout Strategy

1. Desenvolvimento: implementar fases 1–3 localmente.
2. Testes: rodar `unittest`, regressão das 6 originais e testes de API.
3. Empacotamento: construir a imagem Docker e subir com volume nomeado.
4. Validação local: cadastrar sequência, buscar, reiniciar e recriar o
   container, confirmando persistência.
5. Monitoramento: não há staging/produção; a validação é manual e local,
   conforme `docs/adr/0001-local-only-docker-deploy.md`.

## References

- `research/sequencias-customizadas-propostas.md` — Proposta 2, base deste
  plano.
- `research/sequencias-customizadas.md` — pesquisa do comportamento atual.
- `docs/features/sequencias-customizadas/00-enunciado.md` — requisitos e
  restrições.
- `docs/adr/0001-local-only-docker-deploy.md` — deploy local em container
  único.
- `/home/iorran/reppit-framework/templates/design_doc_template.md` — estrutura
  seguida por este documento.
- `main.py:40-45`, `main.py:190-223`, `main.py:226-272` — catálogo, busca e
  paginação atuais.
- `musica.py:16-18` — `cifra`, `acordes` e `seqs_famosas`.
- `scripts/generate_data_set.py:7-24` — regra original da tag `SEQ_FAMOSA`.
- `static/assets/js/controllers/sequencia.js:2-90` — catálogo hardcoded e fluxo
  de busca.
