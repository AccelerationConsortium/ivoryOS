# from ivoryos.utils.script_runner import ScriptRunner


class GlobalConfig:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GlobalConfig, cls).__new__(cls, *args, **kwargs)
            cls._instance._deck = None
            cls._instance._agent = None
            cls._instance._defined_variables = {}
            cls._instance._api_variables = set()
            # cls._instance._task_manager = ScriptRunner()
        return cls._instance

    @property
    def deck(self):
        return self._deck

    @deck.setter
    def deck(self, value):
        if self._deck is None:
            self._deck = value

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
    def task_manager(self):
        return self._task_manager

    @task_manager.setter
    def task_manager(self, value):
        self.task_manager = value