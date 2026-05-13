# 🐳 Docker & Kubernetes for AI Services
> Containerise, orchestrate, and scale your AI workloads

---

## Docker — Production Dockerfile Patterns

### Multi-stage Build (Smallest Possible Image)
```dockerfile
# ─── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system --prefix=/install -e "."

# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy only installed packages from builder (not dev tools)
COPY --from=builder /install /usr/local

# System deps for runtime only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy app code
COPY app/ ./app/

# Security: run as non-root
RUN useradd -m -u 1000 appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### .dockerignore (Always Create This!)
```
.venv/
__pycache__/
*.pyc
.git/
.env
.env.local
tests/
htmlcov/
.coverage
*.log
data/
uploads/
*.pdf
node_modules/
.DS_Store
```

---

## Kubernetes — Deploy AI Services

### Namespace + Deployment
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-services

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-chat-api
  namespace: ai-services
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-chat-api
  template:
    metadata:
      labels:
        app: ai-chat-api
    spec:
      containers:
        - name: ai-chat-api
          image: your-ecr-repo/ai-chat-api:latest
          ports:
            - containerPort: 8000
          env:
            - name: ENV
              value: production
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: ai-secrets
                  key: redis-url
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-chat-api
  namespace: ai-services
spec:
  selector:
    app: ai-chat-api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-chat-api
  namespace: ai-services
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-buffering: "off"  # For streaming!
spec:
  rules:
    - host: api.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ai-chat-api
                port:
                  number: 80
```

### Secrets
```bash
# Create secret for sensitive values
kubectl create secret generic ai-secrets \
  --namespace=ai-services \
  --from-literal=redis-url="redis://redis:6379" \
  --from-literal=groq-api-key="gsk_xxxx"

# View secrets (base64 encoded)
kubectl get secret ai-secrets -n ai-services -o yaml
```

### Essential kubectl Commands
```bash
# Cluster info
kubectl cluster-info
kubectl get nodes

# Deployments
kubectl apply -f k8s/          # Apply all YAML files in dir
kubectl get pods -n ai-services -w   # Watch pods
kubectl describe pod <pod-name> -n ai-services
kubectl logs <pod-name> -n ai-services -f     # Follow logs
kubectl logs <pod-name> -n ai-services --previous  # Crashed pod logs
kubectl exec -it <pod-name> -n ai-services -- bash  # Shell into pod

# Scaling
kubectl scale deployment ai-chat-api --replicas=4 -n ai-services
kubectl autoscale deployment ai-chat-api --min=2 --max=10 --cpu-percent=70

# Rolling update
kubectl set image deployment/ai-chat-api ai-chat-api=new-image:v2 -n ai-services
kubectl rollout status deployment/ai-chat-api -n ai-services
kubectl rollout undo deployment/ai-chat-api -n ai-services  # Rollback!

# Debugging
kubectl get events -n ai-services --sort-by='.lastTimestamp'
kubectl top pods -n ai-services   # Resource usage
```

### Horizontal Pod Autoscaler
```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-chat-api-hpa
  namespace: ai-services
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-chat-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Free Local Kubernetes (For Development)
```bash
# Option 1: minikube (easiest)
brew install minikube         # Mac
minikube start --memory 4096  # Start with 4GB RAM
minikube dashboard            # Open web UI
eval $(minikube docker-env)   # Use minikube's docker

# Option 2: kind (fast, CI-friendly)
brew install kind
kind create cluster --name ai-dev
kubectl cluster-info --context kind-ai-dev

# Option 3: k3s (lightweight, great for Raspberry Pi / EC2)
curl -sfL https://get.k3s.io | sh -
sudo k3s kubectl get nodes
```
