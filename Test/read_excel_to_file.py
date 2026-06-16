import sys
import os
import pandas as pd

file_path = r"c:\Users\DELL\Downloads\2026.02.04 - TP2 Search Criteria - Consolidated version.xlsx"
output_file = "excel_content_utf8.txt"

try:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Python started\n")
        
        if os.path.exists(file_path):
            f.write("File exists\n")
        else:
            f.write("File NOT found\n")
            sys.exit(1)

        f.write("Reading Excel file...\n")
        xls = pd.ExcelFile(file_path)
        f.write("ExcelFile object created\n")
        
        sheet_names = xls.sheet_names
        f.write(f"Sheets: {sheet_names}\n")

        for sheet_name in sheet_names:
            f.write(f"\n--- Sheet: {sheet_name} ---\n")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            f.write("Dataframe read\n")
            f.write(df.to_string())
            f.write("\n")
            
    print(f"Written to {output_file}")
        
except Exception as e:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Error: {e}\n")
    print(f"Error: {e}")
