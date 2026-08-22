#!/usr/bin/env python3
"""
Audit the inline-style channel that stylesheet tooling cannot see.

css_audit.py reads stylesheets. It cannot see style="..." attributes or React
style={{...}} props, and in this repo that is ~2,450 declarations — the audit's
single largest coverage gap.

Inline styles rarely declare their own background, so an exact ratio usually is not
available statically. This reports what IS decidable:

  FAIL-ALL      the foreground fails 4.5:1 on every surface in the palette, so it
                fails wherever it is used. A definite defect, no DOM needed.
  CONDITIONAL   passes on some surfaces, fails on others. Needs a rendered check.
  PASS-ALL      clears 4.5:1 on every surface. Safe wherever it lands.
  PAIRED        the declaration sets both colour and background — measured exactly.

Usage:  python3 inline-contrast.py <file-or-dir> [more...]
"""
import re, sys, pathlib, collections

def lum(rgb):
    def f(c):
        c /= 255
        return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055) ** 2.4
    r, g, b = (f(x) for x in rgb)
    return .2126*r + .7152*g + .0722*b

def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi+.05)/(lo+.05), 2)

NAMED = {"white": (255,255,255), "black": (0,0,0), "red": (255,0,0),
         "grey": (128,128,128), "gray": (128,128,128), "transparent": None}

def parse_colour(v):
    v = v.strip().rstrip(';').strip()
    if v.lower() in NAMED:
        return NAMED[v.lower()]
    m = re.fullmatch(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})', v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = ''.join(c*2 for c in h)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r'rgba?\(([^)]*)\)', v)
    if m:
        parts = [p.strip() for p in m.group(1).replace('/', ',').split(',')]
        try:
            nums = [float(p.rstrip('%')) for p in parts[:3]]
        except ValueError:
            return None
        if len(parts) > 3:
            try:
                if float(parts[3]) < 0.95:
                    return None          # translucent: cannot decide statically
            except ValueError:
                pass
        return tuple(int(n) for n in nums)
    return None                          # var(), gradients, currentColor, inherit

# Surfaces a foreground can plausibly land on. Split light/dark: this app has dark
# chrome (header, sidenav, modal headers) as well as light content, and a light
# foreground that fails on every LIGHT surface is usually correct on the dark chrome
# rather than broken. Only a colour that fails on both families is a definite defect.
LIGHT_SURFACES = {
    "--surface #ffffff": (255,255,255), "--bg #f4f8fc": (244,248,252),
    "--surface-2 #f0f5fa": (240,245,250), "--accent-light #e0f0fa": (224,240,250),
    "--ok-bg #d4f0e3": (212,240,227), "--warn-bg #fff3cd": (255,243,205),
    "sa-scope-bar #eef4fa": (238,244,250), "chip #f0f0f0": (240,240,240),
}
DARK_SURFACES = {
    "--dark #002f65": (0,47,101), "nav top #001b3d": (0,27,61),
    "nav bottom #002550": (0,37,80), "nav active #003a7a": (0,58,122),
}
SURFACES = {**LIGHT_SURFACES, **DARK_SURFACES}

def extract(path):
    """yield (file, line, decls-dict) for every inline style declaration block"""
    text = path.read_text(errors="replace")
    for m in re.finditer(r'style="([^"]*)"', text):          # HTML attribute
        line = text.count("\n", 0, m.start()) + 1
        yield path, line, m.group(1)
    for m in re.finditer(r'style=\{\{([^}]*)\}\}', text):     # React prop
        line = text.count("\n", 0, m.start()) + 1
        body = m.group(1)
        body = re.sub(r'(\w+)\s*:', lambda mm: re.sub(r'([A-Z])', r'-\1', mm.group(1)).lower()+':', body)
        body = body.replace('"', '').replace("'", '')
        # React style objects separate properties with COMMAS, not semicolons, and the
        # rest of this module parses CSS text. Convert only the commas that sit outside
        # parentheses, so rgba(0,0,0,.5) and font stacks survive intact. Getting this
        # wrong silently swallows every property after the first and reports a clean bill.
        out, depth = [], 0
        for ch in body:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)
            out.append(';' if (ch == ',' and depth == 0) else ch)
        yield path, line, ''.join(out)

def main(paths):
    files = []
    for p in paths:
        p = pathlib.Path(p)
        files += [p] if p.is_file() else [q for q in p.rglob('*')
                                          if q.suffix in ('.html', '.tsx', '.ts', '.js')]
    fails, cond, paired_fail = [], [], []
    seen_fg = collections.Counter()
    n_decl = n_fg = 0
    for f in files:
        for path, line, body in extract(f):
            n_decl += 1
            fg_m = re.search(r'(?<![-\w])color\s*:\s*([^;]+)', body)
            bg_m = re.search(r'background(?:-color)?\s*:\s*([^;]+)', body)
            if not fg_m:
                continue
            fg = parse_colour(fg_m.group(1))
            if fg is None:
                continue
            n_fg += 1
            seen_fg[fg_m.group(1).strip()] += 1
            if bg_m:
                bg = parse_colour(bg_m.group(1))
                if bg is not None:
                    r = ratio(fg, bg)
                    if r < 4.5:
                        paired_fail.append((path.name, line, fg_m.group(1).strip(),
                                            bg_m.group(1).strip(), r))
                    continue
            light = max(ratio(fg, s) for s in LIGHT_SURFACES.values())
            dark  = max(ratio(fg, s) for s in DARK_SURFACES.values())
            best  = max(light, dark)
            worst = min(min(ratio(fg, s) for s in LIGHT_SURFACES.values()),
                        min(ratio(fg, s) for s in DARK_SURFACES.values()))
            if best < 4.5:
                # fails on the best light surface AND the best dark one
                fails.append((path.name, line, fg_m.group(1).strip(), best))
            elif worst < 4.5:
                fam = "light-only" if light >= 4.5 > dark else ("dark-only" if dark >= 4.5 > light else "mixed")
                cond.append((path.name, line, fg_m.group(1).strip(), worst, best, fam))
    print(f"COVERAGE  {len(files)} file(s), {n_decl} inline style declarations, "
          f"{n_fg} with a resolvable foreground colour")
    print(f"          {n_decl - n_fg} carry no decidable colour "
          f"(no colour set, or var()/gradient/translucent)\n")
    print(f"PAIRED FAILURES — colour and background in the same declaration: {len(paired_fail)}")
    for fn, ln, fg, bg, r in sorted(paired_fail, key=lambda x: x[4])[:25]:
        print(f"   {r:>5}:1  {fn}:{ln}  {fg} on {bg}")
    print(f"\nFAIL-ALL — fails 4.5:1 on every surface in the palette: {len(fails)}")
    agg = collections.Counter((fg, round(best, 2)) for _, _, fg, best in fails)
    for (fg, best), c in agg.most_common():
        print(f"   {c:>4} site(s)  {fg:<24} best case {best}:1")
    print(f"\nCONDITIONAL — depends on the surface it lands on: {len(cond)}")
    agg2 = collections.Counter((fg, fam) for _, _, fg, _, _, fam in cond)
    for (fg, fam), c in agg2.most_common(12):
        ex = next(x for x in cond if x[2] == fg)
        note = {"light-only": "safe on light surfaces only",
                "dark-only":  "safe on the dark chrome only",
                "mixed":      "safe on some of each"}[fam]
        print(f"   {c:>4} site(s)  {fg:<22} {ex[4]}:1 best — {note}")
    return 1 if (fails or paired_fail) else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["."]))
