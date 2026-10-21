"""Prepara o cartão "Cobertura vacinal das crianças" (no lugar das "Estatísticas sobre o número de hospitais
recebendo vacinas contra a gripe" do Taipei), no painel "Saúde".

Fonte: SI-PNI (Sistema de Informação do Programa Nacional de Imunizações), pelo TabNet do DATASUS
(http://tabnet.datasus.gov.br/cgi/dhdat.exe?bd_pni/cpnibr.def): a parte das crianças da idade certa que
tomaram cada vacina do calendário, a cada ano. O TabNet vai até 2022; de 2023 em diante o Ministério da Saúde
publica a cobertura só num painel de consulta (infoms.saude.gov.br), com outra forma de cálculo, sem arquivo
para baixar.

- comp_335.csv: cobertura (%) de cada vacina, por ano

Rode de novo para atualizar:  python preparar_vacinacao.py
"""
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
DEF = "bd_pni/cpnibr.def"
MUNICIPIO = "150530 ORIXIMINA|150530|6"
ANOS = range(2013, 2023)
META = 95   # meta do Programa Nacional de Imunizações (90% para BCG e rotavírus)
# Vacina no TabNet -> nome no cartão (contra o quê)
VACINAS = {
    "BCG": "BCG (tuberculose)",
    "Poliomielite": "Pólio",
    "Penta": "Penta (difteria e outras)",
    "Pneumocócica": "Pneumocócica",
    "Rotavírus Humano": "Rotavírus (diarreia)",
    "Meningococo C": "Meningite C",
    "Tríplice Viral  D1": "Tríplice viral (sarampo)",
    "Febre Amarela": "Febre amarela",
}


def opcoes(formulario, nome):
    bloco = formulario[formulario.find(f'NAME="{nome}"'):]
    bloco = bloco[:bloco.find("</select>")]
    return [html.unescape(v) for v in re.findall(r'<option value="([^"]*)"', bloco)]


def baixar(url, dados=None):
    pedido = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0",
                                                              "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=180) as resposta:
        return resposta.read().decode("latin-1")


def cobertura():
    # O formulário traz as opções com o código SQL que o TabNet espera: usa os valores dele como estão
    formulario = baixar(f"http://tabnet.datasus.gov.br/cgi/dhdat.exe?{DEF}")
    incrementos = [v for v in opcoes(formulario, "Incremento") if v.split("|")[0] in VACINAS]
    linha = next(v for v in opcoes(formulario, "Linha") if v.startswith("Ano|"))
    anos = [v for v in opcoes(formulario, "PAno") if int(v.split("|")[0]) in ANOS]
    campos = ([("Linha", linha), ("Coluna", "--Não-Ativa--")] + [("Incremento", v) for v in incrementos]
              + [("PAno", v) for v in anos] + [("SMunicípio", MUNICIPIO), ("nomedef", DEF), ("grafico", "")])
    corpo = urllib.parse.urlencode(campos, encoding="latin-1").encode("ascii")
    pagina = baixar(f"http://tabnet.datasus.gov.br/cgi/webtabx.exe?{DEF}", corpo)
    if "ORIXIMINA" not in pagina:
        raise RuntimeError("O TabNet não devolveu a tabela de Oriximiná")
    # A tabela vem dentro do gráfico da página: addColumn('number','BCG') ... ["2019" ,{v: 113.39 ,f: '113,40'} ...]
    colunas = re.findall(r"addColumn\('number','([^']*)'\)", pagina)
    linhas = re.findall(r'\["(\d{4})" ,(.*?)\]', pagina)
    tabela = pd.DataFrame([[float(v) for v in re.findall(r"v: ([\d.]+)", valores)] for _, valores in linhas],
                          index=[int(a) for a, _ in linhas], columns=colunas)
    return tabela.rename(columns=VACINAS)[list(VACINAS.values())].sort_index()


