"""Prepara o cartão "Obras públicas com recursos federais" de Oriximiná (como o "Informações de construção
atuais" do painel de Taipei).

Oriximiná não publica em tempo real as obras abertas nas ruas (o Taipei publica as licenças de escavação);
o cartão usa o Obrasgov.br, o cadastro do governo federal das obras feitas com dinheiro federal:

- comp_305.csv: obras de Oriximiná por área e situação (concluída, em execução, aguardando início...)

O cartão entra como componente da administração (usuarios/admin_painel.json), no painel "Tráfego
rodoviário", logo depois dos cartões da frota. A API entrega as obras do Pará aos poucos (de 100 em 100):
a leitura leva uns 10 minutos.

Rode de novo para atualizar:  python preparar_obras.py
"""
import collections
import gzip
import json
import os
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

PASTA_PROJETO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASTA_COMPONENTES = os.path.join(PASTA_PROJETO, "dados", "componentes")
ARQ_ADMIN = os.path.join(PASTA_PROJETO, "usuarios", "admin_painel.json")
URL_OBRAS = "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?uf=PA&pagina={}&tamanhoDaPagina=100"

# Situações do Obrasgov com o nome mostrado no cartão, na ordem das colunas
SITUACOES = {
    "Concluída": "Concluídas",
    "Em execução": "Em execução",
    "Cadastrada": "Aguardando início",
    "Paralisada": "Paralisadas ou inacabadas",
    "Inacabada": "Paralisadas ou inacabadas",
    "Inativada": "Canceladas ou inativadas",
}
# Nomes mais curtos para as áreas (os "tipos" do Obrasgov)
AREAS = {
    "Infraestrutura Hídrica, Portos, Hidrovia": "Portos, hidrovias e água",
    "Infraestrutura Urbana e Mobilidade": "Ruas e mobilidade urbana",
}


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def pagina(numero):
    """Uma página de obras do Pará (tenta de novo se a API demorar ou falhar)."""
    req = urllib.request.Request(URL_OBRAS.format(numero), headers={"User-Agent": "Mozilla/5.0"})
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as resposta:
                conteudo = resposta.read()
            if conteudo[:2] == bytes([0x1F, 0x8B]):   # às vezes vem compactado (gzip)
                conteudo = gzip.decompress(conteudo)
            return json.loads(conteudo).get("content", [])
        except Exception:
            time.sleep(5 * (tentativa + 1))
    raise RuntimeError(f"A página {numero} do Obrasgov não respondeu")


def obras_de_oriximina():
    """Lê todas as obras do Pará, 6 páginas por vez, e fica com as que citam Oriximiná."""
    achadas, inicio = [], 0
    with ThreadPoolExecutor(6) as executor:
        while True:
            paginas = list(executor.map(pagina, range(inicio, inicio + 12)))
            for itens in paginas:
                achadas += [o for o in itens if "oriximina" in sem_acento(json.dumps(o, ensure_ascii=False))]
            print(f"páginas até {inicio + 11}: {len(achadas)} obras de Oriximiná", flush=True)
            if any(not itens for itens in paginas):
                return achadas
            inicio += 12


def main():
    obras = obras_de_oriximina()
    contagem = collections.Counter()
    for obra in obras:
        tipos = [t.get("descricao") for t in (obra.get("tipos") or []) if t.get("descricao")]
        area = AREAS.get(tipos[0], tipos[0]) if tipos else "Outras"
        contagem[(area, SITUACOES.get(obra.get("situacao"), obra.get("situacao") or "Sem situação"))] += 1
    areas = sorted({a for a, _ in contagem}, key=lambda a: -sum(n for (x, _), n in contagem.items() if x == a))
    colunas = [s for s in dict.fromkeys(SITUACOES.values()) if any(s == c for _, c in contagem)]
    colunas += sorted({c for _, c in contagem} - set(colunas))
    df = pd.DataFrame([{"Área": a, **{c: contagem[(a, c)] for c in colunas}} for a in areas])
    df.to_csv(os.path.join(PASTA_COMPONENTES, "comp_305.csv"), sep=";", index=False, encoding="utf-8")
    print(df.to_string(index=False))

    total = len(obras)
    por_situacao = {c: int(df[c].sum()) for c in colunas}
    resumo = "; ".join(f"{n} {c.lower()}" for c, n in por_situacao.items())
    componente = {
        "id": 305, "titulo": "Obras públicas com recursos federais", "fonte": "Governo Federal | Obrasgov.br",
        "atualizacao": time.strftime("%m/%Y"), "icone": "bar_chart", "area": "Município de Oriximiná",
        "resumo": "Obras em Oriximiná feitas com dinheiro federal, por área e situação.",
        "descricao": (
            f"Mostra as {total} obras de Oriximiná cadastradas no Obrasgov.br, o cadastro do governo federal das "
            f"obras feitas com recursos federais (como as do PAC), separadas por área e situação: {resumo}. "
            "\"Aguardando início\" são obras cadastradas que ainda não começaram. As obras pagas só pela "
            "Prefeitura ou pelo Estado não estão aqui; elas ficam no Geo-Obras do TCM-PA e no Portal da "
            "Transparência da Prefeitura. Diferente do cartão de Taipei, não mostra as obras abertas nas ruas "
            "em tempo real: Oriximiná não publica esse tipo de licença."),
        "exemplo": ("Ajuda a acompanhar o andamento das obras com dinheiro federal na cidade: quais já foram "
                    "entregues, quais estão em execução e quais estão paradas ou ainda não começaram, para "
                    "cobrar prazos e planejar a fiscalização."),
        "tipos": ["barras", "barras_percentuais"],
        "cores": ["#56B96D", "#24B0DD", "#F8CF58", "#F65658", "#a0b8e8", "#c18ad8"],
        "unidade": "obras", "meta": None, "maximo": None,
        "links": [{"nome": "Obrasgov.br – Obras do Governo Federal", "url": "https://obrasgov.gestao.gov.br"}],
        "colaboradores": [], "mapa": None, "historico": None,
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_305"] = componente
    trafego = config.get("paineis_publicos", {}).get("trafego")
    if trafego and "comp_305" not in trafego["cartoes"]:
        # Logo depois dos cartões da frota (comp_301 e comp_302)
        depois = max((trafego["cartoes"].index(c) for c in ("comp_301", "comp_302") if c in trafego["cartoes"]),
                     default=len(trafego["cartoes"]) - 1)
        trafego["cartoes"].insert(depois + 1, "comp_305")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado:", total, "obras;",
          "painel Tráfego rodoviário:", trafego["cartoes"] if trafego else "não encontrado (rode preparar_trafego.py)")


if __name__ == "__main__":
    main()
