from typing import Dict

def load_inputs_from_file(filename: str) -> Dict:
    raw_inputs = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                # Strip line numbers if present (format: "1|key=value")
                if '|' in line:
                    line = line.split('|', 1)[1]
                
                # Remove inline comments (python style)
                if '#' in line:
                    line = line.split('#', 1)[0]
                
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Convert numeric values
                    if key in ['tax_year']:
                        if not value:
                            raise ValueError(f"{key} cannot be empty")
                        raw_inputs[key] = int(value)
                    elif key in ['filing_status']:
                        raw_inputs[key] = value
                    else:
                        if not value:
                            raise ValueError(f"{key} cannot be empty")
                        try:
                            raw_inputs[key] = float(value)
                        except ValueError:
                            raise ValueError(f"{key} must be a valid number, got '{value}'")

                                
    except FileNotFoundError:
        raise FileNotFoundError(f"tax inputs file not found: {filename}")

    return raw_inputs

CY_INPUT_FILE_EXPECTED_KEYS = {
    'tax_year', 'filing_status', 'income_wages', 'income_int', 'income_div_qualified', 'income_div',
    'income_inv_other', 'income_other', 'cg_short_term', 'cg_long_term', 'deduct_medical',
    'deduct_property_tax', 'deduct_charity', 'deduct_margin_int',
    'deduct_mortgage_rate', 'deduct_mortgage_int', 'deduct_mortgage_orig_year',
}

PY_CARRYFORWARD_FILE_EXPECTED_KEYS = {
    'ma_capital_loss_carryforward',
    'us_inv_int_carryforward',
    'us_short_term_loss_carryforward',
    'us_long_term_loss_carryforward'
}

def create_carryforward_file(year: int, values_dict: Dict = None) -> None:
    """Create a carryforward file with all keys set to 0, or updated from a dictionary."""
    filename = f'data/{year}_carryforward.dat'
    values = {key: 0 for key in PY_CARRYFORWARD_FILE_EXPECTED_KEYS}
    
    if values_dict is not None:
        values.update(values_dict)
    
    with open(filename, 'w') as f:
        for key in PY_CARRYFORWARD_FILE_EXPECTED_KEYS:
            f.write(f"{key}={values[key]}\n")

def validate_inputs(raw_inputs: Dict, expected_keys: set) -> Dict:
    if set(raw_inputs.keys()) != expected_keys:
        missing = expected_keys - set(raw_inputs.keys())
        extra = set(raw_inputs.keys()) - expected_keys
        error_msg = "Input file validation failed."
        if missing:
            error_msg += f" Missing keys: {sorted(missing)}."
        if extra:
            error_msg += f" Extra keys: {sorted(extra)}."
        raise ValueError(error_msg)
    
    # Validate types
    for key, value in raw_inputs.items():
        if key == 'tax_year':
            if not isinstance(value, int):
                raise ValueError(f"tax_year must be an integer, got {type(value).__name__}")
        elif key == 'filing_status':
            if not isinstance(value, str):
                raise ValueError(f"filing_status must be a string, got {type(value).__name__}")
        else:
            if not isinstance(value, float):
                raise ValueError(f"{key} must be a float, got {type(value).__name__}")
    
    return raw_inputs