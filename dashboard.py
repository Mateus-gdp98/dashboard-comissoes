import streamlit as st
import pandas as pd

# Configuração da página para ocupar a tela toda
st.set_page_config(page_title="Dashboard de Comissões", layout="wide")

st.title("📊 Painel de Equivalência de Comissões por Grupo")
st.markdown("Faça o upload da planilha geral para gerar o estudo de caso.")

# Componente para upload do arquivo
arquivo_upload = st.file_uploader("Suba o arquivo Excel (.xlsx)", type=["xlsx"])

if arquivo_upload is not None:
    try:
        # Lê especificamente a SEGUNDA ABA do Excel (índice 1)
        df = pd.read_excel(arquivo_upload, sheet_name=1)
        
        # 1. FILTROS E LIMPEZA
        # Ignorar CONVENIO que possua 'INSS'
        df = df[~df['CONVENIO'].astype(str).str.contains('INSS', case=False, na=False)]
        
        # Ignorar TIPO DE PRODUTO que seja 'T' ou 'CB'
        df = df[~df['TIPO DE PRODUTO'].astype(str).isin(['T', 'CB'])]
        
        # 2. TRADUÇÃO DAS SIGLAS (DE-PARA)
        legenda_produtos = {
            'N': 'Novo',
            'C': 'Compra',
            'R': 'Refin',
            'F': 'Refin de Port',
            'P': 'Port'
        }
        df['TIPO DE PRODUTO'] = df['TIPO DE PRODUTO'].map(legenda_produtos).fillna(df['TIPO DE PRODUTO'])
        
        # 3. CÁLCULO DA COMISSÃO TOTAL
        # Garantindo que as colunas sejam numéricas (substituindo o que não for número por 0)
        colunas_total = ['FLAT', 'TOTAL CAMPANHAS', 'BONUS EMP']
        for col in colunas_total:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        df['COMISSAO_TOTAL'] = df['FLAT'] + df['TOTAL CAMPANHAS'] + df['BONUS EMP']
        
        # 4. IDENTIFICAR GRUPOS E CALCULAR COMISSÃO DE CADA UM
        # Lista dos grupos base que possuem a estrutura com aspas (ex: OURO e OURO'''')
        # Baseado nos cabeçalhos normais do arquivo
        grupos_base = ['OURO', 'PRIME', 'PRIME 1', 'PRIME 2', 'PRIME 3', 
                       'PRIVATE', 'PRIVATE 1', 'PRIVATE 2', 'PRIVATE 3', 
                       'DIAMANTE', 'DIAMANTE 1', 'DIAMANTE 2', 'DIAMANTE 3', 'EMP 90', 'EMP 95', 'EMP 98', 'EMP 100', 'VIP', 'VIP 1', 'VIP 2', 'VIP 3', 'MASTER', 'TESTE8', 'TESTE9', 'TESTE10' ]
        
        resultados = []
        
        # Agrupar por Convênio e Tipo de Produto para os cálculos
        df_agrupado = df.groupby(['CONVENIO', 'TIPO DE PRODUTO']).sum(numeric_only=True).reset_index()
        
        for index, row in df_agrupado.iterrows():
            linha_resultado = {
                'Convênio': row['CONVENIO'],
                'Tipo de Produto': row['TIPO DE PRODUTO'],
                'Comissão Total ($)': round(row['COMISSAO_TOTAL'], 2)
            }
            
            # Calcular o percentual de cada grupo
            for grupo in grupos_base:
                coluna_primeira = grupo
                coluna_ultima = f"{grupo}''''" # Nome da coluna com 4 aspas simples
                
                # Verifica se as colunas existem na planilha
                if coluna_primeira in df_agrupado.columns and coluna_ultima in df_agrupado.columns:
                    soma_grupo = row[coluna_primeira] + row[coluna_ultima]
                    
                    if row['COMISSAO_TOTAL'] > 0:
                        percentual = (soma_grupo / row['COMISSAO_TOTAL']) * 100
                    else:
                        percentual = 0
                        
                    # Formatando para exibição em porcentagem
                    linha_resultado[f'% {grupo}'] = f"{percentual:.2f}%"
                    
            resultados.append(linha_resultado)

        # 5. EXIBIÇÃO NO DASHBOARD
        df_final = pd.DataFrame(resultados)
        
        st.success("Dados processados com sucesso!")
        
        st.subheader("Tabela de Equivalência de Comissões (%)")
        st.dataframe(df_final, use_container_width=True)
        
        # Adicionar opção de download do resultado para a diretoria
        csv = df_final.to_csv(index=False, sep=';', decimal=',')
        st.download_button(
            label="📥 Baixar Estudo em CSV",
            data=csv,
            file_name='estudo_comissoes_diretoria.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"Erro ao processar o arquivo. Verifique se ele possui a aba e colunas corretas. Detalhe do erro: {e}")