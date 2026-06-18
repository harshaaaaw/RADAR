import os

workspace = r"c:\Users\DELL\Music\DocumentSearch"
search_terms = ["hp212560601", "C:\\DocumentSearch", "D:\\DocumentSearch", "C:/DocumentSearch", "D:/DocumentSearch"]

results = []

for root, dirs, files in os.walk(workspace):
    # Skip standard folders
    if any(p in root for p in [".git", ".pytest_cache", ".ruff_cache", "__pycache__", "redis_backups"]):
        continue
    for file in files:
        file_path = os.path.join(root, file)
        # Skip binary files
        if file.endswith(('.pkl', '.exe', '.dll', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.xlsx', '.db', '.db-wal', '.db-shm')):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                found = []
                for term in search_terms:
                    if term.lower() in content.lower():
                        found.append(term)
                if found:
                    results.append((file_path, found))
        except Exception as e:
            pass

print("Search results:")
for path, terms in results:
    print(f"File: {path} -> Found: {terms}")
