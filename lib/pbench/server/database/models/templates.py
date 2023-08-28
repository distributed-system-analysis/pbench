import datetime
from pathlib import Path

from sqlalchemy import Column, event, Integer, String
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.sqltypes import DateTime, JSON

from pbench.server.database.database import Database
from pbench.server.database.models import decode_sql_error


class TemplateError(Exception):
    """A base class for errors reported by the Template class.

    It is never raised directly, but may be used in "except" clauses.
    """

    pass


class TemplateSqlError(TemplateError):
    """SQLAlchemy errors reported through Template operations.

    The exception will identify the base name of the template index, along
    with the operation being attempted; the __cause__ will specify the
    original SQLAlchemy exception.
    """

    def __init__(self, cause: Exception, **kwargs):
        super().__init__(
            f"Error on {kwargs.get('operation')} index {kwargs.get('name')!r}: '{cause}'"
        )
        self.cause = cause
        self.kwargs = kwargs


class TemplateFileMissing(TemplateError):
    """Template requires a file name."""

    def __init__(self, name: str):
        super().__init__(f"Template {name!r} is missing required file")
        self.name = name


class TemplateNotFound(TemplateError):
    """Attempt to find a Template that doesn't exist."""

    def __init__(self, name: str):
        super().__init__(
            f"Document template for index {name!r} not found in the database"
        )
        self.name = name


class TemplateDuplicate(TemplateError):
    """Attempt to commit a duplicate Template."""

    def __init__(self, cause: Exception, **kwargs):
        super().__init__(f"Duplicate template {kwargs.get('name')!r}: '{cause}'")
        self.cause = cause
        self.kwargs = kwargs


class TemplateMissingParameter(TemplateError):
    """Attempt to commit a Template with missing parameters."""

    def __init__(self, cause: Exception, **kwargs):
        super().__init__(
            f"Missing required parameters in {kwargs.get('name')!r}: '{cause}'"
        )
        self.cause = cause
        self.kwargs = kwargs


class Template(Database.Base):
    """Identify a Pbench Elasticsearch document template.

    Columns:
        id              Generated unique ID of table row
        name            Index name key (e.g., "fio")
        idxname         Base index name (e.g., "tool-data-fio")
        template_name   The Elasticsearch template name
        file            The source JSON mapping file
        mtime           Template file modification timestamp
        template_pattern The template for the Elasticsearch index name
        index_template  The full index name template "p.v.i.y-m[-d]"
        settings        The JSON settings payload
        mappings        The JSON mappings payload
        version         The template version metadata
    """

    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    idxname = Column(String(255), unique=True, nullable=False)
    template_name = Column(String(255), unique=True, nullable=False)
    file = Column(String(255), unique=False, nullable=False)
    mtime = Column(DateTime, unique=False, nullable=False)
    template_pattern = Column(String(255), unique=False, nullable=False)
    index_template = Column(String(225), unique=False, nullable=False)
    settings = Column(JSON, unique=False, nullable=False)
    mappings = Column(JSON, unique=False, nullable=False)
    version = Column(String(255), unique=False, nullable=False)

    @staticmethod
    def create(**kwargs) -> "Template":
        """A simple factory method to construct a new Template object and
        add it to the database.

        Args:
            kwargs : any of the column names defined above

        Returns:
            A new Template object initialized with the keyword parameters.
        """
        template = Template(**kwargs)
        template.add()
        return template

    @staticmethod
    def find(name: str) -> "Template":
        """Return a Template object with the specified base name.

        For example, find("run-data").

        Args:
            name : Base index name

        Raises:
            TemplateSqlError : problem interacting with Database
            TemplateNotFound : the specified template doesn't exist

        Returns:
            Template : a template object with the specified base name
        """
        try:
            template = Database.db_session.query(Template).filter_by(name=name).first()
        except SQLAlchemyError as e:
            raise TemplateSqlError(e, operation="find", name=name)

        if template is None:
            raise TemplateNotFound(name)
        return template

    def __str__(self) -> str:
        """Return a string representation of the template.

        Returns:
            A string representation of the template.
        """
        return f"{self.name}: {self.index_template}"

    def add(self):
        """Add the Template object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise decode_sql_error(
                e,
                on_duplicate=TemplateDuplicate,
                on_null=TemplateMissingParameter,
                fallback=TemplateSqlError,
                operation="add",
                name=self.name,
            ) from e

    def update(self):
        """Update the database row with the modified version of the
        Template object.
        """
        try:
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise decode_sql_error(
                e,
                on_duplicate=TemplateDuplicate,
                on_null=TemplateMissingParameter,
                fallback=TemplateSqlError,
                operation="update",
                name=self.name,
            ) from e


@event.listens_for(Template, "init")
def check_required(target, args, kwargs):
    """Listen for an init event on Template to validate that a filename was
    specified.

    Automatically capture the file's modification timestamp if it wasn't given.
    """
    if "file" not in kwargs:
        raise TemplateFileMissing(kwargs["name"])

    if "mtime" not in kwargs:
        kwargs["mtime"] = datetime.datetime.fromtimestamp(
            Path(kwargs["file"]).stat().st_mtime
        )
