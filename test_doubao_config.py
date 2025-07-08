#!/usr/bin/env python3
"""
测试豆包模型配置
验证豆包模型是否正确配置并能正常工作
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置配置文件
os.environ["OPENMANUS_CONFIG"] = str(project_root / "config" / "config-doubao.toml")

try:
    from app.llm import LLM
    from app.config import config
except ImportError as e:
    print(f"导入失败: {e}")
    print("请确保已安装所需依赖: pip install -r requirements-realtime.txt")
    sys.exit(1)


async def test_doubao_llm():
    """测试豆包LLM配置"""
    print("🧪 测试豆包模型配置...")
    
    try:
        # 创建LLM实例
        llm = LLM()
        
        print(f"✅ LLM实例创建成功")
        print(f"   模型: {llm.model}")
        print(f"   API类型: {llm.api_type}")
        print(f"   基础URL: {llm.base_url}")
        print(f"   最大Token: {llm.max_tokens}")
        
        # 测试简单对话
        print("\n🤖 测试LLM对话...")
        messages = [
            {"role": "user", "content": "你好，请简单介绍一下你自己。"}
        ]
        
        response = await llm.ask(messages, stream=False)
        
        print(f"✅ LLM响应成功:")
        print(f"   响应: {response[:200]}{'...' if len(response) > 200 else ''}")
        
        # 测试Token计数
        print(f"\n📊 Token使用统计:")
        print(f"   输入Token: {llm.total_input_tokens}")
        print(f"   输出Token: {llm.total_completion_tokens}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def test_config_loading():
    """测试配置加载"""
    print("\n⚙️  测试配置加载...")
    
    try:
        # 检查配置
        llm_config = config.llm["default"]
        
        print(f"✅ 配置加载成功:")
        print(f"   模型: {llm_config.model}")
        print(f"   API类型: {llm_config.api_type}")
        print(f"   基础URL: {llm_config.base_url}")
        print(f"   API密钥: {llm_config.api_key[:10]}...{llm_config.api_key[-4:]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 OpenManus 豆包模型配置测试")
    print("=" * 50)
    
    async def run_tests():
        # 测试配置加载
        config_ok = await test_config_loading()
        
        if config_ok:
            # 测试LLM
            llm_ok = await test_doubao_llm()
            
            if llm_ok:
                print("\n🎉 所有测试通过！豆包模型配置正确。")
                print("\n📝 下一步:")
                print("   1. 运行实时跟踪服务器: python run_realtime_server.py")
                print("   2. 访问测试页面: http://localhost:8000/static/index.html")
                return True
            else:
                print("\n❌ LLM测试失败，请检查API密钥和网络连接。")
                return False
        else:
            print("\n❌ 配置加载失败，请检查配置文件。")
            return False
    
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
