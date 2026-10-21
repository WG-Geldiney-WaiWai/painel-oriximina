"""Prepara o painel "Mudança climática" e o cartão "Emissões de gases de efeito estufa" (como o "Estatísticas
de emissões de gases de efeito estufa" do Taipei).

Fonte: SEEG (Sistema de Estimativas de Emissões e Remoções de Gases de Efeito Estufa), do Observatório do
Clima, versão 13.0: as emissões de cada município do Brasil por setor, de 1970 a 2024, em toneladas de CO2
equivalente (GWP-AR5). Baixe a planilha "Dados municipais resumido" em https://seeg.eco.br/dados e salve em
PASTA_FONTES/SEEG/seeg_municipios_13.xlsx (o site recusa downloads automáticos).

- comp_328.csv: emissões de Oriximiná no último ano, por setor (mil toneladas de CO2e)
- comp_328_historico.csv: as mesmas emissões de 2000 até o último ano

A planilha tem o Brasil inteiro (258 MB, leva uns 2 minutos para ler); as linhas de Oriximiná ficam
guardadas em SEEG/oriximina_seeg.csv e só são lidas de novo quando a planilha muda.

Rode de novo para atualizar:  python preparar_emissoes.py
"""
import csv
import json
import os

import openpyxl
import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

PASTA_FONTES = os.environ.get("PASTA_FONTES", r"C:\Users\Usuário\Downloads\Pasta Mapa de Painel Oriximiná")
ARQ_SEEG = os.path.join(PASTA_FONTES, "SEEG", "seeg_municipios_13.xlsx")
ARQ_ORIXIMINA = os.path.join(PASTA_FONTES, "SEEG", "oriximina_seeg.csv")
PASTA_COMPONENTES = "componentes"
ARQ_ADMIN = os.path.join("..", "usuarios", "admin_painel.json")
CODIGO_SEEG = "11505304"   # "1" + código do IBGE
PRIMEIRO_ANO_HISTORICO = 2000

USO_DA_TERRA = "Desmatamento e uso da terra"
AGROPECUARIA = "Agropecuária (gado e lavouras)"
INDUSTRIA = "Combustível na indústria"
TRANSPORTES = "Transportes"
OUTRA_ENERGIA = "Casas e outros usos de energia"
RESIDUOS = "Resíduos (lixo e esgoto)"
PROCESSOS = "Processos industriais"
ORDEM = [USO_DA_TERRA, AGROPECUARIA, INDUSTRIA, TRANSPORTES, OUTRA_ENERGIA, RESIDUOS, PROCESSOS]


