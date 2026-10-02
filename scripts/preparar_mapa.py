"""Prepara os pontos de escolas e unidades de saúde de Oriximiná para a página de mapa.

Fonte: IBGE - Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE 2022), que traz
a localização de cada endereço visitado no Censo e a espécie dele (domicílio, ensino, saúde...).
Gera o arquivo pequeno que o painel.py usa:

- pontos_oriximina.csv: tipo, nome, localidade, latitude e longitude

Rode de novo só se trocar o arquivo do CNEFE:  python preparar_mapa.py
"""
import pandas as pd
import os

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

ARQ_CNEFE = r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná\CNEFE\1505304_ORIXIMINA.csv"
ESPECIES = {"4": "Estabelecimento de ensino", "5": "Estabelecimento de saúde"}


def main():
    cnefe = pd.read_csv(ARQ_CNEFE, sep=";", dtype=str)
    pontos = cnefe[cnefe["COD_ESPECIE"].isin(list(ESPECIES))].copy()
    pontos["Tipo"] = pontos["COD_ESPECIE"].map(ESPECIES)
    pontos["Nome"] = pontos["DSC_ESTABELECIMENTO"].fillna("Sem nome no cadastro").str.title()
    pontos["Localidade"] = pontos["DSC_LOCALIDADE"].fillna("").str.title()
    pontos["Latitude"] = pontos["LATITUDE"].astype(float)
    pontos["Longitude"] = pontos["LONGITUDE"].astype(float)
    pontos = pontos[["Tipo", "Nome", "Localidade", "Latitude", "Longitude"]]
    pontos.to_csv("pontos_oriximina.csv", sep=";", index=False, encoding="utf-8")
    print(pontos["Tipo"].value_counts().to_string())


if __name__ == "__main__":
    main()
