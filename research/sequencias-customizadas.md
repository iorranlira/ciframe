# Pesquisa — estado atual do codebase (sequências de acordes customizadas)

**Data da pesquisa:** 2026-11-06
**Commit analisado:** `fb97001` (`Update 00-enunciado.md`), árvore limpa
**Escopo:** documentar apenas o que existe hoje no repositório. Este documento não
propõe solução, não avalia alternativas e não faz recomendações.

Fontes lidas integralmente: `main.py`, `musica.py`, `README.md`, `AGENTS.md`,
`CONTRIB.md`, `docs/features/sequencias-customizadas/00-enunciado.md`,
`docs/features/sequencias-customizadas/01-research.md`,
`docs/features/sequencias-customizadas/02-proposal.md`,
`docs/features/sequencias-customizadas/03-plan.md`,
`docs/features/sequencias-customizadas/04-test-report.md`,
`docs/adr/0001-local-only-docker-deploy.md`,
`docs/adr/0002-persist-custom-sequences.md`,
`docs/adr/0003-lift-frontend-freeze.md`, `Dockerfile`, `requirements.txt`,
`static/index.html`, `static/assets/js/app.js`, `static/assets/js/routes.js`,
todos os controllers e diretivas em `static/assets/js/`, os templates em
`static/templates/`, `scripts/generate_data_set.py`,
`scripts/build-chords-transitions.R`, `scripts/normalize_chords.R`,
`scripts/simplify_chords.R`, além de inspeção direta de
`data/top/dataset_final.csv` e `data/mapeamento_sequencias_famosas.txt`.

Além da leitura estática, o backend foi importado e exercitado com o
`Flask.test_client()` (Flask 3.1.3) e o CSV foi analisado com scripts Python
independentes. Os números de seções marcadas como “medição” vêm dessas execuções.

---

## Sumário

O backend é um único arquivo Flask (`main.py`) que carrega
`data/top/dataset_final.csv` inteiro para a memória no momento do import; não há
banco de dados, camada de persistência, migrations ou suíte de testes. A busca
por sequência (`GET /similares?sequencia=...`) não calcula nada em tempo real:
ela remove as vírgulas da string recebida, procura essa string em um dicionário
literal de 6 chaves (`main.py:40-45`) e, se encontrar, retorna as músicas cuja
coluna pré-computada `SEQ_FAMOSA` do CSV contém o id da sequência. O frontend
AngularJS (`#/porsequencia`) tem sua própria lista hardcoded de apenas 4
sequências (`static/assets/js/controllers/sequencia.js:2-37`), monta a mesma URL
`/similares?sequencia=...` e não possui nenhuma tela, formulário ou chamada HTTP
de cadastro. O catálogo de sequências, portanto, existe hoje em dois lugares
desconectados — um dicionário Python com 6 entradas e um conjunto de 4 objetos
JavaScript — e o critério de “sequência aparece na música” está congelado no CSV
na forma de uma tag cujo formato é definido por
`scripts/generate_data_set.py:7-24`.

---

## 1. Backend Flask

### 1.1 Inicialização e modelo em memória

`main.py` é um módulo único de 280 linhas. O carregamento dos dados acontece no
nível do módulo, durante o import, e não dentro de uma função de inicialização:

- `main.py:25-35` define os índices das colunas do CSV e `TAM_PAGINA = 100`.
- `main.py:37-47` declara os globais mutáveis `genero_musicas`, `generos`,
  `acordes`, `sequencias` e `musicas_dict`.
- `main.py:40-45` contém o catálogo hardcoded das 6 sequências:

  | Chave no dicionário | id | Acordes |
  |---|---|---|
  | `BmGDA` | 0 | Bm, G, D, A |
  | `CGAmF` | 1 | C, G, Am, F |
  | `EmG` | 2 | Em, G |
  | `CA7DmG7` | 3 | C, A7, Dm, G7 |
  | `GmF` | 4 | Gm, F |
  | `CC7FFm` | 5 | C, C7, F, Fm |

- `main.py:49-98` lê `data/top/dataset_final.csv` linha a linha. A primeira
  linha é descartada com `f.readline()` em `main.py:50`; o restante é limpo com
  `line.replace('"', '').replace('NA', '')[:-1]` (`main.py:53`) e separado por
  vírgula (`main.py:55`).
- `main.py:69-74` cria um objeto `Musica` por linha e o indexa em
  `musicas_dict` por `id_unico_musica`.
- `main.py:87-89` converte `musicas_dict` em um `OrderedDict` `musicas` ordenado
  por popularidade decrescente.
- `main.py:92` converte o `set` de gêneros em lista (`generos = list(generos)`).
- `main.py:94-96` ordena cada bucket de `genero_musicas` por popularidade.

O objeto de domínio está em `musica.py:1-25`:

- `id_artista`, `nome_artista`, `id_musica`, `nome_musica`, `genero`,
  `popularidade`, `tom`, `cifra`, `seqs_famosas` (`musica.py:7-18`).
- `self.acordes = list(set(cifra))` (`musica.py:17`) — conjunto de acordes sem
  ordem e sem repetições.
