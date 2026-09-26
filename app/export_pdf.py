"""PDF, for the copy that gets attached to an email or put in a case file.

WeasyPrint rather than a headless browser, because the document's sheet
numbering depends on the CSS Paged Media features (``@page`` margin boxes,
``counter(pages)``, ``string-set``) that Chromium's print pipeline does not
implement. "Sheet 2 of 7" in the footer of every sheet is a tamper control: a
single unnumbered sheet can be removed from a set and nobody can tell. Getting
that by pre-paginating in the DOM would mean doing the layout twice, once in
CSS and once in Python, and the two would drift.

It is an optional import on purpose. WeasyPrint needs Pango and Cairo on the
machine, a shop kiosk may not have them, and nothing in the statute requires a
PDF. Where it is missing the HTML documents still render and still print from
any browser, and the route says which of the two happened rather than handing
back a file that will not open.
"""

from __future__ import annotations

from .config import APP_DIR

STATIC = (APP_DIR / "static").resolve()
STATIC_URL = f"file://{STATIC}/"


class PdfUnavailable(RuntimeError):
    """WeasyPrint is not installed, or could not render. The caller falls back
    to the HTML document, which is the same document."""


def available() -> tuple[bool, str]:
    try:
        import weasyprint

        return True, f"WeasyPrint {weasyprint.__version__}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def to_file_urls(html: str) -> str:
    """Point the document's own ``/static/...`` references at the files that
    shipped with this package.

    The same HTML is served over HTTP, where ``/static/...`` is right. For a
    PDF there is no server, so the references are rewritten to file URLs and
    the renderer is then allowed no protocol except ``file`` and ``data``.
    That is what makes a rendered record a thing built entirely out of files
    that came with the software, with no fetch to anywhere.
    """
    return html.replace('href="/static/', f'href="{STATIC_URL}').replace(
        'src="/static/', f'src="{STATIC_URL}'
    )


def render(html: str) -> bytes:
    """The same document the browser gets, with the fonts embedded, so the
    adjuster's copy and ours are one document rather than two with one record
    number on them."""
    try:
        from weasyprint import HTML
        from weasyprint.urls import URLFetcher
    except Exception as exc:
        raise PdfUnavailable(f"WeasyPrint is not available: {exc}") from exc
    try:
        return HTML(
            string=to_file_urls(html),
            base_url=STATIC_URL,
            url_fetcher=URLFetcher(allowed_protocols=["file", "data"]),
        ).write_pdf()
    except Exception as exc:
        raise PdfUnavailable(f"WeasyPrint could not render: {exc}") from exc
