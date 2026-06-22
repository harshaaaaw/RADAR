log_path = r"C:\Users\DELL\.gemini\antigravity\brain\336410ff-a0b4-4cb8-9984-661135b40338\.system_generated\tasks\task-2917.log"
with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'real_funsd_form' in line or 'E4D4' in line:
            print(line.strip())
