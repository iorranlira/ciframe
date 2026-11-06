# Propostas — Sequências de Acordes Customizadas

**Documento de propostas independente da pesquisa.**
A pesquisa de base está em [`research/sequencias-customizadas.md`](sequencias-customizadas.md)
e não é repetida aqui; este arquivo contém apenas as duas propostas de solução.
Data: 2026-11-06. Commit de referência: `fb97001`.

---

## Solution Proposals

**Context:**

- **Request:** permitir que qualquer visitante cadastre sequências de acordes
  anônimas e busque músicas por elas; persistir o catálogo em banco de dados
  (sobrevivendo a reinícios); manter os mesmos resultados das 6 sequências
  atuais; manter músicas/gêneros no CSV em memória; continuar no Dockerfile
  único e local-only; continuar respondendo com `json.dumps(...)`.
- **Research Source:** `research/sequencias-customizadas.md` §§1.3–1.5
  (endpoint e ordenação), 2.1–2.5 (catálogo, tag `SEQ_FAMOSA`, matching e
  vocabulário), 3.1–3.2 (CSV), 4.2–4.3 (frontend), 5.1–5.3
  (persistência/Docker/testes), 8 (baseline).
  Também `docs/features/sequencias-customizadas/00-enunciado.md:45-77` e
  `docs/adr/0001-local-only-docker-deploy.md:1-16`.
- **Gaps da pesquisa:** a pesquisa documenta o estado atual e mede os dados,
  mas não decide qual definição de matching usar, nem o banco, nem o formato
  de API. Essas são as decisões tomadas em cada proposta. A pesquisa também
  registra que não existe suíte de testes hoje (§5.3), então a validação de
  qualquer proposta inclui criar esse harness.

---

## Proposal 1 — SQLite + catálogo único com “caminho legado” para as 6 originais e matching contíguo para sequências novas

### Overview

O catálogo completo passa a viver em SQLite. As 6 sequências originais são
semeadas com um `legacy_tag_id` (0–5) e continuam usando a tag `SEQ_FAMOSA`
exatamente como hoje; sequências cadastradas por visitantes não têm tag e são
resolvidas em tempo real por um matcher de subsequência contígua sobre
`Musica.cifra`. O frontend deixa de ter a lista hardcoded e passa a consumir
`GET /sequencias` e a cadastrar via `POST /sequencias`.

### Key Changes

**Persistência**

- Novo módulo, por exemplo `sequencias_repo.py`, usando `sqlite3` da stdlib.
- Banco em `/app/instance/sequences.db` (fora de `data/`, para não conflitar
  com o CSV copiado por `COPY . .`).
- Schema proposto:

  ```sql
  CREATE TABLE IF NOT EXISTS sequences (
      id             INTEGER PRIMARY KEY,
      nome           TEXT NOT NULL,
      acordes_json   TEXT NOT NULL,
      normalized_key TEXT NOT NULL UNIQUE,
      legacy_tag_id  INTEGER NULL,
      created_at     TEXT NOT NULL
  );
  ```

- Seed idempotente no startup com as 6 entradas de `main.py:40-45`, nomes de
  `data/mapeamento_sequencias_famosas.txt:1-6`, `legacy_tag_id` 0–5.
- `CREATE TABLE IF NOT EXISTS`; sem framework de migration.

**Backend (`main.py`)**

- Manter `sequencias` (`main.py:40-45`) apenas como fallback de resolução
  legada.
- Adicionar `GET /sequencias`, retornando via `json.dumps` uma lista de
  `{id, nome, acordes, origem}`.
- Adicionar `POST /sequencias` recebendo
  `{"nome": "...", "acordes": ["Bm","G","D","A"]}`; validar lista não vazia,
  tokens permitidos, limite de tamanho e duplicidade; responder 201/400/409
  com `json.dumps`.
- No ramo `sequencia` de `/similares` (`main.py:190-197`), resolver a chave
  normalizada no SQLite:
  - se `legacy_tag_id` não for nulo, chamar `get_similares_por_sequencia`
    (`main.py:203-223`) sem alteração;
  - se for sequência nova, aplicar o novo matcher e reutilizar
    `apply_filtro`/`get_pagina` (`main.py:226-228`, `main.py:266-272`).

