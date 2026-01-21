# Tax Calculator
**DISCLAIMER:** 
**
I AM NOT A QUALIFIED TAX PROFESSIONAL. THIS TOOL IS FOR INFORMATIONAL AND EDUCATIONAL PURPOSES ONLY AND SHOULD NOT BE CONSIDERED TAX ADVICE. PLEASE CONSULT WITH A QUALIFIED TAX PROFESSIONAL TO CONFIRM YOUR TAX OBLIGATIONS AND FOR PERSONALIZED ADVICE.  DO NOT RELY ON OUTPUT FROM THIS CODE TO MAKE ANY TAX DECISIONS.
**

A Python-based tax calculation tool for computing US Federal and Massachusetts state income taxes. This tool handles complex tax scenarios including capital gains, investment income, various deductions, and multi-year carryforward calculations.

## Overview
This codebase provides tax calculations for both Federal (US) and Massachusetts (MA) state income taxes, supporting tax years 2023-2025 (2026 assumes 2025 tax brackets). 

The calculator handles:
- Progressive tax brackets for ordinary income
- Long-term and short-term capital gains taxation
- Net Investment Income Tax (NIIT)
- Capital loss carryforwards
- Investment interest expense deductions with carryforwards
- Itemized vs standard deductions
- State and local tax (SALT) limitations
- Mortgage interest deduction limits
- Medical expense deductions

## Project Structure
```
tax-calc/
├── tax_calc.py                    # Main entry point for single tax calculation
├── run_scenarios.py               # Scenario analysis tool for comparing tax impacts
├── us_income_tax_calc.py          # US Federal income tax calculator engine
├── ma_income_tax_calc.py          # Massachusetts state income tax calculator engine
├── utils.py                       # Utility functions for file I/O and validation
├── logging.conf                   # Logging configuration
├── data/
│   ├── us_tax_data.json          # Federal tax brackets and parameters (2023-2025)
│   ├── ma_tax_data.json          # MA state tax rates and parameters (2023-2025)
│   └── *_carryforward.dat        # Prior year carryforward values get created here
├── test/
    └── test.dat                  # tax input test data (template for tax inputs)
```

## Core Components

### Main Scripts

**tax_calc.py**
- Primary calculator that computes both Federal and MA state taxes
- Reads input data from `.dat` files in the `data/` directory
- Applies prior year carryforwards automatically
- Updates carryforward files for the next tax year
- Usage: `./tax_calc.py [input_file]` (defaults to `data/2025_tax_inputs.dat`)

**run_scenarios.py**
- Runs multiple tax scenarios based on a base case
- Useful for tax planning and "what-if" analysis
- Configure scenarios by adjusting income and capital gains parameters
- Usage: `./run_scenarios.py`
- TODO: move scenarios out of script and into files passed in on the command line

### Calculator Engines

**USIncomeTaxCalculator** (`us_income_tax_calc.py`)
- Calculates Federal income tax using progressive brackets
- Handles ordinary income, long-term capital gains (LTCG), and qualified dividends
- Computes Net Investment Income Tax (NIIT - 3.8% surtax)
- Manages complex deduction rules:
  - SALT (State And Local Tax) deduction cap ($10,000)
  - Mortgage interest deduction limits (post-TCJA)
  - Investment interest expense limitation
  - Medical expense deduction (7.5% AGI floor)
- Tracks carryforwards: investment interest, short-term losses, long-term losses
- Returns `us_tax_result` dataclass with detailed breakdown

**MAIncomeTaxCalculator** (`ma_income_tax_calc.py`)
- Calculates Massachusetts state income tax
- Applies different rates to ordinary income (5.0%) vs capital gains (8.5% for short-term, 5.0% for long-term)
- Implements MA "Millionaire's Tax" surtax (4% on income over $1M, effective 2023+)
- Handles capital gains netting rules
- Manages capital loss carryforwards
- Returns `ma_tax_result` dataclass with detailed breakdown

### Data Files

