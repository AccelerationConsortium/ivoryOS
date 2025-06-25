# import argparse
import os

# import requests

# session = requests.Session()


# Function to create class and methods dynamically
def create_function(url, class_name, functions):
    class_template = f'class {class_name.capitalize()}:\n    url = "{url}ivoryos/api/control/deck.{class_name}"\n'

    for function_name, details in functions.items():
        signature = details['signature']
        docstring = details.get('docstring', '')

        # Creating the function definition
        method = f'    def {function_name}{signature}:\n'
        if docstring:
            method += f'        """{docstring}"""\n'

        # Generating the session.post code for sending data
        method += '        return session.post(self.url, data={'
        method += f'"hidden_name": "{function_name}"'

        # Extracting the parameters from the signature string for the data payload
        param_str = signature[6:-1]  # Remove the "(self" and final ")"
        params = [param.strip() for param in param_str.split(',')] if param_str else []

        for param in params:
            param_name = param.split(':')[0].strip()  # Split on ':' and get parameter name
            method += f', "{param_name}": {param_name}'

        method += '}).json()\n'
        class_template += method + '\n'

    return class_template

# Function to export the generated classes to a Python script
def export_to_python(class_definitions, path):
    with open(os.path.join(path, "generated_proxy.py"), 'w') as f:
        # Writing the imports at the top of the script
        f.write('import requests\n\n')
        f.write('session = requests.Session()\n\n')

        # Writing each class definition to the file
        for class_name, class_def in class_definitions.items():
            f.write(class_def)
            f.write('\n')

        # Creating instances of the dynamically generated classes
        for class_name in class_definitions.keys():
            instance_name = class_name.lower()  # Using lowercase for instance names
            f.write(f'{instance_name} = {class_name.capitalize()}()\n')



