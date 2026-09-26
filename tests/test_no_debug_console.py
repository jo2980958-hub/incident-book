"""The statutory record does not ship with a console attached to it.

`app/server.py` ran `application.run(debug=True, port=5057)`. Flask's debug mode
turns on the Werkzeug debugger, which is an interactive Python console served
over HTTP by the process that holds `instance/incident_book.db` -- a five-year
violent incident log under Labor Code 6401.9(f)(3) -- together with every clip
and snapshot fetched for it. It also reloads on source change and prints
tracebacks, including the framed model text this app is careful never to render.

Nothing about that is a scoring problem either. It is the single largest hole in
the app and it is one keyword wide.

This is a source-level assertion rather than a behavioural one on purpose. The
flag lives on the `__main__` branch, so no test can reach it by calling
`create_app()`, and a test that cannot reach the defect is how it survived.
"""

from __future__ import annotations

import ast
import pathlib

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


def _debug_keywords() -> list[tuple[str, int, object]]:
    """Every `debug=` keyword argument passed anywhere in the app package."""
    found = []
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "debug":
                    value = getattr(keyword.value, "value", keyword.value)
                    found.append((path.name, node.lineno, value))
    return found


def test_no_module_in_the_app_turns_the_debugger_on():
    turned_on = [entry for entry in _debug_keywords() if entry[2] is not False]
    assert turned_on == [], f"debug is enabled at {turned_on}"


def test_the_search_actually_found_the_run_call():
    """Non-vacuity. An empty list of violations means nothing unless the walk is
    known to have walked: the app package has files, and `debug=` is genuinely
    passed somewhere, so the assertion above is about a real call site."""
    assert len(list(APP_DIR.rglob("*.py"))) > 20
    keywords = _debug_keywords()
    assert keywords, "no debug= keyword found at all -- the AST walk is not looking where it thinks"
    assert any(name == "server.py" for name, _, _ in keywords)


def test_the_flag_is_a_literal_and_not_an_environment_lookup():
    """`debug=os.environ.get("DEBUG")` would satisfy the test above and ship the
    console to anybody who sets a variable. The value has to be readable off the
    page."""
    for name, lineno, value in _debug_keywords():
        assert isinstance(value, bool), f"{name}:{lineno} computes its debug flag"
