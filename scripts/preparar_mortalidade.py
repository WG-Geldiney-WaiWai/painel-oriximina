"""Prepara o cartão "Principais causas de morte" (como a "Visão geral das taxas de mortalidade por causa" do
Taipei), no painel "Saúde".

Fontes:
- Mortes de moradores de Oriximiná por causa (lista CID-BR-10), por ano: SIM do DATASUS, pelo TabNet
  (http://tabnet.datasus.gov.br/cgi/deftohtm.exe?sim/cnv/obt10pa.def). O último ano ainda é prévia.
- População de cada ano: estimativas do IBGE (SIDRA 6579) e Censo 2022 (SIDRA 4709); 2023, que o IBGE não
  estimou, fica no meio entre 2022 e 2024.

- comp_334.csv: mortes por 100 mil habitantes, por ano (linhas) e causa (colunas)

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_mortalidade.py
"""
import gzip
import html
import json
import os
import re
import urllib.parse
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
CODIGO_TABNET = "85"   # Oriximiná na lista de municípios do Pará no TabNet
PRIMEIRO_ANO = 2015
ULTIMO_FINAL = 2024    # "Dados finais disponíveis até 2024"; o ano seguinte é prévia
ANOS = range(PRIMEIRO_ANO, ULTIMO_FINAL + 2)
POR_100_MIL = 100_000

# Causa no cartão -> começo dos nomes das linhas do TabNet (lista CID-BR-10) que entram nela
# Causa no cartão (nome curto, para caber ao lado do gráfico) -> começo dos nomes das linhas do TabNet
# (lista CID-BR-10) que entram nela. A explicação de cada nome fica na descrição.
CAUSAS = {
    "Pneumonia": ["074 "],
    "AVC": ["070 "],                     # doenças cerebrovasculares
    "Infarto": ["068 "],                 # doenças isquêmicas do coração
    "Câncer": ["032-052 "],              # todas as neoplasias
    "Homicídios": ["110 "],              # agressões
    "Pressão alta": ["067 "],            # doenças hipertensivas
    "Diabetes": ["055 "],
    "Trânsito": ["104 "],                # acidentes de transporte
    "Afogamentos": ["106 "],
    "Suicídios": ["109 "],               # lesões autoprovocadas voluntariamente
    "Covid-19": ["031 "],                # "restante das doenças infecciosas": a covid entra aqui desde 2020
    "Causa mal definida": ["102 ", "103 "],   # morte sem assistência médica e sintomas mal definidos
}
COVID = "Covid-19"
MAL_DEFINIDA = "Causa mal definida"


def baixar(url, dados=None):
    pedido = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0",
                                                              "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=180) as resposta:
        conteudo = resposta.read()
    return gzip.decompress(conteudo) if conteudo[:2] == bytes([0x1F, 0x8B]) else conteudo


def numero(texto):
    """'1.380' -> 1380 (o TabNet usa ponto de milhar); '-' -> 0."""
    texto = texto.strip().replace(".", "")
    return int(texto) if texto.isdigit() else 0


def mortes_por_causa():
    campos = [("Linha", "Causa_-_CID-BR-10"), ("Coluna", "Ano_do_Óbito"), ("Incremento", "Óbitos_p/Residênc"),
              ("SMunicípio", CODIGO_TABNET), ("formato", "table"), ("mostre", "Mostra")]
    campos += [("Arquivos", f"obtpa{ano % 100:02d}.dbf") for ano in ANOS]
    corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode("ascii")
    pagina = baixar("http://tabnet.datasus.gov.br/cgi/tabcgi.exe?sim/cnv/obt10pa.def", corpo).decode("latin-1")
    if "ORIXIMINA" not in pagina.upper():
        raise RuntimeError("O TabNet não devolveu a tabela de Oriximiná (o código do município mudou?)")
    pagina = pagina[pagina.upper().find('CLASS="TABDADOS"'):]
    pagina = pagina[:pagina.upper().find("</TABLE>")]
    linhas = []
    for linha in re.split(r"(?i)<tr", pagina)[1:]:
        celulas = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.split(r"(?i)<t[dh][^>]*>", linha)[1:]]
        if celulas:
            linhas.append(celulas)
    cabecalho = next(l for l in linhas if l[0].startswith("Causa"))
    anos = [int(a) for a in cabecalho[1:-1]]   # a última coluna é o total
    tabela = {}
    for celulas in linhas:
        nome = celulas[0].lstrip(". ")
        if len(celulas) == len(cabecalho):
            tabela[nome] = [numero(c) for c in celulas[1:-1]]
    tabela = pd.DataFrame(tabela, index=anos).T
    resultado = pd.DataFrame(index=anos)
    for causa, comecos in CAUSAS.items():
        resultado[causa] = tabela[tabela.index.str.startswith(tuple(comecos))].sum()
    resultado["Total"] = tabela.loc["TOTAL"]
    return resultado


