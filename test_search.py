from unittest.mock import patch, MagicMock
import pytest
from starlette.testclient import TestClient

from app import app


SAMPLE_ENTRIES = [
    {
        "number": "1",
        "conv": "VIII",
        "name": "О бюджете на 2024 год",
        "url": "/legislation/bills/1",
        "date": "01.01.2024",
    },
    {
        "number": "2",
        "conv": "VIII",
        "name": "О налогообложении",
        "url": "/legislation/bills/2",
        "date": "15.03.2024",
    },
    {
        "number": "15",
        "conv": "VII",
        "name": "О бюджете на 2023 год",
        "url": "/legislation/bills/15",
        "date": "10.06.2023",
    },
]


@pytest.fixture
def client():
    return TestClient(app)


def make_aggregate_result(entries):
    return iter(entries)


def make_find_chain(entries):
    mock = MagicMock()
    mock.sort.return_value = mock
    mock.collation.return_value = mock
    mock.skip.return_value = mock
    mock.limit.return_value = mock
    mock.__iter__ = lambda self: iter(entries)
    return mock


# --- /api/search tests ---


class TestApiSearch:
    def test_empty_query_returns_empty(self, client):
        resp = client.get("/api/search")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_query_with_spaces(self, client):
        resp = client.get("/api/search?q=%20%20")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.entry_db")
    def test_search_by_exact_number(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result([SAMPLE_ENTRIES[0]])

        resp = client.get("/api/search?q=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["number"] == "1"
        assert data[0]["conv"] == "VIII"

        pipeline = mock_db.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        assert match_stage["$or"][0]["number"]["$regex"] == "^1$"

    @patch("app.entry_db")
    def test_search_by_name_substring(self, mock_db, client):
        matching = [SAMPLE_ENTRIES[0], SAMPLE_ENTRIES[2]]
        mock_db.aggregate.return_value = make_aggregate_result(matching)

        resp = client.get("/api/search?q=бюджет")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all("бюджет" in e["name"].lower() for e in data)

    @patch("app.entry_db")
    def test_search_across_convocations(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result(
            [SAMPLE_ENTRIES[0], SAMPLE_ENTRIES[2]]
        )

        resp = client.get("/api/search?q=бюджет")
        data = resp.json()
        convs = {e["conv"] for e in data}
        assert convs == {"VIII", "VII"}

    @patch("app.entry_db")
    def test_search_invalid_offset_take_ignored(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result([SAMPLE_ENTRIES[0]])

        resp = client.get("/api/search?q=бюджет&offset=abc&take=zz")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @patch("app.entry_db")
    def test_search_no_results(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result([])

        resp = client.get("/api/search?q=несуществующий")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.entry_db")
    def test_search_special_characters_escaped(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result([])

        resp = client.get("/api/search?q=test.*()")
        assert resp.status_code == 200

        pipeline = mock_db.aggregate.call_args[0][0]
        match_stage = pipeline[0]["$match"]
        # re.escape should have escaped the special chars
        assert r"\.\*\(\)" in match_stage["$or"][0]["number"]["$regex"]
        assert r"\.\*\(\)" in match_stage["$or"][1]["name"]["$regex"]

    @patch("app.entry_db")
    def test_search_with_offset_and_take(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result([SAMPLE_ENTRIES[1]])

        resp = client.get("/api/search?q=О&offset=1&take=1")
        assert resp.status_code == 200

        pipeline = mock_db.aggregate.call_args[0][0]
        assert {"$skip": 1} in pipeline
        assert {"$limit": 1} in pipeline

    @patch("app.entry_db")
    def test_search_without_pagination(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result(SAMPLE_ENTRIES)

        resp = client.get("/api/search?q=О")
        pipeline = mock_db.aggregate.call_args[0][0]
        stages = [list(s.keys())[0] for s in pipeline]
        assert "$skip" not in stages
        assert "$limit" not in stages

    @patch("app.entry_db")
    def test_search_response_format(self, mock_db, client):
        mock_db.aggregate.return_value = make_aggregate_result([SAMPLE_ENTRIES[0]])

        resp = client.get("/api/search?q=1")
        data = resp.json()
        entry = data[0]
        assert set(entry.keys()) == {"number", "conv", "name", "url", "date"}
        assert entry["url"].startswith("http://www.vspmr.org")


# --- /search (web) tests ---


class TestSearchPage:
    @patch("app.entry_db")
    def test_search_page_renders(self, mock_db, client):
        mock_db.count_documents.return_value = 1
        mock_db.find.return_value = make_find_chain([SAMPLE_ENTRIES[0]])

        resp = client.get("/search?q=бюджет")
        assert resp.status_code == 200
        assert "бюджет" in resp.text

    @patch("app.entry_db")
    def test_search_page_empty_query(self, mock_db, client):
        resp = client.get("/search?q=")
        assert resp.status_code == 200
        # Should not call the database
        mock_db.find.assert_not_called()

    @patch("app.entry_db")
    def test_search_page_shows_results(self, mock_db, client):
        mock_db.count_documents.return_value = 1
        mock_db.find.return_value = make_find_chain([SAMPLE_ENTRIES[0]])

        resp = client.get("/search?q=бюджет")
        assert "О бюджете на 2024 год" in resp.text

    @patch("app.entry_db")
    def test_search_page_preserves_query_in_input(self, mock_db, client):
        mock_db.count_documents.return_value = 0
        mock_db.find.return_value = make_find_chain([])

        resp = client.get("/search?q=тест")
        assert 'value="тест"' in resp.text

    @patch("app.entry_db")
    def test_search_page_pagination_links(self, mock_db, client):
        mock_db.count_documents.return_value = 25
        mock_db.find.return_value = make_find_chain(SAMPLE_ENTRIES)

        resp = client.get("/search?q=О")
        assert "/search?q=%D0%9E" in resp.text or "/search?q=О" in resp.text

    @patch("app.entry_db")
    def test_search_page_links_use_entry_conv(self, mock_db, client):
        # результат из VII созыва должен вести на /conv-VII/..., а не на текущий созыв
        mock_db.count_documents.return_value = 1
        mock_db.find.return_value = make_find_chain([SAMPLE_ENTRIES[2]])

        resp = client.get("/search?q=бюджет")
        assert "/conv-VII/entry/15" in resp.text
        assert "/conv-VIII/entry/15" not in resp.text

    @patch("app.entry_db")
    def test_search_page_invalid_page_ignored(self, mock_db, client):
        mock_db.count_documents.return_value = 1
        mock_db.find.return_value = make_find_chain([SAMPLE_ENTRIES[0]])

        resp = client.get("/search?q=бюджет&page=abc")
        assert resp.status_code == 200

    def test_homepage_has_search_form(self, client):
        with patch("app.entry_db") as mock_db:
            mock_db.count_documents.return_value = 0
            mock_db.find.return_value = make_find_chain([])

            resp = client.get("/")
            assert '<form class="search-form"' in resp.text
            assert 'action="/search"' in resp.text
            assert 'name="q"' in resp.text
