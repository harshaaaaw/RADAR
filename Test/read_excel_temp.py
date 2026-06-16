import pandas as pd
import os

file_path = r"c:\Users\DELL\Downloads\2026.02.04 - TP2 Search Criteria - Consolidated version.xlsx"

try:
    print(f"Attempting to read: {file_path}")
    if not os.path.exists(file_path):
        print("File does not exist!")
    
    # Read all sheets
    xls = pd.ExcelFile(file_path)
    sheet_names = xls.sheet_names
    print(f"File found. Sheets: {sheet_names}")

    for sheet_name in sheet_names:
        print(f"\n--- Sheet: {sheet_name} ---")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Print columns and some rows
        print(f"Columns: {list(df.columns)}")
        print("First 50 rows:")
        print(df.head(50).to_string())
        
        # Print info about content
        print(f"\nTotal rows: {len(df)}")
        
except ImportError as e:
    print(f"ImportError: {e}. Please install openpyxl or pandas.")
except Exception as e:
    print(f"Error reading file: {e}")
