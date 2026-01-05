import asyncio
import inspect
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from wtforms import StringField, FloatField

from ivoryos.utils import utils
from ivoryos.utils.db_models import Script
from ivoryos.utils.form import create_form_from_pseudo
from ivoryos.utils.task_runner import TaskRunner
from ivoryos.utils.utils import _inspect_class


# --- Fixtures & Helpers ---

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['WTF_CSRF_ENABLED'] = False
    return app

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.app_context.return_value.__enter__.return_value = app
    return app

@pytest.fixture
def runner_with_mock_db():
    with patch('ivoryos.utils.task_runner.db') as mock_db:
        runner = TaskRunner()
        yield runner

class MockInstrument:
    def __init__(self):
        self._temp = 25.0

    @property
    def temperature(self):
        return self._temp

    @temperature.setter
    def temperature(self, value):
        self._temp = float(value)

class MockDeck:
    def __init__(self):
        self.inst = MockInstrument()

class TestDevice:
    def __init__(self):
        self._temp = 25.0

    def connect(self):
        """Connect to device"""
        pass

    @property
    def temperature(self):
        """Get temperature"""
        return self._temp

    @temperature.setter
    def temperature(self, value):
        self._temp = value

    @property
    def ready(self):
        """Is ready"""
        return True

# --- Test Classes ---

class TestPropertyIntrospection:
    """Tests from test_utils_properties.py"""
    
    def test_inspect_class_properties(self):
        device = TestDevice()
        result = _inspect_class(device)
        
        # Check regular method
        assert 'connect' in result
        assert result['connect']['docstring'] == 'Connect to device'
        assert not result['connect'].get('is_property')

        # Check property with setter
        assert 'temperature' in result
        temp_info = result['temperature']
        assert temp_info['is_property'] is True
        assert temp_info['has_setter'] is True
        assert temp_info['docstring'] == 'Get temperature'

        # Check read-only property
        assert 'ready' in result
        ready_info = result['ready']
        assert ready_info['is_property'] is True
        assert ready_info['has_setter'] is False
        assert ready_info['docstring'] == 'Is ready'

class TestPropertyCompilation:
    """Tests from test_compilation_properties.py"""

    def test_compile_property_setter(self):
        # Mock snapshot
        snapshot = {
            'my_inst': {
                'temperature': {
                    'is_property': True,
                    'has_setter': True
                },
                'connect': {
                    'is_property': False
                }
            }
        }

        # Create script with setter action
        script = Script(name="test_script")
        script.script_dict = {
            'prep': [],
            'script': [
                {
                    "id": 1,
                    "instrument": "my_inst",
                    "action": "temperature_(setter)",
                    "args": {"value": 30.5},
                    "return": "", # Setters have empty return
                    "arg_types": {'value': 'float'}
                },
                 {
                    "id": 2,
                    "instrument": "my_inst",
                    "action": "connect",
                    "args": {},
                    "return": "",
                },
                {
                    "id": 3,
                    "instrument": "my_inst",
                    "action": "temperature",
                    "args": {},
                    "return": "temp_val",
                    "arg_types": {},
                }
            ],
            'cleanup': []
        }
        
        # Compile
        # We expect 'my_inst.temperature = 30.5' and 'my_inst.connect()'
        # And 'temp_val = my_inst.temperature' (getter, no parens)
        
        exec_str_collection = script.compile(snapshot=snapshot)
        script_code = exec_str_collection['script']
        
        print(script_code)
        
        assert "my_inst.temperature = 30.5" in script_code
        assert "my_inst.connect()" in script_code
        assert "temp_val = my_inst.temperature" in script_code
        assert "my_inst.temperature()" not in script_code
        assert "my_inst.set_temperature" not in script_code

    def test_compile_property_setter_variable(self):
        # Mock snapshot
        snapshot = {
            'my_inst': {
                'temperature': {'is_property': True, 'has_setter': True}
            }
        }
        script = Script(name="test_script_var")
        script.script_dict = {
            'prep': [],
            'script': [
                 {
                    "id": 1,
                    "instrument": "variable",
                    "action": "my_var",
                    "args": {"statement": 10},
                     "return": "",
                     "arg_types": {"statement": "int"}
                },
                {
                    "id": 2,
                    "instrument": "my_inst",
                    "action": "temperature_(setter)",
                    "args": {"value": "#my_var"},
                    "return": "", 
                    "arg_types": {'value': 'float'}
                }
            ],
            'cleanup': []
        }
        
        exec_str_collection = script.compile(snapshot=snapshot)
        script_code = exec_str_collection['script']
        print(script_code)
        
        assert "my_inst.temperature = my_var" in script_code

