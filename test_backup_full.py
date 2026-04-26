#!/usr/bin/env python3
"""
完整备份功能测试 - 模拟前端调用
"""
import requests
import json
import os
import tempfile
import zipfile

BASE_URL = "http://localhost:8000"

def test_full_backup_workflow():
    """测试完整的备份工作流"""
    
    print("=" * 70)
    print("完整备份功能测试")
    print("=" * 70)
    
    session = requests.Session()
    
    # 1. 获取备份列表
    print("\n1. 获取备份列表...")
    try:
        response = session.get(f"{BASE_URL}/api/v1/backups")
        data = response.json()
        backups = data.get("backups", [])
        print(f"   ✓ 获取到 {len(backups)} 个备份")
        
        if not backups:
            print("   ✗ 没有备份，无法继续测试")
            return False
            
        test_backup = backups[0]
        test_name = test_backup['name']
        print(f"   选择测试备份: {test_name}")
        
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return False
    
    # 2. 测试获取备份信息（使用URL编码）
    print(f"\n2. 测试获取备份信息...")
    try:
        from urllib.parse import quote
        encoded_name = quote(test_name)
        print(f"   原始名称: {test_name}")
        print(f"   URL编码: {encoded_name}")
        
        response = session.get(f"{BASE_URL}/api/v1/backups/{encoded_name}")
        if response.status_code == 200:
            print(f"   ✓ 成功获取备份信息")
            info = response.json()
            print(f"   - 名称: {info.get('name')}")
            print(f"   - 节点数: {info.get('node_count')}")
        else:
            print(f"   ✗ 失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return False
    
    # 3. 测试下载备份
    print(f"\n3. 测试下载备份...")
    try:
        response = session.get(f"{BASE_URL}/api/v1/backups/{encoded_name}/download")
        if response.status_code == 200:
            print(f"   ✓ 下载成功，大小: {len(response.content)} bytes")
            # 保存到临时文件用于导入测试
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_file.write(response.content)
            temp_file.close()
            download_path = temp_file.name
            print(f"   临时文件: {download_path}")
        else:
            print(f"   ✗ 下载失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return False
    
    # 4. 测试导入备份
    print(f"\n4. 测试导入备份...")
    try:
        with open(download_path, 'rb') as f:
            files = {'file': (test_name, f, 'application/zip')}
            response = session.post(f"{BASE_URL}/api/v1/backups/upload", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ 导入成功")
            print(f"   - 新名称: {result.get('backup_name')}")
            print(f"   - 节点数: {result.get('node_count')}")
            imported_name = result.get('backup_name')
        else:
            print(f"   ✗ 导入失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return False
    finally:
        # 清理临时文件
        if os.path.exists(download_path):
            os.unlink(download_path)
    
    # 5. 测试恢复备份
    print(f"\n5. 测试恢复备份...")
    try:
        # 使用导入的备份进行恢复
        from urllib.parse import quote
        encoded_imported = quote(imported_name)
        
        response = session.post(
            f"{BASE_URL}/api/v1/backups/{encoded_imported}/restore",
            json={"confirm": True}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ 恢复成功")
            print(f"   - 消息: {result.get('message')}")
            print(f"   - 恢复节点数: {result.get('restored_nodes')}")
        elif response.status_code == 404:
            print(f"   ✗ 备份文件未找到 (404)")
            print(f"   请求URL: /api/v1/backups/{encoded_imported}/restore")
            return False
        else:
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return False
    
    # 6. 测试删除备份
    print(f"\n6. 测试删除备份...")
    try:
        response = session.delete(f"{BASE_URL}/api/v1/backups/{encoded_imported}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ 删除成功: {result.get('message')}")
        elif response.status_code == 404:
            print(f"   ✗ 备份文件未找到 (404)")
            return False
        else:
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✓ 所有测试通过！")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = test_full_backup_workflow()
    exit(0 if success else 1)
