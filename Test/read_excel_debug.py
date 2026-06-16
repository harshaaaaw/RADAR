import sys
print("Python started")
import os
print("Imported os")
import pandas as pd
print("Imported pandas")

file_path = r"c:\Users\DELL\Downloads\2026.02.04 - TP2 Search Criteria - Consolidated version.xlsx"
print(f"Path defined: {file_path}")

try:
    if os.path.exists(file_path):
        print("File exists")
    else:
        print("File NOT found")
        sys.exit(1)

    print("Reading Excel file...")
    xls = pd.ExcelFile(file_path)
    print("ExcelFile object created")
    
    sheet_names = xls.sheet_names
    print(f"Sheets: {sheet_names}")

    for sheet_name in sheet_names:
        print(f"\n--- Sheet: {sheet_name} ---")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print("Dataframe read")
        print(df.to_string())
        
except Exception as e:
    print(f"Error: {e}")
