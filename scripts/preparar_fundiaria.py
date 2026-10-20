"""Prepara o cartão "Situação fundiária" de Oriximiná (como o "Terras públicas" do Taipei), no painel
"Planejamento urbano".

O Taipei mostra de quem são as terras públicas da cidade. Oriximiná não publica o cadastro dos terrenos da
Prefeitura; o cartão mostra de quem é a terra do município inteiro, com o Cadastro Nacional de Florestas
Públicas (CNFP, Serviço Florestal Brasileiro). O CNFP junta as terras indígenas (FUNAI), as unidades de
conservação (ICMBio e Ideflor-Bio), os assentamentos e territórios quilombolas (INCRA) e as glebas públicas
(INCRA e Iterpa) sem contar duas vezes: onde uma área fica dentro da outra, ele cria uma categoria própria
("TI / FLOTA"). O que sobra fora do CNFP é a cidade, as propriedades privadas e as áreas sem floresta.

- comp_313.csv: km² de Oriximiná em cada situação (as linhas somam a área do município)

As fazendas privadas com georreferenciamento certificado vêm do SIGEF (INCRA), só para a descrição: as
"glebas" que aparecem no SIGEF são terra pública e ficam de fora dessa conta.

Os arquivos baixados (CNFP de uns 230 MB e SIGEF do Pará de uns 65 MB) ficam na pasta das fontes, em
AreasProtegidas; o contorno do município vem de PA_Municipios_2025.

Rode de novo para atualizar:  python preparar_fundiaria.py
"""
import glob
import json
import os
import subprocess
import warnings
import zipfile

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA = os.path.join(PASTA_FONTES, "AreasProtegidas")
CODIGO_IBGE = "1505304"
LIMITES = (-58.95, -3.4, -54.8, 2.6)   # retângulo em volta de Oriximiná (lon/lat)
ALBERS = "+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +ellps=GRS80 +units=m"   # área igual
# CNFP 2025 no portal de mapas do Serviço Florestal (item "Cadastro Nacional de Florestas Públicas 2025")
URL_CNFP = "https://mapas.florestal.gov.br/portal/sharing/rest/content/items/2b752dfbf9254920bf8990ce363918af/data"
URL_SIGEF = "https://certificacao.incra.gov.br/csv_shp/zip/Sigef%20Brasil_PA.zip"

# Situações do cartão, a partir da "classe" do CNFP (a ordem é a das linhas)
# (nomes curtos: os compridos apertavam as barras; e sem vírgula: o painel adivinha o separador do CSV)
SITUACOES = [
    ("UCs estaduais", lambda c: c == "UCEST"),
    ("Terras indígenas", lambda c: c == "TI"),
    ("TIs e outras áreas dentro de UCs", lambda c: "/" in c and "UC" in c),
    ("UCs federais", lambda c: c == "UCFED"),
    ("Assentamentos e quilombos", lambda c: c in ("ASSENTFED", "ASSENTEST", "TRQ")),
    ("Terra pública sem destinação", lambda c: c.startswith("GLEBA")),
]
FORA = "Fora das florestas públicas"


def baixar(url, destino):
    """O servidor às vezes corta no meio: continua de onde parou até o ZIP ficar inteiro."""
    for _ in range(15):
        if os.path.exists(destino) and zipfile.is_zipfile(destino):
            return destino
        print("baixando", url, flush=True)
        subprocess.run(["curl", "-s", "-L", "-C", "-", "--max-time", "900", "-o", destino, url], check=False)
    raise RuntimeError(f"Não consegui baixar {url} inteiro; rode de novo para continuar")


def recorta(g, oriximina):
    g = g.to_crs(ALBERS)
    g["geometry"] = g.buffer(0)   # conserta polígonos com defeito de desenho
    g = g[g.intersects(oriximina)].copy()
    g["geometry"] = g.intersection(oriximina)
    g["km2"] = g.area / 1e6
    return g[g["km2"] > 0.01]


