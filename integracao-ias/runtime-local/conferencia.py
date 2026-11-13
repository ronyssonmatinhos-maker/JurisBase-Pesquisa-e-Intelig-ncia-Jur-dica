"""Agente conferidor_fontes_oficiais: confronta norma/tema com portal OFICIAL (somente leitura).

Nao marca CONFERIDO_OFICIAL (ato do advogado). Registra: fonte, URL canonica, momento, como foi obtido,
o que foi localizado e o que ficou pendente. 'via' informa se o portal foi lido pelo conector_http
(ao vivo) ou se o achado vem de busca em dominio oficial registrada em data anterior.
"""
from __future__ import annotations
import auditor_oficial as ao

CAPTURA = "2026-11-13"
ITENS = {
    "tema_1184_stf": {
        "titulo": "Tema 1184/STF - RE 1.355.208/SC (rel. Min. Carmen Lucia), repercussao geral",
        "orgao": "STF",
        "urls": ["https://portal.stf.jus.br/processos/detalhe.asp?incidente=6291425",
                 "https://portal.stf.jus.br/jurisprudenciaRepercussao/verAndamentoProcesso.asp?classeProcesso=RE&incidente=6291425&numeroProcesso=1355208&numeroTema=1184"],
        "achados": [
            "Tese 1: e legitima a extincao de execucao fiscal de baixo valor por ausencia de interesse de agir, pelo principio da eficiencia administrativa, respeitada a competencia de cada ente federado (portal STF, pagina do tema).",
            "Tese 2: o ajuizamento depende de previa tentativa de conciliacao ou solucao administrativa e de protesto do titulo, salvo motivo de eficiencia (texto truncado na captura; alineas completas pendentes).",
            "Embargos de declaracao acolhidos sem efeitos infringentes (sessao virtual de 12.4.2024; registro de 22/04/2024): a tese vale apenas para execucao fiscal de baixo valor, nos limites do Tema 1.184, inclusive execucoes suspensas por causa do tema.",
            "Julgamento de merito em Plenario em 19/12/2023 (conforme considerandos da Res. CNJ 547/2024)."],
        "marcadores": {"https://portal.stf.jus.br/processos/detalhe.asp?incidente=6291425": ["1184", "1355208", "CARMEN LUCIA"]},
        "pendencias": ["portal STF carrega andamentos/decisoes por script: texto da tese vem de busca em dominio oficial, nao da leitura ao vivo",
                       "ler inteiro teor do acordao e do acordao dos embargos (alineas da tese 2, regime temporal e conceito de baixo valor)",
                       "tese nao fixa valor numerico: o limite de R$ 10.000,00 vem da Res. CNJ 547/2024, nao do Tema"]},
    "res_cnj_547_2024": {
        "titulo": "Resolucao CNJ 547, de 22/02/2024 (alterada pelas Res. CNJ 617/2025 e 689/2026)",
        "orgao": "CNJ",
        "urls": ["https://atos.cnj.jus.br/atos/detalhar/5455", "https://atos.cnj.jus.br/atos/detalhar/6018"],
        "achados": [
            "Texto lido AO VIVO em atos.cnj.jus.br/atos/detalhar/5455 (situacao: Alterado; alteracoes pelas Res. 617/2025 e 689, de 8/7/2026).",
            "Art. 1, par. 1: extincao das execucoes fiscais de valor inferior a R$ 10.000,00 (no ajuizamento) sem movimentacao util ha mais de um ano sem citacao, ou, ainda que citado, sem bens penhoraveis.",
            "Par. 1-A (Res. 689/2026): movimentacoes uteis sao as do art. 921, par. 4-A, CPC (citacao efetiva, intimacao do devedor, constricao de bens). Par. 2: somam-se execucoes apensadas contra o mesmo executado. Pars. 3 e 4: nova propositura se achados bens e nao consumada a prescricao; termo inicial = um ano apos a ciencia da Fazenda da nao localizacao. Par. 5: Fazenda pode pedir ate 90 dias.",
            "Art. 1-A (Res. 617/2025): extincao tambem das execucoes sem CPF/CNPJ do executado. Art. 1-B (Res. 689/2026): intimacao do exequente em execucoes pendentes ha mais de 15 anos ou suspensas ha mais de 6 anos; sem manifestacao util, conclusos para exame da prescricao intercorrente (art. 921, pars. 1 a 5, CPC); extinta por prescricao, ficam vedadas outras medidas de cobranca do mesmo credito (par. 4), salvo parcela nao prescrita (par. 5).",
            "Considerandos da Res. 547 invocam o Tema 566/STJ, validado pelo Tema 390/STF, sobre o termo inicial da prescricao apos a propositura (relevante para a skill de marcos).",
            "Consulta CNJ 0002087-16.2024.2.00.0000: R$ 10.000,00 nao e piso de ajuizamento (busca em dominio oficial)."],
        "marcadores": {"https://atos.cnj.jus.br/atos/detalhar/5455": ["10.000,00", "movimentacao util ha mais de um ano", "Resolucao n. 689", "tema 566", "tema 390", "921"],
                       "https://atos.cnj.jus.br/atos/detalhar/6018": ["Art. 1º-A", "CPF ou CNPJ"]},
        "pendencias": ["Res. 689/2026 e muito recente: conferir vigencia, prazos de implementacao e regime de transicao no texto oficial",
                       "Tema 566/STJ x Tema 390/STF: ler inteiro teor (nao capturado)",
                       "conferir aplicabilidade a entes/conselhos e a execucoes de outros entes (competencia de cada ente)"]},
    "lei_14133_arts_190_191_193": {
        "titulo": "Lei 14.133/2021 - arts. 190, 191 e 193 (transicao e revogacao da Lei 8.666/93)",
        "orgao": "Planalto",
        "urls": ["https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm"],
        "leitura_navegador": {"momento_utc": "2026-11-13T10:54:40Z", "ferramenta": "Playwright (navegador real do PC; acesso direto por script foi recusado pelo Planalto e nao foi contornado)",
                              "url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm"},
        "achados": [
            "Art. 190 (lido): contrato com instrumento assinado antes da vigencia da Lei continua regido pelas regras da legislacao revogada.",
            "Art. 191, caput (lido): ate o prazo do art. 193, II, a Administracao pode optar pela Lei ou pelas leis anteriores; a opcao deve constar expressamente do edital/aviso/instrumento; e vedada a aplicacao combinada.",
            "Art. 191, par. unico (lido): se optou pelas leis anteriores, o contrato e regido por elas durante toda a vigencia; o texto aparece marcado como 'Revogado pela MPV 1.167/2023 - Vigencia encerrada' (a marcacao indica que essa revogacao perdeu vigencia; efeito exato a conferir).",
            "Art. 193, II (lido): redacao original = 2 anos da publicacao; redacao da MPV 1.167/2023 = 30/12/2023 (vigencia encerrada); redacao da LC 198/2023 = em 30 de dezembro de 2023 (Lei 8.666/93, Lei 10.520/2002 e arts. 1 a 47-A da Lei 12.462/2011).",
            "Art. 193, I (lido): arts. 89 a 108 da Lei 8.666/93 revogados na data de publicacao da Lei 14.133."],
        "pendencias": ["interpretar o status do par. unico do art. 191 (marcacao 'vigencia encerrada' da MPV 1.167/2023) no texto oficial e na legislacao correlata",
                       "conferir regulamentos vinculados (Decreto 12.174/2024, 12.343/2024, 12.807/2025) apenas se o caso exigir",
                       "conferir quais leis anteriores o caso concreto invoca e a data de assinatura do contrato"]},
}


