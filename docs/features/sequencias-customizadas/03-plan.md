# Plano — Sequências de Acordes Customizadas

## Passos

1. [ ] Capturar o baseline antes de mudar qualquer código. Com o código atual, salvar todas as páginas de /similares?sequencia=chave das 6 sequências originais (também com um filtro de gênero, como generos=Rock). Guardar como conjuntos ordenados de id_unico_musica, porque a ordem dos gêneros varia entre processos.
2. [ ] Criar sequencias.py com a base de persistência. Implementar normalizar_acorde (strip().lower()), chave_normalizada (concatenação sem separador, bmgda), init_db (cria o diretório instance/, o arquivo e a tabela sequences com CREATE TABLE IF NOT EXISTS) e seed_sequencias_originais (6 entradas com is_builtin=1, usando INSERT OR IGNORE pela normalized_key).
3. [ ]  Implementar o matcher unificado em sequencias.py. aparece_na_musica normaliza sequência e Musica.cifra, exige que todos os acordes da música pertençam ao conjunto da sequência e que a sequência seja uma fatia contígua da cifra. Nunca usar Musica.acordes.

4. [ ] Implementar o acesso ao catálogo em sequencias.py. listar_sequencias, buscar_por_chave e criar_sequencia, com validação (tipo, tamanho do nome, quantidade de acordes, lista vazia) e SQL parametrizado.

5. [ ] Validar o matcher contra o baseline. Para cada um dos 6 ids originais, comparar o matcher com str(id) in musica.seqs_famosas nas 67.585 músicas. Só seguir adiante se os conjuntos forem idênticos. Medir também o tempo de uma varredura completa.

6. [ ] Integrar o backend em main.py. Inicializar banco e seed no startup, depois de carregar o CSV. Trocar o lookup do dicionário pelo SQLite no ramo sequencia de /similares (dividir por vírgula, normalizar, gerar a chave, buscar; se não existir, retornar []; se existir, aplicar apply_filtro, matcher e get_pagina). Manter o formato de resposta atual.

7. [ ] Adicionar os endpoints novos em main.py. GET /sequencias e POST /sequencias (201 com total_musicas, 400 para payload inválido, 409 para duplicata normalizada), sempre com json.dumps(...).

8. [ ] Atualizar o frontend. Em sequencia.js, remover sequencia1..4, carregar o catálogo via GET /sequencias e implementar o cadastro com POST, atualizando a lista local. Em sequencia.html, adicionar o formulário (nome + acordes em ordem) e a área que mostra total_musicas, com aviso destacado quando for zero. A busca existente não muda.

9. [ ]  Empacotar com Docker. Adicionar VOLUME /app/instance ao Dockerfile, instance/ ao .gitignore e ao .dockerignore, e documentar no README o comando com -v deciframe-data:/app/instance e o aviso de que sem volume o banco não sobrevive a docker rm.

10. [ ] Escrever os testes em tests/test_sequencias.py (unittest + Flask.test_client): unitários de normalização, chave, matcher, seed e criação; integração de POST → GET /sequencias → /similares; caso total_musicas == 0; sequência inexistente; caixa diferente.

11. [ ] Rodar a regressão final comparando o endpoint novo com o baseline do passo 1, incluindo paginação e filtro por gênero. Registrar o resultado em docs/features/sequencias-customizadas/04-test-report.md.

12. [ ] Validar de ponta a ponta com Docker e volume. Subir o container, cadastrar uma sequência, buscar, recriar o container e confirmar que o catálogo persistiu. Testar o frontend manualmente (catálogo, cadastro, contador inclusive zero, busca por original e por nova).

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Importar `sequencias.py`; inicializar banco e seed no startup; trocar o dicionário `sequencias` pelo SQLite; alterar o ramo `sequencia` de `/similares`; adicionar `GET /sequencias` e `POST /sequencias`. |
| `musica.py` | Sem alteração. `cifra` e `seqs_famosas` são usados como estão (`seqs_famosas` serve de oráculo da regressão). |
| `static/assets/js/controllers/sequencia.js` | Remover as 4 sequências hardcoded; carregar o catálogo do backend; adicionar cadastro e exibição de `total_musicas`. |
| `static/templates/sequencia.html` | Adicionar o formulário (nome + acordes) e a área de aviso/contador. |
| (novo) schema/migração do banco: `sequencias.py` | Normalização, chave, matcher, schema, seed e acesso ao SQLite. O schema é criado com `CREATE TABLE IF NOT EXISTS`, sem migrations. |

## Riscos e mitigação

* O matcher não reproduz as 6 originais. Percebo na regressão do passo 5 ou 11 (conjuntos diferentes). Se acontecer, comparo uma a uma as músicas divergentes e corrijo a normalização ou a regra antes de tocar nos endpoints. Não sigo para o frontend com a regressão falhando.
* Varredura de 67.585 músicas lenta na busca ou no POST. Percebo na medição do passo 5. Se o tempo for inaceitável, volto a este plano e adiciono um cache ou índice em memória antes de continuar.
* Sequências novas com zero resultados, por causa da regra restrita. É um risco aceito. O contador no cadastro e o aviso no frontend tornam isso visível. Se virar um problema de uso, a regra é revista na proposta, não no meio da implementação.
* Banco perdido ao recriar o container. Percebo no teste do passo 12. Mitigo com o volume nomeado e o aviso no README.
* Abuso do cadastro anônimo (payloads grandes, muitas chamadas). Mitigo com validação de tipo e tamanho, limite de acordes, SQL parametrizado e UNIQUE na chave. Rate limiting e moderação ficam fora do escopo.
* Ordem dos resultados instável entre processos, o que poderia dar falso erro na regressão. Mitigo comparando sempre conjuntos ordenados de id_unico_musica.
* Duplicatas por caixa ou espaços. A normalized_key com UNIQUE e a função única de chave bloqueiam; o 409 informa o usuário.

## Definição de pronto

* O cadastro de sequência funciona sem login, e entradas inválidas retornam 400 e duplicatas normalizadas retornam 409.
* O POST /sequencias retorna 201 com total_musicas, igual ao tamanho da lista completa e não paginada da busca da mesma sequência. O caso 0 também retorna 201 e o frontend exibe o aviso.
* A busca por uma sequência cadastrada funciona em /similares, com paginação e filtro por gênero.
* As 6 sequências originais retornam exatamente o mesmo conjunto de id_unico_musica do baseline, em todas as páginas e com filtro de gênero.
* O matcher bate com str(id) in musica.seqs_famosas nas 67.585 músicas para os 6 ids.
* GET /sequencias retorna o catálogo real e a lista hardcoded do frontend foi removida.
* O catálogo persiste após reiniciar o servidor e após recriar o container com volume nomeado, e o seed não duplica as 6 originais nem sobrescreve sequências de visitantes.
* Todos os endpoints continuam retornando json.dumps(...), sem jsonify.
* Nenhuma dependência nova de runtime foi adicionada, e a aplicação continua em um único container Docker.
* Os testes (unittest) passam e o resultado está registrado em 04-test-report.md.
