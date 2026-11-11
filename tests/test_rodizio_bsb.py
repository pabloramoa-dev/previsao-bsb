"""Testes offline: o rodízio não depende de serviços externos."""
import unittest
from datetime import timedelta
from boletim import INICIO_RODIZIO, REGIOES, indice_destaque, selecionar_localidades


class RodizioBSB(unittest.TestCase):
    def test_catalogo_completo_e_sem_duplicacao(self):
        nomes = [n for locais in REGIOES.values() for n, _, _ in locais]
        self.assertEqual(len(REGIOES), 5)
        self.assertEqual(len(nomes), 35)
        self.assertEqual(len(set(nomes)), 35)

    def test_todas_aparecem_em_cinco_dias(self):
        vistas = {s: set() for s in REGIOES}
        for dia_offset in range(5):
            dia = INICIO_RODIZIO + timedelta(days=dia_offset)
            for turno in ("manha", "noite"):
                for setor, (nome, _, _) in selecionar_localidades(dia, turno):
                    vistas[setor].add(nome)
        for setor, locais in REGIOES.items():
            self.assertEqual(vistas[setor], {n for n, _, _ in locais})

    def test_sem_repeticao_nos_reels_consecutivos(self):
        anteriores = {}
        for d in range(40):
            dia = INICIO_RODIZIO + timedelta(days=d)
            for turno in ("manha", "noite"):
                escolhidas = selecionar_localidades(dia, turno)
                self.assertEqual(len(escolhidas), 5)
                for setor, (nome, _, _) in escolhidas:
                    self.assertNotEqual(nome, anteriores.get(setor))
                    anteriores[setor] = nome

    def test_selecao_estavel_e_abertura_variada(self):
        dia = INICIO_RODIZIO
        self.assertEqual(selecionar_localidades(dia, "manha"),
                         selecionar_localidades(dia, "manha"))
        self.assertNotEqual(selecionar_localidades(dia, "manha"),
                            selecionar_localidades(dia, "noite"))
        indices = [indice_destaque(dia + timedelta(days=i // 2),
                                   "manha" if i % 2 == 0 else "noite")
                   for i in range(6)]
        self.assertEqual(indices, [0, 1, 2, 3, 4, 0])


if __name__ == "__main__":
    unittest.main()
