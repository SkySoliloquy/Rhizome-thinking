#!/usr/bin/env python3
"""
备份API功能测试脚本
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_backup_api():
    """测试备份API的各个功能"""
    
    print("=" * 60)
    print("备份API功能测试")
    print("=" * 60)
    
    # 1. 获取备份列表
    print("\n1. 获取备份列表...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/backups")
        if response.status_code == 200:
            data = response.json()
            backups = data.get("backups", [])
            print(f"   ✓ 成功获取 {len(backups)} 个备份")
            if backups:
                print(f"   最新备份: {backups[0]['name']}")
                test_backup_name = backups[0]['name']
            else:
                print("   ✗ 没有备份可供测试")
                return
        else:
            print(f"   ✗ 失败: HTTP {response.status_code}")
            return
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return
    
    # 2. 获取单个备份信息
    print(f"\n2. 获取备份信息: {test_backup_name}...")
    try:
        encoded_name = requests.utils.quote(test_backup_name)
        response = requests.get(f"{BASE_URL}/api/v1/backups/{encoded_name}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 成功获取备份信息")
            print(f"   - 名称: {data.get('name')}")
            print(f"   - 节点数: {data.get('node_count')}")
            print(f"   - 创建时间: {data.get('created_at')}")
        else:
            print(f"   ✗ 失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")
    
    # 3. 测试恢复备份（不实际恢复，只测试API调用）
    print(f"\n3. 测试恢复备份API: {test_backup_name}...")
    try:
        encoded_name = requests.utils.quote(test_backup_name)
        response = requests.post(
            f"{BASE_URL}/api/v1/backups/{encoded_name}/restore",
            json={"confirm": False}  # 不确认，只测试API是否可访问
        )
        # 即使返回400/500也可能是正常的（因为没有确认）
        print(f"   状态码: {response.status_code}")
        if response.status_code in [200, 400, 409]:
            print(f"   ✓ API可访问")
            print(f"   响应: {response.json()}")
        elif response.status_code == 404:
            print(f"   ✗ 备份文件未找到")
            print(f"   响应: {response.text}")
        else:
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")
    
    # 4. 测试删除备份（不实际删除，只测试API调用）
    print(f"\n4. 测试删除备份API: {test_backup_name}...")
    try:
        encoded_name = requests.utils.quote(test_backup_name)
        # 使用GET代替DELETE来测试（避免误删）
        response = requests.get(f"{BASE_URL}/api/v1/backups/{encoded_name}")
        if response.status_code == 200:
            print(f"   ✓ 备份文件存在，可删除")
        elif response.status_code == 404:
            print(f"   ✗ 备份文件不存在")
        else:
            print(f"   状态码: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_backup_api()
