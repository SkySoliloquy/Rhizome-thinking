#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Rhizome Thinking 部署脚本
.DESCRIPTION
    部署 Rhizome Thinking 到生产环境
#>

param(
    [string]$HostIP = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Rhizome Thinking 部署脚本" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
Write-Host "检查 Python 环境..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python 未安装" -ForegroundColor Red
    exit 1
}
Write-Host "✓ $pythonVersion" -ForegroundColor Green

# 检查虚拟环境
Write-Host ""
Write-Host "检查虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Yellow
    python -m venv venv
}
Write-Host "✓ 虚拟环境就绪" -ForegroundColor Green

# 激活虚拟环境
Write-Host ""
Write-Host "激活虚拟环境..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# 安装依赖
Write-Host ""
Write-Host "安装依赖..." -ForegroundColor Yellow
pip install -e ".[stage2]" -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 依赖安装失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 依赖安装完成" -ForegroundColor Green

# 检查环境变量
Write-Host ""
Write-Host "检查环境配置..." -ForegroundColor Yellow
if (-not $env:MINIMAX_API_KEY) {
    Write-Host "⚠️ 未设置 MINIMAX_API_KEY 环境变量" -ForegroundColor Yellow
    Write-Host "   请设置环境变量: $env:MINIMAX_API_KEY = 'your-api-key'" -ForegroundColor Gray
}

# 初始化存储
Write-Host ""
Write-Host "初始化存储..." -ForegroundColor Yellow
python -c "from rhizome.config import settings; settings.ensure_directories()"
Write-Host "✓ 存储目录就绪" -ForegroundColor Green

# 检查向量库
Write-Host ""
Write-Host "检查向量库..." -ForegroundColor Yellow
try {
    $vectorCount = python -c "from rhizome.retrieval.vector_store import VectorStore; vs = VectorStore(); print(vs.get_stats()['total_vectors'])" 2>$null
    Write-Host "✓ 向量库中有 $vectorCount 个向量" -ForegroundColor Green
    
    if ($vectorCount -eq 0) {
        Write-Host "⚠️ 向量库为空，建议运行: rhz vectorize" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ 无法检查向量库，可能需要初始化" -ForegroundColor Yellow
}

# 启动服务
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "🎉 部署完成！" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动服务器:" -ForegroundColor Yellow
Write-Host "  rhz serve --host $HostIP --port $Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "或使用 uvicorn 直接启动:" -ForegroundColor Yellow
Write-Host "  uvicorn rhizome.api.main:app --host $HostIP --port $Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "API 文档地址:" -ForegroundColor Yellow
Write-Host "  http://localhost:$Port/docs" -ForegroundColor Cyan
Write-Host ""

# 询问是否启动
$startNow = Read-Host "是否立即启动服务器? (y/n)"
if ($startNow -eq "y" -or $startNow -eq "Y") {
    Write-Host ""
    Write-Host "启动服务器..." -ForegroundColor Green
    rhz serve --host $HostIP --port $Port
}