- `self.id_unico_musica = '%s_%s' % (id_artista, id_musica)` (`musica.py:20`).
- `self.url` monta `http://www.cifraclub.com.br/<id_artista>/<id_musica>`
  (`musica.py:22`).

O processo inteiro (gunicorn, uma única instância sem `--workers`, conforme
`Dockerfile:12`) mantém esse estado em memória. Não há arquivo de banco, ORM,
driver de banco, migrations ou volume de dados no repositório.

### 1.2 Mapa de endpoints

Rotas registradas no `app` (verificadas via `app.url_map`):

| Rota | Função | Linhas | Comportamento observado |
|---|---|---|---|
| `/` | `index` | `main.py:101-103` | Serve `static/index.html` |
| `/<path:path>` | `static_proxy` | `main.py:109-112` | Serve qualquer arquivo estático |
| `/search` | `busca` | `main.py:114-142` | Busca por título/artista; exige `key` |
| `/musicas` | `get_musicas` | `main.py:154-156` | Retorna **todas** as músicas |
| `/generos` | `get_generos` | `main.py:158-160` | Retorna a lista de gêneros |
| `/acordes` | `get_acordes` | `main.py:162-164` | Retorna o conjunto de acordes |
| `/musica/<m_id>/` | `get_musica` | `main.py:166-168` | Busca por `id_unico_musica` |
| `/similares` | `get_similares` | `main.py:170-201` | Três modos: `acordes`, `id_unico_musica`, `sequencia` |

Todas as respostas JSON usam `json.dumps(...)` diretamente, nunca `jsonify`.
Nas execuções de teste, todos os endpoints JSON responderam
`Content-Type: text/html; charset=utf-8`, e o `after_request` em
`main.py:274-277` adicionou `Access-Control-Allow-Origin: *` a todas as
respostas, inclusive às estáticas.

### 1.3 O caminho de `/similares?sequencia=...`

O trecho relevante é `main.py:170-201`:

1. `main.py:173-176` lê `acordes`, `id_unico_musica`, `sequencia` e `pagina`
   (default `'1'`).
2. `main.py:179-182` monta `generos_key`; se `generos` não vier na query, usa a
   lista global `generos` (todos os gêneros).
3. `main.py:184-190` usa uma cadeia `if`/`elif`: `acordes` tem precedência,
   depois `id_unico_musica`, depois `sequencia`. Se nenhum vier, `acordes`
   permanece `[]`.
4. No ramo de sequência (`main.py:190-197`):
   - `acordes = sequencia_tag.replace(',','')` (`main.py:191`) remove **apenas**
     vírgulas; não remove espaços, não altera caixa, não normaliza acordes.
   - `if acordes in sequencias` (`main.py:194`) faz uma busca exata de string no
     dicionário de 6 chaves.
   - Em caso de acerto, `get_similares_por_sequencia(id_seq, generos_key)` é
     chamado e o resultado passa por `get_pagina(...)` (`main.py:195-196`).
   - A função retorna imediatamente `json.dumps(similares)` (`main.py:197`).
   - Em caso de string desconhecida, `similares` continua `[]` e a resposta é
     `[]` com HTTP 200.
5. Se o ramo de sequência não for acionado, `get_similares(...)` é chamado em
   `main.py:199-201`.

Não existe endpoint de escrita, formulário de cadastro, `POST`, `PUT` ou
`DELETE` no backend. As únicas rotas são as oito listadas acima.

### 1.4 `get_similares_por_sequencia`

`main.py:203-223` implementa o filtro por tag:

```python
collection = apply_filtro(musicas.values(), generos_key)
for musica in collection:
    if str(id_seq) in musica.seqs_famosas:
        similar = {
            'id_unico_musica': ..., 'id_artista': ..., 'id_musica': ...,
            'nome_artista': ..., 'nome_musica': ..., 'popularidade': ...,
            'acordes': ..., 'genero': ..., 'url': ...,
        }
        similares.append(similar)
```

Pontos factuais:

- O critério é `str(id_seq) in musica.seqs_famosas` (`main.py:209`); a lista
  `musica.seqs_famosas` vem diretamente do CSV (`main.py:63`).
- O resultado dessa função **não inclui** a chave `diferenca`, ao contrário do
  resultado de `get_similares` (`main.py:256-257`).
- O resultado inclui `acordes` (a lista deduplicada e sem ordem de
  `musica.acordes`), mas não inclui `tom` nem `cifra`.
- Não há cálculo de ordem, distância ou interseção nesse caminho.

### 1.5 Paginação, filtro de gênero e ordenação

- `TAM_PAGINA = 100` (`main.py:35`) e `get_pagina` (`main.py:226-228`) fazem
  slicing `colecao[(pagina-1)*100 : (pagina-1)*100+100]`.
- `apply_filtro` (`main.py:266-272`) percorre `generos_key` na ordem recebida e
  concatena os buckets `genero_musicas[genero]`; gêneros inexistentes são
  ignorados.
