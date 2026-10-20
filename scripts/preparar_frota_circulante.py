"""Prepara o cartão "Frota registrada e frota circulante" de Oriximiná, no painel "Tráfego rodoviário".

A frota registrada conta todos os veículos com registro no município, inclusive os que já não rodam (o
registro só sai quando o dono dá baixa). O RENAEST (Registro Nacional de Sinistros e Estatísticas de
Trânsito, da SENATRAN) publica, mês a mês, também a frota circulante: a estimativa de quantos desses
veículos ainda estão em circulação.

- comp_306.csv: frota registrada e circulante em dezembro de cada ano (e no último mês publicado)

O RENAEST vem num ZIP de uns 500 MB (os acidentes do país inteiro; o Pará quase não envia acidentes, por
isso o painel não tem um cartão de acidentes por mês). O ZIP fica na pasta das fontes, em RENAEST.

Rode de novo para atualizar:  python preparar_frota_circulante.py
(ou, com um ZIP já baixado:   python preparar_frota_circulante.py caminho/do/arquivo.zip)
"""
import io
import json
import os
import subprocess
import sys
import urllib.request
import zipfile

import pandas as pd

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
PASTA_RENAEST = os.path.join(os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná"),
                             "RENAEST")
API_RENAEST = "https://dados.transportes.gov.br/api/3/action/package_show?id=renaest"
CODIGO_IBGE = "1505304"


def baixar_renaest():
    """Baixa o pacote mais recente do RENAEST (o servidor às vezes corta no meio: continua de onde parou)."""
    with urllib.request.urlopen(urllib.request.Request(API_RENAEST, headers={"User-Agent": "Mozilla/5.0"}),
                                timeout=60) as resposta:
        recursos = json.loads(resposta.read())["result"]["resources"]
    url = max(recursos, key=lambda r: r.get("created") or "")["url"]
    os.makedirs(PASTA_RENAEST, exist_ok=True)
    destino = os.path.join(PASTA_RENAEST, os.path.basename(url))
    for _ in range(15):
        if os.path.exists(destino) and zipfile.is_zipfile(destino):
            return destino
        print("baixando", url, flush=True)
        subprocess.run(["curl", "-s", "-L", "-C", "-", "--max-time", "900", "-o", destino, url], check=False)
    raise RuntimeError("Não consegui baixar o RENAEST inteiro; rode de novo para continuar o download")


def frota_de_oriximina(arquivo_zip):
    """Linhas de Oriximiná da tabela de localidades do RENAEST (uma por mês)."""
    with zipfile.ZipFile(arquivo_zip) as z:
        nome = next(n for n in z.namelist() if n.startswith("Localidade_"))
        with z.open(nome) as arquivo:
            df = pd.read_csv(io.TextIOWrapper(arquivo, encoding="latin-1"), sep=";", dtype=str)
    df = df[df["codigo_ibge"] == CODIGO_IBGE].copy()
    for coluna in ("ano_referencia", "mes_referencia", "qtde_habitantes", "frota_total", "frota_circulante"):
        df[coluna] = df[coluna].astype(int)
    return df.sort_values(["ano_referencia", "mes_referencia"])


def main():
    arquivo_zip = sys.argv[1] if len(sys.argv) > 1 else baixar_renaest()
    df = frota_de_oriximina(arquivo_zip)
    ultimo = df.iloc[-1]
    # Dezembro de cada ano e, no ano corrente, o último mês publicado
    anual = df[(df["mes_referencia"] == 12) | (df.index == df.index[-1])]
    tabela = pd.DataFrame({
        # Só o ano (as linhas do tempo pedem anos na 1ª coluna); a descrição avisa que o último é parcial
        "Ano": anual["ano_referencia"].values,
        "Frota registrada": anual["frota_total"].values,
        "Frota circulante": anual["frota_circulante"].values,
    })
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_306.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    primeiro = anual.iloc[0]
    parte = ultimo["frota_circulante"] / ultimo["frota_total"]
    por_mil = ultimo["frota_circulante"] / ultimo["qtde_habitantes"] * 1000
    mes = f"{int(ultimo['mes_referencia']):02d}/{int(ultimo['ano_referencia'])}"

    def numero(n):
        return f"{int(n):,}".replace(",", ".")
    componente = {
        "id": 306, "titulo": "Frota registrada e frota circulante", "fonte": "SENATRAN | RENAEST",
        "atualizacao": mes, "icone": "show_chart", "area": "Município de Oriximiná",
        "resumo": "Veículos registrados em Oriximiná e quantos deles ainda circulam, ano a ano.",
        "descricao": (
            f"Compara a frota registrada em Oriximiná com a frota circulante, a estimativa da SENATRAN de "
            f"quantos desses veículos ainda estão em circulação, publicada no RENAEST. Em {mes}, eram "
            f"{numero(ultimo['frota_total'])} veículos registrados e {numero(ultimo['frota_circulante'])} "
            f"circulando ({parte:.0%}), cerca de {por_mil:.0f} veículos em circulação para cada mil habitantes. "
            f"Em {int(primeiro['ano_referencia'])}, a frota circulante era "
            f"{primeiro['frota_circulante'] / primeiro['frota_total']:.0%} da registrada. A diferença são "
            "veículos que continuam no registro mas já não rodam (quebrados, abandonados, vendidos para fora "
            "sem transferência). Os valores são de dezembro de cada ano; o ano corrente vai até o último mês "
            "publicado."),
        "exemplo": ("Dá a medida mais real do trânsito da cidade: é a frota circulante que ocupa as ruas e os "
                    "estacionamentos, e é com ela que se planejam sinalização, fiscalização e campanhas."),
        "tipos": ["linha_tempo_separada", "colunas"],
        "cores": ["#a0b8e8", "#24B0DD"], "unidade": "veículos", "meta": None, "maximo": None,
        "links": [{"nome": "RENAEST – dados abertos (Ministério dos Transportes)",
                   "url": "https://dados.transportes.gov.br/dataset/renaest"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_306"] = componente
    trafego = config.get("paineis_publicos", {}).get("trafego")
    if trafego and "comp_306" not in trafego["cartoes"]:
        # Logo depois do cartão da frota ano a ano (comp_301)
        posicao = trafego["cartoes"].index("comp_301") + 1 if "comp_301" in trafego["cartoes"] else 0
        trafego["cartoes"].insert(posicao, "comp_306")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Tráfego rodoviário:",
          trafego["cartoes"] if trafego else "não encontrado (rode preparar_trafego.py)")


if __name__ == "__main__":
    main()
