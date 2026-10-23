"""Troca o nome "Streamlit" e a coroa da aba do navegador pelo nome e pelo brasão do painel.

Ao abrir ou atualizar a página, o navegador mostra primeiro a página inicial do próprio Streamlit (com o
título "Streamlit" e a coroa) e só depois o painel troca o título e o ícone. Este script muda essa página
inicial no Streamlit instalado, para a aba já abrir com "Painel Oriximiná" e o brasão.

O Streamlit manda o navegador guardar o favicon.png por um ano; por isso o endereço do ícone ganha um
"?v=..." que muda junto com a imagem, e o navegador busca o brasão novo em vez de usar a coroa guardada.

Também põe na página inicial um pedacinho (entre os comentários "painel-oriximina") que:
- troca de volta pelo brasão qualquer ícone sem o "?v=..." (é o que faz o JavaScript antigo do Streamlit que o
  navegador ainda guarda; sem isso a coroa aparecia por um segundo em quem já tinha aberto o painel);
- esconde a barra cinza "carregando" do Streamlit e deixa o fundo escuro desde o início (a barra aparecia e
  sumia, e a tela parecia pular).

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
COR_FUNDO = "#090909"   # a mesma do painel (.streamlit/config.toml)
PASTA_STATIC = os.path.join(os.path.dirname(streamlit.__file__), "static")
INICIO, FIM = "<!-- painel-oriximina -->", "<!-- /painel-oriximina -->"
PEDACO = r"""<!-- painel-oriximina -->
    <style>
      html, body { background-color: COR_FUNDO; }
      [data-testid="stAppSkeleton"] { display: none !important; }
    </style>
    <script>
      (() => {
        const BRASAO = "./favicon.png?v=VERSAO";
        const corrigir = () => document.querySelectorAll('link[rel*="icon"]').forEach(l => {
          if (/favicon\.png$/.test(l.getAttribute("href") || "")) l.setAttribute("href", BRASAO);
        });
        new MutationObserver(corrigir).observe(document.head,
          {childList: true, subtree: true, attributes: true, attributeFilter: ["href"]});
        corrigir();
      })();
    </script>
    <!-- /painel-oriximina -->
"""


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
    pedaco = PEDACO.replace("COR_FUNDO", COR_FUNDO).replace("VERSAO", versao)

    def endereco(texto):
        return re.sub(r"\./favicon\.png(\?v=[0-9a-f]+)?", f"./favicon.png?v={versao}", texto)

    def pagina_inicial(texto):
        texto = re.sub(r"<title>.*?</title>", f"<title>{TITULO}</title>", texto, count=1)
        texto = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIM) + r"\s*", "", texto, flags=re.S)
        texto = endereco(texto)   # antes de pôr o pedaço: o "favicon\.png$" dele não pode ganhar "?v="
        return texto.replace("</head>", pedaco + "  </head>", 1)

    trocar(os.path.join(PASTA_STATIC, "index.html"), pagina_inicial)
    # O Streamlit também põe o ícone padrão pelo JavaScript, ao conectar, antes de o painel mandar o dele
    for js in glob.glob(os.path.join(PASTA_STATIC, "static", "js", "index.*.js")):
        trocar(js, endereco)
    shutil.copyfile(ICONE, os.path.join(PASTA_STATIC, "favicon.png"))
    print(f"Aba do navegador: \"{TITULO}\" e o brasão ({PASTA_STATIC})")


if __name__ == "__main__":
    main()
