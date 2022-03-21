import datetime
import pytest

from pbench.server.database.models.template import (
    Template,
    TemplateDuplicate,
    TemplateFileMissing,
    TemplateMissingParameter,
    TemplateNotFound,
)


class TestTemplate:
    def test_construct(self, fake_mtime, db_session):
        """Test dataset constructor"""
        template = Template(
            name="run",
            idxname="run-data",
            template_name="tname",
            file="run.json",
            template_pattern="drb.v1.run.*",
            index_template="drb.v1.run.{year}-{month}",
            settings={"none": False},
            mappings={"properties": None},
            version=5,
        )
        template.add()
        assert template.name == "run"
        assert template.mtime == datetime.datetime(2021, 1, 29, 0, 0, 0)
        assert "run: drb.v1.run.{year}-{month}" == str(template)

    def test_construct_duplicate(self, fake_mtime, db_session):
        """Test dataset constructor"""
        template = Template(
            name="run",
            idxname="run-data",
            template_name="tname",
            file="run.json",
            template_pattern="drb.v1.run.*",
            index_template="drb.v1.run.{year}-{month}",
            settings={"none": False},
            mappings={"properties": None},
            version=5,
        )
        template.add()
        with pytest.raises(TemplateDuplicate) as e:
            template1 = Template(
                name="run",
                idxname="run-data",
                template_name="tname",
                file="run.json",
                template_pattern="drb.v1.run.*",
                index_template="drb.v1.run.{year}-{month}",
                settings={"none": False},
                mappings={"properties": None},
                version=5,
            )
            template1.add()
        assert str(e).find("run") != -1

    def test_construct_fileless(self, fake_mtime, db_session):
        """Test dataset constructor without a file column"""
        with pytest.raises(TemplateFileMissing) as e:
            Template(
                name="run",
                idxname="run-data",
                template_name="tname",
                template_pattern="drb.v1.run.*",
                index_template="drb.v1.run.{year}-{month}",
                settings={"none": False},
                mappings={"properties": None},
                version=5,
            )
        assert str(e).find("run") != -1

    def test_construct_missing(self, fake_mtime, db_session):
        """Test dataset constructor when non-nullable columns are omitted;
        the constuctor works, but SQL will throw an IntegrityError when we
        try to commit to the DB.
        """
        with pytest.raises(TemplateMissingParameter) as e:
            template = Template(
                name="run",
                file="map.json",
                template_name="tname",
                template_pattern="drb.v1.run.*",
                index_template="drb.v1.run.{year}-{month}",
                version=5,
            )
            template.add()
        assert str(e).find("run") != -1

    def test_find_exists(self, fake_mtime, db_session):
        """Test that we can find a template"""
        template1 = Template(
            name="run",
            idxname="run-data",
            template_name="run",
            file="run-toc.json",
            template_pattern="drb.v2.run-toc.*",
            index_template="drb.v2.run-toc.{year}-{month}",
            settings={"none": False},
            mappings={"properties": None},
            version=5,
        )
        template1.add()

        template2 = Template.find(name="run")
        assert template2.name == template1.name
        assert template2.id is template1.id

    def test_find_none(self, fake_mtime, db_session):
        """Test expected failure when we try to find a template that
        does not exist.
        """
        with pytest.raises(TemplateNotFound):
            Template.find(name="data")

    def test_update(self, fake_mtime, db_session):
        """Test template update"""
        template = Template(
            name="run",
            file="run.json",
            idxname="run-data",
            template_name="tname",
            template_pattern="drb.v1.run.*",
            index_template="drb.v1.run.{year}-{month}",
            settings={"none": False},
            mappings={"properties": None},
            version=5,
        )
        template.add()
        template.mappings = {"properties": "something"}
        template.update()

    def test_update_missing(self, fake_mtime, db_session):
        """Test template update"""
        template = Template(
            name="run",
            file="run.json",
            idxname="run-data",
            template_name="tname",
            template_pattern="drb.v1.run.*",
            index_template="drb.v1.run.{year}-{month}",
            settings={"none": False},
            mappings={"properties": None},
            version=5,
        )
        template.add()
        template.idxname = None
        with pytest.raises(TemplateMissingParameter) as e:
            template.update()
        assert str(e).find("run") != -1
        assert str(e).find("idxname") != -1
