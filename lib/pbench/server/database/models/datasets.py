import copy
import datetime
import enum
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from dateutil import parser as date_parser
from sqlalchemy import Column, Enum, event, ForeignKey, Integer, JSON, String
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Query, relationship, validates

from pbench.server.database.database import Database
from pbench.server.database.models import TZDateTime
from pbench.server.database.models.server_config import (
    OPTION_DATASET_LIFETIME,
    ServerConfig,
)


class DatasetError(Exception):
    """A base class for errors reported by the Dataset class.

    It is never raised directly, but may be used in "except" clauses.
    """


class DatasetBadName(DatasetError):
    """Specified filename does not follow Pbench tarball naming rules."""

    def __init__(self, name: Path):
        self.name: str = str(name)

    def __str__(self) -> str:
        return f"File name {self.name!r} does not end in {Dataset.TARBALL_SUFFIX!r}"


class DatasetSqlError(DatasetError):
    """SQLAlchemy errors reported through Dataset operations.

    The exception will identify the name of the target dataset, along with the
    operation being attempted; the __cause__ will specify the original
    SQLAlchemy exception.
    """

    def __init__(self, operation: str, **kwargs):
        self.operation = operation
        self.kwargs = [f"{key}={value}" for key, value in kwargs.items()]

    def __str__(self) -> str:
        return f"Error {self.operation} dataset {'|'.join(self.kwargs)}"


class DatasetDuplicate(DatasetError):
    """Attempt to create a Dataset that already exists."""

    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"Duplicate dataset {self.name!r}"


class DatasetNotFound(DatasetError):
    """Attempt to locate a Dataset that doesn't exist."""

    def __init__(self, **kwargs):
        self.kwargs = [f"{key}={value}" for key, value in kwargs.items()]

    def __str__(self) -> str:
        return f"No dataset {'|'.join(self.kwargs)}"


class DatasetBadParameterType(DatasetError):
    """A parameter of the wrong type was passed to a method in the Dataset
    module.

    The error text will identify the actual value and type, and the expected
    type.
    """

    def __init__(self, bad_value: Any, expected_type: Any):
        self.bad_value = bad_value
        self.expected_type = (
            expected_type.__name__ if isinstance(expected_type, type) else expected_type
        )

    def __str__(self) -> str:
        return f'Value "{self.bad_value}" ({type(self.bad_value)}) is not a {self.expected_type}'


class MetadataError(DatasetError):
    """A base class for errors reported by the Metadata class.

    It is never raised directly, but may be used in "except" clauses.
    """

    def __init__(self, dataset: "Dataset", key: str):
        self.dataset = dataset
        self.key = key

    def __str__(self) -> str:
        return f"Generic error on {self.dataset} key {self.key}"


class MetadataSqlError(MetadataError):
    """SQLAlchemy errors reported through Metadata operations.

    The exception will identify the dataset and the metadata key, along with
    the operation being attempted; the __cause__ will specify the original
    SQLAlchemy exception.
    """

    def __init__(self, operation: str, dataset: "Dataset", key: str):
        self.operation = operation
        super().__init__(dataset, key)

    def __str__(self) -> str:
        ds = str(self.dataset) if self.dataset else "no dataset"
        return f"Error {self.operation} {ds} key {self.key}"


class MetadataNotFound(MetadataError):
    """An attempt to `get` or remove a Metadata key that isn't present.

    The error text will identify the dataset and metadata key that was
    specified.
    """

    def __init__(self, dataset: "Dataset", key: str):
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"No metadata {self.key} for {self.dataset}"


class MetadataBadStructure(MetadataError):
    """Invalid metadata structure encountered.

    A call to `getvalue` or `setvalue` found a level in the JSON document where
    the caller's key expected a nested JSON object but the type at that level
    is something else. For example, when `user.contact.email` finds that
    `user.contact` is a string, it's impossible to look up the `email` field.

    The error text will identify the key path and the expected key element that
    is missing.
    """

    def __init__(self, dataset: "Dataset", path: str, element: str):
        super().__init__(dataset, path)
        self.element = element

    def __str__(self) -> str:
        return f"Key {self.element!r} value for {self.key!r} in {self.dataset} is not a JSON object"


