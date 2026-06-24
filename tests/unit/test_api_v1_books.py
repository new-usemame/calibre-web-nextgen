import json
import inspect
import pytest
import flask
from types import SimpleNamespace
from unittest.mock import patch


@pytest.mark.unit
def test_books_list_envelope():
    from cps.api import books as books_mod
    from cps.pagination import Pagination
    bks = [SimpleNamespace(id=1, title="A", series_index="1.0", has_cover=1,
                           authors=[SimpleNamespace(name="Auth")], series=[],
                           data=[SimpleNamespace(format="EPUB")])]
    pag = Pagination(1, 60, 1)
    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/books?page=1"):
        with patch.object(books_mod.calibre_db, "fill_indexpage",
                          return_value=(bks, None, pag)), \
             patch.object(books_mod.config, "config_books_per_page", 60, create=True), \
             patch.object(books_mod.config, "config_read_column", 0, create=True):
            view = inspect.unwrap(books_mod.list_books)  # strip @login_required_if_no_ano
            resp = view()
    data = json.loads(resp.get_data(as_text=True))
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["per_page"] == 60
    assert data["items"][0]["title"] == "A"
    assert data["items"][0]["cover_url"] == "/cover/1/sm"


@pytest.mark.unit
def test_books_list_calls_fill_indexpage_with_join_archive_read_false():
    """Regression: fill_indexpage must be called with join_archive_read=False (6th positional arg).

    When join_archive_read=True, fill_indexpage returns SQLAlchemy Row tuples
    (Book + read/archived columns), not plain Books ORM objects. serialize_book_list_item
    expects plain Books (.id, .title, .authors…) and raises AttributeError on Row tuples.
    This test pins the call signature so a regression back to True fails fast.
    """
    from cps.api import books as books_mod
    from cps.pagination import Pagination
    import inspect
    from unittest.mock import patch

    bks = [SimpleNamespace(id=1, title="B", series_index="1.0", has_cover=0,
                           authors=[SimpleNamespace(name="Auth")], series=[], data=[])]
    pag = Pagination(1, 60, 1)

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/books"):
        with patch.object(books_mod.calibre_db, "fill_indexpage",
                          return_value=(bks, None, pag)) as mock_fill, \
             patch.object(books_mod.config, "config_books_per_page", 60, create=True), \
             patch.object(books_mod.config, "config_read_column", 0, create=True):
            view = inspect.unwrap(books_mod.list_books)
            view()

    call_args = mock_fill.call_args
    # 6th positional arg (index 5) is join_archive_read; must be False
    assert call_args is not None, "fill_indexpage was never called"
    positional = call_args.args
    assert len(positional) >= 6, (
        f"Expected ≥6 positional args to fill_indexpage, got {len(positional)}: {positional}"
    )
    assert positional[5] is False, (
        f"join_archive_read (arg[5]) must be False to return plain Books ORM objects, "
        f"got {positional[5]!r} — True causes Row tuples that break serialize_book_list_item"
    )


@pytest.mark.unit
def test_list_books_sort_abc():
    """GET /api/v1/books?sort=abc passes SORT_MAP['abc'] as the order arg to fill_indexpage."""
    from cps.api import books as books_mod
    from cps.pagination import Pagination

    bks = [SimpleNamespace(id=1, title="A", series_index="1.0", has_cover=0,
                           authors=[], series=[], data=[])]
    pag = Pagination(1, 60, 1)

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/books?sort=abc"):
        with patch.object(books_mod.calibre_db, "fill_indexpage",
                          return_value=(bks, None, pag)) as mock_fill, \
             patch.object(books_mod.config, "config_books_per_page", 60, create=True), \
             patch.object(books_mod.config, "config_read_column", 0, create=True):
            view = inspect.unwrap(books_mod.list_books)
            view()

    call_args = mock_fill.call_args
    assert call_args is not None, "fill_indexpage was never called"
    # 5th positional arg (index 4) is the order list
    positional = call_args.args
    assert len(positional) >= 5, f"Expected ≥5 positional args, got {len(positional)}"
    assert positional[4] == books_mod.SORT_MAP["abc"], (
        f"Expected SORT_MAP['abc'] for sort=abc, got {positional[4]!r}"
    )


@pytest.mark.unit
def test_list_books_sort_unknown_defaults_to_new():
    """Unknown sort key falls back to SORT_MAP['new']."""
    from cps.api import books as books_mod
    from cps.pagination import Pagination

    bks = []
    pag = Pagination(1, 60, 0)

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/books?sort=bogus"):
        with patch.object(books_mod.calibre_db, "fill_indexpage",
                          return_value=(bks, None, pag)) as mock_fill, \
             patch.object(books_mod.config, "config_books_per_page", 60, create=True), \
             patch.object(books_mod.config, "config_read_column", 0, create=True):
            view = inspect.unwrap(books_mod.list_books)
            view()

    positional = mock_fill.call_args.args
    assert positional[4] == books_mod.SORT_MAP["new"]


@pytest.mark.unit
def test_list_books_search():
    """GET /api/v1/books?search=dune routes through get_search_results and total==1."""
    from cps.api import books as books_mod

    fake_book = SimpleNamespace(id=42, title="Dune", series_index="1.0", has_cover=1,
                                authors=[SimpleNamespace(name="Frank Herbert")],
                                series=[], data=[SimpleNamespace(format="EPUB")])

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/books?search=dune"):
        with patch.object(books_mod.calibre_db, "get_search_results",
                          return_value=([fake_book], 1, None)) as mock_search, \
             patch.object(books_mod.config, "config_books_per_page", 60, create=True), \
             patch.object(books_mod.config, "config_read_column", 0, create=True):
            view = inspect.unwrap(books_mod.list_books)
            resp = view()

    mock_search.assert_called_once()
    call_args = mock_search.call_args
    # first positional arg is the search term
    assert call_args.args[0] == "dune", (
        f"get_search_results first arg should be 'dune', got {call_args.args[0]!r}"
    )

    data = json.loads(resp.get_data(as_text=True))
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Dune"


@pytest.mark.unit
def test_list_books_search_empty_string_uses_fill_indexpage():
    """An empty search string must NOT route to get_search_results."""
    from cps.api import books as books_mod
    from cps.pagination import Pagination

    bks = []
    pag = Pagination(1, 60, 0)

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/books?search="):
        with patch.object(books_mod.calibre_db, "fill_indexpage",
                          return_value=(bks, None, pag)) as mock_fill, \
             patch.object(books_mod.calibre_db, "get_search_results",
                          return_value=([], 0, None)) as mock_search, \
             patch.object(books_mod.config, "config_books_per_page", 60, create=True), \
             patch.object(books_mod.config, "config_read_column", 0, create=True):
            view = inspect.unwrap(books_mod.list_books)
            view()

    mock_fill.assert_called_once()
    mock_search.assert_not_called()
