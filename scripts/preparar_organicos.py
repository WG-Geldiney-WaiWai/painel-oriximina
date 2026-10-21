"""Prepara o cartão "Produtores orgânicos certificados" (como a "Distribuição em fazendas orgânicas" do Taipei),
no painel "Segurança e saúde alimentar".

Fonte: o CNPO (Cadastro Nacional de Produtores Orgânicos) do Ministério da Agricultura, uma planilha atualizada
de tempos em tempos: https://www.gov.br/agricultura/pt-br/assuntos/sustentabilidade/organicos/
cadastro-nacional-de-produtores-organicos-cnpo (arquivo cnpo-mapa-DD-MM-AAAA.xlsx). O script procura na página a
planilha mais nova. A cidade é digitada à mão no cadastro e às vezes vem errada (Oriximiná aparece como
"ORIXIMA"): por isso o nome é comparado com os municípios da Calha Norte pelo jeito mais parecido.

- comp_345.csv: produtores orgânicos de cada município da Calha Norte
- comp_345_mapa.csv: o mesmo, para o mapa dos municípios e para a "Comparação de mapas"

Rode de novo para atualizar (ou clique em "Atualizar" na administração):  python preparar_organicos.py
"""
import difflib
import json
import os
import re
import unicodedata
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_CNPO = os.path.join(PASTA_FONTES, "CNPO")
PAGINA = ("https://www.gov.br/agricultura/pt-br/assuntos/sustentabilidade/organicos/"
          "cadastro-nacional-de-produtores-organicos-cnpo")
ARQ_REGIAO = "regiao_idades.csv"   # os 9 municípios da Calha Norte do painel
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
PRODUTORES = "Produtores orgânicos"
CABECALHO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}


def sem_acento(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().upper().strip()


def planilha_mais_nova():
    with urllib.request.urlopen(urllib.request.Request(PAGINA, headers=CABECALHO), timeout=120) as resposta:
        pagina = resposta.read().decode("utf-8", "ignore")
    links = set(re.findall(r'href="([^"]*cnpo-mapa-(\d{2})-(\d{2})-(\d{4})\.xlsx)"', pagina))
    if not links:
        raise RuntimeError("Não achei a planilha do CNPO na página do Ministério da Agricultura")
    url, dia, mes, ano = max(links, key=lambda l: (l[3], l[2], l[1]))
    os.makedirs(PASTA_CNPO, exist_ok=True)
    arquivo = os.path.join(PASTA_CNPO, f"cnpo_{ano}{mes}{dia}.xlsx")
    if not os.path.exists(arquivo):
        with urllib.request.urlopen(urllib.request.Request(url, headers=CABECALHO), timeout=300) as resposta, \
                open(arquivo, "wb") as saida:
            saida.write(resposta.read())
    return arquivo, f"{dia}/{mes}/{ano}"


def main():
    arquivo, data = planilha_mais_nova()
    cadastro = pd.read_excel(arquivo, header=2, dtype=str)   # as 2 primeiras linhas são o título
    para = cadastro[cadastro["UF"].str.strip() == "PA"].copy()
    regiao = pd.read_csv(ARQ_REGIAO, sep=";", dtype=str)["Nome"].tolist()
    por_nome = {sem_acento(m): m for m in regiao}
    # Cidade digitada -> município da região, se o nome for bem parecido ("ORIXIMA" -> Oriximiná)
    para["municipio"] = [por_nome.get((difflib.get_close_matches(sem_acento(c), list(por_nome), n=1, cutoff=0.8)
                                       or [None])[0]) for c in para["CIDADE"]]
    nossos = para[para["municipio"].notna()]
    print(nossos.groupby(["municipio", "CIDADE"]).size().to_string())
    contagem = nossos["municipio"].value_counts().reindex(regiao, fill_value=0).sort_values(ascending=False)
    tabela = pd.DataFrame({"Município": contagem.index, PRODUTORES: contagem.values})
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_345.csv"), sep=";", index=False, encoding="utf-8")
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_345_mapa.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    oriximina = nossos[nossos["municipio"] == "Oriximiná"]
    atividades = oriximina["ATIVIDADES"].fillna("").str.upper()
    copaiba = int(atividades.str.contains("COPA").sum())
    processamento = int(oriximina["ESCOPO"].fillna("").str.upper().str.contains("PROCESSAMENTO").sum())
    certificadoras = sorted({e.strip().title() for e in oriximina["ENTIDADE"].dropna()})
    com_produtores = tabela[tabela[PRODUTORES] > 0]
    nomes_errados = sorted({c.strip() for c in oriximina["CIDADE"] if sem_acento(c) != "ORIXIMINA"})
    componente = {
        "id": 345, "titulo": "Produtores orgânicos certificados", "fonte": "Ministério da Agricultura | CNPO",
        "atualizacao": data, "icone": "eco", "area": "Calha Norte do Pará",
        "resumo": "Quantos produtores orgânicos certificados há em Oriximiná e nos municípios vizinhos.",
        "descricao": (
            "Mostra quantos produtores orgânicos certificados há em cada município da Calha Norte, segundo o "
            f"Cadastro Nacional de Produtores Orgânicos do Ministério da Agricultura ({data}). Oriximiná tem "
            f"{len(oriximina)}, "
            + ("todos no extrativismo de óleo de copaíba" if copaiba == len(oriximina) and copaiba else
               f"{copaiba} deles no extrativismo de óleo de copaíba")
            + (f", {processamento} também com o processamento do óleo" if processamento else "")
            + f", certificados pela {', '.join(certificadoras)}. Na região, só "
            f"{' e '.join(f'{m} ({n})' for m, n in zip(com_produtores['Município'], com_produtores[PRODUTORES]))} "
            "têm produtores orgânicos certificados. "
            + (f"No cadastro, a cidade é escrita à mão, e Oriximiná aparece com o nome errado "
               f"({', '.join(chr(34) + n + chr(34) for n in nomes_errados)}); o painel junta os nomes parecidos. "
               if nomes_errados else "")
            + "Os produtores que vendem como orgânicos sem certificado não entram. Em Taipei, este cartão mostra "
            "as fazendas orgânicas."),
        "exemplo": ("Mostra o potencial dos produtos da floresta certificados, como o óleo de copaíba, e ajuda a "
                    "planejar apoio à certificação de mais produtores, como a castanha e o açaí."),
        "tipos": ["barras"],
        "cores": ["#56B96D"],
        "unidade": "produtores", "meta": None, "maximo": None,
        "links": [{"nome": "Ministério da Agricultura – Cadastro Nacional de Produtores Orgânicos", "url": PAGINA}],
        "colaboradores": [], "mapa": {"tipo": "municipios", "nome": "Produtores orgânicos certificados",
                                      "cor": "#56B96D"},
        "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_345"] = componente
    painel = config.get("paineis_publicos", {}).get("alimentar")
    if painel and "comp_345" not in painel["cartoes"]:
        painel["cartoes"].append("comp_345")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo_admin:
        json.dump(config, arquivo_admin, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Segurança e saúde alimentar:", painel["cartoes"] if painel else "—")


if __name__ == "__main__":
    main()
