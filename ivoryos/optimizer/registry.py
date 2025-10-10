# optimizers/registry.py

from ivoryos.optimizer.ax_optimizer import AxOptimizer
from ivoryos.optimizer.baybe_optimizer import BaybeOptimizer
from ivoryos.optimizer.nimo_optimizer import NIMOOptimizer

OPTIMIZER_REGISTRY = {
    "ax": AxOptimizer,
    "baybe": BaybeOptimizer,
    "nimo": NIMOOptimizer,
}
