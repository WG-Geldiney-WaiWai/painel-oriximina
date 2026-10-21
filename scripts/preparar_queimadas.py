"""Prepara o cartão "Focos de queimada" (no lugar dos "Locais de risco de incêndio" do Taipei), no painel
"Mudança climática".

Fonte: o Programa Queimadas do INPE (Instituto Nacional de Pesquisas Espaciais), que publica cada foco de
fogo visto por satélite, com a posição: https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/
Para comparar os anos, o INPE usa um satélite só, o "satélite de referência" (AQUA, à tarde):
- anos fechados: arquivos anuais do satélite de referência (anual/Brasil_sat_ref/focos_br_ref_ANO.zip);
- ano atual: arquivos mensais com todos os satélites (mensal/Brasil/focos_mensal_br_AAAAMM.csv), dos quais
  ficam só os focos do satélite de referência. Esses arquivos são grandes (até 130 MB): o script lê enquanto
  baixa e guarda só as linhas de Oriximiná.

- comp_341.csv: focos de cada um dos últimos 13 meses e a média daquele mês (desde 2003)
- comp_341_historico.csv: focos de cada ano
- comp_341_mapa.csv: onde foram os focos dos últimos 12 meses, para o mapa e para a "Comparação de mapas"

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_queimadas.py
"""
import csv
import io
import json
import os
import time
import urllib.request
import zipfile

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_INPE = os.path.join(PASTA_FONTES, "INPE_queimadas")
ARQ_ANOS = os.path.join(PASTA_INPE, "oriximina_focos_anos_fechados.csv")
BASE = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv"
PRIMEIRO_ANO = 2003
SATELITE_REFERENCIA = "AQUA_M-T"
CODIGO_IBGE = "1505304"
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
MESES_NO_CARTAO = 13
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_POR_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                     "setembro", "outubro", "novembro", "dezembro"]
FOCOS_MES, MEDIA_MES = "Focos no mês", f"Média do mês (desde {PRIMEIRO_ANO})"
FOCOS_ANO = "Focos no ano"


def abrir(url, tentativas=4):
    for tentativa in range(tentativas):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                          timeout=600)
        except OSError as erro:
            if getattr(erro, "code", None) == 404:
                return None
            print(f"INPE não respondeu ({erro}); tentando de novo...")
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"O servidor do INPE não respondeu: {url}")


def focos_ano_fechado(ano):
    """Focos do satélite de referência em Oriximiná num ano fechado (arquivo anual do Brasil, ~6 MB)."""
    resposta = abrir(f"{BASE}/anual/Brasil_sat_ref/focos_br_ref_{ano}.zip")
    if resposta is None:
        return None
    with resposta:
        pacote = zipfile.ZipFile(io.BytesIO(resposta.read()))
    tabela = pd.read_csv(pacote.open(pacote.namelist()[0]), dtype=str)
    nossos = tabela[(tabela["municipio"].str.upper() == "ORIXIMINÁ") & (tabela["estado"].str.upper() == "PARÁ")]
    return pd.DataFrame({"data": pd.to_datetime(nossos["data_pas"]), "lat": nossos["lat"].astype(float),
                         "lon": nossos["lon"].astype(float)})


def focos_mes(ano, mes):
    """Focos do satélite de referência em Oriximiná num mês (lê o arquivo do Brasil enquanto baixa)."""
    resposta = abrir(f"{BASE}/mensal/Brasil/focos_mensal_br_{ano}{mes:02d}.csv")
    if resposta is None:
        return None
    linhas = []
    with resposta:
        texto = io.TextIOWrapper(resposta, encoding="utf-8", errors="replace")
        cabecalho = next(csv.reader([texto.readline()]))
        for linha in texto:
            if CODIGO_IBGE in linha and SATELITE_REFERENCIA in linha:
                linhas.append(dict(zip(cabecalho, next(csv.reader([linha])))))
    tabela = pd.DataFrame(linhas, columns=cabecalho)
    tabela = tabela[(tabela["municipio_id"] == CODIGO_IBGE) & (tabela["satelite"] == SATELITE_REFERENCIA)]
    return pd.DataFrame({"data": pd.to_datetime(tabela["data_hora_gmt"]), "lat": tabela["lat"].astype(float),
                         "lon": tabela["lon"].astype(float)})


