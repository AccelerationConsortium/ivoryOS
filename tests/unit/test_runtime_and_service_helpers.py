import pytest

from ivoryos.runtime.runner_runtime import HumanInterventionRequired, ensure_deck, global_state, pause
from ivoryos.services.connection_history import available_pseudo_deck, import_history, save_to_history
from ivoryos.utils.decorators import BUILDING_BLOCKS, BlockNamespace, block


def test_connection_history_deduplicates_and_lists_pseudo_decks(tmp_path):
    history = tmp_path / "deck_history.txt"
    deck_file = tmp_path / "deck.py"
    deck_file.write_text("# deck")

    save_to_history(str(deck_file), history)
    save_to_history(str(deck_file), history)

    assert import_history(history) == [str(deck_file)]
    assert import_history(tmp_path / "missing.txt") == []

    (tmp_path / "one.pkl").write_text("one")
    (tmp_path / "two.pkl").write_text("two")
    assert sorted(available_pseudo_deck(tmp_path)) == ["deck.py", "deck_history.txt", "one.pkl", "two.pkl"]


def test_block_decorator_registers_functions_and_namespace_exposes_them():
    original = {category: dict(methods) for category, methods in BUILDING_BLOCKS.items()}
    BUILDING_BLOCKS.clear()

    try:
        @block(category="math")
        def add_one(value: int):
            """Add one."""
            return value + 1

        @block
        async def async_identity(value):
            return value

        assert BUILDING_BLOCKS["math"]["add_one"]["func"] is add_one
        assert str(BUILDING_BLOCKS["math"]["add_one"]["signature"]) == "(value: int)"
        assert BUILDING_BLOCKS["math"]["add_one"]["docstring"] == "Add one."
        assert BUILDING_BLOCKS["general"]["async_identity"]["coroutine"] is True

        namespace = BlockNamespace(BUILDING_BLOCKS["math"])
        assert namespace.add_one(2) == 3
    finally:
        BUILDING_BLOCKS.clear()
        BUILDING_BLOCKS.update(original)


def test_ensure_deck_and_pause_use_global_runtime_state():
    previous_deck = global_state._deck
    previous_handlers = list(global_state._notification_handlers)
    calls = []

    try:
        global_state._deck = None
        assert ensure_deck() is None
        with pytest.raises(RuntimeError, match="No deck is configured"):
            ensure_deck(required=True)

        deck = object()
        global_state._deck = deck
        assert ensure_deck(required=True) is deck

        def handler(reason):
            calls.append(reason)

        def failing_handler(reason):
            raise RuntimeError(reason)

        global_state._notification_handlers = [handler, failing_handler]
        with pytest.raises(HumanInterventionRequired, match="Check sample"):
            pause("Check sample")

        assert calls == ["Check sample"]
    finally:
        global_state._deck = previous_deck
        global_state._notification_handlers = previous_handlers
