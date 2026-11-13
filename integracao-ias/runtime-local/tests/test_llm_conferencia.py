# -*- coding: utf-8 -*-
"""Integracao LLM (provedor simulado) e agente conferidor_fontes_oficiais. Dados SINTETICOS."""
import json, os, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agentes, llm, conferencia, robo, auditor_oficial as ao
from test_agentes import Base

CASO = "Maria Souza Lima, CPF 111.222.333-96, execucao fiscal com prescricao intercorrente, art. 40 Lei 6.830/80"
def saida(**k):
    d = {x: [] for x in ["fatos", "lacunas", "normas_oficiais", "julgados_nao_conferidos", "teses_favoraveis", "teses_contrarias", "riscos", "providencias", "pendencias_validacao"]}
    d.update(k); return d


class TestLLM(Base):
    def test_sem_provedor_falha_explicita(self):
        os.environ.pop("JURISBASE_LLM_PROVIDER", None)
        with self.assertRaises(llm.LLMIndisponivel): llm.responder("execucao_fiscal", CASO)
        r = robo.comando({"acao": "responder_agente", "agente": "execucao_fiscal", "caso": CASO})
        self.assertEqual(r["erro"], "modelo indisponivel"); self.assertFalse(r["conferido_oficial"])
    def test_prompt_recebe_so_texto_sanitizado(self):
        vistos = []
        def prov(p): vistos.append(p); return json.dumps(saida())
        r = llm.responder("execucao_fiscal", CASO, provedor=prov)
        self.assertTrue(r["valida"]); self.assertEqual(r["dados_enviados_ao_modelo"], "texto sanitizado")
        self.assertNotIn("111.222.333-96", vistos[0]); self.assertNotIn("Maria Souza", vistos[0])
        r = llm.responder("execucao_fiscal", CASO, provedor=prov, dados_reais=True)
        self.assertIn("111.222.333-96", vistos[1]); self.assertIn("autorizado", r["dados_enviados_ao_modelo"])
    def test_citacoes_do_modelo_vao_ao_auditor_e_ficam_nao_conferidas(self):
        cit = {"tribunal": "STJ", "processo": "REsp 1.340.553/RS", "tese_atribuida": "x", "url": "https://exemplo.com/x"}
        r = llm.responder("execucao_fiscal", CASO, provedor=lambda p: "texto antes " + json.dumps(saida(julgados_nao_conferidos=[cit])) + " depois")
        a = r["auditoria_citacoes"][0]
        self.assertEqual(a["status"], "NAO_CONFERIDO"); self.assertFalse(a["apto_para_conferencia_do_advogado"]); self.assertFalse(a["pode_constar_na_minuta"])
        self.assertFalse(r["conferido_oficial"]); self.assertFalse(r["pode_constar_na_minuta"])
        self.assertTrue(any("NAO_CONFERIDO" in x for x in r["saida"]["pendencias_validacao"]))
    def test_saida_invalida_e_chaves_ausentes(self):
        r = llm.responder("execucao_fiscal", CASO, provedor=lambda p: "sem json aqui")
        self.assertFalse(r["valida"]); self.assertIn("invalida", r["erro"])
        r = llm.responder("execucao_fiscal", CASO, provedor=lambda p: json.dumps({"fatos": ["a"]}))
        self.assertFalse(r["valida"]); self.assertTrue(any("chaves ausentes" in x for x in r["avisos_runtime"]))
    def test_precondicao_nao_liberada_avisa(self):
        r = llm.responder("execucao_fiscal", CASO, provedor=lambda p: json.dumps(saida()))
        self.assertFalse(r["pre_condicoes"]["pode_concluir"]); self.assertTrue(any("condicional" in x for x in r["avisos_runtime"]))
    def test_agente_desabilitado_ou_inexistente(self):
        with self.assertRaises(LookupError): llm.responder("inexistente", CASO, provedor=lambda p: "{}")
    def test_provedores_sem_credencial(self):
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"): os.environ.pop(k, None)
        for n in ("anthropic", "openai"):
            with self.assertRaises(llm.LLMIndisponivel): llm.PROVEDORES[n]("x")


class TestConferidor(Base):
    def test_itens_e_nunca_conferido(self):
        self.assertEqual(set(conferencia.ITENS), {"tema_1184_stf", "res_cnj_547_2024", "lei_14133_arts_190_191_193"})
        off = lambda u: {"consulta": u, "acessivel": False, "erro": "sem rede (simulado)"}
        for k in conferencia.ITENS:
            r = conferencia.conferir(k, off)
            self.assertEqual(r["estado"], "LOCALIZADO_OFICIAL"); self.assertFalse(r["conferido_oficial"]); self.assertFalse(r["pode_constar_na_minuta"])
            self.assertFalse(r["inteiro_teor_obtido"]); self.assertTrue(r["pendencias"]); self.assertTrue(r["achados"])
            self.assertTrue(all(ao.url_oficial(u) for u in conferencia.ITENS[k]["urls"]))
    def test_portal_indisponivel_nao_vira_verificacao_ao_vivo(self):
        r = conferencia.conferir("tema_1184_stf", lambda u: (_ for _ in ()).throw(TimeoutError("t")))
        self.assertTrue(r["via"].startswith("busca_em_dominio_oficial")); self.assertFalse(any(c["acessivel"] for c in r["consultas_ao_vivo"]))
    def test_marcadores_do_texto_ao_vivo(self):
        txt = "<html>Resolução n. 689 ... 10.000,00 ... movimentação útil há mais de um ano ... tema 566 ... tema 390 ... art. 921</html>"
        r = conferencia.conferir("res_cnj_547_2024", lambda u: {"consulta": u, "acessivel": True, "status_http": 200, "texto": txt})
        c = r["consultas_ao_vivo"][0]; self.assertEqual(c["marcadores_ausentes"], []); self.assertEqual(r["via"], "conector_http_ao_vivo")
        r = conferencia.conferir("res_cnj_547_2024", lambda u: {"consulta": u, "acessivel": True, "status_http": 200, "texto": "pagina qualquer"})
        self.assertTrue(r["consultas_ao_vivo"][0]["marcadores_ausentes"])
    def test_item_desconhecido_e_endpoint(self):
        with self.assertRaises(LookupError): conferencia.conferir("x")
        self.assertIn("itens", robo.comando({"acao": "conferir_fonte_oficial"}))
        self.assertIn("conferidor_fontes_oficiais", agentes.listar()["componentes"])
    def test_conferidor_na_config_e_ficha(self):
        c = agentes.config(); self.assertEqual(c["verifiers"][0]["id"], "conferidor_fontes_oficiais"); self.assertEqual(len(c["agents"]), 20)
        self.assertTrue((agentes.FICHAS / "conferidor_fontes_oficiais.txt").exists())

if __name__ == "__main__":
    unittest.main()
