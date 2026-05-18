import os
import re
import sys
import time
import argparse
from typing import List, Dict, Any, Optional

try:
    import chromadb
except ImportError:
    chromadb = None

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = object

try:
    import tree_sitter
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    
    TS_LANGS = {
        'python': tree_sitter.Language(tree_sitter_python.language()),
        'javascript': tree_sitter.Language(tree_sitter_javascript.language()),
        'typescript': tree_sitter.Language(tree_sitter_typescript.language_typescript()),
        'tsx': tree_sitter.Language(tree_sitter_typescript.language_tsx()),
    }
except ImportError:
    tree_sitter = None
    TS_LANGS = {}

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(SCRIPT_DIR) == "codecompass":
    ROOT_DIR = os.path.dirname(SCRIPT_DIR)
else:
    ROOT_DIR = os.getcwd()

AI_MAP_FILE = os.path.join(ROOT_DIR, "AI_MAP.md")
CURSOR_RULES_FILE = os.path.join(ROOT_DIR, ".cursorrules")
DB_DIR = os.path.join(ROOT_DIR, ".ag_chromadb")
COLLECTION_NAME = "codebase"

IGNORED_DIRS = {
    'node_modules', '.git', 'dist', 'build', 'out', 'bin', 'obj', 
    'venv', '.venv', '__pycache__', '.idea', '.vscode', '.next', '.nuxt', 
    'coverage', 'vendor', 'ag-map-builder-export', 'codecompass', 
    'public', 'assets', '.ag_chromadb'
}

ALLOWED_EXTS = {
    '.js', '.jsx', '.ts', '.tsx', '.py', 
    '.cs', '.java', '.go', '.rs', '.cpp', '.c', '.h', '.hpp', 
    '.rb', '.php', '.swift', '.kt', '.m'
}

# --- PARSER LOGIC ---

def generate_cursor_rules():
    new_rules = """
## AI Context Builder (Auto-Generated)
Before starting any complex task, **you MUST read the `AI_MAP.md` file** in the root directory. It contains the structural skeleton of the project.

### Deep Semantic Search (Vector DB)
You have access to a local Vector Database for deep semantic search across the codebase. 
**TREAT THIS AS A NATIVE TOOL.**
If you need to find specific logic, implementations, or code examples, run the following command in the terminal:
`python codecompass.py --search "your search query"`
(Adjust the path if the script is inside a folder, e.g. `python codecompass/codecompass.py --search "query"`).
Read the terminal output to get exact file paths and line numbers.

### Maintaining the Context
If you create a new file or change the structure, remind the user to run the indexer or ensure the watcher is running.
"""
    
    if os.path.exists(CURSOR_RULES_FILE):
        with open(CURSOR_RULES_FILE, 'r', encoding='utf-8') as f:
            existing = f.read()
        if "Deep Semantic Search (Vector DB)" in existing:
            return # Már benne van, nem piszkáljuk az egyedi szabályokat
            
        with open(CURSOR_RULES_FILE, 'a', encoding='utf-8') as f:
            f.write("\n" + new_rules)
        print("[CodeCompass] Appended AI tools to existing .cursorrules file.")
    else:
        with open(CURSOR_RULES_FILE, 'w', encoding='utf-8') as f:
            f.write("# AI Assistant Instructions\n" + new_rules)
        print("[CodeCompass] Created new .cursorrules file.")


