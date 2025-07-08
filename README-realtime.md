# OpenManus 实时跟踪系统

## 概述

这是 OpenManus 项目的实时跟踪系统实现，提供了完整的事件驱动架构，支持 Agent 执行过程的实时监控和数据持久化。

## 功能特性

- ✅ **事件驱动架构**: 所有组件通过事件总线进行通信
- ✅ **实时 WebSocket 推送**: 前端实时显示 Agent 执行过程
- ✅ **会话管理**: 完整的会话生命周期管理
- ✅ **RESTful API**: 标准的 HTTP 接口
- ✅ **最小侵入**: 不破坏现有代码结构

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements-realtime.txt
```

### 2. 配置豆包模型

系统已预配置豆包模型，配置文件位于 `config/config-doubao.toml`：

```toml
[llm]
api_type = 'openai'
model = "ep-20250620094521-tdv5v"
base_url = "https://ark.cn-beijing.volces.com/api/v3"
api_key = "0f7502a9-c9a1-43c5-951a-7a2e39df15df"
max_tokens = 32768
temperature = 0.0
```

### 3. 启动服务器

```bash
# 使用默认豆包配置启动
python run_realtime_server.py

# 或指定其他配置文件
python run_realtime_server.py --config config.toml

# 开发模式（热重载）
python run_realtime_server.py --reload
```

服务器将在 `http://localhost:8000` 启动。

### 3. 访问测试页面

打开浏览器访问：`http://localhost:8000/static/index.html`

## API 接口

### 会话管理

- `POST /api/sessions/start` - 启动新会话
- `GET /api/sessions/{session_id}` - 获取会话信息
- `GET /api/sessions` - 获取会话列表
- `POST /api/sessions/{session_id}/stop` - 停止会话
- `POST /api/sessions/{session_id}/continue` - 继续会话

### WebSocket

- `WS /ws/{session_id}` - 实时事件推送

### 系统信息

- `GET /health` - 健康检查
- `GET /api/stats` - 系统统计信息

## 架构说明

### 事件类型

系统定义了完整的事件类型体系：

- **会话事件**: `session.create.request`, `session.started`, `session.stopped`
- **Agent 事件**: `agent.step.start`, `agent.step.end`, `agent.thinking`
- **工具事件**: `tool.call.start`, `tool.call.end`, `tool.call.error`
- **沙箱事件**: `sandbox.command.start`, `sandbox.command.output`

### 组件结构

```
app/
├── events/           # 事件系统
│   ├── types.py     # 事件类型定义
│   └── bus.py       # 事件总线实现
├── session/         # 会话管理
│   └── manager.py   # 会话管理器
├── execution/       # 执行管理
│   └── manager.py   # 执行管理器
└── api/            # API 服务
    └── server.py   # HTTP/WebSocket 服务器
```

## 使用示例

### 启动 Agent

```python
import requests

response = requests.post('http://localhost:8000/api/sessions/start', json={
    "prompt": "创建一个 Hello World 程序",
    "agent_type": "manus",
    "max_steps": 5
})

session_info = response.json()
print(f"会话ID: {session_info['session_id']}")
```

### WebSocket 连接

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);

ws.onmessage = function(event) {
    const eventData = JSON.parse(event.data);
    console.log('收到事件:', eventData.event_type, eventData.data);
};
```

## 开发说明

### 添加新的事件类型

1. 在 `app/events/types.py` 中添加新的 `EventType`
2. 在相应组件中发布事件
3. 在需要的地方订阅事件

### 扩展 Agent 支持

1. 在 `app/execution/manager.py` 的 `_create_agent` 方法中添加新的 Agent 类型
2. 确保新的 Agent 继承自 `BaseAgent` 并支持事件发布

### 添加新的 API 端点

在 `app/api/server.py` 中添加新的路由处理器。

## 测试

### 运行测试

```bash
pytest tests/
```

### 手动测试

1. 启动服务器：`python run_realtime_server.py`
2. 访问测试页面：`http://localhost:8000/static/index.html`
3. 输入任务并启动 Agent
4. 观察实时事件流

## 配置

目前使用默认配置，后续可以通过配置文件进行自定义：

- 服务器端口：8000
- WebSocket 路径：`/ws/{session_id}`
- 日志级别：INFO
- 事件队列大小：无限制

## 故障排除

### 常见问题

1. **WebSocket 连接失败**
   - 检查防火墙设置
   - 确认服务器正在运行
   - 检查浏览器控制台错误

2. **Agent 启动失败**
   - 检查服务器日志
   - 确认依赖已正确安装
   - 验证请求参数格式

3. **事件丢失**
   - 检查事件总线状态
   - 确认订阅者正确注册
   - 查看错误日志

### 日志文件

- 服务器日志：`logs/realtime_server.log`
- 控制台输出：实时显示

## 下一步计划

- [ ] 数据持久化（SQLite）
- [ ] 沙箱事件集成
- [ ] 更多 Agent 类型支持
- [ ] 性能优化
- [ ] 安全性增强

## 贡献

欢迎提交 Issue 和 Pull Request！
