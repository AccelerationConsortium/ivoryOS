import asyncio
from typing import List, Set
import pytest
from ivoryos.utils.task_runner import TaskRunner

# Mock function definitions for type checking
def mock_func(a, b, c=None):
    pass

def mock_func_with_types(a: list, b: List[int], c: Set[str]):
    pass

class TestTaskRunnerConversion:
    """Tests for TaskRunner argument type conversion logic."""

    def test_tuple_to_list_untyped(self):
        """Test that comma-separated strings remain tuples/strings for untyped functions."""
        runner = TaskRunner()
        kwargs = {"a": "1,2,3", "b": "1,2,3"}
        
        # mock_func is untyped, so default behavior (often tuple for csv in some contexts, 
        # but here we rely on what _convert_kwargs_type does by default or if it leaves it alone)
        # Based on original test expectation: "Untyped '1,2,3' should remain tuple" 
        # (Wait, if it comes from the form it might be string, but let's see how the original test asserted it)
        # Original assertion: assert converted['a'] == (1, 2, 3) 
        # This implies _convert_kwargs_type does some auto-conversion to tuple if it detects commas?
        # Let's reproduce the original test's expectations exactly.
        
        converted = runner._convert_kwargs_type(kwargs, mock_func)
        assert converted['a'] == (1, 2, 3)

    def test_tuple_to_list_typed(self):
        """Test that comma-separated strings convert to lists when type hint requires list."""
        runner = TaskRunner()
        kwargs = {"a": "1,2,3", "b": "1,2,3"}
        
        converted = runner._convert_kwargs_type(kwargs, mock_func_with_types)
        
        # 'a' is hinted as 'list'
        assert converted['a'] == [1, 2, 3]
        assert isinstance(converted['a'], list)
        
        # 'b' is hinted as 'List[int]'
        assert converted['b'] == [1, 2, 3]
        assert isinstance(converted['b'], list)
