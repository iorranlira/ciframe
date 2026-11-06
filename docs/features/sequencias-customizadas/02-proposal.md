# Proposta — Sequências de Acordes Customizadas

> Com base na pesquisa, declare a abordagem escolhida e por quê. Esta fase é sobre
> decidir, não sobre implementar. Apague este bloco de instruções antes de
> entregar.

## Abordagem escolhida

### Algoritmo de matching

Escolhi a Proposta 2: um único matcher para todas as sequências, que replica a regra da tag SEQ_FAMOSA. Uma música é compatível com uma sequência quando, depois de normalizar ambas com strip().lower(), duas condições precisam ser verdadeiras ao mesmo tempo: 1) Todos os acordes da música pertencem ao conjunto de acordes da sequência. 2) A sequência aparece como fatia contígua de Musica.cifra, na mesma ordem e com as mesmas repetições.

### Banco de dados

Escolhido o SQLite em arquivo, via sqlite3 da biblioteca padrão por fins de simplicidade. Ele não exige serviço externo nem dependência nova, cabe no container Docker único e local-only e atende à persistência necessária. O arquivo vai ficar em instance/sequences.db, com volume nomeado em /app/instance. Músicas e gêneros continuam vindo do CSV em memória.

### Esquema de dados (alto nível)

Uma única tabela, sequences, com os campos:

id: identificador.
nome: nome dado à sequência.
acordes_json: lista ordenada de acordes, na grafia original.
normalized_key: acordes normalizados concatenados sem separador (bmgda), com restrição UNIQUE para impedir duplicatas por caixa ou espaços.
created_at: data de criação.
is_builtin: marca as 6 originais, que são semeadas no startup sem duplicar e sem sobrescrever sequências de visitantes.

### API

* GET /sequencias: retorna o catálogo (id, nome, acordes, normalized_key, is_builtin, created_at).
* POST /sequencias: recebe {"nome": "...", "acordes": ["Bm","G","D","A"]}. Valida tipo, tamanho e quantidade de acordes e rejeita listas vazias. Responde 201 com a sequência criada e total_musicas, 400 para payload inválido e 409 para duplicata normalizada. Sequência com zero resultados é permitida.
* GET /similares?sequencia=...: continua como caminho de busca e aceita qualquer sequência do catálogo. Sequência inexistente continua retornando []. O formato de resposta não muda.


### Frontend

Em #/porsequencia:

* Remover a lista hardcoded sequencia1..4 (sequencia.js:2-37) e carregar o catálogo via GET /sequencias. Isso também elimina a divergência entre as 4 sequências do frontend e as 6 do backend.
* Adicionar em sequencia.html um formulário com nome e acordes em ordem.
Após o POST, exibir o total_musicas retornado, com aviso destacado quando for zero, e atualizar a lista local.
* A busca existente (sequencia.js:63-90) não muda e funciona do mesmo jeito para sequências antigas e novas.

## Alternativas consideradas e descartadas

O caminho da Proposta 1. Manter a tag do CSV para as 6 originais e usar matching contíguo simples para as novas. Descartei porque a mesma lista de acordes daria resultados diferentes conforme a origem (199 músicas como original contra 866 como nova, para BmGDA).

## Escopo explícito

**Dentro do escopo:**

* Cadastro anônimo de sequências com nome e acordes ordenados.
* Persistência do catálogo em SQLite, com volume nomeado.
* Matcher único sobre Musica.cifra, com normalização strip().lower().
* GET /sequencias, POST /sequencias e adaptação de /similares.
* Frontend lendo o catálogo do backend, com formulário e contador.
* Testes de regressão das 6 originais (conjuntos ordenados de id_unico_musica), testes unitários e de API, e medição de desempenho.

**Fora do escopo (e por quê):**

* Autenticação e moderação: o catálogo é aberto e anônimo por requisito.
* Edição e remoção de sequências: não foi pedido.
* Migração de músicas e gêneros para o banco: continuam no CSV em memória.
* Normalização rica de acordes (C#/Db, barras, extensões): fica como melhoria futura.
* Cache ou índice em memória: só se a medição mostrar que a varredura completa é inaceitável.
* Mudança da stack do frontend: a página continua com a stack atual.