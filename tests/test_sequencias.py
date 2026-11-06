# coding: utf-8
import json
import os
import tempfile
import unittest
from types import SimpleNamespace

_BD_TEMP = tempfile.TemporaryDirectory()
os.environ['SEQUENCES_DB'] = os.path.join(_BD_TEMP.name, 'sequences.db')

import main  # noqa: E402
import sequencias  # noqa: E402


class TestNormalizacao(unittest.TestCase):

    def test_normaliza_caixa_e_espacos(self):
        self.assertEqual(sequencias.normalizar_acorde('  Bm '), 'bm')
        self.assertEqual(sequencias.normalizar_acorde('   '), '')
        self.assertEqual(
            sequencias.normalizar_acordes([' Bm ', 'G', 'D', 'A']),
            ['bm', 'g', 'd', 'a'],
        )

    def test_chave_mantem_formato_sem_separador(self):
        self.assertEqual(
            sequencias.chave_normalizada(['Bm', 'G', 'D', 'A']),
            'bmgda',
        )
        self.assertEqual(
            sequencias.chave_normalizada(['bm', 'g', 'd', 'a']),
            'bmgda',
        )


class TestMatcher(unittest.TestCase):

    def _musica(self, cifra):
        return SimpleNamespace(cifra=cifra)

    def test_trecho_contiguo_presente(self):
        self.assertTrue(
            sequencias.aparece_na_musica(
                ['c', 'g'],
                self._musica(['C', 'G', 'C']),
            )
        )

    def test_fora_de_ordem_nao_casa(self):
        self.assertFalse(
            sequencias.aparece_na_musica(
                ['c', 'g', 'c'],
                self._musica(['G', 'C', 'G']),
            )
        )

    def test_acorde_fora_do_conjunto_nao_casa(self):
        self.assertFalse(
            sequencias.aparece_na_musica(
                ['c', 'g'],
                self._musica(['C', 'G', 'Am']),
            )
        )

    def test_cifra_vazia_nao_casa(self):
        self.assertFalse(
            sequencias.aparece_na_musica(['c', 'g'], self._musica([]))
        )

    def test_repeticao_e_sequencia_de_um_acorde(self):
        self.assertTrue(
            sequencias.aparece_na_musica(
                ['c', 'g', 'c'],
                self._musica(['C', 'G', 'C', 'G']),
            )
        )
        self.assertTrue(
            sequencias.aparece_na_musica(['c'], self._musica(['C', 'C']))
        )

    def test_caixa_diferente_nos_dois_lados(self):
        self.assertTrue(
            sequencias.aparece_na_musica(
                sequencias.normalizar_acordes(['C', 'G']),
                self._musica(['c', 'g']),
            )
        )


