"""Prepara o painel "Tráfego rodoviário" de Oriximiná (como o "Tráfego rodoviário" do painel de Taipei).

Oriximiná não tem sensores de trânsito nas ruas (os do Taipei medem velocidade e fluxo em tempo real);
os cartões usam os dados oficiais que existem para o município:

- comp_301.csv: frota de veículos ano a ano, por tipo (IBGE Cidades, com os dados da SENATRAN)
- comp_302.csv: como é a frota no último ano
- comp_303.csv: mortes de moradores em acidentes de transporte (DATASUS, SIM, CID-10 V01-V99)
- comp_304.csv: internações de moradores no SUS por acidentes de transporte (DATASUS, SIH)
- comp_309.csv: meio de transporte para ir ao trabalho (IBGE, Censo 2022; lido de regiao_transporte_meio.csv,
  feito pelo preparar_transporte.py). Oriximiná não tem bicicletas compartilhadas (o YouBike do Taipei), mas o
  Censo mostra quantos vão de bicicleta, de moto, a pé ou de barco

Os cartões entram como componentes da administração (usuarios/admin_painel.json), no painel público
"Tráfego rodoviário" do grupo "Painel de Oriximiná", junto do mapa da rede viária.

Rode de novo para atualizar:  python preparar_trafego.py
"""
import gzip
import html
import json
import os
import re
import urllib.parse
import urllib.request

import pandas as pd

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")

CODIGO_IBGE = "1505304"
CODIGO_TABNET = "85"   # Oriximiná na lista de municípios do Pará no TabNet
# Anos com dados finais do SIM (os mais novos ainda são prévias e mudam)
ANOS_OBITOS = range(2010, 2025)
ANOS_INTERNACOES = range(2010, 2026)

# Tipos de veículo da pesquisa de frota do IBGE (pesquisa 22) agrupados no cartão
TIPOS_FROTA = {
    "Motocicletas e motonetas": ["28128", "28129"],
    "Automóveis": ["28122"],
    "Caminhonetes e utilitários": ["28125", "28126", "28132"],
    "Caminhões": ["28123"],
    "Ônibus e micro-ônibus": ["28130", "28127"],
}
TOTAL_FROTA = "28120"


def baixar(url, dados=None):
    req = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0",
                                                           "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=180) as resposta:
        conteudo = resposta.read()
    # O IBGE às vezes responde compactado (gzip), mesmo sem pedir
    return gzip.decompress(conteudo) if conteudo[:2] == bytes([0x1F, 0x8B]) else conteudo


def frota():
    """Frota de Oriximiná por tipo, de 2006 em diante (IBGE Cidades)."""
    codigos = [TOTAL_FROTA] + [c for lista in TIPOS_FROTA.values() for c in lista]
    url = (f"https://servicodados.ibge.gov.br/api/v1/pesquisas/22/periodos/all/indicadores/"
           f"{'%7C'.join(codigos)}/resultados/{CODIGO_IBGE}")
    series = {ind["id"]: ind["res"][0]["res"] for ind in json.loads(baixar(url))}
    linhas = []
    for ano in sorted(series[int(TOTAL_FROTA)]):
        linha = {"Ano": ano}
        for nome, lista in TIPOS_FROTA.items():
            linha[nome] = sum(int(series[int(c)].get(ano) or 0) for c in lista)
        linha["Outros"] = int(series[int(TOTAL_FROTA)][ano]) - sum(linha[n] for n in TIPOS_FROTA)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabnet(definicao, campos):
    """Consulta o TabNet do DATASUS e devolve a tabela (1ª linha = cabeçalho)."""
    corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode("ascii")
    pagina = baixar(f"http://tabnet.datasus.gov.br/cgi/tabcgi.exe?{definicao}", corpo).decode("latin-1")
    pagina = pagina[pagina.upper().find('CLASS="TABDADOS"'):]
    pagina = pagina[:pagina.upper().find("</TABLE>")]
    tabela = []
    for linha in re.split(r"(?i)<tr", pagina)[1:]:
        celulas = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.split(r"(?i)<t[dh][^>]*>", linha)[1:]]
        if celulas:
            tabela.append(celulas)
    cabecalho = next(t for t in tabela if t[0].startswith("Ano"))
    anos = [t for t in tabela if t[0].isdigit()]
    df = pd.DataFrame(anos, columns=cabecalho).replace("-", "0")
    df[cabecalho[1:]] = df[cabecalho[1:]].astype(int)
    df["Ano"] = df[cabecalho[0]].astype(int)
    return df


