"""Prepara o cartão "Fábricas de alimentos e bebidas" (como a "Distribuição dos distritos administrativos para
fábricas de alimentos" do Taipei), no painel "Segurança e saúde alimentar".

Fonte: RAIS (Relação Anual de Informações Sociais, Ministério do Trabalho), arquivo de estabelecimentos
(RAIS_ESTAB_PUB), um por ano: ftp://ftp.mtps.gov.br/pdet/microdados/RAIS/ANO/RAIS_ESTAB_PUB.7z. Salve cada um
em PASTA_FONTES/RAIS_ESTAB como ESTABANO.7z (fora da pasta RAIS, que o preparar_rais.py lê inteira). A RAIS só
conta empresas que declararam ao Ministério do Trabalho; as fábricas familiares (como a maioria das casas de
farinha) e quem trabalha sem carteira assinada não entram.

Cada arquivo tem o Brasil inteiro (1,4 GB descompactado): as linhas de Oriximiná ficam guardadas em
RAIS_ESTAB/oriximina_ANO.csv e o .7z só é lido de novo se mudar.

- comp_338.csv: estabelecimentos de fabricação de alimentos e bebidas declarados na RAIS, por ano e tipo
- comp_338_historico.csv: empregados com carteira nesses estabelecimentos, por ano

Rode de novo quando sair uma RAIS nova:  python preparar_industria_alimentos.py
"""
import csv
import glob
import io
import json
import os
import re
import tempfile

import pandas as pd
import py7zr

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_ESTAB = os.path.join(PASTA_FONTES, "RAIS_ESTAB")
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
CODIGO_RAIS = "150530"   # a RAIS usa o código do IBGE sem o último dígito
COLUNAS = {"Município": "municipio", "CNAE 2.0 Subclasse": "subclasse", "Qtd Vínculos Ativos": "empregados",
           "Ind Atividade Ano": "ativo"}

# Tipo no cartão -> começo da subclasse CNAE 2.0 (divisão 10 = alimentos, 11 = bebidas)
TIPOS = {
    "Polpas de frutas e açaí": ["1031", "1033"],   # conservas de frutas e sucos
    "Padarias e confeitarias": ["1091"],
    "Gelo": ["1099604"],
    "Água mineral e bebidas": ["11"],
    "Farinha de mandioca": ["1063"],
    "Pescado e carnes": ["101", "102"],
    "Outros alimentos": ["10"],   # (o que sobrar da divisão 10; fica por último)
}


def tipo(subclasse):
    for nome, comecos in TIPOS.items():
        if subclasse.startswith(tuple(comecos)):
            return nome
    return None


def linhas_de_oriximina(arquivo_7z, ano):
    """Estabelecimentos de Oriximiná de um ano da RAIS (lidos do .7z uma vez e guardados num CSV pequeno)."""
    guardado = os.path.join(PASTA_ESTAB, f"oriximina_{ano}.csv")
    if os.path.exists(guardado) and os.path.getmtime(guardado) >= os.path.getmtime(arquivo_7z):
        return pd.read_csv(guardado, sep=";", dtype=str)
    with tempfile.TemporaryDirectory() as pasta, py7zr.SevenZipFile(arquivo_7z, "r") as pacote:
        pacote.extractall(pasta)
        nome = os.path.join(pasta, os.listdir(pasta)[0])
        with open(nome, encoding="latin-1") as arquivo:
            cabecalho = arquivo.readline()
            separador = ";" if cabecalho.count(";") > cabecalho.count(",") else ","   # mudou em 2025
            colunas = next(csv.reader([cabecalho], delimiter=separador))
            # Alguns anos repetem o nome de uma coluna: a repetida ganha um número no fim
            colunas = [c if c not in colunas[:i] else f"{c}_{i}" for i, c in enumerate(colunas)]
            # Só as linhas com o código de Oriximiná passam pelo leitor de CSV (o resto é descartado rápido)
            nossas = [l for l in arquivo if CODIGO_RAIS in l]
    tabela = pd.read_csv(io.StringIO("".join(nossas)), sep=separador, names=colunas, dtype=str)
    renomear = {c: novo for c in tabela.columns for velho, novo in COLUNAS.items() if c.startswith(velho)}
    tabela = tabela.rename(columns=renomear)[list(COLUNAS.values())]
    tabela = tabela[tabela["municipio"].str.strip() == CODIGO_RAIS]
    tabela.to_csv(guardado, sep=";", index=False)
    return tabela


