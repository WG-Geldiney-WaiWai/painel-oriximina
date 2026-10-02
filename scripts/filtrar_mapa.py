import geopandas as gpd
import os

# Os arquivos lidos e gerados ficam na pasta "dados" do painel, qualquer que seja
# a pasta de onde o script for rodado
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))

# Descobre automaticamente o arquivo .shp que está em dados/fontes
arquivos_shp = [os.path.join('fontes', f) for f in os.listdir('fontes') if f.endswith('.shp')]

if not arquivos_shp:
    print("Erro: Nenhum arquivo .shp foi encontrado nesta pasta!")
    print("Coloque os arquivos extraídos do IBGE (.shp, .dbf, .shx...) na pasta dados/fontes.")
else:
    caminho_shapefile = arquivos_shp[0]
    print(f"Lendo o arquivo: {caminho_shapefile}...")
    
    # 1. Carrega os dados do mapa completo do estado
    dados_mapa = gpd.read_file(caminho_shapefile)
    
    # 2. Filtra pelo código oficial de Oriximiná (1505304)
    colunas = dados_mapa.columns
    print(f"Colunas encontradas no arquivo: {list(colunas)}")
    
    oriximina_mapa = None
    
    # Tentativa 1: Código numérico/texto do município
    for col in ['CD_MUN', 'code_muni', 'CD_MUNICIPIO']:
        if col in colunas:
            oriximina_mapa = dados_mapa[dados_mapa[col].astype(str) == '1505304']
            break
            
    # Tentativa 2: Se não achar pelo código, busca pelo nome exato
    if oriximina_mapa is None or oriximina_mapa.empty:
        for col in ['NM_MUN', 'NM_MUNICIPIO', 'name_muni']:
            if col in colunas:
                oriximina_mapa = dados_mapa[dados_mapa[col].str.upper() == 'ORIXIMINÁ']
                break

    # 3. Salva se encontrar os dados
    if oriximina_mapa is not None and not oriximina_mapa.empty:
        oriximina_mapa.to_file("oriximina_setores.geojson", driver="GeoJSON")
        print("\n--- SUCESSO! ---")
        print("O arquivo 'oriximina_setores.geojson' foi gerado com sucesso!")
    else:
        print("\nErro: Não conseguimos isolar a cidade de Oriximiná automaticamente.")
