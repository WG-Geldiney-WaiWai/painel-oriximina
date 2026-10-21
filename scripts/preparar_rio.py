"""Prepara o painel "Uma cidade resistente a desastres" e o cartão "Nível do rio Trombetas" (como o
"Monitoramento do nível da água" do Taipei).

Fonte: a estação 16900000 – ORIXIMINÁ, da ANA (Agência Nacional de Águas), no rio Trombetas, na cidade.
Ela tem a régua lida à mão desde 1968 (série histórica) e uma régua automática que manda o nível a cada
15 minutos (telemetria). Os dois usam o mesmo zero da régua, em centímetros.

- comp_331.csv: o nível médio de cada um dos últimos 13 meses, ao lado do normal daquele mês (a média de
  todos os anos desde 1970; 1968 e 1969 têm muitas leituras erradas)
- comp_331_historico.csv: a maior cheia e a menor seca de cada ano

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_rio.py
"""
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
ESTACAO = "16900000"
SERVICO = "http://telemetriaws1.ana.gov.br/ServiceANA.asmx"
URL_HISTORICO = (f"{SERVICO}/HidroSerieHistorica?codEstacao={ESTACAO}&dataInicio=01/01/1960&dataFim={{fim}}"
                 "&tipoDados=1&nivelConsistencia=")
URL_TELEMETRIA = f"{SERVICO}/DadosHidrometeorologicos?codEstacao={ESTACAO}&dataInicio={{inicio}}&dataFim={{fim}}"
MESES_NO_CARTAO = 13
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_POR_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                     "setembro", "outubro", "novembro", "dezembro"]
NIVEL_MES, NORMAL_MES = "Nível médio do mês", "Normal do mês (média desde 1970)"
CHEIA, SECA = "Maior nível do ano (cheia)", "Menor nível do ano (seca)"
INICIO_CONFIAVEL = "1970-01-01"
FAIXA_POSSIVEL = (-500, 1500)   # cm na régua: fora disso é leitura errada (o rio nunca chegou perto)
SALTO_MAXIMO = 150   # cm de diferença para a mediana dos dias vizinhos (o rio muda poucos cm por dia)
DIAS_MINIMOS_NO_ANO = 300  # ano com poucas leituras fica fora do histórico (a cheia ou a seca podem faltar)


def baixar_xml(url):
    # O servidor da ANA às vezes corta a conexão no meio: tenta de novo algumas vezes
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(url, timeout=300) as resposta:
                return ET.fromstring(resposta.read())
        except (OSError, ET.ParseError) as erro:
            print(f"ANA não respondeu ({erro}); tentando de novo...")
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"O servidor da ANA não respondeu: {url}")


def serie_historica(fim):
    """Nível de cada dia pela régua lida à mão. A ANA manda uma linha por mês (Cota01 a Cota31) e às vezes
    duas versões do mesmo mês: a "consistida" (nível 2, já conferida) vale mais que a bruta (nível 1)."""
    raiz = baixar_xml(URL_HISTORICO.format(fim=fim.strftime("%d/%m/%Y")))
    dias = {}
    for linha in raiz.iter("SerieHistorica"):
        mes = pd.Timestamp(linha.find("DataHora").text.strip()).normalize()
        consistencia = int(linha.find("NivelConsistencia").text)
        for dia in range(1, 32):
            campo = linha.find(f"Cota{dia:02d}")
            if campo is None or not (campo.text or "").strip():
                continue
            data = mes.replace(day=1) + pd.Timedelta(days=dia - 1)
            if data.month != mes.month:
                continue
            anterior = dias.get(data)
            if anterior is None or consistencia >= anterior[0]:
                dias[data] = (consistencia, float(campo.text))
    return pd.Series({d: v for d, (_, v) in dias.items()}).sort_index()


