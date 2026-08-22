import re,sys,pathlib,csv
# Estimate rendered box for rules that look interactive.
# height ~= font-size*line-height + padding-top + padding-bottom + 2*border
INTERACTIVE = re.compile(r'(^|[\s,>])(button|a|\.btn|\.nav-item|\.nav-subitem|\.chip|\.pill|\.tab|\.pw-chip|input|select|textarea|\[role="button"\]|\.ht\b|\.close|\.icon-btn|\.row-act|-btn\b|-act\b|-toggle\b)', re.I)

def num(m, d=0.0): return float(m.group(1)) if m else d

def pad(body, axis):
    m=re.search(r'(?<![-\w])padding\s*:\s*([^;]+)', body)
    if m:
        parts=[p for p in m.group(1).split() if p.endswith('px') or p=='0']
        v=[float(p.replace('px','') or 0) for p in parts] if parts else []
        if not v: return None
        if len(v)==1: t=b=l=r=v[0]
        elif len(v)==2: t=b=v[0]; l=r=v[1]
        elif len(v)==3: t=v[0]; l=r=v[1]; b=v[2]
        else: t,r,b,l=v[0],v[1],v[2],v[3]
        return (t+b) if axis=='y' else (l+r)
    if axis=='y':
        a=re.search(r'padding-top\s*:\s*([\d.]+)px',body); c=re.search(r'padding-bottom\s*:\s*([\d.]+)px',body)
    else:
        a=re.search(r'padding-left\s*:\s*([\d.]+)px',body); c=re.search(r'padding-right\s*:\s*([\d.]+)px',body)
    if a or c: return num(a)+num(c)
    return None

rows=[]
for path in sys.argv[1:]:
    css=pathlib.Path(path).read_text(errors="replace")
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
    for m in re.finditer(r'([^{}@]+)\{([^{}]*)\}', css):
        sel=' '.join(m.group(1).split()); body=m.group(2)
        if not INTERACTIVE.search(sel): continue
        if ':hover' in sel or ':focus' in sel or '::' in sel: continue
        h  = re.search(r'(?<![-\w])height\s*:\s*([\d.]+)px', body)
        mh = re.search(r'min-height\s*:\s*([\d.]+)px', body)
        w  = re.search(r'(?<![-\w])width\s*:\s*([\d.]+)px', body)
        mw = re.search(r'min-width\s*:\s*([\d.]+)px', body)
        fs = re.search(r'font-size\s*:\s*([\d.]+)px', body)
        lh = re.search(r'line-height\s*:\s*([\d.]+)(?!px)', body)
        py, px_ = pad(body,'y'), pad(body,'x')
        if h: H=float(h.group(1)); src='height'
        elif mh: H=float(mh.group(1)); src='min-height'
        elif fs and py is not None:
            H=float(fs.group(1))*(float(lh.group(1)) if lh else 1.4)+py; src='fs+pad'
        else: continue
        W = float(w.group(1)) if w else (float(mw.group(1)) if mw else None)
        rows.append(dict(file=pathlib.Path(path).name, selector=sel[:52],
                         height=round(H,1), width=(round(W,1) if W else ''),
                         basis=src,
                         pointer='PASS' if H>=28 else 'FAIL',
                         touch  ='PASS' if H>=44 else 'FAIL'))
w=csv.DictWriter(sys.stdout,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