class MetadataBadValue(MetadataError):
    """An unsupported value was specified for a special metadata key.

    The error text will identify the metadata key that was specified and the
    actual and expected value type.
    """

    def __init__(
        self, dataset: Optional["Dataset"], key: str, value: str, expected: str
    ):
        """Construct an exception to report a failure in metadata key validation.

        This is used during creation of a new dataset where we don't yet have a
        Dataset object, so the caller can omit the dataset.

        Args:
            dataset: Identify the associated dataset, or None before creation
            key: Metadata key name
            value: Metadata key value
            expected: The expected metadata value type
        """
        super().__init__(dataset, key)
        self.value = value
        self.expected = expected

    def __str__(self) -> str:
        return (
            f"Metadata key {self.key!r} value {self.value!r} for dataset"
            f"{' ' + str(self.dataset) if self.dataset else ''} must be a {self.expected}"
        )


class MetadataKeyError(MetadataError):
    """A base class for metadata key errors in the context of Metadata errors
    that have no associated Dataset.

    It is never raised directly, but may be used in "except" clauses.
    """


class MetadataMissingParameter(MetadataKeyError):
    """A Metadata required parameter was not specified."""

    def __init__(self, what: str):
        self.what = what

    def __str__(self) -> str:
        return f"Metadata must specify a {self.what}"


class MetadataBadKey(MetadataKeyError):
    """An unsupported metadata key was specified.

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key!r} is not supported"


class MetadataProtectedKey(MetadataKeyError):
    """A metadata key was specified that cannot be modified in the current
    context.

    Usually an internally reserved key that was referenced in an external
    client API.

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key} cannot be modified by client"


