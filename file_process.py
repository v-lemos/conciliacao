import os
import pandas as pd

def load_excel_and_find_header(file_path):
    """
    Reads an Excel file, searches row-by-row until it finds a row containing both
    'Débito' and 'Crédito' (case-insensitive), and sets that row as the header,
    dropping all rows above it. It also drops any completely empty rows.
    """
    # Read without headers initially so we can inspect row-by-row
    df_raw = pd.read_excel(file_path, header=None)
    
    header_row_idx = None
    for idx, row in df_raw.iterrows():
        # Convert row values to strings, clean up, and search
        row_str_values = [str(val).strip().lower() for val in row.values if pd.notna(val)]
        
        # Check if both "débito" (or "debito") and "crédito" (or "credito") exist in this row
        has_debito = any("débito" in val or "debito" in val for val in row_str_values)
        has_credito = any("crédito" in val or "credito" in val for val in row_str_values)
        
        if has_debito and has_credito:
            header_row_idx = idx
            break
            
    if header_row_idx is None:
        raise ValueError(f"Could not find a row containing both 'Débito' and 'Crédito' headers in {os.path.basename(file_path)}.")
        
    # Re-read the file setting the correct header row
    df = pd.read_excel(file_path, header=header_row_idx)
    
    # Drop rows that are completely empty (all elements are NaN)
    df.dropna(how='all', inplace=True)
    
    return df


def clean_float(val):
    """
    Cleans and converts Excel cell values (including formatted strings) to floats.
    """
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    s = str(val).strip()
    if not s:
        return 0.0
    
    # Check for European number formatting (e.g. 1.234,56)
    if ',' in s:
        if '.' in s:
            if s.find('.') < s.find(','):
                s = s.replace('.', '')
        s = s.replace(',', '.')
        
    # Remove any non-numeric characters except negative/positive sign and decimal dot
    s = ''.join(c for c in s if c.isdigit() or c in ['-', '.', '+'])
    
    try:
        return float(s)
    except ValueError:
        return 0.0






