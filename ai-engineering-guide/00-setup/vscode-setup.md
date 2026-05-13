# 💻 VS Code Setup for AI Engineering
> The definitive VS Code configuration for Python AI development

---

## 1. Install VS Code
Download from: https://code.visualstudio.com/ (100% free)

---

## 2. Essential Extensions

Install all of these (Ctrl+Shift+X → search each):

| Extension | ID | Purpose |
|-----------|-----|---------|
| Python | `ms-python.python` | Core Python support |
| Pylance | `ms-python.pylance` | Intellisense, type checking |
| Ruff | `charliermarsh.ruff` | Ultra-fast linter + formatter |
| Mypy | `ms-python.mypy-type-checker` | Static type checking |
| Docker | `ms-azuretools.vscode-docker` | Docker GUI |
| GitLens | `eamodio.gitlens` | Supercharged Git |
| REST Client | `humao.rest-client` | Test APIs from `.http` files |
| Thunder Client | `rangav.vscode-thunder-client` | Postman inside VS Code |
| YAML | `redhat.vscode-yaml` | YAML validation |
| Even Better TOML | `tamasfe.even-better-toml` | pyproject.toml support |
| GitHub Actions | `github.vscode-github-actions` | CI/CD syntax highlighting |

Install all at once via terminal:
```bash
code --install-extension ms-python.python ms-python.pylance charliermarsh.ruff \
     ms-python.mypy-type-checker ms-azuretools.vscode-docker eamodio.gitlens \
     humao.rest-client rangav.vscode-thunder-client redhat.vscode-yaml \
     tamasfe.even-better-toml github.vscode-github-actions
```

---

## 3. Workspace Settings

Create `.vscode/settings.json` in every project:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,

  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },

  "mypy-type-checker.args": ["--strict"],
  
  "editor.rulers": [88],
  "editor.tabSize": 4,
  "editor.insertSpaces": true,
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,

  "terminal.integrated.env.linux": {
    "PYTHONPATH": "${workspaceFolder}"
  },
  "terminal.integrated.env.osx": {
    "PYTHONPATH": "${workspaceFolder}"
  }
}
```

---

## 4. Debug Configurations

Create `.vscode/launch.json` in every project:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI: Run Server",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "ENV": "development"
      },
      "justMyCode": false
    },
    {
      "name": "Python: Current File",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Pytest: All Tests",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "--tb=short"],
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Pytest: Current File",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v", "-s"],
      "console": "integratedTerminal"
    }
  ]
}
```

---

## 5. Debugging Commands (Master These)

### In VS Code UI:
| Action | Shortcut |
|--------|----------|
| Set breakpoint | `F9` |
| Start debugging | `F5` |
| Step over | `F10` |
| Step into | `F11` |
| Step out | `Shift+F11` |
| Continue | `F5` |
| Stop | `Shift+F5` |
| Restart | `Ctrl+Shift+F5` |
| Debug console | `Ctrl+Shift+Y` |

### Python Debugger (pdb) — Terminal Debugging:
```python
# Add this line anywhere in your code to drop into debugger:
import pdb; pdb.set_trace()

# Or use the modern version (Python 3.7+):
breakpoint()
```

### pdb Commands:
```
n       → next line (step over)
s       → step into function
c       → continue until next breakpoint
q       → quit debugger
p var   → print variable value
pp var  → pretty-print variable
l       → list surrounding code
w       → print call stack (where am I?)
u       → move up in call stack
d       → move down in call stack
b 42    → set breakpoint at line 42
cl      → clear all breakpoints
```

### FastAPI Debugging Tips:
```python
# In your route, add:
import logging
logger = logging.getLogger(__name__)

@app.get("/debug")
async def debug_route(request: Request):
    logger.debug(f"Headers: {dict(request.headers)}")
    logger.debug(f"Query params: {dict(request.query_params)}")
    breakpoint()  # Drop into debugger here
    return {"status": "debugging"}
```

---

## 6. Useful Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|--------------|-----|
| Command palette | `Ctrl+Shift+P` | `Cmd+Shift+P` |
| Quick open file | `Ctrl+P` | `Cmd+P` |
| Terminal | `Ctrl+\`` | `Cmd+\`` |
| Split terminal | `Ctrl+Shift+5` | `Cmd+Shift+5` |
| Find in files | `Ctrl+Shift+F` | `Cmd+Shift+F` |
| Go to definition | `F12` | `F12` |
| Rename symbol | `F2` | `F2` |
| Format document | `Shift+Alt+F` | `Shift+Option+F` |
| Zen mode | `Ctrl+K Z` | `Cmd+K Z` |
| Multi-cursor | `Alt+Click` | `Option+Click` |
| Select all occurrences | `Ctrl+Shift+L` | `Cmd+Shift+L` |

---

## 7. Python Virtual Environment Setup

```bash
# Create venv (do this in every project)
python3.11 -m venv .venv

# Activate (Linux/Mac)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Tell VS Code to use this venv
# Ctrl+Shift+P → "Python: Select Interpreter" → choose .venv
```

---

## 8. REST Client (.http files)

Create `requests.http` in your project to test APIs directly in VS Code:

```http
### Health check
GET http://localhost:8000/health

### Chat with AI
POST http://localhost:8000/api/v1/chat
Content-Type: application/json

{
  "message": "What is machine learning?",
  "conversation_id": "test-123"
}

### Upload document
POST http://localhost:8000/api/v1/documents/upload
Content-Type: multipart/form-data; boundary=----boundary

------boundary
Content-Disposition: form-data; name="file"; filename="test.pdf"
Content-Type: application/pdf

< ./test.pdf
------boundary--
```

Click "Send Request" above each `###` block to execute. 

---

## 9. Integrated Git Workflow

```bash
# VS Code Git shortcuts
Ctrl+Shift+G    → Open Source Control panel
Ctrl+Enter      → Commit staged changes (in Source Control panel)

# Terminal git shortcuts (add to ~/.bashrc)
alias gs='git status'
alias ga='git add -A'
alias gc='git commit -m'
alias gp='git push'
alias gl='git log --oneline --graph --all'
alias gd='git diff'
alias gb='git branch -a'
```