def serie_telemetria(inicio, fim):
    """Nível de cada dia pela régua automática (média das leituras de 15 em 15 minutos), mês a mês."""
    leituras = []
    for comeco in pd.date_range(inicio.replace(day=1), fim, freq="MS"):
        final = min(comeco + pd.offsets.MonthEnd(0), fim)
        raiz = baixar_xml(URL_TELEMETRIA.format(inicio=comeco.strftime("%d/%m/%Y"), fim=final.strftime("%d/%m/%Y")))
        for item in raiz.iter("DadosHidrometereologicos"):
            nivel = (item.find("Nivel").text or "").strip()
            if nivel:
                leituras.append((pd.Timestamp(item.find("DataHora").text.strip()), float(nivel)))
    if not leituras:
        return pd.Series(dtype=float), None
    serie = pd.Series(dict(leituras)).sort_index()
    return serie.resample("D").mean().dropna(), serie


def main():
    hoje = pd.Timestamp.now(tz="America/Santarem").tz_localize(None).normalize()
    diario = serie_historica(hoje)
    ultimo_historico = diario.index.max()
    telemetria, leituras = serie_telemetria(ultimo_historico + pd.Timedelta(days=1), hoje)
    diario = pd.concat([diario, telemetria[telemetria.index > ultimo_historico]]).sort_index()
    # Leituras erradas (ex.: 9707 e -9749 em 1969): o rio não sobe nem desce metros de um dia para o outro,
    # então sai o dia que foge mais de SALTO_MAXIMO cm da mediana das duas semanas em volta
    # 1968 e 1969: os primeiros anos da régua têm muitas leituras erradas; a série começa em 1970
    diario = diario[(diario.index >= INICIO_CONFIAVEL) & diario.between(*FAIXA_POSSIVEL)]
    mediana = diario.rolling("15D", center=True, min_periods=3).median()
    errados = (diario - mediana).abs() > SALTO_MAXIMO
    print(f"Leituras descartadas: {int(errados.sum())}", diario[errados].to_dict())
    diario = diario[~errados]
    print(f"Régua: {diario.index.min():%d/%m/%Y} a {ultimo_historico:%d/%m/%Y}; "
          f"telemetria até {telemetria.index.max() if len(telemetria) else '—'}")

    mensal = diario.resample("MS").mean().dropna()
    anos_completos = mensal[mensal.index.year < hoje.year]
    normal = anos_completos.groupby(anos_completos.index.month).mean()
    ultimos = mensal.tail(MESES_NO_CARTAO)
    rotulos = [f"{MESES[m.month - 1]}/{m.year % 100:02d}" for m in ultimos.index]
    if diario.index[-1] < ultimos.index[-1] + pd.offsets.MonthEnd(0):
        rotulos[-1] = f"até {diario.index[-1].day}/{MESES[diario.index[-1].month - 1]}"   # mês atual pela metade
    tabela = pd.DataFrame({"Mês": rotulos, NIVEL_MES: ultimos.round().astype(int).values,
                           NORMAL_MES: normal.reindex(ultimos.index.month).round().astype(int).values})
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_331.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    contagem = diario.groupby(diario.index.year).size()
    anos_bons = contagem[contagem >= DIAS_MINIMOS_NO_ANO].index
    por_ano = diario[diario.index.year.isin(anos_bons)]
    historico = pd.DataFrame({CHEIA: por_ano.groupby(por_ano.index.year).max(),
                              SECA: por_ano.groupby(por_ano.index.year).min()}).round().astype(int)
    historico.rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_331_historico.csv"), sep=";", index=False, encoding="utf-8")

    # Números para o texto: o nível de agora, o normal deste mês e os recordes
    agora = leituras.iloc[-1] if leituras is not None else diario.iloc[-1]
    quando = leituras.index[-1] if leituras is not None else diario.index[-1]
    normal_agora = normal[quando.month]
    maior, menor = diario.idxmax(), diario.idxmin()
    menor_antes = diario[diario.index.year < hoje.year]
    recorde_seca = menor_antes.idxmin()
    print(f"Agora: {agora:.0f} cm em {quando}; normal de {MESES[quando.month - 1]}: {normal_agora:.0f}; "
          f"maior {diario.max():.0f} em {maior:%d/%m/%Y}; menor {diario.min():.0f} em {menor:%d/%m/%Y}")

    def data(d):
        return f"{d.day} de {MESES_POR_EXTENSO[d.month - 1]} de {d.year}"
    comparacao = ("abaixo" if agora < normal_agora else "acima")
    recorde = (f" É o nível mais baixo já registrado: o recorde anterior era {menor_antes.min():.0f} cm, em "
               f"{data(recorde_seca)}." if agora <= menor_antes.min() else
               f" O nível mais baixo já registrado foi {diario.min():.0f} cm, em {data(menor)}.")
    componente = {
        "id": 331, "titulo": "Nível do rio Trombetas", "fonte": "ANA | Estação 16900000 – Oriximiná",
        "atualizacao": "Diária", "icone": "water", "area": "Rio Trombetas, na sede de Oriximiná",
        "resumo": "O nível do rio Trombetas na cidade, mês a mês, comparado com o normal: cheias e secas.",
        "descricao": (
            "Mostra o nível médio do rio Trombetas em frente à cidade em cada um dos últimos 13 meses, ao lado "
            "do normal daquele mês (a média de todos os anos desde 1970), em centímetros na régua da ANA "
            "(Agência Nacional de Águas). O rio sobe de janeiro a junho, com a cheia, e desce até a seca, de "
            f"outubro a dezembro. Na última leitura ({quando:%d/%m/%Y} às {quando:%H:%M}), o rio estava em "
            f"{agora:.0f} cm, {abs(agora - normal_agora):.0f} cm {comparacao} do normal de "
            f"{MESES_POR_EXTENSO[quando.month - 1]} ({normal_agora:.0f} cm).{recorde} A maior cheia foi "
            f"{diario.max():.0f} cm, em {data(maior)}. O histórico mostra a maior cheia e a menor seca de cada "
            "ano. Os meses mais recentes vêm da régua automática, que manda o nível a cada 15 minutos."),
        "exemplo": ("Ajuda a Defesa Civil a se preparar para as cheias (famílias desalojadas nas áreas baixas) e "
                    "para as secas (barcos que não chegam às comunidades, falta de água e de peixe)."),
        "tipos": ["colunas", "linha_tempo_separada"],
        "cores": ["#24B0DD", "#bdbdbd"],
        "unidade": "cm", "meta": None, "maximo": None,
        "links": [{"nome": "ANA – HidroWeb, estação 16900000 (Oriximiná)",
                   "url": "https://www.snirh.gov.br/hidroweb/serieshistoricas"},
                  {"nome": "ANA – Sala de Situação (rios da Amazônia)",
                   "url": "https://www.gov.br/ana/pt-br/sala-de-situacao"}],
        "colaboradores": [], "mapa": None, "historico": {"tipo": "arquivo"},
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_331"] = componente   # o texto traz o nível do dia
    paineis = config.setdefault("paineis_publicos", {})
    if "desastres" not in paineis:
        # Painel novo, logo depois do "Mudança climática" (antes dos painéis da Calha Norte)
        novo = {"titulo": "Uma cidade resistente a desastres", "icone": "flood", "cartoes": ["comp_331"],
                "grupo": "Painel de Oriximiná"}
        ordem = list(paineis.items())
        chaves = [c for c, _ in ordem]
        depois = chaves.index("clima") + 1 if "clima" in chaves else len(ordem)
        ordem.insert(depois, ("desastres", novo))
        config["paineis_publicos"] = paineis = dict(ordem)
    elif "comp_331" not in paineis["desastres"]["cartoes"]:
        paineis["desastres"]["cartoes"].append("comp_331")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painéis:", list(paineis), paineis["desastres"]["cartoes"])


if __name__ == "__main__":
    main()
