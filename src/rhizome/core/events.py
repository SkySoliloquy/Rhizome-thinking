"""Event handling system for Rhizome Thinking.

Provides event-driven architecture for node lifecycle events,
relationship analysis, and theme evolution detection.
"""

import asyncio
import logging
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional, TypeVar

from rhizome.core.models import Node
from rhizome.core.theme_models import Theme

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class NodeCreatedEvent:
    """Event triggered when a new node is created.

    Attributes:
        node: The newly created node
        timestamp: When the event occurred
        metadata: Additional event metadata
    """

    node: Node
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisCompletedEvent:
    """Event triggered when analysis completes.

    Attributes:
        node_id: ID of the analyzed node
        analysis_type: Type of analysis performed
        results: Analysis results
        success: Whether analysis succeeded
        timestamp: When the analysis completed
    """

    node_id: str
    analysis_type: str
    results: Any
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


class EventHandler:
    """Base class for event handlers."""

    async def handle(self, event: Any) -> None:
        """Handle an event.

        Args:
            event: The event to handle
        """
        raise NotImplementedError


class RelationshipAnalysisHandler(EventHandler):
    """Handler for relationship analysis on new node creation."""

    def __init__(
        self,
        node_store=None,
        theme_store=None,
        relationship_manager=None
    ) -> None:
        """Initialize the handler.

        Args:
            node_store: NodeStore instance for fetching nodes
            theme_store: ThemeStore instance for fetching themes
            relationship_manager: RelationshipManager instance (lazy loaded if None)
        """
        self._node_store_ref = weakref.ref(node_store) if node_store else None
        self._theme_store_ref = weakref.ref(theme_store) if theme_store else None
        self._relationship_manager = relationship_manager

    def _get_node_store(self):
        """Get node store from weak reference."""
        if self._node_store_ref:
            return self._node_store_ref()
        return None

    def _get_theme_store(self):
        """Get theme store from weak reference."""
        if self._theme_store_ref:
            return self._theme_store_ref()
        return None

    def _get_relationship_manager(self):
        """Get or create relationship manager."""
        if self._relationship_manager is None:
            try:
                from rhizome.core.relationship_manager import RelationshipManager
                self._relationship_manager = RelationshipManager()
            except (ValueError, ImportError) as e:
                logger.warning(f"Failed to create RelationshipManager: {e}")
                from rhizome.core.relationship_manager import MockRelationshipManager
                self._relationship_manager = MockRelationshipManager()
        return self._relationship_manager

    async def handle(self, event: NodeCreatedEvent) -> None:
        """Analyze relationships for the newly created node.

        Args:
            event: NodeCreatedEvent containing the new node
        """
        node = event.node
        logger.info(f"开始分析节点关系: {node.id[:8]}")

        try:
            # Get existing nodes and themes for analysis
            node_store = self._get_node_store()
            theme_store = self._get_theme_store()

            all_nodes = []
            all_themes = []

            if node_store:
                all_nodes = node_store.list_all(limit=50)
                # Exclude the new node itself
                all_nodes = [n for n in all_nodes if n.id != node.id]

            if theme_store:
                all_themes = theme_store.list_all()

            # Perform relationship analysis
            manager = self._get_relationship_manager()
            suggestions = await manager.analyze_new_node(
                node=node,
                all_nodes=all_nodes,
                all_themes=all_themes,
                max_candidates=20
            )

            logger.info(f"节点 {node.id[:8]} 关系分析完成: {len(suggestions)} 个建议")

        except Exception as e:
            logger.error(f"节点 {node.id[:8]} 关系分析失败: {e}")
            raise


