import os
import re
import inspect
from enum import Enum
from typing import Dict, Set, Any, Optional, Type, Union


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
        self.collected_enums: Dict[str, Type[Enum]] = {}

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
                if re.search(rf"\b{symbol}\b", str(signature)):
                    self.used_typing_symbols.add(symbol)
        return self.used_typing_symbols

    def _collect_types_from_signature(self, signature: inspect.Signature):
        """
        Recursively find Enum types in a signature and add to collected_enums.
        """
        if not signature or isinstance(signature, str):
            return

        for param in signature.parameters.values():
            self._collect_types_from_annotation(param.annotation)

        if signature.return_annotation is not inspect.Signature.empty:
            self._collect_types_from_annotation(signature.return_annotation)

    def _collect_types_from_annotation(self, annotation):
        """Helper to check an annotation for Enums."""
        if annotation is inspect.Parameter.empty:
            return

        # Check if it's an Enum
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            self.collected_enums[annotation.__name__] = annotation
            return

        # Check for composite types (Union, Optional, List, etc.)
        if hasattr(annotation, "__args__"):
            for arg in annotation.__args__:
                self._collect_types_from_annotation(arg)

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
        str_signature = str(signature) if signature else "(self)"
        
        # Clean up the signature string
        # Remove __main__. prefix from types
        str_signature = str_signature.replace("__main__.", "")
        
        # Also clean up any other module prefixes for collected enums (optional, but good practice)
        for enum_name in self.collected_enums:
             # This regex matches "somemodule.EnumName" but not just "EnumName"
             # It's a bit risky if EnumName is common, but sufficient for now.
             # Actually, simple string replacement for module paths found in the enum might be better if we tracked them.
             # For now, just handling __main__ is the primary request.
             pass

        docstring = details.get("docstring", "")

        # Build method header
        method = f"    def {function_name}{str_signature}:\n"

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

    def _write_enum_definitions(self, f):
        """Write generated Enum classes to the file."""
        if not self.collected_enums:
            return

        f.write("# Generated Enum definitions\n")
        f.write("from enum import Enum\n\n")
        
        for name, enum_cls in self.collected_enums.items():
            f.write(f"class {name}(Enum):\n")
            for member in enum_cls:
                # Handle value types (str or int)
                value = member.value
                if isinstance(value, str):
                    f.write(f"    {member.name} = \"{value}\"\n")
                else:
                    f.write(f"    {member.name} = {value}\n")
            f.write("\n")

    def _extract_parameters(self, signature: Union[str, inspect.Signature]) -> list:
        """
        Extract parameter names from a function signature.

        Args:
            signature: Function signature string or inspect.Signature object

        Returns:
            List of parameter names (excluding 'self')
        """
        if isinstance(signature, inspect.Signature):
            return [name for name in signature.parameters.keys() if name != 'self']

        # Remove parentheses and split by comma
        param_str = str(signature).strip("()").strip()
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
        self.collected_enums.clear()

        # First pass: collect all types and Enums
        for instrument_key, instrument_data in snapshot.items():
            for function_key, function_data in instrument_data.items():
                sig = function_data.get('signature')
                if isinstance(sig, inspect.Signature):
                   self._collect_types_from_signature(sig)

        # Process each instrument in the snapshot
        for instrument_key, instrument_data in snapshot.items():
            # Convert function signatures to strings if needed
            for function_key, function_data in instrument_data.items():
                if 'signature' in function_data:
                     # We keep the object for now to allow _generate_method to use string conversion late
                     pass

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

            # Write Enum definitions
            self._write_enum_definitions(f)

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
