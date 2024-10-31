import abstract_sdl as deck
import time

def example_cleanup():
	global example_cleanup

def example_prep():
	global example_prep

def example_script(amount,rate,solvent):
	global example_script
	mass = deck.sdl.dose_solid(**{'amount_in_mg': amount, 'bring_in': True})
	deck.sdl.dose_solvent(**{'amount_in_ml': rate, 'rate_ml_per_minute': '1', 'solvent_name': solvent})
	deck.sdl.analyze(**{})
	return {'mass':mass,}