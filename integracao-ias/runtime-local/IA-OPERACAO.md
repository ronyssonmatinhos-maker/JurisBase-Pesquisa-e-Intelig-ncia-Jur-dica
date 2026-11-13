# Como a IA usa o Robô Julgados

O Robô Julgados fica instalado e executando no computador. A IA não acessa o
banco diretamente: ela pede ações ao núcleo local por comandos JSON ou pelo
endpoint `http://127.0.0.1:8767/api/ia/comando`.

## Fluxo obrigatório

1. `estado`: verificar banco, regras e quantidade de achados.
2. `buscar`: usar termos jurídicos genéricos e consultar o acervo local.
3. `classificar`: classificar cada item sem transformar hipótese em fato.
4. Mostrar os candidatos ao usuário.
5. Só depois da confirmação, `gravar_achado`.
6. Todo novo achado é gravado como `nao_conferido`.
7. Somente o advogado pode usar `conferir_oficial`.

## Blocos locais disponíveis

- `salvar_pesquisa` e `listar_pesquisas`: histórico de temas e consultas;
- `listar_auditoria`: trilha local das ações;
- `fontes`: catálogo informativo de fontes oficiais;
- `backup`: cópia do banco de trabalho antes de operações importantes;
- `relatorio`: exportação TXT dos achados;
- `listar_achados`: fila de revisão.

## Exemplos

```json
{"acao":"estado"}
```

```json
{"acao":"buscar","termo":"prescrição intercorrente","tribunal":"TRT9","limite":20}
```

```json
{"acao":"gravar_achado","item":{"id":"123","processo":"...","tribunal":"TRT9","texto":"..."},"classificacao":{"categoria":"revisao_manual"},"termo":"prescrição intercorrente","confirmacao":"CONFIRMO_GRAVACAO"}
```

```json
{"acao":"conferir_oficial","id":1,"papel":"advogado","agente":"advogado","confirmacao":"CONFIRMO_CONFERENCIA_OFICIAL"}
```

O acervo original é aberto somente para leitura. O histórico de pesquisas,
achados e auditoria fica em `app/data/robo-julgados.db`.
REGRA ABSOLUTA — FONTES ORIGINAIS
JurisBase é ferramenta de pesquisa, nunca fonte da informação ou autoridade jurídica. Jamais citar o próprio app, JurisBase ou IA como fundamento em minutas, pareceres ou relatórios jurídicos. Citar apenas a fonte original efetivamente conferida (tribunal, órgão, processo, relator e datas disponíveis; norma e dispositivo; autor e obra). Não inventar metadados nem inserir comentários operacionais na peça. Precedentes não confirmados devem ser excluídos da minuta e apontados como pendência interna. Esta regra vale para qualquer modelo GPT ou outro assistente.


## Agentes juridicos (20 especialistas + coordenador + auditor)

Comandos adicionais (mesmo endpoint/CLI): `agentes`, `rotear`, `preparar_agente`,
`fluxo_agentes`, `sanitizar`, `auditar_citacoes`, `consultar_fonte`.
Configuracao: `app/config/agentes/` (config-agentes.json, fichas/). Codigo: `app/agentes.py`.
Testes: `python tests/test_agentes.py`.

- O termo de pesquisa externa e montado so com vocabulario juridico (nunca com texto livre).
- `auditar_citacoes` nunca devolve conferido_oficial; so o advogado confere.
- Nenhum comando de agente grava no banco; gravar exige CONFIRMO_GRAVACAO.
- Fontes sem base local (STF, STJ, TST/TRT9, TRF4, TCE, TSE): consultar o portal oficial.
