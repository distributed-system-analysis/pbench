import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.index_map import (
    IndexMap,
    IndexMapDuplicate,
    IndexMapMissingParameter,
    IndexMapSqlError,
    IndexStream,
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
        assert IndexMap.exists(drb) is False
        IndexMap.create(drb, map)
        assert IndexMap.exists(drb) is True
        assert IndexMap.indices(drb, "run-toc") == list(map["run-toc"].keys())
        assert sorted(list(IndexMap.stream(drb)), key=lambda s: s.id) == [
            IndexStream("prefix.run-data.2023-07", "id1"),
            IndexStream("prefix.run-data.2023-07", "id2"),
            IndexStream("prefix.run-toc.2023-06", "id3"),
            IndexStream("prefix.run-toc.2023-06", "id4"),
            IndexStream("prefix.run-toc.2023-07", "id5"),
            IndexStream("prefix.run-toc.2023-07", "id6"),
        ]

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

        map = list(IndexMap.stream(drb))
        ids = [m.id for m in map]
        indices = set(m.index for m in map)
        assert sorted(indices) == [
            "prefix.run-data.2023-06",
            "prefix.run-data.2023-07",
            "prefix.run-sample.2023-08",
            "prefix.run-toc.2023-06",
            "prefix.run-toc.2023-07",
            "prefix.run-toc.2023-08",
        ]
        assert sorted(ids) == [
            "id1",
            "id10",
            "id12",
            "id13",
            "id14",
            "id2",
            "id20",
            "id21",
            "id22",
            "id23",
            "id3",
            "id4",
            "id5",
            "id6",
            "id8",
            "id9",
        ]

    def test_merge_none(self, db_session, attach_dataset):
        """Test index map merge with no existing map

        The result should be the new map.
        """

        map = {"run-data": {"prefix.run-data.2023-06": ["id8"]}}
        drb = Dataset.query(name="drb")
        IndexMap.merge(drb, map)
        assert list(IndexMap.stream(drb)) == [
            IndexStream("prefix.run-data.2023-06", "id8")
        ]

    @pytest.mark.parametrize(
        "source,expected,message",
        (
            (
                IntegrityError(
                    statement="", params="", orig=BaseException("UNIQUE constraint")
                ),
                IndexMapDuplicate,
                "Duplicate index map 'any'",
            ),
            (
                IntegrityError(
                    statement="", params="", orig=BaseException("NOT NULL constraint")
                ),
                IndexMapMissingParameter,
                "Missing required parameters in 'any'",
            ),
            (
                IntegrityError(statement="", params="", orig=BaseException("JUNK")),
                IntegrityError,
                "(builtins.BaseException) JUNK",
            ),
            (Exception("Not me"), IndexMapSqlError, "Error create index drb:any"),
        ),
    )
    def test_commit_error(
        self, monkeypatch, db_session, attach_dataset, source, expected, message
    ):
        """Test commit integrity error"""

        def fake_commit():
            raise source

        monkeypatch.setattr(Database.db_session, "commit", fake_commit)
        drb = Dataset.query(name="drb")
        with pytest.raises(expected) as e:
            IndexMap.create(drb, {"root": {"index": ["id"]}})
        assert str(e.value).startswith(
            message
        ), f"{str(e.value)!r} doesn't start with {message!r}"

    def test_delete(self, db_session, create_user):
        """Test index map deletion with dataset

        We create a "scratch" dataset so that deleting it doesn't
        impact subsequent test cases.
        """

        map = {"run-data": {"prefix.run-data.2023-07": ["id1", "id2"]}}
        d = Dataset(owner=create_user, name="test", resource_id="fakeid")
        d.add()
        ref = d.id
        IndexMap.create(d, map)
        before = (
            Database.db_session.query(IndexMap)
            .filter(IndexMap.dataset_ref == ref)
            .all()
        )
        assert len(before) == 1
        assert str(before[0]) == "test [run-data:prefix.run-data.2023-07]: 2 IDs"
        Dataset.delete(d)
        after = (
            Database.db_session.query(IndexMap)
            .filter(IndexMap.dataset_ref == ref)
            .all()
        )
        assert after == []

    def test_create_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index map creation failure"""

        def fake_add_all(idx: list[IndexMap]):
            raise Exception("Yeah, that didn't work")

        monkeypatch.setattr(Database.db_session, "add_all", fake_add_all)

        drb = Dataset.query(name="drb")
        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.create(drb, {"root": {"idx": ["id"]}})
        assert str(e.value) == "Error add_all index drb:all: Yeah, that didn't work"

    def test_merge_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index map creation failure"""

        def fake_add(idx: IndexMap):
            raise SQLAlchemyError("That was easy")

        monkeypatch.setattr(Database.db_session, "add", fake_add)

        drb = Dataset.query(name="drb")
        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.merge(drb, {"root": {"idx": ["id"]}})
        assert str(e.value) == "Error merge index drb:all: That was easy"

    def test_indices_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index list failure"""

        def fake_query(db_type):
            raise SQLAlchemyError("That was easy")

        drb = Dataset.query(name="drb")
        monkeypatch.setattr(Database.db_session, "query", fake_query)

        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.indices(drb, "idx")
        assert str(e.value) == "Error finding index drb:idx: That was easy"

    def test_exists_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index existence check failure"""

        def fake_query(db_type):
            raise SQLAlchemyError("That was easy")

        drb = Dataset.query(name="drb")
        monkeypatch.setattr(Database.db_session, "query", fake_query)

        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.exists(drb)
        assert str(e.value) == "Error checkexist index drb:any: That was easy"
