import streamlit as st
import pandas as pd
import requests
import urllib3
import os
import plotly.express as px
from datetime import datetime
import pytz

# 1. Configurações Globais e de Imagem Local
# Ignora avisos de segurança SSL para redes restritas
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Define o nome do arquivo de logo local
# CERTIFIQUE-SE DE QUE ESTE ARQUIVO EXISTE NA PASTA DO PROJETO!
LOGOPATH = "f1_logo.png"

# Configuração da Página: O ícone na aba do navegador ainda pode ser a URL, 
# mas se falhar lá, não quebra o dashboard principal.
st.set_page_config(
    page_title="Dashboard F1 2026", 
    page_icon="https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Formula_1_logo.svg/320px-Formula_1_logo.svg.png",
    layout="wide"
)

# 2. Função de Busca de Dados
@st.cache_data(ttl=3600)
def fetch_data(endpoint):
    if endpoint == "schedule":
        # A rota para o calendário anual usa apenas o ano na URL base
        url = "https://api.jolpi.ca/ergast/f1/2026.json"
    else:
        url = f"https://api.jolpi.ca/ergast/f1/2026/{endpoint}.json"
        
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        return None
    return None

# --- INTERFACE DO USUÁRIO ---

# TÍTULO DA PÁGINA: Carregando o logo localmente para evitar o erro de rede
col_logo, col_titulo = st.columns([1, 9])
with col_logo:
    # Verifica se o arquivo local existe antes de tentar carregar
    if os.path.exists(LOGOPATH):
        st.image(LOGOPATH, width=120)
    else:
        # Mostra um aviso discreto se o arquivo não for encontrado
        st.warning("Logo não encontrado.")
with col_titulo:
    st.title("Dashboard F1 2026")

# --- BLOCO 1: PONTUAÇÕES (PILOTOS E EQUIPES) ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 Classificação de Pilotos")
    data_drivers = fetch_data("driverStandings")
    try:
        standings = data_drivers['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']
        df_drivers = pd.DataFrame([{
            "Pos": d['position'],
            "Piloto": f"{d['Driver']['givenName']} {d['Driver']['familyName']}",
            "Equipe": d['Constructors'][0]['name'],
            "Pontos": d['points']
        } for d in standings])
        # Usamos st.dataframe para uma tabela nítida e com rolagem
        st.dataframe(df_drivers, use_container_width=True, hide_index=True)
    except (TypeError, KeyError, IndexError):
        st.info("Classificação de pilotos ainda não disponível para a temporada 2026.")

with col2:
    st.subheader("🏗️ Classificação de Equipes")
    data_constructors = fetch_data("constructorStandings")
    try:
        standings = data_constructors['MRData']['StandingsTable']['StandingsLists'][0]['ConstructorStandings']
        df_const = pd.DataFrame([
            {
                "Pos": c['position'],
                "Equipe": c['Constructor']['name'], 
                "Pontos": c['points']
            } for c in standings
        ])
        st.dataframe(df_const, use_container_width=True, hide_index=True)
    except (TypeError, KeyError, IndexError):
        st.info("Classificação de equipes ainda não disponível para a temporada 2026.")

# Adiciona uma linha divisória visual
st.markdown("---")


# --- BLOCO 2: MAPA MÚNDI COM CORES POR STATUS (PASSADA, PRÓXIMA, FUTURA) ---
st.subheader("🗺️ Circuito Mundial F1 2026 (Calendário Interativo)")

with st.spinner('Carregando mapa das etapas...'):
    data_cal = fetch_data("schedule")

