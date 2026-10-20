"""Prepara o cartão "Idade da área construída por bairro" (como o "Distribuição das idades dos edifícios" do
Taipei), no painel "Planejamento urbano".

O Taipei usa o cadastro de imóveis, com o ano de cada edifício; Oriximiná não tem esse cadastro público. O
cartão usa o GHSL (Global Human Settlement Layer, Comissão Europeia), que mapeia por satélite quanta área
construída havia em cada época, em quadrados de 3 segundos de grau (uns 90 m): o mesmo GHSL que dá a altura
dos prédios em 3D (preparar_predios.py).

- comp_312.csv: hectares construídos em cada bairro da sede, pela época em que já estavam construídos:
  até 1985 (mais de 40 anos), de 1985 a 2005 (20 a 40 anos) e de 2005 a 2020 (5 a 20 anos). O GHSL tem
  dados medidos até 2020 (2025 e 2030 são projeções), por isso não há a faixa "até 5 anos"

Cada quadrado entra no bairro pela parte dele que fica dentro do bairro. Os arquivos do GHSL (uns 4 MB cada)
ficam na pasta das fontes, em GHSL.

Rode de novo para atualizar:  python preparar_idade_construcoes.py
"""
import io
import json
import os
import urllib.request
import zipfile

import numpy as np
import pandas as pd
from PIL import Image
from shapely.geometry import box, shape

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_BAIRROS = os.path.join(PASTA_PROJETO, "dados", "oriximina_bairros.geojson")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
PASTA_GHSL = os.path.join(os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná"),
                          "GHSL")
# Pedaço R10_C13 do GHSL (o mesmo do preparar_predios.py), camada de área construída (GHS-BUILT-S)
URL_GHSL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/"
            "GHS_BUILT_S_E{0}_GLOBE_R2023A_4326_3ss/V1-0/tiles/{1}.zip")
EPOCAS = [1985, 2005, 2020]
FAIXAS = ["Mais de 40 anos (até 1985)", "20 a 40 anos (1985 a 2005)", "5 a 20 anos (2005 a 2020)"]


def area_construida(epoca, caixa):
    """(m² construídos por quadrado, longitude do canto, latitude do canto, tamanho do quadrado) na caixa."""
    nome = f"GHS_BUILT_S_E{epoca}_GLOBE_R2023A_4326_3ss_V1_0_R10_C13"
    caminho = os.path.join(PASTA_GHSL, f"{nome}.zip")
    if not os.path.exists(caminho):
        print(f"Baixando a área construída de {epoca} do GHSL (uns 4 MB)...", flush=True)
        os.makedirs(PASTA_GHSL, exist_ok=True)
        with urllib.request.urlopen(URL_GHSL.format(epoca, nome), timeout=600) as resposta, \
                open(caminho, "wb") as arquivo:
            arquivo.write(resposta.read())
    Image.MAX_IMAGE_PIXELS = None   # o pedaço inteiro tem 12.000 × 12.000 quadrados
    with zipfile.ZipFile(caminho) as pacote:
        imagem = Image.open(io.BytesIO(pacote.read(f"{nome}.tif")))
    oeste, norte = imagem.tag_v2[33922][3], imagem.tag_v2[33922][4]   # canto de cima à esquerda
    passo = imagem.tag_v2[33550][0]
    o, s, l, n = caixa
    col0, lin0 = int((o - oeste) / passo), int((norte - n) / passo)
    col1, lin1 = int((l - oeste) / passo) + 1, int((norte - s) / passo) + 1
    recorte = np.array(imagem.crop((col0, lin0, col1, lin1)), dtype=float)
    return np.clip(recorte, 0, None), oeste + col0 * passo, norte - lin0 * passo, passo


