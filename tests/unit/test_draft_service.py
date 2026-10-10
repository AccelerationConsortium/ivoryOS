from ivoryos.services.draft_service import discard_draft, get_script_for_user, post_script_for_user
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
