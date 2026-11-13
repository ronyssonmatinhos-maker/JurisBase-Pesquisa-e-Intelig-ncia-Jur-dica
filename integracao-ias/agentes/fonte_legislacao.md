# Fonte de legislacao (federal, estadual, municipal)

Status: ficha de fonte, nao testada.

## Acervo local (somente leitura)
- C:\JURISBASE\fontes do direito\dados\planalto\ (94 arquivos: codigos e leis em HTML e JSON, inclui mediacao.json com 18 normas)
- C:\JURISBASE\fontes do direito\dados\parana\ (2 arquivos de legislacao estadual)
- C:\JURISBASE\julgados\legislacao_matinhos\matinhos.sqlite3 (27 atos, 27 versoes, 2 execucoes; abrir somente com mode=ro)

## Uso
texto e vigencia de normas: CF, CC, CPC, CP, CPP, CDC, CLT, LEF, CTN, ECA, Lei 14.133, Lei 8.666, legislacao eleitoral, municipal

## Origem oficial para conferir
planalto.gov.br, in.gov.br (DOU), diarios oficiais e portal municipal de Matinhos

## Regras obrigatorias
- Somente leitura: nunca alterar, mover ou gravar arquivos ou bancos.
- Indice local nao e fonte oficial. Toda citacao exige tribunal, orgao, processo, relator, data e URL oficial conferida. Sem isso: NAO_CONFERIDO, nao citar como validado.
- Julgado novo fica NAO_CONFERIDO ate validacao expressa do advogado. Nenhum resultado_confiavel e preenchido automaticamente.
- Nunca citar o JurisBase, o acervo ou a IA como fundamento (ver AGENTS.md).
- Consultas externas sem nomes, CPF, numeros de processo ou dados de cliente.
- Distinguir fato, hipotese e conclusao. Verificar vigencia e situacao (vigente, cancelado, superado) antes de citar.
- Estado: ficha nova, nao testada.
