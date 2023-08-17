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
        assert list(IndexMap.indices(drb, "run-toc")) == list(map["run-toc"].keys())
        assert sorted(IndexMap.stream(drb), key=lambda s: s.id) == [
            IndexStream("prefix.run-data.2023-07", "id1"),
            IndexStream("prefix.run-data.2023-07", "id2"),
            IndexStream("prefix.run-toc.2023-06", "id3"),
            IndexStream("prefix.run-toc.2023-06", "id4"),
            IndexStream("prefix.run-toc.2023-07", "id5"),
            IndexStream("prefix.run-toc.2023-07", "id6"),
        ]

    @pytest.mark.parametrize("m1,m2", ((0, 1), (1, 0)))
    def test_merge(self, db_session, attach_dataset, m1, m2):
        """Test index map merge

        We merge "a into b" and "b into a" ... the results should be identical.
        """

        maps = [
            {
                "run-data": {"prefix.run-data.2023-07": ["id1", "id2"]},
                "run-toc": {
                    "prefix.run-toc.2023-06": ["id3", "id4"],
                    "prefix.run-toc.2023-07": ["id5", "id6"],
                },
                "funky-data": {"prefix.funky-data.1918-02": ["id1", "id2"]},
            },
            {
                "run-data": {"prefix.run-data.2023-06": ["id8", "id9"]},
                "run-toc": {
                    "prefix.run-toc.2023-06": ["id10", "id12", "id13", "id14"],
                    "prefix.run-toc.2023-08": ["id20", "id21"],
                },
                "run-sample": {"prefix.run-sample.2023-08": ["id22", "id23"]},
            },
        ]
        dataset = Dataset.query(name="drb")
        assert not IndexMap.exists(dataset)
        assert list(IndexMap.stream(dataset)) == []

        IndexMap.create(dataset, maps[m1])
        IndexMap.merge(dataset, maps[m2])

        assert sorted(IndexMap.stream(dataset), key=lambda i: (i.id, i.index)) == [
            IndexStream("prefix.funky-data.1918-02", "id1"),
            IndexStream("prefix.run-data.2023-07", "id1"),
            IndexStream("prefix.run-toc.2023-06", "id10"),
            IndexStream("prefix.run-toc.2023-06", "id12"),
            IndexStream("prefix.run-toc.2023-06", "id13"),
            IndexStream("prefix.run-toc.2023-06", "id14"),
            IndexStream("prefix.funky-data.1918-02", "id2"),
            IndexStream("prefix.run-data.2023-07", "id2"),
            IndexStream("prefix.run-toc.2023-08", "id20"),
            IndexStream("prefix.run-toc.2023-08", "id21"),
            IndexStream("prefix.run-sample.2023-08", "id22"),
            IndexStream("prefix.run-sample.2023-08", "id23"),
            IndexStream("prefix.run-toc.2023-06", "id3"),
            IndexStream("prefix.run-toc.2023-06", "id4"),
            IndexStream("prefix.run-toc.2023-07", "id5"),
            IndexStream("prefix.run-toc.2023-07", "id6"),
            IndexStream("prefix.run-data.2023-06", "id8"),
            IndexStream("prefix.run-data.2023-06", "id9"),
        ]

    @pytest.mark.parametrize("to", (False, True))
    def test_merge_none(self, db_session, attach_dataset, to):
        """Test index map merge with an empty map

        We test two cases: one merging a map into an empty map, and then
        merging an empty map into an existing map.

        In either case the result should be the single map.
        """

        map = {
            "run-data": {
                "prefix.run-data.2023-06": ["id8"],
                "prefix.run-data.2023-07": ["id1", "id2"],
            },
            "run-sample": {"prefix.run-sample.2023-06": ["id3", "id4"]},
        }
        drb = Dataset.query(name="drb")
        assert not IndexMap.exists(drb)

        if to:
            IndexMap.create(drb, map)
            IndexMap.merge(drb, {})
        else:
            IndexMap.merge(drb, map)

        assert sorted(IndexMap.stream(drb), key=lambda i: (i.id, i.index)) == [
            IndexStream("prefix.run-data.2023-07", "id1"),
            IndexStream("prefix.run-data.2023-07", "id2"),
            IndexStream("prefix.run-sample.2023-06", "id3"),
            IndexStream("prefix.run-sample.2023-06", "id4"),
            IndexStream("prefix.run-data.2023-06", "id8"),
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

    def test_stream_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index stream failure"""

        def fake_query(db_type):
            raise SQLAlchemyError("That was easy")

        drb = Dataset.query(name="drb")
        monkeypatch.setattr(Database.db_session, "query", fake_query)

        with pytest.raises(IndexMapSqlError) as e:
            [i for i in IndexMap.stream(drb)]
        assert str(e.value) == "Error streaming index drb:all: That was easy"
