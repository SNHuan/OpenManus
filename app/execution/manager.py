"""
执行管理器
负责Agent的创建、执行和生命周期管理
"""

import asyncio
import logging
from typing import Dict, Optional

from app.events.bus import EventBus
from app.events.types import Event, EventType
from app.agent.base import BaseAgent
from app.llm import LLM


class ExecutionManager:
    """执行管理器 - 管理Agent的创建和执行"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.component_name = "execution_manager"
        self.running_agents: Dict[str, BaseAgent] = {}
        self.execution_tasks: Dict[str, asyncio.Task] = {}
        self.logger = logging.getLogger(__name__)

        # 订阅相关事件
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """订阅执行相关事件"""
        # 只处理发送给执行管理器的事件
        self.event_bus.subscribe_component(self.component_name, self._handle_targeted_events)

        self.logger.info("ExecutionManager subscribed to events")

    async def _handle_targeted_events(self, event: Event):
        """处理发送给执行管理器的事件"""
        self.logger.info(f"ExecutionManager received event: {event.event_type}, target: {event.target}")

        if event.target != self.component_name:
            self.logger.info(f"Event not for this component, ignoring")
            return

        try:
            if event.event_type == EventType.SESSION_START_REQUEST:
                self.logger.info(f"Handling SESSION_START_REQUEST for session: {event.session_id}")
                await self._start_agent_execution(event)
            elif event.event_type == EventType.SESSION_STOP_REQUEST:
                self.logger.info(f"Handling SESSION_STOP_REQUEST for session: {event.session_id}")
                await self._stop_agent_execution(event)
        except Exception as e:
            self.logger.error(f"Error handling event {event.event_type}: {e}")
            await self._publish_error(event, str(e))

    async def _start_agent_execution(self, event: Event):
        """启动Agent执行"""
        session_id = event.session_id

        if not session_id:
            self.logger.error("No session_id in start request")
            return

        if session_id in self.running_agents:
            self.logger.warning(f"Agent already running for session: {session_id}")
            return

        try:
            # 创建Agent实例
            agent = await self._create_agent(event.data)

            # 设置会话上下文
            agent.session_id = session_id
            agent.event_bus = self.event_bus  # 所有Agent都应该有event_bus属性

            self.running_agents[session_id] = agent

            self.logger.info(f"Agent created for session: {session_id}")

            # 发布启动成功事件
            started_event = Event(
                event_type=EventType.SESSION_STARTED,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "agent_type": event.data.get("agent_type", "manus"),
                    "config": event.data.get("config", {})
                }
            )

            await self.event_bus.publish(started_event)

            # 如果启用了沙箱，创建沙箱
            if event.data.get("use_sandbox", True):
                sandbox_create_event = Event(
                    event_type=EventType.SANDBOX_CREATE_REQUEST,
                    source=self.component_name,
                    session_id=session_id,
                    correlation_id=event.correlation_id,
                    data=event.data.get("sandbox_config", {})
                )
                await self.event_bus.publish(sandbox_create_event)

            # 在后台任务中运行Agent
            task = asyncio.create_task(self._run_agent(agent, event.data.get("prompt", "")))
            self.execution_tasks[session_id] = task

        except Exception as e:
            self.logger.error(f"Failed to start agent for session {session_id}: {e}")
            await self._publish_error(event, str(e))

    async def _stop_agent_execution(self, event: Event):
        """停止Agent执行"""
        session_id = event.session_id

        if not session_id:
            self.logger.error("No session_id in stop request")
            return

        # 检查是否已经在处理停止请求
        if session_id not in self.running_agents and session_id not in self.execution_tasks:
            self.logger.info(f"Session {session_id} already stopped or not running")
            return

        try:
            stopped_reason = "user_requested"

            # 取消执行任务
            if session_id in self.execution_tasks:
                task = self.execution_tasks[session_id]
                if not task.done():
                    task.cancel()
                    self.logger.info(f"Cancelled execution task for session: {session_id}")

                try:
                    await task
                except asyncio.CancelledError:
                    self.logger.info(f"Agent execution cancelled for session: {session_id}")
                    stopped_reason = "cancelled"
                except Exception as task_error:
                    self.logger.error(f"Error in agent execution task: {task_error}")
                    stopped_reason = "error"

                del self.execution_tasks[session_id]

            # 清理Agent
            if session_id in self.running_agents:
                agent = self.running_agents[session_id]
                # 这里可以添加Agent的清理逻辑
                del self.running_agents[session_id]
                self.logger.info(f"Cleaned up agent for session: {session_id}")

            self.logger.info(f"Agent execution stopped for session: {session_id}")

            # 发布停止事件
            stopped_event = Event(
                event_type=EventType.SESSION_STOPPED,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "reason": stopped_reason,
                    "status": "stopped"
                }
            )

            await self.event_bus.publish(stopped_event)

        except Exception as e:
            self.logger.error(f"Failed to stop agent for session {session_id}: {e}")
            await self._publish_error(event, str(e))

    async def _run_agent(self, agent: BaseAgent, prompt: str):
        """运行Agent"""
        session_id = agent.session_id

        try:
            self.logger.info(f"Starting agent execution for session: {session_id}")

            # 运行Agent
            result = await agent.run(prompt)

            self.logger.info(f"Agent execution completed for session: {session_id}")

            # 发布完成事件
            complete_event = Event(
                event_type=EventType.SESSION_STOPPED,
                source=self.component_name,
                session_id=session_id,
                data={
                    "result": result,
                    "status": "completed",
                    "reason": "task_completed"
                }
            )

            await self.event_bus.publish(complete_event)

        except asyncio.CancelledError:
            self.logger.info(f"Agent execution cancelled for session: {session_id}")
            raise
        except Exception as e:
            self.logger.error(f"Agent execution failed for session {session_id}: {e}")

            error_event = Event(
                event_type=EventType.SESSION_ERROR,
                source=self.component_name,
                session_id=session_id,
                data={
                    "error": str(e),
                    "stage": "execution"
                }
            )
            await self.event_bus.publish(error_event)

        finally:
            # 清理资源
            if session_id in self.running_agents:
                del self.running_agents[session_id]
            if session_id in self.execution_tasks:
                del self.execution_tasks[session_id]

    async def _create_agent(self, request_data: dict) -> BaseAgent:
        """根据请求数据创建Agent实例"""
        agent_type = request_data.get("agent_type", "manus")
        config = request_data.get("config", {})

        self.logger.info(f"Creating agent of type: {agent_type}")

        # 创建真正的Agent实例
        if agent_type == "manus":
            from app.agent.manus import Manus
            self.logger.info(f"Creating Manus agent for real task execution")
            return Manus(**config)
        else:
            # 对于其他类型，暂时使用MockAgent
            self.logger.info(f"Creating MockAgent for type: {agent_type} (not implemented yet)")
            return MockAgent(name=agent_type, **config)

    async def _publish_error(self, original_event: Event, error_message: str):
        """发布错误事件"""
        error_event = Event(
            event_type=EventType.SESSION_ERROR,
            source=self.component_name,
            session_id=original_event.session_id,
            correlation_id=original_event.event_id,
            data={
                "error": error_message,
                "original_event_type": original_event.event_type.value
            }
        )
        await self.event_bus.publish(error_event)

    def get_running_sessions(self) -> list[str]:
        """获取正在运行的会话列表"""
        return list(self.running_agents.keys())

    def get_stats(self) -> dict:
        """获取执行管理器统计信息"""
        return {
            "running_agents": len(self.running_agents),
            "execution_tasks": len(self.execution_tasks),
            "sessions": list(self.running_agents.keys())
        }


class MockAgent(BaseAgent):
    """模拟Agent - 用于测试最小可运行版本，集成真实LLM"""

    def __init__(self, name: str = "mock", **kwargs):
        # 设置默认值
        if 'max_steps' not in kwargs:
            kwargs['max_steps'] = 5

        super().__init__(name=name, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.event_bus = None
        self.session_id = None

    async def step(self) -> str:
        """模拟执行步骤，使用真实LLM"""
        self.logger.info(f"MockAgent executing step {self.current_step}")

        # 发布步骤开始事件
        if self.event_bus and self.session_id:
            step_start_event = Event(
                event_type=EventType.AGENT_STEP_START,
                source=f"agent_{self.name}",
                session_id=self.session_id,
                data={
                    "step_number": self.current_step,
                    "max_steps": self.max_steps
                }
            )
            await self.event_bus.publish(step_start_event)

            # 发布LLM调用开始事件
            llm_start_event = Event(
                event_type=EventType.LLM_CALL_START,
                source=f"agent_{self.name}",
                session_id=self.session_id,
                data={
                    "model": self.llm.model,
                    "step_number": self.current_step,
                    "prompt": f"执行步骤 {self.current_step}"
                }
            )
            await self.event_bus.publish(llm_start_event)

        try:
            # 使用真实LLM进行简单对话
            prompt = f"这是第 {self.current_step} 步，请简单回复你正在执行什么任务。限制在50字以内。"

            # 使用Message格式
            from app.schema import Message
            messages = [Message.user_message(prompt)]

            # 发布详细的LLM调用开始事件，包含输入信息
            if self.event_bus and self.session_id:
                llm_start_event = Event(
                    event_type=EventType.LLM_CALL_START,
                    source=f"agent_{self.name}",
                    session_id=self.session_id,
                    data={
                        "model": self.llm.model,
                        "step_number": self.current_step,
                        "prompt": prompt,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": self.llm.max_tokens,
                        "temperature": self.llm.temperature
                    }
                )
                await self.event_bus.publish(llm_start_event)

            response = await self.llm.ask(messages, stream=False)

            # 发布详细的LLM调用结束事件，包含完整响应
            if self.event_bus and self.session_id:
                llm_end_event = Event(
                    event_type=EventType.LLM_CALL_END,
                    source=f"agent_{self.name}",
                    session_id=self.session_id,
                    data={
                        "model": self.llm.model,
                        "step_number": self.current_step,
                        "prompt": prompt,
                        "response": response,
                        "input_tokens": getattr(self.llm, 'total_input_tokens', 0),
                        "output_tokens": getattr(self.llm, 'total_completion_tokens', 0),
                        "success": True
                    }
                )
                await self.event_bus.publish(llm_end_event)

            result = f"步骤 {self.current_step}: {response}"

            # 模拟一些处理时间
            await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            result = f"步骤 {self.current_step}: LLM调用失败 - {str(e)}"

            # 发布详细的LLM调用错误事件
            if self.event_bus and self.session_id:
                llm_error_event = Event(
                    event_type=EventType.LLM_CALL_ERROR,
                    source=f"agent_{self.name}",
                    session_id=self.session_id,
                    data={
                        "model": getattr(self.llm, 'model', 'unknown'),
                        "step_number": self.current_step,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "prompt": f"这是第 {self.current_step} 步，请简单回复你正在执行什么任务。限制在50字以内。",
                        "success": False
                    }
                )
                await self.event_bus.publish(llm_error_event)

        # 发布步骤结束事件
        if self.event_bus and self.session_id:
            step_end_event = Event(
                event_type=EventType.AGENT_STEP_END,
                source=f"agent_{self.name}",
                session_id=self.session_id,
                data={
                    "step_number": self.current_step,
                    "result": result
                }
            )
            await self.event_bus.publish(step_end_event)

        self.logger.info(f"MockAgent step {self.current_step} completed: {result[:50]}...")

        # 检查是否应该结束
        if self.current_step >= 3:  # 简化测试，只执行3步
            from app.agent.base import AgentState
            self.state = AgentState.FINISHED

        return result
