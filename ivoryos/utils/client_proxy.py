import os
import re
from typing import Dict, Set, Any, Optional


class ProxyGenerator:
    """
    A class to generate Python proxy interfaces for API clients.

    This generator creates client classes that wrap API endpoints,
    automatically handling request/response cycles and error handling.
    """

    # Common typing symbols to scan for in function signatures
    TYPING_SYMBOLS = {
        "Optional", "Union", "List", "Dict", "Tuple",
        "Any", "Callable", "Iterable", "Sequence", "Set"
    }

    def __init__(self, base_url: str, api_path_template: str = "ivoryos/instruments/deck.{class_name}"):
        """
        Initialize the ProxyGenerator.

        Args:
            base_url: The base URL for the API
            api_path_template: Template for API paths, with {class_name} placeholder
        """
        self.base_url = base_url.rstrip('/')
        self.api_path_template = api_path_template
        self.used_typing_symbols: Set[str] = set()

    def extract_typing_from_signatures(self, functions: Dict[str, Dict[str, Any]]) -> Set[str]:
        """
        Scan function signatures for typing symbols and track usage.

        Args:
            functions: Dictionary of function definitions with signatures

        Returns:
            Set of typing symbols found in the signatures
        """
        for function_data in functions.values():
            signature = function_data.get("signature", "")
            for symbol in self.TYPING_SYMBOLS:
                if re.search(rf"\b{symbol}\b", signature):
                    self.used_typing_symbols.add(symbol)
        return self.used_typing_symbols

    def create_class_definition(self, class_name: str, functions: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate a class definition string for one API client class.

        Args:
            class_name: Name of the class to generate
            functions: Dictionary of function definitions

        Returns:
            String containing the complete class definition
        """
        capitalized_name = class_name.capitalize()
        api_url = f"{self.base_url}/{self.api_path_template.format(class_name=class_name)}"

        class_template = f"class {capitalized_name}:\n"
        class_template += f'    """Auto-generated API client for {class_name} operations."""\n'
        class_template += f'    url = "{api_url}"\n\n'

        # Add the __init__ with auth
        class_template += self._generate_init()

        # Add the _auth
        class_template += self._generate_auth()

        # Add the base _call method
        class_template += self._generate_call_method()

        # Add individual methods for each function
        for function_name, details in functions.items():
            method_def = self._generate_method(function_name, details)
            class_template += method_def + "\n"

        return class_template

    def _generate_call_method(self) -> str:
        """Generate the base _call method for API communication."""
        return '''    def _call(self, payload):
        """Make API call with error handling."""
        res = session.post(self.url, json=payload, allow_redirects=False)
            # Handle 302 redirect (likely auth issue)
        if res.status_code == 302:
            try:
                self._auth()
                res = session.post(self.url, json=payload, allow_redirects=False)
            except Exception as e:
                raise AuthenticationError(
                    "Authentication failed during re-attempt. "
                    "Please check your credentials or connection."
                ) from e
        res.raise_for_status()
        data = res.json()
        if not data.get('success'):
            raise Exception(data.get('output', "Unknown API error."))
        return data.get('output')

'''

    def _generate_method(self, function_name: str, details: Dict[str, Any]) -> str:
        """
        Generate a single method definition.

        Args:
            function_name: Name of the method
            details: Function details including signature and docstring

        Returns:
            String containing the method definition
        """
        signature = details.get("signature", "(self)")
        docstring = details.get("docstring", "")

        # Build method header
        method = f"    def {function_name}{signature}:\n"

        if docstring:
            method += f'        """{docstring}"""\n'

        # Build payload
        method += f'        payload = {{"hidden_name": "{function_name}"}}\n'

        # Extract parameters from signature (excluding 'self')
        params = self._extract_parameters(signature)

        for param_name in params:
            method += f'        payload["{param_name}"] = {param_name}\n'

        method += "        return self._call(payload)\n"

        return method

    def _extract_parameters(self, signature: str) -> list:
        """
        Extract parameter names from a function signature.

        Args:
            signature: Function signature string like "(self, param1, param2: int = 5)"

        Returns:
            List of parameter names (excluding 'self')
        """
        # Remove parentheses and split by comma
        param_str = signature.strip("()").strip()
        if not param_str or param_str == "self":
            return []

        params = [param.strip() for param in param_str.split(",")]
        result = []

        for param in params:
            if param and param != "self":
                # Extract parameter name (before : or = if present)
                param_name = param.split(":")[0].split("=")[0].strip()
                if param_name:
                    result.append(param_name)

        return result

    def generate_proxy_file(self,
                            snapshot: Dict[str, Dict[str, Any]],
                            output_path: str,
                            filename: str = "generated_proxy.py") -> str:
        """
        Generate the complete proxy file from a snapshot of instruments.

        Args:
            snapshot: Dictionary containing instrument data with functions
            output_path: Directory to write the output file
            filename: Name of the output file

        Returns:
            Path to the generated file
        """
        class_definitions = {}
        self.used_typing_symbols.clear()

        # Process each instrument in the snapshot
        for instrument_key, instrument_data in snapshot.items():
            # Convert function signatures to strings if needed
            for function_key, function_data in instrument_data.items():
                if 'signature' in function_data:
                    function_data['signature'] = str(function_data['signature'])

            # Extract class name from instrument path
            class_name = instrument_key.split('.')[-1]

            # Generate class definition
            class_definitions[class_name] = self.create_class_definition(
                class_name, instrument_data
            )

            # Track typing symbols used
            self.extract_typing_from_signatures(instrument_data)

        # Write the complete file
        filepath = self._write_proxy_file(class_definitions, output_path, filename)
        return filepath

    def _write_proxy_file(self,
                          class_definitions: Dict[str, str],
                          output_path: str,
                          filename: str) -> str:
        """
        Write the generated classes to a Python file.

        Args:
            class_definitions: Dictionary of class names to class definition strings
            output_path: Directory to write the file
            filename: Name of the file

        Returns:
            Full path to the written file
        """
        filepath = os.path.join(output_path, filename)

        with open(filepath, "w") as f:
            # Write imports
            f.write("import requests\n")
            if self.used_typing_symbols:
                f.write(f"from typing import {', '.join(sorted(self.used_typing_symbols))}\n")
            f.write("\n")

            # Write session setup
            f.write("session = requests.Session()\n\n")

            # Write class definitions
            for class_name, class_def in class_definitions.items():
                f.write(class_def)
                f.write("\n")

            # Create default instances
            f.write("# Default instances for convenience\n")
            for class_name in class_definitions.keys():
                instance_name = class_name.lower()
                f.write(f"{instance_name} = {class_name.capitalize()}()\n")

        return filepath

    def generate_from_flask_route(self,
                                  snapshot: Dict[str, Dict[str, Any]],
                                  request_url_root: str,
                                  output_folder: str) -> str:
        """
        Convenience method that matches the original Flask route behavior.

        Args:
            snapshot: The deck snapshot from global_config
            request_url_root: The URL root from Flask request
            output_folder: Output folder path from app config

        Returns:
            Path to the generated file
        """
        # Set the base URL from the request
        self.base_url = request_url_root.rstrip('/')

        # Generate the proxy file
        return self.generate_proxy_file(snapshot, output_folder)

    def _generate_init(self):
        return '''    def __init__(self, username=None, password=None):
        """Initialize the client with authentication."""
        self.username = username
        self.password = password
        self._auth()

'''


    def _generate_auth(self):
        return f"""    def _auth(self):
        username = self.username or 'admin'
        password = self.password or 'admin'
        res = session.get('{self.base_url}/ivoryos/', allow_redirects=False)
        if res.status_code == 200:
            return
        else:
            session.post(
                '{self.base_url}/ivoryos/auth/login',
                data={{"username": username, "password": password}}
            )
            res = session.get('{self.base_url}/ivoryos/', allow_redirects=False)
            if res.status_code != 200:
                raise Exception("Authentication failed")
                    
"""
