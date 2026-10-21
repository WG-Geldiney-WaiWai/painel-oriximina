"""Prepara o cartão "Crédito do Pronaf" (no lugar do "Empréstimos para empreendedorismo juvenil" do Taipei),
no painel "Servindo ao povo".

Fonte: Matriz de Dados do Crédito Rural (Sicor) do Banco Central, pela API Olinda. Ela traz o valor dos
créditos rurais de cada município, por mês, programa e subprograma. O Pronaf (agricultura familiar) é o
programa 0001. O Pronaf Jovem (subprograma 6, MCR 10-10), que seria o cartão do Taipei, não teve nenhum
contrato em Oriximiná desde 2013; o cartão mostra as linhas do Pronaf que o município usa.

- comp_327.csv: valor do Pronaf em Oriximiná por ano e linha (em mil reais)

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_pronaf.py
"""
import json
import os
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
API = "https://olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata"
# A API dá erro com páginas grandes ou com $skip; Oriximiná tem poucas centenas de linhas em cada tabela
CONSULTAS = {
    "custeio": f"{API}/CusteioMunicipioProduto?$top=1000&$format=json&$filter=codIbge%20eq%20'1505304'",
    "investimento": f"{API}/InvestMunicipioProduto?$top=1000&$format=json&$filter=cdMunicipio%20eq%20'17828'",
}
PRONAF = "0001"
SUB_JOVEM = 6
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CUSTEIO = "Custeio (plantar e criar)"
MAIS_ALIMENTOS = "Mais Alimentos (máquinas e equipamentos)"
MICROCREDITO = "Microcrédito rural (Grupo B)"
REFORMA = "Reforma agrária"
OUTROS = "Outros investimentos"
LINHAS_INVESTIMENTO = {2: MAIS_ALIMENTOS, 56: MICROCREDITO, 54: REFORMA}   # subprograma -> linha


def baixar(url):
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(url, timeout=240) as resposta:
                texto = resposta.read().decode("utf-8")
            if texto.startswith("{"):
                return pd.DataFrame(json.loads(texto)["value"])
        except OSError:
            pass
    raise RuntimeError(f"A API do Banco Central não respondeu: {url}")


def main():
    custeio = baixar(CONSULTAS["custeio"])
    investimento = baixar(CONSULTAS["investimento"])
    if len(custeio) >= 1000 or len(investimento) >= 1000:
        raise RuntimeError("Mais de 1000 linhas: a consulta precisa ser dividida (a API não aceita $skip)")
    custeio["valor"], investimento["valor"] = custeio["VlCusteio"], investimento["VlInvest"]
    todos = pd.concat([custeio.assign(tipo="custeio"), investimento.assign(tipo="investimento")])
    todos["ano"] = todos["AnoEmissao"].astype(int)
    todos["mes"] = todos["AnoEmissao"].astype(int) * 100 + todos["MesEmissao"].astype(int)
    pronaf = todos[todos["cdPrograma"] == PRONAF].copy()
    pronaf["sub"] = pronaf["cdSubPrograma"].astype(int)
    jovem = pronaf[pronaf["sub"] == SUB_JOVEM]
    print(f"Pronaf Jovem em Oriximiná: {len(jovem)} registros, R$ {jovem['valor'].sum():,.2f}")

    pronaf["linha"] = [CUSTEIO if t == "custeio" else LINHAS_INVESTIMENTO.get(s, OUTROS)
                       for t, s in zip(pronaf["tipo"], pronaf["sub"])]
    anos = range(todos["ano"].min(), todos["ano"].max() + 1)
    tabela = (pronaf.pivot_table(index="ano", columns="linha", values="valor", aggfunc="sum", fill_value=0)
              .reindex(index=anos, columns=[CUSTEIO, MAIS_ALIMENTOS, MICROCREDITO, REFORMA, OUTROS], fill_value=0)
              / 1000).round(1)
    ultimo = todos["mes"].max()
    rotulos = [str(a) for a in tabela.index]
    if ultimo % 100 < 12:   # ano atual ainda pela metade
        rotulos[-1] = f"{ultimo // 100} (até {MESES[ultimo % 100 - 1]})"
    tabela.index = rotulos
    tabela = tabela.rename_axis("Ano").reset_index()
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_327.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    componente = {
        "id": 327, "titulo": "Crédito do Pronaf", "fonte": "Banco Central | Matriz de Dados do Crédito Rural",
        "atualizacao": "Mensal", "icone": "agriculture", "area": "Município de Oriximiná",
        "resumo": "Quanto os agricultores familiares de Oriximiná pegaram de crédito do Pronaf por ano, em cada linha.",
        "descricao": (
            "Mostra, ano a ano, o valor dos empréstimos do Pronaf (Programa Nacional de Fortalecimento da "
            "Agricultura Familiar) feitos em Oriximiná, em mil reais, segundo a Matriz de Dados do Crédito Rural "
            "do Banco Central: o custeio, para plantar e criar, e os investimentos do Mais Alimentos (máquinas e "
            "equipamentos), do microcrédito rural do Grupo B (as famílias de menor renda), da reforma agrária "
            "(assentados) e outros. O ano atual vai até o último mês já publicado. Em Taipei, este cartão mostra "
            "os empréstimos da cidade para jovens empreendedores; aqui, a linha parecida é o Pronaf Jovem, para "
            "agricultores de 16 a 29 anos, mas ela não teve nenhum contrato em Oriximiná desde 2013, o começo "
            "dos dados."),
        "exemplo": ("Mostra quanto crédito chega à agricultura familiar e quais linhas ninguém usa, como o "
                    "Pronaf Jovem, para a Prefeitura, a Emater e o sindicato rural divulgarem e ajudarem os "
                    "agricultores a fazer os projetos."),
        "tipos": ["linha_tempo_empilhada", "colunas"],
        "cores": ["#56B96D", "#24B0DD", "#F8CF58", "#c18ad8", "#bdbdbd"],
        "unidade": "mil reais", "meta": None, "maximo": None,
        "links": [{"nome": "Banco Central – Matriz de Dados do Crédito Rural",
                   "url": "https://www.bcb.gov.br/estabilidadefinanceira/micrrural"},
                  {"nome": "BNDES – Pronaf Jovem",
                   "url": "https://www.bndes.gov.br/wps/portal/site/home/financiamento/produto/pronaf-jovem"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    componentes = config.setdefault("componentes_novos", {})
    painel = config.get("paineis_publicos", {}).get("servindo")
    # Só grava o admin_painel.json quando algo muda (a atualização mensal só troca o CSV)
    if componentes.get("comp_327") != componente or (painel and "comp_327" not in painel["cartoes"]):
        componentes["comp_327"] = componente
        if painel and "comp_327" not in painel["cartoes"]:
            painel["cartoes"].append("comp_327")
        with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
            json.dump(config, arquivo, ensure_ascii=False, indent=2)
        print("admin_painel.json atualizado; painel Servindo ao povo:",
              painel["cartoes"] if painel else "não encontrado (rode preparar_lixo.py)")


if __name__ == "__main__":
    main()
