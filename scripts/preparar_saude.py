"""Prepara o painel "Saúde" de Oriximiná (como o "Distribuição de clínicas e hospitais de obstetrícia e
ginecologia" do Taipei), com os dados do DATASUS (TabNet):

- comp_319.csv: leitos de internação dos hospitais de Oriximiná por especialidade, do SUS e particulares
  (CNES, Cadastro Nacional de Estabelecimentos de Saúde, mês mais recente)
- comp_320.csv: nascimentos de bebês de mães que moram em Oriximiná, por ano e local do parto (SINASC)
- comp_321.csv: os mesmos nascimentos pelo número de consultas de pré-natal da mãe (SINASC)

Os cartões entram como componentes da administração (usuarios/admin_painel.json), no painel público "Saúde"
do grupo "Painel de Oriximiná".

Rode de novo para atualizar:  python preparar_saude.py
"""
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
TABNET = "http://tabnet.datasus.gov.br/cgi/"
CODIGO_TABNET = "85"   # Oriximiná na lista de municípios do Pará no TabNet
ANOS_NASCIMENTOS = range(2014, 2025)   # anos com dados finais do SINASC (os mais novos ainda são prévias)
TIPOS_LEITO = ["Cirúrgicos", "Clínicos", "Obstétrico", "Pediátrico", "Outras Especialidades", "Hospital/DIA"]


def baixar(url, dados=None):
    req = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0",
                                                           "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=180) as resposta:
        return resposta.read().decode("latin-1")


def tabnet(definicao, campos):
    """Consulta o TabNet do DATASUS e devolve as linhas da tabela (a 1ª é o cabeçalho)."""
    pagina = baixar(TABNET + "tabcgi.exe?" + definicao, urllib.parse.urlencode(campos, encoding="latin-1").encode())
    pagina = pagina[pagina.upper().find('CLASS="TABDADOS"'):]
    pagina = pagina[:pagina.upper().find("</TABLE>")]
    linhas = []
    for linha in re.split(r"(?i)<tr", pagina)[1:]:
        celulas = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.split(r"(?i)<t[dh][^>]*>", linha)[1:]]
        if len(celulas) > 1:
            linhas.append(celulas)
    return linhas


def numero(texto):
    """'1.380' -> 1380 (o TabNet usa ponto de milhar); '-' -> 0."""
    texto = texto.strip().replace(".", "")
    return int(texto) if texto.isdigit() else 0


def leitos():
    """(mês, tabela) dos leitos por especialidade no mês mais recente do CNES."""
    pagina = baixar(TABNET + "deftohtm.exe?cnes/cnv/leiintpa.def")
    arquivo, mes = re.search(r'(?i)<option[^>]*value="(ltpa\d{4}\.dbf)"[^>]*>\s*([^<\r\n]+)', pagina).groups()
    tabelas = {}
    for incremento in ("Qtd_existente", "Qtd_SUS"):
        linhas = tabnet("cnes/cnv/leiintpa.def", [
            ("Linha", "Especialidade"), ("Coluna", "--Não-Ativa--"), ("Incremento", incremento),
            ("Arquivos", arquivo), ("SMunicípio", CODIGO_TABNET), ("formato", "table"), ("mostre", "Mostra")])
        tabelas[incremento] = {l[0]: numero(l[1]) for l in linhas if l[0] in TIPOS_LEITO}
    df = pd.DataFrame([{"Especialidade": "Obstétricos (partos)" if t == "Obstétrico" else
                        ("Pediátricos" if t == "Pediátrico" else t),
                        "Leitos do SUS": tabelas["Qtd_SUS"].get(t, 0),
                        "Leitos particulares": tabelas["Qtd_existente"].get(t, 0) - tabelas["Qtd_SUS"].get(t, 0)}
                       for t in TIPOS_LEITO if tabelas["Qtd_existente"].get(t)])
    return mes.strip(), df


def nascimentos(coluna):
    """Nascimentos de mães que moram em Oriximiná, por ano e pela coluna pedida do SINASC."""
    campos = [("Linha", "Ano_do_nascimento"), ("Coluna", coluna), ("Incremento", "Nascim_p/resid.mãe"),
              ("SMunicípio", CODIGO_TABNET), ("formato", "table"), ("mostre", "Mostra")]
    campos += [("Arquivos", f"nvpa{ano % 100:02d}.dbf") for ano in ANOS_NASCIMENTOS]
    linhas = tabnet("sinasc/cnv/nvpa.def", campos)
    cabecalho = next(l for l in linhas if l[0].startswith("Ano"))
    df = pd.DataFrame([l for l in linhas if l[0].isdigit()], columns=cabecalho)
    df = df.rename(columns={cabecalho[0]: "Ano"}).drop(columns=["Total"], errors="ignore")
    for c in df.columns[1:]:
        df[c] = df[c].map(numero)
    df["Ano"] = df["Ano"].astype(int)
    return df[df["Ano"].isin(ANOS_NASCIMENTOS)].reset_index(drop=True)


