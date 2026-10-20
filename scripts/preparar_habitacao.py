"""Prepara o painel "Habitação" de Oriximiná (o Taipei tem um painel de habitação, com o subsídio de aluguel).

Oriximiná não publica dados do aluguel social; os cartões usam o Minha Casa Minha Vida, do Ministério das
Cidades, que publica os dados por município:

- comp_307.csv: empreendimentos do MCMV subsidiado em Oriximiná (moradias entregues e em obra)
- comp_308.csv: moradias financiadas pela Caixa com recursos do FGTS, por ano

Os cartões entram como componentes da administração (usuarios/admin_painel.json), no painel público
"Habitação" do grupo "Painel de Oriximiná". Os nomes dos arquivos mudam a cada atualização (pelo menos a
cada três meses): o script procura os links mais recentes na página de bases de dados do programa.

Rode de novo para atualizar:  python preparar_habitacao.py
"""
import io
import json
import os
import re
import urllib.request
import zipfile

import pandas as pd

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
PAGINA_BASES = ("https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/habitacao/"
                "programa-minha-casa-minha-vida/bases-de-dados-do-programa-minha-casa-minha-vida")
CODIGO_IBGE = "150530"   # o MCMV usa o código do IBGE sem o último dígito

MODALIDADES = {"FAR": "FAR", "Entidades": "Entidades", "Rural": "Rural"}
# O arquivo do Ministério vem sem acentos: as palavras conhecidas voltam acentuadas no cartão
ACENTOS = {"Oriximina": "Oriximiná", "Simoes": "Simões", "Irma": "Irmã", "Veronica": "Verônica", "Sao": "São",
           "Jose": "José", "Joao": "João", "Conceicao": "Conceição", "Esperanca": "Esperança"}


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resposta:
        return resposta.read()


def ler_zip(url):
    """Lê o CSV de dentro do ZIP (os arquivos do MCMV vêm em latin-1, separados por ponto e vírgula)."""
    with zipfile.ZipFile(io.BytesIO(baixar(url))) as z:
        return pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), sep=";", encoding="latin-1", dtype=str)


def numero(texto):
    """'51.685.937,07' ou '994' -> número."""
    texto = str(texto or "0").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto or 0)


def nome_bonito(nome):
    nome = re.sub(r"\s+", " ", nome or "").strip().title()
    nome = re.sub(r"\b(De|Da|Do|Dos|Das|E)\b", lambda m: m.group(1).lower(), nome)
    nome = re.sub(r"\b(Ii|Iii|Iv)\b", lambda m: m.group(1).upper(), nome)   # "Oriximina Ii" -> "II"
    return re.sub(r"\b\w+\b", lambda m: ACENTOS.get(m.group(0), m.group(0)), nome)


