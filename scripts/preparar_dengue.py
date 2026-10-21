"""Prepara o cartão "Alerta de dengue" (como o "Alerta de epidemia de enterovírus" do Taipei), no painel "Saúde".

O InfoDengue (Fiocruz e FGV) calcula toda semana, para cada município, os casos de dengue e o nível de
alerta: verde (sem risco), amarelo (clima favorável ao mosquito), laranja (transmissão em alta) e
vermelho (epidemia). O enterovírus do cartão do Taipei não é de notificação obrigatória no Brasil.

- comp_325.csv: as últimas 26 semanas, com os casos da semana na coluna do nível de alerta dela
- comp_325_historico.csv: casos de dengue, chikungunya e zika por ano, desde 2015

Os números das últimas semanas ainda mudam (os casos chegam com atraso); o InfoDengue já corrige isso
com uma estimativa ("casos estimados"), que é a usada aqui.

Rode de novo toda semana para atualizar (ou clique em "Atualizar" na administração):  python preparar_dengue.py
"""
import io
import json
import os
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
CODIGO_ORIXIMINA = 1505304
API = "https://info.dengue.mat.br/api/alertcity"
PRIMEIRO_ANO = 2015
SEMANAS_NO_CARTAO = 26
NIVEIS = {1: "Verde", 2: "Amarelo", 3: "Laranja", 4: "Vermelho"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DOENCAS = {"dengue": "Dengue", "chikungunya": "Chikungunya", "zika": "Zika"}


def baixar(doenca, ano_inicio, ano_fim):
    url = (f"{API}?geocode={CODIGO_ORIXIMINA}&disease={doenca}&format=csv"
           f"&ew_start=1&ew_end=53&ey_start={ano_inicio}&ey_end={ano_fim}")
    with urllib.request.urlopen(url, timeout=60) as resposta:
        df = pd.read_csv(io.StringIO(resposta.read().decode("utf-8")))
    return df.sort_values("SE").drop_duplicates("SE", keep="last")


def main():
    hoje = pd.Timestamp.now()
    dengue = baixar("dengue", hoje.year - 1, hoje.year)
    ultimas = dengue.tail(SEMANAS_NO_CARTAO).copy()
    ultimas["casos_cartao"] = ultimas["casos_est"].round().astype(int)
    # Rótulo curto: o dia em que a semana começa (domingo), como "05/abr"
    inicio = pd.to_datetime(ultimas["data_iniSE"])
    tabela = pd.DataFrame({"Semana que começa em": [f"{d.day:02d}/{MESES[d.month - 1]}" for d in inicio]})
    for nivel, nome in NIVEIS.items():
        tabela[f"Alerta {nome.lower()}"] = [c if n == nivel else 0
                                            for c, n in zip(ultimas["casos_cartao"], ultimas["nivel"])]
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_325.csv"), sep=";", index=False, encoding="utf-8")
    print(pd.concat([tabela, ultimas[["nivel", "casos"]].reset_index(drop=True)], axis=1).to_string(index=False))

    # Histórico: casos por ano das três doenças do mosquito Aedes
    historico = {}
    for doenca, nome in DOENCAS.items():
        anos = baixar(doenca, PRIMEIRO_ANO, hoje.year)
        historico[nome] = anos.groupby(anos["SE"] // 100)["casos_est"].sum().round().astype(int)
    historico = pd.DataFrame(historico).fillna(0).astype(int).rename_axis("Ano").reset_index()
    historico.to_csv(os.path.join(PASTA_COMPONENTES, "comp_325_historico.csv"), sep=";", index=False,
                     encoding="utf-8")
    print(historico.to_string(index=False))

    semana = ultimas.iloc[-1]
    print(f"Última semana: {semana['SE']} ({semana['data_iniSE']}), nível {NIVEIS[semana['nivel']]}")

    componente = {
        "id": 325, "titulo": "Alerta de dengue", "fonte": "InfoDengue | Fiocruz e FGV",
        "atualizacao": "Semanal", "icone": "coronavirus", "area": "Município de Oriximiná",
        "resumo": "Casos de dengue das últimas semanas, com a cor do nível de alerta de cada semana.",
        "descricao": (
            f"Mostra os casos de dengue de Oriximiná nas últimas {SEMANAS_NO_CARTAO} semanas epidemiológicas "
            "(cada coluna tem a data do domingo em que a semana começa). "
            "A cor de cada coluna é o nível de alerta daquela semana, calculado pelo InfoDengue (Fiocruz e FGV) "
            "a partir dos casos notificados e do clima: verde, sem risco; amarelo, clima favorável ao mosquito "
            "Aedes aegypti; laranja, transmissão em alta; vermelho, epidemia. Como os casos chegam com atraso, os "
            "números das semanas mais recentes são os casos estimados pelo InfoDengue e ainda podem mudar. O "
            "histórico mostra os casos por ano de dengue, chikungunya e zika, as três doenças do mesmo mosquito. "
            "Em Taipei, este cartão é o alerta de enterovírus, doença que no Brasil não é de notificação "
            "obrigatória; a dengue é o alerta semanal de doença que existe para Oriximiná."),
        "exemplo": ("Avisa quando a dengue começa a subir, para a Prefeitura reforçar a visita dos agentes de "
                    "endemias, os mutirões contra o mosquito e o atendimento nas unidades de saúde."),
        "tipos": ["colunas"],
        "cores": ["#56B96D", "#F8CF58", "#F49F36", "#F65658"],
        "unidade": "casos", "meta": None, "maximo": None,
        "links": [{"nome": "InfoDengue – boletim de Oriximiná",
                   "url": "https://info.dengue.mat.br/alerta/1505304/dengue"},
                  {"nome": "InfoDengue – sobre os níveis de alerta", "url": "https://info.dengue.mat.br"}],
        "colaboradores": [], "mapa": None, "historico": {"tipo": "arquivo"},
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    componentes = config.setdefault("componentes_novos", {})
    saude = config.get("paineis_publicos", {}).get("saude")
    # Só grava o admin_painel.json quando algo muda (a atualização semanal só troca os CSV)
    if componentes.get("comp_325") != componente or (saude and "comp_325" not in saude["cartoes"]):
        componentes["comp_325"] = componente
        if saude and "comp_325" not in saude["cartoes"]:
            saude["cartoes"].append("comp_325")
        with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
            json.dump(config, arquivo, ensure_ascii=False, indent=2)
        print("admin_painel.json atualizado; painel Saúde:", saude["cartoes"] if saude else "não encontrado")


if __name__ == "__main__":
    main()
