"""Prepara o cartão "Chuva em Oriximiná" (no lugar da "Densidade da estação meteorológica" do Taipei), no painel
"Meio ambiente sustentável".

Fonte: as estações de chuva (pluviométricas) da ANA, a Agência Nacional de Águas, pelo serviço público
http://telemetriaws1.ana.gov.br/ServiceANA.asmx:
- a estação 00155000 – ORIXIMINÁ, na sede: a chuva lida à mão todo dia desde 1968 (HidroSerieHistorica);
- os meses mais recentes, que a série ainda não tem, vêm do pluviômetro automático da estação 16900000, no
  mesmo lugar (DadosHidrometeorologicos, chuva de 15 em 15 minutos);
- o inventário das estações de chuva do município, para o mapa (HidroInventario).

- comp_340.csv: a chuva de cada um dos últimos 13 meses e o normal de cada mês (média desde 1970)
- comp_340_historico.csv: a chuva de cada ano
- comp_340_mapa.csv: onde ficam as estações de chuva da ANA em Oriximiná

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_chuva.py
"""
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
SERVICO = "http://telemetriaws1.ana.gov.br/ServiceANA.asmx"
PLUVIOMETRO = "00155000"   # régua da chuva na sede
TELEMETRIA = "16900000"    # estação automática no mesmo lugar (manda a chuva junto com o nível do rio)
INICIO_NORMAL = 1970
MESES_NO_CARTAO = 13
DIAS_MINIMOS = 25          # mês com menos dias medidos não entra na conta (a chuva ficaria menor)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_POR_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                     "setembro", "outubro", "novembro", "dezembro"]
CHUVA_MES, NORMAL_MES = "Chuva do mês (mm)", "Normal do mês (média desde 1970)"
CHUVA_ANO = "Chuva no ano (mm)"


def baixar_xml(url):
    for tentativa in range(5):   # o servidor da ANA às vezes corta a conexão
        try:
            with urllib.request.urlopen(url, timeout=300) as resposta:
                return ET.fromstring(resposta.read())
        except (OSError, ET.ParseError) as erro:
            print(f"ANA não respondeu ({erro}); tentando de novo...")
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"O servidor da ANA não respondeu: {url}")


def chuva_diaria(hoje):
    """Chuva de cada dia na sede (mm), pela régua lida à mão. Vale a versão conferida (consistência 2)."""
    raiz = baixar_xml(f"{SERVICO}/HidroSerieHistorica?codEstacao={PLUVIOMETRO}&dataInicio=01/01/1960"
                      f"&dataFim={hoje:%d/%m/%Y}&tipoDados=2&nivelConsistencia=")
    dias = {}
    for linha in raiz.iter("SerieHistorica"):
        mes = pd.Timestamp(linha.find("DataHora").text.strip()).normalize().replace(day=1)
        consistencia = int(linha.find("NivelConsistencia").text)
        for dia in range(1, 32):
            campo = linha.find(f"Chuva{dia:02d}")
            if campo is None or not (campo.text or "").strip():
                continue
            data = mes + pd.Timedelta(days=dia - 1)
            if data.month == mes.month and (data not in dias or consistencia >= dias[data][0]):
                dias[data] = (consistencia, float(campo.text))
    return pd.Series({d: v for d, (_, v) in dias.items()}, dtype=float).sort_index()


def chuva_telemetria(inicio, fim):
    """Chuva de cada dia pelo pluviômetro automático (soma das leituras de 15 em 15 minutos)."""
    leituras = []
    for comeco in pd.date_range(inicio.replace(day=1), fim, freq="MS"):
        final = min(comeco + pd.offsets.MonthEnd(0), fim)
        raiz = baixar_xml(f"{SERVICO}/DadosHidrometeorologicos?codEstacao={TELEMETRIA}"
                          f"&dataInicio={comeco:%d/%m/%Y}&dataFim={final:%d/%m/%Y}")
        for item in raiz.iter("DadosHidrometereologicos"):
            chuva = (item.find("Chuva").text or "").strip() if item.find("Chuva") is not None else ""
            if chuva:
                leituras.append((pd.Timestamp(item.find("DataHora").text.strip()), float(chuva)))
    if not leituras:
        return pd.Series(dtype=float)
    serie = pd.Series(dict(leituras)).sort_index()
    serie = serie[~serie.index.duplicated()]
    return serie.resample("D").sum()


def estacoes():
    url = (f"{SERVICO}/HidroInventario?codEstDE=&codEstATE=&tpEst=2&nmEst=&nmRio=&codSubBacia=&codBacia="
           f"&nmMunicipio={urllib.parse.quote('ORIXIMINÁ')}&nmEstado=&sgResp=&sgOper=&telemetrica=")
    linhas = []
    for estacao in baixar_xml(url).iter("Table"):
        def campo(nome):
            item = estacao.find(nome)
            return (item.text or "").strip() if item is not None and item.text else ""
        if campo("Operando") != "1":
            continue
        nome = " ".join(campo("Nome").title().split())
        for errado, certo in ((" Da ", " da "), (" Do ", " do "), (" De ", " de "), ("Cach ", "Cachoeira "),
                              (" - Conj 1", ""), (" Conjunto 1", "")):
            nome = nome.replace(errado, certo)
        inicio = pd.to_datetime(campo("PeriodoPluviometroInicio"), errors="coerce")
        linhas.append({"Estação": nome, "Latitude": float(campo("Latitude")), "Longitude": float(campo("Longitude")),
                       "Mede a chuva desde": int(inicio.year) if pd.notna(inicio) else "",
                       "Manda os dados sozinha": "Sim" if campo("TipoEstacaoTelemetrica") == "1" else "Não",
                       "Código ANA": campo("Codigo")})
    return pd.DataFrame(linhas)