def main():
    pagina = baixar(PAGINA_BASES).decode("utf-8", "ignore")
    links = re.findall(r'href="([^"]+\.zip)"', pagina)
    url_subsidiado = next(u for u in links if "mcmv_subsidiado" in u)
    url_fgts = next(u for u in links if "financ_sintetico" in u)
    print(url_subsidiado, url_fgts, sep="\n")

    # Empreendimentos subsidiados (FAR, Entidades, Rural): uma linha por empreendimento
    sub = ler_zip(url_subsidiado)
    sub = sub[sub["cod_ibge"].str.replace(".", "", regex=False).str.strip() == CODIGO_IBGE].copy()
    sub["ano"] = sub["dt_assinatura"].str[-4:]
    for coluna in ("qtd_uh", "qtd_uh_entregues", "qtd_uh_vigentes", "qtd_uh_distratadas"):
        sub[coluna] = sub[coluna].map(numero).astype(int)
    sub = sub.sort_values(["ano", "qtd_uh"], ascending=[True, False])
    df_emp = pd.DataFrame({
        # Sem vírgula no texto: o painel adivinha o separador do CSV e se confundia com ela
        "Empreendimento": [f"{nome_bonito(n)} ({MODALIDADES.get(m, m)} – {a})"
                           for n, m, a in zip(sub["txt_nome_empreendimento"], sub["txt_modalidade"], sub["ano"])],
        "Moradias entregues": sub["qtd_uh_entregues"].values,
        "Moradias em obra": sub["qtd_uh_vigentes"].values,
    })
    if sub["qtd_uh_distratadas"].sum():
        df_emp["Contratos desfeitos"] = sub["qtd_uh_distratadas"].values
    df_emp.to_csv(os.path.join(PASTA_COMPONENTES, "comp_307.csv"), sep=";", index=False, encoding="utf-8")
    print(df_emp.to_string(index=False))

    # Financiamentos com FGTS: moradias por ano de contratação
    fgts = ler_zip(url_fgts)
    fgts = fgts[fgts["cod_ibge"].str.strip() == CODIGO_IBGE].copy()
    fgts["qtd"] = fgts["qtd_uh_financiadas"].astype(int)
    fgts["subsidio"] = fgts["vlr_subsidio"].astype(float)
    # Com desconto do governo: o que corresponde ao subsídio de juros do Taipei
    fgts["qtd_desconto"] = fgts["qtd"].where(fgts["subsidio"] > 0, 0)
    df_fgts = (fgts.groupby("num_ano")[["qtd", "qtd_desconto"]].sum().reset_index()
               .rename(columns={"num_ano": "Ano", "qtd": "Moradias financiadas",
                                "qtd_desconto": "Com desconto do governo"}))
    df_fgts.to_csv(os.path.join(PASTA_COMPONENTES, "comp_308.csv"), sep=";", index=False, encoding="utf-8")
    print(df_fgts.to_string(index=False))

    data_ref = sub["data_referencia"].iloc[0].strip('"')
    total, entregues, em_obra = int(sub["qtd_uh"].sum()), int(sub["qtd_uh_entregues"].sum()), int(sub["qtd_uh_vigentes"].sum())
    maior = sub.sort_values("qtd_uh").iloc[-1]
    rurais = sub[sub["txt_modalidade"] == "Rural"]

    def fmt(n):
        return f"{int(n):,}".replace(",", ".")
    link = {"nome": "Ministério das Cidades – Bases de dados do Minha Casa Minha Vida", "url": PAGINA_BASES}
    componentes = {
        "comp_307": {
            "id": 307, "titulo": "Moradias do Minha Casa Minha Vida", "fonte": "Ministério das Cidades | MCMV",
            "atualizacao": data_ref[3:], "icone": "bar_chart", "area": "Município de Oriximiná",
            "resumo": "Empreendimentos do Minha Casa Minha Vida em Oriximiná: moradias entregues e em obra.",
            "descricao": (
                f"Mostra os {len(sub)} empreendimentos do Minha Casa Minha Vida subsidiado em Oriximiná (moradias "
                f"pagas quase todas pelo governo, para famílias de baixa renda), com {fmt(total)} moradias: "
                f"{fmt(entregues)} entregues e {fmt(em_obra)} ainda em obra. O maior é o "
                f"{nome_bonito(maior['txt_nome_empreendimento'])}, com {fmt(maior['qtd_uh'])} moradias. "
                f"FAR são os conjuntos contratados pela Caixa com construtoras; Entidades, os feitos com "
                f"associações e sindicatos; Rural, as casas no campo ({fmt(rurais['qtd_uh'].sum())} moradias, "
                f"nenhuma entregue até {data_ref}). As datas são as da assinatura do contrato."),
            "exemplo": ("Ajuda a acompanhar a entrega das moradias populares e a cobrar as obras atrasadas, como "
                        "as casas rurais contratadas que ainda não foram entregues."),
            # Em porcentagem primeiro: em números, o Tia Ana (994) apagava os outros empreendimentos
            "tipos": ["barras_percentuais", "barras"],
            "cores": ["#56B96D", "#F8CF58", "#F65658"], "unidade": "moradias", "meta": None, "maximo": None,
            "links": [link], "colaboradores": [], "mapa": None, "historico": None,
        },
        "comp_308": {
            "id": 308, "titulo": "Moradias financiadas com FGTS", "fonte": "Ministério das Cidades | MCMV-FGTS",
            "atualizacao": str(df_fgts["Ano"].iloc[-1]), "icone": "show_chart", "area": "Município de Oriximiná",
            "resumo": "Moradias financiadas em Oriximiná com FGTS, por ano, e quantas tiveram desconto do governo.",
            "descricao": (
                f"Mostra quantas moradias foram financiadas em Oriximiná pelo Minha Casa Minha Vida com recursos "
                f"do FGTS (a família compra a casa e paga em prestações, com desconto do governo conforme a renda), "
                f"por ano do contrato: {fmt(df_fgts['Moradias financiadas'].sum())} de {df_fgts['Ano'].iloc[0]} a "
                f"{df_fgts['Ano'].iloc[-1]}, com o pico em {df_fgts.loc[df_fgts['Moradias financiadas'].idxmax(), 'Ano']}. "
                f"Dessas, {fmt(df_fgts['Com desconto do governo'].sum())} "
                f"({df_fgts['Com desconto do governo'].sum() / df_fgts['Moradias financiadas'].sum():.0%}) tiveram "
                f"desconto do governo, que somou R$ {fmt(fgts['subsidio'].sum())} de "
                f"R$ {fmt(fgts['vlr_financiamento'].astype(float).sum())} financiados"
                " (é o parecido, aqui, com o subsídio de juros do Taipei: o governo paga parte da casa das famílias de "
                "renda mais baixa). Os números são pequenos porque, em Oriximiná, poucas famílias conseguem comprar casa financiada; "
                "a maior parte das moradias do programa na cidade são as subsidiadas (o outro cartão)."),
            "exemplo": ("Mostra se o crédito para a casa própria chega à cidade: poucos financiamentos indicam "
                        "espaço para ações com a Caixa e as imobiliárias, e para a regularização de terrenos."),
            "tipos": ["colunas", "linha_tempo_separada"],
            "cores": ["#24B0DD", "#56B96D"], "unidade": "moradias", "meta": None, "maximo": None,
            "links": [link], "colaboradores": [], "mapa": None, "historico": None,
        },
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {}).update(componentes)
    paineis = config["paineis_publicos"]
    habitacao = {"titulo": "Habitação", "icone": "home", "cartoes": list(componentes), "grupo": "Painel de Oriximiná"}
    if "habitacao" in paineis:
        paineis["habitacao"] = {**habitacao, "cartoes": paineis["habitacao"]["cartoes"]}   # mantém a ordem escolhida
    else:
        # No fim do grupo "Painel de Oriximiná" (antes dos painéis da Calha Norte)
        novos = {}
        for chave, painel in paineis.items():
            if painel["grupo"] != "Painel de Oriximiná" and "habitacao" not in novos:
                novos["habitacao"] = habitacao
            novos[chave] = painel
        novos.setdefault("habitacao", habitacao)
        config["paineis_publicos"] = novos
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado: painel \"Habitação\" com", ", ".join(habitacao["cartoes"]))


if __name__ == "__main__":
    main()
