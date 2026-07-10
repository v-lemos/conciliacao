import pandas as pd
from file_process import clean_float

def conciliate_c_e(df1, df2, debito_col, credito_col, file2_col):
    """
    Reconciles Contabilidade to Extrato:
    For each row in Contabilidade, looks for matching value in Extrato:
      - If Débito is non-zero (V), looks for -V in Extrato.
      - If Crédito is non-zero (V), looks for V in Extrato.
    Drops matched rows from both dataframes.
    """
    df1_remaining = df1.copy()
    df2_remaining = df2.copy()
    
    indices_to_drop_df1 = []
    indices_to_drop_df2 = []
    
    for idx1, row1 in df1_remaining.iterrows():
        D = clean_float(row1[debito_col])
        C = clean_float(row1[credito_col])
        
        if D != 0:
            target_val = D
        elif C != 0:
            target_val = -C
        else:
            continue
            
        target_val_rounded = round(target_val, 2)
        
        # Search for target_val_rounded in df2
        match_idx2 = None
        for idx2, row2 in df2_remaining.iterrows():
            if idx2 in indices_to_drop_df2:
                continue
            val2 = clean_float(row2[file2_col])
            if round(val2, 2) == target_val_rounded:
                match_idx2 = idx2
                break
                
        if match_idx2 is not None:
            indices_to_drop_df1.append(idx1)
            indices_to_drop_df2.append(match_idx2)
            
    return df1_remaining.drop(indices_to_drop_df1), df2_remaining.drop(indices_to_drop_df2)