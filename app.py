import sys
import importlib

# Force reload of local modules to prevent Streamlit caching issues
for module_name in ['file_process', 'conciliate']:
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])

import streamlit as st
import pandas as pd
import os
import io
from file_process import load_excel_and_find_header, clean_float, filter_invalid_rows
from conciliate import find_next_reconciliation_step

# --- Page config ---
st.set_page_config(
    page_title="Conciliação Bancária",
    page_icon="🏦",
    layout="centered",
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* Main title */
    .main-title {
        text-align: center;
        padding: 0.5rem 0 0.2rem 0;
    }
    .main-title h1 {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
    }
    .main-title p {
        color: #a0aec0;
        font-size: 0.95rem;
        margin-top: -0.5rem;
    }

    /* Metric cards */
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1.2rem 1rem;
        text-align: center;
        border: 1px solid #e9ecef;
    }
    .metric-card .label {
        font-size: 0.8rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
    .metric-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a1a2e;
    }

    /* Status messages */
    .step-msg {
        font-size: 0.85rem;
        color: #495057;
        padding: 0.2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# --- Preferred Labels for Extrato Column ---
PREFERRED_LABELS = ["Valor"]

def clear_results():
    st.session_state.reconciliation_results = None
    st.session_state.df1_remaining = None
    st.session_state.df2_remaining = None
    st.session_state.reconciliation_stage = None
    st.session_state.current_conflict = None
    st.session_state.unmatched_df1 = None
    st.session_state.debito_col = None
    st.session_state.credito_col = None
    st.session_state.file2_col = None

if "reconciliation_results" not in st.session_state:
    st.session_state.reconciliation_results = None
if "df1_remaining" not in st.session_state:
    st.session_state.df1_remaining = None
if "df2_remaining" not in st.session_state:
    st.session_state.df2_remaining = None
if "reconciliation_stage" not in st.session_state:
    st.session_state.reconciliation_stage = None
if "current_conflict" not in st.session_state:
    st.session_state.current_conflict = None
if "unmatched_df1" not in st.session_state:
    st.session_state.unmatched_df1 = None
if "debito_col" not in st.session_state:
    st.session_state.debito_col = None
if "credito_col" not in st.session_state:
    st.session_state.credito_col = None
if "file2_col" not in st.session_state:
    st.session_state.file2_col = None

def extract_key_fields(row, df_cols):
    # Find candidate columns
    date_col = next((c for c in df_cols if any(k in str(c).lower() for k in ["data", "date", "dt", "dia"])), None)
    desc_col = next((c for c in df_cols if any(k in str(c).lower() for k in ["desc", "hist", "detalhe", "narrative", "info", "nome", "concepto", "parceiro", "cliente", "fornecedor"])), None)
    doc_col = next((c for c in df_cols if any(k in str(c).lower() for k in ["doc", "ref", "num", "id", "trans", "cheque", "recibo"])), None)
    
    # Extract values
    date_val = "N/A"
    if date_col is not None and pd.notna(row[date_col]):
        val = row[date_col]
        if hasattr(val, "strftime"):
            date_val = val.strftime("%d/%m/%Y")
        else:
            date_val = str(val).split(" ")[0]
            
    desc_val = "N/A"
    if desc_col is not None and pd.notna(row[desc_col]):
        desc_val = str(row[desc_col]).strip()
        
    doc_val = ""
    if doc_col is not None and pd.notna(row[doc_col]):
        doc_val = str(row[doc_col]).strip()
        
    # Fallback if date/desc are not found
    if date_val == "N/A" and desc_val == "N/A":
        # Just grab the first few columns
        non_empty_parts = [f"{col}: {val}" for col, val in row.items() if pd.notna(val) and str(val).strip() != ""]
        if len(non_empty_parts) > 0:
            desc_val = " | ".join(non_empty_parts[:3])
            
    return date_val, desc_val, doc_val


# --- Header ---
st.markdown("""
<div class="main-title">
    <h1>Conciliação Bancária</h1>
    <p>Carregue os seus ficheiros, selecione a coluna de valor e concilie.</p>
</div>
""", unsafe_allow_html=True)


# --- File uploads ---
col_up1, col_up2 = st.columns(2)

with col_up1:
    file1 = st.file_uploader(
        "Contabilidade",
        type=["xlsx", "xls", "xlsm", "xlsb"],
        accept_multiple_files=False,
        key="contabilidade",
        help="Ficheiro com os dados da contabilidade.",
        on_change=clear_results,
    )

with col_up2:
    file2 = st.file_uploader(
        "Extrato Bancário",
        type=["xlsx", "xls", "xlsm", "xlsb"],
        accept_multiple_files=False,
        key="extrato",
        help="Ficheiro do extrato bancário, obtido num banco. Caso só tenha em PDF ou noutro tipo de ficheiro que não seja um dos referidos abaixo, sugiro que peça ao ChatGPT que converta a tabela no seu ficheiro para um dos ficheiros compatíveis.",
        on_change=clear_results,
    )

# --- File Preview Section ---
if file1 is not None or file2 is not None:
    with st.expander("🔍 Pré-visualizar Ficheiros Carregados", expanded=False):
        tab1, tab2 = st.tabs(["Contabilidade", "Extrato Bancário"])
        
        with tab1:
            if file1 is not None:
                try:
                    file1.seek(0)
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_preview:
                        tmp_preview.write(file1.getvalue())
                        tmp_preview_path = tmp_preview.name
                    df1_preview = load_excel_and_find_header(tmp_preview_path)
                    os.unlink(tmp_preview_path)
                    file1.seek(0)
                    
                    preview_debito = next((c for c in df1_preview.columns if str(c).strip().lower() in ['débito', 'debito']), None)
                    preview_credito = next((c for c in df1_preview.columns if str(c).strip().lower() in ['crédito', 'credito']), None)
                    if preview_debito and preview_credito:
                        df1_preview = filter_invalid_rows(df1_preview, preview_debito, preview_credito)
                        
                    st.dataframe(df1_preview, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Não foi possível ler a pré-visualização da Contabilidade: {e}")
            else:
                st.info("Carregue um ficheiro de Contabilidade para ver a sua pré-visualização.")
                
        with tab2:
            if file2 is not None:
                try:
                    file2.seek(0)
                    df2_preview = pd.read_excel(file2)
                    file2.seek(0)
                    st.dataframe(df2_preview, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Não foi possível ler a pré-visualização do Extrato: {e}")
            else:
                st.info("Carregue um ficheiro de Extrato para ver a sua pré-visualização.")

# --- Column picker for Extrato (only shown when file2 is uploaded) ---
file2_col = None
if file2 is not None:
    try:
        df_preview = pd.read_excel(file2, nrows=0)
        available_columns = list(df_preview.columns)
        # Reset the file pointer so it can be read again later
        file2.seek(0)

        if available_columns:
            # Find if any available column matches a preferred label
            preferred_index = None
            for idx, col in enumerate(available_columns):
                if str(col).strip() in PREFERRED_LABELS:
                    preferred_index = idx
                    break
            
            file2_col = st.selectbox(
                "Selecione a coluna de valor do ficheiro de Extrato",
                options=available_columns,
                index=preferred_index,
                placeholder="Escolha a coluna de valor...",
                help='Os ficheiros de extratos bancários podem assumir um nome diferente de "valor" para a coluna dos valores. Assim, para garantir que o programa funciona independentemente da designação, o utilizador poderá selecionar manualmente a coluna que contém os valores. Caso haja uma coluna chamada "valor" ou com outro nome... sugestivo, será selecionada por defeito.',
                on_change=clear_results,
            )
        else:
            st.warning("O ficheiro de Extrato não tem cabeçalhos de coluna.")
    except Exception as e:
        st.error(f"Não foi possível ler os cabeçalhos do ficheiro de Extrato: {e}")

# --- Run button ---
can_run = file1 is not None and file2 is not None and file2_col is not None
run_clicked = st.button("▶  Executar Conciliação", disabled=not can_run, use_container_width=True, type="primary")

# --- Processing ---
def advance_reconciliation():
    df1_remaining = st.session_state.df1_remaining
    df2_remaining = st.session_state.df2_remaining
    debito_col = st.session_state.debito_col
    credito_col = st.session_state.credito_col
    file2_col = st.session_state.file2_col

    df1_next, df2_next, stage, conflict = find_next_reconciliation_step(
        df1_remaining, df2_remaining, debito_col, credito_col, file2_col
    )
    
    st.session_state.df1_remaining = df1_next
    st.session_state.df2_remaining = df2_next
    st.session_state.reconciliation_stage = stage
    st.session_state.current_conflict = conflict
    
    if stage == "done":
        # Concatenate any manually unmatched Contabilidade rows back
        if st.session_state.unmatched_df1 is not None and not st.session_state.unmatched_df1.empty:
            df1_final = pd.concat([df1_next, st.session_state.unmatched_df1])
        else:
            df1_final = df1_next
            
        st.session_state.reconciliation_results = {
            "df1_final": df1_final,
            "df2_final": df2_next
        }

if run_clicked:
    clear_results()
    with st.spinner("A ler e a conciliar os ficheiros..."):
        try:
            # 1. Load Contabilidade with auto-header finder
            # Save uploaded file to a temp path so load_excel_and_find_header can read it
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp1:
                tmp1.write(file1.getvalue())
                tmp1_path = tmp1.name

            df1 = load_excel_and_find_header(tmp1_path)
            os.unlink(tmp1_path)

            # Find Débito / Crédito columns
            debito_col = next((c for c in df1.columns if str(c).strip().lower() in ['débito', 'debito']), None)
            credito_col = next((c for c in df1.columns if str(c).strip().lower() in ['crédito', 'credito']), None)

            if not debito_col or not credito_col:
                st.error(f"Não foi possível encontrar as colunas 'Débito' e 'Crédito' na Contabilidade. Encontrado: {list(df1.columns)}")
                st.stop()

            # Filter out invalid/empty/non-numeric rows
            df1 = filter_invalid_rows(df1, debito_col, credito_col)

            # 2. Load Extrato
            df2 = pd.read_excel(file2)

            if file2_col not in df2.columns:
                st.error(f"A coluna '{file2_col}' não foi encontrada no ficheiro de Extrato.")
                st.stop()

            # Initialize reconciliation state
            st.session_state.df1_remaining = df1.copy()
            st.session_state.df2_remaining = df2.copy()
            st.session_state.debito_col = debito_col
            st.session_state.credito_col = credito_col
            st.session_state.file2_col = file2_col
            st.session_state.unmatched_df1 = pd.DataFrame(columns=df1.columns)

            # Run reconciliation
            advance_reconciliation()

        except Exception as e:
            st.error(f"Ocorreu um erro durante a conciliação: {e}")
            st.stop()

# --- Results or Conflict UI ---
if st.session_state.reconciliation_stage == "conflict":
    conflict = st.session_state.current_conflict
    val = conflict["value"]
    c_indices = conflict["c_indices"]
    e_indices = conflict["e_indices"]
    
    df1_rem = st.session_state.df1_remaining
    df2_rem = st.session_state.df2_remaining
    debito_col = st.session_state.debito_col
    credito_col = st.session_state.credito_col
    file2_col = st.session_state.file2_col

    # Format title card with gradient orange styling
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #f57c00 0%, #ff9800 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 15px rgba(245, 124, 0, 0.15);
        ">
            <h3 style="margin: 0; color: white; font-weight: 700; font-size: 1.35rem;">⚠️ Resolver Conflito de Correspondência</h3>
            <p style="margin: 6px 0 0 0; opacity: 0.95; font-size: 0.95rem; line-height: 1.4;">
                Múltiplas transações encontradas com o valor correspondente a <b>{abs(val):,.2f}€</b> ({'Crédito' if val >= 0 else 'Débito'}).<br/>
                Contabilidade: <b>{len(c_indices)}</b> {'linhas' if len(c_indices) >= 2 else 'linha'} vs Extrato: <b>{len(e_indices)}</b> {'linhas' if len(e_indices) >= 2 else 'linha'}.
                Por favor, faça as associações corretas abaixo.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Pre-format Extrato options
    extrato_options = ["Não conciliar / Manter aberto"]
    extrato_mapping = {}
    extrato_mapping["Não conciliar / Manter aberto"] = "Unmatched / Keep"
    for idx_e in e_indices:
        row = df2_rem.loc[idx_e]
        e_date, e_desc, e_doc = extract_key_fields(row, df2_rem.columns)
        
        parts = []
        if e_date != "N/A":
            parts.append(e_date)
        if e_desc != "N/A":
            truncated_desc = e_desc[:40] + "..." if len(e_desc) > 40 else e_desc
            parts.append(truncated_desc)
        if e_doc:
            parts.append(f"Doc: {e_doc}")
            
        option_label = f"Linha {idx_e} — " + " | ".join(parts)
        extrato_options.append(option_label)
        extrato_mapping[option_label] = idx_e

    # Setup columns layout
    col_c, col_e = st.columns([1.1, 0.9])
    
    selections = {}
    
    with col_c:
        st.markdown("### 📄 Contabilidade")
        for idx_c in c_indices:
            row_c = df1_rem.loc[idx_c]
            c_date, c_desc, c_doc = extract_key_fields(row_c, df1_rem.columns)
            
            with st.container(border=True):
                st.markdown(f"**Lançamento #{idx_c}**")
                
                details_html = f"""
                <div style='font-size: 0.88rem; margin-bottom: 12px; line-height: 1.45;'>
                    <b>Data:</b> {c_date}<br/>
                    <b>Descrição:</b> {c_desc}
                    {f'<br/><b>Doc:</b> {c_doc}' if c_doc else ''}
                </div>
                """
                st.markdown(details_html, unsafe_allow_html=True)
                
                selected = st.selectbox(
                    "Selecione o correspondente do Extrato:",
                    options=extrato_options,
                    key=f"match_group_{val}_{idx_c}",
                    label_visibility="collapsed"
                )
                selections[idx_c] = selected

    # Gather matching details for badge updates
    with col_e:
        st.markdown("### 🏦 Extrato Bancário")
        for idx_e in e_indices:
            row_e = df2_rem.loc[idx_e]
            e_date, e_desc, e_doc = extract_key_fields(row_e, df2_rem.columns)
            
            # Find which Contabilidade row has matched this Extrato item
            matched_by = []
            for c_idx, sel_label in selections.items():
                if sel_label != "Não conciliar / Manter aberto" and extrato_mapping[sel_label] == idx_e:
                    matched_by.append(c_idx)
            
            with st.container(border=True):
                if len(matched_by) == 0:
                    status_badge = '<span style="background-color: #1e3a1e; color: #4ade80; border: 1px solid #2e7d32; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600;">Disponível</span>'
                elif len(matched_by) == 1:
                    status_badge = f'<span style="background-color: #1e293b; color: #38bdf8; border: 1px solid #1d4ed8; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600;">-> Lançamento #{matched_by[0]}</span>'
                else:
                    status_badge = f'<span style="background-color: #450a0a; color: #f87171; border: 1px solid #b91c1c; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600;">Duplicado (#{", ".join(map(str, matched_by))})</span>'
                
                st.markdown(
                    f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: 600; font-size: 0.95rem;">Lançamento #{idx_e}</span>
                        {status_badge}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                details_html = f"""
                <div style='font-size: 0.88rem; line-height: 1.45;'>
                    <b>Data:</b> {e_date}<br/>
                    <b>Descrição:</b> {e_desc}
                    {f'<br/><b>Doc:</b> {e_doc}' if e_doc else ''}
                </div>
                """
                st.markdown(details_html, unsafe_allow_html=True)

    # Validation: check for duplicate matches
    chosen_labels = [v for v in selections.values() if v != "Não conciliar / Manter aberto"]
    has_duplicates = len(chosen_labels) != len(set(chosen_labels))

    if has_duplicates:
        st.error("⚠️ Atenção: Cada linha do Extrato só pode ser selecionada uma vez!")

    col_btn_left, col_btn_right = st.columns([1, 1])
    with col_btn_left:
        # Button to confirm matches
        confirm_clicked = st.button("Confirmar Correspondências", type="primary", use_container_width=True, disabled=has_duplicates)
        
    if confirm_clicked:
        c_to_drop = []
        e_to_drop = []
        c_unmatched = []
        
        for idx_c, selected_label in selections.items():
            mapped_val = extrato_mapping[selected_label]
            if mapped_val == "Unmatched / Keep":
                c_unmatched.append(idx_c)
            else:
                c_to_drop.append(idx_c)
                e_to_drop.append(mapped_val)
                
        # 1. Handle matched ones (delete from both)
        if c_to_drop:
            st.session_state.df1_remaining = df1_rem.drop(index=c_to_drop)
        if e_to_drop:
            st.session_state.df2_remaining = df2_rem.drop(index=e_to_drop)
            
        # 2. Handle unmatched Contabilidade items:
        # "delete the row and add them to the list of unmatched items"
        if c_unmatched:
            # We append the unmatched rows to unmatched_df1
            st.session_state.unmatched_df1 = pd.concat([st.session_state.unmatched_df1, df1_rem.loc[c_unmatched]])
            # Drop them from active df1_remaining so they don't block the next stages
            st.session_state.df1_remaining = st.session_state.df1_remaining.drop(index=c_unmatched)
            
        st.toast("Correspondências processadas!", icon="✅")
        
        # Proceed
        advance_reconciliation()
        st.rerun()

    # Expander with raw complete tables for reference
    with st.expander("🔍 Visualizar tabelas completas em conflito", expanded=False):
        tab1, tab2 = st.tabs(["Contabilidade Completa", "Extrato Completo"])
        with tab1:
            st.dataframe(df1_rem.loc[c_indices], use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(df2_rem.loc[e_indices], use_container_width=True, hide_index=True)


elif st.session_state.reconciliation_results is not None:
    df1_final = st.session_state.reconciliation_results["df1_final"]
    df2_final = st.session_state.reconciliation_results["df2_final"]

    st.subheader("Resultados")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">Não Conciliado — Contabilidade</div>
                <div class="value">{len(df1_final)}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col_m2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">Não Conciliado — Extrato</div>
                <div class="value">{len(df2_final)}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.write("")  # spacer

    # --- Preview tables ---
    with st.expander("🔍 Pré-visualizar Linhas Não Conciliadas", expanded=False):
        tab1, tab2 = st.tabs(["Contabilidade Restante", "Extrato Restante"])
        with tab1:
            st.dataframe(df1_final, use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(df2_final, use_container_width=True, hide_index=True)

    # --- Download buttons ---
    st.write("")
    col_dl1, col_dl2 = st.columns(2)

    def to_excel_bytes(df):
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        return buf.getvalue()

    with col_dl1:
        st.download_button(
            label="⬇  Contabilidade Restante",
            data=to_excel_bytes(df1_final),
            file_name="contabilidade_restante.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_dl2:
        st.download_button(
            label="⬇  Extrato Restante",
            data=to_excel_bytes(df2_final),
            file_name="extrato_restante.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
