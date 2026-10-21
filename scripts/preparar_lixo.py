"""Prepara o painel "Servindo ao povo" com os cartões do destino do lixo das casas (Censo do IBGE), no lugar
do "Ponto de coleta de caminhão de lixo" do Taipei (Oriximiná não publica as rotas nem os pontos do caminhão).

- comp_323.csv: destino do lixo das casas do município em 2022 (IBGE/SIDRA, tabela 6892)
  comp_323_historico.csv: o mesmo em 2000, 2010 e 2022 (tabelas 1439, 3217 e 6892)
- comp_324.csv: casas com e sem coleta em cada bairro da sede; comp_324_mapa.csv: % sem coleta por bairro.
  Usa o caminho do preparar_dados.py: o destino do lixo de cada setor do Censo 2022 (com o sigilo do IBGE
  completado) repartido pelos bairros conforme onde ficam os domicílios do setor no CNEFE.

Arquivos do IBGE (pasta das fontes), além dos do preparar_dados.py:
  Agregados_por_setores_caracteristicas_domicilio1_BR/d1.zip   (total de casas de cada setor, V00001)
  Agregados_por_setores_caracteristicas_domicilio2_BR/d2.zip   (destino do lixo, V00397 a V00402)
  https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/

Rode de novo para atualizar:  python preparar_lixo.py
"""
import gzip
import io
import json
import os
import unicodedata
import urllib.request
import zipfile

import pandas as pd

import preparar_dados   # (ao importar, ele passa a trabalhar na pasta "dados" do painel)

PASTA_COMPONENTES = os.path.join("componentes")
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
PASTA_IBGE = preparar_dados.PASTA_IBGE
ARQ_DOMICILIO1 = os.path.join(PASTA_IBGE, "Agregados_por_setores_caracteristicas_domicilio1_BR", "d1.zip")
ARQ_DOMICILIO2 = os.path.join(PASTA_IBGE, "Agregados_por_setores_caracteristicas_domicilio2_BR", "d2.zip")
API_SIDRA = "https://servicodados.ibge.gov.br/api/v3/agregados"

# Destinos do lixo: variável do setor (Censo 2022) e categorias das tabelas do SIDRA de 2022, 2010 e 2000
COLETA_CASA = "Coletado em casa"
CACAMBA = "Caçamba da limpeza"
QUEIMADO = "Queimado na propriedade"
DESTINOS = {
    COLETA_CASA: "V00397", QUEIMADO: "V00399", CACAMBA: "V00398", "Enterrado na propriedade": "V00400",
    "Jogado em terreno ou área pública": "V00401", "Outro destino": "V00402",
}
CATEGORIAS_SIDRA = {   # nome no SIDRA (sem acento e minúsculo, para comparar) -> destino do cartão
    "coletado no domicilio por servico de limpeza": COLETA_CASA, "coletado por servico de limpeza": COLETA_CASA,
    "depositado em cacamba de servico de limpeza": CACAMBA, "coletado em cacamba de servico de limpeza": CACAMBA,
    "queimado na propriedade": QUEIMADO, "queimado (na propriedade)": QUEIMADO,
    "enterrado na propriedade": "Enterrado na propriedade", "enterrado (na propriedade)": "Enterrado na propriedade",
    "jogado em terreno baldio, encosta ou area publica": "Jogado em terreno ou área pública",
    "jogado em terreno baldio ou logradouro": "Jogado em terreno ou área pública",
    "jogado em rio, lago ou mar": "Jogado em terreno ou área pública",
    "outro destino": "Outro destino",
}
TABELAS_SIDRA = {   # ano: (tabela, variável, classificações)
    2000: (1439, 96, "1[0]|67[all]"),
    2010: (3217, 96, "1[0]|67[all]|61[0]|309[0]"),
    2022: (6892, 381, "67[all]"),
}
# Por bairro: com coleta (em casa ou caçamba), queimado e o resto
COM_COLETA, SEM_COLETA_OUTROS = "Com coleta", "Outro destino sem coleta"
SEM_COLETA_PCT = "Casas sem coleta de lixo (%)"
FORA_DOS_BAIRROS = (preparar_dados.AREA_FORA_SEDE, preparar_dados.AREA_TROMBETAS)


