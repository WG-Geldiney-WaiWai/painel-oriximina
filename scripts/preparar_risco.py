"""Prepara o cartão "Áreas de risco de desastre" (como o "Localizações de risco de taludes" do Taipei), no
painel "Uma cidade resistente a desastres".

Fonte: os estudos do Serviço Geológico do Brasil (SGB/CPRM) que marcaram os setores de risco alto e muito
alto de Oriximiná, com os arquivos de mapa (shapefile):
- 2012 (atualizado em 2018): "Ação emergencial para delimitação de áreas em alto e muito alto risco a
  enchentes e movimentos de massa" – https://rigeo.sgb.gov.br/handle/doc/20756
- 2023: "Avaliação técnica pós-desastre: Oriximiná, Pará" – https://rigeo.sgb.gov.br/handle/doc/23682
Baixe os arquivos "SIG" das duas páginas e descompacte em PASTA_FONTES/SGB_risco (sig2012/ e sig2023/).
Quando o mesmo lugar aparece nos dois estudos (a menos de DISTANCIA_MESMO_LUGAR metros), fica o mais novo.

- comp_332.csv: setores, casas e pessoas em risco por tipo de risco
- comp_332_mapa.csv: um ponto por setor de risco, para o mapa e para a "Comparação de mapas"

Rode de novo para atualizar:  python preparar_risco.py
"""
import json
import os

import geopandas as gpd
import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
ESTUDOS = {   # ano do estudo -> shapefile dos setores
    2012: os.path.join(PASTA_FONTES, "SGB_risco", "sig2012", "Shapefile", "PA_ORIXIMI_SR_CPRM.shp"),
    2023: os.path.join(PASTA_FONTES, "SGB_risco", "sig2023", "SIG", "shp", "PA_ORIXIMI_SR_SGB.shp"),
}
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
DISTANCIA_MESMO_LUGAR = 200   # metros
TIPOS = {"Inundação": "Inundação (cheia do rio)", "Deslizamento": "Deslizamento de encosta",
         "Erosão": "Erosão (ravinas e voçorocas)"}
SETORES, CASAS, PESSOAS = "Setores de risco", "Casas em risco", "Pessoas em risco"


def ler_setores():
    partes = []
    for ano, caminho in ESTUDOS.items():
        setores = gpd.read_file(caminho).to_crs(31981)
        setores["estudo"] = ano
        setores["data"] = pd.to_datetime(setores["DATA_SETOR"])
        setores["geometry"] = setores.geometry.centroid
        partes.append(setores[["estudo", "data", "LOCAL", "TIPOLO_G1", "GRAU_RISCO", "NUM_EDIF", "NUM_PESS",
                               "DESCRICAO", "geometry"]])
    todos = pd.concat(partes, ignore_index=True).sort_values("data", ascending=False)
    # O mesmo lugar nos dois estudos: fica o mais novo (a lista está do mais novo para o mais velho)
    ficam = []
    for i, setor in todos.iterrows():
        if all(setor.geometry.distance(todos.loc[j].geometry) > DISTANCIA_MESMO_LUGAR for j in ficam):
            ficam.append(i)
    print(f"{len(todos)} setores nos estudos; {len(todos) - len(ficam)} repetidos (o mesmo lugar)")
    return gpd.GeoDataFrame(todos.loc[ficam], crs=31981).to_crs(4326)


def sem_virgula(texto):
    """O leitor de tabelas do painel descobre o separador sozinho: vírgula no texto atrapalha."""
    texto = str(texto).replace("Birro ", "Bairro ")   # erro de digitação no arquivo do SGB
    return " ".join(texto.replace(",", " /").split())


