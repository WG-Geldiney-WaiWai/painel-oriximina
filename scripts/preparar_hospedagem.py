"""Prepara o painel "Revitalizando o distrito comercial" e o cartão "Hotéis e pousadas" (como as "Estatísticas de
hotéis" do Taipei).

Fontes:
- RAIS (Ministério do Trabalho), arquivo de estabelecimentos já guardado pelo preparar_industria_alimentos.py em
  PASTA_FONTES/RAIS_ESTAB/oriximina_ANO.csv: os hotéis e pousadas (CNAE 5510) e outros alojamentos (5590)
  declarados a cada ano;
- Cadastur, o cadastro do Ministério do Turismo (https://dados.turismo.gov.br/dataset/meios-de-hospedagem): os
  meios de hospedagem cadastrados no trimestre mais recente, com quartos e leitos. O cadastro é voluntário,
  por isso tem menos estabelecimentos que a RAIS.

- comp_344.csv: hotéis e pousadas e outros alojamentos por ano (RAIS)
- comp_344_mapa.csv não há: o Cadastur traz o endereço, mas não a posição no mapa

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_hospedagem.py
"""
import glob
import json
import os
import re
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_RAIS = os.path.join(PASTA_FONTES, "RAIS_ESTAB")
PASTA_CADASTUR = os.path.join(PASTA_FONTES, "Cadastur")
API_CADASTUR = "https://dados.turismo.gov.br/api/3/action/package_show?id=meios-de-hospedagem"
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
HOTEIS, OUTROS = "Hotéis e pousadas", "Outros alojamentos"


def rais():
    linhas = []
    for arquivo in sorted(glob.glob(os.path.join(PASTA_RAIS, "oriximina_*.csv"))):
        ano = int(re.search(r"(\d{4})", os.path.basename(arquivo)).group(1))
        tabela = pd.read_csv(arquivo, sep=";", dtype=str)
        subclasse = tabela["subclasse"].str.strip().str.zfill(7)
        empregados = pd.to_numeric(tabela["empregados"], errors="coerce").fillna(0)
        hoteis = subclasse.str.startswith("551")
        linhas.append({"Ano": ano, HOTEIS: int(hoteis.sum()), OUTROS: int(subclasse.str.startswith("559").sum()),
                       "empregados": int(empregados[hoteis].sum())})
    return pd.DataFrame(linhas).set_index("Ano")


def cadastur():
    """Meios de hospedagem de Oriximiná no arquivo mais recente do Cadastur (baixa se ainda não tiver)."""
    with urllib.request.urlopen(urllib.request.Request(API_CADASTUR, headers={"User-Agent": "Mozilla/5.0"}),
                                timeout=120) as resposta:
        recursos = json.loads(resposta.read())["result"]["resources"]
    planilhas = [r for r in recursos if str(r.get("url", "")).lower().endswith((".xlsx", ".xls"))]
    recente = max(planilhas, key=lambda r: r.get("created") or "")
    os.makedirs(PASTA_CADASTUR, exist_ok=True)
    arquivo = os.path.join(PASTA_CADASTUR, f"hospedagem_{recente['id']}{os.path.splitext(recente['url'])[1]}")
    if not os.path.exists(arquivo):
        with urllib.request.urlopen(urllib.request.Request(recente["url"], headers={"User-Agent": "Mozilla/5.0"}),
                                    timeout=300) as resposta, open(arquivo, "wb") as saida:
            saida.write(resposta.read())
    tabela = pd.read_excel(arquivo, dtype=str)
    nossos = tabela[(tabela["UF"] == "PA") & (tabela["Município"].str.upper() == "ORIXIMINÁ")
                    & (tabela["Situação da Atividade"].str.strip() == "Operação")]
    return nossos, recente["name"]


