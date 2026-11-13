"""Linha do tempo tipada para prescricao (skill_marcos_e_precedentes v1.0).

Regra: quantidade de datas NUNCA libera conclusao. So marcos estruturados
(tipo, data, fonte, certeza, efeito) sao considerados; datas soltas no texto sao ignoradas.
Modulo puro: nao le nem grava nada.
"""
from __future__ import annotations
import re
from datetime import date

TIPOS = {
    "constituicao_definitiva": "constituicao definitiva do credito / exigibilidade",
    "ajuizamento": "ajuizamento da execucao fiscal",
    "despacho_citatorio": "despacho que ordena a citacao",
    "tentativa_citacao_localizacao": "tentativa de citacao ou de localizacao de devedor/bens e resultado",
    "ciencia_fazenda_nao_localizacao": "primeira ciencia da Fazenda da nao localizacao de devedor/bens",
    "suspensao_art40_inicio": "inicio da suspensao de 1 ano (art. 40, par. 1, LEF)",
    "suspensao_art40_fim": "fim do ano de suspensao",
    "citacao_efetiva": "citacao efetiva do executado",
    "constricao_efetiva": "constricao patrimonial efetiva (penhora/bloqueio realizado)",
    "requerimento_infrutifero": "peticao/diligencia da Fazenda sem constricao efetiva",
    "causa_suspensao_interrupcao": "causa legal de suspensao ou interrupcao (parcelamento, etc.)",
    "intimacao_contraditorio": "intimacao/oitiva da Fazenda antes do reconhecimento (art. 40, par. 4, LEF)",
}
CERTEZAS = {"documental", "alegado", "inferido", "desconhecido"}
ESSENCIAIS = ["constituicao_definitiva", "ajuizamento", "despacho_citatorio",
              "ciencia_fazenda_nao_localizacao", "suspensao_art40_inicio", "intimacao_contraditorio"]
# ordem cronologica esperada quando ambos existem (cada par: anterior <= posterior)
ORDEM = [("constituicao_definitiva", "ajuizamento"), ("ajuizamento", "despacho_citatorio"),
         ("despacho_citatorio", "ciencia_fazenda_nao_localizacao"),
         ("ciencia_fazenda_nao_localizacao", "suspensao_art40_inicio"),
         ("suspensao_art40_inicio", "suspensao_art40_fim")]
TEMA_566 = ("Tema 566/STJ (REsp 1.340.553/RS): NAO_CONFERIDO - confrontar tese e inteiro teor na fonte oficial "
            "antes de aplicar; nao presumir marcos nem prazos")


def _data(v) -> date | None:
    s = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s) or None
    try:
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return None


