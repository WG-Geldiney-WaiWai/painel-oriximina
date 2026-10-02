"""Prepara os dados da Calha Norte paraense para o "Painel da Calha Norte".

A Calha Norte do Pará são os 9 municípios ao norte do rio Amazonas: Oriximiná, Óbidos, Terra Santa,
Faro, Alenquer, Curuá, Monte Alegre, Prainha e Almeirim. As fontes são as mesmas dos cartões de
Oriximiná, e os arquivos gerados são os que o painel.py usa:

- regiao_municipios.geojson: contorno de cada município (IBGE, malha municipal)
- regiao_idades.csv: população por faixa de idade de cada município (IBGE, Censo 2022, tabela 9514)
- regiao_dependencia.csv: estimativas por ano e faixa de idade (DATASUS, 2013-2025)
- regiao_emprego.csv: empregos formais por ano e faixa de idade (RAIS 2017-2022)

Rode de novo para atualizar:  python preparar_regiao.py
"""
import glob
import gzip
import io
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request

import pandas as pd
import py7zr
import shapely.geometry
import shapely.geometry.polygon

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

MUNICIPIOS = {   # código do IBGE: nome
    "1505304": "Oriximiná", "1505106": "Óbidos", "1507979": "Terra Santa", "1503002": "Faro",
    "1500404": "Alenquer", "1502855": "Curuá", "1504802": "Monte Alegre", "1506005": "Prainha",
    "1500503": "Almeirim",
}
PASTA_RAIS = r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná\RAIS"
TABNET = "http://tabnet.datasus.gov.br/cgi/tabcgi.exe?ibge/cnv/popsvs2024br.def"
FORM_TABNET = "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?ibge/cnv/popsvs2024br.def"
ANOS_DATASUS = range(2013, 2026)
GRUPOS_EMPREGO = {
    "1.População empregada não idosa": (0, 44),
    "2.População empregada de meia-idade": (45, 64),
    "3.População empregada idosa": (65, 200),
}


def pegar_json(url):
    pedido = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "painel-oriximina"})
    dados = urllib.request.urlopen(pedido, timeout=180).read()
    if dados[:2] == b"\x1f\x8b":
        dados = gzip.decompress(dados)
    return json.loads(dados)


def malha_municipios():
    feicoes = []
    for codigo, nome in MUNICIPIOS.items():
        malha = pegar_json(f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{codigo}"
                           "?formato=application/vnd.geo+json&qualidade=intermediaria")
        for feicao in malha["features"]:
            # O IBGE entrega o contorno no sentido anti-horário; o mapa do Plotly quer o horário
            # (senão pinta o lado de fora do município)
            geometria = shapely.geometry.shape(feicao["geometry"])
            partes = geometria.geoms if geometria.geom_type == "MultiPolygon" else [geometria]
            geometria = shapely.geometry.MultiPolygon([shapely.geometry.polygon.orient(p, sign=-1.0)
                                                       for p in partes])
            feicao["geometry"] = shapely.geometry.mapping(geometria)
            feicao["properties"] = {"codigo": codigo, "nome": nome}
            feicoes.append(feicao)
    with open("regiao_municipios.geojson", "w", encoding="utf-8") as arquivo:
        json.dump({"type": "FeatureCollection", "features": feicoes}, arquivo, ensure_ascii=False)
    print(f"Malha: {len(feicoes)} municípios")


def idades_censo():
    """População por grupo de 5 anos de idade (Censo 2022) somada nas faixas do painel."""
    meta = pegar_json("https://servicodados.ibge.gov.br/api/v3/agregados/9514/metadados")
    idade = next(c for c in meta["classificacoes"] if c["id"] == 287)
    grupos = {}
    for categoria in idade["categorias"]:
        faixa = re.fullmatch(r"(\d+) a (\d+) anos", categoria["nome"])
        if faixa and int(faixa.group(2)) - int(faixa.group(1)) == 4:
            grupos[categoria["id"]] = int(faixa.group(1))
        elif categoria["nome"] == "100 anos ou mais":
            grupos[categoria["id"]] = 100
    url = ("https://servicodados.ibge.gov.br/api/v3/agregados/9514/periodos/2022/variaveis/93"
           f"?localidades=N6[{','.join(MUNICIPIOS)}]"
           f"&classificacao=2[6794]|286[113635]|287[{','.join(str(i) for i in grupos)}]")
    resultado = pegar_json(url)[0]["resultados"]
    linhas = []
    for bloco in resultado:
        # Cada bloco é um grupo de idade; a categoria dele diz qual
        cat_idade = next(c for c in bloco["classificacoes"] if c["id"] == "287")
        inicio = grupos[int(next(iter(cat_idade["categoria"])))]
        for serie in bloco["series"]:
            linhas.append({"codigo": serie["localidade"]["id"], "inicio": inicio,
                           "pessoas": int(serie["serie"]["2022"])})
    df = pd.DataFrame(linhas)

    def soma(de, ate):
        return df[df["inicio"].between(de, ate)].groupby("codigo")["pessoas"].sum()

    idades = pd.DataFrame({
        "0 a 14 anos": soma(0, 14), "15 a 59 anos": soma(15, 59), "60 anos ou mais": soma(60, 200),
        "15 a 64 anos": soma(15, 64), "65 anos ou mais": soma(65, 200),
    }).reset_index()
    idades["Habitantes"] = idades["0 a 14 anos"] + idades["15 a 59 anos"] + idades["60 anos ou mais"]
    idades.insert(1, "Nome", idades["codigo"].map(MUNICIPIOS))
    idades.to_csv("regiao_idades.csv", sep=";", index=False, encoding="utf-8")
    print(idades.to_string(index=False))


