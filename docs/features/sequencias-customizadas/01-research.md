# Pesquisa — Sequências de Acordes Customizadas

> Preencha esta fase antes de propor qualquer solução. O objetivo é investigar as
> perguntas abaixo com evidência real (código, dados, testes rápidos que você mesmo
> rodou), não chutar. Apague este bloco de instruções antes de entregar.

## Perguntas que você precisa responder

1. **Algoritmo de matching**: hoje, as 6 sequências hardcoded em `main.py` (linhas
   40-45) são comparadas contra músicas via uma tag pré-computada
   (`SEQ_FAMOSA`/`seqs_famosas`, vinda do CSV). Sequências cadastradas pelo usuário
   não têm essa tag — o matching precisa ser calculado em tempo real a partir da
   lista de acordes de cada música (`musica.acordes`/`musica.cifra`). O que vai
   definir "a sequência X aparece na música Y"? A ordem dos acordes importa?
   Repetições de acorde dentro da música importam? É preciso normalizar (ex.:
   maiúsculas/minúsculas, variações de escrita do mesmo acorde)?
2. **Validação da hipótese**: rode o algoritmo que você está considerando contra os
   dados reais em `data/top/dataset_final.csv`, para as 6 sequências hoje
   hardcoded, e confirme (ou refute) que ele reproduz os mesmos matches que o
   código atual produz via `seqs_famosas`. Esse é o bar mínimo de correção que
   você vai usar na fase de testes.
3. **Banco de dados**: quais bancos embarcados (sem serviço externo adicional) são
   viáveis dentro do container Docker único e local-only já documentado em
   `docs/adr/0001-local-only-docker-deploy.md`? O que cada opção implica para o
   `Dockerfile` atual e para a persistência dos dados entre reinícios do
   container?
4. **Frontend existente**: o que a página `#/porsequencia`
   (`static/templates/sequencia.html` +
   `static/assets/js/controllers/sequencia.js`) já faz? Repare que ela tem hoje uma
   lista *hardcoded no JavaScript* de 4 sequências (`sequencia1`..`sequencia4`),
   diferente das 6 que existem no backend — um detalhe real e pré-existente do
   código, não um erro seu, que vale entender antes de decidir o que precisa
   mudar.

## Registro das descobertas

1. Algoritmo de matching:
**O que define “a sequência X aparece na música Y?”** A sequência X aparece na música Y quando duas condições são verdadeiras ao mesmo tempo, depois de normalizar ambas com a mesma função. 
**A ordem importa?** Sim. A sequência precisa ser uma parte contígua de musica.cifra, em ordem. Se for uma sequência fora de ordem não encontra o padrão. 
**Repetições importam?** Sim. A entrada deve respeitar as repetições originais da sequência. 
**Normalização?** Sim, levando em consideração espaços (strip().lower()) aplicada à sequência e a cada acorde da música. A chave persistida fica sem separador e em minúsculas, Variações de escrita do mesmo acorde não são tratadas e ficam para o  futuro.

2. **Validação da hipótese**:

3. **Banco de dados**: 
o BD escolhido foi SQLite via sqlite3 da stdlib. Para o ´Dockerfile´ é preciso declarar VOLUME /app/instance e executar o container com um volume nomeado, por exemplo -v deciframe-data:/app/instance. Em relação a persistência local, o banco não sobrevive ao ´docker rm´.

4. **Frontend existente**
A página #/porsequencia é a tela da feature de busca de músicas por sequência de acordes. Hoje ela: guarda uma lista fixa de 4 sequências (sequencia1 a sequencia4) e, quando o usuário escolhe uma, faz a busca chamando similares?sequencia=...´ no backend. 
 

## Trade-offs identificados

1. Algoritmo de matching: A regra estrita da tag (todos os acordes da música dentro do conjunto da sequência, e a sequência como trecho contíguo de cifra) reproduz exatamente as 6 originais e serve para todas as sequências. A parte negativa é que ela é restritiva e pode retornar zero ou poucos resultados para sequências novas. Exigir só o trecho contíguo traria mais resultados, mas não reproduziria as 6 originais. Ignorar ordem e repetição (usando acordes como conjunto) é simples, mas perde o sentido de “sequência” e não bate com a tag atual

2. Chave normalizada. Concatenar os acordes em minúsculas, sem separador (bmgda), mantém o formato que o backend já usa, mas não preserva a caixa original (que fica em nome e acordes_json). Usar vírgula como separador seria mais legível, mas mudaria o contrato atual da busca.

3. Banco de dados. O SQLite via sqlite3 da stdlib não exige serviço nem dependência nova e cabe no container único. O custo é não ter migrations e precisar de volume nomeado para persistir. Manter tudo em memória não muda a infraestrutura, mas não persiste. Um serviço externo, como Postgres, é mais robusto, mas viola o deploy local-only em container único.

4. Frontend. Carregar o catálogo via GET /sequencias cria uma fonte única de verdade e elimina a divergência entre 4 e 6 sequências, mas passa a depender do backend. Apenas ampliar a lista hardcoded para 6 é mais simples, porém não resolve o cadastro nem a duplicação de fonte. 