# Setup script for Rhizome Thinking (Windows PowerShell)

Write-Host "🚀 Setting up Rhizome Thinking..." -ForegroundColor Green

# Check Python version
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python 3\.(1[1-9]|[2-9][0-9])") {
    Write-Host "✓ Python version check passed: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -e ".[stage1,dev]"

# Create storage directories
Write-Host "Creating storage directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "storage\nodes", "storage\metadata", "storage\chroma" | Out-Null

# Copy environment file if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "⚠ Please edit .env file and add your MiniMax API key" -ForegroundColor Yellow
}

Write-Host "" 
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host "" 
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env file and add your MiniMax API key"
Write-Host "  2. Run 'rhz init' to initialize storage"
Write-Host "  3. Run 'rhz --help' to see available commands"
Write-Host "  4. Try 'rhz add --mock \"Your first note\"' to test"
