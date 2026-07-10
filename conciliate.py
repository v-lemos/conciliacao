import pandas as pd
from file_process import clean_float

def group_matches_by_value(df1, df2, debito_col, credito_col, file2_col):
    """
    Groups df1 and df2 index labels by their matching target rounded values.
    """
    c_groups = {}
    for idx1 in df1.index:
        row1 = df1.loc[idx1]
        D = clean_float(row1[debito_col])
        C = clean_float(row1[credito_col])
        if D != 0:
            val = D
        elif C != 0:
            val = -C
        else:
            continue
        val_rounded = round(val, 2)
        c_groups.setdefault(val_rounded, []).append(idx1)
        
    e_groups = {}
    for idx2 in df2.index:
        row2 = df2.loc[idx2]
        val2 = clean_float(row2[file2_col])
        val_rounded = round(val2, 2)
        e_groups.setdefault(val_rounded, []).append(idx2)
        
    return c_groups, e_groups

def find_next_reconciliation_step(df1, df2, debito_col, credito_col, file2_col):
    """
    Scans df1 and df2 for matching transaction groups:
    1. Groups rows by matching numeric values (respecting signs).
    2. Auto-reconciles groups with equal counts of records in both Contabilidade and Extrato.
    3. Identifies the first value where the counts differ (conflict group) and returns it.
    4. If no conflict groups exist, returns status "done".
    
    Returns:
      - (df1_updated, df2_updated, "done", None)
      - (df1_updated, df2_updated, "conflict", {"value": val, "c_indices": c_indices, "e_indices": e_indices})
    """
    df1_remaining = df1.copy()
    df2_remaining = df2.copy()
    
    # Pass 1: Auto-reconcile identical counts groups
    while True:
        c_groups, e_groups = group_matches_by_value(df1_remaining, df2_remaining, debito_col, credito_col, file2_col)
        
        to_drop_df1 = []
        to_drop_df2 = []
        
        for val, c_indices in c_groups.items():
            e_indices = e_groups.get(val, [])
            if len(e_indices) > 0 and len(c_indices) == len(e_indices):
                to_drop_df1.extend(c_indices)
                to_drop_df2.extend(e_indices)
                
        if not to_drop_df1:
            break
            
        df1_remaining.drop(index=to_drop_df1, inplace=True)
        df2_remaining.drop(index=to_drop_df2, inplace=True)
        
    # Pass 2: Find the first conflict group (len(c_indices) != len(e_indices) and both > 0)
    c_groups, e_groups = group_matches_by_value(df1_remaining, df2_remaining, debito_col, credito_col, file2_col)
    for val, c_indices in c_groups.items():
        e_indices = e_groups.get(val, [])
        if len(e_indices) > 0 and len(c_indices) != len(e_indices):
            return df1_remaining, df2_remaining, "conflict", {
                "value": val,
                "c_indices": c_indices,
                "e_indices": e_indices
            }
            
    return df1_remaining, df2_remaining, "done", None