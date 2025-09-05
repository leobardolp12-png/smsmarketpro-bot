import random
PRICE_PER_SMS = 10
def calculate_total(quantity, price_per_sms=PRICE_PER_SMS):
    q = int(quantity)
    price = float(price_per_sms)
    if q >= 25:
        price = price - 1
    return round(q * price, 2), round(price, 2)

def generate_captcha_options():
    a = random.randint(100, 999)
    b = random.randint(10, 99)
    correct = a + b
    s = str(correct)
    if len(s) < 3:
        s = s.zfill(3)
    prefix = s[:-1]
    last = int(s[-1])
    opts = []
    opts.append(int(f"{prefix}{last}"))
    for _ in range(2):
        wrong_last = (last + random.randint(1, 8)) % 10
        opts.append(int(f"{prefix}{wrong_last}")) 
    random.shuffle(opts)
    return (a, b, opts, correct)
