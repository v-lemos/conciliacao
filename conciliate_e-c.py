import pandas as pd
from file_process import clean_float

def conciliate_e_c(df1, df2, debito_col, credito_col, file2_col):
    """
    Reconciles Extrato to Contabilidade:
    For each remaining row in Extrato:
      - If value is negative (V < 0), looks for |V| in Contabilidade Débito.
      - If value is positive (V > 0), looks for V in Contabilidade Crédito.
    Drops matched rows from both dataframes.
    """
    df1_remaining = df1.copy()
    df2_remaining = df2.copy()
    
    indices_to_drop_df1 = []
    indices_to_drop_df2 = []
    
    for idx2, row2 in df2_remaining.iterrows():
        E = clean_float(row2[file2_col])
        if E == 0:
            continue
            
        target_val = abs(E)
        target_val_rounded = round(target_val, 2)
        
        match_idx1 = None
        for idx1, row1 in df1_remaining.iterrows():
            if idx1 in indices_to_drop_df1:
                continue
                
            if E < 0:
                val1 = clean_float(row1[credito_col])
            else:
                val1 = clean_float(row1[debito_col])
                
            if round(val1, 2) == target_val_rounded:
                match_idx1 = idx1
                break
                
        if match_idx1 is not None:
            indices_to_drop_df1.append(match_idx1)
            indices_to_drop_df2.append(idx2)
            
    return df1_remaining.drop(indices_to_drop_df1), df2_remaining.drop(indices_to_drop_df2)
