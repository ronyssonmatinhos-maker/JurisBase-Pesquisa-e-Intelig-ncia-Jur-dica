@echo off
REM Roda os casos sinteticos com modelo real (claude -p da sua sessao). Saida em config\agentes\testes\saida-modelo-real-claude_cli.json
cd /d "%~dp0"
set JURISBASE_LLM_PROVIDER=claude_cli
python teste_modelo_real.py > config\agentes\testes\saida-modelo-real-console.txt 2>&1
type config\agentes\testes\saida-modelo-real-console.txt
pause
