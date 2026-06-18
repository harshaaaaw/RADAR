import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

filepath = r"c:\Users\DELL\Downloads\DocumentSearch\DocumentSearch\src\tagging\tagging_engine.py"
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"File: {filepath} ({len(lines)} lines)")
print("-" * 80)
for idx, line in enumerate(lines, start=1):
    if "def " in line and ("_classify" in line or "tag(" in line or "derive" in line or "extract" in line):
        print(f"Line {idx:4d}: {line.strip()}")
