def format_currency(amount: float) -> str:
    """Formatea cantidades en formato $1,234.56 con separadores y dos decimales."""
    return f"${amount:,.2f}"
