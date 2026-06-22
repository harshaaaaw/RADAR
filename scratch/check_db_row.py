import sqlite3
import json

def main():
    db_path = r"C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        row = conn.execute('SELECT * FROM file_state WHERE file_name="real_funsd_form_001.pdf"').fetchone()
        if row:
            print("=== File Info ===")
            print(f"File Name: {row['file_name']}")
            print(f"Smart ID: {row['smart_id']}")
            print(f"Approval Status: {row['approval_status']}")
            print(f"Extraction Accuracy: {row['extraction_accuracy']}")
            print(f"Enhanced Accuracy: {row['enhanced_accuracy']}")
            print(f"Pipeline Type: {row['pipeline_type']}")
            print(f"Accuracy Loss: {json.dumps(json.loads(row['accuracy_loss_json']), indent=2)}")
            print(f"Page Metrics: {row['page_metrics_json']}")
        else:
            print("No record found.")
            
    except Exception as exc:
        print(f"Failed: {exc}")

if __name__ == "__main__":
    main()
