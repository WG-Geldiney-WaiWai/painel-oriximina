"""Prepara os cartões de áreas verdes da sede de Oriximiná (como o "Parques e áreas verdes" do Taipei), no
painel "Planejamento urbano".

A Prefeitura não publica o cadastro das praças e parques. São dois cartões que se completam:

- comp_314.csv: parques, praças, campos e áreas de lazer desenhados no OpenStreetMap, em hectares. O mapa é
  feito por voluntários e está incompleto (faltam áreas e a maioria não tem nome); quando ele for completado,
  rodar este script de novo atualiza o cartão
- comp_315.csv: cobertura do chão em cada bairro da sede (árvores, gramado e arbustos, área construída, água),
  em hectares, pelo ESA WorldCover 2021 (Agência Espacial Europeia): imagem de satélite em quadrados de 10 m,
  que vê toda a vegetação, inclusive quintais, terrenos e matas que não são praça

O quadro do WorldCover (uns 35 MB) fica na pasta das fontes, em WorldCover. Precisa do rasterio
(pip install rasterio).

Rode de novo para atualizar:  python preparar_areas_verdes.py
"""
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from collections import defaultdict

import pandas as pd
import rasterio
from pyproj import Geod
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_BAIRROS = os.path.join(PASTA_PROJETO, "dados", "oriximina_bairros.geojson")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
PASTA_WORLDCOVER = os.path.join(
    os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná"), "WorldCover")
# Quadro de 3° × 3° que cobre a sede (canto de baixo à esquerda: 3° S, 57° O)
NOME_WORLDCOVER = "ESA_WorldCover_10m_2021_v200_S03W057_Map.tif"
URL_WORLDCOVER = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{NOME_WORLDCOVER}"
SERVIDORES_OSM = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
                  "https://overpass.private.coffee/api/interpreter"]

TIPOS_OSM = {   # etiqueta do OpenStreetMap: nome do tipo no cartão
    "park": "Praças e parques", "garden": "Praças e parques", "square": "Praças e parques",
    "pitch": "Campos e quadras", "playground": "Parquinhos", "stadium": "Estádio e clubes",
    "sports_centre": "Estádio e clubes", "recreation_ground": "Áreas de lazer",
    "nature_reserve": "Áreas de preservação", "grass": "Gramados", "village_green": "Gramados",
}
# Nomes com erro de digitação ou em inglês no OpenStreetMap (o nome usado na cidade)
NOMES_CORRIGIDOS = {"Parque de Esposição": "Parque de Exposição", "Centenário Park": "Praça do Centenário",
                    "Praça Santo Antonio": "Praça Santo Antônio"}
CLASSES_SATELITE = {   # código do WorldCover: coluna do cartão
    10: "Árvores", 20: "Gramado e arbustos", 30: "Gramado e arbustos", 50: "Área construída",
    80: "Água e áreas alagadas", 90: "Água e áreas alagadas", 40: "Outros", 60: "Outros",
}
GEOD = Geod(ellps="WGS84")


def hectares(forma):
    return abs(GEOD.geometry_area_perimeter(forma)[0]) / 1e4


def areas_osm(caixa):
    """Polígonos de lazer e áreas verdes do OpenStreetMap na caixa (sul, oeste, norte, leste)."""
    filtro = "|".join(TIPOS_OSM)
    consulta = (f'[out:json][timeout:90];(nwr["leisure"~"{filtro}"]({caixa});nwr["place"="square"]({caixa});'
                f'nwr["landuse"~"grass|village_green|recreation_ground"]({caixa}););out geom tags;')
    for tentativa in range(3):
        for servidor in SERVIDORES_OSM:
            try:
                pedido = urllib.request.Request(servidor, data=urllib.parse.urlencode({"data": consulta}).encode(),
                                                headers={"User-Agent": "PainelOriximina/1.0"})
                with urllib.request.urlopen(pedido, timeout=180) as resposta:
                    return json.load(resposta)["elements"]
            except Exception as erro:
                print(f"  {servidor} falhou ({erro}); tentando outro", flush=True)
        time.sleep(10 * (tentativa + 1))
    raise SystemExit("O OpenStreetMap não respondeu. Tente de novo mais tarde.")


