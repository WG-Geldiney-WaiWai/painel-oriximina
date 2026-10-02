import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
import math
import base64
from functools import partial
import hashlib
import html
import os
import secrets
import re
import shutil
import smtplib
import subprocess
import sys
import time
import unicodedata
from email.message import EmailMessage

import shapely.geometry

# Pastas do projeto (igual à organização do painel de Taipei)
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(PASTA_PROJETO, "dados")
PASTA_IMAGENS = os.path.join(PASTA_PROJETO, "imagens")
PASTA_USUARIOS = os.path.join(PASTA_PROJETO, "usuarios")
os.makedirs(PASTA_USUARIOS, exist_ok=True)


def arquivo_dados(nome):
    return os.path.join(PASTA_DADOS, nome)

def e_celular():
    """Celular ou tablet, pelo navegador (User-Agent), como o isMobileDevice do Taipei. No celular o menu
    lateral vira o botão ☰ da barra de cima e as camadas do mapa ficam num botão "Camadas"."""
    agente = st.context.headers.get("User-Agent", "") or ""
    return any(marca in agente for marca in ("Mobi", "Android", "iPhone", "iPad"))


CELULAR = e_celular()

# 1. Configura a página para modo painel (Tela cheia)
st.set_page_config(
    page_title="Painel Oriximiná",
    layout="wide",
    initial_sidebar_state="collapsed" if CELULAR else "expanded"
)

# Cores do cartão do painel de Taipei
COR_FUNDO = "#090909"
COR_CARTAO = "#282a2c"
COR_TEXTO_CINZA = "#9a9a9a"
# Escala de uma cor só: mais escuro = menos gente, mais claro = mais gente
ESCALA_AZUL = ["#1d6585", "#2386b0", "#28a6d6", "#2ec4f2"]
COR_INDICADOR_NOME = "#F65658"    # cores do aging_kpi no Taipei
COR_INDICADOR_VALOR = "#F49F36"
# Mesmas cores e ordem do Taipei: azul (crianças), verde (adultos), amarelo (idosos)
CORES_IDADES = {
    "0 a 14 anos": "#24B0DD",
    "15 a 59 anos": "#56B96D",
    "60 anos ou mais": "#F8CF58"
}

st.markdown(f"""
    <style>
    [data-testid="stApp"] {{ background-color: {COR_FUNDO}; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    [class*="st-key-cartao_"] {{
        background-color: {COR_CARTAO};
        border-radius: 6px;
        border: none !important;
        padding: 18px 20px 10px 20px;
    }}
    .cartao-titulo {{ font-size: 1.3rem !important; font-weight: 700; color: #ffffff; line-height: 1.25; }}
    .cartao-fonte {{ font-size: 0.85rem !important; color: {COR_TEXTO_CINZA}; line-height: 1.3; margin-top: 4px; }}
    /* Botões cinza de alternar mapa/colunas, como no Taipei */
    [class*="st-key-tipo_grafico"] button {{
        background-color: #3a3c3e !important; color: #8a8a8a !important;
        border: none !important; margin: 0 !important; border-radius: 5px !important;
    }}
    /* Compactos, lado a lado numa linha só e no meio do cartão (sem quebrar em duas linhas) */
    [class*="st-key-tipo_grafico"] {{ align-self: center; max-width: 100%; }}
    [class*="st-key-tipo_grafico"] [role="radiogroup"] {{ flex-wrap: nowrap !important; gap: 4px !important; }}
    [class*="st-key-tipo_grafico"] button {{
        flex: 0 1 auto; min-width: 0; min-height: 0 !important; padding: 3px 7px !important;
    }}
    [class*="st-key-tipo_grafico"] button p {{
        font-size: 0.88rem !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    [class*="st-key-tipo_grafico"] button > div, [class*="st-key-tipo_grafico"] button span {{ min-width: 0; overflow: hidden; }}
    [class*="st-key-tipo_grafico"] button[kind*="Active"], [class*="st-key-tipo_grafico"] button[aria-checked="true"] {{
        background-color: #5b5d60 !important; color: #ffffff !important;
    }}
    [class*="st-key-tipo_grafico"] button p {{ color: inherit !important; }}
    /* Coração grande e cinza */
    [class*="st-key-botao_favorito"] button p {{ font-size: 2rem !important; color: #8a8a8a; line-height: 1; }}
    /* "Informações do componente" em azul */
    [class*="st-key-info_componente"] button p {{
        color: #4a9eff !important; white-space: nowrap; overflow: visible !important; text-overflow: clip !important;
    }}
    /* Círculo azul com seta depois do texto, como no Taipei (também no "Página de informações" do catálogo) */
    [class*="st-key-info_componente"] button p::after, [class*="st-key-catalogo_info_"] button p::after {{
        /* A seta é desenhada como imagem (SVG) para ficar exatamente no meio do círculo */
        content: ""; display: inline-block; width: 18px; height: 18px; margin-left: 8px;
        border-radius: 50%; vertical-align: middle; position: relative; top: -1px;
        background: #4a9eff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M3.5 8h8M8 4.5 11.5 8 8 11.5' fill='none' stroke='%23282a2c' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / 12px 12px no-repeat;
    }}
    /* Descrição do componente: texto cinza justificado, título em branco */
    [class*="st-key-texto_descricao"] p, [class*="st-key-texto_descricao"] li {{
        color: {COR_TEXTO_CINZA}; text-align: justify; font-size: 0.95rem;
    }}
    [class*="st-key-texto_descricao"] strong {{ color: #ffffff; }}
    /* Títulos alinhados à esquerda, sem os espaços grandes do texto justificado */
    [class*="st-key-texto_descricao"] p:has(> strong:only-child) {{ text-align: left; }}
    /* Linha vertical separando o gráfico da descrição */
    [class*="st-key-lado_descricao"] {{ border-left: 1px solid #4a4c4f; padding-left: 20px; }}
    /* "Dados relacionados": aviso numa caixa de cantos arredondados */
    .caixa-aviso {{
        border: 1px solid #8a8a8a; border-radius: 10px; padding: 10px 14px; margin: 4px 0 12px 0;
        color: {COR_TEXTO_CINZA}; font-size: 0.95rem; line-height: 1.5;
    }}
    .texto-cinza {{ color: {COR_TEXTO_CINZA}; font-size: 0.95rem; margin-bottom: 10px; }}
    .texto-cinza.pequeno {{ font-size: 0.8rem; }}
    a.link-dados {{ color: #4a9eff !important; text-decoration: none; }}
    a.link-dados:hover {{ text-decoration: underline; }}
    .titulo-colaboradores {{ color: #ffffff; font-weight: 700; margin: 6px 0 6px 0; }}
    .logo-colaborador {{
        width: 34px; height: 34px; border-radius: 50%; object-fit: cover; object-position: top;
        border: 1px solid #4a4c4f;
    }}
    /* Botões azuis Reportar / Baixar / Incorporar */
    [class*="st-key-acoes_info"] button {{
        background-color: #4a9eff !important; color: #ffffff !important;
        border: none !important; border-radius: 5px !important;
    }}
    [class*="st-key-acoes_info"] button p {{ color: #ffffff !important; font-size: 1.05rem; }}
    [class*="st-key-acoes_info"] button:focus, [class*="st-key-acoes_info"] button:focus-visible,
    [class*="st-key-acoes_info"] button:active {{
        outline: none !important; box-shadow: none !important; transform: none !important;
        background-color: #4a9eff !important;
    }}
    /* Janelas abrem e fecham direto, sem zoom nem desbotamento (ao trocar a janela de informações
       pela de Reportar / Baixar / Incorporar, a tela não "se espalha") */
    .stDialog, .stDialog > div, .stDialog div:has(> [role="dialog"]), [role="dialog"] {{
        animation: none !important; transition: none !important;
    }}
    [role="dialog"] [data-stale="true"], .stDialog [data-stale="true"] {{
        opacity: 1 !important; transition: none !important;
    }}
    /* "Informações do componente" já abre com a altura final (a dos cartões fica entre 570 e 630 px):
       sem isso ela abria baixa e crescia enquanto o gráfico carregava, e a tela parecia pular */
    [role="dialog"]:has(.st-key-conteudo_janela_info) {{ min-height: min(630px, calc(100vh - 100px)); }}
    /* Reportar / Baixar / Incorporar dentro de "Informações do componente": a janela fica estreita */
    /* Reportar / Baixar / Incorporar por cima de "Informações do componente": fundo escuro na tela toda
       e a caixa no meio, como a janela pequena do Streamlit */
    .st-key-acao_na_janela_info {{
        position: fixed !important; inset: 0; z-index: 1000; width: 100vw !important; height: 100vh;
        background: rgba(0, 0, 0, 0.55); display: flex !important; align-items: center; justify-content: center;
    }}
    /* (o Streamlit põe uma caixa em volta da caixa: ela precisa encolher e ir para o meio) */
    .st-key-acao_na_janela_info > div {{ width: auto !important; flex: 0 0 auto !important; margin: auto !important; }}
    .st-key-caixa_acao_info {{
        width: min(460px, calc(100vw - 32px)) !important; max-height: calc(100vh - 48px); overflow-y: auto;
        background: {COR_CARTAO}; border: 1px solid #494b4e; border-radius: 8px; padding: 24px 24px 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    }}
    .st-key-caixa_acao_info {{ position: relative; }}
    .st-key-fechar_acao_info {{ position: absolute !important; top: 14px; right: 16px; width: auto !important; z-index: 1; }}
    .st-key-fechar_acao_info button p {{ color: #ffffff !important; font-size: 1.1rem; }}
    .titulo-acao-info {{ font-size: 1.5rem; font-weight: 700; color: #ffffff; margin: 0 0 4px 0; }}
    /* Janela "Baixar dados", no estilo do Taipei */
    .stDialog div:has(> [role="dialog"]) {{
        background-color: {COR_CARTAO} !important; max-width: 400px; border: 1px solid #494b4e;
    }}
    [role="dialog"] [data-testid="stWidgetLabel"] p {{ color: {COR_TEXTO_CINZA} !important; font-weight: 400; }}
    [role="dialog"] [data-testid$="RootElement"] {{ background-color: #1e1f21; }}
    /* Opção marcada em branco, as outras em cinza */
    [role="dialog"] [role="radiogroup"] label:has(input:checked) p {{ color: #ffffff !important; }}
    .st-key-cancelar_baixar button p, .st-key-cancelar_reportar button p {{ color: #ffffff !important; }}
    .st-key-confirmar_reportar button,
    .st-key-confirmar_baixar button {{
        background-color: #4a9eff !important; color: #ffffff !important;
        border: none !important; border-radius: 5px !important;
    }}
    /* Coração de favoritar: cinza; o dos favoritos fica vermelho (regra montada no fim da página) */
    [class*="st-key-botao_favorito_"] button p, [class*="st-key-catalogo_favorito_"] button p {{
        color: #8a8a8a !important; font-size: 1.9rem !important; line-height: 1;
    }}
    [class*="st-key-botao_favorito_"] button:hover p, [class*="st-key-catalogo_favorito_"] button:hover p {{
        opacity: 0.8;
    }}
    /* Ao clicar, o coração não se espalha: sem brilho/contorno de foco, sem efeito de apertar,
       sem animação e sem o esmaecimento do Streamlit enquanto a página recarrega */
    [class*="st-key-botao_favorito_"] button, [class*="st-key-catalogo_favorito_"] button,
    [class*="st-key-botao_favorito_"] button:focus, [class*="st-key-catalogo_favorito_"] button:focus,
    [class*="st-key-botao_favorito_"] button:focus-visible, [class*="st-key-catalogo_favorito_"] button:focus-visible,
    [class*="st-key-botao_favorito_"] button:active, [class*="st-key-catalogo_favorito_"] button:active {{
        outline: none !important; box-shadow: none !important; background: transparent !important;
        transform: none !important; transition: none !important; filter: none !important;
    }}
    [class*="st-key-botao_favorito_"] button *, [class*="st-key-catalogo_favorito_"] button * {{
        transition: none !important; text-shadow: none !important; filter: none !important; transform: none !important;
    }}
    [class*="st-key-botao_favorito_"], [class*="st-key-catalogo_favorito_"],
    [data-stale="true"] [class*="st-key-botao_favorito_"], [data-stale="true"] [class*="st-key-catalogo_favorito_"] {{
        opacity: 1 !important; transition: none !important; filter: none !important;
    }}
    /* Aviso no alto da tela, como a notificação do Taipei: fundo escuro, ícone e texto verde-claro */
    [data-testid="stToastContainer"] {{
        top: 28px !important; bottom: auto !important; left: 50% !important; right: auto !important;
        transform: translateX(-50%); z-index: 1000000 !important;
        /* Partindo do meio da tela, a caixa só tinha metade da largura: no celular o texto quebrava
           uma palavra por linha. Agora ela usa a largura do texto, até a tela menos as margens */
        width: max-content !important; max-width: min(560px, calc(100vw - 32px)) !important;
    }}
    /* No celular: a caixa ocupa a largura da tela, com 16px de margem dos dois lados */
    @media (max-width: 640px) {{
        [data-testid="stToastContainer"] {{
            left: 16px !important; right: 16px !important; transform: none !important;
            width: auto !important; max-width: none !important;
        }}
        [data-testid="stToast"] {{ width: 100% !important; max-width: none !important; }}
    }}
    [data-testid="stToast"] {{ background-color: #3a3b3d !important; border-radius: 6px; width: auto !important; }}
    [data-testid="stToast"] p {{ color: #b4f33e !important; font-size: 1rem; }}
    /* O Streamlit corta o aviso em 3 linhas medindo com a letra menor dele: com a letra maior do painel,
       aparecia "view more" mesmo com o texto inteiro. Os avisos são curtos: mostra tudo, sem o botão */
    [data-testid="stToastText"] {{
        display: block !important; -webkit-line-clamp: unset !important; overflow: visible !important;
    }}
    [data-testid="stToastViewButton"] {{ display: none !important; }}
    [data-testid="stToast"] [data-testid="stIconMaterial"] {{ color: #b4f33e !important; }}
    .cartao-atualizacao {{
        display: inline-block; font-size: 0.8rem; color: {COR_TEXTO_CINZA};
        border: 1px solid {COR_TEXTO_CINZA}; border-radius: 4px; padding: 1px 6px;
    }}
    .legenda-total {{ color: #d0d0d0; font-size: 0.95rem; line-height: 1.3; }}
    .legenda-barra {{
        display: inline-block; width: 54px; height: 20px; border-radius: 3px; vertical-align: middle;
        margin: 0 6px; background: linear-gradient(90deg, {ESCALA_AZUL[-1]}, {ESCALA_AZUL[0]});
    }}
    /* Grade com os cartões lado a lado, todos da mesma altura, como no Taipei: cabem quantos
       cartões a largura permitir (com zoom menor, mais cartões por linha) */
    .st-key-grade_cartoes {{
        /* min(400px, 100%): numa tela menor que 400px (celular) o cartão ocupa a largura toda sem sobrar */
        display: grid !important; grid-template-columns: repeat(auto-fit, minmax(min(400px, 100%), 1fr));
        gap: 1rem !important; align-items: stretch;
    }}
    /* O Streamlit põe uma caixa (stLayoutWrapper) em volta de cada contêiner; ela também precisa esticar
       para o cartão ocupar a altura toda e o "Informações do componente" ficar no pé do cartão */
    .st-key-grade_cartoes > div {{ display: flex; flex-direction: column; width: auto !important; min-width: 0; }}
    /* Painel com poucos cartões (ex.: um só): o cartão fica do tamanho normal, sem esticar na tela toda */
    .st-key-grade_cartoes > div {{ max-width: 620px; }}
    /* Janela "Informações do componente": gráfico e descrição lado a lado, como no Taipei */
    .stDialog div:has(> [role="dialog"]):has([class*="st-key-janela_grafico_"]) {{ max-width: 980px; }}
    [class*="st-key-celula_"], [class*="st-key-celula_"] [class*="st-key-cartao_"] {{ flex: 1; }}
    [class*="st-key-celula_"] > div:has(> [class*="st-key-cartao_"]),
    [class*="st-key-cartao_"] > div:has(> [class*="st-key-grafico_"]) {{
        flex: 1; display: flex; flex-direction: column;
    }}
    [class*="st-key-cartao_"] {{ height: 100%; min-height: 690px; }}
    [class*="st-key-grafico_"] {{ flex: 1; }}
    [class*="st-key-grafico_"] > div:last-child {{ margin-top: auto; }}
    /* Indicadores de cuidados de longo prazo: 4 quadros separados por uma cruz fina */
    .grade-indicadores {{
        display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
        height: 420px; margin-top: 10px;
    }}
    .indicador {{ display: flex; align-items: center; justify-content: center; padding: 10px 14px; }}
    .indicador:nth-child(1), .indicador:nth-child(3) {{ border-right: 1px solid #55575a; }}
    .indicador:nth-child(1), .indicador:nth-child(2) {{ border-bottom: 1px solid #55575a; }}
    .indicador-nome {{ color: {COR_INDICADOR_NOME}; font-size: 1.25rem; line-height: 1.25; }}
    .indicador-valor {{ color: {COR_INDICADOR_VALOR}; font-size: 2rem; text-align: center; line-height: 1.4; }}
    .indicador-valor span {{ font-size: 1.2rem; }}
    /* --- ESTRUTURA DO SITE (barra de cima e menu lateral do Taipei) --- */
    /* Esconde só o "Deploy" e o menu ⋮ do Streamlit; o botão de reabrir o menu lateral fica
       dentro da mesma barra de ferramentas e não pode sumir junto */
    [data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
    [data-testid="stDecoration"] {{ display: none !important; }}
    header[data-testid="stHeader"] {{ top: 60px; height: 0; background: transparent; pointer-events: none; }}
    /* A barra de ferramentas invisível do Streamlit (dentro do cabeçalho) cobria a faixa logo abaixo da barra
       de cima e "pegava" os cliques (ex.: "Voltar ao painel"); só os botões de verdade recebem clique */
    header[data-testid="stHeader"] * {{ pointer-events: none; }}
    header[data-testid="stHeader"] button {{ pointer-events: auto; }}
    /* Menu recolhido: botão » sempre visível à esquerda, logo abaixo da barra de cima, como no Taipei */
    [data-testid="stExpandSidebarButton"] {{
        position: fixed !important; top: 70px; left: 10px; z-index: 999991;
        width: 36px !important; height: 36px !important; display: flex !important;
        align-items: center; justify-content: center; visibility: visible !important;
        background-color: {COR_CARTAO} !important; border: 1px solid #494b4e !important; border-radius: 6px;
        color: #ffffff !important; pointer-events: auto;
    }}
    [data-testid="stSidebarCollapseButton"] {{ visibility: visible !important; }}
    /* Embaixo, espaço para rolar o conteúdo para fora de trás do robozinho fixo no canto */
    .stMainBlockContainer {{ padding-top: 76px !important; padding-bottom: 130px !important; }}
    /* Elementos que não aparecem (estilos, scripts e a barra de cima, que fica presa no topo) não somam o
       espaço de 16px entre blocos: assim o título do painel fica logo abaixo da barra, como no Taipei */
    .stMainBlockContainer > div > .stElementContainer:has(> .stMarkdown style):not(:has(p, span, img, a, li, table)),
    .stMainBlockContainer > div > :has(> .st-key-barra_topo),
    .stMainBlockContainer > div > :has(> .st-key-scripts_pagina),
    .stMainBlockContainer > div > :has(> .st-key-estilo_favoritos) {{ margin-bottom: -16px; }}
    .st-key-barra_topo {{
        position: fixed; top: 0; left: 0; right: 0; height: 60px; z-index: 999990;
        background-color: {COR_CARTAO}; border-bottom: 1px solid #494b4e; padding: 0 16px;
        flex-wrap: nowrap !important;
    }}
    .topo-logo, .topo-logo:hover {{ display: flex; align-items: center; gap: 12px; text-decoration: none !important;
                                    color: inherit !important; cursor: pointer; }}
    .topo-logo img {{ width: 45px; height: 45px; object-fit: contain; border-radius: 50%; }}
    .topo-titulo, .topo-subtitulo {{ display: block; }}
    .topo-titulo {{ font-size: 1.25rem; font-weight: 500; color: #ffffff; line-height: 1.2; }}
    .topo-subtitulo {{ font-size: 0.85rem; color: #ffffff; line-height: 1.2; }}
    .st-key-abas_topo button {{
        height: 59px; border-radius: 0 !important; border-bottom: 3px solid transparent !important;
        padding: 0 6px !important;
    }}
    .st-key-abas_topo button p {{ color: #ffffff; font-size: 1rem; }}
    .st-key-abas_topo button:hover {{ opacity: 0.8; }}
    .st-key-usuario_topo button {{ background: transparent !important; border: none !important; }}
    .st-key-tela_cheia button [data-testid="stIconMaterial"] {{ font-size: 1.5rem; }}
    /* Quadro invisível com o script da tela cheia: não ocupa espaço na página */
    .st-key-scripts_pagina, .st-key-estilo_favoritos {{ position: absolute; width: 0; height: 0; overflow: hidden; }}
    .st-key-usuario_topo button p, .st-key-usuario_topo button span {{ color: #ffffff !important; }}
    section[data-testid="stSidebar"] {{
        top: 60px; height: calc(100vh - 60px) !important; background-color: {COR_FUNDO};
        border-right: 1px solid #494b4e; width: 280px !important; min-width: 280px !important;
    }}
    /* Menu lateral como o do Taipei: sem faixa vazia em cima (o « fica na linha de "Painel privado"),
       margens pequenas, itens juntos, letras grandes e texto alinhado à esquerda */
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        height: 0; padding: 0; position: absolute; top: 34px; right: 10px; z-index: 5;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding: 0 !important; }}
    /* Barra de rolagem do menu sempre visível, com as setas ▲ ▼ do navegador, como no Taipei */
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
        overflow-y: scroll !important; scrollbar-width: auto !important; scrollbar-color: auto !important;
        color-scheme: dark;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar {{ width: 10px; }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-track {{
        background: #0b0b0b;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {{
        background: #4a4b4e; border-radius: 5px; border: 2px solid #0b0b0b;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-thumb:hover {{ background: #6a6b6e; }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-button:single-button {{
        display: block; height: 12px; background-color: #0b0b0b; background-repeat: no-repeat;
        background-position: center; background-size: 8px 6px;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-button:single-button:vertical:decrement {{
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 6'><path d='M4 0 8 6H0z' fill='%239a9a9a'/></svg>");
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-button:single-button:vertical:increment {{
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 6'><path d='M0 0h8L4 6z' fill='%239a9a9a'/></svg>");
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding: 10px 10px 24px 14px !important; }}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 2px; }}
    /* O Streamlit põe -16px embaixo de todo texto; no menu isso fazia o item de baixo cobrir o nome do grupo */
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button span {{ font-size: 1.6rem; }}
    .menu-titulo {{ color: #ffffff; font-size: 1.45rem; font-weight: 700; margin: 8px 0 0 0; }}
    .menu-grupo {{ color: #9a9a9a; font-size: 1.15rem; margin: 4px 0 0 20px; }}
    [class*="st-key-aba_menu_"] button, [class*="st-key-celular_"] button {{
        justify-content: flex-start !important; border-left: 4px solid transparent !important;
        border-radius: 0 5px 5px 0 !important; padding: 6px 10px 6px 16px !important; min-height: 0 !important;
    }}
    [class*="st-key-aba_menu_"] button:hover, [class*="st-key-celular_"] button:hover {{ background-color: {COR_CARTAO} !important; }}
    [class*="st-key-aba_menu_"], [class*="st-key-aba_menu_"] .stButton, [class*="st-key-celular_"], [class*="st-key-celular_"] .stButton,
    [class*="st-key-aba_menu_"] button, [class*="st-key-celular_"] button {{ width: 100% !important; }}
    [class*="st-key-aba_menu_"] button div, [class*="st-key-aba_menu_"] button [data-testid="stMarkdownContainer"], [class*="st-key-celular_"] button div, [class*="st-key-celular_"] button [data-testid="stMarkdownContainer"] {{
        justify-content: flex-start !important; text-align: left !important;
    }}
    [class*="st-key-aba_menu_"] button p, [class*="st-key-celular_"] button p {{
        color: #ffffff; font-size: 1.25rem; text-align: left; white-space: normal; line-height: 1.25;
    }}
    [class*="st-key-aba_menu_"] button [data-testid="stIconMaterial"], [class*="st-key-celular_"] button [data-testid="stIconMaterial"] {{
        color: #ffffff; font-size: 1.5rem; width: 1.5rem; flex: 0 0 auto; margin-right: 10px;
    }}
    /* Coração de "Componentes favoritos" preenchido de branco, como no Taipei */
    /* (a fonte de ícones do Streamlit não tem o coração cheio, então o ícone é trocado pelo caractere ♥) */
    .st-key-aba_menu_favoritos button [data-testid="stIconMaterial"] {{
        font-size: 0 !important; display: inline-flex; align-items: center; justify-content: center;
    }}
    .st-key-aba_menu_favoritos button [data-testid="stIconMaterial"]::before {{
        content: "\\2665"; font-family: "Segoe UI Symbol", "DejaVu Sans", sans-serif; font-size: 2rem;
        color: #ffffff; line-height: 1;
    }}
    .icone-material {{
        font-family: "Material Symbols Rounded"; font-size: 1.6rem; vertical-align: middle;
        margin-right: 8px; font-weight: normal; line-height: 1;
    }}
    .titulo-painel {{ color: #ffffff; font-size: 1.35rem; font-weight: 700; margin: 0 0 6px 0; }}
    .aviso-vazio {{
        color: #888787; border: 1px dashed #494b4e; border-radius: 6px; padding: 24px; text-align: center;
    }}
    /* Página de mapa: camadas em cartõezinhos à esquerda, mapa à direita */
    [class*="st-key-camada_"] {{ background-color: {COR_CARTAO}; border-radius: 6px; padding: 12px 14px; }}
    .camada-titulo {{ color: #ffffff; font-weight: 700; font-size: 1rem; line-height: 1.3; }}
    .legenda-ponto {{
        display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px;
        vertical-align: middle;
    }}
    .st-key-caixa_mapa {{ border-radius: 6px; overflow: hidden; position: relative; }}
    /* Título do grupo "Camadas básicas" na lista de camadas do mapa */
    .camadas-basicas-titulo {{ color: {COR_TEXTO_CINZA}; font-size: 0.95rem; font-weight: 600; margin-top: 10px;
                               border-top: 1px solid #494b4e; padding-top: 10px; }}
    /* Ferramentas do mapa: barra de botões, campo escondido da posição, resultado e janelinha do clique */
    .st-key-barra_mapa {{ flex-wrap: wrap; }}
    .st-key-vista_atual_mapa, .st-key-marco_temporario, .st-key-minha_localizacao {{
        position: absolute !important; width: 1px !important; height: 1px !important;
        overflow: hidden; opacity: 0; pointer-events: none; }}
    .st-key-scripts_mapa {{ position: absolute; width: 0; height: 0; overflow: hidden; }}
    .st-key-script_fechar_menu {{ position: absolute !important; width: 1px !important; height: 1px !important;
        overflow: hidden; opacity: 0; pointer-events: none; }}
    /* Sem a dica em inglês "Press Enter to apply" nos campos de entrar e cadastrar */
    .st-key-novo_nome [data-testid="InputInstructions"], .st-key-login_email [data-testid="InputInstructions"],
    .st-key-login_senha [data-testid="InputInstructions"] {{ display: none !important; }}
    .st-key-script_login {{ position: absolute !important; width: 1px !important; height: 1px !important;
        overflow: hidden; opacity: 0; pointer-events: none; }}
    /* Prédios em 3D: balão ao passar o mouse e aviso da fonte da altura */
    #balao-predio {{
        position: fixed; display: none; z-index: 1000; pointer-events: none; max-width: 260px;
        background: #1e1f21; border: 1px solid #555555; border-radius: 4px; padding: 6px 9px;
        color: #ffffff; font-size: 14px; line-height: 1.35; font-family: "Source Sans Pro", sans-serif;
    }}
    #balao-predio span {{ color: #b0b0b0; font-size: 12.5px; }}
    .aviso-predios {{ color: #b0b0b0; font-size: 0.85rem; line-height: 1.35; }}
    .aviso-predios .icone-material {{ font-size: 1rem; vertical-align: -3px; margin-right: 4px; }}
    .resultado-proximo {{ color: #d0d0d0; font-size: 0.95rem; }}
    .resultado-proximo .icone-material {{ font-size: 1.2rem; color: #5a9cf8; margin-right: 6px; }}
    .st-key-popup_mapa {{
        position: absolute; top: 12px; right: 12px; z-index: 5; width: 320px; max-width: calc(100% - 24px);
        background-color: {COR_CARTAO}; border: 1px solid #494b4e; border-radius: 6px; padding: 12px 14px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5); gap: 6px;
    }}
    .st-key-popup_mapa [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    .popup-titulo {{ color: #ffffff; font-weight: 700; font-size: 1.05rem; line-height: 1.25; }}
    .popup-camada {{ color: {COR_TEXTO_CINZA}; font-size: 0.8rem; }}
    .popup-linha {{ color: #e0e0e0; font-size: 0.9rem; line-height: 1.4; }}
    .popup-linha span {{ color: {COR_TEXTO_CINZA}; margin-right: 6px; }}
    .st-key-popup_mapa button p {{ font-size: 0.85rem; }}
    /* Título e × na mesma linha; resultado do "Ponto mais próximo" e "Limpar" também */
    .st-key-popup_topo, .st-key-resultado_proximo_caixa {{ flex-wrap: nowrap !important; }}
    .st-key-popup_topo > div:first-child, .st-key-resultado_proximo_caixa > div:first-child {{
        flex: 1 1 auto !important; min-width: 0; }}
    .st-key-popup_topo > div:last-child, .st-key-resultado_proximo_caixa > div:last-child {{
        flex: 0 0 auto !important; width: auto !important; }}
    /* Catálogo de componentes: cartõezinhos de resumo, como os do Taipei */
    .st-key-grade_catalogo {{ max-width: 1560px; margin: 0 auto; }}
    .st-key-grade_catalogo [data-testid="stColumn"] > div {{ height: 100%; }}
    [class*="st-key-catalogo_item_"] {{
        height: 100%; background-color: {COR_CARTAO}; border-radius: 6px; padding: 16px 20px; gap: 8px;
    }}
    .catalogo-titulo {{ color: #ffffff; font-size: 1.45rem; font-weight: 700; line-height: 1.25; }}
    .catalogo-descricao {{ color: #ffffff; font-size: 0.95rem; line-height: 1.35; }}
    .catalogo-fonte {{ color: {COR_TEXTO_CINZA}; font-size: 0.85rem; }}
    .catalogo-etiquetas {{ border: 1px dashed #6a6c6f; border-radius: 5px; padding: 4px 6px; }}
    .catalogo-etiqueta {{
        display: inline-block; color: #ffffff; font-size: 0.85rem; border-radius: 3px; padding: 0 4px;
        margin-right: 4px;
    }}
    .catalogo-index {{ color: {COR_TEXTO_CINZA}; font-size: 0.85rem; margin-top: 2px; }}
    .catalogo-icone {{
        font-family: "Material Symbols Rounded"; font-size: 2.6rem; line-height: 1; color: #1e1f21;
        background: #d0d0d0; border-radius: 6px; padding: 4px;
    }}
    .catalogo-filtro {{
        color: {COR_TEXTO_CINZA}; font-size: 0.85rem; border: 1px solid #6a6c6f; border-radius: 4px;
        padding: 2px 6px;
    }}
    [class*="st-key-catalogo_info_"] button p, [class*="st-key-catalogo_info_"] button span {{
        color: #5a9cf8 !important;
    }}
    [class*="st-key-catalogo_controles_"] button {{ padding: 0 2px !important; min-height: 0 !important; }}
    /* Formulário "Adicionar painel" à esquerda, separado dos cartões por uma linha */
    .st-key-lateral_catalogo {{ border-right: 1px solid #494b4e; padding-right: 18px; min-height: 80vh; }}
    .st-key-lateral_catalogo [data-testid="stWidgetLabel"] p {{ color: {COR_TEXTO_CINZA} !important; }}
    .st-key-cat_lista {{ border: 1px solid #6a6c6f; border-radius: 5px; }}
    .st-key-cat_salvar button, .st-key-pesquisar_catalogo button {{
        background-color: #5a9cf8 !important; border: none !important; border-radius: 5px !important;
    }}
    .st-key-cat_salvar button p {{ color: #ffffff !important; }}
    .st-key-pesquisar_catalogo button {{
        background-color: #5a9cf8 !important; border: none !important; border-radius: 5px !important;
    }}
    .st-key-pesquisar_catalogo button p {{ color: #ffffff !important; }}
    /* Janela "Adicionar/Editar painel": larga, com dois quadros, como no Taipei */
    .stDialog div:has(> [role="dialog"]):has(.st-key-pp_quadro_dados) {{ max-width: 760px; }}
    .stDialog div:has(> [role="dialog"]):has(.st-key-pp_escolha) {{ max-width: 860px; }}
    .escolha-titulo {{ color: #ffffff; font-size: 1.3rem; font-weight: 700; }}
    .escolha-contagem {{ color: #ffffff; font-size: 0.9rem; }}
    .st-key-pp_confirmar_escolha button {{
        background-color: #5a9cf8 !important; border: none !important; border-radius: 5px !important;
    }}
    .st-key-pp_confirmar_escolha button p, .st-key-pp_confirmar_escolha button span {{ color: #ffffff !important; }}
    .st-key-pp_cancelar_escolha button p {{ color: #ffffff !important; }}
    [class*="st-key-pp_resumo_"] {{
        position: relative; height: 100%; min-height: 230px; border: 1px solid #55575a; border-radius: 5px;
        padding: 14px 18px; background-color: {COR_CARTAO};
    }}
    [class*="st-key-pp_resumo_"]:hover {{ border-color: #8a8c8f; }}
    /* Botão invisível esticado por cima do cartão inteiro (ele e tudo o que o envolve) */
    [class*="st-key-pp_escolher_"] {{
        position: absolute !important; inset: 0; z-index: 2; width: 100% !important; height: 100% !important;
    }}
    [class*="st-key-pp_escolher_"] div, [class*="st-key-pp_escolher_"] button {{
        width: 100% !important; height: 100% !important;
    }}
    [class*="st-key-pp_escolher_"] button {{ opacity: 0; cursor: pointer; }}
    .resumo-topo {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
    .resumo-topo .catalogo-titulo {{ font-size: 1.25rem; }}
    .resumo-rodape {{
        display: flex; justify-content: space-between; align-items: flex-end; gap: 10px; margin: 6px 0;
    }}
    /* "Confirmar adição" na linha do título, no lugar do X (como no Taipei; fecha com Esc ou clicando fora) */
    .st-key-controles_painel_pessoal {{ margin-top: -62px; margin-right: 0; width: auto !important; }}
    [role="dialog"]:has(.st-key-controles_painel_pessoal) button[aria-label="Close"] {{ display: none; }}
    .st-key-confirmar_painel_pessoal button {{
        background-color: #5a9cf8 !important; border: none !important; border-radius: 5px !important;
    }}
    .st-key-confirmar_painel_pessoal button p {{ color: #ffffff !important; }}
    [class*="st-key-pp_quadro_"] {{ border-color: #55575a !important; }}
    /* Quadradinhos cinza dos componentes do painel, lado a lado com o "+" */
    .st-key-pp_lista_componentes {{ flex-wrap: wrap; justify-content: flex-start !important; gap: 8px !important; }}
    .st-key-pp_lista_componentes > * {{ flex: 0 0 auto !important; width: auto !important; }}
    [class*="st-key-pp_item_"] {{
        position: relative; flex: 0 0 auto; width: 92px !important; height: 54px;
        background-color: #8a8a8a; border-radius: 5px; padding: 4px 6px;
    }}
    .pp-item-id {{ color: #ffffff; font-size: 0.95rem; line-height: 1.3; }}
    .pp-item-titulo {{
        color: #ffffff; font-size: 0.85rem; line-height: 1.3;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    [class*="st-key-pp_tirar_"] {{ position: absolute !important; top: 1px; right: 3px; width: auto !important; }}
    /* Arrastar para mudar a ordem: mãozinha, quadradinho arrastado apagado e uma barra azul onde vai cair */
    .st-key-pp_lista_componentes [class*="st-key-pp_item_"] {{ cursor: grab; }}
    .pp-arrastando {{ opacity: 0.4; }}
    .pp-soltar-antes {{ box-shadow: -4px 0 0 0 #4a9eff; }}
    .pp-soltar-depois {{ box-shadow: 4px 0 0 0 #4a9eff; }}
    .st-key-pp_ordem, .st-key-pp_script_arrastar {{
        position: absolute !important; width: 1px !important; height: 1px !important;
        overflow: hidden; opacity: 0; pointer-events: none; }}
    /* Setinhas ‹ ›: só em tela de toque, embaixo à direita do quadradinho */
    [class*="st-key-pp_setas_"] {{ display: none !important; }}
    @media (hover: none) {{
        [class*="st-key-pp_setas_"] {{ display: flex !important; position: absolute !important; bottom: 0;
            right: 2px; width: auto !important; }}
        [class*="st-key-pp_setas_"] button {{ padding: 0 !important; min-height: 0 !important; }}
        [class*="st-key-pp_setas_"] button span {{ color: #ffffff !important; font-size: 1.1rem; }}
        .pp-item-titulo {{ max-width: 44px; }}
    }}
    [class*="st-key-pp_tirar_"] button {{ padding: 0 !important; min-height: 0 !important; }}
    [class*="st-key-pp_tirar_"] button span {{ color: #ffffff !important; font-size: 1rem; }}
    .st-key-pp_adicionar button {{
        width: 96px; height: 54px; background: transparent !important;
        border: 2px dashed #6a6c6f !important; border-radius: 5px !important;
    }}
    .st-key-pp_adicionar button span {{ color: #b0b0b0 !important; font-size: 1.6rem; }}
    .st-key-pp_adicionar button [data-testid="stIconMaterial"]:last-child:not(:first-child) {{ display: none; }}
    /* Janela de login, igual à do Taipei */
    /* O logo sobe por cima do cabeçalho da janela; sem pointer-events ele não bloqueia o X de fechar */
    .login-logo {{ display: flex; align-items: center; gap: 14px; margin: -28px 0 10px 0; pointer-events: none; }}
    .login-logo img {{ width: 50px; height: 50px; object-fit: contain; }}
    .login-titulo {{ font-size: 1.5rem; color: #ffffff; line-height: 1.2; }}
    .login-subtitulo {{ font-size: 0.9rem; color: #ffffff; }}
    .st-key-confirmar_login button {{
        width: 200px; background-color: #03b2c3 !important; border: none !important;
        border-radius: 100px !important; padding: 6px 0 !important; margin-top: 10px;
    }}
    .st-key-confirmar_login button p {{ color: #ffffff !important; font-size: 1.2rem; }}
    .st-key-confirmar_login button:hover {{ opacity: 0.85; }}
    .st-key-alternar_login button p {{ color: #5a9cf8 !important; font-size: 0.85rem; }}
    .login-texto {{ color: #888787; font-size: 0.9rem; text-align: center; margin-top: 8px; line-height: 1.5; }}
    .login-texto a {{ color: #5a9cf8 !important; text-decoration: none; }}
    .login-erro {{ color: #e5484d; font-size: 0.9rem; text-align: center; }}
    /* Esqueci a senha: link pequeno à direita, títulos e avisos da recuperação */
    /* "Esqueci a senha" logo abaixo do campo da senha (tira os espaços do script escondido entre os dois) */
    :has(> .st-key-esqueci_linha) {{ margin-top: -30px; }}
    .st-key-esqueci_linha button {{ min-height: 0 !important; padding: 2px 0 !important; }}
    .st-key-esqueci_senha button p, .st-key-rec_reenviar button p, .st-key-rec_voltar button p {{
        color: #5a9cf8 !important; font-size: 0.85rem; }}
    .login-aviso {{ color: #56B96D; font-size: 0.9rem; text-align: center; }}
    .login-rec-titulo {{ color: #ffffff; font-size: 1.15rem; font-weight: 700; margin-top: 4px; }}
    .login-rec-texto {{ color: #b0b0b0; font-size: 0.9rem; line-height: 1.45; }}
    .st-key-rec_enviar button, .st-key-rec_trocar button {{
        width: 200px; background-color: #03b2c3 !important; border: none !important; border-radius: 24px !important;
        min-height: 44px; }}
    .st-key-rec_enviar button p, .st-key-rec_trocar button p {{ color: #ffffff !important; font-size: 1.1rem; }}
    .st-key-rec_codigo [data-testid="InputInstructions"], .st-key-rec_email [data-testid="InputInstructions"],
    .st-key-rec_senha [data-testid="InputInstructions"], .st-key-rec_senha2 [data-testid="InputInstructions"] {{
        display: none !important; }}
    /* Cartão de informações cartográficas (legenda do mapa, como o MapLegend do Taipei) */
    [class*="st-key-cartao_vias"] {{ min-height: 0 !important; }}
    .lista-legenda {{ margin: 36px 0 30px 6px; }}
    .legenda-via {{ color: #ffffff; font-size: 1.1rem; margin: 10px 0; display: flex; align-items: center; }}
    .linha-via {{ display: inline-block; width: 22px; height: 8px; border-radius: 4px; margin-right: 12px; }}
    [class*="st-key-botoes_mapa_vias"] button {{
        background: transparent !important; border: 1px solid #5b5d60 !important; border-radius: 5px !important;
        padding: 2px 10px !important; min-height: 0 !important;
    }}
    [class*="st-key-botoes_mapa_vias"] button p, [class*="st-key-botoes_mapa_vias"] button span {{ color: #8a8a8a !important; }}
    [class*="st-key-botoes_mapa_vias"] {{ position: absolute; bottom: 14px; left: 20px; width: auto !important; z-index: 2; }}
    [class*="st-key-cartao_vias"] {{ position: relative; }}
    /* Painel pessoal no menu lateral: título, botão azul "Adicionar" e "Nenhum painel pessoal" */
    .st-key-linha_painel_pessoal {{ gap: 6px; margin-top: 4px; flex-wrap: nowrap !important; }}
    .st-key-linha_painel_pessoal > div {{ width: auto !important; flex: 0 0 auto !important; }}
    .st-key-linha_painel_pessoal .menu-grupo {{ margin: 0 0 0 20px; }}
    .st-key-adicionar_painel button {{
        background-color: #5a9cf8 !important; border: none !important; border-radius: 5px !important;
        padding: 0 6px !important; min-height: 28px !important; gap: 4px !important;
    }}
    .st-key-adicionar_painel button p, .st-key-adicionar_painel button span {{ color: #ffffff !important; }}
    .st-key-adicionar_painel button p {{ font-size: 0.9rem !important; }}
    .menu-vazio {{ color: #ffffff; font-style: italic; font-size: 0.9rem; margin: 2px 0 6px 20px; }}
    /* Linha fina sob o título do painel, separando-o dos cartões (como no Taipei) */
    .st-key-linha_titulo_painel {{
        border-bottom: 1px solid #494b4e; padding-bottom: 14px !important; margin-bottom: 10px !important;
    }}
    .st-key-linha_titulo_painel .titulo-painel {{ margin: 0; }}
    .st-key-editar_painel button p, .st-key-editar_painel button span {{ color: #888787 !important; }}
    /* Engrenagem cheia e cinza antes de "Configurações", como no Taipei (a fonte de ícones do Streamlit
       só tem a engrenagem vazada, então ela é desenhada aqui como imagem SVG) */
    .st-key-editar_painel button p::before {{
        content: ""; display: inline-block; width: 24px; height: 24px; margin-right: 6px; vertical-align: middle;
        position: relative; top: -1px;
        background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='%23888787' d='M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84a.47.47 0 0 0-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87a.47.47 0 0 0 .12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z'/%3E%3C/svg%3E") center / contain no-repeat;
    }}
    /* Sem a margem negativa do Streamlit no texto, o título e a engrenagem ficam na mesma altura */
    .st-key-linha_titulo_painel [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    /* Robozinho do assistente, fixo no canto de baixo à direita, como no Taipei */
    .st-key-robo {{ position: fixed; right: 28px; bottom: 40px; z-index: 999; width: auto !important; }}
    .st-key-robo [data-testid="stPopover"] button {{
        width: 72px; height: 72px; border-radius: 50% !important; padding: 0 !important;
        background-color: #d9d9d9 !important; border: 3px solid #9fc7f0 !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }}
    /* A caixa do ícone precisa ter o tamanho do desenho (senão ele "vaza" para o lado e fica fora do meio) */
    .st-key-robo [data-testid="stPopover"] button > div {{ margin: 0 !important; }}
    .st-key-robo [data-testid="stPopover"] button [data-testid="stIconMaterial"] {{
        font-size: 2.6rem; width: 2.6rem; height: 2.6rem; line-height: 1; color: #282a2c;
        display: flex; align-items: center; justify-content: center;
    }}
    /* Esconde a setinha de "abrir" do botão, para o robozinho ficar no meio do círculo */
    .st-key-robo [data-testid="stPopover"] button div[aria-hidden="true"] {{ display: none; }}
    .st-key-robo_minimizar button {{ min-height: 0 !important; padding: 0 4px !important; }}
    .st-key-robo_minimizar button p {{ color: #ffffff !important; font-size: 1.4rem; font-weight: 700; line-height: 1; }}
    /* Recolhido: só uma abinha com o robozinho na borda direita */
    .st-key-robo_recolhido {{ position: fixed; right: 0; bottom: 40px; z-index: 999; width: auto !important; }}
    .st-key-robo_recolhido button {{
        border-radius: 8px 0 0 8px !important; background-color: #d9d9d9 !important; border: none !important;
        padding: 6px 8px !important;
    }}
    .st-key-robo_recolhido button [data-testid="stIconMaterial"] {{ color: #282a2c; font-size: 1.6rem; }}
    [data-testid="stPopoverBody"]:has(.st-key-robo_conversa) {{ width: 360px; max-height: 75vh; }}
    .robo-titulo {{ color: #ffffff; font-weight: 700; font-size: 1.05rem; }}
    .robo-pergunta {{ color: {COR_TEXTO_CINZA}; font-size: 0.85rem; font-style: italic; }}
    .st-key-robo_conversa [data-testid="stButton"] button p {{ font-size: 0.9rem; text-align: left; }}
    /* "Próxima atualização: 9:25", pequeno e cinza, no rodapé à direita */
    .st-key-linha_atualizacao {{ position: fixed; right: 24px; bottom: 6px; z-index: 998; width: auto !important; }}
    .st-key-linha_atualizacao [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    .proxima-atualizacao {{ color: {COR_TEXTO_CINZA}; font-size: 0.85rem; }}
    /* ☰ do celular (no lugar do menu lateral) e botão "Camadas" do mapa */
    .st-key-menu_celular [data-testid="stPopoverButton"] [data-testid="stIconMaterial"] {{ font-size: 1.7rem; }}
    .st-key-menu_celular [data-testid="stPopoverButton"] div[aria-hidden="true"] {{ display: none; }}
    [data-testid="stPopoverBody"]:has([class*="st-key-celular_pagina_"]) {{ width: 290px; max-height: 80vh; }}
    [class*="st-key-celular_pagina_"] button, [class*="st-key-celular_menu_"] button {{
        justify-content: flex-start !important; text-align: left;
    }}
    [data-testid="stPopoverBody"]:has(.st-key-lista_camadas) {{ width: calc(100vw - 24px); max-height: 70vh; }}
    /* Telas estreitas (celular), como o @media do Taipei */
    @media (max-width: 750px) {{
        .stMainBlockContainer {{ padding-left: 12px !important; padding-right: 12px !important;
                                 padding-top: 72px !important; }}
        .proxima-atualizacao {{ font-size: 0.75rem; background: rgba(9, 9, 9, 0.85); padding: 1px 6px;
                                border-radius: 4px; }}
        .st-key-barra_topo {{ padding: 0 10px; }}
        .topo-titulo {{ font-size: 1.05rem; }}
        .titulo-painel {{ font-size: 1.15rem; }}
        [class*="st-key-cartao_"] {{ min-height: 0; padding: 14px 14px 8px 14px; }}
        .st-key-robo {{ right: 12px; bottom: 34px; }}
        .st-key-robo [data-testid="stPopover"] button {{ width: 56px; height: 56px; }}
        .st-key-robo [data-testid="stPopover"] button [data-testid="stIconMaterial"] {{
            font-size: 2rem; width: 2rem; height: 2rem; }}
        [data-testid="stPopoverBody"]:has(.st-key-robo_conversa) {{ width: calc(100vw - 24px); }}
        .st-key-linha_atualizacao {{ right: 12px; }}
    }}
    @media (max-width: 500px) {{ .topo-subtitulo {{ display: none; }} }}
    /* Página do componente: o cartão fica do tamanho do conteúdo, com o gráfico logo abaixo dos botões
       (na grade ele estica e empurra o rodapé para baixo, mas aqui não há rodapé) */
    .st-key-pagina_componente_cartao [class*="st-key-cartao_"] {{ min-height: 0; }}
    .st-key-pagina_componente_cartao [class*="st-key-grafico_"] > div:last-child {{ margin-top: 0; }}
    .st-key-voltar_catalogo button p, .st-key-voltar_catalogo button span {{ color: #5a9cf8 !important; }}
    .st-key-voltar_catalogo button [data-testid="stIconMaterial"] {{ font-size: 1.4rem; }}
    /* Colaboradores do projeto: fotos redondas; na ficha, rótulos cinza como no Taipei */
    .foto-colaborador {{ border-radius: 50%; object-fit: cover; display: block; margin: 0 auto; }}
    [class*="st-key-ver_colaborador_"] button p {{ text-align: center; font-size: 0.9rem; }}
    .info-colaborador-topo {{ display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }}
    .info-colaborador-topo .foto-colaborador {{ margin: 0; }}
    .info-colaborador-nome {{ color: #ffffff; font-size: 1.2rem; font-weight: 700; }}
    .info-colaborador-rotulo {{ color: {COR_TEXTO_CINZA}; font-size: 0.85rem; margin-top: 6px; }}
    .info-colaborador p {{ margin: 0 0 6px 0; }}
    /* Gráfico "Número com unidade" (TextUnitChart do Taipei): números grandes com a unidade */
    .numero-grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 18px;
                     min-height: 250px; align-content: center; padding: 10px 0; }}
    .numero-rotulo {{ color: {COR_TEXTO_CINZA}; font-size: 0.95rem; margin-bottom: 4px; }}
    .numero-valor {{ font-size: 2.6rem; font-weight: 700; line-height: 1.1; }}
    .numero-valor span {{ font-size: 1rem; font-weight: 400; margin-left: 6px; color: #d0d0d0; }}
    /* Colaboradores do componente (acrescentados na administração) */
    .colaboradores-componente {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 6px; }}
    .colaborador-componente {{ display: flex; align-items: center; gap: 8px; color: #d0d0d0; font-size: 0.9rem; }}
    .colaborador-componente .foto-colaborador {{ margin: 0; }}
    /* Área de administração: tabelas com cabeçalho cinza e linhas separadas, como as do Taipei */
    .admin-cabecalho {{ color: {COR_TEXTO_CINZA}; font-size: 0.85rem; font-weight: 600;
                        border-bottom: 1px solid #494b4e; padding-bottom: 6px; }}
    .admin-celula {{ color: #e6e6e6; font-size: 0.92rem; line-height: 1.35; overflow-wrap: anywhere; }}
    .admin-celula .icone-material {{ font-size: 1.2rem; margin-right: 6px; }}
    .admin-situacao {{ border: 1px solid; border-radius: 4px; padding: 1px 6px; font-size: 0.8rem;
                       white-space: nowrap; }}
    /* Documentação técnica: texto numa coluna de leitura */
    .st-key-documentacao {{ max-width: 980px; }}
    /* Alto da documentação, como o do Taipei: título grande em degradê, frase, botões e cartão de exemplo */
    .doc-heroi {{ text-align: center; padding: 40px 0 18px 0; }}
    .doc-titulo {{
        font-size: clamp(2.8rem, 6vw, 5rem); font-weight: 700; line-height: 1.15;
        background: linear-gradient(90deg, #5a9cf8 0%, #7a90b8 55%, #5a9cf8 100%);
        -webkit-background-clip: text; background-clip: text; color: transparent;
    }}
    .doc-titulo span {{ display: inline-block; }}
    .doc-frase {{ color: #b8b8b8; font-size: clamp(1.3rem, 2.4vw, 2.1rem); margin-top: 18px; }}
    .st-key-doc_botoes {{ flex-wrap: wrap; }}
    .st-key-doc_botoes button, .st-key-doc_botoes a {{ border-radius: 5px !important; min-height: 40px; }}
    .st-key-doc_sobre button {{ background-color: #6b6c6e !important; border: none !important; }}
    .st-key-doc_botoes [data-testid="stLinkButton"] a {{ background: transparent !important; border: 2px solid #ffffff !important; }}
    .st-key-doc_ir_painel button {{ background-color: #5a9cf8 !important; border: none !important; }}
    .st-key-doc_botoes button p, .st-key-doc_botoes a p, .st-key-doc_botoes span {{ color: #ffffff !important; font-size: 1.05rem; }}
    .st-key-cartao_demo {{ background-color: {COR_CARTAO}; border-radius: 6px; padding: 20px 22px 14px 22px;
                          height: 520px; overflow: hidden; }}
    .demo-topo {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }}
    .demo-titulo {{ color: #ffffff; font-size: 1.3rem; font-weight: 700; line-height: 1.25; }}
    .demo-etiqueta {{ color: {COR_TEXTO_CINZA}; border: 1px solid #8a8a8a; border-radius: 5px; padding: 1px 7px;
                      font-size: 0.82rem; white-space: nowrap; }}
    .demo-resumo {{ color: {COR_TEXTO_CINZA}; margin-top: 18px; font-size: 0.95rem; }}
    .demo-resumo b {{ color: #c8c8c8; font-weight: 400; font-size: 1.45rem; }}
    .demo-legenda {{ display: block; font-size: 0.9rem; color: {COR_TEXTO_CINZA}; margin-top: 2px; }}
    .demo-escala {{ display: inline-block; width: 60px; height: 14px; border-radius: 4px; vertical-align: -2px;
                    background: linear-gradient(90deg, #b46fd0, #4a2f5c); margin: 0 6px; }}
    .doc-divisa {{ border: none; border-top: 1px dashed #494b4e; margin: 28px 0 18px 0; }}
    /* Chavinha escuro/claro da documentação (como a do Taipei): pílula cinza com a bolinha branca */
    .st-key-tema_doc_escuro button, .st-key-tema_doc_claro button {{
        width: 52px !important; min-width: 52px; height: 28px; min-height: 28px !important; padding: 0 3px !important;
        border-radius: 14px !important; border: none !important; display: flex !important;
        background-color: #5b5d60 !important; justify-content: flex-end !important;
    }}
    .st-key-tema_doc_claro button {{ background-color: #c9ccd1 !important; justify-content: flex-start !important; }}
    .st-key-tema_doc_escuro button > div, .st-key-tema_doc_claro button > div {{ width: auto !important; flex: 0 0 auto; }}
    .st-key-tema_doc_escuro [data-testid="stIconMaterial"], .st-key-tema_doc_claro [data-testid="stIconMaterial"] {{
        background-color: #ffffff; color: #3a3c3e !important; border-radius: 50%; width: 22px; height: 22px;
        font-size: 17px !important; display: flex; align-items: center; justify-content: center; margin: 0 !important;
    }}
    .st-key-tema_doc_claro [data-testid="stIconMaterial"] {{ color: #e0a400 !important; }}
    .st-key-voltar_documentacao button p, .st-key-voltar_documentacao button span {{ color: #5a9cf8 !important; }}
    .st-key-abrir_documentacao button, .st-key-abrir_documentacao button div,
    .st-key-abrir_colaboradores button, .st-key-abrir_colaboradores button div {{
        justify-content: flex-start !important; }}
    /* Aviso inicial: parágrafos separados e a dica do mapa em vermelho, como no Taipei */
    .aviso-inicial p {{ margin: 0 0 12px 0; line-height: 1.45; }}
    .aviso-inicial-destaque {{ color: #FF6961; }}
    /* Painel sem cartões: ícone, "Nenhum componente adicionado" e a dica, no meio da tela */
    .painel-vazio {{
        min-height: 62vh; display: flex; flex-direction: column; align-items: center; justify-content: center;
        text-align: center; color: #ffffff;
    }}
    .painel-vazio .icone-material {{ font-size: 2.2rem; margin: 0 0 10px 0; }}
    .painel-vazio-titulo {{ font-size: 1.3rem; font-weight: 700; }}
    .painel-vazio-dica {{ font-size: 0.9rem; }}
    /* Título da coluna de montar painéis no catálogo, como no Taipei */
    .catalogo-titulo-lateral {{ color: #ffffff; font-size: 1.35rem; font-weight: 700; line-height: 1.3; }}
    .etiqueta-grupo {{
        font-size: 0.8rem; font-weight: 400; color: #888787; border: 1px solid #494b4e; border-radius: 4px;
        padding: 1px 6px; margin-left: 10px; vertical-align: middle;
    }}
    /* Meio de transporte: quadros com ícone e porcentagem (IconPercentChart do Taipei) */
    .grade-meios {{
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; height: 380px; margin-top: 16px;
        align-content: center;
    }}
    .quadro-meio {{ text-align: center; padding: 10px 4px; }}
    .icone-meio {{ font-size: 2.6rem !important; color: #9DC56E; margin: 0 !important; }}
    .valor-meio {{ color: #ffffff; font-size: 1.7rem; line-height: 1.3; }}
    .nome-meio {{ color: #d0d0d0; font-size: 0.95rem; line-height: 1.25; }}
    </style>
""", unsafe_allow_html=True)

# --- DADOS REAIS DO IBGE (Censo 2022) ---
# Moradores e faixas de idade de cada setor censitário e de cada bairro.
# Esses dois arquivos são gerados pelo preparar_dados.py a partir dos arquivos do IBGE.
FAIXAS = ["0 a 14 anos", "15 a 59 anos", "60 anos ou mais"]
df_dados_setores = pd.read_csv(arquivo_dados("dados_setores_oriximina.csv"), sep=";", dtype={"CD_SETOR": str})
df_dados_bairros = pd.read_csv(arquivo_dados("dados_bairros_oriximina.csv"), sep=";")

populacao_total = f"{df_dados_setores['Habitantes'].sum():,}".replace(",", ".")  # 68.294
urbana_total = int(df_dados_setores.loc[df_dados_setores["SITUACAO"] == "Urbana", "Habitantes"].sum())  # 47.358
rural_total = int(df_dados_setores.loc[df_dados_setores["SITUACAO"] == "Rural", "Habitantes"].sum())    # 20.936

# Faixas etárias reais do município inteiro (IBGE, Censo 2022 - Pirâmide etária)
pop_0_14 = 20097
pop_15_59 = 41700      # 15 a 64 anos (43.687) menos 60 a 64 anos (1.987)
pop_60_mais = 6497     # 60 a 64 anos (1.987) mais 65 anos ou mais (4.510)
pop_idades = pop_0_14 + pop_15_59 + pop_60_mais   # 68.294
perc_0_14 = pop_0_14 / pop_idades        # 29,4%
perc_15_59 = pop_15_59 / pop_idades      # 61,1%
perc_60_mais = pop_60_mais / pop_idades  # 9,5%


def formatar(n):
    return f"{int(round(n)):,}".replace(",", ".")


def formatar_perc(p):
    return f"{p:.1%}".replace(".", ",")


def montar_balao(linha, extra=""):
    # Balão no estilo do painel de Taipei: total e as três faixas de idade
    return (
        f"{extra}{formatar(linha['Habitantes'])} habitantes<br>"
        f"População de 0 a 14 anos: {formatar(linha['0 a 14 anos'])} habitantes<br>"
        f"População de 60 anos ou mais: {formatar(linha['60 anos ou mais'])} habitantes<br>"
        f"População de 15 a 59 anos: {formatar(linha['15 a 59 anos'])} habitantes"
    )


# Bairros da sede urbana, extraídos do Mapa de Macrozoneamento Urbano
# (Revisão do Plano Diretor 2017, mapa 01/19)
with open(arquivo_dados("oriximina_bairros.geojson"), "r", encoding="utf-8") as f:
    geojson_bairros = json.load(f)

df_bairros = pd.DataFrame([feature["properties"] for feature in geojson_bairros["features"]])

# Setores censitários do IBGE (.geojson)
with open(arquivo_dados("oriximina_setores.geojson"), "r", encoding="utf-8") as f:
    geojson_oriximina = json.load(f)

lista_setores = []
for index, feature in enumerate(geojson_oriximina["features"]):
    properties = feature["properties"]
    # O GeoJSON do IBGE não traz NM_BAIRRO preenchido; usa o nome da localidade quando existir
    nome_local = str(
        properties.get("NM_BAIRRO") or properties.get("NM_AGLOM")
        or properties.get("NM_NU") or properties.get("NM_FCU") or ""
    )
    lista_setores.append({
        "CD_SETOR": properties.get("CD_SETOR", str(index)),
        "Localidade": nome_local.title() if nome_local else "Não identificada",
    })

df_setores = pd.DataFrame(lista_setores).merge(df_dados_setores, on="CD_SETOR", how="left")
df_setores["Zona"] = df_setores["SITUACAO"].map({"Urbana": "Zona Urbana", "Rural": "Zona Rural"})

# --- CARTÃO NO ESTILO DO PAINEL DE TAIPEI ---
# Aviso no canto da tela depois de uma ação (como a notificação do Taipei)
if "aviso" in st.session_state:
    st.toast(st.session_state.pop("aviso"), icon=":material/check_circle:")

OPCOES_AREA = {"Município de Oriximiná": "geral", "Zona Urbana (bairros)": "urbana"}
OPCOES_GRAFICO = ["Gráfico de distritos/regiões", "Gráfico de colunas verticais"]

# Texto de "Informações do componente", no formato do painel de Taipei
DESCRICAO_COMPONENTE = """
**Descrição do componente ( ID: 216 | Index: city_age_distribution | City: oriximina )**

Mostra a divisão da população de Oriximiná por faixa etária, distribuindo os moradores de cada bairro,
distrito ou comunidade conforme a idade. Essa divisão ajuda a entender a composição populacional de cada
região do município, incluindo a população infantil, a população em idade ativa e a população idosa,
servindo de base analítica importante para formuladores de políticas, planejadores urbanos e pesquisadores
locais. Por meio desses dados, é possível realizar a alocação de recursos públicos e o planejamento de
instalações comunitárias, garantindo que o desenvolvimento em educação, saúde, transporte (incluindo o
fluvial) e assistência social de Oriximiná esteja mais alinhado às necessidades reais de cada faixa etária,
promovendo um desenvolvimento equilibrado entre a estrutura populacional e a infraestrutura do município.

**Exemplo de uso**

Usado em planejamento municipal, formulação de políticas sociais e análise estatística populacional, os
dados de divisão etária por localidade de Oriximiná podem ajudar órgãos governamentais e pesquisadores a
entender mudanças na estrutura demográfica. Também é aplicado na avaliação da distribuição de faixas etárias
em diferentes áreas, auxiliando no planejamento de recursos educacionais (como o transporte escolar e escolas
polo), instalações de saúde (como Unidades Básicas de Saúde) e serviços de assistência social (como o CRAS e
programas para a terceira idade). Além disso, o comércio local e novas empresas também podem usar esses dados
para análises de mercado, projetando produtos e serviços voltados a diferentes grupos etários, aumentando a
precisão das estratégias comerciais e a eficácia operacional nas diferentes regiões do município.

**Dados relacionados**
"""

# "Dados relacionados" no formato do Taipei: aviso dentro de uma caixa arredondada,
# conjunto de dados e colaboradores com o brasão em círculo
DADOS_RELACIONADOS = """
<div class="caixa-aviso">
Aviso: a frequência de atualização, a qualidade dos dados, a conversão de endereços territoriais e as
limitações da fonte (como dados censitários ou cadastros municipais) podem fazer com que os dados do painel
sejam ligeiramente diferentes dos dados originais.
</div>
<div class="texto-cinza"><a class="link-dados" href="https://cidades.ibge.gov.br/brasil/pa/oriximina/panorama"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(IBGE, Censo Demográfico 2022)</a></div>
<div class="texto-cinza pequeno">
Município inteiro: {populacao_total} habitantes ({urbana_total} na zona urbana e {rural_total} na
zona rural); 0 a 14 anos: {pop_0_14} ({perc_0_14}); 15 a 59 anos: {pop_15_59} ({perc_15_59});
60 anos ou mais: {pop_60_mais} ({perc_60_mais}).
Moradores e idades de cada setor: Agregados por Setores Censitários (básico e demografia). Nos setores
pequenos, o IBGE esconde algumas faixas por sigilo; elas foram completadas de forma que o total de cada
setor e o total de cada faixa no município (Pirâmide etária) fechem com os números oficiais.
Cada bairro recebe os moradores dos setores conforme a localização dos domicílios no Cadastro Nacional
de Endereços (CNEFE 2022). Porto Trombetas e as áreas da sede fora dos bairros do Plano Diretor aparecem
à parte no gráfico de colunas.
</div>
<div class="titulo-colaboradores">Colaboradores</div>
{logo_colaborador}
"""

# Brasão da Prefeitura de Oriximiná para o círculo de "Colaboradores"
logo_colaborador = ""
ARQ_LOGO = os.path.join(PASTA_IMAGENS, "oriximina-logo.jpg")
if os.path.exists(ARQ_LOGO):
    with open(ARQ_LOGO, "rb") as arquivo_logo:
        logo_base64 = base64.b64encode(arquivo_logo.read()).decode()
    logo_colaborador = ('<a href="https://www.oriximina.pa.gov.br" target="_blank" rel="noreferrer">'
                        f'<img class="logo-colaborador" src="data:image/jpeg;base64,{logo_base64}" '
                        'title="Prefeitura Municipal de Oriximiná"></a>')


# Destaque ao passar o mouse na legenda, como no Taipei: a faixa escolhida fica acesa
# e as outras ficam apagadas. O Plotly não faz isso sozinho, então os gráficos são
# desenhados em HTML com este pequeno JavaScript. Guarda a transparência original de
# cada faixa (o radar é meio transparente) para devolvê-la quando o mouse sai.
JS_DESTACAR_LEGENDA = """
    const gd = document.getElementById('{plot_id}');
    const original = gd.data.map(t => (t.opacity === undefined ? 1 : t.opacity));
    function ligarLegenda() {
        gd.querySelectorAll('.legend .traces').forEach(function (item, i) {
            const indice = (item.__data__ && item.__data__[0].trace.index) ?? i;
            item.style.cursor = 'pointer';
            item.onmouseenter = function () {
                Plotly.restyle(gd, {opacity: original.map((o, j) => j === indice ? o : 0.15)});
            };
            item.onmouseleave = function () {
                Plotly.restyle(gd, {opacity: original});
            };
        });
    }
    gd.on('plotly_afterplot', ligarLegenda);
    ligarLegenda();
"""


def corpo_divisoes(area_escolhida):
    """Mapa ou colunas do cartão de divisões etárias. Devolve os dados mostrados."""
    visao = OPCOES_AREA[area_escolhida]

    # Botões para alternar entre o mapa e o gráfico de colunas
    tipo_grafico = tipo_de_grafico("divisoes", OPCOES_GRAFICO)   # desmarcado: volta para o primeiro

    if visao == "urbana":
        # Moradores reais de cada bairro: soma dos setores do IBGE que ficam dentro dele
        df_dados = df_dados_bairros.rename(columns={"nome": "Nome"})
        texto_total = formatar(df_dados["Habitantes"].sum())
        df_mapa = df_bairros.merge(df_dados, left_on="nome", right_on="Nome", how="left")
        df_mapa["Título"] = df_mapa["nome"]
        df_mapa["balao"] = df_mapa.apply(
            lambda l: montar_balao(l) if pd.notna(l["Habitantes"]) else f"{l['tipo']}<br>Sem moradores",
            axis=1
        )
        geojson_mapa, chave_mapa, coluna_local = geojson_bairros, "properties.nome", "nome"
    else:
        texto_total = populacao_total
        # Colunas: Zona Urbana e Zona Rural, somando os setores reais de cada uma
        df_dados = (df_setores.dropna(subset=["Zona"])
                    .groupby("Zona", as_index=False)[["Habitantes"] + FAIXAS].sum()
                    .rename(columns={"Zona": "Nome"}))
        df_mapa = df_setores.copy()
        # Setores sem moradores ficam em cinza no mapa
        df_mapa.loc[df_mapa["Habitantes"].fillna(0) == 0, "Habitantes"] = float("nan")
        df_mapa["Título"] = df_mapa["Zona"].fillna("Setor sem moradores")
        df_mapa["balao"] = df_mapa.apply(
            lambda l: montar_balao(l, f"Localidade: {l['Localidade']}<br>")
            if pd.notna(l["Habitantes"]) else f"Localidade: {l['Localidade']}<br>Sem moradores",
            axis=1
        )
        geojson_mapa, chave_mapa, coluna_local = geojson_oriximina, "properties.CD_SETOR", "CD_SETOR"

    if tipo_grafico == OPCOES_GRAFICO[0]:
        # Legenda do Taipei: total de habitantes e barra "Mais ▬ Menos"
        st.markdown(
            f'<div class="legenda-total">Total<br>{texto_total} habitantes'
            + ('<br><span class="texto-cinza pequeno">Porto Trombetas e áreas fora dos bairros: '
               'ver colunas</span>' if visao == "urbana" else '') + '<br>'
            'Mais<span class="legenda-barra"></span>Menos</div>',
            unsafe_allow_html=True
        )

        df_com_dados = df_mapa[df_mapa["Habitantes"].notna()]
        df_sem_dados = df_mapa[df_mapa["Habitantes"].isna()]

        # Mapa só com as formas (sem fundo de ruas), pintado pela quantidade de habitantes
        fig_mapa = go.Figure(go.Choropleth(
            geojson=geojson_mapa,
            featureidkey=chave_mapa,
            locations=df_com_dados[coluna_local],
            z=df_com_dados["Habitantes"],
            colorscale=ESCALA_AZUL,
            showscale=False,
            marker_line_color=COR_CARTAO,
            marker_line_width=1,
            customdata=df_com_dados[["Título", "balao"]],
            hovertemplate=(f"<span style='color:{COR_TEXTO_CINZA}'>%{{customdata[0]}}</span><br>"
                           "%{customdata[1]}<extra></extra>")
        ))
        if not df_sem_dados.empty:
            # Áreas sem dados de população ficam em cinza
            fig_mapa.add_trace(go.Choropleth(
                geojson=geojson_mapa,
                featureidkey=chave_mapa,
                locations=df_sem_dados[coluna_local],
                z=[0] * len(df_sem_dados),
                colorscale=[[0, "#4a4d50"], [1, "#4a4d50"]],
                showscale=False,
                marker_line_color=COR_CARTAO,
                marker_line_width=1,
                customdata=df_sem_dados[["Título", "balao"]],
                hovertemplate=(f"<span style='color:{COR_TEXTO_CINZA}'>%{{customdata[0]}}</span><br>"
                               "%{customdata[1]}<extra></extra>")
            ))
        fig_mapa.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)",
                             projection_type="mercator")
        fig_mapa.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            height=340,
            paper_bgcolor="rgba(0,0,0,0)",
            dragmode=False,
            hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555",
                            font=dict(color="white", size=15))
        )
        fig_mapa.update_layout(font=dict(family="Source Sans Pro, sans-serif"))

        # Efeito do Taipei: a área embaixo do mouse cresce um pouco, fica mais clara
        # e passa para a frente das vizinhas. O Plotly não faz isso sozinho.
        aumentar_area = """
            const gd = document.getElementById('{plot_id}');
            let areaAtiva = null;
            function soltarArea() {
                if (areaAtiva) { areaAtiva.classList.remove('area-ativa'); areaAtiva = null; }
            }
            gd.on('plotly_hover', function (ev) {
                const ponto = ev.points[0];
                const caminhos = gd.querySelectorAll('.choroplethlocation');
                const area = Array.from(caminhos).find(
                    p => p.__data__ && p.__data__.loc === ponto.location
                );
                if (!area || area === areaAtiva) return;
                soltarArea();
                area.parentNode.appendChild(area);   // traz para a frente
                area.classList.add('area-ativa');
                areaAtiva = area;
            });
            gd.on('plotly_unhover', soltarArea);
        """
        html_mapa = fig_mapa.to_html(
            full_html=False, include_plotlyjs="cdn", post_script=aumentar_area,
            config={"displayModeBar": False, "responsive": True},
            default_height="460px", default_width="100%"
        )
        estilo_mapa = """
            <style>
            .choroplethlocation { transition: transform 0.15s ease, filter 0.15s ease; }
            .area-ativa {
                transform-box: fill-box; transform-origin: center; transform: scale(1.12);
                filter: brightness(1.15) drop-shadow(0 3px 6px rgba(0, 0, 0, 0.6));
            }
            </style>
        """
        st.iframe(f'<body style="margin:0">{estilo_mapa}{html_mapa}</body>', height=350)
    else:
        # Colunas verticais empilhadas por faixa de idade, do maior para o menor
        df_colunas = df_dados.sort_values("Habitantes", ascending=False)

        # Colunas empilhadas; só a ponta de cima de cada coluna fica arredondada.
        # Ordem de baixo para cima igual à do Taipei: 0-14, 60+, 15-59.
        fig_colunas = go.Figure()
        for faixa in ["0 a 14 anos", "60 anos ou mais", "15 a 59 anos"]:
            fig_colunas.add_trace(go.Bar(
                name=f"População de {faixa}",
                x=df_colunas["Nome"],
                # Eixo em "mil habitantes", como o Taipei (仟人); o balão mostra o número exato
                y=df_colunas[faixa] / 1000,
                customdata=df_colunas[faixa],
                marker=dict(color=CORES_IDADES[faixa], line=dict(color=COR_CARTAO, width=1.5)),
                hovertemplate="%{x}<br>%{fullData.name}: %{customdata:,.0f} habitantes<extra></extra>"
            ))
        fig_colunas.update_layout(
            template="plotly_dark",
            barmode="stack",
            barcornerradius=5,
            bargap=0.45,
            margin=dict(l=0, r=0, t=30, b=0),
            height=340,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            separators=",.",
            xaxis=dict(title=None, tickangle=-45, automargin=True),
            yaxis=dict(title="Mil habitantes", gridcolor="#3a3c3e", tickformat=",.1~f"),
            legend=dict(title=None, traceorder="normal", orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0)
        )
        fig_colunas.update_layout(font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"))

        html_colunas = fig_colunas.to_html(
            full_html=False, include_plotlyjs="cdn", post_script=JS_DESTACAR_LEGENDA,
            config={"displayModeBar": False, "responsive": True},
            default_height="460px", default_width="100%"
        )
        st.iframe(f'<body style="margin:0">{html_colunas}</body>', height=350)

    return df_dados


# --- CARTÃO 2: INDICADORES DE CUIDADOS DE LONGO PRAZO (aging_kpi no Taipei) ---
# Mesmas definições do Taipei e do IBGE, com a Pirâmide etária oficial de Oriximiná
pop_15_64 = 43687      # 15 a 64 anos
pop_65_mais = 4510     # 65 anos ou mais
def calcular_indicadores(p0_14, p15_64, p65):
    return [
        ("Razão de dependência idosa", round(p65 / p15_64 * 100)),
        ("Razão de dependência infantil", round(p0_14 / p15_64 * 100)),
        ("Razão de dependência total", round((p0_14 + p65) / p15_64 * 100)),
        ("Índice de envelhecimento", round(p65 / p0_14 * 100)),
    ]


INDICADORES = calcular_indicadores(pop_0_14, pop_15_64, pop_65_mais)   # 10, 46, 56 e 22

DESCRICAO_INDICADORES = """
**Descrição do componente ( ID: 218 | Index: aging_kpi | City: oriximina )**

Este gráfico apresenta indicadores relacionados aos cuidados de longo prazo em Oriximiná: razão de
dependência idosa, razão de dependência infantil, razão de dependência total e índice de envelhecimento.
A razão de dependência idosa mostra quantas pessoas de 65 anos ou mais existem para cada 100 pessoas em
idade ativa (15 a 64 anos); a razão de dependência infantil mostra quantas crianças de 0 a 14 anos existem
para cada 100 pessoas em idade ativa; a razão de dependência total soma as duas e reflete o peso geral
sobre a população em idade de trabalhar. O índice de envelhecimento compara a população idosa com a
infantil, mostrando a tendência de envelhecimento da população.

**Exemplo de uso**

Ao planejar políticas de cuidados de longo prazo, a Prefeitura pode usar a razão de dependência idosa, a
infantil, a total e o índice de envelhecimento para avaliar as necessidades futuras de atendimento. Em
Oriximiná, a razão de dependência infantil (46%) é bem maior que a idosa (10%) e o índice de envelhecimento
é de 22%, o que indica uma população jovem: a prioridade hoje é creche, escola e saúde infantil. Se o
índice de envelhecimento subir e passar de 100%, haverá mais idosos do que crianças, e será preciso ampliar
os serviços de cuidado à pessoa idosa, o atendimento domiciliar e os programas de convivência.

**Dados relacionados**
"""

DADOS_RELACIONADOS_INDICADORES = """
<div class="caixa-aviso">
Aviso: a frequência de atualização, a qualidade dos dados, a conversão de endereços territoriais e as
limitações da fonte (como dados censitários ou cadastros municipais) podem fazer com que os dados do painel
sejam ligeiramente diferentes dos dados originais.
</div>
<div class="texto-cinza"><a class="link-dados" href="https://cidades.ibge.gov.br/brasil/pa/oriximina/panorama"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(IBGE, Censo Demográfico 2022 - Pirâmide etária)</a></div>
<div class="texto-cinza pequeno">
0 a 14 anos: {pop_0_14}; 15 a 64 anos: {pop_15_64}; 65 anos ou mais: {pop_65_mais}.
Razão de dependência idosa = 65+ ÷ 15-64; infantil = 0-14 ÷ 15-64; total = (0-14 + 65+) ÷ 15-64;
índice de envelhecimento = 65+ ÷ 0-14 (todos multiplicados por 100).
</div>
<div class="titulo-colaboradores">Colaboradores</div>
{logo_colaborador}
"""


# --- JANELAS (iguais às do Taipei) ---
# Verdadeiro enquanto a janela "Informações do componente" é montada: aí Reportar, Baixar e Incorporar
# trocam o conteúdo da própria janela (fechar uma janela e abrir outra fazia a tela pular)
dentro_da_info = False


def sair_da_acao_na_info(fechar_janela=False):
    """Volta das telas Reportar / Baixar / Incorporar para as informações do componente (ou fecha tudo)."""
    st.session_state.pop("acao_na_info", None)
    if fechar_janela:
        st.session_state.info_aberto = None
        st.rerun()
    st.rerun(scope="fragment")


def janela_baixar(nome_padrao, conteudo_json, conteudo_csv):
    if dentro_da_info:
        formulario_baixar(nome_padrao, conteudo_json, conteudo_csv)
    else:
        dialogo_baixar(nome_padrao, conteudo_json, conteudo_csv)


@st.dialog("Baixar dados", width="small")
def dialogo_baixar(nome_padrao, conteudo_json, conteudo_csv):
    formulario_baixar(nome_padrao, conteudo_json, conteudo_csv)


def formulario_baixar(nome_padrao, conteudo_json, conteudo_csv):
    # Janela "Baixar dados": nome do arquivo, formato e Cancelar / Baixar
    na_info = dentro_da_info
    nome = st.text_input("Digite o nome do arquivo", value=nome_padrao)
    formato = st.radio("Selecione o formato do arquivo", ["JSON", "CSV (UTF-8)"])
    if formato == "JSON":
        conteudo, extensao, tipo = conteudo_json, "json", "application/json"
    else:
        conteudo, extensao, tipo = conteudo_csv, "csv", "text/csv"

    with st.container(horizontal=True, horizontal_alignment="right", key="controles_baixar"):
        if st.button("Cancelar", type="tertiary", key="cancelar_baixar"):
            if na_info:
                sair_da_acao_na_info()
            st.rerun()
        # Sem nome, o botão de baixar some, como no Taipei
        if nome.strip() and st.download_button(
            f"Baixar {extensao.upper()}", conteudo, file_name=f"{nome.strip()}.{extensao}",
            mime=tipo, type="primary", key="confirmar_baixar"
        ):
            if na_info:
                sair_da_acao_na_info(fechar_janela=True)
            st.rerun()   # Fecha a janela depois de baixar


TIPOS_PROBLEMA = [
    "Informações básicas do componente incorretas",
    "Dados do componente incorretos ou desatualizados",
    "Problema do sistema",
    "Outra sugestão",
]


def limpar_relato():
    for chave in ("relato_titulo", "relato_tipo", "relato_descricao", "relato_incompleto"):
        st.session_state.pop(chave, None)


def janela_reportar(componente, area):
    """Dentro de "Informações do componente", o formulário troca o conteúdo da própria janela (sem fechar
    e abrir outra, o que fazia a tela pular); fora dela, abre a janela "Reportar um problema"."""
    if dentro_da_info:
        formulario_reportar(componente, area)
    else:
        dialogo_reportar(componente, area)


@st.dialog("Reportar um problema", width="small", on_dismiss=limpar_relato)
def dialogo_reportar(componente, area):
    formulario_reportar(componente, area)


def formulario_reportar(componente, area):
    # Janela "Reportar um problema": título, tipo, descrição, Cancelar / Reportar
    na_info = dentro_da_info
    titulo_atual = st.session_state.get("relato_titulo", "")
    descricao_atual = st.session_state.get("relato_descricao", "")
    # Campos obrigatórios ainda vazios ficam com a borda vermelha, como no Taipei
    vazios = [chave for chave, valor in (("relato_titulo", titulo_atual), ("relato_descricao", descricao_atual))
              if not valor.strip()]
    if vazios:
        st.markdown("<style>" + " ".join(
            f".st-key-{chave} [data-testid$='RootElement'] {{ border-color: #e5484d !important; }}" for chave in vazios
        ) + "</style>", unsafe_allow_html=True)

    # O contador (x/20, x/200) aparece dentro do campo e muda a cada letra digitada
    titulo = st.text_input("Título do problema* (máx. 20)", max_chars=20, key="relato_titulo")
    tipo = st.radio("Tipo de problema*", TIPOS_PROBLEMA, key="relato_tipo")
    descricao = st.text_area("Descrição breve* (máx. 200)", max_chars=200,
                             height=90, key="relato_descricao")
    if st.session_state.pop("relato_incompleto", False):
        st.markdown('<div style="color:#e5484d; font-size:0.9rem;">Preencha o título e a descrição.</div>',
                    unsafe_allow_html=True)

    with st.container(horizontal=True, horizontal_alignment="right", key="controles_reportar"):
        if st.button("Cancelar", type="tertiary", key="cancelar_reportar"):
            limpar_relato()
            if na_info:
                sair_da_acao_na_info()   # volta para as informações do componente, na mesma janela
            st.rerun()
        # O botão fica sempre visível: no Streamlit o texto só é confirmado ao sair do
        # campo, e clicar no botão já confirma o que foi digitado
        if st.button("Reportar problema", type="primary", key="confirmar_reportar"):
            if not (titulo.strip() and descricao.strip()):
                st.session_state.relato_incompleto = True
                st.rerun(scope="fragment")
            # Os relatos vão para a lista "Problemas a responder" da área de administração
            problemas = carregar_json(ARQ_PROBLEMAS, [])
            problemas.append({
                "id": max([p["id"] for p in problemas], default=0) + 1, "titulo": titulo.strip(), "tipo": tipo,
                "componente": componente, "area": area, "descricao": descricao.strip(),
                "data": f"{pd.Timestamp.now():%d/%m/%Y %H:%M}",
                "usuario": (st.session_state.usuario or {}).get("email", "anônimo"),
                "status": "Pendente", "resposta": "", "editado_em": "", "editado_por": ""})
            salvar_json(ARQ_PROBLEMAS, problemas)
            limpar_relato()
            if na_info:
                st.session_state.pop("acao_na_info", None)
                st.session_state.info_aberto = None
            st.session_state.aviso = "Problema reportado com sucesso. Obrigado pela sugestão"
            st.rerun()


def janela_incorporar(id_componente, titulo_componente):
    if dentro_da_info:
        formulario_incorporar(id_componente, titulo_componente)
    else:
        dialogo_incorporar(id_componente, titulo_componente)


@st.dialog("Incorporar componente", width="small")
def dialogo_incorporar(id_componente, titulo_componente):
    formulario_incorporar(id_componente, titulo_componente)


def formulario_incorporar(id_componente, titulo_componente):
    # Janela "Incorporar componente": código do iframe e botão "Copiar código"
    endereco = (st.context.url or "http://localhost:8501").split("?")[0].rstrip("/")
    codigo = f"""<iframe
    id="Oriximina-City-Dashboard-Component-{id_componente}"
    title="{titulo_componente}"
    src="{endereco}/?embed=true&componente={id_componente}"
    width="760"
    height="760"
    style="border-radius: 5px"
    frameborder="0"
    allow="fullscreen"
    loading="lazy"
></iframe>"""
    st.markdown('<div class="texto-cinza">Copie o código abaixo para incorporar este componente '
                'à sua página</div>', unsafe_allow_html=True)
    # Caixa de texto e botão em HTML, porque copiar para a área de transferência precisa de JavaScript
    st.iframe(f"""
        <body style="margin:0; font-family: 'Source Sans Pro', sans-serif;">
        <textarea id="codigo" readonly style="width:100%; height:160px; box-sizing:border-box; resize:none;
            background:#1e1f21; color:#d0d0d0; border:1px solid #555; border-radius:5px;
            padding:8px 10px; font-size:14px; font-family:inherit; outline:none;">{html.escape(codigo)}</textarea>
        <div style="display:flex; justify-content:flex-end; align-items:center; gap:10px; margin-top:12px;">
            <span id="aviso" style="color:#56B96D; font-size:14px;"></span>
            <button id="copiar" style="background:#4a9eff; color:#fff; border:none; border-radius:5px;
                padding:6px 12px; font-size:15px; cursor:pointer; font-family:inherit;">Copiar código</button>
        </div>
        <script>
        document.getElementById('copiar').onclick = function () {{
            const caixa = document.getElementById('codigo');
            caixa.select();
            let copiou = false;
            try {{ copiou = document.execCommand('copy'); }} catch (e) {{}}
            if (!copiou && navigator.clipboard) navigator.clipboard.writeText(caixa.value);
            caixa.setSelectionRange(0, 0);
            document.getElementById('aviso').textContent = 'Código copiado!';
        }};
        </script>
        </body>
    """, height=215)


# --- PARTES COMUNS DOS CARTÕES ---
# Dentro da janela "Informações do componente" o cartão aparece de novo (ele continua no fundo), e o
# Streamlit não aceita dois botões/caixas com a mesma chave: lá dentro as chaves ganham este sufixo
sufixo_chave = ""


def k(nome):
    return nome + sufixo_chave


# Altura do texto com rolagem da descrição: 440 na janela "Informações do componente", maior na página
# própria do componente (pagina_componente)
altura_descricao = 440


def alternar_favorito(chave):
    """Marca ou desmarca o cartão como favorito e avisa, como a notificação do Taipei."""
    favorito = chave not in st.session_state.favoritos
    st.session_state.favoritos ^= {chave}
    salvar_favoritos()
    st.session_state.aviso = ("Componente adicionado aos favoritos com sucesso" if favorito
                              else "Componente removido dos favoritos com sucesso")


def cabecalho(chave, titulo, fonte, opcoes_area, atualizacao="Censo 2022"):
    """Título e fonte à esquerda; atualização, favorito e área à direita. Devolve a área escolhida."""
    editado = componente_editado(chave)   # mudanças feitas na área de administração
    titulo = editado.get("titulo") or titulo
    fonte = editado.get("fonte") or fonte
    atualizacao = editado.get("atualizacao") or atualizacao
    col_titulo, col_controles = st.columns([3, 2])
    with col_titulo:
        st.markdown(f'<div class="cartao-titulo">{titulo}</div><div class="cartao-fonte">{fonte}</div>',
                    unsafe_allow_html=True)
    with col_controles:
        col_atualizacao, col_coracao = st.columns([3, 1])
        favorito = chave in st.session_state.favoritos
        # A cor do coração vai junto do próprio cartão: assim ela muda mesmo quando só a janela é refeita
        cor_coracao = (f"<style>.st-key-{k(f'botao_favorito_{chave}')} button p {{ color: #f44336 !important; }}"
                       "</style>" if favorito else "")
        col_atualizacao.markdown(f'<span class="cartao-atualizacao">Atualização: {atualizacao}</span>{cor_coracao}',
                                 unsafe_allow_html=True)
        # Como no Taipei, o coração de favoritar só aparece para quem entrou com uma conta
        if st.session_state.usuario and col_coracao.button(
            "♥", key=k(f"botao_favorito_{chave}"), type="tertiary",
            help="Remover dos favoritos" if favorito else "Adicionar aos favoritos"
        ):
            alternar_favorito(chave)
            # Dentro de "Informações do componente", refaz só a janela (refazer a página fecha e reabre
            # a janela, e a tela pula); o painel de trás é atualizado quando a janela fechar
            st.rerun(scope="fragment" if dentro_da_info else "app")
        # Com uma única opção a caixa fica travada, como no Taipei
        return st.selectbox("Área", opcoes_area, label_visibility="collapsed", key=k(f"area_{chave}"),
                            disabled=len(opcoes_area) == 1)


def botao_info(chave):
    # Rodapé: "Informações do componente" abre a janela com a descrição (ver grade_cartoes), como no Taipei
    rodape = st.container(horizontal=True, horizontal_alignment="right")
    # O clique só marca qual janela abrir (on_click roda antes da página): assim a janela é aberta
    # antes de os cartões serem desenhados de novo, e aparece logo
    rodape.button("Informações do componente", type="tertiary", key=f"info_componente_{chave}",
                  width="content", on_click=abrir_info, args=(chave,))


def abrir_info(chave):
    st.session_state.info_aberto = chave


def grafico_historico(chave, series):
    """Gráfico de histórico (HistoryChart do Taipei): como o dado mudou ao longo dos anos.

    series: lista de (nome, valores por ano (pd.Series com os anos no índice), cor, unidade).
    Em cima, botões de período ("Últimos 5 anos", ...), como no Taipei; embaixo, linha suave com área.
    """
    anos = sorted({int(a) for _, valores, _, _ in series for a in valores.index})
    periodos = {f"Últimos {n} anos": n for n in (5, 10) if n < len(anos)}
    periodos[f"Todo o período ({anos[0]}–{anos[-1]})"] = len(anos)
    periodo = st.segmented_control("Período do histórico", list(periodos), default=list(periodos)[0],
                                   label_visibility="collapsed", key=f"historico_periodo_{chave}") \
        or list(periodos)[0]
    inicio = anos[-periodos[periodo]]

    fig = go.Figure()
    for nome, valores, cor, unidade in series:
        valores = valores[valores.index.astype(int) >= inicio]
        r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
        fig.add_trace(go.Scatter(
            name=nome, x=valores.index.astype(int), y=valores.values, mode="lines+markers",
            line=dict(color=cor, width=2, shape="spline"), marker=dict(size=6, color=cor),
            fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.18)",
            hovertemplate=f"%{{x}}<br>%{{fullData.name}}: %{{y:.1f}} {unidade}<extra></extra>"))
    fig.update_layout(
        template="plotly_dark", height=200, margin=dict(l=0, r=8, t=28 if len(series) > 1 else 8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
        font=dict(family="Source Sans Pro, sans-serif", color=COR_TEXTO_CINZA),
        # Meio ano de folga nas pontas, para o primeiro e o último ano aparecerem inteiros
        xaxis=dict(showgrid=False, dtick=1, linecolor="#555555", range=[inicio - 0.5, anos[-1] + 0.5]),
        yaxis=dict(showgrid=False, rangemode="tozero", automargin=True),
        showlegend=len(series) > 1, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, itemclick=False),
        hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white", size=14)))
    st.iframe('<body style="margin:0">' + fig.to_html(
        full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True},
        default_height="200px", default_width="100%") + "</body>", height=210)


def partes_descricao(descricao):
    """Separa o texto do componente em: linha do ID, descrição, exemplo de uso e o resto."""
    topo, _, resto = descricao.strip().partition("\n\n")
    texto, _, resto = resto.partition("**Exemplo de uso**")
    exemplo, _, fim = resto.partition("**Dados relacionados**")
    return topo, texto.strip(), exemplo.strip(), fim


def descricao_com_edicoes(chave, descricao):
    """Troca a descrição e o exemplo de uso pelos textos editados na área de administração."""
    editado = componente_editado(chave)
    if not (editado.get("descricao") or editado.get("exemplo")):
        return descricao
    topo, texto, exemplo, fim = partes_descricao(descricao)
    return (f"\n{topo}\n\n{editado.get('descricao') or texto}\n\n**Exemplo de uso**\n\n"
            f"{editado.get('exemplo') or exemplo}\n\n**Dados relacionados**{fim}")


def extras_relacionados(chave):
    """Links de dados e colaboradores do componente acrescentados na administração (HTML)."""
    editado = componente_editado(chave)
    partes = []
    links = editado.get("links", [])
    if links:
        partes.append('<div class="titulo-colaboradores">Mais conjuntos de dados</div>' + "".join(
            f'<div class="texto-cinza"><a class="link-dados" href="{html.escape(l["url"])}" target="_blank" '
            f'rel="noreferrer">{html.escape(l["nome"] or l["url"])}</a></div>' for l in links))
    nomes = editado.get("colaboradores", [])
    escolhidos = [c for c in COLABORADORES if c["nome"] in nomes]
    if escolhidos:
        partes.append('<div class="titulo-colaboradores">Colaboradores deste componente</div>'
                      '<div class="colaboradores-componente">' + "".join(
                          f'<div class="colaborador-componente">{foto_colaborador(c, 44)}'
                          f'<span>{html.escape(c["nome"])}</span></div>' for c in escolhidos) + '</div>')
    return "".join(partes)


def painel_descricao(chave, descricao, dados_relacionados, acao_reportar, acao_baixar, acao_incorporar,
                     historico=None):
    descricao = descricao_com_edicoes(chave, descricao)
    with st.container(key=f"lado_descricao_{chave}"):
        # Texto com rolagem, como no painel de Taipei
        with st.container(height=altura_descricao, border=False, key=f"texto_descricao_{chave}"):
            if historico:
                # Como no Taipei: o histórico vem depois do exemplo de uso e antes dos dados relacionados
                antes, _, depois = descricao.partition("**Dados relacionados**")
                st.markdown(antes)
                st.markdown("**Histórico**")
                historico()
                st.markdown("**Dados relacionados**" + depois)
            else:
                st.markdown(descricao)
            st.markdown(dados_relacionados + extras_relacionados(chave), unsafe_allow_html=True)

        # Botões azuis: Reportar, Baixar e Incorporar. Dentro da janela de informações, a tela escolhida
        # aparece na mesma janela; fora dela, abre a janela própria no fim da montagem da página
        with st.container(horizontal=True, horizontal_alignment="right", key=f"acoes_info_{chave}"):
            for rotulo, nome, acao in (("⚑ Reportar", "reportar", acao_reportar),
                                       ("⤓ Baixar", "baixar", acao_baixar),
                                       ("‹› Incorporar", "incorporar", acao_incorporar)):
                if st.button(rotulo, key=f"abrir_{nome}_{chave}"):
                    if dentro_da_info:
                        # Aparece na mesma janela, sem recarregar a página
                        st.session_state.acao_na_info = (nome, acao)
                        st.rerun(scope="fragment")
                    st.session_state.info_aberto = None
                    st.session_state.janela_pendente = acao
                    st.rerun()


TITULOS_ACAO_NA_INFO = {"reportar": "Reportar um problema", "baixar": "Baixar dados",
                        "incorporar": "Incorporar componente"}


def fechar_info():
    st.session_state.info_aberto = None
    st.session_state.pop("acao_na_info", None)
    limpar_relato()


@st.dialog(" ", width="large", on_dismiss=fechar_info)
def janela_info(chave):
    """Janela "Informações do componente": o gráfico à esquerda e a descrição à direita, como no Taipei."""
    global dentro_da_info
    if "aviso" in st.session_state:
        st.toast(st.session_state.pop("aviso"), icon=":material/check_circle:")
    dentro_da_info = True
    try:
        with st.container(key="conteudo_janela_info"):
            conteudo_info(chave)
        acao_na_info = st.session_state.get("acao_na_info")
        if acao_na_info:
            # Clicou em Reportar / Baixar / Incorporar: como no Taipei, a janela de informações continua atrás,
            # escurecida, e a nova aparece por cima (o Streamlit não abre uma janela dentro da outra, então
            # esta é uma caixa flutuante desenhada no CSS de .st-key-acao_na_janela_info)
            nome, acao = acao_na_info
            with st.container(key="acao_na_janela_info"), st.container(key="caixa_acao_info"):
                # X no canto: o fundo escuro cobre o X da janela de trás (e o Incorporar não tem Cancelar)
                if st.button("✕", type="tertiary", key="fechar_acao_info", help="Fechar"):
                    limpar_relato()
                    sair_da_acao_na_info()
                st.markdown(f'<div class="titulo-acao-info">{TITULOS_ACAO_NA_INFO[nome]}</div>',
                            unsafe_allow_html=True)
                acao()
    finally:
        dentro_da_info = False


def conteudo_info(chave):
    global sufixo_chave
    _, desenhar_grafico, desenhar_descricao = CARTOES[chave]
    col_grafico, col_descricao = st.columns([1.5, 1], gap="medium")
    sufixo_chave = "_janela"
    try:
        with col_grafico, st.container(key=f"janela_grafico_{chave}"):
            resultado = desenhar_grafico()
    finally:
        sufixo_chave = ""
    with col_descricao:
        desenhar_descricao(resultado)


def cartao(chave, desenhar_grafico):
    """Cartão no estilo do Taipei: gráfico e, no pé, o "Informações do componente"."""
    with st.container(key=f"cartao_{chave}"), st.container(key=f"grafico_{chave}"):
        desenhar_grafico()
        botao_info(chave)


# --- CARTÃO 1: DIVISÕES ETÁRIAS ---
def grafico_divisoes():
    area_escolhida = cabecalho("divisoes", "Divisões etárias em toda a cidade",
                               "Diretoria-Geral de Estatística | Oriximiná – Dados do Censo IBGE 2022",
                               list(OPCOES_AREA))
    df_dados = corpo_divisoes(area_escolhida)
    return area_escolhida, df_dados


def descricao_divisoes(resultado):
    area_escolhida, df_dados = resultado
    dados = DADOS_RELACIONADOS.format(
        populacao_total=populacao_total,
        pop_0_14=formatar(pop_0_14), perc_0_14=formatar_perc(perc_0_14),
        pop_15_59=formatar(pop_15_59), perc_15_59=formatar_perc(perc_15_59),
        pop_60_mais=formatar(pop_60_mais), perc_60_mais=formatar_perc(perc_60_mais),
        urbana_total=formatar(urbana_total), rural_total=formatar(rural_total),
        logo_colaborador=logo_colaborador
    )
    # Mesmo formato do Taipei: "data" com uma série por faixa etária e "categories" com os locais
    conteudo_json = json.dumps({
        "data": [{"name": f"População de {faixa}", "data": [int(v) for v in df_dados[faixa]]}
                 for faixa in FAIXAS],
        "categories": df_dados["Nome"].tolist()
    }, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = (df_dados.rename(columns={"Nome": "Local"})
                    .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"))
    titulo = "Divisões etárias em toda a cidade"
    painel_descricao(
        "divisoes", DESCRICAO_COMPONENTE, dados,
        lambda: janela_reportar(titulo, area_escolhida),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar(216, titulo),
    )


# --- CARTÃO 2: INDICADORES DE CUIDADOS DE LONGO PRAZO ---
def grafico_indicadores(chave="indicadores", opcoes_area=("Município de Oriximiná",),
                        indicadores_da_area=lambda area: INDICADORES):
    area_escolhida = cabecalho(chave, "Indicadores de cuidados de longo prazo",
                               "IBGE - Censo 2022 | Dados fixos", list(opcoes_area))
    INDICADORES = indicadores_da_area(area_escolhida)
    # Quatro quadros separados por uma cruz fina, como o TextUnitChart do Taipei
    quadros = "".join(
        f'<div class="indicador"><div class="indicador-conteudo">'
        f'<div class="indicador-nome">{nome}</div>'
        f'<div class="indicador-valor">{valor}<span> %</span></div></div></div>'
        for nome, valor in INDICADORES
    )
    st.markdown(f'<div class="grade-indicadores">{quadros}</div>', unsafe_allow_html=True)
    return area_escolhida, INDICADORES


def descricao_indicadores(resultado, chave="indicadores", descricao=DESCRICAO_INDICADORES,
                          dados=None, id_componente=218):
    area_escolhida, INDICADORES = resultado
    dados = dados or DADOS_RELACIONADOS_INDICADORES.format(
        pop_0_14=formatar(pop_0_14), pop_15_64=formatar(pop_15_64), pop_65_mais=formatar(pop_65_mais),
        logo_colaborador=logo_colaborador
    )
    # Formato do Taipei para esse gráfico: uma lista com nome, valor e unidade
    lista = [{"x": nome, "y": valor, "icon": "%"} for nome, valor in INDICADORES]
    conteudo_json = json.dumps({"data": [{"data": lista}]}, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = (pd.DataFrame(INDICADORES, columns=["Indicador", "Valor (%)"])
                    .to_csv(index=False, sep=";").encode("utf-8-sig"))
    titulo = "Indicadores de cuidados de longo prazo"
    painel_descricao(
        chave, descricao, dados,
        lambda: janela_reportar(titulo, area_escolhida),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar(id_componente, titulo),
    )


# --- CARTÃO 3: ESTRUTURA ANUAL DA POPULAÇÃO IDOSA EMPREGADA (aging_workforce_trend no Taipei) ---
# Empregos formais ativos em 31/12 de cada ano (RAIS), gerados pelo preparar_rais.py
GRUPOS_EMPREGO = {
    "1.População empregada não idosa": "#24B0DD",       # até 44 anos
    "2.População empregada de meia-idade": "#56B96D",   # 45 a 64 anos
    "3.População empregada idosa": "#F8CF58",           # 65 anos ou mais
}
OPCOES_GRAFICO_EMPREGO = ["Gráfico de barras (%)", "Gráfico de radar", "Gráfico de colunas verticais"]
df_emprego = pd.read_csv(arquivo_dados("dados_emprego_idade_oriximina.csv"), sep=";")
ULTIMO_ANO_RAIS = df_emprego["Ano"].max()

DESCRICAO_EMPREGO = """
**Descrição do componente ( ID: 215 | Index: aging_workforce_trend | City: oriximina )**

Mostra, ano a ano, como os trabalhadores com emprego formal em Oriximiná se dividem por idade: população
empregada não idosa (até 44 anos), de meia-idade (45 a 64 anos) e idosa (65 anos ou mais). A série permite
acompanhar se a força de trabalho do município está envelhecendo, observando o peso de cada faixa etária no
total de empregados em 31 de dezembro de cada ano. Os dados são contínuos e comparáveis entre os anos, o
que os torna adequados para análises de longo prazo.

**Exemplo de uso**

Útil para políticas de emprego, qualificação profissional e previdência no município. Por exemplo, se a
participação dos trabalhadores de meia-idade e idosos crescer, a Prefeitura e as empresas locais podem
planejar programas de requalificação, saúde do trabalhador e transição para a aposentadoria; se a
participação dos mais jovens cair, pode ser sinal de que é preciso ampliar o primeiro emprego e a formação
técnica para a juventude de Oriximiná.

**Dados relacionados**
"""

DADOS_RELACIONADOS_EMPREGO = """
<div class="caixa-aviso">
Aviso: a frequência de atualização, a qualidade dos dados, a conversão de endereços territoriais e as
limitações da fonte (como dados censitários ou cadastros municipais) podem fazer com que os dados do painel
sejam ligeiramente diferentes dos dados originais.
</div>
<div class="texto-cinza"><a class="link-dados"
href="https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(Ministério do Trabalho e Emprego, RAIS {anos})</a></div>
<div class="texto-cinza pequeno">
Vínculos de emprego formal (com carteira assinada, servidores públicos e outros registrados na RAIS) ativos
em 31 de dezembro, de estabelecimentos localizados em Oriximiná. Trabalhadores informais e por conta própria
não entram na RAIS. Total de empregados: {totais}.
Atenção: em 2021 quase nenhum servidor da administração pública de Oriximiná aparece na RAIS (237, contra
1.829 em 2020 e 3.594 em 2022), provavelmente por falta de declaração naquele ano. Como os servidores são
em média mais velhos, a parte de meia-idade de 2021 fica menor do que a real.
</div>
<div class="titulo-colaboradores">Colaboradores</div>
{logo_colaborador}
"""


def percentuais_emprego(df):
    perc = df[list(GRUPOS_EMPREGO)].div(df["Empregados"], axis=0).mul(100)
    perc.insert(0, "Ano", df["Ano"].astype(str).values)
    return perc


def grafico_emprego(chave="emprego", opcoes_area=("Município de Oriximiná",),
                    dados_da_area=lambda area: df_emprego):
    area_escolhida = cabecalho(chave, "Estrutura de crescimento anual da população idosa empregada",
                               "Ministério do Trabalho e Emprego | RAIS – Empregos formais",
                               list(opcoes_area), atualizacao=f"RAIS {ULTIMO_ANO_RAIS}")
    tipo = tipo_de_grafico(chave, OPCOES_GRAFICO_EMPREGO)

    df_emprego = dados_da_area(area_escolhida).reset_index(drop=True)
    df_emprego_perc = percentuais_emprego(df_emprego)
    fig = go.Figure()
    anos = df_emprego_perc["Ano"]
    for i, (grupo, cor) in enumerate(GRUPOS_EMPREGO.items()):
        valores = df_emprego_perc[grupo]
        pessoas = df_emprego[grupo]
        balao = "%{customdata[0]}<br>" + grupo[2:] + ": %{customdata[1]:.1f}% (%{customdata[2]:,} pessoas)<extra></extra>"
        dados_balao = list(zip(anos, valores, pessoas))
        if tipo == OPCOES_GRAFICO_EMPREGO[0]:
            # Barras horizontais de 100%, uma por ano, com a porcentagem escrita dentro
            fig.add_trace(go.Bar(
                name=grupo, y=anos, x=valores, orientation="h", marker_color=cor,
                marker_line=dict(color=COR_CARTAO, width=2),
                text=[f"{v:.0f}%" if v >= 5 else "" for v in valores], textposition="inside", insidetextanchor="middle",
                textfont=dict(color="white", size=14, family="Arial Black"),
                customdata=dados_balao, hovertemplate=balao
            ))
        elif tipo == OPCOES_GRAFICO_EMPREGO[1]:
            # Radar: um eixo por ano, uma linha por faixa de idade
            fig.add_trace(go.Scatterpolar(
                name=grupo, theta=list(anos) + [anos.iloc[0]], r=list(valores) + [valores.iloc[0]],
                line_color=cor, fill="toself", opacity=0.75,
                customdata=dados_balao + [dados_balao[0]], hovertemplate=balao
            ))
        else:
            fig.add_trace(go.Bar(
                name=grupo, x=anos, y=valores, marker_color=cor,
                marker_line=dict(color=COR_CARTAO, width=1.5),
                customdata=dados_balao, hovertemplate=balao
            ))

    legenda = dict(title=None, orientation="v", traceorder="normal", yanchor="bottom", y=1.02, xanchor="left", x=0,
                   font=dict(color=COR_TEXTO_CINZA, size=14), itemclick=False)
    fig.update_layout(
        template="plotly_dark", height=380, margin=dict(l=0, r=10, t=110, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
        font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"), legend=legenda,
        hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white", size=14))
    )
    if tipo == OPCOES_GRAFICO_EMPREGO[0]:
        fig.update_layout(barmode="stack", barcornerradius=6, bargap=0.55)
        fig.update_xaxes(visible=False, range=[0, 100])
        fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=COR_TEXTO_CINZA, size=14))
    elif tipo == OPCOES_GRAFICO_EMPREGO[1]:
        fig.update_layout(polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#3a3c3e", tickfont=dict(size=11)),
            angularaxis=dict(gridcolor="#3a3c3e", tickfont=dict(color=COR_TEXTO_CINZA, size=13))
        ))
    else:
        fig.update_layout(barmode="stack", barcornerradius=5, bargap=0.45)
        fig.update_yaxes(title="%", range=[0, 100], gridcolor="#3a3c3e")

    st.iframe('<body style="margin:0">' + fig.to_html(
        full_html=False, include_plotlyjs="cdn", post_script=JS_DESTACAR_LEGENDA,
        config={"displayModeBar": False, "responsive": True}, default_height="520px", default_width="100%"
    ) + "</body>", height=390)
    return area_escolhida, df_emprego


def descricao_emprego(resultado, chave="emprego", descricao=DESCRICAO_EMPREGO,
                      relacionados=DADOS_RELACIONADOS_EMPREGO, id_componente=215):
    area_escolhida, df_emprego = resultado
    df_emprego_perc = percentuais_emprego(df_emprego)
    anos = f"{df_emprego['Ano'].min()}–{df_emprego['Ano'].max()}"
    totais = "; ".join(f"{a}: {formatar(t)}" for a, t in zip(df_emprego["Ano"], df_emprego["Empregados"]))
    dados = relacionados.format(anos=anos, totais=totais, logo_colaborador=logo_colaborador)
    # Mesmo formato do Taipei: "data" com uma série por faixa e "categories" com os anos
    conteudo_json = json.dumps({
        "data": [{"name": grupo, "data": [round(v) for v in df_emprego_perc[grupo]]} for grupo in GRUPOS_EMPREGO],
        "categories": df_emprego_perc["Ano"].tolist()
    }, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = (df_emprego.merge(df_emprego_perc.assign(Ano=df_emprego["Ano"]), on="Ano", suffixes=("", " (%)"))
                    .round(1).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"))
    titulo = "Estrutura de crescimento anual da população idosa empregada"
    idosos = df_emprego_perc.set_index("Ano")["3.População empregada idosa"]
    painel_descricao(
        chave, descricao, dados,
        lambda: janela_reportar(titulo, area_escolhida),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar(id_componente, titulo),
        historico=lambda: grafico_historico(chave, [
            ("Idosos entre os empregados formais", idosos, GRUPOS_EMPREGO["3.População empregada idosa"], "%"),
        ]),
    )


# --- CARTÃO 4: RAZÃO DE DEPENDÊNCIA E ÍNDICE DE ENVELHECIMENTO (dependency_aging no Taipei) ---
# Estimativas anuais do Ministério da Saúde (DATASUS), geradas pelo preparar_dependencia.py
df_dependencia = pd.read_csv(arquivo_dados("dados_dependencia_oriximina.csv"), sep=";")
COR_DEPENDENCIA = "#67baca"       # cores do dependency_aging no Taipei
COR_ENVELHECIMENTO = "#fbf3ac"
OPCOES_GRAFICO_DEPENDENCIA = ["Gráfico de colunas e linhas", "Gráfico de linhas (comparativo)"]

DESCRICAO_DEPENDENCIA = """
**Descrição do componente ( ID: 214 | Index: dependency_aging | City: oriximina )**

Mostra, ano a ano, a razão de dependência e o índice de envelhecimento da população de Oriximiná. A razão
de dependência indica quantas crianças (0 a 14 anos) e idosos (65 anos ou mais) existem para cada 100
pessoas em idade de trabalhar (15 a 64 anos), refletindo o peso que a população economicamente dependente
representa. O índice de envelhecimento indica quantos idosos existem para cada 100 crianças e mostra o
ritmo em que a população do município está envelhecendo.

**Exemplo de uso**

Útil no planejamento de longo prazo de educação, saúde e assistência social. Em Oriximiná, a razão de
dependência vem caindo (menos crianças por adulto), enquanto o índice de envelhecimento sobe todos os anos.
Isso indica que, com o tempo, a demanda deve se deslocar de creches e escolas para serviços voltados à
pessoa idosa, como atenção básica para doenças crônicas, cuidado domiciliar e acessibilidade, e ajuda a
Prefeitura a antecipar essas mudanças no orçamento e na oferta de serviços.

**Dados relacionados**
"""

DADOS_RELACIONADOS_DEPENDENCIA = """
<div class="caixa-aviso">
Aviso: a frequência de atualização, a qualidade dos dados, a conversão de endereços territoriais e as
limitações da fonte (como dados censitários ou cadastros municipais) podem fazer com que os dados do painel
sejam ligeiramente diferentes dos dados originais.
</div>
<div class="texto-cinza"><a class="link-dados"
href="http://tabnet.datasus.gov.br/cgi/deftohtm.exe?ibge/cnv/popsvs2024br.def"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(Ministério da Saúde / DATASUS, Estimativas
populacionais por município, idade e sexo 2000-2025)</a></div>
<div class="texto-cinza pequeno">
Razão de dependência = (0 a 14 anos + 65 anos ou mais) ÷ 15 a 64 anos × 100; índice de envelhecimento =
65 anos ou mais ÷ 0 a 14 anos × 100. São estimativas para cada ano ({anos}). Em 2022 a estimativa
(71.692 habitantes) é maior que a população contada pelo Censo (68.294); por isso os valores de 2022
diferem um pouco do cartão "Indicadores de cuidados de longo prazo", que usa o Censo.
</div>
<div class="titulo-colaboradores">Colaboradores</div>
{logo_colaborador}
"""


def grafico_dependencia(chave="dependencia", opcoes_area=("Município de Oriximiná",),
                        dados_da_area=lambda area: df_dependencia):
    area_escolhida = cabecalho(chave, "Razão de dependência e índice de envelhecimento",
                               "Ministério da Saúde | DATASUS – Estimativas populacionais",
                               list(opcoes_area),
                               atualizacao=f"Estimativa {df_dependencia['Ano'].max()}")
    tipo = tipo_de_grafico(chave, OPCOES_GRAFICO_DEPENDENCIA)

    dados = dados_da_area(area_escolhida)
    anos = dados["Ano"].astype(str)
    dependencia = dados["Razão de dependência"]
    envelhecimento = dados["Índice de envelhecimento"]
    balao = "%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>"
    fig = go.Figure()
    if tipo == OPCOES_GRAFICO_DEPENDENCIA[0]:
        # Colunas para a razão de dependência (eixo da esquerda) e linha para o índice (eixo da direita)
        fig.add_trace(go.Bar(name="Razão de dependência", x=anos, y=dependencia, marker_color=COR_DEPENDENCIA,
                             marker_line=dict(color=COR_DEPENDENCIA, width=1), opacity=0.85,
                             hovertemplate=balao))
        fig.add_trace(go.Scatter(name="Índice de envelhecimento", x=anos, y=envelhecimento, yaxis="y2",
                                 mode="lines+markers", line=dict(color=COR_ENVELHECIMENTO, width=2),
                                 marker=dict(size=10), hovertemplate=balao))
    else:
        # Duas linhas lado a lado no tempo, cada uma com o seu eixo, para comparar as tendências
        fig.add_trace(go.Scatter(name="Razão de dependência", x=anos, y=dependencia, mode="lines+markers",
                                 line=dict(color=COR_DEPENDENCIA, width=3), marker=dict(size=8),
                                 hovertemplate=balao))
        fig.add_trace(go.Scatter(name="Índice de envelhecimento", x=anos, y=envelhecimento, yaxis="y2",
                                 mode="lines+markers", line=dict(color=COR_ENVELHECIMENTO, width=3),
                                 marker=dict(size=8), hovertemplate=balao))

    titulo_eixo = dict(font=dict(color=COR_TEXTO_CINZA, size=14, weight="bold"))
    # Eixos com números redondos e o mesmo número de divisões, para as marcas ficarem alinhadas
    divisoes = math.ceil(dependencia.max() / 10)
    passo_direita = math.ceil(envelhecimento.max() / divisoes)
    fig.update_layout(
        template="plotly_dark", height=380, margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
        font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"), bargap=0.3,
        xaxis=dict(tickangle=-45, tickfont=dict(color=COR_TEXTO_CINZA, size=13), showgrid=False),
        yaxis=dict(title=dict(text="Razão de dependência", **titulo_eixo), range=[0, divisoes * 10], dtick=10,
                   gridcolor="#3a3c3e", tickfont=dict(color=COR_TEXTO_CINZA)),
        yaxis2=dict(title=dict(text="Índice de envelhecimento", **titulo_eixo), overlaying="y", side="right",
                    range=[0, divisoes * passo_direita], dtick=passo_direita, showgrid=False, tickfont=dict(color=COR_TEXTO_CINZA)),
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, itemclick=False,
                    font=dict(color=COR_TEXTO_CINZA, size=14)),
        hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white", size=14))
    )
    st.iframe('<body style="margin:0">' + fig.to_html(
        full_html=False, include_plotlyjs="cdn", post_script=JS_DESTACAR_LEGENDA,
        config={"displayModeBar": False, "responsive": True}, default_height="520px", default_width="100%"
    ) + "</body>", height=390)
    return area_escolhida, dados


def descricao_dependencia(resultado, chave="dependencia", descricao=DESCRICAO_DEPENDENCIA,
                          relacionados=DADOS_RELACIONADOS_DEPENDENCIA, id_componente=214):
    area_escolhida, df = resultado
    anos = f"{df['Ano'].min()}–{df['Ano'].max()}"
    dados = relacionados.format(anos=anos, logo_colaborador=logo_colaborador)
    # Mesmo formato do Taipei: uma série por indicador e "categories" com os anos
    conteudo_json = json.dumps({
        "data": [{"name": nome, "data": df[nome].tolist()}
                 for nome in ("Razão de dependência", "Índice de envelhecimento")],
        "categories": df["Ano"].astype(str).tolist()
    }, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    titulo = "Razão de dependência e índice de envelhecimento"
    por_ano = df.set_index("Ano")
    painel_descricao(
        chave, descricao, dados,
        lambda: janela_reportar(titulo, area_escolhida),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar(id_componente, titulo),
        historico=lambda: grafico_historico(chave, [
            ("Razão de dependência", por_ano["Razão de dependência"], COR_DEPENDENCIA, "%"),
            ("Índice de envelhecimento", por_ano["Índice de envelhecimento"], COR_ENVELHECIMENTO, "%"),
        ]),
    )




# --- CARTÃO 5: INFORMAÇÕES CARTOGRÁFICAS (bike_map no Taipei) ---
# No OpenStreetMap não há ciclovias mapeadas em Oriximiná; o cartão mostra a rede viária
# da sede, gerada pelo preparar_vias.py
with open(arquivo_dados("vias_oriximina.geojson"), encoding="utf-8") as arquivo:
    geojson_vias = json.load(arquivo)
df_vias = pd.DataFrame([f["properties"] for f in geojson_vias["features"]])
CORES_VIAS = {                      # as duas primeiras são as cores do bike_map no Taipei
    "Vias principais": "#a0b8e8",
    "Vias locais": "#b7ff98",
    "Caminhos e trilhas": "#9a9a9a",
}
resumo_vias = (df_vias.groupby("tipo")["comprimento_m"].agg(["count", "sum"])
               .reindex(list(CORES_VIAS)).fillna(0))

DESCRICAO_VIAS = """
**Descrição do componente ( ID: 217 | Index: road_map | City: oriximina )**

Mostra a rede viária da sede urbana de Oriximiná, dividida em vias principais (as ruas e estradas que
ligam os bairros e dão acesso à cidade), vias locais (ruas dos bairros) e caminhos e trilhas (passagens
de pedestres, ramais e trilhas). No mapa, cada tipo aparece com uma cor, o que permite ver como os bairros
estão ligados entre si e onde a malha de ruas é mais densa ou mais rarefeita.

**Exemplo de uso**

Útil no planejamento de transporte e obras: a Prefeitura pode identificar bairros com poucas ligações
com as vias principais, priorizar pavimentação e iluminação, estudar rotas de transporte escolar e de
coleta de lixo e, no futuro, planejar uma rede de ciclovias ligando os bairros ao Centro e à orla.

**Dados relacionados**
"""

DADOS_RELACIONADOS_VIAS = """
<div class="caixa-aviso">
Aviso: a frequência de atualização, a qualidade dos dados, a conversão de endereços territoriais e as
limitações da fonte (como dados censitários ou cadastros municipais) podem fazer com que os dados do painel
sejam ligeiramente diferentes dos dados originais.
</div>
<div class="texto-cinza"><a class="link-dados" href="https://www.openstreetmap.org/#map=14/-1.7630/-55.8660"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(OpenStreetMap, © colaboradores do OpenStreetMap)</a></div>
<div class="texto-cinza pequeno">
Ruas e caminhos mapeados por voluntários no OpenStreetMap (licença ODbL), na área da sede urbana. O mapa
pode estar incompleto em áreas novas ou pouco mapeadas. Não há ciclovias cadastradas em Oriximiná no
OpenStreetMap. {resumo}.
</div>
<div class="titulo-colaboradores">Colaboradores</div>
{logo_colaborador}
"""


def formatar_km(metros):
    # Formato brasileiro: ponto nos milhares e vírgula nos decimais (4.789,5 km)
    return f"{metros / 1000:,.1f} km".replace(",", "#").replace(".", ",").replace("#", ".")


def grafico_vias():
    area_escolhida = cabecalho("vias", "Informações cartográficas da rede viária",
                               "OpenStreetMap | Ruas e caminhos da sede urbana", ["Município de Oriximiná"],
                               atualizacao="OpenStreetMap")
    # Legenda do mapa, como o MapLegend do Taipei: uma linha colorida para cada tipo de via
    linhas = "".join(
        f'<div class="legenda-via"><span class="linha-via" style="background:{cor}"></span>{tipo}'
        f'<span class="cartao-fonte">&nbsp;&nbsp;{formatar_km(resumo_vias.loc[tipo, "sum"])}</span></div>'
        for tipo, cor in CORES_VIAS.items()
    )
    st.markdown(f'<div class="lista-legenda">{linhas}</div>', unsafe_allow_html=True)
    # "Filtrar mapa" e "Dados" só funcionam na Comparação de mapas, como no Taipei
    with st.container(horizontal=True, key=k("botoes_mapa_vias")):
        for rotulo, icone in (("Filtrar mapa", "tune"), ("Dados", "map")):
            if st.button(rotulo, icon=f":material/{icone}:", key=k(f"vias_{icone}"),
                         help="Abre a camada na Comparação de mapas"):
                st.session_state.pagina = "mapa"
                st.session_state.ligar_vias = True
                st.rerun()
    return area_escolhida


def descricao_vias(area_escolhida):
    resumo = "; ".join(f"{tipo}: {int(linha['count'])} trechos, {formatar_km(linha['sum'])}"
                       for tipo, linha in resumo_vias.iterrows())
    dados = DADOS_RELACIONADOS_VIAS.format(resumo=resumo, logo_colaborador=logo_colaborador)
    conteudo_json = json.dumps(geojson_vias, ensure_ascii=False).encode("utf-8")
    conteudo_csv = (df_vias.rename(columns={"comprimento_m": "comprimento (m)", "classe_osm": "classe OSM"})
                    .to_csv(index=False, sep=";").encode("utf-8-sig"))
    titulo = "Informações cartográficas da rede viária"
    painel_descricao(
        "vias", DESCRICAO_VIAS, dados,
        lambda: janela_reportar(titulo, area_escolhida),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar(217, titulo),
    )


# --- PAINEL DA CALHA NORTE (equivalente ao "Painel da Grande Taipei") ---
# Os 9 municípios da Calha Norte paraense, com as mesmas fontes dos cartões de Oriximiná.
# Arquivos gerados pelo preparar_regiao.py
REGIAO = "Calha Norte (9 municípios)"
with open(arquivo_dados("regiao_municipios.geojson"), encoding="utf-8") as arquivo:
    geojson_regiao = json.load(arquivo)
df_regiao_idades = pd.read_csv(arquivo_dados("regiao_idades.csv"), sep=";", dtype={"codigo": str})
df_regiao_dependencia = pd.read_csv(arquivo_dados("regiao_dependencia.csv"), sep=";", dtype={"codigo": str})
df_regiao_emprego = pd.read_csv(arquivo_dados("regiao_emprego.csv"), sep=";", dtype={"codigo": str})
# Caixa de área: a região inteira ou um município (Oriximiná primeiro, os outros em ordem alfabética)
OPCOES_REGIAO = [REGIAO, "Oriximiná"] + sorted(n for n in df_regiao_idades["Nome"] if n != "Oriximiná")
MUNICIPIOS_REGIAO = ", ".join(OPCOES_REGIAO[1:])


def filtrar_regiao(df, area):
    return df if area == REGIAO else df[df["Nome"] == area]


def dependencia_regiao(area):
    colunas = ["0 a 14 anos", "15 a 64 anos", "65 anos ou mais"]
    dados = filtrar_regiao(df_regiao_dependencia, area).groupby("Ano", as_index=False)[colunas].sum()
    dados["Razão de dependência"] = ((dados["0 a 14 anos"] + dados["65 anos ou mais"])
                                     / dados["15 a 64 anos"] * 100).round(1)
    dados["Índice de envelhecimento"] = (dados["65 anos ou mais"] / dados["0 a 14 anos"] * 100).round(1)
    return dados


def emprego_regiao(area):
    return (filtrar_regiao(df_regiao_emprego, area)
            .groupby("Ano", as_index=False)[["Empregados"] + list(GRUPOS_EMPREGO)].sum())


def indicadores_regiao(area):
    soma = filtrar_regiao(df_regiao_idades, area)[["0 a 14 anos", "15 a 64 anos", "65 anos ou mais"]].sum()
    return calcular_indicadores(soma["0 a 14 anos"], soma["15 a 64 anos"], soma["65 anos ou mais"])


AVISO_PADRAO = """
<div class="caixa-aviso">
Aviso: a frequência de atualização, a qualidade dos dados, a conversão de endereços territoriais e as
limitações da fonte (como dados censitários ou cadastros municipais) podem fazer com que os dados do painel
sejam ligeiramente diferentes dos dados originais.
</div>"""
RODAPE_COLABORADORES = """
<div class="titulo-colaboradores">Colaboradores</div>
{logo_colaborador}
"""

DESCRICAO_DEPENDENCIA_CN = f"""
**Descrição do componente ( ID: 214 | Index: dependency_aging | City: calhanorte )**

Mostra, ano a ano, a razão de dependência e o índice de envelhecimento da Calha Norte paraense
({MUNICIPIOS_REGIAO}). A razão de dependência indica quantas crianças (0 a 14 anos) e idosos (65 anos ou
mais) existem para cada 100 pessoas de 15 a 64 anos; o índice de envelhecimento indica quantos idosos
existem para cada 100 crianças. Na caixa de área é possível ver a região inteira ou cada município.

**Exemplo de uso**

Permite comparar o ritmo de envelhecimento dos municípios vizinhos e planejar serviços que atendem a
região como um todo, como hospitais regionais, transporte fluvial de pacientes e consórcios de saúde.

**Dados relacionados**
"""
DADOS_RELACIONADOS_DEPENDENCIA_CN = AVISO_PADRAO + """
<div class="texto-cinza"><a class="link-dados"
href="http://tabnet.datasus.gov.br/cgi/deftohtm.exe?ibge/cnv/popsvs2024br.def"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(Ministério da Saúde / DATASUS, Estimativas
populacionais por município, idade e sexo 2000-2025)</a></div>
<div class="texto-cinza pequeno">
Estimativas para cada ano ({anos}); para a região, as pessoas de cada faixa de idade dos 9 municípios são
somadas antes do cálculo. Razão de dependência = (0 a 14 + 65 ou mais) ÷ 15 a 64 × 100; índice de
envelhecimento = 65 ou mais ÷ 0 a 14 × 100.
</div>""" + RODAPE_COLABORADORES

DESCRICAO_EMPREGO_CN = f"""
**Descrição do componente ( ID: 215 | Index: aging_workforce_trend | City: calhanorte )**

Mostra, ano a ano, como os trabalhadores com emprego formal da Calha Norte paraense ({MUNICIPIOS_REGIAO})
se dividem por idade: não idosos (até 44 anos), meia-idade (45 a 64 anos) e idosos (65 anos ou mais). Na
caixa de área é possível ver a região inteira ou cada município.

**Exemplo de uso**

Ajuda a planejar qualificação profissional e políticas de emprego em conjunto entre os municípios, e a
identificar onde a força de trabalho formal está envelhecendo mais depressa.

**Dados relacionados**
"""
DADOS_RELACIONADOS_EMPREGO_CN = AVISO_PADRAO + """
<div class="texto-cinza"><a class="link-dados"
href="https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(Ministério do Trabalho e Emprego, RAIS {anos})</a></div>
<div class="texto-cinza pequeno">
Vínculos de emprego formal ativos em 31 de dezembro, em estabelecimentos dos 9 municípios. Trabalhadores
informais e por conta própria não entram na RAIS. Total de empregados: {totais}.
Quando uma prefeitura deixa de entregar a declaração num ano, os servidores dela somem daquele ano
(em Oriximiná isso aconteceu em 2021).
</div>""" + RODAPE_COLABORADORES

DESCRICAO_INDICADORES_CN = f"""
**Descrição do componente ( ID: 218 | Index: aging_kpi | City: calhanorte )**

Indicadores de cuidados de longo prazo da Calha Norte paraense ({MUNICIPIOS_REGIAO}), pelo Censo 2022:
razão de dependência idosa, infantil e total e índice de envelhecimento. Na caixa de área é possível ver a
região inteira ou cada município.

**Exemplo de uso**

Comparar os municípios mostra onde a população é mais jovem (mais demanda de creches e escolas) e onde
ela já envelhece mais depressa (mais demanda de cuidado à pessoa idosa).

**Dados relacionados**
"""

DESCRICAO_DIVISOES_CN = f"""
**Descrição do componente ( ID: 216 | Index: city_age_distribution | City: calhanorte )**

Mostra a população de cada município da Calha Norte paraense ({MUNICIPIOS_REGIAO}) dividida em três faixas
de idade: 0 a 14 anos, 15 a 59 anos e 60 anos ou mais. No mapa, cada município é pintado pelo número de
habitantes; no gráfico de colunas, cada coluna é um município.

**Exemplo de uso**

Útil para planejar serviços regionais de saúde, educação e assistência social, e para comparar o tamanho e
a estrutura de idade da população de Oriximiná com a dos municípios vizinhos.

**Dados relacionados**
"""


def relacionados_censo_regiao(area):
    dados = filtrar_regiao(df_regiao_idades, area)
    return AVISO_PADRAO + f"""
<div class="texto-cinza"><a class="link-dados" href="https://sidra.ibge.gov.br/tabela/9514"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(IBGE, Censo Demográfico 2022, tabela 9514)</a></div>
<div class="texto-cinza pequeno">
{area}: {formatar(dados['Habitantes'].sum())} habitantes; 0 a 14 anos: {formatar(dados['0 a 14 anos'].sum())};
15 a 64 anos: {formatar(dados['15 a 64 anos'].sum())}; 65 anos ou mais: {formatar(dados['65 anos ou mais'].sum())};
60 anos ou mais: {formatar(dados['60 anos ou mais'].sum())}.
</div>""" + RODAPE_COLABORADORES.format(logo_colaborador=logo_colaborador)


def grafico_divisoes_regiao():
    area = cabecalho("divisoes_cn", "Divisões etárias em toda a região", "IBGE | Censo 2022 – Calha Norte paraense",
                     OPCOES_REGIAO)
    tipo = tipo_de_grafico("divisoes_cn", OPCOES_GRAFICO)
    dados = filtrar_regiao(df_regiao_idades, area)

    if tipo == OPCOES_GRAFICO[0]:
        st.markdown(f'<div class="legenda-total">Total<br>{formatar(dados["Habitantes"].sum())} habitantes<br>'
                    'Mais<span class="legenda-barra"></span>Menos</div>', unsafe_allow_html=True)
        baloes = dados.apply(montar_balao, axis=1)
        fig = go.Figure(go.Choropleth(
            geojson=geojson_regiao, featureidkey="properties.codigo", locations=dados["codigo"],
            z=dados["Habitantes"], colorscale=ESCALA_AZUL, showscale=False,
            marker_line_color=COR_CARTAO, marker_line_width=1.2,
            customdata=list(zip(dados["Nome"], baloes)),
            hovertemplate=(f"<span style='color:{COR_TEXTO_CINZA}'>%{{customdata[0]}}</span><br>"
                           "%{customdata[1]}<extra></extra>"),
        ))
        fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator")
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=340, paper_bgcolor="rgba(0,0,0,0)",
                          dragmode=False, font=dict(family="Source Sans Pro, sans-serif"),
                          hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555",
                                          font=dict(color="white", size=15)))
        html_fig = fig.to_html(full_html=False, include_plotlyjs="cdn",
                               config={"displayModeBar": False, "responsive": True},
                               default_height="460px", default_width="100%")
    else:
        colunas = dados.sort_values("Habitantes", ascending=False)
        fig = go.Figure()
        for faixa in ["0 a 14 anos", "60 anos ou mais", "15 a 59 anos"]:
            fig.add_trace(go.Bar(
                name=f"População de {faixa}", x=colunas["Nome"], y=colunas[faixa] / 1000,
                customdata=colunas[faixa],
                marker=dict(color=CORES_IDADES[faixa], line=dict(color=COR_CARTAO, width=1.5)),
                hovertemplate="%{x}<br>%{fullData.name}: %{customdata:,.0f} habitantes<extra></extra>"
            ))
        fig.update_layout(
            template="plotly_dark", barmode="stack", barcornerradius=5, bargap=0.45,
            margin=dict(l=0, r=0, t=30, b=0), height=340, paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", separators=",.",
            xaxis=dict(title=None, tickangle=-45, automargin=True),
            yaxis=dict(title="Mil habitantes", gridcolor="#3a3c3e", tickformat=",.1~f"),
            legend=dict(title=None, traceorder="normal", orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
            font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"),
        )
        html_fig = fig.to_html(full_html=False, include_plotlyjs="cdn", post_script=JS_DESTACAR_LEGENDA,
                               config={"displayModeBar": False, "responsive": True},
                               default_height="460px", default_width="100%")
    st.iframe(f'<body style="margin:0">{html_fig}</body>', height=350)
    return area, dados


def descricao_divisoes_regiao(resultado):
    area, dados = resultado
    conteudo_json = json.dumps({
        "data": [{"name": f"População de {faixa}", "data": [int(v) for v in dados[faixa]]} for faixa in FAIXAS],
        "categories": dados["Nome"].tolist()
    }, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = (dados.rename(columns={"Nome": "Município", "codigo": "Código IBGE"})
                    .to_csv(index=False, sep=";").encode("utf-8-sig"))
    titulo = "Divisões etárias em toda a região"
    painel_descricao(
        "divisoes_cn", DESCRICAO_DIVISOES_CN, relacionados_censo_regiao(area),
        lambda: janela_reportar(titulo, area),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar("216cn", titulo),
    )


def descricao_indicadores_regiao(resultado):
    descricao_indicadores(resultado, chave="indicadores_cn", descricao=DESCRICAO_INDICADORES_CN,
                          dados=relacionados_censo_regiao(resultado[0]), id_componente="218cn")


# --- PAINEL "TRANSPORTE PRÁTICO" DA CALHA NORTE ---
# No Taipei: bicicletas compartilhadas, ônibus elétricos e ciclovias. Na Calha Norte não existe
# nada disso; os cartões usam os dados oficiais de transporte dos 9 municípios (preparar_transporte.py)
df_transporte_meio = pd.read_csv(arquivo_dados("regiao_transporte_meio.csv"), sep=";", dtype={"codigo": str})
df_transporte_tempo = pd.read_csv(arquivo_dados("regiao_transporte_tempo.csv"), sep=";", dtype={"codigo": str})
df_frota = pd.read_csv(arquivo_dados("regiao_frota.csv"), sep=";", dtype={"codigo": str})
MES_FROTA = df_frota["Mês"].iloc[0]
COR_TRANSPORTE = "#9DC56E"            # cores do youbike_availability e do ebus_percent no Taipei
COR_TRANSPORTE_ESCURA = "#356340"
PALETA_TIPOS = ["#24B0DD", "#56B96D", "#F8CF58", "#F5AD4A", "#E170A6", "#ED6A45", "#AF4137"]

# Meios de transporte na ordem do cartão, com o ícone de cada um (Material Symbols)
ICONES_MEIOS = {
    "A pé": "directions_walk", "Bicicleta": "pedal_bike", "Motocicleta ou mototáxi": "two_wheeler",
    "Automóvel ou táxi": "directions_car", "Ônibus, van ou pau de arara": "directions_bus",
    "Barco ou lancha": "directions_boat", "Outros": "more_horiz",
}
ORDEM_TEMPO = ["Até cinco minutos", "De seis minutos até quinze minutos", "Mais de quinze minutos até meia hora",
               "Mais de meia hora até uma hora", "Mais de uma hora até duas horas",
               "Mais de duas horas até quatro horas", "Mais de quatro horas"]
ROTULO_TEMPO = dict(zip(ORDEM_TEMPO, ["Até 5 min", "6 a 15 min", "16 a 30 min", "31 min a 1 h", "1 a 2 h",
                                      "2 a 4 h", "Mais de 4 h"]))
ATE_MEIA_HORA = ORDEM_TEMPO[:3]
TIPOS_FROTA = ["Motocicletas", "Automóveis", "Caminhonetes e utilitários", "Caminhões", "Ônibus e micro-ônibus",
               "Outros"]


def figura_em_iframe(fig, altura=380, destacar_legenda=False):
    st.iframe('<body style="margin:0">' + fig.to_html(
        full_html=False, include_plotlyjs="cdn", post_script=JS_DESTACAR_LEGENDA if destacar_legenda else None,
        config={"displayModeBar": False, "responsive": True}, default_height=f"{altura}px", default_width="100%"
    ) + "</body>", height=altura + 10)


def layout_escuro(fig, altura=380, **extra):
    fig.update_layout(
        template="plotly_dark", height=altura, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        separators=",.", font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"),
        hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white", size=14)), **extra
    )


def formatar_pct(valor):
    return f"{valor:.1f}%".replace(".", ",")


def opcoes_do_componente(chave, opcoes):
    """Tipos de gráfico do componente, na ordem escolhida na administração (o primeiro é o padrão)."""
    escolhidos = [o for o in componente_editado(chave).get("tipos", []) if o in opcoes]
    return escolhidos or list(opcoes)


def tipo_de_grafico(chave, opcoes):
    opcoes = opcoes_do_componente(chave, opcoes)
    if len(opcoes) == 1:   # um tipo só: sem botões de troca
        return opcoes[0]
    # Com 3 botões ou mais, sem o "Gráfico de" no começo, para caberem lado a lado numa linha só
    curto = lambda opcao: opcao[len("Gráfico de "):].capitalize() if opcao.startswith("Gráfico de ") else opcao
    return st.segmented_control("Tipo de gráfico", opcoes, default=opcoes[0], label_visibility="collapsed",
                                format_func=curto if len(opcoes) >= 3 else str,
                                key=k(f"tipo_grafico_{chave}")) or opcoes[0]


def relacionados_transporte(link, fonte, observacao):
    return AVISO_PADRAO + f"""
<div class="texto-cinza"><a class="link-dados" href="{link}" target="_blank" rel="noreferrer">
Conjunto de dados - 1<br>({fonte})</a></div>
<div class="texto-cinza pequeno">{observacao}</div>""" + RODAPE_COLABORADORES.format(logo_colaborador=logo_colaborador)


# --- Cartão: tempo de deslocamento para o trabalho (youbike_availability no Taipei) ---
OPCOES_GRAFICO_TEMPO = ["Gráfico de medidor", "Gráfico de barras (%)"]

DESCRICAO_TEMPO = f"""
**Descrição do componente ( ID: 60 | Index: commute_time | City: calhanorte )**

Mostra quanto tempo as pessoas da Calha Norte paraense ({MUNICIPIOS_REGIAO}) levam, normalmente, para ir de
casa ao trabalho. O medidor indica a parte dos trabalhadores que chega em até meia hora; o gráfico de barras
mostra, para cada município, quem chega em até meia hora e quem leva mais que isso.

**Exemplo de uso**

Deslocamentos longos costumam indicar trabalho em comunidades distantes, áreas de mineração ou roça e a
dependência de barcos e estradas precárias. O dado ajuda a planejar linhas de transporte, estradas vicinais
e horários de embarcações.

**Dados relacionados**
"""


def grafico_tempo():
    area = cabecalho("tempo_cn", "Tempo de deslocamento para o trabalho", "IBGE | Censo 2022 – Trabalho e deslocamento",
                     OPCOES_REGIAO)
    tipo = tipo_de_grafico("tempo_cn", OPCOES_GRAFICO_TEMPO)
    dados = filtrar_regiao(df_transporte_tempo, area)
    por_tempo = dados.groupby("Tempo")["pessoas"].sum().reindex(ORDEM_TEMPO).fillna(0)
    total = por_tempo.sum()
    ate_meia_hora = por_tempo[ATE_MEIA_HORA].sum() / total * 100

    if tipo == OPCOES_GRAFICO_TEMPO[0]:
        # Medidor, como o GuageChart do Taipei
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=round(ate_meia_hora, 1), number=dict(suffix="%", font=dict(size=54)),
            title=dict(text=f"chegam ao trabalho em até meia hora<br><span style='font-size:13px;color:{COR_TEXTO_CINZA}'>"
                            f"{formatar(por_tempo[ATE_MEIA_HORA].sum())} de {formatar(total)} trabalhadores</span>",
                       font=dict(size=17, color="#d0d0d0")),
            gauge=dict(axis=dict(range=[0, 100], ticksuffix="%", tickcolor=COR_TEXTO_CINZA),
                       bar=dict(color=COR_TRANSPORTE, thickness=0.35), bgcolor=COR_TRANSPORTE_ESCURA,
                       borderwidth=0),
        ))
        layout_escuro(fig, margin=dict(l=40, r=40, t=120, b=20))
    else:
        # Barras de 100% por município: até meia hora x mais de meia hora
        por_municipio = (dados.assign(Grupo=dados["Tempo"].isin(ATE_MEIA_HORA).map(
            {True: "Até meia hora", False: "Mais de meia hora"}))
            .pivot_table(index="Nome", columns="Grupo", values="pessoas", aggfunc="sum").fillna(0))
        perc = por_municipio.div(por_municipio.sum(axis=1), axis=0).mul(100).sort_values("Até meia hora")
        fig = go.Figure()
        for grupo, cor in (("Até meia hora", COR_TRANSPORTE), ("Mais de meia hora", COR_TRANSPORTE_ESCURA)):
            fig.add_trace(go.Bar(
                name=grupo, y=perc.index, x=perc[grupo], orientation="h", marker_color=cor,
                text=[f"{v:.0f}%" for v in perc[grupo]], textposition="inside", insidetextanchor="middle",
                textfont=dict(color="white", size=13), marker_line=dict(color=COR_CARTAO, width=2),
                customdata=por_municipio.loc[perc.index, grupo],
                hovertemplate="%{y}<br>" + grupo + ": %{x:.1f}% (%{customdata:,.0f} pessoas)<extra></extra>",
            ))
        # Legenda presa à borda esquerda do cartão (não da área das barras), com os dois itens lado a lado
        layout_escuro(fig, barmode="stack", barcornerradius=6, bargap=0.45, margin=dict(l=0, r=10, t=40, b=0),
                      legend=dict(orientation="h", xref="container", x=0, xanchor="left",
                                  yref="container", y=1, yanchor="top",
                                  font=dict(color=COR_TEXTO_CINZA, size=14),
                                  itemclick=False, traceorder="normal"))
        fig.update_xaxes(visible=False, range=[0, 100])
        fig.update_yaxes(showgrid=False, tickfont=dict(color=COR_TEXTO_CINZA, size=13))
    figura_em_iframe(fig, destacar_legenda=tipo != OPCOES_GRAFICO_TEMPO[0])
    return area, dados


def descricao_tempo(resultado):
    area, dados = resultado
    tabela = (dados.pivot_table(index="Nome", columns="Tempo", values="pessoas", aggfunc="sum")
              .reindex(columns=ORDEM_TEMPO).fillna(0).astype(int).reset_index())
    conteudo_json = json.dumps({
        "data": [{"name": ROTULO_TEMPO[t], "data": tabela[t].tolist()} for t in ORDEM_TEMPO],
        "categories": tabela["Nome"].tolist()}, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = tabela.rename(columns={"Nome": "Município"}).to_csv(index=False, sep=";").encode("utf-8-sig")
    dados_rel = relacionados_transporte(
        "https://sidra.ibge.gov.br/tabela/10331", "IBGE, Censo Demográfico 2022, tabela 10331",
        "Pessoas de 10 anos ou mais, ocupadas, que trabalham fora de casa, por tempo habitual de deslocamento "
        f"de casa para o trabalho principal. {area}: {formatar(dados['pessoas'].sum())} pessoas.")
    titulo = "Tempo de deslocamento para o trabalho"
    painel_descricao("tempo_cn", DESCRICAO_TEMPO, dados_rel,
                     lambda: janela_reportar(titulo, area),
                     lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
                     lambda: janela_incorporar("60cn", titulo))


# --- Cartão: meio de transporte para o trabalho (ebus_percent no Taipei) ---
OPCOES_GRAFICO_MEIO = ["Gráfico de ícones (%)", "Gráfico de barras (%)"]

DESCRICAO_MEIO = f"""
**Descrição do componente ( ID: 212 | Index: commute_mode | City: calhanorte )**

Mostra o meio de transporte em que as pessoas da Calha Norte paraense ({MUNICIPIOS_REGIAO}) passam mais tempo
para chegar ao trabalho: a pé, bicicleta, motocicleta ou mototáxi, automóvel ou táxi, ônibus, van ou pau de
arara, barco ou lancha, e outros.

**Exemplo de uso**

Mostra o peso da motocicleta e do barco no dia a dia da região, o que orienta investimentos em trapiches e
portos, segurança no trânsito de motos, ciclovias e linhas de ônibus entre a sede e as comunidades.

**Dados relacionados**
"""


def grafico_meio():
    area = cabecalho("meio_cn", "Meio de transporte para o trabalho", "IBGE | Censo 2022 – Trabalho e deslocamento",
                     OPCOES_REGIAO)
    tipo = tipo_de_grafico("meio_cn", OPCOES_GRAFICO_MEIO)
    dados = filtrar_regiao(df_transporte_meio, area)
    por_meio = dados.groupby("Meio")["pessoas"].sum().reindex(list(ICONES_MEIOS)).fillna(0)
    perc = por_meio / por_meio.sum() * 100

    if tipo == OPCOES_GRAFICO_MEIO[0]:
        # Quadros com ícone e porcentagem, como o IconPercentChart do Taipei
        quadros = "".join(
            f'<div class="quadro-meio"><span class="icone-material icone-meio">{icone}</span>'
            f'<div class="valor-meio">{formatar_pct(perc[meio])}</div>'
            f'<div class="nome-meio">{meio}</div><div class="cartao-fonte">{formatar(por_meio[meio])} pessoas</div></div>'
            for meio, icone in ICONES_MEIOS.items()
        )
        st.markdown(f'<div class="grade-meios">{quadros}</div>', unsafe_allow_html=True)
    else:
        ordem = perc.sort_values()
        fig = go.Figure(go.Bar(
            y=ordem.index, x=ordem.values, orientation="h", marker_color=COR_TRANSPORTE,
            text=[formatar_pct(v) for v in ordem.values], textposition="outside",
            textfont=dict(color="#d0d0d0", size=13), customdata=por_meio[ordem.index],
            hovertemplate="%{y}<br>%{x:.1f}% (%{customdata:,.0f} pessoas)<extra></extra>",
        ))
        layout_escuro(fig, barcornerradius=5, bargap=0.4, margin=dict(l=0, r=40, t=20, b=0), showlegend=False)
        fig.update_xaxes(visible=False, range=[0, ordem.max() * 1.25])
        fig.update_yaxes(showgrid=False, tickfont=dict(color=COR_TEXTO_CINZA, size=13))
        figura_em_iframe(fig)
    return area, dados


def descricao_meio(resultado):
    area, dados = resultado
    tabela = (dados.pivot_table(index="Nome", columns="Meio", values="pessoas", aggfunc="sum")
              .reindex(columns=list(ICONES_MEIOS)).fillna(0).astype(int).reset_index())
    conteudo_json = json.dumps({
        "data": [{"name": meio, "data": tabela[meio].tolist()} for meio in ICONES_MEIOS],
        "categories": tabela["Nome"].tolist()}, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = tabela.rename(columns={"Nome": "Município"}).to_csv(index=False, sep=";").encode("utf-8-sig")
    dados_rel = relacionados_transporte(
        "https://sidra.ibge.gov.br/tabela/10332", "IBGE, Censo Demográfico 2022, tabela 10332",
        "Pessoas de 10 anos ou mais, ocupadas, que trabalham fora de casa, pelo meio de transporte em que passam "
        "mais tempo no caminho. As 14 categorias do IBGE foram juntadas em 7 (por exemplo, embarcação de pequeno "
        f"e de grande porte formam \"Barco ou lancha\"). {area}: {formatar(dados['pessoas'].sum())} pessoas.")
    titulo = "Meio de transporte para o trabalho"
    painel_descricao("meio_cn", DESCRICAO_MEIO, dados_rel,
                     lambda: janela_reportar(titulo, area),
                     lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
                     lambda: janela_incorporar("212cn", titulo))


# --- Cartão: frota de veículos (bike_network no Taipei) ---
OPCOES_GRAFICO_FROTA = ["Gráfico de rosca", "Gráfico de barras"]

DESCRICAO_FROTA = f"""
**Descrição do componente ( ID: 213 | Index: vehicle_fleet | City: calhanorte )**

Mostra a frota de veículos registrados nos municípios da Calha Norte paraense ({MUNICIPIOS_REGIAO}), por tipo:
motocicletas, automóveis, caminhonetes e utilitários, caminhões, ônibus e outros. O gráfico de rosca mostra a
divisão por tipo; o de barras compara os municípios (ou, com um município escolhido, os tipos de veículo).

**Exemplo de uso**

Ajuda a dimensionar a fiscalização de trânsito, a sinalização e os serviços de habilitação, e mostra o
peso da motocicleta como principal veículo da região.

**Dados relacionados**
"""


def grafico_frota():
    area = cabecalho("frota_cn", "Frota de veículos", "Ministério dos Transportes | SENATRAN – Frota por município",
                     OPCOES_REGIAO, atualizacao=MES_FROTA)
    tipo = tipo_de_grafico("frota_cn", OPCOES_GRAFICO_FROTA)
    dados = filtrar_regiao(df_frota, area)
    por_tipo = dados[TIPOS_FROTA].sum()
    total = int(por_tipo.sum())

    if tipo == OPCOES_GRAFICO_FROTA[0]:
        # Rosca por tipo de veículo, como o DonutChart do Taipei
        fig = go.Figure(go.Pie(
            labels=TIPOS_FROTA, values=por_tipo.values, hole=0.6, sort=False,
            marker=dict(colors=PALETA_TIPOS, line=dict(color=COR_CARTAO, width=2)),
            # Fatias muito pequenas ficam sem rótulo (o valor aparece ao passar o mouse)
            texttemplate=[f"{v / total * 100:.1f}%".replace(".", ",") if v / total >= 0.02 else ""
                          for v in por_tipo.values],
            textposition="inside", textfont=dict(size=13), direction="clockwise",
            hovertemplate="%{label}<br>%{value:,.0f} veículos (%{percent})<extra></extra>",
        ))
        fig.add_annotation(text=f"<b>{formatar(total)}</b><br><span style='font-size:13px'>veículos</span>",
                           showarrow=False, font=dict(size=24, color="#ffffff"))
        layout_escuro(fig, margin=dict(l=0, r=0, t=20, b=0),
                      legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center",
                                  font=dict(color=COR_TEXTO_CINZA, size=13)))
    else:
        if area == REGIAO:   # uma barra por município
            barras = dados.set_index("Nome")["Total"].sort_values()
        else:                # um município: uma barra por tipo de veículo
            barras = por_tipo.sort_values()
        fig = go.Figure(go.Bar(
            y=barras.index, x=barras.values, orientation="h", marker_color=COR_TRANSPORTE,
            text=[formatar(v) for v in barras.values], textposition="outside",
            textfont=dict(color="#d0d0d0", size=13),
            hovertemplate="%{y}<br>%{x:,.0f} veículos<extra></extra>",
        ))
        layout_escuro(fig, barcornerradius=5, bargap=0.4, margin=dict(l=0, r=50, t=20, b=0), showlegend=False)
        fig.update_xaxes(visible=False, range=[0, barras.max() * 1.25])
        fig.update_yaxes(showgrid=False, tickfont=dict(color=COR_TEXTO_CINZA, size=13))
    figura_em_iframe(fig)
    return area, dados


def descricao_frota(resultado):
    area, dados = resultado
    tabela = dados[["Nome"] + TIPOS_FROTA + ["Total"]]
    conteudo_json = json.dumps({
        "data": [{"name": tipo, "data": tabela[tipo].tolist()} for tipo in TIPOS_FROTA],
        "categories": tabela["Nome"].tolist()}, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = tabela.rename(columns={"Nome": "Município"}).to_csv(index=False, sep=";").encode("utf-8-sig")
    habitantes = filtrar_regiao(df_regiao_idades, area)["Habitantes"].sum()
    por_mil = dados["Total"].sum() / habitantes * 1000
    dados_rel = relacionados_transporte(
        "https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-2026",
        f"Ministério dos Transportes / SENATRAN, frota por município e tipo – {MES_FROTA}",
        f"Veículos com placa registrados em cada município (barcos não entram, pois não têm registro no "
        f"Detran). {area}: {formatar(dados['Total'].sum())} veículos, cerca de {por_mil:.0f} para cada "
        "1.000 habitantes (Censo 2022). Motocicletas incluem motonetas, ciclomotores, triciclos e quadriciclos.")
    titulo = "Frota de veículos"
    painel_descricao("frota_cn", DESCRICAO_FROTA, dados_rel,
                     lambda: janela_reportar(titulo, area),
                     lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
                     lambda: janela_incorporar("213cn", titulo))


# --- CARTÃO: INFORMAÇÕES CARTOGRÁFICAS DA CALHA NORTE (bike_map da Grande Taipei) ---
# Estradas principais e sedes municipais do OpenStreetMap, geradas pelo preparar_cartografia_regiao.py
with open(arquivo_dados("regiao_estradas.geojson"), encoding="utf-8") as arquivo:
    geojson_estradas = json.load(arquivo)
df_sedes = pd.read_csv(arquivo_dados("regiao_sedes.csv"), sep=";", dtype={"codigo": str})
CORES_ESTRADAS = {"Rodovias principais": "#a0b8e8", "Estradas vicinais": "#b7ff98"}


def municipio_de_cada_estrada():
    """Município onde fica o meio de cada trecho de estrada (para a caixa de área do cartão)."""
    poligonos = [(f["properties"]["nome"], shapely.geometry.shape(f["geometry"])) for f in geojson_regiao["features"]]
    linhas = []
    for estrada in geojson_estradas["features"]:
        meio = shapely.geometry.shape(estrada["geometry"]).interpolate(0.5, normalized=True)
        nome = next((n for n, p in poligonos if p.contains(meio)), None)
        linhas.append({**estrada["properties"], "Nome": nome})
    return pd.DataFrame(linhas)


df_estradas = municipio_de_cada_estrada()

DESCRICAO_VIAS_CN = f"""
**Descrição do componente ( ID: 217 | Index: road_map | City: calhanorte )**

Mostra as estradas que ligam as sedes e as comunidades da Calha Norte paraense ({MUNICIPIOS_REGIAO}):
rodovias principais (como a PA-254, que liga Oriximiná, Óbidos, Curuá, Alenquer, Monte Alegre e Prainha) e
estradas vicinais, junto com os limites e as sedes dos municípios.

**Exemplo de uso**

Na Calha Norte muitas comunidades só são alcançadas por rio; o mapa mostra onde existe ligação por estrada
entre os municípios e onde ela falta, o que ajuda no planejamento de obras, do escoamento da produção e do
transporte escolar e de saúde entre as sedes.

**Dados relacionados**
"""


def grafico_vias_regiao():
    area = cabecalho("vias_cn", "Informações cartográficas da rede viária",
                     "OpenStreetMap | Estradas da Calha Norte", OPCOES_REGIAO, atualizacao="OpenStreetMap")
    estradas = filtrar_regiao(df_estradas, area)
    sedes = filtrar_regiao(df_sedes, area)
    # Legenda do mapa, como o MapLegend do Taipei
    linhas = "".join(
        f'<div class="legenda-via"><span class="linha-via" style="background:{cor}"></span>{tipo}'
        f'<span class="cartao-fonte">&nbsp;&nbsp;{formatar_km(estradas.loc[estradas["tipo"] == tipo, "comprimento_m"].sum())}'
        '</span></div>'
        for tipo, cor in CORES_ESTRADAS.items()
    )
    linhas += ('<div class="legenda-via"><span class="linha-via" style="background:transparent;'
               'border:2px solid #ffffff; height:14px"></span>Limites municipais</div>'
               f'<div class="legenda-via"><span class="legenda-ponto" style="background:#F65658; margin:0 17px 0 5px">'
               f'</span>Sedes municipais<span class="cartao-fonte">&nbsp;&nbsp;{len(sedes)}</span></div>')
    st.markdown(f'<div class="lista-legenda">{linhas}</div>', unsafe_allow_html=True)
    with st.container(horizontal=True, key=k("botoes_mapa_vias_cn")):
        for rotulo, icone in (("Filtrar mapa", "tune"), ("Dados", "map")):
            if st.button(rotulo, icon=f":material/{icone}:", key=k(f"vias_cn_{icone}"),
                         help="Abre a camada na Comparação de mapas"):
                st.session_state.pagina = "mapa"
                st.session_state.ligar_estradas_cn = True
                st.rerun()
    return area, estradas


def descricao_vias_regiao(resultado):
    area, estradas = resultado
    resumo = "; ".join(f"{tipo}: {int((estradas['tipo'] == tipo).sum())} trechos, "
                       f"{formatar_km(estradas.loc[estradas['tipo'] == tipo, 'comprimento_m'].sum())}"
                       for tipo in CORES_ESTRADAS)
    dados = AVISO_PADRAO + f"""
<div class="texto-cinza"><a class="link-dados" href="https://www.openstreetmap.org/#map=7/-1.2/-55.0"
target="_blank" rel="noreferrer">Conjunto de dados - 1<br>(OpenStreetMap, © colaboradores do OpenStreetMap)</a></div>
<div class="texto-cinza pequeno">
Estradas mapeadas por voluntários no OpenStreetMap (licença ODbL): rodovias principais (classes trunk, primary e
secondary) e estradas vicinais (tertiary e unclassified). Ramais, ruas das cidades e trilhas não entram. Limites
dos municípios: IBGE. {area}: {resumo}.
</div>""" + RODAPE_COLABORADORES.format(logo_colaborador=logo_colaborador)
    conteudo_json = json.dumps(geojson_estradas, ensure_ascii=False).encode("utf-8")
    conteudo_csv = (estradas.rename(columns={"Nome": "Município", "comprimento_m": "comprimento (m)",
                                             "classe_osm": "classe OSM", "ref": "referência"})
                    .to_csv(index=False, sep=";").encode("utf-8-sig"))
    titulo = "Informações cartográficas da rede viária"
    painel_descricao("vias_cn", DESCRICAO_VIAS_CN, dados,
                     lambda: janela_reportar(titulo, area),
                     lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
                     lambda: janela_incorporar("217cn", titulo))


# --- CONTAS DE USUÁRIO (login) ---
# Como no Taipei, favoritos e o painel privado só existem para quem entrou com uma conta.
# As contas ficam num arquivo local; a senha é guardada só como resumo (hash), nunca em texto.
ARQ_USUARIOS = os.path.join(PASTA_USUARIOS, "usuarios_painel.json")
# Área de administração: problemas reportados e as mudanças feitas pelos administradores
ARQ_PROBLEMAS = os.path.join(PASTA_USUARIOS, "problemas_painel.json")
ARQ_ADMIN = os.path.join(PASTA_USUARIOS, "admin_painel.json")


def carregar_json(caminho, vazio):
    if not os.path.exists(caminho):
        return vazio
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


# Mudanças da administração (painéis públicos, componentes, colaboradores), lidas uma vez a cada execução
CONFIG_ADMIN = carregar_json(ARQ_ADMIN, {})


def componente_editado(chave):
    """O que a administração mudou neste componente (título, fonte, descrição...), ou {}."""
    return CONFIG_ADMIN.get("componentes", {}).get(chave, {})


def e_admin():
    """Quem entrou é administrador? (lê o arquivo, para valer na hora em que outro admin mudar)"""
    usuario = st.session_state.get("usuario")
    return bool(usuario and carregar_usuarios().get(usuario["email"], {}).get("admin"))


def carregar_usuarios():
    if not os.path.exists(ARQ_USUARIOS):
        return {}
    with open(ARQ_USUARIOS, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_usuarios(usuarios):
    with open(ARQ_USUARIOS, "w", encoding="utf-8") as arquivo:
        json.dump(usuarios, arquivo, ensure_ascii=False, indent=2)


def resumo_senha(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), 200_000).hex()


# Sessões abertas: uma chave aleatória no endereço da página (?sessao=...) diz quem entrou,
# para o login continuar depois de atualizar a página (F5 / Ctrl+R)
ARQ_SESSOES = os.path.join(PASTA_USUARIOS, "sessoes_painel.json")


def carregar_sessoes():
    if not os.path.exists(ARQ_SESSOES):
        return {}
    with open(ARQ_SESSOES, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_sessoes(sessoes):
    with open(ARQ_SESSOES, "w", encoding="utf-8") as arquivo:
        json.dump(sessoes, arquivo, ensure_ascii=False, indent=2)


def entrar(email, nova_sessao=True):
    usuario = carregar_usuarios()[email]
    st.session_state.usuario = {"email": email, "nome": usuario["nome"], "admin": bool(usuario.get("admin"))}
    st.session_state.favoritos = set(usuario.get("favoritos", []))
    st.session_state.paineis_pessoais = usuario.get("paineis", [])
    st.session_state.pontos_de_vista = usuario.get("pontos_de_vista", [])
    if nova_sessao:
        # Guarda a hora do login, mostrada em "Configurações do usuário" (como o login_at do Taipei)
        usuarios = carregar_usuarios()
        usuarios[email]["ultimo_login"] = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
        salvar_usuarios(usuarios)
        chave = secrets.token_urlsafe(24)
        sessoes = carregar_sessoes()
        sessoes[chave] = email
        salvar_sessoes(sessoes)
        st.query_params["sessao"] = chave


def sair():
    sessoes = carregar_sessoes()
    if sessoes.pop(st.query_params.get("sessao"), None):
        salvar_sessoes(sessoes)
    st.query_params.pop("sessao", None)
    st.session_state.usuario = None
    st.session_state.favoritos = set()
    st.session_state.paineis_pessoais = []
    st.session_state.pontos_de_vista = []


def retomar_sessao():
    """Depois de atualizar a página, entra de novo com a chave de sessão do endereço."""
    email = carregar_sessoes().get(st.query_params.get("sessao"))
    if email in carregar_usuarios():
        entrar(email, nova_sessao=False)
    else:
        st.query_params.pop("sessao", None)   # chave velha ou apagada


def salvar_favoritos():
    if st.session_state.usuario:
        usuarios = carregar_usuarios()
        usuarios[st.session_state.usuario["email"]]["favoritos"] = sorted(st.session_state.favoritos)
        salvar_usuarios(usuarios)


def salvar_paineis():
    if st.session_state.usuario:
        usuarios = carregar_usuarios()
        usuarios[st.session_state.usuario["email"]]["paineis"] = st.session_state.paineis_pessoais
        salvar_usuarios(usuarios)


def limpar_config_usuario():
    st.session_state.pop("cfg_nome", None)


@st.dialog("Configurações do usuário", width="small", on_dismiss=limpar_config_usuario)
def janela_config_usuario():
    """Janela "Configurações do usuário" (UserSettings do Taipei): o nome pode ser mudado; conta, tipo de
    usuário e último login só aparecem."""
    email = st.session_state.usuario["email"]
    nome_atual = st.session_state.usuario["nome"]
    dados = carregar_usuarios().get(email, {})
    if "cfg_nome" not in st.session_state:
        st.session_state.cfg_nome = nome_atual
    # Até 10 letras, como no Taipei (ou mais, se o nome da conta já for maior que isso)
    nome = st.text_input("Nome do usuário", max_chars=max(10, len(nome_atual)), key="cfg_nome").strip()
    st.text_input("Conta", value=email, disabled=True)
    st.text_input("Tipo de usuário", value="Administrador" if dados.get("admin") else "Usuário comum",
                  disabled=True)
    st.text_input("Último login", value=dados.get("ultimo_login", "—"), disabled=True)
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Alterar informações do usuário", type="primary", key="cfg_salvar"):
            if not nome or nome == nome_atual or not dados:
                st.session_state.aviso = "O nome do usuário não mudou"
            else:
                usuarios = carregar_usuarios()
                usuarios[email]["nome"] = nome
                salvar_usuarios(usuarios)
                st.session_state.usuario["nome"] = nome
                st.session_state.aviso = "Informações do usuário atualizadas"
            limpar_config_usuario()
            st.rerun()


# Links do texto "Ao entrar, você declara..." da janela de login (troque pelos endereços oficiais
# quando a Prefeitura tiver uma página própria do painel e da política de privacidade)
LINK_PAINEL = "https://www.oriximina.pa.gov.br"
LINK_POLITICA_PRIVACIDADE = "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm"


def limpar_login():
    for chave in ("login_email", "login_senha", "novo_nome", "login_modo", "login_erro", "login_aviso",
                  "rec_email", "rec_codigo", "rec_senha", "rec_senha2", "rec_etapa", "rec_para", "rec_erro",
                  "rec_info"):
        st.session_state.pop(chave, None)


# --- ESQUECI A SENHA: código de 6 números enviado por e-mail ---
# A conta que envia os e-mails fica no .streamlit/secrets.toml (nunca no código), na parte [email]:
#   servidor = "smtp.gmail.com", porta = 587, usuario = "conta@gmail.com", senha = "senha de app",
#   remetente = "Painel Oriximiná <conta@gmail.com>"
ARQ_RECUPERACAO = os.path.join(PASTA_USUARIOS, "recuperacao_senha.json")
VALIDADE_CODIGO = 15 * 60      # segundos
TENTATIVAS_CODIGO = 5
ESPERA_REENVIO = 60            # segundos entre um pedido de código e outro


def config_email():
    """Dados da conta que envia os e-mails, ou None se ainda não foi configurada."""
    try:
        cfg = dict(st.secrets.get("email", {}))
    except Exception:   # sem arquivo secrets.toml
        return None
    return cfg if all(cfg.get(campo) for campo in ("servidor", "usuario", "senha")) else None


def enviar_email(para, assunto, texto):
    cfg = config_email()
    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = cfg.get("remetente") or cfg["usuario"]
    mensagem["To"] = para
    mensagem.set_content(texto)
    porta = int(cfg.get("porta", 587))
    if porta == 465:   # conexão já protegida desde o início
        with smtplib.SMTP_SSL(cfg["servidor"], porta, timeout=30) as servidor:
            servidor.login(cfg["usuario"], cfg["senha"])
            servidor.send_message(mensagem)
    else:
        with smtplib.SMTP(cfg["servidor"], porta, timeout=30) as servidor:
            if cfg.get("tls", True):
                servidor.starttls()
            servidor.login(cfg["usuario"], cfg["senha"])
            servidor.send_message(mensagem)


def carregar_recuperacao():
    if not os.path.exists(ARQ_RECUPERACAO):
        return {}
    with open(ARQ_RECUPERACAO, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_recuperacao(pedidos):
    with open(ARQ_RECUPERACAO, "w", encoding="utf-8") as arquivo:
        json.dump(pedidos, arquivo, ensure_ascii=False, indent=2)


def pedir_codigo(email):
    """Manda o código para o e-mail, se ele tiver conta. Devolve "" ou a mensagem de erro."""
    agora = time.time()
    pedidos = {e: p for e, p in carregar_recuperacao().items() if p["expira"] > agora}   # tira os vencidos
    anterior = pedidos.get(email)
    if anterior and agora - anterior["enviado"] < ESPERA_REENVIO:
        return f"Espere {int(ESPERA_REENVIO - (agora - anterior['enviado'])) + 1} segundos para pedir outro código."
    usuario = carregar_usuarios().get(email)
    if usuario and usuario.get("ativo") is not False:
        codigo = f"{secrets.randbelow(10 ** 6):06d}"
        sal = secrets.token_hex(16)
        try:
            enviar_email(email, "Código para criar uma senha nova – Painel Oriximiná",
                         f"Olá, {usuario['nome']}.\n\n"
                         f"O seu código para criar uma senha nova no Painel Oriximiná é: {codigo}\n\n"
                         f"Ele vale por {VALIDADE_CODIGO // 60} minutos. Se você não pediu, ignore este e-mail: "
                         "a sua senha continua a mesma.\n\nPainel Oriximiná")
        except Exception:
            return "Não foi possível enviar o e-mail agora. Tente de novo mais tarde."
        # O código fica guardado embaralhado (como as senhas), nunca em texto aberto
        pedidos[email] = {"codigo": resumo_senha(codigo, sal), "sal": sal, "expira": agora + VALIDADE_CODIGO,
                          "enviado": agora, "tentativas": 0}
    salvar_recuperacao(pedidos)
    return ""   # mesma resposta com ou sem conta: ninguém descobre quais e-mails estão cadastrados


def trocar_senha_com_codigo(email, codigo, nova):
    """Confere o código e troca a senha. Devolve "" ou a mensagem de erro."""
    pedidos = carregar_recuperacao()
    pedido = pedidos.get(email)
    if not pedido or time.time() > pedido["expira"]:
        return "O código venceu ou não existe. Peça um código novo."
    if pedido["tentativas"] >= TENTATIVAS_CODIGO:
        return "Muitas tentativas erradas. Peça um código novo."
    if resumo_senha(codigo, pedido["sal"]) != pedido["codigo"]:
        pedido["tentativas"] += 1
        salvar_recuperacao(pedidos)
        restam = TENTATIVAS_CODIGO - pedido["tentativas"]
        return f"Código incorreto. Restam {restam} tentativas." if restam else \
            "Código incorreto. Peça um código novo."
    usuarios = carregar_usuarios()
    sal = secrets.token_hex(16)
    usuarios[email]["sal"] = sal
    usuarios[email]["senha"] = resumo_senha(nova, sal)
    salvar_usuarios(usuarios)
    pedidos.pop(email)
    salvar_recuperacao(pedidos)
    # Quem estava logado com a senha antiga sai (em outros computadores também)
    sessoes = carregar_sessoes()
    salvar_sessoes({chave: e for chave, e in sessoes.items() if e != email})
    return ""


def voltar_ao_login(aviso=None, email=None):
    for chave in ("rec_codigo", "rec_senha", "rec_senha2", "rec_etapa", "rec_para", "rec_erro", "rec_info"):
        st.session_state.pop(chave, None)
    st.session_state.login_modo = None
    st.session_state.pop("login_erro", None)
    if aviso:
        st.session_state.login_aviso = aviso
    if email:
        st.session_state.login_email = email


def formulario_recuperar():
    """Esqueci a senha: 1) e-mail -> código por e-mail; 2) código e senha nova."""
    st.markdown('<div class="login-rec-titulo">Esqueci a senha</div>', unsafe_allow_html=True)
    if not config_email():
        st.markdown('<div class="login-erro">O envio de e-mail ainda não foi configurado neste painel. '
                    'Fale com o administrador para trocar a sua senha.</div>', unsafe_allow_html=True)
    elif st.session_state.get("rec_etapa") != "codigo":
        st.markdown('<div class="login-rec-texto">Digite o e-mail da sua conta. Vamos enviar um código de 6 '
                    'números para você criar uma senha nova.</div>', unsafe_allow_html=True)
        email = st.text_input("E-mail", key="rec_email", autocomplete="username").strip().lower()
        if st.session_state.get("rec_erro"):
            st.markdown(f'<div class="login-erro">{st.session_state.rec_erro}</div>', unsafe_allow_html=True)
        with st.container(horizontal=True, horizontal_alignment="center", key="botao_rec_enviar"):
            enviar = st.button("Enviar código", key="rec_enviar")
        if enviar:
            if "@" not in email:
                st.session_state.rec_erro = "Digite um e-mail válido."
            else:
                with st.spinner("Enviando o código..."):
                    erro = pedir_codigo(email)
                st.session_state.rec_erro = erro
                if not erro:
                    st.session_state.rec_etapa = "codigo"
                    st.session_state.rec_para = email
                    st.session_state.rec_info = (f"Se <b>{html.escape(email)}</b> tiver conta no painel, enviamos um "
                                                 "código para ele. Veja também a caixa de spam.")
            st.rerun(scope="fragment")
    else:
        para = st.session_state.rec_para
        st.markdown(f'<div class="login-rec-texto">{st.session_state.get("rec_info", "")}</div>',
                    unsafe_allow_html=True)
        codigo = st.text_input("Código (6 números)", key="rec_codigo", max_chars=6,
                               autocomplete="one-time-code").strip()
        nova = st.text_input("Senha nova (mínimo 6 caracteres)", type="password", key="rec_senha",
                             autocomplete="new-password")
        nova2 = st.text_input("Repita a senha nova", type="password", key="rec_senha2", autocomplete="new-password")
        with st.container(key="script_login"):
            script_login()
        if st.session_state.get("rec_erro"):
            st.markdown(f'<div class="login-erro">{st.session_state.rec_erro}</div>', unsafe_allow_html=True)
        with st.container(horizontal=True, horizontal_alignment="center", key="botao_rec_trocar"):
            trocar = st.button("Trocar senha", key="rec_trocar")
        if trocar:
            if not (codigo.isdigit() and len(codigo) == 6):
                st.session_state.rec_erro = "Digite o código de 6 números que chegou no e-mail."
            elif len(nova) < 6:
                st.session_state.rec_erro = "A senha nova precisa ter pelo menos 6 caracteres."
            elif nova != nova2:
                st.session_state.rec_erro = "As duas senhas novas não são iguais."
            else:
                erro = trocar_senha_com_codigo(para, codigo, nova)
                if not erro:
                    voltar_ao_login("Senha trocada. Entre com a senha nova.", para)
                    st.rerun(scope="fragment")
                st.session_state.rec_erro = erro
            st.rerun(scope="fragment")
        with st.container(horizontal=True, horizontal_alignment="center", key="rec_reenviar_linha"):
            if st.button("Não chegou? Enviar outro código", type="tertiary", key="rec_reenviar"):
                erro = pedir_codigo(para)
                st.session_state.rec_erro = erro
                if not erro:
                    st.session_state.rec_info = "Enviamos um código novo. Use o mais recente."
                st.rerun(scope="fragment")
    with st.container(horizontal=True, horizontal_alignment="center", key="rec_voltar_linha"):
        if st.button("Voltar para entrar", type="tertiary", key="rec_voltar"):
            voltar_ao_login()
            st.rerun(scope="fragment")


def script_login():
    """O navegador preenche o e-mail e a senha guardados sem passar pelo campo; o Streamlit só guarda o
    valor quando o campo perde o foco. Ao apertar "Entrar", passa por cada campo para o valor valer."""
    st.iframe("""<script>
    const d = window.parent.document;
    if (!d.getElementById("script-login")) {
        const s = d.createElement("script");
        s.id = "script-login";
        s.textContent = `
            document.addEventListener("pointerdown", (ev) => {
                if (!ev.target.closest || !ev.target.closest(".st-key-confirmar_login button, .st-key-rec_trocar button")) return;
                document.querySelectorAll(".st-key-novo_nome input, .st-key-login_email input, "
                                          + ".st-key-login_senha input, .st-key-rec_codigo input, "
                                          + ".st-key-rec_senha input, .st-key-rec_senha2 input").forEach((campo) => {
                    campo.focus();
                    // Avisa o Streamlit do valor que está no campo (o preenchido pelo navegador). O React só
                    // percebe a mudança se o valor que ele lembra for outro: por isso esquece o lembrado antes
                    if (campo._valueTracker) campo._valueTracker.setValue("");
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(campo, campo.value);
                    campo.dispatchEvent(new Event("input", {bubbles: true}));
                    campo.blur();
                });
            }, true);
        `;
        d.head.appendChild(s);
    }
    </script>""", height=1)


@st.dialog(" ", width="small", on_dismiss=limpar_login)
def janela_login():
    # Janela de login igual à do Taipei: logo e título, e-mail, senha, botão redondo "Entrar"
    # e o texto de concordância embaixo. "Cadastre-se" fica num link pequeno, porque aqui
    # as contas são criadas pelo próprio painel.
    criando = st.session_state.get("login_modo") == "criar"
    logo = f'<img src="data:image/jpeg;base64,{logo_base64}" alt="Logo de Oriximiná">' if logo_colaborador else ""
    st.markdown(f'<div class="login-logo">{logo}<div><div class="login-titulo">Painel Estatístico</div>'
                '<div class="login-subtitulo">Painel de controle da cidade de Oriximiná</div></div></div>',
                unsafe_allow_html=True)
    if st.session_state.get("login_modo") == "recuperar":
        formulario_recuperar()
        return

    email_atual = st.session_state.get("login_email", "")
    senha_atual = st.session_state.get("login_senha", "")
    nome_atual = st.session_state.get("novo_nome", "")
    # Campos obrigatórios vazios ficam com a borda vermelha, como no Taipei
    vazios = [chave for chave, valor in (("login_email", email_atual), ("login_senha", senha_atual),
                                         ("novo_nome", nome_atual)) if not valor.strip()]
    st.markdown("<style>" + " ".join(
        f".st-key-{chave} [data-testid$='RootElement'] {{ border-color: #e5484d !important; }}" for chave in vazios
    ) + "</style>", unsafe_allow_html=True)

    if criando:
        nome = st.text_input("Nome", key="novo_nome", autocomplete="name").strip()
    # "autocomplete" diz ao navegador que são usuário e senha: ele oferece o login guardado e pergunta
    # se quer guardar depois de entrar (como no Taipei)
    email = st.text_input("E-mail", key="login_email", autocomplete="username").strip().lower()
    senha = st.text_input("Senha" + (" (mínimo 6 caracteres)" if criando else ""), type="password",
                          key="login_senha", autocomplete="new-password" if criando else "current-password")
    with st.container(key="script_login"):
        script_login()
    if not criando:
        with st.container(horizontal=True, horizontal_alignment="right", key="esqueci_linha"):
            if st.button("Esqueci a senha", type="tertiary", key="esqueci_senha"):
                st.session_state.login_modo = "recuperar"
                st.session_state.rec_email = email
                st.session_state.pop("login_erro", None)
                st.session_state.pop("login_aviso", None)
                st.rerun(scope="fragment")
    if st.session_state.get("login_aviso"):
        st.markdown(f'<div class="login-aviso">{st.session_state.login_aviso}</div>', unsafe_allow_html=True)
    if st.session_state.get("login_erro"):
        st.markdown(f'<div class="login-erro">{st.session_state.login_erro}</div>', unsafe_allow_html=True)

    with st.container(horizontal=True, horizontal_alignment="center", key="botao_login"):
        confirmar = st.button("Cadastrar" if criando else "Entrar", key="confirmar_login")
    if confirmar:
        st.session_state.pop("login_aviso", None)
        usuarios = carregar_usuarios()
        if criando:
            if not nome or "@" not in email or len(senha) < 6:
                st.session_state.login_erro = ("Preencha o nome, um e-mail válido e uma senha com pelo "
                                               "menos 6 caracteres.")
            elif email in usuarios:
                st.session_state.login_erro = "Já existe uma conta com esse e-mail."
            else:
                sal = secrets.token_hex(16)
                usuarios[email] = {"nome": nome, "sal": sal, "senha": resumo_senha(senha, sal), "favoritos": []}
                salvar_usuarios(usuarios)
                entrar(email)
                limpar_login()
                st.session_state.aviso = f"Cadastro feito. Bem-vindo(a), {nome}!"
                st.rerun()
        else:
            usuario = usuarios.get(email)
            if usuario and usuario.get("ativo") is False:
                # Conta desativada na área de administração ("Usuários")
                st.session_state.login_erro = "Esta conta está desativada. Fale com o administrador do painel."
                st.rerun(scope="fragment")
            if usuario and resumo_senha(senha, usuario["sal"]) == usuario["senha"]:
                entrar(email)
                limpar_login()
                st.session_state.aviso = f"Bem-vindo(a), {usuario['nome']}!"
                st.rerun()
            st.session_state.login_erro = "E-mail ou senha incorretos."
        st.rerun(scope="fragment")

    with st.container(horizontal=True, horizontal_alignment="center", key="trocar_login"):
        if st.button("Já tem conta? Entrar" if criando else "Não tem conta? Cadastre-se",
                     type="tertiary", key="alternar_login"):
            st.session_state.login_modo = None if criando else "criar"
            st.session_state.pop("login_erro", None)
            st.rerun(scope="fragment")

    st.markdown(
        '<div class="login-texto">Ao entrar, você declara que leu e concorda com<br>'
        f'<a href="{LINK_PAINEL}" target="_blank" rel="noopener">o Painel da Cidade de Oriximiná</a> e com '
        f'<a href="{LINK_POLITICA_PRIVACIDADE}" target="_blank" rel="noopener">a Política de Privacidade</a></div>'
        '<div class="login-texto">"Faça do Painel da Cidade de Oriximiná o seu painel"</div>',
        unsafe_allow_html=True)


# --- PAINÉIS, CARTÕES E CAMADAS DO MAPA ---
CARTOES = {
    "dependencia": (214, grafico_dependencia, descricao_dependencia),
    "emprego": (215, grafico_emprego, descricao_emprego),
    "divisoes": (216, grafico_divisoes, descricao_divisoes),
    "vias": (217, grafico_vias, descricao_vias),
    "indicadores": (218, grafico_indicadores, descricao_indicadores),
    # Mesmos cartões para a Calha Norte (a caixa de área escolhe a região ou um município)
    "dependencia_cn": ("214cn",
                       partial(grafico_dependencia, chave="dependencia_cn", opcoes_area=OPCOES_REGIAO,
                               dados_da_area=dependencia_regiao),
                       partial(descricao_dependencia, chave="dependencia_cn", descricao=DESCRICAO_DEPENDENCIA_CN,
                               relacionados=DADOS_RELACIONADOS_DEPENDENCIA_CN, id_componente="214cn")),
    "emprego_cn": ("215cn",
                   partial(grafico_emprego, chave="emprego_cn", opcoes_area=OPCOES_REGIAO,
                           dados_da_area=emprego_regiao),
                   partial(descricao_emprego, chave="emprego_cn", descricao=DESCRICAO_EMPREGO_CN,
                           relacionados=DADOS_RELACIONADOS_EMPREGO_CN, id_componente="215cn")),
    "divisoes_cn": ("216cn", grafico_divisoes_regiao, descricao_divisoes_regiao),
    "indicadores_cn": ("218cn",
                       partial(grafico_indicadores, chave="indicadores_cn", opcoes_area=OPCOES_REGIAO,
                               indicadores_da_area=indicadores_regiao),
                       descricao_indicadores_regiao),
    "tempo_cn": ("60cn", grafico_tempo, descricao_tempo),
    "meio_cn": ("212cn", grafico_meio, descricao_meio),
    "frota_cn": ("213cn", grafico_frota, descricao_frota),
    "vias_cn": ("217cn", grafico_vias_regiao, descricao_vias_regiao),
}
# Painéis do menu lateral: nome, ícone (Material Symbols, como no Taipei) e cartões
PAINEIS_PUBLICOS = {
    "cuidados": ("Cuidados de longo prazo", "elderly", ["dependencia", "emprego", "divisoes", "indicadores"]),
    "cartografia": ("Informações cartográficas", "public", ["vias"]),
    "cuidados_cn": ("Cuidados de longo prazo", "elderly",
                    ["dependencia_cn", "emprego_cn", "divisoes_cn", "indicadores_cn"]),
    "transporte_cn": ("Transporte prático", "directions_car", ["tempo_cn", "meio_cn", "frota_cn"]),
    "cartografia_cn": ("Informações cartográficas", "public", ["vias_cn"]),
}
# Grupos de painéis públicos no menu lateral (como "Painel de Taipei" e "Painel da Grande Taipei")
GRUPOS_MENU = {
    "Painel de Oriximiná": ["cuidados", "cartografia"],
    "Painel da Calha Norte": ["cuidados_cn", "transporte_cn", "cartografia_cn"],
}
PAINEL_FAVORITOS = ("Componentes favoritos", "favorite")
TITULOS_CARTOES = {
    "dependencia": "Razão de dependência e índice de envelhecimento",
    "emprego": "Estrutura de crescimento anual da população idosa empregada",
    "divisoes": "Divisões etárias em toda a cidade",
    "vias": "Informações cartográficas da rede viária",
    "indicadores": "Indicadores de cuidados de longo prazo",
    "dependencia_cn": "Razão de dependência e índice de envelhecimento (Calha Norte)",
    "emprego_cn": "Estrutura anual da população idosa empregada (Calha Norte)",
    "divisoes_cn": "Divisões etárias em toda a região (Calha Norte)",
    "indicadores_cn": "Indicadores de cuidados de longo prazo (Calha Norte)",
    "tempo_cn": "Tempo de deslocamento para o trabalho (Calha Norte)",
    "meio_cn": "Meio de transporte para o trabalho (Calha Norte)",
    "frota_cn": "Frota de veículos (Calha Norte)",
    "vias_cn": "Informações cartográficas da rede viária (Calha Norte)",
}
# Ícones que podem ser escolhidos para um painel pessoal (Material Symbols, como no Taipei)
ICONES_PAINEL = [
    "dashboard", "star", "bookmark", "favorite", "elderly", "family_restroom", "child_care", "school",
    "local_hospital", "health_and_safety", "work", "home", "apartment", "public", "map", "location_city",
    "directions_car", "directions_boat", "directions_bike", "water", "forest", "park", "agriculture",
    "bar_chart", "pie_chart", "analytics", "groups", "accessible",
]

# Camadas da página de mapa e de quais cartões elas vêm
CAMADAS = {
    "populacao": ("Divisões etárias – habitantes por setor censitário", "IBGE, Censo 2022"),
    "idosos": ("População de 60 anos ou mais por setor censitário", "IBGE, Censo 2022"),
    "bairros": ("Bairros da sede urbana", "Plano Diretor de Oriximiná, 2017"),
    "saude": ("Estabelecimentos de saúde", "IBGE, CNEFE 2022"),
    "ensino": ("Estabelecimentos de ensino", "IBGE, CNEFE 2022"),
    "vias": ("Rede viária da sede urbana", "OpenStreetMap"),
    "municipios_cn": ("Municípios da Calha Norte – habitantes", "IBGE, Censo 2022"),
    "frota_cn": ("Municípios da Calha Norte – frota de veículos", "SENATRAN"),
    "estradas_cn": ("Estradas da Calha Norte", "OpenStreetMap"),
    "limites_cn": ("Limites municipais", "IBGE, malha municipal"),
    "sedes_cn": ("Sedes municipais", "OpenStreetMap"),
}
CAMADAS_DO_CARTAO = {
    "divisoes": ["populacao", "bairros", "ensino"],
    "indicadores": ["idosos", "saude"],
    "dependencia": ["idosos"],
    "emprego": [],
    "vias": ["vias"],
    "divisoes_cn": ["municipios_cn"],
    "indicadores_cn": ["municipios_cn"],
    "dependencia_cn": [],
    "emprego_cn": [],
    "tempo_cn": [],
    "meio_cn": [],
    "frota_cn": ["frota_cn"],
    "vias_cn": ["estradas_cn", "limites_cn", "sedes_cn"],
}
COR_PONTOS = {"saude": "#F65658", "ensino": "#F8CF58"}
TIPO_PONTO = {"saude": "Estabelecimento de saúde", "ensino": "Estabelecimento de ensino"}
df_pontos = pd.read_csv(arquivo_dados("pontos_oriximina.csv"), sep=";")


def painel_pessoal(painel):
    """O painel pessoal com esse código (ex.: "pessoal_3"), ou None."""
    return next((p for p in st.session_state.paineis_pessoais if f"pessoal_{p['id']}" == painel), None)


def cartoes_do_painel(painel):
    if painel == "favoritos":
        return [c for c in CARTOES if c in st.session_state.favoritos]
    if painel.startswith("pessoal_"):
        return [c for c in painel_pessoal(painel)["cartoes"] if c in CARTOES]
    return PAINEIS_PUBLICOS[painel][2]


def nome_do_painel(painel):
    if painel == "favoritos":
        return PAINEL_FAVORITOS
    if painel.startswith("pessoal_"):
        pessoal = painel_pessoal(painel)
        return pessoal["nome"], pessoal["icone"]
    return PAINEIS_PUBLICOS[painel][:2]


# --- PAINEL PESSOAL: ADICIONAR, EDITAR E EXCLUIR (AddEditDashboards do Taipei) ---
def limpar_painel_pessoal():
    for chave in ("pp_nome", "pp_busca", "pp_icone", "pp_cartoes", "pp_excluir", "pp_escolhendo", "pp_selecao",
                  "pp_busca_nome", "pp_busca_indice", "pp_guardado", "pp_sem_nome"):
        st.session_state.pop(chave, None)


# --- "Adicionar componente ao painel": escolha dos cartões, aberta pelo "+" da janela do painel.
# O Streamlit não abre uma janela dentro de outra, então ela toma o lugar do formulário.
# Campos do formulário que o Streamlit apaga enquanto não estão na tela: ficam guardados à parte
CAMPOS_FORMULARIO_PAINEL = ("pp_nome", "pp_busca", "pp_icone", "pp_excluir")


def abrir_escolha():
    st.session_state.pp_guardado = {c: st.session_state[c] for c in CAMPOS_FORMULARIO_PAINEL
                                    if c in st.session_state}
    st.session_state.pp_escolhendo = True
    st.session_state.pp_selecao = []


def fechar_escolha():
    st.session_state.update(st.session_state.pop("pp_guardado", {}))
    for chave in ("pp_escolhendo", "pp_selecao", "pp_busca_nome", "pp_busca_indice"):
        st.session_state.pop(chave, None)


def confirmar_escolha():
    st.session_state.pp_cartoes.extend(st.session_state.pp_selecao)
    fechar_escolha()


def alternar_escolha(chave):
    selecao = st.session_state.pp_selecao
    if chave in selecao:
        selecao.remove(chave)
    else:
        selecao.append(chave)


def html_resumo_cartao(chave):
    """Resumo do cartão (o mesmo do catálogo) em HTML, para os cartões clicáveis da escolha."""
    descricao, fonte, atualizacao, icone = RESUMO_CARTOES[chave]
    filtro = '<span class="catalogo-filtro">Filtrar mapa</span>' if CAMADAS_DO_CARTAO[chave] else ""
    return (
        f'<div class="resumo-topo"><div class="catalogo-titulo">{TITULOS_CARTOES[chave]}</div>'
        f'<span class="cartao-atualizacao">{atualizacao}</span></div>'
        f'<div class="catalogo-descricao">{descricao}</div><div class="catalogo-fonte">{fonte} | {atualizacao}</div>'
        f'<div class="resumo-rodape"><div class="catalogo-etiquetas">{etiquetas_do_cartao(chave)}'
        f'<div class="catalogo-index">Index: {chave}</div></div><span class="catalogo-icone">{icone}</span></div>'
        f'{filtro}'
    )


def escolher_componentes():
    selecao = st.session_state.pp_selecao
    st.markdown('<div class="escolha-titulo">Adicionar componente ao painel</div>', unsafe_allow_html=True)
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="pp_escolha"):
        nome = st.text_input("Nome", placeholder="Pesquisar por nome", key="pp_busca_nome", width=200,
                             label_visibility="collapsed").strip().lower()
        indice = st.text_input("Índice", placeholder="Pesquisar por índice", key="pp_busca_indice", width=200,
                               label_visibility="collapsed").strip().lower()
        st.space("stretch")
        st.button("Cancelar", type="tertiary", key="pp_cancelar_escolha", on_click=fechar_escolha)
        st.button("Confirmar adição", icon=":material/add_chart:", key="pp_confirmar_escolha",
                  on_click=confirmar_escolha, disabled=not selecao)
    candidatos = [c for c in TITULOS_CARTOES if c not in st.session_state.pp_cartoes
                  and nome in f"{TITULOS_CARTOES[c]} {RESUMO_CARTOES[c][0]}".lower()
                  and indice in f"{CARTOES[c][0]} {c}".lower()]
    st.markdown(f'<div class="escolha-contagem">{len(candidatos)} componentes correspondem aos filtros | '
                f'Selecionados: {len(selecao)}</div>', unsafe_allow_html=True)
    # Cartão escolhido fica com a borda azul
    st.markdown("<style>" + " ".join(f".st-key-pp_resumo_{c} {{ border-color: #5a9cf8 !important; }}"
                                     for c in selecao) + "</style>", unsafe_allow_html=True)
    with st.container(height=520, border=False):
        for inicio in range(0, len(candidatos), 2):
            for coluna, chave in zip(st.columns(2, gap="medium"), candidatos[inicio:inicio + 2]):
                with coluna, st.container(key=f"pp_resumo_{chave}"):
                    st.markdown(html_resumo_cartao(chave), unsafe_allow_html=True)
                    # Botão invisível por cima do cartão inteiro: clicar marca ou desmarca
                    st.button("Selecionar", key=f"pp_escolher_{chave}", on_click=alternar_escolha, args=(chave,))


def reordenar_componentes():
    """Recebe do script de arrastar a nova ordem dos quadradinhos e aplica na lista do painel."""
    try:
        ordem = json.loads(st.session_state.pp_ordem or "[]")
    except ValueError:
        ordem = []
    st.session_state.pp_ordem = ""
    if isinstance(ordem, list) and sorted(ordem) == sorted(st.session_state.pp_cartoes):
        st.session_state.pp_cartoes[:] = ordem


def mover_componente(chave, passo):
    cartoes = st.session_state.pp_cartoes
    i = cartoes.index(chave)
    if 0 <= i + passo < len(cartoes):
        cartoes[i], cartoes[i + passo] = cartoes[i + passo], cartoes[i]


def script_arrastar_componentes():
    """Deixa os quadradinhos do painel pessoal arrastáveis. Ao soltar, manda a nova ordem para o campo
    escondido (o Streamlit desenha de novo na ordem certa; a página não mexe nos quadradinhos sozinha)."""
    st.iframe("""<script>
    const d = window.parent.document;
    if (!d.getElementById("script-arrastar-pp")) {
        const s = d.createElement("script");
        s.id = "script-arrastar-pp";
        s.textContent = `
            const LISTA = ".st-key-pp_lista_componentes";
            const ITEM = '[class*="st-key-pp_item_"]';
            const chaveDo = (el) => ([...el.classList].find(c => c.startsWith("st-key-pp_item_")) || "")
                .replace("st-key-pp_item_", "");
            const itemDo = (alvo) => alvo.closest && alvo.closest(LISTA + " " + ITEM);
            let arrastado = null;
            const limparMarcas = () => document.querySelectorAll(".pp-soltar-antes, .pp-soltar-depois")
                .forEach(el => el.classList.remove("pp-soltar-antes", "pp-soltar-depois"));
            // O quadradinho fica arrastável ao apertar o mouse nele (menos no ⓧ e nas setinhas)
            document.addEventListener("pointerdown", (ev) => {
                const item = itemDo(ev.target);
                if (item) item.draggable = !ev.target.closest("button");
            }, true);
            document.addEventListener("dragstart", (ev) => {
                const item = itemDo(ev.target);
                if (!item) return;
                arrastado = item;
                item.classList.add("pp-arrastando");
                ev.dataTransfer.effectAllowed = "move";
                ev.dataTransfer.setData("text/plain", chaveDo(item));
            });
            document.addEventListener("dragover", (ev) => {
                const item = arrastado && itemDo(ev.target);
                if (!item) return;
                ev.preventDefault();
                limparMarcas();
                if (item === arrastado) return;
                const caixa = item.getBoundingClientRect();
                item.classList.add(ev.clientX < caixa.left + caixa.width / 2 ? "pp-soltar-antes" : "pp-soltar-depois");
            });
            document.addEventListener("drop", (ev) => {
                const item = arrastado && itemDo(ev.target);
                if (!item) return;
                ev.preventDefault();
                if (item === arrastado) return;
                const caixa = item.getBoundingClientRect();
                const depois = ev.clientX >= caixa.left + caixa.width / 2;
                const ordem = [...document.querySelectorAll(LISTA + " " + ITEM)]
                    .filter(el => el !== arrastado).map(chaveDo);
                ordem.splice(ordem.indexOf(chaveDo(item)) + (depois ? 1 : 0), 0, chaveDo(arrastado));
                const campo = document.querySelector(".st-key-pp_ordem input");
                campo.focus();
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(
                    campo, JSON.stringify(ordem));
                campo.dispatchEvent(new Event("input", {bubbles: true}));
                campo.blur();
            });
            document.addEventListener("dragend", () => {
                if (arrastado) arrastado.classList.remove("pp-arrastando");
                arrastado = null;
                limparMarcas();
            });
        `;
        d.head.appendChild(s);
    }
    </script>""", height=1)


def formulario_painel_pessoal(existente):
    if "pp_cartoes" not in st.session_state:   # primeira vez que a janela abre: preenche os campos
        st.session_state.pp_nome = existente["nome"] if existente else ""
        st.session_state.pp_icone = existente["icone"] if existente else ICONES_PAINEL[0]
        st.session_state.pp_cartoes = list(existente["cartoes"]) if existente else []

    if st.session_state.get("pp_escolhendo"):
        escolher_componentes()
        return
    nome_atual = st.session_state.get("pp_nome", "")
    cartoes = st.session_state.pp_cartoes
    # Como no Taipei: título e "Confirmar" em cima, e embaixo dois quadros lado a lado
    # (nome e ícone à esquerda; componentes do painel à direita)
    topo = st.container(horizontal=True, horizontal_alignment="right", key="controles_painel_pessoal")
    col_dados, col_componentes = st.columns(2, gap="medium")
    with col_dados, st.container(border=True, height=440, key="pp_quadro_dados"):
        if not nome_atual.strip():
            st.markdown("<style>.st-key-pp_nome [data-testid$='RootElement'] "
                        "{ border-color: #e5484d !important; }</style>", unsafe_allow_html=True)
        nome = st.text_input(f"Nome* ({len(nome_atual)}/10)", max_chars=10, key="pp_nome",
                             placeholder="Meu painel")
        if st.session_state.get("pp_sem_nome") and not nome.strip():
            st.markdown('<div style="color:#e5484d; font-size:0.9rem;">Dê um nome ao painel antes de confirmar.'
                        '</div>', unsafe_allow_html=True)
        busca = st.text_input("Ícone*", placeholder="Pesquisar ícone", key="pp_busca").strip().lower()
        icones = [i for i in ICONES_PAINEL if busca.replace(" ", "_") in i] or ICONES_PAINEL
        if st.session_state.get("pp_icone") and st.session_state.pp_icone not in icones:
            icones = [st.session_state.pp_icone] + icones
        icone = st.pills("Ícone", icones, format_func=lambda i: f":material/{i}:", key="pp_icone",
                         label_visibility="collapsed") or ICONES_PAINEL[0]
        excluir = existente and st.checkbox("Ativar a exclusão do painel", key="pp_excluir")

    with col_componentes, st.container(border=True, height=440, key="pp_quadro_componentes"):
        st.markdown('<div class="catalogo-fonte">Adicionar componentes do painel (arraste os quadradinhos '
                    'para mudar a ordem)</div>', unsafe_allow_html=True)
        # Campo escondido: o script de arrastar escreve aqui a nova ordem (como o draggable do Taipei)
        st.text_input("Ordem dos componentes", key="pp_ordem", label_visibility="collapsed",
                      on_change=reordenar_componentes)
        with st.container(key="pp_script_arrastar"):
            script_arrastar_componentes()
        # Como no Taipei: um quadradinho cinza por componente (ID e nome), com ⓧ para tirar,
        # e o quadro tracejado "+" no fim, que abre a escolha dos componentes
        with st.container(horizontal=True, gap="small", key="pp_lista_componentes"):
            for chave in cartoes:
                titulo = TITULOS_CARTOES[chave]
                with st.container(gap=None, width=92, key=f"pp_item_{chave}"):
                    st.markdown(f'<div class="pp-item-id">{CARTOES[chave][0]}</div>'
                                f'<div class="pp-item-titulo" title="{titulo}">{titulo}</div>',
                                unsafe_allow_html=True)
                    st.button("", icon=":material/cancel:", type="tertiary", key=f"pp_tirar_{chave}",
                              on_click=cartoes.remove, args=(chave,), help="Tirar do painel")
                    # Em tela de toque (celular), onde não dá para arrastar, setinhas ‹ › mudam a ordem
                    with st.container(horizontal=True, gap=None, key=f"pp_setas_{chave}"):
                        st.button("", icon=":material/chevron_left:", type="tertiary", key=f"pp_antes_{chave}",
                                  on_click=mover_componente, args=(chave, -1), help="Mover para antes")
                        st.button("", icon=":material/chevron_right:", type="tertiary", key=f"pp_depois_{chave}",
                                  on_click=mover_componente, args=(chave, 1), help="Mover para depois")
            if any(c not in cartoes for c in TITULOS_CARTOES):
                st.button("", icon=":material/add:", key="pp_adicionar", on_click=abrir_escolha)

    with topo:
        if excluir and st.button("Excluir painel", key="excluir_painel_pessoal"):
            st.session_state.paineis_pessoais = [p for p in st.session_state.paineis_pessoais
                                                 if p["id"] != existente["id"]]
            salvar_paineis()
            limpar_painel_pessoal()
            st.session_state.painel = "cuidados"
            st.session_state.aviso = "Painel excluído"
            st.rerun()
        # Sempre visível, ao lado do título (como no Taipei); sem nome, avisa em vermelho embaixo do campo
        if st.button("Confirmar alteração" if existente else "Confirmar adição",
                     type="primary", key="confirmar_painel_pessoal"):
            if not nome.strip():
                st.session_state.pp_sem_nome = True
                st.rerun(scope="fragment")
            cartoes = list(cartoes)
            if existente:
                existente.update(nome=nome.strip(), icone=icone, cartoes=cartoes)
                painel_id = existente["id"]
            else:
                painel_id = max([p["id"] for p in st.session_state.paineis_pessoais], default=0) + 1
                st.session_state.paineis_pessoais.append(
                    {"id": painel_id, "nome": nome.strip(), "icone": icone, "cartoes": cartoes})
            salvar_paineis()
            limpar_painel_pessoal()
            st.session_state.painel = f"pessoal_{painel_id}"
            st.session_state.pagina = "painel"
            st.session_state.aviso = "Painel salvo"
            st.rerun()


@st.dialog("Adicionar painel", width="large", on_dismiss=limpar_painel_pessoal)
def janela_adicionar_painel():
    formulario_painel_pessoal(None)


@st.dialog("Editar painel", width="large", on_dismiss=limpar_painel_pessoal)
def janela_editar_painel(painel):
    formulario_painel_pessoal(painel_pessoal(painel))


# --- BARRA DE CIMA (NavBar do Taipei) ---
PAGINAS = {"catalogo": "Catálogo de componentes", "painel": "Visão geral do painel",
           "mapa": "Comparação de mapas"}


def barra_topo():
    logo = f'<img src="data:image/jpeg;base64,{logo_base64}" alt="Logo de Oriximiná">' if logo_colaborador else ""
    # Clicar no logo ou no nome atualiza a página e volta para o início, mantendo a conta de quem entrou
    sessao = st.query_params.get("sessao")
    endereco = f"./?sessao={html.escape(sessao)}" if sessao else "./"
    with st.container(key="barra_topo", horizontal=True, horizontal_alignment="distribute",
                      vertical_alignment="center"):
        # (dentro de um link o Markdown só aceita <span>, não <div>)
        st.markdown(f'<a class="topo-logo" href="{endereco}" target="_self" title="Atualizar o painel">{logo}<span>'
                    '<span class="topo-titulo">Painel Oriximiná</span>'
                    '<span class="topo-subtitulo">Painel de controle da cidade de Oriximiná</span></span></a>',
                    unsafe_allow_html=True, width="content")
        # No celular, como no Taipei: sem as abas, a tela cheia e a conta; as páginas ficam no ☰
        if not CELULAR:
            with st.container(horizontal=True, key="abas_topo", width="content", gap="small"):
                for pagina, rotulo in PAGINAS.items():
                    if st.button(rotulo, key=f"aba_topo_{pagina}", type="tertiary"):
                        st.session_state.pagina = pagina
                        st.rerun()
        with st.container(horizontal=True, key="usuario_topo", width="content",
                          vertical_alignment="center", gap="small"):
            # Tela cheia (⛶), como no Taipei: quem liga/desliga é o script de script_tela_cheia(), no navegador
            if not CELULAR:
                st.button("", icon=":material/fullscreen:", type="tertiary", key="tela_cheia", help="Tela cheia")
            # ⓘ como no Taipei: documentação técnica e colaboradores do projeto
            with st.popover("", icon=":material/info:", key="info_topo"):
                if st.button("Documentação técnica", icon=":material/description:", type="tertiary",
                             key="abrir_documentacao", width="stretch"):
                    st.session_state.pagina = "documentacao"
                    st.session_state.fechar_menu_info = True
                    st.rerun()
                if st.button("Colaboradores do projeto", icon=":material/groups:", type="tertiary",
                             key="abrir_colaboradores", width="stretch"):
                    janela_colaboradores()
            if CELULAR:
                menu_celular()
            elif st.session_state.usuario:
                with st.popover(st.session_state.usuario["nome"], icon=":material/person:", key="menu_usuario"):
                    st.caption(st.session_state.usuario["email"])
                    if st.button("Configurações do usuário", key="abrir_config_usuario", width="stretch"):
                        janela_config_usuario()
                    # Só para administradores, como o "Painel de administração" do Taipei
                    if e_admin():
                        na_admin = st.session_state.pagina == "admin"
                        if st.button("Voltar ao painel" if na_admin else "Painel de administração",
                                     key="abrir_admin", width="stretch"):
                            st.session_state.pagina = "painel" if na_admin else "admin"
                            st.rerun()
                    if st.button("Sair", key="sair", width="stretch"):
                        sair()
                        if st.session_state.painel not in PAINEIS_PUBLICOS:
                            st.session_state.painel = "cuidados"
                        st.rerun()
            elif st.button("Entrar", key="abrir_login", type="tertiary", icon=":material/login:"):
                janela_login()
            # Na documentação, como no Taipei: chavinha escuro/claro no cantinho direito
            if st.session_state.get("pagina") == "documentacao":
                claro = st.session_state.get("doc_claro", False)
                st.button("", icon=":material/light_mode:" if claro else ":material/dark_mode:",
                          key="tema_doc_claro" if claro else "tema_doc_escuro", on_click=trocar_tema_doc,
                          help="Voltar para o modo escuro" if claro else "Mudar para o modo claro")


# --- COLABORADORES DO PROJETO (ContributorsList e ContributorInfo do Taipei) ---
# Para acrescentar alguém, copie um item da lista: "imagem" é um arquivo da pasta imagens/
COLABORADORES = [
    {"nome": "Prefeitura Municipal de Oriximiná", "imagem": "oriximina-logo.jpg",
     "funcao": "Órgão responsável pelo painel",
     "contribuicao": "Responsável pelo Painel Oriximiná e pela organização dos dados do município.",
     "link": "https://www.oriximina.pa.gov.br"},
]


def foto_colaborador(colaborador, tamanho):
    arquivo = os.path.join(PASTA_IMAGENS, colaborador["imagem"])
    if not os.path.exists(arquivo):
        return f'<span class="icone-material foto-colaborador" style="font-size:{tamanho}px">account_circle</span>'
    with open(arquivo, "rb") as arq:
        dados = base64.b64encode(arq.read()).decode()
    tipo = "png" if arquivo.lower().endswith(".png") else "jpeg"
    return (f'<img class="foto-colaborador" src="data:image/{tipo};base64,{dados}" '
            f'style="width:{tamanho}px; height:{tamanho}px" alt="{html.escape(colaborador["nome"])}">')


def limpar_colaborador():
    st.session_state.pop("colaborador_escolhido", None)


@st.dialog("Colaboradores do projeto", width="small", on_dismiss=limpar_colaborador)
def janela_colaboradores():
    """Lista de colaboradores com foto; ao clicar num deles aparecem função, contribuição e link."""
    escolhido = st.session_state.get("colaborador_escolhido")
    if escolhido is None:
        st.markdown('<div class="catalogo-fonte">Clique num colaborador para saber mais</div>',
                    unsafe_allow_html=True)
        with st.container(horizontal=True, gap="medium", key="lista_colaboradores"):
            for i, colaborador in enumerate(COLABORADORES):
                with st.container(width=130, horizontal_alignment="center", gap="small", key=f"colaborador_{i}"):
                    st.markdown(foto_colaborador(colaborador, 72), unsafe_allow_html=True)
                    if st.button(colaborador["nome"], type="tertiary", key=f"ver_colaborador_{i}"):
                        st.session_state.colaborador_escolhido = i
                        st.rerun(scope="fragment")
        return
    colaborador = COLABORADORES[escolhido]
    if st.button("Voltar à lista", icon=":material/arrow_back:", type="tertiary", key="voltar_colaboradores"):
        limpar_colaborador()
        st.rerun(scope="fragment")
    link = colaborador["link"]
    st.markdown(f"""<div class="info-colaborador">
        <div class="info-colaborador-topo">{foto_colaborador(colaborador, 64)}
            <div class="info-colaborador-nome">{html.escape(colaborador["nome"])}</div></div>
        <div class="info-colaborador-rotulo">Função</div><p>{html.escape(colaborador["funcao"])}</p>
        <div class="info-colaborador-rotulo">Contribuição</div><p>{html.escape(colaborador["contribuicao"])}</p>
        {f'''<a class="link-dados" href="{html.escape(link)}" target="_blank" rel="noreferrer">
            {"GitHub" if "github" in link else "Link relacionado"}
            <span class="icone-material" style="font-size:1rem; margin:0">open_in_new</span></a>''' if link else ""}
    </div>""", unsafe_allow_html=True)


# --- DOCUMENTAÇÃO TÉCNICA (o link de documentação do ⓘ do Taipei): mostra o README.md do projeto ---
# No alto, como na página de documentação do Taipei: título grande, botões e um cartão de exemplo que
# troca sozinho entre gráficos do painel (com os dados reais dos cartões)
LINK_TAIPEI_GITHUB = "https://github.com/tpe-doit/Taipei-City-Dashboard"
INTERVALO_DEMO = 5   # segundos entre um gráfico e outro
CORES_DEMO_IDADES = ["#24B0DD", "#56B96D", "#F8CF58"]


def demo_idades():
    fig = go.Figure(go.Pie(
        labels=["0 a 14 anos", "15 a 59 anos", "60 anos ou mais"], values=[pop_0_14, pop_15_59, pop_60_mais],
        hole=0.82, sort=False, direction="clockwise", marker=dict(colors=CORES_DEMO_IDADES, line=dict(width=3, color=COR_CARTAO)),
        textinfo="label", textposition="outside", textfont=dict(color="#ffffff", size=13),
        hovertemplate="%{label}: %{value:,.0f} habitantes<extra></extra>"))
    fig.add_annotation(text=f'<span style="color:{COR_TEXTO_CINZA}">Em resumo</span><br>'
                            f'<span style="font-size:22px; color:#c8c8c8">{formatar(pop_idades)}</span>',
                       showarrow=False, font=dict(size=15))
    return ("Divisões etárias em toda a cidade", "Censo 2022", "IBGE | Censo Demográfico 2022", None, fig)


def demo_frota():
    frota = df_frota.sort_values("Total")
    cores = ["#d94f4f", "#e08a3c", "#d9b45a", "#8fae6e", "#4a9e8a", "#4b8a96", "#5a7fb0", "#7d6fb0", "#a06aa8"]
    fig = go.Figure(go.Bar(
        x=frota["Total"], y=frota["Nome"], orientation="h", marker_color=cores[:len(frota)][::-1],
        text=[formatar(v) for v in frota["Total"]], textposition="auto", insidetextanchor="end",
        textfont=dict(color="#ffffff", size=13), cliponaxis=False,
        hovertemplate="%{y}: %{x:,.0f} veículos<extra></extra>"))
    fig.update_layout(xaxis=dict(visible=False), yaxis=dict(tickfont=dict(color="#c8c8c8", size=12)), bargap=0.35)
    return ("Frota de veículos da Calha Norte", f"SENATRAN {df_frota['Mês'].iloc[0].split()[-1]}",
            f"SENATRAN | Frota de veículos, {df_frota['Mês'].iloc[0].lower()}",
            f"{formatar(df_frota['Total'].sum())} veículos", fig)


def demo_municipios():
    fig = go.Figure(go.Choropleth(
        geojson=geojson_regiao, featureidkey="properties.codigo", locations=df_regiao_idades["codigo"],
        z=df_regiao_idades["Habitantes"], colorscale=[[0, "#4a2f5c"], [1, "#b46fd0"]], showscale=False,
        marker_line_color="#2b1f33", marker_line_width=1.2, customdata=df_regiao_idades["Nome"],
        hovertemplate="%{customdata}: %{z:,.0f} habitantes<extra></extra>"))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor=COR_CARTAO)
    legenda = ('<span class="demo-legenda">Mais <span class="demo-escala"></span> Menos</span>')
    return ("Habitantes dos municípios da Calha Norte", "Censo 2022", "IBGE | Censo Demográfico 2022",
            f"{formatar(df_regiao_idades['Habitantes'].sum())} habitantes{legenda}", fig)


def demo_vias():
    km = (resumo_vias["sum"] / 1000).round(1)
    fig = go.Figure(go.Treemap(
        labels=list(km.index), parents=[""] * len(km), values=list(km.values),
        marker=dict(colors=[CORES_VIAS[t] for t in km.index], line=dict(width=2, color=COR_CARTAO)),
        textinfo="label", textposition="middle center", textfont=dict(color="#1e1f21", size=15),
        tiling=dict(pad=0),
        hovertemplate="%{label}: %{value:,.1f} km<extra></extra>"))
    total = f"{km.sum():,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("Rede viária da sede urbana", "Dados fixos", "OpenStreetMap | Ruas e caminhos da sede",
            f"{total} km", fig)


DEMOS = [demo_idades, demo_frota, demo_municipios, demo_vias]


@st.fragment(run_every=INTERVALO_DEMO)
def cartao_demo():
    """Cartão de exemplo do alto da documentação: a cada poucos segundos mostra outro gráfico do painel."""
    vez = st.session_state.get("demo_vez", -1) + 1
    st.session_state.demo_vez = vez
    titulo, atualizacao, fonte, resumo, fig = DEMOS[vez % len(DEMOS)]()
    fig.update_layout(height=340, margin=dict(l=4, r=4, t=10, b=4), paper_bgcolor=COR_CARTAO,
                      plot_bgcolor=COR_CARTAO, showlegend=False, separators=",.",
                      font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"),
                      hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white")))
    if st.session_state.get("doc_claro"):
        figura_demo_clara(fig)
    with st.container(key="cartao_demo"):
        st.markdown(f'<div class="demo-topo"><div class="demo-titulo">{titulo}</div>'
                    f'<span class="demo-etiqueta">Atualização: {atualizacao}</span></div>'
                    f'<div class="cartao-fonte">{fonte}</div>'
                    + (f'<div class="demo-resumo"><div>Em resumo</div><b>{resumo}</b></div>' if resumo else ""),
                    unsafe_allow_html=True)
        st.plotly_chart(fig, key=f"demo_{vez}", config={"displayModeBar": False, "staticPlot": False})


def topo_documentacao():
    col_texto, col_cartao = st.columns([1.35, 1], gap="large", vertical_alignment="center")
    with col_texto:
        st.markdown('<div class="doc-heroi"><div class="doc-titulo">Painel <span>Oriximiná</span></div>'
                    '<div class="doc-frase">Faça do Painel de Oriximiná o seu painel</div></div>',
                    unsafe_allow_html=True)
        with st.container(horizontal=True, horizontal_alignment="center", gap="small", key="doc_botoes"):
            if st.button("Sobre nós", icon=":material/play_circle:", key="doc_sobre"):
                janela_colaboradores()
            st.link_button("Inspirado no Painel de Taipei (GitHub)", LINK_TAIPEI_GITHUB, icon=":material/code:")
            if st.button("Vá até o painel", key="doc_ir_painel"):
                st.session_state.pagina = "painel"
                st.rerun()
    with col_cartao:
        cartao_demo()
    st.markdown('<hr class="doc-divisa">', unsafe_allow_html=True)


def trocar_tema_doc():
    st.session_state.doc_claro = not st.session_state.get("doc_claro", False)


# Modo claro da documentação: fundo branco e textos escuros (o resto do painel continua escuro)
CSS_DOC_CLARO = """<style>
    .stApp, [data-testid="stAppViewContainer"], .stMain { background-color: #f5f6f7 !important; }
    .st-key-barra_topo { background-color: #ffffff !important; border-bottom-color: #d9dadc !important; }
    .st-key-barra_topo p, .st-key-barra_topo span, .st-key-barra_topo div { color: #1f2328 !important; }
    .st-key-barra_topo button p, .st-key-barra_topo [data-testid="stIconMaterial"] { color: #1f2328 !important; }
    .st-key-barra_topo button[kind="tertiary"]:hover p { color: #5a9cf8 !important; }
    .st-key-tema_doc_claro [data-testid="stIconMaterial"] { color: #e0a400 !important; }
    .st-key-documentacao, .st-key-documentacao p, .st-key-documentacao li, .st-key-documentacao td,
    .st-key-documentacao th, .st-key-documentacao h1, .st-key-documentacao h2, .st-key-documentacao h3,
    .st-key-documentacao strong, .st-key-documentacao .titulo-painel { color: #1f2328 !important; }
    .st-key-documentacao code { background-color: #eceef0 !important; color: #1f2328 !important; }
    .st-key-documentacao table, .st-key-documentacao th, .st-key-documentacao td { border-color: #d0d7de !important; }
    .st-key-documentacao a { color: #2f6fd6 !important; }
    .doc-frase { color: #4a4f55 !important; }
    .doc-divisa { border-top-color: #c4c7cb !important; }
    .st-key-cartao_demo { background-color: #ffffff !important; box-shadow: 0 1px 6px rgba(0, 0, 0, 0.12); }
    .st-key-cartao_demo .demo-titulo { color: #1f2328 !important; }
    .st-key-cartao_demo .cartao-fonte, .demo-resumo, .demo-legenda { color: #6a6f75 !important; }
    .demo-resumo b { color: #3a3f45 !important; }
    .demo-etiqueta { color: #6a6f75 !important; border-color: #9aa0a6 !important; }
    .st-key-doc_botoes [data-testid="stLinkButton"] a { border-color: #1f2328 !important; }
    .st-key-doc_botoes [data-testid="stLinkButton"] a p,
    .st-key-doc_botoes [data-testid="stLinkButton"] a span { color: #1f2328 !important; }
</style>"""


def figura_demo_clara(fig):
    """Os mesmos gráficos do cartão de exemplo, com fundo branco e textos escuros."""
    fig.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font=dict(color="#1f2328"))
    fig.update_traces(selector=dict(type="pie"), textfont_color="#1f2328", marker_line_color="#ffffff")
    fig.update_traces(selector=dict(type="bar"), outsidetextfont_color="#1f2328")
    fig.update_traces(selector=dict(type="treemap"), marker_line_color="#ffffff")
    fig.update_yaxes(tickfont_color="#4a4f55")
    fig.update_geos(bgcolor="#ffffff")
    for nota in fig.layout.annotations:
        nota.text = nota.text.replace("#c8c8c8", "#3a3f45").replace(COR_TEXTO_CINZA, "#6a6f75")
    return fig


def pagina_documentacao():
    if st.session_state.get("doc_claro"):
        st.markdown(CSS_DOC_CLARO, unsafe_allow_html=True)
    if st.button("Voltar ao painel", icon=":material/arrow_circle_left:", type="tertiary", key="voltar_documentacao"):
        st.session_state.pagina = "painel"
        st.rerun()
    if st.session_state.pop("fechar_menu_info", False):
        # O menu ⓘ continua aberto depois do clique; um "Esc" no navegador fecha ele
        with st.container(key="script_fechar_menu"):
            st.iframe("""<script>window.parent.document.dispatchEvent(
                new KeyboardEvent("keydown", {key: "Escape", code: "Escape", keyCode: 27, bubbles: true}));
                </script>""", height=1)
    topo_documentacao()
    with st.container(key="documentacao"):
        st.markdown('<div class="titulo-painel"><span class="icone-material">description</span>'
                    'Documentação técnica</div>', unsafe_allow_html=True)
        arquivo = os.path.join(PASTA_PROJETO, "README.md")
        if os.path.exists(arquivo):
            with open(arquivo, encoding="utf-8") as arq:
                st.markdown(arq.read())
        else:
            st.markdown('<div class="aviso-vazio">O arquivo README.md não foi encontrado na pasta do painel.</div>',
                        unsafe_allow_html=True)


# --- AVISO INICIAL (InitialWarning do Taipei) ---
# Aparece ao abrir o painel; com "Não mostrar esta janela novamente" marcado, o navegador guarda um cookie
# e a janela não aparece mais nas próximas visitas
COOKIE_AVISO_INICIAL = "aviso_inicial_painel"


def marcar_aviso_visto():
    st.session_state.aviso_inicial_visto = True


AVISO_INICIAL = """<div class="aviso-inicial">
    <p>Bem-vindo ao Painel Oriximiná. Ele reúne, em cartões com gráficos e mapas, dados oficiais sobre
    Oriximiná e os municípios da Calha Norte paraense, para apoiar o planejamento da Prefeitura e
    facilitar o acesso da população a essas informações.</p>
    <p>Os dados vêm de fontes oficiais (IBGE, DATASUS, Ministério do Trabalho, SENATRAN e OpenStreetMap) e
    foram organizados para este painel. Muitos não são em tempo real (por exemplo, o Censo é de 2022) e
    podem ser um pouco diferentes dos dados originais; a fonte e a data de cada um aparecem no próprio
    cartão.</p>
    <p>Para salvar favoritos e montar os seus próprios painéis, clique em <b>Entrar</b>, no canto de cima
    à direita.</p>
    <p class="aviso-inicial-destaque">Para ver as informações no mapa, abra a página <b>Comparação de
    mapas</b>, na barra de cima, e ligue as camadas que quiser ver.</p>
</div>"""

# Versão para celular, como a do Taipei: o que não funciona na tela pequena
AVISO_INICIAL_CELULAR = """<div class="aviso-inicial">
    <p>O Painel Oriximiná foi feito principalmente para computadores e tablets. No celular ele serve como uma
    visão geral, e algumas funções não estão disponíveis.</p>
    <p>No celular não aparecem: entrar na conta (favoritos e painéis pessoais), o catálogo de componentes e
    a tela cheia.</p>
    <p>Para usar todas as funções, abra o painel num computador ou tablet.</p>
    <p class="aviso-inicial-destaque">Para ver as informações no mapa, toque no <b>☰</b>, escolha
    <b>Comparação de mapas</b> e depois toque em <b>Camadas</b>.</p>
</div>"""


@st.dialog("Instruções de uso do Painel Oriximiná", width="small", on_dismiss=marcar_aviso_visto)
def janela_aviso_inicial():
    conteudo_aviso_inicial(AVISO_INICIAL)


@st.dialog("Painel Oriximiná no celular", width="small", on_dismiss=marcar_aviso_visto)
def janela_aviso_inicial_celular():
    conteudo_aviso_inicial(AVISO_INICIAL_CELULAR)


def conteudo_aviso_inicial(texto):
    st.markdown(texto, unsafe_allow_html=True)
    nao_mostrar = st.checkbox("Não mostrar esta janela novamente", key="aviso_nao_mostrar")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Entendi", type="primary", key="aviso_entendi"):
            marcar_aviso_visto()
            st.session_state.gravar_cookie_aviso = nao_mostrar
            st.rerun()


def script_gravar_cookie_aviso():
    # Guarda no navegador (por 1 ano) que a pessoa pediu para não ver mais o aviso inicial
    st.iframe(f"""<script>
    window.parent.document.cookie = "{COOKIE_AVISO_INICIAL}=visto; max-age=31536000; path=/; SameSite=Lax";
    </script>""", height=1)


def script_tela_cheia():
    """Liga/desliga a tela cheia ao clicar no ⛶ da barra de cima.

    O Streamlit só roda Python no servidor, e a tela cheia precisa de JavaScript no navegador. Este quadro
    invisível põe um script na página (uma vez só) que pega o clique no botão antes do Streamlit (assim a
    página não recarrega), liga ou desliga a tela cheia e troca o ícone (⛶ / sair da tela cheia).
    """
    st.iframe("""<script>
    const d = window.parent.document;
    if (!d.getElementById("script-tela-cheia")) {
        const s = d.createElement("script");
        s.id = "script-tela-cheia";
        s.textContent = `
            document.addEventListener("click", (ev) => {
                if (!ev.target.closest || !ev.target.closest(".st-key-tela_cheia button")) return;
                ev.preventDefault();
                ev.stopPropagation();
                if (document.fullscreenElement) document.exitFullscreen();
                else document.documentElement.requestFullscreen();
            }, true);
            document.addEventListener("fullscreenchange", () => {
                const icone = document.querySelector('.st-key-tela_cheia [data-testid="stIconMaterial"]');
                if (icone) icone.textContent = document.fullscreenElement ? "fullscreen_exit" : "fullscreen";
            });
        `;
        d.head.appendChild(s);
    }
    // Menu ☰ do celular: ao tocar numa página ou painel, o menu fecha na hora (antes ficava aberto
    // por cima da página nova). Escuta depois do Streamlit (sem "capture"), então o toque já foi
    // registrado; o "Esc" é o que fecha o menu
    if (!d.getElementById("script-fechar-menu-celular")) {
        const s = d.createElement("script");
        s.id = "script-fechar-menu-celular";
        s.textContent = `
            document.addEventListener("click", (ev) => {
                const opcao = ev.target.closest && ev.target.closest(
                    '[class*="st-key-celular_pagina_"] button, [class*="st-key-celular_menu_"] button');
                if (!opcao) return;
                setTimeout(() => document.dispatchEvent(new KeyboardEvent("keydown",
                    {key: "Escape", code: "Escape", keyCode: 27, bubbles: true})), 0);
            });
        `;
        d.head.appendChild(s);
    }
    </script>""", height=1)   # o Streamlit não aceita altura 0; o quadro fica escondido pelo CSS


# --- MENU LATERAL (SideBar do Taipei) ---
def aba_menu(painel, titulo, icone, prefixo="aba_menu"):
    if st.button(titulo, key=f"{prefixo}_{painel}", icon=f":material/{icone}:", type="tertiary",
                 width="stretch"):
        st.session_state.painel = painel
        st.session_state.info_aberto = None
        st.rerun()


def menu_lateral():
    with st.sidebar:
        if st.session_state.usuario:
            st.markdown('<div class="menu-titulo">Painel privado</div>'
                        '<div class="menu-grupo">Meus favoritos</div>', unsafe_allow_html=True)
            aba_menu("favoritos", *PAINEL_FAVORITOS)
            with st.container(horizontal=True, vertical_alignment="center", key="linha_painel_pessoal"):
                st.markdown('<div class="menu-grupo">Painel pessoal</div>', unsafe_allow_html=True,
                            width="content")
                if st.button("Adicionar", icon=":material/add_circle:", key="adicionar_painel"):
                    limpar_painel_pessoal()
                    janela_adicionar_painel()
            if not st.session_state.paineis_pessoais:
                st.markdown('<div class="menu-vazio">Nenhum painel pessoal</div>', unsafe_allow_html=True)
            for pessoal in st.session_state.paineis_pessoais:
                aba_menu(f"pessoal_{pessoal['id']}", pessoal["nome"], pessoal["icone"])
        st.markdown('<div class="menu-titulo">Painéis públicos</div>', unsafe_allow_html=True)
        for grupo, paineis in GRUPOS_MENU.items():
            st.markdown(f'<div class="menu-grupo">{grupo}</div>', unsafe_allow_html=True)
            for painel in paineis:
                titulo, icone, _ = PAINEIS_PUBLICOS[painel]
                aba_menu(painel, titulo, icone)


def menu_celular():
    """Botão ☰ da barra de cima no celular (MobileNavigation do Taipei): as páginas e a lista de painéis,
    no lugar do menu lateral, que no celular cobriria a tela toda."""
    with st.popover("", icon=":material/menu:", key="menu_celular"):
        st.markdown('<div class="menu-titulo">Páginas</div>', unsafe_allow_html=True)
        for pagina, (rotulo, icone) in {"painel": ("Visão geral do painel", "dashboard"),
                                        "mapa": ("Comparação de mapas", "map")}.items():
            if st.button(rotulo, key=f"celular_pagina_{pagina}", icon=f":material/{icone}:", type="tertiary",
                         width="stretch"):
                st.session_state.pagina = pagina
                st.rerun()
        if st.session_state.usuario:
            st.markdown('<div class="menu-titulo">Painel privado</div>', unsafe_allow_html=True)
            aba_menu("favoritos", *PAINEL_FAVORITOS, prefixo="celular_menu")
            for pessoal in st.session_state.paineis_pessoais:
                aba_menu(f"pessoal_{pessoal['id']}", pessoal["nome"], pessoal["icone"], prefixo="celular_menu")
        st.markdown('<div class="menu-titulo">Painéis públicos</div>', unsafe_allow_html=True)
        for grupo, paineis in GRUPOS_MENU.items():
            st.markdown(f'<div class="menu-grupo">{grupo}</div>', unsafe_allow_html=True)
            for painel in paineis:
                titulo, icone, _ = PAINEIS_PUBLICOS[painel]
                aba_menu(painel, titulo, icone, prefixo="celular_menu")


# --- PÁGINA "VISÃO GERAL DO PAINEL": CARTÕES LADO A LADO ---
def titulo_painel(painel):
    titulo, icone = nome_do_painel(painel)
    with st.container(horizontal=True, vertical_alignment="center", key="linha_titulo_painel"):
        grupo = next((g for g, paineis in GRUPOS_MENU.items() if painel in paineis), "")
        etiqueta = f'<span class="etiqueta-grupo">{grupo}</span>' if grupo else ""
        st.markdown(f'<div class="titulo-painel"><span class="icone-material">{icone}</span>{titulo}'
                    f'{etiqueta}</div>', unsafe_allow_html=True, width="content")
        # Engrenagem de configurações do painel pessoal, como no Taipei (abre a janela "Editar painel")
        # (a engrenagem cheia é desenhada no CSS de .st-key-editar_painel)
        if painel.startswith("pessoal_") and st.button("Configurações", type="tertiary", key="editar_painel"):
            limpar_painel_pessoal()
            janela_editar_painel(painel)


def grade_cartoes(chaves):
    # "Informações do componente" abre por cima dos cartões, que continuam no fundo. Ela é aberta antes
    # de os cartões serem desenhados, para aparecer logo depois do clique
    if st.session_state.info_aberto in chaves:
        janela_info(st.session_state.info_aberto)
    # Quantos cartões couberem por linha, como no Taipei (a grade é feita no CSS de .st-key-grade_cartoes)
    with st.container(key="grade_cartoes"):
        for chave in chaves:
            with st.container(key=f"celula_{chave}"):
                cartao(chave, CARTOES[chave][1])


def aviso_painel_vazio(painel):
    """Painel sem cartões: ícone e aviso no meio da tela, como no Taipei."""
    dica = ("Clique no coração de outro componente do painel para adicioná-lo aos favoritos"
            if painel == "favoritos" else "Clique em Editar para escolher os componentes deste painel")
    st.markdown(f'<div class="painel-vazio"><span class="icone-material">add_chart</span>'
                f'<div class="painel-vazio-titulo">Nenhum componente adicionado</div>'
                f'<div class="painel-vazio-dica">{dica}</div></div>', unsafe_allow_html=True)


def pagina_painel():
    painel = st.session_state.painel
    titulo_painel(painel)
    chaves = cartoes_do_painel(painel)
    if not chaves:
        aviso_painel_vazio(painel)
        return
    grade_cartoes(chaves)


# --- PÁGINA "CATÁLOGO DE COMPONENTES" (ComponentView do Taipei) ---
# Resumo de cada cartão no catálogo: descrição curta, fonte, frequência de atualização e
# ícone do tipo de gráfico (Material Symbols)
RESUMO_CARTOES = {
    "dependencia": ("Razão de dependência e índice de envelhecimento de Oriximiná, ano a ano.",
                    "Ministério da Saúde | DATASUS", "Anual", "show_chart"),
    "emprego": ("Empregos formais de pessoas idosas em Oriximiná, ano a ano.",
                "Ministério do Trabalho e Emprego | RAIS", "Anual", "bar_chart"),
    "divisoes": ("Habitantes por faixa etária em cada localidade de Oriximiná.",
                 "IBGE | Censo 2022", "Dados fixos", "bar_chart"),
    "vias": ("Ruas e caminhos da sede urbana de Oriximiná, por tipo de via.",
             "OpenStreetMap", "Dados fixos", "map"),
    "indicadores": ("Indicadores de cuidados de longo prazo de Oriximiná.",
                    "IBGE | Censo 2022", "Dados fixos", "grid_view"),
    "dependencia_cn": ("Razão de dependência e índice de envelhecimento dos municípios da Calha Norte.",
                       "Ministério da Saúde | DATASUS", "Anual", "show_chart"),
    "emprego_cn": ("Empregos formais de pessoas idosas nos municípios da Calha Norte.",
                   "Ministério do Trabalho e Emprego | RAIS", "Anual", "bar_chart"),
    "divisoes_cn": ("Habitantes por faixa etária em cada município da Calha Norte.",
                    "IBGE | Censo 2022", "Dados fixos", "bar_chart"),
    "indicadores_cn": ("Indicadores de cuidados de longo prazo dos municípios da Calha Norte.",
                       "IBGE | Censo 2022", "Dados fixos", "grid_view"),
    "tempo_cn": ("Tempo de casa até o trabalho nos municípios da Calha Norte.",
                 "IBGE | Censo 2022", "Dados fixos", "speed"),
    "meio_cn": ("Meio de transporte usado para ir ao trabalho nos municípios da Calha Norte.",
                "IBGE | Censo 2022", "Dados fixos", "directions_bus"),
    "frota_cn": ("Veículos registrados em cada município da Calha Norte.",
                 "Ministério dos Transportes | SENATRAN", "Mensal", "donut_large"),
    "vias_cn": ("Estradas, limites e sedes dos municípios da Calha Norte.",
                "OpenStreetMap", "Dados fixos", "map"),
}
COR_ETIQUETA_GRUPO = {"Painel de Oriximiná": "#a8830f", "Painel da Calha Norte": "#1f7a4d"}


def painel_do_cartao(chave):
    """O primeiro painel público que mostra esse cartão (ou None: componente novo, ainda sem painel)."""
    return next((p for p, (_, _, cartoes) in PAINEIS_PUBLICOS.items() if chave in cartoes), None)


def etiquetas_do_cartao(chave):
    """Etiquetas coloridas do grupo e do painel público do cartão (catálogo e escolha de componentes)."""
    painel = painel_do_cartao(chave)
    if painel is None:
        return '<span class="catalogo-etiqueta" style="background:#555">Ainda sem painel público</span>'
    grupo = next((g for g, paineis in GRUPOS_MENU.items() if painel in paineis), "")
    return (f'<span class="catalogo-etiqueta" style="background:{COR_ETIQUETA_GRUPO.get(grupo, "#555")}">'
            f'{html.escape(grupo)}</span>'
            f'<span class="catalogo-etiqueta" style="background:#2323a8">{html.escape(PAINEIS_PUBLICOS[painel][0])}</span>')


def item_catalogo(chave):
    # Cartão de resumo, como o ComponentCard do catálogo do Taipei
    descricao, fonte, atualizacao, icone = RESUMO_CARTOES[chave]
    with st.container(key=f"catalogo_item_{chave}"):
        with st.container(horizontal=True, vertical_alignment="top", gap="small"):
            st.markdown(f'<div class="catalogo-titulo">{TITULOS_CARTOES[chave]}</div>', unsafe_allow_html=True)
            with st.container(horizontal=True, width="content", vertical_alignment="center", gap="small",
                              key=f"catalogo_controles_{chave}"):
                st.markdown(f'<span class="cartao-atualizacao">{atualizacao}</span>', unsafe_allow_html=True,
                            width="content")
                # Como no painel, "+" e o coração só aparecem para quem entrou com uma conta.
                # O "+" põe o componente na lista do painel que está sendo montado à esquerda.
                if st.session_state.usuario:
                    na_lista = chave in st.session_state.get("cat_cartoes", [])
                    if st.button("", icon=":material/check_circle:" if na_lista else ":material/add_circle:",
                                 type="tertiary", disabled=na_lista, key=f"catalogo_adicionar_{chave}",
                                 help="Já está no painel" if na_lista else "Adicionar ao painel"):
                        st.session_state.cat_cartoes.append(chave)
                        st.rerun()
                    favorito = chave in st.session_state.favoritos
                    if st.button("♥", key=f"catalogo_favorito_{chave}", type="tertiary",
                                 help="Remover dos favoritos" if favorito else "Adicionar aos favoritos"):
                        alternar_favorito(chave)
                        st.rerun()
        st.markdown(f'<div class="catalogo-descricao">{descricao}</div>'
                    f'<div class="catalogo-fonte">{fonte} | {atualizacao}</div>', unsafe_allow_html=True)
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.markdown(
                f'<div class="catalogo-etiquetas">{etiquetas_do_cartao(chave)}'
                f'<div class="catalogo-index">ID: {CARTOES[chave][0]} · Index: {chave}</div></div>',
                unsafe_allow_html=True, width="content")
            st.space("stretch")
            st.markdown(f'<span class="catalogo-icone">{icone}</span>', unsafe_allow_html=True, width="content")
        with st.container(horizontal=True, vertical_alignment="center"):
            if CAMADAS_DO_CARTAO[chave]:
                st.markdown('<span class="catalogo-filtro">Filtrar mapa</span>', unsafe_allow_html=True,
                            width="content")
            st.space("stretch")
            # Abre o painel do cartão já com a descrição aberta
            # Abre a página própria do componente (ComponentInfoView do Taipei)
            if st.button("Página de informações", type="tertiary", key=f"catalogo_info_{chave}"):
                st.session_state.pagina = "componente"
                st.session_state.componente = chave
                st.rerun()


def carregar_painel_catalogo():
    """Preenche o formulário da esquerda com o painel escolhido (ou vazio, para um painel novo)."""
    existente = next((p for p in st.session_state.paineis_pessoais
                      if p["id"] == st.session_state.get("cat_alvo")), None)
    st.session_state.cat_nome = existente["nome"] if existente else ""
    st.session_state.cat_icone = existente["icone"] if existente else ICONES_PAINEL[0]
    st.session_state.cat_cartoes = list(existente["cartoes"]) if existente else []


def lateral_catalogo():
    # Formulário "Adicionar painel" do catálogo do Taipei: nome, ícone e a lista de componentes,
    # que vai sendo preenchida pelo [+] dos cartões à direita
    if not st.session_state.usuario:
        st.markdown('<div class="aviso-vazio">Entre com uma conta para montar os seus painéis com os '
                    'componentes do catálogo.</div>', unsafe_allow_html=True)
        return
    paineis = st.session_state.paineis_pessoais
    # 0 = "Adicionar painel" (painel novo); os painéis pessoais têm id a partir de 1. Não dá para usar None:
    # o Streamlit mostra None como "Choose an option", como se nada estivesse escolhido
    opcoes = [0] + [p["id"] for p in paineis]
    if "cat_alvo_proximo" in st.session_state:   # painel recém-criado: passa a editá-lo
        st.session_state.cat_alvo = st.session_state.pop("cat_alvo_proximo")
    if "cat_cartoes" not in st.session_state or st.session_state.get("cat_alvo") not in opcoes:
        st.session_state.cat_alvo = 0
        carregar_painel_catalogo()
    nomes = {p["id"]: p["nome"] for p in paineis}
    st.markdown('<div class="catalogo-titulo-lateral">Adicionar componentes ao painel</div>',
                unsafe_allow_html=True)
    alvo = st.selectbox("Selecionar painel", opcoes, key="cat_alvo", on_change=carregar_painel_catalogo,
                        format_func=lambda i: "Adicionar painel" if i == 0 else f"Editar: {nomes[i]}")

    nome_atual = st.session_state.get("cat_nome", "")
    if not nome_atual.strip():
        st.markdown("<style>.st-key-cat_nome [data-testid$='RootElement'] "
                    "{ border-color: #e5484d !important; }</style>", unsafe_allow_html=True)
    nome = st.text_input(f"Nome* ({len(nome_atual)}/10)", max_chars=10, key="cat_nome",
                         placeholder="Meu painel")
    busca = st.text_input("Ícone*", placeholder="Buscar ícone", key="cat_busca_icone").strip().lower()
    icones = [i for i in ICONES_PAINEL if busca.replace(" ", "_") in i] or ICONES_PAINEL
    if st.session_state.get("cat_icone") and st.session_state.cat_icone not in icones:
        icones = [st.session_state.cat_icone] + icones
    icone = st.pills("Ícone", icones, format_func=lambda i: f":material/{i}:", key="cat_icone",
                     label_visibility="collapsed") or ICONES_PAINEL[0]

    st.divider()
    st.markdown('<div class="catalogo-fonte">Componentes do painel (clique no ícone [+] à direita para '
                'adicionar)</div>', unsafe_allow_html=True)
    with st.container(height=330, key="cat_lista"):
        for chave in list(st.session_state.cat_cartoes):
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.markdown(f'<div class="catalogo-descricao">{TITULOS_CARTOES[chave]}</div>',
                            unsafe_allow_html=True)
                if st.button("", icon=":material/close:", type="tertiary", key=f"cat_remover_{chave}",
                             help="Tirar do painel"):
                    st.session_state.cat_cartoes.remove(chave)
                    st.rerun()

    if st.button("Adicionar componentes ao painel" if alvo == 0 else "Salvar alterações no painel",
                 key="cat_salvar", width="stretch"):
        if not nome.strip():
            st.session_state.aviso = "Dê um nome ao painel antes de salvar"
            st.rerun()
        cartoes = list(st.session_state.cat_cartoes)
        if alvo == 0:
            alvo = max([p["id"] for p in paineis], default=0) + 1
            paineis.append({"id": alvo, "nome": nome.strip(), "icone": icone, "cartoes": cartoes})
            st.session_state.cat_alvo_proximo = alvo
        else:
            next(p for p in paineis if p["id"] == alvo).update(nome=nome.strip(), icone=icone, cartoes=cartoes)
        salvar_paineis()
        st.session_state.aviso = f"Painel {nome.strip()} salvo"
        st.rerun()


def pagina_catalogo():
    # Como no Taipei: o formulário fica colado à esquerda, numa coluna estreita, e os cartões ocupam o resto
    st.markdown("""<style>
        .stMainBlockContainer { padding-left: 20px !important; padding-right: 24px !important;
                                padding-top: 76px !important; max-width: none !important; }
        [data-testid="stColumn"]:has(.st-key-lateral_catalogo) { flex: 0 0 330px !important; width: 330px !important; }
        [data-testid="stColumn"]:has(.st-key-grade_catalogo),
        [data-testid="stColumn"]:has(.st-key-linha_busca_catalogo) { flex: 1 1 0 !important; width: auto !important; }
        .st-key-lateral_catalogo { gap: 0.6rem; }
        /* O Streamlit dá margem negativa (-16px) aos textos; com o texto em duas linhas, a caixa de baixo
           subia por cima da segunda linha */
        .st-key-lateral_catalogo [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
        .st-key-lateral_catalogo .catalogo-fonte { line-height: 1.35; }
    </style>""", unsafe_allow_html=True)
    col_lateral, col_cartoes = st.columns([1, 2.3], gap="medium")
    with col_lateral, st.container(key="lateral_catalogo"):
        lateral_catalogo()
    with col_cartoes:
        cartoes_catalogo()


def cartoes_catalogo():
    # Todos os cartões do painel num lugar só, com uma busca pelo nome, descrição ou ID
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="linha_busca_catalogo"):
        busca = st.text_input("Pesquisar componente", placeholder="Pesquisar por nome", width=260,
                              key="busca_catalogo", label_visibility="collapsed").strip().lower()
        st.button("Pesquisar", key="pesquisar_catalogo")   # o texto já vale ao apertar Enter
    chaves = [c for c, (id_c, *_) in CARTOES.items()
              if busca in f"{TITULOS_CARTOES[c]} {RESUMO_CARTOES[c][0]} {id_c} {c}".lower()]
    if not chaves:
        st.markdown('<div class="aviso-vazio">Nenhum componente encontrado.</div>', unsafe_allow_html=True)
        return
    with st.container(key="grade_catalogo"):
        for inicio in range(0, len(chaves), 2):
            colunas = st.columns(2, gap="medium")
            for coluna, chave in zip(colunas, chaves[inicio:inicio + 2]):
                with coluna:
                    item_catalogo(chave)


# --- PÁGINA DE UM COMPONENTE (ComponentInfoView do Taipei) ---
def pagina_componente():
    """Página só de um cartão: o cartão à esquerda e, à direita, ID, descrição, exemplo de uso, dados
    relacionados, colaboradores e os botões Reportar / Baixar / Incorporar."""
    chave = st.session_state.get("componente")
    if chave not in CARTOES:   # componente que não existe mais: volta ao catálogo
        st.session_state.pagina = "catalogo"
        st.rerun()
    if st.button("Voltar ao catálogo de componentes", icon=":material/arrow_circle_left:", type="tertiary",
                 key="voltar_catalogo"):
        st.session_state.pagina = "catalogo"
        st.rerun()
    _, desenhar_grafico, desenhar_descricao = CARTOES[chave]
    global altura_descricao
    col_cartao, col_texto = st.columns([1, 1.2], gap="large")
    with col_cartao, st.container(key="pagina_componente_cartao"), st.container(key=f"cartao_{chave}"), \
            st.container(key=f"grafico_{chave}"):
        resultado = desenhar_grafico()
    altura_descricao = 560   # mais alto que na janela: acompanha o cartão ao lado
    try:
        with col_texto, st.container(key="pagina_componente_texto"):
            desenhar_descricao(resultado)
    finally:
        altura_descricao = 440


# --- PÁGINA "COMPARAÇÃO DE MAPAS" (MapView do Taipei) ---
def camadas_do_painel(painel):
    usadas = {c for chave_cartao in cartoes_do_painel(painel) for c in CAMADAS_DO_CARTAO[chave_cartao]}
    return [c for c in CAMADAS if c in usadas]   # sempre na mesma ordem


def linhas_no_mapa(fig, geojson, cores, chave_filtro):
    """Desenha ruas ou estradas, uma cor por tipo, respeitando o "Filtrar mapa"."""
    for tipo, cor in cores.items():
        if tipo not in st.session_state.get(chave_filtro, list(cores)):
            continue
        lat, lon, nomes = [], [], []
        for via in geojson["features"]:
            if via["properties"]["tipo"] == tipo:
                # Todas as vias do tipo numa linha só, separadas por um ponto vazio (mais rápido)
                rotulo = " – ".join(p for p in (via["properties"].get("ref"), via["properties"]["nome"])
                                    if p and p != "Sem nome") or "Sem nome"
                lon += [c[0] for c in via["geometry"]["coordinates"]] + [None]
                lat += [c[1] for c in via["geometry"]["coordinates"]] + [None]
                nomes += [rotulo] * len(via["geometry"]["coordinates"]) + [None]
        fig.add_trace(go.Scattermap(
            lat=lat, lon=lon, mode="lines", name=tipo, text=nomes, customdata=[[n] for n in nomes], meta=["Via"],
            line=dict(color=cor, width=3 if tipo == list(cores)[0] else 1.6),
            hovertemplate=f"%{{text}}<br>{tipo}<extra></extra>",
        ))


def centro_do_mapa(ligadas):
    # Só a camada da região: mostra os 9 municípios; nas outras, a sede de Oriximiná
    regionais = {"municipios_cn", "frota_cn", "estradas_cn", "limites_cn", "sedes_cn"}
    if ligadas and all(c in regionais or camada_nova_regional(c) for c in ligadas):
        return dict(style="carto-darkmatter", center=dict(lat=-0.9, lon=-55.0), zoom=5.6)
    return dict(style="carto-darkmatter", center=dict(lat=-1.763, lon=-55.866), zoom=12.3)


def filtrar(camada, df, coluna):
    """Só as linhas da categoria escolhida no gráfico da camada ("Clique numa barra para filtrar o mapa")."""
    escolhida = filtro_do_mapa(camada)
    return df if escolhida is None else df[df[coluna].astype(str) == escolhida]


def figura_mapa(ligadas):
    fig = go.Figure()
    setores = df_setores[df_setores["Habitantes"].fillna(0) > 0]
    escala_idosos = ["#5c4a1d", "#8a6d25", "#c99a33", "#F8CF58"]
    for camada, coluna, cores in (("populacao", "Habitantes", ESCALA_AZUL),
                                  ("idosos", "60 anos ou mais", escala_idosos)):
        if camada in ligadas:
            setores_camada = filtrar(camada, setores, "Zona")
            fig.add_trace(go.Choroplethmap(
                geojson=geojson_oriximina, featureidkey="properties.CD_SETOR",
                locations=setores_camada["CD_SETOR"], z=setores_camada[coluna], colorscale=cores, showscale=False,
                zmin=setores[coluna].min(), zmax=setores[coluna].max(),
                marker_opacity=0.5, marker_line_width=0.6, marker_line_color="#1e1f21",
                customdata=setores_camada[["Localidade", coluna]], name=CAMADAS[camada][0], meta=["Localidade", coluna],
                hovertemplate=f"%{{customdata[0]}}<br>{coluna}: %{{customdata[1]:,.0f}}<extra></extra>",
            ))
    if "bairros" in ligadas:
        transparente = "rgba(255,255,255,0.06)"
        bairros = filtrar("bairros", df_bairros, "nome")
        fig.add_trace(go.Choroplethmap(
            geojson=geojson_bairros, featureidkey="properties.nome", locations=bairros["nome"],
            z=[1] * len(bairros), colorscale=[[0, transparente], [1, transparente]], showscale=False,
            marker_line_width=1.5, marker_line_color="#ffffff", name=CAMADAS["bairros"][0],
            customdata=[[nome] for nome in bairros["nome"]], meta=["Bairro"],
            hovertemplate="Bairro: %{location}<extra></extra>",
        ))
    if "municipios_cn" in ligadas:
        municipios = filtrar("municipios_cn", df_regiao_idades, "Nome")
        fig.add_trace(go.Choroplethmap(
            geojson=geojson_regiao, featureidkey="properties.codigo", locations=municipios["codigo"],
            z=municipios["Habitantes"], colorscale=ESCALA_AZUL, showscale=False, marker_opacity=0.6,
            # Com um só município, a escala fixa da região mantém a cor dele
            zmin=df_regiao_idades["Habitantes"].min(), zmax=df_regiao_idades["Habitantes"].max(),
            marker_line_width=1.5, marker_line_color="#ffffff", name=CAMADAS["municipios_cn"][0],
            customdata=municipios[["Nome", "Habitantes"]], meta=["Município", "Habitantes"],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]:,.0f} habitantes<extra></extra>",
        ))
    if "frota_cn" in ligadas:
        frota = filtrar("frota_cn", df_frota, "Nome")
        fig.add_trace(go.Choroplethmap(
            geojson=geojson_regiao, featureidkey="properties.codigo", locations=frota["codigo"],
            z=frota["Total"], zmin=df_frota["Total"].min(), zmax=df_frota["Total"].max(), colorscale=[[0, COR_TRANSPORTE_ESCURA], [1, COR_TRANSPORTE]], showscale=False,
            marker_opacity=0.65, marker_line_width=1.5, marker_line_color="#ffffff", name=CAMADAS["frota_cn"][0],
            customdata=frota[["Nome", "Total", "Motocicletas"]], meta=["Município", "Veículos", "Motocicletas"],
            hovertemplate=("%{customdata[0]}<br>%{customdata[1]:,.0f} veículos<br>"
                           "%{customdata[2]:,.0f} motocicletas<extra></extra>"),
        ))
    if "vias" in ligadas:
        linhas_no_mapa(fig, geojson_vias, CORES_VIAS, "filtro_vias")
    if "limites_cn" in ligadas:
        transparente = "rgba(255,255,255,0.04)"
        limites = filtrar("limites_cn", df_regiao_idades, "Nome")
        fig.add_trace(go.Choroplethmap(
            geojson=geojson_regiao, featureidkey="properties.codigo", locations=limites["codigo"],
            z=[1] * len(limites), colorscale=[[0, transparente], [1, transparente]], showscale=False,
            marker_line_width=1.5, marker_line_color="#ffffff", name=CAMADAS["limites_cn"][0],
            customdata=[[nome] for nome in limites["Nome"]], meta=["Município"],
            hovertemplate="%{customdata[0]}<extra></extra>",
        ))
    if "estradas_cn" in ligadas:
        linhas_no_mapa(fig, geojson_estradas, CORES_ESTRADAS, "filtro_estradas")
    if "sedes_cn" in ligadas:
        sedes = filtrar("sedes_cn", df_sedes, "Nome")
        fig.add_trace(go.Scattermap(
            lat=sedes["Latitude"], lon=sedes["Longitude"], mode="markers+text", text=sedes["Nome"],
            textposition="top right", textfont=dict(color="#ffffff", size=13), name=CAMADAS["sedes_cn"][0],
            customdata=[[nome] for nome in sedes["Nome"]], meta=["Sede de"],
            marker=dict(size=11, color="#F65658"), hovertemplate="Sede de %{text}<extra></extra>",
        ))
    for camada in ("saude", "ensino"):
        if camada in ligadas:
            pontos = filtrar(camada, df_pontos[df_pontos["Tipo"] == TIPO_PONTO[camada]], "Localidade")
            fig.add_trace(go.Scattermap(
                lat=pontos["Latitude"], lon=pontos["Longitude"], mode="markers", name=CAMADAS[camada][0],
                marker=dict(size=10, color=COR_PONTOS[camada]), customdata=pontos[["Nome", "Localidade"]],
                meta=["Nome", "Localidade"],
                hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
            ))
    # Camadas dos componentes criados na administração
    for camada in ligadas:
        if camada.startswith("novo_"):
            desenhar_camada_nova(fig, camada)
    # Ocorrências relatadas pelos cidadãos (botão "Relatar ocorrência")
    if st.session_state.get("mostrar_ocorrencias"):
        # Só as aprovadas na área de administração (quem é administrador vê também as pendentes)
        ocorrencias = [o for o in carregar_ocorrencias()
                       if o.get("status", "Pendente") == "Aprovada"
                       or (e_admin() and o.get("status", "Pendente") == "Pendente")]
        if ocorrencias:
            fig.add_trace(go.Scattermap(
                lat=[o["lat"] for o in ocorrencias], lon=[o["lon"] for o in ocorrencias], mode="markers",
                name="Ocorrências relatadas", marker=dict(size=13, color=COR_OCORRENCIA),
                customdata=[[o["tipo"], o["descricao"], o["local"], o["data"]] for o in ocorrencias],
                meta=["Tipo", "Descrição", "Local", "Relatada em"],
                hovertemplate="%{customdata[0]}<br>%{customdata[1]}<br>%{customdata[3]}<extra></extra>",
            ))
    # Marcos salvos (pins azuis com o nome) e o marco novo, ainda sem nome, marcado com dois cliques
    marcos = marcos_salvos()
    if marcos:
        fig.add_trace(go.Scattermap(
            lat=[m["lat"] for m in marcos], lon=[m["lon"] for m in marcos], mode="markers+text",
            text=[m["nome"] for m in marcos], textposition="top center", textfont=dict(color="#ffffff", size=13),
            name=NOME_CAMADA_MARCOS, marker=dict(size=15, color=COR_MARCO),
            customdata=[[m["nome"]] for m in marcos], meta=["Marco"],
            hovertemplate="Marco: %{text}<extra></extra>"))
    novo = marco_temporario()
    if novo:
        fig.add_trace(go.Scattermap(
            lat=[novo["lat"]], lon=[novo["lon"]], mode="markers", name="Marco novo",
            marker=dict(size=17, color="#ffffff"), customdata=[["Marco novo (ainda sem nome)"]],
            hovertemplate="Marco novo: abra “Pontos de vista” e clique em “Adicionar marco”<extra></extra>"))
    # Minha localização: ponto azul com um halo em volta (como o GeolocateControl do mapa do Taipei)
    local = minha_localizacao()
    if local and "lat" in local:
        precisao = f"± {local.get('precisao', 0):.0f} m"
        fig.add_trace(go.Scattermap(
            lat=[local["lat"]] * 2, lon=[local["lon"]] * 2, mode="markers", name="Minha localização",
            marker=dict(size=[34, 13], color=["rgba(90,156,248,0.25)", COR_MARCO]),
            customdata=[["Minha localização", precisao]] * 2, meta=["Nome", "Precisão"],
            hovertemplate="Minha localização<br>Precisão: %{customdata[1]}<extra></extra>"))
    # Resultado do "Ponto mais próximo": linha tracejada da partida até o ponto encontrado
    proximo = st.session_state.get("resultado_proximo")
    if proximo:
        fig.add_trace(go.Scattermap(
            lat=[proximo["lat_partida"], proximo["lat"]], lon=[proximo["lon_partida"], proximo["lon"]],
            mode="lines", line=dict(color="#ffffff", width=2), name="Distância", hoverinfo="skip"))
        fig.add_trace(go.Scattermap(
            lat=[proximo["lat_partida"], proximo["lat"]], lon=[proximo["lon_partida"], proximo["lon"]],
            mode="markers", marker=dict(size=[12, 18], color=["#ffffff", "#5a9cf8"]), name="Ponto mais próximo",
            customdata=[[proximo["partida"], "Ponto de partida"],
                        [proximo["nome"], f"{formatar_distancia(proximo['distancia'])} de {proximo['partida']}"]],
            meta=["Nome", "Distância"], hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
    # Ao clicar, o ponto escolhido não deve apagar os outros (o Plotly apaga os "não selecionados")
    for trace in fig.data:
        opacidade = trace.marker.opacity if trace.marker.opacity is not None else 1
        trace.unselected = dict(marker=dict(opacity=opacidade))
    # Posição e zoom: ficam onde a pessoa deixou (uirevision); um ponto de vista salvo leva o mapa até ele
    mapa = centro_do_mapa(ligadas)
    vista = st.session_state.get("vista_mapa")
    regiao = mapa["zoom"] < 8
    if vista:
        mapa.update(center=dict(lat=vista["lat"], lon=vista["lon"]), zoom=vista["zoom"])
    fig.update_layout(
        map=mapa, uirevision=f"{'regiao' if regiao else 'sede'}-{vista['n'] if vista else 0}",
        height=780, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=COR_CARTAO, separators=",.",
        font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"), showlegend=False,
        hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white", size=14)),
    )
    return fig


# --- FERRAMENTAS DO MAPA: pontos de vista, ponto mais próximo, ocorrências e janelinha ao clicar ---
# (AddViewPoint, FindClosestPoint, IncidentReport e MapPopup do Taipei)
COR_OCORRENCIA = "#ff8a3d"
ARQ_OCORRENCIAS = os.path.join(PASTA_USUARIOS, "ocorrencias_painel.json")
TIPOS_OCORRENCIA = ["Buraco ou problema na via", "Iluminação pública", "Lixo ou entulho", "Alagamento",
                    "Árvore caída", "Falta de água", "Outro"]
# Onde procurar no "Ponto mais próximo"
ALVOS_PROXIMO = {
    "Estabelecimentos de saúde": lambda: df_pontos[df_pontos["Tipo"] == TIPO_PONTO["saude"]],
    "Estabelecimentos de ensino": lambda: df_pontos[df_pontos["Tipo"] == TIPO_PONTO["ensino"]],
    "Sedes municipais da Calha Norte": lambda: df_sedes.assign(Localidade="Sede municipal"),
}


COR_MARCO = "#5a9cf8"
NOME_CAMADA_MARCOS = "Marcos"


def marcos_salvos():
    """Os marcos (pins) ficam na mesma lista dos pontos de vista, com "tipo": "marco" (como no Taipei)."""
    return [v for v in st.session_state.pontos_de_vista if v.get("tipo") == "marco"]


def marco_temporario():
    """Lugar marcado com dois cliques no mapa (o script escreve no campo escondido), ou None."""
    try:
        novo = json.loads(st.session_state.get("marco_temporario") or "")
        return novo if isinstance(novo, dict) and "lat" in novo else None
    except ValueError:
        return None


def minha_localizacao():
    """Posição dada pelo navegador (GPS do celular ou localização do computador), ou None.
    O script do mapa escreve no campo escondido {lat, lon, precisao} ou {erro} ao clicar em "Minha localização"."""
    try:
        local = json.loads(st.session_state.get("minha_localizacao") or "")
        return local if isinstance(local, dict) else None
    except ValueError:
        return None


def carregar_ocorrencias():
    return carregar_json(ARQ_OCORRENCIAS, [])


def salvar_pontos_de_vista():
    if st.session_state.usuario:
        usuarios = carregar_usuarios()
        usuarios[st.session_state.usuario["email"]]["pontos_de_vista"] = st.session_state.pontos_de_vista
        salvar_usuarios(usuarios)


def distancia_km(lat1, lon1, lat2, lon2):
    """Distância em linha reta (fórmula de haversine); lat2/lon2 podem ser colunas inteiras."""
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = lat2 * math.pi / 180, lon2 * math.pi / 180
    a = ((lat2 - lat1) / 2).map(math.sin) ** 2 + math.cos(lat1) * lat2.map(math.cos) * (
        ((lon2 - lon1) / 2).map(math.sin) ** 2)
    return 2 * 6371 * a.map(lambda x: math.asin(math.sqrt(x)))


def formatar_distancia(km):
    return f"{km * 1000:.0f} m" if km < 1 else f"{km:.1f} km".replace(".", ",")


def ir_para(lat, lon, zoom):
    """Leva o mapa até um lugar (muda o uirevision, e o Plotly aceita o novo centro e zoom)."""
    st.session_state.vista_n = st.session_state.get("vista_n", 0) + 1
    st.session_state.vista_mapa = dict(lat=lat, lon=lon, zoom=zoom, n=st.session_state.vista_n)


@st.cache_data
def pontos_de_partida():
    """Centro de cada bairro da sede e de cada localidade do Censo, para escolher de onde partir."""
    partidas = {}
    for feature in geojson_bairros["features"]:
        centro = shapely.geometry.shape(feature["geometry"]).centroid
        partidas[f"Bairro: {feature['properties']['nome']}"] = (centro.y, centro.x)
    centros = {}
    for feature, setor in zip(geojson_oriximina["features"], lista_setores):
        if setor["Localidade"] != "Não identificada":
            centro = shapely.geometry.shape(feature["geometry"]).centroid
            centros.setdefault(setor["Localidade"], []).append((centro.y, centro.x))
    for nome in sorted(centros):
        lista = centros[nome]
        partidas[f"Localidade: {nome}"] = (sum(p[0] for p in lista) / len(lista),
                                           sum(p[1] for p in lista) / len(lista))
    return partidas


def partidas_disponiveis():
    """O ponto clicado no mapa, os pontos de vista salvos e os bairros/localidades."""
    partidas = {}
    local = minha_localizacao()
    if local and "lat" in local:   # como no Taipei, a localização da pessoa vem primeiro
        partidas["Minha localização"] = (local["lat"], local["lon"])
    clique = st.session_state.get("ultimo_clique")
    if clique:
        partidas[f"Ponto clicado no mapa ({clique['nome']})"] = (clique["lat"], clique["lon"])
    for vista in st.session_state.pontos_de_vista:
        tipo = "Marco" if vista.get("tipo") == "marco" else "Ponto de vista"
        partidas[f"{tipo}: {vista['nome']}"] = (vista["lat"], vista["lon"])
    partidas.update(pontos_de_partida())
    return partidas


def nome_do_local(opcao):
    """Texto da opção de partida/local sem o prefixo: "Bairro: Centro" -> "Centro";
    "Ponto clicado no mapa (Escola X)" -> "Escola X"."""
    if opcao.startswith("Ponto clicado no mapa (") and opcao.endswith(")"):
        return opcao[len("Ponto clicado no mapa ("):-1]
    return opcao.split(": ", 1)[-1]


def limpar_ponto_de_vista():
    st.session_state.pop("pv_nome", None)


@st.dialog("Adicionar ponto de vista", width="small", on_dismiss=limpar_ponto_de_vista)
def janela_ponto_de_vista():
    """Guarda a posição e o zoom atuais do mapa com um nome (até 10 letras, como no Taipei)."""
    try:
        vista = json.loads(st.session_state.get("vista_atual_mapa") or "")
    except ValueError:
        vista = None
    if not vista:
        st.markdown('<div class="aviso-vazio">Não foi possível ler a posição do mapa. Feche esta janela, '
                    'mexa um pouco no mapa e tente de novo.</div>', unsafe_allow_html=True)
        return
    nome_atual = st.session_state.get("pv_nome", "")
    nome = st.text_input(f"Nome do ponto de vista* ({len(nome_atual)}/10)", max_chars=10, key="pv_nome",
                         placeholder="Ex.: Centro").strip()
    st.markdown(f'<div class="catalogo-fonte">Posição: {vista["lat"]:.5f}, {vista["lon"]:.5f} · '
                f'zoom {vista["zoom"]:.1f}</div>', unsafe_allow_html=True)
    if not st.session_state.usuario:
        st.markdown('<div class="catalogo-fonte">Sem entrar na conta, o ponto de vista vale só até fechar '
                    'a página.</div>', unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Confirmar", type="primary", key="pv_confirmar"):
            if not nome:
                st.session_state.aviso = "Dê um nome ao ponto de vista"
            else:
                st.session_state.pontos_de_vista.append(
                    {"nome": nome, "lat": vista["lat"], "lon": vista["lon"], "zoom": vista["zoom"]})
                salvar_pontos_de_vista()
                st.session_state.aviso = f"Ponto de vista {nome} salvo"
            limpar_ponto_de_vista()
            st.rerun()


def limpar_marco():
    st.session_state.pop("marco_nome", None)


@st.dialog("Adicionar marco", width="small", on_dismiss=limpar_marco)
def janela_marco():
    """Dá nome ao marco marcado com dois cliques no mapa (o "Adicionar marco" do Taipei)."""
    novo = marco_temporario()
    if not novo:
        st.markdown('<div class="aviso-vazio">Dê dois cliques no mapa, no lugar do marco, e depois clique de novo '
                    'em “Adicionar marco”.</div>', unsafe_allow_html=True)
        return
    nome_atual = st.session_state.get("marco_nome", "")
    nome = st.text_input(f"Nome do marco* ({len(nome_atual)}/10)", max_chars=10, key="marco_nome",
                         placeholder="Ex.: Minha casa").strip()
    st.markdown(f'<div class="catalogo-fonte">Posição: {novo["lat"]:.5f}, {novo["lon"]:.5f}</div>',
                unsafe_allow_html=True)
    if not st.session_state.usuario:
        st.markdown('<div class="catalogo-fonte">Sem entrar na conta, o marco vale só até fechar a página.</div>',
                    unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Confirmar", type="primary", key="marco_confirmar"):
            if not nome:
                st.session_state.aviso = "Dê um nome ao marco"
            else:
                st.session_state.pontos_de_vista.append(
                    {"nome": nome, "lat": novo["lat"], "lon": novo["lon"], "zoom": 16.0, "tipo": "marco"})
                salvar_pontos_de_vista()
                st.session_state.limpar_marco_temporario = True   # tira o pin branco temporário
                st.session_state.aviso = f"Marco {nome} adicionado"
            limpar_marco()
            st.rerun()


@st.dialog("Ponto mais próximo", width="small")
def janela_ponto_proximo():
    """Escolhe um ponto de partida e o que procurar; mostra no mapa o mais próximo em linha reta."""
    partidas = partidas_disponiveis()
    if st.session_state.get("proximo_partida") not in partidas:
        st.session_state.proximo_partida = next(iter(partidas))
    partida = st.selectbox("Ponto de partida", list(partidas), key="proximo_partida")
    alvo = st.selectbox("Procurar", list(ALVOS_PROXIMO), key="proximo_alvo")
    st.markdown('<div class="catalogo-fonte">A distância é em linha reta, não pelo caminho das ruas.</div>',
                unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Procurar", type="primary", key="proximo_procurar"):
            lat0, lon0 = partidas[partida]
            locais = ALVOS_PROXIMO[alvo]().reset_index(drop=True)
            distancias = distancia_km(lat0, lon0, locais["Latitude"], locais["Longitude"])
            mais_perto = locais.loc[distancias.idxmin()]
            km = float(distancias.min())
            st.session_state.resultado_proximo = dict(
                partida=nome_do_local(partida), lat_partida=lat0, lon_partida=lon0, alvo=alvo,
                nome=mais_perto["Nome"], localidade=mais_perto["Localidade"], distancia=km,
                lat=float(mais_perto["Latitude"]), lon=float(mais_perto["Longitude"]))
            # Zoom de acordo com a distância, para a partida e o ponto aparecerem juntos
            ir_para((lat0 + mais_perto["Latitude"]) / 2, (lon0 + mais_perto["Longitude"]) / 2,
                    max(5.5, min(16.0, 14.5 - math.log2(max(km, 0.2)))))
            st.rerun()


def limpar_ocorrencia():
    for chave in ("ocorrencia_descricao", "ocorrencia_incompleta"):
        st.session_state.pop(chave, None)


@st.dialog("Relatar ocorrência", width="small", on_dismiss=limpar_ocorrencia)
def janela_ocorrencia():
    """O cidadão avisa de um problema na cidade: tipo, descrição, local, posição e hora (como no Taipei)."""
    partidas = partidas_disponiveis()
    if st.session_state.get("ocorrencia_local") not in partidas:
        st.session_state.ocorrencia_local = next(iter(partidas))
    tipo = st.selectbox("Tipo de ocorrência", TIPOS_OCORRENCIA, key="ocorrencia_tipo")
    descricao_atual = st.session_state.get("ocorrencia_descricao", "")
    descricao = st.text_input(f"Descrição* ({len(descricao_atual)}/100)", max_chars=100,
                              key="ocorrencia_descricao", placeholder="Conte em poucas palavras o que aconteceu")
    if st.session_state.pop("ocorrencia_incompleta", False):
        st.markdown('<div style="color:#e5484d; font-size:0.9rem;">Escreva uma descrição.</div>',
                    unsafe_allow_html=True)
    local = st.selectbox("Local da ocorrência", list(partidas), key="ocorrencia_local")
    lat, lon = partidas[local]
    st.text_input("Posição", value=f"{lat:.5f}, {lon:.5f}", disabled=True)
    agora = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
    st.text_input("Data e hora", value=agora, disabled=True)
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Enviar", type="primary", key="ocorrencia_enviar"):
            if not descricao.strip():
                st.session_state.ocorrencia_incompleta = True
                st.rerun(scope="fragment")
            ocorrencias = carregar_ocorrencias()
            ocorrencias.append({
                "id": max([o["id"] for o in ocorrencias], default=0) + 1, "tipo": tipo,
                "descricao": descricao.strip(), "local": nome_do_local(local), "lat": lat, "lon": lon,
                "data": agora, "usuario": (st.session_state.usuario or {}).get("email", "anônimo"),
                "status": "Pendente"})   # a administração aprova ou rejeita (como no Taipei)
            salvar_json(ARQ_OCORRENCIAS, ocorrencias)
            limpar_ocorrencia()
            st.session_state.aviso = "Ocorrência enviada. Ela aparece no mapa depois de aprovada. Obrigado!"
            st.rerun()


@st.cache_data(ttl=60, show_spinner=False)
def endereco_https():
    """Endereço https:// do túnel da Cloudflare (serviço "tunel" do docker-compose.yml), ou None.
    O túnel diz o endereço atual em http://tunel:20241/quicktunnel; fora do Docker, ou com o túnel
    desligado, a pergunta falha e não há link."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://tunel:20241/quicktunnel", timeout=1.5) as resposta:
            nome = json.loads(resposta.read()).get("hostname")
        return f"https://{nome}" if nome else None
    except Exception:
        return None


def barra_ferramentas_mapa():
    """Botões em cima do mapa: pontos de vista, ponto mais próximo, relatar ocorrência e ocorrências."""
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="barra_mapa"):
        # Campo escondido: com dois cliques no mapa, o script escreve aqui o lugar do marco novo
        if st.session_state.pop("limpar_marco_temporario", False):
            st.session_state.marco_temporario = ""
        st.text_input("Marco novo", key="marco_temporario", label_visibility="collapsed")
        # Campo escondido: o script escreve aqui a posição que o navegador deu (ou o erro)
        st.text_input("Minha localização", key="minha_localizacao", label_visibility="collapsed")
        local = minha_localizacao()
        if local and local.get("t") != st.session_state.get("localizacao_tratada"):
            st.session_state.localizacao_tratada = local.get("t")
            if "erro" in local:
                aviso = local["erro"]
                # Aberto por http (ex.: o endereço da rede de casa no celular): se o túnel estiver ligado,
                # o aviso já traz o link https, mantendo a conta de quem entrou
                link = endereco_https() if "https://" in aviso else None
                if link:
                    sessao = st.query_params.get("sessao")
                    link += f"/?sessao={sessao}" if sessao else ""
                    aviso += f" [Abrir pelo endereço seguro]({link})"
                st.toast(aviso, icon=":material/location_off:")
            else:   # posição nova: leva o mapa até ela
                ir_para(local["lat"], local["lon"], 15.5)
        # Quem pede a localização é o script do mapa (no navegador); o clique não recarrega a página
        st.button("Minha localização", icon=":material/my_location:", key="botao_minha_localizacao",
                  help="Mostrar no mapa onde você está (o navegador pede permissão)")
        with st.popover("Pontos de vista", icon=":material/bookmark:", key="popover_pontos_vista"):
            # Campo escondido: o script do mapa escreve aqui a posição e o zoom antes do "Adicionar"
            st.text_input("Posição do mapa", key="vista_atual_mapa", label_visibility="collapsed")
            # Pontos de vista e marcos na mesma lista (como no Taipei), mostrados em duas partes
            for titulo_lista, e_marco, icone, vazio in (
                    ("Pontos de vista", False, "location_on", "Nenhum ponto de vista salvo"),
                    ("Marcos", True, "push_pin", "Nenhum marco salvo")):
                st.markdown(f'<div class="menu-grupo" style="margin-left:0">{titulo_lista}</div>',
                            unsafe_allow_html=True)
                itens = [(i, v) for i, v in enumerate(st.session_state.pontos_de_vista)
                         if (v.get("tipo") == "marco") == e_marco]
                if not itens:
                    st.markdown(f'<div class="menu-vazio" style="margin-left:0">{vazio}</div>', unsafe_allow_html=True)
                for i, vista in itens:
                    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                        if st.button(vista["nome"], icon=f":material/{icone}:", type="tertiary", key=f"pv_ir_{i}"):
                            ir_para(vista["lat"], vista["lon"], vista["zoom"])
                            st.rerun()
                        if st.button("", icon=":material/close:", type="tertiary", key=f"pv_apagar_{i}",
                                     help="Apagar"):
                            st.session_state.pontos_de_vista.pop(i)
                            salvar_pontos_de_vista()
                            st.rerun()
            if st.button("Adicionar ponto de vista", icon=":material/add_location_alt:",
                         key="adicionar_ponto_vista", width="stretch"):
                janela_ponto_de_vista()
            if st.button("Adicionar marco", icon=":material/push_pin:", key="adicionar_marco", width="stretch"):
                janela_marco()
            if not marco_temporario():
                st.markdown('<div class="catalogo-fonte">Para um marco, dê dois cliques no mapa, no lugar '
                            'desejado.</div>', unsafe_allow_html=True)
        if st.button("Ponto mais próximo", icon=":material/near_me:", key="abrir_ponto_proximo"):
            janela_ponto_proximo()
        if st.button("Relatar ocorrência", icon=":material/campaign:", key="abrir_ocorrencia"):
            janela_ocorrencia()
        st.toggle("Mostrar ocorrências", key="mostrar_ocorrencias")
        # Prédios em 3D (o botão de prédios 3D do mapa do Taipei)
        st.toggle("Prédios em 3D", key="predios_3d", disabled=publicar_predios() is None,
                  help="Levanta os prédios da sede de Oriximiná e inclina o mapa (aproxime o mapa da sede)"
                  if publicar_predios() else "Rode o script preparar_predios.py para gerar os prédios")
    if st.session_state.get("predios_3d") and publicar_predios():
        st.markdown('<div class="aviso-predios"><span class="icone-material">apartment</span>'
                    f'{TEXTO_FONTE_PREDIOS}</div>', unsafe_allow_html=True)
    proximo = st.session_state.get("resultado_proximo")
    if proximo:
        with st.container(horizontal=True, vertical_alignment="center", key="resultado_proximo_caixa"):
            st.markdown(f'<div class="resultado-proximo"><span class="icone-material">near_me</span>'
                        f'Mais perto de <b>{html.escape(proximo["partida"])}</b>: '
                        f'<b>{html.escape(str(proximo["nome"]))}</b> ({html.escape(str(proximo["localidade"]))}), '
                        f'a {formatar_distancia(proximo["distancia"])} em linha reta</div>', unsafe_allow_html=True)
            if st.button("Limpar", type="tertiary", key="limpar_proximo"):
                st.session_state.pop("resultado_proximo")
                st.rerun()


def info_do_clique(fig, ponto):
    """Título, camada, linhas de informação e posição do item clicado no mapa (ou None)."""
    numero = ponto.get("curve_number")
    if numero is None or numero >= len(fig.data):
        return None
    trace = fig.data[numero]
    valores = ponto.get("customdata")
    valores = list(valores) if isinstance(valores, (list, tuple)) else ([valores] if valores is not None else [])
    # O clique pode ter vindo de outro desenho do mapa (camadas trocadas): confere com os dados da camada
    indice = ponto.get("point_index")
    if trace.customdata is not None and indice is not None and indice < len(trace.customdata):
        # Só o primeiro campo (o nome): números podem voltar em outro formato (123 e 123.0)
        esperado = trace.customdata[indice]
        esperado = esperado[0] if hasattr(esperado, "__len__") and not isinstance(esperado, str) else esperado
        if valores and str(esperado) != str(valores[0]):
            return None
    if "ct" in ponto:
        lon, lat = ponto["ct"]
    elif "lat" in ponto:
        lat, lon = ponto["lat"], ponto["lon"]
    else:
        return None
    rotulos = list(trace.meta or [])
    texto = [formatar(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)
             for v in valores if v is not None]
    titulo = texto[0] if texto else str(ponto.get("location", trace.name))
    linhas = [(rotulos[i] if i < len(rotulos) else "", v) for i, v in enumerate(texto) if i > 0]
    return dict(titulo=titulo, camada=trace.name, linhas=linhas, lat=lat, lon=lon,
                assinatura=f"{numero}-{indice}-{titulo}")


def janelinha_do_mapa(info):
    """Janelinha sobre o mapa com os detalhes do item clicado (MapPopup do Taipei)."""
    with st.container(key="popup_mapa"):
        with st.container(horizontal=True, vertical_alignment="top", key="popup_topo"):
            st.markdown(f'<div class="popup-titulo">{html.escape(info["titulo"])}</div>'
                        f'<div class="popup-camada">{html.escape(str(info["camada"]))}</div>', unsafe_allow_html=True)
            if st.button("", icon=":material/close:", type="tertiary", key="fechar_popup", help="Fechar"):
                st.session_state.popup_fechado = info["assinatura"]
                st.rerun()
        linhas = "".join(f'<div class="popup-linha"><span>{html.escape(r)}</span>{html.escape(v)}</div>'
                         for r, v in info["linhas"])
        st.markdown(f'{linhas}<div class="popup-linha"><span>Posição</span>{info["lat"]:.5f}, {info["lon"]:.5f}</div>',
                    unsafe_allow_html=True)
        with st.container(horizontal=True, gap="small"):
            if st.button("Ponto mais próximo daqui", icon=":material/near_me:", key="popup_proximo"):
                st.session_state.proximo_partida = f"Ponto clicado no mapa ({info['titulo']})"
                janela_ponto_proximo()
            if st.button("Relatar ocorrência aqui", icon=":material/campaign:", key="popup_ocorrencia"):
                st.session_state.ocorrencia_local = f"Ponto clicado no mapa ({info['titulo']})"
                janela_ocorrencia()
        # Marco salvo: pode ser apagado daqui mesmo (como o botão da janelinha do pin no Taipei)
        if info["camada"] == NOME_CAMADA_MARCOS and st.button("Apagar marco", icon=":material/delete:",
                                                               type="tertiary", key="popup_apagar_marco"):
            st.session_state.pontos_de_vista = [
                v for v in st.session_state.pontos_de_vista
                if not (v.get("tipo") == "marco" and v["nome"] == info["titulo"]
                        and abs(v["lat"] - info["lat"]) < 1e-6 and abs(v["lon"] - info["lon"]) < 1e-6)]
            salvar_pontos_de_vista()
            st.session_state.popup_fechado = info["assinatura"]
            st.session_state.aviso = f"Marco {info['titulo']} apagado"
            st.rerun()


def script_mapa():
    """Antes do "Adicionar ponto de vista", copia a posição e o zoom do mapa para o campo escondido
    (o Streamlit não recebe do Plotly onde a pessoa deixou o mapa)."""
    st.iframe("""<script>
    const d = window.parent.document;
    // "Minha localização": pede a posição ao navegador e manda para o campo escondido
    if (!d.getElementById("script-localizacao")) {
        const s = d.createElement("script");
        s.id = "script-localizacao";
        s.textContent = `
            function escreverLocalizacao(dados) {
                const campo = document.querySelector(".st-key-minha_localizacao input");
                if (!campo) return;
                dados.t = Date.now();   // valor sempre novo, mesmo clicando de novo no mesmo lugar
                campo.focus();
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(
                    campo, JSON.stringify(dados));
                campo.dispatchEvent(new Event("input", {bubbles: true}));
                campo.blur();
            }
            document.addEventListener("click", (ev) => {
                const botao = ev.target.closest && ev.target.closest(".st-key-botao_minha_localizacao button");
                if (!botao) return;
                ev.preventDefault();
                ev.stopPropagation();   // o clique fica só com o navegador: a página não recarrega à toa
                if (!navigator.geolocation || !window.isSecureContext) {
                    // (curta: o Streamlit corta avisos longos com "view more")
                    escreverLocalizacao({erro: "Localização bloqueada: ela só funciona em endereços https://."});
                    return;
                }
                const achou = (p) => escreverLocalizacao({lat: p.coords.latitude, lon: p.coords.longitude,
                                                          precisao: p.coords.accuracy});
                // Avisos curtos (o Streamlit corta os longos com "view more"), com o caminho certo
                // para liberar a localização em cada aparelho
                const agente = navigator.userAgent;
                const iphone = /iPhone|iPad|iPod/.test(agente) ||
                               (agente.includes("Mac") && navigator.maxTouchPoints > 1);
                const android = /Android/.test(agente);
                const bloqueada = iphone
                    ? "Localização bloqueada. Libere em Ajustes > Privacidade > Serviços de Localização."
                    : android ? "Localização bloqueada. Libere em Configurações do site, no menu ⋮ do navegador."
                    : "Localização bloqueada. Clique no cadeado ao lado do endereço e permita.";
                const falhou = (e) => escreverLocalizacao({erro:
                    e.code === 1 ? bloqueada
                    : e.code === 3 ? "Demorou demais para achar a sua localização. Tente de novo."
                    : "Não foi possível achar a sua posição. Ligue o Wi-Fi ou o GPS e tente de novo."});
                // Primeiro com alta precisão (GPS do celular); se falhar, tenta de novo do jeito comum
                // (Wi-Fi/rede), que é o que funciona num computador sem GPS
                navigator.geolocation.getCurrentPosition(achou, (e) => {
                    if (e.code === 1) { falhou(e); return; }
                    navigator.geolocation.getCurrentPosition(achou, falhou,
                        {enableHighAccuracy: false, timeout: 20000, maximumAge: 600000});
                }, {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000});
            }, true);
        `;
        d.head.appendChild(s);
    }
    if (!d.getElementById("script-predios-3d")) {
        const s = d.createElement("script");
        s.id = "script-predios-3d";
        s.textContent = `""" + SCRIPT_PREDIOS_3D + """`;
        d.head.appendChild(s);
    }
    if (!d.getElementById("script-mapa-2")) {
        const s = d.createElement("script");
        s.id = "script-mapa-2";
        s.textContent = `
            // Dois cliques no mapa: marca o lugar do marco novo (como o dblclick do mapa do Taipei)
            document.addEventListener("dblclick", (ev) => {
                const grafico = ev.target.closest && ev.target.closest(".st-key-caixa_mapa .js-plotly-plot");
                const campo = document.querySelector(".st-key-marco_temporario input");
                if (!grafico || !campo || !grafico._fullLayout.map) return;
                const mapa = grafico._fullLayout.map._subplot.map;
                const caixa = mapa.getCanvas().getBoundingClientRect();
                const lugar = mapa.unproject([ev.clientX - caixa.left, ev.clientY - caixa.top]);
                const valor = JSON.stringify({lat: lugar.lat, lon: lugar.lng});
                // Escreve no campo escondido e tira o foco: o Streamlit recebe o valor e desenha o pin
                campo.focus();
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(campo, valor);
                campo.dispatchEvent(new Event("input", {bubbles: true}));
                campo.blur();
            }, true);
            document.addEventListener("pointerdown", (ev) => {
                if (!ev.target.closest || !ev.target.closest(".st-key-adicionar_ponto_vista button")) return;
                const grafico = document.querySelector(".st-key-caixa_mapa .js-plotly-plot");
                const campo = document.querySelector(".st-key-vista_atual_mapa input");
                if (!grafico || !campo || !grafico._fullLayout.map) return;
                const mapa = grafico._fullLayout.map._subplot.map;
                const centro = mapa.getCenter();
                const valor = JSON.stringify({lat: centro.lat, lon: centro.lng, zoom: mapa.getZoom()});
                // Escreve como se fosse digitado: ao clicar no botão, o campo perde o foco e o Streamlit
                // recebe o valor junto com o clique
                campo.focus();
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(campo, valor);
                campo.dispatchEvent(new Event("input", {bubbles: true}));
            }, true);
        `;
        d.head.appendChild(s);
    }
    </script>""", height=1)


# --- PRÉDIOS EM 3D (o botão de prédios 3D do mapa do Taipei) ---
# O mapa do Plotly é desenhado pelo MapLibre, que sabe levantar prédios ("fill-extrusion"). O script abaixo
# põe essa camada no próprio mapa do painel, sem trocar a ferramenta: marcos, pontos de vista, ocorrências
# e o filtro pelo gráfico continuam iguais. O arquivo vem do scripts/preparar_predios.py.
NOME_ARQ_PREDIOS = "predios_oriximina.geojson"
PASTA_STATIC = os.path.join(PASTA_PROJETO, "static")
TEXTO_FONTE_PREDIOS = ("Prédios: contornos do OpenStreetMap. Altura média estimada por satélite em quadrados de "
                       "cerca de 90 m (GHSL 2018, Comissão Europeia): todos os prédios do mesmo quadrado ficam "
                       "com a mesma altura, que não é a medida de cada prédio. Aproxime o mapa da sede para ver.")


def publicar_predios():
    """Copia os prédios para a pasta static (o Streamlit serve em app/static/). Devolve a versão ou None."""
    origem = os.path.join(PASTA_DADOS, NOME_ARQ_PREDIOS)
    if not os.path.exists(origem):
        return None
    destino = os.path.join(PASTA_STATIC, NOME_ARQ_PREDIOS)
    versao = int(os.path.getmtime(origem))
    try:
        if not os.path.exists(destino) or int(os.path.getmtime(destino)) != versao:
            os.makedirs(PASTA_STATIC, exist_ok=True)
            shutil.copy2(origem, destino)   # copy2 mantém a data: só copia de novo quando o script roda
    except OSError:
        return None
    return versao


SCRIPT_PREDIOS_3D = """
    // Prédios em 3D: a cada instante confere se a marca #predios-3d existe e põe ou tira a camada do mapa
    // (o Plotly às vezes refaz o mapa; aí a camada volta sozinha)
    let dadosPredios = null, urlPredios = null, carregandoPredios = false;
    const ORIGEM_ALTURA = {
        ghsl: "média do quadrado, estimada por satélite (GHSL)",
        ghsl_vizinhos: "média dos quadrados vizinhos, estimada por satélite (GHSL)",
        andares: "pelo número de andares (OpenStreetMap)",
        padrao: "sem estimativa: 3 m (um andar)"};
    function mapaDoPainel() {
        const g = document.querySelector(".st-key-caixa_mapa .js-plotly-plot");
        return g && g._fullLayout && g._fullLayout.map && g._fullLayout.map._subplot
            && g._fullLayout.map._subplot.map;
    }
    function balaoPredio() {
        let b = document.getElementById("balao-predio");
        if (!b) {
            b = document.createElement("div");
            b.id = "balao-predio";
            document.body.appendChild(b);
        }
        return b;
    }
    // Balão ao passar o mouse num prédio (o Plotly fica com os eventos do mapa; por isso escuta a página)
    document.addEventListener("mousemove", (ev) => {
        const balao = balaoPredio();
        const mapa = mapaDoPainel();
        if (!mapa || !mapa.getLayer("predios-3d")) { balao.style.display = "none"; return; }
        const caixa = mapa.getCanvas().getBoundingClientRect();
        const x = ev.clientX - caixa.left, y = ev.clientY - caixa.top;
        const dentro = x >= 0 && y >= 0 && x <= caixa.width && y <= caixa.height;
        const achados = dentro ? mapa.queryRenderedFeatures([x, y], {layers: ["predios-3d"]}) : [];
        if (!achados.length) { balao.style.display = "none"; return; }
        const p = achados[0].properties;
        balao.innerHTML = "<b>Prédio</b><br>Altura: " + String(p.a).replace(".", ",") + " m<br>"
            + "<span>" + (ORIGEM_ALTURA[p.o] || "") + "</span>";
        balao.style.left = (ev.clientX + 14) + "px";
        balao.style.top = (ev.clientY + 14) + "px";
        balao.style.display = "block";
    });
    setInterval(() => {
        const mapa = mapaDoPainel();
        if (!mapa || !mapa.isStyleLoaded()) return;
        const marca = document.getElementById("predios-3d");
        const temCamada = !!mapa.getLayer("predios-3d");
        if (!marca) {
            if (temCamada) {
                mapa.removeLayer("predios-3d");
                balaoPredio().style.display = "none";
                mapa.easeTo({pitch: 0, duration: 800});
            }
            return;
        }
        const url = marca.dataset.url;
        if (url !== urlPredios) {
            if (!carregandoPredios) {
                carregandoPredios = true;
                fetch(url).then(r => r.json()).then(d => { dadosPredios = d; urlPredios = url; })
                    .finally(() => { carregandoPredios = false; });
            }
            return;
        }
        if (mapa.getSource("predios") && mapa._versaoPredios !== url) {
            if (temCamada) mapa.removeLayer("predios-3d");
            mapa.removeSource("predios");
        }
        if (!mapa.getSource("predios")) {
            mapa.addSource("predios", {type: "geojson", data: dadosPredios});
            mapa._versaoPredios = url;
        }
        if (!mapa.getLayer("predios-3d")) {
            // Embaixo das camadas do painel: pontos, marcos e linhas continuam por cima dos prédios
            const primeira = mapa.getStyle().layers.find(c => c.id.startsWith("plotly-trace-layer"));
            mapa.addLayer({id: "predios-3d", type: "fill-extrusion", source: "predios", minzoom: 12, paint: {
                "fill-extrusion-color": ["interpolate", ["linear"], ["get", "a"],
                    2, "#3b5675", 5, "#5a8fc0", 8, "#9cc3e6", 11, "#e3f1ff"],
                "fill-extrusion-height": ["get", "a"],
                "fill-extrusion-base": 0,
                "fill-extrusion-opacity": 0.9}}, primeira ? primeira.id : undefined);
            // Ao ligar: inclina o mapa e, se ele estiver longe, aproxima da sede (onde estão os prédios)
            if (mapa.getPitch() < 20) {
                const perto = mapa.getZoom() >= 14;
                mapa.easeTo(Object.assign({pitch: 55, duration: 1200},
                    perto ? {} : {center: [-55.8655, -1.7605], zoom: 15.3}));
            }
        }
    }, 700);
"""


# --- RESUMO COM IA DAS CAMADAS DO MAPA (o "✦ Insight com IA" do Taipei, aqui com o Claude) ---
# A chave da API fica fora do código: variável de ambiente ANTHROPIC_API_KEY ou .streamlit/secrets.toml
MODELO_IA = "claude-opus-5-5"
NOME_MODELO_IA = "Claude Opus 5.5 (Anthropic)"
SISTEMA_IA = """Você escreve resumos curtos para o Painel Oriximiná, um painel público de dados da Prefeitura \
de Oriximiná (PA). Você recebe os números de uma camada do mapa e escreve em português do Brasil, para \
gestores e cidadãos sem formação técnica.

Use só os números recebidos: não invente dados, causas, tendências nem comparações com outros lugares. \
Quando comparar, diga os valores. Escreva de 3 a 5 tópicos curtos em markdown, cada um com um achado \
concreto (onde há mais ou menos, concentrações, diferenças que chamam a atenção). Termine com uma linha \
começando com "Atenção:" sobre um limite desses dados, se houver algum."""


def dados_da_camada(camada):
    """Os números de uma camada do mapa, em tabelas de texto, para a IA resumir."""
    tabela = lambda df: df.to_csv(index=False, sep=";")
    if camada in ("populacao", "idosos"):
        setores = df_setores[df_setores["Habitantes"].fillna(0) > 0]
        por_local = (setores.groupby("Localidade")[["Habitantes", "60 anos ou mais"]].sum()
                     .sort_values("Habitantes", ascending=False).reset_index())
        por_local["% com 60 anos ou mais"] = (por_local["60 anos ou mais"] / por_local["Habitantes"] * 100).round(1)
        zonas = setores.groupby("Zona")[["Habitantes", "60 anos ou mais"]].sum().reset_index()
        return (f"Setores censitários com moradores: {len(setores)}\n\nPor zona:\n{tabela(zonas)}\n"
                f"Por localidade (as 20 com mais habitantes, de {len(por_local)}):\n{tabela(por_local.head(20))}")
    if camada == "bairros":
        bairros = pd.read_csv(arquivo_dados("dados_bairros_oriximina.csv"), sep=";")
        return f"Bairros da sede urbana (Plano Diretor 2017) e moradores (Censo 2022):\n{tabela(bairros)}"
    if camada in ("saude", "ensino"):
        pontos = df_pontos[df_pontos["Tipo"] == TIPO_PONTO[camada]]
        por_local = pontos.groupby("Localidade").size().sort_values(ascending=False).reset_index(name="Quantidade")
        return (f"{TIPO_PONTO[camada]}: {len(pontos)} no município (endereços do CNEFE 2022)\n\n"
                f"Por localidade:\n{tabela(por_local)}")
    if camada == "vias":
        vias = resumo_vias.rename(columns={"count": "Trechos", "sum": "Metros"}).reset_index(names="Tipo de via")
        vias["Quilômetros"] = (vias["Metros"] / 1000).round(1)
        return f"Rede viária da sede urbana (OpenStreetMap):\n{tabela(vias[['Tipo de via', 'Trechos', 'Quilômetros']])}"
    if camada in ("municipios_cn", "limites_cn"):
        municipios = df_regiao_idades[["Nome", "Habitantes", "0 a 14 anos", "60 anos ou mais"]].copy()
        municipios["% com 60 anos ou mais"] = (municipios["60 anos ou mais"] / municipios["Habitantes"] * 100).round(1)
        return f"Municípios da Calha Norte paraense (Censo 2022):\n{tabela(municipios)}"
    if camada == "frota_cn":
        colunas = ["Nome", "Total", "Motocicletas", "Automóveis", "Caminhonetes e utilitários", "Caminhões"]
        frota = df_frota[colunas].merge(df_regiao_idades[["Nome", "Habitantes"]], on="Nome")
        frota["Veículos por 100 habitantes"] = (frota["Total"] / frota["Habitantes"] * 100).round(1)
        return f"Frota de veículos por município (SENATRAN, {df_frota['Mês'].iloc[0]}):\n{tabela(frota)}"
    if camada == "estradas_cn":
        estradas = pd.DataFrame([f["properties"] for f in geojson_estradas["features"]])
        por_tipo = estradas.groupby("tipo")["comprimento_m"].agg(["count", "sum"]).reset_index()
        por_tipo.columns = ["Tipo de estrada", "Trechos", "Metros"]
        por_tipo["Quilômetros"] = (por_tipo["Metros"] / 1000).round(1)
        return f"Estradas da Calha Norte (OpenStreetMap):\n{tabela(por_tipo[['Tipo de estrada', 'Trechos', 'Quilômetros']])}"
    if camada == "sedes_cn":
        return f"Sedes municipais da Calha Norte:\n{tabela(df_sedes[['Nome', 'Latitude', 'Longitude']])}"
    if camada.startswith("novo_"):   # camada de componente criado na administração
        config, df = mapa_componente(camada[len("novo_"):])
        if config is not None:
            return f"{TIPOS_MAPA[config['tipo']][0]} ({len(df)} linhas):\n{tabela(df)}"
    return ""


def chave_api_ia():
    """Chave da API da Anthropic: variável de ambiente ou .streamlit/secrets.toml (nunca no código)."""
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        try:
            chave = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:   # sem arquivo secrets.toml
            chave = None
    return chave


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def gerar_resumo_ia(camada, titulo, dados):
    """Pede o resumo ao Claude. Fica guardado por 24 h para os mesmos dados (não paga de novo a cada clique);
    se der erro, a exceção sobe e nada é guardado."""
    import anthropic   # só aqui: o painel funciona mesmo sem a biblioteca instalada

    cliente = anthropic.Anthropic(api_key=chave_api_ia())
    resposta = cliente.beta.messages.create(
        model=MODELO_IA,
        max_tokens=8000,
        output_config={"effort": "low"},   # resumo curto de uma tabela: esforço baixo basta
        # Se o modelo recusar por engano, a API tenta de novo num modelo reserva (fallback do servidor)
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SISTEMA_IA,
        messages=[{"role": "user", "content": f"Camada do mapa: {titulo}\n\n{dados}"}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("A IA não gerou um resumo para esta camada.")
    texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()
    if not texto:
        raise RuntimeError("A IA não devolveu texto. Tente de novo.")
    return {"texto": texto, "hora": agora_texto()}


def mensagem_erro_ia(erro):
    """Explica em português o que deu errado ao pedir o resumo."""
    try:
        import anthropic
    except ImportError:
        return "A biblioteca do Claude não está instalada. Rode: python -m pip install -r requirements.txt"
    if isinstance(erro, anthropic.AuthenticationError):
        return "A chave da API da Anthropic não foi aceita. Confira a chave em .streamlit/secrets.toml."
    if isinstance(erro, anthropic.PermissionDeniedError):
        return "A chave da API não tem permissão para usar este modelo."
    if isinstance(erro, anthropic.RateLimitError):
        return "Muitos pedidos à IA agora. Espere um minuto e tente de novo."
    if isinstance(erro, anthropic.APIConnectionError):
        return "Sem conexão com a IA. Confira a internet e tente de novo."
    if isinstance(erro, anthropic.APIStatusError):
        return f"A IA respondeu com erro ({erro.status_code}). Tente de novo mais tarde."
    return str(erro) or "Não foi possível gerar o resumo."


@st.dialog("✦ Resumo com IA", width="medium")
def janela_resumo_ia(camada):
    titulo, fonte = CAMADAS[camada]
    st.markdown('<div class="caixa-aviso">Aviso: este resumo é gerado automaticamente por inteligência '
                'artificial a partir dos números do painel. Pode conter erros de interpretação; use apenas '
                'como referência.</div>', unsafe_allow_html=True)
    linhas = [("Painel", nome_do_painel(st.session_state.painel)[0]), ("Camada analisada", titulo),
              ("Fonte dos dados", fonte), ("Categoria", "Mapa"), ("Modelo de IA", NOME_MODELO_IA)]
    if not chave_api_ia():
        st.markdown("".join(f'<div class="popup-linha"><span>▪ {r}</span>{html.escape(v)}</div>' for r, v in linhas),
                    unsafe_allow_html=True)
        st.markdown('<div class="aviso-vazio">O resumo com IA ainda não está ligado: falta a chave da API da '
                    'Anthropic. Veja como configurar na <b>Documentação técnica</b> (menu ⓘ).</div>',
                    unsafe_allow_html=True)
        return
    try:
        with st.spinner("Analisando os dados da camada…"):
            resumo = gerar_resumo_ia(camada, titulo, dados_da_camada(camada))
    except Exception as erro:   # a mensagem explica o tipo de erro (chave, limite, conexão...)
        st.markdown("".join(f'<div class="popup-linha"><span>▪ {r}</span>{html.escape(v)}</div>' for r, v in linhas),
                    unsafe_allow_html=True)
        st.markdown(f'<div class="aviso-vazio">{html.escape(mensagem_erro_ia(erro))}</div>', unsafe_allow_html=True)
        return
    linhas.append(("Hora da análise", resumo["hora"]))
    st.markdown("".join(f'<div class="popup-linha"><span>▪ {r}</span>{html.escape(v)}</div>' for r, v in linhas),
                unsafe_allow_html=True)
    st.markdown(resumo["texto"])


# Camadas básicas da Comparação de mapas (as "camadas básicas" do Taipei): ficam em todos os painéis
CAMADAS_BASICAS = ["bairros", "saude", "ensino", "vias", "limites_cn"]

# --- FILTRAR O MAPA PELO GRÁFICO (map_filter do Taipei) ---
# Cada camada tem um gráfico pequeno: clicar numa barra deixa no mapa só o que corresponde a ela.
# Nas ruas e estradas, o clique muda o "Filtrar mapa" (os tipos de via que aparecem).
FILTRO_POR_TIPO = {"vias": ("filtro_vias", CORES_VIAS), "estradas_cn": ("filtro_estradas", CORES_ESTRADAS)}


def categorias_da_camada(camada):
    """(o que cada barra é, valores por categoria, unidade) do gráfico de filtro da camada, ou None."""
    maior_primeiro = lambda serie: serie.sort_values(ascending=False)
    if camada in ("populacao", "idosos"):
        coluna = "Habitantes" if camada == "populacao" else "60 anos ou mais"
        setores = df_setores[df_setores["Habitantes"].fillna(0) > 0]
        return "Zona", setores.groupby("Zona")[coluna].sum(), "habitantes"
    if camada == "bairros":
        moradores = df_dados_bairros.set_index("nome")["Habitantes"]
        return "Bairro", maior_primeiro(moradores.reindex(df_bairros["nome"].unique()).fillna(0)), "habitantes"
    if camada in ("saude", "ensino"):
        pontos = df_pontos[df_pontos["Tipo"] == TIPO_PONTO[camada]]
        return "Localidade", maior_primeiro(pontos.groupby("Localidade").size()), "locais"
    if camada == "vias":
        return "Tipo de via", (resumo_vias["sum"] / 1000).round(1), "km"
    if camada == "estradas_cn":
        estradas = pd.DataFrame([f["properties"] for f in geojson_estradas["features"]])
        km = (estradas.groupby("tipo")["comprimento_m"].sum() / 1000).round(1)
        return "Tipo de estrada", km.reindex(list(CORES_ESTRADAS)).fillna(0), "km"
    if camada in ("municipios_cn", "limites_cn", "sedes_cn"):
        habitantes = df_regiao_idades.set_index("Nome")["Habitantes"]
        if camada == "sedes_cn":
            habitantes = habitantes[habitantes.index.isin(df_sedes["Nome"])]
        return "Município", maior_primeiro(habitantes), "habitantes"
    if camada == "frota_cn":
        return "Município", maior_primeiro(df_frota.set_index("Nome")["Total"]), "veículos"
    if camada.startswith("novo_"):   # camada de componente criado na administração
        config, df = mapa_componente(camada[len("novo_"):])
        if config is None or df.empty:
            return None
        if config["tipo"] != "pontos":
            rotulo, valor = df.columns[0], df.columns[1]
            return rotulo, maior_primeiro(df.groupby(rotulo)[valor].sum()), valor
        # Pontos: agrupa pela 1ª coluna de texto que se repete (ex.: localidade ou tipo)
        for coluna in df.columns[1:]:
            if coluna not in ("Latitude", "Longitude") and df[coluna].dtype == object \
                    and df[coluna].nunique() < len(df):
                return coluna, maior_primeiro(df.groupby(coluna).size()), "locais"
    return None


def filtro_do_mapa(camada):
    """Categoria escolhida no gráfico da camada (None = o mapa mostra tudo)."""
    return st.session_state.get("filtro_mapa", {}).get(camada)


def nova_versao_grafico(camada):
    # Uma chave nova a cada clique: o gráfico volta sem a seleção do Plotly e as cores mostram o filtro
    versoes = st.session_state.setdefault("filtro_versao", {})
    versoes[camada] = versoes.get(camada, 0) + 1


def escolher_no_grafico(camada, chave):
    pontos = st.session_state[chave]["selection"]["points"]
    nova_versao_grafico(camada)
    if not pontos:
        return
    categoria = pontos[0].get("y")
    if camada in FILTRO_POR_TIPO:
        chave_tipos, cores = FILTRO_POR_TIPO[camada]
        # Clicar no tipo que já está sozinho volta a mostrar todos
        st.session_state[chave_tipos] = list(cores) if st.session_state.get(chave_tipos) == [categoria] \
            else [categoria]
        return
    filtros = st.session_state.setdefault("filtro_mapa", {})
    filtros[camada] = None if filtros.get(camada) == categoria else categoria


def mostrar_tudo(camada):
    if camada in FILTRO_POR_TIPO:
        chave_tipos, cores = FILTRO_POR_TIPO[camada]
        st.session_state[chave_tipos] = list(cores)
    else:
        st.session_state.setdefault("filtro_mapa", {})[camada] = None
    nova_versao_grafico(camada)


def grafico_filtro(camada):
    dados = categorias_da_camada(camada)
    if dados is None or dados[1].empty:
        return
    eixo, valores, unidade = dados
    nomes = [str(n) for n in valores.index]
    if camada in FILTRO_POR_TIPO:
        chave_tipos, cores = FILTRO_POR_TIPO[camada]
        marcadas = st.session_state.get(chave_tipos, list(cores))
        escolhidas = None if set(marcadas) == set(cores) else marcadas
        cores_base = [cores.get(n, PALETA_PADRAO[0]) for n in nomes]
    else:
        escolhida = filtro_do_mapa(camada)
        escolhidas = [escolhida] if escolhida in nomes else None
        cores_base = [COR_PONTOS.get(camada, PALETA_PADRAO[0])] * len(nomes)
    # Com filtro, as barras que ficaram de fora do mapa ficam cinza
    cores_barras = [cor if not escolhidas or nome in escolhidas else "#3a3b3e" for cor, nome in zip(cores_base, nomes)]
    altura = 24 * len(nomes) + 10
    curto = lambda nome: nome if len(nome) <= 20 else nome[:19] + "…"
    fig = go.Figure(go.Bar(
        x=valores.values, y=nomes, orientation="h", marker_color=cores_barras,
        text=[numero_br(v) for v in valores.values], textposition="outside", cliponaxis=False,
        textfont=dict(color="#c8c8c8", size=12),
        hovertemplate=f"%{{y}}: %{{text}} {html.escape(str(unidade))}<extra></extra>"))
    fig.update_layout(
        height=altura, margin=dict(l=0, r=48, t=0, b=0), paper_bgcolor=COR_CARTAO, plot_bgcolor=COR_CARTAO,
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(autorange="reversed", fixedrange=True, automargin=True, tickvals=nomes,
                   ticktext=[curto(n) for n in nomes], tickfont=dict(color="#c8c8c8", size=12)),
        font=dict(family="Source Sans Pro, sans-serif", color="#fafafa"), separators=",.",
        dragmode=False, showlegend=False, bargap=0.3,
        hovermode="y",   # a linha inteira da barra vale o clique (barras curtas também)
        hoverlabel=dict(bgcolor="#1e1f21", bordercolor="#555555", font=dict(color="white", size=13)))
    st.markdown(f'<div class="cartao-fonte">Clique numa barra para filtrar o mapa por {eixo.lower()}</div>',
                unsafe_allow_html=True)
    chave = f"filtro_graf_{camada}_{st.session_state.get('filtro_versao', {}).get(camada, 0)}"
    # Muitas categorias: o gráfico rola dentro do cartão
    with st.container(height=220 if altura > 230 else "content", border=False):
        st.plotly_chart(fig, key=chave, on_select=lambda: escolher_no_grafico(camada, chave),
                        selection_mode="points", config={"displayModeBar": False})
    if escolhidas:
        with st.container(horizontal=True, vertical_alignment="center", key=f"filtro_ativo_{camada}"):
            st.markdown(f'<div class="cartao-fonte">Mostrando: {html.escape(", ".join(escolhidas))}</div>',
                        unsafe_allow_html=True)
            st.button("Mostrar tudo", icon=":material/filter_alt_off:", type="tertiary",
                      key=f"filtro_limpar_{camada}", on_click=mostrar_tudo, args=(camada,))


def cartaozinho_camada(camada, ligada_de_inicio):
    """Cartãozinho de uma camada com o botão de ligar/desligar, como no Taipei. Devolve se está ligada."""
    titulo, fonte = CAMADAS[camada]
    with st.container(key=f"camada_{camada}"):
        st.markdown(f'<div class="camada-titulo">{titulo}</div><div class="cartao-fonte">{fonte}</div>',
                    unsafe_allow_html=True)
        chave_botao = f"ligar_{camada}"
        if chave_botao not in st.session_state:
            st.session_state[chave_botao] = ligada_de_inicio
        ligada = st.toggle("Mostrar no mapa", key=chave_botao)
        # Resumo automático da camada feito por IA (como o "✦ Insight com IA" do Taipei)
        if st.button("✦ Resumo com IA", type="tertiary", key=f"resumo_ia_{camada}"):
            janela_resumo_ia(camada)
        if camada in FILTRO_POR_TIPO:
            # "Filtrar mapa": escolher quais tipos de via aparecem (o gráfico abaixo também muda essa lista)
            chave_tipos, cores = FILTRO_POR_TIPO[camada]
            if chave_tipos not in st.session_state:
                st.session_state[chave_tipos] = list(cores)
            st.multiselect("Filtrar mapa", list(cores), key=chave_tipos)
        if camada in COR_PONTOS:
            st.markdown(f'<span class="legenda-ponto" style="background:{COR_PONTOS[camada]}"></span>'
                        f'<span class="cartao-fonte">{(df_pontos["Tipo"] == TIPO_PONTO[camada]).sum()} '
                        'locais</span>', unsafe_allow_html=True)
        if ligada:
            grafico_filtro(camada)
    return ligada


def pagina_mapa():
    painel = st.session_state.painel
    titulo_painel(painel)
    if not cartoes_do_painel(painel):   # painel sem cartões: nada de mapa vazio, só o aviso
        aviso_painel_vazio(painel)
        return
    camadas = camadas_do_painel(painel)
    if CELULAR:
        # Celular (MobileLayers do Taipei): o mapa na tela toda e as camadas num botão "Camadas" em cima dele
        caixa_camadas = st.popover("Camadas", icon=":material/layers:", key="camadas_celular")
        col_camadas, col_mapa = caixa_camadas, st.container()
    else:
        col_camadas, col_mapa = st.columns([1, 3], gap="medium")
    ligadas = []
    with col_camadas, st.container(key="lista_camadas"):
        if not camadas:
            st.markdown('<div class="aviso-vazio">Os cartões deste painel não têm camadas próprias. Use as '
                        'camadas básicas abaixo.</div>', unsafe_allow_html=True)
        for camada in camadas:   # a primeira camada do painel começa ligada
            if cartaozinho_camada(camada, ligada_de_inicio=camada == camadas[0]):
                ligadas.append(camada)
        # Camadas básicas (como as do Taipei): sempre disponíveis, qualquer que seja o painel
        basicas = [c for c in CAMADAS_BASICAS if c not in camadas]
        if basicas:
            st.markdown('<div class="camadas-basicas-titulo">Camadas básicas</div>', unsafe_allow_html=True)
            for camada in basicas:
                if cartaozinho_camada(camada, ligada_de_inicio=False):
                    ligadas.append(camada)
    with col_mapa:
        barra_ferramentas_mapa()
        with st.container(key="scripts_mapa"):
            script_mapa()
            versao = publicar_predios()
            if st.session_state.get("predios_3d") and versao:
                # O script do mapa vê esta marca e levanta os prédios (sem ela, tira a camada)
                st.markdown(f'<div id="predios-3d" data-url="app/static/{NOME_ARQ_PREDIOS}?v={versao}"></div>',
                            unsafe_allow_html=True)
        with st.container(key="caixa_mapa"):
            fig = figura_mapa(ligadas)
            # Clicar num ponto ou numa área faz a página rodar de novo com o item escolhido
            evento = st.plotly_chart(fig, key="mapa", on_select="rerun", selection_mode="points",
                                     config={"displayModeBar": False, "scrollZoom": True})
            pontos = evento.selection.points if evento and evento.selection else []
            info = info_do_clique(fig, pontos[0]) if pontos else None
            if info:
                st.session_state.ultimo_clique = dict(nome=info["titulo"], lat=info["lat"], lon=info["lon"])
                if st.session_state.get("popup_fechado") != info["assinatura"]:
                    janelinha_do_mapa(info)


# --- ASSISTENTE (ROBOZINHO NO CANTO) E PRÓXIMA ATUALIZAÇÃO, COMO NO TAIPEI ---
# Perguntas frequentes com respostas prontas (não usa internet nem inteligência artificial)
RESPOSTAS_ROBO = {
    "O que é este painel?":
        "É o painel de controle de Oriximiná (PA). Ele mostra dados oficiais de Oriximiná e da Calha Norte "
        "paraense em cartões, além de gráficos e mapas.",
    "De onde vêm os dados?":
        "De fontes oficiais: **IBGE** (Censo 2022 e CNEFE), **DATASUS** (estimativas populacionais), "
        "**RAIS** do Ministério do Trabalho (empregos formais), **SENATRAN** (frota de veículos) e "
        "**OpenStreetMap** (ruas e estradas). A fonte de cada cartão aparece embaixo do título dele.",
    "Como vejo mais detalhes de um cartão?":
        "Clique em **Informações do componente**, no pé do cartão. Abre uma janela com o gráfico, a descrição, "
        "um exemplo de uso e os botões Reportar, Baixar e Incorporar.",
    "Como baixo os dados de um cartão?":
        "Abra as **Informações do componente** do cartão e clique em **Baixar**. Dê um nome ao arquivo e "
        "escolha o formato: JSON ou CSV (abre no Excel).",
    "Como favorito um cartão?":
        "Entre com a sua conta (botão **Entrar**, no alto à direita) e clique no **coração** do cartão. "
        "Os favoritos ficam em **Componentes favoritos**, no menu da esquerda.",
    "Como monto o meu próprio painel?":
        "Entre com a sua conta e abra o **Catálogo de componentes**. À esquerda, dê um nome e escolha um ícone; "
        "à direita, clique no **[+]** dos cartões que quiser e depois em **Adicionar componentes ao painel**.",
    "Como comparo mapas?":
        "Abra **Comparação de mapas**, na barra de cima, e ligue as camadas que quiser ver juntas. Nos cartões "
        "de mapa, os botões **Filtrar mapa** e **Dados** também levam para lá.",
    "Como reporto um erro nos dados?":
        "Abra as **Informações do componente** do cartão e clique em **Reportar**. Escreva um título, escolha "
        "o tipo de problema e descreva o que viu.",
    "Quando os dados são atualizados?":
        "O painel recarrega sozinho a cada 10 minutos (a hora aparece embaixo, à direita). Cada cartão mostra "
        "a data da sua fonte em **Atualização** (ex.: Censo 2022, RAIS 2022).",
}
INTERVALO_RECARGA = 10 * 60   # segundos


def perguntar_robo(pergunta):
    st.session_state.robo_pergunta = pergunta


def robo_ajuda():
    """Botão redondo com o robozinho no canto de baixo; o "–" o recolhe para uma abinha na borda."""
    if st.session_state.get("robo_minimizado"):
        with st.container(key="robo_recolhido"):
            if st.button("", icon=":material/smart_toy:", key="robo_mostrar", help="Mostrar o assistente"):
                st.session_state.robo_minimizado = False
                st.rerun()
        return
    with st.container(horizontal_alignment="right", gap=None, key="robo"):
        if st.button("–", type="tertiary", key="robo_minimizar", help="Esconder o assistente"):
            st.session_state.robo_minimizado = True
            st.rerun()
        # Sem dica (help): ela aparecia por cima do "–" e atrapalhava o clique
        with st.popover("", icon=":material/smart_toy:"):
            with st.container(key="robo_conversa"):
                st.markdown('<div class="robo-titulo">Assistente do Painel Oriximiná</div>', unsafe_allow_html=True)
                pergunta = st.session_state.get("robo_pergunta")
                with st.chat_message("assistant", avatar=":material/smart_toy:"):
                    st.markdown(RESPOSTAS_ROBO[pergunta] if pergunta else
                                "Olá! Sou o assistente do painel. Escolha uma pergunta abaixo.")
                if pergunta:
                    st.markdown(f'<div class="robo-pergunta">Você perguntou: {pergunta}</div>',
                                unsafe_allow_html=True)
                st.markdown('<div class="catalogo-fonte">Perguntas frequentes</div>', unsafe_allow_html=True)
                for i, texto in enumerate(RESPOSTAS_ROBO):
                    st.button(texto, key=f"robo_pergunta_{i}", on_click=perguntar_robo, args=(texto,),
                              width="stretch", type="primary" if texto == pergunta else "secondary")


@st.fragment(run_every=30)
def proxima_atualizacao():
    # Confere a cada 30 s; na hora marcada recarrega a página inteira (os dados são lidos de novo dos arquivos)
    agora = time.time()
    proxima = st.session_state.setdefault("proxima_recarga", agora + INTERVALO_RECARGA)
    if agora >= proxima:
        st.session_state.proxima_recarga = agora + INTERVALO_RECARGA
        st.rerun(scope="app")
    hora = time.localtime(proxima)
    st.markdown(f'<div class="proxima-atualizacao">Próxima atualização: {hora.tm_hour}:{hora.tm_min:02d}</div>',
                unsafe_allow_html=True)


# --- GRÁFICOS GENÉRICOS E COMPONENTES NOVOS (os tipos de gráfico do Taipei + o AdminAddComponent) ---
# Um componente novo é uma tabela (CSV) + tipos de gráfico + cores + textos, criado na administração.
# A tabela: 1ª coluna = rótulos (categorias ou anos); as outras colunas = séries de números.
PASTA_COMPONENTES = os.path.join(PASTA_DADOS, "componentes")
TIPOS_GRAFICO = {   # tipo: (nome no botão, para que serve / formato da tabela)
    "colunas": ("Gráfico de colunas verticais", "Comparar valores entre categorias (uma ou mais séries)."),
    "barras": ("Gráfico de barras", "Como as colunas, deitadas: bom para rótulos longos."),
    "barras_percentuais": ("Gráfico de barras (%)", "Cada linha vira 100%: mostra a divisão entre as séries."),
    "barras_meta": ("Barras com meta", "Valores comparados a uma meta (coluna \"Meta\" ou meta fixa)."),
    "linha_tempo_separada": ("Linha do tempo (separada)", "Uma linha por série ao longo do tempo (1ª coluna = anos)."),
    "linha_tempo_empilhada": ("Linha do tempo (empilhada)", "Séries empilhadas ao longo do tempo: mostra o total."),
    "rosca": ("Gráfico de rosca", "Partes de um todo (usa a 1ª série)."),
    "area_polar": ("Gráfico de área polar", "Categorias em volta de um círculo (usa a 1ª série)."),
    "radar": ("Gráfico de radar", "Perfil de uma ou mais séries em várias categorias."),
    "mapa_arvore": ("Mapa de árvore", "Retângulos proporcionais aos valores (usa a 1ª série)."),
    "mapa_calor": ("Mapa de calor", "Tabela colorida: linhas = rótulos, colunas = séries."),
    "velocimetro": ("Velocímetro", "Um valor (o da última linha) numa escala até o máximo."),
    "medidor": ("Medidor", "Anéis de porcentagem para até 4 rótulos (valor ÷ máximo)."),
    "numero": ("Número com unidade", "Números grandes com a unidade, um por rótulo."),
}
PALETA_PADRAO = ["#24B0DD", "#56B96D", "#F8CF58", "#F65658", "#9DC56E", "#a0b8e8", "#c18ad8", "#F49F36"]
ICONES_COMPONENTE = ["bar_chart", "show_chart", "pie_chart", "donut_large", "speed", "grid_view", "insights",
                     "analytics", "map", "leaderboard"]


def exemplo_csv(tipo):
    """Tabela de exemplo de cada tipo (baixada na janela de criar componente)."""
    if tipo in ("linha_tempo_separada", "linha_tempo_empilhada", "mapa_calor"):
        return "Ano;Zona Urbana;Zona Rural\n2019;120;80\n2020;135;78\n2021;150;75\n2022;162;70\n"
    if tipo == "barras_meta":
        return "Bairro;Vacinados;Meta\nCentro;820;900\nFátima;640;700\nSantíssimo;410;600\n"
    if tipo in ("velocimetro", "numero", "medidor"):
        return "Indicador;Valor\nCobertura de água;78\nCobertura de esgoto;32\n"
    return "Categoria;Quantidade\nEscolas;148\nPostos de saúde;58\nPraças;12\n"


def para_numero(coluna):
    """Converte textos como "1.234,5" ou "1234.5" em número (CSV do Brasil ou de fora)."""
    if pd.api.types.is_numeric_dtype(coluna):   # já é número: não converte de novo
        return coluna
    texto = coluna.astype(str).str.strip()
    # "4.210" ou "1.234.567" (ponto só como separador de milhar, sem vírgula) também é número brasileiro
    brasileiro = texto.str.contains(",", regex=False) | texto.str.fullmatch(r"-?\d{1,3}(\.\d{3})+")
    texto = texto.where(~brasileiro, texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(texto, errors="coerce")


def ler_tabela(origem):
    """Lê o CSV (vírgula ou ponto e vírgula) e deixa a 1ª coluna como texto e as outras como números."""
    df = pd.read_csv(origem, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    df[df.columns[0]] = df[df.columns[0]].astype(str).str.strip()
    for coluna in df.columns[1:]:
        df[coluna] = para_numero(df[coluna])
    return df.dropna(axis=1, how="all")


def numero_br(valor):
    valor = float(valor)
    return formatar(round(valor)) if valor.is_integer() else f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def desenhar_grafico_generico(tipo, df, cores, unidade="", meta=None, maximo=None, altura=380):
    """Desenha a tabela no tipo de gráfico escolhido (Plotly), com as cores do componente."""
    rotulos = df.iloc[:, 0].tolist()
    series = [c for c in df.columns[1:] if not (tipo == "barras_meta" and c.lower() == "meta")]
    if not series or df.empty:
        st.markdown('<div class="aviso-vazio">A tabela precisa de uma coluna de rótulos e pelo menos uma '
                    'coluna de números.</div>', unsafe_allow_html=True)
        return
    cores = (list(cores) + PALETA_PADRAO)[:max(len(series), len(rotulos), 1)]
    if tipo in ("barras", "barras_percentuais", "barras_meta"):   # barras deitadas: cresce com o número de linhas
        altura = max(altura, len(rotulos) * (14 + 10 * (len(series) if tipo == "barras" else 1)) + 90)
    sufixo = f" {unidade}" if unidade else ""
    # Balão como o dos outros cartões: o rótulo em cima e a série embaixo, numa caixa só
    # (",.1~f": 1.581 em vez de 1.581,0; a casa decimal só aparece quando existe)
    balao = f"%{{x}}<br>%{{fullData.name}}: %{{y:,.1~f}}{sufixo}<extra></extra>"
    primeira = df[series[0]].fillna(0)
    fig = go.Figure()
    # Passar o mouse num item da legenda destaca a série no gráfico (JS_DESTACAR_LEGENDA), como nos outros cartões
    legenda = dict(orientation="h", yanchor="top", y=-0.18, x=0.5, xanchor="center", font=dict(color=COR_TEXTO_CINZA),
                   itemclick=False, itemdoubleclick=False)

    if tipo == "numero":   # não é gráfico do Plotly: números grandes em HTML
        itens = "".join(f'<div class="numero-item"><div class="numero-rotulo">{html.escape(str(r))}</div>'
                        f'<div class="numero-valor" style="color:{cores[i % len(cores)]}">{numero_br(v)}'
                        f'<span>{html.escape(unidade)}</span></div></div>'
                        for i, (r, v) in enumerate(zip(rotulos, primeira)))
        st.markdown(f'<div class="numero-grade">{itens}</div>', unsafe_allow_html=True)
        return
    if tipo in ("colunas", "barras"):
        for i, serie in enumerate(series):
            if tipo == "colunas":
                fig.add_trace(go.Bar(name=serie, x=rotulos, y=df[serie], marker_color=cores[i], hovertemplate=balao))
            else:
                fig.add_trace(go.Bar(name=serie, y=rotulos, x=df[serie], orientation="h", marker_color=cores[i],
                                     hovertemplate=f"%{{y}}<br>%{{fullData.name}}: %{{x:,.1~f}}{sufixo}<extra></extra>"))
        fig.update_layout(barmode="group", showlegend=len(series) > 1, legend=legenda,
                          yaxis=dict(autorange="reversed") if tipo == "barras" else {})
    elif tipo == "barras_percentuais":
        totais = df[series].sum(axis=1).replace(0, 1)
        for i, serie in enumerate(series):
            pct = df[serie] / totais * 100
            fig.add_trace(go.Bar(name=serie, y=rotulos, x=pct, orientation="h", marker_color=cores[i],
                                 text=[f"{p:.0f}%" for p in pct], textposition="inside",
                                 hovertemplate="%{y}<br>%{fullData.name}: %{x:.1f}%<extra></extra>"))
        fig.update_layout(barmode="stack", legend=legenda, xaxis=dict(range=[0, 100], ticksuffix="%"),
                          yaxis=dict(autorange="reversed"))
    elif tipo == "barras_meta":
        metas = df[[c for c in df.columns if c.lower() == "meta"][0]] if any(c.lower() == "meta" for c in df.columns) \
            else pd.Series([meta] * len(df)) if meta is not None else None
        fig.add_trace(go.Bar(name=series[0], y=rotulos, x=primeira, orientation="h", marker_color=cores[0],
                             hovertemplate=f"%{{y}}: %{{x:,.1~f}}{sufixo}<extra></extra>"))
        if metas is not None:
            fig.add_trace(go.Scatter(name="Meta", y=rotulos, x=metas, mode="markers",
                                     marker=dict(symbol="line-ns", size=26, line=dict(width=4, color="#ffffff")),
                                     hovertemplate=f"%{{y}}<br>Meta: %{{x:,.1~f}}{sufixo}<extra></extra>"))
        fig.update_layout(legend=legenda, yaxis=dict(autorange="reversed"))
    elif tipo in ("linha_tempo_separada", "linha_tempo_empilhada"):
        for i, serie in enumerate(series):
            fig.add_trace(go.Scatter(
                name=serie, x=rotulos, y=df[serie], mode="lines+markers", line=dict(color=cores[i], width=2.5),
                stackgroup="um" if tipo == "linha_tempo_empilhada" else None, hovertemplate=balao))
        fig.update_layout(legend=legenda, showlegend=len(series) > 1, hovermode="x unified")
    elif tipo == "rosca":
        fig.add_trace(go.Pie(labels=rotulos, values=primeira, hole=0.6, marker=dict(colors=cores), sort=False,
                             textinfo="percent", hovertemplate=f"%{{label}}: %{{value:,.1f}}{sufixo}<extra></extra>"))
        fig.update_layout(legend=legenda, annotations=[dict(text=f"Total<br><b>{numero_br(primeira.sum())}</b>",
                                                            showarrow=False, font=dict(size=18, color="#ffffff"))])
    elif tipo == "area_polar":
        fig.add_trace(go.Barpolar(r=primeira, theta=rotulos, marker_color=cores[:len(rotulos)], opacity=0.85,
                                  hovertemplate=f"%{{theta}}: %{{r:,.1f}}{sufixo}<extra></extra>"))
        # Sem os números da escala (ficavam uns sobre os outros); o valor aparece ao passar o mouse
        fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(color=COR_TEXTO_CINZA),
                                     radialaxis=dict(showticklabels=False, gridcolor="#3a3c3e")))
    elif tipo == "radar":
        for i, serie in enumerate(series):
            fig.add_trace(go.Scatterpolar(name=serie, r=list(df[serie]) + [df[serie].iloc[0]],
                                          theta=rotulos + [rotulos[0]], fill="toself", line=dict(color=cores[i]),
                                          hovertemplate=f"%{{theta}}<br>%{{fullData.name}}: %{{r:,.1~f}}{sufixo}<extra></extra>"))
        fig.update_layout(legend=legenda, showlegend=len(series) > 1,
                          polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(color=COR_TEXTO_CINZA),
                                     radialaxis=dict(showticklabels=False, gridcolor="#3a3c3e")))
    elif tipo == "mapa_arvore":
        fig.add_trace(go.Treemap(labels=rotulos, parents=[""] * len(rotulos), values=primeira,
                                 marker=dict(colors=cores[:len(rotulos)]), textinfo="label+value",
                                 hovertemplate=f"%{{label}}: %{{value:,.1f}}{sufixo}<extra></extra>"))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    elif tipo == "mapa_calor":
        fig.add_trace(go.Heatmap(z=df[series].T.values, x=rotulos, y=series, colorscale=[[0, COR_CARTAO], [1, cores[0]]],
                                 hovertemplate=f"%{{y}} · %{{x}}: %{{z:,.1f}}{sufixo}<extra></extra>",
                                 colorbar=dict(tickfont=dict(color=COR_TEXTO_CINZA))))
    elif tipo in ("velocimetro", "medidor"):
        topo = float(maximo) if maximo else (100.0 if primeira.max() <= 100 else float(primeira.max()) * 1.2)
        if tipo == "velocimetro":
            valor = float(primeira.iloc[-1])
            fig.add_trace(go.Indicator(
                mode="gauge+number", value=valor, number=dict(suffix=sufixo, font=dict(color="#ffffff")),
                title=dict(text=str(rotulos[-1]), font=dict(color=COR_TEXTO_CINZA, size=15)),
                gauge=dict(axis=dict(range=[0, topo], tickcolor=COR_TEXTO_CINZA), bar=dict(color=cores[0]),
                           bgcolor="#3a3c3e", borderwidth=0,
                           threshold=dict(line=dict(color="#ffffff", width=3), value=float(meta)) if meta else None)))
        else:
            n = min(len(rotulos), 4)
            for i in range(n):
                valor = float(primeira.iloc[i])
                fig.add_trace(go.Pie(values=[valor, max(topo - valor, 0)], hole=0.78, sort=False, textinfo="none",
                                     marker=dict(colors=[cores[i], "#3a3c3e"]), hoverinfo="skip",
                                     domain=dict(x=[i / n + 0.02, (i + 1) / n - 0.02], y=[0.15, 1])))
                fig.add_annotation(x=(i + 0.5) / n, y=0.575, text=f"<b>{valor / topo * 100:.0f}%</b>", showarrow=False,
                                   font=dict(size=20, color="#ffffff"))
                fig.add_annotation(x=(i + 0.5) / n, y=0.02, text=str(rotulos[i]), showarrow=False,
                                   font=dict(size=13, color=COR_TEXTO_CINZA))
            fig.update_layout(showlegend=False)
    margem = dict(l=0, r=0, t=10, b=0) if tipo == "mapa_arvore" else dict(l=10, r=10, t=30, b=10)
    layout_escuro(fig, altura=altura, margin=margem)
    fig.update_xaxes(gridcolor="#3a3c3e", tickfont=dict(color=COR_TEXTO_CINZA))
    fig.update_yaxes(gridcolor="#3a3c3e", tickfont=dict(color=COR_TEXTO_CINZA))
    # Com mais de uma série na legenda, o mouse sobre a legenda destaca a série no gráfico
    varias_series = len(fig.data) > 1 and fig.layout.showlegend is not False
    figura_em_iframe(fig, altura=altura, destacar_legenda=varias_series)


def componentes_novos():
    return CONFIG_ADMIN.get("componentes_novos", {})


def tabela_componente(chave):
    return ler_tabela(os.path.join(PASTA_COMPONENTES, f"{chave}.csv"))


# Mapa e histórico dos componentes novos (o map_config e o history_config dos componentes do Taipei)
TIPOS_MAPA = {   # tipo: (nome, formato da tabela)
    "pontos": ("Pontos (latitude e longitude)",
               "Uma linha por lugar: nome, latitude e longitude (pode ter outras colunas, como localidade)."),
    "bairros": ("Valores por bairro da sede", "1ª coluna com o nome do bairro e 2ª com um número."),
    "municipios": ("Valores por município da Calha Norte", "1ª coluna com o nome do município e 2ª com um número."),
}
TIPOS_HISTORICO = {
    "propria": "Usar a tabela do componente (1ª coluna com os anos)",
    "arquivo": "Tabela própria de histórico (1ª coluna com os anos)",
}


def exemplo_csv_mapa(tipo):
    if tipo == "pontos":
        return ("Nome;Latitude;Longitude;Localidade\nPoço artesiano 1;-1.7625;-55.8651;Centro\n"
                "Poço artesiano 2;-1.7690;-55.8712;Fátima\n")
    if tipo == "bairros":
        return "Bairro;Domicílios\n" + "".join(f"{b};{100 + 10 * i}\n" for i, b in enumerate(df_bairros["nome"][:4]))
    return "Município;Valor\n" + "".join(f"{m};{50 + 5 * i}\n" for i, m in enumerate(df_regiao_idades["Nome"][:4]))


def normalizar_nome(texto):
    """Nome sem acento e sem diferença de maiúsculas, para achar o bairro/município digitado na tabela."""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().casefold().strip()


def e_coordenada(coluna):
    return normalizar_nome(coluna).startswith(("lat", "lon", "lng"))


def para_coordenada(coluna):
    """Latitude/longitude: a vírgula vira ponto, e o ponto é sempre decimal ("-1.765" não é milhar)."""
    if pd.api.types.is_numeric_dtype(coluna):
        return coluna
    return pd.to_numeric(coluna.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def ler_tabela_mapa(origem):
    """Lê o CSV do mapa mantendo textos; converte em número só as colunas que são todas numéricas."""
    df = pd.read_csv(origem, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    for coluna in df.columns[1:]:
        numeros = para_coordenada(df[coluna]) if e_coordenada(coluna) else para_numero(df[coluna])
        if numeros.notna().all():
            df[coluna] = numeros
    return df


def validar_mapa(tipo, df):
    """Confere a tabela do mapa e devolve (tabela arrumada, mensagem de erro ou "")."""
    if tipo == "pontos":
        achar = lambda *inicios: next((c for c in df.columns if normalizar_nome(c).startswith(inicios)), None)
        lat, lon = achar("lat"), achar("lon", "lng")
        if not lat or not lon:
            return None, "A tabela de pontos precisa das colunas Latitude e Longitude."
        df = df.rename(columns={lat: "Latitude", lon: "Longitude"})
        df["Latitude"], df["Longitude"] = para_coordenada(df["Latitude"]), para_coordenada(df["Longitude"])
        ruins = df[df["Latitude"].isna() | df["Longitude"].isna() | ~df["Latitude"].between(-90, 90)
                   | ~df["Longitude"].between(-180, 180)]
        if len(ruins):
            return None, f"Coordenadas inválidas em {len(ruins)} linha(s) (ex.: {ruins.iloc[0, 0]})."
        return df, ""
    oficiais = list(df_bairros["nome"]) if tipo == "bairros" else list(df_regiao_idades["Nome"])
    por_nome = {normalizar_nome(n): n for n in oficiais}
    numericas = [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
    if not numericas:
        return None, "A 2ª coluna precisa ter números."
    nomes = df.iloc[:, 0].map(lambda n: por_nome.get(normalizar_nome(n)))
    faltando = df.iloc[:, 0][nomes.isna()].tolist()
    if faltando:
        return None, (f"Nomes não encontrados: {', '.join(map(str, faltando[:5]))}. Use os nomes do painel: "
                      f"{', '.join(oficiais[:6])}…")
    return pd.DataFrame({df.columns[0]: nomes, numericas[0]: df[numericas[0]]}), ""


def mapa_componente(chave):
    """(configuração do mapa, tabela) do componente novo, ou (None, None) se ele não tem mapa."""
    config = componentes_novos().get(chave, {}).get("mapa")
    caminho = os.path.join(PASTA_COMPONENTES, f"{chave}_mapa.csv")
    if not config or not os.path.exists(caminho):
        return None, None
    return config, ler_tabela_mapa(caminho)


def camada_do_componente(chave):
    return f"novo_{chave}"


def camada_nova_regional(camada):
    """Camada de componente novo com valores por município (o mapa mostra a região inteira)."""
    if not camada.startswith("novo_"):
        return False
    return (componentes_novos().get(camada[len("novo_"):], {}).get("mapa") or {}).get("tipo") == "municipios"


def desenhar_camada_nova(fig, camada):
    """Desenha a camada de um componente novo: pontos, bairros ou municípios pintados."""
    chave = camada[len("novo_"):]
    config, df = mapa_componente(chave)
    if config is None:
        return
    cor, nome = config.get("cor") or PALETA_PADRAO[0], CAMADAS[camada][0]
    categorias = categorias_da_camada(camada)
    completo = df
    if categorias:
        df = filtrar(camada, df, categorias[0])
    if config["tipo"] == "pontos":
        extras = [c for c in df.columns if c not in ("Latitude", "Longitude")]
        fig.add_trace(go.Scattermap(
            lat=df["Latitude"], lon=df["Longitude"], mode="markers", name=nome, marker=dict(size=11, color=cor),
            customdata=df[extras].astype(str).values.tolist(), meta=extras,
            hovertemplate="%{customdata[0]}<extra></extra>"))
        return
    rotulo, valor = df.columns[0], df.columns[1]
    escala = [[0, COR_CARTAO], [1, cor]]
    faixa = dict(zmin=completo[valor].min(), zmax=completo[valor].max())   # a cor não muda com o filtro
    if config["tipo"] == "bairros":
        fig.add_trace(go.Choroplethmap(
            geojson=geojson_bairros, featureidkey="properties.nome", locations=df[rotulo], z=df[valor], **faixa,
            colorscale=escala, showscale=False, marker_opacity=0.75, marker_line_width=1.2,
            marker_line_color="#ffffff", name=nome, customdata=df[[rotulo, valor]].values.tolist(),
            meta=[rotulo, valor], hovertemplate=f"%{{customdata[0]}}<br>{valor}: %{{z:,.1f}}<extra></extra>"))
    else:
        codigos = df[rotulo].map(dict(zip(df_regiao_idades["Nome"], df_regiao_idades["codigo"])))
        fig.add_trace(go.Choroplethmap(
            geojson=geojson_regiao, featureidkey="properties.codigo", locations=codigos, z=df[valor], **faixa,
            colorscale=escala, showscale=False, marker_opacity=0.75, marker_line_width=1.5,
            marker_line_color="#ffffff", name=nome, customdata=df[[rotulo, valor]].values.tolist(),
            meta=[rotulo, valor], hovertemplate=f"%{{customdata[0]}}<br>{valor}: %{{z:,.1f}}<extra></extra>"))


def historico_componente(chave):
    """Tabela do histórico (1ª coluna = anos) do componente novo, ou None."""
    config = componentes_novos().get(chave, {}).get("historico")
    if not config:
        return None
    caminho = os.path.join(PASTA_COMPONENTES, f"{chave}.csv" if config["tipo"] == "propria"
                           else f"{chave}_historico.csv")
    if not os.path.exists(caminho):
        return None
    df = ler_tabela(caminho)
    anos = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    if anos.isna().any() or not anos.between(1900, 2100).all():
        return None   # a 1ª coluna não é de anos: sem histórico
    return df.set_index(anos.astype(int))


def validar_historico(df):
    anos = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    if anos.isna().any() or not anos.between(1900, 2100).all():
        return "Para o histórico, a 1ª coluna precisa ter só anos (ex.: 2019, 2020...)."
    if len(df) < 2:
        return "O histórico precisa de pelo menos dois anos."
    return ""


def grafico_generico(chave):
    comp = componentes_novos()[chave]
    area = cabecalho(chave, comp["titulo"], comp["fonte"], [comp.get("area") or "Município de Oriximiná"],
                     atualizacao=comp.get("atualizacao") or "Dados fixos")
    rotulos = {TIPOS_GRAFICO[t][0]: t for t in comp["tipos"] if t in TIPOS_GRAFICO}
    escolha = tipo_de_grafico(chave, list(rotulos))
    df = tabela_componente(chave)
    desenhar_grafico_generico(rotulos[escolha], df, comp.get("cores", []), comp.get("unidade", ""),
                              comp.get("meta"), comp.get("maximo"))
    return area, df


def descricao_generica(resultado, chave):
    area, df = resultado
    comp = componentes_novos()[chave]
    descricao = (f"\n**Descrição do componente ( ID: {comp['id']} | Index: {chave} | City: oriximina )**\n\n"
                 f"{comp.get('descricao') or comp.get('resumo', '')}\n\n**Exemplo de uso**\n\n"
                 f"{comp.get('exemplo') or '—'}\n\n**Dados relacionados**\n")
    links = "".join(f'<div class="texto-cinza"><a class="link-dados" href="{html.escape(l["url"])}" target="_blank" '
                    f'rel="noreferrer">Conjunto de dados - {i}<br>({html.escape(l["nome"] or l["url"])})</a></div>'
                    for i, l in enumerate(comp.get("links", []), 1))
    dados = ('<div class="caixa-aviso">Aviso: a frequência de atualização, a qualidade dos dados e as limitações da '
             'fonte podem fazer com que os dados do painel sejam ligeiramente diferentes dos dados originais.</div>'
             + links)
    rotulo = df.columns[0]
    conteudo_json = json.dumps({"data": [{"name": s, "data": [None if pd.isna(v) else v for v in df[s]]}
                                         for s in df.columns[1:]],
                                "categories": df[rotulo].tolist()}, ensure_ascii=False, indent=2).encode("utf-8")
    conteudo_csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    titulo = comp["titulo"]
    # Histórico (como o history_config do Taipei): uma linha por série, com as cores do componente
    historico = historico_componente(chave)
    desenhar_historico = None
    if historico is not None:
        cores = list(comp.get("cores", [])) + PALETA_PADRAO
        series = [(serie, historico[serie], cores[i], comp.get("unidade", ""))
                  for i, serie in enumerate(historico.columns[1:])]
        desenhar_historico = lambda: grafico_historico(chave, series)
    painel_descricao(
        chave, descricao, dados,
        lambda: janela_reportar(titulo, area),
        lambda: janela_baixar(titulo, conteudo_json, conteudo_csv),
        lambda: janela_incorporar(comp["id"], titulo),
        historico=desenhar_historico,
    )


def registrar_componentes_novos():
    """Põe os componentes criados na administração junto dos outros (catálogo, painéis, favoritos...)."""
    for chave, comp in componentes_novos().items():
        if not os.path.exists(os.path.join(PASTA_COMPONENTES, f"{chave}.csv")):
            continue   # tabela apagada: o componente some sem quebrar o painel
        CARTOES[chave] = (comp["id"], partial(grafico_generico, chave), partial(descricao_generica, chave=chave))
        TITULOS_CARTOES[chave] = comp["titulo"]
        RESUMO_CARTOES[chave] = (comp.get("resumo") or comp["titulo"], comp["fonte"] or "—",
                                 comp.get("atualizacao") or "Dados fixos", comp.get("icone") or "bar_chart")
        CAMADAS_DO_CARTAO[chave] = []
        # Camada no mapa (Comparação de mapas), se o componente tiver
        if comp.get("mapa") and os.path.exists(os.path.join(PASTA_COMPONENTES, f"{chave}_mapa.csv")):
            camada = camada_do_componente(chave)
            CAMADAS[camada] = (comp["mapa"].get("nome") or comp["titulo"], comp["fonte"] or "—")
            CAMADAS_DO_CARTAO[chave] = [camada]


# Cores dos componentes originais que a administração pode trocar: (nome da cor, variável ou dicionário)
# As versões da Calha Norte usam as mesmas cores das de Oriximiná.
CORES_EDITAVEIS = {
    "dependencia": [("Razão de dependência", "COR_DEPENDENCIA", None),
                    ("Índice de envelhecimento", "COR_ENVELHECIMENTO", None)],
    "emprego": [(g, "GRUPOS_EMPREGO", g) for g in GRUPOS_EMPREGO],
    "divisoes": [(g, "CORES_IDADES", g) for g in CORES_IDADES],
    # (as cores dos indicadores ficam no CSS do começo da página, antes destas mudanças: não entram aqui)
    "vias": [(t, "CORES_VIAS", t) for t in CORES_VIAS],
    "vias_cn": [(t, "CORES_ESTRADAS", t) for t in CORES_ESTRADAS],
    "tempo_cn": [("Cor principal", "COR_TRANSPORTE", None), ("Cor escura", "COR_TRANSPORTE_ESCURA", None)],
}
for _base in ("dependencia", "emprego", "divisoes"):
    CORES_EDITAVEIS[f"{_base}_cn"] = CORES_EDITAVEIS[_base]
CORES_EDITAVEIS["meio_cn"] = CORES_EDITAVEIS["frota_cn"] = CORES_EDITAVEIS["tempo_cn"]
# Tipos de gráfico originais de cada componente (a administração escolhe quais aparecem e a ordem)
OPCOES_DOS_COMPONENTES = {
    "divisoes": OPCOES_GRAFICO, "divisoes_cn": OPCOES_GRAFICO,
    "emprego": OPCOES_GRAFICO_EMPREGO, "emprego_cn": OPCOES_GRAFICO_EMPREGO,
    "dependencia": OPCOES_GRAFICO_DEPENDENCIA, "dependencia_cn": OPCOES_GRAFICO_DEPENDENCIA,
    "tempo_cn": OPCOES_GRAFICO_TEMPO, "meio_cn": OPCOES_GRAFICO_MEIO, "frota_cn": OPCOES_GRAFICO_FROTA,
}


def cor_atual(variavel, chave_dict):
    valor = globals()[variavel]
    return valor[chave_dict] if chave_dict is not None else valor


# Cores de antes das mudanças da administração (para saber o que mudou e voltar ao original)
CORES_ORIGINAIS = {(variavel, chave_dict): cor_atual(variavel, chave_dict)
                   for cores in CORES_EDITAVEIS.values() for _, variavel, chave_dict in cores}


def aplicar_cores_editadas():
    for chave, editado in CONFIG_ADMIN.get("componentes", {}).items():
        for nome, variavel, chave_dict in CORES_EDITAVEIS.get(chave, []):
            cor = editado.get("cores", {}).get(nome)
            if not cor:
                continue
            if chave_dict is None:
                globals()[variavel] = cor
            else:
                globals()[variavel][chave_dict] = cor


# --- ÁREA DE ADMINISTRAÇÃO (AdminDashboard, AdminEditComponent, AdminIssue, AdminDisaster, AdminUser e
# AdminContributor do Taipei). As mudanças ficam em usuarios/admin_painel.json e valem sem mexer no código ---
TITULOS_ORIGINAIS = dict(TITULOS_CARTOES)
RESUMOS_ORIGINAIS = dict(RESUMO_CARTOES)


def aplicar_config_admin():
    """Troca os painéis públicos, os títulos/resumos dos componentes e os colaboradores pelos da administração."""
    if CONFIG_ADMIN.get("paineis_publicos"):
        PAINEIS_PUBLICOS.clear()
        GRUPOS_MENU.clear()
        for chave, painel in CONFIG_ADMIN["paineis_publicos"].items():
            PAINEIS_PUBLICOS[chave] = (painel["titulo"], painel["icone"],
                                       [c for c in painel["cartoes"] if c in CARTOES])
            GRUPOS_MENU.setdefault(painel["grupo"], []).append(chave)
    for chave, editado in CONFIG_ADMIN.get("componentes", {}).items():
        if chave in CARTOES and editado.get("titulo"):
            TITULOS_CARTOES[chave] = editado["titulo"]
        if chave in RESUMO_CARTOES and editado.get("resumo"):
            RESUMO_CARTOES[chave] = (editado["resumo"], *RESUMO_CARTOES[chave][1:])
    if "colaboradores" in CONFIG_ADMIN:
        COLABORADORES[:] = CONFIG_ADMIN["colaboradores"]
    aplicar_cores_editadas()


registrar_componentes_novos()   # antes de aplicar_config_admin: os painéis públicos podem usar os novos
aplicar_config_admin()

SECOES_ADMIN = {   # seção: (grupo no menu, título, ícone)
    "paineis": ("Painéis", "Painéis públicos", "dashboard"),
    "componentes": ("Componentes", "Editar componentes públicos", "edit_note"),
    "problemas": ("Problemas", "Problemas a responder", "bug_report"),
    "ocorrencias": ("Problemas", "Ocorrências dos cidadãos", "flood"),
    "usuarios": ("Sistema", "Usuários", "person"),
    "colaboradores": ("Sistema", "Colaboradores", "handshake"),
    "atualizacao": ("Sistema", "Atualização dos dados", "sync"),
}
SITUACOES_PROBLEMA = ["Pendente", "Em andamento", "Resolvido"]


def salvar_config_admin(chave, valor):
    config = carregar_json(ARQ_ADMIN, {})
    if valor is None:
        config.pop(chave, None)
    else:
        config[chave] = valor
    salvar_json(ARQ_ADMIN, config)


def agora_texto():
    return pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")


def etiqueta_situacao(situacao):
    cores = {"Pendente": "#F8CF58", "Em andamento": "#5a9cf8", "Resolvido": "#56B96D", "Aprovada": "#56B96D",
             "Rejeitada": "#e5484d", "Ativo": "#56B96D", "Desativado": "#e5484d", "Atualizado": "#56B96D",
             "Sem mudança": "#F8CF58", "Erro": "#e5484d"}
    return f'<span class="admin-situacao" style="border-color:{cores.get(situacao, "#888")}; ' \
           f'color:{cores.get(situacao, "#ccc")}">{html.escape(situacao)}</span>'


def linha_admin(valores, larguras, cabecalho=False):
    """Uma linha da tabela: cada valor numa coluna; devolve a última coluna (para os botões)."""
    colunas = st.columns(larguras, vertical_alignment="center", gap="small")
    classe = "admin-cabecalho" if cabecalho else "admin-celula"
    for coluna, valor in zip(colunas, valores):
        coluna.markdown(f'<div class="{classe}">{valor}</div>', unsafe_allow_html=True)
    return colunas[-1]


def menu_admin():
    """Menu lateral da administração (AdminSideBar do Taipei)."""
    with st.sidebar:
        st.markdown('<div class="menu-titulo">Administração</div>', unsafe_allow_html=True)
        grupo_anterior = None
        for secao, (grupo, titulo, icone) in SECOES_ADMIN.items():
            if grupo != grupo_anterior:
                st.markdown(f'<div class="menu-grupo">{grupo}</div>', unsafe_allow_html=True)
                grupo_anterior = grupo
            if st.button(titulo, key=f"aba_menu_admin_{secao}", icon=f":material/{icone}:", type="tertiary",
                         width="stretch"):
                st.session_state.admin_secao = secao
                st.rerun()


def pagina_admin():
    if not e_admin():
        st.markdown('<div class="aviso-vazio">Só administradores podem ver esta página.</div>',
                    unsafe_allow_html=True)
        return
    secao = st.session_state.get("admin_secao", "paineis")
    _, titulo, icone = SECOES_ADMIN[secao]
    st.markdown(f"""<style>
        .st-key-aba_menu_admin_{secao} button {{ border-left: 4px solid #5a9cf8 !important;
            background-color: {COR_CARTAO} !important; }}
        .st-key-aba_menu_admin_{secao} button p, .st-key-aba_menu_admin_{secao} button span {{
            color: #5a9cf8 !important; }}
    </style>""", unsafe_allow_html=True)
    with st.container(horizontal=True, vertical_alignment="center", key="linha_titulo_painel"):
        st.markdown(f'<div class="titulo-painel"><span class="icone-material">{icone}</span>{titulo}'
                    '<span class="etiqueta-grupo">Administração</span></div>', unsafe_allow_html=True,
                    width="content")
    {"paineis": admin_paineis, "componentes": admin_componentes, "problemas": admin_problemas,
     "ocorrencias": admin_ocorrencias, "usuarios": admin_usuarios, "colaboradores": admin_colaboradores,
     "atualizacao": admin_atualizacao}[secao]()


# Painéis públicos
def paineis_atuais():
    return {chave: {"titulo": PAINEIS_PUBLICOS[chave][0], "icone": PAINEIS_PUBLICOS[chave][1],
                    "cartoes": list(PAINEIS_PUBLICOS[chave][2]), "grupo": grupo}
            for grupo, chaves in GRUPOS_MENU.items() for chave in chaves}


def admin_paineis():
    if st.button("Adicionar painel público", icon=":material/add_circle:", key="admin_novo_painel"):
        janela_admin_painel(None)
    larguras = [2.2, 1.6, 3.6, 0.9]
    linha_admin(["Painel", "Grupo", "Componentes", ""], larguras, cabecalho=True)
    for grupo, chaves in GRUPOS_MENU.items():
        for chave in chaves:
            titulo, icone, cartoes = PAINEIS_PUBLICOS[chave]
            nomes = ", ".join(html.escape(TITULOS_CARTOES.get(c, c)) for c in cartoes) or "—"
            ultima = linha_admin([f'<span class="icone-material">{icone}</span>{html.escape(titulo)}',
                                  html.escape(grupo), f"{len(cartoes)}: {nomes}", ""], larguras)
            if ultima.button("Editar", icon=":material/edit:", type="tertiary", key=f"admin_editar_painel_{chave}"):
                janela_admin_painel(chave)


def aviso_na_janela(texto):
    """Aviso de campo faltando numa janela da administração, sem fechar a janela."""
    st.toast(texto, icon=":material/error:")


@st.dialog("Painel público", width="large")
def janela_admin_painel(chave):
    atual = paineis_atuais().get(chave, {"titulo": "", "icone": ICONES_PAINEL[0], "cartoes": [],
                                         "grupo": next(iter(GRUPOS_MENU), "Painel de Oriximiná")})
    sufixo = chave or "novo"
    nome = st.text_input("Nome do painel*", value=atual["titulo"], max_chars=30, key=f"adm_p_nome_{sufixo}").strip()
    grupos = list(GRUPOS_MENU) + ["Novo grupo…"]
    grupo = st.selectbox("Grupo no menu", grupos, index=grupos.index(atual["grupo"]) if atual["grupo"] in grupos
                         else 0, key=f"adm_p_grupo_{sufixo}")
    if grupo == "Novo grupo…":
        grupo = st.text_input("Nome do novo grupo*", key=f"adm_p_grupo_novo_{sufixo}").strip()
    icone = st.pills("Ícone", ICONES_PAINEL, default=atual["icone"], format_func=lambda i: f":material/{i}:",
                     key=f"adm_p_icone_{sufixo}") or ICONES_PAINEL[0]
    cartoes = st.multiselect("Componentes (na ordem em que aparecem)", list(CARTOES), default=atual["cartoes"],
                             format_func=lambda c: f"{CARTOES[c][0]} · {TITULOS_CARTOES[c]}", key=f"adm_p_cartoes_{sufixo}")
    excluir = chave and st.checkbox("Excluir este painel público", key=f"adm_p_excluir_{sufixo}")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if excluir and st.button("Excluir painel", key=f"adm_p_apagar_{sufixo}"):
            paineis = paineis_atuais()
            if len(paineis) == 1:
                aviso_na_janela("É preciso ter pelo menos um painel público")
                return
            else:
                paineis.pop(chave)
                salvar_config_admin("paineis_publicos", paineis)
                st.session_state.aviso = f"Painel {atual['titulo']} excluído"
            st.rerun()
        if st.button("Salvar", type="primary", key=f"adm_p_salvar_{sufixo}"):
            if not nome or not grupo:
                aviso_na_janela("Preencha o nome do painel e o grupo")
                return
            paineis = paineis_atuais()
            if not chave:
                numeros = [int(c.split("_")[-1]) for c in paineis if c.startswith("publico_")]
                chave = f"publico_{max(numeros, default=0) + 1}"
            paineis[chave] = {"titulo": nome, "icone": icone, "cartoes": cartoes, "grupo": grupo}
            salvar_config_admin("paineis_publicos", paineis)
            st.session_state.aviso = f"Painel {nome} salvo"
            st.rerun()


# Componentes
def descricao_original(chave):
    """Descrição e exemplo de uso originais do componente (do texto DESCRICAO_... do código)."""
    id_base = str(CARTOES[chave][0]).replace("cn", "")
    cidade = "calhanorte" if chave.endswith("_cn") else "oriximina"
    for nome, texto in globals().items():
        if nome.startswith("DESCRICAO_") and isinstance(texto, str) \
                and f"ID: {id_base} |" in texto and f"City: {cidade}" in texto:
            return partes_descricao(texto)
    return "", "", "", ""


def admin_componentes():
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        busca = st.text_input("Pesquisar componente", placeholder="Pesquisar por nome ou ID", width=320,
                              label_visibility="collapsed", key="admin_busca_componente").strip().lower()
        # Componente novo a partir de um modelo (AdminAddComponent do Taipei)
        if st.button("Adicionar componente", icon=":material/add_chart:", key="admin_novo_componente"):
            janela_admin_componente_novo(None)
    larguras = [0.7, 3.2, 2.4, 1.1, 0.9]
    linha_admin(["ID", "Componente", "Fonte", "Situação", ""], larguras, cabecalho=True)
    novos = componentes_novos()
    for chave, (id_c, *_) in CARTOES.items():
        if busca and busca not in f"{id_c} {TITULOS_CARTOES[chave]}".lower():
            continue
        editado = componente_editado(chave)
        situacao = "Criado aqui" if chave in novos else ("Editado" if editado else "Original")
        ultima = linha_admin([str(id_c), html.escape(TITULOS_CARTOES[chave]),
                              html.escape(editado.get("fonte") or RESUMO_CARTOES[chave][1]), situacao, ""], larguras)
        if ultima.button("Editar", icon=":material/edit:", type="tertiary", key=f"admin_editar_comp_{chave}"):
            if chave in novos:
                janela_admin_componente_novo(chave)
            else:
                janela_admin_componente(chave)


def ler_links(texto):
    """Uma linha por link: "Nome | https://..." (ou só o endereço)."""
    links = []
    for linha in texto.splitlines():
        nome, _, url = linha.rpartition("|") if "|" in linha else ("", "", linha)
        if url.strip():
            links.append({"nome": nome.strip(), "url": url.strip()})
    return links


def texto_links(links):
    return "\n".join(f"{l['nome']} | {l['url']}" if l["nome"] else l["url"] for l in links)


def nome_cor(chave, nome):
    """Chave de CORES_ORIGINAIS da cor "nome" do componente."""
    _, variavel, chave_dict = next(c for c in CORES_EDITAVEIS[chave] if c[0] == nome)
    return (variavel, chave_dict)


@st.dialog("Editar componente", width="large")
def janela_admin_componente(chave):
    editado = componente_editado(chave)
    _, texto, exemplo, _ = descricao_original(chave)
    st.markdown(f'<div class="catalogo-fonte">ID {CARTOES[chave][0]} · {html.escape(TITULOS_ORIGINAIS[chave])}'
                '</div>', unsafe_allow_html=True)
    aba_textos, aba_grafico, aba_dados = st.tabs(["Textos", "Gráfico", "Links e colaboradores"])
    with aba_textos:
        titulo = st.text_input("Título", value=editado.get("titulo") or TITULOS_ORIGINAIS[chave],
                               key=f"adm_c_titulo_{chave}").strip()
        col_fonte, col_atualizacao = st.columns(2)
        fonte = col_fonte.text_input("Fonte (em branco: a original)", value=editado.get("fonte", ""),
                                     key=f"adm_c_fonte_{chave}").strip()
        atualizacao = col_atualizacao.text_input("Atualização (em branco: a original)",
                                                 value=editado.get("atualizacao", ""),
                                                 key=f"adm_c_atual_{chave}").strip()
        resumo = st.text_area("Resumo (aparece no catálogo)",
                              value=editado.get("resumo") or RESUMOS_ORIGINAIS[chave][0], height=70,
                              key=f"adm_c_resumo_{chave}").strip()
        descricao = st.text_area("Descrição do componente", value=editado.get("descricao") or texto, height=150,
                                 key=f"adm_c_desc_{chave}").strip()
        uso = st.text_area("Exemplo de uso", value=editado.get("exemplo") or exemplo, height=150,
                           key=f"adm_c_uso_{chave}").strip()
    with aba_grafico:
        opcoes = OPCOES_DOS_COMPONENTES.get(chave)
        tipos = []
        if opcoes:
            tipos = st.multiselect("Tipos de gráfico (na ordem dos botões; o primeiro abre primeiro)", opcoes,
                                   default=opcoes_do_componente(chave, opcoes), key=f"adm_c_tipos_{chave}")
        else:
            st.markdown('<div class="catalogo-fonte">Este componente tem um tipo de gráfico só.</div>',
                        unsafe_allow_html=True)
        cores = {}
        editaveis = CORES_EDITAVEIS.get(chave, [])
        if editaveis:
            st.markdown('<div class="catalogo-fonte">Cores (as versões de Oriximiná e da Calha Norte do mesmo '
                        'componente usam as mesmas cores)</div>', unsafe_allow_html=True)
            colunas = st.columns(min(len(editaveis), 4))
            for i, (nome, variavel, chave_dict) in enumerate(editaveis):
                cores[nome] = colunas[i % len(colunas)].color_picker(
                    nome, value=cor_atual(variavel, chave_dict), key=f"adm_c_cor_{chave}_{i}")
        else:
            st.markdown('<div class="catalogo-fonte">As cores deste componente não podem ser trocadas aqui.</div>',
                        unsafe_allow_html=True)
    with aba_dados:
        links = ler_links(st.text_area("Mais conjuntos de dados (um por linha: Nome | https://...)",
                                       value=texto_links(editado.get("links", [])), height=90,
                                       key=f"adm_c_links_{chave}"))
        nomes_colaboradores = [c["nome"] for c in COLABORADORES]
        colaboradores = st.multiselect("Colaboradores deste componente", nomes_colaboradores,
                                       default=[n for n in editado.get("colaboradores", []) if n in nomes_colaboradores],
                                       key=f"adm_c_colab_{chave}")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if editado and st.button("Restaurar o original", key=f"adm_c_restaurar_{chave}"):
            componentes = carregar_json(ARQ_ADMIN, {}).get("componentes", {})
            componentes.pop(chave, None)
            salvar_config_admin("componentes", componentes)
            st.session_state.aviso = "Componente restaurado"
            st.rerun()
        if st.button("Salvar", type="primary", key=f"adm_c_salvar_{chave}"):
            # Guarda só o que ficou diferente do original
            novo = {campo: valor for campo, valor, original in (
                ("titulo", titulo, TITULOS_ORIGINAIS[chave]), ("resumo", resumo, RESUMOS_ORIGINAIS[chave][0]),
                ("descricao", descricao, texto), ("exemplo", uso, exemplo),
                ("fonte", fonte, ""), ("atualizacao", atualizacao, "")) if valor and valor != original}
            if opcoes and tipos and tipos != list(opcoes):
                novo["tipos"] = tipos
            cores_mudadas = {nome: cor for nome, cor in cores.items()
                             if cor.lower() != CORES_ORIGINAIS[nome_cor(chave, nome)].lower()}
            if cores_mudadas:
                novo["cores"] = cores_mudadas
            if links:
                novo["links"] = links
            if colaboradores:
                novo["colaboradores"] = colaboradores
            componentes = carregar_json(ARQ_ADMIN, {}).get("componentes", {})
            if novo:
                componentes[chave] = novo
            else:
                componentes.pop(chave, None)
            salvar_config_admin("componentes", componentes)
            st.session_state.aviso = "Componente salvo"
            st.rerun()


@st.dialog("Componente novo", width="large")
def janela_admin_componente_novo(chave):
    """Cria (ou edita) um componente a partir de um modelo de gráfico e de uma tabela CSV."""
    comp = componentes_novos().get(chave, {})
    sufixo = chave or "novo"
    aba_modelo, aba_textos, aba_dados, aba_mapa = st.tabs(
        ["Modelo e tabela", "Textos", "Links e colaboradores", "Mapa e histórico"])
    with aba_modelo:
        modelo = st.selectbox("Modelo (tipo de gráfico principal)", list(TIPOS_GRAFICO),
                              index=list(TIPOS_GRAFICO).index(comp["tipos"][0]) if comp.get("tipos") else 0,
                              format_func=lambda t: TIPOS_GRAFICO[t][0], key=f"adm_n_modelo_{sufixo}")
        st.markdown(f'<div class="catalogo-fonte">{TIPOS_GRAFICO[modelo][1]} A tabela: 1ª coluna com os rótulos '
                    '(categorias ou anos) e as outras com os números de cada série.</div>', unsafe_allow_html=True)
        st.download_button("Baixar tabela de exemplo", exemplo_csv(modelo).encode("utf-8-sig"),
                           file_name=f"exemplo_{modelo}.csv", mime="text/csv", key=f"adm_n_exemplo_{sufixo}")
        arquivo = st.file_uploader("Tabela do componente (CSV)" + (" — em branco: mantém a atual" if chave else "*"),
                                   type=["csv", "txt"], key=f"adm_n_arquivo_{sufixo}")
        df, erro_tabela = None, ""
        try:
            if arquivo is not None:
                df = ler_tabela(arquivo)
            elif chave:
                df = tabela_componente(chave)
        except Exception as erro:   # CSV mal formado
            erro_tabela = f"Não consegui ler a tabela: {erro}"
        outros = [t for t in TIPOS_GRAFICO if t != modelo]
        extras = st.multiselect("Outros tipos de gráfico (botões de troca)", outros,
                                default=[t for t in comp.get("tipos", [])[1:] if t in outros],
                                format_func=lambda t: TIPOS_GRAFICO[t][0], key=f"adm_n_tipos_{sufixo}")
        col_unidade, col_meta, col_maximo = st.columns(3)
        unidade = col_unidade.text_input("Unidade (ex.: %, pessoas)", value=comp.get("unidade", ""),
                                         key=f"adm_n_unidade_{sufixo}").strip()
        meta = col_meta.number_input("Meta (barras com meta, velocímetro)", value=comp.get("meta"), step=1.0,
                                     key=f"adm_n_meta_{sufixo}")
        maximo = col_maximo.number_input("Máximo (velocímetro, medidor)", value=comp.get("maximo"), step=1.0,
                                         key=f"adm_n_maximo_{sufixo}")
        n_cores = 1
        if df is not None:
            n_cores = max(len(df.columns) - 1, len(df), 1)
        n_cores = min(n_cores, 8)
        st.markdown('<div class="catalogo-fonte">Cores (na ordem das séries ou dos rótulos)</div>',
                    unsafe_allow_html=True)
        colunas = st.columns(n_cores)
        cores_atuais = list(comp.get("cores", [])) + PALETA_PADRAO
        cores = [colunas[i].color_picker(f"Cor {i + 1}", value=cores_atuais[i], key=f"adm_n_cor_{sufixo}_{i}",
                                         label_visibility="collapsed") for i in range(n_cores)]
        if erro_tabela:
            st.markdown(f'<div style="color:#e5484d">{html.escape(erro_tabela)}</div>', unsafe_allow_html=True)
        elif df is not None:
            st.markdown('<div class="catalogo-fonte">Pré-visualização</div>', unsafe_allow_html=True)
            desenhar_grafico_generico(modelo, df, cores, unidade, meta, maximo, altura=300)
    with aba_textos:
        titulo = st.text_input("Título*", value=comp.get("titulo", ""), key=f"adm_n_titulo_{sufixo}").strip()
        col_fonte, col_atualizacao, col_icone = st.columns([2, 1, 1])
        fonte = col_fonte.text_input("Fonte*", value=comp.get("fonte", ""), placeholder="Ex.: Secretaria de Saúde",
                                     key=f"adm_n_fonte_{sufixo}").strip()
        atualizacao = col_atualizacao.text_input("Atualização", value=comp.get("atualizacao", "Dados fixos"),
                                                 key=f"adm_n_atual_{sufixo}").strip()
        icone = col_icone.selectbox("Ícone no catálogo", ICONES_COMPONENTE,
                                    index=ICONES_COMPONENTE.index(comp.get("icone", "bar_chart")),
                                    format_func=lambda i: f":material/{i}: {i}", key=f"adm_n_icone_{sufixo}")
        area = st.text_input("Área (aparece na caixa do cartão)", value=comp.get("area", "Município de Oriximiná"),
                             key=f"adm_n_area_{sufixo}").strip()
        resumo = st.text_area("Resumo (aparece no catálogo)*", value=comp.get("resumo", ""), height=70,
                              key=f"adm_n_resumo_{sufixo}").strip()
        descricao = st.text_area("Descrição do componente", value=comp.get("descricao", ""), height=110,
                                 key=f"adm_n_desc_{sufixo}").strip()
        uso = st.text_area("Exemplo de uso", value=comp.get("exemplo", ""), height=110,
                           key=f"adm_n_uso_{sufixo}").strip()
    with aba_dados:
        links = ler_links(st.text_area("Conjuntos de dados (um por linha: Nome | https://...)",
                                       value=texto_links(comp.get("links", [])), height=90,
                                       key=f"adm_n_links_{sufixo}"))
        nomes_colaboradores = [c["nome"] for c in COLABORADORES]
        colaboradores = st.multiselect("Colaboradores deste componente", nomes_colaboradores,
                                       default=[n for n in comp.get("colaboradores", []) if n in nomes_colaboradores],
                                       key=f"adm_n_colab_{sufixo}")
        paineis = paineis_atuais()
        destino = st.selectbox("Colocar também no painel público", ["(nenhum)"] + list(paineis),
                               format_func=lambda p: p if p == "(nenhum)"
                               else f"{paineis[p]['titulo']} ({paineis[p]['grupo']})", key=f"adm_n_painel_{sufixo}")
    with aba_mapa:
        # Camada no mapa (map_config do Taipei): aparece na Comparação de mapas
        mapa_atual, df_mapa_atual = mapa_componente(chave) if chave else (None, None)
        opcoes_mapa = ["nenhum"] + list(TIPOS_MAPA)
        tipo_mapa = st.selectbox("Camada no mapa", opcoes_mapa,
                                 index=opcoes_mapa.index(mapa_atual["tipo"]) if mapa_atual else 0,
                                 format_func=lambda t: "Sem mapa" if t == "nenhum" else TIPOS_MAPA[t][0],
                                 key=f"adm_n_tipo_mapa_{sufixo}")
        df_mapa, erro_mapa, nome_mapa, cor_mapa = None, "", "", PALETA_PADRAO[0]
        if tipo_mapa != "nenhum":
            st.markdown(f'<div class="catalogo-fonte">{TIPOS_MAPA[tipo_mapa][1]}</div>', unsafe_allow_html=True)
            st.download_button("Baixar tabela de exemplo do mapa", exemplo_csv_mapa(tipo_mapa).encode("utf-8-sig"),
                               file_name=f"exemplo_mapa_{tipo_mapa}.csv", mime="text/csv",
                               key=f"adm_n_exemplo_mapa_{sufixo}")
            arquivo_mapa = st.file_uploader("Tabela do mapa (CSV)" + (" — em branco: mantém a atual"
                                            if mapa_atual and mapa_atual["tipo"] == tipo_mapa else "*"),
                                            type=["csv", "txt"], key=f"adm_n_arquivo_mapa_{sufixo}")
            try:
                if arquivo_mapa is not None:
                    df_mapa, erro_mapa = validar_mapa(tipo_mapa, ler_tabela_mapa(arquivo_mapa))
                elif mapa_atual and mapa_atual["tipo"] == tipo_mapa:
                    df_mapa = df_mapa_atual
            except Exception as erro:   # CSV mal formado
                erro_mapa = f"Não consegui ler a tabela do mapa: {erro}"
            col_nome, col_cor = st.columns([3, 1])
            nome_mapa = col_nome.text_input("Nome da camada", value=(mapa_atual or {}).get("nome", ""),
                                            placeholder="Em branco: o título do componente",
                                            key=f"adm_n_nome_mapa_{sufixo}").strip()
            cor_mapa = col_cor.color_picker("Cor", value=(mapa_atual or {}).get("cor", PALETA_PADRAO[0]),
                                            key=f"adm_n_cor_mapa_{sufixo}")
            if erro_mapa:
                st.markdown(f'<div style="color:#e5484d">{html.escape(erro_mapa)}</div>', unsafe_allow_html=True)
            elif df_mapa is not None:
                st.markdown(f'<div class="catalogo-fonte">Tabela do mapa lida: {len(df_mapa)} linha(s).</div>',
                            unsafe_allow_html=True)
        # Histórico (history_config do Taipei): aparece na descrição, com os botões de período
        historico_atual = comp.get("historico")
        opcoes_hist = ["nenhum"] + list(TIPOS_HISTORICO)
        tipo_hist = st.selectbox("Histórico", opcoes_hist,
                                 index=opcoes_hist.index(historico_atual["tipo"]) if historico_atual else 0,
                                 format_func=lambda t: "Sem histórico" if t == "nenhum" else TIPOS_HISTORICO[t],
                                 key=f"adm_n_tipo_hist_{sufixo}")
        df_hist, erro_hist = None, ""
        if tipo_hist == "propria":
            df_hist = df
            erro_hist = validar_historico(df) if df is not None else "Envie antes a tabela do componente."
        elif tipo_hist == "arquivo":
            st.download_button("Baixar tabela de exemplo do histórico",
                               exemplo_csv("linha_tempo_separada").encode("utf-8-sig"), file_name="exemplo_historico.csv",
                               mime="text/csv", key=f"adm_n_exemplo_hist_{sufixo}")
            arquivo_hist = st.file_uploader("Tabela do histórico (CSV)" + (" — em branco: mantém a atual"
                                            if historico_atual and historico_atual["tipo"] == "arquivo" else "*"),
                                            type=["csv", "txt"], key=f"adm_n_arquivo_hist_{sufixo}")
            try:
                if arquivo_hist is not None:
                    df_hist = ler_tabela(arquivo_hist)
                elif historico_atual and historico_atual["tipo"] == "arquivo":
                    caminho = os.path.join(PASTA_COMPONENTES, f"{chave}_historico.csv")
                    df_hist = ler_tabela(caminho) if os.path.exists(caminho) else None
                erro_hist = validar_historico(df_hist) if df_hist is not None else "Envie a tabela do histórico."
            except Exception as erro:
                erro_hist = f"Não consegui ler a tabela do histórico: {erro}"
        if tipo_hist != "nenhum":
            if erro_hist:
                st.markdown(f'<div style="color:#e5484d">{html.escape(erro_hist)}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="catalogo-fonte">Histórico de {int(df_hist.iloc[0, 0])} a '
                            f'{int(df_hist.iloc[-1, 0])} ({len(df_hist.columns) - 1} série(s)).</div>',
                            unsafe_allow_html=True)
    excluir = chave and st.checkbox("Excluir este componente", key=f"adm_n_excluir_{sufixo}")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if excluir and st.button("Excluir componente", key=f"adm_n_apagar_{sufixo}"):
            novos = carregar_json(ARQ_ADMIN, {}).get("componentes_novos", {})
            novos.pop(chave, None)
            salvar_config_admin("componentes_novos", novos)
            paineis = paineis_atuais()
            for painel in paineis.values():
                painel["cartoes"] = [c for c in painel["cartoes"] if c != chave]
            salvar_config_admin("paineis_publicos", paineis)
            for final in ("", "_mapa", "_historico"):   # a tabela, a do mapa e a do histórico
                caminho = os.path.join(PASTA_COMPONENTES, f"{chave}{final}.csv")
                if os.path.exists(caminho):
                    os.remove(caminho)
            st.session_state.aviso = "Componente excluído"
            st.rerun()
        if st.button("Salvar", type="primary", key=f"adm_n_salvar_{sufixo}"):
            falta = [n for n, v in (("título", titulo), ("fonte", fonte), ("resumo", resumo)) if not v]
            if df is None or erro_tabela:
                falta.append("tabela")
            if tipo_mapa != "nenhum" and (df_mapa is None or erro_mapa):
                falta.append("tabela do mapa (ou escolha \"Sem mapa\")")
            if tipo_hist != "nenhum" and erro_hist:
                falta.append("histórico (ou escolha \"Sem histórico\")")
            if falta:
                aviso_na_janela("Preencha ou corrija: " + ", ".join(falta))
                return
            if chave:
                id_novo = comp["id"]
            else:
                ids = [int(str(c[0])) for c in CARTOES.values() if str(c[0]).isdigit()]
                id_novo = max(ids + [299]) + 1
                chave = f"comp_{id_novo}"
            os.makedirs(PASTA_COMPONENTES, exist_ok=True)
            df.to_csv(os.path.join(PASTA_COMPONENTES, f"{chave}.csv"), index=False, sep=";")
            # Tabelas do mapa e do histórico (arquivos à parte); sem mapa/histórico, os arquivos antigos saem
            caminho_mapa = os.path.join(PASTA_COMPONENTES, f"{chave}_mapa.csv")
            caminho_hist = os.path.join(PASTA_COMPONENTES, f"{chave}_historico.csv")
            if tipo_mapa != "nenhum":
                df_mapa.to_csv(caminho_mapa, index=False, sep=";")
            elif os.path.exists(caminho_mapa):
                os.remove(caminho_mapa)
            if tipo_hist == "arquivo":
                df_hist.to_csv(caminho_hist, index=False, sep=";")
            elif os.path.exists(caminho_hist):
                os.remove(caminho_hist)
            novos = carregar_json(ARQ_ADMIN, {}).get("componentes_novos", {})
            novos[chave] = {"id": id_novo, "titulo": titulo, "fonte": fonte, "atualizacao": atualizacao,
                            "icone": icone, "area": area, "resumo": resumo, "descricao": descricao, "exemplo": uso,
                            "tipos": [modelo] + extras, "cores": cores, "unidade": unidade, "meta": meta,
                            "maximo": maximo, "links": links, "colaboradores": colaboradores,
                            "mapa": {"tipo": tipo_mapa, "nome": nome_mapa, "cor": cor_mapa}
                            if tipo_mapa != "nenhum" else None,
                            "historico": {"tipo": tipo_hist} if tipo_hist != "nenhum" else None}
            salvar_config_admin("componentes_novos", novos)
            if destino != "(nenhum)":
                paineis = paineis_atuais()
                if chave not in paineis[destino]["cartoes"]:
                    paineis[destino]["cartoes"].append(chave)
                salvar_config_admin("paineis_publicos", paineis)
            st.session_state.aviso = f"Componente {titulo} salvo (ID {id_novo})"
            st.rerun()


# Problemas reportados pelos usuários (botão "Reportar" dos componentes)
def admin_problemas():
    problemas = carregar_json(ARQ_PROBLEMAS, [])
    filtro = st.segmented_control("Situação", ["Todos"] + SITUACOES_PROBLEMA, default="Todos",
                                  label_visibility="collapsed", key="admin_filtro_problemas") or "Todos"
    lista = [p for p in reversed(problemas) if filtro == "Todos" or p["status"] == filtro]
    if not lista:
        st.markdown('<div class="aviso-vazio">Nenhum problema reportado com esta situação.</div>',
                    unsafe_allow_html=True)
        return
    larguras = [1.1, 2.2, 2, 2, 1.2, 1.5, 1]
    linha_admin(["Situação", "Título", "Tipo", "Componente", "Aberto em", "Última edição", ""], larguras,
                cabecalho=True)
    for problema in lista:
        edicao = f"{problema['editado_em']}<br>{html.escape(problema['editado_por'])}" if problema["editado_em"] else "—"
        ultima = linha_admin([etiqueta_situacao(problema["status"]), html.escape(problema["titulo"]),
                              html.escape(problema["tipo"]), html.escape(problema["componente"]), problema["data"],
                              edicao, ""], larguras)
        if ultima.button("Responder", icon=":material/reply:", type="tertiary", key=f"admin_problema_{problema['id']}"):
            janela_admin_problema(problema["id"])


@st.dialog("Responder problema", width="medium")
def janela_admin_problema(id_problema):
    problemas = carregar_json(ARQ_PROBLEMAS, [])
    problema = next(p for p in problemas if p["id"] == id_problema)
    st.markdown(f"""<div class="info-colaborador">
        <div class="info-colaborador-nome">{html.escape(problema["titulo"])}</div>
        <div class="info-colaborador-rotulo">Tipo</div><p>{html.escape(problema["tipo"])}</p>
        <div class="info-colaborador-rotulo">Componente e área</div>
        <p>{html.escape(problema["componente"])} · {html.escape(str(problema["area"]))}</p>
        <div class="info-colaborador-rotulo">Descrição</div><p>{html.escape(problema["descricao"])}</p>
        <div class="info-colaborador-rotulo">Aberto em</div>
        <p>{problema["data"]} por {html.escape(problema["usuario"])}</p></div>""", unsafe_allow_html=True)
    situacao = st.selectbox("Situação", SITUACOES_PROBLEMA, index=SITUACOES_PROBLEMA.index(problema["status"]),
                            key=f"adm_pr_situacao_{id_problema}")
    resposta = st.text_area("Resposta / decisão", value=problema.get("resposta", ""), height=100,
                            key=f"adm_pr_resposta_{id_problema}").strip()
    # Apagar de vez (ex.: relato de teste): só aparece depois de marcar a caixa, como nas outras janelas
    excluir = st.checkbox("Excluir este problema", key=f"adm_pr_excluir_{id_problema}")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if excluir and st.button("Excluir problema", key=f"adm_pr_apagar_{id_problema}"):
            salvar_json(ARQ_PROBLEMAS, [p for p in problemas if p["id"] != id_problema])
            st.session_state.aviso = "Problema excluído"
            st.rerun()
        if st.button("Salvar", type="primary", key=f"adm_pr_salvar_{id_problema}"):
            problema.update(status=situacao, resposta=resposta, editado_em=agora_texto(),
                            editado_por=st.session_state.usuario["email"])
            salvar_json(ARQ_PROBLEMAS, problemas)
            st.session_state.aviso = "Problema atualizado"
            st.rerun()


# Ocorrências relatadas pelos cidadãos no mapa (aprovar ou rejeitar, como o AdminDisaster do Taipei)
def admin_ocorrencias():
    ocorrencias = carregar_ocorrencias()
    filtro = st.segmented_control("Situação", ["Todas", "Pendente", "Aprovada", "Rejeitada"], default="Todas",
                                  label_visibility="collapsed", key="admin_filtro_ocorrencias") or "Todas"
    lista = [o for o in reversed(ocorrencias) if filtro == "Todas" or o.get("status", "Pendente") == filtro]
    if not lista:
        st.markdown('<div class="aviso-vazio">Nenhuma ocorrência com esta situação.</div>', unsafe_allow_html=True)
        return
    larguras = [1.1, 1.8, 2.8, 1.8, 1.2, 1.6]
    linha_admin(["Situação", "Tipo", "Descrição", "Local", "Data", ""], larguras, cabecalho=True)
    for ocorrencia in lista:
        situacao = ocorrencia.get("status", "Pendente")
        ultima = linha_admin([etiqueta_situacao(situacao), html.escape(ocorrencia["tipo"]),
                              html.escape(ocorrencia["descricao"]), html.escape(ocorrencia["local"]),
                              ocorrencia["data"], ""], larguras)
        with ultima.container(horizontal=True, gap="small"):
            for rotulo, icone, nova in (("Aprovar", "check", "Aprovada"), ("Rejeitar", "close", "Rejeitada")):
                if situacao != nova and st.button(rotulo, icon=f":material/{icone}:", type="tertiary",
                                                  key=f"admin_oc_{nova}_{ocorrencia['id']}"):
                    ocorrencia.update(status=nova, revisado_em=agora_texto(),
                                      revisado_por=st.session_state.usuario["email"])
                    salvar_json(ARQ_OCORRENCIAS, ocorrencias)
                    st.session_state.aviso = f"Ocorrência {nova.lower()}"
                    st.rerun()


# Usuários
def admin_usuarios():
    busca = st.text_input("Pesquisar usuário", placeholder="Pesquisar por nome ou e-mail", width=320,
                          label_visibility="collapsed", key="admin_busca_usuario").strip().lower()
    larguras = [1.8, 2.6, 1.4, 1.1, 1.5, 0.9]
    linha_admin(["Nome", "Conta", "Tipo", "Situação", "Último login", ""], larguras, cabecalho=True)
    for email, usuario in carregar_usuarios().items():
        if busca and busca not in f"{usuario['nome']} {email}".lower():
            continue
        ativo = usuario.get("ativo", True)
        ultima = linha_admin([html.escape(usuario["nome"]), html.escape(email),
                              "Administrador" if usuario.get("admin") else "Usuário comum",
                              etiqueta_situacao("Ativo" if ativo else "Desativado"),
                              usuario.get("ultimo_login", "—"), ""], larguras)
        if ultima.button("Editar", icon=":material/edit:", type="tertiary", key=f"admin_usuario_{email}"):
            janela_admin_usuario(email)


@st.dialog("Editar usuário", width="small")
def janela_admin_usuario(email):
    usuarios = carregar_usuarios()
    usuario = usuarios[email]
    proprio = email == st.session_state.usuario["email"]
    nome = st.text_input("Nome do usuário", value=usuario["nome"], key=f"adm_u_nome_{email}").strip()
    st.text_input("Conta", value=email, disabled=True)
    admin = st.toggle("Administrador", value=bool(usuario.get("admin")), disabled=proprio, key=f"adm_u_admin_{email}")
    ativo = st.toggle("Conta ativa (pode entrar)", value=usuario.get("ativo", True), disabled=proprio,
                      key=f"adm_u_ativo_{email}")
    if proprio:
        st.markdown('<div class="catalogo-fonte">Você não pode tirar o seu próprio acesso de administrador nem '
                    'desativar a sua conta.</div>', unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Salvar", type="primary", key=f"adm_u_salvar_{email}"):
            usuario.update(nome=nome or usuario["nome"], admin=admin, ativo=ativo)
            salvar_usuarios(usuarios)
            if proprio:
                st.session_state.usuario["nome"] = usuario["nome"]
            if not ativo:   # derruba as sessões abertas da conta desativada
                salvar_sessoes({k: v for k, v in carregar_sessoes().items() if v != email})
            st.session_state.aviso = "Usuário atualizado"
            st.rerun()


# Colaboradores
def admin_colaboradores():
    if st.button("Adicionar colaborador", icon=":material/person_add:", key="admin_novo_colaborador"):
        janela_admin_colaborador(None)
    larguras = [0.6, 2.4, 2.4, 2.4, 0.9]
    linha_admin(["", "Nome", "Função", "Link", ""], larguras, cabecalho=True)
    for i, colaborador in enumerate(COLABORADORES):
        ultima = linha_admin([foto_colaborador(colaborador, 36), html.escape(colaborador["nome"]),
                              html.escape(colaborador["funcao"]), html.escape(colaborador["link"]), ""], larguras)
        if ultima.button("Editar", icon=":material/edit:", type="tertiary", key=f"admin_colaborador_{i}"):
            janela_admin_colaborador(i)


@st.dialog("Colaborador", width="medium")
def janela_admin_colaborador(indice):
    atual = COLABORADORES[indice] if indice is not None else {"nome": "", "imagem": "", "funcao": "",
                                                              "contribuicao": "", "link": ""}
    sufixo = "novo" if indice is None else indice
    nome = st.text_input("Nome*", value=atual["nome"], key=f"adm_co_nome_{sufixo}").strip()
    funcao = st.text_input("Função", value=atual["funcao"], key=f"adm_co_funcao_{sufixo}").strip()
    contribuicao = st.text_area("Contribuição", value=atual["contribuicao"], height=80,
                                key=f"adm_co_contrib_{sufixo}").strip()
    link = st.text_input("Link", value=atual["link"], placeholder="https://", key=f"adm_co_link_{sufixo}").strip()
    foto = st.file_uploader("Foto (PNG ou JPG)", type=["png", "jpg", "jpeg"], key=f"adm_co_foto_{sufixo}")
    excluir = indice is not None and st.checkbox("Excluir este colaborador", key=f"adm_co_excluir_{sufixo}")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if excluir and st.button("Excluir colaborador", key=f"adm_co_apagar_{sufixo}"):
            salvar_config_admin("colaboradores", [c for i, c in enumerate(COLABORADORES) if i != indice])
            st.session_state.aviso = "Colaborador excluído"
            st.rerun()
        if st.button("Salvar", type="primary", key=f"adm_co_salvar_{sufixo}"):
            if not nome:
                aviso_na_janela("Preencha o nome do colaborador")
                return
            imagem = atual["imagem"]
            if foto is not None:   # a foto vai para a pasta imagens/
                extensao = foto.name.rsplit(".", 1)[-1].lower()
                base = "".join(ch if ch.isalnum() else "_" for ch in nome.lower())[:40]
                imagem = f"colaborador_{base}.{extensao}"
                with open(os.path.join(PASTA_IMAGENS, imagem), "wb") as arquivo:
                    arquivo.write(foto.getvalue())
            novo = {"nome": nome, "imagem": imagem, "funcao": funcao, "contribuicao": contribuicao, "link": link}
            lista = list(COLABORADORES)
            if indice is None:
                lista.append(novo)
            else:
                lista[indice] = novo
            salvar_config_admin("colaboradores", lista)
            st.session_state.aviso = f"Colaborador {nome} salvo"
            st.rerun()


# --- ATUALIZAÇÃO DOS DADOS (administração): data de cada fonte e botão para rodar os scripts ---
PASTA_SCRIPTS = os.path.join(PASTA_PROJETO, "scripts")
PASTA_BACKUPS = os.path.join(PASTA_PROJETO, "backups")
ARQ_ATUALIZACOES = os.path.join(PASTA_USUARIOS, "atualizacoes_painel.json")
# script: (dados, fonte, arquivos que gera em dados/, com que frequência a fonte publica, de onde lê)
# "de onde lê": "internet" ou uma lista de pastas/arquivos dentro da pasta de downloads das fontes
FONTES_DADOS = {
    "filtrar_mapa.py": ("Mapa dos setores censitários", "IBGE – malha de setores do Censo 2022",
                        ["oriximina_setores.geojson"], "A cada Censo (10 anos)", ["@dados/fontes"]),
    "preparar_dados.py": ("Moradores por setor e por bairro", "IBGE – Censo 2022 e CNEFE",
                          ["dados_setores_oriximina.csv", "dados_bairros_oriximina.csv"], "A cada Censo (10 anos)",
                          ["Agregados_por_setores_basico_BR_20260520", "Agregados_por_setores_demografia_BR", "CNEFE"]),
    "preparar_mapa.py": ("Escolas e postos de saúde", "IBGE – CNEFE 2022", ["pontos_oriximina.csv"],
                         "A cada Censo (10 anos)", ["CNEFE"]),
    "preparar_dependencia.py": ("Razão de dependência de Oriximiná", "DATASUS – estimativas populacionais (TabNet)",
                                ["dados_dependencia_oriximina.csv"], "Anual", "internet"),
    "preparar_rais.py": ("Empregos por idade de Oriximiná", "Ministério do Trabalho – RAIS",
                         ["dados_emprego_idade_oriximina.csv"], "Anual", ["RAIS"]),
    "preparar_vias.py": ("Ruas da sede", "OpenStreetMap", ["vias_oriximina.geojson"],
                         "Quando o mapa colaborativo muda", "internet"),
    "preparar_regiao.py": ("Dados da Calha Norte", "IBGE, DATASUS e RAIS",
                           ["regiao_municipios.geojson", "regiao_idades.csv", "regiao_dependencia.csv",
                            "regiao_emprego.csv"], "Anual", ["RAIS"]),
    "preparar_transporte.py": ("Transporte da Calha Norte", "IBGE – Censo 2022 e SENATRAN (frota)",
                               ["regiao_transporte_meio.csv", "regiao_transporte_tempo.csv", "regiao_frota.csv"],
                               "Mensal (frota)", "internet"),
    "preparar_cartografia_regiao.py": ("Estradas e sedes da Calha Norte", "OpenStreetMap",
                                       ["regiao_estradas.geojson", "regiao_sedes.csv"],
                                       "Quando o mapa colaborativo muda", "internet"),
    "preparar_predios.py": ("Prédios em 3D da sede", "OpenStreetMap (contornos) e GHSL – Comissão Europeia (altura)",
                            ["predios_oriximina.geojson"], "Quando o mapa colaborativo muda", "internet"),
}


def pasta_das_fontes():
    """Pasta dos arquivos grandes baixados das fontes (a mesma que os scripts usam)."""
    try:
        with open(os.path.join(PASTA_SCRIPTS, "preparar_dados.py"), encoding="utf-8") as arquivo:
            achado = re.search(r'PASTA_IBGE = r"(.+?)"', arquivo.read())
        return achado.group(1) if achado else None
    except OSError:
        return None


def fontes_locais_ok(origem):
    """(pronto?, texto) sobre a origem dos dados: internet ou arquivos baixados que precisam existir."""
    if origem == "internet":
        return True, "Internet"
    base = pasta_das_fontes()
    faltando = []
    for item in origem:
        caminho = os.path.join(PASTA_PROJETO, item[1:]) if item.startswith("@") else os.path.join(base or "", item)
        if not base and not item.startswith("@") or not os.path.exists(caminho):
            faltando.append(item.lstrip("@"))
    if faltando:
        return False, "Faltam arquivos: " + ", ".join(faltando)
    return True, "Arquivos baixados"


def data_dos_arquivos(arquivos):
    """Data da última atualização (o arquivo mais recente) ou None se algum não existe."""
    caminhos = [os.path.join(PASTA_DADOS, a) for a in arquivos]
    if not all(os.path.exists(c) for c in caminhos):
        return None
    return max(os.path.getmtime(c) for c in caminhos)


def rodar_script(script):
    """Roda um script de scripts/ guardando antes uma cópia dos arquivos que ele gera (em backups/).
    Se o script der erro, os arquivos antigos voltam. Devolve o registro da atualização."""
    nome, _, arquivos, _, _ = FONTES_DADOS[script]
    carimbo = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    pasta_copia = os.path.join(PASTA_BACKUPS, f"dados_antes_{os.path.splitext(script)[0]}_{carimbo}")
    os.makedirs(pasta_copia, exist_ok=True)
    for arquivo in arquivos:
        if os.path.exists(os.path.join(PASTA_DADOS, arquivo)):
            shutil.copy2(os.path.join(PASTA_DADOS, arquivo), pasta_copia)
    inicio = time.time()
    try:
        processo = subprocess.run([sys.executable, os.path.join(PASTA_SCRIPTS, script)], cwd=PASTA_SCRIPTS,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        codigo, saida = processo.returncode, (processo.stdout or "") + (processo.stderr or "")
    except subprocess.TimeoutExpired:
        codigo, saida = -1, "O script passou de 30 minutos e foi interrompido."
    duracao = time.time() - inicio
    mudou = [a for a in arquivos if os.path.exists(os.path.join(PASTA_DADOS, a))
             and os.path.getmtime(os.path.join(PASTA_DADOS, a)) >= inicio]
    if codigo != 0:
        # Deu erro: devolve os arquivos de antes (o script pode ter deixado algum pela metade)
        for arquivo in arquivos:
            copia = os.path.join(pasta_copia, arquivo)
            if os.path.exists(copia):
                shutil.copy2(copia, os.path.join(PASTA_DADOS, arquivo))
        resultado = "Erro"
        mudou = []   # nada ficou mudado: os arquivos de antes voltaram
    else:
        resultado = "Atualizado" if mudou else "Sem mudança"
    registro = {"script": script, "dados": nome, "quando": agora_texto(), "duracao_s": round(duracao),
                "resultado": resultado, "arquivos": mudou, "copia": os.path.relpath(pasta_copia, PASTA_PROJETO),
                "usuario": st.session_state.usuario["email"], "saida": saida[-4000:]}
    historico = carregar_json(ARQ_ATUALIZACOES, [])
    historico.append(registro)
    salvar_json(ARQ_ATUALIZACOES, historico[-200:])
    return registro


def admin_atualizacao():
    st.markdown('<div class="catalogo-fonte">Censo, RAIS e DATASUS publicam dados poucas vezes por ano ou por década, '
                'por isso o painel não é em tempo real. Quando sair um dado novo, clique em <b>Atualizar</b>: o script '
                'da pasta <code>scripts/</code> roda e gera de novo os arquivos da pasta <code>dados/</code>. Antes, uma '
                'cópia dos arquivos atuais vai para <code>backups/</code>; se o script der erro, eles voltam. As fontes '
                '"Arquivos baixados" precisam dos arquivos novos na pasta de downloads das fontes '
                f'(<code>{html.escape(pasta_das_fontes() or "não encontrada")}</code>).</div>', unsafe_allow_html=True)
    ultimo = st.session_state.pop("ultima_atualizacao", None)
    if ultimo:
        with st.container(key="resultado_atualizacao"):
            detalhe = ("O script deu erro e os arquivos de antes foram restaurados (veja as mensagens abaixo)."
                       if ultimo["resultado"] == "Erro" else
                       f'Arquivos atualizados: {html.escape(", ".join(ultimo["arquivos"]) or "nenhum")}.')
            st.markdown(f'{etiqueta_situacao(ultimo["resultado"])} <b>{html.escape(ultimo["dados"])}</b> — '
                        f'{ultimo["duracao_s"]} s. {detalhe} Cópia de antes: '
                        f'<code>{html.escape(ultimo["copia"])}</code>', unsafe_allow_html=True)
            with st.expander("Mensagens do script"):
                st.code(ultimo["saida"] or "(sem mensagens)", language=None)
    larguras = [2.2, 2.4, 1.5, 1.4, 1.8, 1.1]
    linha_admin(["Dados", "Fonte", "Frequência", "Última atualização", "Origem", ""], larguras, cabecalho=True)
    for script, (nome, fonte, arquivos, frequencia, origem) in FONTES_DADOS.items():
        data = data_dos_arquivos(arquivos)
        pronto, origem_texto = fontes_locais_ok(origem)
        quando = pd.Timestamp(data, unit="s", tz="UTC").tz_convert("America/Belem").strftime("%d/%m/%Y %H:%M") \
            if data else "Arquivo faltando"
        ultima = linha_admin([f'{html.escape(nome)}<br><span class="popup-camada">{script}</span>', html.escape(fonte),
                              frequencia, quando,
                              html.escape(origem_texto) if pronto
                              else f'<span style="color:#e5484d">{html.escape(origem_texto)}</span>', ""], larguras)
        if ultima.button("Atualizar", icon=":material/sync:", type="tertiary",
                         key=f"atualizar_{os.path.splitext(script)[0]}",   # chave sem o ponto do ".py"
                         disabled=not pronto, help=None if pronto else origem_texto):
            with st.spinner(f"Rodando {script}… pode levar alguns minutos. Não feche a página."):
                st.session_state.ultima_atualizacao = rodar_script(script)
            st.rerun()
    historico = carregar_json(ARQ_ATUALIZACOES, [])
    if historico:
        st.markdown('<div class="camadas-basicas-titulo">Últimas atualizações</div>', unsafe_allow_html=True)
        larguras_h = [1.4, 2.2, 1.2, 1, 2]
        linha_admin(["Quando", "Dados", "Resultado", "Duração", "Quem"], larguras_h, cabecalho=True)
        for registro in reversed(historico[-10:]):
            linha_admin([registro["quando"], html.escape(registro["dados"]), etiqueta_situacao(registro["resultado"]),
                         f'{registro["duracao_s"]} s', html.escape(registro["usuario"])], larguras_h)


# --- MONTAGEM DA PÁGINA ---
for chave, valor in (("info_aberto", None), ("favoritos", set()), ("usuario", None), ("paineis_pessoais", []),
                     ("pontos_de_vista", []), ("pagina", "painel"), ("painel", "cuidados")):
    if chave not in st.session_state:
        st.session_state[chave] = valor
if st.session_state.usuario is None and "sessao" in st.query_params:
    retomar_sessao()
# Painel que não existe mais (ex.: excluído na administração, ou painel pessoal de quem saiu): volta ao primeiro
painel_atual = st.session_state.painel
if not (painel_atual in PAINEIS_PUBLICOS or (painel_atual == "favoritos" and st.session_state.usuario)
        or (painel_atual.startswith("pessoal_") and painel_pessoal(painel_atual))):
    st.session_state.painel = next(iter(PAINEIS_PUBLICOS))
# Área de administração só para administradores (ex.: depois de sair da conta)
if st.session_state.pagina == "admin" and not e_admin():
    st.session_state.pagina = "painel"

# "Incorporar": com ?componente=216 (ou outro ID) mostra só aquele cartão, sem barra nem menu
so_um = st.query_params.get("componente")
chaves_incorporadas = [c for c, (id_c, *_) in CARTOES.items() if str(id_c) == so_um]
if chaves_incorporadas:
    st.markdown('<style>.stMainBlockContainer { padding-top: 16px !important; padding-bottom: 16px !important; }'
                '</style>', unsafe_allow_html=True)
    grade_cartoes(chaves_incorporadas)
else:
    # Aba ativa da barra de cima e do menu lateral em azul, como no Taipei
    pagina, painel = st.session_state.pagina, st.session_state.painel
    aba = "catalogo" if pagina == "componente" else pagina   # a página do componente faz parte do catálogo
    st.markdown(f"""<style>
        .st-key-aba_topo_{aba} button {{ border-bottom: 3px solid #5a9cf8 !important; }}
        .st-key-aba_topo_{aba} button p {{ color: #5a9cf8 !important; }}
        .st-key-aba_menu_{painel} button, .st-key-celular_menu_{painel} button {{
            border-left: 4px solid #5a9cf8 !important; background-color: {COR_CARTAO} !important; }}
        .st-key-aba_menu_{painel} button p, .st-key-aba_menu_{painel} button span,
        .st-key-celular_menu_{painel} button p, .st-key-celular_menu_{painel} button span,
        .st-key-celular_pagina_{aba} button p, .st-key-celular_pagina_{aba} button span {{
            color: #5a9cf8 !important; }}
    </style>""", unsafe_allow_html=True)
    # Corações vermelhos nos cartões que já são favoritos (no painel e no catálogo)
    # (sempre desenhado, mesmo vazio, para a página não mudar de lugar ao marcar o primeiro favorito)
    with st.container(key="estilo_favoritos"):
        st.markdown("<style>" + " ".join(
            f".st-key-botao_favorito_{c} button p, .st-key-botao_favorito_{c}_janela button p, "
            f".st-key-catalogo_favorito_{c} button p "
            "{ color: #f44336 !important; }" for c in st.session_state.favoritos
        ) + "</style>", unsafe_allow_html=True)
    barra_topo()
    with st.container(key="scripts_pagina"):
        script_tela_cheia()
        if st.session_state.pop("gravar_cookie_aviso", False):
            script_gravar_cookie_aviso()
    # No catálogo e na página do componente não há menu lateral (como no Taipei); no celular ele vira o ☰
    if pagina == "admin" and not CELULAR:
        menu_admin()
    elif pagina not in ("catalogo", "componente", "documentacao", "admin") and not CELULAR:
        menu_lateral()
    if pagina == "mapa":
        pagina_mapa()
    elif pagina == "catalogo":
        pagina_catalogo()
    elif pagina == "componente":
        pagina_componente()
    elif pagina == "documentacao":
        pagina_documentacao()
    elif pagina == "admin":
        pagina_admin()
    else:
        pagina_painel()
    robo_ajuda()
    with st.container(key="linha_atualizacao"):
        proxima_atualizacao()
    # Aviso inicial: uma vez por visita, a não ser que a pessoa tenha pedido para não ver mais
    if (not st.session_state.get("aviso_inicial_visto")
            and st.context.cookies.get(COOKIE_AVISO_INICIAL) != "visto"):
        janela_aviso_inicial_celular() if CELULAR else janela_aviso_inicial()

# Reportar / Baixar / Incorporar pedidos de dentro da janela "Informações do componente" (que já fechou)
janela_pendente = st.session_state.pop("janela_pendente", None)
if janela_pendente:
    janela_pendente()