**Matcher novo**

- `aparece_contigua(sequencia, musica.cifra)` comparando tokens na ordem,
  preservando repetições.
- Usar `musica.cifra`, que é a lista ordenada (`musica.py:16`), e não
  `musica.acordes`, que perde ordem (`musica.py:17`).
- Normalização de caixa/espaços deve ser decidida e aplicada de forma
  explícita.

**Frontend**

- Remover a lista fixa `sequencia1..4`
  (`static/assets/js/controllers/sequencia.js:2-37`) e carregar
  `GET /sequencias` no controller.
- Adicionar formulário no template (`static/templates/sequencia.html`) com
  nome e acordes ordenados; implementar `cadastrarSequencia` com
  `$http.post` e recarga da lista.
- O fluxo de busca existente (`sequencia.js:63-90`) e a URL
  `similares?sequencia=...` permanecem.

**Docker/execução**

- Adicionar `VOLUME /app/instance` ao `Dockerfile`.
- Documentar `docker run -p 8080:8080 -v deciframe-data:/app/instance ciframe`.
- Adicionar `instance/` ao `.gitignore` e `.dockerignore`.
- Sem volume, o arquivo sobrevive a `docker restart`, mas não a
  `docker rm`/recriação.

### Trade-offs

- **Prós:** preserva exatamente o comportamento das 6 originais, porque o
  caminho delas continua sendo a tag do CSV; permite um matching mais natural
  para sequências novas; mudança mínima no endpoint e no template existentes.
- **Contras:** convivem duas semânticas de matching — a mesma lista de acordes
  pode retornar 199 músicas como original e 866 como sequência nova (números
  de `research/sequencias-customizadas.md` §2.3). Isso exige regra explícita
  de duplicidade para impedir que alguém recadastre `BmGDA` como sequência
  customizada; cria também um segundo caminho de leitura e mais superfície de
  teste.
- **Impacto:** `main.py`, novo módulo de persistência,
  `static/assets/js/controllers/sequencia.js`,
  `static/templates/sequencia.html`, `Dockerfile`, README,
  `.gitignore`/`.dockerignore`.

### Validation

- **Regressão:** capturar, antes da mudança e com o código atual, todas as
  páginas de `/similares?sequencia=<chave>` para as 6 chaves. Como a ordem dos
  gêneros varia entre processos (`main.py:38`, `main.py:92`;
  `research/sequencias-customizadas.md` §1.5), comparar conjuntos ordenados de
  `id_unico_musica`, não a ordem bruta. Repetir também com `generos=Rock` ou
  outro filtro.
- **Testes novos:** `unittest` + `Flask.test_client` (sem dependência nova de
  runtime) para matcher, GET/POST, duplicidade, validação, paginação e filtro
  por gênero.
- **Persistência:** criar sequência, reiniciar o processo/container e verificar
  leitura; repetir com remoção e recriação do container usando o volume
  nomeado.
- **Performance:** medir o tempo do matcher sobre as 67.585 músicas e comparar
  com o caminho legado; definir um limite interno antes de expor o endpoint.
- **Frontend:** fluxo manual/e2e: catálogo carregado do backend, cadastro,
  reload, busca por original e por sequência nova.

### Open Questions

- “Mesmos resultados” significa o mesmo conjunto de músicas ou também a mesma
  ordem? A ordem já não é estável hoje, o que favorece comparar conjuntos.
- Política de duplicidade: rejeitar com 409, retornar a existente ou permitir
  duplicata? Qual a chave de normalização (caixa, espaços, `C#` vs `Db`,
  acordes com barra)?
- Qual é a definição correta de “aparece” para sequências novas: contígua,
  contígua após colapsar repetições, subsequência com lacunas ou conjunto de
  acordes? A pesquisa apenas mede essas opções (§2.3).
