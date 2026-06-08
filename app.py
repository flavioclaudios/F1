import streamlit as st
import pandas as pd
import requests
import urllib3
import os

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

# --- BLOCO 2: CALENDÁRIO ---
st.subheader("🗓️ Calendário Oficial de Corridas (Horário de Brasília)")

with st.spinner('Carregando cronograma das etapas...'):
    data_cal = fetch_data("schedule")

if data_cal and 'RaceTable' in data_cal['MRData']:
    try:
        races = data_cal['MRData']['RaceTable']['Races']
        df_cal = pd.DataFrame(races)
        
        # Tratamento: se alguma corrida futura estiver sem horário definido na API, preenche com meia-noite UTC
        df_cal['time'] = df_cal['time'].fillna('00:00:00Z')
        
        # Combina data e hora UTC removendo o caractere "Z"
        df_cal['datetime_utc'] = pd.to_datetime(df_cal['date'] + ' ' + df_cal['time'].str.replace('Z', '', regex=False))
        
        # Converte o fuso de UTC para o horário oficial de Brasília (America/Sao_Paulo)
        # O Pandas gerencia automaticamente o ajuste de UTC-3 ou UTC-2 (horário de verão), se houver
        df_cal['horario_brasilia'] = df_cal['datetime_utc'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')
        
        # Formata no padrão brasileiro (Dia/Mês/Ano Hora:Minuto) para exibição nítida
        df_cal['Data / Hora (Brasília)'] = df_cal['horario_brasilia'].dt.strftime('%d/%m/%Y %H:%M')
        
        # Seleciona e renomeia as colunas finais para exibição limpa
        df_display = df_cal[['round', 'raceName', 'Data / Hora (Brasília)']].copy()
        df_display.columns = ['Etapa', 'Grande Prêmio', 'Horário de Brasília (UTC-3)']
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao converter os horários do calendário: {e}")
else:
    st.error("Não foi possível renderizar o calendário. Verifique os dados da API.")