class MetadataMissingKeyValue(MetadataKeyError):
    """A value must be specified for the metadata key.

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key} value is required"


class MetadataDuplicateKey(MetadataError):
    """An attempt to add a Metadata key that already exists on the dataset.

    The error text will identify the dataset and metadata key that was
    specified.
    """

    def __init__(self, dataset: "Dataset", key: str):
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"{self.dataset} already has metadata key {self.key}"


class Dataset(Database.Base):
    """Identify a Pbench dataset (tarball plus metadata).

    Columns:
        id          Generated unique ID of table row
        owner_id    Owning UUID of the owner of the dataset
        access      Dataset is "private" to owner, or "public"
        name        Base name of dataset (tarball)
        md5         The dataset MD5 hash (Elasticsearch ID)
        created     Tarball metadata timestamp (set during PUT)
        uploaded    Dataset record creation timestamp
        state       The current state of the dataset
        transition  The timestamp of the last state transition
    """

    __tablename__ = "datasets"

    # "Virtual" metadata key paths to access Dataset column data
    ACCESS = "dataset.access"
    OWNER = "dataset.owner"
    UPLOADED = "dataset.uploaded"

    # Acceptable values of the "access" column
    #
    # TODO: This may be expanded in the future to support groups
    PUBLIC_ACCESS = "public"
    PRIVATE_ACCESS = "private"
    ACCESS_KEYWORDS = [PUBLIC_ACCESS, PRIVATE_ACCESS]

    # Access policy for Dataset (public or private)
    access = Column(String(255), unique=False, nullable=False, default="private")

    # Generated unique ID for Dataset row
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Dataset name
    name = Column(String(1024), unique=False, nullable=False)

    # OIDC UUID of the owning user
    owner_id = Column(String(255), nullable=False)

    # This is the MD5 hash of the dataset tarball, which we use as the unique
    # dataset resource ID throughout the Pbench server.
    resource_id = Column(String(255), unique=True, nullable=False)

    # Time of Dataset record creation
    uploaded = Column(TZDateTime, nullable=False, default=TZDateTime.current_time)

    metadatas = relationship(
        "Metadata", back_populates="dataset", cascade="all, delete-orphan"
    )
    operations = relationship(
        "Operation", back_populates="dataset", cascade="all, delete-orphan"
    )

    TARBALL_SUFFIX = ".tar.xz"

    @staticmethod
    def is_tarball(path: Union[Path, str]) -> bool:
        """Determine whether a path has the expected suffix to qualify as a
        Pbench tarball.

        NOTE: The file represented by the path doesn't need to exist, only end
        with the expected suffix.

        Args:
            path : file path

        Returns:
            True if path ends with the supported suffix, False if not
        """
        return str(path).endswith(Dataset.TARBALL_SUFFIX)

    @staticmethod
    def stem(path: Union[str, Path]) -> str:
        """Convenience method to return full "stem" of a tar ball.

        The Path.stem() removes a single suffix, so our standard "a.tar.xz"
        returns "a.tar" instead of "a". We could double-stem, but instead
        this just checks for the expected 7 character suffix and strips it.

        If the path does not end in ".tar.xz" then the full path.name is
        returned.

        Args:
            path: A file path that might be a Pbench tarball

        Raises:
            BadFilename: the path name does not end in TARBALL_SUFFIX

        Returns:
            The stripped "stem" of the dataset
        """
        p = Path(path)
        if __class__.is_tarball(p):
            return p.name[: -len(Dataset.TARBALL_SUFFIX)]
        else:
            raise DatasetBadName(p)

    @validates("access")
    def validate_access(self, key: str, value: str) -> str:
        """Validate the access key for the dataset.

        Args:
            key : access
            value : string "private" or "public"

        Raises:
            DatasetBadParameterType : the access value given isn't allowed.

        Returns:
            access keyword string
        """
        access = value.lower()
        if access in Dataset.ACCESS_KEYWORDS:
            return access
        raise DatasetBadParameterType(value, "access keyword")

    @staticmethod
    def query(**kwargs) -> "Dataset":
        """Query dataset object based on a given column name of the run document."""
        try:
            dataset = Database.db_session.query(Dataset).filter_by(**kwargs).first()
        except SQLAlchemyError as e:
            Dataset.logger.warning("Error querying {}: {}", kwargs, str(e))
            raise DatasetSqlError("querying", **kwargs)

        if dataset is None:
            raise DatasetNotFound(**kwargs)

        return dataset

    def as_dict(self) -> Dict[str, Any]:
        """Return the Metadata object as a simple dictionary.

        Return a dict representing the extended public view of the dataset,
        including non-private primary SQL columns and the `metadata.log` data
        from the metadata table.

        This mapping provides the basis of the "dataset" metadata namespace
        for the API.

        Returns
            Dictionary representation of the DB object
        """
        try:
            metadata_log = Metadata.get(self, Metadata.METALOG).value
        except MetadataNotFound:
            metadata_log = None
        operations = (
            Database.db_session.query(Operation)
            .filter(Operation.dataset_ref == self.id)
            .all()
        )
        return {
            "access": self.access,
            "name": self.name,
            "owner_id": self.owner_id,
            "uploaded": self.uploaded.isoformat(),
            "metalog": metadata_log,
            "operations": {
                o.name.name: {"state": o.state.name, "message": o.message}
                for o in operations
            },
        }

    def __str__(self) -> str:
        """Provide a string representation of the dataset

        Returns:
            string: Representation of the dataset
        """
        return f"({self.owner_id})|{self.name}"

    def add(self):
        """Add the Dataset object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except IntegrityError as e:
            Database.db_session.rollback()
            self.logger.warning("Duplicate dataset {}: {}", self.name, e)
            raise DatasetDuplicate(self.name) from None
        except Exception:
            Database.db_session.rollback()
            self.logger.exception("Can't add {} to DB", str(self))
            raise DatasetSqlError("adding", name=self.name)

    def update(self):
        """Update the database row with the modified version of the Dataset
        object.
        """
        try:
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            self.logger.error("Can't update {} in DB", str(self))
            raise DatasetSqlError("updating", name=self.name)

    def delete(self):
        """Delete the Dataset from the database."""
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise


