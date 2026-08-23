"""Allowlist sanitiser for system_admin-authored Help & Reference and FAQ content.

This is the only place in the TMS where one user's HTML reaches another user's
page, so the cases below are the trust boundary rather than ordinary unit tests.
"""

import pytest

from app.richtext import rich_text_to_plain, sanitize_rich_text


# ── formatting the author actually asked for survives ─────────────────────────

def test_keeps_the_tags_the_toolbar_emits():
    html = "<h2>Setting up</h2><p>Create a <strong>training year</strong> first.</p>"
    assert sanitize_rich_text(html) == html


def test_rewrites_presentational_tags_the_browser_emits():
    # execCommand('bold') produces <b>, not <strong>. The author asked for bold,
    # so rewrite rather than drop.
    assert sanitize_rich_text("<b>bold</b> and <i>italic</i>") == "<strong>bold</strong> and <em>italic</em>"


def test_demotes_h1_so_the_page_outline_keeps_one_top_heading():
    assert sanitize_rich_text("<h1>Title</h1>") == "<h2>Title</h2>"


def test_keeps_lists_and_underline():
    html = "<ul><li>One</li><li><u>Two</u></li></ul>"
    assert sanitize_rich_text(html) == html


def test_keeps_line_breaks():
    assert sanitize_rich_text("a<br>b") == "a<br>b"
    assert sanitize_rich_text("a<br/>b") == "a<br>b"


# ── script execution ─────────────────────────────────────────────────────────

def test_drops_script_tag_and_its_contents():
    out = sanitize_rich_text("<p>Hello</p><script>alert(1)</script>")
    assert out == "<p>Hello</p>"
    assert "alert" not in out


@pytest.mark.parametrize("tag", ["style", "iframe", "object", "embed", "svg", "template", "noscript"])
def test_drops_other_content_bearing_tags_entirely(tag):
    out = sanitize_rich_text(f"<p>ok</p><{tag}>PAYLOAD</{tag}>")
    assert "PAYLOAD" not in out
    assert out == "<p>ok</p>"


def test_drops_event_handler_attributes():
    out = sanitize_rich_text('<p onclick="steal()">text</p>')
    assert out == "<p>text</p>"
    assert "onclick" not in out


def test_drops_every_attribute_that_is_not_an_allowed_href():
    out = sanitize_rich_text('<p id="x" class="y" style="position:fixed" data-z="1">text</p>')
    assert out == "<p>text</p>"


def test_unwraps_img_so_no_onerror_payload_can_land():
    out = sanitize_rich_text('<img src=x onerror="alert(1)">caption')
    assert "<img" not in out
    assert "onerror" not in out
    assert "caption" in out


def test_is_case_insensitive():
    out = sanitize_rich_text("<SCRIPT>alert(1)</SCRIPT><P>ok</P>")
    assert out == "<p>ok</p>"


# ── link schemes ─────────────────────────────────────────────────────────────

def test_keeps_relative_and_https_links():
    assert sanitize_rich_text('<a href="/planning">Planning</a>') == '<a href="/planning">Planning</a>'
    out = sanitize_rich_text('<a href="https://aafc.org.au">AAFC</a>')
    assert 'href="https://aafc.org.au"' in out


def test_external_links_get_noopener():
    # An external link opened in a new tab must not hand window.opener over.
    out = sanitize_rich_text('<a href="https://example.org">x</a>')
    assert 'rel="noopener noreferrer"' in out
    assert 'target="_blank"' in out


def test_relative_links_do_not_get_target_blank():
    out = sanitize_rich_text('<a href="/planning">x</a>')
    assert "target" not in out


@pytest.mark.parametrize("href", [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "java\tscript:alert(1)",
    "java\nscript:alert(1)",
    " javascript:alert(1)",
    "data:text/html;base64,PHNjcmlwdD4=",
    "vbscript:msgbox(1)",
    "//evil.example.com",
    "file:///etc/passwd",
])
def test_rejects_dangerous_hrefs_but_keeps_the_link_text(href):
    out = sanitize_rich_text(f'<a href="{href}">click me</a>')
    assert "href" not in out
    assert "click me" in out


# ── malformed markup cannot break the host page ──────────────────────────────

def test_closes_tags_the_author_left_open():
    assert sanitize_rich_text("<p>unclosed") == "<p>unclosed</p>"
    assert sanitize_rich_text("<ul><li>a") == "<ul><li>a</li></ul>"


def test_ignores_a_stray_closing_tag():
    assert sanitize_rich_text("</div>text</p>") == "text"


def test_unwraps_unknown_tags_but_keeps_their_text():
    assert sanitize_rich_text("<div><span>kept</span></div>") == "<p>kept</p>"
    assert sanitize_rich_text("<marquee>kept</marquee>") == "kept"


def test_escapes_bare_angle_brackets_and_ampersands():
    out = sanitize_rich_text("<p>5 < 6 & 7 > 2</p>")
    assert "&lt;" in out and "&amp;" in out


def test_does_not_double_escape_existing_entities():
    assert sanitize_rich_text("<p>Tom &amp; Jerry</p>") == "<p>Tom &amp; Jerry</p>"


def test_survives_a_second_pass_unchanged():
    # Render-time sanitising runs over already-sanitised storage, so the function
    # has to be idempotent or content degrades on every save.
    html = '<h2>T</h2><p>a <strong>b</strong> <a href="/x">l</a></p><ul><li>i</li></ul>'
    once = sanitize_rich_text(html)
    assert sanitize_rich_text(once) == once


# ── boundaries ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_input_gives_empty_output(value):
    assert sanitize_rich_text(value) == ""


def test_truncates_absurdly_long_input_rather_than_storing_it():
    from app.richtext import MAX_LENGTH
    out = sanitize_rich_text("<p>" + ("a" * (MAX_LENGTH + 5_000)) + "</p>")
    assert len(out) <= MAX_LENGTH + 10


def test_plain_text_rendering_strips_markup_for_search():
    assert rich_text_to_plain("<h2>Title</h2><p>Body <strong>text</strong></p>") == "Title Body text"
    assert rich_text_to_plain("") == ""
