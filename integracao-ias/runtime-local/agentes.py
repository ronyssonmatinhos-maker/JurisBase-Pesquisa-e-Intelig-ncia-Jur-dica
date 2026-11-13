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
    return {"especialistas": ag, "componentes": ["coordenador", "auditor_citacoes"],
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


def termo_generico(caso: str, agente: str | None = None) -> str:
    """Termo de pesquisa externa montado SO com vocabulario juridico (nunca com texto livre)."""
    termos: list[str] = []
    for a in config()["agents"]:
        if agente and a["id"] != agente:
            continue
        termos += [x for x in a["trigger_terms"] if _tem(x, caso)]
    for rx in (r"\btema\s+\d+", r"\bs[uú]mula\s+(?:vinculante\s+)?\d+", r"\bart(?:igo)?s?\.?\s*\d+[\w\-]*",
               r"\blei\s+(?:complementar\s+)?(?:n[ºo.]*\s*)?\d[\d.]*(?:/\d{2,4})?"):
        termos += [m.group(0) for m in re.finditer(rx, caso or "", re.I)]
    visto, out = set(), []
    for t in termos:
        k = norm(t)
        if k not in visto:
            visto.add(k); out.append(t)
    return " ".join(out)


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


def pre_condicoes(agente: str, caso: str) -> dict:
    t, lac, avis = norm(caso), [], []
    ok = True
    if agente == "execucao_fiscal":
        if "prescri" in t and len(set(_DATA.findall(caso))) < 3:
            ok = False
            lac += ["data de constituicao definitiva do credito", "data da citacao",
                    "marco de suspensao (art. 40 da LEF) e ciencia da Fazenda", "datas de cada intimacao"]
            avis.append("nao afirmar prescricao sem marcos; separar prescricao de nulidade")
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
    return {"agente": agente, "pode_concluir": ok, "lacunas": lac, "avisos": avis}


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


def auditar_citacoes(citacoes: list[dict]) -> dict:
    """Nunca devolve conferido_oficial: so o advogado confere."""
    res = []
    for c in citacoes or []:
        falta = [k for k in OBRIG if not str(c.get(k, "")).strip()]
        prob = []
        if falta:
            prob.append("campos ausentes: " + ", ".join(falta))
        if c.get("url") and not _url_oficial(c["url"]):
            prob.append("url nao oficial")
        v = cnj_valido(c.get("processo", ""))
        if v is False:
            prob.append("numero CNJ com digito verificador invalido (possivel citacao fictícia)")
        txt = norm(" ".join(str(x) for x in c.values()))
        if "jurisbase" in txt or "segundo o acervo" in txt or "a ia " in txt:
            prob.append("o app/IA nao pode ser citado como fundamento")
        res.append({"citacao": c.get("processo") or c.get("referencia") or "(sem identificacao)",
                    "status": "NAO_CONFERIDO", "apto_para_conferencia_do_advogado": not prob,
                    "pode_constar_na_minuta": False, "problemas": prob})
    return {"auditoria": res, "regra": "somente o advogado marca conferido_oficial; ate la, fora da minuta"}


def preparar(agente: str, caso: str = "", nomes: list[str] | None = None) -> dict:
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
            "politica_fontes": a["source_policy"], "pre_condicoes": pre_condicoes(agente, caso),
            "termo_externo": termo_generico(caso, agente), "sanitizacao": san["registro"],
            "sanitizado_complementar": san["texto_externo"],
            "escrita": "bloqueada sem confirmacao expressa do advogado",
            "auditoria_obrigatoria": "auditar_citacoes antes de qualquer saida com precedente"}


def fluxo(caso: str, nomes: list[str] | None = None) -> dict:
    """Coordenador completo: roteia, prepara cada especialista e exige auditoria."""
    r = rotear(caso)
    pacotes = [preparar(x["agente"], caso, nomes) for x in r["agentes"]]
    return {"roteamento": r, "pacotes": pacotes,
            "proximo": "triagem humana" if not pacotes else "responder e passar por auditar_citacoes"}


def consultar_fonte(fonte: str, termo: str, limite: int = 20) -> dict:
    """Adaptador de leitura: usa o buscar() existente, com termo sanitizado."""
    if fonte not in FONTES:
        raise LookupError("Fonte desconhecida")
    from robo import buscar
    s = sanitizar(termo)
    r = buscar(s["texto_externo"], FONTES[fonte], limite, {})
    r["termo_enviado"] = s["texto_externo"]
    r["fonte_adaptador"] = fonte
    if fonte in PORTAIS:
        r["portal_oficial"] = PORTAIS[fonte]
    if fonte not in LOCAL_COM_BASE:
        r["aviso_base"] = ("Sem base local para esta fonte (o acervo local tem TJPR e DJEN). "
                           "Resultado vazio NAO significa inexistencia: consultar o portal oficial.")
    r["verificacao"] = "nao_conferido"
    return r