- Como `generos` nasce de um `set` (`main.py:38`) e vira lista em
  `main.py:92`, a ordem dos buckets varia entre processos. Em execuções com
  `PYTHONHASHSEED=1`, `2` e `3`, a lista `generos` começou,
  respectivamente, com `Marchas/Hinos`, `Emocore` e `MPB`; a primeira música
  retornada para `sequencia=BmGDA` também mudou (`Capital Inicial`,
  `Darvin`, `Oswaldo Montenegro`).
- Se o parâmetro `generos` repetir um gênero (`generos=Rock,Rock`), o mesmo
  bucket é concatenado duas vezes e as músicas aparecem duplicadas no JSON. Foi
  observado com `sequencia=EmG`: 4 registros, com cada `id_unico_musica`
  repetido duas vezes.
- `get_similares` (caminho de `acordes`/`id_unico_musica`) ordena por
  `(len(diferenca), -len(intersecao))` (`main.py:262-263`). O comentário em
  `main.py:262` cita “maior popularidade”, mas a chave de ordenação não inclui
  popularidade.
- O frontend reordena os cards no cliente com `orderBy:'-popularidade'`
  (`static/templates/sequencia.html:42`); a ordem do JSON e a ordem visual não
  são necessariamente a mesma.

### 1.6 Comportamentos de borda observados

Execuções com `Flask.test_client()`:

| Requisição | Resultado |
|---|---|
| `GET /generos` | 200, array com 52 gêneros |
| `GET /similares?sequencia=BmGDA` | 200, 100 itens (primeira página) |
| `GET /similares?sequencia=BmGDA&pagina=2` | 200, 99 itens (total 199) |
| `GET /similares?sequencia=C,G,Am,F` | 200, 100 itens (idêntico a `CGAmF`) |
| `GET /similares?sequencia=cgamf` | 200, `[]` (busca case-sensitive) |
| `GET /similares?sequencia=EmG` | 200, 4 itens |
| `GET /similares?sequencia=CA7DmG7` | 200, 5 itens |
| `GET /similares?sequencia=GmF` | 200, 7 itens |
| `GET /similares?sequencia=CC7FFm` | 200, 3 itens |
| `GET /similares?sequencia=ZZZ` | 200, `[]` |
| `GET /similares?sequencia=` | 200, `[]` |
| `GET /similares?sequencia=CGAmF&generos=Rock` | 200, 8 itens |
| `GET /musicas` | 200, 67.585 objetos |
| `GET /musica/14-bis_adoraveis-criaturas/` | 200, um objeto |
| `GET /search?key=legiao` | 200, 100 itens |
| `GET /search` (sem `key`) | 500 (`AttributeError` em `main.py:118`) |

Observações adicionais:

- O docstring de `/musicas` (`main.py:149-153`) descreve um serviço paginado,
  mas a implementação (`main.py:154-156`) devolve a coleção inteira.
- `get_musica` usa `musicas[m_id]` sem tratamento de ausência
  (`main.py:166-168`); um `m_id` inexistente gera `KeyError`.
- A rota `/musica/<m_id>/` exige a barra final.
- `GET /` devolve `index.html` com 200 e `Content-Type: text/html`.

---

## 2. O catálogo de sequências e o matching que existe hoje

### 2.1 Onde as 6 sequências aparecem

- Backend: `main.py:40-45` (dicionário `sequencias`), usado apenas em
  `main.py:194-196`.
- Dados: coluna 7 do CSV (`SEQ_FAMOSA`, `main.py:33`), lida em `main.py:63` e
  exposta como `Musica.seqs_famosas` (`musica.py:18`).
- Artefato de documentação: `data/mapeamento_sequencias_famosas.txt:1-6`
  (id, nome e acordes). Esse arquivo não é lido pelo runtime; um `grep` no
  repositório não encontrou referência a ele fora do próprio arquivo.
- Frontend: quatro objetos hardcoded em
  `static/assets/js/controllers/sequencia.js:2-37` (detalhado na seção 4).

### 2.2 Origem da tag `SEQ_FAMOSA`

A função que define o formato da tag está em `scripts/generate_data_set.py:7-24`:

```python
seqs = ['bm;g;d;a', 'c;g;am;f', 'em;g', 'c;a7;dm;g7', 'gm;f', 'c;c7;f;fm']
if s in acorde:                  # s é substring da cifra ';'-joined, em minúsculas
    for l in acorde.split(';'):  # cada acorde da música
        if l not in tokens:      # precisa pertencer ao conjunto da sequência
            achou = False
```

O efeito combinado das duas verificações é: a música inteira usa somente acordes
do conjunto da sequência **e** contém a sequência exata como trecho contíguo da
lista de acordes. O script grava o id retornado em `famosas`
(`scripts/generate_data_set.py:84-89`); no CSV atual há no máximo um id por
música.

Reprodução da função contra o CSV carregado: para as 67.585 linhas que
`main.py` carrega, a função `get_famosas` gera exatamente as mesmas tags que
estão no arquivo em 67.585/67.585 linhas (67.071 sem tag e 514 com tag). Não há
linha com mais de uma tag.

### 2.3 Medições sobre os dados atuais

Contagens sobre as 67.585 músicas carregadas por `main.py`:

