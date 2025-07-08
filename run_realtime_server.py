#!/usr/bin/env python3
"""
OpenManus 实时跟踪服务器启动脚本
启动HTTP API服务器和WebSocket服务，提供实时Agent执行跟踪功能
"""

import asyncio
import logging
import sys
import argparse
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn
    from app.api.server import app
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Please install required packages:")
    print("pip install fastapi uvicorn websockets")
    sys.exit(1)


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/realtime_server.log', mode='a')
        ]
    )

    # 创建日志目录
    Path('logs').mkdir(exist_ok=True)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="OpenManus 实时跟踪服务器")
    parser.add_argument(
        "--config",
        type=str,
        default="config-doubao.toml",
        help="配置文件名 (默认: config-doubao.toml)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="服务器主机地址 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="服务器端口 (默认: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用热重载 (开发模式)"
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    setup_logging()
    logger = logging.getLogger(__name__)

    # 设置配置文件环境变量
    config_path = project_root / "config" / args.config
    if config_path.exists():
        os.environ["OPENMANUS_CONFIG"] = str(config_path)
        logger.info(f"Using config file: {config_path}")
    else:
        logger.warning(f"Config file not found: {config_path}, using default config")

    logger.info("Starting OpenManus Real-time Tracking Server with Doubao LLM...")

    # 服务器配置
    server_config = {
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "log_level": "info",
        "access_log": True
    }

    try:
        # 启动服务器
        uvicorn.run("app.api.server:app", **server_config)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
