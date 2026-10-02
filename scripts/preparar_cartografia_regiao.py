"""Prepara o cartão "Informações cartográficas" do Painel da Calha Norte.

Fonte: OpenStreetMap (© colaboradores do OpenStreetMap, licença ODbL), pela Overpass API.
Baixa as estradas principais (rodovias e estradas que ligam as sedes e comunidades) e as sedes
municipais dos 9 municípios, e guarda só o que fica dentro deles (malha do IBGE):

- regiao_estradas.geojson: estradas com nome, referência (ex.: PA-254), tipo e comprimento
- regiao_sedes.csv: nome, latitude e longitude da sede de cada município

Rode de novo para atualizar:  python preparar_cartografia_regiao.py
"""
import json

import geopandas as gpd
import pandas as pd
import shapely.geometry

from preparar_regiao import MUNICIPIOS
from preparar_vias import baixar_pedaco, comprimento_m
import os

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

# Classes do OpenStreetMap das estradas que ligam cidades e comunidades
TIPOS = {
    "Rodovias principais": ["trunk", "primary", "secondary"],
    "Estradas vicinais": ["tertiary", "unclassified"],
}
TIPO_DA_CLASSE = {classe: tipo for tipo, classes in TIPOS.items() for classe in classes}


def main():
    municipios = gpd.read_file("regiao_municipios.geojson")
    area = municipios.union_all()
    oeste, sul, leste, norte = municipios.total_bounds

    # Estradas: só as classes principais (a região tem poucas estradas, cabe numa consulta)
    caixa = f"({sul:.4f},{oeste:.4f},{norte:.4f},{leste:.4f})"
    consulta_classes = "|".join(TIPO_DA_CLASSE)
    print("Baixando estradas...", flush=True)
    estradas = {via["id"]: via for via in baixar_pedaco(caixa, f'way["highway"~"^({consulta_classes})$"]')}
    print(f"{len(estradas)} trechos baixados", flush=True)
    feicoes = []
    for via in estradas.values():
        pontos = [(p["lat"], p["lon"]) for p in via.get("geometry", [])]
        linha = shapely.geometry.LineString([(lon, lat) for lat, lon in pontos]) if len(pontos) > 1 else None
        if linha is None or not linha.intersects(area):
            continue
        tags = via.get("tags", {})
        feicoes.append({
            "type": "Feature",
            "properties": {"nome": tags.get("name", "Sem nome"), "ref": tags.get("ref", ""),
                           "tipo": TIPO_DA_CLASSE[tags["highway"]], "classe_osm": tags["highway"],
                           "comprimento_m": round(comprimento_m(pontos))},
            "geometry": shapely.geometry.mapping(linha),
        })
    with open("regiao_estradas.geojson", "w", encoding="utf-8") as arquivo:
        json.dump({"type": "FeatureCollection", "features": feicoes}, arquivo, ensure_ascii=False)
    for tipo in TIPOS:
        km = sum(f["properties"]["comprimento_m"] for f in feicoes if f["properties"]["tipo"] == tipo) / 1000
        print(f"{tipo}: {sum(f['properties']['tipo'] == tipo for f in feicoes)} trechos, {km:.0f} km")

    # Sedes municipais: o lugar (cidade ou vila) com o mesmo nome do município, dentro dele
    sedes = []
    caixa = f"({sul:.4f},{oeste:.4f},{norte:.4f},{leste:.4f})"
    lugares = baixar_pedaco(caixa, 'node["place"~"^(city|town|village)$"]')
    for municipio in municipios.itertuples():
        candidatos = [l for l in lugares if l.get("tags", {}).get("name") == municipio.nome
                      and municipio.geometry.contains(shapely.geometry.Point(l["lon"], l["lat"]))]
        if candidatos:
            sedes.append({"codigo": municipio.codigo, "Nome": municipio.nome,
                          "Latitude": candidatos[0]["lat"], "Longitude": candidatos[0]["lon"]})
        else:
            print(f"Sede não encontrada no OpenStreetMap: {municipio.nome}")
    pd.DataFrame(sedes).to_csv("regiao_sedes.csv", sep=";", index=False, encoding="utf-8")
    print(f"Sedes: {len(sedes)} de {len(MUNICIPIOS)}")


if __name__ == "__main__":
    main()