class OperationName(enum.Enum):
    """Track and orchestrate the progress of a dataset (tarball) through the
    various stages of the Pbench server.
    """

    BACKUP = enum.auto()
    DELETE = enum.auto()
    INDEX = enum.auto()
    REINDEX = enum.auto()
    TOOLINDEX = enum.auto()
    UNPACK = enum.auto()
    UPDATE = enum.auto()
    UPLOAD = enum.auto()


class OperationState(enum.Enum):
    """Record the status of an Operation as its enabled and retired"""

    READY = enum.auto()
    WORKING = enum.auto()
    OK = enum.auto()
    FAILED = enum.auto()


class Operation(Database.Base):
    """Orchestrate and track the operational flow of datasets through the
    server.

    This table is managed by the Sync class, but defined here with the parent
    Dataset class since they're linked.

    Columns:
        id          Generated unique ID of table row
        dataset_ref Dataset row ID (foreign key)
        name        Operation name (OperationName enum)
        status      Status of operation (OperationStatus enum)
        message     Message explaining operation status
    """

    __tablename__ = "dataset_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Enum(OperationName), index=True)
    state = Column(Enum(OperationState))
    message = Column(String(255))
    dataset_ref = Column(Integer, ForeignKey("datasets.id"))
    dataset = relationship("Dataset", back_populates="operations")


