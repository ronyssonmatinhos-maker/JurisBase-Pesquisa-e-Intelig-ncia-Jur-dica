# Fonte STF (suprema corte)

Status: ficha de fonte, nao testada.

## Acervo local (somente leitura)
- C:\JURISBASE\fontes do direito\dados\stf\sumulas_stf_completas.json (798 registros: sumulas com situacao e verificacao)
- C:\JURISBASE\fontes do direito\dados\stf\catalogo_sumulas_stf.json (736 registros)
- C:\JURISBASE\fontes do direito\dados\stf\informativos_stf.json (11.633 registros de informativos)
- C:\JURISBASE\fontes do direito\dados\stf\Dados_InformativosSTF.xlsx; SumulasSTJ.pdf; ListadosRepositoriosdeJurisprudenciaCMS.pdf
- C:\JURISBASE\fontes do direito\dados\planalto\ (Constituicao e leis, ver fonte_legislacao)

## Uso
sumulas, repercussao geral, informativos, controle de constitucionalidade

## Origem oficial para conferir
stf.jus.br (API /api/search/search por base: acordaos, decisoes, sumulas, novo_informativo)

## Regras obrigatorias
- Somente leitura: nunca alterar, mover ou gravar arquivos ou bancos.
- Indice local nao e fonte oficial. Toda citacao exige tribunal, orgao, processo, relator, data e URL oficial conferida. Sem isso: NAO_CONFERIDO, nao citar como validado.
- Julgado novo fica NAO_CONFERIDO ate validacao expressa do advogado. Nenhum resultado_confiavel e preenchido automaticamente.
- Nunca citar o JurisBase, o acervo ou a IA como fundamento (ver AGENTS.md).
- Consultas externas sem nomes, CPF, numeros de processo ou dados de cliente.
- Distinguir fato, hipotese e conclusao. Verificar vigencia e situacao (vigente, cancelado, superado) antes de citar.
- Estado: ficha nova, nao testada.
