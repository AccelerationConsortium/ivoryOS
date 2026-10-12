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


# ---- undo history -------------------------------------------------------------------------

def _steps(*actions):
    return [{"id": i, "uuid": 100 + i, "instrument": "deck.balance", "action": action, "args": {}, "return": ""}
            for i, action in enumerate(actions, start=1)]


def _draft(*actions, **fields):
    return Script(author="hist_user", script_dict={"prep": [], "script": _steps(*actions), "cleanup": []}, **fields)


def test_a_change_can_be_undone_and_redone(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h1")
        post_script_for_user("hist_user", _draft("weigh", "tare"), draft_id="h1")

        script, message = draft_service.undo_for_user("hist_user", "h1")
        assert [s["action"] for s in script.script_dict["script"]] == ["weigh"]
        assert message == "Undid Add balance.tare"
        # the draft itself is back, not only the answer
        assert [s["action"] for s in get_script_for_user("hist_user", "h1").script_dict["script"]] == ["weigh"]

        script, message = draft_service.redo_for_user("hist_user", "h1")
        assert [s["action"] for s in script.script_dict["script"]] == ["weigh", "tare"]
        assert message == "Redid Add balance.tare"


def test_the_first_change_can_be_undone_back_to_an_empty_draft(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h2")

        script, _ = draft_service.undo_for_user("hist_user", "h2")

        assert script.isEmpty()
        assert draft_service.undo_for_user("hist_user", "h2") == (None, None)


def test_undo_still_works_after_a_server_restart(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h3")
        post_script_for_user("hist_user", _draft("weigh", "tare"), draft_id="h3")

        draft_service._drafts.clear()
        draft_service._histories.clear()  # the process restarted; the files are still there

        summary = draft_service.draft_history_for_user("hist_user", "h3")
        assert summary["can_undo"] and summary["undo_label"] == "Add balance.tare"
        script, _ = draft_service.undo_for_user("hist_user", "h3")
        assert [s["action"] for s in script.script_dict["script"]] == ["weigh"]


def test_a_save_the_user_did_not_make_is_not_a_change_to_undo(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h4")
        post_script_for_user("hist_user", _draft("weigh", deck="lab_deck"), draft_id="h4", record=False)

        summary = draft_service.draft_history_for_user("hist_user", "h4", entries=True)
        assert [entry["label"] for entry in summary["entries"]] == ["Start", "Add balance.weigh"]
        draft_service.undo_for_user("hist_user", "h4")
        script, _ = draft_service.redo_for_user("hist_user", "h4")
        assert script.deck == "lab_deck"


def test_a_save_that_starts_no_history_writes_none(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft(deck="lab_deck"), draft_id="h5", record=False)

        assert not os.path.exists(draft_service.get_history_path("hist_user", "h5"))
        assert draft_service.draft_history_for_user("hist_user", "h5")["can_undo"] is False


def test_another_workflow_starts_a_new_history(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h8")
        post_script_for_user("hist_user", _draft("tare", name="flow"), draft_id="h8",
                             label="Open “flow”", new_history=True)

        summary = draft_service.draft_history_for_user("hist_user", "h8", entries=True)
        assert [entry["label"] for entry in summary["entries"]] == ["Open “flow”"]
        assert draft_service.undo_for_user("hist_user", "h8") == (None, None)
        assert [s["action"] for s in get_script_for_user("hist_user", "h8").script_dict["script"]] == ["tare"]


def test_a_label_given_by_the_route_names_the_change(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h6", label="Import “flow”")

        assert draft_service.draft_history_for_user("hist_user", "h6")["undo_label"] == "Import “flow”"


def test_discarding_a_draft_removes_its_history(app):
    with app.app_context():
        post_script_for_user("hist_user", _draft("weigh"), draft_id="h7")
        history_path = draft_service.get_history_path("hist_user", "h7")
        assert os.path.exists(history_path)

        discard_draft("hist_user", "h7")

        assert not os.path.exists(history_path)
        draft_service._histories.clear()
        assert draft_service.draft_history_for_user("hist_user", "h7")["can_undo"] is False


def test_histories_do_not_count_as_drafts_and_go_with_theirs(app, monkeypatch):
    monkeypatch.setattr(draft_service, "MAX_DRAFTS", 2)
    with app.app_context():
        for draft_id in ("p_old", "p_mid"):
            post_script_for_user("prune_hist", _draft("weigh"), draft_id=draft_id)
        old_path = get_draft_path("prune_hist", "p_old")
        stale = time.time() - 3600
        os.utime(old_path, (stale, stale))

        post_script_for_user("prune_hist", _draft("weigh"), draft_id="p_new")

        assert not os.path.exists(old_path)
        assert not os.path.exists(draft_service.get_history_path("prune_hist", "p_old"))
        for draft_id in ("p_mid", "p_new"):
            assert os.path.exists(get_draft_path("prune_hist", draft_id))
            assert os.path.exists(draft_service.get_history_path("prune_hist", draft_id))
