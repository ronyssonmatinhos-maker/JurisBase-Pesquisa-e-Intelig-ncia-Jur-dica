# Teste com MODELO REAL (provedor claude_cli ou API). Dados SINTETICOS. Saida: config/agentes/testes/saida-modelo-real-<provedor>.json
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm, marcos
prov = os.environ.get("JURISBASE_LLM_PROVIDER", "claude_cli")
CASOS = {
 "T01_execucao_fiscal_prescricao_sem_marcos": ("execucao_fiscal", "Execucao fiscal de IPTU com alegacao de prescricao intercorrente; ha tres datas no processo: 01/02/2018, 03/04/2019 e 05/06/2020. Pode-se concluir pela prescricao?"),
 "T02_execucao_fiscal_baixo_valor": ("execucao_fiscal", "Execucao fiscal municipal de R$ 4.000,00, sem movimentacao ha dois anos, sem bens. Cabe extincao? Cite o Tema 1184 e a Resolucao CNJ 547/2024."),
 "T04_licitacoes_transicao": ("administrativo_licitacoes", "Contrato administrativo assinado em 2022 sob a Lei 8.666/93; discute-se qual regime se aplica apos a Lei 14.133/2021."),
}
saidas = {}
for nome, (ag, caso) in CASOS.items():
    try:
        r = llm.responder(ag, caso)
        saidas[nome] = {"valida": r.get("valida"), "erro": r.get("erro"), "avisos": r.get("avisos_runtime"),
                        "saida": r.get("saida"), "auditoria": r.get("auditoria_citacoes"), "pre_condicoes_pode_concluir": r.get("pre_condicoes", {}).get("pode_concluir")}
    except Exception as e:
        saidas[nome] = {"indisponivel": f"{type(e).__name__}: {e}"[:300]}
out = Path(__file__).resolve().parent / "config" / "agentes" / "testes" / f"saida-modelo-real-{prov}.json"
out.write_text(json.dumps(saidas, ensure_ascii=False, indent=1), encoding="utf-8")
print(out); print({k: (v.get("valida"), v.get("indisponivel")) for k, v in saidas.items()})
