import os
from file_process import process_excel_files, get_valid_excel_path, select_column_from_extrato

def main():
    print("=" * 49)
    print("         Conciliação Console Interface         ")
    print("=" * 49)
    
    # 1. Contabilidade path (now first)
    file1_path = get_valid_excel_path("Enter the path for Contabilidade file: ")
    
    # 2. Extrato Bancário path (now second)
    file2_path = get_valid_excel_path("Enter the path for Extrato Bancário file: ")

    # Load Extrato Bancário (file2) headers and select column
    file2_col = select_column_from_extrato(file2_path)
    if not file2_col:
        print("Could not retrieve a column header from the file. Exiting.")
        return

    # Delegate the processing/reading of the files to file_process
    df1_left, df2_left = process_excel_files(file1_path, file2_path, file2_col)
    
    if df1_left is not None and df2_left is not None:
        print("\n" + "=" * 49)
        print("             Reconciliation Complete             ")
        print("=" * 49)
        print(f"Unreconciled rows in Contabilidade: {len(df1_left)}")
        print(f"Unreconciled rows in Extrato Bancário: {len(df2_left)}")
        
        # Save results to new Excel files
        out1_path = "contabilidade_restante.xlsx"
        out2_path = "extrato_restante.xlsx"
        
        try:
            df1_left.to_excel(out1_path, index=False)
            df2_left.to_excel(out2_path, index=False)
            print(f"\nRemaining rows successfully saved to:")
            print(f"  - {out1_path}")
            print(f"  - {out2_path}")
        except Exception as e:
            print(f"Warning: Could not save output Excel files: {e}")
            
        return df1_left, df2_left
    else:
        print("\nReconciliation failed due to an error.")
        return None, None

if __name__ == "__main__":
    main()





