from datetime import datetime
import uuid

class Script:
    def __init__(self, name=None, deck=None, status='editing', script_dict: dict = None, id_order: dict = None,
                 time_created=None, last_modified=None, editing_type=None):
        if script_dict is None:
            script_dict = {"prep": [], "script": [], "cleanup": []}
        if id_order is None:
            id_order = {"prep": [], "script": [], "cleanup": []}
        if time_created is None:
            time_created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if last_modified is None:
            last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if editing_type is None:
            editing_type = "script"
        self.name = name
        self.deck = deck
        self.status = status
        self.script_dict = script_dict
        self.time_created = time_created
        self.last_modified = last_modified
        self.id_order = id_order
        self.editing_type = editing_type

    @property
    def stypes(self):
        return list(self.script_dict.keys())

    @property
    def currently_editing_script(self):
        return self.script_dict[self.editing_type]

    @currently_editing_script.setter
    def currently_editing_script(self, script):
        self.script_dict[self.editing_type] = script

    @property
    def currently_editing_order(self):
        return self.id_order[self.editing_type]

    @currently_editing_order.setter
    def currently_editing_order(self, script):
        self.id_order[self.editing_type] = script

    # @property
    # def editing_type(self):
    #     return self.editing_type

    # @editing_type.setter
    # def editing_type(self, change_type):
    #     self.editing_type = change_type

    def update_time_stamp(self):
        self.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_script(self, stype: str):
        return self.script_dict[stype]

    def isEmpty(self) -> bool:
        return not (self.script_dict['script'] and self.script_dict['prep'] and self.script_dict['cleanup'])

    def _sort(self, script_type):
        if len(self.id_order[script_type]) > 0:
            for action in self.script_dict[script_type]:
                for i in range(len(self.id_order[script_type])):
                    if action['id'] == int(self.id_order[script_type][i]):
                        # print(i+1)
                        action['id'] = i + 1
                        break
            self.id_order[script_type].sort()
            if not int(self.id_order[script_type][-1]) == len(self.script_dict[script_type]):
                new_order = list(range(1, len(self.script_dict[script_type]) + 1))
                self.id_order[script_type] = [str(i) for i in new_order]
            self.script_dict[script_type].sort(key=lambda x: x['id'])

    def sort_actions(self, script_type=None):
        if script_type:
            self._sort(script_type)
        else:
            for i in self.stypes:
                self._sort(i)

    def add_action(self, action: dict):
        current_len = len(self.currently_editing_script)
        action['id'] = current_len + 1
        action['uuid'] = uuid.uuid4().fields[-1]
        self.currently_editing_script.append(action)
        self.currently_editing_order.append(str(current_len + 1))
        self.update_time_stamp()

    def add_logic_action(self, logic_type: str, args, var_name=None):
        current_len = len(self.currently_editing_script)
        uid = uuid.uuid4().fields[-1]
        logic_dict = {
            "if":
                [
                    {"id": current_len + 1, "instrument": 'if', "action": 'if', "args": args, "return": '', "uuid": uid},
                    {"id": current_len + 2, "instrument": 'if', "action": 'else', "args": '', "return": '', "uuid": uid},
                    {"id": current_len + 3, "instrument": 'if', "action": 'endif', "args": '', "return": '', "uuid": uid},
                ],
            "while":
                [
                    {"id": current_len + 1, "instrument": 'while', "action": 'while', "args": args, "return": '', "uuid": uid},
                   {"id": current_len + 2, "instrument": 'while', "action": 'endwhile', "args": '', "return": '', "uuid": uid},
                ],
            "variable":
                [
                    {"id": current_len + 1, "instrument": 'variable', "action": var_name, "args": args, "return": '', "uuid": uid},
                ]
        }
        action_list = logic_dict[logic_type]
        self.currently_editing_script.extend(action_list)
        self.currently_editing_order.extend([str(current_len + i + 1) for i in range(len(action_list))])
        self.update_time_stamp()

    def delete_action(self, id: int):
        uid = next((action['uuid'] for action in self.currently_editing_script if action['id'] == int(id)), None)
        id_to_be_removed = [action['id'] for action in self.currently_editing_script if action['uuid'] == uid]
        order = self.currently_editing_order
        script = self.currently_editing_script
        self.currently_editing_order = [i for i in order if int(i) not in id_to_be_removed]
        self.currently_editing_script = [action for action in script if action['id'] not in id_to_be_removed]
        self.update_time_stamp()

    def config(self):
        """
        take the global script_dict
        :return: list of variable that require input
        """
        configure = []
        for action in self.script_dict['script']:
            args = action['args']
            if args is not None:
                if type(args) is not dict:
                    if type(args) is str and args.startswith("#") and not args[1:] in configure:
                        configure.append(args[1:])
                else:
                    for arg in args:
                        if type(args[arg]) is str \
                                and args[arg].startswith("#") \
                                and not args[arg][1:] in configure:
                            configure.append(args[arg][1:])
        return configure

    def config_return(self):
        """
        take the global script_dict
        :return: list of variable that require input
        """
        return_list = [action['return'] for action in self.script_dict['script'] if not action['return'] == '']
        output_str = "return {"
        for i in return_list:
            output_str += "'" + i + "':" + i + ","
        output_str += "}"
        return output_str, return_list

    def finalize(self):
        self.status = "finalized"
        self.update_time_stamp()

    def save_as(self, name):
        self.name = name
        self.status = "editing"
        self.update_time_stamp()



if __name__ == "__main__":
    a = Script()

    print("")