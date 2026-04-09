#!/usr/bin/env python3
"""
Agent Orchestrator - Multi-Agent Coordination Patterns

Inspired by:
- LangGraph: Graph-based agent workflows
- Kore.ai: Supervisor, Coordinator-Worker, Blackboard patterns
- Quranic Hikmah (Wisdom) + Adl (Justice): Wise routing, fair allocation

Features:
- Supervisor pattern (hierarchical control)
- Coordinator-Worker pattern (parallel execution)
- Blackboard pattern (shared state collaboration)
- Task decomposition and routing
- Result aggregation
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from enum import Enum
from datetime import datetime, timezone
from abc import ABC, abstractmethod
import asyncio
import threading
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

# Optional: integrate with ledger if available
try:
    import sys
    sys.path.insert(0, str(__file__).replace("autoclaude/agent_orchestrator.py", ""))
    from ledger.event_logger import EventLogger
    HAS_LEDGER = True
except ImportError:
    HAS_LEDGER = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class OrchestrationPattern(Enum):
    """Available orchestration patterns."""
    SUPERVISOR = "supervisor"        # Central controller
    COORDINATOR_WORKER = "coordinator_worker"  # Parallel delegation
    BLACKBOARD = "blackboard"        # Shared state
    PIPELINE = "pipeline"            # Sequential chain
    HIERARCHICAL = "hierarchical"    # Multi-level


class AgentStatus(Enum):
    """Agent operational status."""
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    COMPLETED = "completed"
    WAITING = "waiting"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentCapability:
    """Describes what an agent can do."""
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    quality_score: float = 1.0  # 0.0 to 1.0
    cost_per_call: float = 0.0
    avg_latency_ms: float = 1000.0


@dataclass
class Agent:
    """Represents an agent in the system."""
    id: str
    name: str
    description: str
    capabilities: List[AgentCapability]
    model: Optional[str] = None  # LLM model if applicable
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_handle(self, task_type: str) -> bool:
        """Check if agent can handle a task type."""
        for cap in self.capabilities:
            if task_type in cap.input_types or task_type == cap.name:
                return True
        return False

    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get a specific capability."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None


@dataclass
class Task:
    """A unit of work to be executed."""
    id: str
    task_type: str
    input_data: Any
    priority: int = 5  # 1-10, higher = more important
    parent_task_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=_now_utc)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_result": self.result is not None,
            "has_error": self.error is not None
        }


@dataclass
class BlackboardEntry:
    """Entry in the shared blackboard."""
    key: str
    value: Any
    source_agent: str
    timestamp: datetime = field(default_factory=_now_utc)
    version: int = 1
    subscribers: Set[str] = field(default_factory=set)


@dataclass
class OrchestrationResult:
    """Result of an orchestrated operation."""
    success: bool
    tasks_completed: int
    tasks_failed: int
    results: Dict[str, Any]
    total_duration_ms: float
    total_cost: float
    agent_stats: Dict[str, Dict[str, Any]]
    errors: List[str] = field(default_factory=list)


class TaskDecomposer:
    """Decomposes complex tasks into subtasks."""

    def __init__(self):
        self._decomposition_rules: Dict[str, Callable] = {}

    def register_rule(
        self,
        task_type: str,
        decomposer: Callable[[Task], List[Task]]
    ) -> None:
        """Register a decomposition rule for a task type."""
        self._decomposition_rules[task_type] = decomposer

    def decompose(self, task: Task) -> List[Task]:
        """Decompose a task into subtasks."""
        if task.task_type in self._decomposition_rules:
            subtasks = self._decomposition_rules[task.task_type](task)
            # Set parent relationship
            for st in subtasks:
                st.parent_task_id = task.id
            return subtasks
        return [task]  # Return as-is if no rule


class AgentRouter:
    """Routes tasks to appropriate agents."""

    def __init__(self, strategy: str = "best_match"):
        self._strategy = strategy

    def route(
        self,
        task: Task,
        agents: List[Agent],
        blackboard: Optional[Dict[str, BlackboardEntry]] = None
    ) -> Optional[Agent]:
        """Select the best agent for a task."""
        candidates = [a for a in agents if a.can_handle(task.task_type) and a.status == AgentStatus.IDLE]

        if not candidates:
            return None

        if self._strategy == "best_match":
            # Score by capability quality and availability
            def score_agent(agent: Agent) -> float:
                cap = agent.get_capability(task.task_type)
                if cap:
                    return cap.quality_score * (1.0 / (cap.avg_latency_ms + 1))
                return 0.0

            candidates.sort(key=score_agent, reverse=True)
            return candidates[0]

        elif self._strategy == "round_robin":
            # Pick least recently used
            candidates.sort(key=lambda a: a.completed_tasks)
            return candidates[0]

        elif self._strategy == "cost_optimized":
            # Pick cheapest
            def get_cost(agent: Agent) -> float:
                cap = agent.get_capability(task.task_type)
                return cap.cost_per_call if cap else float('inf')

            candidates.sort(key=get_cost)
            return candidates[0]

        else:
            return candidates[0] if candidates else None


class ResultAggregator:
    """Aggregates results from multiple agents."""

    def __init__(self, strategy: str = "merge"):
        self._strategy = strategy

    def aggregate(
        self,
        results: List[Tuple[Task, Any]],
        original_task: Task
    ) -> Any:
        """Aggregate results from subtasks."""
        if not results:
            return None

        if self._strategy == "merge":
            # Merge all results into a dict
            merged = {}
            for task, result in results:
                if isinstance(result, dict):
                    merged.update(result)
                else:
                    merged[task.id] = result
            return merged

        elif self._strategy == "concat":
            # Concatenate string/list results
            parts = []
            for _, result in results:
                if isinstance(result, list):
                    parts.extend(result)
                elif isinstance(result, str):
                    parts.append(result)
                else:
                    parts.append(str(result))
            return parts

        elif self._strategy == "first_success":
            # Return first successful result
            for task, result in results:
                if task.status == TaskStatus.COMPLETED:
                    return result
            return None

        elif self._strategy == "vote":
            # Majority vote (for classification tasks)
            votes: Dict[Any, int] = {}
            for _, result in results:
                key = str(result)
                votes[key] = votes.get(key, 0) + 1
            if votes:
                winner = max(votes.items(), key=lambda x: x[1])
                return winner[0]
            return None

        else:
            return [r for _, r in results]


class AgentOrchestrator:
    """
    Orchestrates multi-agent workflows using various patterns.

    Hikmah (Wisdom) + Adl (Justice) Principles:
    - Wise task routing based on capabilities
    - Fair workload distribution
    - Transparent decision making
    """

    def __init__(
        self,
        pattern: OrchestrationPattern = OrchestrationPattern.SUPERVISOR,
        max_workers: int = 4,
        ledger_path: Optional[str] = None
    ):
        self._pattern = pattern
        self._agents: Dict[str, Agent] = {}
        self._tasks: Dict[str, Task] = {}
        self._blackboard: Dict[str, BlackboardEntry] = {}
        self._decomposer = TaskDecomposer()
        self._router = AgentRouter()
        self._aggregator = ResultAggregator()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._task_handlers: Dict[str, Callable] = {}

        # Ledger integration
        self._logger: Optional[EventLogger] = None
        if HAS_LEDGER and ledger_path:
            self._logger = EventLogger(ledger_path)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        timestamp = _now_utc().isoformat()
        return f"{prefix}_{hashlib.sha256(timestamp.encode()).hexdigest()[:8]}"

    def register_agent(
        self,
        name: str,
        description: str,
        capabilities: List[AgentCapability],
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Agent:
        """Register an agent with the orchestrator."""
        agent_id = self._generate_id("agent")
        agent = Agent(
            id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            model=model,
            metadata=metadata or {}
        )

        with self._lock:
            self._agents[agent_id] = agent

        if self._logger:
            self._logger.log_event(
                event_type="AGENT_REGISTERED",
                card_id="autoclaude",
                details={
                    "agent_id": agent_id,
                    "name": name,
                    "capabilities": [c.name for c in capabilities]
                }
            )

        return agent

    def register_task_handler(
        self,
        task_type: str,
        handler: Callable[[Task, Agent], Any]
    ) -> None:
        """Register a handler function for a task type."""
        self._task_handlers[task_type] = handler

    def register_decomposition_rule(
        self,
        task_type: str,
        decomposer: Callable[[Task], List[Task]]
    ) -> None:
        """Register a task decomposition rule."""
        self._decomposer.register_rule(task_type, decomposer)

    def create_task(
        self,
        task_type: str,
        input_data: Any,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create a new task."""
        task_id = self._generate_id("task")
        task = Task(
            id=task_id,
            task_type=task_type,
            input_data=input_data,
            priority=priority,
            metadata=metadata or {}
        )

        with self._lock:
            self._tasks[task_id] = task

        return task

    def _execute_task(self, task: Task, agent: Agent) -> Any:
        """Execute a single task with an agent."""
        handler = self._task_handlers.get(task.task_type)
        if not handler:
            raise ValueError(f"No handler for task type: {task.task_type}")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = _now_utc()
        agent.status = AgentStatus.BUSY
        agent.current_task = task.id

        try:
            result = handler(task, agent)
            task.result = result
            task.status = TaskStatus.COMPLETED
            agent.completed_tasks += 1

            # Update cost tracking
            cap = agent.get_capability(task.task_type)
            if cap:
                agent.total_cost += cap.cost_per_call

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            agent.failed_tasks += 1
            raise

        finally:
            task.completed_at = _now_utc()
            agent.status = AgentStatus.IDLE
            agent.current_task = None

        return task.result

    def execute_supervisor(self, task: Task) -> OrchestrationResult:
        """
        Execute using Supervisor pattern.
        Central coordinator decomposes, assigns, and aggregates.
        """
        start_time = _now_utc()
        results: Dict[str, Any] = {}
        errors: List[str] = []
        completed = 0
        failed = 0
        total_cost = 0.0

        # Decompose task
        subtasks = self._decomposer.decompose(task)

        # Execute each subtask
        for subtask in subtasks:
            with self._lock:
                self._tasks[subtask.id] = subtask

            # Route to best agent
            agent = self._router.route(subtask, list(self._agents.values()))
            if not agent:
                subtask.status = TaskStatus.FAILED
                subtask.error = "No available agent"
                failed += 1
                errors.append(f"Task {subtask.id}: No agent available")
                continue

            subtask.assigned_agent = agent.id

            try:
                result = self._execute_task(subtask, agent)
                results[subtask.id] = result
                completed += 1
                cap = agent.get_capability(subtask.task_type)
                if cap:
                    total_cost += cap.cost_per_call
            except Exception as e:
                failed += 1
                errors.append(f"Task {subtask.id}: {str(e)}")

        # Aggregate results
        task_results = [(self._tasks[tid], results.get(tid)) for tid in results]
        aggregated = self._aggregator.aggregate(task_results, task)

        duration_ms = (_now_utc() - start_time).total_seconds() * 1000

        if self._logger:
            self._logger.log_event(
                event_type="ORCHESTRATION_COMPLETE",
                card_id="autoclaude",
                details={
                    "pattern": "supervisor",
                    "task_id": task.id,
                    "completed": completed,
                    "failed": failed,
                    "duration_ms": duration_ms
                }
            )

        return OrchestrationResult(
            success=failed == 0,
            tasks_completed=completed,
            tasks_failed=failed,
            results={"aggregated": aggregated, "individual": results},
            total_duration_ms=duration_ms,
            total_cost=total_cost,
            agent_stats=self._get_agent_stats(),
            errors=errors
        )

    def execute_coordinator_worker(
        self,
        task: Task,
        parallel: bool = True
    ) -> OrchestrationResult:
        """
        Execute using Coordinator-Worker pattern.
        Parallel execution of subtasks.
        """
        start_time = _now_utc()
        results: Dict[str, Any] = {}
        errors: List[str] = []
        total_cost = 0.0

        # Decompose task
        subtasks = self._decomposer.decompose(task)

        for subtask in subtasks:
            with self._lock:
                self._tasks[subtask.id] = subtask

        if parallel:
            # Submit all tasks for parallel execution
            futures: Dict[Future, Task] = {}

            for subtask in subtasks:
                agent = self._router.route(subtask, list(self._agents.values()))
                if agent:
                    subtask.assigned_agent = agent.id
                    future = self._executor.submit(self._execute_task, subtask, agent)
                    futures[future] = subtask
                else:
                    subtask.status = TaskStatus.FAILED
                    subtask.error = "No available agent"

            # Collect results
            for future in as_completed(futures):
                subtask = futures[future]
                try:
                    result = future.result()
                    results[subtask.id] = result
                except Exception as e:
                    errors.append(f"Task {subtask.id}: {str(e)}")

        else:
            # Sequential execution
            for subtask in subtasks:
                agent = self._router.route(subtask, list(self._agents.values()))
                if agent:
                    subtask.assigned_agent = agent.id
                    try:
                        result = self._execute_task(subtask, agent)
                        results[subtask.id] = result
                    except Exception as e:
                        errors.append(f"Task {subtask.id}: {str(e)}")

        completed = len(results)
        failed = len(subtasks) - completed

        # Aggregate
        task_results = [(self._tasks[tid], results.get(tid)) for tid in results]
        aggregated = self._aggregator.aggregate(task_results, task)

        duration_ms = (_now_utc() - start_time).total_seconds() * 1000

        return OrchestrationResult(
            success=failed == 0,
            tasks_completed=completed,
            tasks_failed=failed,
            results={"aggregated": aggregated, "individual": results},
            total_duration_ms=duration_ms,
            total_cost=total_cost,
            agent_stats=self._get_agent_stats(),
            errors=errors
        )

    def execute_blackboard(
        self,
        task: Task,
        max_iterations: int = 10
    ) -> OrchestrationResult:
        """
        Execute using Blackboard pattern.
        Agents collaborate via shared state.
        """
        start_time = _now_utc()
        errors: List[str] = []
        completed = 0
        total_cost = 0.0

        # Initialize blackboard with task
        self.write_to_blackboard("input", task.input_data, "orchestrator")
        self.write_to_blackboard("status", "in_progress", "orchestrator")

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            progress_made = False

            # Let each agent contribute
            for agent in self._agents.values():
                if agent.status != AgentStatus.IDLE:
                    continue

                # Check if agent can contribute
                for cap in agent.capabilities:
                    if self._can_contribute(agent, cap):
                        # Create contribution task
                        contrib_task = self.create_task(
                            task_type=cap.name,
                            input_data=self.read_from_blackboard("input"),
                            metadata={"iteration": iteration}
                        )

                        try:
                            result = self._execute_task(contrib_task, agent)
                            self.write_to_blackboard(
                                f"result_{cap.name}",
                                result,
                                agent.id
                            )
                            completed += 1
                            progress_made = True
                        except Exception as e:
                            errors.append(f"Agent {agent.name}: {str(e)}")

            # Check termination condition
            status = self.read_from_blackboard("status")
            if status == "complete" or not progress_made:
                break

        # Collect all results from blackboard
        results = {}
        for key, entry in self._blackboard.items():
            if key.startswith("result_"):
                results[key] = entry.value

        duration_ms = (_now_utc() - start_time).total_seconds() * 1000

        return OrchestrationResult(
            success=len(errors) == 0,
            tasks_completed=completed,
            tasks_failed=len(errors),
            results=results,
            total_duration_ms=duration_ms,
            total_cost=total_cost,
            agent_stats=self._get_agent_stats(),
            errors=errors
        )

    def _can_contribute(self, agent: Agent, capability: AgentCapability) -> bool:
        """Check if agent can contribute to blackboard."""
        # Check if required inputs are available
        for input_type in capability.input_types:
            if not self.read_from_blackboard(input_type):
                # Check if alternative exists
                if not self.read_from_blackboard("input"):
                    return False
        return True

    def write_to_blackboard(
        self,
        key: str,
        value: Any,
        source_agent: str
    ) -> None:
        """Write to shared blackboard."""
        with self._lock:
            if key in self._blackboard:
                entry = self._blackboard[key]
                entry.value = value
                entry.version += 1
                entry.timestamp = _now_utc()
                entry.source_agent = source_agent
            else:
                self._blackboard[key] = BlackboardEntry(
                    key=key,
                    value=value,
                    source_agent=source_agent
                )

    def read_from_blackboard(self, key: str) -> Optional[Any]:
        """Read from shared blackboard."""
        with self._lock:
            entry = self._blackboard.get(key)
            return entry.value if entry else None

    def subscribe_to_blackboard(self, key: str, agent_id: str) -> None:
        """Subscribe agent to blackboard key changes."""
        with self._lock:
            if key in self._blackboard:
                self._blackboard[key].subscribers.add(agent_id)

    def execute(self, task: Task) -> OrchestrationResult:
        """Execute task using configured pattern."""
        if self._pattern == OrchestrationPattern.SUPERVISOR:
            return self.execute_supervisor(task)
        elif self._pattern == OrchestrationPattern.COORDINATOR_WORKER:
            return self.execute_coordinator_worker(task)
        elif self._pattern == OrchestrationPattern.BLACKBOARD:
            return self.execute_blackboard(task)
        elif self._pattern == OrchestrationPattern.PIPELINE:
            return self.execute_supervisor(task)  # Pipeline is sequential supervisor
        else:
            return self.execute_supervisor(task)

    def _get_agent_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all agents."""
        stats = {}
        for agent_id, agent in self._agents.items():
            stats[agent_id] = {
                "name": agent.name,
                "status": agent.status.value,
                "completed_tasks": agent.completed_tasks,
                "failed_tasks": agent.failed_tasks,
                "total_cost": agent.total_cost
            }
        return stats

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_all_agents(self) -> List[Agent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def shutdown(self) -> None:
        """Shutdown the orchestrator."""
        self._executor.shutdown(wait=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        with self._lock:
            task_stats = {
                "pending": len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING]),
                "in_progress": len([t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS]),
                "completed": len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]),
                "failed": len([t for t in self._tasks.values() if t.status == TaskStatus.FAILED])
            }

            return {
                "pattern": self._pattern.value,
                "registered_agents": len(self._agents),
                "total_tasks": len(self._tasks),
                "task_stats": task_stats,
                "blackboard_entries": len(self._blackboard),
                "agent_stats": self._get_agent_stats()
            }


# Convenience exports
__all__ = [
    "AgentOrchestrator",
    "Agent",
    "AgentCapability",
    "AgentStatus",
    "Task",
    "TaskStatus",
    "OrchestrationPattern",
    "OrchestrationResult",
    "TaskDecomposer",
    "AgentRouter",
    "ResultAggregator",
    "BlackboardEntry"
]
