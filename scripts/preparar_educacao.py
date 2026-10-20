"""Prepara o painel "Educação" de Oriximiná (o Taipei tem cartões de escolas, como o "Visão geral da promoção
sustentável do campus").

Oriximiná não publica um programa de reforma das escolas; os cartões usam o Censo Escolar do INEP, que tem a
infraestrutura de cada escola do país:

- comp_316.csv: em cada item (água potável, energia, esgoto, internet, biblioteca...), a porcentagem das escolas
  urbanas e das rurais que têm o item
- comp_317.csv: escolas e matrículas da cidade, dos assentamentos, dos quilombos, das terras indígenas e do
  resto da zona rural
- comp_318.csv: crianças que moram no município (Censo 2022 do IBGE, idade a idade) e matrículas na creche
  (0 a 3 anos) e na pré-escola (4 e 5 anos): que parte das crianças está na creche (como o "Recursos de apoio à
  creche" do Taipei)

Só entram as escolas em atividade. Os microdados (uns 35 MB) ficam na pasta das fontes, em INEP; o script usa o
ano mais novo que o INEP já publicou.

Rode de novo para atualizar:  python preparar_educacao.py
"""
import gzip
import io
import json
import os
import subprocess
import time
import urllib.request
import zipfile

import pandas as pd

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
PASTA_INEP = os.path.join(os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná"), "INEP")
URL_INEP = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{}.zip"
CODIGO_IBGE = "1505304"

# Itens do cartão (coluna do Censo Escolar: nome no cartão); "SEM_" quer dizer "não ter a coluna"
ITENS = {
    "IN_AGUA_POTAVEL": "Água potável",
    "SEM_IN_ENERGIA_INEXISTENTE": "Energia elétrica",
    "IN_ENERGIA_REDE_PUBLICA": "Energia da rede pública",
    "IN_ESGOTO_REDE_PUBLICA": "Esgoto da rede pública",
    "IN_LIXO_SERVICO_COLETA": "Coleta de lixo",
    "IN_BANHEIRO": "Banheiro",
    "IN_ALIMENTACAO": "Merenda escolar",
    "IN_INTERNET": "Internet",
    "IN_INTERNET_ALUNOS": "Internet para os alunos",
    "IN_BIBLIOTECA_SALA_LEITURA": "Biblioteca ou sala de leitura",
    "IN_LABORATORIO_INFORMATICA": "Laboratório de informática",
    "IN_LABORATORIO_CIENCIAS": "Laboratório de ciências",
    "IN_QUADRA_ESPORTES": "Quadra de esportes",
    "IN_ACESSIBILIDADE_RAMPAS": "Rampas de acessibilidade",
}
LOCAIS = {"1": "assentamentos", "2": "terras indígenas", "3": "quilombos"}   # TP_LOCALIZACAO_DIFERENCIADA
# Censo 2022, tabela 9514 (população por idade): menos de 1 ano, 1, 2, 3, 4 e 5 anos
URL_IDADES = ("https://apisidra.ibge.gov.br/values/t/9514/n6/{}/v/93/p/2022/c2/6794/"
              "c287/6557,6558,6559,6560,6561,6562/c286/113635")
META_CRECHE = 50   # Plano Nacional de Educação, meta 1: creche para pelo menos 50% das crianças de até 3 anos


def criancas_por_idade():
    """{idade: moradores} de 0 a 5 anos em Oriximiná, no Censo 2022."""
    req = urllib.request.Request(URL_IDADES.format(CODIGO_IBGE), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resposta:
        conteudo = resposta.read()
    if conteudo[:2] == bytes([0x1F, 0x8B]):   # às vezes vem compactado (gzip)
        conteudo = gzip.decompress(conteudo)
    linhas = json.loads(conteudo)[1:]   # a 1ª linha é o cabeçalho
    return {i: int(l["V"]) for i, l in enumerate(linhas)}


def microdados():
    """(ano, tabela das escolas de Oriximiná) do Censo Escolar mais novo já publicado."""
    os.makedirs(PASTA_INEP, exist_ok=True)
    for ano in range(int(time.strftime("%Y")), 2019, -1):
        caminho = os.path.join(PASTA_INEP, f"microdados_censo_escolar_{ano}.zip")
        if not os.path.exists(caminho):
            # O INEP publica o ano anterior lá por fevereiro: se ainda não saiu, o servidor responde 404
            resposta = subprocess.run(["curl", "-s", "-L", "-f", "--max-time", "900", "-A", "Mozilla/5.0",
                                       "-o", caminho, URL_INEP.format(ano)], check=False)
            if resposta.returncode != 0 or not zipfile.is_zipfile(caminho):
                if os.path.exists(caminho):
                    os.remove(caminho)
                continue
        with zipfile.ZipFile(caminho) as pacote:
            nome = next(n for n in pacote.namelist() if n.endswith(f"microdados_ed_basica_{ano}.csv"))
            df = pd.read_csv(io.BytesIO(pacote.read(nome)), sep=";", encoding="latin1", dtype=str, low_memory=False)
        return ano, df[df["CO_MUNICIPIO"] == CODIGO_IBGE]
    raise SystemExit("Não achei os microdados do Censo Escolar no site do INEP.")


def tem(escolas, coluna):
    if coluna.startswith("SEM_"):
        return escolas[coluna[4:]] != "1"
    return escolas[coluna] == "1"


def main():
    ano, todas = microdados()
    escolas = todas[todas["TP_SITUACAO_FUNCIONAMENTO"] == "1"].copy()   # em atividade
    urbanas, rurais = escolas[escolas["TP_LOCALIZACAO"] == "1"], escolas[escolas["TP_LOCALIZACAO"] == "2"]
    col_u, col_r = f"Escolas urbanas ({len(urbanas)})", f"Escolas rurais ({len(rurais)})"
    df_infra = pd.DataFrame([{"Item": nome, col_u: round(tem(urbanas, c).mean() * 100),
                              col_r: round(tem(rurais, c).mean() * 100)} for c, nome in ITENS.items()])
    df_infra.to_csv(os.path.join(PASTA_COMPONENTES, "comp_316.csv"), sep=";", index=False, encoding="utf-8")
    print(df_infra.to_string(index=False))

    escolas["matriculas"] = pd.to_numeric(escolas["QT_MAT_BAS"], errors="coerce").fillna(0).astype(int)

    def onde(e):
        if e["TP_LOCALIZACAO"] == "1":
            return "Cidade (zona urbana)"
        local = LOCAIS.get(e["TP_LOCALIZACAO_DIFERENCIADA"])
        return f"Rural em {local}" if local else "Rural (outras comunidades)"
    escolas["local"] = escolas.apply(onde, axis=1)
    ordem = ["Cidade (zona urbana)", "Rural em assentamentos", "Rural em quilombos", "Rural em terras indígenas",
             "Rural (outras comunidades)"]
    df_local = (escolas.groupby("local").agg(Escolas=("CO_ENTIDADE", "count"), Matrículas=("matriculas", "sum"))
                .reindex(ordem).dropna().astype(int).reset_index().rename(columns={"local": "Localização"}))
    df_local.to_csv(os.path.join(PASTA_COMPONENTES, "comp_317.csv"), sep=";", index=False, encoding="utf-8")

    # Creche e pré-escola: crianças do município (Censo 2022) e matrículas (Censo Escolar)
    idades = criancas_por_idade()
    for coluna in ("QT_MAT_INF_CRE", "QT_MAT_INF_PRE"):
        escolas[coluna] = pd.to_numeric(escolas[coluna], errors="coerce").fillna(0).astype(int)
    criancas_creche, criancas_pre = sum(idades[i] for i in range(4)), idades[4] + idades[5]
    mat_creche, mat_pre = int(escolas["QT_MAT_INF_CRE"].sum()), int(escolas["QT_MAT_INF_PRE"].sum())
    df_creche = pd.DataFrame({
        "Etapa": ["Creche (0 a 3 anos)", "Pré-escola (4 e 5 anos)"],
        "Crianças no município (Censo 2022)": [criancas_creche, criancas_pre],
        f"Matrículas ({ano})": [mat_creche, mat_pre],
    })
    df_creche.to_csv(os.path.join(PASTA_COMPONENTES, "comp_318.csv"), sep=";", index=False, encoding="utf-8")
    print(df_creche.to_string(index=False))
    com_creche = escolas[escolas["QT_MAT_INF_CRE"] > 0]
    creche_urbana = int(com_creche.loc[com_creche["TP_LOCALIZACAO"] == "1", "QT_MAT_INF_CRE"].sum())
    print(df_local.to_string(index=False))

    def n(cond):
        return int(cond.sum())
    sem_energia = n(~tem(escolas, "SEM_IN_ENERGIA_INEXISTENTE"))
    gerador = n(escolas["IN_ENERGIA_GERADOR_FOSSIL"] == "1")
    sem_internet = n(~tem(escolas, "IN_INTERNET"))
    redes = escolas["TP_DEPENDENCIA"].map({"1": "federais", "2": "estaduais", "3": "municipais", "4": "particulares"})
    contagem_redes = ", ".join(f"{q} {r}" for r, q in redes.value_counts().items())
    total_mat = int(escolas["matriculas"].sum())

    def fmt(v):
        return f"{v:,}".replace(",", ".")
    link = {"nome": f"INEP – Microdados do Censo Escolar {ano}",
            "url": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar"}
    componentes = {
        "comp_316": {
            "id": 316, "titulo": "Infraestrutura das escolas", "fonte": "INEP | Censo Escolar",
            "atualizacao": str(ano), "icone": "bar_chart", "area": "Município de Oriximiná",
            "resumo": "Quantas escolas urbanas e rurais de Oriximiná têm água, energia, esgoto, internet, biblioteca...",
            "descricao": (
                f"Mostra, para cada item, a porcentagem das {len(escolas)} escolas em atividade de Oriximiná que o têm, "
                f"separando as {len(urbanas)} urbanas das {len(rurais)} rurais, segundo o Censo Escolar {ano} (INEP), "
                f"respondido pelas próprias escolas. {sem_energia} escolas não têm energia elétrica, e {gerador} usam "
                f"gerador a combustível; {sem_internet} não têm internet. As escolas rurais, muitas ribeirinhas, "
                "quilombolas e em assentamentos, são as que mais esperam por água potável, energia, internet e "
                "espaços como biblioteca e quadra. \"Energia elétrica\" vale para qualquer fonte (rede, gerador ou "
                "placa solar); \"Energia da rede pública\" só para a rede."),
            "exemplo": ("Mostra onde investir primeiro: levar energia, água potável e internet às escolas rurais que "
                        "ainda não têm, e planejar bibliotecas, laboratórios e quadras."),
            "tipos": ["barras", "mapa_calor"],
            "cores": ["#24B0DD", "#56B96D"], "unidade": "% das escolas", "meta": None, "maximo": 100,
            "links": [link], "colaboradores": [], "mapa": None, "historico": None,
        },
        "comp_317": {
            "id": 317, "titulo": "Escolas e matrículas por localização", "fonte": "INEP | Censo Escolar",
            "atualizacao": str(ano), "icone": "donut_large", "area": "Município de Oriximiná",
            "resumo": "Escolas e alunos da cidade, dos assentamentos, dos quilombos, das terras indígenas e da zona rural.",
            "descricao": (
                f"Mostra onde ficam as {len(escolas)} escolas em atividade de Oriximiná ({contagem_redes}) e "
                f"quantos alunos estudam nelas ({fmt(total_mat)} matrículas na educação básica), segundo o Censo "
                f"Escolar {ano} (INEP): na cidade, nos assentamentos da reforma agrária, nos quilombos, nas terras "
                "indígenas e nas outras comunidades rurais. A maior parte das escolas é rural, mas a maior parte dos "
                "alunos estuda na cidade: as escolas do interior são pequenas e ficam longe umas das outras."),
            "exemplo": ("Ajuda a planejar o transporte escolar (muitas vezes por barco), a merenda e a contratação "
                        "de professores para as escolas do interior, inclusive as quilombolas e indígenas."),
            "tipos": ["rosca", "barras"],
            "cores": ["#24B0DD", "#F8CF58", "#c18ad8", "#F49F36", "#56B96D"], "unidade": "escolas",
            "meta": None, "maximo": None, "links": [link], "colaboradores": [], "mapa": None, "historico": None,
        },
        "comp_318": {
            "id": 318, "titulo": "Creches e pré-escolas", "fonte": "INEP | Censo Escolar e IBGE | Censo 2022",
            "atualizacao": str(ano), "icone": "bar_chart", "area": "Município de Oriximiná",
            "resumo": "Quantas crianças de 0 a 3 e de 4 e 5 anos moram em Oriximiná e quantas estão na creche e na pré-escola.",
            "descricao": (
                f"Compara as crianças que moram em Oriximiná (Censo 2022 do IBGE) com as matrículas na educação "
                f"infantil (Censo Escolar {ano} do INEP). Na creche são {fmt(mat_creche)} matrículas para "
                f"{fmt(criancas_creche)} crianças de 0 a 3 anos, cerca de {mat_creche / criancas_creche:.0%}; a meta do "
                f"Plano Nacional de Educação é atender pelo menos {META_CRECHE}% delas. São {len(com_creche)} escolas "
                f"com creche, {creche_urbana} das matrículas na cidade, e as do interior atendem poucas crianças cada. "
                f"Na pré-escola são {fmt(mat_pre)} matrículas para {fmt(criancas_pre)} crianças de 4 e 5 anos: a "
                "pré-escola está praticamente universalizada (também é meta do Plano). As matrículas podem passar do "
                "número de crianças porque incluem crianças fora da idade exata e porque o Censo da população é de "
                f"2022 e o das escolas, de {ano}. O cartão do Taipei soma vários serviços de apoio à creche; em "
                "Oriximiná, os dados públicos são os das creches das escolas."),
            "exemplo": ("Mostra onde faltam vagas: com poucas crianças de até 3 anos na creche, abrir vagas de creche "
                        "(sobretudo na cidade, onde mora a maior parte das famílias) é o que mais aproxima Oriximiná "
                        "da meta nacional."),
            "tipos": ["barras", "colunas"],
            "cores": ["#a0b8e8", "#F49F36"], "unidade": "crianças", "meta": None, "maximo": None,
            "links": [link, {"nome": "IBGE – SIDRA, Censo 2022, tabela 9514 (população por idade)",
                             "url": "https://sidra.ibge.gov.br/tabela/9514"}],
            "colaboradores": [], "mapa": None, "historico": None,
        },
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {}).update(componentes)
    paineis = config["paineis_publicos"]
    educacao = {"titulo": "Educação", "icone": "school", "cartoes": list(componentes), "grupo": "Painel de Oriximiná"}
    if "educacao" in paineis:
        cartoes = paineis["educacao"]["cartoes"]   # mantém a ordem escolhida
        cartoes += [c for c in componentes if c not in cartoes]
        paineis["educacao"] = {**educacao, "cartoes": cartoes}
    else:
        # No fim do grupo "Painel de Oriximiná" (antes dos painéis da Calha Norte)
        novos = {}
        for chave, painel in paineis.items():
            if painel["grupo"] != "Painel de Oriximiná" and "educacao" not in novos:
                novos["educacao"] = educacao
            novos[chave] = painel
        novos.setdefault("educacao", educacao)
        config["paineis_publicos"] = novos
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado: painel Educação com", ", ".join(educacao["cartoes"]))


if __name__ == "__main__":
    main()
