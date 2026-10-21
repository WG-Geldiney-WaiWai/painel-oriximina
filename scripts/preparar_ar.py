"""Prepara o cartão "Qualidade do ar" (como o do Taipei), no painel "Mudança climática".

Oriximiná não tem estação que mede o ar. O cartão usa a estimativa do serviço europeu Copernicus (CAMS),
calculada por satélite e modelo de computador para o ponto da sede, pela API gratuita do Open-Meteo: a
fumaça e a poeira fina no ar (PM2.5, em microgramas por metro cúbico), hora a hora, desde agosto de 2022.

- comp_330.csv: a média de PM2.5 de cada um dos últimos 36 meses, com os meses da época das queimadas
  (agosto a novembro) numa coluna à parte, para ficarem com outra cor

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_ar.py
"""
import json
import os
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
LATITUDE, LONGITUDE = -1.7656, -55.8661   # sede de Oriximiná
INICIO = "2022-08-01"   # começo dos dados do CAMS no Open-Meteo
URL = ("https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=pm2_5"
       "&start_date={inicio}&end_date={fim}&timezone=America%2FSantarem")
MESES_NO_CARTAO = 36
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_POR_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                     "setembro", "outubro", "novembro", "dezembro"]
MESES_QUEIMADAS = (8, 9, 10, 11)
QUEIMADAS = "Época das queimadas (ago a nov)"
RESTO = "Resto do ano"
LIMITE_OMS = 15         # µg/m³ na média do dia (diretriz da OMS de 2021)
LIMITE_RUIM = 50        # µg/m³ na média do dia: acima disso o ar fica "ruim" no índice de qualidade do ar do MMA


def main():
    ontem = (pd.Timestamp.now(tz="America/Santarem") - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    url = URL.format(lat=LATITUDE, lon=LONGITUDE, inicio=INICIO, fim=ontem)
    with urllib.request.urlopen(url, timeout=120) as resposta:
        horas = json.loads(resposta.read())["hourly"]
    pm25 = pd.Series(horas["pm2_5"], index=pd.to_datetime(horas["time"]), dtype=float).dropna()
    dias = pm25.resample("D").mean().dropna()
    meses = pm25.resample("MS").mean().dropna().tail(MESES_NO_CARTAO).round(1)

    rotulos = [f"{MESES[m.month - 1]}/{m.year % 100:02d}" for m in meses.index]
    if dias.index[-1] < meses.index[-1] + pd.offsets.MonthEnd(0):   # mês atual ainda pela metade
        rotulos[-1] = f"até {dias.index[-1].day}/{MESES[dias.index[-1].month - 1]}"
    tabela = pd.DataFrame({"Mês": rotulos})
    queimada = meses.index.month.isin(MESES_QUEIMADAS)
    tabela[QUEIMADAS] = meses.where(queimada, 0).values
    tabela[RESTO] = meses.where(~queimada, 0).values
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_330.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    ano = dias[dias.index > dias.index[-1] - pd.Timedelta(days=365)]
    acima_oms = int((ano > LIMITE_OMS).sum())
    acima_ruim = int((ano > LIMITE_RUIM).sum())
    semana = dias.tail(7).mean()
    media_queimadas = pm25[pm25.index.month.isin(MESES_QUEIMADAS)].mean()
    media_resto = pm25[~pm25.index.month.isin(MESES_QUEIMADAS)].mean()
    pior = pm25.resample("MS").mean().idxmax()
    print(f"Últimos 7 dias: {semana:.1f}; dias acima da OMS em 12 meses: {acima_oms}; acima de 50: {acima_ruim}")

    def num(x):
        return f"{x:.1f}".replace(".", ",")
    componente = {
        "id": 330, "titulo": "Qualidade do ar", "fonte": "Copernicus (CAMS) | Open-Meteo",
        "atualizacao": "Diária", "icone": "air", "area": "Sede de Oriximiná",
        "resumo": "Quanta fumaça e poeira fina há no ar de Oriximiná, mês a mês: o ar piora na época das queimadas.",
        "descricao": (
            f"Mostra a média de cada mês da fumaça e poeira fina no ar da sede de Oriximiná (PM2.5, em "
            "microgramas por metro cúbico), nos últimos três anos. Oriximiná não tem estação que mede o ar: "
            "os números são estimativas do serviço europeu Copernicus (CAMS), feitas por satélite e modelo de "
            "computador. O ar piora sobretudo na época das queimadas, de agosto a novembro (as colunas "
            f"laranja), quando chega fumaça de toda a região: em média {num(media_queimadas)}, contra "
            f"{num(media_resto)} no resto do ano. O pior mês foi {MESES_POR_EXTENSO[pior.month - 1]} de {pior.year}. Nos "
            f"últimos 12 meses, o ar passou do limite da Organização Mundial da Saúde ({LIMITE_OMS} na média "
            f"do dia) em {acima_oms} dias, e ficou ruim pelo índice de qualidade do ar do Ministério do Meio "
            f"Ambiente (acima de {LIMITE_RUIM}) em "
            f"{acima_ruim} dias. Na última semana, a média foi {num(semana)}. Em Taipei, este cartão mostra as "
            "estações que medem o ar ao vivo."),
        "exemplo": ("Avisa quando o ar fica pior por causa das queimadas, para a Saúde orientar crianças, idosos "
                    "e quem tem asma, e mostra a importância de combater o fogo na região."),
        "tipos": ["colunas"],
        "cores": ["#F49F36", "#24B0DD"],
        "unidade": "µg/m³", "meta": None, "maximo": None,
        "links": [{"nome": "Open-Meteo – qualidade do ar (Copernicus CAMS)",
                   "url": "https://open-meteo.com/en/docs/air-quality-api"},
                  {"nome": "OMS – diretrizes de qualidade do ar (2021)",
                   "url": "https://www.who.int/publications/i/item/9789240034228"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    componentes = config.setdefault("componentes_novos", {})
    clima = config.get("paineis_publicos", {}).get("clima")
    componentes["comp_330"] = componente   # o texto traz os números do dia: grava sempre
    if clima and "comp_330" not in clima["cartoes"]:
        clima["cartoes"].append("comp_330")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Mudança climática:",
          clima["cartoes"] if clima else "não encontrado (rode preparar_emissoes.py)")


if __name__ == "__main__":
    main()
