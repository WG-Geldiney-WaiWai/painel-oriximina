"""Prepara o cartão "Estabelecimentos de saúde por tipo" (no lugar dos cartões do Taipei de consultórios de
clínica geral, de medicina interna e de farmácias), no painel "Saúde".

Fontes:
- CNES (Cadastro Nacional de Estabelecimentos de Saúde), pelo TabNet do DATASUS
  (http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/estabpa.def): os estabelecimentos de Oriximiná por
  tipo, em dezembro de cada ano e no mês mais recente;
- RAIS (Ministério do Trabalho), arquivo de estabelecimentos já guardado pelo preparar_industria_alimentos.py
  em PASTA_FONTES/RAIS_ESTAB/oriximina_ANO.csv: as farmácias e drogarias (CNAE 4771), porque a maioria das
  drogarias não se cadastra no CNES.

- comp_343.csv: estabelecimentos de cada tipo no mês mais recente (e as farmácias e drogarias da RAIS)
- comp_343_historico.csv: estabelecimentos de cada tipo, ano a ano (CNES)

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_estabelecimentos_saude.py
"""
import glob
import html
import json
import os
import re
import urllib.parse
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_RAIS = os.path.join(PASTA_FONTES, "RAIS_ESTAB")
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
CODIGO_TABNET = "85"   # Oriximiná na lista de municípios do Pará no TabNet
PRIMEIRO_ANO = 2010
MESES_TABNET = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
POSTOS = "Postos e Unidades Básicas"
HOSPITAIS = "Hospitais"
CLINICAS = "Clínicas e consultórios"
EXAMES = "Laboratórios e exames"
INDIGENA = "Saúde indígena"
MOVEIS = "Unidades móveis (barco e SAMU)"
OUTROS = "Outros (vigilância e gestão)"
FARMACIAS = "Farmácias e drogarias"
# Tipo no CNES (começo do nome) -> grupo do cartão
GRUPOS = {
    "POSTO DE SAUDE": POSTOS, "CENTRO DE SAUDE": POSTOS,
    "HOSPITAL": HOSPITAIS, "PRONTO": HOSPITAIS, "UNIDADE MISTA": HOSPITAIS,
    "POLICLINICA": CLINICAS, "CONSULTORIO": CLINICAS, "CLINICA": CLINICAS,
    "UNIDADE DE APOIO DIAGNOSE": EXAMES, "LABORATORIO": EXAMES,
    "UNIDADE DE ATENCAO A SAUDE INDIGENA": INDIGENA,
    "UNIDADE MOVEL": MOVEIS,
    "FARMACIA": FARMACIAS,
}
ORDEM = [POSTOS, CLINICAS, HOSPITAIS, EXAMES, INDIGENA, MOVEIS, OUTROS]


def baixar(url, dados=None):
    pedido = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0",
                                                              "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=180) as resposta:
        return resposta.read().decode("latin-1")


def cnes():
    formulario = baixar("http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/estabpa.def")
    ultimo = max(set(re.findall(r"stpa(\d{4})\.dbf", formulario)))
    ano_ultimo = 2000 + int(ultimo[:2])
    arquivos = [f"stpa{a % 100:02d}12.dbf" for a in range(PRIMEIRO_ANO, ano_ultimo)] + [f"stpa{ultimo}.dbf"]
    campos = [("Linha", "Tipo_de_Estabelecimento"), ("Coluna", "Ano/mês_compet."), ("Incremento", "Quantidade"),
              ("SMunicípio", CODIGO_TABNET), ("formato", "table"), ("mostre", "Mostra")]
    campos += [("Arquivos", a) for a in arquivos]
    corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode("ascii")
    pagina = baixar("http://tabnet.datasus.gov.br/cgi/tabcgi.exe?cnes/cnv/estabpa.def", corpo)
    if "ORIXIMINA" not in pagina.upper():
        raise RuntimeError("O TabNet não devolveu a tabela de Oriximiná")
    pagina = pagina[pagina.upper().find('CLASS="TABDADOS"'):]
    pagina = pagina[:pagina.upper().find("</TABLE>")]
    linhas = []
    for linha in re.split(r"(?i)<tr", pagina)[1:]:
        celulas = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.split(r"(?i)<t[dh][^>]*>", linha)[1:]]
        if celulas:
            linhas.append(celulas)
    cabecalho = next(l for l in linhas if l[0].startswith("Tipo"))
    competencias = cabecalho[1:]
    por_tipo = {}
    for celulas in linhas:
        if len(celulas) == len(cabecalho) and celulas[0] != "TOTAL" and not celulas[0].startswith("Tipo"):
            por_tipo[celulas[0]] = [int(c) if c.isdigit() else 0 for c in celulas[1:]]
    return pd.DataFrame(por_tipo, index=competencias).T, competencias


def grupo(tipo):
    for comeco, nome in GRUPOS.items():
        if tipo.startswith(comeco):
            return nome
    return OUTROS


