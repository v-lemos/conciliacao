import os
import pandas as pd
from conciliate import conciliate_c_e

def get_valid_excel_path(prompt):
    """
    Normalizes and validates the file path.
    """
    while True:
        path = input(prompt).strip()
        # Remove surrounding quotes
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]

        if not path:
            print("Path cannot be empty. Please try again.")
            continue

        if not os.path.exists(path):
            print(f"Error: The path '{path}' does not exist. Please check the spelling.")
            continue

        if not os.path.isfile(path):
            print(f"Error: '{path}' is a directory, not a file.")
            continue

        if not (path.endswith('.xlsx') or path.endswith('.xls') or path.endswith('.xlsm') or path.endswith('.xlsb')):
            print(
                "Warning: The file extension does not match a standard Excel format (e.g., .xlsx). Attempting to open anyway...")

        return path

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


def select_column_from_extrato(file_path):
    """
    Loads headers from the raw Extrato Bancário file (without dropping rows or auto-finding headers)
    and prompts the user to select a column via a numbered list in the terminal.
    """
    try:
        # Load raw file headers from row 0
        df_preview = pd.read_excel(file_path, nrows=0)
        available_columns = list(df_preview.columns)
    except Exception as e:
        print(f"Error reading file headers: {e}")
        return None

    if not available_columns:
        print("Error: Excel file seems to have no columns/headers.")
        return None

    while True:
        print(f"\nAvailable columns in {os.path.basename(file_path)}:")
        for idx, col in enumerate(available_columns, 1):
            print(f"  [{idx}] {col}")
            
        try:
            choice = input(f"Select the column header number (1-{len(available_columns)}): ").strip()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_columns):
                selected_col = available_columns[choice_idx]
                print(f"Selected column: '{selected_col}'\n")
                return selected_col
            else:
                print(f"Error: Selection must be between 1 and {len(available_columns)}.")
        except ValueError:
            print("Error: Please enter a valid number.")

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


def process_excel_files(file1_path, file2_path, file2_col):
    """
    Handles all the logic of reading and processing the Excel files.
    """
    print("\nReading files, please wait...")
    try:
        # File 1 (Contabilidade) uses the auto-header row finder
        df1 = load_excel_and_find_header(file1_path)
        print(f"Successfully loaded File 1 (Contabilidade): {os.path.basename(file1_path)} (Shape: {df1.shape})")
        
        # Find actual column names for Débito and Crédito in df1
        debito_col = next((c for c in df1.columns if str(c).strip().lower() in ['débito', 'debito']), None)
        credito_col = next((c for c in df1.columns if str(c).strip().lower() in ['crédito', 'credito']), None)
        
        if not debito_col or not credito_col:
            raise ValueError(f"Could not find columns named 'Débito' and 'Crédito' in Contabilidade file. Found: {list(df1.columns)}")
        
        # File 2 (Extrato) reads normally without auto-finding / dropping rows
        df2 = pd.read_excel(file2_path)
        print(f"Successfully loaded File 2 (Extrato Bancário): {os.path.basename(file2_path)} (Shape: {df2.shape})")
        
        # Verify the column header exists in the second file (Extrato Bancário)
        if file2_col not in df2.columns:
            print(f"Error: Column '{file2_col}' was not found in the Extrato Bancário file.")
            print(f"Available columns: {list(df2.columns)}")
            return None, None
            
        print(f"Validated Extrato Bancário column: '{file2_col}'")
        
        # Perform reconciliation (Contabilidade -> Extrato)
        print("\nRunning reconciliation (Contabilidade -> Extrato)...")
        df1_final, df2_final = conciliate_c_e(df1, df2, debito_col, credito_col, file2_col)
        print(f"Remaining - Contabilidade: {len(df1_final)} rows, Extrato: {len(df2_final)} rows")
        
        return df1_final, df2_final
        
    except Exception as e:
        print(f"\nAn error occurred while loading or conciliating the Excel files: {e}")
        return None, None





