"""D11 (2026-10-11): HTML-escaped values inside inline JS string literals.

The Main TMS builds handlers like  onclick="cpOpenEdit('${esc(ph.name)}')".
esc() is HTML escaping: it turns ' into &#39;, and the browser decodes that
back to ' while parsing the attribute, before the JavaScript runs. So a name
such as  x');window.__pwned=1;('  closed the string literal and ran as the
user who clicked (reproduced in Chromium on a custom training phase).

A value interpolated into a handler's JavaScript must go through jsq(), which
emits a complete, HTML-escaped JSON string literal: onclick="f(${jsq(v)})".
This scan forbids the two quoted-esc forms inside any inline handler. Outside
handlers (element text, ordinary attributes) esc() is still the right tool.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "connected-frontend"
HANDLER = re.compile(r"\bon[a-z]+=")   # every inline handler attribute
# '${esc(x)}'  (template literal)  and  \''+esc(x)+'\'  (concatenation)
QUOTED_ESC = re.compile(r"'\$\{esc\(|\\''\+esc\(|'[^'\s]*-\$\{esc\(")
# Raw JSON in a handler: a string value's " ends the attribute (D12, the
# conflict Override link) and a ' ends a single-quoted one (holiday edit).
RAW_JSON = re.compile(r"(?<!esc\()JSON\.stringify\(")
# Free-text fields interpolated with no escaping at all (D11: curriculum code).
RAW_TEXT = re.compile(r"'\$\{[\w.]+\.(?:code|name|title|display_name|description)\}'")


def _sources():
    return sorted((ROOT / "js").glob("*.js")) + [ROOT / "index.html"]


def test_no_html_escaped_value_inside_an_inline_handler_string():
    offenders = []
    for path in _sources():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            first = HANDLER.search(line)
            if not first:
                continue
            for rule, rx in (("quoted esc()", QUOTED_ESC), ("raw JSON", RAW_JSON), ("raw text", RAW_TEXT)):
                if rx.search(line, first.end()):
                    offenders.append(f"{path.relative_to(ROOT)}:{n} ({rule})")
    assert offenders == [], (
        f"{len(offenders)} inline handler(s) quote esc() output; use ${{jsq(value)}} instead:\n"
        + "\n".join(offenders))


def test_jsq_helper_exists_and_wraps_a_json_literal_in_html_escaping():
    utils = (ROOT / "js" / "utils.js").read_text(encoding="utf-8")
    assert re.search(r"function jsq\(v\)\{return esc\(JSON\.stringify\(", utils), \
        "jsq() must be esc(JSON.stringify(String(v))) so the attribute decodes to a JS string literal"


def test_no_raw_json_interpolated_into_markup():
    """${JSON.stringify(x)} inside a template literal lands in markup, usually
    a handler built across several lines (the D12 Override link, whose onclick=
    is on the line before), so the per-line handler scan cannot see it. JSON in
    markup is always wrapped: ${esc(JSON.stringify(x))}."""
    offenders = [f"{p.relative_to(ROOT)}:{n}"
                 for p in _sources()
                 for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                 if "${JSON.stringify(" in line]
    assert offenders == [], "\n".join(offenders)
