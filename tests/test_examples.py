import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

EXAMPLES = Path(__file__).parents[1] / "examples"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check(reports: list) -> None:  # type: ignore[type-arg]
    cold, warm, edited = reports
    assert (cold.mode, warm.mode, edited.mode) == ("miss", "prefetch", "hint")
    assert warm.tool_calls < cold.tool_calls
    assert warm.cited == cold.cited
    assert len(edited.cited) == len(cold.cited) - 1
    assert "Changed since:" in edited.rendered


def test_chunk_rag_example() -> None:
    check(load("chunk_rag").run())


def test_subforest_rag_example() -> None:
    pytest.importorskip("subforest")
    check(load("subforest_rag").run())


def test_examples_print(capsys: pytest.CaptureFixture[str]) -> None:
    assert load("chunk_rag").main() == 0
    assert "[prefetch]" in capsys.readouterr().out
