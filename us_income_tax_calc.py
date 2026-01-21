import logging
#logger = logging.getLogger('main.us_income_tax_calc')
logger = logging.getLogger('US-CALC')

import json
import os
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass

@dataclass
class us_tax_result:
    tax_year: int
    filing_status: str
    gross_ordinary_income: float
    gross_ltcg: float
    ordinary_tax: float
    ltcg_tax: float
    niit_tax: float
    total_federal_tax: float
    taxable_income: float
    taxable_ordinary_income: float
    taxable_ltcg_income: float
    agi: float
    itemized_deductions: float
    standard_deduction: float
    deduction_used: str
    effective_tax_rate: float
    effective_tax_rate_agi: float
    marginal_tax_rate: float
    ltcg_tax_rate: float
    inv_int_carryforward: float
    st_loss_carryforward: float
    lt_loss_carryforward: float

TAX_DATA_JSON = 'data/us_tax_data.json'

class USIncomeTaxCalculator:
    def __init__(self, data_file: str = None):
        """
        Initialize the calculator.
        
        Args:
            data_file: Path to JSON file containing tax data. If None, uses default location.
        """
        if data_file is None:
            # Default to same directory as this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_file = os.path.join(script_dir, TAX_DATA_JSON)
        
        self.data_file = data_file
        self.tax_data = self._load_tax_data()
        
    def _load_tax_data(self) -> Dict:
        """Load tax brackets and parameters from JSON file."""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Tax data file not found: {self.data_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in tax data file: {e}")
    
    def get_available_years(self) -> List[int]:
        """Get list of supported tax years."""
        return sorted([int(year) for year in self.tax_data.keys()])
    
    def get_filing_statuses(self) -> List[str]:
        """Get list of supported filing statuses."""
        # Get from any year's data (they should all be the same)
        sample_year = str(self.get_available_years()[0])
        return list(self.tax_data[sample_year]['ordinary_income_brackets'].keys())
    
    def _calculate_bracket_tax(self, income: float, brackets: List[Dict]) -> Tuple[float, float]:
        """
        Calculate tax using progressive brackets.
        
        Args:
            income: Taxable income amount
            brackets: List of tax brackets with min, max, and rate
            
        Returns:
            Tuple of (tax_owed, marginal_rate)
        """
        if income <= 0:
            return 0.0, 0.0
            
        total_tax = 0.0
        marginal_rate = 0.0
        
        for bracket in brackets:
            bracket_min = bracket['min']
            bracket_max = bracket['max']
            rate = bracket['rate']
            
            if income <= bracket_min:
                break
                
            # Calculate taxable amount in this bracket
            if bracket_max is None:  # Top bracket
                taxable_in_bracket = income - bracket_min
                marginal_rate = rate
            elif income <= bracket_max:
                taxable_in_bracket = income - bracket_min
                marginal_rate = rate
            else:
                taxable_in_bracket = bracket_max - bracket_min

            total_tax += taxable_in_bracket * rate
            logger.debug(f"ORDI :: taxable_in_bracket [{rate*100:>2,.0f}%] [{bracket_min:>7}-{bracket_max if bracket_max is not None else float('inf'):>7}]: ${taxable_in_bracket:>12,.2f}  LTCG: ${total_tax:>12,.2f}")
            
            if bracket_max and income <= bracket_max:
                break
                
        return total_tax, marginal_rate
    
    def _calculate_niit(self, investment_income: float, agi: float, filing_status: str, tax_year: int) -> float:
        """
        Calculate Net Investment Income Tax (NIIT).
        
        NIIT is 3.8% on the lesser of:
        1. Net investment income, or
        2. AGI exceeding the threshold
        """
        year_data = self.tax_data[str(tax_year)]
        threshold = year_data['net_investment_income_tax']['thresholds'][filing_status]
        rate = year_data['net_investment_income_tax']['rate']
        
        if agi <= threshold:
            return 0.0
            
        excess_agi = agi - threshold
        taxable_investment_income = min(investment_income, excess_agi)

        logger.debug(f"NIIT calc :: investment_income: ${investment_income:,.0f}")
        logger.debug(f"NIIT calc :: agi: ${agi:,.0f}")
        logger.debug(f"NIIT calc :: threshold: ${threshold:,.0f}")
        logger.debug(f"NIIT calc :: rate: {rate}")  
        logger.debug(f"NIIT calc :: taxable_investment_income: ${taxable_investment_income:,.0f}")
        logger.debug(f"NIIT calc :: excess_agi: ${excess_agi:,.0f}")
        
        return taxable_investment_income * rate
    
    def _calculate_medical_expense_deduction(self,medical_expenses: float,agi: float,tax_year: int) -> Tuple[float, str]:
        """
        Calculate allowable medical expense deduction based on federal rules.
        
        Medical expenses are deductible only to the extent they exceed 7.5% of AGI.
        This threshold has been 7.5% since 2019 for all taxpayers.
        
        Args:
            medical_expenses: Total qualifying medical expenses paid
            agi: Adjusted Gross Income
            tax_year: Tax year
            
        Returns:
            Tuple of (allowable_deduction, explanation)
        """
        if medical_expenses <= 0:
            return 0.0, "No medical expenses reported"
        
        # Calculate 7.5% of AGI threshold
        agi_threshold = agi * 0.075
        
        # Calculate allowable deduction (amount exceeding threshold)
        if medical_expenses > agi_threshold:
            allowable_deduction = medical_expenses - agi_threshold
            explanation = f"Deductible amount (${medical_expenses:,.0f} - ${agi_threshold:,.0f} AGI threshold = ${allowable_deduction:,.0f})"
        else:
            allowable_deduction = 0.0
            explanation = f"No deduction (${medical_expenses:,.0f} does not exceed ${agi_threshold:,.0f} AGI threshold)"
        
        return allowable_deduction, explanation
    
    def _calculate_investment_interest_deduction(self, investment_interest_expense: float, investment_income: float, stcg:float, py_carryover: float = 0.0) -> Tuple[float, float, str]:
        if investment_interest_expense <= 0 and py_carryover <= 0:
            return 0.0, 0.0, "No investment interest expense reported"
        
        total_inv_inc = investment_income + max(0,stcg)
        total_investment_interest = investment_interest_expense + py_carryover
        
        # Calculate allowable deduction (limited to net investment income)
        if total_inv_inc >= total_investment_interest:
            # Can deduct all investment interest
            allowable_deduction = total_investment_interest
            carryover = 0.0
            explanation = f"Full deduction (${total_investment_interest:,.0f} ≤ net investment income ${total_inv_inc:,.0f})"
        else:
            # Limited by net investment income
            allowable_deduction = total_inv_inc
            carryover = total_investment_interest - total_inv_inc
            explanation = f"Limited deduction (${allowable_deduction:,.0f} of ${total_investment_interest:,.0f}, ${carryover:,.0f} carryover)"
        
        return allowable_deduction, carryover, explanation
    
    def _calculate_mortgage_interest_deduction(
        self,
        mortgage_interest: float,
        mortgage_rate: float,
        mortgage_origination_year: int,
        filing_status: str,
        tax_year: int
    ) -> Tuple[float, str]:
        """
        Calculate the allowable mortgage interest deduction based on federal rules.
        
        Args:
            mortgage_interest: Total mortgage interest paid
            mortgage_rate: the interest rate of the mortgage e.g. 0.03375
            mortgage_origination_year: Year the mortgage was originated
            home_equity_debt: Home equity debt balance
            filing_status: Filing status
            tax_year: Tax year
            
        Returns:
            Tuple of (allowable_deduction, explanation)
        """
        if mortgage_interest <= 0:
            return 0.0, "No mortgage interest reported"
        
        mortgage_balance = mortgage_interest / mortgage_rate if mortgage_rate > 0 else 0
        logger.debug(f"mortgage_balance: ${mortgage_balance:,.0f}")

        # Determine acquisition debt limit based on origination date
        # Tax Cuts and Jobs Act changed limits for loans after 12/15/2017
        if mortgage_origination_year >= 2018 or (mortgage_origination_year == 2017 and mortgage_balance > 0):
            # Post-TCJA limits (12/16/2017 and later)
            if filing_status == 'married_filing_separately':
                acquisition_limit = 375000  # $750K / 2
            else:
                acquisition_limit = 750000
            limit_type = "post-2017 TCJA"
        else:
            # Pre-TCJA limits (before 12/16/2017)
            if filing_status == 'married_filing_separately':
                acquisition_limit = 500000  # $1M / 2
            else:
                acquisition_limit = 1000000
            limit_type = "pre-2017 grandfathered"
        
        if mortgage_balance <= acquisition_limit:
            # Full deduction allowed
            allowable_deduction = mortgage_interest
            explanation = f"Full deduction (debt ${mortgage_balance:,.0f} under ${acquisition_limit:,.0f} {limit_type} limit)"
        else:
            # Prorate the interest based on qualifying debt
            qualifying_ratio = acquisition_limit / mortgage_balance if mortgage_balance > 0 else 0
            allowable_deduction = mortgage_interest * qualifying_ratio
            explanation = f"Prorated deduction (${allowable_deduction:,.0f} of ${mortgage_interest:,.0f} due to ${limit_type} debt limit)"
        
        return allowable_deduction, explanation
        
    def _calculate_capital_gains_tax(self, taxable_ordinary_income: float, taxable_capital_gains: float, total_taxable_income: float, filing_status: str, year_data: Dict) -> Tuple[float, float]:
        """
        Calculate capital gains tax.

        Args:
            taxable_ordinary_income: The portion of taxable income that is ordinary.
            taxable_capital_gains: The portion of taxable income that is capital gains.
            total_taxable_income: The sum of taxable_ordinary_income and taxable_capital_gains.
            filing_status: The taxpayer's filing status.
            year_data: Dictionary containing tax data for the specific year.

        Returns:
            Tuple of (ltcg_tax, ltcg_tax_rate)
        """
        ltcg_tax = 0.0
        if taxable_capital_gains > 0:
            current_income_level = taxable_ordinary_income # Ordinary income fills the lower brackets first
            capital_gains_brackets = year_data['long_term_capital_gains_brackets'][filing_status]
            for bracket in capital_gains_brackets:
                bracket_min = bracket['min']
                bracket_max = bracket['max']
                rate = bracket['rate']
                taxable_in_bracket = max(0, min(total_taxable_income, bracket_max if bracket_max is not None else float('inf')) - max(bracket_min, current_income_level))
                ltcg_tax += min(taxable_in_bracket, taxable_capital_gains) * rate
                logger.debug(f"LTCG :: taxable_in_bracket [{rate*100:>2,.0f}%] [{bracket_min:>7}-{bracket_max if bracket_max is not None else float('inf'):>7}]: ${taxable_in_bracket:>12,.2f}  LTCG: ${ltcg_tax:>12,.2f}")
                current_income_level = max(current_income_level, bracket_max if bracket_max is not None else float('inf'))
        ltcg_tax_rate = (ltcg_tax / taxable_capital_gains) if taxable_capital_gains > 0 else 0.0
        return ltcg_tax, ltcg_tax_rate

    def calc(
        self,
        tax_year: int,
        filing_status: str,
        income_wages: float = 0,
        income_int: float = 0,
        income_div: float = 0,
        income_div_qualified: float = 0,
        income_inv_other: float = 0,                 
        income_other: float = 0,
        cg_short_term: float = 0,
        cg_long_term: float = 0,
        deduct_medical: float = 0,
        deduct_property_tax: float = 0,
        deduct_state_income_tax: float = 0,
        deduct_charity: float = 0,
        deduct_margin_int: float = 0,
        deduct_mortgage_int: float = 0,
        deduct_mortgage_rate: float = 0,
        deduct_mortgage_orig_year: int = 0,
        py_inv_int_carryforward: float = 0,
        py_short_term_loss_carryforward: float = 0,
        py_long_term_loss_carryforward: float = 0
    ) -> us_tax_result:
        """
        Calculate federal income taxes.
        
        Args:
            tax_year: Tax year (2023, 2024, 2025)
            filing_status: Filing status ('single', 'married_filing_jointly', etc.)
            income_wages: W-2 income (wages, tips, etc.)
            income_int: Interest income (e.g. savings, CDs, etc.)
            income_div: Dividend income (includes both ordinary and qualified)
            income_div_qualified: Qualified dividend income
            income_inv_other: Other investment income (e.g. rental income, K1 portfolio income.)
            income_other: Other income (e.g. unemployment, pension, 401k, social security, self-employment, etc.)
            cg_short_term: Short-term capital gains
            cg_long_term: Long-term capital gains
            deduct_medical: Total qualifying medical expenses paid
            deduct_property_tax: Total property taxes paid
            deduct_state_income_tax: Total state income tax paid
            deduct_charity: Total charitable donations
            deduct_margin_int: Total investment interest paid (margin interest, etc.)   
            deduct_mortgage_int: Total mortgage interest paid
            deduct_mortgage_rate: Mortgage interest rate (e.g. 0.03375)
            deduct_mortgage_orig_year: Year the mortgage was originated
            py_inv_int_carryforward: Investment interest carryover from prior years
            py_short_term_loss_carryforward: Short-term capital losses carryover from prior years
            py_short_term_loss_carryforward: Short-term capital losses carryover from prior years

        Returns:
            TaxResult object with detailed calculation results
        """
        # Validate inputs
        if str(tax_year) not in self.tax_data:
            raise ValueError(f"Tax year {tax_year} not supported. Available: {self.get_available_years()}")
        
        if filing_status not in self.get_filing_statuses():
            raise ValueError(f"Filing status '{filing_status}' not supported. Available: {self.get_filing_statuses()}")
        
        year_data = self.tax_data[str(tax_year)]
        
        gross_income = income_wages + income_int + income_div + income_inv_other + income_other + max(0, cg_short_term)
        gross_ltcg = cg_long_term + min(0, cg_short_term)
        logger.debug(f"gross_income: ${gross_income:,.2f}")
        logger.debug(f"gross_ltcg: ${gross_ltcg:,.2f}")

        # Calculate AGI - which includes carryforwards
        logger.debug(f"ltcg (CY): ${cg_long_term:,.2f}")
        logger.debug(f"stcg (CY): ${cg_short_term:,.2f}")
        cg_long_term = cg_long_term - py_long_term_loss_carryforward
        cg_short_term = cg_short_term - py_short_term_loss_carryforward
        net_ltcg = cg_long_term + min(0, cg_short_term)
        logger.debug(f"stcg (w/PYCF): ${cg_short_term:,.2f}")
        logger.debug(f"ltcg (w/PYCF): ${cg_long_term:,.2f}")
        logger.debug(f"net_capital_gains: ${net_ltcg:,.2f}")

        ordinary_income = income_wages + income_int + income_div + income_inv_other + income_other + max(0, cg_short_term)
        logger.debug(f"ordinary_income: ${ordinary_income:,.2f}")

        # Handle long-term capital gains losses
        if net_ltcg < 0:
            # Can deduct up to $3,000 of capital losses against ordinary income
            capital_loss_income_deduction = min(abs(net_ltcg), 3000)
            agi = ordinary_income - capital_loss_income_deduction
            capital_loss_carry_forward = abs(net_ltcg) - capital_loss_income_deduction
            
            # Allocate carryforward pro-rata between LTCG and STCG losses
            ltcg_loss_ratio = abs(cg_long_term) / net_ltcg if cg_long_term < 0 else 0
            stcg_loss_ratio = 100 - ltcg_loss_ratio if cg_short_term < 0 else 0
            lt_loss_carry_forward = capital_loss_carry_forward * ltcg_loss_ratio * 0.01
            st_loss_carry_forward = capital_loss_carry_forward * stcg_loss_ratio * 0.01

        else:
            agi = ordinary_income + max(0, net_ltcg)
            capital_loss_income_deduction = 0
            capital_loss_carry_forward = 0
            lt_loss_carry_forward = 0
            st_loss_carry_forward = 0
        
        logger.debug(f"capital_loss_income_deduction: ${capital_loss_income_deduction:,.2f}")
        logger.debug(f"capital_loss_carry_forward: ${capital_loss_carry_forward:,.2f}")
        logger.debug(f"lt_loss_carry_forward: ${lt_loss_carry_forward:,.2f}")
        logger.debug(f"st_loss_carry_forward: ${st_loss_carry_forward:,.2f}")
        logger.debug(f"agi: ${agi:,.2f}")

        ## ITEMIZED DEDUCTIONS   .............................................................
        itemized_deductions_list = []

        # Apply SALT deduction limit
        salt_limit = year_data['salt_deduction']['max']
        salt_deduction = min(deduct_property_tax + deduct_state_income_tax, salt_limit)
        itemized_deductions_list.append(salt_deduction)
        logger.debug(f"salt_deduction: ${salt_deduction:,.2f}")
        
        # Calculate allowable mortgage interest deduction
        mortgage_interest_deduction, mortgage_explanation = self._calculate_mortgage_interest_deduction(deduct_mortgage_int, deduct_mortgage_rate, deduct_mortgage_orig_year, filing_status, tax_year)     
        itemized_deductions_list.append(mortgage_interest_deduction)
        logger.debug(f"mortgage_interest_deduction: ${mortgage_interest_deduction:,.2f}")
        
        # Calculate allowable investment interest expense deduction
        investment_int_deduction, inv_int_carryforward, investment_explanation = self._calculate_investment_interest_deduction(deduct_margin_int, income_int+income_div-income_div_qualified+income_inv_other, cg_short_term, py_inv_int_carryforward)
        itemized_deductions_list.append(investment_int_deduction)
        logger.debug(f"investment_interest_allowed: ${investment_int_deduction:,.2f}")
        logger.debug(f"investment_interest_carryover: ${inv_int_carryforward:,.2f}")
        logger.debug(f"investment_explanation: {investment_explanation}")

        # Calculate allowable medical expense deduction
        medical_exp_deduction, medical_explanation = self._calculate_medical_expense_deduction(deduct_medical, agi, tax_year)
        itemized_deductions_list.append(medical_exp_deduction)
        logger.debug(f"medical_exp_deduction: ${medical_exp_deduction:,.2f}")
        logger.debug(f"medical_explanation: {medical_explanation}")

        # Calculate sum of itemized deductions
        itemized_deductions_list.append(deduct_charity)
        logger.debug(f"itemized_deductions_list: {itemized_deductions_list}")
        itemized_deductions = sum(itemized_deductions_list)
      
        standard_deduction = year_data['standard_deductions'][filing_status]
        if itemized_deductions > standard_deduction:
            total_deductions = itemized_deductions
            deduction_used = "itemized"
        else:
            total_deductions = standard_deduction
            deduction_used = "standard"
        logger.debug(f"total_deductions: ${total_deductions:,.2f}")

        # Calculate taxable income
        taxable_ordinary_income = max(0, ordinary_income - total_deductions - income_div_qualified)     # remove qualified dividends from ordinary income first
        taxable_capital_gains = max(0, net_ltcg) + income_div_qualified                                 # add back qualified dividends to LTCG portion
        total_taxable_income = taxable_ordinary_income + taxable_capital_gains
        logger.debug(f"taxable_ordinary_income: ${taxable_ordinary_income:,.2f}")
        logger.debug(f"taxable_capital_gains: ${taxable_capital_gains:,.2f}")
        logger.debug(f"total_taxable_income: ${total_taxable_income:,.2f}")
        
        # Calculate ordinary income tax
        ordinary_brackets = year_data['ordinary_income_brackets'][filing_status]
        ordinary_tax, marginal_rate = self._calculate_bracket_tax(taxable_ordinary_income, ordinary_brackets)
        
        # Calculate long-term capital gains tax
        ltcg_tax, ltcg_tax_rate = self._calculate_capital_gains_tax(taxable_ordinary_income, taxable_capital_gains, total_taxable_income, filing_status, year_data)
        logger.debug(f"ltcg_tax: ${ltcg_tax:,.2f}")

        # Calculate NIIT (applies to investment income)
        investment_income = income_int + income_div + cg_long_term + cg_short_term + income_inv_other
        niit_tax = self._calculate_niit(investment_income, agi, filing_status, tax_year)
        logger.debug(f"niit_tax: ${niit_tax:,.2f}")
        
        # Calculate total federal tax
        total_federal_tax = ordinary_tax + ltcg_tax + niit_tax
        
        # Calculate effective tax rate
        effective_tax_rate_agi = (total_federal_tax / agi * 100) if agi > 0 else 0.0
        effective_tax_rate = (total_federal_tax / total_taxable_income * 100) if total_taxable_income > 0 else 0.0
        
        return us_tax_result(
            tax_year=tax_year,
            filing_status=filing_status,
            gross_ordinary_income=ordinary_income,
            gross_ltcg=net_ltcg,
            ordinary_tax=round(ordinary_tax, 2),
            ltcg_tax=round(ltcg_tax, 2),
            niit_tax=round(niit_tax, 2),
            total_federal_tax=round(total_federal_tax, 2),
            taxable_income=round(total_taxable_income, 2),
            taxable_ordinary_income=round(taxable_ordinary_income, 2),
            taxable_ltcg_income=round(taxable_capital_gains, 2),
            agi=round(agi, 2),
            itemized_deductions=round(itemized_deductions, 2),
            standard_deduction=round(standard_deduction, 2),
            deduction_used=deduction_used,
            effective_tax_rate=round(effective_tax_rate, 2),
            effective_tax_rate_agi=round(effective_tax_rate_agi, 2),
            marginal_tax_rate=round(marginal_rate * 100, 2),
            ltcg_tax_rate=round(ltcg_tax_rate * 100, 2),
            inv_int_carryforward=round(inv_int_carryforward, 2),
            st_loss_carryforward=round(st_loss_carry_forward, 2),
            lt_loss_carryforward=round(lt_loss_carry_forward, 2)
        )
