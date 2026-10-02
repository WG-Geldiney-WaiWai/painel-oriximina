# Painel Oriximiná

Painel de controle da cidade de Oriximiná (PA), inspirado no
[Painel da Cidade de Taipei](https://github.com/tpe-doit/Taipei-City-Dashboard). Mostra dados
oficiais de Oriximiná e da Calha Norte paraense em cartões, com mapas e gráficos.

## Como abrir

1. Instale as bibliotecas (só na primeira vez):
   `python -m pip install -r requirements.txt`
2. Rode o atalho do seu sistema:
   - **Windows:** `iniciar.ps1` (botão direito > "Executar com o PowerShell")
   - **Linux / Mac:** no terminal, nesta pasta: `bash iniciar.sh`

   (Ou, em qualquer sistema, no terminal nesta pasta: `python -m streamlit run painel.py`.)
3. O painel abre em http://localhost:8501.

## Pastas

| Pasta / arquivo | O que tem |
|---|---|
| `painel.py` | O painel inteiro: barra de cima, menu lateral, cartões, janelas e mapa |
| `iniciar.ps1` / `iniciar.sh` | Atalhos para abrir o painel (Windows / Linux e Mac) |
| `.streamlit/config.toml` | Tema escuro e a cor azul do painel de Taipei |
| `dados/` | Arquivos que o painel lê (CSV e GeoJSON), gerados pelos scripts |
| `dados/fontes/` | Malha de setores censitários do Pará (IBGE, Censo 2022) |
| `imagens/` | Brasão de Oriximiná |
| `scripts/` | Scripts que baixam e preparam os dados (rode quando quiser atualizar) |
| `usuarios/` | Contas, favoritos, painéis pessoais e relatos (criados pelo próprio painel) |
| `backups/` | Versões anteriores do painel e dos dados |
| `static/` | Cópia dos prédios em 3D que o navegador baixa (o painel cria e atualiza sozinho) |

## Painéis

**Painel de Oriximiná**
- Cuidados de longo prazo: razão de dependência, emprego por idade, divisões etárias, indicadores
- Informações cartográficas: rede viária da sede urbana

**Painel da Calha Norte** (Oriximiná, Óbidos, Terra Santa, Faro, Alenquer, Curuá, Monte Alegre, Prainha e Almeirim)
- Cuidados de longo prazo
- Transporte prático: tempo de deslocamento, meio de transporte e frota de veículos
- Informações cartográficas: estradas, limites e sedes municipais

## Funções do painel

| Onde | O que faz |
|---|---|
| **Visão geral do painel** | Cartões lado a lado; "Informações do componente" abre a descrição, o histórico e os botões Reportar, Baixar e Incorporar |
| **Catálogo de componentes** | Todos os cartões, com busca; "Página de informações" abre a página própria de cada um; com a conta, monta painéis pessoais pelo [+] |
| **Comparação de mapas** | Camadas dos cartões (setores, bairros, pontos, vias, estradas) para ligar e desligar no mesmo mapa, mais as **camadas básicas** (bairros, saúde, ensino, ruas da sede e limites municipais), disponíveis em todos os painéis. Cada camada ligada tem um gráfico pequeno: clicar numa barra deixa no mapa só aquela zona, bairro, localidade, município ou tipo de via (clicar de novo, ou em "Mostrar tudo", volta tudo). O botão **Prédios em 3D** levanta os prédios da sede e inclina o mapa |
| **Entrar** | Conta com e-mail e senha: favoritos (♥), painéis pessoais e configurações do usuário. No painel pessoal, a ordem dos componentes muda arrastando os quadradinhos (no celular, pelas setinhas ‹ ›) |
| **Barra de cima** | Tela cheia (⛶); ⓘ com esta documentação e os colaboradores do projeto. Na documentação, a chavinha 🌙 no canto direito deixa a página escura ou clara |
| **Robozinho** (canto de baixo) | Perguntas frequentes com respostas prontas |
| **Celular** | Menu ☰ no lugar do menu lateral e botão "Camadas" no mapa |
| **Administração** (conta de administrador) | Painéis públicos, componentes (textos, tipos de gráfico, cores, links, colaboradores e **componentes novos** a partir de uma tabela CSV), problemas reportados, ocorrências, usuários e colaboradores |

**Componentes novos:** na administração, em "Editar componentes públicos" > "Adicionar componente", escolha
o modelo de gráfico (colunas, barras, barras (%), barras com meta, linha do tempo separada ou empilhada, rosca,
área polar, radar, mapa de árvore, mapa de calor, velocímetro, medidor ou número com unidade), baixe a tabela
de exemplo, preencha e envie o CSV. A 1ª coluna tem os rótulos (categorias ou anos) e as outras, os números.
As tabelas ficam em `dados/componentes/`.

Na aba **Mapa e histórico** o componente novo pode ganhar:
- **uma camada no mapa** (aparece na Comparação de mapas): pontos (colunas Nome, Latitude e Longitude),
  valores por bairro da sede ou valores por município da Calha Norte - cada modelo tem tabela de exemplo;
- **um histórico** (aparece na descrição, com os botões de período): a própria tabela do componente, quando
  a 1ª coluna tem anos, ou uma tabela de histórico à parte.

O painel recarrega sozinho a cada 10 minutos, lendo de novo os arquivos da pasta `dados/`.
Um cartão pode ser colocado em outro site com o endereço `?componente=ID` (botão "Incorporar").

## Entrar, cadastrar e "Esqueci a senha"

Na janela **Entrar**: quem não tem conta clica em **"Não tem conta? Cadastre-se"** (nome, e-mail e senha) e já
fica logado. Quem esqueceu a senha clica em **"Esqueci a senha"**, digita o e-mail e recebe um **código de 6
números**; com ele, cria uma senha nova e entra normalmente.

- O código vale por 15 minutos e aceita 5 tentativas; um código novo só pode ser pedido depois de 1 minuto.
- O código fica guardado embaralhado em `usuarios/recuperacao_senha.json` (nunca em texto aberto).
- A resposta é a mesma com ou sem conta, para ninguém descobrir quais e-mails estão cadastrados.
- Depois de trocar a senha, quem estava logado com a senha antiga (em outro computador) sai.

Para o painel mandar o e-mail, ele precisa de uma conta que envie as mensagens. Com Gmail: ative a
verificação em duas etapas da conta e crie uma **senha de app** (em myaccount.google.com > Segurança >
Senhas de app). Depois crie (ou complete) o arquivo `.streamlit/secrets.toml` nesta pasta e reinicie o painel:

```toml
[email]
servidor = "smtp.gmail.com"
porta = 587
usuario = "sua-conta@gmail.com"
senha = "a-senha-de-app-de-16-letras"
remetente = "Painel Oriximiná <sua-conta@gmail.com>"
```

Outros provedores também servem (Outlook: `smtp.office365.com`, porta 587). Não envie esse arquivo para
ninguém. Sem ele, o "Esqueci a senha" avisa que o envio de e-mail não foi configurado.

## Prédios em 3D (mapa)

Na **Comparação de mapas**, o botão **Prédios em 3D** (na barra de cima do mapa) levanta os 16 mil prédios
da sede de Oriximiná e inclina o mapa, como o mapa 3D do Taipei. Passando o mouse num prédio aparece a altura.

- **Contornos:** OpenStreetMap.
- **Altura:** GHSL (Global Human Settlement Layer, da Comissão Europeia), que estima por satélite a altura
  média dos prédios de 2018 em quadrados de cerca de 90 m. Todos os prédios do mesmo quadrado ficam com a
  mesma altura: é uma média, não a medida de cada prédio. Os poucos prédios com número de andares no
  OpenStreetMap usam os andares (3 m por andar).

O navegador baixa os prédios do endereço `app/static/`, que precisa da linha `enableStaticServing = true`
em `.streamlit/config.toml` (já colocada). Depois de mudar esse arquivo, feche e abra o painel de novo.

## Resumo com IA (mapa)

Cada camada da **Comparação de mapas** tem o botão **✦ Resumo com IA**: o painel junta os números da
camada e o Claude (modelo Claude Opus 5.5, da Anthropic) escreve um resumo curto em português. O mesmo
resumo fica guardado por 24 horas, para não pagar de novo a cada clique.

Para ligar, é preciso uma chave da API da Anthropic (criada em https://platform.claude.com, com custo
por uso). Crie o arquivo `.streamlit/secrets.toml` nesta pasta com a linha abaixo e reinicie o painel:

```toml
ANTHROPIC_API_KEY = "sua-chave-aqui"
```

Não envie esse arquivo para ninguém nem o coloque em repositórios públicos: quem tiver a chave pode usar
a sua conta. Sem a chave, o botão continua aparecendo e avisa que o resumo não está ligado.

## Atualizar os dados

Cada script em `scripts/` gera os seus arquivos na pasta `dados/`:

| Script | Gera | Fonte |
|---|---|---|
| `filtrar_mapa.py` | `oriximina_setores.geojson` | IBGE, malha de setores (em `dados/fontes`) |
| `preparar_dados.py` | `dados_setores_oriximina.csv`, `dados_bairros_oriximina.csv` | IBGE, Censo 2022 e CNEFE |
| `preparar_dependencia.py` | `dados_dependencia_oriximina.csv` | DATASUS, estimativas populacionais |
| `preparar_rais.py` | `dados_emprego_idade_oriximina.csv` | Ministério do Trabalho, RAIS |
| `preparar_mapa.py` | `pontos_oriximina.csv` | IBGE, CNEFE 2022 |
| `preparar_vias.py` | `vias_oriximina.geojson` | OpenStreetMap |
| `preparar_regiao.py` | `regiao_municipios.geojson`, `regiao_idades.csv`, `regiao_dependencia.csv`, `regiao_emprego.csv` | IBGE, DATASUS, RAIS |
| `preparar_transporte.py` | `regiao_transporte_meio.csv`, `regiao_transporte_tempo.csv`, `regiao_frota.csv` | IBGE, SENATRAN |
| `preparar_cartografia_regiao.py` | `regiao_estradas.geojson`, `regiao_sedes.csv` | OpenStreetMap |
| `preparar_predios.py` | `predios_oriximina.geojson` | OpenStreetMap (contornos) e GHSL, Comissão Europeia (altura) |

Também dá para rodar os scripts pelo próprio painel: entre com uma conta de administrador e abra
**Painel de administração > Atualização dos dados**. A página mostra a fonte, a frequência e a data dos
arquivos de cada dado, e o botão **Atualizar** roda o script. Antes, uma cópia dos arquivos atuais vai para
`backups/dados_antes_<script>_<data>/`; se o script der erro, os arquivos de antes voltam. O histórico fica
em `usuarios/atualizacoes_painel.json`.

Os arquivos grandes baixados das fontes (Censo, CNEFE, RAIS, SENATRAN) ficam em
`Downloads\Pasta Mapa de Painel Oriximiná`, fora deste projeto.
