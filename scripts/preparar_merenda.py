"""Prepara o painel "Segurança e saúde alimentar" e o cartão "Merenda escolar (PNAE)" (no lugar da "Cadeia de
suprimentos de refeições escolares" do Taipei).

Fonte: as liberações do FNDE (Fundo Nacional de Desenvolvimento da Educação) para a Prefeitura de Oriximiná no
PNAE, o Programa Nacional de Alimentação Escolar, pagamento por pagamento (SIGEF, consulta pública):
https://www.fnde.gov.br/sigefweb/index.php/liberacoes. Cada pagamento diz para que alunos é (creche,
pré-escola, fundamental, escolas indígenas, quilombolas...). A parte comprada da agricultura familiar (a lei
manda pelo menos 30%, Lei 11.947/2009) só aparece num painel do FNDE, sem arquivo para baixar.

- comp_337.csv: dinheiro da merenda recebido por ano, por tipo de aluno (em mil reais)

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_merenda.py
"""
import html
import json
import os
import re
import unicodedata
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
URL = ("https://www.fnde.gov.br/sigefweb/index.php/liberacoes/resultado-entidade/ano/{ano}/programa/C7/uf/PA/"
       "municipio/150530")
PRIMEIRO_ANO = 2015
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
QUILOMBOLAS = "Escolas quilombolas"
INDIGENAS = "Escolas indígenas"
INFANTIL = "Creche e pré-escola"
OUTROS = "Fundamental e outros"
GRUPOS = [INFANTIL, OUTROS, QUILOMBOLAS, INDIGENAS]


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def grupo(programa):
    """O nome do pagamento mudou ao longo dos anos ("ALIMENTAÇÃO ESCOLAR - QUILOMBOLA", "PNAE - Alimentação
    Escolar - Quilombola", "Mais Educação - Quilombolas"...): basta a palavra-chave."""
    nome = sem_acento(programa)
    if "quilombol" in nome:
        return QUILOMBOLAS
    if "indigen" in nome or "indgen" in nome:
        return INDIGENAS
    if "creche" in nome or "pre-escola" in nome or "pr-escola" in nome or "pre escola" in nome:
        return INFANTIL
    return OUTROS


def pagamentos(ano):
    pedido = urllib.request.Request(URL.format(ano=ano), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        pagina = resposta.read().decode("utf-8", "ignore")
    linhas = []
    for linha in re.findall(r"(?is)<tr.*?</tr>", pagina):
        celulas = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"(?is)<td[^>]*>.*?</td>", linha)]
        # Data de pagamento | Ordem bancária | Valor | Parcela | Programa | ...
        if len(celulas) >= 5 and re.match(r"\d\d/[A-Z]{3}/\d\d", celulas[0]):
            valor = float(celulas[2].replace(".", "").replace(",", "."))
            linhas.append({"ano": ano, "data": celulas[0], "valor": valor, "grupo": grupo(celulas[4])})
    return linhas


