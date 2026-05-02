"""Task scheduler for automated background tasks in Rhizome Thinking.

This module provides scheduled execution of maintenance tasks like
relationship review and theme evolution checks.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    AsyncIOScheduler = None
    IntervalTrigger = None
    MemoryJobStore = None
    EVENT_JOB_EXECUTED = None
    EVENT_JOB_ERROR = None
    JobExecutionEvent = None

from rhizome.config import settings
from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.core.relationship_manager import RelationshipManager
from rhizome.core.theme_evolution import ThemeEvolutionAnalyzer


class Scheduler:
    """Task scheduler for automated background tasks.

    Manages periodic execution of:
    - Relationship review: Discovers missing connections between nodes
    - Theme evolution check: Analyzes themes for needed updates
    """

    def __init__(
        self,
        relationship_manager: Optional[RelationshipManager] = None,
        evolution_analyzer: Optional[ThemeEvolutionAnalyzer] = None,
        node_store: Optional[NodeStore] = None,
        theme_store: Optional[ThemeStore] = None,
    ) -> None:
        """Initialize the scheduler.

        Args:
            relationship_manager: RelationshipManager instance
            evolution_analyzer: ThemeEvolutionAnalyzer instance
            node_store: NodeStore instance
            theme_store: ThemeStore instance
        """
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._relationship_manager = relationship_manager
        self._evolution_analyzer = evolution_analyzer
        self._node_store = node_store or NodeStore()
        self._theme_store = theme_store or ThemeStore()
        self._running = False

    def start(self) -> None:
        """Start the scheduler.

        Initializes the APScheduler and begins executing scheduled jobs.
        If scheduler is already running, this method does nothing.
        """
        if self._running:
            return

        if not APSCHEDULER_AVAILABLE:
            print("[Scheduler] 警告: APScheduler未安装，调度器将以模拟模式运行")
            self._running = True
            return

        jobstores = {
            "default": MemoryJobStore()
        }

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone="UTC"
        )

        # Add event listeners for logging
        self._scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

        self._scheduler.start()
        self._running = True

        print(f"[Scheduler] 调度器已启动于 {datetime.now().isoformat()}")

    def shutdown(self, wait: bool = True) -> None:
        """Stop the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        if not self._running or not self._scheduler:
            return

        self._scheduler.shutdown(wait=wait)
        self._running = False
        self._scheduler = None

        print(f"[Scheduler] 调度器已停止于 {datetime.now().isoformat()}")

    def schedule_relationship_review(
        self,
        interval_seconds: Optional[int] = None,
        max_pairs: int = 50
    ) -> None:
        """Schedule periodic relationship review task.

        This task analyzes existing nodes to discover missing relationships.

        Args:
            interval_seconds: Interval between runs (default: RELATIONSHIP_REVIEW_INTERVAL)
            max_pairs: Maximum node pairs to analyze per run
        """
        if not self._running:
            raise RuntimeError("Scheduler not started. Call start() first.")

        if not APSCHEDULER_AVAILABLE:
            print("[Scheduler] 模拟模式: 关系审查任务已配置")
            return

        interval = interval_seconds or settings.relationship_review_interval

        self._scheduler.add_job(
            func=self._run_relationship_review,
            trigger=IntervalTrigger(seconds=interval),
            id="relationship_review",
            name="关系审查任务",
            replace_existing=True,
            args=[max_pairs]
        )

        print(f"[Scheduler] 关系审查任务已配置，间隔: {interval}秒")

    def schedule_theme_evolution_check(
        self,
        interval_seconds: Optional[int] = None
    ) -> None:
        """Schedule periodic theme evolution check task.

        This task analyzes all themes for potential updates or conflicts.

        Args:
            interval_seconds: Interval between runs (default: THEME_EVOLUTION_CHECK_INTERVAL)
        """
        if not self._running:
            raise RuntimeError("Scheduler not started. Call start() first.")

        if not APSCHEDULER_AVAILABLE:
            print("[Scheduler] 模拟模式: 主题演进检查任务已配置")
            return

        interval = interval_seconds or settings.theme_evolution_check_interval

        self._scheduler.add_job(
            func=self._run_theme_evolution_check,
            trigger=IntervalTrigger(seconds=interval),
            id="theme_evolution_check",
            name="主题演进检查任务",
            replace_existing=True
        )

        print(f"[Scheduler] 主题演进检查任务已配置，间隔: {interval}秒")

    async def _run_relationship_review(self, max_pairs: int = 50) -> None:
        """Execute relationship review task.

        Args:
            max_pairs: Maximum node pairs to analyze
        """
        print(f"[Scheduler] 开始执行关系审查任务 ({datetime.now().isoformat()})")

        try:
            # Get all nodes
            all_nodes = self._node_store.list_all()

            if len(all_nodes) < 2:
                print("[Scheduler] 节点数量不足，跳过关系审查")
                return

            # Initialize manager if not provided
            manager = self._relationship_manager
            if manager is None:
                try:
                    manager = RelationshipManager()
                except ValueError as e:
                    print(f"[Scheduler] 无法初始化RelationshipManager: {e}")
                    return

            # Run review
            suggestions = await manager.review_existing_relationships(
                all_nodes=all_nodes,
                max_pairs=max_pairs
            )

            print(f"[Scheduler] 关系审查完成，发现 {len(suggestions)} 个潜在关系")

        except Exception as e:
            print(f"[Scheduler] 关系审查任务执行失败: {e}")

    async def _run_theme_evolution_check(self) -> None:
        """Execute theme evolution check task."""
        print(f"[Scheduler] 开始执行主题演进检查任务 ({datetime.now().isoformat()})")

        try:
            # Get all themes
            all_themes = self._theme_store.get_all_themes()

            if not all_themes:
                print("[Scheduler] 没有主题，跳过演进检查")
                return

            # Initialize analyzer if not provided
            analyzer = self._evolution_analyzer
            if analyzer is None:
                try:
                    analyzer = ThemeEvolutionAnalyzer(
                        theme_store=self._theme_store
                    )
                except ValueError as e:
                    print(f"[Scheduler] 无法初始化ThemeEvolutionAnalyzer: {e}")
                    return

            # Check each theme
            total_suggestions = 0
            for theme in all_themes:
                # Get related nodes for this theme
                related_nodes = []
                for node_id in theme.node_ids:
                    node = self._node_store.get(node_id)
                    if node:
                        related_nodes.append(node)

                if not related_nodes:
                    continue

                # Generate evolution suggestions
                suggestions = await analyzer.generate_evolution_suggestions(
                    theme=theme,
                    related_nodes=related_nodes
                )

                total_suggestions += len(suggestions)

            print(f"[Scheduler] 主题演进检查完成，生成 {total_suggestions} 条建议")

        except Exception as e:
            print(f"[Scheduler] 主题演进检查任务执行失败: {e}")

    def _on_job_executed(self, event) -> None:
        """Handle job execution events for logging.

        Args:
            event: The job execution event
        """
        if event.exception:
            print(f"[Scheduler] 任务执行失败 {event.job_id}: {event.exception}")
        else:
            print(f"[Scheduler] 任务执行成功 {event.job_id}")

    def get_job_status(self) -> dict[str, Any]:
        """Get status of scheduled jobs.

        Returns:
            Dictionary with job information
        """
        if not self._scheduler:
            return {"running": False, "jobs": []}

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "running": self._running,
            "jobs": jobs
        }

    def run_job_now(self, job_id: str) -> bool:
        """Manually trigger a scheduled job.

        Args:
            job_id: The job ID to run

        Returns:
            True if job was triggered successfully
        """
        if not self._scheduler:
            return False

        job = self._scheduler.get_job(job_id)
        if not job:
            return False

        # Modify the job to run immediately
        self._scheduler.modify_job(job_id, next_run_time=datetime.now())
        return True


