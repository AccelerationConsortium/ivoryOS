from ivoryos.runtime.state import GlobalState


global_state = GlobalState()


class HumanInterventionRequired(Exception):
    pass


def ensure_deck(required=False):
    """Return the current deck without keeping a stale module-level cache."""
    if required:
        return global_state.require_deck()
    return global_state.deck


def pause(reason="Human intervention required"):
    handlers = global_state.notification_handlers
    if handlers:
        for handler in handlers:
            try:
                handler(reason)
            except Exception as e:
                print(f"[notify] handler {handler} failed: {e}")
    raise HumanInterventionRequired(reason)
