# -*- coding: utf-8 -*-
import hashlib, json, os, sys, unittest, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agentes, robo

REAL = agentes.config
def _enabled():
    c = REAL(); [a.__setitem__("enabled", True) for a in c["agents"]]; return c
def _disabled():
    c = REAL(); [a.__setitem__("enabled", False) for a in c["agents"]]; return c

def cnj(n, aaaa, j, tr, oooo):
    dd = 98 - int(f"{n:07d}{aaaa}{j}{tr}{oooo}00") % 97
    return f"{n:07d}-{dd:02d}.{aaaa}.{j}.{tr}.{oooo}"

class Base(unittest.TestCase):
    def setUp(self): agentes.config = _enabled
    def tearDown(self): agentes.config = REAL

class TestEstrutura(Base):
    def test_22_componentes_e_9_fontes(self):
        d = agentes.FICHAS
        c = REAL()
        self.assertEqual(len(c["agents"]), 20)
        for a in c["agents"]:
            self.assertTrue((d / f"{a['id']}.txt").exists(), a["id"])
        for extra in ["auditor_citacoes", "coordenador"] + sorted(agentes.FONTES):
            self.assertTrue((d / f"{extra}.txt").exists(), extra)
        self.assertEqual(len(agentes.FONTES), 9)

class TestRoteamento(Base):
    def test_cada_especialista_positivo(self):
        for a in REAL()["agents"]:
            for t in a["trigger_terms"]:
                r = agentes.rotear(f"Preciso de analise sobre {t} neste caso")
                ids = [x["agente"] for x in r["agentes"]]
                self.assertEqual(ids, [a["id"]], f"{a['id']} / {t} -> {ids}")
    def test_cada_especialista_negativo(self):
        r = agentes.rotear("receita de bolo de cenoura e compra de bicicleta")
        self.assertEqual(r["modo"], "triagem_humana")
    def test_ambiguo_vira_cooperacao(self):
        r = agentes.rotear("execucao fiscal com precatorio")
        self.assertEqual(r["modo"], "cooperacao_revisao_humana")
        self.assertGreater(len(r["agentes"]), 1)
    def test_licitacao_nao_aciona_citacao(self):
        r = agentes.rotear("licitacao")
        self.assertEqual([x["agente"] for x in r["agentes"]], ["administrativo_licitacoes"])
    def test_desabilitado_nao_roteia_nem_prepara(self):
        agentes.config = _disabled
        self.assertEqual(agentes.rotear("execucao fiscal")["modo"], "triagem_humana")
        with self.assertRaises(PermissionError):
            agentes.preparar("execucao_fiscal", "x")

class TestPacotes(Base):
    def test_pacote_de_cada_agente(self):
        for a in REAL()["agents"]:
            p = agentes.preparar(a["id"], "caso generico")
            self.assertTrue(p["instrucoes"], a["id"])
            self.assertIn("julgados_nao_conferidos", p["saida"])
            self.assertIn("NAO_CONFERIDO", p["ficha"], a["id"])
            self.assertIn("bloqueada", p["escrita"])
    def test_agente_desconhecido(self):
        with self.assertRaises(LookupError): agentes.preparar("inexistente")