def linhas_de_oriximina():
    """Linhas de Oriximiná da planilha do SEEG (guardadas num CSV pequeno enquanto a planilha não muda)."""
    if os.path.exists(ARQ_ORIXIMINA) and os.path.getmtime(ARQ_ORIXIMINA) >= os.path.getmtime(ARQ_SEEG):
        return pd.read_csv(ARQ_ORIXIMINA, sep=";", dtype={"ID Território": str})
    livro = openpyxl.load_workbook(ARQ_SEEG, read_only=True)
    linhas = livro["Dados"].iter_rows(values_only=True)
    cabecalho = next(linhas)
    territorio = cabecalho.index("ID Território")
    dados = [linha for linha in linhas if str(linha[territorio]) == CODIGO_SEEG]
    livro.close()
    with open(ARQ_ORIXIMINA, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(cabecalho)
        escritor.writerows(dados)
    return pd.read_csv(ARQ_ORIXIMINA, sep=";", dtype={"ID Território": str})


def setor_do_cartao(linha):
    setor, categoria = linha["Setor de emissão"], linha["Categoria emissora"]
    if setor == "Mudança de Uso da Terra e Floresta":
        return USO_DA_TERRA
    if setor == "Agropecuária":
        return AGROPECUARIA
    if setor == "Resíduos":
        return RESIDUOS
    if setor == "Processos Industriais":
        return PROCESSOS
    if categoria == "Industrial":
        return INDUSTRIA
    if categoria == "Transportes":
        return TRANSPORTES
    return OUTRA_ENERGIA


def main():
    dados = linhas_de_oriximina()
    anos = [c for c in dados.columns if str(c).isdigit()]
    ultimo = anos[-1]
    tipo = dados["Emissão/Remoção/Bunker"]
    # "Emissão NCI" (áreas protegidas e terras indígenas, fora do inventário oficial) fica à parte
    emissoes = dados[tipo == "Emissão"].copy()
    emissoes["setor"] = emissoes.apply(setor_do_cartao, axis=1)
    por_setor = emissoes.groupby("setor")[anos].sum().reindex(ORDEM, fill_value=0) / 1000   # mil toneladas
    remocoes = -dados[tipo.str.startswith("Remoção")][anos].sum() / 1000
    nci = dados[tipo == "Emissão NCI"][anos].sum() / 1000
    # Setor sem nenhuma emissão no período (ex.: processos industriais) não entra no cartão
    por_setor = por_setor[por_setor.loc[:, str(PRIMEIRO_ANO_HISTORICO):].sum(axis=1) > 0]
    # O SEEG só reparte a energia pelos municípios a partir de um certo ano (2006): o histórico começa nele,
    # para os anos de antes não parecerem sem emissão de combustível
    inicio = str(max(PRIMEIRO_ANO_HISTORICO, int(min(a for a in anos if por_setor.loc[INDUSTRIA, a] > 0))))

    cartao = por_setor[ultimo].round(1)
    pd.DataFrame({"Setor": cartao.index, "Emissões (mil toneladas de CO2e)": cartao.values}).to_csv(
        os.path.join(PASTA_COMPONENTES, "comp_328.csv"), sep=";", index=False, encoding="utf-8")
    historico = por_setor.loc[:, inicio:].T.round(1).rename_axis("Ano").reset_index()
    historico.to_csv(os.path.join(PASTA_COMPONENTES, "comp_328_historico.csv"), sep=";", index=False,
                     encoding="utf-8")
    total = cartao.sum()
    print(cartao.to_string())
    print(f"Total {ultimo}: {total:.0f} mil t; remoções {remocoes[ultimo]:.0f} mil t; NCI {nci[ultimo]:.0f} mil t")

    def mil(n):
        return f"{n:,.0f}".replace(",", ".")

    def milhoes(n):
        return f"{n / 1000:.1f}".replace(".", ",")
    pico = por_setor.loc[USO_DA_TERRA, inicio:].idxmax()
    componente = {
        "id": 328, "titulo": "Emissões de gases de efeito estufa", "fonte": "Observatório do Clima | SEEG 13.0",
        "atualizacao": f"{ultimo}", "icone": "factory", "area": "Município de Oriximiná",
        "resumo": "Quanto gás de efeito estufa Oriximiná emite por ano e de onde ele vem: desmatamento, gado, combustíveis...",
        "descricao": (
            f"Mostra as emissões de gases de efeito estufa de Oriximiná em {ultimo}, por setor, em mil toneladas "
            f"de CO2 equivalente, segundo o SEEG do Observatório do Clima. No total, o município emitiu cerca de "
            f"{milhoes(total)} milhões de toneladas. A maior parte vem do desmatamento e da mudança do uso da "
            f"terra ({cartao[USO_DA_TERRA] / total:.0%}), seguida da agropecuária, sobretudo o gado "
            f"({cartao.get(AGROPECUARIA, 0) / total:.0%}), e do combustível queimado na indústria, principalmente "
            "na mineração de Porto Trombetas. As florestas de Oriximiná, sobretudo as das áreas protegidas e "
            f"terras indígenas, absorvem muito mais: cerca de {milhoes(remocoes[ultimo])} milhões de toneladas por "
            f"ano, umas {remocoes[ultimo] / total:.0f} vezes o que o município emite. Essa absorção e as emissões "
            "dentro dessas áreas "
            f"(mais {mil(nci[ultimo])} mil toneladas) ficam fora das colunas, como no inventário oficial. O "
            f"histórico mostra cada setor desde {inicio}, quando o SEEG começa a calcular a energia por município; "
            f"o desmatamento teve o pico em {pico}."),
        "exemplo": ("Mostra onde agir para reduzir as emissões de Oriximiná: combater o desmatamento, melhorar o "
                    "manejo do gado e cuidar do lixo, e mostra o valor das florestas em pé."),
        "tipos": ["barras", "rosca"],
        "cores": ["#F65658", "#F49F36", "#c18ad8", "#24B0DD", "#F8CF58", "#a1887f", "#bdbdbd"][:len(cartao)],
        "unidade": "mil t CO2e", "meta": None, "maximo": None,
        "links": [{"nome": "SEEG – Observatório do Clima (dados)", "url": "https://seeg.eco.br/dados"},
                  {"nome": "Plataforma SEEG – municípios", "url": "https://plataforma.seeg.eco.br"}],
        "colaboradores": [], "mapa": None, "historico": {"tipo": "arquivo"},
    }

    config = json.load(open(ARQ_ADMIN, encoding="utf-8"))
    config.setdefault("componentes_novos", {})["comp_328"] = componente
    paineis = config.setdefault("paineis_publicos", {})
    if "clima" not in paineis:
        # Painel novo, logo depois do "Servindo ao povo" (antes dos painéis da Calha Norte)
        novo = {"titulo": "Mudança climática", "icone": "eco", "cartoes": ["comp_328"],
                "grupo": "Painel de Oriximiná"}
        ordem = list(paineis.items())
        chaves = [c for c, _ in ordem]
        depois = chaves.index("servindo") + 1 if "servindo" in chaves else len(ordem)
        ordem.insert(depois, ("clima", novo))
        config["paineis_publicos"] = paineis = dict(ordem)
    elif "comp_328" not in paineis["clima"]["cartoes"]:
        paineis["clima"]["cartoes"].insert(0, "comp_328")
    with open(ARQ_ADMIN, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    print("admin_painel.json atualizado; painéis:", list(paineis), paineis["clima"]["cartoes"])


if __name__ == "__main__":
    main()
