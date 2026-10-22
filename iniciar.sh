#!/usr/bin/env bash
# Abre o Painel Oriximiná no navegador (http://localhost:8501) — Linux e Mac
# Uso: no terminal, nesta pasta:  bash iniciar.sh
# (ou torne executável uma vez com  chmod +x iniciar.sh  e depois rode  ./iniciar.sh)
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
    python3 scripts/ajustar_streamlit.py   # aba do navegador com o nome e o brasão do painel
    python3 -m streamlit run painel.py
else
    python scripts/ajustar_streamlit.py
    python -m streamlit run painel.py
fi
