import logging
import logging.config
import os
import sys

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

# for debugging in the IDE and when run with no parameters
INPUTS_FILE = 'test/test.dat'

def dump_ma_tax_calc_results(data):
    print()
    print(f"{data.tax_year} - MA State Income Tax")
    print(f"Income Tax: ${data.ma_income_tax:,.0f}  [Taxable Income: ${data.taxable_income:,.0f}]")
    print(f"  {'Ordinary Income Tax:':<34} ${data.ordinary_tax:>12,.0f}  [${data.taxable_ordinary:>12,.0f} at {data.ordinary_rate*100:>4.1f}%]")
    print(f"  {'Long-Term Capital Gains Tax:':<34} ${data.ltcg_tax:>12,.0f}  [${data.taxable_long_term:>12,.0f} at {data.long_term_rate*100:>4.1f}%]")
    print(f"  {'Short-Term Capital Gains Tax:':<34} ${data.stcg_tax:>12,.0f}  [${data.taxable_short_term:>12,.0f} at {data.short_term_rate*100:>4.1f}%]")
    if data.is_surtax:
        print(f"  (Includes Millionaire's Surtax)")
    print(f"\n  {'Capital Loss Carryforward:':<34} ${data.capital_loss_carryforward:>12,.0f}")

def dumps_us_tax_calc_results(data):
    print()
    print(f"{data.tax_year} - US Federal Income Tax")
    print(f"Income Tax: ${data.total_federal_tax:,.0f}  [Taxable Income: ${data.taxable_income:,.0f}]")
    print(f"  {'Ordinary Income Tax:':<34} ${data.ordinary_tax:>12,.0f}  [${data.taxable_income-data.taxable_ltcg_income:>12,.0f}]")  
    print(f"  {'Long-Term Capital Gains Tax:':<34} ${data.ltcg_tax:>12,.0f}  [${data.taxable_ltcg_income:>12,.0f}  Marginal Rate: {data.ltcg_tax_rate:>4.1f}%]")
    print(f"  {'NIIT Tax:':<34} ${data.niit_tax:>12,.0f}")
    print(f"  {'Effective Tax Rate:':<34} {data.effective_tax_rate:>12,.1f}%  [${data.total_federal_tax:>8,.0f} / ${data.taxable_income:>8,.0f}]")
    print(f"  {'Effective Tax Rate (AGI):':<34} {data.effective_tax_rate_agi:>12,.1f}%  [${data.total_federal_tax:>8,.0f} / ${data.agi:>8,.0f}]")
    print(f"  {'Marginal Tax Rate:':<34} {data.marginal_tax_rate:>12,.1f}%")
    print(f"\n  {'Investment Interest Carryforward:':<34} ${data.inv_int_carryforward:>12,.0f}")
    print(f"  {'Short-Term Loss Carryforward:':<34} ${data.st_loss_carryforward:>12,.0f}")
    print(f"  {'Long-Term Loss Carryforward:':<34} ${data.lt_loss_carryforward:>12,.0f}")

