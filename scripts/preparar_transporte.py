"""Prepara os dados do painel "Transporte prático" da Calha Norte.

Na Calha Norte não há bicicletas compartilhadas, ônibus elétricos nem ciclovias (os cartões do
Taipei); os cartões usam os dados oficiais de transporte que existem para os 9 municípios:

- regiao_transporte_meio.csv: meio de transporte em que a pessoa passa mais tempo para chegar ao
  trabalho (IBGE, Censo 2022, tabela 10332)
- regiao_transporte_tempo.csv: tempo habitual de deslocamento de casa para o trabalho
  (IBGE, Censo 2022, tabela 10331)
- regiao_frota.csv: frota de veículos por tipo (Ministério dos Transportes / SENATRAN)

Rode de novo para atualizar:  python preparar_transporte.py
"""
import gzip
import json
import os
import unicodedata
import urllib.request

import pandas as pd

from preparar_regiao import MUNICIPIOS

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_SENATRAN = r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná\SENATRAN"
URL_FROTA = ("https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/"
             "frota-de-veiculos-2026-2/Frota_por_municipio_e_tipo_Julho_2026.xlsx")
MES_FROTA = "Julho de 2026"

# Categorias do Censo agrupadas nos meios que aparecem no cartão
MEIOS = {
    "A pé": ["A pé"],
    "Bicicleta": ["Bicicleta"],
    "Motocicleta ou mototáxi": ["Motocicleta", "Mototáxi"],
    "Automóvel ou táxi": ["Automóvel", "Táxi ou assemelhados"],
    "Ônibus, van ou pau de arara": ["Ônibus", "Van, perua ou assemelhados", "BRT ou ônibus de trânsito rápido",
                                    "Caminhonete ou caminhão adaptado (pau de arara)"],
    "Barco ou lancha": ["Embarcação de pequeno porte (até 20 pessoas)",
                        "Embarcação de médio e grande porte (acima de 20 pessoas)"],
    "Outros": ["Trem ou metrô", "Outros"],
}
# Tipos da frota agrupados
FROTA = {
    "Motocicletas": ["MOTOCICLETA", "MOTONETA", "CICLOMOTOR", "TRICICLO", "QUADRICICLO", "SIDE-CAR"],
    "Automóveis": ["AUTOMOVEL"],
    "Caminhonetes e utilitários": ["CAMINHONETE", "CAMIONETA", "UTILITARIO"],
    "Caminhões": ["CAMINHAO", "CAMINHAO TRATOR", "REBOQUE", "SEMI-REBOQUE"],
    "Ônibus e micro-ônibus": ["ONIBUS", "MICRO-ONIBUS"],
    "Outros": ["BONDE", "CHASSI PLATAF", "OUTROS", "TRATOR ESTEI", "TRATOR RODAS"],
}


def pegar_json(url):
    pedido = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "painel-oriximina"})
    dados = urllib.request.urlopen(pedido, timeout=180).read()
    if dados[:2] == b"\x1f\x8b":
        dados = gzip.decompress(dados)
    return json.loads(dados)


def numero(valor):
    """O IBGE usa "-" para zero e "X" para valor escondido por sigilo."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def tabela_censo(tabela, variavel, classificacao, filtros):
    meta = pegar_json(f"https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados")
    categorias = next(c for c in meta["classificacoes"] if c["id"] == classificacao)["categorias"]
    nomes = {k["id"]: k["nome"] for k in categorias if k["nome"] != "Total"}
    classificacoes = f"{classificacao}[{','.join(str(i) for i in nomes)}]|" + "|".join(filtros)
    url = (f"https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos/2022/variaveis/{variavel}"
           f"?localidades=N6[{','.join(MUNICIPIOS)}]&classificacao={classificacoes}")
    linhas = []
    for bloco in pegar_json(url)[0]["resultados"]:
        cat = next(c for c in bloco["classificacoes"] if c["id"] == str(classificacao))
        nome = cat["categoria"][next(iter(cat["categoria"]))]
        for serie in bloco["series"]:
            codigo = serie["localidade"]["id"]
            linhas.append({"codigo": codigo, "Nome": MUNICIPIOS[codigo], "categoria": nome,
                           "pessoas": numero(serie["serie"]["2022"])})
    return pd.DataFrame(linhas)


def meio_de_transporte():
    df = tabela_censo(10332, 13377, 2088, ["1568[120704]", "86[95251]"])
    grupo_de = {cat: grupo for grupo, cats in MEIOS.items() for cat in cats}
    df["Meio"] = df["categoria"].map(grupo_de)
    df = df.groupby(["codigo", "Nome", "Meio"], as_index=False)["pessoas"].sum()
    df.to_csv("regiao_transporte_meio.csv", sep=";", index=False, encoding="utf-8")
    print(df.pivot(index="Nome", columns="Meio", values="pessoas").to_string())


def tempo_de_deslocamento():
    df = tabela_censo(10331, 13556, 537, ["2[6794]", "86[95251]", "386[9680]"])
    df = df.rename(columns={"categoria": "Tempo"})
    df.to_csv("regiao_transporte_tempo.csv", sep=";", index=False, encoding="utf-8")
    print(df.pivot(index="Nome", columns="Tempo", values="pessoas").to_string())


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper().strip()


def frota():
    os.makedirs(PASTA_SENATRAN, exist_ok=True)
    arquivo = os.path.join(PASTA_SENATRAN, os.path.basename(URL_FROTA))
    if not os.path.exists(arquivo):
        # O site do governo recusa downloads que não se identificam como navegador
        pedido = urllib.request.Request(URL_FROTA, headers={"User-Agent": "Mozilla/5.0 (painel-oriximina)"})
        with open(arquivo, "wb") as saida:
            saida.write(urllib.request.urlopen(pedido, timeout=300).read())
    bruto = pd.read_excel(arquivo, header=None)
    linha_cabecalho = bruto.index[bruto.iloc[:, 0].astype(str).str.strip() == "UF"][0]
    tabela = bruto.iloc[linha_cabecalho + 1:].copy()
    tabela.columns = [str(c).strip() for c in bruto.iloc[linha_cabecalho]]
    tabela = tabela[tabela["UF"].astype(str).str.strip() == "PA"]
    codigo_do_nome = {sem_acento(nome): codigo for codigo, nome in MUNICIPIOS.items()}
    tabela["codigo"] = tabela["MUNICIPIO"].astype(str).map(sem_acento).map(codigo_do_nome)
    tabela = tabela.dropna(subset=["codigo"])
    assert len(tabela) == len(MUNICIPIOS), f"Achei {len(tabela)} de {len(MUNICIPIOS)} municípios na frota"
    dados = pd.DataFrame({"codigo": tabela["codigo"], "Nome": tabela["codigo"].map(MUNICIPIOS)})
    for grupo, tipos in FROTA.items():
        dados[grupo] = tabela[tipos].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1).astype(int)
    dados["Total"] = pd.to_numeric(tabela["TOTAL"]).astype(int)
    assert (dados[list(FROTA)].sum(axis=1) == dados["Total"]).all(), "A soma dos tipos não bate com o total"
    dados["Mês"] = MES_FROTA
    dados.to_csv("regiao_frota.csv", sep=";", index=False, encoding="utf-8")
    print(dados.to_string(index=False))


def main():
    meio_de_transporte()
    tempo_de_deslocamento()
    frota()


if __name__ == "__main__":
    main()
