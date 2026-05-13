# 🚀 The Ultimate AI Engineering Guide
### From JavaScript/Python Basics → Production-Grade AI Engineer

> **Zero to AI Engineering Hero — Everything Free & Open Source**
> Built for developers who know JavaScript and basic Python and want to become **world-class AI engineers**.

---

## 📋 Table of Contents

| # | Module | What You'll Learn |
|---|--------|-------------------|
| 00 | [Environment Setup](./00-setup/) | VS Code, Python, Git, Docker — full dev environment |
| 01 | [Python Mastery for AI](./01-python-mastery/) | Advanced Python patterns used in real AI systems |
| 02 | [AI Fundamentals](./02-ai-fundamentals/) | LLMs, embeddings, tokens, RAG, agents — the theory |
| 03 | [FastAPI — Production APIs](./03-fastapi/) | Build world-class async APIs for AI services |
| 04 | [AI Stack](./04-ai-stack/) | LangChain, LangGraph, Ollama, ChromaDB, agents |
| 05 | [Observability](./05-observability/) | OpenTelemetry, Prometheus, Grafana, structured logging |
| 06 | [CI/CD](./06-cicd/) | GitHub Actions pipelines for AI services |
| 07 | [AWS Cloud](./07-aws/) | Deploy AI on AWS — EC2, ECS, Lambda, Bedrock (free tier) |
| 08 | [Docker & Kubernetes](./08-docker-k8s/) | Containerise and orchestrate AI workloads |
| P1 | [Project 1: AI Chat API](./projects/project-1-ai-chat-api/) | Streaming chat API with local LLM + Redis history |
| P2 | [Project 2: RAG Document Q&A](./projects/project-2-rag-document-qa/) | Upload PDFs, ask questions — full RAG pipeline |
| P3 | [Project 3: AI Agent System](./projects/project-3-ai-agent-system/) | Multi-tool LangGraph agent with full observability |
| CS | [Cheatsheets](./cheatsheets/) | Quick reference cards for everything |

---

## 🎯 Learning Path (Recommended Order)

```
Week 1-2:   00-setup → 01-python-mastery
Week 3-4:   02-ai-fundamentals → 03-fastapi
Week 5-6:   04-ai-stack → Project 1
Week 7-8:   05-observability → 06-cicd → Project 2
Week 9-10:  07-aws → 08-docker-k8s → Project 3
Week 11-12: Polish all 3 projects, deploy to AWS, add to portfolio
```

---

## 🛠️ Complete Free Tech Stack

| Category | Tool | Why |
|----------|------|-----|
| **Language** | Python 3.11+ | Industry standard for AI |
| **API Framework** | FastAPI | Async, auto-docs, typed |
| **LLM (local)** | Ollama + Llama 3.1 | Run LLMs free on your machine |
| **LLM (cloud)** | Groq API (free tier) | Lightning-fast inference |
| **Agents** | LangGraph | Production agent framework |
| **Vector DB** | ChromaDB | Free, embedded, powerful |
| **Embeddings** | sentence-transformers | Free, runs locally |
| **Cache/Memory** | Redis (Docker) | Conversation history |
| **Observability** | OpenTelemetry | Industry standard tracing |
| **Metrics** | Prometheus + Grafana | Free monitoring stack |
| **Logging** | structlog | Structured JSON logging |
| **CI/CD** | GitHub Actions | Free for public repos |
| **Container** | Docker + Docker Compose | Reproducible environments |
| **Cloud** | AWS Free Tier | EC2, ECS, Lambda, Bedrock |
| **IaC** | Terraform | Infrastructure as code |
| **Editor** | VS Code | Best free editor |
| **Testing** | pytest + httpx | Full test suite |
| **Linting** | ruff + mypy | Code quality |

---

## 🏃 Quick Start (Get Running in 10 Minutes)

```bash
# 1. Clone this guide
git clone https://github.com/YOUR_USERNAME/ai-engineering-guide
cd ai-engineering-guide

# 2. Run setup script
chmod +x 00-setup/setup.sh
./00-setup/setup.sh

# 3. Jump into Project 1
cd projects/project-1-ai-chat-api
docker compose up -d
uvicorn app.main:app --reload

# 4. Hit the API
curl http://localhost:8000/docs
```

---

## 💡 How to Use This Guide

1. **Read** each module's `.md` file top to bottom
2. **Type** every code snippet (don't copy-paste — muscle memory matters)
3. **Run** each example and observe what happens
4. **Break** things intentionally and debug them
5. **Build** the 3 projects from scratch using the guide as reference
6. **Deploy** each project to AWS

---

> **Remember:** Every expert was once a beginner. The only difference is they didn't stop. 🔥
