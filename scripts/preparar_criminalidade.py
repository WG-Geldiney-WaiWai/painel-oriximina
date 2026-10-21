"""Prepara o cartão "Ocorrências criminais" (como o "Estatísticas criminais" do Taipei), no painel
"Servindo ao povo".

Fonte: Sinesp VDE, do Ministério da Justiça e Segurança Pública. São os dados que as polícias de cada estado
mandam todo mês ao Ministério, um arquivo por ano (2015 em diante). Por município, o Sinesp traz só os
crimes contra a vida (homicídio, feminicídio, latrocínio, tentativas...) e os mandados de prisão cumpridos;
roubos e furtos só vêm somados para o estado inteiro. Os casos esclarecidos (a outra linha do cartão do
Taipei) não são publicados.

- comp_326.csv: por ano, as vítimas de homicídio e de outras mortes violentas, as de tentativa de homicídio
  e os mandados de prisão cumpridos em Oriximiná

Os arquivos ficam em PASTA_FONTES/SINESP (bancovde-ANO.xlsx). A cada vez que roda, o script baixa de novo o
arquivo do ano atual (que o Ministério atualiza todo mês) e os anos que ainda faltam.

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_criminalidade.py
"""
import json
import os
import unicodedata
import urllib.request
from concurrent.futures import ProcessPoolExecutor

import openpyxl
import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_SINESP = os.path.join(PASTA_FONTES, "SINESP")
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
URL_ANO = ("https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/download/"
           "dnsp-base-de-dados/bancovde-{ano}.xlsx/@@download/file")
PRIMEIRO_ANO = 2015
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

MORTES = "Homicídios e outras mortes violentas"
TENTATIVAS = "Tentativas de homicídio"
MANDADOS = "Mandados de prisão cumpridos"
EVENTOS = {   # evento do Sinesp (sem acento, minúsculo) -> linha do cartão
    "homicidio doloso": MORTES, "feminicidio": MORTES, "roubo seguido de morte (latrocinio)": MORTES,
    "lesao corporal seguida de morte": MORTES,
    "tentativa de homicidio": TENTATIVAS, "tentativa de feminicidio": TENTATIVAS,
    "mandado de prisao cumprido": MANDADOS,
}


