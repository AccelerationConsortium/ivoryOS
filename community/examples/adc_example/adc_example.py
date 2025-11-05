"""
ADC Automation
Platform Developers: Liam Roberts. All rights reserved.
"""

from adc_automation.adc_deck import AdcDeck
# https://gitlab.com/heingroup/adc_automation/-/blob/main/adc_deck.py

import ivoryos


class AdcExample(AdcDeck):
    def initial_conditions_ivoryos(self, desired_dar: float, ab_molecular_weight: float, ab_concentration: float,
                                   ab_amount: float, reduction_concentration: float, dl_concentration: float,
                                   tcep_concentration: float, tcep_eq_initial: float):
        """
        Initial conditions: original code used input in command line to prompt user for those input
        this modified code is based on the original code from https://gitlab.com/heingroup/adc_automation/-/blob/main/adc_deck.py
        changing the initial input() to parameter inputs

        :param desired_dar: the desired DAR value
        :param ab_molecular_weight: the antibody molecular weight
        :param ab_concentration: the antibody concentration
        :param ab_amount: the antibody amount
        :param reduction_concentration: the reduction agent concentration
        :param dl_concentration: the drug linker concentration
        :param tcep_concentration: the TCEP concentration
        :param tcep_eq_initial: the initial TCEP equivalence
        """
        self.desired_dar = desired_dar
        self.ab_molecular_weight = ab_molecular_weight
        self.ab_concentration = ab_concentration
        self.ab_amount = ab_amount
        self.reduction_concentration = reduction_concentration
        self.dl_concentration = dl_concentration
        self.tcep_concentration = tcep_concentration
        self.tcep_eq_initial = tcep_eq_initial
        self.initial_reagent_volume_calculations()


if __name__ == "__main__":
    hplc_dir = r"D:\Chemstation\1\Data\2024-04-25_dar_analysis"
    wavelength_ab = 248
    wavelength_dl = 280

    adc_example = AdcExample(hplc_dir=hplc_dir, wavelength_ab=wavelength_ab, wavelength_dl=wavelength_dl)

    ivoryos.run(__name__)
