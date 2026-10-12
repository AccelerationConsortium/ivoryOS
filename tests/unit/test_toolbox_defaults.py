from ivoryos.routes.design.design import open_toolbox_groups


def methods(n):
    return {f"method_{i}": {} for i in range(n)}


def test_a_small_deck_opens_every_instrument():
    schema = {"balance": methods(2), "pump": methods(3), "sdl": methods(6)}
    assert open_toolbox_groups(list(schema), schema, budget=12) == ["balance", "pump", "sdl"]


def test_instruments_open_from_the_top_until_the_budget_is_used():
    schema = {"a": methods(5), "b": methods(5), "c": methods(5), "d": methods(1)}
    assert open_toolbox_groups(list(schema), schema, budget=12) == ["a", "b"]


def test_the_first_instrument_opens_even_when_it_alone_is_over_budget():
    schema = {"a": methods(30), "b": methods(1)}
    assert open_toolbox_groups(list(schema), schema, budget=12) == ["a"]


def test_without_a_schema_every_instrument_opens():
    assert open_toolbox_groups(["a", "b"], None) == ["a", "b"]
    assert open_toolbox_groups([], {}) == []