class Metadata(Database.Base):
    """Retain secondary information about datasets

    Columns:
        id          Generated unique ID of table row
        dataset_ref Dataset row ID (foreign key)
        key         Metadata key string
        value       Metadata value string
    """

    __tablename__ = "dataset_metadata"

    # +++ Standard Metadata keys:
    #
    # Metadata accessible through the API comes from both the parent Dataset
    # object and from JSON documents associated with multiple Metadata keys
    # attached to that Dataset.
    #
    # Metadata keys representing Dataset column values are in a virtual
    # "dataset" namespace and use the column name: "dataset.access",
    # "dataset.owner";
    #
    # Metadata keys reserved for internal modification within the server are in
    # the "server" namespace, and are strictly controlled by keyword path:
    # e.g., "server.deleted", "server.archived";
    #
    # The "global" and "user" namespaces can be written by an authenticated
    # client to track external metadata. The difference is that "global" key
    # values are visible to all clients with READ access to the dataset, while
    # the "user" namespace is visible only to clients authenticated to the user
    # that wrote the data. Both are represented as arbitrarily nested JSON
    # objects accessible at any level by a dotted key path. For example, for a
    # value of "global": {"favorite": true, "mine": {"contact": "me"}}, the
    # value of key path "global" is the entire object, "global.favorite" is
    # true, "global.mine" is {"contact": "me"}, and "global.mine.contact" is
    # "me".

    # GLOBAL provides an open metadata namespace allowing a client which is
    # authenticated as the owner of the dataset to define arbitrary metadata
    # accessible to all users.
    #
    # {"global.dashboard.seen": True}
    GLOBAL = "global"

    # DATASET is a "virtual" key namespace representing the columns of the
    # Dataset SQL table. Through Dataset.as_dict() we allow the columns to be
    # accessed as a normal metadata key namespace.
    #
    # {"dataset.created": "3000-03-30T03:30:30.303030+00:00"}
    DATASET = "dataset"

    # The Dataset name column can be modified by the owner
    #
    # {"dataset.name": "my name string"}
    DATASET_NAME = f"{DATASET}.name"

    # SERVER is an internally maintained key namespace for additional metadata
    # relating to the server's management of datasets. The information here is
    # accessible to callers, but can't be changed.
    #
    # {"server.deletion": "3030-03-30T03:30:30.303030+00:00"}
    SERVER = "server"

    # USER provides an open metadata namespace allowing a client which is
    # authenticated to define arbitrary metadata accessible only to that
    # authenticated user. Writing 'user' keys requires only READ access to the
    # referenced dataset, but the value set is visible only to clients that are
    # authenticated as the user which set them. Each user can have its own
    # unique value for these keys, for example "user.favorite". Unauthenticated
    # clients can neither set nor read metadata in the USER namespace.
    #
    # {"user.dashboard.favorite": True}
    USER = "user"

    # "Native" keys are the value of the database "key" column in the SQL table.
    # We support hierarchical nested keys of the form "server.indexed", but the
    # first element of any nested key path must be one of these. The METALOG key
    # is special, representing the Metadata table portion of the DATASET.
    METALOG = "metalog"
    NATIVE_KEYS = [GLOBAL, METALOG, SERVER, USER]

    # DELETION timestamp for dataset based on user settings and system
    # settings when the dataset is created.
    #
    # {"server.deletion": "2021-12-25"}
    SERVER_DELETION = "server.deletion"

    # ARCHIVEONLY allows a user on upload to designate that a dataset should
    # not be unpacked or indexed by the server.
    SERVER_ARCHIVE = "server.archiveonly"

    # ORIGIN allows the client to record the source of the dataset.
    SERVER_ORIGIN = "server.origin"

    # TARBALL_PATH access path of the dataset tarball. (E.g., we could use this
    # to record an S3 object store key.) NOT YET USED.
    #
    # {
    #   "server.tarball-path": "/srv/pbench/archive/fs-version-001/"
    #       "ctrl/example__2021.05.21T07.15.27.tar.xz"
    # }
    TARBALL_PATH = "server.tarball-path"

    # INDEX_MAP a dict recording the set of MD5 document IDs for each
    # Elasticsearch index that contains documents for this dataset.
    #
    # {
    #    "server.index-map": {
    #      "drb.v6.run-data.2021-07": ["MD5"],
    #      "drb.v6.run-toc.2021-07": ["MD5-1", "MD5-2"]
    #    }
    # }
    INDEX_MAP = "server.index-map"

    # --- Standard Metadata keys

    # Metadata keys that clients can update
    #
    # NOTE: the entire "global" and "user" namespaces are writable, but only
    # specific keys in the "dataset" and "server" namespaces can be modified.
    USER_UPDATEABLE_METADATA = [
        DATASET_NAME,
        GLOBAL,
        SERVER_ARCHIVE,
        SERVER_DELETION,
        SERVER_ORIGIN,
        USER,
    ]

    # Metadata keys that clients can read
    METADATA_KEYS = sorted([DATASET, GLOBAL, SERVER, USER])

    # NOTE: the ECMA JSON specification allows JSON "names" (keys) to be any
    # string, though most implementations and schemas enforce or recommend
    # stricter syntax. Pbench restricts dataset metadata open namespace keys to
    # lowercase letters, numbers, underscore, and hyphen, with keys separated
    # by a period.
    _valid_key_charset = re.compile(r"[a-z0-9_.-]+")

    # Dataset name size limits
    MIN_NAME_LEN = 1
    MAX_NAME_LEN = 32

    # 1 day as a delta time
    ONE_DAY = datetime.timedelta(days=1)

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=False, nullable=False, index=True)
    value = Column(JSON, unique=False, nullable=True)
    dataset_ref = Column(Integer, ForeignKey("datasets.id"), nullable=False)

    dataset = relationship("Dataset", back_populates="metadatas")
    user_id = Column(String(255), nullable=True)

    @validates("key")
    def validate_key(self, _, value: Any) -> str:
        """SQLAlchemy validator to check the specified value of a model object
        attribute (column).

        Args:
            _ : Name of the model attribute (always "key" because of the
                decorator parameter, so we ignore it)
            value : Specified value for the "key" attribute
        """
        if type(value) is str:
            v = value.lower()
            if v in Metadata.NATIVE_KEYS:
                return v
        raise MetadataBadKey(value)

    @staticmethod
    def create(**kwargs) -> "Metadata":
        """Create a new Metadata object.

        This will fail if the key already exists for the referenced Dataset.

        NOTE: use this only for raw first-level Metadata keys, not dotted
        paths like "global.seen", which will fail key validation. Instead,
        use the higher-level `setvalue` helper.

        Args:
            dataset : Associated Dataset
            key : Metadata key
            value : Metadata value
        """
        if "dataset" not in kwargs:
            raise MetadataMissingParameter("dataset")
        dataset = kwargs.get("dataset")
        if type(dataset) is not Dataset:
            raise DatasetBadParameterType(dataset, Dataset)

        try:
            meta = Metadata(**kwargs)
            meta.add(dataset)
        except Exception:
            Metadata.logger.exception(
                "Failed create: {}>>{}", kwargs.get("dataset"), kwargs.get("key")
            )
            return None
        else:
            return meta

    @staticmethod
    def get_native_key(key: str) -> str:
        """Extract the root key name.

        Args:
            key : Key path (e.g., "user.tag")

        Returns:
            native SQL key name ("user")
        """
        return key.lower().split(".")[0]

    @staticmethod
    def is_key_path(key: str, valid: List[str]) -> bool:
        """Determine whether 'key' is a valid Metadata key path using the list
        specified in 'valid'.

        If the "native" key (first element of a dotted path) is in the list,
        then it's valid.

        NOTE: we only validate the "native" key of the path.  The "global" and
        "user" namespaces are completely open for any subsidiary keys the
        caller desires.  The "dataset" and "server" namespaces are internally
        defined by Pbench, and can't be modified by the client, however a
        query for a metadata key that's not defined will simply return None.
        This seems preferable to building a complicated multi-level keyword
        path validator and provides a degree of version independence.  (That
        is, if we add "server.nextgenkey" a query for that key on a previous
        server version will return None rather than failing in validation.)

        Args:
            key: metadata key path
            valid: list of acceptable key paths

        Returns:
            True if the path is valid, or False
        """
        k = key.lower()
        # Check for exact match
        if k in valid:
            return True
        path = k.split(".")
        # Disallow ".." and trailing "."
        if "" in path:
            return False
        # Check for namespace match
        if path[0] not in valid:
            return False
        # Check that all open namespace keys are valid symbols
        return bool(re.fullmatch(Metadata._valid_key_charset, k))

    @staticmethod
    def getvalue(
        dataset: Dataset, key: str, user_id: Optional[str] = None
    ) -> Optional[JSON]:
        """Returns the value of the specified key, which may be a dotted
        hierarchical path (e.g., "server.deleted").

        The specific value of the dotted key path is returned, not the top
        level Metadata object. The full JSON value of a top level key can be
        acquired directly using `Metadata.get(dataset, key)`

        For example, if the metadata database has

            "global": {
                    "contact": {
                        "name": "dave",
                        "email": "d@example.com"
                    }
                }

        then Metadata.get(dataset, "global.contact.name") would return

            "Dave"

        whereas Metadata.get(dataset, "global") would return the entire user
        key JSON, such as

            {"global" {"contact": {"name": "Dave", "email": "d@example.com}}}

        Args:
            dataset : associated dataset
            key : hierarchical key path to fetch
            user : User-specific key value (used only for "user." namespace)

        Returns:
            Value of the key path
        """
        if not Metadata.is_key_path(key, Metadata.METADATA_KEYS):
            raise MetadataBadKey(key)
        keys = key.lower().split(".")
        native_key = keys.pop(0)
        if native_key == "dataset":
            value = dataset.as_dict()
        else:
            try:
                meta = Metadata.get(dataset, native_key, user_id)
            except MetadataNotFound:
                return None
            value = meta.value
        name = native_key
        for i in keys:
            # If we have a nested key, and the `value` at this level isn't
            # a dictionary, then the `getvalue` path is inconsistent with
            # the stored data; let the caller know with an exception.
            if type(value) is not dict:
                raise MetadataBadStructure(dataset, key, name)
            if i not in value:
                return None
            value = value[i]
            name = i
        return value

    @staticmethod
    def validate(dataset: Optional[Dataset], key: str, value: Any) -> Any:
        """Validate a metadata value.

        This method supports hierarchical dotted paths like "global.seen" and
        should be used in most contexts where client-visible metadata paths
        are used.

        1) 'dataset.name': a non-empty UTF-8 encoded string.
        2) 'server.deletion': an ISO date/time string. We store only the UTC
           date, as we don't guarantee that deletion will occur at any specific
           time of day. The maximum retention period (from upload) is defined
           by the server configuration dataset-lifetime property.
        3) 'server.archiveonly': a boolean value. When true, the server will
           not unpack or index the dataset. (Only meaningful on upload.)
        4) 'server.origin': a string that can be used to track the origin of a
           dataset.

        For any other key value, there's no required format.

        Args:
            dataset : Associated Dataset
            key : Lookup key (including hierarchical dotted paths)
            value : Value to be assigned to the specified key

        Returns:
            A validated (and possibly altered) key value

        """
        v = value
        if key == __class__.DATASET_NAME:
            if type(v) is not str or not v:
                raise MetadataBadValue(
                    dataset, key, v, "UTF-8 string of 1 to 1024 characters"
                )
            try:
                v.encode("utf-8", errors="strict")
            except UnicodeDecodeError as u:
                raise MetadataBadValue(dataset, key, v, "UTF-8 string") from u
        elif key == __class__.SERVER_DELETION:
            try:
                target = date_parser.parse(v).astimezone(datetime.timezone.utc)
            except date_parser.ParserError as p:
                raise MetadataBadValue(dataset, key, v, "date/time") from p
            max_retention = ServerConfig.get(key=OPTION_DATASET_LIFETIME)

            # If 'dataset' was omitted, then assume the current UTC timestamp.
            base_time = (
                dataset.uploaded
                if dataset
                else datetime.datetime.now(datetime.timezone.utc)
            )
            maximum = base_time + datetime.timedelta(days=int(max_retention.value))
            if target > maximum:
                raise MetadataBadValue(
                    dataset, key, v, f"date/time before {maximum:%Y-%m-%d}"
                )
            target += __class__.ONE_DAY
            v = f"{target:%Y-%m-%d}"
        elif key == __class__.SERVER_ARCHIVE:
            if type(v) is str:
                if v.lower() in ("t", "true", "y", "yes"):
                    v = True
                elif v.lower() in ("f", "false", "n", "no"):
                    v = False
                else:
                    raise MetadataBadValue(dataset, key, v, "boolean")
            elif type(v) is not bool:
                raise MetadataBadValue(dataset, key, v, "boolean")
        elif key == __class__.SERVER_ORIGIN:
            if type(v) is not str:
                raise MetadataBadValue(dataset, key, v, "string")
        return v

    @staticmethod
    def setvalue(dataset: Dataset, key: str, value: Any, user_id: Optional[str] = None):
        """Set a metadata value.

        This method supports hierarchical dotted paths like "dashboard.seen"
        and should be used in most contexts where client-visible metadata
        paths are used.

        This will create a nested JSON structure (represented as a Python dict)
        as necessary as it descends the hierarchy. For example, if you assign
        "a.b.c" a value of "bar", and then query "a", you'll get back
        "a": {"b": {"c": "bar"}}}

        Args:
            dataset : Associated Dataset
            key : Lookup key (including hierarchical dotted paths)
            value : Value to be assigned to the specified key
        """
        if not Metadata.is_key_path(key, Metadata.METADATA_KEYS):
            raise MetadataBadKey(key)
        keys = key.lower().split(".")
        native_key = keys.pop(0)
        found = True
        v = __class__.validate(dataset, key, value)

        # Setting the dataset name is a direct modification to the Dataset SQL
        # column, so do that first and exit without touching the Metadata
        # table.
        if key == __class__.DATASET_NAME:
            dataset.name = v
            try:
                Database.db_session.commit()
            except DataError as e:
                Database.db_session.rollback()
                raise MetadataBadValue(
                    dataset, key, v, "UTF-8 string of 1 to 1024 characters"
                ) from e
            return

        try:
            meta = Metadata.get(dataset, native_key, user_id)

            # SQLAlchemy determines whether to perform an `update` based on the
            # Python object reference. We make a copy here to ensure that it
            # sees we've made a change.
            meta_value = copy.deepcopy(meta.value)
        except MetadataNotFound:
            found = False
            meta_value = {}

        if not keys:
            meta_value = v
        else:
            walker = meta_value
            name = native_key
            for i in range(len(keys)):
                # If we have a nested key, and the `value` at this level isn't
                # a dictionary, then the `setvalue` path is inconsistent with
                # the stored data; let the caller know with an exception.
                if type(walker) is not dict:
                    raise MetadataBadStructure(dataset, key, name)
                inner_key = keys[i]

                # If we've reached the final key, assign the value in this
                # dict; otherwise continue descending.
                if i == len(keys) - 1:
                    walker[inner_key] = v
                else:
                    if inner_key not in walker:
                        walker[inner_key] = {}
                    walker = walker[inner_key]
                    name = inner_key

        if found:
            meta.value = meta_value
            meta.update()
        else:
            Metadata.create(
                dataset=dataset, key=native_key, value=meta_value, user_id=user_id
            )

    @staticmethod
    def _query(dataset: Dataset, key: str, user_id: Optional[str]) -> Query:
        return Database.db_session.query(Metadata).filter_by(
            dataset=dataset, key=key, user_id=user_id
        )

    @staticmethod
    def get(dataset: Dataset, key: str, user_id: Optional[str] = None) -> "Metadata":
        """Fetch a Metadata (row) from the database by key name.

        Args:
            dataset : Associated Dataset
            key : Lookup key (root native SQL row key)

        Raises:
            MetadataSqlError : SQL error in retrieval
            MetadataNotFound : No value exists for specified key

        Returns:
            The Metadata model object
        """
        try:
            meta = __class__._query(dataset, key, user_id).first()
        except SQLAlchemyError as e:
            Metadata.logger.exception("Can't get {}>>{} from DB", dataset, key)
            raise MetadataSqlError("getting", dataset, key) from e
        else:
            if meta is None:
                raise MetadataNotFound(dataset, key)
            return meta

    @staticmethod
    def remove(dataset: Dataset, key: str, user_id: Optional[str] = None):
        """Remove a metadata key from the dataset.

        Args:
            dataset (Dataset) : Dataset with which key is associated
            key (string) : Name of metadata key to remove

        Raises:
            DatasetSqlError : Something went wrong
        """
        try:
            __class__._query(dataset, key, user_id).delete()
            Database.db_session.commit()
        except SQLAlchemyError as e:
            Metadata.logger.exception("Can't remove {}>>{} from DB", dataset, key)
            raise MetadataSqlError("deleting", dataset, key) from e

    def __str__(self) -> str:
        return f"{self.dataset}>>{self.key}"

    def add(self, dataset: Dataset):
        """Add the Metadata object to the dataset."""
        if type(dataset) is not Dataset:
            raise DatasetBadParameterType(dataset, Dataset)

        try:
            Metadata.get(dataset, self.key, self.user_id)
        except MetadataNotFound:
            pass
        else:
            raise MetadataDuplicateKey(dataset, self.key)

        try:
            dataset.metadatas.append(self)
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            self.logger.exception("Can't add {}>>{} to DB", dataset, self.key)
            dataset.metadatas.remove(self)
            raise MetadataSqlError("adding", dataset, self.key) from e

    def update(self):
        """Update the database with the modified Metadata."""
        try:
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            self.logger.exception("Can't update {} in DB", self)
            raise MetadataSqlError("updating", self.dataset, self.key) from e

    def delete(self):
        """Remove the Metadata from the database."""
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            self.logger.exception("Can't delete {} from DB", self)
            raise MetadataSqlError("deleting", self.dataset, self.key) from e


@event.listens_for(Metadata, "init")
def check_required(target, args, kwargs):
    """Listen for an init event on Metadata to verify parameters before the
    SQLAlchemy constructor gets control.

    We want the constructor to see both "key" and "value" parameters; if either
    isn't present, give a simpler and more useful error message rather than the
    internal SQL constraint failures that would result.
    """
    if "key" not in kwargs:
        raise MetadataMissingParameter("key")
    if "value" not in kwargs:
        raise MetadataMissingKeyValue(kwargs.get("key"))
