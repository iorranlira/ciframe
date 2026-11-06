# coding: utf-8
import json
import os
import sqlite3
from typing import Iterable, List, Optional

from musica import Musica

MAX_NOME = 120
MAX_ACORDES = 64
MAX_ACORDE = 20

# A ordem desta lista é a mesma dos ids usados pela coluna SEQ_FAMOSA:
# 0=BmGDA, 1=CGAmF, 2=EmG, 3=CA7DmG7, 4=GmF, 5=CC7FFm.
SEQUENCIAS_ORIGINAIS = [
    {'nome': 'Sequência de Bm', 'acordes': ['Bm', 'G', 'D', 'A']},
    {'nome': 'Sequência de C', 'acordes': ['C', 'G', 'Am', 'F']},
    {'nome': 'Sequência Em', 'acordes': ['Em', 'G']},
    {'nome': 'Sequência de C (Samba)', 'acordes': ['C', 'A7', 'Dm', 'G7']},
    {'nome': 'Sequência de Gm', 'acordes': ['Gm', 'F']},
    {'nome': 'Sequência de C (Samba cont.)', 'acordes': ['C', 'C7', 'F', 'Fm']},
]


class SequenciaInvalida(ValueError):
    pass


class SequenciaDuplicada(Exception):
    pass


def normalizar_acorde(acorde):
    # type: (str) -> str
    return acorde.strip().lower()


def normalizar_acordes(acordes):
    # type: (Iterable[str]) -> List[str]
    return [normalizar_acorde(acorde) for acorde in acordes]


def chave_normalizada(acordes):
    # type: (Iterable[str]) -> str
    return ''.join(normalizar_acorde(acorde) for acorde in acordes)


def aparece_na_musica(sequencia_normalizada, musica):
    # type: (List[str], Musica) -> bool
    if not sequencia_normalizada:
        return False

    cifra = normalizar_acordes(musica.cifra)
    if not set(cifra).issubset(set(sequencia_normalizada)):
        return False

    tamanho = len(sequencia_normalizada)
    return any(
        cifra[i:i + tamanho] == sequencia_normalizada
        for i in range(len(cifra) - tamanho + 1)
    )


def caminho_db_padrao():
    # type: () -> str
    configurado = os.environ.get('SEQUENCES_DB')
    if configurado:
        return configurado
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'instance',
        'sequences.db',
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS sequences (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nome           TEXT NOT NULL,
    acordes_json   TEXT NOT NULL,
    normalized_key TEXT NOT NULL UNIQUE,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    is_builtin     INTEGER NOT NULL DEFAULT 0
)
"""


def _conectar(caminho):
    # type: (str) -> sqlite3.Connection
    if caminho != ':memory:':
        diretorio = os.path.dirname(os.path.abspath(caminho))
        if diretorio:
            os.makedirs(diretorio, exist_ok=True)

    conn = sqlite3.connect(caminho, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(caminho=None):
    # type: (Optional[str]) -> sqlite3.Connection
    conn = _conectar(caminho or caminho_db_padrao())
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def seed_sequencias_originais(conn):
    # type: (sqlite3.Connection) -> None
    for sequencia in SEQUENCIAS_ORIGINAIS:
        conn.execute(
            """
            INSERT OR IGNORE INTO sequences
                (nome, acordes_json, normalized_key, is_builtin)
            VALUES (?, ?, ?, 1)
            """,
            (
                sequencia['nome'],
                json.dumps(sequencia['acordes'], ensure_ascii=False),
                chave_normalizada(sequencia['acordes']),
            ),
        )
    conn.commit()


def _linha_para_dict(linha):
    # type: (sqlite3.Row) -> dict
    return {
        'id': linha['id'],
        'nome': linha['nome'],
        'acordes': json.loads(linha['acordes_json']),
        'normalized_key': linha['normalized_key'],
        'is_builtin': linha['is_builtin'],
        'created_at': linha['created_at'],
    }


def listar_sequencias(conn):
    # type: (sqlite3.Connection) -> List[dict]
    linhas = conn.execute(
        """
        SELECT id, nome, acordes_json, normalized_key, is_builtin, created_at
        FROM sequences
        ORDER BY id
        """
    ).fetchall()
    return [_linha_para_dict(linha) for linha in linhas]


def buscar_por_chave(conn, chave):
    # type: (sqlite3.Connection, str) -> Optional[dict]
    linha = conn.execute(
        """
        SELECT id, nome, acordes_json, normalized_key, is_builtin, created_at
        FROM sequences
        WHERE normalized_key = ?
        """,
        (chave,),
    ).fetchone()
    if linha is None:
        return None
    return _linha_para_dict(linha)


def validar_sequencia(nome, acordes):
    # type: (object, object) -> tuple
    if not isinstance(nome, str):
        raise SequenciaInvalida('O nome da sequência deve ser um texto.')
    nome = nome.strip()
    if not nome:
        raise SequenciaInvalida('O nome da sequência é obrigatório.')
    if len(nome) > MAX_NOME:
        raise SequenciaInvalida(
            'O nome da sequência deve ter no máximo %d caracteres.' % MAX_NOME
        )

    if not isinstance(acordes, list) or not acordes:
        raise SequenciaInvalida('Informe pelo menos um acorde.')
    if len(acordes) > MAX_ACORDES:
        raise SequenciaInvalida(
            'A sequência deve ter no máximo %d acordes.' % MAX_ACORDES
        )

    acordes_limpos = []
    for acorde in acordes:
        if not isinstance(acorde, str):
            raise SequenciaInvalida('Todos os acordes devem ser textos.')
        acorde = acorde.strip()
        if not acorde:
            raise SequenciaInvalida('Nenhum acorde pode ser vazio.')
        if len(acorde) > MAX_ACORDE:
            raise SequenciaInvalida(
                'Cada acorde deve ter no máximo %d caracteres.' % MAX_ACORDE
            )
        if any(ord(caractere) < 32 for caractere in acorde):
            raise SequenciaInvalida('Os acordes não podem conter caracteres de controle.')
        acordes_limpos.append(acorde)

    return nome, acordes_limpos


def criar_sequencia(conn, nome, acordes):
    # type: (sqlite3.Connection, object, object) -> dict
    nome, acordes = validar_sequencia(nome, acordes)
    chave = chave_normalizada(acordes)

    if buscar_por_chave(conn, chave) is not None:
        raise SequenciaDuplicada(chave)

    try:
        conn.execute(
            """
            INSERT INTO sequences
                (nome, acordes_json, normalized_key, is_builtin)
            VALUES (?, ?, ?, 0)
            """,
            (nome, json.dumps(acordes, ensure_ascii=False), chave),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise SequenciaDuplicada(chave)

    return buscar_por_chave(conn, chave)
