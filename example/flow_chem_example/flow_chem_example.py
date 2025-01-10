"""
Flow Chemistry Optimization
Platform Developers: Jacob Jessiman, Jiayu Zhang. All rights reserved.
"""
from flow_optimizer import FlowOptimizer
# https://gitlab.com/heingroup/ todo

import ivoryos

if __name__ == "__main__":
    flow_optimizer = FlowOptimizer()

    ivoryos.run(__name__, logger="flow")