def avaliar_prescricao(caso_norm: str, marcos: list[dict] | None, conferencias: dict | None = None) -> dict:
    """caso_norm: texto normalizado (sem acento, minusculo). Devolve avaliacao condicional."""
    marcos = marcos or []
    conferencias = conferencias or {}
    lac: list[str] = []
    contra: list[str] = []
    avis: list[str] = ["nao afirmar prescricao sem marcos; separar prescricao de nulidade",
                       "datas soltas no texto nao sao marcos: so marcos tipados contam"]
    intercorrente = "intercorrente" in caso_norm
    avis.append("tipo: " + ("intercorrente (art. 40 LEF)" if intercorrente else
                            "originaria ou nao definida: nao confundir com intercorrente (art. 174 CTN x art. 40 LEF)"))
    if not marcos:
        lac.append("marcos estruturados ausentes (tipo, data, fonte/documento, certeza, efeito)")
        lac += [f"marco: {v}" for k, v in TIPOS.items() if k in ESSENCIAIS]
        return _resp(False, "CONDICIONAL_SEM_MARCOS", lac, contra, avis, [])

    norm_m: list[dict] = []
    for i, m in enumerate(marcos):
        tipo = str(m.get("tipo", "")).strip()
        d = _data(m.get("data"))
        cert = str(m.get("certeza", "")).strip() or "desconhecido"
        rotulo = f"marco[{i}] {tipo or '(sem tipo)'}"
        if tipo not in TIPOS:
            lac.append(rotulo + ": tipo desconhecido")
            continue
        if d is None:
            lac.append(rotulo + ": data ausente ou invalida")
        if not str(m.get("fonte", "")).strip():
            lac.append(rotulo + ": fonte/documento ausente")
        if cert not in CERTEZAS:
            lac.append(rotulo + ": grau de certeza invalido")
            cert = "desconhecido"
        if not str(m.get("efeito", "")).strip():
            lac.append(rotulo + ": efeito juridico nao informado")
        norm_m.append({"tipo": tipo, "data": d, "certeza": cert, "credito": str(m.get("credito", "")).strip() or "(unico)",
                       "efeito": str(m.get("efeito", "")).lower(), "fonte": m.get("fonte"),
                       "prazo_anos": m.get("prazo_anos"), "natureza": m.get("natureza")})

    creditos = sorted({m["credito"] for m in norm_m}) or ["(unico)"]
    if re.search(r"\b(cdas|creditos|duas cdas|varias cdas|mais de uma cda)\b", caso_norm) and creditos == ["(unico)"]:
        lac.append("varios creditos mencionados: informar marcos e prazo por credito (campo credito)")
    for cr in creditos:
        ms = [m for m in norm_m if m["credito"] == cr]
        tipos = {m["tipo"] for m in ms}
        pref = f"credito {cr}: "
        for e in ESSENCIAIS:
            if e not in tipos:
                lac.append(pref + "falta marco essencial: " + TIPOS[e])
        pz = [m for m in ms if m["prazo_anos"] is not None]
        if not pz or not any(m.get("natureza") for m in ms):
            lac.append(pref + "natureza e prazo prescricional do credito nao informados")
        elif len({str(m["prazo_anos"]) for m in pz}) > 1:
            contra.append(pref + "prazos prescricionais divergentes dentro do mesmo credito")
        for m in ms:
            if m["certeza"] in ("alegado", "inferido", "desconhecido") and m["tipo"] in ESSENCIAIS:
                avis.append(pref + f"marco {m['tipo']} com certeza '{m['certeza']}': conclusao apenas condicional")
        # duplicidade conflitante
        for t in {x["tipo"] for x in ms}:
            ds = {x["data"] for x in ms if x["tipo"] == t and x["data"]}
            if t in ESSENCIAIS and len(ds) > 1:
                contra.append(pref + f"marco {t} com datas conflitantes")
        # cronologia
        por = {}
        for m in ms:
            if m["data"] and m["tipo"] not in por:
                por[m["tipo"]] = m["data"]
        for a, b in ORDEM:
            if a in por and b in por and por[a] > por[b]:
                contra.append(pref + f"cronologia contraditoria: {a} posterior a {b}")
        # requerimento infrutifero nao e constricao
        for m in ms:
            if m["tipo"] == "requerimento_infrutifero" and any(w in m["efeito"] for w in ("interrompe", "interrupcao", "constricao")):
                contra.append(pref + "requerimento infrutifero tratado como causa interruptiva/constricao: so citacao ou constricao efetiva produzem esse efeito")
            if m["tipo"] in ("constricao_efetiva", "citacao_efetiva") and m["data"] is None:
                lac.append(pref + f"{m['tipo']} sem data")
        if "requerimento_infrutifero" in tipos and not tipos & {"constricao_efetiva", "citacao_efetiva"}:
            avis.append(pref + "ha apenas requerimentos infrutiferos: nao interrompem a prescricao intercorrente por si")
        if not intercorrente and "ciencia_fazenda_nao_localizacao" not in tipos:
            pass
    avis.append(TEMA_566)
    completo = not lac and not contra
    pode = completo and bool(conferencias.get("tema_566_conferido_pelo_advogado"))
    status = ("ANALISE_ESTRUTURADA_COMPLETA" if completo else
              "CONTRADICAO" if contra else "CONDICIONAL_COM_LACUNAS")
    if completo and not pode:
        lac.append("conferencia do inteiro teor oficial do Tema 566/REsp 1.340.553/RS pelo advogado pendente")
    cron = [{"credito": m["credito"], "tipo": m["tipo"], "data": m["data"].isoformat() if m["data"] else None,
             "certeza": m["certeza"]} for m in sorted(norm_m, key=lambda x: (x["credito"], x["data"] or date.max))]
    return _resp(pode, status, lac, contra, avis, cron)


def _resp(pode, status, lac, contra, avis, cron):
    return {"pode_concluir": bool(pode), "status": status, "lacunas": lac, "contradicoes": contra,
            "avisos": avis, "cronologia": cron,
            "regra": "pode_concluir nunca decorre de contagem de datas; exige marcos tipados, coerencia e conferencia oficial pelo advogado"}
