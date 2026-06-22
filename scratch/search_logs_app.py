import glob

log_files = glob.glob('runtime/logs/*.log')
print("Searching in files:", log_files)

for f_path in log_files:
    with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '011' in line or 'E4D4' in line:
                print(f"{f_path}: {line.strip()}")
