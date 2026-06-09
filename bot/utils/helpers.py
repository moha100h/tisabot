FA = '۰۱۲۳۴۵۶۷۸۹'
EN = '0123456789'
_FA2EN = str.maketrans(FA, EN)

def to_int(text: str) -> int | None:
    t = text.replace(',','').replace('،','').translate(_FA2EN).strip()
    return int(t) if t.isdigit() else None

def norm_phone(text: str) -> str:
    t = text.translate(_FA2EN).strip()
    if t.startswith('+98'): t = '0' + t[3:]
    if t.startswith('98') and len(t) == 12: t = '0' + t[2:]
    return t

def fmt(n: int) -> str:
    return f'{n:,}'