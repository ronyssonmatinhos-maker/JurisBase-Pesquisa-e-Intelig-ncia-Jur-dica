# -*- coding: utf-8 -*-
"""Regressao A01-A06 + R01-R12 (skill_marcos_e_precedentes v1.0). Somente dados SINTETICOS."""
import hashlib, os, sys, unittest, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agentes, auditor_oficial as ao, marcos as mc, robo
from test_agentes import Base, cnj


def M(tipo, data, cert="documental", efeito="registrado", credito=None, **kw):
    d = {"tipo": tipo, "data": data, "fonte": "doc-sintetico", "certeza": cert, "efeito": efeito}
    if credito: d["credito"] = credito
    d.update(kw); return d


def marcos_ok(credito=None):
    return [M("constituicao_definitiva", "10/01/2015", credito=credito, natureza="nao_tributario", prazo_anos=5),
            M("ajuizamento", "01/02/2016", credito=credito), M("despacho_citatorio", "10/02/2016", credito=credito),
            M("ciencia_fazenda_nao_localizacao", "01/03/2017", credito=credito),
            M("suspensao_art40_inicio", "02/03/2017", credito=credito), M("suspensao_art40_fim", "02/03/2018", credito=credito),
            M("intimacao_contraditorio", "01/05/2023", credito=credito)]


CASO = "execucao fiscal com alegacao de prescricao intercorrente"
def pc(marcos=None, caso=CASO, conf=None): return agentes.pre_condicoes("execucao_fiscal", caso, marcos, conf)


class TestMarcosP1(Base):
    def test_R01_tres_datas_irrelevantes(self):
        self.assertFalse(pc(None, CASO + " 01/01/2020 02/02/2021 03/03/2022")["pode_concluir"])
        irrel = [M("requerimento_infrutifero", d) for d in ("01/01/2020", "02/02/2021", "03/03/2022")]
        r = pc(irrel); self.assertFalse(r["pode_concluir"]); self.assertTrue(any("falta marco essencial" in x for x in r["lacunas"]))
    def test_R02_cronologia_contraditoria(self):
        m = marcos_ok(); m[1]["data"] = "01/02/2014"   # ajuizamento antes da constituicao
        r = pc(m); self.assertFalse(r["pode_concluir"]); self.assertTrue(any("cronologia contraditoria" in x for x in r["marcos"]["contradicoes"]))
    def test_R02b_data_invalida_e_duplicidade(self):
        m = marcos_ok(); m[0]["data"] = "31/02/2015"
        self.assertTrue(any("data ausente ou invalida" in x for x in pc(m)["lacunas"]))
        m = marcos_ok() + [M("ajuizamento", "05/05/2016")]
        self.assertTrue(any("datas conflitantes" in x for x in pc(m)["marcos"]["contradicoes"]))
    def test_R03_requerimento_infrutifero_vs_constricao(self):
        m = marcos_ok() + [M("requerimento_infrutifero", "01/06/2017", efeito="interrompe a prescricao")]
        r = pc(m); self.assertFalse(r["pode_concluir"])
        self.assertTrue(any("requerimento infrutifero" in x for x in r["marcos"]["contradicoes"]))
        m = marcos_ok() + [M("requerimento_infrutifero", "01/06/2017")]
        self.assertTrue(any("nao interrompem" in x for x in pc(m)["avisos"]))
        m = marcos_ok() + [M("constricao_efetiva", None)]
        self.assertTrue(any("sem data" in x for x in pc(m)["lacunas"]))
    def test_R04_sem_ciencia_da_fazenda(self):
        m = [x for x in marcos_ok() if x["tipo"] != "ciencia_fazenda_nao_localizacao"]
        r = pc(m); self.assertFalse(r["pode_concluir"]); self.assertTrue(any("ciencia da Fazenda" in x for x in r["lacunas"]))
    def test_R05_varios_creditos_prazos_distintos(self):
        a, b = marcos_ok("A"), [x for x in marcos_ok("B") if x["tipo"] != "constituicao_definitiva"]
        r = pc(a + b); self.assertFalse(r["pode_concluir"]); self.assertTrue(any("credito B" in x for x in r["lacunas"]))
        r = pc(marcos_ok(), caso=CASO + " em varias CDAs"); self.assertTrue(any("varios creditos" in x for x in r["lacunas"]))
        c = marcos_ok("A"); c[0]["prazo_anos"] = 5; c.append(M("causa_suspensao_interrupcao", "01/01/2016", credito="A", prazo_anos=10))
        self.assertTrue(any("prazos prescricionais divergentes" in x for x in pc(c)["marcos"]["contradicoes"]))
    def test_contraditorio_obrigatorio(self):
        m = [x for x in marcos_ok() if x["tipo"] != "intimacao_contraditorio"]
        self.assertTrue(any("contraditorio" in x or "par. 4" in x for x in pc(m)["lacunas"]))
    def test_certeza_nao_documental_so_condicional(self):
        m = marcos_ok(); m[3]["certeza"] = "alegado"
        r = pc(m, conf={"tema_566_conferido_pelo_advogado": True})
        self.assertTrue(any("conclusao apenas condicional" in x for x in r["avisos"]))
    def test_completo_exige_conferencia_do_advogado(self):
        r = pc(marcos_ok()); self.assertFalse(r["pode_concluir"]); self.assertEqual(r["marcos"]["status"], "ANALISE_ESTRUTURADA_COMPLETA")
        self.assertTrue(any("Tema 566" in x for x in r["lacunas"] + r["avisos"]))
        r = pc(marcos_ok(), conf={"tema_566_conferido_pelo_advogado": True}); self.assertTrue(r["pode_concluir"])
    def test_tema_566_nao_conferido(self):
        self.assertTrue(any("NAO_CONFERIDO" in x and "REsp 1.340.553/RS" in x for x in pc(marcos_ok())["avisos"]))
    def test_originaria_x_intercorrente(self):
        r = pc(None, caso="execucao fiscal com prescricao")
        self.assertTrue(any("nao confundir" in x for x in r["avisos"]))


