import datetime
from pathlib import Path
from sqlalchemy import Column, Integer, String, event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.sql.sqltypes import DateTime, JSON

from pbench.server.database.database import Database


class TemplateError(Exception):
    """
    This is a base class for errors reported by the Template class. It is
    never raised directly, but may be used in "except" clauses.
    """

    pass


class TemplateSqlError(TemplateError):
    """
    SQLAlchemy errors reported through Template operations.

    The exception will identify the base name of the template index,
    along with the operation being attempted; the __cause__ will specify the
    original SQLAlchemy exception.
    """

    def __init__(self, operation: str, name: str):
        self.operation = operation
        self.name = name

    def __str__(self) -> str:
        return f"Error {self.operation} index {self.name!r}"


class TemplateFileMissing(TemplateError):
    """
    Template requires a file name.
    """

    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f"Template {self.name!r} is missing required file"


class TemplateNotFound(TemplateError):
    """
    Attempt to find a Template that doesn't exist.
    """

    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f"No template {self.name!r}"


class TemplateDuplicate(TemplateError):
    """
    Attempt to commit a duplicate Template.
    """

    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f"Duplicate template {self.name!r}"


class TemplateMissingParameter(TemplateError):
    """
    Attempt to commit a Template with missing parameters.
    """

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing required parameters in {self.name!r}: {self.cause}"


class Template(Database.Base):
    """
    Identify a Pbench Elasticsearch document template

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
        """
        A simple factory method to construct a new Template object and
        add it to the database.

        Args:
            kwargs: any of the column names defined above

        Returns:
            A new Template object initialized with the keyword parameters.
        """
        template = Template(**kwargs)
        template.add()
        return template

    @staticmethod
    def find(name: str) -> "Template":
        """
        Return a Template object with the specified base name. For
        example, find("run-data").

        Args:
            name: Base index name

        Raises:
            TemplateSqlError: problem interacting with Database
            TemplateNotFound: the specified template doesn't exist

        Returns:
            Template: a template object with the specified base name
        """
        try:
            template = Database.db_session.query(Template).filter_by(name=name).first()
        except SQLAlchemyError as e:
            Template.logger.warning("Error looking for {}: {}", name, str(e))
            raise TemplateSqlError("finding", name)

        if template is None:
            raise TemplateNotFound(name)
        return template

    def __str__(self) -> str:
        """
        Return a string representation of the template

        Returns:
            string: Representation of the template
        """
        return f"{self.name}: {self.index_template}"

    def _decode(self, exception: IntegrityError) -> Exception:
        """
        Decode a SQLAlchemy IntegrityError to look for a recognizable UNIQUE
        or NOT NULL constraint violation. Return the original exception if
        it doesn't match.

        Args:
            exception: An IntegrityError to decode

        Returns:
            a more specific exception, or the original if decoding fails
        """
        # Postgres engine returns (code, message) but sqlite3 engine only
        # returns (message); so always take the last element.
        cause = exception.orig.args[-1]
        if cause.find("UNIQUE constraint") != -1:
            Template.logger.warning("Duplicate template {!r}: {}", self.name, cause)
            return TemplateDuplicate(self.name)
        elif cause.find("NOT NULL constraint") != -1:
            Template.logger.warning("Missing parameter {!r}, {}", self.name, cause)
            return TemplateMissingParameter(self.name, cause)
        Template.logger.exception("Other integrity error {}", cause)
        return exception

    def add(self):
        """
        Add the Template object to the database
        """
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except IntegrityError as e:
            Database.db_session.rollback()
            raise self._decode(e)
        except Exception:
            self.logger.exception("Can't add {} to DB", str(self))
            Database.db_session.rollback()
            raise TemplateSqlError("adding", self.name)

    def update(self):
        """
        Update the database row with the modified version of the
        Template object.
        """
        try:
            Database.db_session.commit()
        except IntegrityError as e:
            Database.db_session.rollback()
            raise self._decode(e)
        except Exception:
            self.logger.error("Can't update {} in DB", str(self))
            Database.db_session.rollback()
            raise TemplateSqlError("updating", self.name)


@event.listens_for(Template, "init")
def check_required(target, args, kwargs):
    """
    Listen for an init event on Template to validate that a filename was
    specified; and automatically capture the file's modification timestamp
    if it wasn't given.
    """
    if "file" not in kwargs:
        raise TemplateFileMissing(kwargs["name"])

    if "mtime" not in kwargs:
        kwargs["mtime"] = datetime.datetime.fromtimestamp(
            Path(kwargs["file"]).stat().st_mtime
        )
