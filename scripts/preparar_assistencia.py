"""Prepara o cartão "Assistência social para idosos" (no lugar dos "Centros de cuidados de longa permanência" e
do "Clube do Cabelo Prateado" do Taipei), no painel "Cuidados de longo prazo".

Fonte: Censo SUAS 2025, do Ministério do Desenvolvimento e Assistência Social (MDS), que todo ano pergunta a
cada unidade da assistência social o que ela faz. Em Oriximiná não há lar de idosos (ILPI), centro-dia nem
centro de convivência para idosos; o atendimento aos idosos é feito pelos CRAS (Centros de Referência de
Assistência Social), nos grupos do PAIF (Serviço de Proteção e Atendimento Integral à Família).

Baixe em https://aplicacoes.mds.gov.br/sagi/snas/vigilancia/index2.php ("Censo SUAS 2025") os arquivos
1_CRAS.zip, 4_UNIDADE_DE_ACOLHIMENTO.zip e 6_CENTRO_DIA.zip e salve em PASTA_FONTES/CensoSUAS2025 como
1.zip, 4.zip e 6.zip.

- comp_333.csv: idosos (homens e mulheres de 60 anos ou mais) que participam regularmente dos grupos do
  PAIF em cada CRAS
- comp_333_mapa.csv: onde fica cada CRAS, para o mapa e para a "Comparação de mapas"

Rode de novo para atualizar:  python preparar_assistencia.py
"""
import io
import json
import os
import re
import zipfile

import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
PASTA_SUAS = os.path.join(PASTA_FONTES, "CensoSUAS2025")
ANO = 2025
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
IBGE6 = "150530"   # o Censo SUAS usa o código do IBGE sem o último dígito
HOMENS, MULHERES = "Homens de 60 anos ou mais", "Mulheres de 60 anos ou mais"
NOMES_CRAS = {   # nome do Censo SUAS -> nome curto no cartão
    "CENTRO DE REFERÊNCIA EM ASSISTÊNCIA SOCIAL SÃO PEDRO": "CRAS São Pedro",
    "CRAS - CENTRO DE REFERÊNCIA DE ASSISTÊNCIA SOCIAL": "CRAS Cidade Nova",
    "CRAS RIBEIRINHO/EQUIPES VOLANTES": "CRAS Ribeirinho (equipes volantes)",
}


def ler_csv_do_zip(arquivo, final_do_nome):
    with zipfile.ZipFile(os.path.join(PASTA_SUAS, arquivo)) as pacote:
        nome = [n for n in pacote.namelist() if n.endswith(final_do_nome)][0]
        conteudo = pacote.read(nome)
    for codificacao in ("utf-8", "latin-1"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.StringIO(texto), sep=";", dtype=str, low_memory=False)


def coordenada(texto, digitos_inteiros):
    """O arquivo do MDS perdeu o ponto decimal das coordenadas ("-1.7538049290652E+16" é -1,7538...):
    junta os algarismos e põe a vírgula depois dos primeiros (1 na latitude, 2 na longitude de Oriximiná)."""
    algarismos = re.sub(r"\D", "", str(texto).split("E")[0])
    return -float(f"{algarismos[:digitos_inteiros]}.{algarismos[digitos_inteiros:]}")


def contar(texto):
    return int(texto) if str(texto).strip().isdigit() else 0


