"""Prepara o cartão "Crianças de 0 a 4 anos por bairro" (como o "Estatísticas sobre o número de crianças
pequenas" do Taipei), no painel "Educação", ao lado do cartão das creches.

Usa o mesmo caminho do preparar_dados.py: as faixas de idade de cada setor do Censo 2022 (com o sigilo do IBGE
completado) repartidas pelos bairros da sede conforme onde ficam os domicílios do setor no CNEFE. A diferença é
a faixa: aqui a de 0 a 4 anos (V01031), que o preparar_dados.py junta no grupo de 0 a 14.

- comp_322.csv: crianças de 0 a 4 anos e moradores de cada bairro da sede
- comp_322_mapa.csv: as crianças de 0 a 4 anos por bairro, para o mapa e para a "Comparação de mapas"

Lê os mesmos arquivos grandes do IBGE do preparar_dados.py (pasta das fontes).

Rode de novo para atualizar:  python preparar_criancas_bairro.py
"""
import json
import os


import preparar_dados   # (ao importar, ele passa a trabalhar na pasta "dados" do painel)

PASTA_COMPONENTES = os.path.join("componentes")
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
PEQUENAS = "Crianças de 0 a 4 anos"
# Faixas para repartir pelos bairros (somadas dão todos os moradores, como no preparar_dados.py)
GRUPOS = {PEQUENAS: ["V01031"], "5 a 14 anos": ["V01032", "V01033"],
          "15 anos ou mais": ["V01034", "V01035", "V01036", "V01037", "V01038", "V01039", "V01040", "V01041"]}
FORA_DOS_BAIRROS = (preparar_dados.AREA_FORA_SEDE, preparar_dados.AREA_TROMBETAS)


def main():
    setores = preparar_dados.ler_basico().merge(preparar_dados.ler_demografia(), on="CD_SETOR", how="left")
    setores[list(preparar_dados.FAIXAS_IBGE)] = setores[list(preparar_dados.FAIXAS_IBGE)].fillna(0)
    setores = preparar_dados.completar_sigilo(setores)
    for grupo, colunas in GRUPOS.items():
        setores[grupo] = setores[colunas].sum(axis=1)
    preparar_dados.GRUPOS = GRUPOS   # o distribuir_por_bairro reparte as colunas de GRUPOS
    bairros = preparar_dados.distribuir_por_bairro(setores)
    bairros = bairros[~bairros["nome"].isin(FORA_DOS_BAIRROS)].sort_values(PEQUENAS, ascending=False)

    df = bairros.rename(columns={"nome": "Bairro"})[["Bairro", PEQUENAS]]
    df.to_csv(os.path.join(PASTA_COMPONENTES, "comp_322.csv"), sep=";", index=False, encoding="utf-8")
    df.to_csv(os.path.join(PASTA_COMPONENTES, "comp_322_mapa.csv"), sep=";", index=False, encoding="utf-8")
    bairros["parte"] = bairros[PEQUENAS] / bairros["Habitantes"]
    print(bairros[["nome", PEQUENAS, "Habitantes", "parte"]].to_string(index=False))

    total = int(df[PEQUENAS].sum())
    moradores = int(bairros["Habitantes"].sum())
    mais = bairros.iloc[0]
    jovem = bairros[bairros["Habitantes"] >= 1000].sort_values("parte", ascending=False).iloc[0]

    def fmt(n):
        return f"{int(n):,}".replace(",", ".")
    componente = {
        "id": 322, "titulo": "Crianças de 0 a 4 anos por bairro", "fonte": "IBGE | Censo 2022 e CNEFE 2022",
        "atualizacao": "Censo 2022", "icone": "bar_chart", "area": "Sede urbana de Oriximiná",
        "resumo": "Quantas crianças de 0 a 4 anos moram em cada bairro da sede: onde mais se precisa de creche.",
        "descricao": (
            f"Mostra quantas crianças de 0 a 4 anos moram em cada bairro da sede de Oriximiná, segundo o Censo "
            f"2022: {fmt(total)} crianças entre {fmt(moradores)} moradores dos bairros. O bairro com mais crianças "
            f"pequenas é {mais['nome']} ({fmt(mais[PEQUENAS])}); entre os bairros com mais de mil moradores, a "
            f"maior parte de crianças pequenas está em {jovem['nome']} ({jovem['parte']:.0%} dos moradores). Os "
            "moradores de cada setor censitário foram repartidos entre os bairros conforme onde ficam os seus "
            "domicílios no CNEFE, como no cartão \"Moradores por bairro da sede\"; por isso os números por bairro "
            "são estimativas. Junto do cartão \"Creches e pré-escolas\", mostra em que bairros abrir vagas de "
            "creche. A faixa do Censo por setor é de 0 a 4 anos (o cartão do Taipei usa as crianças pequenas)."),
        "exemplo": ("Ajuda a decidir onde construir creches e ampliar vagas: os bairros com mais crianças "
                    "pequenas são os que mais precisam, sobretudo os novos, onde moram muitas famílias jovens."),
        "tipos": ["barras", "mapa_arvore"],
        "cores": ["#a0b8e8"], "unidade": "crianças", "meta": None, "maximo": None,
        "links": [{"nome": "IBGE – Censo Demográfico 2022", "url": "https://censo2022.ibge.gov.br"}],
        "colaboradores": [], "mapa": {"tipo": "bairros", "nome": "Crianças de 0 a 4 anos por bairro", "cor": "#7d9be0"},
        "historico": None,
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_322"] = componente
    educacao = config["paineis_publicos"].get("educacao")
    if educacao and "comp_322" not in educacao["cartoes"]:
        # Logo depois do cartão das creches (comp_318)
        cartoes = educacao["cartoes"]
        cartoes.insert(cartoes.index("comp_318") + 1 if "comp_318" in cartoes else len(cartoes), "comp_322")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Educação:",
          educacao["cartoes"] if educacao else "não encontrado (rode preparar_educacao.py)")


if __name__ == "__main__":
    main()
