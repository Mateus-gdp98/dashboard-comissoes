import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Dashboard de Comissões", layout="wide")

st.title("📊 Painel de Equivalência de Comissões por Grupo")
st.markdown("Faça o upload da planilha geral para gerar o estudo de caso interativo.")

# Barra lateral para os Filtros do BI
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/320/320384.png", width=100) # Ícone apenas para ilustrar
st.sidebar.title("Filtros do B.I.")
st.sidebar.markdown("Use as opções abaixo para refinar os dados.")

# Componente para upload do arquivo
arquivo_upload = st.file_uploader("Suba o arquivo Excel (.xlsx)", type=["xlsx"])

if arquivo_upload is not None:
    try:
        # Lê a segunda aba do Excel
        df = pd.read_excel(arquivo_upload, sheet_name=1)
        
        # 1. FILTROS GERAIS E LIMPEZA
        # Ignorar INSS
        df = df[~df['CONVENIO'].astype(str).str.contains('INSS', case=False, na=False)]
        
        # Ignorar Produtos T e CB
        df = df[~df['TIPO DE PRODUTO'].astype(str).isin(['T', 'CB'])]
        
        # NOVO FILTRO: Ignorar TABELA PACOTE que seja igual a 'S'
        df = df[df['TABELA PACOTE'].astype(str).str.strip().str.upper() != 'S']
        
        # De-Para dos tipos de produto
        legenda_produtos = {
            'N': 'Novo',
            'C': 'Compra',
            'R': 'Refin',
            'F': 'Refin de Port',
            'P': 'Port'
        }
        df['TIPO DE PRODUTO'] = df['TIPO DE PRODUTO'].map(legenda_produtos).fillna(df['TIPO DE PRODUTO'])
        
        # 2. FILTROS INTERATIVOS DO USUÁRIO (B.I.)
        lista_convenios = df['CONVENIO'].dropna().unique().tolist()
        lista_produtos = df['TIPO DE PRODUTO'].dropna().unique().tolist()
        
        convenios_selecionados = st.sidebar.multiselect("🏢 Selecione o Convênio", options=lista_convenios, default=lista_convenios)
        produtos_selecionados = st.sidebar.multiselect("📦 Selecione o Produto", options=lista_produtos, default=lista_produtos)
        
        df_filtrado = df[df['CONVENIO'].isin(convenios_selecionados) & df['TIPO DE PRODUTO'].isin(produtos_selecionados)]
        
        if df_filtrado.empty:
            st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados.")
        else:
            # 3. CÁLCULO DA COMISSÃO TOTAL
            colunas_total = ['FLAT', 'TOTAL CAMPANHAS', 'BONUS EMP']
            for col in colunas_total:
                df_filtrado.loc[:, col] = pd.to_numeric(df_filtrado[col], errors='coerce').fillna(0)
                
            df_filtrado.loc[:, 'COMISSAO_TOTAL'] = df_filtrado['FLAT'] + df_filtrado['TOTAL CAMPANHAS'] + df_filtrado['BONUS EMP']
            
            # 4. IDENTIFICAR GRUPOS DE FORMA INTELIGENTE E CALCULAR
            grupos_base = ['OURO', 'PRIME', 'PRIME 1', 'PRIME 2', 'PRIME 3', 
                           'PRIVATE', 'PRIVATE 1', 'PRIVATE 2', 'PRIVATE 3', 
                           'DIAMANTE', 'DIAMANTE 1', 'DIAMANTE 2', 'DIAMANTE 3', 'EMP 90', 'EMP 95', 'EMP 98', 'EMP 100', 'VIP', 'VIP 1',
                           'VIP 2', 'VIP 3', 'MASTER', 'TESTE8', 'TESTE9', 'TESTE10']
            
            resultados = []
            
            df_agrupado = df_filtrado.groupby(['CONVENIO', 'TIPO DE PRODUTO']).sum(numeric_only=True).reset_index()
            
            for index, row in df_agrupado.iterrows():
                linha_resultado = {
                    'Convênio': row['CONVENIO'],
                    'Tipo de Produto': row['TIPO DE PRODUTO'],
                    'Perc de Comissão Total': round(row['COMISSAO_TOTAL'], 2)
                }
                
                for grupo in grupos_base:
                    colunas_do_grupo = [col for col in df_agrupado.columns if str(col).replace("'", "").strip() == grupo]
                    
                    if len(colunas_do_grupo) >= 2:
                        coluna_primeira = colunas_do_grupo[0]
                        coluna_ultima = colunas_do_grupo[-1]
                        
                        soma_grupo = row[coluna_primeira] + row[coluna_ultima]
                        
                        if row['COMISSAO_TOTAL'] > 0:
                            percentual = (soma_grupo / row['COMISSAO_TOTAL']) * 100
                        else:
                            percentual = 0
                            
                        linha_resultado[f'% {grupo}'] = f"{percentual:.2f}%"
                        
                resultados.append(linha_resultado)

            # 5. EXIBIÇÃO NO DASHBOARD
            df_final = pd.DataFrame(resultados)
            
            st.success("Dados carregados e filtrados com sucesso!")          
            st.subheader("Tabela de Equivalência de Comissões (%)")
            st.dataframe(df_final, use_container_width=True)
            
            csv = df_final.to_csv(index=False, sep=';', decimal=',')
            st.download_button(
                label="📥 Baixar Dados Filtrados (CSV)",
                data=csv,
                file_name='estudo_filtrado_diretoria.csv',
                mime='text/csv',
            )

    except Exception as e:
        st.error(f"Erro ao processar o arquivo. Detalhe do erro: {e}")