class MockScheduler(Scheduler):
    """Mock scheduler for testing without actual task execution."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize mock scheduler."""
        super().__init__(*args, **kwargs)
        self._mock_jobs: list[dict] = []

    def start(self) -> None:
        """Mock start - just mark as running."""
        self._running = True
        print("[MockScheduler] 模拟调度器已启动")

    def shutdown(self, wait: bool = True) -> None:
        """Mock shutdown."""
        self._running = False
        self._mock_jobs.clear()
        print("[MockScheduler] 模拟调度器已停止")

    def schedule_relationship_review(
        self,
        interval_seconds: Optional[int] = None,
        max_pairs: int = 50
    ) -> None:
        """Mock schedule relationship review."""
        self._mock_jobs.append({
            "id": "relationship_review",
            "name": "关系审查任务",
            "interval": interval_seconds or 86400,
            "max_pairs": max_pairs
        })
        print("[MockScheduler] 模拟关系审查任务已配置")

    def schedule_theme_evolution_check(
        self,
        interval_seconds: Optional[int] = None
    ) -> None:
        """Mock schedule theme evolution check."""
        self._mock_jobs.append({
            "id": "theme_evolution_check",
            "name": "主题演进检查任务",
            "interval": interval_seconds or 86400
        })
        print("[MockScheduler] 模拟主题演进检查任务已配置")

    async def _run_relationship_review(self, max_pairs: int = 50) -> None:
        """Mock relationship review."""
        print("[MockScheduler] 模拟关系审查任务执行")

    async def _run_theme_evolution_check(self) -> None:
        """Mock theme evolution check."""
        print("[MockScheduler] 模拟主题演进检查任务执行")

    def get_job_status(self) -> dict[str, Any]:
        """Get mock job status."""
        return {
            "running": self._running,
            "mock_mode": True,
            "jobs": self._mock_jobs
        }
