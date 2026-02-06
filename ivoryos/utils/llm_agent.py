import os
import json
from openai import OpenAI
import re

class LlmAgent:
    def __init__(self, base_url, model, output_path=None):
        self.base_url = base_url
        self.model = model
        if output_path is not None:
            self.output_path = os.path.join(output_path, "llm_output")
            os.makedirs(self.output_path, exist_ok=True)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", None), base_url=self.base_url)
        self.system_prompt = "You are IvoryOS, a scientific experiment planner for automated/self-drving laboratories. You have access to the current deck configuration which lists all available instruments, their possible actions, and required arguments. Convert natural language lab instructions into a precise json sequence of action calls using this information. Only return a valid json and stay true to the output format."

    def generate_design(self, user_request: str, deck_info: dict) -> list:
        """
        Converts natural language instructions into a structured sequence of action calls.

        Args:
            user_request (str): The natural language description of the experiment or task.
            deck_info (dict): A dictionary mapping available instruments to their actions, args, arg-types.
                This is injected into the prompt as context.

        Returns:
            list[dict]: The parsed experimental design containing a list of action calls.
        """
        full_prompt = f'''**Create a list of instrument actions based on the following user request:** "{user_request}"

### Deck Information
```
{json.dumps(deck_info, indent=4)}
```

### Rules
1. Completeness: All arguments must be included in the action call with their correct `arg_type`
2. Explicit Values First: If the user specifies a literal value, use it directly.
3. Variable Handling: Only variables when the user explicitly directs to do so (e.g., "use variable X"). Format variables as `#descriptive_name`.
4. Defaults & Omissions: If an argument isn't mentioned and has a `default_value` in the deck config, use the default value, if it exists.
5. Missing Arguments: If an argument has no default value and was not mentioned in the user request, create a placeholder `#argument_name` for <value>.

### Output Format: Output only the valid JSON without any comments or introduction and exactly as defined below. 
```
[
    {{  
        "action": "<action_name>",
        "instrument": "<instrument_name>",
        "args": {{
            "<arg_name>": <value>,
            ...
        }}
    }},
    ...
]
```
'''
        self._write_to_file(filename = "full_prompt.md", content = full_prompt) 
        
        # generate action list
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": full_prompt}
        ]
        output = self.client.chat.completions.create(
                messages=messages,
                model=self.model
            )
        out_raw = output.choices[0].message.content
        
        # validate action list
        valid_action_list = self._check_LLM_output(output=out_raw, deck_info=deck_info)
        
        self._write_to_file(filename = "llm_response.json", content = json.dumps(valid_action_list, indent=4))
        return valid_action_list


    def _check_LLM_output(self, output: str, deck_info: dict, skip_incorrect_actions: bool = True):
        """
        Parses and validates the LLM output against the deck configuration.

        Args:
            output (str): The raw string response from the LLM.
            deck_info (dict): The dictionary containing valid instruments, actions, and argument specs.
            skip_incorrect_actions (bool, defaults: True): If TRUE, semantical incorrect action are simply removed from the 
                action list. If FALSE, an execption is raised and the design process is aborted.
            
        Returns:
            action_list (list[dict]): A list of validated action dictionaries.

        Raises:
            TypeError: If the output is not valid JSON.
            ValueError: If instruments, actions, or arguments are invalid or missing.
        """
        try:
            action_list = self._find_valid_json_list(text=output)
        except Exception as e:
            self._write_to_file(filename = "llm_response-failed.txt", content = output)
            raise TypeError(f"The agent failed to generate a syntactically correct action list. ({e}). See last output at 'llm_response-failed.txt'.")
        
        # iterate through syntactically correct action list
        deck_instruments = tuple(deck_info.keys())
        for i, action in enumerate(action_list):
            try:            
                # check that generated action contains all neccessary keys
                if tuple(action.keys()) != ("action", "instrument", "args"):
                    self._write_to_file(filename = "llm_response-failed.json", content = json.dumps(action_list, indent=4))
                    raise ValueError(f"The necessary keys ('action'(-id), 'instrument', 'args') could be generated for action {i+1}.")
                
                action_name = action["action"]
                action_instrument = action["instrument"]
                action_args = action["args"]

                # check for valid instrument
                if action_instrument not in deck_instruments: 
                    self._write_to_file(filename = "llm_response-failed.json", content = json.dumps(action_list, indent=4))
                    raise ValueError(f"The generated instrument name ('{action_instrument}') in action {i+1} was not found in the current deck configuration.")
                
                # check for valid function/action identifier
                if action_name not in deck_info[action_instrument]["actions"]:
                    self._write_to_file(filename = "llm_response-failed.json", content = json.dumps(action_list, indent=4))
                    raise ValueError(f"The generated function name ('{action_name}' for instrument '{action_instrument}') of action {i+1} could not be found in the current deck configuration.")
                
                # check if generated arguments match with those of the deck info 
                # TODO: add type verification - would be probably benefit from a Pydantic implementation in IvoryOS
                deck_arguments = deck_info[action_instrument]["actions"][action_name]["args"]
                if action_args.keys() != deck_arguments.keys():    
                    self._write_to_file(filename = "llm_response-failed.json", content = json.dumps(action_list, indent=4))         
                    raise ValueError(f"The generated arguments {tuple(action_args.keys())} do not match the arguments found for {action_instrument}.{action_name} in current deck configuration {tuple(deck_arguments.keys())}.")
            except Exception as e:
                if skip_incorrect_actions:
                    action_list.pop(i)
                    continue
                else:
                    raise Exception(f"{e}")

        return action_list
    
    def _find_valid_json_list(self, text: str) -> list:
        """
        Extracts a dictionary list from an arbitrary string object. Looks for the first valid JSON by searching for the start pattern `[{` and 
        iterating through all valid JSON list[dict] endings `}]` until one could be validated. Most of the time the first match is a valid JSON.

        Args:
            text (str): The input text that may contain embedded JSON structures.

        Raises:
            Exception: If no valid JSON object can be extracted from the text.

        Returns:
            list: The first valid JSON object found in the text.
        """
        start_pattern = r'\[\s*\{.*'
        start_match = re.search(start_pattern, text, re.DOTALL)
        if not start_match:
            raise Exception("No potential JSON structure found in the text.")
            
        end_pattern = r'.*?\}\s*\]'
        match_list = re.findall(end_pattern, start_match[0], re.DOTALL)
        data = None
        for i, match in enumerate(match_list):
            raw_str = "".join(match_list[:i+1])
            try:
                data = json.loads(raw_str)
                break
            except Exception:
                continue
        
        if data is None:
            raise Exception("No valid JSON object could be extracted from the text.")
        else:
            return data


    def _write_to_file(self, filename: str, content: str):
        if self.output_path is not None:
            with open(os.path.join(self.output_path, filename), "w") as f:
                f.write(content)