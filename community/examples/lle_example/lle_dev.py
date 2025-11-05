"""
Liquid Liquid Extraction (WIP) platform
Platform Developers: Maria Politi. All rights reserved.
"""
from automated_lle.implementations.SDL7.sdl7_ur_manager import ArmManager
from automated_lle.implementations.SDL7.sdl7_mlh import MLH
from automated_lle.components.balance_control import Quan
from automated_lle.components.lc_control import HPLC
from automated_lle.components.logger import logger, file_log

import ivoryos

file_log(enable=True, path="D:/git_repositories/automated-lle/implementation/SDL7/logs")
logger.info("Redo from 2025-01-27")
logger.info("Running Navy Blue Dye extraction example with wash")

# import your sequence(s) from a URScript file
sequence = r"D:\git_repositories\automated-lle\automated_lle\components\sequences\LLE_Deck.script"
# create an instance o UR3Arm
ur_address = "137.82.65.187"
ur = ArmManager(ur_address, sequence)
mlh = MLH(mlh_port='COM3', rinse_port='COM4')
balance = Quan()
hplc = HPLC()

if __name__ == "__main__":
    ivoryos.run(__name__)