| id | Sequência | Músicas com a tag (retorno atual) | Músicas em que a sequência é fatia contígua ordenada de `cifra` | Fatia contígua após colapsar repetições consecutivas | Subsequência ordenada (com lacunas) | Todos os acordes da sequência presentes, sem ordem |
|---|---|---|---|---|---|---|
| 0 | Bm, G, D, A | 199 | 866 | 882 | 4.763 | 5.768 |
| 1 | C, G, Am, F | 296 | 1.216 | 1.235 | 5.887 | 6.894 |
| 2 | Em, G | 4 | 3.110 | 3.110 | 13.643 | 14.160 |
| 3 | C, A7, Dm, G7 | 5 | 96 | 96 | 427 | 582 |
| 4 | Gm, F | 7 | 1.039 | 1.039 | 3.641 | 3.847 |
| 5 | C, C7, F, Fm | 3 | 132 | 132 | 280 | 365 |
| **Total** | | **514** | | | | |

Fatos que essa medição estabelece:

- As 514 músicas hoje retornadas satisfazem **todas** as definições da tabela
  (a tag implica o conjunto de acordes contido na sequência e a ocorrência
  contígua).
- As outras definições da tabela produzem contagens maiores do que as 514
  atualmente retornadas. Exemplo: para `BmGDA`, há 866 músicas com a sequência
  contígua, e 199 com a tag.
- O conjunto de acordes das músicas taggeadas é sempre subconjunto do conjunto
  da sequência; o número máximo de acordes distintos numa música taggeada é
  igual ao tamanho da sequência (4, 4, 2, 4, 2, 4 para os ids 0–5).
- As músicas taggeadas contêm repetições: o comprimento mediano da `cifra` é
  48, 47, 44, 36, 22 e 48 acordes para os ids 0–5, respectivamente, com apenas
  2–4 acordes distintos.
- A posição da primeira ocorrência da sequência na `cifra` varia de 0 a 127
  (id 0) e de 0 a 70 (id 1); nos demais ids, a posição máxima observada é 12.

Exemplos reais de músicas taggeadas:

```
id 0: 30 Seconds To Mars - City Of Angels
      D;A;Bm;G;D;A;Bm;G;...  (57 acordes, 4 distintos)
id 1: 5 Seconds Of Summer - Broken Pieces
      C;G;Am;F;C;G;Am;F;...  (86 acordes, 4 distintos)
id 2: Ultraje a Rigor - Inútil
      Em;G;Em;G;...          (48 acordes, 2 distintos)
id 3: Martinho da Vila - Na Aba
      C;A7;Dm;G7;C;G7;...    (52 acordes, 4 distintos)
id 4: Raça Negra - Cheia de Manias
      Gm;F;Gm;F;...          (34 acordes, 2 distintos)
id 5: Claudia Leitte - Bem Vindo Amor
      C;C7;F;Fm;C;C7;F;Fm;... (48 acordes, 4 distintos)
```

### 2.4 Entrada de sequência: o que é aceito hoje

- O backend remove vírgulas e faz lookup exato (`main.py:191-194`). Não há
  `strip`, `lower`, remoção de acentos, reordenação ou deduplicação.
- Consequências observadas: `C,G,Am,F` e `CGAmF` retornam o mesmo resultado;
  `cgamf` retorna `[]`; `ZZZ` retorna `[]`; `Bm, G, D, A` (com espaços) não
  corresponde a nenhuma chave.
- O frontend monta a string unindo os acordes com vírgula
  (`static/assets/js/controllers/sequencia.js:55-61`) e não usa
  `encodeURIComponent` (`sequencia.js:72-77`). Como `#` inicia o fragmento da
  URL, um acorde com sustenido na query string seria truncado pelo navegador
  nesse caminho. As 4 sequências hardcoded atuais não contêm `#`.
- O parâmetro `generos` é repassado ao filtro e concatenado com `&`
  (`sequencia.js:74-76`).

### 2.5 Vocabulário de acordes no CSV

Medições sobre a coluna `CIFRA` das 67.585 músicas carregadas:

- 3.505.331 ocorrências de acordes, 6.653 tokens distintos.
- 3.940 tokens contêm letras minúsculas (ex.: `Am`, `Bb7M`, `Dm7/9`,
  `F#m7(b5)`, `Eadd9`).
- 3.808 tokens contêm `/` (ex.: `D/F#`, `G/B`, `Bb5-/D`, `A4(7/9)`).
- 2.287 tokens contêm parênteses (ex.: `Fm7(13)`, `C(add9)`, `Am7(9)`).
- Há tokens que não são acordes (ex.: `2x`, `heF#`, `GmI'll`, `E7_`, `D-`).
- Acordes mais frequentes: `G` (346.972), `D` (284.572), `C` (267.143),
  `A` (244.312), `E` (201.723), `F` (164.123), `Am` (128.104),
  `Em` (118.810), `B` (87.329), `Bm` (87.271).