class ThemeEvolutionHandler(EventHandler):
    """Handler for theme evolution detection on new node creation."""

    def __init__(
        self,
        theme_store=None,
        evolution_analyzer=None
    ) -> None:
        """Initialize the handler.

        Args:
            theme_store: ThemeStore instance for fetching themes
            evolution_analyzer: ThemeEvolutionAnalyzer instance (lazy loaded if None)
        """
        self._theme_store_ref = weakref.ref(theme_store) if theme_store else None
        self._evolution_analyzer = evolution_analyzer

    def _get_theme_store(self):
        """Get theme store from weak reference."""
        if self._theme_store_ref:
            return self._theme_store_ref()
        return None

    def _get_evolution_analyzer(self):
        """Get or create evolution analyzer."""
        if self._evolution_analyzer is None:
            try:
                from rhizome.core.theme_evolution import ThemeEvolutionAnalyzer
                self._evolution_analyzer = ThemeEvolutionAnalyzer()
            except (ValueError, ImportError) as e:
                logger.warning(f"Failed to create ThemeEvolutionAnalyzer: {e}")
                from rhizome.core.theme_evolution import MockThemeEvolutionAnalyzer
                self._evolution_analyzer = MockThemeEvolutionAnalyzer()
        return self._evolution_analyzer

    async def handle(self, event: NodeCreatedEvent) -> None:
        """Detect theme evolution conflicts for the newly created node.

        Args:
            event: NodeCreatedEvent containing the new node
        """
        node = event.node
        logger.info(f"开始检测主题演进冲突: {node.id[:8]}")

        try:
            # Get existing themes for analysis
            theme_store = self._get_theme_store()
            all_themes = []

            if theme_store:
                all_themes = theme_store.list_all()

            if not all_themes:
                logger.info(f"没有现有主题需要检测冲突: {node.id[:8]}")
                return

            # Perform conflict detection
            analyzer = self._get_evolution_analyzer()
            suggestions = await analyzer.detect_conflicts(
                new_node=node,
                all_themes=all_themes
            )

            if suggestions:
                # Save suggestions to evolution store
                try:
                    from rhizome.core.evolution_store import EvolutionStore
                    store = EvolutionStore()
                    for suggestion in suggestions:
                        store.save_suggestion(suggestion)
                    logger.info(f"检测到 {len(suggestions)} 个主题演进建议")
                except ImportError:
                    logger.warning("EvolutionStore 不可用，建议未持久化")

            logger.info(f"节点 {node.id[:8]} 主题演进检测完成: {len(suggestions)} 个冲突/建议")

        except Exception as e:
            logger.error(f"节点 {node.id[:8]} 主题演进检测失败: {e}")
            raise


class EventBus:
    """Simple event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._handlers: dict[type, list[EventHandler]] = {}
        self._callback_handlers: dict[type, list[weakref.ref]] = {}

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The type of event to subscribe to
            handler: The handler to call when events occur
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler {handler.__class__.__name__} subscribed to {event_type.__name__}")

    def subscribe_callback(
        self,
        event_type: type,
        callback: Callable[[Any], Coroutine[Any, Any, None]]
    ) -> None:
        """Subscribe a callback function to an event type.

        Args:
            event_type: The type of event to subscribe to
            callback: The async callback function
        """
        if event_type not in self._callback_handlers:
            self._callback_handlers[event_type] = []
        # Use weakref to avoid memory leaks
        self._callback_handlers[event_type].append(weakref.ref(callback))

    async def publish(self, event: Any) -> list[asyncio.Task]:
        """Publish an event to all subscribers.

        Args:
            event: The event to publish

        Returns:
            List of tasks created for async handlers
        """
        event_type = type(event)
        tasks = []

        # Handle class-based handlers
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                task = asyncio.create_task(handler.handle(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Handler {handler.__class__.__name__} failed: {e}")

        # Handle callback-based handlers
        callbacks = self._callback_handlers.get(event_type, [])
        for callback_ref in callbacks[:]:  # Copy list to allow removal
            callback = callback_ref()
            if callback is None:
                # Callback was garbage collected, remove it
                callbacks.remove(callback_ref)
                continue
            try:
                task = asyncio.create_task(callback(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Callback handler failed: {e}")

        return tasks


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns:
        The global EventBus instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (mainly for testing)."""
    global _event_bus
    _event_bus = None


async def publish_node_created(
    node: Node,
    metadata: Optional[dict[str, Any]] = None
) -> list[asyncio.Task]:
    """Publish a NodeCreatedEvent.

    Args:
        node: The newly created node
        metadata: Optional metadata to include

    Returns:
        List of tasks created for handlers
    """
    event = NodeCreatedEvent(node=node, metadata=metadata or {})
    return await get_event_bus().publish(event)


def setup_default_handlers(
    node_store=None,
    theme_store=None
) -> None:
    """Set up default event handlers.

    Args:
        node_store: NodeStore instance
        theme_store: ThemeStore instance
    """
    bus = get_event_bus()

    # Subscribe relationship analysis handler
    relationship_handler = RelationshipAnalysisHandler(
        node_store=node_store,
        theme_store=theme_store
    )
    bus.subscribe(NodeCreatedEvent, relationship_handler)

    # Subscribe theme evolution handler
    evolution_handler = ThemeEvolutionHandler(
        theme_store=theme_store
    )
    bus.subscribe(NodeCreatedEvent, evolution_handler)

    logger.info("默认事件处理器已设置")
