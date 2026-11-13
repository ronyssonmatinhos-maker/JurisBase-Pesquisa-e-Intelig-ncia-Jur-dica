"""Auditor de precedentes em 4 niveis (skill_marcos_e_precedentes v1.0). Somente leitura.

Estados: NAO_CONFERIDO < LOCALIZADO_OFICIAL < DOCUMENTO_VERIFICADO < ANALISE_PRELIMINAR.
CONFERIDO_OFICIAL nunca e produzido aqui: so o advogado, por ato expresso (robo.conferir_oficial).
Falha de acesso ou busca sem resultado NUNCA prova inexistencia nem verificacao.
"""
from __future__ import annotations
import hashlib, re, socket, ssl
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler

HOSTS_OFICIAIS = (".jus.br", ".gov.br", ".leg.br", ".mp.br", ".def.br")
ESTADOS = ["NAO_CONFERIDO", "LOCALIZADO_OFICIAL", "DOCUMENTO_VERIFICADO", "ANALISE_PRELIMINAR"]
# tribunal -> sufixos de host esperados
HOST_TRIBUNAL = {"STF": ("stf.jus.br",), "STJ": ("stj.jus.br",), "TST": ("tst.jus.br",), "TSE": ("tse.jus.br",),
                 "TJPR": ("tjpr.jus.br",), "TRF4": ("trf4.jus.br",), "TRT9": ("trt9.jus.br",),
                 "TRF1": ("trf1.jus.br",), "TRF2": ("trf2.jus.br",), "TRF3": ("trf3.jus.br",), "TRF5": ("trf5.jus.br",),
                 "TJSP": ("tjsp.jus.br",), "TJSC": ("tjsc.jus.br",), "TJRS": ("tjrs.jus.br",), "TCU": ("tcu.gov.br",)}
# (J, TR) do numero CNJ -> tribunal
CNJ_TRIBUNAL = {("1", "00"): "STF", ("3", "00"): "STJ", ("5", "00"): "TST", ("8", "16"): "TJPR", ("4", "04"): "TRF4",
                ("5", "09"): "TRT9", ("4", "01"): "TRF1", ("4", "02"): "TRF2", ("4", "03"): "TRF3", ("4", "05"): "TRF5",
                ("8", "26"): "TJSP", ("8", "24"): "TJSC", ("8", "21"): "TJRS"}
OBRIG = ["tribunal", "orgao_julgador", "processo", "relator", "data_julgamento", "url"]
CLASSES_VINCULANTES = ("repetitivo", "repercussao geral", "sumula vinculante", "recurso repetitivo", "irdr", "iac")


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")


def cnj_valido(proc: str):
    m = re.fullmatch(r"(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})", (proc or "").strip())
    if not m:
        return None
    n, dd, aaaa, j, tr, oooo = m.groups()
    return (98 - int(n + aaaa + j + tr + oooo + "00") % 97) == int(dd)


def url_oficial(url: str) -> bool:
    try:
        p = urlparse(url or "")
    except Exception:
        return False
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host.endswith(h) for h in HOSTS_OFICIAIS)


def _host_bate_tribunal(url: str, tribunal: str):
    esperados = HOST_TRIBUNAL.get(str(tribunal or "").upper().replace(" ", ""))
    if not esperados:
        return None  # tribunal sem mapa: nao afirma nada
    host = (urlparse(url or "").hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in esperados)