def main():
    os.makedirs(PASTA, exist_ok=True)
    municipios = gpd.read_file(glob.glob(os.path.join(PASTA_FONTES, "PA_Municipios_2025", "*.shp"))[0])
    oriximina = municipios[municipios["CD_MUN"] == CODIGO_IBGE].to_crs(ALBERS).union_all()
    area_mun = oriximina.area / 1e6

    arq_cnfp = baixar(URL_CNFP, os.path.join(PASTA, "CNFP_2025.zip"))
    shp = next(n for n in zipfile.ZipFile(arq_cnfp).namelist() if n.endswith(".shp"))
    cnfp = recorta(gpd.read_file(f"zip://{arq_cnfp}!{shp}", bbox=LIMITES), oriximina)
    linhas, usadas = [], set()
    for nome, regra in SITUACOES:
        escolhidas = cnfp[cnfp["classe"].map(lambda c: regra(str(c)))]
        usadas |= set(escolhidas.index)
        linhas.append({"Situação": nome, "Área (km²)": escolhidas["km2"].sum()})
    sobra = cnfp.drop(index=list(usadas))
    if len(sobra):   # classe nova que o script ainda não conhece: não some da conta
        linhas.append({"Situação": "Outras florestas públicas", "Área (km²)": sobra["km2"].sum()})
        print("classes sem situação:", sorted(sobra["classe"].unique()))
    florestas_publicas = gpd.GeoSeries([cnfp.union_all()], crs=ALBERS).area.sum() / 1e6
    linhas.append({"Situação": FORA, "Área (km²)": area_mun - florestas_publicas})
    df = pd.DataFrame(linhas)
    df = df[df["Área (km²)"] >= 0.5]
    df["Área (km²)"] = df["Área (km²)"].round().astype(int)
    df.to_csv(os.path.join(PASTA_COMPONENTES, "comp_313.csv"), sep=";", index=False, encoding="utf-8")
    print(df.to_string(index=False), "\nsoma:", df["Área (km²)"].sum(), "| município:", round(area_mun))

    # Fazendas privadas certificadas no SIGEF (as "glebas" do SIGEF são terra pública)
    arq_sigef = baixar(URL_SIGEF, os.path.join(PASTA, "Sigef_Brasil_PA.zip"))
    shp = next(n for n in zipfile.ZipFile(arq_sigef).namelist() if n.endswith(".shp"))
    sigef = recorta(gpd.read_file(f"zip://{arq_sigef}!{shp}", bbox=LIMITES, encoding="latin1"), oriximina)
    privadas = sigef[~sigef["nome_area"].astype(str).str.upper().str.contains("GLEBA")]
    km_privadas = gpd.GeoSeries([privadas.union_all()], crs=ALBERS).area.sum() / 1e6 if len(privadas) else 0

    def km2(n):
        return f"{n:,.0f}".replace(",", ".")
    valor = dict(zip(df["Situação"], df["Área (km²)"]))
    sem_destino = valor.get("Terra pública sem destinação", 0)
    componente = {
        "id": 313, "titulo": "Situação fundiária", "fonte": "Serviço Florestal Brasileiro | CNFP 2025",
        "atualizacao": "2025", "icone": "bar_chart", "area": "Município de Oriximiná",
        "resumo": "De quem é a terra de Oriximiná: unidades de conservação, terras indígenas, quilombos, glebas públicas.",
        "descricao": (
            f"Mostra de quem é a terra dos {km2(area_mun)} km² de Oriximiná, segundo o Cadastro Nacional de "
            f"Florestas Públicas (Serviço Florestal Brasileiro, 2025), que junta as áreas da FUNAI, do ICMBio, do "
            f"Ideflor-Bio, do INCRA e do Iterpa sem contar duas vezes (as linhas somam a área do município). As "
            f"florestas públicas ocupam {km2(florestas_publicas)} km² ({florestas_publicas / area_mun:.0%}). Onde "
            "uma terra indígena, um quilombo ou um assentamento fica dentro de uma unidade de conservação, a área "
            f"conta uma vez só, na linha \"TIs e outras áreas dentro de UCs\" (TI é terra indígena; UC, unidade de "
            "conservação: estação ecológica, reserva biológica, floresta nacional ou estadual). "
            f"Há {km2(sem_destino)} km² de terra pública sem destinação (glebas "
            "arrecadadas pela União e pelo Estado que ainda não viraram unidade de conservação, terra indígena ou "
            f"assentamento). Fora das florestas públicas ficam a cidade, as áreas sem floresta e as propriedades "
            f"privadas: as fazendas com georreferenciamento certificado no SIGEF (INCRA) somam só {km2(km_privadas)} "
            "km². O cartão do Taipei mostra os terrenos públicos da cidade por dono; Oriximiná não publica o "
            "cadastro dos terrenos da Prefeitura."),
        "exemplo": ("Mostra que quase toda a terra do município é pública e tem regras próprias: o crescimento da "
                    "cidade, a regularização de terrenos e os projetos no interior precisam ser combinados com a "
                    "FUNAI, o ICMBio, o Ideflor-Bio, o INCRA e o Iterpa."),
        "tipos": ["barras", "mapa_arvore"],
        "cores": ["#2E7D32", "#F49F36", "#c18ad8", "#56B96D", "#F8CF58", "#F65658", "#a0b8e8"],
        "unidade": "km²", "meta": None, "maximo": None,
        "links": [{"nome": "Serviço Florestal Brasileiro – Cadastro Nacional de Florestas Públicas 2025",
                   "url": "https://www.gov.br/florestal/pt-br/assuntos/cadastro-nacional-de-florestas-publicas/"
                          "cadastro-nacional-de-florestas-publicas-atualizacao-2025"},
                  {"nome": "INCRA – Acervo fundiário (SIGEF)", "url": "https://certificacao.incra.gov.br"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_313"] = componente
    planejamento = config["paineis_publicos"].setdefault(
        "planejamento", {"titulo": "Planejamento urbano", "icone": "home_work", "cartoes": [], "grupo": "Painel de Oriximiná"})
    if "comp_313" not in planejamento["cartoes"]:
        planejamento["cartoes"].append("comp_313")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print(f"fazendas privadas certificadas: {km_privadas:.0f} km²; painel Planejamento urbano:", planejamento["cartoes"])


if __name__ == "__main__":
    main()
