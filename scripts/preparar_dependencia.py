"""Prepara a razão de dependência e o índice de envelhecimento de Oriximiná, ano a ano.

Fonte: Ministério da Saúde / DATASUS - "Estudo de Estimativas Populacionais por Município,
Idade e Sexo 2000-2025" (TabNet popsvs2024br). São estimativas para cada ano; para 2022 a
população estimada (71.692) é maior que a contada pelo Censo (68.294).
O script consulta o TabNet, guarda a tabela original (população por ano e idade simples)
e gera o arquivo pequeno que o painel.py usa:

- dados_dependencia_oriximina.csv: população por grande faixa de idade e os dois indicadores

Rode de novo para atualizar:  python preparar_dependencia.py
"""
import io
import re
import urllib.parse
import urllib.request

import pandas as pd
import os

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

ENDERECO_TABNET = "http://tabnet.datasus.gov.br/cgi/tabcgi.exe?ibge/cnv/popsvs2024br.def"
CODIGO_ORIXIMINA_TABNET = "240"   # posição de "150530 ORIXIMINA" na lista de municípios do TabNet
ANOS = range(2013, 2026)
ARQ_ORIGINAL = r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná\datasus_pop_oriximina_idade.csv"


def baixar_tabela():
    """População de Oriximiná por ano (linhas) e idade simples (colunas)."""
    campos = [("Linha", "Ano"), ("Coluna", "Idade_simples"), ("Incremento", "População_residente")]
    campos += [("Arquivos", f"pop{ano % 100:02d}.dbf") for ano in ANOS]
    campos += [("SMunicípio", CODIGO_ORIXIMINA_TABNET), ("formato", "prn"), ("mostre", "Mostra")]
    corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode()
    resposta = urllib.request.urlopen(urllib.request.Request(ENDERECO_TABNET, corpo), timeout=180)
    pagina = resposta.read().decode("latin-1")
    texto = re.search(r"<PRE>(.*?)</PRE>", pagina, re.S | re.I).group(1).strip()
    with open(ARQ_ORIGINAL, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    return pd.read_csv(io.StringIO(texto), sep=";")


def main():
    tabela = baixar_tabela()
    tabela = tabela[tabela["Ano"].astype(str).str.fullmatch(r"\d{4}")]   # tira a linha "Total"
    idades = [c for c in tabela.columns if c not in ("Ano", "Total")]
    idade_de = {c: 0 if c.startswith("Menos") else int(c.split()[0]) for c in idades}   # "80 anos e mais" -> 80

    def soma(de, ate):
        return tabela[[c for c in idades if de <= idade_de[c] <= ate]].astype(int).sum(axis=1)

    dados = pd.DataFrame({
        "Ano": tabela["Ano"].astype(int),
        "0 a 14 anos": soma(0, 14),
        "15 a 64 anos": soma(15, 64),
        "65 anos ou mais": soma(65, 200),
        "População total": tabela["Total"].astype(int),
    })
    # Mesmas fórmulas do Taipei e do IBGE
    dados["Razão de dependência"] = ((dados["0 a 14 anos"] + dados["65 anos ou mais"])
                                     / dados["15 a 64 anos"] * 100).round(1)
    dados["Índice de envelhecimento"] = (dados["65 anos ou mais"] / dados["0 a 14 anos"] * 100).round(1)
    dados.to_csv("dados_dependencia_oriximina.csv", sep=";", index=False, encoding="utf-8")
    print(dados.to_string(index=False))


if __name__ == "__main__":
    main()
