# Legacy premium calculator ported from the 2009 rating engine (task T3: explain it).
def calc(p, a, z, c, nc):
    b = 0
    if p == "AUTO":
        b = 620.0
    elif p == "HOME":
        b = 410.0
    else:
        b = 300.0
    f = 1.0
    if a < 25:
        f = f * 1.45
    elif a > 70:
        f = f * 1.25
    if z in ("A", "B"):
        f = f * 0.92
    elif z == "D":
        f = f * 1.18
    f = f * (1 + 0.15 * min(c, 4))
    if nc >= 5:
        f = f * 0.85
    elif nc >= 3:
        f = f * 0.93
    r = b * f
    if r < 150:
        r = 150
    return round(r, 2)
