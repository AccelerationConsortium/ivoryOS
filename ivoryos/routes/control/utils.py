from flask import session

from ivoryos.utils.global_config import GlobalConfig


global_config = GlobalConfig()


def find_instrument_by_name(name: str):
    """
    find instrument class object by instance name
    """
    if name.startswith("deck"):
        name = name.replace("deck.", "")
        return getattr(global_config.deck, name)
    elif name.startswith("blocks"):
        return global_config.building_blocks[name]
    elif name in global_config.defined_variables:
        return global_config.defined_variables[name]
    elif name in globals():
        return globals()[name]


def get_session_by_instrument(session_name, instrument):
    """get data from session by instrument"""
    session_object = session.get(session_name, {})
    functions = session_object.get(instrument, [])
    return functions


def post_session_by_instrument(session_name, instrument, data):
    """
    save new data to session by instrument
    :param session_name: "card_order" or "hidden_functions"
    :param instrument: function name of class object
    :param data: order list or hidden function list
    """
    session_object = session.get(session_name, {})
    session_object[instrument] = data
    session[session_name] = session_object