- O repositório também contém scripts offline de normalização por grau
  (`scripts/normalize_chords.R:3-30`, `scripts/simplify_chords.R:3-28`) que usam
  `TOM` e `data/transposition_matrix2.csv` para gerar `NCIFRA` (graus como
  `I;V;VI;IV`). Esses scripts não são importados nem executados pelo runtime.
  O artefato `data/dataset_seq_notas.csv` (66.526 linhas) é entrada de
  `scripts/build-chords-transitions.R:73` e também não é lido por `main.py`.

---

## 3. Dataset e ingestão

### 3.1 Formato do arquivo

`data/top/dataset_final.csv` tem 16 MB e 67.586 linhas, **todas de dados** — não
há linha de cabeçalho. As 9 colunas são posicionais (`main.py:26-34`):

| Índice | Constante | Conteúdo |
|---|---|---|
| 0 | `ARTISTA_ID` | slug do artista |
| 1 | `MUSICA_ID` | slug da música |
| 2 | `ARTISTA` | nome do artista |
| 3 | `MUSICA` | nome da música |
| 4 | `GENERO` | gênero |
| 5 | `POPULARIDADE` | inteiro com separador de milhar `.` |
| 6 | `TOM` | tom |
| 7 | `SEQ_FAMOSA` | ids de sequência separados por `;` ou `NA` |
| 8 | `CIFRA` | acordes separados por `;` ou `NA` |

`main.py:50` descarta a primeira linha (`f.readline()`), de modo que o runtime
carrega **67.585** músicas, e não 67.586. A linha descartada é
`14-bis,a-qualquer-tempo,14 Bis,A Qualquer Tempo,MPB,...`.

Características observadas no arquivo:

- 8.141 músicas têm `CIFRA` vazia (após o parsing).
- 52 gêneros distintos em memória; 67.071 músicas sem tag e 514 com tag.
- Nenhum `id_unico_musica` duplicado entre as 67.585 linhas carregadas.

### 3.2 Comportamentos do parser

- `main.py:53` remove **todas** as aspas e **todas** as ocorrências da substring
  `NA` da linha inteira, antes de separar por vírgula. Isso altera títulos que
  contêm `NA` no meio. Exemplos reais após o parsing: `DNA` → `D`,
  `CABANA` → `CABA`, `JULIANA` → `JULIA`, `ROTINA DE POBRE` → `ROTI DE POBRE`,
  `She's Got Style (Versão ORIGINAL)` → `She's Got Style (Versão ORIGIL)`.
  Ocorre em 7 títulos de música; nenhum nome de artista e nenhum gênero
  contêm `NA` no arquivo.
- `line[:-1]` (`main.py:53`) remove o último caractere de cada linha (o `\n`).
- `line.split(',')` (`main.py:55`) não respeita aspas. No arquivo atual,
  todas as 67.586 linhas têm exatamente 9 campos CSV e nenhum campo contém
  vírgula; há 18 linhas com aspas (ex.: `"3"`, `"Vamo" Comer`,
  `Os "punho"`), que o `replace('"', '')` remove. O parser posicional assume
  9 colunas; se um campo passasse a conter vírgula, a contagem de colunas
  mudaria.
- `POPULARIDADE` é convertida com `int(...replace('.', ''))`
  (`main.py:56`); valores vazios após a remoção de `NA` gerariam erro, mas a
  medição não encontrou linha com esse problema nas 67.585 carregadas.
- `limpa_cifra` (`main.py:11-23`) recebe a `CIFRA` separada por `;`; se um
  token contém `|`, usa o primeiro pedaço antes do pipe; caso contrário, quebra
  por espaços. No arquivo atual os acordes já vêm separados por `;`.
- `musica[SEQ_FAMOSA] = musica[SEQ_FAMOSA].split(";")` (`main.py:63`): para
  músicas sem tag, o resultado é `['']`, e não uma lista vazia.
- O gênero `R&B;` aparece literalmente na coluna 4 do CSV (ex.:
  `data/top/dataset_final.csv:2167`), com ponto e vírgula no valor.
  `/generos` devolve 52 entradas, incluindo `R&B;`; a constante hardcoded do
  frontend tem 51 entradas e não inclui `R&B;`.
- O parser não usa `csv.reader`/`pandas`; a leitura é feita com `open` e
  `split`.

---

## 4. Frontend AngularJS

### 4.1 Bootstrap e rotas

- `static/index.html:125-147` carrega jQuery 1.11.3, Bootstrap 3.3.6,
  AngularJS 1.4.9 (`angular.js`, `angular-route`, `angular-animate`),
  `angular-ui-bootstrap` 2.1.4, `ngprogress.js` e os arquivos locais de
  `assets/js`. Tudo vem de CDN ou de arquivos estáticos; não há build step.
- `static/index.html:22` usa `ng-controller="MainController"` no `<body>`.
- `static/index.html:123` tem `<div class="page" ng-view></div>`.
- `static/assets/js/routes.js:17-21` registra `#/porsequencia` com
  `templateUrl: "templates/sequencia.html"`, `controller: "SequenciaController"`
  e `controllerAs: "Sequencia"`.
