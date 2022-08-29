import copy
import datetime
import enum
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from dateutil import parser as date_parser
from sqlalchemy import Column, DateTime, Enum, event, ForeignKey, Integer, JSON, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Query, relationship, validates
from sqlalchemy.types import TypeDecorator

from pbench.server import JSONVALUE
from pbench.server.database.database import Database
from pbench.server.database.models.server_config import (
    OPTION_DATASET_LIFETIME,
    ServerConfig,
)


class DatasetError(Exception):
    """
    This is a base class for errors reported by the Dataset class. It is never
    raised directly, but may be used in "except" clauses.
    """

    pass


class DatasetBadName(DatasetError):
    """
    Specified filename does not follow Pbench tarball naming rules.
    """

    def __init__(self, name: Path):
        self.name: str = str(name)

    def __str__(self) -> str:
        return f"File name {self.name!r} does not end in {Dataset.TARBALL_SUFFIX!r}"


class DatasetSqlError(DatasetError):
    """
    SQLAlchemy errors reported through Dataset operations.

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
    """
    Attempt to create a Dataset that already exists.
    """

    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"Duplicate dataset {self.name!r}"


class DatasetNotFound(DatasetError):
    """
    Attempt to attach to a Dataset that doesn't exist.
    """

    def __init__(self, **kwargs):
        self.kwargs = [f"{key}={value}" for key, value in kwargs.items()]

    def __str__(self) -> str:
        return f"No dataset {'|'.join(self.kwargs)}"


class DatasetBadParameterType(DatasetError):
    """
    A parameter of the wrong type was passed to a method in the Dataset module.

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


class DatasetTransitionError(DatasetError):
    """
    A base class for errors reporting disallowed dataset state transitions. It
    is never raised directly, but may be used in "except" clauses.
    """

    pass


class DatasetTerminalStateViolation(DatasetTransitionError):
    """
    An attempt was made to change the state of a dataset currently in a
    terminal state.

    The error text will identify the dataset by name, and both the current and
    requested new states.
    """

    def __init__(self, dataset: "Dataset", requested_state: "States"):
        self.dataset = dataset
        self.requested_state = requested_state

    def __str__(self) -> str:
        return f"Dataset {self.dataset} state {self.dataset.state} is terminal and cannot be advanced to {self.requested_state}"


class DatasetBadStateTransition(DatasetTransitionError):
    """
    An attempt was made to advance a dataset to a new state that's not
    reachable from the current state.

    The error text will identify the dataset by name, and both the current and
    requested new states.
    """

    def __init__(self, dataset: "Dataset", requested_state: "States"):
        self.dataset = dataset
        self.requested_state = requested_state

    def __str__(self) -> str:
        return f"Dataset {self.dataset} desired state {self.requested_state} is not allowed from current state {self.dataset.state}"


class MetadataError(DatasetError):
    """
    A base class for errors reported by the Metadata class. It is never raised
    directly, but may be used in "except" clauses.
    """

    def __init__(self, dataset: "Dataset", key: str):
        self.dataset = dataset
        self.key = key

    def __str__(self) -> str:
        return f"Generic error on {self.dataset} key {self.key}"


class MetadataSqlError(MetadataError):
    """
    SQLAlchemy errors reported through Metadata operations.

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
    """
    An attempt to `get` or remove a Metadata key that isn't present.

    The error text will identify the dataset and metadata key that was
    specified.
    """

    def __init__(self, dataset: "Dataset", key: str):
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"No metadata {self.key} for {self.dataset}"


class MetadataBadStructure(MetadataError):
    """
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
    """
    An unsupported value was specified for a special metadata key

    The error text will identify the metadata key that was specified and the
    actual and expected value type.
    """

    def __init__(self, dataset: "Dataset", key: str, value: str, expected: str):
        super().__init__(dataset, key)
        self.value = value
        self.expected = expected

    def __str__(self) -> str:
        return (
            f"Metadata key {self.key!r} value {self.value!r} for dataset "
            f"{self.dataset} must be a {self.expected}"
        )