def poligonos(elementos):
    """(nome, tipo, forma) de cada área desenhada como polígono (os pontos soltos não têm área)."""
    for e in elementos:
        tags = e.get("tags", {})
        tipo = TIPOS_OSM.get(tags.get("leisure") or tags.get("place") or tags.get("landuse"))
        if not tipo:
            continue
        aneis = []
        if e["type"] == "way" and len(e.get("geometry", [])) > 3:
            aneis = [[(p["lon"], p["lat"]) for p in e["geometry"]]]
        elif e["type"] == "relation":
            aneis = [[(p["lon"], p["lat"]) for p in m["geometry"]] for m in e.get("members", [])
                     if m.get("role") == "outer" and len(m.get("geometry", [])) > 3]
        for anel in aneis:
            nome = tags.get("name")
            yield NOMES_CORRIGIDOS.get(nome, nome), tipo, Polygon(anel).buffer(0)


def baixar_worldcover():
    caminho = os.path.join(PASTA_WORLDCOVER, NOME_WORLDCOVER)
    if not os.path.exists(caminho):
        os.makedirs(PASTA_WORLDCOVER, exist_ok=True)
        print("Baixando o ESA WorldCover (uns 35 MB)...", flush=True)
        # Pelo curl: a leitura direta pela internet (/vsicurl) do rasterio travava neste Windows
        subprocess.run(["curl", "-s", "-L", "--max-time", "900", "-o", caminho, URL_WORLDCOVER], check=True)
    return caminho


