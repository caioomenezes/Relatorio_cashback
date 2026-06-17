import io
import os
import logging
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px

from src.loader import load_dataframe
from src.validator import validate_dataframe
from src.metrics import compute_group_metrics
from src.decision_engine import rank_variants
from src.ai_analysis import analyze_with_ai
from src.report_generator import generate_pdf_report
from src.sheets import append_summary_row

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Analisador AI-Native de Testes A/B de Cashback", layout="wide")

# ── Inicializa session_state no topo — garante que as chaves existam
# antes de qualquer rerun causado por widgets ──────────────────────────────
if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None
if "pdf_file_name" not in st.session_state:
    st.session_state["pdf_file_name"] = None

st.title("Analisador AI-Native de Testes A/B de Cashback")
st.write("Faça upload de um dataset e receba uma análise automatizada do experimento.")

uploaded = st.file_uploader("Envie o CSV do experimento", type=["csv"])

if uploaded is not None:
    try:
        bytes_io = io.BytesIO(uploaded.read())
        df = load_dataframe(bytes_io)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        st.stop()

    st.sidebar.markdown("**Arquivo**")
    st.sidebar.write(uploaded.name)
    st.sidebar.markdown("**Linhas**")
    st.sidebar.write(len(df))

    # Infere parceiro e período
    partner = None
    for c in df.columns:
        if 'parceiro' in c or 'partner' in c:
            partner = c
            break
    partner_val = df[partner].dropna().unique().tolist()[0] if partner is not None and not df[partner].dropna().empty else "-"

    date_col = None
    for c in df.columns:
        if 'date' in c.lower() or 'data' in c.lower():
            date_col = c
            break
    period = "-"
    if date_col is not None:
        try:
            period = f"{pd.to_datetime(df[date_col]).min().date()} - {pd.to_datetime(df[date_col]).max().date()}"
        except Exception:
            period = "-"

    st.sidebar.markdown("**Parceiro**")
    st.sidebar.write(partner_val)
    st.sidebar.markdown("**Período**")
    st.sidebar.write(period)

    issues, df_clean = validate_dataframe(df)
    if issues:
        st.warning("Problemas detectados:\n" + "\n".join(issues))

    st.dataframe(df_clean.head(50))

    if st.button("Analisar Experimento"):
        # Limpa PDF anterior ao iniciar nova análise
        st.session_state["pdf_bytes"] = None
        st.session_state["pdf_file_name"] = None

        with st.spinner("Processando..."):
            try:
                group_col = None
                for c in df_clean.columns:
                    if 'grupo' in c.lower() or 'group' in c.lower() or 'variant' in c.lower():
                        group_col = c
                        break
                if group_col is None:
                    st.error('Coluna de grupos não encontrada.')
                    st.stop()

                metrics_df, summary = compute_group_metrics(df_clean, group_col)

                # Plots
                cols = st.columns(2)
                fig1 = px.bar(metrics_df, x='group', y='total_users', title='Usuários por grupo')
                cols[0].plotly_chart(fig1, use_container_width=True)

                fig2 = px.bar(metrics_df, x='group', y='commission', title='Comissão por grupo')
                cols[1].plotly_chart(fig2, use_container_width=True)

                cols2 = st.columns(2)
                fig3 = px.bar(metrics_df, x='group', y='cashback', title='Cashback por grupo')
                cols2[0].plotly_chart(fig3, use_container_width=True)

                fig4 = px.bar(metrics_df, x='group', y='net_revenue', title='Receita Líquida por grupo')
                cols2[1].plotly_chart(fig4, use_container_width=True)

                fig5 = px.bar(metrics_df, x='group', y='roi', title='ROI por grupo')
                st.plotly_chart(fig5, use_container_width=True)

                ranking = rank_variants(metrics_df)

                st.subheader('Ranking de variantes')
                st.table(ranking[['rank', 'group', 'score']])

                # AI analysis
                ai_summary = analyze_with_ai(summary, ranking, partner_val, period)
                st.subheader('Resumo AI')
                st.markdown(ai_summary)

                # Gera PDF e guarda no session_state
                report_path, pdf_bytes = generate_pdf_report(
                    uploaded.name, partner_val, period, metrics_df, ranking, ai_summary
                )
                st.session_state["pdf_bytes"]     = pdf_bytes
                st.session_state["pdf_file_name"] = os.path.basename(report_path)
                st.success(f"Relatório salvo em {report_path}")

                # Append to Google Sheets ou CSV
                winner_group = ranking.iloc[0]['group'] if len(ranking) else ''
                winner_net   = float(metrics_df.set_index('group').at[winner_group, 'net_revenue']) if winner_group else 0.0
                winner_roi   = float(metrics_df.set_index('group').at[winner_group, 'roi'])         if winner_group else 0.0

                row = {
                    'timestamp':           datetime.utcnow().isoformat(),
                    'source':              'streamlit',
                    'test_name':           f"{partner_val} - {period}",
                    'description':         f'Análise via app Streamlit (arquivo: {uploaded.name})',
                    'file_name':           uploaded.name,
                    'partner':             partner_val,
                    'num_groups':          len(metrics_df),
                    'result':              '',
                    'decision':            ai_summary.split('\n')[0] if ai_summary else '',
                    'winner_group':        winner_group,
                    'winner_net_revenue':  winner_net,
                    'winner_roi':          winner_roi,
                    'report_id':           '',
                    'report_path':         report_path,
                    'elapsed_ms':          '',
                }
                append_summary_row(row)
                st.balloons()

            except Exception as e:
                logger.exception(e)
                st.error(f'Erro no processamento: {e}')

    # ── BOTÃO DE DOWNLOAD — renderiza sempre que pdf_bytes estiver no state ──
    # Funciona porque session_state persiste entre reruns do Streamlit
    if st.session_state["pdf_bytes"] is not None:
        st.download_button(
            label="Baixar relatório PDF",
            data=st.session_state["pdf_bytes"],
            file_name=st.session_state["pdf_file_name"],
            mime="application/pdf",
        )