class MetadataKeyError(DatasetError):
    """
    A base class for metadata key errors in the context of Metadata errors
    that have no associated Dataset. It is never raised directly, but may
    be used in "except" clauses.
    """


class MetadataMissingParameter(MetadataKeyError):
    """
    A Metadata required parameter was not specified.
    """

    def __init__(self, what: str):
        self.what = what

    def __str__(self) -> str:
        return f"Metadata must specify a {self.what}"


class MetadataBadKey(MetadataKeyError):
    """
    An unsupported metadata key was specified.

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key!r} is not supported"


class MetadataProtectedKey(MetadataKeyError):
    """
    A metadata key was specified that cannot be modified in the current
    context. (Usually an internally reserved key that was referenced in
    an external client API.)

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key} cannot be modified by client"


class MetadataMissingKeyValue(MetadataKeyError):
    """
    A value must be specified for the metadata key.

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key} value is required"


class MetadataDuplicateKey(MetadataError):
    """
    An attempt to add a Metadata key that already exists on the dataset.

    The error text will identify the dataset and metadata key that was
    specified.
    """

    def __init__(self, dataset: "Dataset", key: str):
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"{self.dataset} already has metadata key {self.key}"


class States(enum.Enum):
    """
    Track the progress of a dataset (tarball) through the various stages and
    operation of the Pbench server.
    """

    UPLOADING = ("Uploading", True)
    UPLOADED = ("Uploaded", False)
    INDEXING = ("Indexing", True)
    INDEXED = ("Indexed", False)
    DELETING = ("Deleting", True)
    DELETED = ("Deleted", False)
    QUARANTINED = ("Quarantined", False)

    def __init__(self, friendly: str, mutating: bool):
        """
        __init__ Extended ENUM constructor in order to add a value
        to record whether each state is a "busy" state where some
        component is mutating the dataset in some way, and a mixed
        case "friendly" name for the state. "Mutating" states are
        expected to be transient as the component should complete
        the mutation, and should usually have "-ing" endings.

        Args:
            name (string): Friendly name for the state
            mutating (boolean): True if a component is mutating dataset
        """
        self.friendly = friendly
        self.mutating = mutating

    def __str__(self) -> str:
        """
        Return the state's friendly name
        """
        return self.friendly


def current_time() -> datetime.datetime:
    """
    Return the current time in UTC.

    This provides a Callable that can be specified in the SQLAlchemy Column
    to generate an appropriate (aware UTC) datetime object when a Dataset
    object is created.

    Returns:
        Current UTC timestamp
    """
    return datetime.datetime.now(datetime.timezone.utc)


class TZDateTime(TypeDecorator):
    """
    SQLAlchemy protocol is that stored timestamps are naive UTC; so we use a
    custom type decorator to ensure that our incoming and outgoing timestamps
    are consistent by adjusting TZ before storage and enhancing with UTC TZ
    on retrieval so that we're always working with "aware" UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        "Naive" datetime objects are treated as UTC, and "aware" datetime
        objects are converted to UTC and made "naive" by replacing the TZ
        for SQL storage.
        """
        if value is not None and value.utcoffset() is not None:
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        """
        Retrieved datetime objects are naive, and are assumed to be UTC, so set
        the TZ to UTC to make them "aware". This ensures that we communicate
        the "+00:00" ISO 8601 suffix to API clients.
        """
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value


class Dataset(Database.Base):
    """
    Identify a Pbench dataset (tarball plus metadata)

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

    transitions = {
        States.UPLOADING: [States.UPLOADED, States.QUARANTINED],
        States.UPLOADED: [States.INDEXING, States.QUARANTINED],
        States.INDEXING: [States.INDEXED, States.QUARANTINED],
        States.INDEXED: [States.INDEXING, States.DELETING, States.QUARANTINED],
        States.DELETING: [States.DELETED, States.INDEXED, States.QUARANTINED],
        # NOTE: DELETED and QUARANTINED do not appear as keys in the table
        # because they're terminal states that cannot be exited.
    }

    # "Virtual" metadata key paths to access Dataset column data
    ACCESS = "dataset.access"
    OWNER = "dataset.owner"
    CREATED = "dataset.created"
    UPLOADED = "dataset.uploaded"

    # Acceptable values of the "access" column
    #
    # TODO: This may be expanded in the future to support groups
    PUBLIC_ACCESS = "public"
    PRIVATE_ACCESS = "private"
    ACCESS_KEYWORDS = [PUBLIC_ACCESS, PRIVATE_ACCESS]

    # Generated unique ID for Dataset row
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Dataset name
    name = Column(String(255), unique=False, nullable=False)

    # OIDC UUID of the owning user
    owner_id = Column(String(255), nullable=False)

    # Access policy for Dataset (public or private)
    access = Column(String(255), unique=False, nullable=False, default="private")

    # This is the MD5 hash of the dataset tarball, which we use as the unique
    # dataset resource ID throughout the Pbench server.
    resource_id = Column(String(255), unique=True, nullable=False)

    # Time of Dataset record creation
    uploaded = Column(TZDateTime, nullable=False, default=current_time)

    # Time of the data collection run (from metadata.log `date`). This is the
    # time the data was generated as opposed to the date it was imported into
    # the server ("uploaded").
    created = Column(TZDateTime, nullable=True, unique=False)

    # Current state of the Dataset
    state = Column(Enum(States), unique=False, nullable=False, default=States.UPLOADING)

    # Timestamp when Dataset state was last changed
    transition = Column(TZDateTime, nullable=False, default=current_time)

    # NOTE: this relationship defines a `dataset` property in `Metadata`
    # that refers to the parent `Dataset` object.
    metadatas = relationship(
        "Metadata", back_populates="dataset", cascade="all, delete-orphan"
    )

    TARBALL_SUFFIX = ".tar.xz"

    @staticmethod
    def is_tarball(path: Union[Path, str]) -> bool:
        """
        Determine whether a path has the expected suffix to qualify as a Pbench
        tarball.

        NOTE: The file represented by the path doesn't need to exist, only end
        with the expected suffix.

        Args:
            path: file path

        Returns:
            True if path ends with the supported suffix, False if not
        """
        return str(path).endswith(Dataset.TARBALL_SUFFIX)

    @staticmethod
    def stem(path: Union[str, Path]) -> str:
        """
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

    @validates("state")
    def validate_state(self, key: str, value: Any) -> States:
        """
        Validate that the value provided for the Dataset state is a member
        of the States ENUM before it's applied by the SQLAlchemy constructor.

        Args:
            key: state
            value: state ENUM member

        Raises:
            DatasetBadParameter: the value given doesn't resolve to a
                States ENUM.

        Returns:
            state
        """
        if type(value) is not States:
            raise DatasetBadParameterType(value, States)
        return value

    @validates("access")
    def validate_access(self, key: str, value: str) -> str:
        """
        Validate the access key for the dataset.

        Args:
            key: access
            value: string "private" or "public"

        Raises:
            DatasetBadParameterType: the access value given isn't allowed.

        Returns:
            access keyword string
        """
        access = value.lower()
        if access in Dataset.ACCESS_KEYWORDS:
            return access
        raise DatasetBadParameterType(value, "access keyword")

    @staticmethod
    def create(**kwargs) -> "Dataset":
        """
        A simple factory method to construct a new Dataset object and
        add it to the database.

        Args:
            kwargs (dict):
                access: The dataset access policy
                name: The dataset name (file path stem).
                owner_id: The owner id of the dataset.
                resource_id: The tarball MD5
                state: The initial state of the new dataset.

        Returns:
            A new Dataset object initialized with the keyword parameters.
        """
        try:
            dataset = Dataset(**kwargs)
            dataset.add()
        except Exception:
            Dataset.logger.exception("Failed create: {}", kwargs.get("name"))
            raise
        return dataset

    @staticmethod
    def attach(resource_id: str, state: Optional[States] = None) -> "Dataset":
        """
        Attempt to find the dataset with the specified dataset resource ID.

        If state is specified, attach will attempt to advance the dataset to
        that state.

        NOTE: Unless you need to advance the state of the dataset, use
        Dataset.query instead.

        Args:
            resource_id: The dataset resource ID.
            state: The desired state to advance the dataset.

        Raises:
            DatasetSqlError: problem interacting with Database
            DatasetNotFound: the specified dataset doesn't exist
            DatasetBadParameterType: The state parameter isn't a States ENUM
            DatasetTerminalStateViolation: dataset is in terminal state and
                can't be advanced
            DatasetBadStateTransition: dataset cannot be advanced to the
                specified state

        Returns:
            Dataset: a dataset object in the desired state (if specified)
        """
        dataset = Dataset.query(resource_id=resource_id)

        if dataset is None:
            Dataset.logger.warning("Dataset {} not found", resource_id)
            raise DatasetNotFound(resource_id=resource_id)
        elif state:
            dataset.advance(state)
        return dataset

    @staticmethod
    def query(**kwargs) -> "Dataset":
        """
        Query dataset object based on a given column name of the run document
        """
        try:
            dataset = Database.db_session.query(Dataset).filter_by(**kwargs).first()
        except SQLAlchemyError as e:
            Dataset.logger.warning("Error querying {}: {}", kwargs, str(e))
            raise DatasetSqlError("querying", **kwargs)

        if dataset is None:
            raise DatasetNotFound(**kwargs)

        return dataset

    def as_dict(self) -> Dict[str, Any]:
        """
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
        return {
            "access": self.access,
            "created": self.created.isoformat() if self.created else None,
            "name": self.name,
            "owner_id": self.owner_id,
            "state": str(self.state),
            "transition": self.transition.isoformat(),
            "uploaded": self.uploaded.isoformat(),
            Metadata.METALOG: metadata_log,
        }

    def __str__(self) -> str:
        """
        Return a string representation of the dataset

        Returns:
            string: Representation of the dataset
        """
        return f"({self.owner_id})|{self.name}"

    def advance(self, new_state: States):
        """
        Modify the state of the Dataset object, if the new_state is
        a valid transition from the dataset's current state.

        Args:
            new_state (State ENUM): New desired state for the dataset

        Raises:
            DatasetBadParameterType: The state parameter isn't a States ENUM
            DatasetTerminalStateViolation: The dataset is in a terminal state
                that cannot be changed.
            DatasetBadStateTransition: The dataset does not support transition
                from the current state to the desired state.
        """
        if type(new_state) is not States:
            raise DatasetBadParameterType(new_state, States)
        if self.state not in self.transitions:
            self.logger.error(
                "Terminal state {} can't advance to {}", self.state, new_state
            )
            raise DatasetTerminalStateViolation(self, new_state)
        elif new_state not in self.transitions[self.state]:
            self.logger.error(
                "Current state {} can't advance to {}", self.state, new_state
            )
            raise DatasetBadStateTransition(self, new_state)

        # TODO: this would be a good place to generate an audit log

        self.state = new_state
        self.transition = datetime.datetime.utcnow()
        self.update()

    def add(self):
        """
        Add the Dataset object to the database
        """
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except IntegrityError as e:
            Dataset.logger.warning("Duplicate dataset {}: {}", self.name, e)
            Database.db_session.rollback()
            raise DatasetDuplicate(self.name) from None
        except Exception:
            self.logger.exception("Can't add {} to DB", str(self))
            Database.db_session.rollback()
            raise DatasetSqlError("adding", name=self.name)

    def update(self):
        """
        Update the database row with the modified version of the
        Dataset object.
        """
        try:
            Database.db_session.commit()
        except Exception:
            self.logger.error("Can't update {} in DB", str(self))
            Database.db_session.rollback()
            raise DatasetSqlError("updating", name=self.name)

    def delete(self):
        """
        Delete the Dataset from the database
        """
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise


