#!/usr/bin/env bash
# =============================================================================
# SolarGuard -- Automated Setup Script for Ubuntu Linux ARM64
# Designed for Oracle Cloud Always Free Ampere A1 (Ubuntu 22.04/24.04 LTS aarch64)
# =============================================================================

set -o errexit
set -o nounset

echo "========================================================================"
echo " SolarGuard -- Ubuntu Linux ARM64 Automated Provisioning"
echo " Target Architecture: aarch64 (Oracle Cloud Ampere A1)"
echo "========================================================================"

# 1. Verify Architecture
ARCH=$(uname -m)
echo "System architecture detected: ${ARCH}"
if [ "${ARCH}" != "aarch64" ] && [ "${ARCH}" != "arm64" ]; then
    echo "[WARNING] This script is optimized for ARM64 (aarch64). Detected: ${ARCH}."
    echo "Proceeding with standard Linux setup..."
fi

# 2. Update System & Install Dependencies
echo "[Step 1/8] Updating package repository and installing prerequisites..."
sudo apt-get update -y
sudo apt-get install -y \
    software-properties-common \
    build-essential \
    curl \
    git \
    sqlite3 \
    nginx \
    libgl1 \
    libglib2.0-0 \
    ufw

# Ensure Python 3.11 is available
if ! command -v python3.11 &> /dev/null; then
    echo "Adding deadsnakes PPA for Python 3.11..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -y
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

# 3. Create Dedicated System User & Directories
echo "[Step 2/8] Creating service account and directories..."
if ! id "solarguard" &>/dev/null; then
    sudo useradd -r -s /bin/false -d /var/www/solarguard solarguard
fi

sudo mkdir -p /var/www/solarguard
sudo mkdir -p /var/log/solarguard
sudo mkdir -p /var/www/solarguard/backups
sudo mkdir -p /var/www/solarguard/media
sudo mkdir -p /etc/solarguard

# 4. Set Up Python Virtual Environment
echo "[Step 3/8] Creating isolated Python 3.11 virtual environment..."
sudo python3.11 -m venv /var/www/solarguard/venv
sudo /var/www/solarguard/venv/bin/pip install --upgrade pip

# 5. Install Dependencies
echo "[Step 4/8] Installing SolarGuard dependencies (TensorFlow, Keras, OpenCV, WhiteNoise, Gunicorn)..."
cd /var/www/solarguard
sudo /var/www/solarguard/venv/bin/pip install -r requirements.txt

# 6. Generate Production Environment Configuration
echo "[Step 5/8] Configuring production environment (/etc/solarguard/solarguard.env)..."
if [ ! -f /etc/solarguard/solarguard.env ]; then
    RANDOM_KEY=$(python3.11 -c "import secrets; print(secrets.token_urlsafe(50))")
    PUBLIC_IP=$(curl -s ifconfig.me || echo "127.0.0.1")
    
    sudo bash -c "cat <<EOF > /etc/solarguard/solarguard.env
# SolarGuard Production Environment (Ubuntu ARM64)
DJANGO_SECRET_KEY=${RANDOM_KEY}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,${PUBLIC_IP}
DJANGO_CSRF_TRUSTED_ORIGINS=http://${PUBLIC_IP},https://${PUBLIC_IP}
SOLARGUARD_MEDIA_ROOT=/var/www/solarguard/media
SOLARGUARD_MODEL_VERSION=v3
SOLARGUARD_USE_REAL_CNN=True
SOLARGUARD_USE_DEV_MOCK=False
SOLARGUARD_CONFIDENCE_THRESHOLD=60.0
WEB_CONCURRENCY=2
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=120
DJANGO_SECURE_SSL_REDIRECT=False
EOF"
    sudo chmod 600 /etc/solarguard/solarguard.env
    sudo chown solarguard:solarguard /etc/solarguard/solarguard.env
    echo "  [OK] Generated secure /etc/solarguard/solarguard.env with host IP: ${PUBLIC_IP}"
fi

# 7. Collect Static Assets & Run Migrations
echo "[Step 6/8] Collecting static assets and executing database migrations..."
sudo -E /var/www/solarguard/venv/bin/python manage.py collectstatic --no-input
sudo -E /var/www/solarguard/venv/bin/python manage.py migrate --no-input

# 8. Verify AI Model Integrity on ARM64
echo "[Step 7/8] Verifying MobileNetV2 v3.0 model loading on ARM64 architecture..."
sudo -E /var/www/solarguard/venv/bin/python manage.py verify_model

# 9. Configure Nginx and Systemd Service
echo "[Step 8/8] Installing systemd service and configuring Nginx..."
sudo cp deploy/systemd/solarguard.service /etc/systemd/system/solarguard.service
sudo cp deploy/nginx/solarguard.conf /etc/nginx/sites-available/solarguard.conf

if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm -f /etc/nginx/sites-enabled/default
fi
sudo ln -sf /etc/nginx/sites-available/solarguard.conf /etc/nginx/sites-enabled/

# Set ownership
sudo chown -R solarguard:solarguard /var/www/solarguard
sudo chown -R solarguard:solarguard /var/log/solarguard
sudo chmod 750 /var/www/solarguard/media

# Reload services
sudo systemctl daemon-reload
sudo systemctl enable solarguard.service
sudo systemctl restart solarguard.service
sudo nginx -t
sudo systemctl restart nginx

# Firewall configuration
echo "Configuring UFW firewall (allowing ports 22, 80, 443)..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

echo "========================================================================"
echo " SolarGuard Ubuntu ARM64 Deployment Complete!"
echo " Service Status: sudo systemctl status solarguard"
echo " Nginx Status:   sudo systemctl status nginx"
echo " Live Site:      http://${PUBLIC_IP}"
echo "========================================================================"
