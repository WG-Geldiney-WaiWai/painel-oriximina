"""Prepara o cartão "Equipes de Saúde da Família" (no lugar da "Distribuição das instituições médicas de
medicina de família" do Taipei), no painel "Saúde".

Fonte: CNES (Cadastro Nacional de Estabelecimentos de Saúde), pelo TabNet do DATASUS
(http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/equipepa.def): as equipes de saúde de Oriximiná
cadastradas em cada mês, por tipo. O cartão usa dezembro de cada ano e o mês mais recente. A população, para
saber quantas pessoas cada equipe atende, é a estimativa do IBGE (SIDRA 6579).

- comp_342.csv: equipes por tipo, a cada ano

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_saude_familia.py
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
PRIMEIRO_ANO = 2008
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_TABNET = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
# Tipo no cartão -> códigos do tipo de equipe no CNES (os nomes e códigos mudaram em 2020)
SAUDE_FAMILIA = "Saúde da Família"
TIPOS = {
    SAUDE_FAMILIA: [1, 2, 3, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 70],
    "Saúde bucal (dentista)": [71],
    "Agentes comunitários": [4, 10, 11],
    "Saúde indígena": [8, 9],
    "Apoio e outras": None,   # o resto (NASF, atenção básica, domiciliar...)
}
RIBEIRINHAS = [12, 13, 14, 15, 39]   # ribeirinha e fluvial (no barco)
PESSOAS_POR_EQUIPE = (2000, 3500)   # o que a Política Nacional de Atenção Básica (2017) recomenda


def baixar(url, dados=None):
    pedido = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0",
                                                              "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=180) as resposta:
        conteudo = resposta.read()
    # O IBGE às vezes responde compactado (gzip), mesmo sem pedir
    return gzip.decompress(conteudo) if conteudo[:2] == bytes([0x1F, 0x8B]) else conteudo


def ultimo_arquivo():
    """O arquivo mais novo do CNES (eppaAAMM.dbf) que o TabNet oferece."""
    formulario = baixar("http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/equipepa.def").decode("latin-1")
    return max(set(re.findall(r"eppa(\d{4})\.dbf", formulario)))


def equipes():
    ultimo = ultimo_arquivo()
    ano_ultimo = 2000 + int(ultimo[:2])
    arquivos = [f"eppa{a % 100:02d}12.dbf" for a in range(PRIMEIRO_ANO, ano_ultimo)] + [f"eppa{ultimo}.dbf"]
    campos = [("Linha", "Tipo_da_Equipe"), ("Coluna", "Ano/mês_compet."), ("Incremento", "Quantidade"),
              ("SMunicípio", CODIGO_TABNET), ("formato", "table"), ("mostre", "Mostra")]
    campos += [("Arquivos", a) for a in arquivos]
    corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode("ascii")
    pagina = baixar("http://tabnet.datasus.gov.br/cgi/tabcgi.exe?cnes/cnv/equipepa.def", corpo).decode("latin-1")
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
    competencias = cabecalho[1:]   # "2008/Dez" ... "2026/Set"
    tabela = {}
    for celulas in linhas:
        codigo = re.match(r"(\d+) ", celulas[0])
        if codigo and len(celulas) == len(cabecalho):
            tabela[int(codigo.group(1))] = [int(c) if c.isdigit() else 0 for c in celulas[1:]]
    return pd.DataFrame(tabela, index=competencias).T, competencias


def populacao():
    url = ("https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-1/variaveis/9324"
           "?localidades=N6[1505304]")
    dados = json.loads(baixar(url))
    serie = dados[0]["resultados"][0]["series"][0]["serie"]
    ano, valor = sorted(serie.items())[-1]
    return int(ano), int(valor)


def main():
    por_tipo, competencias = equipes()
    resultado = pd.DataFrame(index=competencias)
    usados = set()
    for nome, codigos in TIPOS.items():
        if codigos is None:
            codigos = [c for c in por_tipo.index if c not in usados]
        usados.update(codigos)
        resultado[nome] = por_tipo.reindex(codigos).fillna(0).sum().astype(int)
    resultado = resultado.loc[:, resultado.sum() > 0]
    ribeirinhas = int(por_tipo.reindex(RIBEIRINHAS).fillna(0).iloc[:, -1].sum())
    ano_final, mes_final = competencias[-1].split("/")
    rotulos = [c.split("/")[0] for c in competencias]
    if mes_final != "Dez":
        rotulos[-1] = f"até {MESES[MESES_TABNET.index(mes_final)]}/{int(ano_final) % 100:02d}"
    tabela = resultado.copy()
    tabela.index = rotulos
    tabela.rename_axis("Ano").reset_index().to_csv(os.path.join(PASTA_COMPONENTES, "comp_342.csv"), sep=";",
                                                   index=False, encoding="utf-8")
    print(tabela.to_string())

    agora = resultado.iloc[-1]
    esf = int(agora[SAUDE_FAMILIA])
    esf_inicio = int(resultado[SAUDE_FAMILIA].iloc[0])
    ano_pop, pessoas = populacao()
    por_equipe = pessoas / esf if esf else 0
    acima = por_equipe > PESSOAS_POR_EQUIPE[1]

    def fmt(n):
        return f"{int(round(n)):,}".replace(",", ".")
    componente = {
        "id": 342, "titulo": "Equipes de Saúde da Família", "fonte": "Ministério da Saúde | CNES (DATASUS)",
        "atualizacao": "Mensal", "icone": "family_restroom", "area": "Município de Oriximiná",
        "resumo": "Quantas equipes de Saúde da Família, de dentistas, de agentes comunitários e indígenas Oriximiná tem.",
        "descricao": (
            "Mostra quantas equipes de saúde da atenção básica Oriximiná tinha cadastradas no CNES, o cadastro "
            f"do Ministério da Saúde, em dezembro de cada ano desde {PRIMEIRO_ANO} e no mês mais recente: as "
            "equipes de Saúde da Família (médico, enfermeiro, técnico e agentes comunitários, nas UBS), as de "
            "saúde bucal (dentista), as de agentes comunitários e as de saúde indígena. Em "
            f"{MESES[MESES_TABNET.index(mes_final)]}/{ano_final}, eram {esf} equipes de Saúde da Família "
            f"({'era' if esf_inicio == 1 else 'eram'} {esf_inicio} em {PRIMEIRO_ANO}), {fmt(por_equipe)} "
            "moradores para cada uma (população "
            f"estimada pelo IBGE em {ano_pop}: {fmt(pessoas)}). O Ministério recomenda de "
            f"{fmt(PESSOAS_POR_EQUIPE[0])} a {fmt(PESSOAS_POR_EQUIPE[1])} pessoas por equipe"
            + (", então Oriximiná está um pouco acima do recomendado. " if acima else ". ")
            + ("Nenhuma equipe está cadastrada como ribeirinha ou fluvial (de barco), os tipos criados para as "
               "comunidades dos rios. " if ribeirinhas == 0 else
               f"{ribeirinhas} delas são ribeirinhas ou fluviais (de barco), para as comunidades dos rios. ")
            + "Em 2020 o Ministério mudou os tipos de equipe: até 2019, as equipes de dentista entravam junto "
            "com as de Saúde da Família, e depois as equipes só de agentes comunitários deixam de aparecer. Em Taipei, este cartão mostra as clínicas de medicina de família."),
        "exemplo": ("Mostra se a atenção básica está crescendo junto com a população e ajuda a planejar novas "
                    "equipes, inclusive ribeirinhas e fluviais, para as comunidades dos rios."),
        "tipos": ["linha_tempo_empilhada", "colunas"],
        "cores": ["#56B96D", "#24B0DD", "#F8CF58", "#c18ad8", "#bdbdbd"],
        "unidade": "equipes", "meta": None, "maximo": None,
        "links": [{"nome": "DATASUS – TabNet: equipes de saúde do Pará (CNES)",
                   "url": "http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/equipepa.def"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_342"] = componente
    saude = config.get("paineis_publicos", {}).get("saude")
    if saude and "comp_342" not in saude["cartoes"]:
        saude["cartoes"].append("comp_342")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Saúde:", saude["cartoes"] if saude else "—")


if __name__ == "__main__":
    main()
