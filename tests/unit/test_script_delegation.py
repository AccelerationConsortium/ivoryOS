import pytest
from ivoryos.script.models import Script

def test_script_delegates_to_editor(app):
    with app.app_context():
        # Create a blank script
        script = Script(author="test_author")
        
        # Test that we can access a method that exists on ScriptEditor
        # but not on Script directly.
        valid_name = script.validate_function_name("invalid-name!")
        assert valid_name == "invalid_name_"
        
        # Test property delegation
        script.editing_type = "script"
        script.script_dict = {"script": [{"id": 1, "action": "test"}]}
        
        res = script.currently_editing_script
        assert len(res) == 1
        assert res[0]["action"] == "test"

        # Test error for non-existent attribute
        with pytest.raises(AttributeError):
            script.non_existent_method_xyz()
