"""Prepara o painel "Meio ambiente sustentável" e o cartão "Estações de qualidade da água" (como os "Pontos de
monitoramento da qualidade da água" do Taipei).

Fonte: o inventário de estações da ANA (Agência Nacional de Águas), pelo serviço público
http://telemetriaws1.ana.gov.br/ServiceANA.asmx (HidroInventario): as estações de Oriximiná que medem a
qualidade da água, com o rio, a posição e desde quando medem. Os resultados das análises (turbidez, oxigênio,
fósforo...) dessas estações só saem do HidroWeb com cadastro e senha (token); o serviço de mapas aberto de
indicadores de qualidade da ANA só tem as redes dos estados, e o Pará não aparece nele.

- comp_339.csv: há quantos anos cada estação mede a qualidade da água
- comp_339_mapa.csv: onde fica cada estação, para o mapa e para a "Comparação de mapas"

Rode de novo para atualizar:  python preparar_qualidade_agua.py
"""
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
URL = ("http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroInventario?codEstDE=&codEstATE=&tpEst=&nmEst="
       "&nmRio=&codSubBacia=&codBacia=&nmMunicipio={municipio}&nmEstado=&sgResp=&sgOper=&telemetrica=")
ANOS = "Anos medindo a qualidade da água"
RIOS = {"RIO CUMINA / EREPECURU / P.D'OESTE": "Rio Erepecuru (Cuminá)",   # nomes do inventário da ANA
        "RIO MAPUERA OU URUCURINA": "Rio Mapuera"}


def inventario():
    url = URL.format(municipio=urllib.parse.quote("ORIXIMINÁ"))
    for tentativa in range(5):   # o servidor da ANA às vezes corta a conexão
        try:
            with urllib.request.urlopen(url, timeout=180) as resposta:
                return ET.fromstring(resposta.read())
        except (OSError, ET.ParseError) as erro:
            print(f"ANA não respondeu ({erro}); tentando de novo...")
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError("O servidor da ANA não respondeu")


def nome_bonito(texto):
    texto = " ".join(str(texto).split()).title()
    for errado, certo in ((" Da ", " da "), (" Do ", " do "), (" De ", " de "), ("Cach ", "Cachoeira "),
                          (" Conj. 1", ""), (" Conjunto 1", ""), ("Rebio", "Rebio"), (" Ou ", " ou ")):
        texto = texto.replace(errado, certo)
    return texto


def main():
    hoje = pd.Timestamp.now()
    linhas = []
    for estacao in inventario().iter("Table"):
        def campo(nome):
            item = estacao.find(nome)
            return (item.text or "").strip() if item is not None and item.text else ""
        if campo("TipoEstacaoQualAgua") != "1" or campo("Operando") != "1":
            continue
        inicio = pd.to_datetime(campo("PeriodoQualAguaInicio"), errors="coerce")
        linhas.append({
            "Estação": nome_bonito(campo("Nome")), "Latitude": float(campo("Latitude")),
            "Longitude": float(campo("Longitude")), "Rio": RIOS.get(campo("RioNome"), nome_bonito(campo("RioNome"))),
            "Código ANA": campo("Codigo"), "Mede desde": int(inicio.year) if pd.notna(inicio) else None,
            "Responsável": campo("ResponsavelSigla"),
        })
    estacoes = pd.DataFrame(linhas).sort_values("Mede desde")
    estacoes[ANOS] = hoje.year - estacoes["Mede desde"]
    estacoes[["Estação", ANOS]].to_csv(os.path.join(PASTA_COMPONENTES, "comp_339.csv"), sep=";", index=False,
                                       encoding="utf-8")
    estacoes[["Estação", "Latitude", "Longitude", "Rio", "Mede desde", "Código ANA"]].to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_339_mapa.csv"), sep=";", index=False, encoding="utf-8")
    print(estacoes.to_string(index=False))

    rios = sorted(set(estacoes["Rio"]))
    mais_antiga = estacoes.iloc[0]
    componente = {
        "id": 339, "titulo": "Estações de qualidade da água", "fonte": "ANA | Inventário de estações",
        "atualizacao": "Inventário da ANA", "icone": "water_drop", "area": "Rios de Oriximiná",
        "resumo": "Onde a Agência Nacional de Águas mede a qualidade da água dos rios de Oriximiná, e desde quando.",
        "descricao": (
            f"Mostra as {len(estacoes)} estações da ANA (Agência Nacional de Águas) que medem a qualidade da "
            f"água dos rios de Oriximiná e estão funcionando: no {', no '.join(rios[:-1])} e no {rios[-1]}. "
            "Nelas, técnicos colhem amostras de água algumas vezes por ano para medir a turbidez (água barrenta), "
            "o oxigênio, a temperatura e outros indicadores. A mais antiga é a de "
            f"{mais_antiga['Estação']}, no {mais_antiga['Rio']}, que mede desde {int(mais_antiga['Mede desde'])}. "
            "O mapa (e a Comparação de mapas) mostra onde fica cada uma. Os resultados das análises não estão "
            "abertos: só saem do HidroWeb, o sistema da ANA, com cadastro e senha, e o serviço aberto de "
            "indicadores de qualidade da ANA só traz as redes dos estados (o Pará não aparece nele). Em Taipei, "
            "este cartão mostra os pontos de monitoramento da qualidade da água da cidade."),
        "exemplo": ("Mostra onde já se acompanha a água dos rios, perto das áreas protegidas, da mineração e das "
                    "comunidades, e onde faltaria acompanhar, como na frente da cidade."),
        "tipos": ["barras"],
        "cores": ["#24B0DD"],
        "unidade": "anos", "meta": None, "maximo": None,
        "links": [{"nome": "ANA – HidroWeb (séries históricas das estações)",
                   "url": "https://www.snirh.gov.br/hidroweb/serieshistoricas"},
                  {"nome": "ANA – Indicadores de qualidade de água (metadados)",
                   "url": "https://metadados.snirh.gov.br/geonetwork/srv/api/records/647706bb-bbad-4b99-8413-6b4f48697521"}],
        "colaboradores": [], "mapa": {"tipo": "pontos", "nome": "Estações de qualidade da água (ANA)", "cor": "#24B0DD"},
        "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_339"] = componente
    paineis = config.setdefault("paineis_publicos", {})
    if "ambiente" not in paineis:
        # Painel novo, logo depois do "Segurança e saúde alimentar" (antes dos da Calha Norte)
        novo = {"titulo": "Meio ambiente sustentável", "icone": "nature", "cartoes": ["comp_339"],
                "grupo": "Painel de Oriximiná"}
        ordem = list(paineis.items())
        chaves = [c for c, _ in ordem]
        depois = chaves.index("alimentar") + 1 if "alimentar" in chaves else len(ordem)
        ordem.insert(depois, ("ambiente", novo))
        config["paineis_publicos"] = paineis = dict(ordem)
    elif "comp_339" not in paineis["ambiente"]["cartoes"]:
        paineis["ambiente"]["cartoes"].insert(0, "comp_339")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painéis:", list(paineis), paineis["ambiente"]["cartoes"])


if __name__ == "__main__":
    main()
