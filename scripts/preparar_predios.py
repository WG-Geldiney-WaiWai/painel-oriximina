"""Prepara os prédios da sede de Oriximiná para o botão "Prédios em 3D" da Comparação de mapas.

Fontes:
- Contornos dos prédios: OpenStreetMap (© colaboradores do OpenStreetMap, licença ODbL), pela Overpass API.
- Altura: GHSL – Global Human Settlement Layer, Comissão Europeia (JRC), camada GHS-BUILT-H R2023A
  ("ANBH", altura média dos prédios em 2018), estimada por satélite em quadrados de 3 segundos de grau
  (cerca de 90 m). Todos os prédios do mesmo quadrado ficam com a mesma altura: é uma média, não a
  medida de cada prédio.

Quando o prédio tem o número de andares no OpenStreetMap, a altura usa os andares (3 m por andar).
Quando o quadrado do prédio não tem estimativa no GHSL, usa a média dos quadrados vizinhos; se nem
eles tiverem, o prédio fica com 3 m (um andar) e isso fica marcado no arquivo.

Gera o arquivo que o painel.py usa:

- predios_oriximina.geojson: cada prédio com a altura em metros (a), de onde veio a altura (o) e o tipo (t)

O arquivo do GHSL (cerca de 6 MB) é baixado uma vez para a pasta dos arquivos grandes
(a mesma do Censo e do CNEFE) e reaproveitado depois.

Rode de novo para atualizar:  python preparar_predios.py
"""
import io
import json
import os
import time
import urllib.parse
import urllib.request
import zipfile

import numpy as np
from PIL import Image

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_IBGE = r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná"
SERVIDORES = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
              "https://overpass.kumi.systems/api/interpreter"]
CAIXA = (-1.82, -55.92, -1.70, -55.80)   # sede urbana de Oriximiná (sul, oeste, norte, leste)

# Pedaço R10_C13 do GHSL: de 0,9° S a 10,9° S e de 60° O a 50° O (cobre a sede)
NOME_GHSL = "GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_4326_3ss_V1_0_R10_C13"
URL_GHSL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_H_GLOBE_R2023A/"
            f"GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_4326_3ss/V1-0/tiles/{NOME_GHSL}.zip")
METROS_POR_ANDAR = 3
ALTURA_SEM_ESTIMATIVA = 3

# De onde veio a altura (campo "o" do arquivo)
ORIGEM_ANDARES, ORIGEM_GHSL, ORIGEM_VIZINHOS, ORIGEM_PADRAO = "andares", "ghsl", "ghsl_vizinhos", "padrao"


def baixar_predios():
    consulta = f'[out:json][timeout:180];way["building"]{CAIXA};out tags geom;'
    dados = urllib.parse.urlencode({"data": consulta}).encode()
    for tentativa in range(3):
        for servidor in SERVIDORES:
            try:
                pedido = urllib.request.Request(servidor, data=dados, headers={"User-Agent": "PainelOriximina/1.0"})
                with urllib.request.urlopen(pedido, timeout=240) as resposta:
                    return json.load(resposta)["elements"]
            except Exception as erro:
                print(f"  {servidor} falhou ({erro}); tentando outro")
        time.sleep(10 * (tentativa + 1))
    raise SystemExit("Não foi possível baixar os prédios do OpenStreetMap. Tente de novo mais tarde.")


def ler_ghsl():
    """(alturas, longitude do canto, latitude do canto, tamanho do quadrado) do recorte da sede."""
    caminho_zip = os.path.join(PASTA_IBGE, f"{NOME_GHSL}.zip")
    if not os.path.exists(caminho_zip):
        print("Baixando a altura dos prédios do GHSL (cerca de 6 MB)...")
        os.makedirs(PASTA_IBGE, exist_ok=True)
        with urllib.request.urlopen(URL_GHSL, timeout=600) as resposta:
            conteudo = resposta.read()
        with open(caminho_zip, "wb") as arquivo:
            arquivo.write(conteudo)
    Image.MAX_IMAGE_PIXELS = None   # o pedaço inteiro tem 12.000 × 12.000 quadrados
    with zipfile.ZipFile(caminho_zip) as pacote:
        imagem = Image.open(io.BytesIO(pacote.read(f"{NOME_GHSL}.tif")))
    oeste, norte = imagem.tag_v2[33922][3], imagem.tag_v2[33922][4]   # canto de cima à esquerda
    passo = imagem.tag_v2[33550][0]
    sul, o, n, leste = CAIXA
    col0, lin0 = int((o - oeste) / passo), int((norte - n) / passo)
    col1, lin1 = int((leste - oeste) / passo) + 1, int((norte - sul) / passo) + 1
    recorte = np.array(imagem.crop((col0, lin0, col1, lin1)), dtype=float)
    return recorte, oeste + col0 * passo, norte - lin0 * passo, passo


def altura_do_quadrado(alturas, lin, col):
    """(altura, origem) do quadrado; sem estimativa, a média dos 8 vizinhos que têm."""
    if 0 <= lin < alturas.shape[0] and 0 <= col < alturas.shape[1] and alturas[lin, col] > 0:
        return float(alturas[lin, col]), ORIGEM_GHSL
    vizinhos = alturas[max(lin - 1, 0):lin + 2, max(col - 1, 0):col + 2]
    vizinhos = vizinhos[vizinhos > 0]
    if vizinhos.size:
        return float(vizinhos.mean()), ORIGEM_VIZINHOS
    return ALTURA_SEM_ESTIMATIVA, ORIGEM_PADRAO


def andares(tags):
    try:
        return int(float(tags.get("building:levels", "")))
    except ValueError:
        return None


def main():
    print("Baixando os prédios do OpenStreetMap...")
    elementos = baixar_predios()
    alturas, oeste, norte, passo = ler_ghsl()
    predios, contagem = [], {}
    for elemento in elementos:
        pontos = [(round(p["lon"], 6), round(p["lat"], 6)) for p in elemento.get("geometry", [])]
        if len(pontos) < 4:
            continue
        if pontos[0] != pontos[-1]:
            pontos.append(pontos[0])
        tags = elemento.get("tags", {})
        if andares(tags):
            altura, origem = andares(tags) * METROS_POR_ANDAR, ORIGEM_ANDARES
        else:
            lon = sum(p[0] for p in pontos[:-1]) / (len(pontos) - 1)
            lat = sum(p[1] for p in pontos[:-1]) / (len(pontos) - 1)
            altura, origem = altura_do_quadrado(alturas, int((norte - lat) / passo), int((lon - oeste) / passo))
        contagem[origem] = contagem.get(origem, 0) + 1
        predios.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [pontos]},
                        "properties": {"a": round(altura, 1), "o": origem, "t": tags.get("building", "yes")}})
    with open("predios_oriximina.geojson", "w", encoding="utf-8") as arquivo:
        json.dump({"type": "FeatureCollection", "features": predios}, arquivo, ensure_ascii=False,
                  separators=(",", ":"))
    print(f"{len(predios)} prédios gravados em predios_oriximina.geojson")
    print("Altura: " + ", ".join(f"{n} por {o}" for o, n in contagem.items()))


if __name__ == "__main__":
    main()
