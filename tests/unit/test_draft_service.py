import os
import json
from ivoryos.services.draft_service import get_draft_path, get_script_for_user, post_script_for_user
from ivoryos.script import Script

def test_get_draft_path(app):
    with app.app_context():
        path = get_draft_path("test_user")
        assert "test_user" in path
        assert path.endswith(".json")

def test_post_and_get_script_for_user(app):
    with app.app_context():
        user_id = "test_user_draft"
        script = Script(author=user_id, name="Draft Test")
        
        # Save
        post_script_for_user(user_id, script)
        
        # Read back
        loaded = get_script_for_user(user_id)
        assert loaded.author == user_id
        assert loaded.name == "Draft Test"
        
        # Cleanup
        draft_path = get_draft_path(user_id)
        if os.path.exists(draft_path):
            os.remove(draft_path)

def test_get_script_for_missing_user(app):
    with app.app_context():
        # Should return a new empty script
        loaded = get_script_for_user("nonexistent_user_12345")
        assert loaded.author == "nonexistent_user_12345"