class TestRepositorio(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.tempdir.name, 'sequences.db')
        self.conn = sequencias.init_db(self.caminho)
        sequencias.seed_sequencias_originais(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tempdir.cleanup()

    def test_seed_idempotente(self):
        sequencias.seed_sequencias_originais(self.conn)
        catalogo = sequencias.listar_sequencias(self.conn)
        self.assertEqual(len(catalogo), 6)
        self.assertTrue(all(item['is_builtin'] == 1 for item in catalogo))

    def test_busca_por_chave_normalizada(self):
        sequencia = sequencias.buscar_por_chave(self.conn, 'bmgda')
        self.assertIsNotNone(sequencia)
        self.assertEqual(sequencia['acordes'], ['Bm', 'G', 'D', 'A'])

    def test_cria_sequencia_nova(self):
        sequencia = sequencias.criar_sequencia(
            self.conn,
            'Teste C G',
            ['C', 'G'],
        )
        self.assertEqual(sequencia['normalized_key'], 'cg')
        self.assertEqual(sequencia['is_builtin'], 0)
        self.assertEqual(
            sequencias.buscar_por_chave(self.conn, 'cg')['nome'],
            'Teste C G',
        )

    def test_duplicata_normalizada(self):
        with self.assertRaises(sequencias.SequenciaDuplicada):
            sequencias.criar_sequencia(
                self.conn,
                'Duplicada',
                ['bm', 'g', 'd', 'a'],
            )

    def test_validacao(self):
        casos = [
            ('', ['C']),
            ('Nome', []),
            ('Nome', 'C'),
            ('Nome', ['C', '']),
            ('Nome', [1]),
        ]
        for nome, acordes in casos:
            with self.assertRaises(sequencias.SequenciaInvalida):
                sequencias.validar_sequencia(nome, acordes)

    def test_persistencia_apos_reabrir(self):
        sequencias.criar_sequencia(self.conn, 'Persistente', ['C', 'G'])
        self.conn.close()

        self.conn = sequencias.init_db(self.caminho)
        sequencia = sequencias.buscar_por_chave(self.conn, 'cg')
        self.assertIsNotNone(sequencia)
        self.assertEqual(sequencia['nome'], 'Persistente')


class TestAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = main.app.test_client()

    def _json(self, response):
        return json.loads(response.get_data(as_text=True))

    def _ids_da_busca(self, sequencia_param, generos=None):
        ids = set()
        pagina = 1
        while True:
            query_string = {
                'sequencia': sequencia_param,
                'pagina': pagina,
            }
            if generos:
                query_string['generos'] = generos

            response = self.client.get(
                '/similares',
                query_string=query_string,
            )
            self.assertEqual(response.status_code, 200)
            dados = self._json(response)
            if not dados:
                break
            ids.update(item['id_unico_musica'] for item in dados)
            pagina += 1
        return ids

    def _ids_esperados_por_tag(self, id_seq):
        return {
            musica.id_unico_musica
            for musica in main.musicas.values()
            if str(id_seq) in musica.seqs_famosas
        }

    def test_get_catalogo(self):
        response = self.client.get('/sequencias')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.content_type)
        catalogo = self._json(response)
        self.assertGreaterEqual(len(catalogo), 6)
        self.assertEqual(
            len([item for item in catalogo if item['is_builtin'] == 1]),
            6,
        )

    def test_regressao_matcher_contra_seq_famosa(self):
        for id_seq, sequencia in enumerate(sequencias.SEQUENCIAS_ORIGINAIS):
            normalizada = sequencias.normalizar_acordes(sequencia['acordes'])
            for musica in main.musicas.values():
                esperado = str(id_seq) in musica.seqs_famosas
                obtido = sequencias.aparece_na_musica(normalizada, musica)
                self.assertEqual(
                    obtido,
                    esperado,
                    'Divergência na sequência %s, música %s' % (
                        id_seq,
                        musica.id_unico_musica,
                    ),
                )

    def test_regressao_endpoint_contra_seq_famosa(self):
        for id_seq, sequencia in enumerate(sequencias.SEQUENCIAS_ORIGINAIS):
            parametro = ','.join(sequencia['acordes'])
            self.assertEqual(
                self._ids_da_busca(parametro),
                self._ids_esperados_por_tag(id_seq),
                'Divergência no endpoint para %s' % parametro,
            )

    def test_regressao_endpoint_com_filtro_de_genero(self):
        id_seq = 0
        sequencia = sequencias.SEQUENCIAS_ORIGINAIS[id_seq]
        parametro = ','.join(sequencia['acordes'])
        genero = sorted(main.generos)[0]

        esperado = {
            item['id_unico_musica']
            for item in main.get_similares_por_tag(id_seq, [genero])
        }
        self.assertEqual(
            self._ids_da_busca(parametro, generos=genero),
            esperado,
        )

    def test_busca_normaliza_caixa(self):
        self.assertEqual(
            self._ids_da_busca('bm,g,d,a'),
            self._ids_da_busca('Bm,G,D,A'),
        )
        self.assertEqual(
            self._ids_da_busca('BmGDA'),
            self._ids_da_busca('Bm,G,D,A'),
        )

    def test_busca_sequencia_inexistente_retorna_vazio(self):
        self.assertEqual(self._ids_da_busca('Zz,YY'), set())

    def test_post_cria_e_busca_sequencia(self):
        response = self.client.post(
            '/sequencias',
            json={'nome': 'Teste C G', 'acordes': ['C', 'G']},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('text/html', response.content_type)
        criada = self._json(response)
        self.assertIn('total_musicas', criada)
        self.assertEqual(criada['normalized_key'], 'cg')

        ids = self._ids_da_busca('C,G')
        self.assertEqual(len(ids), criada['total_musicas'])

        catalogo = self._json(self.client.get('/sequencias'))
        self.assertIn('Teste C G', [item['nome'] for item in catalogo])

    def test_post_zero_resultados(self):
        response = self.client.post(
            '/sequencias',
            json={'nome': 'Teste Zz', 'acordes': ['Zz']},
        )
        self.assertEqual(response.status_code, 201)
        criada = self._json(response)
        self.assertEqual(criada['total_musicas'], 0)
        self.assertEqual(self._ids_da_busca('Zz'), set())

    def test_post_duplicata(self):
        response = self.client.post(
            '/sequencias',
            json={'nome': 'Duplicada', 'acordes': ['Bm', 'G', 'D', 'A']},
        )
        self.assertEqual(response.status_code, 409)

    def test_post_payload_invalido(self):
        response = self.client.post(
            '/sequencias',
            json={'nome': 'Sem acordes', 'acordes': []},
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post('/sequencias', data='nao é json')
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