**Tax Input Files** (`data/*_tax_inputs.dat`)
Format: `key=value` pairs with optional comments
```
tax_year=2025
filing_status=MFJ
income_wages=1000
income_int=126
income_div_qualified=6551
income_div=6633
cg_short_term=215000
cg_long_term=0
deduct_charity=2500
# ... more fields
```

**Carryforward Files** (`data/*_carryforward.dat`)
Stores values that carry forward from prior years:
- `ma_capital_loss_carryforward` - MA state capital loss carryover
- `us_inv_int_carryforward` - Federal investment interest expense carryover
- `us_short_term_loss_carryforward` - Federal short-term capital loss carryover
- `us_long_term_loss_carryforward` - Federal long-term capital loss carryover

**Tax Data Files** (`data/*_tax_data.json`)
- `us_tax_data.json`: Federal tax brackets, standard deductions, NIIT thresholds
- `ma_tax_data.json`: MA tax rates, standard exemptions, surtax thresholds

## Key Features

### Federal Tax Calculation
- Progressive ordinary income tax brackets (10%, 12%, 22%, 24%, 32%, 35%, 37%)
- Preferential long-term capital gains rates (0%, 15%, 20%)
- NIIT (3.8%) on investment income when AGI exceeds thresholds
- Capital loss limitation ($3,000 per year against ordinary income)
- Investment interest expense limitation (deductible only against investment income)
- Itemized deduction calculations with various limitations

### Massachusetts Tax Calculation
- Flat 5.0% tax on ordinary income (Part A income)
- 8.5% tax on short-term capital gains (Part B income)
- 5.0% tax on long-term capital gains (Part C income)
- 4% Millionaire's Surtax on income over $1M (2023+)
- Capital gains netting between short-term and long-term
- Capital loss carryforward management

## Usage Examples

### Single Tax Calculation
```bash
# Calculate taxes using default input file (2025_tax_inputs.dat)
./tax_calc.py

# Calculate taxes using a specific input file
./tax_calc.py data/2024_tax_inputs.dat
```

### Scenario Analysis
```bash
# Run multiple scenarios from run_scenarios.py
./run_scenarios.py
```

Edit the `SCENARIOS` list in `run_scenarios.py` to define different tax scenarios:
```python
SCENARIOS = [
    {'Description': 'Base Case', 'income_other': '+0', 'cg_long_term': '+0'},
    {'Description': '100K LT Gains', 'income_other': '+0', 'cg_long_term': '+100000'},
    {'Description': '100K 401k Dist', 'income_other': '+100000', 'cg_long_term': '+0'},
]
```

### Running Tests

## Configuration

### Logging
Logging is controlled by `logging.conf`. To disable logging, remove or rename the file.

### Filing Status
Supported filing statuses ...
- `single`                    -> SNG
- `married_filing_jointly`    -> MFJ
- `married_filing_separately` -> MFS
- `head_of_household`         -> HOH

## Tax Rules Implementation

### Federal Capital Loss Rules
- Losses offset gains within the same category first (short-term vs long-term)
- Remaining losses can offset up to $3,000 of ordinary income
- Excess losses carry forward indefinitely, maintaining their character

### Massachusetts Capital Gains Netting
- Short-term and long-term gains/losses are netted against each other
- Losses can offset investment income (up to annual limit)
- Excess losses carry forward to subsequent years

### Investment Interest Expense
- Deductible only to the extent of net investment income
- Investment income includes interest, ordinary dividends, and short-term gains
- Qualified dividends and long-term gains can be included if you elect to forgo preferential rates (not implemented)
- Excess expense carries forward indefinitely

## Dependencies
- Python 3.x
- Standard library only (json, logging, os, sys, dataclasses, typing)

## Notes
- Tax data (brackets, rates) is stored in JSON files for easy updates
- Calculations are based on 2023-2025 tax law
- The calculator handles carryforwards automatically between years
- Results are rounded to 2 decimal places (cents)
- Effective tax rates are calculated both on taxable income and AGI