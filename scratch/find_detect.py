import glob
results = []
for f in glob.glob('src/ocr/ocr_worker.py'):
    for i, line in enumerate(open(f, encoding='utf-8', errors='ignore')):
        ls = line.strip()
        if 'def ' in ls and ('visual' in ls.lower() or 'snippet' in ls.lower() or 'segment' in ls.lower() or 'detect' in ls.lower() or 'classify' in ls.lower() or 'extract_region' in ls.lower() or 'logo' in ls.lower() or 'stamp' in ls.lower() or 'handwrit' in ls.lower()):
            results.append(f"{i+1}: {ls}")
for r in results:
    print(r)