def n1_formal(c: dict) -> list[str]:
    """Plausibilidade formal. NAO comprova existencia."""
    prob = []
    falta = [k for k in OBRIG if not str(c.get(k, "")).strip()]
    if falta:
        prob.append("campos ausentes: " + ", ".join(falta))
    if c.get("url") and not url_oficial(c["url"]):
        prob.append("url nao oficial")
    elif c.get("url") and _host_bate_tribunal(c["url"], c.get("tribunal")) is False:
        prob.append("dominio da url nao corresponde ao tribunal citado")
    v = cnj_valido(c.get("processo", ""))
    if v is False:
        prob.append("numero CNJ com digito verificador invalido (possivel citacao ficticia)")
    elif v:
        m = re.search(r"\.(\d)\.(\d{2})\.", c["processo"])
        t = CNJ_TRIBUNAL.get((m.group(1), m.group(2))) if m else None
        trib = str(c.get("tribunal", "")).upper().replace(" ", "")
        if t and trib and t != trib and not (t == "TJPR" and trib in ("TJ/PR", "TJPR")):
            prob.append(f"segmentos J.TR do numero CNJ indicam {t}, mas a citacao aponta {c.get('tribunal')}")
    txt = _norm(" ".join(str(x) for x in c.values()))
    if "jurisbase" in txt or "segundo o acervo" in txt or "a ia " in txt:
        prob.append("o app/IA nao pode ser citado como fundamento")
    return prob


