#!/bin/bash
# AI-OS Deploy Script for Timeweb VPS (Ubuntu 22/24)
# Usage: ssh root@YOUR_IP 'bash -s' < deploy.sh

set -e

echo "=== AI-OS Deploy ==="

# 1. System update
apt update && apt upgrade -y

# 2. Install Docker
if ! command -v docker &> /dev/null; then
    echo "[1/5] Installing Docker..."
    apt install -y docker.io docker-compose-v2
    systemctl enable docker
    systemctl start docker
else
    echo "[1/5] Docker already installed"
fi

# 3. Install nginx for reverse proxy + SSL
if ! command -v nginx &> /dev/null; then
    echo "[2/5] Installing nginx..."
    apt install -y nginx certbot python3-certbot-nginx
else
    echo "[2/5] nginx already installed"
fi

# 4. Clone repo
echo "[3/5] Cloning AI-OS..."
cd /opt
if [ -d "ai-os" ]; then
    cd ai-os && git pull
else
    git clone https://github.com/abelbleoworld-blip/ai-os.git
    cd ai-os
fi

# 5. Setup env
echo "[4/5] Setting up environment..."
if [ ! -f .env ]; then
    echo "OPENROUTER_API_KEY=YOUR_KEY_HERE" > .env
    echo ">>> Edit /opt/ai-os/.env with your OpenRouter API key!"
fi

# 6. Build and run
echo "[5/5] Starting AI-OS..."
docker compose up --build -d

# 7. Setup nginx
cat > /etc/nginx/sites-available/ai-os << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/ai-os /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== AI-OS Deployed! ==="
echo "1. Edit API key:  nano /opt/ai-os/.env"
echo "2. Restart:       cd /opt/ai-os && docker compose up -d"
echo "3. Open:          http://$(curl -s ifconfig.me)"
echo ""
echo "For SSL (if you have a domain):"
echo "  certbot --nginx -d yourdomain.com"
echo ""
