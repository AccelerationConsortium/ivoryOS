from typing import Union

from kinova_deck.moving.kinova_movable_config import KinovaMoveableSequence, KinovaMoveableConfig


def pddl_object(name: str, kind: str, args: dict = None) -> dict:
    return {
        "name": name,
        "kind": kind,
        "args": args
    } if args else {
        "name": name,
        "kind": kind,
    }


def predicate(name: str, objects: list, initial_value: Union[bool, int, float],
              final_value: Union[bool, int, float] = None) -> dict:
    return {
        "predicate": name,
        "objects": [o["name"] for o in objects],
        "initial_value": initial_value,
        "final_value": final_value
    } if final_value else {
        "predicate": name,
        "objects": [o["name"] for o in objects],
        "initial_value": initial_value,
    }


home = pddl_object("home", "location", {"sequence_location_name": "central_home"})

vial_location = pddl_object("vial tray", "addable", {
    "sequence_location_name": "vial_tray_center_grip",
    "rows": 4,
    "columns": 4,
    "spacing_x": 20,
    "spacing_y": 20,
    "offset_rx": -90,
    "offset_ry": 180,
    "offset_rz": 180,
    "index": "A1"})

vial_locations = []

for r in range(vial_location["args"]["rows"]):
    for c in range(vial_location["args"]["columns"]):
        letter = "ABCDEFGHIJKLMNO"[r]
        new_vial_location = vial_location.copy()
        new_vial_location["name"] = vial_location["name"] + letter + str(c + 1)
        vial_locations.append(new_vial_location)

kinova = pddl_object("kinova", "arm",
                     {"home_coordinates": "central_home"})

liquid_handler_base = pddl_object("europa base", "handlerable",
                                  {"sequence_location_name": "liquid_base_xy"})

# TODO: add grid for this too
solvent_tray = pddl_object("solvent tray", "holdable", {
    "sequence_location_name": "solvent_tray_draw",
    "rows": 1,
    "columns": 2,
    "spacing_x": 38,
    "spacing_y": 0,
    "offset_rx": -90,
    "offset_ry": -180,
    "offset_rz": 180})

kinova_shaker = pddl_object("kinova shaker", "shakable", {
    "sequence_location_name": "shaker_center_grip_vial_height",
    "rows": 3,
    "columns": 4,
    "spacing_x": 18,
    "spacing_y": 18,
    "offset_rx": -90,
    "offset_ry": -180,
    "offset_rz": 180
})

liquid_handler = pddl_object("europa", "handlerequip", {"max_volume_ul": 1000})

vial_1 = pddl_object("vial 1", "glassware")

vial_2 = pddl_object("vial 2", "glassware")

acetone = pddl_object("acetone", "liquid", {
    "density": 0.7900,
    "formula": "C3H6O"
})

salt = pddl_object("salt", "solid", {
    "density": 2.16,
    "formula": "NaCl"
})

predicates = [
    predicate("arm-location", [kinova, home], True, True),
    predicate("moveable-gripped", [liquid_handler, kinova], False, False),
    predicate("max-volume", [liquid_handler], 1),
    predicate("moveable-home", [liquid_handler, liquid_handler_base], True),
    predicate("object-allowed-at-location", [liquid_handler, liquid_handler_base], True),
    predicate("object-allowed-at-location", [liquid_handler, home], True),
    predicate("object-at-location", [liquid_handler, liquid_handler_base], True),
    predicate("safe-to-move", [liquid_handler], True, True),
    predicate("handler-amount", [acetone, liquid_handler], 0),
]

objects = [
    home,
    kinova,
    liquid_handler_base,
    liquid_handler,
    acetone
]

kinova_configs = [
    KinovaMoveableConfig(name=liquid_handler["name"],
                         safe_moves=[
                             KinovaMoveableSequence(location_A=home["name"],
                                                    location_B=[liquid_handler_base["name"]])],
                         grip_open=0,
                         grip_close=0.29)]
