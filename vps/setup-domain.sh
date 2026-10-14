#!/bin/bash
# Pasang tracker.joysi.my.id (HTTPS) di depan workout tracker.
# Syarat: DNS A record tracker.joysi.my.id -> IP VPS sudah dibuat di Cloudflare.
# Jalankan DI VPS dari dalam folder vps/ hasil git pull.
set -e

DOMAIN="tracker.joysi.my.id"
EMAIL="ganti-dengan-email@kamu.com"   # <-- GANTI dengan email kamu (untuk notif expiry cert)

if [ "$EMAIL" = "ganti-dengan-email@kamu.com" ]; then
  echo "Ganti dulu EMAIL di dalam script ini, lalu jalankan lagi."
  exit 1
fi

sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
sudo ufw allow 80,443/tcp 2>/dev/null || true

sudo cp nginx-tracker.conf /etc/nginx/sites-available/tracker
sudo ln -sf /etc/nginx/sites-available/tracker /etc/nginx/sites-enabled/tracker
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect

echo ""
echo "==================================="
echo "Live di: https://$DOMAIN"
echo "Cert auto-renew via systemd timer bawaan certbot."
echo "Opsional (opsional): tutup port 8000 publik -> sudo ufw delete allow 8000/tcp"
echo "==================================="
