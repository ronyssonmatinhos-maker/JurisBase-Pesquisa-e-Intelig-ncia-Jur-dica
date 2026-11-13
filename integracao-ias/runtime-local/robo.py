# -*- coding: utf-8 -*-
"""Núcleo local do Robô Julgados.

Este módulo é a fronteira entre a interface, a IA e o acervo. Ele não usa
credenciais externas e não grava um achado sem confirmação explícita.
"""
from __future__ import annotations

import json
import os
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path

from engine.classificador import classificar

HERE = Path(__file__).resolve().parent
WORK_DB = HERE / "data" / "robo-julgados.db"
BACKUP_DIR = HERE / "data" / "backups"
REPORT_DIR = HERE / "data" / "relatorios"
DEFAULT_SOURCE_DB = Path(r"C:\JURISBASE\julgados\base\julgados.db")


def source_db() -> Path:
    return Path(os.environ.get("ROBO_JULGADOS_DB", str(DEFAULT_SOURCE_DB)))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_work() -> sqlite3.Connection:
    WORK_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(WORK_DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
      create table if not exists pesquisas (
        id integer primary key, tema text not null, termo text not null,
        tribunal text not null default '', nota text not null default '',
        criado_em text not null, criado_por text not null default 'IA'
      );
      create table if not exists achados (
        id integer primary key, pesquisa_id integer, julgado_id text not null,
        processo text, tribunal text, tipo text, trecho text, classificacao text,
        verificacao text not null default 'nao_conferido', conferido_por text,
        conferido_em text, criado_em text not null,
        foreign key (pesquisa_id) references pesquisas(id)
      );
      create table if not exists auditoria (
        id integer primary key, acao text not null, detalhes text not null,
        criado_em text not null, agente text not null
      );
      create table if not exists coletas (
        id integer primary key, tipo text not null, resumo text not null,
        total integer not null default 0, fonte text not null default 'app',
        criado_em text not null
      );
      create unique index if not exists achados_unico on achados(pesquisa_id, julgado_id);
    """)
    for statement in ("alter table pesquisas add column tribunal text not null default ''",
                      "alter table pesquisas add column nota text not null default ''"):
        try:
            con.execute(statement)
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    return con


def audit(con: sqlite3.Connection, action: str, details: dict, agent: str = "IA") -> None:
    con.execute("insert into auditoria(acao,detalhes,criado_em,agente) values(?,?,?,?)",
                (action, json.dumps(details, ensure_ascii=False), now(), agent))


def normalize_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["id"] = str(item.get("id", ""))
    item["texto"] = item.get("texto") or ""
    item["tribunal"] = item.get("tribunal") or item.get("fonte") or ""
    item["fonte_url"] = item.get("link") or ""
    return item


_ACENTOS = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ", "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN")


def sem_acento(valor) -> str:
    """Minúsculas e sem acento, para comparar termos de busca."""
    return str(valor or "").translate(_ACENTOS).lower()


def _padrao_largo(palavra: str) -> str:
    """Troca as letras que podem levar acento por '_' (qualquer caractere) para o filtro inicial em SQL."""
    return "".join("_" if c in "aeioucn" else c for c in sem_acento(palavra))


def buscar(termo: str, tribunal: str = "", limite: int = 30, filtros: dict | None = None) -> dict:
    termo = (termo or "").strip()
    if len(termo) > 240:
        raise ValueError("A busca deve ter no máximo 240 caracteres.")
    filtros = filtros if isinstance(filtros, dict) else {}
    if not termo and not any(str(filtros.get(k) or "").strip() for k in ("fonte", "tipo", "orgao", "classe", "comarca", "autoridade", "data_de", "data_ate")):
        raise ValueError("Informe um termo ou pelo menos um filtro.")
    limite = max(1, min(int(limite), 200))
    db = source_db()
    if not db.exists():
        return {"termo": termo, "total": 0, "resultados": [], "aviso": "acervo não encontrado"}
    # O acervo original é somente leitura. A consulta é parametrizada.
    palavras = [p for p in termo.split() if p]
    where = []
    params: list[str] = []
    # Busca sem distinção de acento: um filtro largo em SQL (rápido) e a conferência exata por sem_acento().
    for palavra in palavras:
        exato = f"%{sem_acento(palavra)}%"
        largo = f"%{_padrao_largo(palavra)}%"
        partes = []
        for coluna in ("texto", "processo", "classe", "orgao", "resultado", "tipo"):
            partes.append(f"({coluna} like ? and sa({coluna}) like ?)")
            params.extend([largo, exato])
        where.append("(" + " or ".join(partes) + ")")
    fonte = str(filtros.get("fonte") or tribunal or "").strip()
    if fonte:
        where.append("sa(fonte) like ?")
        params.append(f"%{sem_acento(fonte)}%")
    for key, column in (("orgao", "orgao"), ("classe", "classe"), ("comarca", "comarca"), ("autoridade", "autoridade")):
        value = str(filtros.get(key) or "").strip()
        if value:
            where.append(f"sa(COALESCE({column}, '')) like ?")
            params.append(f"%{sem_acento(value)}%")
    tipo = str(filtros.get("tipo") or "").strip()
    if tipo:
        where.append("COALESCE(tipo, '') = ?")
        params.append(tipo)
    data_de = str(filtros.get("data_de") or "").strip()
    data_ate = str(filtros.get("data_ate") or "").strip()
    if data_de:
        where.append("COALESCE(data, '') >= ?")
        params.append(data_de)
    if data_ate:
        where.append("COALESCE(data, '') <= ?")
        params.append(data_ate)
    sql = "select id, fonte, tipo, data, processo, classe, orgao, resultado, link, texto from docs where " + " and ".join(where) + " order by data desc limit ?"
    params.append(limite)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.create_function("sa", 1, sem_acento, deterministic=True)
    try:
        rows = [normalize_row(r) for r in con.execute(sql, params)]
    finally:
        con.close()
    return {"termo": termo, "total": len(rows), "resultados": rows}


def registrar_coleta(tipo: str, resumo: str, total: int = 0, fonte: str = "rotina") -> dict:
    tipo = colapsar_texto(tipo)[:40] or "coleta"
    resumo = colapsar_texto(resumo)[:240] or "Coleta concluída"
    con = connect_work()
    try:
        cur = con.execute("insert into coletas(tipo,resumo,total,fonte,criado_em) values(?,?,?,?,?)",
                          (tipo, resumo, max(0, int(total or 0)), colapsar_texto(fonte)[:40] or "rotina", now()))
        audit(con, "registrar_coleta", {"coleta_id": cur.lastrowid, "tipo": tipo, "total": max(0, int(total or 0))}, "sistema")
        con.commit()
        return {"id": cur.lastrowid, "tipo": tipo, "resumo": resumo, "total": max(0, int(total or 0))}
    finally:
        con.close()


def colapsar_texto(value: object) -> str:
    return " ".join(str(value or "").split())


def listar_coletas(limite: int = 6) -> list[dict]:
    con = connect_work()
    try:
        return [dict(r) for r in con.execute("select * from coletas where fonte <> 'app' order by id desc limit ?", (max(1, min(int(limite), 30)),))]
    finally:
        con.close()


def classificar_item(item: dict, contexto: dict | None = None) -> dict:
    return classificar(item, contexto or {})


def gravar_achado(item: dict, classificacao: dict, termo: str, confirmacao: str,
                  agente: str = "IA", pesquisa_id: int | None = None) -> dict:
    if confirmacao != "CONFIRMO_GRAVACAO":
        raise PermissionError("A gravação exige confirmação explícita: CONFIRMO_GRAVACAO.")
    con = connect_work()
    try:
        if pesquisa_id is None:
            cur = con.execute("insert into pesquisas(tema,termo,criado_em,criado_por) values(?,?,?,?)",
                              (termo, termo, now(), agente))
            pesquisa_id = cur.lastrowid
        cur = con.execute("""insert into achados
          (pesquisa_id,julgado_id,processo,tribunal,tipo,trecho,classificacao,criado_em)
          values(?,?,?,?,?,?,?,?)""", (pesquisa_id, str(item.get("id", "")), item.get("processo"),
          item.get("tribunal") or item.get("fonte"), item.get("tipo"), (item.get("texto") or "")[:1200],
          json.dumps(classificacao, ensure_ascii=False), now()))
        achado_id = cur.lastrowid
        audit(con, "gravar_achado", {"achado_id": achado_id, "julgado_id": item.get("id"), "termo": termo}, agente)
        con.commit()
        return {"id": achado_id, "verificacao": "nao_conferido", "pesquisa_id": pesquisa_id}
    finally:
        con.close()


def listar_achados() -> list[dict]:
    con = connect_work()
    try:
        return [dict(r) for r in con.execute("select * from achados order by id desc")]
    finally:
        con.close()


def salvar_pesquisa(termo: str, tribunal: str = "", nota: str = "", agente: str = "IA") -> dict:
    termo = (termo or "").strip()
    if not termo:
        raise ValueError("Informe o termo da pesquisa.")
    con = connect_work()
    try:
        cur = con.execute("insert into pesquisas(tema,termo,tribunal,nota,criado_em,criado_por) values(?,?,?,?,?,?)",
                          (termo, termo, tribunal or "", nota or "", now(), agente))
        audit(con, "salvar_pesquisa", {"pesquisa_id": cur.lastrowid, "termo": termo, "tribunal": tribunal}, agente)
        con.commit()
        return {"id": cur.lastrowid, "termo": termo, "tribunal": tribunal or ""}
    finally:
        con.close()


def listar_pesquisas() -> list[dict]:
    con = connect_work()
    try:
        return [dict(r) for r in con.execute("select p.*, (select count(*) from achados a where a.pesquisa_id=p.id) as total_achados from pesquisas p order by p.id desc")]
    finally:
        con.close()


def listar_auditoria(limite: int = 100) -> list[dict]:
    con = connect_work()
    try:
        return [dict(r) for r in con.execute("select * from auditoria order by id desc limit ?", (max(1, min(int(limite), 500)),))]
    finally:
        con.close()


def fontes() -> dict:
    path = HERE.parent / "fontes" / "fontes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"meta": {}, "convencoes": {}, "orientacoes_tst": {}}


def backup() -> dict:
    con = connect_work()
    con.commit(); con.close()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"robo-julgados-{stamp}.db"
    shutil.copy2(WORK_DB, dest)
    con = connect_work()
    try:
        audit(con, "backup", {"arquivo": str(dest)}, "sistema")
        con.commit()
    finally:
        con.close()
    return {"arquivo": str(dest), "tamanho": dest.stat().st_size}


def relatorio(limite: int = 200) -> dict:
    rows = listar_achados()[:max(1, min(int(limite), 1000))]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = REPORT_DIR / f"relatorio-julgados-{stamp}.txt"
    lines = ["RELATÓRIO DO ROBÔ JULGADOS", f"Gerado em: {now()}", f"Achados: {len(rows)}", ""]
    for row in rows:
        lines.extend([f"[{row.get('verificacao')}] {row.get('tribunal') or ''} — {row.get('processo') or ''}",
                      f"Tipo: {row.get('tipo') or 'não identificado'}", f"Trecho: {row.get('trecho') or ''}", ""])
    dest.write_text("\n".join(lines), encoding="utf-8")
    return {"arquivo": str(dest), "total": len(rows)}


def conferir_achado(achado_id: int, papel: str, confirmacao: str, agente: str = "advogado") -> dict:
    if papel != "advogado":
        raise PermissionError("Somente o advogado pode marcar conferido_oficial.")
    if confirmacao != "CONFIRMO_CONFERENCIA_OFICIAL":
        raise PermissionError("A conferência exige confirmação expressa.")
    con = connect_work()
    try:
        cur = con.execute("update achados set verificacao='conferido_oficial', conferido_por=?, conferido_em=? where id=?",
                          (agente, now(), int(achado_id)))
        if cur.rowcount != 1:
            raise LookupError("Achado não encontrado.")
        audit(con, "conferir_oficial", {"achado_id": achado_id}, agente)
        con.commit()
        return {"id": achado_id, "verificacao": "conferido_oficial", "conferido_por": agente}
    finally:
        con.close()


def estado() -> dict:
    con = connect_work()
    try:
        total = con.execute("select count(*) from achados").fetchone()[0]
        nao = con.execute("select count(*) from achados where verificacao='nao_conferido'").fetchone()[0]
        pesquisas = con.execute("select count(*) from pesquisas").fetchone()[0]
        coletas = [dict(r) for r in con.execute("select * from coletas where fonte <> 'app' order by id desc limit 6")]
    finally:
        con.close()
    return {"acervo": str(source_db()), "acervo_existe": source_db().exists(),
            "banco_trabalho": str(WORK_DB), "achados": total, "nao_conferidos": nao, "pesquisas": pesquisas,
            "coletas": coletas, "ultima_atualizacao": coletas[0]["criado_em"] if coletas else "",
            "regras": ["gravação exige confirmação", "novo achado=nao_conferido", "conferido_oficial exige papel advogado",
                       "Jamais citar JurisBase, o próprio app ou IA como fonte da informação ou autoridade jurídica. Citar exclusivamente a fonte original efetivamente conferida. Não inserir comentários operacionais de pesquisa nas minutas."]}


def comando(payload: dict) -> dict:
    action = payload.get("acao") or payload.get("action")
    if action == "estado":
        return estado()
    if action == "buscar":
        return buscar(payload.get("termo", ""), payload.get("tribunal", ""), payload.get("limite", 30), payload.get("filtros", {}))
    if action == "classificar":
        return classificar_item(payload.get("item", {}), payload.get("contexto", {}))
    if action == "gravar_achado":
        return gravar_achado(payload["item"], payload.get("classificacao", {}), payload.get("termo", ""), payload.get("confirmacao", ""), payload.get("agente", "IA"), payload.get("pesquisa_id"))
    if action == "listar_achados":
        return {"achados": listar_achados()}
    if action == "salvar_pesquisa":
        return salvar_pesquisa(payload.get("termo", ""), payload.get("tribunal", ""), payload.get("nota", ""), payload.get("agente", "IA"))
    if action == "listar_pesquisas":
        return {"pesquisas": listar_pesquisas()}
    if action == "listar_auditoria":
        return {"auditoria": listar_auditoria(payload.get("limite", 100))}
    if action == "listar_coletas":
        return {"coletas": listar_coletas(payload.get("limite", 6))}
    if action == "registrar_coleta":
        return registrar_coleta(payload.get("tipo", "coleta"), payload.get("resumo", "Coleta concluída"), payload.get("total", 0), payload.get("fonte", "rotina"))
    if action == "fontes":
        return fontes()
    if action == "backup":
        return backup()
    if action == "relatorio":
        return relatorio(payload.get("limite", 200))
    if action == "conferir_oficial":
        return conferir_achado(payload["id"], payload.get("papel", ""), payload.get("confirmacao", ""), payload.get("agente", "advogado"))
    if action in ("agentes", "rotear", "preparar_agente", "sanitizar", "auditar_citacoes", "fluxo_agentes", "consultar_fonte", "consultar_agente", "cobertura_fontes", "conferir_fonte_oficial", "responder_agente"):
        import agentes
        if action == "agentes":
            return agentes.listar()
        if action == "rotear":
            return agentes.rotear(payload.get("caso", ""))
        if action == "preparar_agente":
            return agentes.preparar(payload["agente"], payload.get("caso", ""), payload.get("nomes"), payload.get("marcos"), payload.get("conferencias"))
        if action == "sanitizar":
            return agentes.sanitizar(payload.get("texto", ""), payload.get("nomes"))
        if action == "conferir_fonte_oficial":
            import conferencia
            return conferencia.conferir(payload["item"]) if payload.get("item") else conferencia.listar()
        if action == "responder_agente":
            import llm
            try:
                return llm.responder(payload["agente"], payload.get("caso", ""), payload.get("nomes"), payload.get("marcos"), payload.get("conferencias"), None, bool(payload.get("dados_reais")))
            except llm.LLMIndisponivel as e:
                return {"erro": "modelo indisponivel", "detalhe": str(e), "conferido_oficial": False}
        if action == "auditar_citacoes":
            return agentes.auditar_citacoes(payload.get("citacoes", []), payload.get("evidencias"))
        if action == "fluxo_agentes":
            return agentes.fluxo(payload.get("caso", ""), payload.get("nomes"))
        if action == "consultar_agente":
            return agentes.consultar_agente(payload["agente"], payload.get("termo", ""), payload.get("limite", 10))
        if action == "cobertura_fontes":
            return agentes.cobertura()
        return agentes.consultar_fonte(payload["fonte"], payload.get("termo", ""), payload.get("limite", 20))
    raise ValueError("Ação não reconhecida. Consulte IA-OPERACAO.md para a lista de comandos.")
