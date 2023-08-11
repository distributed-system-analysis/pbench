import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.index_map import (
    IndexMap,
    IndexMapDuplicate,
    IndexMapMissingParameter,
    IndexMapSqlError,
)


class TestIndexMapDB:
    def test_create(self, db_session, attach_dataset):
        """Test index map creation"""

        map = {
            "run-data": {"prefix.run-data.2023-07": ["id1", "id2"]},
            "run-toc": {
                "prefix.run-toc.2023-06": ["id3", "id4"],
                "prefix.run-toc.2023-07": ["id5", "id6"],
            },
        }
        drb = Dataset.query(name="drb")
        IndexMap.create(drb, map)

        assert IndexMap.map(drb) == map
        assert IndexMap.find(drb, "run-toc") == map["run-toc"]

    def test_merge(self, db_session, attach_dataset):
        """Test index map merge"""

        map1 = {
            "run-data": {"prefix.run-data.2023-07": ["id1", "id2"]},
            "run-toc": {
                "prefix.run-toc.2023-06": ["id3", "id4"],
                "prefix.run-toc.2023-07": ["id5", "id6"],
            },
        }
        map2 = {
            "run-data": {"prefix.run-data.2023-06": ["id8", "id9"]},
            "run-toc": {
                "prefix.run-toc.2023-06": ["id10", "id12", "id13", "id14"],
                "prefix.run-toc.2023-08": ["id20", "id21"],
            },
            "run-sample": {"prefix.run-sample.2023-08": ["id22", "id23"]},
        }
        drb = Dataset.query(name="drb")
        IndexMap.create(drb, map1)
        IndexMap.merge(drb, map2)

        map = IndexMap.map(drb)
        assert sorted(map.keys()) == ["run-data", "run-sample", "run-toc"]
        assert sorted(map["run-toc"].keys()) == [
            "prefix.run-toc.2023-06",
            "prefix.run-toc.2023-07",
            "prefix.run-toc.2023-08",
        ]
        assert sorted(map["run-toc"]["prefix.run-toc.2023-06"]) == [
            "id10",
            "id12",
            "id13",
            "id14",
            "id3",
            "id4",
        ]

    @pytest.mark.parametrize(
        "source,expected",
        (
            (
                IntegrityError(
                    statement="", params="", orig=BaseException("UNIQUE constraint")
                ),
                IndexMapDuplicate,
            ),
            (
                IntegrityError(
                    statement="", params="", orig=BaseException("NOT NULL constraint")
                ),
                IndexMapMissingParameter,
            ),
            (Exception("Not me"), IndexMapSqlError),
        ),
    )
    def test_commit_error(
        self, monkeypatch, db_session, attach_dataset, source, expected
    ):
        """Test commit integrity error"""

        def fake_commit():
            raise source

        monkeypatch.setattr(Database.db_session, "commit", fake_commit)
        drb = Dataset.query(name="drb")
        with pytest.raises(expected):
            IndexMap.create(drb, {"root": {"index": ["id"]}})
