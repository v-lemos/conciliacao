import streamlit as st
import pandas as pd
import os
import io
from file_process import load_excel_and_find_header, clean_float
# Import reconciliation functions
from conciliate import conciliate_c_e, find_next_reconciliation_step

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

    /* Section dividers */
    hr {
        border: none;
        border-top: 1px solid #e9ecef;
        margin: 1.5rem 0;
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

# --- Header ---
st.markdown("""
<div class="main-title">
    <h1>🏦 Conciliação Bancária</h1>
    <p>Upload your files, pick the value column, and reconcile.</p>
</div>
""", unsafe_allow_html=True)

st.divider()

# --- File uploads ---
col_up1, col_up2 = st.columns(2)

with col_up1:
    st.markdown("**Contabilidade**")
    file1 = st.file_uploader(
        "Upload the Contabilidade file",
        type=["xlsx", "xls", "xlsm", "xlsb"],
        accept_multiple_files=False,
        key="contabilidade",
        label_visibility="collapsed",
        on_change=clear_results,
    )

with col_up2:
    st.markdown("**Extrato Bancário**")
    file2 = st.file_uploader(
        "Upload the Extrato Bancário file",
        type=["xlsx", "xls", "xlsm", "xlsb"],
        accept_multiple_files=False,
        key="extrato",
        label_visibility="collapsed",
        on_change=clear_results,
    )

# --- File Preview Section ---
if file1 is not None or file2 is not None:
    st.divider()
    with st.expander("🔍 Preview Uploaded Files", expanded=False):
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
                    st.dataframe(df1_preview, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Could not read Contabilidade preview: {e}")
            else:
                st.info("Upload a Contabilidade file to view its preview.")
                
        with tab2:
            if file2 is not None:
                try:
                    file2.seek(0)
                    df2_preview = pd.read_excel(file2)
                    file2.seek(0)
                    st.dataframe(df2_preview, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Could not read Extrato preview: {e}")
            else:
                st.info("Upload an Extrato file to view its preview.")

# --- Column picker for Extrato (only shown when file2 is uploaded) ---
file2_col = None
if file2 is not None:
    try:
        df_preview = pd.read_excel(file2, nrows=0)
        available_columns = list(df_preview.columns)
        # Reset the file pointer so it can be read again later
        file2.seek(0)

        if available_columns:
            st.divider()
            st.markdown("**Select the value column from the Extrato file**")
            
            # Find if any available column matches a preferred label
            preferred_index = None
            for idx, col in enumerate(available_columns):
                if str(col).strip() in PREFERRED_LABELS:
                    preferred_index = idx
                    break
            
            file2_col = st.selectbox(
                "Column",
                options=available_columns,
                index=preferred_index,
                placeholder="Choose the value column...",
                label_visibility="collapsed",
                on_change=clear_results,
            )
        else:
            st.warning("The Extrato file has no column headers.")
    except Exception as e:
        st.error(f"Could not read Extrato file headers: {e}")

# --- Run button ---
st.divider()
can_run = file1 is not None and file2 is not None and file2_col is not None
run_clicked = st.button("▶  Run Reconciliation", disabled=not can_run, use_container_width=True, type="primary")

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
    with st.spinner("Reading and reconciling files…"):
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
                st.error(f"Could not find 'Débito' and 'Crédito' columns in Contabilidade. Found: {list(df1.columns)}")
                st.stop()

            # 2. Load Extrato
            df2 = pd.read_excel(file2)

            if file2_col not in df2.columns:
                st.error(f"Column '{file2_col}' not found in the Extrato file.")
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
            st.error(f"An error occurred during reconciliation: {e}")
            st.stop()

# --- Results or Conflict UI ---
if st.session_state.reconciliation_stage == "conflict":
    st.divider()
    st.markdown('<h3 style="color:#f39c12; margin-top:0;">⚠️ Match Conflict Group</h3>', unsafe_allow_html=True)
    
    conflict = st.session_state.current_conflict
    val = conflict["value"]
    c_indices = conflict["c_indices"]
    e_indices = conflict["e_indices"]
    
    df1_rem = st.session_state.df1_remaining
    df2_rem = st.session_state.df2_remaining
    debito_col = st.session_state.debito_col
    credito_col = st.session_state.credito_col
    file2_col = st.session_state.file2_col

    st.info(f"Múltiplas transações encontradas com o valor correspondente a **{val}**. Contabilidade: **{len(c_indices)}** linhas vs Extrato: **{len(e_indices)}** linhas. Faça a correspondência individual abaixo:")

    col_c, col_e = st.columns(2)
    with col_c:
        st.markdown("**Contabilidade:**")
        st.dataframe(df1_rem.loc[c_indices], use_container_width=True, hide_index=True)
    with col_e:
        st.markdown("**Extrato:**")
        st.dataframe(df2_rem.loc[e_indices], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**Selecione a linha correspondente do Extrato para cada linha da Contabilidade:**")

    # Pre-format Extrato options
    extrato_options = ["Unmatched / Keep"]
    extrato_mapping = {}
    for idx_e in e_indices:
        row = df2_rem.loc[idx_e]
        parts = []
        for col, cell_val in row.items():
            if pd.notna(cell_val) and str(cell_val).strip() != "":
                parts.append(f"{col}: {cell_val}")
        option_label = f"Linha {idx_e} — " + " | ".join(parts[:5])
        extrato_options.append(option_label)
        extrato_mapping[option_label] = idx_e

    selections = {}
    for idx_c in c_indices:
        row_c = df1_rem.loc[idx_c]
        parts_c = []
        for col, cell_val in row_c.items():
            if pd.notna(cell_val) and str(cell_val).strip() != "":
                parts_c.append(f"{col}: {cell_val}")
        row_c_summary = f"Contabilidade {idx_c} — " + " | ".join(parts_c[:5])
        
        selected = st.selectbox(
            f"Corresponde a ({row_c_summary}):",
            options=extrato_options,
            key=f"match_group_{val}_{idx_c}"
        )
        selections[idx_c] = selected

    # Validation: check for duplicate matches
    chosen_labels = [v for v in selections.values() if v != "Unmatched / Keep"]
    has_duplicates = len(chosen_labels) != len(set(chosen_labels))

    if has_duplicates:
        st.error("⚠️ Cada linha do Extrato só pode ser selecionada uma vez!")

    if st.button("Confirmar Correspondências", type="primary", use_container_width=True, disabled=has_duplicates):
        c_to_drop = []
        e_to_drop = []
        c_unmatched = []
        
        for idx_c, selected_label in selections.items():
            if selected_label == "Unmatched / Keep":
                c_unmatched.append(idx_c)
            else:
                chosen_idx_e = extrato_mapping[selected_label]
                c_to_drop.append(idx_c)
                e_to_drop.append(chosen_idx_e)
                
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

elif st.session_state.reconciliation_results is not None:
    df1_final = st.session_state.reconciliation_results["df1_final"]
    df2_final = st.session_state.reconciliation_results["df2_final"]

    st.divider()
    st.subheader("Results")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">Unreconciled — Contabilidade</div>
                <div class="value">{len(df1_final)}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col_m2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">Unreconciled — Extrato</div>
                <div class="value">{len(df2_final)}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.write("")  # spacer

    # --- Preview tables ---
    with st.expander("🔍 Preview Unreconciled Rows", expanded=False):
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
            label="⬇  Contabilidade restante",
            data=to_excel_bytes(df1_final),
            file_name="contabilidade_restante.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_dl2:
        st.download_button(
            label="⬇  Extrato restante",
            data=to_excel_bytes(df2_final),
            file_name="extrato_restante.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