def coluna(df, comeco):
    """Soma das colunas cujo nome começa com o texto (as colunas sem nenhum caso não aparecem no TabNet)."""
    nomes = [c for c in df.columns if c.startswith(comeco)]
    return df[nomes].sum(axis=1) if nomes else 0


def obitos():
    """Mortes de moradores de Oriximiná em acidentes de transporte, por tipo de vítima (SIM)."""
    campos = [("Linha", "Ano_do_Óbito"), ("Coluna", "Grupo_CID10"), ("Incremento", "Óbitos_p/Residênc"),
              ("SMunicípio", CODIGO_TABNET), ("SGrande_Grupo_CID10", "1"),
              ("formato", "table"), ("mostre", "Mostra")]
    campos += [("Arquivos", f"extpa{ano % 100:02d}.dbf") for ano in ANOS_OBITOS]
    df = tabnet("sim/cnv/ext10pa.def", campos)
    df = df[df["Ano"].isin(ANOS_OBITOS)]
    return pd.DataFrame({
        "Ano": df["Ano"],
        "Motociclistas": coluna(df, "Motociclista"),
        "Pedestres e ciclistas": coluna(df, "Pedestre") + coluna(df, "Ciclista"),
        # (sem vírgula no nome: o painel adivinha o separador do CSV e confundia com ela)
        "Ocupantes de veículos": coluna(df, "Ocupante"),
        "Por água (barcos)": coluna(df, "Acidentes de transporte por"),
        "Outros e não especificados": coluna(df, "Outros acidentes"),
    })


def internacoes():
    """Internações no SUS de moradores de Oriximiná por acidentes de transporte (SIH, por residência)."""
    campos = [("Linha", "Ano_processamento"), ("Coluna", "Grupo_de_Causas"), ("Incremento", "Internações"),
              ("SMunicípio", CODIGO_TABNET), ("SGrande_Grup_Causas", "1"),
              ("formato", "table"), ("mostre", "Mostra")]
    campos += [("Arquivos", f"frpa{ano % 100:02d}{mes:02d}.dbf") for ano in ANOS_INTERNACOES for mes in range(1, 13)]
    df = tabnet("sih/cnv/frpa.def", campos)
    df = df[df["Ano"].isin(ANOS_INTERNACOES)]
    motos = coluna(df, "V20-V29")
    nao_especificados = coluna(df, "V98-V99")
    return pd.DataFrame({
        "Ano": df["Ano"],
        "Motociclistas": motos,
        "Outros tipos de vítima": df["Total"] - motos - nao_especificados,
        "Tipo não especificado": nao_especificados,
    })


def formatar(n):
    return f"{n:,}".replace(",", ".")


def salvar(chave, df):
    df.to_csv(os.path.join(PASTA_COMPONENTES, f"{chave}.csv"), sep=";", index=False, encoding="utf-8")
    print(f"{chave}.csv")
    print(df.to_string(index=False))


def componente(id_, titulo, fonte, atualizacao, icone, resumo, descricao, exemplo, tipos, cores, unidade, links):
    return {"id": id_, "titulo": titulo, "fonte": fonte, "atualizacao": atualizacao, "icone": icone,
            "area": "Município de Oriximiná", "resumo": resumo, "descricao": descricao, "exemplo": exemplo,
            "tipos": tipos, "cores": cores, "unidade": unidade, "meta": None, "maximo": None, "links": links,
            "colaboradores": [], "mapa": None, "historico": None}