def main():
    bairros = json.load(open(ARQ_BAIRROS, encoding="utf-8"))["features"]
    formas = [shape(b["geometry"]) for b in bairros]
    limites = np.array([f.bounds for f in formas])
    caixa = (limites[:, 0].min() - 0.01, limites[:, 1].min() - 0.01, limites[:, 2].max() + 0.01, limites[:, 3].max() + 0.01)
    camadas = {e: area_construida(e, caixa) for e in EPOCAS}
    _, x0, y0, passo = camadas[EPOCAS[0]]

    linhas = []
    for bairro, forma in zip(bairros, formas):
        soma = dict.fromkeys(EPOCAS, 0.0)
        o, s, l, n = forma.bounds
        for i in range(int((y0 - n) / passo), int((y0 - s) / passo) + 1):
            for j in range(int((o - x0) / passo), int((l - x0) / passo) + 1):
                quadrado = box(x0 + j * passo, y0 - (i + 1) * passo, x0 + (j + 1) * passo, y0 - i * passo)
                parte = quadrado.intersection(forma).area / quadrado.area
                if parte > 0:
                    for epoca in EPOCAS:
                        soma[epoca] += camadas[epoca][0][i, j] * parte
        # Em hectares; a área construída pode "encolher" um pouco entre épocas (ruído do satélite): fica em 0
        antes = [soma[e] for e in EPOCAS]
        linhas.append({"Bairro": bairro["properties"]["nome"],
                       FAIXAS[0]: antes[0] / 1e4,
                       FAIXAS[1]: max(antes[1] - antes[0], 0) / 1e4,
                       FAIXAS[2]: max(antes[2] - antes[1], 0) / 1e4})
    df = pd.DataFrame(linhas)
    df["total"] = df[FAIXAS].sum(axis=1)
    df = df[df["total"] >= 1].sort_values("total", ascending=False)   # sem as áreas com menos de 1 ha construído
    df[FAIXAS] = df[FAIXAS].round(1)
    df[["Bairro"] + FAIXAS].to_csv(os.path.join(PASTA_COMPONENTES, "comp_312.csv"), sep=";", index=False,
                                   encoding="utf-8")
    print(df[["Bairro"] + FAIXAS].to_string(index=False))

    total = df[FAIXAS].sum()
    em_1985, em_2020 = total.iloc[0], total.sum()
    antigo = df.assign(p=df[FAIXAS[0]] / df["total"]).sort_values("p", ascending=False).iloc[0]
    novo = df.assign(p=df[FAIXAS[2]] / df["total"]).sort_values("p", ascending=False).iloc[0]

    def ha(n):
        return f"{n:,.0f}".replace(",", ".")
    componente = {
        "id": 312, "titulo": "Idade da área construída por bairro", "fonte": "Comissão Europeia | GHSL",
        "atualizacao": str(EPOCAS[-1]), "icone": "bar_chart", "area": "Sede urbana de Oriximiná",
        "resumo": "Quanto da área construída de cada bairro da sede tem mais de 40, de 20 a 40 e de 5 a 20 anos.",
        "descricao": (
            f"Mostra, em cada bairro da sede, a área construída pela época em que ela já existia, segundo o GHSL "
            f"(Comissão Europeia), que mapeia por imagens de satélite as construções do mundo inteiro desde 1975. "
            f"A sede tinha {ha(em_1985)} hectares construídos em {EPOCAS[0]} e {ha(em_2020)} em {EPOCAS[-1]}. O "
            f"bairro mais antigo é {antigo['Bairro']} ({antigo['p']:.0%} da área construída já existia em "
            f"{EPOCAS[0]}); o mais novo, {novo['Bairro']} ({novo['p']:.0%} construída de {EPOCAS[1]} a "
            f"{EPOCAS[2]}). É uma estimativa: o satélite vê quadrados de uns 90 m, e um pouco das construções "
            "de um bairro pode cair no vizinho. Mede a área construída, e não cada edifício (o cartão do Taipei "
            "usa o ano de cada edifício, do cadastro de imóveis, que Oriximiná não publica). O GHSL tem dados "
            f"medidos até {EPOCAS[-1]}, por isso não há a faixa de até 5 anos. Bairros e ocupações com menos de "
            "1 hectare construído ficam de fora."),
        "exemplo": ("Ajuda a planejar a manutenção e a infraestrutura: os bairros mais antigos pedem reforma de "
                    "redes de água, esgoto e drenagem; os mais novos, a chegada dos serviços (escolas, postos, "
                    "transporte) que ainda faltam."),
        "tipos": ["barras_percentuais", "barras"],
        "cores": ["#8D6E3C", "#A5C882", "#6FD3C0"], "unidade": "hectares", "meta": None, "maximo": None,
        "links": [{"nome": "GHSL – Global Human Settlement Layer (Comissão Europeia)",
                   "url": "https://human-settlement.emergency.copernicus.eu/download.php?ds=bu"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_312"] = componente
    planejamento = config["paineis_publicos"].setdefault(
        "planejamento", {"titulo": "Planejamento urbano", "icone": "home_work", "cartoes": [], "grupo": "Painel de Oriximiná"})
    if "comp_312" not in planejamento["cartoes"]:
        planejamento["cartoes"].append("comp_312")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Planejamento urbano:", planejamento["cartoes"])


if __name__ == "__main__":
    main()
