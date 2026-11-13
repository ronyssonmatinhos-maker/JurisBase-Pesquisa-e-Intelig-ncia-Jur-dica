@echo off
REM Executa a bateria no Python NATIVO do Windows (cmd). Saida em config\agentes\testes\saida-testes-windows.txt
cd /d "%~dp0"
set ROBO_JULGADOS_DB=C:\JURISBASE\julgados\base\julgados.db
python --version > config\agentes\testes\saida-testes-windows.txt 2>&1
python -m unittest discover -s tests -v >> config\agentes\testes\saida-testes-windows.txt 2>&1
type config\agentes\testes\saida-testes-windows.txt | findstr /C:"Ran " /C:"OK" /C:"FAILED"
