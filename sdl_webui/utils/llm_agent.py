import inspect
import json
import os
import re

import ollama


UPDATE_DOCSTRING = True
STREAM = False
USE_VOICE = False
host = "137.82.65.246"
model = "llama3"




def extract_annotations_docstrings(cls):
    extracted_methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if not name.startswith('_'):
            annotation = inspect.signature(method).return_annotation
            docstring = inspect.getdoc(method)
            extracted_methods.append((name, annotation, docstring))
    method_name = [t[0] for t in extracted_methods]
    variables = [(key, value) for key, value in vars(cls).items() if not key.startswith("_") and not key in method_name]
    class_str = ""
    # class_str = f"class {cls.__name__}:\n"
    # class_str += f'\t"""{inspect.getdoc(cls)}"""\n\n'
    for key, value in variables:
        class_str += f'\t{key}={value}\n'
    for name, annotation, docstring in extracted_methods:
        class_str += f'\tdef {name}{inspect.signature(getattr(cls, name))}:\n'
        class_str += f'\t\t"""\n{docstring}\n"""' + '\n\n' if docstring else ''
    class_str = class_str.replace('self, ', '')
    class_str = class_str.replace('self', '')
    # print(class_str)
    # with open("../../example/docstring_manual.txt", "w") as f:
    #     f.write(class_str)

    return class_str


def save_stream(stream):
    write = False
    with open("../../example/test.py", "w") as f:
        for chunk in stream:
            if "``" in chunk['message']['content']:
                write = not write
                f.write("#")
            if write:
                f.write(chunk['message']['content'])
            else:
                print(chunk['message']['content'], end='', flush=True)


def parse_code_from_msg(msg):
    msg = msg.strip()
    # print(msg)
    code_blocks = re.findall(r'```(?:json\s)?(.*?)```', msg, re.DOTALL)

    json_blocks = []
    for block in code_blocks:
        try:
            # Try to parse the block as JSON
            json_data = json.loads(block.strip())
            if isinstance(json_data, list):
                print(isinstance(json_data, list))
                json_blocks = json_data
        except json.JSONDecodeError:
            continue
    return json_blocks

def exec_code(code):
    os.system(f'python {code}')


def start_gpt(robot, prompt):
    # deck_info = update_docstring_file(deck_path)
    ollama_client = ollama.Client(host=host)

    deck_info = extract_annotations_docstrings(type(robot))
    prompt = '''
                    I have some python functions, for example when calling them I want to write them using JSON, for example
                    def dose_solid(amount_in_mg:float, bring_in:bool=True): def analyze():
                    dose_solid(3)
                    analyze()
                    I would want to write to
                    [
                    {
                        "action": "dose_solid",
                        "arg_types": {
                            "amount_in_mg": "float",
                            "bring_in": "bool"
                        },
                        "args": {
                            "amount_in_mg": 3,
                            "bring_in": True
                        },
                    },
                    {
                        "action": "analyze",
                        "arg_types": {},
                        "args": {}
                    }
                    ]

                    '''+f'''
                    Now these are my callable functions,
                    {deck_info}

                    and I want you to find the most appropriate function if I want to do these tasks
                    """{prompt}"""
                    ,and write a list of dictionary in json accordingly. Please do not use other function names than the listed above.
                    '''
    # with open("../../example/prompt.txt", "w") as f:
    #     f.write(prompt)
    output = ollama_client.chat(
        model=model,
        messages=[{'role': 'user',
                   'content': prompt}],
        stream=False,
    )
    msg = output['message']['content']
    print(msg)

    code = parse_code_from_msg(msg)
    print('\033[91m', code, '\033[0m')
    return code


if __name__ == "__main__":
    from example.dummy_deck import DummySDLDeck, sdl
    # robot = IrohDeck()
    # extract_annotations_docstrings(DummySDLDeck)
    prompt = '''I want to start with dosing 10 mg of current sample, and add 1 mL of toluene 
    and equilibrate for 10 minute at 40 degrees, then sample 20 ul of sample to analyze with hplc, and save result'''
    start_gpt(sdl, None, prompt)

"""
I want to dose 10mg, 6mg, 4mg, 3mg, 2mg, 1mg to 6 vials
I want to add 10 mg to vial a3, and 10 ml of liquid, then shake them for 3 minutes

"""
