# Attribution

## Type

The web shell (`app/static/tokens.css`, `app/static/style.css`, and every
template under `app/templates/` except `app/templates/documents/record.html`)
uses OS font stacks — `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
'Helvetica Neue', Arial, 'Noto Sans', sans-serif` for text, `'Iowan Old
Style', 'Palatino Linotype', Palatino, Georgia, serif` for headings and the
statute's own wording, `ui-monospace, SFMono-Regular, 'SF Mono', Menlo,
Consolas, monospace` for hashes and record numbers. These are copied verbatim
from Recourse's `tokens.css` (`--sans`/`--serif`/`--mono`), the shared
internal design language used as the reference for this pass. No font files
are downloaded or embedded for the web shell: every name in the stack is
either resolved by the visitor's OS or falls through to the next, and
Recourse's own stylesheet vendors nothing either — there is no `@font-face`
rule and no Google Fonts link in it. Nothing to licence here.

## The statutory log and the evidence pack

`app/static/record.css` and `app/templates/documents/record.html` are
unchanged by this pass and keep their own, separate font stack, embedded so
the rendered PDF looks the same regardless of what is installed on the
machine that renders it (typically a server, not the visitor's browser).
That requirement predates this redesign and has nothing to do with which web
app the shell resembles, so these files were left alone. The four font files
under `app/static/fonts/` are still on disk and still in use, only by
`record.css`:

- **Public Sans**, SIL Open Font License 1.1. U.S. Web Design System
  typeface, drawn for government forms. Carries labels and running text in
  the printed documents.
- **Source Serif 4**, SIL Open Font License 1.1. Carries headings and the
  statute's own wording in the printed documents.
- **IBM Plex Mono**, SIL Open Font License 1.1 (weights 400 and 600). Carries
  hashes and record numbers in the printed documents.

Full licence text for the SIL Open Font License 1.1: https://openfontlicense.org
