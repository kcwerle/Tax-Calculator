import logging
logger = logging.getLogger('MA-CALC')

from typing import Dict
import json
import os
from dataclasses import dataclass

MA_DATA_JSON = 'data/ma_tax_data.json'

@dataclass
class ma_tax_result:
    tax_year: int
    filing_status: str
    ordinary_tax: float
    ltcg_tax: float
    stcg_tax: float
    ma_income_tax: float
    taxable_income: float
    taxable_ordinary: float
    taxable_long_term: float
    taxable_short_term: float
    is_surtax: bool
    ordinary_rate: float
    long_term_rate: float
    short_term_rate: float
    capital_loss_carryforward: float

class MAIncomeTaxCalculator:
    """Core Massachusetts state income tax calculation engine."""
    
    def __init__(self):
        # Tax parameters by year - load tax parameters from JSON file
        json_path = os.path.join(os.path.dirname(__file__), MA_DATA_JSON)         
        with open(json_path, 'r') as f:
            tax_data = json.load(f)
            # Convert string keys to integers
            self.tax_years = {int(year): params for year, params in tax_data.items()}
    
    def get_year_params(self, tax_year: int) -> Dict:
        """Get tax parameters for a specific year."""
        if tax_year not in self.tax_years:
            raise ValueError(f"Tax year {tax_year} not supported. Supported years: {list(self.tax_years.keys())}")
        return self.tax_years[tax_year]
    
    def get_standard_deduction(self, tax_year: int, filing_status: str) -> float:
        """Get standard deduction for a specific year and filing status."""
        year_params = self.get_year_params(tax_year)
        if filing_status not in year_params['standard_exemption']:
            raise ValueError(f"Invalid filing status: {filing_status}")
        return year_params['standard_exemption'][filing_status]
    
    def calc(self, 
                     tax_year: int,
                     ordinary_income: float = 0.0,                  # wages + other income
                     investment_income: float = 0.0,                # interest + dividends + other investment income
                     short_term_gains: float = 0.0,                 # short-term capital gains/losses (negative for losses)
                     long_term_gains: float = 0.0,                  # long-term capital gains/losses (negative for losses)
                     deductions: float = 0.0,                       # charitable contributions + social security withholdings
                     py_capital_loss_carryforward: float = 0.0,
                     filing_status: str = 'MFJ',
                     custom_standard_deduction: float = None) -> Dict:
        """
        Calculate Massachusetts state income tax.
        
        Args:
            tax_year: Tax year (2023, 2024, or 2025)
            ordinary_income: Income from W-2 and 1099 sources
            investment_income: Interest and dividends
            short_term_gains: Short-term capital gains/losses (negative for losses)
            long_term_gains: Long-term capital gains/losses (negative for losses)
            deductions: Deductions (charitable contributions + social security withholdings)
            py_capital_loss_carryforward: Prior year excess capital losses
            filing_status: 'single', 'married_joint', 'married_separate', or 'head_of_household'
            custom_standard_deduction: Override default standard deduction
        
        Returns:
            Dictionary with detailed tax calculation results
        """
        
        # Get year-specific tax parameters
        year_params = self.get_year_params(tax_year)
        
        # Get standard deduction
        if custom_standard_deduction is not None:
            standard_exemption = custom_standard_deduction
        else:
            standard_exemption = self.get_standard_deduction(tax_year, filing_status)
               
        net_short_term = short_term_gains
        net_long_term = long_term_gains
      
        # Apply netting rules for capital gains/losses - if one is positive and the other negative, net them against each other
        if net_short_term > 0 and net_long_term < 0:
            # Long-term losses offset short-term gains
            offset_amount = min(net_short_term, abs(net_long_term))
            net_short_term -= offset_amount
            net_long_term += offset_amount
        elif net_short_term < 0 and net_long_term > 0:
            # Short-term losses offset long-term gains  
            offset_amount = min(net_long_term, abs(net_short_term))
            net_long_term -= offset_amount
            net_short_term += offset_amount

        # Apply prior year capital loss carry forward to reduce short-term and long-term gains
        loss_carryforward = py_capital_loss_carryforward
        if loss_carryforward > 0:
            if net_short_term > 0:
                offset_amount = min(net_short_term, loss_carryforward)
                net_short_term -= offset_amount
                loss_carryforward -= offset_amount
            if loss_carryforward > 0 and net_long_term > 0:
                offset_amount = min(net_long_term, loss_carryforward)
                net_long_term -= offset_amount
                loss_carryforward -= offset_amount

        # Calculate remaining offset balance that can be used to reduce investment income       
        offset_balance = loss_carryforward - min(0, net_short_term) - min(0, net_long_term)
        logger.debug(f"offset_balance: {offset_balance:,.2f}")

        # if the offset balance is positive, it means we have excess losses that can be used to reduce investment income (up to max allowed)
        logger.debug(f"investment_income: {investment_income:,.2f}")
        adjusted_investment_income = investment_income
        if offset_balance > 0:
            # Apply prior year losses to investment income (up to max allowed)
            investment_income_adjustment = min(year_params['max_int_div_adj'], offset_balance)
            adjusted_investment_income = max(0, investment_income - investment_income_adjustment)
            offset_balance -= investment_income_adjustment
        logger.debug(f"adjusted_investment_income: {adjusted_investment_income:,.2f}")   
        
        # Remaining offset balance becomes the new capital loss carryforward for next year
        capital_loss_carryforward = offset_balance if offset_balance > 0 else 0.0

        # For tax purposes, only positive amounts are taxable
        taxable_short_term_gains = max(0, net_short_term)
        taxable_long_term_gains = max(0, net_long_term)
        logger.debug(f"taxable_short_term_gains: {taxable_short_term_gains:,.2f}")
        logger.debug(f"taxable_long_term_gains: {taxable_long_term_gains:,.2f}")

        # Calculate total income for AGI
        logger.debug(f"ordinary_income: {ordinary_income:,.2f}")
        logger.debug(f"deductions: {deductions:,.2f}")
        adjusted_ordinary_income = max(0,ordinary_income - deductions)
        total_capital_gains = taxable_short_term_gains + taxable_long_term_gains
        agi = adjusted_ordinary_income + adjusted_investment_income + total_capital_gains
        logger.debug(f"adjusted_ordinary_income: {adjusted_ordinary_income:,.2f}")
        logger.debug(f"total_capital_gains: {total_capital_gains:,.2f}")
        logger.debug(f"AGI: {agi:,.2f}")

        # Determine if surtax applies (2023+)
        surtax_threshold = year_params['surtax_threshold']
        is_surtax = surtax_threshold and agi >= surtax_threshold
        surtax = year_params['surtax'] if is_surtax else 0.0
        
        # Calculate tax on each income type separately
        # We need to allocate the standard deduction proportionally
        if agi > standard_exemption:
            # Calculate what portion of each income type is taxable after deduction
            deduction_remaining = standard_exemption
            logger.debug(f"standard_exemption: {standard_exemption:,.2f}")

            # Apply deduction in order: short-term gains, long-term gains, then investment income
            taxable_short_term_final = max(0, taxable_short_term_gains - deduction_remaining)
            deduction_remaining = max(0, deduction_remaining - taxable_short_term_gains)

            taxable_long_term_final = max(0, taxable_long_term_gains - deduction_remaining)
            deduction_remaining = max(0, deduction_remaining - taxable_long_term_gains)

            taxable_ordinary_income = max(0, adjusted_ordinary_income + adjusted_investment_income - deduction_remaining)           
        else:
            taxable_ordinary_income = 0
            taxable_long_term_final = 0
            taxable_short_term_final = 0

        total_taxable_income = taxable_ordinary_income + taxable_long_term_final + taxable_short_term_final
        logger.debug(f"taxable_ordinary_income: {taxable_ordinary_income:,.2f}")
        logger.debug(f"taxable_long_term_final: {taxable_long_term_final:,.2f}")
        logger.debug(f"taxable_short_term_final: {taxable_short_term_final:,.2f}")
        logger.debug(f"total_taxable_income: {total_taxable_income:,.2f}")
        
        # Calculate tax rates for each income type (including millionaire's tax if applicable)
        ordinary_rate = year_params['ordinary_rate'] + surtax
        long_term_rate = year_params['long_term_rate'] + surtax
        short_term_rate = year_params['short_term_rate'] + surtax
        
        # Calculate tax for each income type
        ordinary_tax = taxable_ordinary_income * ordinary_rate
        long_term_tax = taxable_long_term_final * long_term_rate
        short_term_tax = taxable_short_term_final * short_term_rate
        total_income_tax = ordinary_tax + long_term_tax + short_term_tax

        return ma_tax_result(
            tax_year=tax_year,
            filing_status=filing_status,
            ordinary_tax=round(ordinary_tax, 2),
            ltcg_tax=round(long_term_tax, 2),
            stcg_tax=round(short_term_tax, 2),
            ma_income_tax=round(total_income_tax, 2),
            taxable_income=round(total_taxable_income, 2),
            taxable_ordinary=round(taxable_ordinary_income, 2),
            taxable_long_term=round(taxable_long_term_final, 2),
            taxable_short_term=round(taxable_short_term_final, 2),
            is_surtax=is_surtax,
            ordinary_rate=round(ordinary_rate, 4),
            long_term_rate=round(long_term_rate, 4),
            short_term_rate=round(short_term_rate, 4),
            capital_loss_carryforward=round(capital_loss_carryforward, 2)
        )

    