def codigos_tabnet():
    """Posição de cada município na lista do TabNet (ex.: "150530 ORIXIMINA" -> 240)."""
    pagina = urllib.request.urlopen(FORM_TABNET, timeout=180).read().decode("latin-1")
    codigos = {}
    for valor, codigo6 in re.findall(r'<OPTION VALUE="(\d+)">(\d{6}) ', pagina):
        for codigo in MUNICIPIOS:
            if codigo.startswith(codigo6):
                codigos[codigo] = valor
    return codigos


def dependencia_datasus():
    linhas = []
    for codigo, valor_tabnet in codigos_tabnet().items():
        campos = [("Linha", "Ano"), ("Coluna", "Idade_simples"), ("Incremento", "População_residente")]
        campos += [("Arquivos", f"pop{ano % 100:02d}.dbf") for ano in ANOS_DATASUS]
        campos += [("SMunicípio", valor_tabnet), ("formato", "prn"), ("mostre", "Mostra")]
        corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode()
        pagina = urllib.request.urlopen(urllib.request.Request(TABNET, corpo), timeout=180).read().decode("latin-1")
        texto = re.search(r"<PRE>(.*?)</PRE>", pagina, re.S | re.I).group(1).strip()
        tabela = pd.read_csv(io.StringIO(texto), sep=";")
        tabela = tabela[tabela["Ano"].astype(str).str.fullmatch(r"\d{4}")]
        idades = [c for c in tabela.columns if c not in ("Ano", "Total")]
        idade_de = {c: 0 if c.startswith("Menos") else int(c.split()[0]) for c in idades}
        for _, linha in tabela.iterrows():
            def soma(de, ate):
                return int(sum(int(linha[c]) for c in idades if de <= idade_de[c] <= ate))
            linhas.append({"codigo": codigo, "Nome": MUNICIPIOS[codigo], "Ano": int(linha["Ano"]),
                           "0 a 14 anos": soma(0, 14), "15 a 64 anos": soma(15, 64),
                           "65 anos ou mais": soma(65, 200)})
        print(f"DATASUS: {MUNICIPIOS[codigo]}")
        time.sleep(1)
    pd.DataFrame(linhas).to_csv("regiao_dependencia.csv", sep=";", index=False, encoding="utf-8")


def emprego_rais():
    """Empregos formais ativos em 31/12 por município e faixa de idade (a RAIS usa o código com 6 dígitos)."""
    codigos6 = {codigo[:6]: codigo for codigo in MUNICIPIOS}
    linhas = []
    for arquivo in sorted(glob.glob(os.path.join(PASTA_RAIS, "*.7z"))):
        ano = int(re.search(r"(20\d\d)", os.path.basename(arquivo)).group(1))
        idades = {codigo: [] for codigo in MUNICIPIOS}
        with tempfile.TemporaryDirectory() as pasta_temp:
            with py7zr.SevenZipFile(arquivo, "r") as z:
                z.extractall(path=pasta_temp)
            for caminho in glob.glob(os.path.join(pasta_temp, "**", "*.*"), recursive=True):
                with open(caminho, encoding="latin-1") as texto:
                    cabecalho = texto.readline().rstrip("\r\n").split(";")
                    col_mun = next(i for i, c in enumerate(cabecalho) if c.strip().lower().startswith("munic"))
                    col_idade = next(i for i, c in enumerate(cabecalho) if c.strip().lower() == "idade")
                    col_ativo = next(i for i, c in enumerate(cabecalho) if "ativo 31/12" in c.lower())
                    for linha in texto:
                        campos = linha.split(";")
                        codigo = codigos6.get(campos[col_mun].strip())
                        if codigo and campos[col_ativo].strip() == "1":
                            idades[codigo].append(int(campos[col_idade]))
        for codigo, lista in idades.items():
            serie = pd.Series(lista, dtype=int)
            linha = {"codigo": codigo, "Nome": MUNICIPIOS[codigo], "Ano": ano, "Empregados": len(serie)}
            for grupo, (de, ate) in GRUPOS_EMPREGO.items():
                linha[grupo] = int(serie.between(de, ate).sum())
            linhas.append(linha)
        print(f"RAIS {ano}: " + ", ".join(f"{MUNICIPIOS[c]} {len(v)}" for c, v in idades.items()))
    pd.DataFrame(linhas).sort_values(["Ano", "codigo"]).to_csv(
        "regiao_emprego.csv", sep=";", index=False, encoding="utf-8")


def main():
    malha_municipios()
    idades_censo()
    dependencia_datasus()
    emprego_rais()


if __name__ == "__main__":
    main()