def main():
    bairros = json.load(open(ARQ_BAIRROS, encoding="utf-8"))["features"]
    formas = [shape(b["geometry"]) for b in bairros]
    sede = unary_union(formas)
    o, s, l, n = sede.bounds

    # 1) Parques e praças do OpenStreetMap, dentro da área dos bairros da sede (com uma margem de uns 500 m)
    area_da_sede = sede.buffer(0.005)
    areas = [(nome, tipo, forma.intersection(area_da_sede)) for nome, tipo, forma in
             poligonos(areas_osm(f"{s - 0.01},{o - 0.01},{n + 0.01},{l + 0.01}")) if forma.intersects(area_da_sede)]
    linhas, sem_nome = [], defaultdict(lambda: [0, 0.0])
    for nome, tipo, forma in areas:
        if nome:
            linhas.append({"Área": nome, "Hectares": hectares(forma)})
        else:
            sem_nome[tipo][0] += 1
            sem_nome[tipo][1] += hectares(forma)
    for tipo, (quantos, ha) in sem_nome.items():
        linhas.append({"Área": f"{tipo} sem nome no mapa ({quantos})", "Hectares": ha})
    df_osm = pd.DataFrame(linhas).groupby("Área", as_index=False)["Hectares"].sum()
    df_osm = df_osm[df_osm["Hectares"] >= 0.05].sort_values("Hectares", ascending=False)
    df_osm["Hectares"] = df_osm["Hectares"].round(2)
    df_osm.to_csv(os.path.join(PASTA_COMPONENTES, "comp_314.csv"), sep=";", index=False, encoding="utf-8")
    print(df_osm.to_string(index=False))
    total_osm = hectares(unary_union([f for _, _, f in areas]))   # sem contar duas vezes (quadra dentro de praça)
    com_nome = sum(1 for nome, _, _ in areas if nome)

    # 2) Cobertura do chão por bairro (WorldCover, quadrados de 10 m)
    with rasterio.open(baixar_worldcover()) as imagem:
        janela = from_bounds(o - 0.002, s - 0.002, l + 0.002, n + 0.002, imagem.transform)
        classes = imagem.read(1, window=janela)
        transformacao = imagem.window_transform(janela)
    linhas = []
    for bairro, forma in zip(bairros, formas):
        dentro = ~geometry_mask([forma], classes.shape, transformacao)
        if not dentro.any():
            continue
        # Cada quadrado vale a área do bairro dividida pelo número de quadrados dentro dele
        ha_por_quadrado = hectares(forma) / dentro.sum()
        linha = {"Bairro": bairro["properties"]["nome"]}
        for codigo, coluna in CLASSES_SATELITE.items():
            linha[coluna] = linha.get(coluna, 0) + (classes[dentro] == codigo).sum() * ha_por_quadrado
        linhas.append(linha)
    colunas = list(dict.fromkeys(CLASSES_SATELITE.values()))
    df_sat = pd.DataFrame(linhas).fillna(0)
    df_sat["verde"] = (df_sat["Árvores"] + df_sat["Gramado e arbustos"]) / df_sat[colunas].sum(axis=1)
    df_sat = df_sat.sort_values("verde", ascending=False)
    df_sat[colunas] = df_sat[colunas].round(1)
    df_sat[["Bairro"] + colunas].to_csv(os.path.join(PASTA_COMPONENTES, "comp_315.csv"), sep=";", index=False,
                                        encoding="utf-8")
    print(df_sat[["Bairro"] + colunas + ["verde"]].to_string(index=False))
    soma = df_sat[colunas].sum()
    verde_sede = (soma["Árvores"] + soma["Gramado e arbustos"]) / soma.sum()
    arvores_sede = soma["Árvores"] / soma.sum()
    mais, menos = df_sat.iloc[0], df_sat.iloc[-1]

    def br(n, casas=0):
        return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    componentes = {
        "comp_314": {
            "id": 314, "titulo": "Parques, praças e áreas de lazer", "fonte": "OpenStreetMap | contribuidores",
            "atualizacao": time.strftime("%m/%Y"), "icone": "grid_view", "area": "Sede urbana de Oriximiná",
            "resumo": "Parques, praças, campos e áreas de lazer da sede desenhados no OpenStreetMap, em hectares.",
            "descricao": (
                f"Mostra as áreas de lazer e verdes da sede desenhadas no OpenStreetMap, o mapa aberto feito por "
                f"voluntários: {len(areas)} áreas, {com_nome} com nome, que somam {br(total_osm, 1)} hectares (sem "
                "contar duas vezes uma quadra dentro de uma praça). Atenção: o mapa de Oriximiná está incompleto — "
                "faltam praças e campos que existem na cidade, e a maioria das áreas desenhadas não tem nome; as "
                "sem nome aparecem juntas, por tipo. Qualquer pessoa pode completar o mapa em openstreetmap.org, e "
                "o cartão é atualizado ao rodar o script de novo. Para a vegetação de verdade de cada bairro, veja "
                "o cartão \"Áreas verdes por bairro\" (satélite). A Prefeitura não publica o cadastro das praças e "
                "parques, que o cartão do Taipei usa."),
            "exemplo": ("Ajuda a ver onde estão as praças e áreas de lazer da cidade e a planejar onde faltam; "
                        "também mostra o que falta mapear, para quem quiser completar o mapa."),
            "tipos": ["mapa_arvore", "barras"],
            "cores": ["#56B96D", "#9DC56E", "#2E7D32", "#F8CF58", "#24B0DD", "#a0b8e8", "#c18ad8", "#F49F36"],
            "unidade": "hectares", "meta": None, "maximo": None,
            "links": [{"nome": "OpenStreetMap – mapa aberto (para ver e completar)",
                       "url": "https://www.openstreetmap.org/#map=15/-1.7650/-55.8650"}],
            "colaboradores": [], "mapa": None, "historico": None,
        },
        "comp_315": {
            "id": 315, "titulo": "Áreas verdes por bairro", "fonte": "Agência Espacial Europeia | ESA WorldCover",
            "atualizacao": "2021", "icone": "bar_chart", "area": "Sede urbana de Oriximiná",
            "resumo": "Quanto de cada bairro da sede é árvore, gramado, área construída e água, por satélite.",
            "descricao": (
                f"Mostra a cobertura do chão em cada bairro da sede, segundo o ESA WorldCover 2021 (Agência "
                f"Espacial Europeia), que classifica cada quadrado de 10 m × 10 m da Terra por imagem de satélite. "
                f"Na sede, {verde_sede:.0%} da área dos bairros é verde ({arvores_sede:.0%} de árvores; o resto, "
                f"gramado e arbustos). O bairro mais verde é {mais['Bairro']} ({mais['verde']:.0%}); o menos, "
                f"{menos['Bairro']} ({menos['verde']:.0%}). Conta toda a vegetação — praças, quintais, terrenos "
                "vazios e matas —, e não só os parques. É uma estimativa: quadrados de 10 m misturam o que está "
                "dentro deles (uma árvore sobre o telhado conta como árvore), e a imagem é de 2021."),
            "exemplo": ("Ajuda a planejar a arborização e as novas praças: os bairros com pouco verde esquentam "
                        "mais e pedem árvores nas ruas; os mais verdes mostram onde proteger as matas que restam."),
            "tipos": ["barras_percentuais", "barras"],
            "cores": ["#2E7D32", "#9DC56E", "#F65658", "#24B0DD", "#bdbdbd"],
            "unidade": "hectares", "meta": None, "maximo": None,
            "links": [{"nome": "ESA WorldCover (Agência Espacial Europeia)", "url": "https://esa-worldcover.org"}],
            "colaboradores": [], "mapa": None, "historico": None,
        },
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {}).update(componentes)
    planejamento = config["paineis_publicos"].setdefault(
        "planejamento", {"titulo": "Planejamento urbano", "icone": "home_work", "cartoes": [], "grupo": "Painel de Oriximiná"})
    for chave in componentes:
        if chave not in planejamento["cartoes"]:
            planejamento["cartoes"].append(chave)
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Planejamento urbano:", planejamento["cartoes"])


if __name__ == "__main__":
    main()
