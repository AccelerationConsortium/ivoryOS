# optimizers/registry.py

from ivoryos.optimizer.ax_optimizer import AxOptimizer
from ivoryos.optimizer.baybe_optimizer import BaybeOptimizer

OPTIMIZER_REGISTRY = {
    "ax": AxOptimizer,
    "baybe": BaybeOptimizer
}
