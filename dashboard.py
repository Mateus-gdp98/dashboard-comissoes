import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Dashboard de Equivalência", layout="wide")

st.title("📊 Painel de Comissões e Curva ABC de Produção")
st.markdown("Faça o upload da planilha geral de comissões e da planilha de produção para gerar o estudo cruzado.")

# Barra lateral para os Filtros do BI
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/320/320384.png", width=100)
st.sidebar.title("Filtros do B.I.")

# Componentes para upload dos arquivos (Lado a lado)
col_up1, col_up2 = st.columns(2)
arquivo_comissao = col_up1.file_uploader("1. Arquivo GERAL (Comissões) .xlsx", type=["xlsx"])
arquivo_producao = col_up2.file_uploader("2. Arquivo de PRODUÇÃO .csv ou .xlsx", type=["csv", "xlsx"])

if arquivo_comissao is not None and arquivo_producao is not None:
    try:
        with st.spinner("Cruzando dados e calculando médias..."):
            # ==========================================
            # 1. LEITURA E LIMPEZA COMISSÕES
            # ==========================================
            df_com = pd.read_excel(arquivo_comissao, sheet_name=1)
            
            df_com = df_com[~df_com['CONVENIO'].astype(str).str.contains('INSS', case=False, na=False)]
            df_com = df_com[~df_com['TIPO DE PRODUTO'].astype(str).isin(['T', 'CB'])]
            df_com = df_com[df_com['TABELA PACOTE'].astype(str).str.strip().str.upper() != 'S']
            
            legenda_produtos = {'N': 'Novo', 'C': 'Compra', 'R': 'Refin', 'F': 'Refin de Port', 'P': 'Port'}
            df_com['TIPO DE PRODUTO'] = df_com['TIPO DE PRODUTO'].map(legenda_produtos).fillna(df_com['TIPO DE PRODUTO'])
            
            df_com['P FINAL'] = pd.to_numeric(df_com['P FINAL'], errors='coerce').fillna(0).astype(int)
            max_p_final = df_com.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['P FINAL'].transform('max')
            df_com = df_com[df_com['P FINAL'] == max_p_final]

            # Salva os convênios que sobreviveram aos filtros de limpeza
            valid_convenios = df_com['CONVENIO'].dropna().unique().tolist()

            # ==========================================
            # 2. LEITURA E AUTO-FILTRO DE BANCO (PRODUÇÃO)
            # ==========================================
            if arquivo_producao.name.endswith('.csv'):
                df_prod = pd.read_csv(arquivo_producao, sep=None, engine='python')
            else:
                df_prod = pd.read_excel(arquivo_producao)
            
            df_prod['VALOR PROPOSTA'] = pd.to_numeric(df_prod['VALOR PROPOSTA'], errors='coerce').fillna(0)
            df_prod['QUANTIDADE'] = pd.to_numeric(df_prod['QUANTIDADE'], errors='coerce').fillna(0).astype(int)

            # Detecção automática do Banco - Sem precisar de menu suspenso!
            produtos_comissao = df_com['PRODUTO'].dropna().unique()
            bancos_sugeridos = df_prod[df_prod['PRODUTO'].isin(produtos_comissao)]['BANCO'].value_counts()
            banco_selecionado = bancos_sugeridos.index[0] if not bancos_sugeridos.empty else df_prod['BANCO'].iloc[0]
            
            df_prod_banco = df_prod[df_prod['BANCO'] == banco_selecionado]
            
            total_prod_geral = df_prod['VALOR PROPOSTA'].sum()
            total_prod_banco = df_prod_banco['VALOR PROPOSTA'].sum()
            perc_banco_total = (total_prod_banco / total_prod_geral * 100) if total_prod_geral > 0 else 0

            # Informa qual banco o robô detectou
            st.sidebar.success(f"🏦 Banco detectado: **{banco_selecionado}**")

            # ==========================================
            # 3. TOP 10 + CLT/FGTS (AGORA GARANTIDO!)
            # ==========================================
            # Filtra a produção APENAS pelos convênios válidos da comissão ANTES de fazer o rank dos maiores
            df_prod_banco_validos = df_prod_banco[df_prod_banco['ORGAO'].isin(valid_convenios)]
            
            prod_por_orgao = df_prod_banco_validos.groupby('ORGAO')['VALOR PROPOSTA'].sum().reset_index()
            prod_por_orgao = prod_por_orgao.sort_values(by='VALOR PROPOSTA', ascending=False)
            
            orgaos_destaque = prod_por_orgao[prod_por_orgao['ORGAO'].astype(str).str.upper().isin(['FGTS', 'CLT'])]['ORGAO'].tolist()
            outros_orgaos = prod_por_orgao[~prod_por_orgao['ORGAO'].astype(str).str.upper().isin(['FGTS', 'CLT'])]['ORGAO'].head(10).tolist()
            
            top_convenios_padrao = list(set(orgaos_destaque + outros_orgaos))
            
            # ==========================================
            # 4. FILTROS INTERATIVOS DO USUÁRIO
            # ==========================================
            st.sidebar.markdown("Use as opções abaixo para refinar os dados.")
            convenios_selecionados = st.sidebar.multiselect("🏢 Selecione o Convênio", options=valid_convenios, default=top_convenios_padrao)
            
            lista_produtos_comissao = df_com['TIPO DE PRODUTO'].dropna().unique().tolist()
            produtos_selecionados = st.sidebar.multiselect("📦 Selecione o Produto", options=lista_produtos_comissao, default=lista_produtos_comissao)
            
            df_filtrado = df_com[df_com['CONVENIO'].isin(convenios_selecionados) & df_com['TIPO DE PRODUTO'].isin(produtos_selecionados)]
            
            if df_filtrado.empty:
                st.warning("⚠️ Nenhum dado de comissão encontrado para os filtros selecionados.")
            else:
                # ==========================================
                # 5. CURVA ABC (70%) - PRAZO EXATO
                # ==========================================
                prazos_maximos = df_filtrado[['PRODUTO', 'P FINAL']].drop_duplicates()
                df_prod_banco_com_prazo = df_prod_banco.merge(prazos_maximos, on='PRODUTO', how='inner')
                df_prod_banco_max_prazo = df_prod_banco_com_prazo[df_prod_banco_com_prazo['QUANTIDADE'] == df_prod_banco_com_prazo['P FINAL']]
                
                prod_por_produto = df_prod_banco_max_prazo.groupby('PRODUTO')['VALOR PROPOSTA'].sum().reset_index()
                
                df_filtrado = df_filtrado.merge(prod_por_produto, on='PRODUTO', how='left')
                df_filtrado['VALOR PROPOSTA'] = df_filtrado['VALOR PROPOSTA'].fillna(0)
                
                df_filtrado = df_filtrado.sort_values(by=['CONVENIO', 'TIPO DE PRODUTO', 'VALOR PROPOSTA'], ascending=[True, True, False])
                
                df_filtrado['PROD_TOTAL_GRUPO'] = df_filtrado.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['VALOR PROPOSTA'].transform('sum')
                df_filtrado['CUMSUM_PROD'] = df_filtrado.groupby(['CONVENIO', 'TIPO DE PRODUTO'])['VALOR PROPOSTA'].cumsum()
                
                df_filtrado['% CUMULATIVA'] = (df_filtrado['CUMSUM_PROD'] / df_filtrado['PROD_TOTAL_GRUPO']).fillna(0)
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
                               'DIAMANTE', 'DIAMANTE 1', 'DIAMANTE 2', 'DIAMANTE 3', 'EMP 90', 'EMP 95', 'EMP 98',
                               'EMP 100', 'VIP', 'VIP 1', 'VIP 2', 'VIP 3', 'MASTER', 'TESTE8', 'TESTE9', 'TESTE10']
                
                resultados = []
                df_agrupado = df_70.groupby(['CONVENIO', 'TIPO DE PRODUTO', 'PRODUTO', 'P FINAL']).sum(numeric_only=True).reset_index()
                
                for index, row in df_agrupado.iterrows():
                    linha_resultado = {
                        'Convênio': row['CONVENIO'],
                        'Tipo de Produto': row['TIPO DE PRODUTO'],
                        'Produto (Tabela)': row['PRODUTO'],
                        'Prazo Máx.': row['P FINAL'],
                        'Produção R$ Original': row['VALOR PROPOSTA'], # Usado para os cálculos
                        'Produção R$': f"R$ {row['VALOR PROPOSTA']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'Comissão Total ($)': f"{row['COMISSAO_TOTAL']:.2f}"
                    }
                    
                    for grupo in grupos_base:
                        colunas_do_grupo = [col for col in df_agrupado.columns if str(col).replace("'", "").strip() == grupo]
                        if len(colunas_do_grupo) >= 2:
                            coluna_primeira = colunas_do_grupo[0]
                            coluna_ultima = colunas_do_grupo[-1]
                            
                            soma_grupo = row[coluna_primeira] + row[coluna_ultima]
                            percentual = (soma_grupo / row['COMISSAO_TOTAL']) * 100 if row['COMISSAO_TOTAL'] > 0 else 0
                            
                            linha_resultado[f'% {grupo}'] = percentual
                            
                    resultados.append(linha_resultado)

                # ==========================================
                # 7. ADICIONANDO AS MÉDIAS
                # ==========================================
                df_parcial = pd.DataFrame(resultados)
                linhas_finais = []
                
                # Identifica dinamicamente as colunas que são de percentual
                colunas_perc = [col for col in df_parcial.columns if col.startswith('% ')]
                
                for (conv, tipo), group_df in df_parcial.groupby(['Convênio', 'Tipo de Produto'], sort=False):
                    # 7.1. Adiciona as linhas normais daquele bloco, formatando para texto (%)
                    for _, row in group_df.iterrows():
                        row_dict = row.to_dict()
                        for c in colunas_perc:
                            if pd.notnull(row_dict[c]):
                                row_dict[c] = f"{row_dict[c]:.2f}%"
                        # Remove a coluna temporária usada apenas pra cálculo
                        row_dict.pop('Produção R$ Original', None)
                        linhas_finais.append(row_dict)
                        
                    # 7.2. Cria a linha da Média
                    media_row = {
                        'Convênio': conv,
                        'Tipo de Produto': tipo,
                        'Produto (Tabela)': '➡️ MÉDIA DO GRUPO',
                        'Prazo Máx.': '-',
                        'Produção R$': '-',
                        'Comissão Total ($)': '-'
                    }
                    # Calcula a média pra cada coluna de comissão e formata
                    for c in colunas_perc:
                        media_val = group_df[c].mean()
                        media_row[c] = f"{media_val:.2f}%" if pd.notnull(media_val) else "0.00%"
                        
                    linhas_finais.append(media_row)

                df_final = pd.DataFrame(linhas_finais)

                # ==========================================
                # 8. EXIBIÇÃO NO DASHBOARD
                # ==========================================
                st.success("Dados processados com sucesso! Exibindo ~70% do volume com a linha de médias inclusa.")
                
                col1, col2, col3, col4 = st.columns(4)
                
                qtd_convenios = df_parcial['Convênio'].nunique()
                qtd_tabelas = df_parcial['Produto (Tabela)'].nunique()
                soma_prod_exibida = df_parcial['Produção R$ Original'].sum()
                
                col1.metric("Convênios Filtrados", qtd_convenios)
                col2.metric("Tabelas Selecionadas", qtd_tabelas)
                
                soma_formatada = f"R$ {soma_prod_exibida:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                perc_filtrado_banco = (soma_prod_exibida / total_prod_banco * 100) if total_prod_banco > 0 else 0
                
                col3.metric(
                    label="Volume das tabelas filtradas", 
                    value=soma_formatada,
                    delta=f"{perc_filtrado_banco:.2f}% do banco",
                    delta_color="normal"
                )
                
                soma_banco_formatada = f"R$ {total_prod_banco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                col4.metric(
                    label=f"Total Produzido ({banco_selecionado})", 
                    value=soma_banco_formatada, 
                    delta=f"{perc_banco_total:.2f}% do volume geral",
                    delta_color="normal"
                )
                
                st.subheader("Tabela de Equivalência (%)")
                
                # Deixa a linha de MÉDIA destacada (em negrito e fundo diferente)
                def style_media(row):
                    if row['Produto (Tabela)'] == '➡️ MÉDIA DO GRUPO':
                        return ['background-color: #f0f2f6; font-weight: bold; color: #000000;'] * len(row)
                    return [''] * len(row)
                    
                st.dataframe(df_final.style.apply(style_media, axis=1), use_container_width=True, hide_index=True)
                
                csv = df_final.to_csv(index=False, sep=';', decimal=',')
                st.download_button(
                    label="📥 Baixar Estudo Completo (CSV)",
                    data=csv,
                    file_name='estudo_comissoes_producao_diretoria.csv',
                    mime='text/csv',
                )

    except Exception as e:
        st.error(f"Erro ao processar os arquivos. Verifique se os layouts estão corretos. Detalhe do erro: {e}")
