"""Prepara o cartão "Comércio de alimentos" (como a "Distribuição dos mercados de suprimentos alimentares" do
Taipei), no painel "Segurança e saúde alimentar".

Fonte: RAIS (Ministério do Trabalho), arquivo de estabelecimentos já guardado pelo preparar_industria_alimentos.py
em PASTA_FONTES/RAIS_ESTAB/oriximina_ANO.csv: as lojas de alimentos declaradas a cada ano, pelo CNAE
(4711 supermercados, 4712 mercadinhos e mercearias, 4721 padarias e laticínios, 4722 açougues e peixarias,
4723 bebidas, 4724 hortifrúti, 4729 outros alimentos). A RAIS não traz o endereço, então não há mapa; e quem
não tem empregado registrado nem declara (como as bancas das feiras) não entra.

- comp_346.csv: lojas de alimentos por tipo, a cada ano

Rode de novo quando sair uma RAIS nova (ou clique em "Atualizar" na administração):  python preparar_comercio_alimentos.py
"""
import glob
import json
import os
import re

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_RAIS = os.path.join(PASTA_FONTES, "RAIS_ESTAB")
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
MERCADINHOS = "Mercadinhos e mercearias"
TIPOS = {   # tipo no cartão -> começo da subclasse CNAE 2.0
    MERCADINHOS: ["4712"],
    "Supermercados": ["4711"],
    "Padarias e laticínios": ["4721"],
    "Bebidas": ["4723"],
    "Açougues e peixarias": ["4722"],
    "Hortifrúti": ["4724"],
    "Outros alimentos": ["4729"],
}


def tipo(subclasse):
    for nome, comecos in TIPOS.items():
        if subclasse.startswith(tuple(comecos)):
            return nome
    return None


def main():
    linhas = []
    for arquivo in sorted(glob.glob(os.path.join(PASTA_RAIS, "oriximina_*.csv"))):
        ano = int(re.search(r"(\d{4})", os.path.basename(arquivo)).group(1))
        tabela = pd.read_csv(arquivo, sep=";", dtype=str)
        tabela["tipo"] = tabela["subclasse"].str.strip().str.zfill(7).map(tipo)
        tabela["empregados"] = pd.to_numeric(tabela["empregados"], errors="coerce").fillna(0)
        lojas = tabela[tabela["tipo"].notna()]
        contagem = lojas["tipo"].value_counts()
        linhas.append({"Ano": ano, **{t: int(contagem.get(t, 0)) for t in TIPOS},
                       "empregados": int(lojas["empregados"].sum())})
    por_ano = pd.DataFrame(linhas).set_index("Ano")
    tabela = por_ano[list(TIPOS)]
    tabela = tabela.loc[:, tabela.sum() > 0]
    tabela.rename_axis("Ano").reset_index().to_csv(os.path.join(PASTA_COMPONENTES, "comp_346.csv"), sep=";",
                                                   index=False, encoding="utf-8")
    print(por_ano.to_string())

    ultimo, primeiro = int(tabela.index.max()), int(tabela.index.min())
    total = tabela.sum(axis=1)
    componente = {
        "id": 346, "titulo": "Comércio de alimentos", "fonte": "Ministério do Trabalho | RAIS",
        "atualizacao": f"RAIS {ultimo}", "icone": "storefront", "area": "Município de Oriximiná",
        "resumo": "Quantos mercadinhos, supermercados, padarias, açougues e outras lojas de alimentos Oriximiná tem.",
        "descricao": (
            f"Mostra quantas lojas de alimentos de Oriximiná declararam a RAIS, do Ministério do Trabalho, a cada "
            f"ano de {primeiro} a {ultimo}, por tipo. Em {ultimo}, eram {int(total[ultimo])} (eram "
            f"{int(total[primeiro])} em {primeiro}), com {int(por_ano.loc[ultimo, 'empregados'])} empregados "
            f"de carteira assinada. A maioria são mercadinhos e mercearias ({int(tabela.loc[ultimo, MERCADINHOS])}); "
            f"supermercados são {int(tabela.loc[ultimo, 'Supermercados'])}. A RAIS não traz o endereço, então "
            "não dá para pôr as lojas no mapa. As bancas das feiras, como a Feira do Produtor, e as lojas sem "
            "empregado registrado que não declaram a RAIS não entram. Em Taipei, este cartão mostra os mercados, "
            "supermercados e feiras no mapa."),
        "exemplo": ("Mostra onde as famílias compram comida e ajuda a planejar feiras e a fiscalização "
                    "sanitária, e a ver se o comércio acompanha o crescimento da cidade."),
        "tipos": ["linha_tempo_empilhada", "colunas"],
        "cores": ["#F49F36", "#24B0DD", "#F8CF58", "#7d9be0", "#F65658", "#56B96D", "#bdbdbd"],
        "unidade": "lojas", "meta": None, "maximo": None,
        "links": [{"nome": "Ministério do Trabalho – microdados da RAIS (PDET)",
                   "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_346"] = componente
    painel = config.get("paineis_publicos", {}).get("alimentar")
    if painel and "comp_346" not in painel["cartoes"]:
        painel["cartoes"].append("comp_346")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Segurança e saúde alimentar:", painel["cartoes"] if painel else "—")


if __name__ == "__main__":
    main()
