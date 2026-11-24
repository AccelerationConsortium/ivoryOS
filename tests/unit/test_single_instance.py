"""One process per deck script."""
import os
import subprocess
import sys
import textwrap

import pytest

from ivoryos.utils import single_instance


@pytest.fixture(autouse=True)
def lock_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(single_instance, "LOCK_DIR", str(tmp_path / "locks"))
    yield
    for script in list(single_instance._held):
        single_instance.release(script)


@pytest.fixture
def script(tmp_path):
    path = tmp_path / "my_deck.py"
    path.write_text("pump = None\n")
    return str(path)


def _hold_in_child(script, lock_dir):
    """Start a process that holds ``script`` until its stdin closes."""
    code = textwrap.dedent("""
        import sys
        from ivoryos.utils import single_instance
        single_instance.LOCK_DIR = sys.argv[1]
        single_instance.acquire(sys.argv[2], url="http://localhost:8123/ivoryos")
        print("held", flush=True)
        sys.stdin.read()
    """)
    child = subprocess.Popen([sys.executable, "-c", code, lock_dir, script],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == "held"
    return child


def test_a_second_process_is_refused_with_who_holds_it(script):
    child = _hold_in_child(script, single_instance.LOCK_DIR)
    try:
        with pytest.raises(single_instance.AlreadyRunning) as err:
            single_instance.acquire(script)
        message = str(err.value)
        assert f"process {child.pid}" in message
        assert "http://localhost:8123/ivoryos" in message
        assert "my_deck.py" in message
        assert str(child.pid) in message.split("Stop the running one first")[1]
    finally:
        child.stdin.close()
        child.wait(timeout=10)


def test_the_lock_goes_away_when_the_holder_is_killed(script):
    child = _hold_in_child(script, single_instance.LOCK_DIR)
    child.kill()
    child.wait(timeout=10)
    single_instance.acquire(script)  # no stale lock left behind


def test_the_same_path_written_differently_is_the_same_script(script, tmp_path):
    child = _hold_in_child(script, single_instance.LOCK_DIR)
    try:
        other_spelling = os.path.join(str(tmp_path), ".", "my_deck.py")
        with pytest.raises(single_instance.AlreadyRunning):
            single_instance.acquire(other_spelling)
    finally:
        child.stdin.close()
        child.wait(timeout=10)


def test_different_scripts_run_side_by_side(script, tmp_path):
    other = tmp_path / "other_deck.py"
    other.write_text("")
    child = _hold_in_child(script, single_instance.LOCK_DIR)
    try:
        single_instance.acquire(str(other))
    finally:
        child.stdin.close()
        child.wait(timeout=10)


def test_acquiring_twice_in_one_process_is_fine(script):
    single_instance.acquire(script)
    single_instance.acquire(script)


def test_release_lets_another_process_take_it(script):
    single_instance.acquire(script)
    single_instance.release(script)
    child = _hold_in_child(script, single_instance.LOCK_DIR)
    child.stdin.close()
    child.wait(timeout=10)


def test_message_without_holder_details_still_says_what_to_do():
    message = str(single_instance.AlreadyRunning("/lab/deck.py", {}))
    assert "already running deck.py." in message
    assert "Ctrl+C" in message
