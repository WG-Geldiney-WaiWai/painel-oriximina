# Abre o Painel Oriximiná no navegador (http://localhost:8501)
# Uso: clique com o botão direito neste arquivo > "Executar com o PowerShell",
# ou, no terminal do VS Code aberto nesta pasta:  .\iniciar.ps1
Set-Location $PSScriptRoot
python scripts/ajustar_streamlit.py   # aba do navegador com o nome e o brasão do painel
python -m streamlit run painel.py