- `static/assets/js/app.js:1-5` define o módulo `deciframeApp` e uma constante
  `RESTAPI` com `url: 'http://localhost:5003'`. Um `grep` no frontend não
  encontrou nenhum uso de `RESTAPI`; os controllers usam `apiUrl = ""` e URLs
  relativas.
- `static/assets/js/app.js:6-58` define a constante `GENEROS` com 51 nomes.
  Nenhum controller chama `/generos`; todos usam a constante.

### 4.2 `SequenciaController`

`static/assets/js/controllers/sequencia.js:1-105`:

- `sequencia1`..`sequencia4` (`linhas 2-31`) são objetos com `index: 1` e um
  array `acordes` de `{acorde, cor}`. São exatamente 4:

  | Variável | Acordes | Corresponde ao id do backend |
  |---|---|---|
  | `sequencia1` | Bm, G, D, A | 0 |
  | `sequencia2` | C, G, Am, F | 1 |
  | `sequencia3` | Gm, F | 4 |
  | `sequencia4` | C, C7, F, Fm | 5 |

  As sequências de id 2 (`EmG`) e 3 (`CA7DmG7`) existem no backend mas não
  aparecem nessa lista.
- `vm.sequenciasFamosas` é preenchido com os 4 objetos (`linhas 32-37`).
- `vm.minhaSequencia = {}` (`linha 38`), `vm.musics = []` (`linha 42`),
  `vm.generos = GENEROS` (`linha 43`), `vm.meuGenero = ""` (`linha 44`).
- `vm.temAcorde` (`linhas 47-53`) só verifica pertencimento à lista de acordes
  da sequência selecionada.
- `createChordsString` (`linhas 55-61`) concatena `acorde + ','` e remove a
  última vírgula.
- `vm.pesquisarPorSequencia` (`linhas 63-90`):
  - se receber `sequencia`, substitui `vm.minhaSequencia` (`linhas 64-66`);
  - inicia a barra de progresso e limpa `vm.musics` (`linhas 67-70`);
  - monta `"similares?sequencia=" + createChordsString(...)` (`linha 73`);
  - se `vm.meuGenero` estiver preenchido, acrescenta `&generos=` (`linhas
    74-76`);
  - faz `$http.get(apiUrl.concat(searchString))` (`linha 77`);
  - no sucesso, preenche `vm.musics` com `data` (`linhas 78-84`);
  - no erro, mostra “Ops! Algo errado.” (`linhas 85-89`).
- `vm.limparPesquisa` (`linhas 92-95`) zera `minhaSequencia` e `musics`.
- `vm.goToLirics` (`linhas 97-99`) abre `music.url` em nova janela.
- `vm.goToResults` (`linhas 101-104`) faz scroll até `#results`.

Não há função de cadastro, campo de formulário, chamada `$http.post`, nem
consumo de um catálogo vindo do backend nesse controller.

### 4.3 `sequencia.html`

`static/templates/sequencia.html:1-63`:

- Painel esquerdo (`linhas 3-16`): título “Aponte uma sequencia de acordes”,
  `ng-repeat='sequencia in Sequencia.sequenciasFamosas'` com
  `ng-click="Sequencia.pesquisarPorSequencia(sequencia)"` (`linha 6`), e um
  `df-hex` por acorde (`linha 7`).
- Botão de resultados (`linhas 10-14`) aparece quando
  `Sequencia.showSearchResultsCount` é verdadeiro.
- Painel direito (`linhas 17-62`): cabeçalho com `Sequencia.esfigeSpeech`
  (`linha 20`); select de gênero com
  `ng-options="genero for genero in Sequencia.generos | orderBy:'genero'"`
  (`linhas 24-30`), cujo `ng-change` chama `Sequencia.pesquisarPorSequencia()`
  sem argumento (`linha 28`); os acordes da sequência selecionada são exibidos
  como `df-hex` e o clique limpa a pesquisa (`linha 34`).
- Cards de música (`linhas 40-59`) usam
  `ng-repeat="music in Sequencia.musics | orderBy:'-popularidade'"` e
  `ng-hide="music.diferenca.length"` (`linhas 42-43`). Como o endpoint de
  sequência não devolve `diferenca` (`main.py:210-220`), essa expressão é
  avaliada sobre uma propriedade ausente.
- Não existe `<form>`, `<input>` ou botão de cadastro no template.

### 4.4 Relação com as outras páginas

- `#/poracordes` (`routes.js:7-11`) usa `AcordesController`, que monta
  `similares?acordes=...` (`static/assets/js/controllers/acordes.js:84-96`).
- `#/pormusica` (`routes.js:12-16`) usa `MusicaController`, que monta
  `similares?id_unico_musica=...` (`static/assets/js/controllers/musica.js:43-70`).
- `#/porsequencia` usa o terceiro ramo de `/similares` (`sequencia=`).
- As três páginas compartilham o mesmo formato de card e o mesmo padrão de
  `ng-hide="music.diferenca.length"`; somente `/similares?acordes=` e
  `/similares?id_unico_musica=` devolvem `diferenca`
  (`main.py:246-258`).
- As três páginas usam `vm.generos = GENEROS` (constante do frontend), e não o
  endpoint `/generos`.