def sem_acento(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower().strip()


def baixar_ano(ano, sempre=False):
    caminho = os.path.join(PASTA_SINESP, f"bancovde-{ano}.xlsx")
    if sempre or not os.path.exists(caminho):
        os.makedirs(PASTA_SINESP, exist_ok=True)
        try:
            with urllib.request.urlopen(URL_ANO.format(ano=ano), timeout=300) as resposta:
                conteudo = resposta.read()
        except OSError as erro:
            print(f"{ano}: não baixou ({erro})")
            return caminho if os.path.exists(caminho) else None
        if not conteudo.startswith(b"PK"):   # não veio uma planilha (ano ainda não publicado)
            print(f"{ano}: ainda não publicado")
            return caminho if os.path.exists(caminho) else None
        with open(caminho + ".novo", "wb") as arquivo:
            arquivo.write(conteudo)
        os.replace(caminho + ".novo", caminho)
    return caminho


def linhas_de_oriximina(caminho):
    """Só as linhas de Oriximiná (PA) da planilha do Brasil inteiro."""
    livro = openpyxl.load_workbook(caminho, read_only=True)
    linhas = livro.worksheets[0].iter_rows(values_only=True)
    cabecalho = [sem_acento(c) for c in next(linhas)]
    uf, municipio = cabecalho.index("uf"), cabecalho.index("municipio")
    dados = [linha for linha in linhas
             if linha[uf] == "PA" and sem_acento(linha[municipio] or "").startswith("oriximina")]
    livro.close()
    return pd.DataFrame(dados, columns=cabecalho)


def main():
    hoje = pd.Timestamp.now()
    caminhos = [baixar_ano(ano, sempre=ano >= hoje.year - 1) for ano in range(PRIMEIRO_ANO, hoje.year + 1)]
    caminhos = [c for c in caminhos if c]
    with ProcessPoolExecutor(max_workers=4) as grupo:
        tabelas = list(grupo.map(linhas_de_oriximina, caminhos))
    dados = pd.concat(tabelas, ignore_index=True)
    dados["linha"] = dados["evento"].map(lambda e: EVENTOS.get(sem_acento(e)))
    dados = dados.dropna(subset=["linha"])
    # Vítimas nos crimes contra a vida; quantidade nos mandados de prisão
    valor = pd.to_numeric(dados["total_vitima"], errors="coerce")
    dados["valor"] = valor.fillna(pd.to_numeric(dados["total"], errors="coerce")).fillna(0)
    dados["data"] = pd.to_datetime(dados["data_referencia"])
    ultimo_mes = dados["data"].max()

    tabela = dados.pivot_table(index=dados["data"].dt.year, columns="linha", values="valor",
                               aggfunc="sum", fill_value=0)
    tabela = tabela.reindex(columns=[MORTES, TENTATIVAS, MANDADOS], fill_value=0).astype(int)
    rotulos = [str(ano) for ano in tabela.index]
    if ultimo_mes.month < 12:   # ano atual ainda pela metade
        rotulos[-1] = f"{ultimo_mes.year} (até {MESES[ultimo_mes.month - 1]})"
    tabela.index = rotulos
    tabela = tabela.rename_axis("Ano").reset_index()
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_326.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))
    print("Último mês com dados:", ultimo_mes.strftime("%m/%Y"))

    componente = {
        "id": 326, "titulo": "Ocorrências criminais", "fonte": "Ministério da Justiça | Sinesp",
        "atualizacao": "Mensal", "icone": "local_police", "area": "Município de Oriximiná",
        "resumo": "Vítimas de homicídio e de tentativa de homicídio e mandados de prisão cumpridos, por ano.",
        "descricao": (
            "Mostra, ano a ano desde 2015, os crimes contra a vida em Oriximiná registrados pela Polícia Civil "
            "do Pará no Sinesp, o sistema de estatísticas de segurança pública do Ministério da Justiça: as "
            "vítimas de homicídio e de outras mortes violentas (homicídio doloso, feminicídio, latrocínio e "
            "lesão corporal seguida de morte) e as vítimas de tentativa de homicídio ou de feminicídio. A "
            "terceira linha são os mandados de prisão cumpridos no município. O ano atual vai até o último mês "
            "já publicado. Por município, o Sinesp não traz roubos e furtos (só o total do estado), nem quantos "
            "casos foram esclarecidos, que é a outra linha do cartão de Taipei; os mandados de prisão cumpridos "
            "são o dado mais próximo do trabalho da polícia."),
        "exemplo": ("Acompanha a violência em Oriximiná ao longo dos anos e ajuda a planejar a segurança junto "
                    "com o Estado: iluminação, guarda municipal e ações de prevenção."),
        "tipos": ["linha_tempo_separada", "colunas"],
        "cores": ["#F65658", "#F8CF58", "#24B0DD"],
        "unidade": "", "meta": None, "maximo": None,
        "links": [{"nome": "Ministério da Justiça – Sinesp VDE (base de dados)",
                   "url": "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/"
                          "dados-nacionais-1/base-de-dados-e-notas-metodologicas-dos-gestores-estaduais-sinesp-vde-2022-e-2023"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    componentes = config.setdefault("componentes_novos", {})
    painel = config.get("paineis_publicos", {}).get("servindo")
    # Só grava o admin_painel.json quando algo muda (a atualização mensal só troca o CSV)
    if componentes.get("comp_326") != componente or (painel and "comp_326" not in painel["cartoes"]):
        componentes["comp_326"] = componente
        if painel and "comp_326" not in painel["cartoes"]:
            painel["cartoes"].append("comp_326")
        with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
            json.dump(config, arquivo, ensure_ascii=False, indent=2)
        print("admin_painel.json atualizado; painel Servindo ao povo:",
              painel["cartoes"] if painel else "não encontrado (rode preparar_lixo.py)")


if __name__ == "__main__":
    main()
