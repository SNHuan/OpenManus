from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.sandbox.client import SANDBOX_CLIENT
from app.schema import ROLE_TYPE, AgentState, Memory, Message
from app.event import EventAwareMixin, create_agent_step_start_event, AgentStepCompleteEvent


class BaseAgent(BaseModel, EventAwareMixin, ABC):
    """Abstract base class for managing agent state and execution.

    Provides foundational functionality for state transitions, memory management,
    and a step-based execution loop. Subclasses must implement the `step` method.
    """

    # Core attributes
    name: str = Field(..., description="Unique name of the agent")
    description: Optional[str] = Field(None, description="Optional agent description")

    # Event tracking
    conversation_id: Optional[str] = Field(None, description="Current conversation ID for event tracking")

    # Interrupt handling
    interrupted: bool = Field(default=False, description="Whether the agent has been interrupted")

    # Prompts
    system_prompt: Optional[str] = Field(
        None, description="System-level instruction prompt"
    )
    next_step_prompt: Optional[str] = Field(
        None, description="Prompt for determining next action"
    )

    # Dependencies
    llm: LLM = Field(default_factory=LLM, description="Language model instance")
    memory: Memory = Field(default_factory=Memory, description="Agent's memory store")
    state: AgentState = Field(
        default=AgentState.IDLE, description="Current agent state"
    )

    # Execution control
    max_steps: int = Field(default=10, description="Maximum steps before termination")
    current_step: int = Field(default=0, description="Current step in execution")

    duplicate_threshold: int = 2

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for flexibility in subclasses

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """Initialize agent with default settings if not provided."""
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())
        if not isinstance(self.memory, Memory):
            self.memory = Memory()
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """Context manager for safe agent state transitions.

        Args:
            new_state: The state to transition to during the context.

        Yields:
            None: Allows execution within the new state.

        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # Transition to ERROR on failure
            raise e
        finally:
            self.state = previous_state  # Revert to previous state

    def update_memory(
        self,
        role: ROLE_TYPE,  # type: ignore
        content: str,
        base64_image: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Add a message to the agent's memory.

        Args:
            role: The role of the message sender (user, system, assistant, tool).
            content: The message content.
            base64_image: Optional base64 encoded image.
            **kwargs: Additional arguments (e.g., tool_call_id for tool messages).

        Raises:
            ValueError: If the role is unsupported.
        """
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")

        # Create message with appropriate parameters based on role
        kwargs = {"base64_image": base64_image, **(kwargs if role == "tool" else {})}
        self.memory.add_message(message_map[role](content, **kwargs))

    async def run(self, request: Optional[str] = None, conversation_id: Optional[str] = None) -> str:
        """Execute the agent's main loop asynchronously.

        Args:
            request: Optional initial user request to process.
            conversation_id: Optional conversation ID for event tracking.

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        # Set conversation ID for event tracking
        if conversation_id:
            self.conversation_id = conversation_id

        if request:
            self.update_memory("user", request)

        results: List[str] = []

        try:
            async with self.state_context(AgentState.RUNNING):
                while (
                    self.current_step < self.max_steps and
                    self.state != AgentState.FINISHED and
                    not self.interrupted
                ):
                    self.current_step += 1
                    logger.info(f"Executing step {self.current_step}/{self.max_steps}")

                    # Check for interrupt before starting step
                    if await self._check_interrupt():
                        logger.info(f"Agent interrupted at step {self.current_step}")
                        results.append(f"Interrupted at step {self.current_step}")
                        break

                    # Publish step start event
                    await self.publish_agent_step_start(self.current_step)

                    try:
                        step_result = await self.step()

                        # Check for interrupt after step execution
                        if await self._check_interrupt():
                            logger.info(f"Agent interrupted after step {self.current_step}")
                            results.append(f"Interrupted after step {self.current_step}")
                            break

                        # Publish step complete event
                        await self.publish_agent_step_complete(self.current_step, step_result)

                        # Check for stuck state
                        if self.is_stuck():
                            self.handle_stuck_state()

                        results.append(f"Step {self.current_step}: {step_result}")

                    except Exception as e:
                        # Publish error event
                        await self.publish_error(
                            error_type=type(e).__name__,
                            error_message=str(e),
                            context={"step": self.current_step, "method": "step"}
                        )
                        raise

                if self.interrupted:
                    self.state = AgentState.IDLE
                    self.current_step = 0
                    results.append("Execution interrupted by user")
                elif self.current_step >= self.max_steps:
                    self.current_step = 0
                    self.state = AgentState.IDLE
                    results.append(f"Terminated: Reached max steps ({self.max_steps})")

        except Exception as e:
            # Publish general error event
            await self.publish_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={"method": "run", "current_step": self.current_step}
            )
            raise
        finally:
            await SANDBOX_CLIENT.cleanup()

        return "\n".join(results) if results else "No steps executed"

    @abstractmethod
    async def step(self) -> str:
        """Execute a single step in the agent's workflow.

        Must be implemented by subclasses to define specific behavior.
        """

    def handle_stuck_state(self):
        """Handle stuck state by adding a prompt to change strategy"""
        stuck_prompt = "\
        Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """Check if the agent is stuck in a loop by detecting duplicate content"""
        if len(self.memory.messages) < 2:
            return False

        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        # Count identical content occurrences
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    async def _check_interrupt(self) -> bool:
        """Check if the agent has been interrupted.

        Returns:
            bool: True if the agent should stop execution
        """
        if self.interrupted:
            return True

        # Check for interrupt events in the conversation
        if self.conversation_id:
            try:
                from app.event.manager import event_manager
                # Check if there are any recent interrupt events for this conversation
                recent_events = await event_manager.get_recent_events(
                    limit=10,
                    conversation_id=self.conversation_id
                )

                for event in recent_events:
                    if (hasattr(event, 'event_type') and
                        event.event_type == "conversation.interrupt" and
                        hasattr(event, 'timestamp')):
                        # Check if interrupt is recent (within last 30 seconds)
                        from datetime import datetime, timedelta
                        if isinstance(event.timestamp, str):
                            from dateutil.parser import parse
                            event_time = parse(event.timestamp)
                        else:
                            event_time = event.timestamp

                        if datetime.now() - event_time.replace(tzinfo=None) < timedelta(seconds=30):
                            logger.info(f"Found recent interrupt event: {event.event_id}")
                            self.interrupted = True
                            return True

            except Exception as e:
                logger.error(f"Error checking for interrupt events: {e}")

        return False

    def interrupt(self):
        """Mark the agent as interrupted."""
        self.interrupted = True
        logger.info(f"Agent {self.name} marked as interrupted")

    def reset_interrupt(self):
        """Reset the interrupt flag."""
        self.interrupted = False
        logger.debug(f"Agent {self.name} interrupt flag reset")

    @property
    def messages(self) -> List[Message]:
        """Retrieve a list of messages from the agent's memory."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value
