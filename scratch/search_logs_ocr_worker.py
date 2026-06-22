log_path = 'runtime/logs/ocr.worker.log'
lines = []
with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Print lines around the time real_funsd_form_011.pdf was processed
for i, line in enumerate(lines):
    if 'real_funsd_form_011.pdf' in line:
        start = max(0, i - 15)
        end = min(len(lines), i + 15)
        print(f"\n--- Log lines around 'real_funsd_form_011.pdf' (line {i+1}) ---")
        for j in range(start, end):
            print(f"{j+1}: {lines[j].strip()}")
