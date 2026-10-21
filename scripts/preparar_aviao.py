"""Prepara o cartão "Passageiros de avião" (no lugar do "Fluxo de passageiros nas estações do MRT" do Taipei),
no painel "Tráfego rodoviário".

Fonte: Dados Estatísticos do Transporte Aéreo da ANAC (Agência Nacional de Aviação Civil): os passageiros
de cada voo das empresas aéreas, por mês, origem e destino, desde 2000. Oriximiná tem dois aeroportos:
SBTB (Porto Trombetas, com voos regulares) e SNOX (a sede, quase sem voos de empresas aéreas).

O arquivo da ANAC tem o Brasil inteiro (cerca de 360 MB). O script baixa de novo quando o da pasta tem mais
de DIAS_PARA_BAIXAR dias; as linhas de Oriximiná ficam guardadas em ANAC/oriximina_voos.csv.

- comp_336.csv: passageiros que embarcaram e que desembarcaram nos aeroportos de Oriximiná, por ano

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_aviao.py
"""
import json
import os
import shutil
import time
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_ANAC = os.path.join(PASTA_FONTES, "ANAC")
ARQ_ANAC = os.path.join(PASTA_ANAC, "Dados_Estatisticos.csv")
ARQ_ORIXIMINA = os.path.join(PASTA_ANAC, "oriximina_voos.csv")
URL_ANAC = ("https://sistemas.anac.gov.br/dadosabertos/Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/"
            "Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo/Dados_Estatisticos.csv")
DIAS_PARA_BAIXAR = 25
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
AEROPORTOS = {"SBTB": "Porto Trombetas", "SNOX": "sede de Oriximiná"}
PRIMEIRO_ANO = 2010
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_POR_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                     "setembro", "outubro", "novembro", "dezembro"]
EMBARQUES, DESEMBARQUES = "Embarques", "Desembarques"
COLUNAS = ["ANO", "MES", "EMPRESA_NOME", "AEROPORTO_DE_ORIGEM_SIGLA", "AEROPORTO_DE_ORIGEM_NOME",
           "AEROPORTO_DE_DESTINO_SIGLA", "AEROPORTO_DE_DESTINO_NOME", "GRUPO_DE_VOO", "PASSAGEIROS_PAGOS",
           "PASSAGEIROS_GRATIS", "DECOLAGENS"]