class TestT01aT08(Base):
    def test_T01(self):
        r = agentes.pre_condicoes("execucao_fiscal", "CDA com alegacao de prescricao intercorrente")
        self.assertFalse(r["pode_concluir"]); self.assertTrue(any("art. 40" in x for x in r["lacunas"]))
        ok = agentes.pre_condicoes("execucao_fiscal", "prescricao: CDA 01/02/2015, citacao 03/04/2016, suspensao 05/06/2017, intimacao 07/08/2018")
        self.assertFalse(ok["pode_concluir"], "tres datas no texto nunca liberam conclusao (skill_marcos_e_precedentes)")
    def test_T02(self):
        r = agentes.pre_condicoes("execucao_fiscal", "Execucao de baixo valor e Tema 1184")
        self.assertFalse(r["pode_concluir"])
        self.assertTrue(any("nao presumir extincao" in x for x in r["avisos"]))
        self.assertIn("1.355.208", agentes.preparar("execucao_fiscal", "x")["ficha"])
    def test_T03(self):
        r = agentes.pre_condicoes("civil_processual", "Citacao contestada e defesa apresentada")
        self.assertFalse(r["pode_concluir"])
        self.assertTrue(any("comparecimento espontaneo" in x for x in r["lacunas"]))
    def test_T04(self):
        r = agentes.pre_condicoes("administrativo_licitacoes", "Contrato iniciado sob lei anterior")
        self.assertFalse(r["pode_concluir"]); self.assertTrue(any("14.133" in x for x in r["avisos"]))
        f = agentes.preparar("administrativo_licitacoes", "x")["ficha"]
        self.assertIn("art. 190", f); self.assertIn("193", f)
    def test_T05(self):
        r = agentes.pre_condicoes("imobiliario_registral", "Conflito possessorio coletivo")
        self.assertFalse(r["pode_concluir"]); self.assertTrue(any("desapropriacao" in x for x in r["avisos"]))
    def test_T06(self):
        s = agentes.sanitizar("Joao da Silva Pereira, CPF 123.456.789-09, proc. 0001234-55.2020.8.16.0116, joao@x.com, tel (41) 99999-8888", nomes=["Joao da Silva Pereira"])
        t = s["texto_externo"]
        for proibido in ["Joao", "123.456.789-09", "0001234-55", "joao@x.com", "99999-8888"]:
            self.assertNotIn(proibido, t)
        self.assertTrue(s["sanitizado"])
        # o fluxo completo tambem sanitiza o termo externo
        p = agentes.preparar("execucao_fiscal", "Maria Souza Lima CPF 111.222.333-96 execucao fiscal")
        self.assertNotIn("Maria", p["termo_externo"]); self.assertNotIn("111.222", p["termo_externo"])
    def test_T06_nao_destroi_termos_juridicos(self):
        t = agentes.sanitizar("Supremo Tribunal Federal Tema 1184 Codigo de Processo Civil")["texto_externo"]
        self.assertIn("Supremo Tribunal Federal", t); self.assertIn("Codigo de Processo Civil", t)
    def test_T07(self):
        r = agentes.auditar_citacoes([{"tribunal": "TJPR", "processo": "RE 1.355.208"}])["auditoria"][0]
        self.assertEqual(r["status"], "NAO_CONFERIDO"); self.assertFalse(r["pode_constar_na_minuta"])
        self.assertFalse(r["apto_para_conferencia_do_advogado"])
    def test_T08(self):
        with self.assertRaises(PermissionError):
            robo.comando({"acao": "gravar_achado", "item": {"id": "1"}, "classificacao": {}, "termo": "t", "confirmacao": ""})
        with self.assertRaises(PermissionError):
            robo.comando({"acao": "gravar_achado", "item": {"id": "1"}, "classificacao": {}, "termo": "t", "confirmacao": "sim"})

class TestSanitizacaoAdversarial(Base):
    CASOS = [("Cliente Maria cobrada pela CDA 123 contra Pedro, fone 41 99888-7777 execucao fiscal", ["Maria", "Pedro", "99888"]),
             ("Ronysson Antonio Pontes OAB/PR 70.662 processo 0000417-64.2026.8.16.0116 prescricao intercorrente", ["Ronysson", "70.662", "0000417"]),
             ("CPF 12345678909 CNPJ 12.345.678/0001-95 rg 12.345.678-9 tributos", ["12345678909", "12.345.678", "0001-95"]),
             ("JOAO DA SILVA e MARIA SOUZA moram na Rua das Flores, 123 CEP 83260-000 execucao fiscal", ["JOAO", "SILVA", "MARIA", "Flores", "83260"]),
             ("o executado joao silva deve IPTU, execucao fiscal, art. 40 da Lei 6.830/80 e Tema 1184", ["joao", "silva"])]
    def test_termo_externo_nunca_vaza(self):
        for caso, proibidos in self.CASOS:
            termo = agentes.termo_generico(caso)
            for p in proibidos:
                self.assertNotIn(p.lower(), termo.lower(), (caso, termo))
            pacote_ok = agentes.preparar("execucao_fiscal", caso)["termo_externo"]
            for p in proibidos:
                self.assertNotIn(p.lower(), pacote_ok.lower())
    def test_termo_externo_mantem_vocabulario_juridico(self):
        t = agentes.termo_generico("execucao fiscal, art. 40 da Lei 6.830/80 e Tema 1184 do Sr Fulano")
        for k in ["execucao fiscal", "art. 40", "Lei 6.830/80", "Tema 1184"]:
            self.assertIn(k, t)
    def test_sanitizador_complementar(self):
        for caso, proibidos in self.CASOS:
            t = agentes.sanitizar(caso)["texto_externo"]
            for p in proibidos:
                if p.lower() not in ("joao", "silva", "pedro"):   # minusculas sem papel: coberto pelo termo generico
                    self.assertNotIn(p, t, (caso, t))

