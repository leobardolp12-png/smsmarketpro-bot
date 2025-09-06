# captcha.py
import random

def generate_captcha_options() -> tuple[int, int, list[int], int]:
    """Genera un captcha simple de suma con opciones."""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    correct = a + b
    options = [correct, correct + 1, correct - 1, correct + 2]
    random.shuffle(options)
    return a, b, options, correct