def baixar_json(url):
    with urllib.request.urlopen(url, timeout=60) as resposta:
        conteudo = resposta.read()
    if conteudo[:2] == bytes([0x1F, 0x8B]):
        conteudo = gzip.decompress(conteudo)
    return json.loads(conteudo)


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


def destino_do_lixo_sidra(ano):
    """Casas de Oriximiná por destino do lixo no Censo daquele ano (SIDRA)."""
    tabela, variavel, classificacao = TABELAS_SIDRA[ano]
    url = (f"{API_SIDRA}/{tabela}/periodos/{ano}/variaveis/{variavel}"
           f"?localidades=N6[{preparar_dados.CODIGO_ORIXIMINA}]&classificacao={classificacao}")
    totais = dict.fromkeys(DESTINOS, 0)
    for resultado in baixar_json(url)[0]["resultados"]:
        categoria = [list(c["categoria"].values())[0] for c in resultado["classificacoes"]
                     if c["id"] == "67"][0]
        destino = CATEGORIAS_SIDRA.get(sem_acento(categoria))
        valor = list(resultado["series"][0]["serie"].values())[0]
        if destino and valor.isdigit():
            totais[destino] += int(valor)
    return pd.Series(totais)


def ler_setores_zip(arquivo, colunas):
    """Só as linhas de Oriximiná do arquivo do Brasil inteiro (lido de dentro do .zip, sem descompactar)."""
    with zipfile.ZipFile(arquivo) as pacote:
        nome = [n for n in pacote.namelist() if n.endswith(".csv")][0]
        with pacote.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1")
            cabecalho = texto.readline()
            linhas = [l for l in texto if l.lstrip('"').startswith(preparar_dados.CODIGO_ORIXIMINA)]
    df = pd.read_csv(io.StringIO(cabecalho + "".join(linhas)), sep=";", dtype=str)
    df = df.rename(columns={df.columns[0]: "CD_SETOR"})
    return df[["CD_SETOR"] + colunas]


