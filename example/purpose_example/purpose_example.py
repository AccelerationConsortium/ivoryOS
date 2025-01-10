"""
PurPOSE Automation Platform.
Platform Developers: Noah Depner, Rebekah Greenwood, Jiyoon Min. All rights reserved.
"""
from ur.self_driving.configuration.self_driving_config import cryst_cosolvent
# https://gitlab.com/heingroup/purpose/-/blob/main/ur/self_driving/configuration/self_driving_config.py?ref_type=heads

from ur.configuration.ur_deck import (
     filter_handling,
     vial_handling,
     shaker_handling,
     quantos_handling,
     cap_handling,
     hplc_handling
)
# https://gitlab.com/heingroup/purpose/-/blob/main/ur/configuration/ur_deck.py?ref_type=heads

import ivoryos

if __name__ == "__main__":
    ivoryos.run(__name__)