def main():
    if len(sys.argv) > 1:
        inputs_file = sys.argv[1]
    else:
        inputs_file = INPUTS_FILE

    logger.debug(f"Loading inputs from {inputs_file}")
    # get the current year tax inputs
    inputs = utils.load_inputs_from_file(inputs_file)
    inputs = utils.validate_inputs(inputs, utils.CY_INPUT_FILE_EXPECTED_KEYS)

    # get the carryforward data
    tax_year = inputs['tax_year']
    carryforward_file = f'data/{tax_year}_carryforward.dat'
    ma_capital_loss_carryforward = 0  
    try:
        py_data = utils.load_inputs_from_file(carryforward_file)
        py_data = utils.validate_inputs(py_data, utils.PY_CARRYFORWARD_FILE_EXPECTED_KEYS)
        logger.debug(f"carryforward data: {carryforward_file}") # type: ignore
        for key, value in py_data.items():
            logger.debug(f"  {key:>40}: {value:>12,.2f}")
    except FileNotFoundError:
        logger.warning(f"Carryforward file {carryforward_file} not found. Creating new one.")
        utils.create_carryforward_file(tax_year)

    # Calculate Massachusetts state taxes
    investment_income = inputs['income_int'] + inputs['income_div'] + inputs['income_inv_other']
    ordinary_income = inputs['income_wages'] + inputs['income_other']
    logger.debug("Calculating MA taxes...")
    ma_taxes = MAIncomeTaxCalculator().calc(tax_year=inputs['tax_year'], 
                                        ordinary_income=ordinary_income,
                                        investment_income=investment_income,     
                                        short_term_gains=inputs['cg_short_term'],    
                                        long_term_gains=inputs['cg_long_term'],
                                        deductions=inputs['deduct_charity'],
                                        py_capital_loss_carryforward=py_data.get('ma_capital_loss_carryforward', 0))


    logger.debug("Calculating US taxes...")
    us_taxes = USIncomeTaxCalculator().calc(**inputs, 
                                            deduct_state_income_tax=ma_taxes.ma_income_tax,
                                            py_inv_int_carryforward=py_data.get('us_inv_int_carryforward', 0),
                                            py_long_term_loss_carryforward=py_data.get('us_long_term_loss_carryforward', 0),
                                            py_short_term_loss_carryforward=py_data.get('us_short_term_loss_carryforward', 0)
                                            )

    logger.debug(f"Updating carryforward file for {tax_year + 1}")
    utils.create_carryforward_file(tax_year + 1, {
        'ma_capital_loss_carryforward': ma_taxes.capital_loss_carryforward,
        'us_inv_int_carryforward': us_taxes.inv_int_carryforward,
        'us_short_term_loss_carryforward': us_taxes.st_loss_carryforward,
        'us_long_term_loss_carryforward': us_taxes.lt_loss_carryforward
    })  
    logger.debug(f"  {'ma_capital_loss_carryforward':>40}: {ma_taxes.capital_loss_carryforward:>12,.2f}")
    logger.debug(f"  {'us_inv_int_carryforward':>40}: {us_taxes.inv_int_carryforward:>12,.2f}")
    logger.debug(f"  {'us_short_term_loss_carryforward':>40}: {us_taxes.st_loss_carryforward:>12,.2f}")
    logger.debug(f"  {'us_long_term_loss_carryforward':>40}: {us_taxes.lt_loss_carryforward:>12,.2f}")

    dump_ma_tax_calc_results(ma_taxes)
    dumps_us_tax_calc_results(us_taxes)

    gross = us_taxes.gross_ordinary_income + us_taxes.gross_ltcg
    taxes = us_taxes.total_federal_tax + ma_taxes.ma_income_tax
    net = gross - taxes    
    print()
    print(f"{us_taxes.tax_year} TAXES")
    print(f"Gross: {gross:>10,.0f}")
    print(f"Taxes: {taxes:>10,.0f}  [{taxes/gross*100:>6.1f}%]")
    print(f"Net:   {net:>10,.0f}")
    print()

    logging.debug("INPUTS " + 32 * '.')
    for key, value in inputs.items():
        if isinstance(value, (float)):
            logging.debug(f"{key:>30}: {value:>14,.5f}")
        else:
            logging.debug(f"{key:>30}: {value:>14}")

    logging.debug("RESULTS [ MA ]" + 32 * '.')
    for key, value in ma_taxes.__dict__.items():
        if isinstance(value, (float)):
            logging.debug(f"{key:>30}: {value:>14,.5f}")
        else:
            logging.debug(f"{key:>30}: {value:>14}")        

    logging.debug("RESULTS [ US ]" + 32 * '.')
    for key, value in us_taxes.__dict__.items():
        if isinstance(value, (float)):
            logging.debug(f"{key:>30}: {value:>14,.5f}")
        else:
            logging.debug(f"{key:>30}: {value:>14}")        

if __name__ == "__main__":
    main()