class Metadata(Database.Base):
    """
    Retain secondary information about datasets

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

    # "Native" keys are the value of the PostgreSQL "key" column in the SQL
    # table. We support hierarchical nested keys of the form "server.indexed",
    # but the first element of any nested key path must be one of these. The
    # METALOG key is special, representing the Metadata table portion of the
    # DATASET
    METALOG = "metalog"
    NATIVE_KEYS = [GLOBAL, METALOG, SERVER, USER]

    # DELETION timestamp for dataset based on user settings and system
    # settings when the dataset is created.
    #
    # {"server.deletion": "2021-12-25"}
    DELETION = "server.deletion"

    # REINDEX boolean flag to indicate when a dataset should be re-indexed
    #
    # {"server.reindex": True}
    REINDEX = "server.reindex"

    # ARCHIVED boolean flag to indicate when a tarball has been archived
    #
    # {"server.archived": True}
    ARCHIVED = "server.archived"

    # OPERATION tag to tell the Pbench Server cron tools which operation needs
    # to be performed next, replacing the old STATE symlink subdirectories.
    OPERATION = "server.operation"

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
    USER_UPDATEABLE_METADATA = [DATASET_NAME, DELETION, GLOBAL, USER]

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

    dataset = relationship("Dataset", back_populates="metadatas", single_parent=True)
    user_id = Column(String(255), nullable=True)

    @validates("key")
    def validate_key(self, _, value: Any) -> str:
        """
        SQLAlchemy validator to check the specified value of a model object
        attribute (column).

        Args:
            _: Name of the model attribute (always "key" because of the
                decorator parameter, so we ignore it)
            value: Specified value for the "key" attribute
        """
        if type(value) is str:
            v = value.lower()
            if v in Metadata.NATIVE_KEYS:
                return v
        raise MetadataBadKey(value)

    @staticmethod
    def create(**kwargs) -> "Metadata":
        """
        Create a new Metadata object. This will fail if the key already exists
        for the referenced Dataset.

        NOTE: use this only for raw first-level Metadata keys, not dotted
        paths like "global.seen", which will fail key validation. Instead,
        use the higher-level `setvalue` helper.

        Args:
            dataset: Associated Dataset
            key: Metadata key
            value: Metadata value
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
        """
        Extract the root key name

        Args:
            key:    Key path (e.g., "user.tag")

        Returns:
            native SQL key name ("user")
        """
        return key.lower().split(".")[0]

    @staticmethod
    def is_key_path(key: str, valid: List[str]) -> bool:
        """
        Determine whether 'key' is a valid Metadata key path using the list
        specified in 'valid'. If the "native" key (first element of a dotted
        path) is in the list, then it's valid.

        NOTE: we only validate the "native" key of the path. The "global"
        and "user" namespaces are completely open for any subsidiary keys the
        caller desires. The "dataset" and "server" namespaces are internally
        defined by Pbench, and can't be modified by the client, however a query
        for a metadata key that's not defined will simply return None. This
        seems preferable to building a complicated multi-level keyword path
        validator and provides a degree of version independence. (That is, if
        we add "server.nextgenkey" a query for that key on a previous server
        version will return None rather than failing in validation.)

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
    def getvalue(dataset: Dataset, key: str, user_id: Optional[str] = None) -> JSON:
        """
        Returns the value of the specified key, which may be a dotted
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
            dataset: associated dataset
            key: hierarchical key path to fetch
            user: User-specific key value (used only for "user." namespace)

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
    def validate(dataset: Dataset, key: str, value: Any) -> Any:
        """
        Create or modify an existing metadata value. This method supports
        hierarchical dotted paths like "global.seen" and should be used in
        most contexts where client-visible metadata paths are used.

        1) For 'dataset.name', we require a UTF-8 encoded string of 1 to 32
           characters.
        2) For 'server.deletion', the string must be an ISO date/time string,
           and we fail otherwise. We store only the UTC date, as we don't
           guarantee that deletion will occur at any specific time of day.

        For any other key value, there's no required format.

        Args:
            dataset: Associated Dataset
            key: Lookup key (including hierarchical dotted paths)
            value: Value to be assigned to the specified key

        Returns:
            A validated (and possibly altered) key value
        """
        if key == __class__.DATASET_NAME:
            if (
                type(value) is not str
                or len(value) > __class__.MAX_NAME_LEN
                or len(value) < __class__.MIN_NAME_LEN
            ):
                raise MetadataBadValue(
                    dataset,
                    key,
                    value,
                    f"UTF-8 string of {__class__.MIN_NAME_LEN} to {__class__.MAX_NAME_LEN} characters",
                )

            try:
                value.encode("utf-8", errors="strict")
            except UnicodeDecodeError as u:
                raise MetadataBadValue(dataset, key, value, "UTF-8 string") from u

            return value
        elif key == __class__.DELETION:
            try:
                target = date_parser.parse(value).astimezone(datetime.timezone.utc)
            except date_parser.ParserError as p:
                raise MetadataBadValue(dataset, key, value, "date/time") from p

            max_retention = ServerConfig.get(key=OPTION_DATASET_LIFETIME)
            maximum = dataset.uploaded + datetime.timedelta(
                days=int(max_retention.value)
            )
            if target > maximum:
                raise MetadataBadValue(
                    dataset, key, value, f"date/time before {maximum:%Y-%m-%d}"
                )
            target += __class__.ONE_DAY
            return f"{target:%Y-%m-%d}"
        else:
            return value

    @staticmethod
    def setvalue(dataset: Dataset, key: str, value: Any, user_id: Optional[str] = None):
        """
        Create or modify an existing metadata value. This method supports
        hierarchical dotted paths like "dashboard.seen" and should be used in
        most contexts where client-visible metadata paths are used.

        This will create a nested JSON structure (represented as a Python dict)
        as necessary as it descends the hierarchy. For example, if you assign
        "a.b.c" a value of "bar", and then query "a", you'll get back
        "a": {"b": {"c": "bar"}}}

        Args:
            dataset: Associated Dataset
            key: Lookup key (including hierarchical dotted paths)
            value: Value to be assigned to the specified key
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
            dataset.update()
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
        """
        Fetch a Metadata (row) from the database by key name.

        Args:
            dataset: Associated Dataset
            key: Lookup key (root native SQL row key)

        Raises:
            MetadataSqlError: SQL error in retrieval
            MetadataNotFound: No value exists for specified key

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
        """
        remove Remove a metadata key from the dataset

        Args:
            dataset (Dataset): Dataset with which key is associated
            key (string): Name of metadata key to remove

        Raises:
            DatasetSqlError: Something went wrong
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
        """
        Add the Metadata object to the dataset
        """
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
            Metadata.logger.exception("Can't add {}>>{} to DB", dataset, self.key)
            Database.db_session.rollback()
            dataset.metadatas.remove(self)
            raise MetadataSqlError("adding", dataset, self.key) from e

    def update(self):
        """
        update Update the database with the modified Metadata.
        """
        try:
            Database.db_session.commit()
        except Exception as e:
            Metadata.logger.exception("Can't update {} in DB", self)
            Database.db_session.rollback()
            raise MetadataSqlError("updating", self.dataset, self.key) from e

    def delete(self):
        """
        delete Remove the Metadata from the database.
        """
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception as e:
            Metadata.logger.exception("Can't delete {} from DB", self)
            Database.db_session.rollback()
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
