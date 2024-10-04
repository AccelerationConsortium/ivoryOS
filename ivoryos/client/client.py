import inspect
import requests

session = requests.Session()


# Function to create class and methods dynamically
def create_function(url, class_name, functions):
    class_template = f'class {class_name.capitalize()}:\n    url = "{url}/backend_control/deck.{class_name}"\n'

    for function_name, details in functions.items():
        signature = details['signature']
        docstring = details.get('docstring', '')

        # Creating the function definition
        method = f'    def {function_name}{signature}:\n'
        if docstring:
            method += f'        """{docstring}"""\n'

        # Generating the session.post code for sending data
        method += '        session.post(self.url, data={'
        method += f'"hidden_name": "{function_name}"'

        # Extracting the parameters from the signature string for the data payload
        param_str = signature[6:-1]  # Remove the "(self" and final ")"
        params = [param.strip() for param in param_str.split(',')] if param_str else []

        for param in params:
            param_name = param.split(':')[0].strip()  # Split on ':' and get parameter name
            method += f', "{param_name}": {param_name}'

        method += '})\n'
        class_template += method + '\n'

    return class_template


# Function to export the generated classes to a Python script
def export_to_python(class_definitions):
    with open('generated_classes.py', 'w') as f:
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

def generate_proxy_script(url):
    snapshot = session.get(f"{url}/backend_client").json()
    class_definitions = {}
    for class_path, functions in snapshot.items():
        class_name = class_path.split('.')[-1]  # Extracting the class name from the path
        class_definitions[class_name.capitalize()] = create_function(url, class_name, functions)

    # Export the generated class definitions to a .py script
    export_to_python(class_definitions)

# Example input method_dict with string signatures
# Generate the classes dynamically

url = 'http://localhost:8000'


generate_proxy_script(url)
# sdl.url = 'http://example.com/api'
# sdl.analyze()
# sdl.dose_solid(10, True)
