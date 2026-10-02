# Abre o Painel Oriximiná no navegador (http://localhost:8501)
# Uso: clique com o botão direito neste arquivo > "Executar com o PowerShell",
# ou, no terminal do VS Code aberto nesta pasta:  .\iniciar.ps1
Set-Location $PSScriptRoot
python -m streamlit run painel.py
