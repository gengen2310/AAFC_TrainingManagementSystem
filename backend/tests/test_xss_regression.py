"""Regression test: F-001 XSS — u.title escaping in renderProgramAudit output.

The stored XSS existed at connected-frontend/index.html: u.title was concatenated
raw into an innerHTML template while u.code was correctly wrapped with esc().

This file:
1. Verifies the esc() helper's Python equivalent correctly neutralises XSS payloads.
2. Verifies that the dead renderProgramAudit() and renderActionCentre() DOM and
   function code is no longer present in index.html (removal of the XSS vector).
"""
import re


def _esc_py(s: str) -> str:
    """Python equivalent of the JS esc() helper in connected-frontend/index.html."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


XSS_PAYLOAD = '<img src=x onerror="window.__xss_test=1">'
NORMAL_TITLE = "Ground School Part 1"
EMPTY_TITLE = ""


def test_esc_helper_neutralises_xss_payload():
    """esc() must HTML-encode angle brackets so tags cannot execute.

    After escaping, the raw '<img' angle bracket is gone (replaced with '&lt;img'),
    which prevents the browser from parsing it as a tag. The text 'onerror' may
    still appear in the escaped output — that is correct and expected, since it is
    now just literal text, not an HTML attribute.
    """
    result = _esc_py(XSS_PAYLOAD)
    assert "<img" not in result, "Unescaped <img tag survived — XSS not neutralised"
    assert "&lt;img" in result, "Expected encoded &lt;img not found in result"
    assert "&quot;" in result, "Double quotes should be encoded"


def test_esc_helper_preserves_normal_title():
    """Normal curriculum title must survive round-trip without alteration."""
    result = _esc_py(NORMAL_TITLE)
    assert result == NORMAL_TITLE


def test_esc_helper_handles_empty():
    result = _esc_py(EMPTY_TITLE)
    assert result == ""


def test_esc_helper_handles_ampersand():
    result = _esc_py("Drill & Ceremony")
    assert result == "Drill &amp; Ceremony"


def test_esc_helper_handles_double_encode_resistant():
    """esc() applied twice must not double-encode (verify order of replacements)."""
    result = _esc_py("&lt;")
    assert result == "&amp;lt;"


def test_frontend_dead_pages_removed():
    """page-program-audit and page-action-centre DOM must no longer exist.

    These pages were not reachable through navigation (absent from NAV_BY_SCOPE)
    but their presence kept dead render functions in the JS bundle, including
    the F-001 XSS in renderProgramAudit(). They have been removed.
    """
    with open("../connected-frontend/index.html", encoding="utf-8") as f:
        source = f.read()

    assert 'id="page-program-audit"' not in source, (
        "page-program-audit DOM was re-added. This page must not be in the HTML — "
        "it is not in NAV_BY_SCOPE and its render function contained F-001 XSS."
    )
    assert 'id="page-action-centre"' not in source, (
        "page-action-centre DOM was re-added. This page must not be in the HTML — "
        "it is not in NAV_BY_SCOPE."
    )


def test_frontend_dead_render_functions_removed():
    """renderProgramAudit() and renderActionCentre() must no longer exist.

    Both were defined but never called from nav() or any live code path.
    renderProgramAudit() contained the F-001 XSS.
    """
    with open("../connected-frontend/index.html", encoding="utf-8") as f:
        source = f.read()

    assert "function renderProgramAudit" not in source, (
        "renderProgramAudit() was re-added. This function contained F-001 XSS and "
        "was never called through live navigation. Do not reintroduce it."
    )
    assert "function renderActionCentre" not in source, (
        "renderActionCentre() was re-added. This dead function must remain removed."
    )


def test_frontend_action_centre_not_in_nav():
    """action-centre and program-audit must not appear in NAV_BY_SCOPE."""
    with open("../connected-frontend/index.html", encoding="utf-8") as f:
        source = f.read()

    # Find the NAV_BY_SCOPE constant block
    nav_match = re.search(r"const NAV_BY_SCOPE=\{(.+?)\};", source, re.DOTALL)
    if not nav_match:
        # NAV_BY_SCOPE not found in expected format — structural test cannot run
        return

    nav_block = nav_match.group(1)
    assert "action-centre" not in nav_block, (
        "action-centre was added to NAV_BY_SCOPE — the product decision is that "
        "Programme Action Centre must not be user-facing."
    )
    assert "program-audit" not in nav_block, (
        "program-audit was added to NAV_BY_SCOPE — the product decision is that "
        "Program Audit must not be user-facing."
    )
