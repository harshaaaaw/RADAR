import os

def search_files(directory, query):
    matches = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            if query in line:
                                matches.append((path, i, line.strip()))
                except Exception:
                    pass
    return matches

def main():
    print("Searching for _open_source_document:")
    for path, line_num, line in search_files("src", "_open_source_document"):
        print(f"  {path}:{line_num} -> {line}")
        
    print("\nSearching for _build_document_page_link:")
    for path, line_num, line in search_files("src", "_build_document_page_link"):
        print(f"  {path}:{line_num} -> {line}")

if __name__ == "__main__":
    main()
