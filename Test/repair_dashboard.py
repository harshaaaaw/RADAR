

file_path = r'c:\Users\DELL\Downloads\DocumentSearch_v5\DocumentSearch\src\ui\dashboard.py'

mapping = {
    'ðŸ“„': '📄',
    'ðŸ“Š': '📊',
    'ðŸ“‚': '📂',
    'ðŸ”„': '🔄',
    'ðŸ” ': '🔍',
    'âœ…': '✅',
    'â Œ': '❌',
    'ðŸ“ ': '📁',
    'â ³': '⏳',
    'âœ“': '✓',
    'â¬‡ï¸ ': '⬇️',
    'ðŸ’¤': '💤',
    'ðŸ“š': '📚',
    'ðŸ“‹': '📋',
    'ðŸ“¦': '📦',
    'ðŸ“Ž': '📎',
    'ðŸ“ˆ': '📈',
    'â„¹ï¸ ': 'ℹ️',
    'âœ¨': '✨',
    'ðŸ—‚ï¸ ': '🗂️',
    'â†”': '↔',
    'âš™ï¸ ': '⚙️',
    'â€“': '–',
    'âš ï¸ ': '⚠️',
    'â”€â”€': '──',
    'â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€': '────────────────────────────────────────────'
}

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Apply replacements
for corrupted, fixed in mapping.items():
    content = content.replace(corrupted, fixed)

# Also fix the weird arrows in OCR variants comment
content = content.replace('â†”', '↔')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Repair complete.")
