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

**Primeiro administrador:** dentro do painel, só um administrador torna outra conta administradora (em
Administração > Usuários). Num servidor novo ninguém é administrador ainda; crie o primeiro com:

```
python scripts/criar_admin.py email@exemplo.com
docker compose exec painel python scripts/criar_admin.py email@exemplo.com     (com o Docker)
```

Se a conta já existe, ela vira administradora; se não, o script pede o nome e a senha e cria a conta. Sem
e-mail, ele mostra quem é administrador hoje.

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
| `preparar_trafego.py` | `componentes/comp_301.csv` a `comp_304.csv`, `comp_309.csv` (meio de transporte para o trabalho, lido de `regiao_transporte_meio.csv`) e o painel "Tráfego rodoviário" em `usuarios/admin_painel.json` | IBGE Cidades (frota da SENATRAN), DATASUS (SIM e SIH), IBGE (Censo 2022) |
| `preparar_frota_circulante.py` | `componentes/comp_306.csv` (frota registrada e circulante, no painel "Tráfego rodoviário"); baixa um ZIP de uns 500 MB para a pasta `RENAEST` das fontes | SENATRAN, RENAEST |
| `preparar_habitacao.py` | `componentes/comp_307.csv` e `comp_308.csv` e o painel "Habitação" em `usuarios/admin_painel.json` | Ministério das Cidades, Minha Casa Minha Vida |
| `preparar_planejamento.py` | `componentes/comp_310.csv` (e `comp_310_historico.csv`) e `comp_311.csv` e o painel "Planejamento urbano" em `usuarios/admin_painel.json`; baixa os arquivos para as pastas `MapBiomas` e `AreasProtegidas` das fontes | MapBiomas (Coleção 11), FUNAI, INCRA, MMA (CNUC) e o contorno do IBGE (`PA_Municipios_2025`) |
| `preparar_idade_construcoes.py` | `componentes/comp_312.csv` (idade da área construída por bairro, no painel "Planejamento urbano"); baixa a área construída de 1985, 2005 e 2020 para a pasta `GHSL` das fontes | GHSL, Comissão Europeia (GHS-BUILT-S) |
| `preparar_fundiaria.py` | `componentes/comp_313.csv` (situação fundiária, no painel "Planejamento urbano"); baixa o CNFP (uns 230 MB) e o SIGEF do Pará para a pasta `AreasProtegidas` das fontes | Serviço Florestal Brasileiro (CNFP 2025), INCRA (SIGEF) |
| `preparar_areas_verdes.py` | `componentes/comp_314.csv` (parques e praças do OpenStreetMap) e `comp_315.csv` (áreas verdes por bairro, por satélite), no painel "Planejamento urbano"; baixa o quadro do WorldCover para a pasta `WorldCover` das fontes | OpenStreetMap, ESA WorldCover 2021 (Agência Espacial Europeia) |
| `preparar_educacao.py` | `componentes/comp_316.csv` (infraestrutura das escolas), `comp_317.csv` (escolas e matrículas por localização) e `comp_318.csv` (creches e pré-escolas, com as crianças do Censo 2022) e o painel "Educação" em `usuarios/admin_painel.json`; baixa os microdados para a pasta `INEP` das fontes | INEP, Censo Escolar; IBGE, Censo 2022 (tabela 9514) |
| `preparar_saude.py` | `componentes/comp_319.csv` (leitos por especialidade), `comp_320.csv` (nascimentos por local do parto) e `comp_321.csv` (consultas de pré-natal) e o painel "Saúde" em `usuarios/admin_painel.json` | DATASUS (CNES e SINASC) |
| `preparar_criancas_bairro.py` | `componentes/comp_322.csv` e `comp_322_mapa.csv` (crianças de 0 a 4 anos por bairro, no painel "Educação"); usa as funções e os arquivos do IBGE do `preparar_dados.py` | IBGE, Censo 2022 e CNEFE |
| `preparar_lixo.py` | `componentes/comp_323.csv` e `comp_323_historico.csv` (destino do lixo das casas, 2000/2010/2022), `comp_324.csv` e `comp_324_mapa.csv` (coleta de lixo por bairro) e o painel "Servindo ao povo" em `usuarios/admin_painel.json`; precisa dos arquivos `caracteristicas_domicilio1` e `domicilio2` dos setores na pasta das fontes | IBGE (SIDRA, Censo 2022 por setores) e CNEFE |
| `preparar_dengue.py` | `componentes/comp_325.csv` (casos de dengue das últimas 26 semanas, na cor do nível de alerta) e `comp_325_historico.csv` (dengue, chikungunya e zika por ano), no painel "Saúde"; também no botão "Atualizar" da administração (semanal) | InfoDengue (Fiocruz e FGV) |
| `preparar_criminalidade.py` | `componentes/comp_326.csv` (vítimas de homicídio e de tentativa de homicídio e mandados de prisão cumpridos por ano, no painel "Servindo ao povo"); baixa as planilhas `bancovde-ANO.xlsx` para `PASTA_FONTES/SINESP` (o ano atual de novo a cada vez); também no botão "Atualizar" da administração (mensal) | Ministério da Justiça, Sinesp VDE |
| `preparar_pronaf.py` | `componentes/comp_327.csv` (crédito do Pronaf em Oriximiná por ano e linha, em mil reais, no painel "Servindo ao povo"); também no botão "Atualizar" da administração (mensal) | Banco Central, Matriz de Dados do Crédito Rural (API Olinda) |
| `preparar_emissoes.py` | `componentes/comp_328.csv` e `comp_328_historico.csv` (emissões de gases de efeito estufa por setor) e o painel "Mudança climática" em `usuarios/admin_painel.json`; precisa da planilha "Dados municipais resumido" do SEEG em `PASTA_FONTES/SEEG/seeg_municipios_13.xlsx` (baixe à mão: o site recusa downloads automáticos) | Observatório do Clima, SEEG 13.0 |
| `preparar_entorno.py` | `componentes/comp_329.csv` (moradores das áreas urbanas por característica da rua: árvores, pavimento, calçada, bueiro, iluminação, rampa, ponto de ônibus e ciclovia), no painel "Mudança climática" | IBGE, Censo 2022 (Pesquisa Urbanística do Entorno, SIDRA 6752) |
| `preparar_ar.py` | `componentes/comp_330.csv` (fumaça e poeira fina no ar, PM2.5, média dos últimos 36 meses, com a época das queimadas à parte), no painel "Mudança climática"; também no botão "Atualizar" da administração | Copernicus CAMS, pela API do Open-Meteo |
| `preparar_rio.py` | `componentes/comp_331.csv` (nível do rio Trombetas nos últimos 13 meses e o normal de cada mês) e `comp_331_historico.csv` (maior cheia e menor seca de cada ano) e o painel "Uma cidade resistente a desastres" em `usuarios/admin_painel.json`; também no botão "Atualizar" da administração | ANA, estação 16900000 (régua desde 1968 e telemetria) |
| `preparar_risco.py` | `componentes/comp_332.csv` (setores, casas e pessoas em risco por tipo) e `comp_332_mapa.csv` (um ponto por setor de risco), no painel "Uma cidade resistente a desastres"; precisa dos arquivos SIG dos estudos do SGB de 2012 e 2023 em `PASTA_FONTES/SGB_risco` | Serviço Geológico do Brasil (SGB/CPRM) |
| `preparar_assistencia.py` | `componentes/comp_333.csv` (idosos nos grupos do PAIF de cada CRAS) e `comp_333_mapa.csv` (onde fica cada CRAS), no painel "Cuidados de longo prazo"; precisa dos arquivos do Censo SUAS 2025 (1.zip, 4.zip e 6.zip) em `PASTA_FONTES/CensoSUAS2025` | MDS, Censo SUAS 2025 |
| `preparar_mortalidade.py` | `componentes/comp_334.csv` (mortes por causa a cada 100 mil habitantes, por ano), no painel "Saúde"; também no botão "Atualizar" da administração | DATASUS (SIM) e IBGE (população) |
| `preparar_vacinacao.py` | `componentes/comp_335.csv` (cobertura vacinal das crianças por vacina, 2013 a 2022), no painel "Saúde" | Ministério da Saúde, SI-PNI (TabNet do DATASUS) |
| `preparar_aviao.py` | `componentes/comp_336.csv` (passageiros que embarcaram e desembarcaram de avião em Oriximiná por ano), no painel "Tráfego rodoviário"; baixa o arquivo da ANAC (360 MB) para `PASTA_FONTES/ANAC` quando o da pasta tem mais de 25 dias; também no botão "Atualizar" da administração | ANAC, Dados Estatísticos do Transporte Aéreo |
| `preparar_merenda.py` | `componentes/comp_337.csv` (dinheiro do FNDE para a merenda por ano e tipo de aluno) e o painel "Segurança e saúde alimentar" em `usuarios/admin_painel.json`; também no botão "Atualizar" da administração | FNDE, liberações do PNAE |
| `preparar_industria_alimentos.py` | `componentes/comp_338.csv` (fábricas de alimentos e bebidas com empregados, por ano e tipo) e `comp_338_historico.csv` (empregados com carteira), no painel "Segurança e saúde alimentar"; precisa dos arquivos `RAIS_ESTAB_PUB.7z` de cada ano em `PASTA_FONTES/RAIS_ESTAB` (fora da pasta `RAIS`, que o `preparar_rais.py` lê inteira) | Ministério do Trabalho, RAIS (estabelecimentos) |
| `preparar_qualidade_agua.py` | `componentes/comp_339.csv` (há quantos anos cada estação mede a qualidade da água) e `comp_339_mapa.csv` (onde fica cada estação) e o painel "Meio ambiente sustentável" em `usuarios/admin_painel.json` | ANA, inventário de estações (HidroInventario) |
| `preparar_chuva.py` | `componentes/comp_340.csv` (chuva dos últimos 13 meses na sede e o normal de cada mês), `comp_340_historico.csv` (chuva de cada ano) e `comp_340_mapa.csv` (estações de chuva da ANA), no painel "Meio ambiente sustentável"; também no botão "Atualizar" da administração | ANA, estação 00155000 (régua desde 1968) e pluviômetro automático da 16900000 |
| `preparar_queimadas.py` | `componentes/comp_341.csv` (focos de queimada dos últimos 13 meses e a média de cada mês), `comp_341_historico.csv` (focos de cada ano) e `comp_341_mapa.csv` (focos dos últimos 12 meses), no painel "Mudança climática"; guarda os focos de Oriximiná em `PASTA_FONTES/INPE_queimadas`; também no botão "Atualizar" da administração | INPE, Programa Queimadas (satélite de referência) |
| `preparar_saude_familia.py` | `componentes/comp_342.csv` (equipes de Saúde da Família, saúde bucal, agentes comunitários e saúde indígena por ano), no painel "Saúde"; também no botão "Atualizar" da administração | DATASUS (CNES, equipes) e IBGE (população) |
| `preparar_estabelecimentos_saude.py` | `componentes/comp_343.csv` (estabelecimentos de saúde de cada tipo agora, com as farmácias e drogarias da RAIS) e `comp_343_historico.csv` (cada tipo ano a ano), no painel "Saúde"; usa os arquivos da RAIS guardados pelo `preparar_industria_alimentos.py`; também no botão "Atualizar" da administração | DATASUS (CNES) e Ministério do Trabalho (RAIS) |
| `preparar_hospedagem.py` | `componentes/comp_344.csv` (hotéis e pousadas e outros alojamentos por ano, da RAIS) e o painel "Revitalizando o distrito comercial" em `usuarios/admin_painel.json`; baixa o arquivo mais recente do Cadastur para `PASTA_FONTES/Cadastur` e usa os arquivos da RAIS guardados pelo `preparar_industria_alimentos.py`; também no botão "Atualizar" da administração | Ministério do Trabalho (RAIS) e Ministério do Turismo (Cadastur) |
| `preparar_organicos.py` | `componentes/comp_345.csv` e `comp_345_mapa.csv` (produtores orgânicos certificados nos municípios da Calha Norte), no painel "Segurança e saúde alimentar"; baixa a planilha mais nova do CNPO para `PASTA_FONTES/CNPO` e junta os nomes de cidade digitados errado ("ORIXIMA"); também no botão "Atualizar" da administração | Ministério da Agricultura, Cadastro Nacional de Produtores Orgânicos |
| `preparar_comercio_alimentos.py` | `componentes/comp_346.csv` (lojas de alimentos por tipo e ano), no painel "Segurança e saúde alimentar"; usa os arquivos da RAIS guardados pelo `preparar_industria_alimentos.py`; também no botão "Atualizar" da administração | Ministério do Trabalho, RAIS (estabelecimentos) |
| `preparar_obras.py` | `componentes/comp_305.csv` (obras com recursos federais, no painel "Tráfego rodoviário"); leva uns 10 minutos | Obrasgov.br (Governo Federal) |
| `preparar_cartografia_regiao.py` | `regiao_estradas.geojson`, `regiao_sedes.csv` | OpenStreetMap |
| `preparar_predios.py` | `predios_oriximina.geojson` | OpenStreetMap (contornos) e GHSL, Comissão Europeia (altura) |

Também dá para rodar os scripts pelo próprio painel: entre com uma conta de administrador e abra
**Painel de administração > Atualização dos dados**. A página mostra a fonte, a frequência e a data dos
arquivos de cada dado, e o botão **Atualizar** roda o script. Antes, uma cópia dos arquivos atuais vai para
`backups/dados_antes_<script>_<data>/`; se o script der erro, os arquivos de antes voltam. O histórico fica
em `usuarios/atualizacoes_painel.json`.

Os arquivos grandes baixados das fontes (Censo, CNEFE, RAIS, SENATRAN) ficam em
`Downloads\Pasta Mapa de Painel Oriximiná`, fora deste projeto.
