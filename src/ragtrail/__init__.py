"""ragtrail: a trajectory cache for agentic RAG. Cache the path, never the answer."""

from ragtrail.match import MatchConfig
from ragtrail.models import NodeRef, RecallResult, Step, Trajectory
from ragtrail.recall import recall
from ragtrail.recorder import Recorder
from ragtrail.resolver import GenericResolver, NodeResolver
from ragtrail.store import SQLiteStore, TrajectoryStore

__all__ = [
    "GenericResolver",
    "MatchConfig",
    "NodeRef",
    "NodeResolver",
    "RecallResult",
    "Recorder",
    "SQLiteStore",
    "Step",
    "Trajectory",
    "TrajectoryStore",
    "recall",
]