- Persistência deve sobreviver a `docker rm`/rebuild? Isso determina se o
  volume é obrigatório ou apenas recomendado.
- Limites de tamanho/quantidade de acordes e proteção contra abuso de `POST`
  anônimo.

---

## Proposal 2 — SQLite com um único matcher que reproduz exatamente a semântica da tag `SEQ_FAMOSA` para todas as sequências

### Overview

O catálogo também vai para SQLite, mas sem caminho legado separado: todas as
sequências — originais e novas — usam um único matcher que replica
`scripts/generate_data_set.py:7-24`. Ou seja, uma música só é retornada se
todos os seus acordes pertencerem ao conjunto da sequência **e** a sequência
aparecer como trecho contíguo da `cifra`. Isso reproduz as 514 músicas atuais
para as 6 originais e trata qualquer sequência nova com a mesma regra.

A comparação usa `Musica.cifra` (lista ordenada de acordes, `musica.py:16`),
nunca `Musica.acordes` (`musica.py:17`), que é um `set` e perde a ordem. A
sequência cadastrada e os acordes da música passam pela mesma normalização de
caixa antes de qualquer comparação.

### Key Changes

**Persistência**

- Mesmo SQLite em `/app/instance/sequences.db`, com schema mais simples:

  ```sql
  CREATE TABLE IF NOT EXISTS sequences (
      id             INTEGER PRIMARY KEY,
      nome           TEXT NOT NULL,
      acordes_json   TEXT NOT NULL,
      normalized_key TEXT NOT NULL UNIQUE,
      created_at     TEXT NOT NULL,
      is_builtin     INTEGER NOT NULL DEFAULT 0
  );
  ```

- Seed idempotente das 6 originais marcadas como `is_builtin=1`; sem
  `legacy_tag_id`.

**Chave normalizada**

- Manter o formato atual da chave: concatenação dos acordes **sem separador**.
  Hoje o backend transforma `Bm,G,D,A` em `BmGDA` com
  `sequencia_tag.replace(',', '')` (`main.py:190-194`) e usa essa string como
  chave do dicionário (`main.py:40-45`).
- A única mudança é normalizar a caixa antes de concatenar. A mesma chave
  passa a ser calculada por uma função única, usada no seed, no `POST` e na
  busca:

  ```python
  def normalizar_acorde(acorde):
      return acorde.strip().lower()

  def chave_normalizada(acordes):
      return ''.join(normalizar_acorde(a) for a in acordes)
  ```

- Exemplo: `["Bm", "G", "D", "A"]` e `["bm", "g", "d", "a"]` produzem
  `bmgda`. O formato continua sendo a concatenação sem delimitadores; não se
  introduz `Bm-G-D-A`, `Bm,G,D,A` nem hash como chave persistida.
- `nome` e `acordes_json` preservam a grafia original para exibição; apenas
  `normalized_key` é canônica e minúscula. O `UNIQUE` em `normalized_key`
  impede que variações de caixa da mesma sequência virem registros distintos.

**Backend (`main.py`)**

- Substituir o dicionário `sequencias` (`main.py:40-45`) por consulta ao
  SQLite, sempre pela `normalized_key`.
- No ramo `sequencia` (`main.py:190-197`), transformar `sequencia_tag` em lista
  (`split(',')`), aplicar `normalizar_acorde` a cada item, gerar a chave com
  `chave_normalizada` e consultar o catálogo. Não usar `replace(',', '')`
  diretamente no endpoint; o mesmo helper deve ser usado no seed, no `POST` e
  na busca.
- Aplicar o matcher unificado a `musica.cifra` (lista ordenada), reutilizando
  `apply_filtro` e `get_pagina` (`main.py:226-228`, `main.py:266-272`).
- `get_similares_por_sequencia` (`main.py:203-223`) deixa de ser usado para
  busca; pode permanecer temporariamente como referência do comportamento
  legado.
- A coluna `SEQ_FAMOSA` continua no CSV e em `Musica.seqs_famosas`
  (`musica.py:18`) porque é o oráculo do teste de regressão obrigatório.