def main():
    df_frota, df_obitos, df_intern = frota(), obitos(), internacoes()
    ultimo = df_frota.iloc[-1]
    ano_frota, total = int(ultimo["Ano"]), int(ultimo.drop("Ano").sum())
    primeiro = df_frota.iloc[0]
    total_antes = int(primeiro.drop("Ano").sum())
    df_composicao = pd.DataFrame({"Tipo de veículo": list(ultimo.index[1:]),
                                  "Veículos": [int(v) for v in ultimo.values[1:]]})
    motos = int(ultimo["Motocicletas e motonetas"])
    obitos_total, obitos_motos = int(df_obitos.drop(columns="Ano").sum().sum()), int(df_obitos["Motociclistas"].sum())
    recentes = df_intern[df_intern["Ano"] >= 2021]

    salvar("comp_301", df_frota)
    salvar("comp_302", df_composicao)
    salvar("comp_303", df_obitos)
    salvar("comp_304", df_intern)
    meios = pd.read_csv(os.path.join(PASTA_PROJETO, "dados", "regiao_transporte_meio.csv"), sep=";", dtype={"codigo": str})
    meios = meios[meios["codigo"] == CODIGO_IBGE].sort_values("pessoas", ascending=False)
    # Sem vírgula nos rótulos ("Ônibus, van ou pau de arara"): o painel adivinha o separador do CSV e se confundia
    df_meio = pd.DataFrame({"Meio de transporte": meios["Meio"].str.replace(", ", "/").values,
                            "Pessoas": meios["pessoas"].values})
    salvar("comp_309", df_meio)
    pessoas = int(df_meio["Pessoas"].sum())

    def parte(meio):
        return int(df_meio.loc[df_meio["Meio de transporte"] == meio, "Pessoas"].sum()) / pessoas

    link_frota = {"nome": "IBGE Cidades – Frota de veículos de Oriximiná",
                  "url": "https://cidades.ibge.gov.br/brasil/pa/oriximina/pesquisa/22/28120"}
    link_sim = {"nome": "DATASUS – TabNet, óbitos por causas externas (Pará)",
                "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?sim/cnv/ext10pa.def"}
    link_sih = {"nome": "DATASUS – TabNet, internações por causas externas (Pará)",
                "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?sih/cnv/frpa.def"}
    componentes = {
        "comp_301": componente(
            301, "Frota de veículos de Oriximiná", "IBGE Cidades | SENATRAN – Frota de veículos",
            str(ano_frota), "show_chart",
            "Veículos registrados em Oriximiná, ano a ano, por tipo.",
            f"Mostra quantos veículos estão registrados em Oriximiná a cada ano, por tipo, segundo a frota da "
            f"SENATRAN publicada pelo IBGE. A frota passou de {formatar(total_antes)} veículos em "
            f"{int(primeiro['Ano'])} para {formatar(total)} em {ano_frota}; as motocicletas e motonetas são "
            f"{formatar(motos)} ({motos / total:.0%}), o meio de transporte mais comum da cidade. A frota conta "
            "os veículos registrados no município, inclusive os que já não circulam (o registro só sai quando "
            "o dono dá baixa), por isso é uma medida do tamanho do trânsito, e não do movimento nas ruas.",
            "Ajuda a planejar a sinalização, a fiscalização e as campanhas de trânsito: com a frota de motos "
            "crescendo, faz sentido priorizar o uso do capacete, a habilitação e a segurança dos motociclistas.",
            ["linha_tempo_empilhada", "linha_tempo_separada"],
            ["#24B0DD", "#56B96D", "#F8CF58", "#F65658", "#9DC56E", "#a0b8e8"], "veículos", [link_frota]),
        "comp_302": componente(
            302, f"Composição da frota em {ano_frota}", "IBGE Cidades | SENATRAN – Frota de veículos",
            str(ano_frota), "donut_large",
            f"Divisão dos {formatar(total)} veículos de Oriximiná por tipo, em {ano_frota}.",
            f"Mostra como se dividem os {formatar(total)} veículos registrados em Oriximiná em {ano_frota}. "
            f"Motocicletas e motonetas são {motos / total:.0%} da frota; automóveis, "
            f"{int(ultimo['Automóveis']) / total:.0%}. Em \"Outros\" estão reboques, tratores, ciclomotores, "
            "triciclos e demais tipos.",
            "Mostra para quem o trânsito da cidade precisa ser pensado: numa frota de maioria de motos, "
            "estacionamentos, faixas e campanhas devem considerar principalmente os motociclistas.",
            ["rosca", "barras"],
            ["#24B0DD", "#56B96D", "#F8CF58", "#F65658", "#9DC56E", "#a0b8e8"], "veículos", [link_frota]),
        "comp_303": componente(
            303, "Mortes em acidentes de transporte", "Ministério da Saúde | DATASUS – SIM",
            str(ANOS_OBITOS[-1]), "bar_chart",
            "Moradores de Oriximiná que morreram em acidentes de transporte, por ano e tipo de vítima.",
            f"Mostra quantos moradores de Oriximiná morreram em acidentes de transporte (CID-10 V01 a V99) a "
            f"cada ano, de {ANOS_OBITOS[0]} a {ANOS_OBITOS[-1]}, segundo o Sistema de Informações sobre "
            f"Mortalidade. Foram {obitos_total} mortes no período, {obitos_motos} delas de motociclistas. "
            "Conta pelo lugar onde a pessoa morava, mesmo que o acidente ou a morte tenha sido em outra cidade. "
            "\"Ocupantes de veículos\" são os de carros, caminhonetes e caminhões. Inclui os acidentes de barco (\"por água\"), comuns na região. Os anos seguintes ainda são "
            "prévias do Ministério da Saúde e ficam de fora até virarem dados finais.",
            "Ajuda a ver quem mais morre no trânsito e a direcionar as ações: se a maioria das vítimas é de "
            "motociclistas, campanhas de capacete, fiscalização e atendimento rápido aos acidentados salvam "
            "mais vidas.",
            ["linha_tempo_empilhada", "colunas"],
            ["#F65658", "#F8CF58", "#24B0DD", "#56B96D", "#a0b8e8"], "mortes", [link_sim]),
        "comp_304": componente(
            304, "Internações por acidentes de transporte", "Ministério da Saúde | DATASUS – SIH/SUS",
            str(ANOS_INTERNACOES[-1]), "bar_chart",
            "Internações no SUS de moradores de Oriximiná por acidentes de transporte, por ano.",
            f"Mostra quantas vezes moradores de Oriximiná foram internados no SUS por acidentes de transporte, "
            f"a cada ano, segundo o Sistema de Informações Hospitalares (por ano de processamento da "
            f"internação). De 2021 a {ANOS_INTERNACOES[-1]} foram {int(recentes.drop(columns='Ano').sum().sum())} "
            f"internações, {int(recentes['Motociclistas'].sum())} de motociclistas. Atenção: até 2020 a maior "
            "parte das internações foi registrada sem o tipo de vítima (\"tipo não especificado\"); a subida "
            "dos motociclistas a partir de 2021 vem em parte do registro melhor, e não só de mais acidentes. "
            "Internações fora do SUS (planos de saúde e particulares) não entram.",
            "Mostra o peso dos acidentes de trânsito nos hospitais: ajuda a planejar leitos, ortopedia e "
            "reabilitação, e a medir o efeito das campanhas de segurança no trânsito.",
            ["linha_tempo_empilhada", "colunas"],
            ["#F65658", "#24B0DD", "#a0b8e8"], "internações", [link_sih]),
        "comp_309": componente(
            309, "Meio de transporte para ir ao trabalho", "IBGE | Censo 2022 – Trabalho e deslocamento",
            "Censo 2022", "donut_large",
            "Como os moradores de Oriximiná vão ao trabalho: moto, a pé, barco, bicicleta, carro, ônibus.",
            f"Mostra o meio de transporte em que os {formatar(pessoas)} moradores de Oriximiná que trabalham fora "
            f"de casa passam mais tempo no caminho para o trabalho, segundo o Censo 2022 (IBGE, tabela 10332). A "
            f"moto ou o mototáxi leva {parte('Motocicleta ou mototáxi'):.0%}; a pé vão {parte('A pé'):.0%}; de barco "
            f"ou lancha, {parte('Barco ou lancha'):.0%}; de bicicleta, {parte('Bicicleta'):.0%}; de carro ou táxi, "
            f"{parte('Automóvel ou táxi'):.0%}. Oriximiná não tem bicicletas compartilhadas (como o YouBike do "
            "Taipei), mas a bicicleta é um dos meios mais usados da cidade.",
            "Mostra para quem as ruas precisam ser feitas: com muita gente a pé, de bicicleta e de moto, calçadas, "
            "ciclofaixas, iluminação e a segurança dos motociclistas pesam mais que estacionamentos para carros.",
            ["rosca", "barras"],
            ["#24B0DD", "#56B96D", "#F8CF58", "#9DC56E", "#F65658", "#a0b8e8", "#c18ad8"], "pessoas",
            [{"nome": "IBGE – SIDRA, Censo 2022, tabela 10332",
              "url": "https://sidra.ibge.gov.br/tabela/10332"}]),
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {}).update(componentes)
    # O painel novo vai para o fim do grupo "Painel de Oriximiná" (antes dos painéis da Calha Norte)
    paineis = config["paineis_publicos"]
    trafego = {"titulo": "Tráfego rodoviário", "icone": "traffic",
               "cartoes": ["comp_301", "comp_302", "comp_309", "comp_303", "comp_304", "vias"],
               "grupo": "Painel de Oriximiná"}
    if "trafego" in paineis:
        # Mantém a ordem escolhida (na administração ou pelos outros scripts); um cartão novo deste script
        # entra logo depois da composição da frota
        cartoes = paineis["trafego"]["cartoes"]
        for chave in componentes:
            if chave not in cartoes:
                cartoes.insert(cartoes.index("comp_302") + 1 if "comp_302" in cartoes else len(cartoes), chave)
        paineis["trafego"] = {**trafego, "cartoes": cartoes}
        trafego = paineis["trafego"]
    else:
        novos = {}
        for chave, painel in paineis.items():
            if painel["grupo"] != "Painel de Oriximiná" and "trafego" not in novos:
                novos["trafego"] = trafego
            novos[chave] = painel
        novos.setdefault("trafego", trafego)
        config["paineis_publicos"] = novos
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado: painel \"Tráfego rodoviário\" com", ", ".join(trafego["cartoes"]))


if __name__ == "__main__":
    main()