def _plano(html_: str) -> str:
    import html, re
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_, flags=re.S)
    return re.sub(r"\s+", " ", ao._norm(html.unescape(re.sub(r"<[^>]+>", " ", t))))


def listar() -> dict:
    return {"agente": "conferidor_fontes_oficiais", "itens": {k: v["titulo"] for k, v in ITENS.items()}}


def conferir(item_id: str, conector=None) -> dict:
    if item_id not in ITENS:
        raise LookupError("item desconhecido: " + item_id)
    it = ITENS[item_id]
    conector = conector or (lambda url: ao.conector_http(url, timeout=40, capturar_texto=True))
    consultas, vivo = [], False
    for u in it["urls"]:
        try:
            r = conector(u)
        except Exception as e:
            r = {"consulta": u, "acessivel": False, "erro": f"{type(e).__name__}: {e}"[:200]}
        vivo = vivo or bool(r.get("acessivel") and (r.get("status_http") in (200, None)))
        c = {k: r.get(k) for k in ("consulta", "fonte", "momento_utc", "acessivel", "status_http", "erro", "bytes", "sha256_local")}
        marc = it.get("marcadores", {}).get(u)
        if marc and r.get("texto"):
            t = _plano(r["texto"])
            c["marcadores_encontrados"] = [m for m in marc if ao._norm(m) in t]
            c["marcadores_ausentes"] = [m for m in marc if ao._norm(m) not in t]
        consultas.append(c)
    return {"agente": "conferidor_fontes_oficiais", "item": item_id, "titulo": it["titulo"], "orgao": it["orgao"],
            "estado": "LOCALIZADO_OFICIAL",
            "via": "conector_http_ao_vivo" if vivo else ("navegador_playwright_ao_vivo_" + it["leitura_navegador"]["momento_utc"] if it.get("leitura_navegador") else f"busca_em_dominio_oficial_{CAPTURA}"),
            "leitura_navegador": it.get("leitura_navegador"),
            "consultas_ao_vivo": consultas, "achados": it["achados"], "pendencias": it["pendencias"],
            "inteiro_teor_obtido": False, "conferido_oficial": False, "pode_constar_na_minuta": False,
            "regra": "LOCALIZADO_OFICIAL nao e CONFERIDO_OFICIAL: so o advogado confere, apos ler o texto/inteiro teor na fonte"}


def conferir_todos(conector=None) -> dict:
    return {"conferencias": [conferir(k, conector) for k in ITENS]}
