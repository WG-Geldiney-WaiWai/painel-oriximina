"""Prepara a rede viária da sede de Oriximiná para o cartão "Informações cartográficas".

Fonte: OpenStreetMap (© colaboradores do OpenStreetMap, licença ODbL), pela Overpass API.
No OpenStreetMap não há ciclovias mapeadas em Oriximiná; por isso o cartão mostra a
rede viária (ruas e estradas), dividida nas mesmas classes que o mapa usa.
Gera o arquivo pequeno que o painel.py usa:

- vias_oriximina.geojson: cada rua com nome, tipo (classe) e comprimento em metros

Rode de novo para atualizar:  python preparar_vias.py
"""
import json
import math
import time
import urllib.parse
import urllib.request
import os

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

SERVIDORES = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
              "https://overpass.kumi.systems/api/interpreter"]
CAIXA = "(-1.82,-55.92,-1.70,-55.80)"   # sede urbana de Oriximiná (sul, oeste, norte, leste)

# Classes do OpenStreetMap agrupadas em três tipos de via
CLASSES = {
    "Vias principais": ["trunk", "primary", "secondary", "tertiary"],
    "Vias locais": ["residential", "unclassified", "living_street", "service", "road"],
    "Caminhos e trilhas": ["track", "path", "footway", "pedestrian", "steps"],
}
TIPO_DA_CLASSE = {classe: tipo for tipo, classes in CLASSES.items() for classe in classes}


def baixar_pedaco(caixa, filtro='way["highway"]'):
    consulta = f'[out:json][timeout:120];{filtro}{caixa};out tags geom;'
    corpo = urllib.parse.urlencode({"data": consulta}).encode()
    for tentativa in range(4):
        for url in SERVIDORES:
            try:
                pedido = urllib.request.Request(url, corpo, headers={"User-Agent": "painel-oriximina"})
                return json.loads(urllib.request.urlopen(pedido, timeout=180).read())["elements"]
            except Exception as erro:
                print(f"{url}: {erro}")
        time.sleep(15)
    raise RuntimeError("Não foi possível baixar do OpenStreetMap agora; tente mais tarde.")


def baixar():
    """Baixa a área em 4 pedaços menores (os servidores do OpenStreetMap recusam pedidos grandes
    quando estão cheios) e junta tudo, sem repetir as ruas que cruzam dois pedaços."""
    sul, oeste, norte, leste = (float(v) for v in CAIXA.strip("()").split(","))
    meio_lat, meio_lon = (sul + norte) / 2, (oeste + leste) / 2
    vias = {}
    for s, n in ((sul, meio_lat), (meio_lat, norte)):
        for o, l in ((oeste, meio_lon), (meio_lon, leste)):
            for via in baixar_pedaco(f"({s},{o},{n},{l})"):
                vias[via["id"]] = via
            time.sleep(3)
    return list(vias.values())


def comprimento_m(pontos):
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(pontos, pontos[1:]):
        # Distância entre dois pontos na Terra (fórmula de haversine)
        f1, f2 = math.radians(lat1), math.radians(lat2)
        a = (math.sin((f2 - f1) / 2) ** 2
             + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
        total += 2 * 6_371_000 * math.asin(math.sqrt(a))
    return total


def main():
    feicoes = []
    for via in baixar():
        tipo = TIPO_DA_CLASSE.get(via.get("tags", {}).get("highway"))
        if not tipo or not via.get("geometry"):
            continue
        pontos = [(p["lat"], p["lon"]) for p in via["geometry"]]
        feicoes.append({
            "type": "Feature",
            "properties": {"nome": via["tags"].get("name", "Sem nome"), "tipo": tipo,
                           "classe_osm": via["tags"]["highway"], "comprimento_m": round(comprimento_m(pontos))},
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in pontos]},
        })
    with open("vias_oriximina.geojson", "w", encoding="utf-8") as arquivo:
        json.dump({"type": "FeatureCollection", "features": feicoes}, arquivo, ensure_ascii=False)

    for tipo in CLASSES:
        vias = [f for f in feicoes if f["properties"]["tipo"] == tipo]
        km = sum(f["properties"]["comprimento_m"] for f in vias) / 1000
        print(f"{tipo}: {len(vias)} trechos, {km:.1f} km")


if __name__ == "__main__":
    main()
