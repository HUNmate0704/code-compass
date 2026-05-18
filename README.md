# CodeCompass: Universal AI Context Builder & Local RAG

**CodeCompass** is a zero-config repository mapper and local RAG (Retrieval-Augmented Generation) tool designed to drastically improve the memory and context-awareness of AI coding assistants like **Cursor, Claude Code, Windsurf, and Antigravity**.

When working on large codebases, AI assistants often suffer from "context loss." CodeCompass solves this without relying on expensive external APIs by generating a structural map of your repository and maintaining a local vector database for deep semantic searches.

## 🚀 Key Features

1. **Tree-Sitter AST Code Mapping (`AI_MAP.md`)**
   CodeCompass rapidly scans your project and uses **Tree-Sitter Abstract Syntax Trees** (for Python and JS/TS) to perfectly extract critical elements (exported functions, classes, types, hooks, interfaces) without the brittle errors of Regex. It generates a concise `AI_MAP.md` file. When an AI assistant reads this map upon startup, it instantly understands your entire architecture without processing gigabytes of raw code.

2. **Incremental RAG Updates (Local Vector DB)**
   The tool chunks your codebase and generates embeddings using a lightweight, local AI model (`all-MiniLM-L6-v2`), storing them in a hidden SQLite database (`.ag_chromadb`).
   **New:** CodeCompass features a live background Watcher. When you hit `Ctrl+S` (Save) on a file, it performs an **Incremental DB Update**. It deletes only the modified file's old vectors and embeds the new ones in milliseconds! No more waiting for a full 5-minute database rebuild.

3. **Standalone Universal Tool (Dynamic Directory Selection)**
   You don't need to lock the tool inside a specific repository. You can select *any* target directory from the CodeCompass GUI, making it a truly universal context-builder for all your projects.

4. **Auto-Generated AI Instructions (`.cursorrules`)**
   CodeCompass automatically generates (or appends to) your `.cursorrules` or `.clauderules` file. It teaches your AI assistant *how* to use the vector database natively, allowing it to perform semantic searches autonomously!

## 🌍 Supported Languages
CodeCompass is universally compatible and automatically ignores heavy/irrelevant folders (`node_modules`, `.git`, `venv`, `__pycache__`, etc.).
- **Tree-Sitter AST Parsing:** JavaScript, TypeScript, TSX/JSX, Python.
- **Regex Fallback Parsing:** C#, Java, Kotlin, PHP, Go, Rust, C, C++, Ruby.

---

## 📦 Installation (Drop-in Portability)

CodeCompass is designed to be dropped into any project in seconds, or run as a standalone app.

1. Ensure **Python 3.9+** is installed on your machine.
2. Copy the `codecompass` folder anywhere on your computer (or into your project root).
3. Open a terminal and install the dependencies:
   ```bash
   pip install -r codecompass/requirements.txt
   ```
   *(This automatically installs pre-compiled wheels for ChromaDB, Tree-Sitter, and Watchdog).*

---

## 🖥️ Usage: GUI Mode (For Humans)

If you prefer a visual interface, simply run the script without any arguments:

```bash
python codecompass/codecompass.py
```
*(Tip: Always run it from your terminal rather than double-clicking the file in Explorer, to ensure it uses the correct Python environment where you installed the dependencies!)*

- **Top Bar:** Click **"Change Directory"** to target any repository on your computer.
- **Code Map Tab:** Generate the `AI_MAP.md` manually, or toggle the checkbox to auto-update it every time you save a file.
- **Vector Database Tab:** Build the semantic index of your codebase (the first run may take a few minutes as it downloads the ~90MB local embedding model). Toggle the incremental Watcher to auto-update the DB in the background.

---

## 💻 Usage: CLI Mode (For AI Assistants)

These are the commands that your AI assistant will use under the hood (defined in the auto-generated `.cursorrules`). You rarely need to run these yourself:

- **Generate Map:** `python codecompass/codecompass.py --map`
- **Start Watcher:** `python codecompass/codecompass.py --watch`
- **Build Vector DB:** `python codecompass/codecompass.py --index`
- **Semantic Search:** `python codecompass/codecompass.py --search "your search query"`

---

## 🛠️ Troubleshooting & FAQ

### 1. "watchdog is not installed" (GUI Error)
**What happened?** The Python GUI launched, but it can't find the `watchdog` package.
**Solution:** You likely double-clicked the `.py` file from Windows Explorer, which launched a global Python environment. Always launch the GUI from the exact same terminal (e.g., VS Code integrated terminal) where you ran `pip install`.

### 2. Vector DB indexing is very slow on the first run
**What happened?** ChromaDB is downloading the `all-MiniLM-L6-v2` embedding model from HuggingFace (~90MB).
**Solution:** This is perfectly normal and only happens once. Wait for the download to finish.

### 3. The `AI_MAP.md` is generated in the wrong folder
**What happened?** If the map generates inside the `codecompass` folder instead of the project root, it's usually because you used a "Run Python File" button in your IDE, which overrides the working directory.
**Solution:** The latest version of CodeCompass has a foolproof path resolver and a Directory Selection GUI, ensuring you always target the correct root.

### 4. Will this overwrite my custom `.cursorrules`?
**No.** CodeCompass intelligently checks for an existing `.cursorrules` file. If it finds one, it safely **appends** its tool instructions to the bottom of the file without modifying your existing custom rules.