def main():
    cras = ler_csv_do_zip("1.zip", "CRAS_Dados_Gerais.csv")
    cras = cras[cras["IBGE"] == IBGE6].copy()
    acolhimento = ler_csv_do_zip("4.zip", "Unidade_Acolhimento_Dados_Gerais.csv")
    acolhimento = acolhimento[acolhimento["IBGE"] == IBGE6]
    idosos_acolhidos = acolhimento["q1_1"].str.contains("Idos", case=False, na=False).sum()
    print(f"{len(cras)} CRAS; unidades de acolhimento: {list(acolhimento['q1_1'])} (para idosos: {idosos_acolhidos})")

    cras["nome"] = cras["q0_1"].str.strip().map(NOMES_CRAS).fillna(cras["q0_1"].str.strip().str.title())
    cras[HOMENS] = cras["q13_1_4"].map(contar)
    cras[MULHERES] = cras["q13_2_4"].map(contar)
    cras = cras.sort_values(MULHERES, ascending=False)
    tabela = cras.rename(columns={"nome": "Unidade"})[["Unidade", MULHERES, HOMENS]]
    tabela.to_csv(os.path.join(PASTA_COMPONENTES, "comp_333.csv"), sep=";", index=False, encoding="utf-8")
    print(tabela.to_string(index=False))

    mapa = pd.DataFrame({
        "Unidade": cras["nome"],
        "Latitude": [round(coordenada(v, 1), 6) for v in cras["latitude"]],
        "Longitude": [round(coordenada(v, 2), 6) for v in cras["longitude"]],
        "Endereço": [f"{t} {r} {n} – {b}".title() for t, r, n, b in
                     zip(cras["q0_2"], cras["q0_3"], cras["q0_4"], cras["q0_6"])],
        "Idosos nos grupos": cras[HOMENS] + cras[MULHERES],
    })
    mapa.to_csv(os.path.join(PASTA_COMPONENTES, "comp_333_mapa.csv"), sep=";", index=False, encoding="utf-8")
    print(mapa.to_string(index=False))

    total = int(tabela[MULHERES].sum() + tabela[HOMENS].sum())
    rede_scfv = (cras["q29_6"].str.strip() == "Sim").sum()   # (o arquivo traz "Sim " com espaço)
    carteira = (cras["q12_19"].str.strip() == "Sim").sum()
    no_domicilio = (cras["q34"].str.strip() == "Sim").sum()
    componente = {
        "id": 333, "titulo": "Assistência social para idosos", "fonte": f"MDS | Censo SUAS {ANO}",
        "atualizacao": f"Censo SUAS {ANO}", "icone": "elderly", "area": "Município de Oriximiná",
        "resumo": "Quantos idosos participam dos grupos dos CRAS de Oriximiná, e onde ficam os CRAS.",
        "descricao": (
            f"Mostra quantas pessoas de 60 anos ou mais participam regularmente dos grupos do PAIF nos "
            f"{len(cras)} CRAS (Centros de Referência de Assistência Social) de Oriximiná, segundo o Censo "
            f"SUAS {ANO} do Ministério do Desenvolvimento e Assistência Social: {total} idosos, "
            f"{int(tabela[MULHERES].sum())} mulheres e {int(tabela[HOMENS].sum())} homens. O CRAS Ribeirinho, "
            "com as equipes volantes que atendem as comunidades ribeirinhas, é o que atende mais idosos. "
            f"Os {carteira} CRAS orientam e emitem a carteira da pessoa idosa, e {rede_scfv} deles têm, na rede "
            "de entidades ligadas a eles, grupos de convivência para idosos. Em Oriximiná não há lar de idosos "
            "(instituição de longa permanência), centro-dia nem centro de convivência só para idosos, que são "
            "o que os cartões do Taipei contam; a única unidade de acolhimento do município é para crianças e "
            + ("adolescentes. " if not idosos_acolhidos else "adolescentes, e há acolhimento para idosos. ")
            + ("Nenhum CRAS oferece o atendimento no domicílio para idosos e pessoas com deficiência. "
               if not no_domicilio else "")
            + "O mapa (e a Comparação de mapas) mostra onde fica cada CRAS."),
        "exemplo": ("Mostra quantos idosos a assistência social alcança e ajuda a planejar grupos de convivência, "
                    "o atendimento em casa para quem não pode sair e um centro-dia para os idosos que precisam "
                    "de cuidado durante o dia."),
        "tipos": ["barras", "rosca"],
        "cores": ["#c18ad8", "#24B0DD"],
        "unidade": "idosos", "meta": None, "maximo": None,
        "links": [{"nome": f"MDS – Censo SUAS {ANO} (vigilância socioassistencial)",
                   "url": "https://aplicacoes.mds.gov.br/sagi/snas/vigilancia/index2.php"}],
        "colaboradores": [], "mapa": {"tipo": "pontos", "nome": "CRAS (assistência social)", "cor": "#c18ad8"},
        "historico": None,
    }
    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_333"] = componente
    painel = config.get("paineis_publicos", {}).get("cuidados")
    if painel and "comp_333" not in painel["cartoes"]:
        painel["cartoes"].append("comp_333")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painel Cuidados de longo prazo:", painel["cartoes"] if painel else "—")


if __name__ == "__main__":
    main()
