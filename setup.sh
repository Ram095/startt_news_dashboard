# scripts/setup.sh
#!/bin/bash

# News Dashboard Setup Script
set -e

echo "🚀 Setting up News Dashboard..."

# Check if Python 3.9+ is installed
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.9+ is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# # Create virtual environment
# echo "📦 Creating virtual environment..."
# python3 -m venv venv
# source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Install NLTK data
echo "📚 Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs backups data config

# Copy configuration files
echo "⚙️ Setting up configuration..."
if [ ! -f config.yaml ]; then
    cp config.yaml.example config.yaml
    echo "📝 Created config.yaml from example. Please edit it with your settings."
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Created .env from example. Please edit it with your secrets."
fi

# Set up pre-commit hooks
if [ -f .pre-commit-config.yaml ]; then
    echo "🪝 Setting up pre-commit hooks..."
    pre-commit install
fi

# Initialize database (if PostgreSQL)
if command -v psql &> /dev/null; then
    echo "🗄️ Setting up PostgreSQL database..."
    # This would require database credentials
    echo "Please manually create the database and run:"
    echo "psql -d news_dashboard -f scripts/init_db.sql"
else
    echo "⚠️ PostgreSQL not found. Using SQLite for development."
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml with your settings"
echo "2. Edit .env with your API keys and secrets"
echo "3. If using PostgreSQL, create the database and run init_db.sql"
echo "4. Run: streamlit run app.py"
echo ""
echo "For Docker deployment:"
echo "1. docker-compose up -d"