---

## 5. Persistência, deploy e dependências

### 5.1 Estado atual da persistência

- Não há banco de dados no repositório: nenhum arquivo `.db`/`.sqlite`,
  nenhuma dependência de banco em `requirements.txt` (`requirements.txt:4-5`
  lista apenas `Flask==3.1.3` e `gunicorn==23.0.0`), nenhum uso de
  `sqlite3`, SQLAlchemy ou similar em código Python.
- O único estado mutável é em memória: `musicas_dict`, `musicas`,
  `genero_musicas`, `generos`, `acordes` e `sequencias` (`main.py:37-98`).
- O catálogo de sequências é o dicionário literal `sequencias`
  (`main.py:40-45`), recriado a cada import.
- `AGENTS.md:9-11` registra explicitamente: “there is no database” e o CSV é
  carregado “into memory once at startup”.
- `AGENTS.md:45` registra que editar `data/top/*.csv` exige reinício, porque a
  leitura acontece uma vez no import.

### 5.2 Docker e processo

`Dockerfile:1-12`:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
```

- Container único, uma única imagem, sem `VOLUME`, sem `docker-compose`, sem
  serviço externo.
- O comando do gunicorn não define `--workers`; o default do gunicorn é 1
  worker.
- `COPY . .` copia o CSV e todo o restante do contexto para dentro da imagem.
- `.dockerignore:1-4` exclui `.git`, `.venv`, `__pycache__` e `*.pyc`;
  `.gitignore:1-4` exclui `static/assets/vendor`, `.venv`, `*.pyc` e
  `__pycache__/`.
- `AGENTS.md:20-33` documenta `docker build -t ciframe .` /
  `docker run -p 8080:8080 ciframe` e, alternativamente, virtualenv com
  `python main.py` na porta 5000.
- `docs/adr/0001-local-only-docker-deploy.md:1-16` documenta a decisão de
  substituir App Engine/Heroku por esse Dockerfile local-only e registra que a
  arquitetura do backend (single `main.py`, busca em memória sobre o CSV,
  Python 3.9) foi mantida.
- `main.py:279-280` executa `app.run(debug=True)` quando rodado diretamente;
  no Docker, quem serve é o gunicorn.

### 5.3 Testes

- Não existe diretório `tests/`, arquivo `test_*.py`, `pytest.ini`,
  `tox.ini`, `conftest.py` ou dependência de teste em `requirements.txt`.
- A verificação documentada em `AGENTS.md:35-41` é manual:
  `curl http://localhost:8080/generos`.
- Os templates de teste da feature estão vazios em
  `docs/features/sequencias-customizadas/04-test-report.md:1-25`.

---

## 6. Documentação da feature no repositório

- `docs/features/sequencias-customizadas/00-enunciado.md:26-31` descreve o
  estado atual: 6 sequências hardcoded no backend, 4 hardcoded no frontend,
  tag `SEQ_FAMOSA` pré-computada e ausência de cálculo em tempo real.
- `00-enunciado.md:45-55` lista os requisitos funcionais da feature.
- `00-enunciado.md:57-68` fixa: uso de `opencode`/`BigPickle`; músicas e
  gêneros continuam vindo do CSV em memória; aplicação continua no
  `Dockerfile` único local-only do ADR 0001; as 6 sequências atuais precisam
  manter os mesmos resultados; endpoints continuam usando `json.dumps`, não
  `jsonify`.
- `00-enunciado.md:70-77` deixa como decisão do implementador o algoritmo de
  matching, a tecnologia de banco, o formato da API, o esquema e a validação.
- `01-research.md:1-44`, `02-proposal.md:1-49`, `03-plan.md:1-33` e
  `04-test-report.md:1-25` contêm apenas os templates/instruções; nenhuma das
  fases está preenchida.
- `docs/adr/0002-persist-custom-sequences.md:1-8` contém apenas o título
  provisório e o bloco de instruções; o corpo está como `[seu texto aqui]`.
- `docs/adr/0003-lift-frontend-freeze.md:1-21` documenta que a restrição de não
  tocar no frontend AngularJS foi removida, mantendo a stack AngularJS 1.4.9 +
  jQuery sem build step.
- Antes desta pesquisa, não existia diretório `research/` no topo do
  repositório.

---

## 7. Conexões e fluxos de dados

### 7.1 Fluxo de inicialização

```
import main
  └─ main.py:49  open('data/top/dataset_final.csv')
  └─ main.py:50  descarta a 1ª linha
  └─ main.py:52-98  para cada linha:
       ├─ limpa aspas/NA e separa por vírgula
       ├─ limpa CIFRA (limpa_cifra)
       ├─ separa SEQ_FAMOSA por ';'
       ├─ cria Musica (musica.py:1-25)
       │    ├─ acordes = list(set(cifra))   (sem ordem)
       │    └─ seqs_famosas = lista de ids
       ├─ musicas_dict[id_unico_musica] = Musica
       ├─ acordes.update(musica.acordes)
       ├─ genero_musicas[genero].append(Musica)
       └─ generos.add(genero)
  └─ main.py:87-89  musicas = OrderedDict ordenado por popularidade
  └─ main.py:92     generos = list(set)
  └─ main.py:94-96  cada bucket de gênero ordenado por popularidade
```

