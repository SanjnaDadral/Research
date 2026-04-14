#!/usr/bin/env bash
# Exit on error, undefined, and pipe failures
set -o errexit -o nounset -o pipefail

echo "========================================="
echo "PaperAIzer Build Script for Render"
echo "========================================="

echo ""
echo "=== Step 1: Installing Python dependencies ==="
pip install -r requirements.txt --quiet
echo "✓ Dependencies installed"

echo ""
echo "=== Step 2: Collecting static files ==="
python manage.py collectstatic --no-input --clear --verbosity 2
echo "✓ Static files collected"

echo ""
echo "=== Step 3: Running database migrations ==="
python manage.py migrate --no-input --verbosity 2
echo "✓ Migrations completed"

echo ""
echo "=== Step 4: Creating superuser (if needed) ==="
python manage.py shell <<END
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@paperaizer.com', 'admin123')
    print("✓ Superuser created")
else:
    print("✓ Superuser already exists")
END

echo ""
echo "========================================="
echo "Build completed successfully!"
echo "========================================="