def main():
    setores = ler_setores()
    setores["tipo"] = setores["TIPOLO_G1"].map(TIPOS)
    setores[CASAS] = pd.to_numeric(setores["NUM_EDIF"]).fillna(0).astype(int)
    setores[PESSOAS] = pd.to_numeric(setores["NUM_PESS"]).fillna(0).astype(int)

    # Pessoas primeiro: é o número que o cartão mostra grande ("1.680 pessoas")
    tabela = (setores.groupby("tipo").agg(**{PESSOAS: (PESSOAS, "sum"), CASAS: (CASAS, "sum"),
                                             SETORES: ("tipo", "size")})
              .reindex(TIPOS.values(), fill_value=0).rename_axis("Tipo de risco").reset_index())
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_332.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    mapa = pd.DataFrame({
        "Local": [sem_virgula(l) for l in setores["LOCAL"]],
        "Latitude": setores.geometry.y.round(6), "Longitude": setores.geometry.x.round(6),
        "Tipo de risco": setores["tipo"], "Grau de risco": setores["GRAU_RISCO"],
        CASAS: setores[CASAS], PESSOAS: setores[PESSOAS],
        "Estudo": [f"SGB {d:%m/%Y}" for d in setores["data"]],
    })
    mapa.to_csv(os.path.join(PASTA_COMPONENTES, "comp_332_mapa.csv"), sep=";", index=False, encoding="utf-8")
    print(mapa.to_string(index=False))

    def fmt(n):
        return f"{int(n):,}".replace(",", ".")
    total = tabela.set_index("Tipo de risco")
    muito_alto = int((setores["GRAU_RISCO"] == "Muito alto").sum())
    componente = {
        "id": 332, "titulo": "Áreas de risco de desastre", "fonte": "Serviço Geológico do Brasil (SGB/CPRM)",
        "atualizacao": "Estudos de 2012, 2018 e 2023", "icone": "warning", "area": "Sede de Oriximiná",
        "resumo": "Os lugares da cidade com risco alto de inundação, deslizamento de encosta e erosão, e quantas pessoas moram neles.",
        "descricao": (
            f"Mostra os {len(setores)} setores de risco alto ou muito alto da sede de Oriximiná marcados pelo "
            "Serviço Geológico do Brasil nos estudos de 2012 (atualizado em 2018) e de 2023, depois das chuvas "
            f"daquele ano. {muito_alto} deles são de risco muito alto. Moram neles cerca de "
            f"{fmt(total[PESSOAS].sum())} pessoas, em {fmt(total[CASAS].sum())} casas, sobretudo nas encostas "
            "da orla do Centro, de Santa Terezinha, São José, Fátima e Santa Luzia, onde o barranco pode "
            f"deslizar ({fmt(total.loc[TIPOS['Deslizamento'], PESSOAS])} pessoas), e na parte baixa do Centro, "
            f"que a cheia do rio Trombetas inunda ({fmt(total.loc[TIPOS['Inundação'], PESSOAS])} pessoas). Os "
            "outros setores são ravinas abertas pela água da chuva sem drenagem, que avançam sobre as casas "
            "nos bairros novos. Os números de casas e pessoas são as estimativas dos geólogos na visita. "
            "Quando o mesmo lugar aparece nos dois estudos, vale o mais novo. O mapa (e a Comparação de mapas) "
            "mostra cada setor."),
        "exemplo": ("Mostra à Defesa Civil onde fazer vistorias, obras de drenagem e contenção de encostas e "
                    "onde avisar os moradores antes das chuvas e das cheias."),
        "tipos": ["numero"],   # (em barras, 1 setor e 1.680 pessoas ficariam na mesma escala)
        "cores": ["#24B0DD", "#F49F36", "#F65658"],
        "unidade": "pessoas", "meta": None, "maximo": None,
        "links": [{"nome": "SGB – Ação emergencial: áreas de risco de Oriximiná (2012)",
                   "url": "https://rigeo.sgb.gov.br/handle/doc/20756"},
                  {"nome": "SGB – Avaliação técnica pós-desastre: Oriximiná (2023)",
                   "url": "https://rigeo.sgb.gov.br/handle/doc/23682"}],
        "colaboradores": [], "mapa": {"tipo": "pontos", "nome": "Áreas de risco de desastre", "cor": "#F65658"},
        "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_332"] = componente
    painel = config.get("paineis_publicos", {}).get("desastres")
    if painel and "comp_332" not in painel["cartoes"]:
        painel["cartoes"].append("comp_332")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Uma cidade resistente a desastres:",
          painel["cartoes"] if painel else "não encontrado (rode preparar_rio.py)")


if __name__ == "__main__":
    main()
