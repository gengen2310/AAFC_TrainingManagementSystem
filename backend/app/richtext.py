"""Allowlist sanitiser for the small amount of formatted text system_admin can author.

Help & Reference content and FAQ answers are the only places in the TMS where one
user's HTML is rendered into another user's page. Everything else goes through the
frontend's esc() helper as plain text. That makes this module the single trust
boundary for stored HTML, so it is deliberately strict and deliberately small:

  * an allowlist of tags, not a blocklist of dangerous ones
  * every attribute dropped except href on <a>, and only for schemes we accept
  * unknown tags are unwrapped (their text survives), except script/style/etc.
    whose contents are discarded outright
  * unbalanced markup is repaired, so a stray "</div>" cannot break the page it
    is rendered into

The frontend applies the same allowlist again on render. Sanitising on save alone
would leave anything already stored before this landed unfiltered, and sanitising
on render alone would let a bad value sit in the database waiting for a future
consumer that forgets. Doing both is the point, not redundancy.

Kept to the standard library on purpose: adding bleach/nh3 to requirements for
one text field is a dependency and a supply-chain surface we do not need.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

# Tags a system_admin may use. Matches the toolbar the editor offers -- if you add
# a button there, add the tag here, not the other way round.
ALLOWED_TAGS: frozenset[str] = frozenset({
    "p", "br",
    "h2", "h3", "h4",
    "strong", "em", "u",
    "ul", "ol", "li",
    "a",
    "blockquote",
})

# execCommand and pasted content emit presentational tags. Rewrite rather than drop
# them: the author asked for bold, and <b> is how the browser said it.
TAG_ALIASES: dict[str, str] = {
    "b": "strong",
    "i": "em",
    "strike": "em",
    "h1": "h2",   # the page already owns its <h1>; a second one breaks the outline
    "h5": "h4",
    "h6": "h4",
    "div": "p",
}

# Tags whose *contents* are dropped too, not just the tag itself.
DROP_CONTENT_TAGS: frozenset[str] = frozenset({
    "script", "style", "template", "iframe", "object", "embed", "svg", "math",
    "noscript", "title", "head",
})

VOID_TAGS: frozenset[str] = frozenset({"br"})

# Only href on <a> survives. No id, no class, no style, and no on* handler can
# reach the output because nothing outside this map is ever emitted.
ALLOWED_ATTRS: dict[str, frozenset[str]] = {"a": frozenset({"href"})}

_SAFE_SCHEMES: tuple[str, ...] = ("http://", "https://", "mailto:")

MAX_LENGTH = 100_000


def _safe_href(value: str | None) -> str | None:
    """Return the href if we are willing to emit it, else None.

    Rejects javascript:, data:, vbscript: and anything else not explicitly listed.
    Relative links must start with "/" -- a bare "foo" would resolve against
    whatever path the page happens to be on.
    """
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    # Control characters and whitespace inside a scheme ("java\tscript:") are
    # ignored by browsers, so strip them before deciding.
    collapsed = "".join(c for c in raw if c.isprintable() and not c.isspace()).lower()
    if collapsed.startswith("/") and not collapsed.startswith("//"):
        return raw
    if collapsed.startswith("#"):
        return raw
    if any(collapsed.startswith(s) for s in _SAFE_SCHEMES):
        return raw
    return None


class _Sanitiser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open_tags: list[str] = []
        self._suppress_depth = 0
        self._suppressing: str | None = None

    # -- helpers ---------------------------------------------------------
    def _resolve(self, tag: str) -> str:
        tag = tag.lower()
        return TAG_ALIASES.get(tag, tag)

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = tag.lower()
        if self._suppressing is not None:
            if raw == self._suppressing:
                self._suppress_depth += 1
            return
        if raw in DROP_CONTENT_TAGS:
            self._suppressing = raw
            self._suppress_depth = 1
            return

        name = self._resolve(raw)
        if name not in ALLOWED_TAGS:
            return  # unwrap: the tag goes, its text stays

        bits = [name]
        for attr, value in attrs:
            if attr.lower() not in ALLOWED_ATTRS.get(name, frozenset()):
                continue
            if attr.lower() == "href":
                href = _safe_href(value)
                if href is None:
                    continue
                bits.append(f'href="{escape(href, quote=True)}"')
                # An external link opening in a new tab must not hand the opener
                # over to the destination page.
                if href.lower().startswith(("http://", "https://")):
                    bits.append('rel="noopener noreferrer"')
                    bits.append('target="_blank"')

        if name in VOID_TAGS:
            self.out.append(f"<{' '.join(bits)}>")
            return
        self.out.append(f"<{' '.join(bits)}>")
        self.open_tags.append(name)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = self._resolve(tag)
        if name in VOID_TAGS and self._suppressing is None:
            self.out.append(f"<{name}>")

    def handle_endtag(self, tag: str) -> None:
        raw = tag.lower()
        if self._suppressing is not None:
            if raw == self._suppressing:
                self._suppress_depth -= 1
                if self._suppress_depth <= 0:
                    self._suppressing = None
            return

        name = self._resolve(raw)
        if name not in ALLOWED_TAGS or name in VOID_TAGS:
            return
        if name not in self.open_tags:
            return  # a stray close tag closes nothing
        # Close anything left open inside it, so the output stays well-formed.
        while self.open_tags:
            current = self.open_tags.pop()
            self.out.append(f"</{current}>")
            if current == name:
                break

    def handle_data(self, data: str) -> None:
        if self._suppressing is not None:
            return
        if data:
            self.out.append(escape(data, quote=False))

    def close(self) -> None:  # type: ignore[override]
        super().close()
        while self.open_tags:
            self.out.append(f"</{self.open_tags.pop()}>")

    def result(self) -> str:
        return "".join(self.out)


def sanitize_rich_text(value: str | None) -> str:
    """Return `value` reduced to the allowlist above. Never raises on bad markup."""
    if not value:
        return ""
    if len(value) > MAX_LENGTH:
        value = value[:MAX_LENGTH]
    parser = _Sanitiser()
    parser.feed(value)
    parser.close()
    return parser.result().strip()


def rich_text_to_plain(value: str | None) -> str:
    """Best-effort plain-text rendering, for search and for email notifications."""
    if not value:
        return ""

    class _Strip(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

        def handle_starttag(self, tag: str, attrs) -> None:
            if tag.lower() in {"br", "p", "li", "h2", "h3", "h4", "blockquote"}:
                self.parts.append("\n")

    s = _Strip()
    s.feed(value)
    s.close()
    return " ".join("".join(s.parts).split())
