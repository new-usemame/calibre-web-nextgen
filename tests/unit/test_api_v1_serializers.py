import pytest
from types import SimpleNamespace


@pytest.mark.unit
def test_serialize_book_list_item_full():
    from cps.api.serializers import serialize_book_list_item
    book = SimpleNamespace(
        id=7, title="Dune", series_index="1.0", has_cover=1,
        authors=[SimpleNamespace(name="Frank Herbert")],
        series=[SimpleNamespace(name="Dune Chronicles")],
        data=[SimpleNamespace(format="EPUB"), SimpleNamespace(format="PDF")],
    )
    assert serialize_book_list_item(book) == {
        "id": 7, "title": "Dune",
        "authors": ["Frank Herbert"],
        "series": "Dune Chronicles", "series_index": "1.0",
        "cover_url": "/cover/7/sm",
        "formats": ["EPUB", "PDF"],
    }


@pytest.mark.unit
def test_serialize_book_list_item_no_cover_no_series():
    from cps.api.serializers import serialize_book_list_item
    book = SimpleNamespace(id=3, title="X", series_index="1.0", has_cover=0,
                           authors=[], series=[], data=[])
    out = serialize_book_list_item(book)
    assert out["cover_url"] is None
    assert out["series"] is None
    assert out["authors"] == []
    assert out["formats"] == []


@pytest.mark.unit
def test_serialize_user_roles():
    from cps.api.serializers import serialize_user
    from cps import ub, constants
    u = ub.User()
    u.id, u.name, u.locale, u.theme = 1, "admin", "en", 1
    u.role = constants.ROLE_ADMIN | constants.ROLE_UPLOAD
    out = serialize_user(u)
    assert out["id"] == 1 and out["name"] == "admin" and out["locale"] == "en" and out["theme"] == 1
    assert out["role"]["admin"] is True
    assert out["role"]["upload"] is True
    assert out["role"]["edit"] is False


@pytest.mark.unit
def test_serialize_book_detail_sanitizes_description_xss():
    """description_html must be sanitized (no executable HTML) — stored-XSS guard."""
    from types import SimpleNamespace
    from cps.api.serializers import serialize_book_detail
    book = SimpleNamespace(
        id=9, title="X", series_index="1.0", has_cover=0, pubdate=None,
        authors=[], series=[], data=[], tags=[], languages=[], publishers=[], identifiers=[],
        comments=[SimpleNamespace(
            text='<p>Safe</p><script>alert(1)</script><img src=x onerror=alert(2)>')],
    )
    out = serialize_book_detail(book)
    assert "<script>" not in out["description_html"]
    assert "<img" not in out["description_html"]   # img tag escaped/neutralized
    assert "<script" not in out["description_html"]
    assert "<p>Safe</p>" in out["description_html"]
