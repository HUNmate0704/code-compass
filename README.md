# CodeCompass: Universal AI Context Builder & Local RAG

**CodeCompass** is a zero-config repository mapper and local RAG (Retrieval-Augmented Generation) tool designed to drastically improve the memory and context-awareness of AI coding assistants like **Cursor, Claude Code, Windsurf, and Antigravity**.

When working on large codebases, AI assistants often suffer from "context loss." CodeCompass solves this without relying on expensive external APIs by generating a structural map of your repository and maintaining a local vector database for deep semantic searches.

## 🚀 Key Features

1. **Zero-Config Repository Mapper (`AI_MAP.md`)**
   CodeCompass rapidly scans your project and uses regex-based heuristics to extract critical elements (functions, classes, types, hooks, interfaces). It generates a concise `AI_MAP.md` file. When an AI assistant reads this map upon startup, it instantly understands your entire architecture without processing gigabytes of raw code.

2. **Local Vector Search (ChromaDB)**
   The tool chunks your codebase and generates embeddings using a lightweight, local AI model (`all-MiniLM-L6-v2`), storing them in a hidden SQLite database (`.ag_chromadb`). 
   When your AI assistant gets stuck, it can run `--search "payment error handling"`. The vector database instantly returns the exact file paths and line numbers, acting as a massive memory extension.

3. **Auto-Generated AI Instructions (`.cursorrules`)**
   CodeCompass automatically generates (or appends to) your `.cursorrules` or `.clauderules` file. It teaches your AI assistant *how* to use the vector database natively, allowing it to perform semantic searches autonomously!

## 🌍 Supported Languages
CodeCompass is universally compatible and automatically ignores heavy/irrelevant folders (`node_modules`, `.git`, `venv`, `__pycache__`, etc.).
- **Supported:** JavaScript, TypeScript, Python, C#, Java, Kotlin, PHP, Go, Rust, C, C++, Ruby.

---

## 📦 Installation (Drop-in Portability)

CodeCompass is designed to be dropped into any project in seconds.

1. Ensure **Python 3.9+** is installed on your machine.
2. Copy the `codecompass` folder into the root of your project.
3. Open a terminal in the root of your project and install the dependencies:
   ```bash
   pip install -r codecompass/requirements.txt
   ```
   *(This installs ChromaDB for vector search and Watchdog for live file monitoring).*

---

## 🖥️ Usage: GUI Mode (For Humans)

If you prefer a visual interface, simply run the script without any arguments:

```bash
python codecompass/codecompass.py
```
*(Tip: Always run it from your terminal rather than double-clicking the file in Explorer, to ensure it uses the correct Python environment where you installed the dependencies!)*

- **Code Map Tab:** Generate the `AI_MAP.md` or start the background File Watcher to keep the map updated on every file save.
- **Vector Database Tab:** Build the semantic index of your codebase (the first run may take a few minutes as it downloads the ~90MB local embedding model) and test the AI search functionality.

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
**Solution:** The latest version of CodeCompass has a foolproof path resolver, but always ensure you are running the script from the root directory of your project.

### 4. Will this overwrite my custom `.cursorrules`?
**No.** CodeCompass intelligently checks for an existing `.cursorrules` file. If it finds one, it safely **appends** its tool instructions to the bottom of the file without modifying your existing custom rules.
