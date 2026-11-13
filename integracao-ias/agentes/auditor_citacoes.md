# Auditor de citacoes (verificacao cruzada)

Status: ficha de fonte, nao testada.

## Acervo local (somente leitura)
- Recebe a minuta ou resposta de qualquer outro agente e confere cada citacao.

## Uso
verificar tribunal, orgao, processo, relator, data, URL oficial, vigencia e situacao (vigente, cancelado, superado, afetado)

## Origem oficial para conferir
confirmar na fonte oficial; registrar o que nao foi confirmado como pendencia interna

## Regras obrigatorias
- Somente leitura: nunca alterar, mover ou gravar arquivos ou bancos.
- Indice local nao e fonte oficial. Toda citacao exige tribunal, orgao, processo, relator, data e URL oficial conferida. Sem isso: NAO_CONFERIDO, nao citar como validado.
- Julgado novo fica NAO_CONFERIDO ate validacao expressa do advogado. Nenhum resultado_confiavel e preenchido automaticamente.
- Nunca citar o JurisBase, o acervo ou a IA como fundamento (ver AGENTS.md).
- Consultas externas sem nomes, CPF, numeros de processo ou dados de cliente.
- Distinguir fato, hipotese e conclusao. Verificar vigencia e situacao (vigente, cancelado, superado) antes de citar.
- Estado: ficha nova, nao testada.