def populacao():
    url = ("https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/{p}/variaveis/9324"
           "?localidades=N6[1505304]")
    estimativas = json.loads(baixar(url.format(p="|".join(str(a) for a in ANOS))))
    serie = {int(a): int(v) for a, v in estimativas[0]["resultados"][0]["series"][0]["serie"].items()
             if v.isdigit()}
    censo = json.loads(baixar("https://servicodados.ibge.gov.br/api/v3/agregados/4709/periodos/2022/variaveis/93"
                              "?localidades=N6[1505304]"))
    serie[2022] = int(censo[0]["resultados"][0]["series"][0]["serie"]["2022"])
    # Anos sem estimativa (2023): no meio dos vizinhos
    return pd.Series(serie).reindex(ANOS).interpolate().ffill().bfill()


def main():
    mortes = mortes_por_causa()
    pessoas = populacao()
    taxas = (mortes[list(CAUSAS)].div(pessoas, axis=0) * POR_100_MIL).round(1)
    rotulos = [f"{a} (prévia)" if a > ULTIMO_FINAL else str(a) for a in taxas.index]
    tabela = taxas.copy()
    tabela.index = rotulos
    tabela.rename_axis("Ano").reset_index().to_csv(os.path.join(PASTA_COMPONENTES, "comp_334.csv"), sep=";",
                                                   index=False, encoding="utf-8")
    print(mortes.to_string())
    print(pessoas.round().astype(int).to_dict())
    print(tabela.to_string())

    finais = mortes.loc[PRIMEIRO_ANO:ULTIMO_FINAL]
    soma = finais[list(CAUSAS)].sum().drop([COVID, MAL_DEFINIDA]).sort_values(ascending=False)
    mal = finais[MAL_DEFINIDA].sum() / finais["Total"].sum()
    covid = mortes.loc[2020:2021, COVID].sum()

    def nome_curto(causa):
        return causa if causa in ("AVC", "Covid-19") else causa.lower()
    componente = {
        "id": 334, "titulo": "Principais causas de morte", "fonte": "Ministério da Saúde | DATASUS – SIM",
        "atualizacao": f"{ULTIMO_FINAL} (e prévia de {ULTIMO_FINAL + 1})", "icone": "monitor_heart",
        "area": "Município de Oriximiná",
        "resumo": "De que morrem os moradores de Oriximiná: mortes por causa a cada 100 mil habitantes, ano a ano.",
        "descricao": (
            f"Mostra, de {PRIMEIRO_ANO} a {ULTIMO_FINAL + 1}, quantos moradores de Oriximiná morreram de cada "
            "uma das principais causas, a cada 100 mil habitantes, segundo o Sistema de Informações sobre "
            "Mortalidade (SIM) do Ministério da Saúde. Quanto mais forte a cor, mais mortes. AVC são as doenças "
            "cerebrovasculares; infarto, as doenças isquêmicas do coração; pressão alta, as doenças "
            "hipertensivas; câncer, todas as neoplasias; homicídios, as agressões; trânsito, os acidentes de "
            "transporte (inclusive de barco). Em "
            f"{PRIMEIRO_ANO}–{ULTIMO_FINAL}, as causas que mais mataram foram {nome_curto(soma.index[0])}, "
            f"{nome_curto(soma.index[1])}, {nome_curto(soma.index[2])} e {nome_curto(soma.index[3])}. A covid-19 "
            f"(que a lista do SUS põe no grupo 031, das outras doenças infecciosas) matou cerca de {covid} "
            "moradores em 2020 e 2021. Uma parte grande das mortes "
            f"({mal:.0%}) tem a causa mal definida: muitas vezes a pessoa morreu sem assistência médica, em "
            "casa ou numa comunidade longe do hospital, e por isso a causa de verdade não foi registrada. "
            f"{ULTIMO_FINAL + 1} ainda é prévia e pode mudar. Como os números de Oriximiná são pequenos, "
            "as causas mais raras (suicídios, afogamentos) sobem e descem bastante de um ano para outro. A "
            "população de cada ano é a estimativa do IBGE (e o Censo em 2022)."),
        "exemplo": ("Mostra onde a saúde pode evitar mais mortes: controle da pressão e do diabetes, vacinas "
                    "contra a pneumonia, prevenção de câncer e de violência, e mais atendimento nas "
                    "comunidades, para menos pessoas morrerem sem assistência."),
        "tipos": ["mapa_calor", "linha_tempo_separada"],
        "cores": ["#F65658", "#F49F36", "#F8CF58", "#c18ad8", "#24B0DD", "#56B96D", "#9DC56E", "#a1887f",
                  "#7d9be0", "#e57fb0", "#bdbdbd", "#8d6e63"],
        "unidade": "por 100 mil", "meta": None, "maximo": None,
        "links": [{"nome": "DATASUS – TabNet: mortalidade no Pará (CID-10)",
                   "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?sim/cnv/obt10pa.def"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_334"] = componente
    saude = config.get("paineis_publicos", {}).get("saude")
    if saude and "comp_334" not in saude["cartoes"]:
        saude["cartoes"].append("comp_334")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Saúde:", saude["cartoes"] if saude else "—")


if __name__ == "__main__":
    main()
