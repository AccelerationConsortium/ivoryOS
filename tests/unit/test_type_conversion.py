"""
Integration tests for type conversion through the instrument control route.

These tests verify that string values submitted through web forms are correctly
converted to their typed Python equivalents before calling instrument methods.
"""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from tests.conftest import MockEnum


def test_int_conversion(auth, test_deck):
    """Tests that a string from a form is converted to an integer."""
    with patch('ivoryos.runtime.task_runner.TaskRunner._run_single_step', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"success": True, "output": 123}
        response = auth.post(
            '/ivoryos/instruments/deck.dummy',
            data={'hidden_name': 'int_method', 'arg': '123', 'hidden_wait': 'true'},
            follow_redirects=True
        )
        assert response.status_code == 200


def test_float_conversion(auth, test_deck):
    """Tests that a string from a form is converted to a float."""
    with patch('ivoryos.runtime.task_runner.TaskRunner._run_single_step', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"success": True, "output": 123.45}
        response = auth.post(
            '/ivoryos/instruments/deck.dummy',
            data={'hidden_name': 'float_method', 'arg': '123.45', 'hidden_wait': 'true'},
            follow_redirects=True
        )
        assert response.status_code == 200


def test_bool_conversion(auth, test_deck):
    """Tests that a string from a form is converted to a boolean."""
    with patch('ivoryos.runtime.task_runner.TaskRunner._run_single_step', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"success": True, "output": True}
        response = auth.post(
            '/ivoryos/instruments/deck.dummy',
            data={'hidden_name': 'bool_method', 'arg': 'true', 'hidden_wait': 'true'},
            follow_redirects=True
        )
        assert response.status_code == 200


def test_list_conversion(auth, test_deck):
    """Tests that a comma-separated string from a form is converted to a list."""
    with patch('ivoryos.runtime.task_runner.TaskRunner._run_single_step', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"success": True, "output": ['a', 'b', 'c']}
        response = auth.post(
            '/ivoryos/instruments/deck.dummy',
            data={'hidden_name': 'list_method', 'arg': 'a,b,c', 'hidden_wait': 'true'},
            follow_redirects=True
        )
        assert response.status_code == 200


def test_enum_conversion(auth, test_deck):
    """Tests that a string from a form is converted to an Enum member."""
    with patch('ivoryos.runtime.task_runner.TaskRunner._run_single_step', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"success": True, "output": MockEnum.OPTION_B.value}
        response = auth.post(
            '/ivoryos/instruments/deck.dummy',
            data={'hidden_name': 'enum_method', 'arg': 'OPTION_B', 'hidden_wait': 'true'},
            follow_redirects=True
        )
        assert response.status_code == 200