class TestAuditor(Base):
    def cit(self, **kw):
        d = {"tribunal": "STF", "orgao_julgador": "Plenario", "processo": "RE 1.355.208", "relator": "Min. Carmen Lucia",
             "data_julgamento": "19/12/2023", "url": "https://portal.stf.jus.br/x"}; d.update(kw); return d
    def test_completa_oficial_continua_nao_conferida(self):
        r = agentes.auditar_citacoes([self.cit()])["auditoria"][0]
        self.assertTrue(r["apto_para_conferencia_do_advogado"]); self.assertEqual(r["status"], "NAO_CONFERIDO")
        self.assertFalse(r["pode_constar_na_minuta"])
    def test_url_nao_oficial(self):
        r = agentes.auditar_citacoes([self.cit(url="https://www.migalhas.com.br/x")])["auditoria"][0]
        self.assertIn("url nao oficial", r["problemas"])
        r = agentes.auditar_citacoes([self.cit(url="http://portal.stf.jus.br/x")])["auditoria"][0]
        self.assertIn("url nao oficial", r["problemas"])
    def test_cnj_ficticio_e_valido(self):
        bom = cnj(1234, 2020, 8, "16", "0116")
        self.assertTrue(agentes.cnj_valido(bom))
        ruim = bom[:8] + "00" + bom[10:] if bom[8:10] != "00" else bom[:8] + "01" + bom[10:]
        r = agentes.auditar_citacoes([self.cit(processo=ruim)])["auditoria"][0]
        self.assertTrue(any("invalido" in p for p in r["problemas"]))
        r = agentes.auditar_citacoes([self.cit(processo=bom)])["auditoria"][0]
        self.assertFalse(any("invalido" in p for p in r["problemas"]))
    def test_app_como_fundamento(self):
        r = agentes.auditar_citacoes([self.cit(referencia="segundo o acervo JurisBase")])["auditoria"][0]
        self.assertTrue(any("fundamento" in p for p in r["problemas"]))
    def test_nunca_conferido(self):
        for c in [self.cit(), {}, self.cit(url="")]:
            for x in agentes.auditar_citacoes([c])["auditoria"]:
                self.assertEqual(x["status"], "NAO_CONFERIDO"); self.assertFalse(x["pode_constar_na_minuta"])
    def test_conferir_so_advogado(self):
        for papel in ["IA", "auditor_citacoes", "claude", ""]:
            with self.assertRaises(PermissionError):
                robo.comando({"acao": "conferir_oficial", "id": 1, "papel": papel, "confirmacao": "CONFIRMO_CONFERENCIA_OFICIAL"})
        with self.assertRaises(PermissionError):
            robo.comando({"acao": "conferir_oficial", "id": 1, "papel": "advogado", "confirmacao": "ok"})

class TestSemEscrita(Base):
    def test_agentes_nao_alteram_banco(self):
        p = Path(robo.__file__).parent / "data" / "robo-julgados.db"
        h = lambda: hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
        antes = h()
        for pl in [{"acao": "agentes"}, {"acao": "rotear", "caso": "execucao fiscal"},
                   {"acao": "preparar_agente", "agente": "tributario", "caso": "tributos"},
                   {"acao": "sanitizar", "texto": "x"}, {"acao": "auditar_citacoes", "citacoes": []},
                   {"acao": "fluxo_agentes", "caso": "execucao fiscal CDA"}]:
            robo.comando(pl)
        self.assertEqual(antes, h())
    def test_fluxo_completo(self):
        f = agentes.fluxo("execucao fiscal, prescricao intercorrente, Joao Carlos Neves CPF 123.456.789-09")
        self.assertEqual(f["roteamento"]["modo"], "unico")
        self.assertNotIn("Joao", f["pacotes"][0]["termo_externo"])
        self.assertIn("auditar_citacoes", f["proximo"])
        self.assertEqual(agentes.fluxo("receita de bolo")["proximo"], "triagem humana")

class TestFontes(Base):
    def test_adaptador_somente_leitura(self):
        with self.assertRaises(LookupError): agentes.consultar_fonte("fonte_inexistente", "x")
        r = agentes.consultar_fonte("fonte_stj", "prescricao intercorrente", 3)  # sem skip: falha alta se o acervo nao abrir
        self.assertEqual(r["verificacao"], "nao_conferido")
        self.assertGreater(r["total"], 0, "acervo STJ precisa devolver resultados reais")
        self.assertTrue(r["portal_oficial"].startswith("https://"))
        self.assertTrue(all(x["verificacao"] == "nao_conferido" for x in r["resultados"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
