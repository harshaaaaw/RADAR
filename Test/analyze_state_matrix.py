"""Read and analyze the State Matrix Export Excel to validate all columns and tags."""
import openpyxl
import pandas as pd

EXCEL_PATH = r"state_matrix_RETAGGED.xlsx"

print(f"Reading: {EXCEL_PATH}")
df = pd.read_excel(EXCEL_PATH, engine='openpyxl')

print(f"\n{'='*80}")
print(f"STATE MATRIX EXPORT ANALYSIS")
print(f"{'='*80}")
print(f"Rows: {len(df)}")
print(f"Columns ({len(df.columns)}):")
for i, col in enumerate(df.columns, 1):
    dtype = df[col].dtype
    non_null = df[col].notna().sum()
    null_count = df[col].isna().sum()
    unique = df[col].nunique()
    print(f"  {i:2d}. {col:<40s} | dtype={str(dtype):<10s} | non-null={non_null:3d} | null={null_count:3d} | unique={unique:3d}")

print(f"\n{'='*80}")
print(f"COLUMN VALUE SAMPLES (first 3 unique values per column)")
print(f"{'='*80}")
for col in df.columns:
    vals = df[col].dropna().unique()[:5]
    vals_str = [str(v)[:80] for v in vals]
    print(f"\n  {col}:")
    for v in vals_str:
        print(f"    - {v}")

# Detailed tagging analysis
print(f"\n{'='*80}")
print(f"TAGGING COLUMNS ANALYSIS")
print(f"{'='*80}")

# Look for typical tagging columns
tag_columns = [col for col in df.columns if any(kw in col.lower() for kw in 
    ['tag', 'category', 'entity', 'date', 'key', 'person', 'org', 'location', 'topic',
     'department', 'type', 'class', 'label', 'important', 'name', 'nlp'])]

if tag_columns:
    print(f"\nFound {len(tag_columns)} tag-related columns:")
    for col in tag_columns:
        print(f"\n  >>> {col} <<<")
        vals = df[col].dropna()
        print(f"      Filled: {len(vals)}/{len(df)} ({100*len(vals)/len(df):.1f}%)")
        value_counts = df[col].value_counts().head(10)
        for val, count in value_counts.items():
            print(f"      {count:3d}x  {str(val)[:100]}")
else:
    print("\n  No tag-related columns found by keyword match.")
    print("  All columns:")
    for col in df.columns:
        print(f"    - {col}")

# Check for columns with suspicious values
print(f"\n{'='*80}")
print(f"DATA QUALITY CHECKS")
print(f"{'='*80}")

for col in df.columns:
    issues = []
    vals = df[col].dropna()
    
    # Check for empty strings
    if vals.dtype == 'object':
        empty_str = (vals == '').sum()
        if empty_str > 0:
            issues.append(f"{empty_str} empty strings")
        
        # Check for 'None' or 'nan' as string
        none_str = vals.isin(['None', 'nan', 'null', 'N/A']).sum()
        if none_str > 0:
            issues.append(f"{none_str} string-null values")
        
        # Check for very long values
        max_len = vals.astype(str).str.len().max() if len(vals) > 0 else 0
        if max_len > 500:
            issues.append(f"max length {max_len} chars")
        
        # Check for JSON-like values (lists/dicts as strings)
        json_like = vals.astype(str).str.match(r'^\[.*\]$|^\{.*\}$').sum() if len(vals) > 0 else 0
        if json_like > 0:
            issues.append(f"{json_like} JSON-like values")
    
    if issues:
        print(f"  {col}: {', '.join(issues)}")

# Full dump of first 3 rows
print(f"\n{'='*80}")
print(f"FIRST 3 ROWS (full content)")
print(f"{'='*80}")
for idx in range(min(3, len(df))):
    print(f"\n--- Row {idx+1} ---")
    for col in df.columns:
        val = df.iloc[idx][col]
        val_str = str(val) if pd.notna(val) else '<NULL>'
        if len(val_str) > 200:
            val_str = val_str[:200] + '...'
        print(f"  {col}: {val_str}")