**Matcher unificado**

Implementar a mesma regra do gerador, sempre sobre `musica.cifra`:

```python
def aparece_na_musica(sequencia_normalizada, musica):
    cifra = [normalizar_acorde(a) for a in musica.cifra]

    if not set(cifra).issubset(set(sequencia_normalizada)):
        return False

    tamanho = len(sequencia_normalizada)
    return any(
        cifra[i:i + tamanho] == sequencia_normalizada
        for i in range(len(cifra) - tamanho + 1)
    )
```

1. **Normalização nos dois lados:** a sequência cadastrada passa por
   `normalizar_acorde` antes de ser persistida/comparada; cada acorde de
   `musica.cifra` passa pela mesma função dentro do matcher. O gerador faz
   `acorde.lower()` (`scripts/generate_data_set.py:7-24`), então caixa não
   altera o resultado.
2. **Origem da cifra:** usar `Musica.cifra` (`musica.py:16`), que preserva
   ordem e repetições. Não usar `Musica.acordes` (`musica.py:17`), criado com
   `list(set(cifra))`, que perde ordem e repetições.
3. **Conjunto contido:** todos os acordes da música devem pertencer ao conjunto
   da sequência.
4. **Trecho contíguo:** a sequência normalizada deve aparecer como fatia
   contígua da `cifra` normalizada, na mesma ordem e com as mesmas repetições.
5. **Sem mutação:** o matcher trabalha sobre uma lista normalizada derivada de
   `musica.cifra`; a grafia original da música e do catálogo não é alterada.

Essa combinação reproduz `get_famosas`; a pesquisa mostra que a função gera
exatamente as tags atuais em 67.585/67.585 linhas (§2.2).

**API**

- `GET /sequencias`: retorna o catálogo persistido, com `id`, `nome`,
  `acordes`, `normalized_key`, `is_builtin` e `created_at`, via
  `json.dumps(...)`.
- `POST /sequencias`: recebe `{"nome": "...", "acordes": ["Bm","G","D","A"]}`,
  valida lista não vazia, tokens permitidos, tamanho e duplicidade pela
  `normalized_key`, e responde com `json.dumps(...)`.
- A resposta de sucesso (`201`) inclui `total_musicas`: o número de músicas que
  o matcher retorna para a sequência recém-cadastrada, calculado sobre as
  67.585 músicas e sem paginação/filtro de gênero.
- Sequência com `total_musicas == 0` **não é bloqueada**: o cadastro continua
  permitido (catálogo aberto), mas o frontend exibe o aviso imediatamente.
- Duplicidade normalizada responde `409`; payload inválido responde `400`.
- A diferença em relação à Proposta 1 é que o resultado de busca de qualquer
  sequência passa pelo matcher, não por tag.

**Frontend**

- As mesmas mudanças da Proposta 1: remover a lista hardcoded
  (`static/assets/js/controllers/sequencia.js:2-37`), carregar o catálogo do
  backend e adicionar formulário/POST.
- No retorno do `POST /sequencias`, exibir de forma destacada
  “Essa sequência retorna N músicas hoje” ou, quando `N == 0`, um aviso
  explícito de que a sequência não retorna nenhuma música no momento. O
  cadastro não deve falhar por causa disso.
- A busca continua usando `similares?sequencia=...` (`sequencia.js:63-90`);
  o backend é quem normaliza e resolve a sequência.

**Docker**

- Mesmo volume `/app/instance` e mesma atualização do comando de execução da
  Proposta 1.

### Trade-offs

- **Prós:** um único caminho de código e uma única semântica; schema mais
  simples; regressão exata por construção; sequências novas são tratadas
  exatamente como as originais; dispensa ramo de compatibilidade.