class TestDesignPropertyHandler:
    """Tests from test_design_property_handler.py"""

    def test_get_arg_type_with_virtual_setter(self):
        # Simulate the logic I added to methods_handler
        
        # Mock definitions
        functions = {
            'temperature': {
                'is_property': True, 
                'signature': inspect.Signature(return_annotation=float)
            }
        }
        function_name = 'temperature_(setter)'
        kwargs = {'value': '30.5', 'hidden_name': 'temperature_(setter)'}
        
        # Simulate the look up logic
        function_data = functions.get(function_name)
        if not function_data and function_name.endswith("_(setter)"):
            prop_name = function_name[:-9]
            prop_data = functions.get(prop_name)
            if prop_data and prop_data.get('is_property'):
                sig = prop_data.get('signature')
                param_type = inspect._empty
                if sig and sig.return_annotation is not inspect._empty:
                    param_type = sig.return_annotation
                
                setter_sig = inspect.Signature(
                    parameters=[inspect.Parameter('value', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=param_type)],
                    return_annotation=None
                )
                function_data = {'signature': setter_sig}
                
        assert function_data is not None
        assert 'signature' in function_data
        sig = function_data['signature']
        assert 'value' in sig.parameters
        assert sig.parameters['value'].annotation == float
        
        # Verify get_arg_type works with this synthesized data
        arg_types = utils.get_arg_type(kwargs, function_data)
        # create_form_from_pseudo uses 'value' as parameter name
        assert arg_types['value'] == 'float'

class TestPropertyForms:
    """Tests from test_form_properties.py"""

    def test_form_from_properties(self, app):
        with app.app_context():
            # Mock pseudo deck data
            pseudo = {
                'connect': {
                    'signature': inspect.Signature(),
                    'docstring': 'Connect',
                    'is_property': False
                },
                'temperature': {
                    'signature': inspect.Signature(return_annotation=float),
                    'docstring': 'Get temp',
                    'is_property': True,
                    'has_setter': True
                },
                'ready': {
                    'signature': inspect.Signature(return_annotation=bool),
                    'docstring': 'Is ready',
                    'is_property': True,
                    'has_setter': False
                }
            }
            
            forms = create_form_from_pseudo(pseudo, autofill=False, design=True)
            
            assert 'connect' in forms
            assert 'temperature' in forms
            assert 'temperature_(setter)' in forms
            assert 'ready' in forms
            assert 'ready_(setter)' not in forms

            # Check setter form fields
            setter_form = forms['temperature_(setter)']
            # Should have a 'value' field (derived from synthetic signature)
            assert hasattr(setter_form, 'value')
            # Should NOT have a 'return' field
            assert not hasattr(setter_form, 'return')
            # Since we passed design=True, fields are VariableOr...Field, but base depends on annotation
            # checks logic in create_form_for_method

class TestPropertyExecution:
    """Tests from test_task_runner_properties.py"""

    @pytest.mark.asyncio
    async def test_task_runner_properties(self, mock_app, runner_with_mock_db):
        deck = MockDeck()
        
        # Setup global config
        from ivoryos.utils.global_config import GlobalConfig
        gc = GlobalConfig()
        gc.defined_variables['my_inst'] = deck.inst
        gc.deck = deck
        
        # Test Getter
        res = await runner_with_mock_db.run_single_step("my_inst", "temperature", {}, current_app=mock_app)
        assert res['success'] is True, f"Getter failed: {res.get('output')}"
        assert res['output'] == 25.0

        # Test Setter
        res_set = await runner_with_mock_db.run_single_step("my_inst", "temperature_(setter)", {"value": 30.0}, current_app=mock_app)
        assert res_set['success'] is True, f"Setter failed: {res_set.get('output')}"
        assert deck.inst.temperature == 30.0
