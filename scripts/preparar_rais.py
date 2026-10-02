"""Prepara os dados de emprego por idade de Oriximiná (RAIS 2017-2022) para o painel.

A RAIS (Relação Anual de Informações Sociais, Ministério do Trabalho) traz todos os
vínculos de emprego formal do país. Este script lê os arquivos grandes uma vez e
gera um arquivo pequeno que o painel.py usa:

- dados_emprego_idade_oriximina.csv: empregados em 31/12 de cada ano por faixa de idade

Rode de novo só se trocar os arquivos da RAIS:  python preparar_rais.py
"""
import glob
import os
import re
import tempfile

import pandas as pd
import py7zr

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_RAIS = r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná\RAIS"
CODIGO_ORIXIMINA = "150530"   # a RAIS usa o código do IBGE sem o último dígito

# Mesmas faixas do painel de Taipei (aging_workforce_trend)
GRUPOS = {
    "1.População empregada não idosa": (0, 44),
    "2.População empregada de meia-idade": (45, 64),
    "3.População empregada idosa": (65, 200),
}


def ler_ano(arquivo_7z):
    """Lê um arquivo .7z da RAIS e devolve a idade de cada vínculo ativo em 31/12 em Oriximiná."""
    partes = []
    # Descompacta numa pasta temporária (o texto tem mais de 1 GB) e apaga depois
    with tempfile.TemporaryDirectory() as pasta_temp:
        with py7zr.SevenZipFile(arquivo_7z, "r") as z:
            z.extractall(path=pasta_temp)
        for caminho in glob.glob(os.path.join(pasta_temp, "**", "*.*"), recursive=True):
            with open(caminho, encoding="latin-1") as texto:
                cabecalho = texto.readline().rstrip("\r\n").split(";")
                col_mun = next(i for i, c in enumerate(cabecalho) if c.strip().lower().startswith("munic"))
                col_idade = next(i for i, c in enumerate(cabecalho) if c.strip().lower() == "idade")
                col_ativo = next(i for i, c in enumerate(cabecalho) if "ativo 31/12" in c.lower())
                # Milhões de linhas: filtra Oriximiná linha a linha, sem carregar tudo na memória
                for linha in texto:
                    campos = linha.split(";")
                    if campos[col_mun].strip() == CODIGO_ORIXIMINA and campos[col_ativo].strip() == "1":
                        partes.append(int(campos[col_idade]))
    return partes


def main():
    linhas = []
    for arquivo in sorted(glob.glob(os.path.join(PASTA_RAIS, "*.7z"))):
        ano = int(re.search(r"(20\d\d)", os.path.basename(arquivo)).group(1))
        idades = pd.Series(ler_ano(arquivo))
        linha = {"Ano": ano, "Empregados": len(idades)}
        for grupo, (de, ate) in GRUPOS.items():
            linha[grupo] = int(idades.between(de, ate).sum())
        linhas.append(linha)
        print(linha)

    df = pd.DataFrame(linhas).sort_values("Ano")
    df.to_csv("dados_emprego_idade_oriximina.csv", sep=";", index=False, encoding="utf-8")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
