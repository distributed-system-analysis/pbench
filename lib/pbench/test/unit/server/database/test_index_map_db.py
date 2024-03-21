import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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
            "run-data": ["prefix.run-data.2023-07"],
            "run-toc": ["prefix.run-toc.2023-06", "prefix.run-toc.2023-07"],
        }
        drb = Dataset.query(name="drb")
        assert IndexMap.exists(drb) is False
        IndexMap.create(drb, map)
        assert IndexMap.exists(drb) is True
        assert sorted(IndexMap.indices(drb, "run-toc")) == sorted(map["run-toc"])

    def test_delete(self, db_session, attach_dataset):
        """Test index map deletion"""

        map = {
            "run-data": ["prefix.run-data.2023-07"],
            "run-misc": ["prefix.run-misc.2024-03"],
            "run-toc": ["prefix.run-toc.2023-06", "prefix.run-toc.2023-07"],
        }
        drb = Dataset.query(name="drb")
        assert IndexMap.exists(drb) is False
        IndexMap.create(drb, map)
        assert IndexMap.exists(drb) is True
        assert [
            "prefix.run-data.2023-07",
            "prefix.run-misc.2024-03",
            "prefix.run-toc.2023-06",
            "prefix.run-toc.2023-07",
        ] == sorted(IndexMap.indices(drb))
        IndexMap.delete(drb, "run-misc")
        assert [
            "prefix.run-data.2023-07",
            "prefix.run-toc.2023-06",
            "prefix.run-toc.2023-07",
        ] == sorted(IndexMap.indices(drb))
        IndexMap.delete(drb)
        assert IndexMap.exists(drb) is False

    @pytest.mark.parametrize("m1,m2", ((0, 1), (1, 0)))
    def test_merge(self, db_session, attach_dataset, m1, m2):
        """Test index map merge

        We merge "a into b" and "b into a" ... the results should be identical.
        """

        maps = [
            {
                "run-data": ["prefix.run-data.2023-07"],
                "run-toc": ["prefix.run-toc.2023-06", "prefix.run-toc.2023-07"],
                "funky-data": ["prefix.funky-data.1918-02"],
            },
            {
                "run-data": ["prefix.run-data.2023-06"],
                "run-toc": ["prefix.run-toc.2023-06", "prefix.run-toc.2023-08"],
                "run-sample": ["prefix.run-sample.2023-08"],
            },
        ]
        dataset = Dataset.query(name="drb")
        assert not IndexMap.exists(dataset)

        IndexMap.create(dataset, maps[m1])
        IndexMap.merge(dataset, maps[m2])
        indices = set()
        for m in maps:
            for i in m.values():
                indices.update(i)
        assert sorted(IndexMap.indices(dataset)) == sorted(indices)

    @pytest.mark.parametrize(
        "orig,merge", ((False, True), (True, False), (False, False))
    )
    def test_merge_identity(self, db_session, attach_dataset, orig, merge):
        """Test index map merge with an empty map

        We test three cases: one merging a map into an empty map, then merging
        an empty map into an existing map, and finally merging two empty maps.

        In "empty into empty" the result should be empty; otherwise the result
        be the single map.
        """

        map = {
            "run-data": ["prefix.run-data.2023-06", "prefix.run-data.2023-07"],
            "run-sample": ["prefix.run-sample.2023-06"],
        }
        drb = Dataset.query(name="drb")
        assert not IndexMap.exists(drb)

        if orig:
            IndexMap.create(drb, map)

        if merge:
            IndexMap.merge(drb, map)
        else:
            IndexMap.merge(drb, {})

        if orig or merge:
            assert sorted(IndexMap.indices(drb)) == [
                "prefix.run-data.2023-06",
                "prefix.run-data.2023-07",
                "prefix.run-sample.2023-06",
            ]
        else:
            assert list(IndexMap.indices(drb)) == []

    @pytest.mark.parametrize(
        "source,expected,message",
        (
            (
                IntegrityError(
                    statement="", params="", orig=BaseException("UNIQUE constraint")
                ),
                IndexMapDuplicate,
                "Duplicate index map ",
            ),
            (
                IntegrityError(
                    statement="", params="", orig=BaseException("NOT NULL constraint")
                ),
                IndexMapMissingParameter,
                "Missing required parameters ",
            ),
            (
                IntegrityError(statement="", params="", orig=BaseException("JUNK")),
                IndexMapSqlError,
                "Index SQL error on create (drb)|drb:all: '(builtins.BaseException) JUNK",
            ),
            (
                Exception("Not me"),
                IndexMapSqlError,
                "Index SQL error on create (drb)|drb:all",
            ),
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
            IndexMap.create(drb, {"root": ["index"]})
        assert str(e.value).startswith(
            message
        ), f"{str(e.value)!r} doesn't start with {message!r}"

    def test_delete_dataset(self, db_session, create_user):
        """Test index map deletion with dataset

        We create a "scratch" dataset so that deleting it doesn't
        impact subsequent test cases.
        """

        map = {"run-data": ["prefix.run-data.2023-07"]}
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
        assert str(before[0]) == "test [run-data:prefix.run-data.2023-07]"
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
            IndexMap.create(drb, {"root": ["idx"]})
        assert (
            str(e.value)
            == "Index SQL error on create (drb)|drb:all: 'Yeah, that didn't work'"
        )

    def test_merge_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index map creation failure"""

        def fake_add(idx: IndexMap):
            raise SQLAlchemyError("That was easy")

        monkeypatch.setattr(Database.db_session, "add", fake_add)

        drb = Dataset.query(name="drb")
        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.merge(drb, {"root": ["idx"]})
        assert str(e.value) == "Index SQL error on merge (drb)|drb:all: 'That was easy'"

    def test_indices_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index list failure"""

        def fake_query(db_type):
            raise SQLAlchemyError("That was easy")

        drb = Dataset.query(name="drb")
        monkeypatch.setattr(Database.db_session, "query", fake_query)

        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.indices(drb, "idx")
        assert (
            str(e.value) == "Index SQL error on indices (drb)|drb:idx: 'That was easy'"
        )

    def test_exists_fail(self, monkeypatch, db_session, attach_dataset):
        """Test index existence check failure"""

        def fake_query(db_type):
            raise SQLAlchemyError("That was easy")

        drb = Dataset.query(name="drb")
        monkeypatch.setattr(Database.db_session, "query", fake_query)

        with pytest.raises(IndexMapSqlError) as e:
            IndexMap.exists(drb)
        assert (
            str(e.value) == "Index SQL error on exists (drb)|drb:any: 'That was easy'"
        )
