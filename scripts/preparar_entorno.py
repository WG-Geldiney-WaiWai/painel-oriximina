"""Prepara o cartão "Como são as ruas onde as pessoas moram" (no lugar do "Estrada arborizada" do Taipei), no
painel "Mudança climática".

Fonte: Pesquisa Urbanística do Entorno dos Domicílios do Censo 2022 (IBGE/SIDRA, tabela 6752). O recenseador
anotou, em cada quadra das áreas urbanas, se a rua tem árvores, pavimento, calçada, bueiro, iluminação,
rampa para cadeirante, ponto de ônibus e ciclovia. Oriximiná não tem cadastro das árvores das ruas (o que o
cartão do Taipei conta); a parte dos moradores que vivem em rua com árvores é o dado mais próximo.

- comp_329.csv: moradores das áreas urbanas pesquisadas, por característica da rua (existe / não existe /
  não declarado)

Rode de novo para atualizar:  python preparar_entorno.py
"""
import gzip
import json
import os
import urllib.request

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
URL = ("https://servicodados.ibge.gov.br/api/v3/agregados/6752/periodos/2022/variaveis/9598"
       "?localidades=N6[1505304]&classificacao=458[72117]|14[all]")
EXISTE, NAO_EXISTE, NAO_DECLARADO = "Existe", "Não existe", "Não declarado"
# Característica do IBGE -> nome no cartão (na ordem do cartão)
CARACTERISTICAS = {
    "Arborização": "Árvores na rua",
    "Via pavimentada": "Rua pavimentada",
    "Existência de calçada / passeio": "Calçada",
    "Existência de bueiro / boca de lobo": "Bueiro (boca de lobo)",
    "Existência de iluminação pública": "Iluminação pública",
    "Existência de rampa para cadeirante": "Rampa para cadeirante",
    "Existência de ponto de ônibus / van": "Ponto de ônibus ou van",
    "Existência de via sinalizada para bicicleta": "Ciclovia ou ciclofaixa",
}


def baixar():
    with urllib.request.urlopen(URL, timeout=60) as resposta:
        conteudo = resposta.read()
    if conteudo[:2] == bytes([0x1F, 0x8B]):
        conteudo = gzip.decompress(conteudo)
    valores = {}
    for resultado in json.loads(conteudo)[0]["resultados"]:
        categoria = [list(c["categoria"].values())[0] for c in resultado["classificacoes"] if c["id"] == "14"][0]
        valor = list(resultado["series"][0]["serie"].values())[0]
        valores[categoria] = int(valor) if valor.isdigit() else 0
    return valores


def main():
    valores = baixar()
    total = valores["Total"]
    linhas = []
    for nome_ibge, nome in CARACTERISTICAS.items():
        if nome_ibge == "Arborização":   # o IBGE separa por quantidade de árvores; "Existe" = pelo menos uma
            arvores = {k.split(" - ")[1]: v for k, v in valores.items() if k.startswith("Arborização - ")}
            existe = sum(v for k, v in arvores.items() if k not in ("Sem árvores", NAO_DECLARADO))
            linhas.append([nome, existe, arvores["Sem árvores"], arvores[NAO_DECLARADO]])
        else:
            linhas.append([nome] + [valores[f"{nome_ibge} - {s}"] for s in (EXISTE, NAO_EXISTE, NAO_DECLARADO)])
    tabela = pd.DataFrame(linhas, columns=["Característica da rua", EXISTE, NAO_EXISTE, NAO_DECLARADO])
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_329.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.assign(pct=(100 * tabela[EXISTE] / total).round(1)).to_string(index=False))

    def pct(nome):
        parte = tabela.set_index("Característica da rua").loc[nome, EXISTE] / total
        # Perto de 0% ou de 100%, uma casa decimal (senão 99,5% vira "100%" e 0,2% vira "0%")
        texto = f"{parte:.1%}" if parte < 0.01 or parte > 0.99 else f"{parte:.0%}"
        return texto.replace(".", ",")
    cinco = valores["Arborização - 5 ou mais árvores"] / total
    componente = {
        "id": 329, "titulo": "Como são as ruas onde as pessoas moram", "fonte": "IBGE | Censo 2022 (entorno)",
        "atualizacao": "Censo 2022", "icone": "park", "area": "Áreas urbanas de Oriximiná",
        "resumo": "Quantos moradores da cidade vivem em rua com árvores, pavimento, calçada, iluminação, ciclovia...",
        "descricao": (
            f"Mostra o que existe nas ruas onde moram os {total:,}".replace(",", ".") +
            " moradores das áreas urbanas de Oriximiná "
            "(a sede e Porto Trombetas), segundo a Pesquisa Urbanística do Entorno dos Domicílios do Censo "
            f"2022: o recenseador anotou cada quadra. {pct('Árvores na rua')} dos moradores vivem em rua com "
            f"pelo menos uma árvore no seu trecho, mas só {cinco:.0%} em rua com cinco árvores ou mais. "
            f"{pct('Rua pavimentada')} têm rua pavimentada, {pct('Calçada')} têm calçada e "
            f"{pct('Iluminação pública')} têm iluminação pública; já a rampa para cadeirante "
            f"({pct('Rampa para cadeirante')}), o ponto de ônibus ({pct('Ponto de ônibus ou van')}) e a "
            f"ciclovia ({pct('Ciclovia ou ciclofaixa')}) quase não existem. \"Não declarado\" é sobretudo a "
            "rampa nas ruas sem calçada. Em Taipei, este cartão conta as árvores plantadas nas ruas; Oriximiná "
            "não tem esse cadastro, e a parte dos moradores em rua com árvores é o dado mais próximo. Ruas "
            "arborizadas ficam mais frescas e ajudam a enfrentar o calor."),
        "exemplo": ("Mostra onde plantar árvores, fazer calçadas, rampas e ciclovias para a cidade ficar mais "
                    "fresca, segura e fácil de andar a pé e de bicicleta."),
        "tipos": ["barras_percentuais", "barras"],
        "cores": ["#56B96D", "#F65658", "#bdbdbd"],
        "unidade": "moradores", "meta": None, "maximo": None,
        "links": [{"nome": "IBGE – SIDRA, tabela 6752 (entorno dos domicílios)",
                   "url": "https://sidra.ibge.gov.br/tabela/6752"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_329"] = componente
    clima = config.get("paineis_publicos", {}).get("clima")
    if clima and "comp_329" not in clima["cartoes"]:
        clima["cartoes"].append("comp_329")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Mudança climática:",
          clima["cartoes"] if clima else "não encontrado (rode preparar_emissoes.py)")


if __name__ == "__main__":
    main()
