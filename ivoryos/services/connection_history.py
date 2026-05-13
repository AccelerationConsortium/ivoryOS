import os

def save_to_history(filepath, history_path):
    """
    For manual deck connection only
    save deck file path that successfully connected to ivoryos to a history file
    """
    connections = []
    try:
        with open(history_path, 'r') as file:
            lines = file.read()
            connections = lines.split('\n')
    except FileNotFoundError:
        pass
    if filepath not in connections:
        with open(history_path, 'a') as file:
            file.writelines(f"{filepath}\n")


def import_history(history_path):
    """
    For manual deck connection only
    load deck connection history from history file
    """
    connections = []
    try:
        with open(history_path, 'r') as file:
            lines = file.read()
            connections = lines.split('\n')
    except FileNotFoundError:
        pass
    connections = [i for i in connections if not i == '']
    return connections


def available_pseudo_deck(path):
    """
    load interface schema from connection history
    """
    return os.listdir(path)
