# 🔧 Git Setup & GitHub Workflow Guide

## 1. First-Time Git Setup

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
git config --global core.editor "code --wait"   # Use VS Code as Git editor
git config --global pull.rebase false            # Merge, don't rebase on pull
git config --global core.autocrlf input          # Line endings (Linux/Mac)

# Verify
git config --list
```

---

## 2. SSH Key Setup (Do This Once — Required for GitHub)

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "you@example.com"
# Press Enter 3 times (accept defaults, no passphrase for simplicity)

# Copy public key
cat ~/.ssh/id_ed25519.pub
# Copy the output

# Add to GitHub:
# github.com → Settings → SSH and GPG keys → New SSH key → Paste → Save

# Test connection
ssh -T git@github.com
# Should say: "Hi username! You've successfully authenticated..."
```

---

## 3. Create a GitHub Repo & Push

```bash
# Create repo on GitHub first (github.com → New repository)
# Then in your project folder:

git init
git add .
git commit -m "feat: initial project setup"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git push -u origin main

# Future pushes (shorter):
git push
```

---

## 4. Daily Git Workflow

```bash
# Morning: pull latest
git pull

# Work on a feature
git checkout -b feat/add-streaming
# ... make changes ...

git status                        # See what changed
git diff                          # See exact changes
git add .                         # Stage all changes
git add app/services/llm.py      # Stage specific file
git commit -m "feat: add streaming response support"
git push origin feat/add-streaming

# On GitHub: open Pull Request → Review → Merge
git checkout main && git pull     # Back to main with merged changes
git branch -d feat/add-streaming  # Clean up local branch
```

---

## 5. Conventional Commits (Industry Standard)

```
Format: <type>(<scope>): <description>

Types:
  feat     → New feature         → feat: add streaming endpoint
  fix      → Bug fix             → fix: handle empty message validation
  docs     → Documentation       → docs: update API README
  style    → Formatting only     → style: fix line length
  refactor → Restructure code    → refactor: extract LLM service
  test     → Add/update tests    → test: add chat endpoint tests
  chore    → Maintenance         → chore: update dependencies
  ci       → CI/CD changes       → ci: add security scan
  perf     → Performance         → perf: add embedding cache

Examples:
  git commit -m "feat(chat): add multi-turn conversation support"
  git commit -m "fix(rag): handle PDF with no extractable text"
  git commit -m "test(agent): add tool execution tests"
  git commit -m "ci: add Docker build step to pipeline"
```

---

## 6. Useful Git Aliases (Add to ~/.bashrc or ~/.zshrc)

```bash
alias gs='git status'
alias ga='git add -A'
alias gc='git commit -m'
alias gp='git push'
alias gpl='git pull'
alias gl='git log --oneline --graph --all --decorate'
alias gd='git diff'
alias gb='git branch -a'
alias gco='git checkout'
alias gsw='git switch'

# Usage:
gs          # git status
ga          # git add -A (all files)
gc "feat: add streaming"  # commit
gp          # git push
gl          # visual log
```

---

## 7. Undoing Mistakes

```bash
# Undo unstaged changes to a file
git restore app/main.py

# Unstage a file (keep changes)
git restore --staged app/main.py

# Undo last commit, keep changes staged
git reset --soft HEAD~1

# Undo last commit, keep changes unstaged
git reset HEAD~1

# Undo last commit, LOSE all changes (DANGER!)
git reset --hard HEAD~1

# Revert a commit (safe — creates new commit)
git revert abc1234

# Fix last commit message
git commit --amend -m "correct message"

# Add forgotten file to last commit
git add forgotten_file.py
git commit --amend --no-edit
```

---

## 8. GitHub Actions Secrets (For CI/CD)

```
GitHub Repo → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:
  AWS_ACCESS_KEY_ID        → Your AWS access key
  AWS_SECRET_ACCESS_KEY    → Your AWS secret key
  GROQ_API_KEY             → From console.groq.com (free)
```