if data_cal and 'RaceTable' in data_cal['MRData']:
    try:
        races = data_cal['MRData']['RaceTable']['Races']
        
        # Pega a data e hora atual no fuso de Brasília
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso_br)
        
        map_data = []
        proximo_gp = None
        menor_diferenca = float('inf')
        
        # 1. Primeiro passo: Processar horários e descobrir qual é a PRÓXIMA corrida
        for r in races:
            race_time = r.get('time', '00:00:00Z')
            datetime_utc = pd.to_datetime(r['date'] + ' ' + race_time.replace('Z', ''))
            horario_brasilia = datetime_utc.tz_localize('UTC').tz_convert('America/Sao_Paulo')
            
            if horario_brasilia > agora:
                diferenca = (horario_brasilia - agora).total_seconds()
                if diferenca < menor_diferenca:
                    menor_diferenca = diferenca
                    proximo_gp = r['raceName']

        # 2. Segundo passo: Classificar cada corrida com base no momento atual e no Próximo GP
        for r in races:
            race_time = r.get('time', '00:00:00Z')
            datetime_utc = pd.to_datetime(r['date'] + ' ' + race_time.replace('Z', ''))
            horario_brasilia = datetime_utc.tz_localize('UTC').tz_convert('America/Sao_Paulo')
            data_formatada = horario_brasilia.strftime('%d/%m/%Y %H:%M')
            
            # Define o Status de cada uma
            if r['raceName'] == proximo_gp:
                status = "PRÓXIMO GP"
            elif horario_brasilia < agora:
                status = "Corrida Realizada"
            else:
                status = "Futura"
                
            circuit = r['Circuit']
            location = circuit['Location']
            
            map_data.append({
                "Etapa": f"R{r['round']}",
                "Grande Prêmio": r['raceName'],
                "Circuito": circuit['circuitName'],
                "Local": f"{location['locality']}, {location['country']}",
                "Data/Hora (BR)": data_formatada,
                "lat": float(location['lat']),
                "lon": float(location['long']),
                "Status": status
            })
            
        df_map = pd.DataFrame(map_data)
        
        # Define os tamanhos associados diretamente a cada status na tabela
        # Próxima = 18 (Grande), Passadas e Futuras = 10 (Normal)
        df_map["Tamanho_Marcador"] = df_map['Status'].map({
            "Corrida Realizada": 10, 
            "PRÓXIMO GP": 18, 
            "Futura": 10
        })
        
        # 3. Exibe o Card de Destaque para a próxima corrida
        if proximo_gp:
            dados_proximo = df_map[df_map['Status'] == 'PRÓXIMO GP'].iloc[0]
            st.markdown(
                f"""
                <div style="background-color: #1F242E; padding: 15px; border-radius: 10px; border-left: 5px solid #00E676; margin-bottom: 20px;">
                    <span style="color: #00E676; font-weight: bold; text-transform: uppercase;">🏎️ PRÓXIMA ETAPA DA TEMPORADA:</span>
                    <h3 style="margin: 5px 0; color: #FAFAFA;">{dados_proximo['Grande Prêmio']} ({dados_proximo['Etapa']})</h3>
                    <p style="margin: 0; color: #B3B3B3;">📍 <b>Circuito:</b> {dados_proximo['Circuito']} — {dados_proximo['Local']}</p>
                    <p style="margin: 0; color: #FAFAFA;">📅 <b>Data/Hora (Brasília):</b> {dados_proximo['Data/Hora (BR)']}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        # 4. Criando o mapa com o mapeamento exato de cores solicitado
        fig = px.scatter_mapbox(
            df_map,
            lat="lat",
            lon="lon",
            color="Status",
            color_discrete_map={
                "Corrida Realizada": "#757575",  # Cinza discreto
                "PRÓXIMO GP": "#00E676",         # Verde Neon chamativo
                "Futura": "#FF4B4B"              # Vermelho F1
            },
            size="Tamanho_Marcador",
            size_max=18,
            hover_name="Grande Prêmio",
            hover_data={
                "Etapa": True,
                "Circuito": True,
                "Local": True,
                "Data/Hora (BR)": True,
                "Status": True,
                "Tamanho_Marcador": False,
                "lat": False,
                "lon": False
            },
            zoom=1,
            height=500
        )
        
        # Estilizando o mapa Black
        fig.update_layout(
            mapbox_style="carto-darkmatter", 
            margin={"r":0,"t":0,"l":0,"b":0},
            paper_bgcolor="#0E1117", 
            plot_bgcolor="#0E1117",
            legend=dict(
                yanchor="top", 
                y=0.99, 
                xanchor="left", 
                x=0.01, 
                font=dict(color="#FAFAFA"),
                bgcolor="rgba(14, 17, 23, 0.6)" # Fundo semi-transparente para a legenda
            )
        )
        
        st.plotly_chart(fig, width="stretch")
        
    except Exception as e:
        st.error(f"Erro ao gerar o mapa com destaque: {e}")
else:
    st.error("Não foi possível renderizar o mapa. Verifique os dados da API.")