def parse_file(file_path: str) -> Optional[Dict[str, List[str]]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    ext = os.path.splitext(file_path)[1].lower()
    types, funcs, hooks = [], [], []
    
    # 1. Attempt Tree-Sitter AST Parsing
    parsed_with_ts = False
    if tree_sitter is not None:
        lang_key = None
        if ext == '.py': lang_key = 'python'
        elif ext in {'.js', '.jsx'}: lang_key = 'javascript'
        elif ext == '.ts': lang_key = 'typescript'
        elif ext == '.tsx': lang_key = 'tsx'
        
        if lang_key and lang_key in TS_LANGS:
            try:
                lang = TS_LANGS[lang_key]
                parser = tree_sitter.Parser(lang)
                tree = parser.parse(content.encode('utf-8'))
                
                if lang_key == 'python':
                    query = tree_sitter.Query(lang, """
                    (function_definition name: (identifier) @func_name)
                    (class_definition name: (identifier) @class_name)
                    """)
                else: # JS/TS
                    query = tree_sitter.Query(lang, """
                    (export_statement declaration: (function_declaration name: (identifier) @func_name))
                    (export_statement value: (function_declaration name: (identifier) @func_name))
                    (export_statement declaration: (class_declaration name: (identifier) @class_name))
                    (export_statement value: (class_declaration name: (identifier) @class_name))
                    (export_statement declaration: (lexical_declaration (variable_declarator name: (identifier) @var_name value: (arrow_function))))
                    (export_statement declaration: (type_alias_declaration name: (type_identifier) @type_name))
                    (export_statement declaration: (interface_declaration name: (type_identifier) @interface_name))
                    """)
                    
                cursor = tree_sitter.QueryCursor(query)
                for _, captures in cursor.matches(tree.root_node):
                    if 'func_name' in captures:
                        for n in captures['func_name']:
                            name = n.text.decode('utf8')
                            if lang_key == 'python': funcs.append(f"def {name}")
                            else: (hooks if name.startswith('use') else funcs).append(name)
                    if 'var_name' in captures:
                        for n in captures['var_name']:
                            name = n.text.decode('utf8')
                            (hooks if name.startswith('use') else funcs).append(name)
                    if 'class_name' in captures:
                        for n in captures['class_name']:
                            name = n.text.decode('utf8')
                            types.append(f"class {name}")
                    if 'type_name' in captures:
                        for n in captures['type_name']:
                            types.append(f"type {n.text.decode('utf8')}")
                    if 'interface_name' in captures:
                        for n in captures['interface_name']:
                            types.append(f"interface {n.text.decode('utf8')}")
                
                parsed_with_ts = True
            except Exception:
                pass # Fall back to regex if tree-sitter fails
                
    # 2. Regex Fallback
    if not parsed_with_ts:
        if ext in {'.js', '.jsx', '.ts', '.tsx'}:
            interface_regex = re.compile(r'export\s+interface\s+([A-Za-z0-9_]+)')
            type_regex = re.compile(r'export\s+type\s+([A-Za-z0-9_]+)')
            func_regex = re.compile(r'export\s+(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z0-9_]+)')
            arrow_func_regex = re.compile(r'export\s+(?:const|let)\s+([A-Za-z0-9_]+)\s*=')
    
            types.extend([f"interface {m}" for m in interface_regex.findall(content)])
            types.extend([f"type {m}" for m in type_regex.findall(content)])
            
            for name in func_regex.findall(content) + arrow_func_regex.findall(content):
                if name.startswith('use'):
                    hooks.append(name)
                else:
                    funcs.append(name)
    
        elif ext == '.py':
            class_regex = re.compile(r'^class\s+([A-Za-z0-9_]+)', re.MULTILINE)
            func_regex = re.compile(r'^def\s+([A-Za-z0-9_]+)', re.MULTILINE)
            types.extend([f"class {m}" for m in class_regex.findall(content)])
            funcs.extend([f"def {m}" for m in func_regex.findall(content)])
    
        elif ext in {'.cs', '.java', '.kt', '.php'}:
            class_regex = re.compile(r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:sealed\s+)?(?:abstract\s+)?(?:class|interface|record|enum|struct|trait)\s+([A-Za-z0-9_]+)')
            types.extend(class_regex.findall(content))
    
        elif ext == '.go':
            type_regex = re.compile(r'^type\s+([A-Za-z0-9_]+)', re.MULTILINE)
            func_regex = re.compile(r'^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)', re.MULTILINE)
            types.extend([f"type {m}" for m in type_regex.findall(content)])
            funcs.extend([f"func {m}" for m in func_regex.findall(content)])
    
        elif ext == '.rs':
            struct_regex = re.compile(r'^(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)', re.MULTILINE)
            func_regex = re.compile(r'^(?:pub\s+)?fn\s+([A-Za-z0-9_]+)', re.MULTILINE)
            types.extend(struct_regex.findall(content))
            funcs.extend([f"fn {m}" for m in func_regex.findall(content)])
    
        elif ext in {'.c', '.cpp', '.h', '.hpp'}:
            struct_regex = re.compile(r'^(?:struct|class)\s+([A-Za-z0-9_]+)', re.MULTILINE)
            types.extend(struct_regex.findall(content))
    
        elif ext == '.rb':
            class_regex = re.compile(r'^class\s+([A-Za-z0-9_]+)', re.MULTILINE)
            func_regex = re.compile(r'^def\s+([A-Za-z0-9_!]+)', re.MULTILINE)
            types.extend([f"class {m}" for m in class_regex.findall(content)])
            funcs.extend([f"def {m}" for m in func_regex.findall(content)])

    if not types and not funcs and not hooks:
        return None
    return {'types': types, 'funcs': funcs, 'hooks': hooks}

def walk_dir(directory: str) -> List[str]:
    results = []
    for root, dirs, files in os.walk(directory):
        # Mutate dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_EXTS:
                results.append(os.path.join(root, f))
    return results

def generate_map():
    generate_cursor_rules()
    all_files = sorted(walk_dir(ROOT_DIR))
    
    markdown = "# AI Codebase Map\n\n"
    markdown += f"> Generated by `codecompass.py` at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    current_dir = ""
    processed = 0

    for file_path in all_files:
        data = parse_file(file_path)
        if not data:
            continue
            
        processed += 1
        rel_path = os.path.relpath(file_path, ROOT_DIR).replace('\\', '/')
        dir_name = os.path.dirname(rel_path)
        
        if dir_name != current_dir:
            display_dir = "Root" if dir_name == "" else f"/{dir_name}"
            markdown += f"\n## `{display_dir}`\n"
            current_dir = dir_name
            
        file_name = os.path.basename(rel_path)
        uri_path = file_path.replace('\\', '/')
        markdown += f"### [{file_name}](file:///{uri_path})\n"
        
        if data['types']:
            markdown += f"- **Types/Classes**: {', '.join(data['types'])}\n"
        if data['hooks']:
            markdown += f"- **Hooks**: {', '.join(data['hooks'])}\n"
        if data['funcs']:
            markdown += f"- **Exports/Functions**: {', '.join(data['funcs'])}\n"
        markdown += "\n"

    with open(AI_MAP_FILE, 'w', encoding='utf-8') as f:
        f.write(markdown)
    print(f"[CodeCompass] Regenerated AI_MAP.md (Processed {processed} files)")

# --- VECTOR DB LOGIC ---

def get_db_collection():
    if not chromadb:
        raise ImportError("chromadb is not installed. Run: pip install -r requirements.txt")
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return collection

def chunk_file(file_path: str, chunk_size=1000, overlap=200):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []
        
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    
    for i, line in enumerate(lines):
        current_chunk.append(line)
        current_len += len(line) + 1 # +1 for newline
        
        if current_len >= chunk_size:
            chunk_text = '\n'.join(current_chunk)
            start_line = (i - len(current_chunk) + 1) + 1
            chunks.append({
                'text': chunk_text,
                'metadata': {'file': file_path, 'start_line': start_line, 'end_line': i + 1}
            })
            
            # overlap
            overlap_lines = []
            overlap_len = 0
            for overlap_line in reversed(current_chunk):
                overlap_lines.insert(0, overlap_line)
                overlap_len += len(overlap_line) + 1
                if overlap_len >= overlap:
                    break
            current_chunk = overlap_lines
            current_len = overlap_len
            
    if current_chunk and current_len > overlap:
        chunk_text = '\n'.join(current_chunk)
        start_line = (len(lines) - len(current_chunk)) + 1
        chunks.append({
            'text': chunk_text,
            'metadata': {'file': file_path, 'start_line': start_line, 'end_line': len(lines)}
        })
        
    return chunks

def index_project():
    print("[CodeCompass] Building Vector Database. This may take a while on first run...")
    if not chromadb:
        raise ImportError("chromadb is not installed. Run: pip install -r requirements.txt")
    client = chromadb.PersistentClient(path=DB_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    all_files = walk_dir(ROOT_DIR)
    
    docs = []
    metadatas = []
    ids = []
    
    count = 0
    for file_path in all_files:
        chunks = chunk_file(file_path)
        for j, chunk in enumerate(chunks):
            docs.append(chunk['text'])
            metadatas.append(chunk['metadata'])
            ids.append(f"{file_path}_{j}")
            count += 1
            
            # Batch add to avoid memory bloat
            if len(docs) >= 100:
                collection.add(documents=docs, metadatas=metadatas, ids=ids)
                docs, metadatas, ids = [], [], []

    if docs:
        collection.add(documents=docs, metadatas=metadatas, ids=ids)
        
    print(f"[CodeCompass] Indexed {count} code chunks into Vector DB.")

def search_db(query: str, n_results=3):
    try:
        collection = get_db_collection()
    except Exception as e:
        print(f"Error: {e}")
        return
        
    print(f"\n--- AI SEARCH RESULTS FOR: '{query}' ---")
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    
    if not results['documents'] or not results['documents'][0]:
        print("No results found.")
        return
        
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        file_path = meta['file']
        start = meta['start_line']
        end = meta['end_line']
        distance = results['distances'][0][i] if 'distances' in results else 'N/A'
        
        rel_path = os.path.relpath(file_path, ROOT_DIR)
        
        print(f"\n[Result {i+1}] {rel_path} (Lines {start}-{end}) Distance: {distance}")
        print("-" * 50)
        # Print a snippet
        lines = doc.split('\n')
        preview = '\n'.join(lines[:10])
        print(preview)
        if len(lines) > 10:
            print("... (more lines)")
        print("-" * 50)

# --- WATCHER LOGIC ---

class CodeChangeHandler(FileSystemEventHandler if FileSystemEventHandler is not object else object):
    def __init__(self):
        self.last_map_update = 0
        
    def should_process(self, path: str):
        if not path: return False
        ext = os.path.splitext(path)[1].lower()
        if ext not in ALLOWED_EXTS: return False
        parts = path.split(os.sep)
        for part in parts:
            if part in IGNORED_DIRS: return False
        return True

    def on_modified(self, event):
        if event.is_directory: return
        if not self.should_process(event.src_path): return
        
        now = time.time()
        if now - self.last_map_update > 2:
            print(f"[CodeCompass] Detected change in {os.path.basename(event.src_path)}. Updating map...")
            generate_map()
            self.last_map_update = now

def start_watcher():
    if not Observer:
        print("watchdog is not installed. Run: pip install -r requirements.txt")
        return
    observer = Observer()
    observer.schedule(CodeChangeHandler(), ROOT_DIR, recursive=True)
    observer.start()
    print("[CodeCompass] Watcher started. Listening for file changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# --- GUI LOGIC ---

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    import threading
    
    root = tk.Tk()
    root.title("CodeCompass Builder")
    root.geometry("650x500")
    
    style = ttk.Style()
    if 'clam' in style.theme_names():
        style.theme_use('clam')
    
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)
    
    tab_map = ttk.Frame(notebook)
    tab_db = ttk.Frame(notebook)
    notebook.add(tab_map, text="Code Map & Watcher")
    notebook.add(tab_db, text="Vector Database")
    
    # --- Map Tab ---
    def on_generate_map():
        btn_map.config(state="disabled")
        def run_map():
            try:
                generate_map()
                root.after(0, lambda: messagebox.showinfo("Success", "AI_MAP.md and .cursorrules generated successfully!"))
            except Exception as e:
                err = str(e)
                root.after(0, lambda: messagebox.showerror("Error", err))
            finally:
                root.after(0, lambda: btn_map.config(state="normal"))
        threading.Thread(target=run_map, daemon=True).start()

    ttk.Label(tab_map, text="Universal AI Map Generator", font=("Helvetica", 14, "bold")).pack(pady=(20,5))
    ttk.Label(tab_map, text="Scans the root directory and builds AI_MAP.md").pack(pady=5)

    btn_map = ttk.Button(tab_map, text="1. Generate AI Code Map", command=on_generate_map)
    btn_map.pack(pady=10, ipadx=10, ipady=5)
    
    ttk.Separator(tab_map, orient='horizontal').pack(fill='x', pady=20, padx=20)
    
    watcher_thread = None
    def toggle_watcher():
        nonlocal watcher_thread
        if watcher_thread is None or not watcher_thread.is_alive():
            watcher_thread = threading.Thread(target=start_watcher_gui, daemon=True)
            watcher_thread.start()
            btn_watch.config(text="Stop Watcher (Requires Restart)")
            lbl_status.config(text="Watcher: RUNNING", foreground="green")
        else:
            messagebox.showinfo("Watcher", "Watcher is running in background.")
            
    def start_watcher_gui():
        if not Observer:
            root.after(0, lambda: messagebox.showerror("Error", "watchdog is not installed."))
            return
        observer = Observer()
        observer.schedule(CodeChangeHandler(), ROOT_DIR, recursive=True)
        observer.start()
        observer.join()
        
    btn_watch = ttk.Button(tab_map, text="2. Start File Watcher", command=toggle_watcher)
    btn_watch.pack(pady=10, ipadx=10, ipady=5)
    
    lbl_status = ttk.Label(tab_map, text="Watcher: STOPPED", foreground="red")
    lbl_status.pack(pady=5)
    
    # --- Vector DB Tab ---
    ttk.Label(tab_db, text="ChromaDB Vector Database", font=("Helvetica", 14, "bold")).pack(pady=(10,5))
    
    def on_index_db():
        btn_index.config(state="disabled")
        lbl_db_status.config(text="Indexing... Please wait. (Model will download if first time)")
        root.update()
        
        def run_index():
            try:
                index_project()
                root.after(0, lambda: lbl_db_status.config(text="Indexing complete!", foreground="green"))
            except Exception as e:
                err = str(e)
                root.after(0, lambda: lbl_db_status.config(text=f"Error: {err}", foreground="red"))
            finally:
                root.after(0, lambda: btn_index.config(state="normal"))
                
        threading.Thread(target=run_index, daemon=True).start()
        
    btn_index = ttk.Button(tab_db, text="1. Build/Rebuild Vector DB", command=on_index_db)
    btn_index.pack(pady=5, ipadx=10, ipady=5)
    
    lbl_db_status = ttk.Label(tab_db, text="")
    lbl_db_status.pack(pady=5)
    
    frame_search = ttk.LabelFrame(tab_db, text="Test AI Search")
    frame_search.pack(fill='both', expand=True, padx=10, pady=10)
    
    search_entry = ttk.Entry(frame_search)
    search_entry.pack(side='top', fill='x', padx=5, pady=5)
    
    txt_results = scrolledtext.ScrolledText(frame_search, height=10)
    txt_results.pack(side='bottom', fill='both', expand=True, padx=5, pady=5)
    
    def on_search():
        q = search_entry.get()
        if not q: return
        txt_results.delete(1.0, tk.END)
        txt_results.insert(tk.END, f"Searching for: {q}...\n")
        
        def do_search():
            try:
                col = get_db_collection()
                res = col.query(query_texts=[q], n_results=2)
                if not res['documents'] or not res['documents'][0]:
                    root.after(0, lambda: txt_results.insert(tk.END, "No results found."))
                    return
                output = ""
                for i, doc in enumerate(res['documents'][0]):
                    meta = res['metadatas'][0][i]
                    output += f"\n[{i+1}] {os.path.basename(meta['file'])} (Lines {meta['start_line']}-{meta['end_line']})\n"
                    output += doc[:200] + "...\n"
                root.after(0, lambda: txt_results.insert(tk.END, output))
            except Exception as e:
                err = str(e)
                root.after(0, lambda: txt_results.insert(tk.END, f"\nError: {err}"))
                
        threading.Thread(target=do_search, daemon=True).start()
            
    btn_search = ttk.Button(frame_search, text="Search DB", command=on_search)
    btn_search.pack(side='top')
    
    root.mainloop()

# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(description="CodeCompass Builder & Vector DB")
    parser.add_argument("--map", action="store_true", help="Generate AI_MAP.md")
    parser.add_argument("--watch", action="store_true", help="Run file watcher")
    parser.add_argument("--index", action="store_true", help="Index codebase into Vector DB")
    parser.add_argument("--search", type=str, help="Search Vector DB")
    parser.add_argument("--gui", action="store_true", help="Run GUI mode")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        args.gui = True

    if args.gui:
        run_gui()
    else:
        if args.map:
            generate_map()
        if args.index:
            index_project()
        if args.search:
            search_db(args.search)
        if args.watch:
            start_watcher()

if __name__ == "__main__":
    main()