def main():
    hoje = pd.Timestamp.now(tz="America/Santarem").tz_localize(None).normalize()
    diaria = chuva_diaria(hoje)
    ultimo_regua = diaria.index.max()
    automatica = chuva_telemetria(ultimo_regua + pd.Timedelta(days=1), hoje)
    diaria = pd.concat([diaria, automatica[automatica.index > ultimo_regua]]).sort_index()
    print(f"Régua: {diaria.index.min():%m/%Y} a {ultimo_regua:%d/%m/%Y}; automática até {diaria.index.max():%d/%m/%Y}")

    contagem = diaria.resample("MS").count()
    mensal = diaria.resample("MS").sum()
    completos = mensal[(contagem >= DIAS_MINIMOS) & (mensal.index.year >= INICIO_NORMAL)
                       & (mensal.index < hoje.replace(day=1))]
    anteriores = completos[completos.index.year < hoje.year]
    normal = anteriores.groupby(anteriores.index.month).mean()
    ultimos = mensal[mensal.index >= (hoje.replace(day=1) - pd.DateOffset(months=MESES_NO_CARTAO - 1))]
    rotulos = [f"{MESES[m.month - 1]}/{m.year % 100:02d}" for m in ultimos.index]
    if diaria.index[-1] < ultimos.index[-1] + pd.offsets.MonthEnd(0):
        rotulos[-1] = f"até {diaria.index[-1].day}/{MESES[diaria.index[-1].month - 1]}"   # mês pela metade
    tabela = pd.DataFrame({"Mês": rotulos, CHUVA_MES: ultimos.round().astype(int).values,
                           NORMAL_MES: normal.reindex(ultimos.index.month).round().astype(int).values})
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_340.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    # Histórico: só os anos com os 12 meses medidos
    meses_bons = completos.groupby(completos.index.year).size()
    anos = completos.groupby(completos.index.year).sum()[meses_bons == 12].round().astype(int)
    anos.rename(CHUVA_ANO).rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_340_historico.csv"), sep=";", index=False, encoding="utf-8")

    mapa = estacoes()
    mapa.to_csv(os.path.join(PASTA_COMPONENTES, "comp_340_mapa.csv"), sep=";", index=False, encoding="utf-8")
    print(mapa.to_string(index=False))

    media_ano = anos.mean()
    media_texto = f"{media_ano:,.0f}".replace(",", ".")   # 2.435 (só no número: o resto do texto tem vírgulas)
    mais_chuvoso = MESES_POR_EXTENSO[int(normal.idxmax()) - 1]
    mais_seco = MESES_POR_EXTENSO[int(normal.idxmin()) - 1]
    ultimos_cheios = tabela.iloc[:-1] if rotulos[-1].startswith("até") else tabela
    acima = int((ultimos_cheios[CHUVA_MES] > ultimos_cheios[NORMAL_MES]).sum())
    componente = {
        "id": 340, "titulo": "Chuva em Oriximiná", "fonte": "ANA | Estações de chuva",
        "atualizacao": "Diária", "icone": "rainy", "area": "Sede de Oriximiná",
        "resumo": "Quanto choveu na sede de Oriximiná em cada mês, comparado com o normal, e as estações de chuva.",
        "descricao": (
            f"Mostra quanto choveu na sede de Oriximiná em cada um dos últimos {MESES_NO_CARTAO} meses, em "
            "milímetros, ao lado do normal daquele mês (a média desde 1970), medido pela estação de chuva da ANA "
            "(Agência Nacional de Águas) na cidade. Em Oriximiná chove em média "
            f"{media_texto} mm por ano; o mês mais chuvoso costuma ser {mais_chuvoso} "
            f"e o mais seco, {mais_seco}. Dos últimos meses completos, {acima} de {len(ultimos_cheios)} tiveram "
            "chuva acima do normal. Os meses mais recentes vêm do pluviômetro automático, que manda a chuva a "
            "cada 15 minutos; se ele falha alguns dias, o mês pode aparecer com menos chuva do que caiu. O "
            "histórico mostra a chuva de cada ano. O mapa (e a Comparação de mapas) mostra as "
            f"{len(mapa)} estações de chuva da ANA em Oriximiná. Nenhuma delas mede o vento ou a temperatura; "
            "em Taipei, este cartão mostra as estações meteorológicas completas."),
        "exemplo": ("Mostra se o ano está mais seco ou mais chuvoso que o normal, o que ajuda a prever cheias, "
                    "secas, queimadas e a época de plantar."),
        "tipos": ["colunas", "linha_tempo_separada"],
        "cores": ["#24B0DD", "#bdbdbd"],
        "unidade": "mm", "meta": None, "maximo": None,
        "links": [{"nome": "ANA – HidroWeb (estação 00155000, Oriximiná)",
                   "url": "https://www.snirh.gov.br/hidroweb/serieshistoricas"}],
        "colaboradores": [], "mapa": {"tipo": "pontos", "nome": "Estações de chuva (ANA)", "cor": "#7d9be0"},
        "historico": {"tipo": "arquivo"},
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_340"] = componente   # o texto traz os meses recentes
    painel = config.get("paineis_publicos", {}).get("ambiente")
    if painel and "comp_340" not in painel["cartoes"]:
        painel["cartoes"].append("comp_340")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Meio ambiente sustentável:", painel["cartoes"] if painel else "—")


if __name__ == "__main__":
    main()
