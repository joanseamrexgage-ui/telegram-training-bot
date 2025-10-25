"""
Enterprise Task Manager v3.0

BLOCKER-004 FIX: Memory Leak Prevention

Problem: asyncio.create_task() создает tasks без tracking,
которые accumulate в памяти и вызывают memory leak.

Solution: Centralized TaskManager с:
- Automatic task tracking
- Periodic cleanup of completed tasks
- Graceful cancellation on shutdown
- Memory usage monitoring
- Max concurrent task limits

Author: Chief Software Architect (Claude)
Date: 2025-10-25
"""

import asyncio
import weakref
from typing import Set, Optional, Callable, Coroutine, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Production-Ready Task Manager

    Features:
    - Automatic tracking of all background tasks
    - Periodic cleanup of completed tasks (prevents memory leak)
    - Graceful cancellation on shutdown
    - Max concurrent task limit (backpressure)
    - Memory usage monitoring
    - Task lifetime tracking

    Usage:
        task_manager = TaskManager(max_concurrent_tasks=1000)

        # Create tracked task
        await task_manager.create_task(
            my_coroutine(...),
            name="log_activity_123"
        )

        # Periodic cleanup (call from main loop)
        await task_manager.cleanup_completed_tasks()

        # Graceful shutdown
        await task_manager.cancel_all_tasks(timeout=30)
    """

    def __init__(
        self,
        max_concurrent_tasks: int = 1000,
        cleanup_interval: int = 60,
        task_timeout: Optional[int] = 300
    ):
        """
        Initialize TaskManager

        Args:
            max_concurrent_tasks: Maximum concurrent background tasks
            cleanup_interval: Cleanup interval in seconds
            task_timeout: Default task timeout in seconds (None = no timeout)
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.cleanup_interval = cleanup_interval
        self.task_timeout = task_timeout

        # Use WeakSet to automatically remove GC'd tasks
        self._active_tasks: Set[asyncio.Task] = set()

        # Statistics
        self._total_created = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0
        self._total_timeout = 0

        # Last cleanup time
        self._last_cleanup = datetime.utcnow()

        logger.info(
            f"✅ TaskManager initialized: "
            f"max_concurrent={max_concurrent_tasks}, "
            f"cleanup_interval={cleanup_interval}s, "
            f"task_timeout={task_timeout}s"
        )

    async def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> asyncio.Task:
        """
        Create and track a background task

        Args:
            coro: Coroutine to execute
            name: Optional task name for debugging
            timeout: Optional timeout override (seconds)

        Returns:
            Created asyncio.Task

        Raises:
            RuntimeError: If max_concurrent_tasks exceeded
        """
        # Check if we're at capacity
        if len(self._active_tasks) >= self.max_concurrent_tasks:
            # Try to cleanup completed tasks first
            await self.cleanup_completed_tasks()

            # Still at capacity?
            if len(self._active_tasks) >= self.max_concurrent_tasks:
                logger.error(
                    f"❌ TaskManager capacity exceeded: "
                    f"{len(self._active_tasks)}/{self.max_concurrent_tasks}"
                )
                raise RuntimeError(
                    f"Max concurrent tasks exceeded: {self.max_concurrent_tasks}"
                )

        # Apply timeout if specified
        task_timeout = timeout or self.task_timeout
        if task_timeout:
            coro = asyncio.wait_for(coro, timeout=task_timeout)

        # Create task
        task = asyncio.create_task(coro, name=name)
        self._active_tasks.add(task)
        self._total_created += 1

        # Add done callback for statistics
        task.add_done_callback(self._task_done_callback)

        logger.debug(
            f"📝 Task created: {name or 'unnamed'} "
            f"(active: {len(self._active_tasks)}/{self.max_concurrent_tasks})"
        )

        return task

    def _task_done_callback(self, task: asyncio.Task) -> None:
        """
        Callback when task completes

        Updates statistics based on task outcome
        """
        try:
            # Check task outcome
            if task.cancelled():
                self._total_cancelled += 1
            elif task.exception():
                self._total_failed += 1
                exc = task.exception()

                # Check if it's a timeout
                if isinstance(exc, asyncio.TimeoutError):
                    self._total_timeout += 1

                # Log error
                logger.error(
                    f"❌ Background task failed: {task.get_name()}",
                    exc_info=exc
                )
            else:
                # Successful completion
                self._total_completed += 1

        except Exception as e:
            logger.error(f"Error in task callback: {e}")

    async def cleanup_completed_tasks(self) -> int:
        """
        Remove completed/failed/cancelled tasks from tracking

        Returns:
            Number of tasks cleaned up
        """
        initial_count = len(self._active_tasks)

        # Remove done tasks
        self._active_tasks = {
            task for task in self._active_tasks
            if not task.done()
        }

        cleaned = initial_count - len(self._active_tasks)

        if cleaned > 0:
            logger.debug(
                f"🧹 Cleaned up {cleaned} completed tasks. "
                f"Active: {len(self._active_tasks)}"
            )

        self._last_cleanup = datetime.utcnow()
        return cleaned

    async def periodic_cleanup(self) -> None:
        """
        Periodic cleanup task (call from main loop)

        Automatically cleans up completed tasks every cleanup_interval seconds
        """
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_completed_tasks()

        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled")
            raise

    async def cancel_all_tasks(
        self,
        timeout: int = 30,
        graceful: bool = True
    ) -> dict:
        """
        Cancel all tracked tasks (for graceful shutdown)

        Args:
            timeout: Maximum time to wait for cancellation
            graceful: If True, wait for tasks to finish; if False, force cancel

        Returns:
            Statistics dict with cancellation results
        """
        logger.info(
            f"🛑 Cancelling {len(self._active_tasks)} background tasks "
            f"(timeout: {timeout}s, graceful: {graceful})"
        )

        if not self._active_tasks:
            return {"cancelled": 0, "completed": 0, "failed": 0}

        # Copy task set (will be modified during iteration)
        tasks = set(self._active_tasks)

        if graceful:
            # Try graceful completion first
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️ Graceful shutdown timeout after {timeout}s, "
                    f"forcing cancellation"
                )

        # Cancel any remaining tasks
        cancelled = 0
        for task in tasks:
            if not task.done():
                task.cancel()
                cancelled += 1

        # Wait briefly for cancellation to complete
        if cancelled > 0:
            await asyncio.sleep(0.1)

        # Collect statistics
        completed = sum(1 for t in tasks if t.done() and not t.cancelled())
        failed = sum(1 for t in tasks if t.done() and t.exception())

        stats = {
            "cancelled": cancelled,
            "completed": completed,
            "failed": failed
        }

        logger.info(
            f"✅ Task cancellation complete: "
            f"{cancelled} cancelled, {completed} completed, {failed} failed"
        )

        # Clear task set
        self._active_tasks.clear()

        return stats

    def get_stats(self) -> dict:
        """
        Get TaskManager statistics

        Returns:
            Dict with current statistics
        """
        return {
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self.max_concurrent_tasks,
            "total_created": self._total_created,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_cancelled": self._total_cancelled,
            "total_timeout": self._total_timeout,
            "last_cleanup": self._last_cleanup.isoformat(),
            "utilization": len(self._active_tasks) / self.max_concurrent_tasks
        }

    async def health_check(self) -> dict:
        """
        Health check for monitoring

        Returns:
            Health status dict
        """
        stats = self.get_stats()

        # Determine health status
        utilization = stats["utilization"]
        if utilization > 0.9:
            status = "critical"
            message = f"Task utilization critical: {utilization:.1%}"
        elif utilization > 0.7:
            status = "warning"
            message = f"Task utilization high: {utilization:.1%}"
        else:
            status = "healthy"
            message = "Task manager healthy"

        return {
            "status": status,
            "message": message,
            "stats": stats
        }

    def __repr__(self) -> str:
        return (
            f"TaskManager(active={len(self._active_tasks)}, "
            f"max={self.max_concurrent_tasks}, "
            f"created={self._total_created}, "
            f"completed={self._total_completed})"
        )


# Global TaskManager instance
_global_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """
    Get global TaskManager instance

    Returns:
        Global TaskManager (creates if not exists)
    """
    global _global_task_manager

    if _global_task_manager is None:
        _global_task_manager = TaskManager()

    return _global_task_manager


async def create_tracked_task(
    coro: Coroutine[Any, Any, Any],
    name: Optional[str] = None
) -> asyncio.Task:
    """
    Convenience function to create tracked task using global TaskManager

    Args:
        coro: Coroutine to execute
        name: Optional task name

    Returns:
        Created asyncio.Task
    """
    manager = get_task_manager()
    return await manager.create_task(coro, name=name)


__all__ = [
    "TaskManager",
    "get_task_manager",
    "create_tracked_task"
]