class TestAuditorP2(Base):
    def cit(self, **k):
        d = {"tribunal": "TJPR", "orgao_julgador": "1a Camara", "relator": "Des. Sintetico", "data_julgamento": "01/01/2020",
             "processo": cnj(1234567, 2019, 8, 16, "0001"), "url": "https://www.tjpr.jus.br/x"}
        d.update(k); return d
    N2 = lambda self, c=None, **k: {**{"acessivel": True, "encontrado": True, "url_canonica": "https://www.tjpr.jus.br/doc",
                                       "processo_encontrado": (c or self.cit())["processo"], "consulta": "consulta-sintetica",
                                       "fonte": "www.tjpr.jus.br", "momento_utc": "2026-11-13T00:00:00+00:00"}, **k}
    N3 = {"obtido_do_tribunal": True, "verificador_assinatura": True, "sha256_local": "a" * 64}
    N4 = {"natureza": "colegiado", "tese_confere": True, "superado": False, "ratio_obiter": "ratio",
          "trechos": [{"pagina": 3, "texto": "trecho curto sintetico"}], "divergencias": [], "confianca": "media"}
    def aud(self, c=None, **ev): return ao.auditar_niveis(c or self.cit(), ev or None)

    def test_R06_cnj_valido_sem_registro_oficial(self):
        self.assertTrue(ao.cnj_valido(self.cit()["processo"]))
        r = self.aud(); self.assertEqual(r["estado"], "NAO_CONFERIDO")
        r = self.aud(n2=self.N2(encontrado=False)); self.assertEqual(r["estado"], "NAO_CONFERIDO")
        self.assertIn("nao prova inexistencia", r["niveis"]["N2_existencia"]["resultado"])
    def test_R07_url_oficial_sem_documento_verificavel(self):
        c = self.cit(); self.assertTrue(ao.url_oficial(c["url"]))
        self.assertEqual(self.aud(c, n2=self.N2(c), n3={"obtido_do_tribunal": True, "verificador_assinatura": None, "sha256_local": "b" * 64})["estado"], "LOCALIZADO_OFICIAL")
        r = self.aud(self.cit(url="https://www.tjpr.jus.br.falso.com/x")); self.assertIn("url nao oficial", r["niveis"]["N1_formal"]["problemas"])
        r = self.aud(self.cit(url="https://www.stj.jus.br/x")); self.assertTrue(any("nao corresponde ao tribunal" in p for p in r["niveis"]["N1_formal"]["problemas"]))
    def test_R08_inteiro_teor_contraria_tese(self):
        c = self.cit(); r = self.aud(c, n2=self.N2(c), n3=self.N3, n4={**self.N4, "tese_confere": False, "divergencias": ["inteiro teor afirma o oposto"]})
        self.assertEqual(r["estado"], "DOCUMENTO_VERIFICADO"); self.assertTrue(r["niveis"]["N4_aderencia"]["problemas"])
        r = self.aud(c, n2=self.N2(c), n3=self.N3, n4={**self.N4, "trechos": []}); self.assertNotEqual(r["estado"], "ANALISE_PRELIMINAR")
    def test_R09_monocratica_como_repetitivo(self):
        c = self.cit(classificacao_atribuida="recurso repetitivo")
        r = self.aud(c, n2=self.N2(c), n3=self.N3, n4={**self.N4, "natureza": "monocratica"})
        self.assertTrue(any("monocratica" in p for p in r["niveis"]["N4_aderencia"]["problemas"])); self.assertNotEqual(r["estado"], "ANALISE_PRELIMINAR")
    def test_R10_precedente_superado(self):
        c = self.cit(); r = self.aud(c, n2=self.N2(c), n3=self.N3, n4={**self.N4, "superado": True}); self.assertNotEqual(r["estado"], "ANALISE_PRELIMINAR")
        r = self.aud(c, n2=self.N2(c), n3=self.N3, n4={**self.N4, "superado": None}); self.assertNotEqual(r["estado"], "ANALISE_PRELIMINAR")
        r = self.aud(c, n2=self.N2(c), n3=self.N3, n4={**self.N4, "ratio_obiter": "obiter"}); self.assertNotEqual(r["estado"], "ANALISE_PRELIMINAR")
    def test_R11_portal_indisponivel(self):
        c = self.cit()
        class Falha:
            def open(self, *a, **k): raise OSError("rede indisponivel (sintetico)")
        reg = ao.conector_http(c["url"], opener=Falha())
        self.assertFalse(reg["acessivel"]); self.assertIn("OSError", reg["erro"])
        r = ao.auditar_niveis(c, None, conector=lambda x: ao.conector_http(x["url"], opener=Falha()))
        self.assertEqual(r["estado"], "NAO_CONFERIDO"); self.assertIn("nada foi verificado", r["niveis"]["N2_existencia"]["resultado"])
        r = ao.auditar_niveis(c, None, conector=lambda x: (_ for _ in ()).throw(TimeoutError("t")))
        self.assertEqual(r["estado"], "NAO_CONFERIDO")
        self.assertFalse(ao.conector_http("https://www.exemplo.com/x")["acessivel"])   # fora da allowlist
        self.assertFalse(ao.conector_http("http://www.tjpr.jus.br/x")["acessivel"])    # http recusado
    def test_conector_http_registra_hash(self):
        class Resp:
            status = 200; headers = {"Content-Type": "application/pdf"}
            def read(self, n): return b"conteudo sintetico"
            def getcode(self): return 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        class Op:
            def open(self, *a, **k): return Resp()
        reg = ao.conector_http("https://www.tjpr.jus.br/x", opener=Op())
        self.assertTrue(reg["acessivel"]); self.assertEqual(reg["sha256_local"], hashlib.sha256(b"conteudo sintetico").hexdigest())
    def test_documento_sem_verificador_e_sem_hash(self):
        c = self.cit(); r = self.aud(c, n2=self.N2(c), n3={"obtido_do_tribunal": True, "verificador_assinatura": True, "sha256_local": ""})
        self.assertEqual(r["estado"], "LOCALIZADO_OFICIAL")
        r = self.aud(c, n2=self.N2(c), n3={**self.N3, "obtido_do_tribunal": False}); self.assertEqual(r["estado"], "LOCALIZADO_OFICIAL")
    def test_resultado_portal_sem_inteiro_teor(self):
        c = self.cit(); r = self.aud(c, n2=self.N2(c)); self.assertEqual(r["estado"], "LOCALIZADO_OFICIAL")
        self.assertFalse(r["niveis"]["N3_autenticidade"]["executado"])
    def test_identificador_divergente_e_cnj_tribunal(self):
        c = self.cit(); r = self.aud(c, n2=self.N2(c, processo_encontrado="9999999-00.2000.8.16.0001")); self.assertEqual(r["estado"], "NAO_CONFERIDO")
        r = self.aud(self.cit(tribunal="STJ", url="https://www.stj.jus.br/x")); self.assertTrue(any("segmentos J.TR" in p for p in r["niveis"]["N1_formal"]["problemas"]))
        r = self.aud(self.cit(processo="1234567-00.2019.8.16.0001")); self.assertTrue(any("invalido" in p for p in r["niveis"]["N1_formal"]["problemas"]))
    def test_nunca_conferido_oficial_nem_minuta(self):
        c = self.cit(); r = self.aud(c, n2=self.N2(c), n3=self.N3, n4=self.N4)
        self.assertEqual(r["estado"], "ANALISE_PRELIMINAR"); self.assertFalse(r["pode_constar_na_minuta"]); self.assertFalse(r["conferido_oficial"])
        a = agentes.auditar_citacoes([c], [{"n2": self.N2(c), "n3": self.N3, "n4": self.N4}])["auditoria"][0]
        self.assertEqual(a["status"], "NAO_CONFERIDO"); self.assertFalse(a["pode_constar_na_minuta"]); self.assertIn("NAO e prova", a["aviso_apto"])
        for e in ao.ESTADOS: self.assertNotEqual(e, "CONFERIDO_OFICIAL")