def main():
    tabela = cobertura().round(1)
    tabela.rename_axis("Ano").reset_index().to_csv(os.path.join(PASTA_COMPONENTES, "comp_335.csv"), sep=";",
                                                   index=False, encoding="utf-8")
    print(tabela.to_string())

    primeiro, ultimo = tabela.index.min(), tabela.index.max()
    sem_bcg = tabela.drop(columns=VACINAS["BCG"])
    na_meta = int((sem_bcg.loc[ultimo] >= META).sum())
    quantas, chegou = ("nenhuma", "chegou") if na_meta == 0 else (str(na_meta), "chegaram")
    penta = VACINAS["Penta"]
    sarampo = VACINAS["Tríplice Viral  D1"]

    def pct(x):
        return f"{x:.0f}%"
    componente = {
        "id": 335, "titulo": "Cobertura vacinal das crianças", "fonte": "Ministério da Saúde | SI-PNI (DATASUS)",
        "atualizacao": f"{ultimo}", "icone": "vaccines", "area": "Município de Oriximiná",
        "resumo": "Quantas crianças de Oriximiná tomaram as vacinas do calendário, ano a ano, e a meta de 95%.",
        "descricao": (
            f"Mostra, de {primeiro} a {ultimo}, a cobertura vacinal das crianças de Oriximiná: a parte das "
            "crianças da idade certa (até 1 ano, ou 1 ano na tríplice viral) que tomaram cada vacina do "
            "calendário, segundo o Programa Nacional de Imunizações. A meta é vacinar 95% das crianças (90% "
            f"na BCG e na rotavírus). A cobertura caiu muito: a penta foi de {pct(tabela.loc[primeiro, penta])} "
            f"em {primeiro} para {pct(tabela.loc[ultimo, penta])} em {ultimo}, e a tríplice viral, contra o "
            f"sarampo, de {pct(tabela.loc[primeiro, sarampo])} para {pct(tabela.loc[ultimo, sarampo])}. Em "
            f"{ultimo}, {quantas} das {len(sem_bcg.columns)} vacinas (fora a BCG) {chegou} à meta. A BCG, dada "
            "na maternidade, pode passar de 100% porque conta também os bebês de outros municípios que nascem "
            "no hospital de Oriximiná. A cobertura é calculada com as doses aplicadas e uma estimativa do "
            "número de crianças, por isso pode ter erros, sobretudo em municípios pequenos. Os dados vão até "
            f"{ultimo}: depois disso, o Ministério da Saúde mudou o sistema e publica a cobertura só no painel "
            "de vacinação, sem arquivo para baixar. Em Taipei, este cartão mostra os hospitais que aplicam a "
            "vacina da gripe; em Oriximiná, as vacinas são dadas nas unidades básicas de saúde (veja a camada "
            "de estabelecimentos de saúde na Comparação de mapas)."),
        "exemplo": ("Mostra o tamanho da queda da vacinação e ajuda a planejar busca ativa das crianças "
                    "atrasadas, vacinação nas escolas e nas comunidades ribeirinhas."),
        "tipos": ["linha_tempo_separada", "mapa_calor"],
        "cores": ["#a1887f", "#24B0DD", "#F65658", "#56B96D", "#F8CF58", "#c18ad8", "#F49F36", "#7d9be0"],
        "unidade": "%", "meta": None, "maximo": None,
        "links": [{"nome": "DATASUS – TabNet: cobertura vacinal (SI-PNI)",
                   "url": "http://tabnet.datasus.gov.br/cgi/dhdat.exe?bd_pni/cpnibr.def"},
                  {"nome": "Ministério da Saúde – painel de cobertura vacinal (2023 em diante)",
                   "url": "https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_MENU_COBERTURA/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_MENU_COBERTURA.html"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_335"] = componente
    saude = config.get("paineis_publicos", {}).get("saude")
    if saude and "comp_335" not in saude["cartoes"]:
        saude["cartoes"].append("comp_335")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Saúde:", saude["cartoes"] if saude else "—")


if __name__ == "__main__":
    main()
