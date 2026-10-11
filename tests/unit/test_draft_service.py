import os
import time

from ivoryos.services import draft_service
from ivoryos.services.draft_service import discard_draft, get_draft_path, get_script_for_user, post_script_for_user
from ivoryos.script import Script


def test_post_and_get_script_for_user(app):
    with app.app_context():
        user_id = "test_user_draft"
        script = Script(author=user_id, name="Draft Test")

        post_script_for_user(user_id, script, draft_id="d1")

        loaded = get_script_for_user(user_id, "d1")
        assert loaded.author == user_id
        assert loaded.name == "Draft Test"

        discard_draft(user_id, "d1")
        assert get_script_for_user(user_id, "d1").name != "Draft Test"


def test_get_script_for_missing_user(app):
    with app.app_context():
        # Should return a new empty script
        loaded = get_script_for_user("nonexistent_user_12345", "nope")
        assert loaded.author == "nonexistent_user_12345"


def test_drafts_of_one_user_are_kept_per_session(app):
    """A browser and a Python client logged in as the same user must not share a draft."""
    with app.app_context():
        post_script_for_user("same_user", Script(author="same_user", name="browser"), draft_id="browser")
        post_script_for_user("same_user", Script(author="same_user", name="client"), draft_id="client")

        assert get_script_for_user("same_user", "browser").name == "browser"
        assert get_script_for_user("same_user", "client").name == "client"


def test_editing_a_loaded_draft_does_not_change_it_until_posted(app):
    with app.app_context():
        post_script_for_user("u", Script(author="u", name="before"), draft_id="d")
        loaded = get_script_for_user("u", "d")
        loaded.name = "after"
        assert get_script_for_user("u", "d").name == "before"


def test_draft_survives_a_server_restart(app):
    """The session cookie outlives the server process, so the draft it points to must too."""
    with app.app_context():
        post_script_for_user("restart_user", Script(author="restart_user", name="unsaved work"), draft_id="r1")

        draft_service._drafts.clear()  # the process restarted: memory is gone, the file is not

        assert get_script_for_user("restart_user", "r1").name == "unsaved work"


def test_discarding_a_draft_removes_its_file(app):
    with app.app_context():
        post_script_for_user("bye_user", Script(author="bye_user", name="gone on logout"), draft_id="b1")
        path = get_draft_path("bye_user", "b1")
        assert os.path.exists(path)

        discard_draft("bye_user", "b1")

        assert not os.path.exists(path)
        draft_service._drafts.clear()
        assert get_script_for_user("bye_user", "b1").name != "gone on logout"


def test_draft_files_are_safe_paths(app):
    with app.app_context():
        path = get_draft_path("../../etc", "../passwd")
        assert os.path.dirname(path) == draft_service.get_drafts_folder()
        assert ".." not in os.path.basename(path)


def test_oldest_draft_files_are_pruned_beyond_the_cap(app, monkeypatch):
    """Sessions that never log out leave files behind; only the most recently saved ones are kept."""
    monkeypatch.setattr(draft_service, "MAX_DRAFTS", 2)
    with app.app_context():
        for draft_id in ("old", "mid"):
            post_script_for_user("prune_user", Script(author="prune_user", name=draft_id), draft_id=draft_id)
        old_path = get_draft_path("prune_user", "old")
        stale = time.time() - 3600
        os.utime(old_path, (stale, stale))

        post_script_for_user("prune_user", Script(author="prune_user", name="new"), draft_id="new")

        assert not os.path.exists(old_path)
        assert os.path.exists(get_draft_path("prune_user", "mid"))
        assert os.path.exists(get_draft_path("prune_user", "new"))
