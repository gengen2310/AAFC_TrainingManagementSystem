import re, sys, csv, pathlib
ROOT = pathlib.Path("/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source/frontend/src/styles")

def parse_block(text, start):
    """return dict of --var: value inside the brace block starting at index of '{'"""
    depth=0; i=start; out={}
    while i < len(text):
        if text[i]=='{': depth+=1
        elif text[i]=='}':
            depth-=1
            if depth==0: break
        i+=1
    body=text[start+1:i]
    for m in re.finditer(r'(--[\w-]+)\s*:\s*([^;]+);', body):
        out[m.group(1)]=m.group(2).strip()
    return out

tok = (ROOT/"tokens.css").read_text()
contexts={}
# strip @media blocks before harvesting the base :root, so media overrides
# do not leak into the light theme (they are separate contexts)
def strip_at_media(t):
    out=[]; i=0
    while i < len(t):
        m=re.compile(r'@media[^{]*\{').search(t, i)
        if not m: out.append(t[i:]); break
        out.append(t[i:m.start()])
        depth=0; j=m.end()-1
        while j < len(t):
            if t[j]=='{': depth+=1
            elif t[j]=='}':
                depth-=1
                if depth==0: break
            j+=1
        i=j+1
    return ''.join(out)
tok_base = strip_at_media(tok)
base={}
for m in re.finditer(r'(?<![\w\]"])\:root\s*\{', tok_base):
    base.update(parse_block(tok_base, m.end()-1))
assert base.get('--warn','').strip()=='#c97a00', f"base contaminated: --warn={base.get('--warn')}"
print("base sanity: --warn=%s --primary=%s --surface=%s" % (base.get('--warn'),base.get('--primary'),base.get('--surface')))
contexts['light']=dict(base)
for name,pat in [('dark', r'html\[data-theme="dark"\]\s*\{'),
                 ('hc',   r'html\[data-theme="hc"\]\s*\{')]:
    m=re.search(pat, tok)
    d=dict(base); d.update(parse_block(tok, m.end()-1)); contexts[name]=d
m=re.search(r'@media \(prefers-contrast: more\)', tok)
sub=tok[m.start():]
m2=re.search(r':root\s*\{', sub)
d=dict(base); d.update(parse_block(sub, m2.end()-1)); contexts['contrast-more']=d

def hexrgb(h):
    h=h.strip().lstrip('#')
    if len(h)==3: h=''.join(c*2 for c in h)
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def resolve(val, vars, depth=0):
    if depth>12: return None
    val=val.strip()
    m=re.fullmatch(r'var\((--[\w-]+)(?:\s*,[^)]*)?\)', val)
    if m:
        nxt=vars.get(m.group(1))
        return resolve(nxt, vars, depth+1) if nxt else None
    m=re.fullmatch(r'color-mix\(in srgb,\s*(.+?)\s+([\d.]+)%\s*,\s*(.+?)\s*\)', val)
    if m:
        a=resolve(m.group(1),vars,depth+1); b=resolve(m.group(3),vars,depth+1)
        if not a or not b: return None
        p=float(m.group(2))/100
        return tuple(round(a[i]*p + b[i]*(1-p)) for i in range(3))
    if re.fullmatch(r'#[0-9a-fA-F]{3,8}', val): return hexrgb(val[:7])
    if val in ('white','#fff'): return (255,255,255)
    if val=='black': return (0,0,0)
    return None

def lum(rgb):
    def f(c):
        c=c/255
        return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    r,g,b=[f(x) for x in rgb]
    return 0.2126*r+0.7152*g+0.0722*b

def ratio(a,b):
    la,lb=lum(a),lum(b)
    hi,lo=max(la,lb),min(la,lb)
    return round((hi+0.05)/(lo+0.05),2)

def tohex(rgb): return '#%02x%02x%02x'%rgb

# gather text rules: selector -> (color, background, font-size, weight)
rules=[]
for f in sorted(ROOT.glob("*.css")):
    if f.name=="print.css": continue
    css=f.read_text()
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
    for m in re.finditer(r'([^{}@]+)\{([^{}]*)\}', css):
        sel=' '.join(m.group(1).split()); body=m.group(2)
        c=re.search(r'(?<![-\w])color\s*:\s*([^;]+)', body)
        bg=re.search(r'background(?:-color)?\s*:\s*([^;]+)', body)
        fs=re.search(r'font-size\s*:\s*([\d.]+)px', body)
        fw=re.search(r'font-weight\s*:\s*(\d+)', body)
        if c: rules.append((f.name, sel, c.group(1).strip(),
                            bg.group(1).strip() if bg else None,
                            float(fs.group(1)) if fs else None,
                            int(fw.group(1)) if fw else None))
print(f"text-bearing rules with an explicit color: {len(rules)}")

out=[]; unresolved=[]
for fname, sel, cval, bgval, fs, fw in rules:
    for ctx, vars in contexts.items():
        fg=resolve(cval, vars)
        if fg is None:
            unresolved.append((ctx,fname,sel,cval,bgval,'fg-unresolved')); continue
        if bgval:
            bg=resolve(bgval, vars)
            how='same-rule'
            if bg is None:
                unresolved.append((ctx,fname,sel,cval,bgval,'bg-unresolved')); continue
            bgs=[(bg,how)]
        else:
            bgs=[]
            for s in ('--surface','--background'):
                b=resolve(f'var({s})', vars)
                if b: bgs.append((b, f'assumed {s}'))
        size = fs if fs else 13.0     # [DERIVED] project body size when the rule is silent
        weight = fw if fw else 400
        pt = size*0.75                # px -> pt
        large = pt>=18 or (pt>=14 and weight>=700)
        need = 3.0 if large else 4.5
        for bg,how in bgs:
            r=ratio(fg,bg)
            out.append(dict(context=ctx,file=fname,selector=sel[:60],fg=tohex(fg),bg=tohex(bg),
                            px=size,weight=weight,large=large,required=need,ratio=r,
                            result='PASS' if r>=need else 'FAIL',how=how,
                            size_known='yes' if fs else 'no'))

import csv
with open(f"{sys.argv[0].rsplit('/',1)[0]}/planning-text-register.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

from collections import Counter
print(f"\nCOVERAGE: {len(out)} (rule x context x background) evaluations across {len(contexts)} appearance contexts")
print("  per context:", dict(Counter(o['context'] for o in out)))
print("  unresolved :", len(unresolved), dict(Counter(u[5] for u in unresolved)))
print("  results    :", dict(Counter(o['result'] for o in out)))
print("  same-rule pairs (high confidence):", sum(1 for o in out if o['how']=='same-rule'))

fails=[o for o in out if o['result']=='FAIL' and o['how']=='same-rule']
print(f"\n### FAILURES on same-rule pairs only ({len(fails)}) ###")
seen=set()
for o in sorted(fails,key=lambda o:o['ratio']):
    k=(o['selector'],o['fg'],o['bg'])
    if k in seen: continue
    seen.add(k)
    sz=f"{o['px']:.0f}px/{o['weight']}" + ("" if o['size_known']=='yes' else "*")
    print(f"  {o['ratio']:>5}:1 need {o['required']}  [{o['context']:13}] {o['selector'][:44]:44} {o['fg']} on {o['bg']}  {sz}")
print("  (* = font-size not declared in rule; assumed 13px [DERIVED])")