def baixar_se_velho():
    if os.path.exists(ARQ_ANAC) and time.time() - os.path.getmtime(ARQ_ANAC) < DIAS_PARA_BAIXAR * 86400:
        return
    os.makedirs(PASTA_ANAC, exist_ok=True)
    try:
        pedido = urllib.request.Request(URL_ANAC, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(pedido, timeout=600) as resposta, open(ARQ_ANAC + ".novo", "wb") as arquivo:
            shutil.copyfileobj(resposta, arquivo, 1024 * 1024)
        os.replace(ARQ_ANAC + ".novo", ARQ_ANAC)
        print("Arquivo da ANAC baixado de novo")
    except OSError as erro:
        print(f"Não deu para baixar o arquivo novo da ANAC ({erro}); uso o que já está na pasta")


def voos_de_oriximina():
    """Linhas de Oriximiná do arquivo da ANAC (guardadas num CSV pequeno enquanto o arquivo não muda)."""
    if os.path.exists(ARQ_ORIXIMINA) and os.path.getmtime(ARQ_ORIXIMINA) >= os.path.getmtime(ARQ_ANAC):
        return pd.read_csv(ARQ_ORIXIMINA, sep=";")
    # A 1ª linha do arquivo é "Atualizado em: ..."; o cabeçalho vem na 2ª
    dados = pd.read_csv(ARQ_ANAC, sep=";", skiprows=1, dtype=str, usecols=COLUNAS)
    nossos = dados["AEROPORTO_DE_ORIGEM_SIGLA"].isin(AEROPORTOS) | dados["AEROPORTO_DE_DESTINO_SIGLA"].isin(AEROPORTOS)
    voos = dados[nossos].copy()
    for coluna in ("ANO", "MES", "PASSAGEIROS_PAGOS", "PASSAGEIROS_GRATIS", "DECOLAGENS"):
        voos[coluna] = pd.to_numeric(voos[coluna], errors="coerce").fillna(0).astype(int)
    voos["passageiros"] = voos["PASSAGEIROS_PAGOS"] + voos["PASSAGEIROS_GRATIS"]
    voos.to_csv(ARQ_ORIXIMINA, sep=";", index=False)
    return voos


def main():
    baixar_se_velho()
    voos = voos_de_oriximina()
    ultimo_ano = int(voos["ANO"].max())
    ultimo_mes = int(voos.loc[voos["ANO"] == ultimo_ano, "MES"].max())
    # Voo entre os dois aeroportos de Oriximiná conta como embarque num e desembarque no outro
    embarques = voos[voos["AEROPORTO_DE_ORIGEM_SIGLA"].isin(AEROPORTOS)].groupby("ANO")["passageiros"].sum()
    desembarques = voos[voos["AEROPORTO_DE_DESTINO_SIGLA"].isin(AEROPORTOS)].groupby("ANO")["passageiros"].sum()
    por_ano = pd.DataFrame({EMBARQUES: embarques, DESEMBARQUES: desembarques}).fillna(0).astype(int)
    tabela = por_ano.loc[PRIMEIRO_ANO:].copy()
    rotulos = [str(a) for a in tabela.index]
    if ultimo_mes < 12:
        rotulos[-1] = f"até {MESES[ultimo_mes - 1]}/{ultimo_ano % 100:02d}"   # ano atual pela metade
    tabela.index = rotulos
    tabela.rename_axis("Ano").reset_index().to_csv(os.path.join(PASTA_COMPONENTES, "comp_336.csv"), sep=";",
                                                   index=False, encoding="utf-8")
    print(tabela.to_string())

    total = por_ano.sum(axis=1)
    completos = total.loc[:ultimo_ano - 1]
    pico = int(completos.idxmax())
    vale = int(completos.loc[2015:].idxmin())
    recentes = voos[(voos["ANO"] == ultimo_ano) & (voos["passageiros"] > 0)]
    destinos = sorted({d.title() for d in recentes["AEROPORTO_DE_DESTINO_NOME"] if "ORIXIMIN" not in d}
                      | {o.title() for o in recentes["AEROPORTO_DE_ORIGEM_NOME"] if "ORIXIMIN" not in o})
    empresas = sorted({e.split(" (")[0].split(" LTDA")[0].split(" S/A")[0].title() for e in recentes["EMPRESA_NOME"]})
    sede = voos[(voos["AEROPORTO_DE_ORIGEM_SIGLA"] == "SNOX") | (voos["AEROPORTO_DE_DESTINO_SIGLA"] == "SNOX")]
    ultimo_sede = int(sede.loc[sede["passageiros"] > 0, "ANO"].max()) if (sede["passageiros"] > 0).any() else None

    def fmt(n):
        return f"{int(n):,}".replace(",", ".")
    componente = {
        "id": 336, "titulo": "Passageiros de avião", "fonte": "ANAC | Dados Estatísticos do Transporte Aéreo",
        "atualizacao": "Mensal", "icone": "flight", "area": "Aeroportos de Oriximiná",
        "resumo": "Quantos passageiros embarcam e desembarcam de avião em Oriximiná por ano (Porto Trombetas e sede).",
        "descricao": (
            f"Mostra, de {PRIMEIRO_ANO} a {ultimo_ano}, quantos passageiros embarcaram e desembarcaram nos voos "
            "das empresas aéreas nos aeroportos de Oriximiná, segundo a ANAC: o de Porto Trombetas (SBTB), que "
            "tem voos regulares, e o da sede (SNOX). O movimento é quase todo em Porto Trombetas. Desde "
            f"{int(total.index.min())}, o maior ano foi {pico}, com {fmt(completos[pico])} passageiros (somando "
            f"embarques e desembarques). O movimento caiu a partir de 2014 e mais ainda na pandemia, em 2020, e o "
            f"menor ano foi "
            f"{vale}, com {fmt(completos[vale])}; depois voltou a subir. Em {ultimo_ano} (até "
            f"{MESES_POR_EXTENSO[ultimo_mes - 1]}), já foram {fmt(total[ultimo_ano])}, em voos de "
            f"{' e '.join(empresas)} ligando Oriximiná a {' e '.join(destinos)}. "
            + (f"O aeródromo da sede não tem voos de empresas aéreas desde {ultimo_sede}. " if ultimo_sede
               and ultimo_sede < ultimo_ano else "")
            + "Não entram os voos particulares e de táxi aéreo sem registro na ANAC. Em Oriximiná quase todo "
            "mundo viaja de barco, mas a ANTAQ não publica os passageiros do porto; em Taipei, este cartão "
            "mostra os passageiros das estações do metrô."),
        "exemplo": ("Mostra quanto Oriximiná depende do avião para chegar a Manaus e Santarém e ajuda a "
                    "discutir com as empresas aéreas e o governo a oferta de voos."),
        "tipos": ["colunas", "linha_tempo_separada"],
        "cores": ["#24B0DD", "#56B96D"],
        "unidade": "passageiros", "meta": None, "maximo": None,
        "links": [{"nome": "ANAC – Dados Estatísticos do Transporte Aéreo",
                   "url": "https://www.gov.br/anac/pt-br/assuntos/dados-e-estatisticas/dados-estatisticos"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_336"] = componente
    trafego = config.get("paineis_publicos", {}).get("trafego")
    if trafego and "comp_336" not in trafego["cartoes"]:
        trafego["cartoes"].append("comp_336")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Tráfego rodoviário:", trafego["cartoes"] if trafego else "—")


if __name__ == "__main__":
    main()
