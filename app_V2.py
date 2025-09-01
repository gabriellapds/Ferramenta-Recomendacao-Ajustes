import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import traceback

# Define o código CSS para centralizar o conteúdo das células da tabela
css_para_centralizar = """
<style>
    /* Alvo: Todas as células de dados na grade do DataFrame */
    [data-testid="stDataFrameBlock"] [data-testid="stDataFrameCell"] {
        text-align: center;
        justify-content: center;
    }
    /* Alvo: Todos os cabeçalhos de coluna na grade do DataFrame */
    [data-testid="stDataFrameBlock"] [data-testid="stColumnHeader"] {
        text-align: center;
        justify-content: center;
    }
</style>
"""

# Injeta o código CSS na aplicação
st.markdown(css_para_centralizar, unsafe_allow_html=True)

# --- CONFIGURAÇÕES DA PÁGINA E TÍTULO ---
st.set_page_config(page_title="Recomendador de Ajustes", layout="wide")
st.title("Ferramenta de Recomendação de Ajustes")
st.markdown("Insira as características do cenário para obter um ranking de ajustes recomendados.")

COLUNA_ID_AJUSTE = 'Ajustes' # Coluna com os números 2, 5, 32...
HEADER_ROCOF = 'DF_th'
HEADER_TEMPO = 'TD'
HEADER_TENSAO_BLOQUEIO = 'Vblock'
HEADER_DROPOUT = 'tdropout'


@st.cache_data
def load_parameter_database_from(file_path):
    try:
        df = pd.read_excel(file_path)
        df[COLUNA_ID_AJUSTE] = df[COLUNA_ID_AJUSTE].astype(str).str.replace('#', '').str.strip()
        df[COLUNA_ID_AJUSTE] = pd.to_numeric(df[COLUNA_ID_AJUSTE], errors='coerce')
        df.dropna(subset=[COLUNA_ID_AJUSTE], inplace=True)
        df[COLUNA_ID_AJUSTE] = df[COLUNA_ID_AJUSTE].astype(int)
        return df.set_index(COLUNA_ID_AJUSTE)
    except Exception as e:
        st.error(f"Erro ao carregar parâmetros: {e}")
        return None

@st.cache_data
def load_simulation_database_from(x_file, y_file, sheet='X_total'):
    try:
        x_total_sim = pd.read_excel(x_file, sheet_name=sheet)
        y_total_sim = pd.read_excel(y_file)
        return x_total_sim, y_total_sim
    except Exception as e:
        st.error(f"Erro ao carregar base de simulação: {e}")
        return None, None




# --- MAPEAMENTO DE CATEGORIAS PARA CÓDIGOS NUMÉRICOS ---
# !!! VERIFIQUE E AJUSTE ESTES CÓDIGOS DE ACORDO COM SEUS DADOS DE TREINO !!!
tipo_gd_map = {'Gerador Síncrono': 0, 'Gerador Baseado em Inversor': 1}
bloqueio_tensao_map = {'Habilitado': 1, 'Desabilitado': 0}
req_suportabilidade_map = {'Sem Requisitos': 4, 'Categoria I': 1, 'Categoria II': 2, 'Categoria III': 3}
tecnica_ativa_map = {'Desabilitada': 3, 'GEFS': 1, 'GEVS': 2, 'Desconhecido': 4}
cenario_geracao_map = {'Apenas Gerador Síncrono': 1, 'Apenas Gerador Baseado em Inversores': 2, 'Cenário Híbrido (Maior contribuição de GS)': 3, 'Cenário Híbrido (Maior contribuição de GBI)': 4, 'Desconhecido': 5}
curvas_regulacao_map = {'Desabilitada': 1, 'hertz-watt': 2, 'volt-var': 3, 'volt-watt': 4, 'Desconhecido': 5}


# NOVO: Mapeamentos Inversos de Código para Texto (para a saída)
tipo_gd_map_inv = {v: k for k, v in tipo_gd_map.items()}
bloqueio_tensao_map_inv = {v: k for k, v in bloqueio_tensao_map.items()}
req_suportabilidade_map_inv = {v: k for k, v in req_suportabilidade_map.items()}
tecnica_ativa_map_inv = {v: k for k, v in tecnica_ativa_map.items()}
cenario_geracao_map_inv = {v: k for k, v in cenario_geracao_map.items()}
curvas_regulacao_map_inv = {v: k for k, v in curvas_regulacao_map.items()}

# --- INTERFACE DE ENTRADA NA BARRA LATERAL ---
st.sidebar.header("Parâmetros do Cenário")

# Coletando as entradas do usuário
f1_capacidade = st.sidebar.number_input('1. Capacidade da GD (kW)', min_value=0.0, value=0.0, step=50.0, format="%.2f")
f2_tensao = st.sidebar.number_input('2. Tensão do Sistema (kV)', min_value=0.0, value=0.0, step=0.1, format="%.2f")
#f3_inercia = st.sidebar.number_input('3. Constante de Inércia (s)', min_value=0.0, value=100.0, step=0.0001, format="%.4f")
f2_texto = st.sidebar.selectbox('2. Tipo da GD', options=list(tipo_gd_map.keys()))
f3_texto = st.sidebar.selectbox('3. Bloqueio de Tensão', options=list(bloqueio_tensao_map.keys()))
f4_texto = st.sidebar.selectbox('4. Requisito de Suportabilidade', options=list(req_suportabilidade_map.keys()))
f5_texto = st.sidebar.selectbox('5. Técnica Ativa', options=list(tecnica_ativa_map.keys()))
f6_texto = st.sidebar.selectbox('6. Curvas de Regulação', options=list(curvas_regulacao_map.keys()))
f7_texto = st.sidebar.selectbox('7. Cenário de Geração', options=list(cenario_geracao_map.keys()))