# ---------- conectores de consulta (somente leitura) ----------
class _SemRedirectForaDoHost(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if (urlparse(newurl).hostname or "") != (urlparse(req.full_url).hostname or ""):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def conector_http(url: str, timeout: float = 10.0, limite_bytes: int = 5_000_000, opener=None) -> dict:
    """GET somente leitura em URL oficial https. Sem cookies, sem login, sem contornar protecoes.
    Devolve registro de consulta; falha de acesso e explicita (acessivel=False)."""
    reg = {"consulta": url, "fonte": urlparse(url).hostname, "momento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "acessivel": False, "status_http": None, "erro": None, "sha256_local": None, "bytes": 0, "content_type": None}
    if not url_oficial(url):
        reg["erro"] = "url fora da allowlist oficial (https + .jus.br/.gov.br/.leg.br/.mp.br/.def.br)"
        return reg
    op = opener or build_opener(_SemRedirectForaDoHost(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        with op.open(Request(url, headers={"User-Agent": "JurisBase-auditor-readonly/1.0"}, method="GET"), timeout=timeout) as r:
            dados = r.read(limite_bytes + 1)
            reg["status_http"] = getattr(r, "status", None) or r.getcode()
            reg["content_type"] = r.headers.get("Content-Type")
    except Exception as e:  # inclui 403/404/captcha/timeouts: nunca contorna
        reg["erro"] = f"{type(e).__name__}: {e}"[:200]
        reg["status_http"] = getattr(e, "code", None)
        return reg
    if len(dados) > limite_bytes:
        reg["erro"] = "resposta acima do limite; nao processada"
        return reg
    reg.update(acessivel=True, bytes=len(dados), sha256_local=hashlib.sha256(dados).hexdigest())
    return reg


def auditar_niveis(c: dict, evidencias: dict | None = None, conector=None) -> dict:
    """Avalia uma citacao nos 4 niveis. evidencias (opcional) traz resultados ja obtidos pelo operador:
       n2: {acessivel, encontrado, url_canonica, processo_encontrado, consulta, fonte, momento_utc, erro}
       n3: {obtido_do_tribunal, verificador_assinatura(True/False/None), url, sha256_local}
       n4: {natureza(colegiado|monocratica), classe_real, tese_confere(True/False/None), trechos[{pagina,texto}],
            ratio_obiter, superado(True/False/None), divergencias[], confianca}
       conector: callable(citacao)->dict no formato de n2 (opcional; senao usa evidencias['n2'])."""
    ev = evidencias or {}
    niveis, estado, bloq = {}, "NAO_CONFERIDO", False
    p1 = n1_formal(c)
    niveis["N1_formal"] = {"ok": not p1, "problemas": p1, "aviso": "plausibilidade formal; nao comprova existencia"}
    bloq = bool(p1)

    # N2 existencia
    n2 = ev.get("n2")
    if n2 is None and conector and not bloq:
        try:
            n2 = conector(c)
        except Exception as e:
            n2 = {"acessivel": False, "erro": f"{type(e).__name__}: {e}"[:200]}
    if n2 is None:
        niveis["N2_existencia"] = {"executado": False, "resultado": "nao_executado"}
        bloq = True
    else:
        pr2 = []
        if not n2.get("acessivel"):
            res = "falha_acesso: nada foi verificado"
            pr2.append("portal indisponivel/inacessivel; nao afirmar verificacao")
        elif not n2.get("encontrado"):
            res = "nao_localizado: busca sem resultado nao prova inexistencia"
            pr2.append("nao localizado no portal oficial (isso nao prova inexistencia)")
        else:
            res = "localizado"
            if not url_oficial(n2.get("url_canonica", "")):
                pr2.append("url canonica ausente ou nao oficial")
            elif _host_bate_tribunal(n2["url_canonica"], c.get("tribunal")) is False:
                pr2.append("url canonica nao corresponde ao tribunal")
            if _norm(n2.get("processo_encontrado", "")) != _norm(c.get("processo", "")):
                pr2.append("identificador encontrado diverge do citado")
        niveis["N2_existencia"] = {"executado": True, "resultado": res, "problemas": pr2,
                                   "registro": {k: n2.get(k) for k in ("consulta", "fonte", "momento_utc", "erro", "url_canonica")}}
        if pr2 or bloq:
            bloq = True
        else:
            estado = "LOCALIZADO_OFICIAL"

    # N3 autenticidade
    n3 = ev.get("n3")
    if n3 is None or bloq:
        niveis["N3_autenticidade"] = {"executado": False, "estado": "autenticidade_pendente"}
        bloq = True
    else:
        pr3 = []
        if not n3.get("obtido_do_tribunal"):
            pr3.append("documento nao obtido diretamente do tribunal")
        if n3.get("verificador_assinatura") is not True:
            pr3.append("sem verificador/assinatura conferido: PDF em dominio oficial isolado nao prova autenticidade")
        if not re.fullmatch(r"[0-9a-f]{64}", str(n3.get("sha256_local", ""))):
            pr3.append("hash SHA256 local nao registrado")
        niveis["N3_autenticidade"] = {"executado": True, "estado": "autenticidade_pendente" if pr3 else "documento_verificado", "problemas": pr3}
        if pr3:
            bloq = True
        else:
            estado = "DOCUMENTO_VERIFICADO"

    # N4 aderencia
    n4 = ev.get("n4")
    if n4 is None or bloq:
        niveis["N4_aderencia"] = {"executado": False}
    else:
        pr4 = []
        if not n4.get("trechos"):
            pr4.append("sem trechos/paginas do inteiro teor: nao inferir tese de ementa isolada")
        if n4.get("tese_confere") is not True:
            pr4.append("tese atribuida nao confirmada pelo inteiro teor")
        if n4.get("divergencias"):
            pr4.append("divergencias entre proposicao atribuida e inteiro teor: " + "; ".join(map(str, n4["divergencias"]))[:300])
        attr = _norm(c.get("classificacao_atribuida", ""))
        if any(k in attr for k in CLASSES_VINCULANTES) and _norm(n4.get("natureza")) == "monocratica":
            pr4.append("decisao monocratica citada como precedente vinculante/repetitivo")
        if n4.get("superado") is True:
            pr4.append("precedente superado/revogado")
        elif n4.get("superado") is None:
            pr4.append("vigencia/superacao nao verificada")
        if _norm(n4.get("ratio_obiter")) in ("obiter", "voto_vencido", "voto vencido"):
            pr4.append("trecho e obiter dictum ou voto vencido, nao ratio decidendi")
        niveis["N4_aderencia"] = {"executado": True, "problemas": pr4, "confianca": n4.get("confianca", "nao_informada")}
        if not pr4:
            estado = "ANALISE_PRELIMINAR"
    return {"citacao": c.get("processo") or c.get("referencia") or "(sem identificacao)", "estado": estado, "niveis": niveis,
            "pode_constar_na_minuta": False, "conferido_oficial": False,
            "regra": "ate ato expresso do advogado nenhum estado autoriza CONFERIDO_OFICIAL nem inclusao automatica em minuta"}
