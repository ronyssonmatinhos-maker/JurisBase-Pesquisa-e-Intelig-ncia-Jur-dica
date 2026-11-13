"""Integracao com modelo de linguagem para os agentes (somente leitura, sem gravar nada).

Provedores (JURISBASE_LLM_PROVIDER): anthropic (ANTHROPIC_API_KEY), claude_cli (comando `claude -p`,
usa a sessao do usuario), openai (OPENAI_API_KEY). Sem provedor configurado: LLMIndisponivel (falha explicita).
Dados: por padrao o modelo recebe SO o texto sanitizado (minimizacao); texto original apenas com
dados_reais=True, decisao expressa do advogado, registrada no retorno.
Saida do modelo e sempre tratada como NAO_CONFERIDA: citacoes passam pelo auditor, nada vira conferido/minuta.
"""
from __future__ import annotations
import json, os, re, subprocess, urllib.request
import agentes, auditor_oficial


class LLMIndisponivel(RuntimeError):
    pass


def _anthropic(prompt: str, timeout: float = 120) -> str:
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k:
        raise LLMIndisponivel("ANTHROPIC_API_KEY nao definida")
    body = json.dumps({"model": os.environ.get("JURISBASE_LLM_MODEL", "claude-sonnet-5-5"), "max_tokens": 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
                                 headers={"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return "".join(b.get("text", "") for b in json.load(r).get("content", []))


def _openai(prompt: str, timeout: float = 120) -> str:
    k = os.environ.get("OPENAI_API_KEY")
    if not k:
        raise LLMIndisponivel("OPENAI_API_KEY nao definida")
    body = json.dumps({"model": os.environ.get("JURISBASE_LLM_MODEL", "gpt-4.1"), "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + k, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def _claude_cli(prompt: str, timeout: float = 180) -> str:
    try:
        p = subprocess.run([os.environ.get("JURISBASE_CLAUDE_BIN", "claude"), "-p", prompt], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise LLMIndisponivel("comando 'claude' nao encontrado")
    if p.returncode != 0 or not p.stdout.strip():
        raise LLMIndisponivel("claude -p falhou: " + (p.stderr or p.stdout)[:200])
    return p.stdout


PROVEDORES = {"anthropic": _anthropic, "openai": _openai, "claude_cli": _claude_cli}


def provedor_padrao():
    nome = os.environ.get("JURISBASE_LLM_PROVIDER", "")
    if nome not in PROVEDORES:
        raise LLMIndisponivel("defina JURISBASE_LLM_PROVIDER = " + "|".join(PROVEDORES))
    return PROVEDORES[nome]


def montar_prompt(pacote: dict, caso_texto: str) -> str:
    sch = ", ".join(pacote["saida"])
    pc = pacote["pre_condicoes"]
    return (
        "Voce e o especialista '%s' do JurisBase. Responda SOMENTE com um objeto JSON valido (sem texto fora do JSON) "
        "com exatamente estas chaves: %s.\n"
        "REGRAS: nao invente fatos, leis, artigos, numeros de processo, ementas ou trechos; tudo que for precedente vai em "
        "julgados_nao_conferidos como lista de objetos {tribunal, orgao_julgador, processo, relator, data_julgamento, url, tese_atribuida}; "
        "nunca afirme que algo esta conferido; indique lacunas e pendencias; nao conclua alem do que as pre-condicoes permitem.\n\n"
        "INSTRUCOES DO AGENTE:\n- %s\n\nFICHA:\n%s\n\nPRE-CONDICOES (pode_concluir=%s):\nlacunas=%s\navisos=%s\n\nCASO:\n%s\n"
        % (pacote["agente"], sch, "\n- ".join(pacote["instrucoes"]), pacote["ficha"][:6000], pc["pode_concluir"],
           json.dumps(pc["lacunas"], ensure_ascii=False), json.dumps(pc["avisos"], ensure_ascii=False), caso_texto))


def _extrair_json(txt: str):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        raise ValueError("resposta sem JSON")
    return json.loads(m.group(0))


def responder(agente: str, caso: str, nomes=None, marcos=None, conferencias=None, provedor=None, dados_reais: bool = False) -> dict:
    pacote = agentes.preparar(agente, caso, nomes, marcos, conferencias)
    texto = caso if dados_reais else pacote["interno"]["sanitizado_complementar"]
    prov = provedor or provedor_padrao()
    bruto = prov(montar_prompt(pacote, texto))
    avisos = []
    try:
        saida = _extrair_json(bruto)
    except Exception as e:
        return {"agente": agente, "valida": False, "erro": f"saida do modelo invalida: {e}", "bruto_truncado": (bruto or "")[:500],
                "conferido_oficial": False, "pode_constar_na_minuta": False}
    faltam = [k for k in pacote["saida"] if k not in saida]
    if faltam:
        avisos.append("chaves ausentes na saida: " + ", ".join(faltam))
        for k in faltam:
            saida[k] = []
    cits = [c for c in saida.get("julgados_nao_conferidos", []) if isinstance(c, dict)]
    aud = agentes.auditar_citacoes(cits)
    if not pacote["pre_condicoes"]["pode_concluir"]:
        avisos.append("pre-condicoes nao liberam conclusao: tratar a saida como analise condicional")
    for t in ("teses_favoraveis", "teses_contrarias"):
        if not isinstance(saida.get(t), list):
            saida[t] = [str(saida.get(t))] if saida.get(t) else []
    saida["pendencias_validacao"] = list(saida.get("pendencias_validacao") or []) + ["todo precedente: NAO_CONFERIDO ate ato do advogado"]
    return {"agente": agente, "valida": not faltam, "saida": saida, "auditoria_citacoes": aud["auditoria"],
            "pre_condicoes": pacote["pre_condicoes"], "avisos_runtime": avisos,
            "dados_enviados_ao_modelo": "texto original (autorizado pelo advogado)" if dados_reais else "texto sanitizado",
            "conferido_oficial": False, "pode_constar_na_minuta": False}
