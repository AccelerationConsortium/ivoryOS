deck = None
import time

def untitled_cleanup():
	global untitled_cleanup

def untitled_prep():
	global untitled_prep

def untitled_script():
	global untitled_script
	num = 1
	my_str = "str"
	my_bool = True
	test = 12
	deck.sdl.dilute(**{'factor': test, 'solvent': my_str})
	deck.sdl.dilute(**{'factor': test, 'solvent': '"another str"'})
	deck.sdl.dilute(**{'factor': 2.0, 'solvent': '"another str"'})
	deck.sdl.dose_solvent(**{'amount_in_ml': 5.0, 'name': my_str, 'rate_ml_per_minute': test})
	deck.sdl.dose_solvent(**{'amount_in_ml': test, 'name': my_str, 'rate_ml_per_minute': num})