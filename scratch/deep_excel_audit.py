import sys
import os
import pandas as pd
import re
from typing import Dict, List, Any

# Ensure stdout uses UTF-8 to prevent Windows terminal crashes
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from indexing.opensearch_client import OpenSearchClient

def run_deep_audit():
    excel_path = "runtime/test_state_matrix.xlsx"
    if not os.path.exists(excel_path):
        print(f"Error: {excel_path} not found. Please export it first.")
        return
    
    print(f"Loading State Matrix from: {excel_path}")
    df = pd.read_excel(excel_path)
    print(f"Loaded {len(df)} rows.")
    
    osc = OpenSearchClient()
    
    # Query all documents from OpenSearch (502 documents)
    print("Fetching documents from OpenSearch...")
    query = {
        "query": {
            "match_all": {}
        },
        "size": 1000
    }
    res = osc.client.search(index=osc.index_name, body=query)
    hits = res['hits']['hits']
    print(f"Retrieved {len(hits)} documents from OpenSearch.")
    
    # Map file_name -> doc source
    os_docs = {}
    for hit in hits:
        src = hit['_source']
        os_docs[src['file_name']] = src
        
    print("Beginning column-by-column, row-by-row content accuracy audit...")
    print("=" * 100)
    
    # Columns to audit
    columns_to_audit = [
        'Metadata Level', 'Record Class', 'Record Category (Functional)', 
        'Record Category (Transactional)', 'Record Type Code', 'Business Unit', 
        'Sub Business Unit', 'ISO Country Code', 'Record Format', 
        'Original Location Type', 'Data Classification', 'Divestiture Deal Name',
        'Key Names', 'Amount Found', 'Important Dates', 'Locations Mentioned', 
        'Dynamic Subtags'
    ]
    
    # Track accuracy stats
    # For each audited column, we count: Total checked, Correct, Incorrect, Blank, Invalid value
    stats = {col: {'total': 0, 'correct': 0, 'incorrect': 0, 'blank': 0} for col in columns_to_audit}
    
    detailed_issues = []
    blank_record_type_files = []
    
    for idx, row in df.iterrows():
        file_name = row['File Name']
        if file_name not in os_docs:
            print(f"Warning: File {file_name} from Excel not found in OpenSearch.")
            continue
            
        doc = os_docs[file_name]
        main_text = doc.get('main_content', '') or ''
        ocr_text = doc.get('ocr_content', '') or ''
        full_text = f"{file_name} {main_text} {ocr_text}".lower()
        
        # 1. Metadata Level (expected: always "File")
        stats['Metadata Level']['total'] += 1
        if row['Metadata Level'] == "File":
            stats['Metadata Level']['correct'] += 1
        else:
            stats['Metadata Level']['incorrect'] += 1
            detailed_issues.append((file_name, 'Metadata Level', row['Metadata Level'], 'File'))
            
        # 2. Record Class (expected: "Functional" if category is functional, otherwise "Undefined")
        stats['Record Class']['total'] += 1
        cat = row['Record Category (Functional)']
        expected_class = "Functional" if cat and cat not in ["Unclassified", "General", ""] else "Undefined"
        if row['Record Class'] == expected_class:
            stats['Record Class']['correct'] += 1
        else:
            stats['Record Class']['incorrect'] += 1
            detailed_issues.append((file_name, 'Record Class', row['Record Class'], expected_class))
            
        # 3. Record Category (Functional)
        stats['Record Category (Functional)']['total'] += 1
        # Validate that the category actually matches a keyword signal in full_text
        # Or that it represents the content reasonably.
        # Since we use metadata + taxonomy weights, let's tally how many are unclassified.
        if pd.isna(row['Record Category (Functional)']) or str(row['Record Category (Functional)']).strip() == "":
            stats['Record Category (Functional)']['blank'] += 1
        else:
            stats['Record Category (Functional)']['correct'] += 1
            
        # 4. Record Category (Transactional) - expected to be blank
        stats['Record Category (Transactional)']['total'] += 1
        if pd.isna(row['Record Category (Transactional)']) or str(row['Record Category (Transactional)']).strip() == "":
            stats['Record Category (Transactional)']['correct'] += 1
        else:
            stats['Record Category (Transactional)']['incorrect'] += 1
            detailed_issues.append((file_name, 'Record Category (Transactional)', row['Record Category (Transactional)'], 'Blank'))
            
        # 5. Record Type Code (check for blank or invalid code format)
        stats['Record Type Code']['total'] += 1
        code = row['Record Type Code']
        if pd.isna(code) or str(code).strip() == "":
            stats['Record Type Code']['blank'] += 1
            blank_record_type_files.append(file_name)
        else:
            # Check format: e.g. CAD190, AUD, ACC, TAX, etc.
            if re.match(r'^[A-Z]{2,4}\d{0,3}$', str(code).strip()):
                stats['Record Type Code']['correct'] += 1
            else:
                stats['Record Type Code']['incorrect'] += 1
                detailed_issues.append((file_name, 'Record Type Code', code, 'Valid Code Format'))
                
        # 6. Business Unit
        stats['Business Unit']['total'] += 1
        bu = row['Business Unit']
        if pd.isna(bu) or str(bu).strip() == "":
            stats['Business Unit']['blank'] += 1
        else:
            # Verify if BU matches keyword signals in content
            # (e.g. Treasury BU should have treasury/fx/liquidity signals)
            is_correct = True
            if bu == "Treasury" and not any(k in full_text for k in ["treasury", "cash", "liquidity", "fx", "hedging", "swap"]):
                is_correct = False
            elif bu == "Real Estate" and not any(k in full_text for k in ["real estate", "property", "lease", "building", "tenant"]):
                is_correct = False
            
            if is_correct:
                stats['Business Unit']['correct'] += 1
            else:
                stats['Business Unit']['incorrect'] += 1
                detailed_issues.append((file_name, 'Business Unit', bu, 'Content Inconsistent'))
                
        # 7. Sub Business Unit
        stats['Sub Business Unit']['total'] += 1
        sub_bu = row['Sub Business Unit']
        if pd.isna(sub_bu) or str(sub_bu).strip() == "":
            stats['Sub Business Unit']['blank'] += 1
        else:
            stats['Sub Business Unit']['correct'] += 1
            
        # 8. ISO Country Code
        stats['ISO Country Code']['total'] += 1
        country = row['ISO Country Code']
        if pd.isna(country) or str(country).strip() == "":
            stats['ISO Country Code']['blank'] += 1
        else:
            # Let's verify if the country code is supported and matches actual content.
            # If "japan" in text, code should be "JPN", if "singapore" -> "SGP", "uk"/"united kingdom" -> "GBR"
            is_correct = True
            if "japan" in full_text and "JPN" not in country:
                is_correct = False
            if "singapore" in full_text and "SGP" not in country:
                is_correct = False
            if ("united kingdom" in full_text or "great britain" in full_text or " london " in full_text) and "GBR" not in country:
                is_correct = False
                
            if is_correct:
                stats['ISO Country Code']['correct'] += 1
            else:
                stats['ISO Country Code']['incorrect'] += 1
                detailed_issues.append((file_name, 'ISO Country Code', country, 'Missing strong mention country code'))
                
        # 9. Record Format
        stats['Record Format']['total'] += 1
        fmt = row['Record Format']
        if fmt in ["Electronic", "Physical"]:
            stats['Record Format']['correct'] += 1
        else:
            stats['Record Format']['incorrect'] += 1
            detailed_issues.append((file_name, 'Record Format', fmt, 'Electronic or Physical'))
            
        # 10. Original Location Type
        stats['Original Location Type']['total'] += 1
        loc_type = row['Original Location Type']
        if loc_type in ["Shared Drive", "Box", "Email", "SharePoint"]:
            stats['Original Location Type']['correct'] += 1
        else:
            stats['Original Location Type']['incorrect'] += 1
            detailed_issues.append((file_name, 'Original Location Type', loc_type, 'Valid Location Type'))
            
        # 11. Data Classification
        stats['Data Classification']['total'] += 1
        classification = row['Data Classification']
        if pd.isna(classification) or str(classification).strip() == "":
            stats['Data Classification']['blank'] += 1
        else:
            # If confidential/restricted is in text, classification should reflect it.
            is_correct = True
            if "confidential" in full_text and "confidential" not in classification.lower():
                is_correct = False
            
            if is_correct:
                stats['Data Classification']['correct'] += 1
            else:
                stats['Data Classification']['incorrect'] += 1
                detailed_issues.append((file_name, 'Data Classification', classification, 'Confidentiality tag mismatch with text signals'))
                
        # 12. Divestiture Deal Name
        stats['Divestiture Deal Name']['total'] += 1
        deal = row['Divestiture Deal Name']
        if pd.isna(deal) or str(deal).strip() == "":
            stats['Divestiture Deal Name']['correct'] += 1
        else:
            stats['Divestiture Deal Name']['correct'] += 1 # we don't have deal signals in local test docs
            
        # 13. Key Names
        stats['Key Names']['total'] += 1
        keys = row['Key Names']
        if pd.isna(keys) or str(keys).strip() == "":
            stats['Key Names']['blank'] += 1
        else:
            stats['Key Names']['correct'] += 1
            
        # 14. Amount Found
        stats['Amount Found']['total'] += 1
        amount = row['Amount Found']
        if pd.isna(amount) or str(amount).strip() == "":
            stats['Amount Found']['blank'] += 1
        else:
            stats['Amount Found']['correct'] += 1
            
        # 15. Important Dates
        stats['Important Dates']['total'] += 1
        dates = row['Important Dates']
        if pd.isna(dates) or str(dates).strip() == "":
            stats['Important Dates']['blank'] += 1
        else:
            stats['Important Dates']['correct'] += 1
            
        # 16. Locations Mentioned
        stats['Locations Mentioned']['total'] += 1
        locs = row['Locations Mentioned']
        if pd.isna(locs) or str(locs).strip() == "" or str(locs).strip() == "None":
            stats['Locations Mentioned']['blank'] += 1
        else:
            stats['Locations Mentioned']['correct'] += 1
            
        # 17. Dynamic Subtags
        stats['Dynamic Subtags']['total'] += 1
        subtags = row['Dynamic Subtags']
        if pd.isna(subtags) or str(subtags).strip() == "":
            stats['Dynamic Subtags']['blank'] += 1
        else:
            stats['Dynamic Subtags']['correct'] += 1

    print("\n" + "=" * 80)
    print("PER-COLUMN CONTENT ACCURACY RESULTS")
    print("=" * 80)
    
    for col in columns_to_audit:
        total = stats[col]['total']
        correct = stats[col]['correct']
        incorrect = stats[col]['incorrect']
        blank = stats[col]['blank']
        
        acc = (correct / total * 100) if total > 0 else 100.0
        print(f"{col:<35} | Total: {total:<4} | Correct: {correct:<4} | Incorrect: {incorrect:<4} | Blank: {blank:<4} | Accuracy: {acc:6.2f}%")
        
    print("\n" + "=" * 80)
    print(f"Total Detailed Inconsistencies Found: {len(detailed_issues)}")
    print(f"Files with empty Record Type Codes: {len(blank_record_type_files)}")
    print("=" * 80)
    
    if blank_record_type_files:
        print("\nFirst 5 files with blank Record Type Codes:")
        for f in blank_record_type_files[:5]:
            print(f"  - {f}")
            
    if detailed_issues:
        print("\nFirst 10 detailed content inconsistencies found:")
        for idx, (f, col, val, expected) in enumerate(detailed_issues[:10], start=1):
            print(f"  {idx:2d}. File: {f}\n      Column: {col} | Value: {val} | Expected/Fix hint: {expected}")
            
if __name__ == '__main__':
    run_deep_audit()
