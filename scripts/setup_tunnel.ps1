#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Cloudflare Tunnel 配置脚本
.DESCRIPTION
    设置 Cloudflare Tunnel 实现外网访问
#>

$ErrorActionPreference = "Stop"

Write-Host "🌐 Cloudflare Tunnel 配置" -ForegroundColor Cyan
Write-Host ""

# 检查 cloudflared
Write-Host "检查 cloudflared..." -ForegroundColor Yellow
try {
    $version = cloudflared --version 2>&1
    Write-Host "✓ $version" -ForegroundColor Green
} catch {
    Write-Host "❌ cloudflared 未安装" -ForegroundColor Red
    Write-Host ""
    Write-Host "安装方法:" -ForegroundColor Yellow
    Write-Host "  Windows: winget install Cloudflare.cloudflared" -ForegroundColor Gray
    Write-Host "  或访问: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "配置步骤:" -ForegroundColor Cyan
Write-Host ""

# 步骤 1: 登录
Write-Host "1. 登录 Cloudflare" -ForegroundColor Yellow
Write-Host "   运行: cloudflared tunnel login" -ForegroundColor Gray
Write-Host "   按照提示完成认证" -ForegroundColor Gray
Write-Host ""

# 步骤 2: 创建隧道
Write-Host "2. 创建隧道" -ForegroundColor Yellow
$tunnelName = Read-Host "   输入隧道名称 (例如: rhizome)"
if ($tunnelName) {
    Write-Host "   运行: cloudflared tunnel create $tunnelName" -ForegroundColor Gray
} else {
    Write-Host "   运行: cloudflared tunnel create rhizome" -ForegroundColor Gray
}
Write-Host ""

# 步骤 3: 配置域名
Write-Host "3. 配置域名路由" -ForegroundColor Yellow
$domain = Read-Host "   输入你的域名 (例如: kb.yourdomain.com)"
if ($domain -and $tunnelName) {
    Write-Host "   运行: cloudflared tunnel route dns $tunnelName $domain" -ForegroundColor Gray
}
Write-Host ""

# 步骤 4: 创建配置文件
Write-Host "4. 创建配置文件" -ForegroundColor Yellow

$configDir = "$env:USERPROFILE\.cloudflared"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}

$configPath = "$configDir\config.yml"

if ($tunnelName) {
    $configContent = @"
tunnel: $tunnelName
credentials-file: $configDir\$tunnelName.json

ingress:
  - hostname: $domain
    service: http://localhost:8000
  - service: http_status:404
"@
    
    $configContent | Out-File -FilePath $configPath -Encoding UTF8
    Write-Host "   ✓ 配置文件已创建: $configPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "   配置内容:" -ForegroundColor Gray
    Write-Host $configContent -ForegroundColor Gray
}

Write-Host ""

# 步骤 5: 启动隧道
Write-Host "5. 启动隧道" -ForegroundColor Yellow
Write-Host "   运行: cloudflared tunnel run $tunnelName" -ForegroundColor Gray
Write-Host ""

# 步骤 6: 后台运行（可选）
Write-Host "6. 设置后台运行 (可选)" -ForegroundColor Yellow
Write-Host "   Windows: 使用任务计划程序或 NSSM" -ForegroundColor Gray
Write-Host "   Linux: 使用 systemd" -ForegroundColor Gray
Write-Host ""

# 创建 systemd 服务文件示例（用于参考）
$systemdExample = @"
# /etc/systemd/system/cloudflared-rhizome.service
[Unit]
Description=Cloudflare Tunnel for Rhizome Thinking
After=network.target

[Service]
Type=simple
User=$env:USERNAME
ExecStart=cloudflared tunnel run $tunnelName
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"@

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Systemd 服务文件示例:" -ForegroundColor Yellow
Write-Host $systemdExample -ForegroundColor Gray
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 验证步骤
Write-Host "验证步骤:" -ForegroundColor Yellow
Write-Host "  1. 确保 Rhizome 服务器在本地运行: rhz serve" -ForegroundColor Gray
Write-Host "  2. 启动隧道: cloudflared tunnel run $tunnelName" -ForegroundColor Gray
Write-Host "  3. 访问: https://$domain" -ForegroundColor Gray
Write-Host ""

$startNow = Read-Host "是否现在启动隧道? (y/n)"
if (($startNow -eq "y" -or $startNow -eq "Y") -and $tunnelName) {
    Write-Host ""
    Write-Host "启动隧道..." -ForegroundColor Green
    cloudflared tunnel run $tunnelName
}
