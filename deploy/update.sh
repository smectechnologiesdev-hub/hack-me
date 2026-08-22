#!/usr/bin/env bash
# Pull latest code and roll the service. Run from the project directory.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart bruteforce-lab
echo "Deploy complete."
