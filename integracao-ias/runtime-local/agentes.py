# -*- coding: utf-8 -*-
"""Camada de agentes juridicos do JurisBase (runtime local).

JurisBase e ferramenta de localizacao, nunca fonte juridica. Este modulo:
  - carrega a configuracao dos agentes (config/agentes/config-agentes.json);
  - roteia o caso (coordenador) por termos, com limites de palavra;
  - sanitiza texto antes de qualquer pesquisa externa;
  - aplica pre-condicoes por especialidade (lacunas que impedem concluir);
  - audita citacoes (auditor_citacoes): nunca marca como conferido;
  - nao escreve nada: gravacao continua exigindo confirmacao no robo.py.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CFG_DIR = HERE / "config" / "agentes"
CFG_FILE = CFG_DIR / "config-agentes.json"
FICHAS = CFG_DIR / "fichas"

HOSTS_OFICIAIS = (".jus.br", ".gov.br", ".leg.br", ".mp.br", ".def.br")
# adaptadores de fonte: somente leitura, apontam para filtros do buscar()
FONTES = {
    "fonte_stf": "STF", "fonte_stj": "STJ", "fonte_tst_trt9": "TRT9",
    "fonte_tjpr": "TJPR", "fonte_tse_eleitoral": "TSE",
    "fonte_federal_trf4_tru4": "TRF4", "fonte_tribunais_contas": "TCE",
    "fonte_legislacao": "", "fonte_julgados_locais": "",
}


PORTAIS = {"fonte_stf": "https://portal.stf.jus.br", "fonte_stj": "https://www.stj.jus.br",
           "fonte_tst_trt9": "https://www.tst.jus.br", "fonte_tjpr": "https://www.tjpr.jus.br",
           "fonte_tse_eleitoral": "https://www.tse.jus.br", "fonte_federal_trf4_tru4": "https://www.trf4.jus.br",
           "fonte_tribunais_contas": "https://www.tce.pr.gov.br", "fonte_legislacao": "https://www.planalto.gov.br"}
LOCAL_COM_BASE = {"fonte_tjpr", "fonte_julgados_locais", "fonte_legislacao"}  # acervo local: TJPR, DJEN, Escritorio


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _tem(termo: str, texto: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(norm(termo)) + r"(?!\w)", norm(texto)) is not None


def config() -> dict:
    return json.loads(CFG_FILE.read_text(encoding="utf-8"))


def listar() -> dict:
    c = config()
    ag = [{"id": a["id"], "enabled": a.get("enabled", False), "gatilhos": a["trigger_terms"]}
          for a in c["agents"]]
    return {"especialistas": ag, "componentes": ["coordenador", "auditor_citacoes", "conferidor_fontes_oficiais"],
            "adaptadores_fonte": sorted(FONTES), "total_especialistas": len(ag),
            "habilitados": sum(1 for a in ag if a["enabled"])}


def rotear(texto: str) -> dict:
    """Coordenador: escolhe especialistas pelos gatilhos. Sem match -> triagem humana."""
    achados = []
    for a in config()["agents"]:
        if not a.get("enabled"):
            continue
        t = [x for x in a["trigger_terms"] if _tem(x, texto)]
        if t:
            achados.append({"agente": a["id"], "gatilhos": t})
    if not achados:
        return {"modo": "triagem_humana", "agentes": [], "motivo": "sem correspondencia"}
    if len(achados) == 1:
        return {"modo": "unico", "agentes": achados}
    return {"modo": "cooperacao_revisao_humana", "agentes": achados,
            "aviso": "mais de um especialista; mostrar divergencias, nao fundir conclusoes"}


# ---------- sanitizacao ----------
_PADROES = [
    ("processo_cnj", re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")),
    ("cnpj", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("oab", re.compile(r"\bOAB\s*/?\s*[A-Z]{2}\s*[\d.]+", re.I)),
    ("telefone", re.compile(r"(?<!\d)(?:\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}(?!\d)")),
    ("rg", re.compile(r"\b(?:rg|identidade)\s*(?:n[ºo.]*\s*)?\d[\d.\-]*[\dxX]?", re.I)),
    ("cep", re.compile(r"\b\d{5}-?\d{3}\b")),
    ("endereco", re.compile(r"\b(?:rua|avenida|av\.|travessa|alameda|rodovia|estrada)\s+[^,;\n]{2,60}(?:,\s*(?:n[ºo.]*\s*)?\d+)?", re.I)),
    ("matricula", re.compile(r"\bmatr[ií]cula\s*(?:n[ºo.]*\s*)?\d[\d.]*", re.I)),
]
_JURIDICO = {"tribunal", "supremo", "superior", "justica", "codigo", "processo", "civil", "penal",
             "lei", "constituicao", "federal", "estado", "estadual", "municipio", "municipal",
             "fazenda", "publica", "execucao", "fiscal", "regional", "trabalho", "eleitoral",
             "federativa", "republica", "nacional", "conselho", "ministerio", "tributario",
             "complementar", "emenda", "decreto", "resolucao", "sumula", "tema", "vara",
             "camara", "turma", "secao", "orgao", "especial", "contas", "uniao", "brasil",
             "paranagua", "matinhos", "parana", "curitiba"}
_LIGA = {"de", "da", "do", "dos", "das", "e"}
_NOME = re.compile(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+(?:de|da|do|dos|das|e)?\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)+")


_CAPS = re.compile(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:\s+(?:DE|DA|DO|DOS|DAS|E)?\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,})+\b")
_PAPEL = re.compile(r"\b(cliente|autor|autora|r[eé]u|r[eé]|requerente|requerid[oa]|executad[oa]|exequente|contribuinte|"
                    r"herdeir[oa]|falecid[oa]|esposa|marido|filh[oa]|s[oó]ci[oa]|vendedor[a]?|comprador[a]?|inventariante|sr\.?|sra\.?)"
                    r"\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+")


_MAX_TERMOS, _MAX_CHARS = 12, 200
_REGEX_LEGAIS = (r"\btema\s+\d{1,5}\b", r"\bs[uú]mula\s+(?:vinculante\s+)?\d{1,4}\b",
                 r"\bart(?:igo)?s?\.?\s*\d{1,4}(?:-[A-Z])?\b",
                 r"\blei\s+(?:complementar\s+)?(?:n[ºo.]*\s*)?\d{1,2}(?:\.\d{3})?(?:/\d{2,4})?\b")
_TERMO_OK = re.compile(r"[\w\s.\-/ºª§]+", re.U)


def validar_termo_externo(termo: str) -> tuple[bool, list[str]]:
    """Gate unico para consulta externa: so vocabulario juridico curto, sem identificadores pessoais."""
    motivos = []
    t = termo or ""
    if len(t) > _MAX_CHARS:
        motivos.append("termo acima do limite de tamanho")
    if t and not _TERMO_OK.fullmatch(t):
        motivos.append("caracteres nao permitidos")
    for tipo, rx in _PADROES:
        if rx.search(t):
            motivos.append("padrao de identificador pessoal: " + tipo)
    if len(t.split()) > 40:
        motivos.append("termo com texto livre demais")
    return (not motivos), motivos


def termo_generico(caso: str, agente: str | None = None) -> str:
    """Termo de pesquisa externa montado SO com vocabulario juridico (nunca com texto livre)."""
    termos: list[str] = []
    for a in config()["agents"]:
        if agente and a["id"] != agente:
            continue
        termos += [x for x in a["trigger_terms"] if _tem(x, caso)]
    for rx in _REGEX_LEGAIS:
        termos += [m.group(0) for m in re.finditer(rx, caso or "", re.I)]
    visto, out = set(), []
    for t in termos:
        k = norm(t)
        ok, _ = validar_termo_externo(t)
        if k not in visto and ok:
            visto.add(k); out.append(t)
    r = " ".join(out[:_MAX_TERMOS])[:_MAX_CHARS]
    return r if validar_termo_externo(r)[0] else ""


def consulta_externa(termo: str, conector) -> dict:
    """Unica porta de saida para pesquisa externa: valida o termo e so entao chama o conector."""
    ok, motivos = validar_termo_externo(termo)
    if not ok:
        raise PermissionError("termo externo reprovado: " + "; ".join(motivos))
    return conector(termo)


def sanitizar(texto: str, nomes: list[str] | None = None) -> dict:
    out = texto or ""
    removidos: list[dict] = []
    for n in sorted(nomes or [], key=len, reverse=True):
        if n and re.search(re.escape(n), out, re.I):
            out = re.sub(re.escape(n), "[NOME]", out, flags=re.I)
            removidos.append({"tipo": "nome_informado"})
    for tipo, rx in _PADROES:
        out, k = rx.subn("[" + tipo.upper() + "]", out)
        removidos += [{"tipo": tipo}] * k

    def _nome(m):
        toks = [t for t in re.split(r"\s+", m.group(0)) if t.lower() not in _LIGA]
        if any(norm(t) in _JURIDICO for t in toks):
            return m.group(0)
        removidos.append({"tipo": "possivel_nome"})
        return "[NOME]"
    out = _NOME.sub(_nome, out)
    out = _CAPS.sub(lambda m: m.group(0) if any(norm(t) in _JURIDICO for t in re.split(r"\s+", m.group(0))) or len(m.group(0)) < 8 else (removidos.append({"tipo": "possivel_nome"}) or "[NOME]"), out)
    out = _PAPEL.sub(lambda m: (removidos.append({"tipo": "nome_apos_papel"}) or m.group(1) + " [NOME]"), out)
    return {"texto_externo": out, "removidos": removidos, "sanitizado": bool(removidos),
            "registro": f"{len(removidos)} identificador(es) removido(s) antes de pesquisa externa"}


# ---------- pre-condicoes por especialidade ----------
_DATA = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")


def pre_condicoes(agente: str, caso: str, marcos: list | None = None, conferencias: dict | None = None) -> dict:
    t, lac, avis = norm(caso), [], []
    ok = True
    extra: dict = {}
    if agente == "execucao_fiscal":
        if "prescri" in t:
            import marcos as _mc
            av = _mc.avaliar_prescricao(t, marcos, conferencias)
            ok = av["pode_concluir"]
            lac += av["lacunas"]; avis += av["avisos"]
            extra = {"marcos": {k: av[k] for k in ("status", "contradicoes", "cronologia", "regra")}}
        if "1184" in t or "baixo valor" in t:
            avis.append("Tema 1184/STF: conferir tese, requisitos e Resolucao CNJ 547/2024 na fonte oficial; nao presumir extincao automatica")
            lac.append("valor do debito, ente exequente e eventual limite fixado")
            ok = False
    elif agente == "civil_processual":
        if "citacao" in t and ("contest" in t or "defesa" in t):
            ok = False
            lac += ["regime processual aplicavel (CPC) e data do ato", "houve comparecimento espontaneo?", "qual o prejuizo concreto alegado?"]
            avis.append("nao aplicar nulidade como regra absoluta")
    elif agente == "administrativo_licitacoes":
        if "contrato" in t and ("lei anterior" in t or "8.666" in t or "8666" in t or "14.133" in t):
            ok = False
            lac += ["data de celebracao do contrato", "ato de opcao pelo regime (art. 191), se licitado na convivencia normativa"]
            avis.append("verificar regime (Lei 8.666/93 ou 14.133/2021; arts. 190, 191, 193) e vigencia da MPV 1.167/2023 antes de aplicar")
    elif agente == "imobiliario_registral":
        if "possess" in t and ("coletiv" in t or "multidao" in t or "ocupacao" in t):
            ok = False
            lac += ["natureza da posse e do titulo", "fase do procedimento e eventual comissao/mediacao fundiaria"]
            avis.append("nao presumir perda da propriedade, desapropriacao ou acordo compulsorio; conferir resolucao do CNJ aplicavel")
    return {"agente": agente, "pode_concluir": ok, "lacunas": lac, "avisos": avis, **extra}


# ---------- auditor de citacoes ----------
def cnj_valido(proc: str) -> bool | None:
    m = re.fullmatch(r"(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})", (proc or "").strip())
    if not m:
        return None
    n, dd, aaaa, j, tr, oooo = m.groups()
    return (98 - int(n + aaaa + j + tr + oooo + "00") % 97) == int(dd)


def _url_oficial(url: str) -> bool:
    try:
        p = urlparse(url or "")
    except Exception:
        return False
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host.endswith(h) for h in HOSTS_OFICIAIS)


OBRIG = ["tribunal", "orgao_julgador", "processo", "relator", "data_julgamento", "url"]


def auditar_citacoes(citacoes: list[dict], evidencias: list | None = None) -> dict:
    """N1 formal sempre; N2-N4 somente com evidencias do operador. Nunca devolve conferido_oficial."""
    import auditor_oficial as ao
    res = []
    for i, c in enumerate(citacoes or []):
        ev = (evidencias or [None] * (i + 1))[i] if evidencias and i < len(evidencias) else None
        r = ao.auditar_niveis(c, ev)
        prob = r["niveis"]["N1_formal"]["problemas"]
        res.append({"citacao": r["citacao"], "status": "NAO_CONFERIDO", "estado": r["estado"],
                    "apto_para_conferencia_do_advogado": not prob,
                    "aviso_apto": "apto para conferencia NAO e prova de existencia nem de autenticidade",
                    "pode_constar_na_minuta": False, "problemas": prob, "niveis": r["niveis"]})
    return {"auditoria": res, "regra": "somente o advogado marca conferido_oficial; ate la, fora da minuta"}


def preparar(agente: str, caso: str = "", nomes: list[str] | None = None, marcos: list | None = None, conferencias: dict | None = None) -> dict:
    """Pacote para a IA operar um especialista (nao grava nada)."""
    c = config()
    a = next((x for x in c["agents"] if x["id"] == agente), None)
    if a is None:
        raise LookupError(f"Agente desconhecido: {agente}")
    if not a.get("enabled"):
        raise PermissionError(f"Agente {agente} desabilitado.")
    ficha = FICHAS / f"{agente}.txt"
    san = sanitizar(caso, nomes)
    return {"agente": agente, "instrucoes": a["system_instructions"], "saida": a["output_schema"],
            "ficha": ficha.read_text(encoding="utf-8") if ficha.exists() else "",
            "politica_fontes": a["source_policy"], "pre_condicoes": pre_condicoes(agente, caso, marcos, conferencias), "adaptadores": a.get("source_adapters", []),
            "termo_externo": termo_generico(caso, agente), "sanitizacao": san["registro"],
            "interno": {"sanitizado_complementar": san["texto_externo"], "uso": "INTERNO_NUNCA_EXTERNO"},
            "contrato_externo": {"unico_campo_permitido": "termo_externo", "validacao": "validar_termo_externo",
                                 "proibido_externo": ["interno.sanitizado_complementar", "caso", "marcos", "nomes"]},
            "escrita": "bloqueada sem confirmacao expressa do advogado",
            "auditoria_obrigatoria": "auditar_citacoes antes de qualquer saida com precedente"}


def fluxo(caso: str, nomes: list[str] | None = None) -> dict:
    """Coordenador completo: roteia, prepara cada especialista e exige auditoria."""
    r = rotear(caso)
    pacotes = [preparar(x["agente"], caso, nomes) for x in r["agentes"]]
    return {"roteamento": r, "pacotes": pacotes,
            "proximo": "triagem humana" if not pacotes else "responder e passar por auditar_citacoes"}


# ---------- adaptadores de fonte (somente leitura, acervo local de C:\\JURISBASE) ----------
import threading
_LOCK = threading.Lock()
_FULL: dict = {}
_INDICE: dict = {}
_CORROMPIDO = re.compile(r"p[aá]gina n[aã]o encontrada|n[aã]o est[aá] dispon[ií]vel neste endere[cç]o|404 not found|error 404", re.I)
_STOP = {"de", "da", "do", "das", "dos", "para", "com", "que", "uma", "por", "nos", "nas", "em", "ao", "aos", "um", "e", "o", "a", "os", "as"}


def _full():
    with _LOCK:
        if not _FULL:
            import server
            _FULL.update(server.fontes_direito_ler())
            _FULL["_informativos_stf"] = server.json_read(server.STF_INFORMATIVOS_FILE, {}).get("fontes", [])
            _FULL["_planalto"] = []
            for f in sorted((server.FONTES_DIREITO_DIR / "planalto").glob("*.json")):
                if f.name == "indice.json":
                    continue
                d = server.json_read(f, {})
                for a in d.get("artigos", []):
                    _FULL["_planalto"].append({"colecao": "planalto:" + d.get("id", f.stem), "titulo": f"{d.get('nome', f.stem)} - {a.get('rotulo', '')}",
                                               "texto": a.get("texto", ""), "source_url": d.get("fonte", ""), "id": f"{d.get('id', f.stem)}-{a.get('n', '')}"})
            pr = server.json_read(server.FONTES_DIREITO_DIR / "parana" / "legislacao_parana.json", {}).get("atos", [])
            _FULL["_parana"] = [{"colecao": "legislacao_parana", "titulo": a.get("nome", ""), "texto": a.get("texto", ""), "source_url": a.get("fonte", ""), "id": a.get("id", "")} for a in pr]
        return _FULL


def _por_tribunal(chave, tribunal):
    return [x for x in _full().get(chave, []) if x.get("tribunal") == tribunal]


# fonte -> lista de (colecao, funcao que devolve os itens)
def _fontes_def():
    F = _full
    return {
        "fonte_stf": [("stf_sumulas", lambda: F()["normativas_stf"]), ("stf_jurisprudencia", lambda: F()["jurisprudencia_stf"]),
                      ("stf_informativos", lambda: F()["_informativos_stf"]), ("stf_leis", lambda: F()["leis_stf"])],
        "fonte_stj": [("stj_teses", lambda: F()["teses_stj"]), ("stj_precedentes", lambda: F()["precedentes_stj"]),
                      ("stj_sumulas", lambda: [x for x in F()["normativas"] if x.get("tribunal") == "STJ"])],
        "fonte_tst_trt9": [("tst_livro", lambda: F()["livro"]), ("tst_teses_vinculantes", lambda: F()["precedentes"]),
                           ("trt9_informativos", lambda: F()["informativos"]), ("trt9_notas", lambda: F()["notas"]),
                           ("trt9_livros", lambda: F()["trt9_livros"]), ("trt9_repositorios", lambda: F()["trt9_repositorios"]),
                           ("trt9_precedentes_qualificados", lambda: _por_tribunal("precedentes_qualificados", "TRT9"))],
        "fonte_federal_trf4_tru4": [("trf4_sumulas", lambda: F()["sumulas_trf4"]), ("tru4_sumulas", lambda: F()["sumulas_tru4"]),
                                    ("trf4_irdr", lambda: _por_tribunal("precedentes_qualificados", "TRF4"))],
        "fonte_tribunais_contas": [("tribunais_contas", lambda: F()["tribunais_contas"])],
        "fonte_tse_eleitoral": [("tse_sumulas", lambda: F()["sumulas_tse"]), ("tse_legislacao", lambda: F()["legislacao_tse"]),
                                ("tse_compilada", lambda: F()["tse_compilada"])],
        "fonte_tjpr": [("tjpr_irdr_iac", lambda: F()["tjpr_irdr_iac"])],
        "fonte_legislacao": [("planalto", lambda: F()["_planalto"]), ("legislacao_parana", lambda: F()["_parana"])],
        "fonte_julgados_locais": [],
    }


def _texto(it: dict) -> str:
    for k in ("texto", "sumula_texto", "texto_bruto", "texto_integral", "ementa", "enunciado", "conteudo"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return " ".join(str(v) for v in it.values() if isinstance(v, str))


def _titulo(it: dict) -> str:
    return str(it.get("titulo") or it.get("rotulo") or it.get("nome") or it.get("id") or "")


def _indice(fonte: str) -> list:
    with _LOCK:
        if fonte in _INDICE:
            return _INDICE[fonte]
    out = []
    for col, fn in _fontes_def()[fonte]:
        for it in fn():
            if not isinstance(it, dict):
                continue
            txt, tit = _texto(it), _titulo(it)
            out.append({"col": col, "id": str(it.get("id") or it.get("numero") or ""), "tit": tit, "txt": txt, "ntit": norm(tit),
                        "ntxt": norm(txt)[:60000], "url": it.get("source_url") or it.get("fonte") or it.get("link") or it.get("url") or "",
                        "sit": it.get("situacao") or "", "corrompido": bool(_CORROMPIDO.search(txt[:800]))})
    with _LOCK:
        _INDICE[fonte] = out
    return out


def cobertura() -> dict:
    """Quantidade de itens por colecao de cada adaptador e quantos estao corrompidos."""
    res = {}
    for f in FONTES:
        idx = _indice(f) if _fontes_def()[f] else []
        por = {}
        for x in idx:
            d = por.setdefault(x["col"], {"itens": 0, "corrompidos": 0})
            d["itens"] += 1
            d["corrompidos"] += x["corrompido"]
        res[f] = por
    return res


def consultar_fonte(fonte: str, termo: str, limite: int = 20) -> dict:
    """Adaptador de leitura sobre o acervo local. Nunca grava; tudo volta NAO_CONFERIDO."""
    if fonte not in FONTES:
        raise LookupError("Fonte desconhecida")
    limite = max(1, min(int(limite), 100))
    s = sanitizar(termo)
    tokens = [t for t in re.findall(r"\w+", norm(termo_generico(termo) or s["texto_externo"])) if len(t) >= 3 and t not in _STOP]
    if not tokens:
        tokens = [t for t in re.findall(r"\w+", norm(s["texto_externo"])) if len(t) >= 3 and t not in _STOP]
    r = {"fonte_adaptador": fonte, "termo_enviado": " ".join(tokens), "resultados": [], "corrompidos_ignorados": 0,
         "verificacao": "nao_conferido", "portal_oficial": PORTAIS.get(fonte, "")}
    achados = []
    for x in _indice(fonte) if _fontes_def()[fonte] else []:
        if not tokens:
            break
        if not all(t in x["ntit"] or t in x["ntxt"] for t in tokens):
            continue
        if x["corrompido"]:
            r["corrompidos_ignorados"] += 1
            continue
        pontos = sum(3 for t in tokens if t in x["ntit"]) + sum(min(x["ntxt"].count(t), 5) for t in tokens)
        achados.append((pontos, x))
    achados.sort(key=lambda a: -a[0])
    for _, x in achados[:limite]:
        pos = x["ntxt"].find(tokens[0]) if tokens else 0
        ini = max(0, pos - 150)
        r["resultados"].append({"colecao": x["col"], "id": x["id"], "titulo": x["tit"], "trecho": x["txt"][ini:ini + 500].strip(),
                                "url": x["url"], "situacao": x["sit"], "verificacao": "nao_conferido"})
    if fonte in ("fonte_tjpr", "fonte_julgados_locais"):
        from robo import buscar
        b = buscar(" ".join(tokens), "TJPR" if fonte == "fonte_tjpr" else "", limite, {})
        for j in b.get("resultados", []):
            r["resultados"].append({"colecao": "julgados_db", "id": str(j.get("id", "")), "titulo": f"{j.get('classe', '')} {j.get('processo', '')}".strip(),
                                    "trecho": (j.get("texto") or "")[:500], "url": j.get("link") or "", "situacao": j.get("resultado") or "",
                                    "verificacao": "nao_conferido", "fonte_db": j.get("fonte")})
        if b.get("aviso"):
            r["aviso_base"] = b["aviso"]
    r["total"] = len(r["resultados"])
    if r["corrompidos_ignorados"]:
        r["aviso_dados"] = f"{r['corrompidos_ignorados']} item(ns) com texto corrompido (pagina de erro) ignorado(s); recoletar da fonte oficial"
    if r["total"] == 0:
        r["aviso"] = "Sem resultado no acervo local; isso NAO significa inexistencia: consultar o portal oficial."
    return r


def adaptadores_do_agente(agente: str) -> list:
    a = next((x for x in config()["agents"] if x["id"] == agente), None)
    if a is None:
        raise LookupError(f"Agente desconhecido: {agente}")
    return list(a.get("source_adapters", []))


def consultar_agente(agente: str, termo: str, limite: int = 10) -> dict:
    """Consulta todos os adaptadores vinculados ao especialista (somente leitura)."""
    ad = adaptadores_do_agente(agente)
    return {"agente": agente, "adaptadores": ad, "resultados": {f: consultar_fonte(f, termo, limite) for f in ad},
            "proximo": "auditar_citacoes antes de qualquer uso; nada vira conferido sem o advogado"}