def main():
    hoje = pd.Timestamp.now(tz="America/Santarem").tz_localize(None)
    os.makedirs(PASTA_INPE, exist_ok=True)
    guardados = pd.read_csv(ARQ_ANOS, parse_dates=["data"]) if os.path.exists(ARQ_ANOS) else pd.DataFrame(
        columns=["data", "lat", "lon", "ano"])
    anos_guardados = set(guardados["ano"].astype(int)) if len(guardados) else set()
    partes, fechados = [guardados], set(anos_guardados)
    for ano in range(PRIMEIRO_ANO, hoje.year):
        if ano in anos_guardados:
            continue
        focos = focos_ano_fechado(ano)
        if focos is not None:   # (o arquivo do ano anterior só sai alguns meses depois)
            partes.append(focos.assign(ano=ano))
            fechados.add(ano)
            print(f"{ano}: {len(focos)} focos")
    anos = pd.concat(partes, ignore_index=True)
    anos.to_csv(ARQ_ANOS, index=False)
    # Meses que ainda não estão num arquivo anual: o ano atual e, se faltar, o anterior
    recentes = []
    for ano in range(max(fechados) + 1 if fechados else hoje.year, hoje.year + 1):
        for mes in range(1, 13 if ano < hoje.year else hoje.month + 1):
            # Meses que já terminaram há mais de um mês ficam guardados (não mudam mais); os outros, de novo
            guardado = os.path.join(PASTA_INPE, f"oriximina_{ano}{mes:02d}.csv")
            fechado = pd.Timestamp(ano, mes, 1) + pd.DateOffset(months=2) <= hoje
            if fechado and os.path.exists(guardado):
                focos = pd.read_csv(guardado, parse_dates=["data"])
            else:
                focos = focos_mes(ano, mes)
                if focos is not None and fechado:
                    focos.to_csv(guardado, index=False)
            if focos is not None:
                recentes.append(focos)
                print(f"{MESES[mes - 1]}/{ano}: {len(focos)} focos")
    todos = pd.concat([anos[["data", "lat", "lon"]]] + recentes, ignore_index=True)
    todos["data"] = pd.to_datetime(todos["data"])

    por_mes = todos.set_index("data").resample("MS").size()
    por_mes = por_mes.reindex(pd.date_range(f"{PRIMEIRO_ANO}-01-01", hoje.replace(day=1), freq="MS"), fill_value=0)
    anteriores = por_mes[por_mes.index.year < hoje.year]
    media = anteriores.groupby(anteriores.index.month).mean()
    ultimos = por_mes.tail(MESES_NO_CARTAO)
    rotulos = [f"{MESES[m.month - 1]}/{m.year % 100:02d}" for m in ultimos.index]
    rotulos[-1] = f"até {hoje.day}/{MESES[hoje.month - 1]}"   # o mês atual ainda está pela metade
    tabela = pd.DataFrame({"Mês": rotulos, FOCOS_MES: ultimos.values,
                           MEDIA_MES: media.reindex(ultimos.index.month).round().astype(int).values})
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_341.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    por_ano = por_mes.groupby(por_mes.index.year).sum()
    # (a 1ª coluna do histórico precisa ser só o ano: o ano atual, ainda pela metade, fica explicado no texto)
    historico = por_ano.copy()
    historico.rename(FOCOS_ANO).rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_341_historico.csv"), sep=";", index=False, encoding="utf-8")

    ano_passado = todos[todos["data"] > hoje - pd.Timedelta(days=365)].sort_values("data")
    pd.DataFrame({"Foco": [f"Foco de {d:%d/%m/%Y}" for d in ano_passado["data"]],
                  "Latitude": ano_passado["lat"].round(5), "Longitude": ano_passado["lon"].round(5),
                  "Data": [f"{d:%d/%m/%Y}" for d in ano_passado["data"]]}).to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_341_mapa.csv"), sep=";", index=False, encoding="utf-8")

    fechados_ano = por_ano[por_ano.index < hoje.year]
    pico = int(fechados_ano.idxmax())
    pior_mes = MESES_POR_EXTENSO[int(media.idxmax()) - 1]
    # Compara o ano atual até o último mês completo com o mesmo período dos anos anteriores
    ultimo_completo = hoje.month - 1
    ate_hoje = por_mes[(por_mes.index.year == hoje.year) & (por_mes.index.month <= ultimo_completo)].sum()
    periodo = anteriores[anteriores.index.month <= ultimo_completo]
    media_ate_hoje = periodo.groupby(periodo.index.year).sum().mean()
    componente = {
        "id": 341, "titulo": "Focos de queimada", "fonte": "INPE | Programa Queimadas",
        "atualizacao": "Diária", "icone": "local_fire_department", "area": "Município de Oriximiná",
        "resumo": "Quantos focos de fogo os satélites viram em Oriximiná a cada mês, comparado com a média.",
        "descricao": (
            f"Mostra quantos focos de queimada os satélites viram em Oriximiná em cada um dos últimos "
            f"{MESES_NO_CARTAO} meses, ao lado da média daquele mês desde {PRIMEIRO_ANO}, segundo o Programa "
            "Queimadas do INPE. Para dar para comparar os anos, conta só o satélite de referência do INPE "
            "(AQUA, à tarde); somando todos os satélites, o número de focos é bem maior. As queimadas se "
            f"concentram no fim da seca, de setembro a novembro; o mês com mais fogo costuma ser {pior_mes}. "
            + (f"Em {hoje.year}, de janeiro a {MESES_POR_EXTENSO[ultimo_completo - 1]}, foram {int(ate_hoje)} "
               f"focos, contra uma média de {media_ate_hoje:.0f} no mesmo período dos anos anteriores. "
               if ultimo_completo >= 1 else "")   # (em janeiro ainda não há mês completo no ano)
            + f"O ano com mais focos foi {pico}, com "
            f"{int(fechados_ano[pico])}. Um foco é um ponto onde o satélite viu fogo; uma queimada grande pode "
            "ter vários focos, e fogo pequeno ou debaixo das árvores pode não aparecer. O histórico mostra os "
            f"focos de cada ano ({hoje.year} ainda não acabou), e o mapa (e a Comparação de mapas) mostra onde foram os focos dos últimos 12 "
            "meses. Em Taipei, este cartão mostra os prédios com risco de incêndio."),
        "exemplo": ("Avisa quando o fogo está acima do normal, para a Defesa Civil, os brigadistas e a Saúde se "
                    "prepararem, e mostra onde as queimadas se repetem."),
        "tipos": ["colunas", "linha_tempo_separada"],
        "cores": ["#F65658", "#bdbdbd"],
        "unidade": "focos", "meta": None, "maximo": None,
        "links": [{"nome": "INPE – Programa Queimadas (BDQueimadas)",
                   "url": "https://terrabrasilis.dpi.inpe.br/queimadas/bdqueimadas/"},
                  {"nome": "INPE – dados abertos dos focos",
                   "url": "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/"}],
        "colaboradores": [], "mapa": {"tipo": "pontos", "nome": "Focos de queimada (últimos 12 meses)",
                                      "cor": "#F49F36"},
        "historico": {"tipo": "arquivo"},
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_341"] = componente   # o texto traz o ano atual
    clima = config.get("paineis_publicos", {}).get("clima")
    if clima and "comp_341" not in clima["cartoes"]:
        clima["cartoes"].append("comp_341")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Mudança climática:", clima["cartoes"] if clima else "—")


if __name__ == "__main__":
    main()
