#!/usr/bin/env python3

import logging
import logging.config
import os

# if a logging.conf exists use it, if not turn logging off
if os.path.exists('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    logging.basicConfig(level=logging.CRITICAL)

# config logger for this script
logger = logging.getLogger('root')

from ma_income_tax_calc import MAIncomeTaxCalculator
import utils
from us_income_tax_calc import USIncomeTaxCalculator



# TODO: move scenarios to files and pass in file name
# example scenario structure 
# - use +/- at the beginning of strings to add/subtract the value to the base case values in the inputs file
# - if no +/- then the value replaces the base case value in the inputs file
INPUTS_FILE = 'test/test.dat'    # base case
SCENARIOS = [
                 {'Description': 'Base Case         [  0/  0/  0]', 'income_other' : '+000000', 'cg_short_term': '+000000', 'cg_long_term': '000000' },
                 {'Description': 'Agg Inc + LTCG    [  0/360/250]', 'income_other' : '+000000', 'cg_short_term': '360000', 'cg_long_term': '250000' },
                 {'Description': 'Agg Inc + blend   [100/360/150]', 'income_other' : '+100000', 'cg_short_term': '360000', 'cg_long_term': '150000' },
            ]   



def dump_ma_tax_calc_results(data):
    print(f"MA:  {data.ma_income_tax:>10,.0f} {data.taxable_income:>10,.0f} [{data.ordinary_tax:>10,.0f} {data.stcg_tax:>10,.0f} {data.ltcg_tax:>10,.0f}] [{data.ma_income_tax/data.taxable_income*100:>6.2f}%]")

def dump_us_tax_calc_results(data):
    print(f"FED: {data.total_federal_tax:>10,.0f} {data.taxable_income:>10,.0f} [{data.ordinary_tax:>10,.0f} {data.ltcg_tax:>10,.0f} {data.niit_tax:>10,.0f}] [{data.effective_tax_rate:>6.2f}% {data.marginal_tax_rate:>6.2f}%]")

def main():
    # get the current year tax inputs
    inputs = utils.load_inputs_from_file(INPUTS_FILE)
    inputs = utils.validate_inputs(inputs, utils.CY_INPUT_FILE_EXPECTED_KEYS)

    # get the carryforward data
    tax_year = inputs['tax_year']
    carryforward_file = f'data/{tax_year}_carryforward.dat'
    ma_capital_loss_carryforward = 0  
    try:
        py_data = utils.load_inputs_from_file(carryforward_file)
        py_data = utils.validate_inputs(py_data, utils.PY_CARRYFORWARD_FILE_EXPECTED_KEYS)
    except FileNotFoundError:
        utils.create_carryforward_file(tax_year)

    for scenario in SCENARIOS:
        scenario_inputs = inputs.copy()

        # adjust inputs per scenario
        for key, adjustment in scenario.items():
            if key == 'Description':
                continue
            original_value = scenario_inputs[key]
            if adjustment.startswith('+'):
                delta = float(adjustment[1:])
                scenario_inputs[key] = original_value + delta
            elif adjustment.startswith('-'):
                delta = float(adjustment[1:])
                scenario_inputs[key] = original_value - delta
            else:
                scenario_inputs[key] = float(adjustment)

        investment_income = scenario_inputs['income_int'] + scenario_inputs['income_div'] + scenario_inputs['income_inv_other']
        ordinary_income = scenario_inputs['income_wages'] + scenario_inputs['income_other']
        ma_taxes = MAIncomeTaxCalculator().calc(tax_year=scenario_inputs['tax_year'], 
                                            ordinary_income=ordinary_income,
                                            investment_income=investment_income,     
                                            short_term_gains=scenario_inputs['cg_short_term'],    
                                            long_term_gains=scenario_inputs['cg_long_term'],        
                                            deductions=scenario_inputs['deduct_charity'],            
                                            py_capital_loss_carryforward=py_data.get('ma_capital_loss_carryforward', 0)
                                        )

        us_taxes = USIncomeTaxCalculator().calc(**scenario_inputs, 
                                            deduct_state_income_tax=ma_taxes.ma_income_tax,
                                            py_inv_int_carryforward=py_data.get('us_inv_int_carryforward', 0),
                                            py_long_term_loss_carryforward=py_data.get('us_long_term_loss_carryforward', 0),
                                            py_short_term_loss_carryforward=py_data.get('us_short_term_loss_carryforward', 0)
                                            )

        print(f"Scenario: {scenario['Description']}", end=' ')
        # print()
        # dump_ma_tax_calc_results(ma_taxes)
        # dump_us_tax_calc_results(us_taxes)
        
        gross = us_taxes.gross_ordinary_income + us_taxes.gross_ltcg
        taxes = us_taxes.total_federal_tax + ma_taxes.ma_income_tax
        net = gross - taxes    
        print(f"TAXES:{taxes:>9,.0f} {taxes/gross*100:>6.1f}% of {gross:>10,.0f}", end=' ')
        print(f"NET:{net:>10,.0f} [TAXABLE INC:{us_taxes.taxable_income:>10,.0f} TAXABLE ORD:{us_taxes.taxable_ordinary_income:>10,.0f} TAXABLE LTCG:{us_taxes.taxable_ltcg_income:>10,.0f}]")

if __name__ == "__main__":
    main()
