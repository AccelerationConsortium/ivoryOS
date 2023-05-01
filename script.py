import json
import uuid
from datetime import datetime

from flask import jsonify
from flask_login import UserMixin
# from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import JSONType

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    # id = db.Column(db.Integer)
    username = db.Column(db.String, primary_key=True, unique=True, nullable=False)
    # email = db.Column(db.String)
    hashPassword = db.Column(db.String)

    # password = db.Column()
    def __init__(self, username, password):
        # self.id = id
        self.username = username
        # self.email = email
        self.hashPassword = password

    def get_id(self):
        return self.username

# ma = Marshmallow()
#
# class ScriptSchema(ma.Schema):
#     class Meta:
#         fields = ('id','title','url','longitude','latitude')
#
# script_schema = ScriptSchema()
# scripts_schema = ScriptSchema(many=True)


class Script(db.Model):
    # id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), primary_key=True, unique=True)
    deck = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(100), nullable=True)
    script_dict = db.Column(JSONType, nullable=True)
    time_created = db.Column(db.String(100), nullable=True)
    last_modified = db.Column(db.String(100), nullable=True)
    id_order = db.Column(JSONType, nullable=True)
    editing_type = db.Column(db.String(100), nullable=True)
    author = db.Column(db.String(100), nullable=True)

    def __init__(self, name=None, deck=None, status=None, script_dict: dict = None, id_order: dict = None,
                 time_created=None, last_modified=None, editing_type=None, author: str = None):
        if script_dict is None:
            script_dict = {"prep": [], "script": [], "cleanup": []}
        elif type(script_dict) is not dict:
            script_dict = json.loads(script_dict)
        if id_order is None:
            id_order = {"prep": [], "script": [], "cleanup": []}
        elif type(id_order) is not dict:
            id_order = json.loads(id_order)
        if status is None:
            status = 'editing'
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
        self.author = author

    def as_dict(self):
        dict = self.__dict__
        dict.pop('_sa_instance_state', None)
        return dict


    def get(self):
        workflows = db.session.query(Script).all()
        # result = script_schema.dump(workflows)
        return workflows
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
        if not (self.script_dict['script'] or self.script_dict['prep'] or self.script_dict['cleanup']):
            return True
        return False

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
                    {"id": current_len + 1, "instrument": 'if', "action": 'if', "args": 'True' if args == '' else args, "return": '', "uuid": uid},
                    {"id": current_len + 2, "instrument": 'if', "action": 'else', "args": '', "return": '', "uuid": uid},
                    {"id": current_len + 3, "instrument": 'if', "action": 'endif', "args": '', "return": '', "uuid": uid},
                ],
            "while":
                [
                    {"id": current_len + 1, "instrument": 'while', "action": 'while', "args": 'False' if args == '' else args, "return": '', "uuid": uid},
                    {"id": current_len + 2, "instrument": 'while', "action": 'endwhile', "args": '', "return": '', "uuid": uid},
                ],
            "variable":
                [
                    {"id": current_len + 1, "instrument": 'variable', "action": var_name, "args": 'None' if args == '' else args, "return": '', "uuid": uid},
                ],
            "wait":
                [
                    {"id": current_len + 1, "instrument": 'wait', "action": "wait", "args": '0' if args == '' else args, "return": '', "uuid": uid},
                ],
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

    def indent(self, unit=0):
        string = "\n"
        for _ in range(unit):
            string += "\t"
        return string

    def compile(self):
        """
        compile the current script to python file
        :return: Boolean, whether the compile is successful
        """
        self.sort_actions()
        run_name = self.name if self.name else "untitled"
        with open("scripts/" + run_name + ".py", "w") as s:

            if self.deck:
                s.write("import " + self.deck + " as deck")
            else:
                s.write("deck = None")
            s.write("\nimport time")
            exec_string = ''
            for i in self.stypes:
                indent_unit = 1
                exec_string += "\n\ndef " + run_name + "_" + i + "("
                configure = self.config()
                if i == "script":
                    for j in configure:
                        exec_string = exec_string + j + ","
                exec_string = exec_string + "):"
                exec_string = exec_string + self.indent(indent_unit) + "global " + run_name + "_" + i
                for index, action in enumerate(self.script_dict[i]):
                    instrument = action['instrument']
                    args = action['args']
                    save_data = action['return']
                    action = action['action']
                    next_ = None
                    if instrument == 'if':
                        if index < (len(self.script_dict[i]) - 1):
                            next_ = self.script_dict[i][index + 1]
                        if action == 'if':
                            exec_string = exec_string + self.indent(indent_unit) + "if " + args + ":"
                            indent_unit += 1
                            if next_ and next_['instrument'] == 'if':
                                exec_string = exec_string + self.indent(indent_unit) + "pass"
                        elif action == 'else':
                            exec_string = exec_string + self.indent(indent_unit - 1) + "else:"
                            if next_['instrument'] == 'if' and next_['action'] == 'endif':
                                exec_string = exec_string + self.indent(indent_unit) + "pass"
                        else:
                            indent_unit -= 1
                    elif instrument == 'while':
                        if index < (len(self.script_dict[i]) - 1):
                            next_ = self.script_dict[i][index + 1]
                        if action == 'while':
                            exec_string = exec_string + self.indent(indent_unit) + "while " + args + ":"
                            indent_unit += 1
                            if next_ and next_['instrument'] == 'while':
                                exec_string = exec_string + self.indent(indent_unit) + "pass"
                            # else:
                            #     indent = "\t"
                        elif action == 'endwhile':
                            indent_unit -= 1
                    elif instrument == 'variable':
                        # args = "False" if args == '' else args
                        if not args.startswith("#"):
                            exec_string = exec_string + self.indent(indent_unit) + action + " = " + args
                    elif instrument == 'wait':
                        # args = "False" if args == '' else args
                        exec_string = exec_string + self.indent(indent_unit) + "time.sleep(" + args + ")"
                    else:
                        if args:
                            if type(args) is dict:
                                temp = args.__str__()
                                for arg in args:
                                    if type(args[arg]) is str and args[arg].startswith("#"):
                                        temp = temp.replace("'#" + args[arg][1:] + "'", args[arg][1:])
                                single_line = instrument + "." + action + "(**" + temp + ")"
                            else:
                                if type(args) is str and args.startswith("#"):
                                    args = args.replace("'#" + args[1:] + "'", args[1:])
                                single_line = instrument + "." + action + " = " + str(args)
                        else:
                            single_line = instrument + "." + action + "()"
                        if save_data == '':
                            exec_string = exec_string + self.indent(indent_unit) + single_line
                        else:
                            exec_string = exec_string + self.indent(indent_unit) + save_data + " = " + single_line
                return_str, return_list = self.config_return()
                if len(return_list) > 0 and i == "script":
                    exec_string += self.indent(indent_unit) + return_str
            # try:
            #
            #     # exec(exec_string)
            #
            #     # print(exec_string)
            # except Exception:
            #     return ""
            s.write(exec_string)
            # try:
            #
            #     exec(exec_string)
            #
            #     # print(exec_string)
            # except Exception:
            #     return ""
        return exec_string

if __name__ == "__main__":
    a = Script()

    print("")