def farmacias_rais():
    """Farmácias e drogarias (CNAE 4771) declaradas na RAIS, por ano."""
    contagem = {}
    for arquivo in glob.glob(os.path.join(PASTA_RAIS, "oriximina_*.csv")):
        ano = int(re.search(r"(\d{4})", os.path.basename(arquivo)).group(1))
        tabela = pd.read_csv(arquivo, sep=";", dtype=str)
        contagem[ano] = int(tabela["subclasse"].str.strip().str.zfill(7).str.startswith("4771").sum())
    return pd.Series(contagem).sort_index()


def main():
    por_tipo, competencias = cnes()
    por_grupo = por_tipo.groupby(por_tipo.index.map(grupo)).sum()
    farmacias_cnes = int(por_grupo.loc[FARMACIAS].iloc[-1]) if FARMACIAS in por_grupo.index else 0
    por_grupo = por_grupo.reindex(ORDEM, fill_value=0)
    ano_final, mes_final = competencias[-1].split("/")
    farmacias = farmacias_rais()

    agora = por_grupo.iloc[:, -1].astype(int)
    cartao = agora.copy()
    if len(farmacias):
        cartao[FARMACIAS] = int(farmacias.iloc[-1])
    pd.DataFrame({"Tipo": cartao.index, "Estabelecimentos": cartao.values}).to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_343.csv"), sep=";", index=False, encoding="utf-8")
    historico = por_grupo.T.copy()
    historico.index = [int(c.split("/")[0]) for c in competencias]
    historico.rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_343_historico.csv"), sep=";", index=False, encoding="utf-8")
    print(cartao.to_string())
    print(historico.to_string())

    mes_texto = f"{MESES[MESES_TABNET.index(mes_final)]}/{ano_final}"
    total_inicio = int(por_grupo.iloc[:, 0].sum())
    moveis = por_tipo[por_tipo.index.str.startswith("UNIDADE MOVEL")].iloc[:, -1]
    fluvial = int(moveis[moveis.index.str.contains("FLUVIAL")].sum())
    componente = {
        "id": 343, "titulo": "Estabelecimentos de saúde por tipo", "fonte": "DATASUS – CNES e Ministério do Trabalho – RAIS",
        "atualizacao": "Mensal", "icone": "local_pharmacy", "area": "Município de Oriximiná",
        "resumo": "Quantos postos, UBS, clínicas, hospitais, laboratórios e farmácias Oriximiná tem.",
        "descricao": (
            f"Mostra quantos estabelecimentos de saúde Oriximiná tem de cada tipo, segundo o CNES, o cadastro do "
            f"Ministério da Saúde, em {mes_texto}: {int(agora[POSTOS])} postos e unidades básicas de saúde, "
            f"{int(agora[CLINICAS])} clínicas, policlínicas e consultórios, {int(agora[HOSPITAIS])} hospitais, "
            f"{int(agora[EXAMES])} laboratórios e serviços de exames, {int(agora[INDIGENA])} unidades de saúde "
            f"indígena e {int(agora[MOVEIS])} unidades móveis"
            + (f" (entre elas {fluvial} fluvial, um barco de atendimento)" if fluvial else "") + ". "
            f"No CNES aparecem só {farmacias_cnes} farmácias, porque a maioria das drogarias não se cadastra nele"
            + (f"; por isso as farmácias e drogarias vêm da RAIS, do Ministério do Trabalho: "
               f"{int(farmacias.iloc[-1])} em {int(farmacias.index[-1])}, contra {int(farmacias.iloc[0])} em "
               f"{int(farmacias.index[0])}. " if len(farmacias) else ". ")
            + f"Em {PRIMEIRO_ANO}, o CNES tinha "
            f"{total_inicio} estabelecimentos (sem contar as farmácias); o histórico mostra cada tipo ano a ano. "
            "Os consultórios particulares nem sempre se cadastram no CNES, então podem ser mais. O mapa dos "
            "estabelecimentos de saúde está na Comparação de mapas. Em Taipei, estes cartões mostram os "
            "consultórios de clínica geral, de medicina interna e as farmácias."),
        "exemplo": ("Mostra onde a rede de saúde cresceu e o que falta (por exemplo, exames ou atendimento nos "
                    "rios), para planejar novas unidades e serviços."),
        "tipos": ["barras", "rosca"],
        "cores": ["#56B96D", "#24B0DD", "#F65658", "#F8CF58", "#c18ad8", "#7d9be0", "#bdbdbd", "#F49F36"],
        "unidade": "estabelecimentos", "meta": None, "maximo": None,
        "links": [{"nome": "DATASUS – TabNet: estabelecimentos do Pará (CNES)",
                   "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/estabpa.def"},
                  {"nome": "Ministério do Trabalho – microdados da RAIS (PDET)",
                   "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged"}],
        "colaboradores": [], "mapa": None, "historico": {"tipo": "arquivo"},
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_343"] = componente
    saude = config.get("paineis_publicos", {}).get("saude")
    if saude and "comp_343" not in saude["cartoes"]:
        saude["cartoes"].append("comp_343")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Saúde:", saude["cartoes"] if saude else "—")


if __name__ == "__main__":
    main()