def main():
    linhas = []
    for arquivo in sorted(glob.glob(os.path.join(PASTA_ESTAB, "ESTAB*.7z"))):
        ano = int(re.search(r"(\d{4})", os.path.basename(arquivo)).group(1))
        tabela = linhas_de_oriximina(arquivo, ano)
        tabela["subclasse"] = tabela["subclasse"].str.strip().str.zfill(7)
        tabela["empregados"] = pd.to_numeric(tabela["empregados"], errors="coerce").fillna(0).astype(int)
        tabela["tipo"] = tabela["subclasse"].map(tipo)
        # Todas as fábricas declaradas na RAIS, mesmo as que estavam sem empregados em 31 de dezembro
        alimentos = tabela[tabela["tipo"].notna()]
        print(ano, len(tabela), "estabelecimentos em Oriximiná;", len(alimentos), "de alimentos e bebidas")
        for _, linha in alimentos.iterrows():
            linhas.append({"ano": ano, "tipo": linha["tipo"], "empregados": linha["empregados"]})
    dados = pd.DataFrame(linhas)
    estabelecimentos = (dados.pivot_table(index="ano", columns="tipo", values="empregados", aggfunc="size",
                                          fill_value=0).reindex(columns=list(TIPOS), fill_value=0))
    estabelecimentos = estabelecimentos.loc[:, estabelecimentos.sum() > 0]
    estabelecimentos.rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_338.csv"), sep=";", index=False, encoding="utf-8")
    empregados = dados.groupby("ano")["empregados"].sum().rename("Empregados com carteira")
    empregados.rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_338_historico.csv"), sep=";", index=False, encoding="utf-8")
    print(estabelecimentos.to_string())
    print(empregados.to_string())

    ultimo = int(estabelecimentos.index.max())
    primeiro = int(estabelecimentos.index.min())
    total = estabelecimentos.sum(axis=1)
    contagem = estabelecimentos.loc[ultimo]
    mais_comuns = [t.lower() for t in contagem[contagem == contagem.max()].index]   # pode haver empate
    componente = {
        "id": 338, "titulo": "Fábricas de alimentos e bebidas", "fonte": "Ministério do Trabalho | RAIS",
        "atualizacao": f"RAIS {ultimo}", "icone": "bakery_dining", "area": "Município de Oriximiná",
        "resumo": "Quantas fábricas de alimentos e bebidas (polpas de frutas, padarias, gelo, água) há em Oriximiná.",
        "descricao": (
            f"Mostra quantas empresas de fabricação de alimentos e bebidas de Oriximiná declararam a RAIS, do "
            f"Ministério do Trabalho, a cada ano, de {primeiro} a {ultimo}, por tipo: polpas de frutas (como o açaí), "
            "padarias e confeitarias, gelo, água mineral e bebidas e outros. Em "
            f"{ultimo}, eram {int(total[ultimo])} (as mais comuns: {' e '.join(mais_comuns)}), com "
            f"{int(empregados[ultimo])} empregados de carteira assinada (o histórico mostra os empregados de "
            "cada ano). Algumas estavam sem empregados no fim do ano. A RAIS só conta "
            "as empresas que declaram ao Ministério do Trabalho: as fábricas familiares, como a maioria das "
            "casas de farinha, e quem trabalha sem carteira assinada não entram, então a produção de alimentos "
            "de Oriximiná é bem maior do que o cartão mostra. Os supermercados, restaurantes e o comércio de "
            "alimentos também não entram (só quem fabrica)."),
        "exemplo": ("Mostra quem fabrica alimentos em Oriximiná e ajuda a planejar o apoio às agroindústrias, "
                    "a fiscalização sanitária e a compra local para a merenda."),
        "tipos": ["colunas", "linha_tempo_empilhada"],
        "cores": ["#c18ad8", "#F8CF58", "#7d9be0", "#24B0DD", "#a1887f", "#F65658", "#bdbdbd"],
        "unidade": "estabelecimentos", "meta": None, "maximo": None,
        "links": [{"nome": "Ministério do Trabalho – microdados da RAIS (PDET)",
                   "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged"}],
        "colaboradores": [], "mapa": None, "historico": {"tipo": "arquivo"},
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_338"] = componente
    painel = config.get("paineis_publicos", {}).get("alimentar")
    if painel and "comp_338" not in painel["cartoes"]:
        painel["cartoes"].append("comp_338")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Segurança e saúde alimentar:", painel["cartoes"] if painel else "—")


if __name__ == "__main__":
    main()