Todo esse estado vive no processo. Um novo import/restart refaz a leitura do
CSV; nada é gravado em disco.

### 7.2 Fluxo de busca por sequência (estado atual)

```
Browser #/porsequencia
  └─ routes.js:17-21  carrega sequencia.html + SequenciaController
  └─ sequencia.js:32-37  popula vm.sequenciasFamosas com 4 objetos JS
  └─ clique em um card (sequencia.html:6)
       └─ sequencia.js:63-90  pesquisarPorSequencia
            ├─ createChordsString: "Bm,G,D,A" (sequencia.js:55-61)
            ├─ monta "similares?sequencia=Bm,G,D,A[&generos=...]"
            └─ GET (URL relativa, mesma origem)
                 └─ Flask main.py:170-201
                      ├─ generos_key = query ou todos os gêneros
                      ├─ sequencia_tag.replace(',','')  -> "BmGDA"
                      ├─ lookup exato em sequencias (main.py:40-45)
                      ├─ get_similares_por_sequencia(id_seq, generos_key)
                      │    ├─ apply_filtro(musicas.values(), generos_key)
                      │    │    └─ concatena buckets de genero_musicas
                      │    └─ filtra str(id_seq) in musica.seqs_famosas
                      ├─ get_pagina(..., pagina)  -> 100 itens
                      └─ json.dumps(...)          -> text/html
  └─ sequencia.js:78-84  vm.musics = data
  └─ sequencia.html:40-59  cards (ordem local por -popularidade)
```

O dado que decide o match (`musica.seqs_famosas`) não é derivado da `cifra` em
tempo de requisição; ele é lido da coluna 7 do CSV e usado como pertinência de
string (`main.py:209`).

### 7.3 Fluxo de cadastro de sequência

Não existe. O repositório não tem:

- rota de escrita no Flask (`app.url_map` só tem rotas `GET`);
- chamada `$http.post`/`put`/`delete` no frontend;
- formulário de cadastro em `static/templates/sequencia.html`;
- tabela, arquivo ou schema de banco para sequências.

### 7.4 Fluxo das outras buscas (compartilham `/similares`)

```
#/poracordes  -> acordes.js:84-115  -> /similares?acordes=C,G,Am
                                   -> main.py:185-186, 199-201
                                   -> get_similares (interseção/diferença de sets)

#/pormusica   -> musica.js:43-70   -> /similares?id_unico_musica=<id>
                                   -> main.py:187-189, 199-201
                                   -> get_similares (acordes da música escolhida)
```

Esses dois caminhos devolvem `diferenca` e `intersecao`
(`main.py:246-258`); o caminho de sequência não.

---

## 8. Evidências de execução e baseline de regressão

As medições foram feitas com um virtualenv temporário contendo
`Flask==3.1.3`, importando `main.py` com
`PYTHONPATH=/home/iorran/Documents/P10/john_arthur/ciframe`, e com scripts
Python independentes que releem o CSV com a mesma lógica de `main.py:49-98`.
Nenhum arquivo do repositório foi alterado por esses scripts.

Baseline atual das 6 sequências (retorno de `/similares?sequencia=<chave>`):

| Chave | Total de músicas (todas as páginas) | Página 1 | Página 2 |
|---|---|---|---|
| `BmGDA` | 199 | 100 | 99 |
| `CGAmF` | 296 | 100 | 100 (página 3: 96) |
| `EmG` | 4 | 4 | 0 |
| `CA7DmG7` | 5 | 5 | 0 |
| `GmF` | 7 | 7 | 0 |
| `CC7FFm` | 3 | 3 | 0 |

Contagens de tag por id (coluna `SEQ_FAMOSA`): 0 → 199, 1 → 296, 2 → 4,
3 → 5, 4 → 7, 5 → 3; total 514. Não há música com duas tags.

Contagens de músicas carregadas: 67.585. Músicas com `CIFRA` vazia: 8.141.
Gêneros em memória: 52. Tokens de acorde distintos: 6.653.

---

## 9. Restrições declaradas pelo enunciado (fatos do documento, não decisões desta pesquisa)

`docs/features/sequencias-customizadas/00-enunciado.md:57-68` fixa:

- uso do `opencode` e do modelo `BigPickle`;
- catálogo de músicas e gêneros continua vindo do CSV, em memória; somente o
  catálogo de sequências precisa de persistência;
- aplicação continua rodando via o `Dockerfile` único e local-only do ADR 0001
  (container único, sem serviços externos adicionais);
- as 6 sequências atuais precisam continuar produzindo os mesmos resultados de
  busca;
- endpoints continuam retornando `json.dumps(...)` como string, não
  `jsonify`.

`docs/features/sequencias-customizadas/00-enunciado.md:70-77` deixa como
decisão do implementador: o algoritmo de matching, a tecnologia de banco, o
formato exato da API nova, o esquema do banco e os detalhes de validação
(ex.: tratamento de sequências duplicadas).