def salvar(chave, df):
    df.to_csv(os.path.join(PASTA_COMPONENTES, f"{chave}.csv"), sep=";", index=False, encoding="utf-8")
    print(f"{chave}.csv")
    print(df.to_string(index=False))


def fmt(n):
    return f"{int(n):,}".replace(",", ".")


def componente(id_, titulo, fonte, atualizacao, icone, resumo, descricao, exemplo, tipos, cores, unidade, links):
    return {"id": id_, "titulo": titulo, "fonte": fonte, "atualizacao": atualizacao, "icone": icone,
            "area": "Município de Oriximiná", "resumo": resumo, "descricao": descricao, "exemplo": exemplo,
            "tipos": tipos, "cores": cores, "unidade": unidade, "meta": None, "maximo": None, "links": links,
            "colaboradores": [], "mapa": None, "historico": None}


def main():
    mes, df_leitos = leitos()
    salvar("comp_319", df_leitos)

    # Local do parto: hospital, outro estabelecimento, domicílio, aldeia indígena...
    df_local = nascimentos("Local_ocorrência")
    nomes_local = {"Hospital": "Hospital", "Outro Estabelecimento de Saúde": "Outro estabelecimento de saúde",
                   "Domicílio": "Em casa", "Aldeia indígena": "Aldeia indígena", "Outro": "Outro lugar",
                   "Ignorado": "Não informado"}
    df_local = df_local.rename(columns=nomes_local)
    salvar("comp_320", df_local)

    # Consultas de pré-natal (a recomendação do Ministério da Saúde é 7 ou mais)
    df_pre = nascimentos("Consult_pré-natal")
    juntas = {"De 1 a 3 consultas": "1 a 6 consultas", "De 4 a 6 consultas": "1 a 6 consultas",
              "De 1 a 6 consultas, não especificado": "1 a 6 consultas"}
    df_pre = df_pre.T.groupby(lambda c: juntas.get(c, c)).sum().T
    ordem = ["Ano", "7 ou mais consultas", "1 a 6 consultas", "Nenhuma", "Ignorado"]
    df_pre = df_pre[[c for c in ordem if c in df_pre.columns]].rename(
        columns={"Nenhuma": "Nenhuma consulta", "Ignorado": "Não informado"})
    salvar("comp_321", df_pre)

    obst = df_leitos[df_leitos["Especialidade"].str.startswith("Obst")]
    leitos_total = int(df_leitos[["Leitos do SUS", "Leitos particulares"]].sum().sum())
    leitos_sus = int(df_leitos["Leitos do SUS"].sum())
    ultimo = df_local.iloc[-1]
    ano = int(ultimo["Ano"])
    total_ultimo = int(ultimo.drop("Ano").sum())
    # Fora de unidade de saúde: em casa, em aldeia indígena ou em outro lugar (não conta "outro estabelecimento")
    fora_hospital = sum(int(ultimo.get(c, 0)) for c in ("Em casa", "Aldeia indígena", "Outro lugar"))
    media_nasc = df_local.drop(columns="Ano").sum(axis=1).mean()
    pre_ult = df_pre.iloc[-1]
    pre_prim = df_pre.iloc[0]
    sete = pre_ult.get("7 ou mais consultas", 0) / pre_ult.drop("Ano").sum()
    sete_antes = pre_prim.get("7 ou mais consultas", 0) / pre_prim.drop("Ano").sum()

    link_cnes = {"nome": "DATASUS – TabNet, leitos de internação (CNES, Pará)",
                 "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/leiintpa.def"}
    link_sinasc = {"nome": "DATASUS – TabNet, nascidos vivos (SINASC, Pará)",
                   "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?sinasc/cnv/nvpa.def"}
    componentes = {
        "comp_319": componente(
            319, "Leitos hospitalares por especialidade", "Ministério da Saúde | DATASUS – CNES", mes, "bar_chart",
            "Leitos de internação dos hospitais de Oriximiná por especialidade, do SUS e particulares.",
            f"Mostra os {fmt(leitos_total)} leitos de internação dos hospitais de Oriximiná em {mes}, por "
            f"especialidade, segundo o Cadastro Nacional de Estabelecimentos de Saúde (CNES): {fmt(leitos_sus)} "
            f"atendem pelo SUS. Os leitos obstétricos, para partos e gestantes, são "
            f"{fmt(obst[['Leitos do SUS', 'Leitos particulares']].sum().sum())} "
            f"({fmt(obst['Leitos do SUS'].sum())} do SUS), quase todos na maternidade da cidade. Para comparar: "
            f"nascem em média {fmt(media_nasc)} bebês por ano de mães de Oriximiná (cartão \"Nascimentos por ano e "
            "local do parto\"). Leitos de UTI e de observação não entram nesta conta do CNES.",
            "Ajuda a planejar a rede hospitalar: mostra se os leitos de maternidade, pediatria e clínica "
            "acompanham o número de nascimentos e a população, e quanto depende do SUS.",
            ["barras", "mapa_arvore"], ["#24B0DD", "#a0b8e8"], "leitos", [link_cnes]),
        "comp_320": componente(
            320, "Nascimentos por ano e local do parto", "Ministério da Saúde | DATASUS – SINASC", str(ano),
            "show_chart",
            "Bebês de mães que moram em Oriximiná, por ano, e onde nasceram: hospital, em casa, aldeia.",
            f"Mostra quantos bebês de mães que moram em Oriximiná nasceram a cada ano, de "
            f"{ANOS_NASCIMENTOS[0]} a {ano}, e onde foi o parto, segundo o Sistema de Informações sobre Nascidos "
            f"Vivos (SINASC). Em {ano} foram {fmt(total_ultimo)} nascimentos, {fmt(fora_hospital)} fora de uma unidade de "
            "saúde (em casa, em aldeia indígena ou em outro lugar): no interior, com comunidades longe da "
            "cidade e acesso por rio, parte dos partos ainda acontece em casa. Conta pelo lugar onde a mãe mora, "
            "mesmo que o parto tenha sido em outra cidade (como Santarém). Os anos seguintes ainda são prévias do "
            "Ministério da Saúde e ficam de fora até virarem dados finais.",
            "Ajuda a planejar a maternidade e o transporte de gestantes do interior: os partos fora do hospital "
            "mostram onde fortalecer o pré-natal, as parteiras e a remoção para a cidade.",
            ["linha_tempo_empilhada", "colunas"],
            ["#24B0DD", "#56B96D", "#F49F36", "#c18ad8", "#F8CF58", "#bdbdbd"], "nascimentos", [link_sinasc]),
        "comp_321": componente(
            321, "Consultas de pré-natal", "Ministério da Saúde | DATASUS – SINASC", str(ano), "bar_chart",
            "Quantas mães de Oriximiná fizeram 7 ou mais consultas de pré-natal, por ano.",
            f"Mostra, para os bebês de mães que moram em Oriximiná, quantas consultas de pré-natal a mãe fez na "
            f"gravidez, a cada ano, segundo o SINASC. O Ministério da Saúde recomenda 7 consultas ou mais: em {ano}, "
            f"{sete:.0%} das mães chegaram a isso, contra {sete_antes:.0%} em {ANOS_NASCIMENTOS[0]}. Mães sem "
            "nenhuma consulta e com poucas consultas pedem atenção, sobretudo nas comunidades do interior.",
            "Mostra onde reforçar a atenção básica: mais consultas de pré-natal evitam complicações no parto e "
            "mortes de mães e bebês.",
            ["barras_percentuais", "linha_tempo_separada"],
            ["#56B96D", "#F8CF58", "#F65658", "#bdbdbd"], "nascimentos", [link_sinasc]),
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {}).update(componentes)
    paineis = config["paineis_publicos"]
    saude = {"titulo": "Saúde", "icone": "local_hospital", "cartoes": list(componentes), "grupo": "Painel de Oriximiná"}
    if "saude" in paineis:
        cartoes = paineis["saude"]["cartoes"]   # mantém a ordem escolhida
        cartoes += [c for c in componentes if c not in cartoes]
        paineis["saude"] = {**saude, "cartoes": cartoes}
    else:
        novos = {}   # no fim do grupo "Painel de Oriximiná" (antes dos painéis da Calha Norte)
        for chave, painel in paineis.items():
            if painel["grupo"] != "Painel de Oriximiná" and "saude" not in novos:
                novos["saude"] = saude
            novos[chave] = painel
        novos.setdefault("saude", saude)
        config["paineis_publicos"] = novos
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado: painel Saúde com", ", ".join(saude["cartoes"]))


if __name__ == "__main__":
    main()