def main():
    hoje = pd.Timestamp.now()
    todos = pd.DataFrame([p for ano in range(PRIMEIRO_ANO, hoje.year + 1) for p in pagamentos(ano)])
    tabela = (todos.pivot_table(index="ano", columns="grupo", values="valor", aggfunc="sum", fill_value=0)
              .reindex(columns=GRUPOS, fill_value=0) / 1000).round(1)
    rotulos = [str(a) for a in tabela.index]
    if tabela.index[-1] == hoje.year:   # ano atual: os pagamentos ainda não acabaram
        rotulos[-1] = f"até {MESES[hoje.month - 1]}/{hoje.year % 100:02d}"
    saida = tabela.copy()
    saida.index = rotulos
    saida.rename_axis("Ano").reset_index().to_csv(os.path.join(PASTA_COMPONENTES, "comp_337.csv"), sep=";",
                                                  index=False, encoding="utf-8")
    print(saida.to_string())

    completo = tabela.loc[:hoje.year - 1]
    ultimo = int(completo.index[-1])
    total = completo.sum(axis=1)
    comunidades = completo.loc[ultimo, QUILOMBOLAS] + completo.loc[ultimo, INDIGENAS]

    def reais(mil):
        return (f"R$ {mil / 1000:.1f} milhões" if mil >= 1000 else f"R$ {mil:.0f} mil").replace(".", ",")
    componente = {
        "id": 337, "titulo": "Merenda escolar (PNAE)", "fonte": "FNDE | Liberações do PNAE",
        "atualizacao": "Mensal", "icone": "restaurant", "area": "Rede municipal de Oriximiná",
        "resumo": "Quanto dinheiro do governo federal a Prefeitura recebe por ano para a merenda, por tipo de escola.",
        "descricao": (
            "Mostra quanto a Prefeitura de Oriximiná recebeu por ano do FNDE (governo federal) para a merenda "
            "das escolas municipais, pelo Programa Nacional de Alimentação Escolar (PNAE), em mil reais. O "
            "dinheiro vem por aluno, com valores diferentes para cada tipo: creche e pré-escola, ensino "
            "fundamental e outros (EJA, atendimento especializado, tempo integral), e um valor maior por aluno "
            f"nas escolas quilombolas e indígenas. Em {ultimo}, foram {reais(total[ultimo])}, dos quais "
            f"{reais(comunidades)} ({comunidades / total[ultimo]:.0%}) para as escolas das comunidades "
            f"quilombolas e indígenas; em {PRIMEIRO_ANO}, tinham sido {reais(total[PRIMEIRO_ANO])}. Os "
            "municípios costumam completar a merenda com dinheiro próprio, que não aparece aqui. A Lei "
            "11.947/2009 manda usar pelo menos 30% do dinheiro do PNAE para comprar alimentos da agricultura "
            "familiar; quanto "
            "Oriximiná comprou dos agricultores só aparece no painel do FNDE, sem arquivo para baixar. As "
            "escolas estaduais recebem a merenda pelo Governo do Pará e não entram aqui. Em Taipei, este "
            "cartão mostra os fornecedores de cada escola, que no Brasil não são publicados."),
        "exemplo": ("Mostra o tamanho da merenda escolar e ajuda a planejar compras dos agricultores, "
                    "quilombolas e ribeirinhos de Oriximiná, com alimentos frescos e da região."),
        "tipos": ["colunas", "linha_tempo_empilhada"],
        "cores": ["#F8CF58", "#24B0DD", "#c18ad8", "#56B96D"],
        "unidade": "mil reais", "meta": None, "maximo": None,
        "links": [{"nome": "FNDE – liberações (consulta pública)",
                   "url": "https://www.fnde.gov.br/sigefweb/index.php/liberacoes"},
                  {"nome": "FNDE – PNAE: dados da agricultura familiar",
                   "url": "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/programas/pnae/consultas/pnae-dados-da-agricultura-familiar"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_337"] = componente
    paineis = config.setdefault("paineis_publicos", {})
    if "alimentar" not in paineis:
        # Painel novo, logo depois do "Uma cidade resistente a desastres" (antes dos da Calha Norte)
        novo = {"titulo": "Segurança e saúde alimentar", "icone": "restaurant", "cartoes": ["comp_337"],
                "grupo": "Painel de Oriximiná"}
        ordem = list(paineis.items())
        chaves = [c for c, _ in ordem]
        depois = chaves.index("desastres") + 1 if "desastres" in chaves else len(ordem)
        ordem.insert(depois, ("alimentar", novo))
        config["paineis_publicos"] = paineis = dict(ordem)
    elif "comp_337" not in paineis["alimentar"]["cartoes"]:
        paineis["alimentar"]["cartoes"].insert(0, "comp_337")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painéis:", list(paineis), paineis["alimentar"]["cartoes"])


if __name__ == "__main__":
    main()
