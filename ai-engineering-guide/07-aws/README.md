# ☁️ AWS for AI Engineers — Free Tier Guide
> Deploy your AI services on AWS — maximizing the free tier

---

## AWS Free Tier Key Resources

| Service | Free Tier | Use For |
|---------|-----------|---------|
| EC2 t2.micro/t3.micro | 750 hrs/month | Run FastAPI + Ollama |
| Lambda | 1M requests/month | Serverless AI endpoints |
| S3 | 5GB storage | Store documents, models |
| ECR | 500MB/month | Store Docker images |
| CloudWatch | 10 metrics, 5GB logs | Monitoring |
| API Gateway | 1M calls/month | REST/WebSocket APIs |
| Bedrock | Varies by model | Managed LLM APIs |

---

## 1. EC2 Setup for AI Services

```bash
# ─── Launch EC2 instance ──────────────────────────────────────────────────────
# In AWS Console: EC2 → Launch Instance
# AMI: Ubuntu 22.04 LTS
# Instance type: t3.medium (2 vCPU, 4GB RAM) — NOT free tier, but good for AI
# For free tier: t2.micro (1 vCPU, 1GB RAM) — only for API, not Ollama

# ─── Connect via SSH ──────────────────────────────────────────────────────────
ssh -i ~/.ssh/your-key.pem ubuntu@your-ec2-public-ip

# ─── Install everything ───────────────────────────────────────────────────────
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 curl git

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
newgrp docker

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:8b &

# Clone your project
git clone https://github.com/YOUR_USERNAME/ai-chat-api
cd ai-chat-api

# Run
docker compose up -d
```

---

## 2. Systemd Service — Keep App Running

```bash
# /etc/systemd/system/ai-api.service
sudo tee /etc/systemd/system/ai-api.service << 'EOF'
[Unit]
Description=AI Chat API
After=network.target docker.service
Requires=docker.service

[Service]
Type=forking
WorkingDirectory=/home/ubuntu/ai-chat-api
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-api
sudo systemctl start ai-api
sudo systemctl status ai-api
```

---

## 3. Nginx Reverse Proxy + SSL (Free with Let's Encrypt)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# Configure Nginx
sudo tee /etc/nginx/sites-available/ai-api << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;            # Critical for streaming!
        proxy_read_timeout 300s;        # Long timeout for LLM
        proxy_connect_timeout 10s;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/ai-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Free SSL certificate
sudo certbot --nginx -d your-domain.com
```

---

## 4. AWS Lambda — Serverless Endpoints (No Ollama, Use Groq)

```python
# lambda_function.py
import json
import os
from openai import OpenAI  # Use Groq

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda handler — triggered by API Gateway."""
    try:
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "")

        if not message:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "message is required"})
            }

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": message}],
            max_tokens=500,
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "response": response.choices[0].message.content,
                "model": "llama3-8b-8192",
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
```

```bash
# Deploy Lambda with AWS CLI
pip install openai -t ./package/
cp lambda_function.py ./package/
cd package && zip -r ../lambda.zip . && cd ..

aws lambda create-function \
  --function-name ai-chat \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda.zip \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --environment Variables="{GROQ_API_KEY=your-key}" \
  --timeout 30 \
  --memory-size 256
```

---

## 5. AWS ECR + ECS — Container Deployment

```bash
# ─── Push to ECR ──────────────────────────────────────────────────────────────
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1
ECR_REPO=$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/ai-service

# Login
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Create ECR repo
aws ecr create-repository --repository-name ai-service --region $AWS_REGION

# Build + push
docker build -t ai-service .
docker tag ai-service:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
```

---

## 6. Terraform — Infrastructure as Code (Free Tool)

```hcl
# main.tf — Deploy AI service to AWS
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = "us-east-1" }

# Security group
resource "aws_security_group" "ai_api" {
  name = "ai-api-sg"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["YOUR_IP/32"]  # Your IP only!
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# EC2 instance
resource "aws_instance" "ai_api" {
  ami                    = "ami-0c7217cdde317cfec"  # Ubuntu 22.04 us-east-1
  instance_type          = "t3.medium"
  key_name               = "your-key-pair"
  vpc_security_group_ids = [aws_security_group.ai_api.id]

  user_data = <<-EOF
    #!/bin/bash
    apt-get update -y
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    curl -fsSL https://ollama.ai/install.sh | sh
    git clone https://github.com/YOUR_USERNAME/ai-chat-api /app
    cd /app && docker compose up -d
  EOF

  tags = { Name = "ai-api-server" }
}

output "api_url" {
  value = "http://${aws_instance.ai_api.public_ip}:8000"
}
```

```bash
# Terraform commands
terraform init          # Initialize
terraform plan          # Preview changes
terraform apply         # Apply changes (type 'yes')
terraform destroy       # Tear everything down
terraform output        # Show outputs
```

---

## 7. AWS Bedrock — Managed AI Models

```python
import boto3
import json

# Bedrock gives access to Claude, Llama, Titan etc.
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Call Claude via Bedrock
response = bedrock.invoke_model(
    modelId="anthropic.claude-3-haiku-20240307-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": "Explain neural networks"}],
    }),
)

result = json.loads(response["body"].read())
print(result["content"][0]["text"])
```

---

## Cost Optimization Tips

1. **Use Spot Instances** — 70-90% cheaper than on-demand for non-critical workloads
2. **Stop EC2 at night** — Set a CloudWatch alarm + Lambda to auto-stop
3. **Use Groq free tier** — Instead of running Ollama on EC2 (saves compute costs)
4. **S3 for documents** — Don't store large files on EC2 EBS
5. **Lambda for low-traffic** — No server costs when there's no traffic
6. **Set billing alerts** — `aws budgets create-budget` — never get surprised