def main():
    # 1) Município: 2022 no cartão e 2000/2010/2022 no histórico
    historico = pd.DataFrame({ano: destino_do_lixo_sidra(ano) for ano in TABELAS_SIDRA}).T
    municipio = historico.loc[2022]
    print(historico.to_string())
    pd.DataFrame({"Destino do lixo": municipio.index, "Casas": municipio.values}).to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_323.csv"), sep=";", index=False, encoding="utf-8")
    historico.rename_axis("Ano").reset_index().to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_323_historico.csv"), sep=";", index=False, encoding="utf-8")

    # 2) Setores: destino do lixo com o sigilo ("X") completado, como as idades no preparar_dados.py
    basico = pd.read_csv(preparar_dados.ARQ_BASICO, sep=";", dtype=str, encoding="latin-1",
                         usecols=["CD_SETOR", "SITUACAO", "CD_MUN", "v0007"])
    basico = basico[basico["CD_MUN"] == preparar_dados.CODIGO_ORIXIMINA]
    setores = basico.merge(ler_setores_zip(ARQ_DOMICILIO1, ["V00001"]), on="CD_SETOR", how="left")
    setores = setores.merge(ler_setores_zip(ARQ_DOMICILIO2, list(DESTINOS.values())), on="CD_SETOR", how="left")
    setores["SITUACAO"] = setores["SITUACAO"].fillna("Sem moradores")
    # Total de casas do setor (V00001); onde o IBGE escondeu, usa o total de ocupados do básico (v0007)
    setores["Habitantes"] = pd.to_numeric(setores["V00001"], errors="coerce").fillna(
        pd.to_numeric(setores["v0007"], errors="coerce")).fillna(0).astype(int)
    codigos = list(DESTINOS.values())
    setores[codigos] = setores[codigos].fillna("0")
    preparar_dados.FAIXAS_IBGE = dict.fromkeys(codigos, "")
    preparar_dados.ler_totais_oficiais = lambda: pd.Series({DESTINOS[d]: municipio[d] for d in DESTINOS})
    setores = preparar_dados.completar_sigilo(setores)

    for zona in ("Urbana", "Rural"):
        parte = setores[setores["SITUACAO"] == zona]
        com = parte[[DESTINOS[COLETA_CASA], DESTINOS[CACAMBA]]].sum().sum()
        print(f"{zona}: {com} de {parte['Habitantes'].sum()} casas com coleta")
    urbana = setores[setores["SITUACAO"] == "Urbana"]
    rural = setores[setores["SITUACAO"] == "Rural"]
    coleta_zona = {nome: parte[[DESTINOS[COLETA_CASA], DESTINOS[CACAMBA]]].sum().sum() / parte[codigos].sum().sum()
                   for nome, parte in (("urbana", urbana), ("rural", rural))}

    # 3) Bairros da sede: reparte as casas de cada setor pelos bairros (CNEFE)
    grupos = {COM_COLETA: [DESTINOS[COLETA_CASA], DESTINOS[CACAMBA]], QUEIMADO: [DESTINOS[QUEIMADO]],
              SEM_COLETA_OUTROS: [DESTINOS[d] for d in list(DESTINOS)[3:]]}
    for grupo, colunas in grupos.items():
        setores[grupo] = setores[colunas].sum(axis=1)
    preparar_dados.GRUPOS = grupos   # o distribuir_por_bairro reparte as colunas de GRUPOS
    bairros = preparar_dados.distribuir_por_bairro(setores)
    bairros = bairros[~bairros["nome"].isin(FORA_DOS_BAIRROS)].copy()
    bairros[SEM_COLETA_PCT] = (100 * (1 - bairros[COM_COLETA] / bairros["Habitantes"].replace(0, 1))).round(1)
    bairros = bairros.sort_values([SEM_COLETA_PCT, "Habitantes"], ascending=False)
    print(bairros.to_string(index=False))

    df = bairros.rename(columns={"nome": "Bairro"})
    df[["Bairro"] + list(grupos)].to_csv(os.path.join(PASTA_COMPONENTES, "comp_324.csv"),
                                         sep=";", index=False, encoding="utf-8")
    df[["Bairro", SEM_COLETA_PCT]].to_csv(os.path.join(PASTA_COMPONENTES, "comp_324_mapa.csv"),
                                         sep=";", index=False, encoding="utf-8")

    # 4) Componentes e painel no admin_painel.json
    def fmt(n):
        return f"{int(round(n)):,}".replace(",", ".")

    def pct(x):
        return f"{x:.0%}"
    total = municipio.sum()
    com_coleta = municipio[COLETA_CASA] + municipio[CACAMBA]
    total_2000 = historico.loc[2000].sum()
    com_2000 = historico.loc[2000, COLETA_CASA] + historico.loc[2000, CACAMBA]
    pior = bairros[bairros["Habitantes"] >= 200].iloc[0]
    casas_bairros = bairros["Habitantes"].sum()
    sem_bairros = casas_bairros - bairros[COM_COLETA].sum()
    links = [{"nome": "IBGE – SIDRA: Censo 2022, tabela 6892 (destino do lixo)",
              "url": "https://sidra.ibge.gov.br/tabela/6892"},
             {"nome": "IBGE – Censo 2022: agregados por setores censitários",
              "url": "https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html"}]
    componentes = {
        "comp_323": {
            "id": 323, "titulo": "Destino do lixo das casas", "fonte": "IBGE | Censos 2000, 2010 e 2022",
            "atualizacao": "Censo 2022", "icone": "delete", "area": "Município de Oriximiná",
            "resumo": "O que as casas de Oriximiná fazem com o lixo: coleta, caçamba, queimam, enterram...",
            "descricao": (
                f"Mostra o destino do lixo das {fmt(total)} casas de Oriximiná no Censo 2022. {fmt(com_coleta)} "
                f"casas ({pct(com_coleta / total)}) têm o lixo levado pelo serviço de limpeza, recolhido na porta "
                f"ou deixado numa caçamba. Nas outras, o lixo é sobretudo queimado no próprio terreno "
                f"({fmt(municipio[QUEIMADO])} casas, {pct(municipio[QUEIMADO] / total)}); poucas o enterram, "
                f"jogam em terreno ou área pública ou dão outro destino. Na zona urbana, "
                f"{pct(coleta_zona['urbana'])} das casas têm coleta; na zona rural, só "
                f"{pct(coleta_zona['rural'])}, porque o caminhão não chega às comunidades dos rios e da "
                f"floresta. Em 2000 eram {pct(com_2000 / total_2000)} das casas com coleta (veja o histórico). "
                "Em Taipei, este cartão mostra os pontos de parada do caminhão de lixo; Oriximiná não publica as "
                "rotas da coleta, então o cartão mostra quantas casas o serviço alcança."),
            "exemplo": ("Mostra o tamanho do desafio da coleta: onde o caminhão não chega, o lixo é queimado, o "
                        "que faz mal à saúde e ao meio ambiente. Ajuda a planejar a coleta nas comunidades e "
                        "pontos de entrega voluntária."),
            "tipos": ["rosca", "barras"],
            "cores": ["#56B96D", "#F49F36", "#9DC56E", "#a1887f", "#F65658", "#bdbdbd"],
            "unidade": "casas", "meta": None, "maximo": None, "links": links, "colaboradores": [],
            "mapa": None, "historico": {"tipo": "arquivo"},
        },
        "comp_324": {
            "id": 324, "titulo": "Coleta de lixo por bairro", "fonte": "IBGE | Censo 2022 e CNEFE 2022",
            "atualizacao": "Censo 2022", "icone": "delete", "area": "Sede urbana de Oriximiná",
            "resumo": "Em cada bairro da sede, quantas casas têm coleta de lixo e quantas queimam ou dão outro destino.",
            "descricao": (
                f"Mostra, em cada bairro da sede de Oriximiná, quantas casas têm o lixo recolhido pelo serviço de "
                f"limpeza (na porta ou em caçamba) e quantas queimam o lixo ou dão outro destino, segundo o Censo "
                f"2022. Nos bairros da sede, {fmt(sem_bairros)} das {fmt(casas_bairros)} casas "
                f"({pct(sem_bairros / casas_bairros)}) não têm coleta. Entre os bairros com mais de 200 casas, o "
                f"que tem a maior parte sem coleta é {pior['nome']} ({pior[SEM_COLETA_PCT]:.0f}% das casas). "
                "O mapa pinta os bairros conforme a parte das casas sem coleta. As casas de cada setor "
                "censitário foram repartidas entre os bairros conforme onde ficam os seus domicílios no CNEFE, "
                "como no cartão \"Moradores por bairro da sede\"; por isso os números por bairro são estimativas."),
            "exemplo": ("Mostra em que bairros a coleta precisa chegar ou passar mais vezes, e onde colocar "
                        "caçambas ou pontos de entrega de lixo."),
            "tipos": ["barras_percentuais", "barras"],
            "cores": ["#56B96D", "#F49F36", "#F65658"],
            "unidade": "casas", "meta": None, "maximo": None, "links": links, "colaboradores": [],
            "mapa": {"tipo": "bairros", "nome": "Casas sem coleta de lixo por bairro", "cor": "#F65658"},
            "historico": None,
        },
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {}).update(componentes)
    paineis = config.setdefault("paineis_publicos", {})
    painel = paineis.get("servindo")
    if painel is None:
        # Painel novo, logo depois do "Saúde" (antes dos painéis da Calha Norte)
        novo = {"titulo": "Servindo ao povo", "icone": "emoji_people", "cartoes": list(componentes),
                "grupo": "Painel de Oriximiná"}
        ordem = list(paineis.items())
        depois = [c for c, _ in ordem].index("saude") + 1 if "saude" in paineis else len(ordem)
        ordem.insert(depois, ("servindo", novo))
        config["paineis_publicos"] = dict(ordem)
        painel = novo
    else:
        painel["cartoes"] += [c for c in componentes if c not in painel["cartoes"]]
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painéis:", list(config["paineis_publicos"]), painel["cartoes"])


if __name__ == "__main__":
    main()
