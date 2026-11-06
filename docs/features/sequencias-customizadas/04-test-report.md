# Relatório de testes — Sequências de Acordes Customizadas

## Cobertura

A suíte usa `unittest` e `Flask.test_client`, sem dependências novas. Foram
implementados 24 testes:

- normalização de caixa/espaços e geração da chave sem separador;
- matcher estrito: trecho contíguo, ordem, conjunto de acordes, cifra vazia,
  repetições e sequência de um acorde;
- repositório SQLite: schema, seed idempotente das 6 originais, busca por
  chave, criação, duplicata normalizada, validação e persistência após reabrir
  o banco;
- API: `GET /sequencias`, `POST /sequencias`, catálogo após cadastro, caso de
  zero resultados, duplicata (409), payload inválido (400), busca de sequência
  inexistente e normalização de caixa na busca;
- consistência entre o `total_musicas` retornado no cadastro e o tamanho da
  lista completa retornada pela busca.

## Teste de regressão obrigatório

O teste compara, para cada um dos 6 ids originais, o resultado do matcher novo
com a tag `SEQ_FAMOSA` de todas as 67.585 músicas. Também compara o endpoint
`/similares?sequencia=...` com o conjunto de músicas esperado pela tag,
percorrendo todas as páginas e usando conjuntos de `id_unico_musica` para não
depender da ordem não determinística dos gêneros.

Também há um caso de regressão com filtro por gênero, comparando o endpoint
novo com o helper legado por tag. Resultado: **24 testes, todos OK**, tanto no
venv local quanto dentro da imagem Docker (`python:3.9-slim`). Contagens
verificadas:

| Sequência | Músicas pela tag | Músicas pelo matcher |
|---|---:|---:|
| Bm - G - D - A | 199 | 199 |
| C - G - Am - F | 296 | 296 |
| Em - G | 4 | 4 |
| C - A7 - Dm - G7 | 5 | 5 |
| Gm - F | 7 | 7 |
| C - C7 - F - Fm | 3 | 3 |

Também foi validado manualmente no Docker: cadastro de sequência, retorno de
`total_musicas`, busca pela sequência cadastrada e persistência após remover e
recriar o container usando o volume nomeado.

## Como rodar

Com o virtualenv:

```
python3 -m unittest discover -s tests -v
```

Dentro da imagem Docker:

```
docker run --rm ciframe python -m unittest discover -s tests -v
```

## O que ficou de fora

- Não há teste automatizado de browser/e2e; o fluxo da página
  `#/porsequencia` foi validado apenas por inspeção e smoke test via HTTP.
- Não há benchmark formal de performance; apenas a constatação de que a
  varredura das 67.585 músicas é aceitável no uso local.
- Não há teste de concorrência entre múltiplos workers do gunicorn escrevendo
  no SQLite ao mesmo tempo.
- Não há teste de limites de abuso do endpoint anônimo além das validações de
  tamanho e tipo.
