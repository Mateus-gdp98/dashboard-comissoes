import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Dashboard de Comissões e Produção", layout="wide")

st.title("📊 Painel de Comissões e Curva ABC de Produção")
st.markdown("Faça o upload da planilha geral de comissões e da planilha de produção para gerar o estudo cruzado.")

# Barra lateral para os Filtros do BI
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/320/320384.png", width=100)
st.sidebar.title("Filtros do B.I.")
st.sidebar.markdown("Use as opções abaixo para refinar os dados.")

# Componentes para upload dos arquivos (Lado a lado)
col_up1, col_up2 = st.columns(2)
arquivo_comissao = col_up1.file_uploader("1. Arquivo GERAL (Comissões) .xlsx", type=["xlsx"])
arquivo_producao = col_up2.file_uploader("2. Arquivo de PRODUÇÃO .csv ou .xlsx", type=["csv", "xlsx"])

if arquivo_comissao is not None and arquivo_producao is not None:
    try:
        with st.spinner("Cruzando dados de comissão e produção..."):
            # ==========================================
            # 1. LEITURA DOS ARQUIVOS
            # ==========================================
            df_com = pd.read_excel(arquivo_comissao, sheet_name=1)
            
            if arquivo_producao.name.endswith('.csv'):
                # engine python e sep=None ajuda a ler tanto CSV separado por vírgula quanto ponto-e-vírgula (padrão BR)
                df_prod = pd.read_csv(arquivo_producao, sep=None, engine='python')
            else:
                df_prod = pd.read_excel(arquivo_producao)
            
            # ==========================================
            # 2. LIMPEZA BASE DE COMISSÕES
            # ==========================================
            df_com = df_com[~df_com['CONVENIO'].astype(str).str.contains('INSS', case=False, na=False)]
            df_com = df_com[~df_com['TIPO DE PRODUTO'].astype(str).isin(['T', 'CB'])]
            df_com = df_com[df_com['TABELA PACOTE'].astype(str).str.strip().str.upper() != 'S']
            
            legenda_produtos = {'N': 'Novo', 'C': 'Compra', 'R': 'Refin', 'F': 'Refin de Port', 'P': 'Port'}
            df_com['TIPO DE PRODUTO'] = df_com['TIPO DE PRODUTO'].map(legenda_produtos).fillna(df_com['TIPO DE PRODUTO'])
            
            # PASSO 2 (Aprimoramento): Apenas os maiores prazos (P FINAL)
            df_com['P FINAL'] = pd.to_numeric(df_com['P FINAL'], errors='coerce').fillna(0)
            # Calcula o maior P FINAL para cada par (CONVENIO e TIPO DE PRODUTO)
            max_p_final = df_com.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['P FINAL'].transform('max')
            df_com = df_com[df_com['P FINAL'] == max_p_final]

            # ==========================================
            # 3. TRATAMENTO DA PRODUÇÃO & TOP 10 + CLT/FGTS
            # ==========================================
            df_prod['VALOR PROPOSTA'] = pd.to_numeric(df_prod['VALOR PROPOSTA'], errors='coerce').fillna(0)
            
            # Somar produção por Órgão para achar os maiores
            prod_por_orgao = df_prod.groupby('ORGAO')['VALOR PROPOSTA'].sum().reset_index()
            prod_por_orgao = prod_por_orgao.sort_values(by='VALOR PROPOSTA', ascending=False)
            
            # Identificar FGTS e CLT
            orgaos_destaque = prod_por_orgao[prod_por_orgao['ORGAO'].astype(str).str.upper().isin(['FGTS', 'CLT'])]['ORGAO'].tolist()
            # Identificar os top 10 (tirando FGTS e CLT da conta para não duplicar)
            outros_orgaos = prod_por_orgao[~prod_por_orgao['ORGAO'].astype(str).str.upper().isin(['FGTS', 'CLT'])]['ORGAO'].head(10).tolist()
            
            # Lista com os padrões que devem vir selecionados
            top_convenios_padrao = list(set(orgaos_destaque + outros_orgaos))
            
            # ==========================================
            # 4. FILTROS INTERATIVOS DO USUÁRIO (B.I.)
            # ==========================================
            lista_convenios_comissao = df_com['CONVENIO'].dropna().unique().tolist()
            
            # Garantir que os defaults existam na tabela de comissão para não dar erro
            defaults_validos = [c for c in top_convenios_padrao if c in lista_convenios_comissao]
            
            convenios_selecionados = st.sidebar.multiselect("🏢 Selecione o Convênio", options=lista_convenios_comissao, default=defaults_validos)
            
            lista_produtos_comissao = df_com['TIPO DE PRODUTO'].dropna().unique().tolist()
            produtos_selecionados = st.sidebar.multiselect("📦 Selecione o Produto", options=lista_produtos_comissao, default=lista_produtos_comissao)
            
            df_filtrado = df_com[df_com['CONVENIO'].isin(convenios_selecionados) & df_com['TIPO DE PRODUTO'].isin(produtos_selecionados)]
            
            if df_filtrado.empty:
                st.warning("⚠️ Nenhum dado encontrado após os filtros.")
            else:
                # ==========================================
                # 5. CRUZAMENTO DE DADOS E REGRA DOS 70%
                # ==========================================
                # Somar produção por PRODUTO (nome da tabela)
                prod_por_produto = df_prod.groupby('PRODUTO')['VALOR PROPOSTA'].sum().reset_index()
                
                # Juntar a produção com as regras de comissão
                df_filtrado = df_filtrado.merge(prod_por_produto, on='PRODUTO', how='left')
                df_filtrado['VALOR PROPOSTA'] = df_filtrado['VALOR PROPOSTA'].fillna(0)
                
                # Ordenar pelo que mais produziu dentro de cada convênio e tipo
                df_filtrado = df_filtrado.sort_values(by=['CONVENIO', 'TIPO DE PRODUTO', 'VALOR PROPOSTA'], ascending=[True, True, False])
                
                # Calcular o total do grupo e a soma acumulada
                df_filtrado['PROD_TOTAL_GRUPO'] = df_filtrado.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['VALOR PROPOSTA'].transform('sum')
                df_filtrado['CUMSUM_PROD'] = df_filtrado.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['VALOR PROPOSTA'].cumsum()
                
                # Percentual acumulado
                df_filtrado['% CUMULATIVA'] = (df_filtrado['CUMSUM_PROD'] / df_filtrado['PROD_TOTAL_GRUPO']).fillna(0)
                
                # REGRA 70%: Pegamos a porcentagem da linha anterior. Se a anterior já bateu 70%, a atual e as próximas não entram.
                df_filtrado['% CUMULATIVA_ANTERIOR'] = df_filtrado.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['% CUMULATIVA'].shift(1).fillna(0)
                df_70 = df_filtrado[df_filtrado['% CUMULATIVA_ANTERIOR'] < 0.70]
                
                # ==========================================
                # 6. CÁLCULOS DAS COMISSÕES
                # ==========================================
                colunas_total = ['FLAT', 'TOTAL CAMPANHAS', 'BONUS EMP']
                for col in colunas_total:
                    df_70.loc[:, col] = pd.to_numeric(df_70[col], errors='coerce').fillna(0)
                    
                df_70.loc[:, 'COMISSAO_TOTAL'] = df_70['FLAT'] + df_70['TOTAL CAMPANHAS'] + df_70['BONUS EMP']
                
                grupos_base = ['OURO', 'PRIME', 'PRIME 1', 'PRIME 2', 'PRIME 3', 
                               'PRIVATE', 'PRIVATE 1', 'PRIVATE 2', 'PRIVATE 3', 
                               'DIAMANTE', 'DIAMANTE 1', 'DIAMANTE 2', 'DIAMANTE 3']
                
                resultados = []
                
                # Agora o agrupamento inclui o NOME DO PRODUTO (Tabela) para sabermos quem compôs os 70%
                df_agrupado = df_70.groupby(['CONVENIO', 'TIPO DE PRODUTO', 'PRODUTO']).sum(numeric_only=True).reset_index()
                
                for index, row in df_agrupado.iterrows():
                    linha_resultado = {
                        'Convênio': row['CONVENIO'],
                        'Tipo de Produto': row['TIPO DE PRODUTO'],
                        'Produto (Tabela)': row['PRODUTO'],
                        'Produção R$': f"R$ {row['VALOR PROPOSTA']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'Comissão Total ($)': round(row['COMISSAO_TOTAL'], 2)
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

                # ==========================================
                # 7. EXIBIÇÃO NO DASHBOARD
                # ==========================================
                df_final = pd.DataFrame(resultados)
                
                st.success("Dados processados com sucesso! Exibindo apenas as tabelas responsáveis por 70% do volume.")
                
                # Métricas Rápidas
                col1, col2, col3 = st.columns(3)
                col1.metric("Convênios Filtrados", len(df_final['Convênio'].unique()))
                col2.metric("Tabelas Selecionadas (Curva ABC)", len(df_final['Produto (Tabela)'].unique()))
                
                soma_prod_exibida = df_70['VALOR PROPOSTA'].sum()
                soma_formatada = f"R$ {soma_prod_exibida:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                col3.metric("Volume Produzido Exibido", soma_formatada)
                
                st.subheader("Tabela de Equivalência (%)")
                # Exibe sem o índice lateral numérico para ficar mais clean
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                
                csv = df_final.to_csv(index=False, sep=';', decimal=',')
                st.download_button(
                    label="📥 Baixar Estudo Completo (CSV)",
                    data=csv,
                    file_name='estudo_comissoes_producao_diretoria.csv',
                    mime='text/csv',
                )

    except Exception as e:
        st.error(f"Erro ao processar os arquivos. Verifique se os layouts estão corretos. Detalhe do erro: {e}")
