"""检查服务器状态."""
import requests

try:
    # 检查健康端点
    r = requests.get("http://localhost:8084/health", timeout=5)
    print(f"Health check: {r.status_code}")
    print(f"Response: {r.text}")
    
    # 检查主题列表
    r = requests.get("http://localhost:8084/api/v1/themes", timeout=5)
    print(f"\nThemes list: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total themes: {len(data)}")
        
except Exception as e:
    print(f"Server check failed: {e}")
