"""GovernorStateGraph — drop-in LangGraph StateGraph replacement with governance.

Automatically wraps all added nodes with GovernorNode using a default policy.
"""

from typing import Any, Callable

from langgraph.graph import StateGraph

from .core import GovernorNode
from .policy import GovernancePolicy


class GovernorStateGraph(StateGraph):
    """A StateGraph that automatically wraps nodes with GovernorNode.

    Usage:
        from governornode import GovernorStateGraph

        graph = GovernorStateGraph(State, default_policy=my_policy)
        graph.add_node("agent", my_agent_fn)  # auto-wrapped
        app = graph.compile()
        result = app.invoke({"input": "hello"})
    """

    def __init__(self, *args, default_policy: GovernancePolicy | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_policy = default_policy or GovernancePolicy()

    def add_node(self, node: str | Callable, action: Callable | None = None, **kwargs) -> "GovernorStateGraph":
        """Add a node, auto-wrapping it with GovernorNode.

        Supports both:
            add_node("name", fn)
            add_node("name", action=fn)  (LangGraph v1 API compat)
        """
        if isinstance(node, str):
            node_name = node
            node_fn = action if action is not None else kwargs.get("action", None)
            if node_fn is None:
                raise ValueError(f"Must provide a callable for node '{node_name}'")
        else:
            node_name = getattr(node, "__name__", str(node))
            node_fn = node

        # Wrap in GovernorNode if not already wrapped
        if not isinstance(node_fn, GovernorNode):
            node_fn = GovernorNode(
                node=node_fn,
                name=node_name,
                policy=self._default_policy,
            )

        # Add to graph via StateGraph's add_node
        super().add_node(node_name, node_fn)
        return self

    def get_governor(self, node_name: str) -> GovernorNode | None:
        """Retrieve the GovernorNode for a given node name (if wrapped)."""
        for name, action in self.nodes.items():
            if name == node_name and isinstance(action, GovernorNode):
                return action
        return None

    def get_all_recorders(self) -> dict[str, Any]:
        """Get recorders for all governed nodes."""
        result = {}
        for name, node in self.nodes.items():
            if isinstance(node, GovernorNode):
                result[name] = node.get_recorder()
        return result