class TestDadosA02A03A06(Base):
    def test_R12_interno_vs_externo(self):
        caso = "Maria Souza Lima, CPF 111.222.333-96, processo 0001234-55.2019.8.16.0001, execucao fiscal prescricao intercorrente art. 40 Lei 6.830/80"
        p = agentes.preparar("execucao_fiscal", caso)
        self.assertNotIn("sanitizado_complementar", p)
        self.assertEqual(p["interno"]["uso"], "INTERNO_NUNCA_EXTERNO")
        self.assertEqual(p["contrato_externo"]["unico_campo_permitido"], "termo_externo")
        for sensivel in ("Maria", "Souza", "111.222", "0001234"):
            self.assertNotIn(sensivel, p["termo_externo"])
        recebido = []
        agentes.consulta_externa(p["termo_externo"], lambda t: recebido.append(t))
        self.assertEqual(recebido, [p["termo_externo"]])
        with self.assertRaises(PermissionError): agentes.consulta_externa(caso, lambda t: recebido.append(t))
        with self.assertRaises(PermissionError): agentes.consulta_externa("Maria Souza CPF 111.222.333-96", lambda t: None)
        self.assertEqual(len(recebido), 1)
    def test_A03_termo_generico_limites(self):
        t = agentes.termo_generico("execucao fiscal art. 123456789 art. 40 tema 12345678 lei 12345678901234 sumula 99999", "execucao_fiscal")
        self.assertNotIn("123456789", t); self.assertIn("art. 40", t)
        self.assertLessEqual(len(t), 200)
        ruido = " ".join(f"art. {i}" for i in range(1, 60)) + " execucao fiscal"
        self.assertLessEqual(len(agentes.termo_generico(ruido, "execucao_fiscal").split(" art.")), 13)
        for ruim in ("111.222.333-96", "a@b.com", "x;DROP TABLE", "<script>"):
            self.assertFalse(agentes.validar_termo_externo(ruim)[0], ruim)
        self.assertTrue(agentes.validar_termo_externo("execucao fiscal art. 40 Lei 6.830/80")[0])
    def test_A06_nao_escrita_ampla(self):
        raiz = Path(agentes.HERE)
        alvos = [p for p in list((raiz / "data").rglob("*")) + [Path(os.environ.get("ROBO_JULGADOS_DB", ""))] if p.is_file() and p.suffix in (".db", ".json", ".log", ".sqlite")]
        alvos += [p for p in (raiz.parent / "julgados" / "base").glob("*.db")] if (raiz.parent / "julgados" / "base").exists() else []
        def snap(): return {str(p): (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest() if p.stat().st_size < 50_000_000 else p.stat().st_mtime_ns) for p in set(alvos)}
        antes = snap()
        for a in [{"acao": "agentes"}, {"acao": "rotear", "texto": "execucao fiscal prescricao"},
                  {"acao": "preparar_agente", "agente": "execucao_fiscal", "caso": "prescricao", "marcos": marcos_ok()},
                  {"acao": "auditar_citacoes", "citacoes": [{"tribunal": "TJPR", "processo": "x"}]},
                  {"acao": "fluxo_agentes", "caso": "execucao fiscal prescricao"},
                  {"acao": "consultar_agente", "agente": "execucao_fiscal", "termo": "prescricao"}, {"acao": "cobertura_fontes"}]:
            robo.comando(a)
        self.assertEqual(antes, snap(), "nenhum arquivo de dados/acervo pode mudar")
        self.assertGreater(len(antes), 0)
    def test_gravar_continua_bloqueado(self):
        with self.assertRaises(Exception): robo.comando({"acao": "gravar_achado", "achado": {"tese": "x"}})


class TestIntegracaoFichasConfig(Base):
    def test_skill_na_config_e_fichas(self):
        c = agentes.config()
        self.assertIn("skill_marcos_e_precedentes", c.get("approved_skills", []))
        self.assertIn("data_access_policy", c)
        for a in c["agents"]:
            self.assertIn("skill_marcos_e_precedentes", a.get("approved_skills", []), a["id"])
        self.assertEqual(len(c["agents"]), 20)
        fichas = list(agentes.FICHAS.glob("*.txt")); self.assertEqual(len(fichas), 33)
        for f in fichas:
            self.assertIn("skill_marcos_e_precedentes", f.read_text(encoding="utf-8"), f.name)


if __name__ == "__main__":
    unittest.main()
