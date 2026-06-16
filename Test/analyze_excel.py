import pandas as pd
import glob
import os

# Find the latest state matrix file
list_of_files = glob.glob('c:/Users/DELL/Downloads/DocumentSearch_v7/DocumentSearch_v6/DocumentSearch_v5/DocumentSearch/runtime/audit/state_matrix_*.xlsx')
if not list_of_files:
    print("No state matrix files found.")
else:
    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"Analyzing: {latest_file}")
    
    try:
        df = pd.read_excel(latest_file)
        
        # Check Current Status
        if 'Current Status' in df.columns:
            print("\nCurrent Status Counts:")
            print(df['Current Status'].value_counts())
            
        # Check for empty/unknown tags in specific columns
        tag_columns = ['Category', 'Department', 'Purpose', 'Confidentiality']
        print("\nTagging Quality (Null/Empty/Unknown counts):")
        for col in tag_columns:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                unknown_count = df[col].astype(str).str.contains('Unknown', case=False, na=False).sum()
                print(f"{col}: Nulls={null_count}, 'Unknown'={unknown_count}")
                if unknown_count > 0:
                     print(f"   Sample {col} values: {df[col].dropna().unique()[:5]}")

    except Exception as e:
        print(f"Error reading file: {e}")
