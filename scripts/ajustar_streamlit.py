"""Troca o nome "Streamlit" e a coroa da aba do navegador pelo nome e pelo brasão do painel.

Ao abrir ou atualizar a página, o navegador mostra primeiro a página inicial do próprio Streamlit (com o
título "Streamlit" e a coroa) e só depois o painel troca o título e o ícone. Este script muda essa página
inicial no Streamlit instalado, para a aba já abrir com "Painel Oriximiná" e o brasão.

O Streamlit manda o navegador guardar o favicon.png por um ano; por isso o endereço do ícone ganha um
"?v=..." que muda junto com a imagem, e o navegador busca o brasão novo em vez de usar a coroa guardada.

Roda sozinho no Docker e nos atalhos iniciar.ps1 / iniciar.sh. Precisa rodar de novo depois de atualizar o
Streamlit (pip install -U streamlit); rodar mais de uma vez não faz mal.
Uso:  python scripts/ajustar_streamlit.py
"""
import glob
import hashlib
import os
import re
import shutil

import streamlit

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ICONE = os.path.join(PASTA_PROJETO, "imagens", "icone.png")
TITULO = "Painel Oriximiná"
PASTA_STATIC = os.path.join(os.path.dirname(streamlit.__file__), "static")


def trocar(caminho, mudanca):
    with open(caminho, encoding="utf-8") as arquivo:
        texto = arquivo.read()
    novo = mudanca(texto)
    if novo != texto:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(novo)


def main():
    with open(ICONE, "rb") as arquivo:
        versao = hashlib.md5(arquivo.read()).hexdigest()[:8]
    endereco = lambda texto: re.sub(r"\./favicon\.png(\?v=[0-9a-f]+)?", f"./favicon.png?v={versao}", texto)
    trocar(os.path.join(PASTA_STATIC, "index.html"),
           lambda texto: endereco(re.sub(r"<title>.*?</title>", f"<title>{TITULO}</title>", texto, count=1)))
    # O Streamlit também põe o ícone padrão pelo JavaScript, ao conectar, antes de o painel mandar o dele
    for js in glob.glob(os.path.join(PASTA_STATIC, "static", "js", "index.*.js")):
        trocar(js, endereco)
    shutil.copyfile(ICONE, os.path.join(PASTA_STATIC, "favicon.png"))
    print(f"Aba do navegador: \"{TITULO}\" e o brasão ({PASTA_STATIC})")


if __name__ == "__main__":
    main()
