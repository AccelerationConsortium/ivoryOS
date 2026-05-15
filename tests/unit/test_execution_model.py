import datetime
from ivoryos.models.execution import SingleStep

def test_single_step_as_dict():
    step = SingleStep(
        id=1,
        method_name="test_method",
        kwargs={"arg": 1},
        start_time=datetime.datetime(2023, 1, 1, 12, 0, 0),
        end_time=datetime.datetime(2023, 1, 1, 12, 1, 0),
        run_error="none",
        output={"result": "ok"}
    )
    # Add _sa_instance_state manually to simulate SQLAlchemy behavior
    step._sa_instance_state = "mock_state"
    
    result = step.as_dict()
    
    assert "_sa_instance_state" not in result
    assert result["id"] == 1
    assert result["method_name"] == "test_method"
    assert result["kwargs"] == {"arg": 1}
    assert result["run_error"] == "none"
    assert result["output"] == {"result": "ok"}
