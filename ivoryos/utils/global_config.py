import threading


class GlobalConfig:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GlobalConfig, cls).__new__(cls, *args, **kwargs)
            cls._instance._deck = None
            cls._instance._building_blocks = None
            cls._instance._registered_workflows = None
            cls._instance._agent = None
            cls._instance._defined_variables = {}
            cls._instance._api_variables = set()
            cls._instance._deck_snapshot = {}
            cls._instance._runner_lock = threading.Lock()
            cls._instance._runner_status = None
            cls._instance._optimizers = {}
            cls._instance._notification_handlers = []

        return cls._instance

    @property
    def deck(self):
        return self._deck

    @deck.setter
    def deck(self, value):
        if self._deck is None:
            self._deck = value

    def register_notification(self, handler):
        if not callable(handler):
            raise ValueError("Handler must be callable")
        self._notification_handlers.append(handler)

    @property
    def notification_handlers(self):
        return self._notification_handlers

    @property
    def building_blocks(self):
        return self._building_blocks

    @building_blocks.setter
    def building_blocks(self, value):
        if self._building_blocks is None:
            self._building_blocks = value

    @property
    def registered_workflows(self):
        return self._registered_workflows

    @registered_workflows.setter
    def registered_workflows(self, value):
        if self._registered_workflows is None:
            self._registered_workflows = value


    @property
    def deck_snapshot(self):
        return self._deck_snapshot

    @deck_snapshot.setter
    def deck_snapshot(self, value):
        self._deck_snapshot = value


    @property
    def agent(self):
        return self._agent

    @agent.setter
    def agent(self, value):
        if self._agent is None:
            self._agent = value

    @property
    def defined_variables(self):
        return self._defined_variables

    @defined_variables.setter
    def defined_variables(self, value):
        self._defined_variables = value

    @property
    def api_variables(self):
        return self._api_variables

    @api_variables.setter
    def api_variables(self, value):
        self._api_variables = value

    @property
    def runner_lock(self):
        return self._runner_lock

    @runner_lock.setter
    def runner_lock(self, value):
        self._runner_lock = value

    @property
    def runner_status(self):
        return self._runner_status

    @runner_status.setter
    def runner_status(self, value):
        self._runner_status = value

    @property
    def optimizers(self):
        return self._optimizers

    @optimizers.setter
    def optimizers(self, value):
        if isinstance(value, dict):
            self._optimizers = value
        else:
            raise ValueError("Optimizers must be a dictionary.")