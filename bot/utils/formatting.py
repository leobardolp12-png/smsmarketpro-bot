# formatting.py

def format_currency(amount: float) -> str:
    """Formatea un número como moneda en pesos."""
    return f"${amount:,.2f}"

def calculate_total(qty: int, unit_price: float) -> tuple[float, float]:
    """Calcula total y precio unitario."""
    total = qty * unit_price
    return total, unit_price
