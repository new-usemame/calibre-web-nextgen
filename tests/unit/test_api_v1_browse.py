"""Unit tests for /api/v1 entity-list browse endpoints (browse.py)."""
import json
import inspect
import pytest
import flask
from types import SimpleNamespace
from unittest.mock import patch, MagicMock


@pytest.mark.unit
def test_list_authors_items():
    """GET /api/v1/authors returns items with id, name, count; pipes replaced in name."""
    from cps.api import browse as browse_mod

    author = SimpleNamespace(id=1, name="Asimov|Isaac", sort="Asimov")
    # Mock the query chain: session.query(...).join...all()
    mock_result = [(author, 7)]

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/authors"):
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_result

        with patch.object(browse_mod.calibre_db, "session") as mock_session, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            mock_session.query.return_value = mock_query
            view = inspect.unwrap(browse_mod.list_authors)
            result = view()

    # Flask 2.2+ allows returning dict directly from view functions
    if isinstance(result, dict):
        data = result
    else:
        data = json.loads(result.get_data(as_text=True))

    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == 1
    assert item["name"] == "Asimov,Isaac"  # pipe replaced with comma
    assert item["count"] == 7


@pytest.mark.unit
def test_list_tags_items():
    """GET /api/v1/tags returns items with id, name, count."""
    from cps.api import browse as browse_mod

    tag = SimpleNamespace(id=5, name="Science Fiction")
    mock_result = [(tag, 42)]

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/tags"):
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_result

        with patch.object(browse_mod.calibre_db, "session") as mock_session, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            mock_session.query.return_value = mock_query
            view = inspect.unwrap(browse_mod.list_tags)
            result = view()

    if isinstance(result, dict):
        data = result
    else:
        data = json.loads(result.get_data(as_text=True))

    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == 5
    assert item["name"] == "Science Fiction"
    assert item["count"] == 42


@pytest.mark.unit
def test_list_series_items():
    """GET /api/v1/series returns items with id, name, count."""
    from cps.api import browse as browse_mod

    series = SimpleNamespace(id=2, name="Foundation", sort="Foundation")
    mock_result = [(series, 6)]

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/series"):
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_result

        with patch.object(browse_mod.calibre_db, "session") as mock_session, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            mock_session.query.return_value = mock_query
            view = inspect.unwrap(browse_mod.list_series)
            result = view()

    if isinstance(result, dict):
        data = result
    else:
        data = json.loads(result.get_data(as_text=True))

    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == 2
    assert item["name"] == "Foundation"
    assert item["count"] == 6


@pytest.mark.unit
def test_list_publishers_items():
    """GET /api/v1/publishers returns items with id, name, count."""
    from cps.api import browse as browse_mod

    pub = SimpleNamespace(id=3, name="Tor Books", sort="Tor Books")
    mock_result = [(pub, 15)]

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/publishers"):
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_result

        with patch.object(browse_mod.calibre_db, "session") as mock_session, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            mock_session.query.return_value = mock_query
            view = inspect.unwrap(browse_mod.list_publishers)
            result = view()

    if isinstance(result, dict):
        data = result
    else:
        data = json.loads(result.get_data(as_text=True))

    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == 3
    assert item["name"] == "Tor Books"
    assert item["count"] == 15


@pytest.mark.unit
def test_list_languages_uses_speaking_language():
    """GET /api/v1/languages delegates to calibre_db.speaking_language(with_count=True)."""
    from cps.api import browse as browse_mod

    # speaking_language returns [[Category, count], ...]
    cat = SimpleNamespace(id="eng", name="English")
    mock_result = [[cat, 99]]

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/languages"):
        with patch.object(browse_mod.calibre_db, "speaking_language",
                          return_value=mock_result) as mock_sl:
            view = inspect.unwrap(browse_mod.list_languages)
            result = view()

    mock_sl.assert_called_once_with(with_count=True)

    if isinstance(result, dict):
        data = result
    else:
        data = json.loads(result.get_data(as_text=True))

    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == "eng"
    assert item["name"] == "English"
    assert item["count"] == 99


@pytest.mark.unit
def test_list_authors_pipe_replacement():
    """Author names with | are normalised to , in the response."""
    from cps.api import browse as browse_mod

    author = SimpleNamespace(id=10, name="Adams|Douglas", sort="Adams")
    mock_result = [(author, 4)]

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/authors"):
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_result

        with patch.object(browse_mod.calibre_db, "session") as mock_session, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            mock_session.query.return_value = mock_query
            view = inspect.unwrap(browse_mod.list_authors)
            result = view()

    if isinstance(result, dict):
        data = result
    else:
        data = json.loads(result.get_data(as_text=True))

    assert data["items"][0]["name"] == "Adams,Douglas"


@pytest.mark.unit
def test_list_ratings_items():
    """GET /api/v1/ratings returns star-formatted names (calibre stores rating 0-10)."""
    from cps.api import browse as browse_mod

    rating = SimpleNamespace(id=2, rating=8)  # 8/2 = 4 stars
    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/ratings"):
        mq = MagicMock()
        mq.join.return_value = mq
        mq.filter.return_value = mq
        mq.group_by.return_value = mq
        mq.order_by.return_value = mq
        mq.all.return_value = [(rating, 3)]
        with patch.object(browse_mod.calibre_db, "session") as ms, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            ms.query.return_value = mq
            result = inspect.unwrap(browse_mod.list_ratings)()
    data = result if isinstance(result, dict) else json.loads(result.get_data(as_text=True))
    assert data["items"] == [{"id": 2, "name": "4★", "count": 3}]


@pytest.mark.unit
def test_list_formats_items():
    """GET /api/v1/formats returns the format string as both id and name."""
    from cps.api import browse as browse_mod

    app = flask.Flask(__name__)
    with app.test_request_context("/api/v1/formats"):
        mq = MagicMock()
        mq.join.return_value = mq
        mq.filter.return_value = mq
        mq.group_by.return_value = mq
        mq.order_by.return_value = mq
        mq.all.return_value = [("EPUB", 13), ("PDF", 1)]
        with patch.object(browse_mod.calibre_db, "session") as ms, \
             patch.object(browse_mod.calibre_db, "common_filters", return_value=True):
            ms.query.return_value = mq
            result = inspect.unwrap(browse_mod.list_formats)()
    data = result if isinstance(result, dict) else json.loads(result.get_data(as_text=True))
    assert {"id": "EPUB", "name": "EPUB", "count": 13} in data["items"]
    assert {"id": "PDF", "name": "PDF", "count": 1} in data["items"]