def main():
    por_ano = rais()
    por_ano[[HOTEIS, OUTROS]].rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_344.csv"), sep=";", index=False, encoding="utf-8")
    print(por_ano.to_string())
    cadastrados, periodo = cadastur()
    print(cadastrados[["Nome Fantasia", "Tipo de Hospedagem", "Unidade Habitacionais", "Leitos"]].to_string())

    ultimo, primeiro = int(por_ano.index.max()), int(por_ano.index.min())
    nomes = [str(n).strip().title() for n in cadastrados["Nome Fantasia"]]
    quartos = pd.to_numeric(cadastrados["Unidade Habitacionais"], errors="coerce").fillna(0).sum()
    leitos = pd.to_numeric(cadastrados["Leitos"], errors="coerce").fillna(0).sum()
    componente = {
        "id": 344, "titulo": "Hotéis e pousadas", "fonte": "Ministério do Trabalho – RAIS e Ministério do Turismo – Cadastur",
        "atualizacao": f"RAIS {ultimo}", "icone": "hotel", "area": "Município de Oriximiná",
        "resumo": "Quantos hotéis, pousadas e outros alojamentos Oriximiná tem, ano a ano.",
        "descricao": (
            f"Mostra quantos hotéis, pousadas e outros alojamentos de Oriximiná declararam a RAIS, do Ministério "
            f"do Trabalho, a cada ano de {primeiro} a {ultimo}. Em {ultimo}, eram "
            f"{int(por_ano.loc[ultimo, HOTEIS])} hotéis e pousadas e {int(por_ano.loc[ultimo, OUTROS])} outros "
            f"alojamentos, com {int(por_ano.loc[ultimo, 'empregados'])} empregados de carteira assinada; em "
            f"{primeiro}, eram {int(por_ano.loc[primeiro, HOTEIS])} hotéis e pousadas. No Cadastur, o cadastro "
            f"do Ministério do Turismo, que é voluntário, só {len(cadastrados)} estão cadastrados ({periodo.lower()}): "
            f"{', '.join(nomes[:-1]) + ' e ' + nomes[-1] if len(nomes) > 1 else ''.join(nomes)}, com "
            f"{int(quartos)} quartos e {int(leitos)} leitos no total. Quem não tem empregado registrado nem se "
            "cadastrou não aparece (como muitas pousadas familiares e casas que alugam quartos). Em Taipei, este "
            "cartão mostra os hotéis de cada distrito."),
        "exemplo": ("Mostra quanto Oriximiná pode receber de visitantes e ajuda a planejar o turismo e os "
                    "eventos, como o Círio e o Festribal, e a incentivar o cadastro no Cadastur."),
        "tipos": ["colunas", "linha_tempo_empilhada"],
        "cores": ["#c18ad8", "#24B0DD"],
        "unidade": "estabelecimentos", "meta": None, "maximo": None,
        "links": [{"nome": "Ministério do Turismo – Cadastur (meios de hospedagem)",
                   "url": "https://dados.turismo.gov.br/dataset/meios-de-hospedagem"},
                  {"nome": "Ministério do Trabalho – microdados da RAIS (PDET)",
                   "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_344"] = componente
    paineis = config.setdefault("paineis_publicos", {})
    if "comercio" not in paineis:
        # Painel novo, logo depois do "Meio ambiente sustentável" (antes dos da Calha Norte)
        novo = {"titulo": "Revitalizando o distrito comercial", "icone": "shopping_cart", "cartoes": ["comp_344"],
                "grupo": "Painel de Oriximiná"}
        ordem = list(paineis.items())
        chaves = [c for c, _ in ordem]
        depois = chaves.index("ambiente") + 1 if "ambiente" in chaves else len(ordem)
        ordem.insert(depois, ("comercio", novo))
        config["paineis_publicos"] = paineis = dict(ordem)
    elif "comp_344" not in paineis["comercio"]["cartoes"]:
        paineis["comercio"]["cartoes"].append("comp_344")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painéis:", list(paineis), paineis["comercio"]["cartoes"])


if __name__ == "__main__":
    main()