- **Contras:** a semântica legada é muito restritiva para sequências
  arbitrárias: ela exige que a música inteira use apenas os acordes da
  sequência. Uma busca como “C, G, Am, F” retornaria apenas músicas compostas
  exclusivamente por esses quatro acordes, enquanto a mesma sequência como
  original retorna o conjunto de 296 músicas hoje. Na prática, muitas
  sequências novas podem retornar zero resultados, o que pode não corresponder
  à expectativa de “mostrar músicas em que a sequência aparece”. A pesquisa
  mede 866 ocorrências contíguas de `BmGDA` contra 199 com a tag (§2.3),
  evidenciando essa diferença. O contador retornado no cadastro mitiga o
  problema de descoberta: o usuário vê “0 músicas” imediatamente, antes de
  assumir que a sequência funciona. O risco residual é a frustração de um
  catálogo com muitas sequências vazias, não mais o desconhecimento do
  resultado.
- **Impacto:** `main.py`, `musica.py` (possivelmente helper), novo módulo
  SQLite, frontend, `Dockerfile`, README, `.gitignore`/`.dockerignore`.

### Validation

- **Teste de regressão obrigatório (permanece o da tarefa):** para cada um dos
  6 ids originais, percorrer as 67.585 músicas e verificar que o matcher novo
  retorna exatamente `str(id) in musica.seqs_famosas`. Comparar também o
  conjunto de `id_unico_musica` retornado pelo endpoint antigo e pelo novo em
  todas as páginas. Como a ordem dos gêneros varia entre processos
  (`main.py:38`, `main.py:92`), comparar conjuntos ordenados de
  `id_unico_musica`, não a ordem bruta. Registrar o resultado em
  `docs/features/sequencias-customizadas/04-test-report.md`.
- **Normalização e chave:** verificar que `["Bm","G","D","A"]`,
  `["bm","g","d","a"]` e variações com espaços geram a mesma `bmgda`, o mesmo
  registro e o mesmo resultado; verificar que o matcher lê `musica.cifra` e
  não `musica.acordes`; cobrir `cifra` vazia, acordes repetidos e sequência de
  um único acorde.
- **Contador no cadastro:** verificar que `POST /sequencias` retorna
  `total_musicas` igual ao tamanho da lista completa e não paginada retornada
  pela busca da mesma sequência; verificar o caso `0`, que deve responder
  `201` com `total_musicas: 0` e acionar o aviso no frontend.
- **Persistência:** os mesmos testes de restart/recriação com volume.
- **Performance:** medir a varredura de 67.585 músicas por busca e também no
  `POST` que calcula `total_musicas`; comparar com o custo atual, que só
  consulta `musica.seqs_famosas` (`main.py:209`).
- **Frontend:** catálogo vindo do backend, cadastro, contador exibido
  (inclusive zero), busca por original e por sequência nova.

### Open Questions

- A semântica estrita da tag é aceitável como definição de “a sequência
  aparece na música” para sequências novas? Se não, esta proposta não atende à
  intenção funcional e o matcher precisa ser outro.
- A normalização cobre apenas caixa e espaços (`strip().lower()`). Variações
  como `C#`/`Db`, acordes com barra, extensões e tokens sujos como
  `2x`/`heF#` (§2.5) continuam sendo tokens distintos. Isso é aceitável para o
  catálogo aberto ou exige um dicionário de equivalência?
- O mesmo problema de ordenação não determinística (`main.py:38`,
  `main.py:92`) continua valendo para as sequências novas.
- É necessário índice/cache para viabilizar o matcher em tempo real, ou a
  varredura completa é aceitável para o volume atual de 67.585 músicas? O
  `POST` acrescenta mais uma varredura completa para calcular
  `total_musicas`.

---

## Comparação rápida

| Critério | Proposta 1 (dual-path) | Proposta 2 (matcher único) |
|---|---|---|
| Regressão das 6 originais | Exata, via tag CSV | Exata, via matcher equivalente |
| Semântica para sequências novas | Matching contíguo mais natural | Semântica estrita da tag |
| Complexidade de código | Dois caminhos de busca | Um caminho de busca |
| Schema | `legacy_tag_id` | `is_builtin` |
| Principal risco | Inconsistência entre caminhos | Sequências novas vazias; mitigado pelo contador no cadastro |
| Persistência | SQLite + volume nomeado | SQLite + volume nomeado |
