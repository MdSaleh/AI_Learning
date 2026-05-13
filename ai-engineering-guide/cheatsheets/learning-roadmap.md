# 🗺️ Learning Roadmap & Free Resources

## Your 12-Week Plan

### Week 1-2: Foundation
- [ ] Complete `00-setup` — full dev environment working
- [ ] Work through `01-python-mastery` — type hints, async, decorators
- [ ] Run `ollama pull llama3.1:8b` and chat with it in terminal
- [ ] **Milestone**: Write an async function that calls Ollama and prints the response

### Week 3-4: AI Fundamentals + FastAPI
- [ ] Read `02-ai-fundamentals` — understand tokens, embeddings, RAG, agents
- [ ] Work through `03-fastapi` — build a simple API from scratch
- [ ] **Milestone**: Build a `/chat` endpoint that calls Ollama and returns a response

### Week 5-6: Project 1 — AI Chat API
- [ ] Read all files in `projects/project-1-ai-chat-api`
- [ ] Type out the code yourself (don't copy-paste!)
- [ ] Get it running: `make dev`
- [ ] Run tests: `make test`
- [ ] Start Docker stack: `make docker-up`
- [ ] **Milestone**: Working streaming chat API with Redis conversation history

### Week 7-8: Observability + Project 2
- [ ] Read `05-observability` — OpenTelemetry, Prometheus, Grafana
- [ ] Set up Grafana dashboard for Project 1 metrics
- [ ] Build Project 2 — RAG Document Q&A
- [ ] Upload your own PDF and ask questions about it
- [ ] **Milestone**: RAG system answering questions about your own documents

### Week 9-10: Agents + CI/CD
- [ ] Read `04-ai-stack` — LangChain, ChromaDB, Ollama patterns
- [ ] Build Project 3 — AI Agent System
- [ ] Set up GitHub Actions CI from `06-cicd`
- [ ] Push all 3 projects to GitHub with passing CI
- [ ] **Milestone**: Agent using tools to answer multi-step questions

### Week 11-12: Cloud + Polish
- [ ] Read `07-aws` and `08-docker-k8s`
- [ ] Deploy Project 1 to AWS (EC2 or Lambda)
- [ ] Add observability to all 3 projects
- [ ] Write a blog post or LinkedIn post about what you built
- [ ] **Milestone**: Live deployed AI service on AWS with monitoring

---

## Free Learning Resources

### Python & Async
- Python docs: https://docs.python.org/3/
- Real Python async guide: https://realpython.com/async-io-python/
- Pydantic docs: https://docs.pydantic.dev/

### FastAPI
- Official docs (excellent!): https://fastapi.tiangolo.com/
- FastAPI best practices: https://github.com/zhanymkanov/fastapi-best-practices

### AI/LLM
- Ollama: https://ollama.ai/
- Groq (free API): https://console.groq.com/
- LangChain docs: https://python.langchain.com/
- ChromaDB docs: https://docs.trychroma.com/

### Observability
- OpenTelemetry: https://opentelemetry.io/docs/
- Prometheus: https://prometheus.io/docs/
- Grafana: https://grafana.com/docs/

### AWS (Free)
- AWS Free Tier: https://aws.amazon.com/free/
- AWS CLI docs: https://docs.aws.amazon.com/cli/
- Terraform: https://developer.hashicorp.com/terraform/docs

### Free Courses
- Fast.ai (practical deep learning): https://fast.ai
- CS50 AI: https://cs50.harvard.edu/ai/
- Hugging Face course: https://huggingface.co/learn/nlp-course/
- Microsoft AI-102: https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/

---

## Portfolio Projects to Add After This Guide

1. **AI Code Reviewer** — Submit code, get AI review with bugs + improvements
2. **Meeting Summarizer** — Upload audio/transcript, get action items
3. **AI SQL Generator** — Natural language → SQL queries for your DB
4. **Resume Screener** — Upload JD + resumes, rank candidates
5. **AI Chatbot for Docs** — RAG over any website's documentation

---

## Communities to Join (Free)

- Hugging Face Discord: https://discord.gg/hugging-face
- LangChain Discord: https://discord.gg/langchain
- FastAPI GitHub Discussions: https://github.com/fastapi/fastapi/discussions
- r/LocalLLaMA: https://reddit.com/r/LocalLLaMA (Ollama tips)
- AI Engineer Foundation: https://www.ai.engineer/
