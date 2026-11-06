# Persistir o catálogo de sequências de acordes em SQLite

O catálogo de sequências famosas vivia em um dicionário hardcoded em `main.py`.
As seis entradas eram resolvidas por uma chave exata, e as músicas eram
filtradas pela coluna pré-computada `SEQ_FAMOSA` do CSV. Isso impedia que
visitantes cadastrassem sequências novas e fazia qualquer alteração no catálogo
depender de um novo deploy.

Decidimos persistir apenas o catálogo de sequências em SQLite, em
`instance/sequences.db`, usando `sqlite3` da biblioteca padrão. Músicas e
gêneros continuam vindo de `data/top/dataset_final.csv`, carregados em memória
no startup; a migração para banco atinge somente as sequências. A aplicação
continua em um único container Docker local, com um volume nomeado em
`/app/instance` para que o arquivo sobreviva à recriação do container.

Todas as sequências — as seis originais e as cadastradas por visitantes — usam
um único matcher que replica a semântica da tag `SEQ_FAMOSA`: os acordes da
música precisam estar contidos no conjunto da sequência e a sequência precisa
aparecer como trecho contíguo de `Musica.cifra`. A comparação normaliza caixa e
espaços nos dois lados, e a chave persistida mantém o formato atual de
concatenação sem separador, em minúsculas. Isso preserva exatamente os
resultados das seis sequências originais e evita um segundo caminho de busca.

A consequência é que a semântica é restritiva: sequências novas podem não
retornar nenhuma música. Para tornar isso visível, o cadastro calcula e devolve
o total de músicas encontradas; o frontend mostra o número e avisa quando ele é
zero. O custo é uma varredura das 67.585 músicas no cadastro e em cada busca,
aceitável para o uso local atual. Autenticação, moderação, edição/remoção e
rate limiting ficam fora do escopo: o catálogo é aberto e anônimo por requisito.