# 3. Campo de Inércia aparece somente para GS + opção "Inércia desconhecida"
f3_inercia = None
inercia_desconhecida = False

if f2_texto == 'Gerador Síncrono':
    #st.sidebar.markdown("**Constante de Inércia (H)**")
    inercia_desconhecida = st.sidebar.checkbox("Inércia desconhecida", value=False)
    if not inercia_desconhecida:
        f3_inercia = st.sidebar.number_input('Constante de Inércia (H)', min_value=0.0, value=0.0, step=0.01, format="%.4f")
    else:
        f3_inercia = 100  # irá sinalizar para ignorar o critério de H nas buscas
else:
    f3_inercia = 0

model = True

# --- LÓGICA DE PREDIÇÃO ---
if model is not None:
    if st.sidebar.button("Obter Recomendações"):
        
        # --- INÍCIO DA NOVA CAMADA DE VALIDAÇÃO ---
        
        inconsistencia_encontrada = False
        #st.subheader("Validação das Entradas")

        # Regra 1: Cenário apenas com Gerador Síncrono (GS)
        if f7_texto == 'Apenas Gerador Síncrono':
            # Checa se o Tipo da GD é compatível
            if f2_texto != 'Gerador Síncrono':
                st.error(
                    f"**Inconsistência:** Você selecionou o cenário **'{f7_texto}'**, mas o Tipo da GD é **'{f2_texto}'**.\n\n  "
                    "Para este cenário, o Tipo da GD deve ser 'Gerador Síncrono'.",
                    icon="🚨"
                )
                inconsistencia_encontrada = True
            
            # Checa se a Técnica Ativa é compatível (não pode ter técnica ativa)
            if f5_texto != 'Desabilitada':
                st.error(
                    f"**Inconsistência:** Você selecionou o cenário **'{f7_texto}'**, que não foi avaliado com técnicas ativas.\n\n "
                    f"Por favor, mude a 'Técnica Ativa' para 'Desabilitada'.",
                    icon="🚨"
                )
                inconsistencia_encontrada = True

        # Regra 2: Cenário apenas com Gerador Baseado em Inversor (GBI)
        elif f7_texto == 'Apenas Gerador Baseado em Inversores':
            # Checa se o Tipo da GD é compatível
            if f2_texto != 'Gerador Baseado em Inversor':
                st.error(
                    f"**Inconsistência:** Você selecionou o cenário **'{f7_texto}'**, mas o Tipo da GD é **'{f2_texto}'**.\n\n  "
                    "Para este cenário, o Tipo da GD deve ser 'Gerador Baseado em Inversor'.",
                    icon="🚨"
                )
                inconsistencia_encontrada = True
        
        # Adicione outras regras aqui se necessário. Ex:
        # elif f6_texto == 'Cenário Híbrido...':
        #    ... (verificações para cenários híbridos)

        # Se qualquer inconsistência foi encontrada, exibe uma mensagem final e PARA a execução
        if inconsistencia_encontrada:
            st.warning("Por favor, corrija as inconsistências apontadas acima antes de continuar.")
            st.stop() # Este comando interrompe o resto do script
            
        # Se não houver inconsistências, o programa continua normalmente
        #st.success("Processando recomendação...", icon="⏳")
        # --- FIM DA CAMADA DE VALIDAÇÃO ---
        
        # --- TRADUÇÃO E MONTAGEM DO VETOR DE FEATURES ---
        
        # Traduz as escolhas textuais para códigos numéricos
        f2_codigo = tipo_gd_map[f2_texto]
        f3_codigo = bloqueio_tensao_map[f3_texto]
        f4_codigo = req_suportabilidade_map[f4_texto]
        f5_codigo = tecnica_ativa_map[f5_texto]
        f6_codigo = curvas_regulacao_map[f6_texto]
        f7_codigo = cenario_geracao_map[f7_texto]
        
        
        # Define os arquivos de cada sistema
        arquivos_AT = {
            "params": 'results_AT_DT.xlsx',
            "x": 'X_dados_AT.xlsx',
            "y": 'Metricas_Y_AT.xlsx'
            }
        arquivos_MT = {
            "params": 'results_MT_DT.xlsx',
            "x": 'X_dados_MT.xlsx',
            "y": 'Metricas_Y_MT.xlsx'  
            }

        # Seleção de base baseada na tensão do sistema
        if f2_tensao >= 69.0:
            st.info("Usando base de **Alta Tensão (AT)** para recomendações.", icon="⚡")
            df_params = load_parameter_database_from(arquivos_AT["params"])
            X_total_sim, Y_total_sim = load_simulation_database_from(arquivos_AT["x"], arquivos_AT["y"])
            sistema_base = "AT"
            
            ajustes_candidatos = np.array([1, 4, 27, 38, 40, 46, 60, 66, 75, 85])

            ajuste_id_para_label_map = {
                1: 'A_F1',
                38: 'AVB_F1',
                4: 'A_F2',
                40: 'AVB_F2',
                27: 'A_F3',
                66: 'AVB_F3',
                60: 'A_F4',
                46: 'AVB_F4',
                75: 'A_F5',
                85: 'AVB_F5'
            }


            # NOVO: Definindo os conjuntos de regras de especialista para o filtro
            aj_vb = {38, 40, 66, 46, 85}
            aj_svb = {1, 4, 27, 60, 75}
            aj_rs1 = {4, 27, 60, 75, 40, 46, 66, 85}
            aj_rs2 = {27, 60, 75, 46, 66, 85}
            aj_rs3 = {60, 75, 46, 85}
            aj_rs4 = set(ajustes_candidatos) # Sem requisitos = todos são permitidos inicialmente
        else:
            st.info("Usando base de **Média Tensão (MT)** para recomendações.", icon="⚡")
            df_params = load_parameter_database_from(arquivos_MT["params"])
            X_total_sim, Y_total_sim = load_simulation_database_from(arquivos_MT["x"], arquivos_MT["y"])
            sistema_base = "MT"
            
            ajustes_candidatos = np.array([1, 17, 25, 31, 37, 40, 45, 46])

            ajuste_id_para_label_map = {
                1: 'M_F1',
                37: 'MVB_F1',
                25: 'M_F2',
                40: 'MVB_F2',
                31: 'M_F3',
                45: 'MVB_F3',
                17: 'M_F4',
                46: 'MVB_F4',
            }


            # NOVO: Definindo os conjuntos de regras de especialista para o filtro
            aj_vb = {37, 40, 45, 46}
            aj_svb = {1, 25, 31, 17}
            aj_rs1 = {25, 31, 17, 40, 45, 46}
            aj_rs2 = {31, 17, 45, 46}
            aj_rs3 = {17, 46}
            aj_rs4 = set(ajustes_candidatos) # Sem requisitos = todos são permitidos inicialmente

        # Verificações de sanidade
        if df_params is None or X_total_sim is None or Y_total_sim is None:
            st.error("Não foi possível carregar a base selecionada. Verifique os arquivos de dados.")
            st.stop()

        
        # --- EXIBIÇÃO DOS RESULTADOS NA PÁGINA PRINCIPAL ---
        st.subheader("Resultados da Análise")
        
        # --- LÓGICA DE BUSCA PELO CENÁRIO MAIS PRÓXIMO ---
        try:
            # 1. Pega os códigos numéricos das seleções do usuário
            user_categorical_inputs = [f2_codigo, f3_codigo, f4_codigo, f5_codigo, f6_codigo, f7_codigo]
            
            
            feature_cols = X_total_sim.columns[4:10]
            
            fallback_por_coluna = {
                feature_cols[3]: 4,  # TecAt -> valor "desconhecido" na sua base
                feature_cols[4]: 5,  # CR -> se desejar algum agrupamento alternativo, pode ajustar aqui
                feature_cols[5]: 5,  # Cgd -> valor "desconhecido"
                }
            
            df_candidatos = X_total_sim.copy()
            for i, col in enumerate(feature_cols):
                valor_usuario = user_categorical_inputs[i]

                # Tente filtro exato
                mask_exato = (df_candidatos[col] == valor_usuario)
                df_filtrado = df_candidatos[mask_exato]

                if not df_filtrado.empty:
                    df_candidatos = df_filtrado
                else:
                    # Se esta coluna faz parte das que têm fallback, tenta "desconhecido"
                    if col in fallback_por_coluna:
                        valor_fallback = fallback_por_coluna[col]
                        mask_fallback = (df_candidatos[col] == valor_fallback)
                        df_filtrado_fb = df_candidatos[mask_fallback]
                        if not df_filtrado_fb.empty:
                            df_candidatos = df_filtrado_fb
                        else:
                            # Não encontrou match nem com fallback — mantemos df_candidatos como estava
                            pass
                    else:
                        # Coluna sem fallback — não reduzimos adicionalmente
                        pass

            if df_candidatos.empty:
                st.warning("Nenhum cenário compatível foi encontrado com os filtros fornecidos.", icon="⚠️")
            else:
                # 3. Dentro dos compatíveis, encontra o mais próximo em Capacidade da GD
                # Converte a capacidade da base de dados de W para kW
                #cenarios_compativeis.iloc[:, 1] = pd.to_numeric(cenarios_compativeis.iloc[:, 1], errors='coerce')
                capacidade_db_kw = df_candidatos.iloc[:, 1] / 1000.0
                vn_db_kv = df_candidatos.iloc[:, 2] / 1000.0
                h_db = df_candidatos.iloc[:, 3]
                df_tmp = df_candidatos.copy()
                df_tmp = df_tmp.copy()
                
                # Calcula a diferença absoluta e encontra o índice do menor valor
                diff_cap = abs(capacidade_db_kw - f1_capacidade)
                min_diff_cap = diff_cap.min()
                mask_cap = (diff_cap == min_diff_cap)
                df_tmp = df_tmp[mask_cap]
                
                if df_tmp.shape[0] > 1:
                    diff_vn = abs(vn_db_kv - f2_tensao)
                    min_diff_vn = diff_vn.min()
                    mask_vn = (diff_vn == min_diff_vn)
                    df_tmp = df_tmp[mask_vn]
                    
                if df_tmp.shape[0] > 1:
                    # Diferença absoluta para referência
                    diff_h_abs = abs(h_db - f3_inercia)
                    min_diff_h = diff_h_abs.min()

                    # Se o melhor não for exatamente igual, tentamos aplicar a regra especial:
                    if not np.isclose(min_diff_h, 0.0, atol=1e-9):
                        # Diferença com sinal: queremos o menor H_db - H_target positivo (mais próximo acima)
                        diff_h_signed = h_db - f3_inercia
                        mask_maiores = diff_h_signed > 0

                        if mask_maiores.any():
                            # Seleciona o menor positivo (ou seja, o menor H acima do alvo)
                            menor_positivo = diff_h_signed[mask_maiores].min()
                            mask_h_especial = (diff_h_signed == menor_positivo)
                            df_tmp = df_tmp[mask_h_especial]

                        else:
                            # Se não houver maior, escolhe o(s) mais próximo(s) absoluto(s)
                            mask_h_normal = (diff_h_abs == min_diff_h)
                            df_tmp = df_tmp[mask_h_normal]
                    else:
                        # Existem valores iguais a H_target; mantém os exatos
                        mask_h_iguais = (diff_h_abs == 0)
                        df_tmp = df_tmp[mask_h_iguais]
                        
                if df_tmp.empty:
                    st.warning("Nenhum cenário compatível foi encontrado com os filtros fornecidos.", icon="⚠️")
                elif df_tmp.shape[0] == 1:
                
                    # 4. Busca os dados do cenário encontrado (X e Y)
                    idx_cenario_proximo = df_tmp.index[0]
                    dados_X_proximo = X_total_sim.loc[idx_cenario_proximo]
                    metricas_cenario_proximo = Y_total_sim.loc[idx_cenario_proximo]
                    nome_cenario_proximo = metricas_cenario_proximo['NomeCenario']

                
                    # Pega os valores numéricos do cenário encontrado
                    cap_w = dados_X_proximo.iloc[1]
                    v_sys = dados_X_proximo.iloc[2]
                    h_gd = dados_X_proximo.iloc[3]
                    tipo_gd_cod = dados_X_proximo.iloc[4]
                    bloqueio_cod = dados_X_proximo.iloc[5]
                    req_sup_cod = dados_X_proximo.iloc[6]
                    tec_ativa_cod = dados_X_proximo.iloc[7]
                    curva_reg_cod = dados_X_proximo.iloc[8]
                    cen_ger_cod = dados_X_proximo.iloc[9]
                    
                

                    st.markdown(f"**O cenário simulado mais próximo é:** `{dados_X_proximo['NomeCenario']}`")
                    # Exibe os parâmetros do cenário encontrado para validação
                    
                    if tipo_gd_cod == 0 and f3_inercia<100:
                        descricao = f"""
                        Este cenário representa a operação de um **{tipo_gd_map_inv.get(tipo_gd_cod, 'N/A')}** 
                        com capacidade de **{cap_w / 1000:.0f} kW**, tensão de **{v_sys/1000:.1f} kV** 
                        e constante de inércia de **{h_gd:.2f} s**.  
                        O bloqueio de tensão está **{bloqueio_tensao_map_inv.get(bloqueio_cod, 'N/A').lower()}** 
                        e o requisito de suportabilidade é **'{req_suportabilidade_map_inv.get(req_sup_cod, 'N/A')}'**.  
                        A técnica ativa utilizada é **'{tecnica_ativa_map_inv.get(tec_ativa_cod, 'N/A')}'**, 
                        em um cenário de **'{cenario_geracao_map_inv.get(cen_ger_cod, 'N/A').lower()}'** 
                        com a curva de regulação **'{curvas_regulacao_map_inv.get(curva_reg_cod, 'N/A').lower()}'**.
                        """
                    elif tipo_gd_cod == 0 and f3_inercia == 100:
                        descricao = f"""
                        Este cenário representa a operação de um **{tipo_gd_map_inv.get(tipo_gd_cod, 'N/A')}** 
                        com capacidade de **{cap_w / 1000:.0f} kW**, tensão de **{v_sys/1000:.1f} kV** 
                        e constante de inércia **Desconhecida**.  
                        O bloqueio de tensão está **{bloqueio_tensao_map_inv.get(bloqueio_cod, 'N/A').lower()}** 
                        e o requisito de suportabilidade é **'{req_suportabilidade_map_inv.get(req_sup_cod, 'N/A')}'**.  
                        A técnica ativa utilizada é **'{tecnica_ativa_map_inv.get(tec_ativa_cod, 'N/A')}'**, 
                        em um cenário de **'{cenario_geracao_map_inv.get(cen_ger_cod, 'N/A').lower()}'** 
                        com a curva de regulação **'{curvas_regulacao_map_inv.get(curva_reg_cod, 'N/A').lower()}'**.
                        """
                    else:
                        descricao = f"""
                        Este cenário representa a operação de um **{tipo_gd_map_inv.get(tipo_gd_cod, 'N/A')}** 
                        com capacidade de **{cap_w / 1000:.0f} kW** e tensão de **{v_sys/1000:.1f} kV**.  
                        O bloqueio de tensão está **{bloqueio_tensao_map_inv.get(bloqueio_cod, 'N/A').lower()}** 
                        e o requisito de suportabilidade é **'{req_suportabilidade_map_inv.get(req_sup_cod, 'N/A')}'**.  
                        A técnica ativa utilizada é **'{tecnica_ativa_map_inv.get(tec_ativa_cod, 'N/A')}'**, 
                        em um cenário de **'{cenario_geracao_map_inv.get(cen_ger_cod, 'N/A').lower()}'** 
                        com a curva de regulação **'{curvas_regulacao_map_inv.get(curva_reg_cod, 'N/A').lower()}'**.
                        """

                    st.info(descricao, icon="ℹ️")
                
                    # ---  EXTRAIR E REORGANIZAR DADOS DO CENÁRIO ENCONTRADO ---
                    dados_candidatos = []
                    for ajuste_id in ajustes_candidatos:
                        dados_candidatos.append({
                            'Ajuste_ID': ajuste_id,
                            'Label': ajuste_id_para_label_map.get(ajuste_id, f"ID {ajuste_id}"),
                            'BAC': metricas_cenario_proximo[f'BAC_Ajuste_{ajuste_id}'],
                            'FNR': metricas_cenario_proximo[f'FNR_Ajuste_{ajuste_id}'],
                            'FPR': metricas_cenario_proximo[f'FPR_Ajuste_{ajuste_id}']
                            })
                        df_candidatos = pd.DataFrame(dados_candidatos)

                    # --- A MUDANÇA PRINCIPAL: JUNTAR COM A BASE DE PARÂMETROS ---
                    df_candidatos_completo = pd.merge(
                        df_candidatos, 
                        df_params, 
                        left_on='Ajuste_ID', 
                        right_index=True,
                        how='left'
                        )

                    # --- APLICAR FILTROS DE ESPECIALISTA ---
                
                    # Filtro Rígido 1 (Bloqueio de Tensão)
                    if f3_codigo == 1: # Habilitado
                        ajustes_permitidos_vb = aj_vb
                    else: # Desabilitado
                        ajustes_permitidos_vb = aj_svb

                    # Filtro Rígido 2 (Requisito de Suportabilidade)
                    if f4_codigo == 1: # Categoria I
                        ajustes_permitidos_rs = aj_rs1
                    elif f4_codigo == 2: # Categoria II
                        ajustes_permitidos_rs = aj_rs2
                    elif f4_codigo == 3: # Categoria III
                        ajustes_permitidos_rs = aj_rs3
                    else: # Sem Requisitos
                        ajustes_permitidos_rs = aj_rs4
                
                    # Combina os filtros rígidos
                    ajustes_elegiveis = ajustes_permitidos_vb.intersection(ajustes_permitidos_rs)
                    df_filtrado_regras = df_candidatos_completo[df_candidatos_completo['Ajuste_ID'].isin(ajustes_elegiveis)]

                    # Filtro de Desempenho (regras "soft")
                    df_filtrado_final = df_filtrado_regras[
                        (df_filtrado_regras['BAC'] > 90) &
                        (df_filtrado_regras['FNR'] < 10) &
                        (df_filtrado_regras['FPR'] < 10)
                        ]

                    # --- PARTE 4: SELECIONAR VENCEDOR E EXIBIR RESULTADOS ---
                    st.subheader("Recomendações Baseadas em Simulação Similar")

                    if df_filtrado_final.empty:
                        # 1. Mostra o aviso principal com um ícone
                        st.warning("Nenhum ajuste cumpriu todos os critérios de regras e desempenho para este cenário.", icon="⚠️")

                        # 2. Mostra um subcabeçalho para as sugestões
                        st.subheader("Sugestões para Encontrar um Ajuste Válido:")
                    
                        # 3. Lógica condicional baseada nas entradas do usuário
                    
                        # Sugestão para Gerador Síncrono
                        if f2_texto == 'Gerador Síncrono':
                            st.info(
                                "Tente **reduzir o nível do Requisito de Suportabilidade** (ex: de Categoria III para II).\n\n" 
                                "Geradores Síncronos podem ter dificuldade em atingir limiares mais relaxados.",
                                icon="💡"
                                )

                        # Sugestão para Gerador Baseado em Inversor
                        elif f2_texto == 'Gerador Baseado em Inversor' and f3_texto == 'Habilitado':
                            st.info(
                                "Tente **desabilitar o Bloqueio de Tensão**. Ajustes para Geradores Baseados em Inversores frequentemente operam melhor sem essa função.",
                                icon="💡"
                                )
                            # Adiciona um aviso extra se a combinação específica for selecionada
                            if f5_texto == 'GEVS' and f3_texto == 'Habilitado':
                                st.warning(
                                    "**Atenção:** A combinação da técnica **GEVS** com **Bloqueio de Tensão Habilitado** é particularmente restritiva e pode não ter ajustes válidos. Desabilitar o bloqueio é a principal recomendação.",
                                    icon="❗"
                                    )
                    else:
                        # Ordena pelo maior BAC para encontrar o vencedor
                        df_final_ordenado = df_filtrado_final.sort_values(by='BAC', ascending=False)
                    
                        # O vencedor é o primeiro da lista
                        vencedor = df_final_ordenado.iloc[0]
                    
                        with st.container(border=True):
                            # 1. Cria duas colunas: uma para o texto, outra para o gráfico
                            text_col, chart_col = st.columns([0.6, 0.4]) # 60% do espaço para o texto, 40% para o gráfico

                            # --- COLUNA DA ESQUERDA: TEXTO ---
                            with text_col:
                                st.success(f"Principal Recomendação: {vencedor['Label']}", icon="🎯")
                                st.markdown(f"**BAC:** `{vencedor['BAC']:.2f}%` | **FNR:** `{vencedor['FNR']:.2f}%` | **FPR:** `{vencedor['FPR']:.2f}%`")
                                st.markdown("---")
                                # Exibe os parâmetros de engenharia do vencedor
                                st.markdown(f"**Limiar ROCOF:** `{vencedor[HEADER_ROCOF]:.4f} Hz/s`")
                                st.markdown(f"**Temporização:** `{vencedor[HEADER_TEMPO]:.4f} s`")
                                if vencedor[HEADER_DROPOUT] > 0:
                                    st.markdown(f"**Tensão Bloqueio:** `{vencedor[HEADER_TENSAO_BLOQUEIO]:.2f} p.u.`")
                                    st.markdown(f"**Tempo Dropout:** `{vencedor[HEADER_DROPOUT]:.3f} s`")
                                    
                            # --- COLUNA DA DIREITA: GRÁFICO ---
                            with chart_col:
                                # 2. Prepara os dados para o gráfico do vencedor
                                dados_grafico_vencedor = {
                                    'Métrica': ['AB', 'TFN', 'TFP'],
                                    'Valor (%)': [vencedor['BAC'], vencedor['FNR'], vencedor['FPR']]
                                    }
                                df_grafico_vencedor = pd.DataFrame(dados_grafico_vencedor)

                                # Define as cores para cada métrica
                                cores_metricas = {
                                    'AB': 'teal',  # Verde
                                    'TFN': 'sandybrown',  # Amarelo/Laranja
                                    'TFP': 'saddlebrown'   # Vermelho
                                    }

                                # 3. Cria o gráfico de barras
                                fig_vencedor = px.bar(
                                    df_grafico_vencedor,
                                    x='Métrica',
                                    y='Valor (%)',
                                    color='Métrica',           # Usa a coluna 'Métrica' para definir a cor
                                    color_discrete_map=cores_metricas, # Aplica nosso mapa de cores
                                    text_auto='.2f'
                                    )
                                bac_max = vencedor['BAC'].max()
                                # Aumenta o tamanho da fonte dos valores nas barras
                                fig_vencedor.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                # Define um tamanho fixo para o gráfico e ajusta a escala do eixo Y
                                fig_vencedor.update_layout(
                                    showlegend=True,
                                    width=300, height=400,
                                    xaxis_title="AJUSTE VENCEDOR", yaxis_title="DESEMPENHO (%)",
                                
                                    legend=dict(
                                        title_text='', # Opcional: remove o título da legenda (que seria 'Métrica')
                                        orientation="h", # Coloca a legenda na horizontal
                                        yanchor="bottom",
                                        y=1.02, # Posição Y (acima do gráfico)
                                        xanchor="center",
                                        x=0.5, # Posição X (centralizado)
                                        font=dict(size=14)
                                        ),
                                    # Adiciona a configuração de fonte para o eixo X
                                    xaxis=dict(
                                        tickfont=dict(size=14),
                                        automargin=True# Define o tamanho da fonte para os labels do eixo X (A_F1, etc)
                                        ),
                                    
                                    # Adiciona a configuração de fonte ao dicionário já existente do eixo Y
                                    yaxis=dict(
                                        range=[0, 1.1*bac_max],
                                        tickfont=dict(size=14),
                                        automargin=True# Define o tamanho da fonte para os números do eixo Y
                                        )
                                    )   
                                st.plotly_chart(fig_vencedor)

                    
                        # As alternativas são os restantes
                        alternativas = df_final_ordenado.iloc[1:]
                        if not alternativas.empty:
                            with st.expander("Ver outras opções válidas", icon="🔍"):
                            
                                st.markdown("###### Parâmetros dos Ajustes")
                            
                                # Seleciona e renomeia as colunas para a tabela (lógica inalterada)
                                colunas_tabela_rocof = ['Label', HEADER_ROCOF, HEADER_TEMPO]
                                df_tabela_rocof = alternativas[colunas_tabela_rocof].copy() # Usar .copy() para evitar avisos
                                df_tabela_rocof.rename(columns={
                                    'Label': 'Ajuste',
                                    HEADER_ROCOF: 'Limiar ROCOF (Hz/s)',
                                    HEADER_TEMPO: 'Temporização (s)'
                                    }, inplace=True)
                            
                                # Definimos uma largura máxima em pixels para a tabela
                                st.dataframe(df_tabela_rocof, hide_index=True, width=350)

                                st.markdown("---") # Linha divisória
                                
                                st.markdown("###### Métricas de Desempenho")
                            
                                # --- LINHA 1: Tabela de Parâmetros e Gráfico BAC ---
                                bac_col, fnr_col, fpr_col = st.columns(3)
                            
                                with bac_col:
                                
                            
                                    # Gráfico de barras apenas para a Acurácia Balanceada (BAC)
                                    fig_bac = px.bar(
                                        alternativas,
                                        x='Label',
                                        y='BAC',
                                        text_auto='.2f', # Mostra o valor na barra
                                        color_discrete_sequence=['teal'] # Verde para uma métrica positiva
                                        )
                                    bac_max = alternativas['BAC'].max()
                                    # Aumenta o tamanho da fonte dos valores nas barras
                                    fig_bac.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                    # Define um tamanho fixo para o gráfico e ajusta a escala do eixo Y
                                    fig_bac.update_layout(
                                        width=300, height=400,
                                        xaxis_title="AJUSTES", yaxis_title="ACURÁCIA BALANCEADA (%)",
                                        # Adiciona a configuração de fonte para o eixo X
                                        xaxis=dict(
                                            tickfont=dict(size=14),
                                            automargin=True# Define o tamanho da fonte para os labels do eixo X (A_F1, etc)
                                            ),
                                    
                                        # Adiciona a configuração de fonte ao dicionário já existente do eixo Y
                                        yaxis=dict(
                                            range=[0.8*bac_max, 1.02*bac_max],
                                            tickfont=dict(size=14),
                                            automargin=True# Define o tamanho da fonte para os números do eixo Y
                                            )
                                        )   
                                    st.plotly_chart(fig_bac)
                                
                                
                                with fnr_col:
                                
                                    # Gráfico de barras apenas para a Taxa de Falsos Negativos (FNR)
                                    fig_fnr = px.bar(
                                        alternativas,
                                        x='Label',
                                        y='FNR',
                                        text_auto='.2f',
                                        color_discrete_sequence=['sandybrown'] # Amarelo/Laranja para uma métrica de atenção
                                        )
                                    fnr_max = alternativas['FNR'].max()
                                    # Aumenta o tamanho da fonte dos valores nas barras
                                    fig_fnr.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                    # Define um tamanho fixo para o gráfico e ajusta a escala do eixo Y
                                    fig_fnr.update_layout(
                                        width=300, height=400,
                                        xaxis_title="AJUSTES", yaxis_title="TAXA DE FALSO NEGATIVO (%)",
                                        # Adiciona a configuração de fonte para o eixo X
                                        xaxis=dict(
                                            tickfont=dict(size=14),
                                            automargin=True # Define o tamanho da fonte para os labels do eixo X (A_F1, etc)
                                            ),
                                        
                                        # Adiciona a configuração de fonte ao dicionário já existente do eixo Y
                                        yaxis=dict(
                                            range=[0, max(1, fnr_max * 1.2)],
                                            tickfont=dict(size=14),
                                            automargin=True # Define o tamanho da fonte para os números do eixo Y
                                            )
                                        )   
                                    st.plotly_chart(fig_fnr)
                                    
                                    
                                with fpr_col:
                                
                                    # Gráfico de barras apenas para a Taxa de Falsos Positivos (FPR)
                                    fig_fpr = px.bar(
                                        alternativas,
                                        x='Label',
                                        y='FPR',
                                        text_auto='.2f',
                                        color_discrete_sequence=['saddlebrown'] # Vermelho para uma métrica de erro
                                        )
                                    fpr_max = alternativas['FPR'].max()
                                    # Aumenta o tamanho da fonte dos valores nas barras
                                    fig_fpr.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                    # Define um tamanho fixo para o gráfico e ajusta a escala do eixo Y
                                    fig_fpr.update_layout(
                                        width=300, height=400,
                                        xaxis_title="AJUSTES", yaxis_title="TAXA DE FALSO POSITIVO (%)",
                                        # Adiciona a configuração de fonte para o eixo X
                                        xaxis=dict(
                                            tickfont=dict(size=14),
                                            automargin=True # Define o tamanho da fonte para os labels do eixo X (A_F1, etc)
                                            ),
                                        
                                        # Adiciona a configuração de fonte ao dicionário já existente do eixo Y
                                        yaxis=dict(
                                            range=[0, max(1, fpr_max * 1.2)],
                                            tickfont=dict(size=14),
                                            automargin=True # Define o tamanho da fonte para os números do eixo Y
                                            )
                                        )   
                                    st.plotly_chart(fig_fpr)

                else:

                    idx_cenarios = df_tmp.index.tolist()
                    subset_metricas = Y_total_sim.loc[idx_cenarios]

                    # Exibe breve resumo
                    st.info(f"Foram encontrados **{len(idx_cenarios)} cenários compatíveis**. Recomendações baseadas nas **médias de desempenho**.", icon="ℹ️")

                    # Cálculo de médias por ajuste
                    dados_candidatos = []
                    for ajuste_id in ajustes_candidatos:
                        bac_mean = subset_metricas[f'BAC_Ajuste_{ajuste_id}'].mean()
                        fnr_mean = subset_metricas[f'FNR_Ajuste_{ajuste_id}'].mean()
                        fpr_mean = subset_metricas[f'FPR_Ajuste_{ajuste_id}'].mean()
                        dados_candidatos.append({
                            'Ajuste_ID': ajuste_id,
                            'Label': ajuste_id_para_label_map.get(ajuste_id, f"ID {ajuste_id}"),
                            'BAC': bac_mean,
                            'FNR': fnr_mean,
                            'FPR': fpr_mean
                            })
                        
                    df_candidatos = pd.DataFrame(dados_candidatos)

                    # Junta com base de parâmetros
                    df_candidatos_completo = pd.merge(df_candidatos, df_params, left_on='Ajuste_ID', right_index=True, how='left')

                    # Regras de especialista rígidas (VB e RS)
                    ajustes_permitidos_vb = aj_vb if f3_codigo == 1 else aj_svb
                    if f4_codigo == 1:
                        ajustes_permitidos_rs = aj_rs1
                    elif f4_codigo == 2:
                        ajustes_permitidos_rs = aj_rs2
                    elif f4_codigo == 3:
                        ajustes_permitidos_rs = aj_rs3
                    else:
                        ajustes_permitidos_rs = aj_rs4

                    ajustes_elegiveis = ajustes_permitidos_vb.intersection(ajustes_permitidos_rs)
                    df_filtrado_regras = df_candidatos_completo[df_candidatos_completo['Ajuste_ID'].isin(ajustes_elegiveis)]

                    # Filtros de desempenho
                    df_filtrado_final = df_filtrado_regras[
                        (df_filtrado_regras['BAC'] > 90) &
                        (df_filtrado_regras['FNR'] < 10) &
                        (df_filtrado_regras['FPR'] < 10)
                        ]

                    st.subheader("Recomendações Baseadas nas Médias dos Cenários Compatíveis")

                    if df_filtrado_final.empty:
                        st.warning("Nenhum ajuste cumpriu os critérios de regras e desempenho considerando a média dos cenários.", icon="⚠️")
                    
                        
                        # 2. Mostra um subcabeçalho para as sugestões
                        st.subheader("Sugestões para Encontrar um Ajuste Válido:")
                        
                        # 3. Lógica condicional baseada nas entradas do usuário
                        
                        # Sugestão para Gerador Síncrono
                        if f2_texto == 'Gerador Síncrono':
                            st.info(
                                   "Tente **reduzir o nível do Requisito de Suportabilidade** (ex: de Categoria III para II).\n\n" 
                                   "Geradores Síncronos podem ter dificuldade em atingir limiares mais relaxados.",
                                   icon="💡"
                                   )

                        # Sugestão para Gerador Baseado em Inversor
                        elif f2_texto == 'Gerador Baseado em Inversor' and f3_texto == 'Habilitado':
                               st.info(
                                   "Tente **desabilitar o Bloqueio de Tensão**. Ajustes para Geradores Baseados em Inversores frequentemente operam melhor sem essa função.",
                                   icon="💡"
                                   )
                        # Adiciona um aviso extra se a combinação específica for selecionada
                        if f5_texto == 'GEVS' and f3_texto == 'Habilitado':
                            st.warning(
                                "**Atenção:** A combinação da técnica **GEVS** com **Bloqueio de Tensão Habilitado** é particularmente restritiva e pode não ter ajustes válidos. Desabilitar o bloqueio é a principal recomendação.",
                                icon="❗"
                                     )
                    
                    else:
                        # Seleciona vencedor (maior BAC médio)
                        df_final_ordenado = df_filtrado_final.sort_values(by='BAC', ascending=False)
                        vencedor = df_final_ordenado.iloc[0]

                        with st.container(border=True):
                            text_col, chart_col = st.columns([0.6, 0.4])

                            with text_col:
                                st.success(f"Principal Recomendação (média): {vencedor['Label']}", icon="🎯")
                                st.markdown(f"**BAC (média):** `{vencedor['BAC']:.2f}%` | **FNR (média):** `{vencedor['FNR']:.2f}%` | **FPR (média):** `{vencedor['FPR']:.2f}%`")
                                st.markdown("---")
                                st.markdown(f"**Limiar ROCOF:** `{vencedor[HEADER_ROCOF]:.4f} Hz/s`")
                                st.markdown(f"**Temporização:** `{vencedor[HEADER_TEMPO]:.4f} s`")
                                if vencedor[HEADER_DROPOUT] > 0:
                                    st.markdown(f"**Tensão Bloqueio:** `{vencedor[HEADER_TENSAO_BLOQUEIO]:.2f} p.u.`")
                                    st.markdown(f"**Tempo Dropout:** `{vencedor[HEADER_DROPOUT]:.3f} s`")

                            with chart_col:
                                dados_grafico_vencedor = {
                                    'Métrica': ['AB', 'TFN', 'TFP'],
                                    'Valor (%)': [vencedor['BAC'], vencedor['FNR'], vencedor['FPR']]
                                    }
                                df_grafico_vencedor = pd.DataFrame(dados_grafico_vencedor)
                                cores_metricas = {'AB': 'teal', 'TFN': 'sandybrown', 'TFP': 'saddlebrown'}
                                fig_vencedor = px.bar(
                                    df_grafico_vencedor, x='Métrica', y='Valor (%)', color='Métrica',
                                    color_discrete_map=cores_metricas, text_auto='.2f'
                                    )
                                fig_vencedor.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                fig_vencedor.update_layout(
                                    showlegend=True, width=300, height=400,
                                    xaxis_title="AJUSTE VENCEDOR (Média)", yaxis_title="DESEMPENHO (%)",
                                    legend=dict(title_text='', orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=14)),
                                    xaxis=dict(tickfont=dict(size=14), automargin=True),
                                    yaxis=dict(range=[0, max(1, vencedor['BAC'] * 1.1)], tickfont=dict(size=14), automargin=True)
                                    )
                                st.plotly_chart(fig_vencedor)

                        alternativas = df_final_ordenado.iloc[1:]
                        if not alternativas.empty:
                            with st.expander("Ver outras opções válidas (média)", icon="🔍"):
                                st.markdown("###### Parâmetros dos Ajustes")
                                colunas_tabela_rocof = ['Label', HEADER_ROCOF, HEADER_TEMPO]
                                df_tabela_rocof = alternativas[colunas_tabela_rocof].copy()
                                df_tabela_rocof.rename(columns={
                                    'Label': 'Ajuste',
                                    HEADER_ROCOF: 'Limiar ROCOF (Hz/s)',
                                    HEADER_TEMPO: 'Temporização (s)'
                                    }, inplace=True)
                                st.dataframe(df_tabela_rocof, hide_index=True, width=350)

                                st.markdown("---")
                                st.markdown("###### Métricas de Desempenho (Médias)")
                                bac_col, fnr_col, fpr_col = st.columns(3)

                                with bac_col:
                                    fig_bac = px.bar(alternativas, x='Label', y='BAC', text_auto='.2f', color_discrete_sequence=['teal'])
                                    fig_bac.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                    fig_bac.update_layout(width=300, height=400, xaxis_title="AJUSTES", yaxis_title="ACURÁCIA BALANCEADA (%)")
                                    st.plotly_chart(fig_bac)

                                with fnr_col:
                                    fig_fnr = px.bar(alternativas, x='Label', y='FNR', text_auto='.2f', color_discrete_sequence=['sandybrown'])
                                    fig_fnr.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                    fig_fnr.update_layout(width=300, height=400, xaxis_title="AJUSTES", yaxis_title="TAXA DE FALSO NEGATIVO (%)")
                                    st.plotly_chart(fig_fnr)

                                with fpr_col:
                                    fig_fpr = px.bar(alternativas, x='Label', y='FPR', text_auto='.2f', color_discrete_sequence=['saddlebrown'])
                                    fig_fpr.update_traces(textfont_size=14, textangle=0, width=0.4, textposition="outside")
                                    fig_fpr.update_layout(width=300, height=400, xaxis_title="AJUSTES", yaxis_title="TAXA DE FALSO POSITIVO (%)")
                                    st.plotly_chart(fig_fpr)

        except Exception as e:
            st.error(f"Ocorreu um erro ao processar a recomendação: {e}")
            st.code(traceback.format_exc())  # mostra onde ocorreu o erro
            
  