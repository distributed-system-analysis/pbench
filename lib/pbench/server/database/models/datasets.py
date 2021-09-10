import datetime
import enum
import os
from pathlib import Path
from typing import Any, List, Tuple

from sqlalchemy import (
    event,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.users import User


class DatasetError(Exception):
    """
    DatasetError This is a base class for errors reported by the
                Dataset class. It is never raised directly, but
                may be used in "except" clauses.
    """

    pass


class DatasetSqlError(DatasetError):
    """
    DatasetSqlError SQLAlchemy errors reported through Dataset operations.

    The exception will identify the controller and name of the target dataset,
    along with the operation being attempted; the __cause__ will specify the
    original SQLAlchemy exception.
    """

    def __init__(self, operation: str, controller: str, name: str):
        self.operation = operation
        self.controller = controller
        self.name = name

    def __str__(self) -> str:
        return f"Error {self.operation} dataset {self.controller}|{self.name}"


class DatasetDuplicate(DatasetError):
    """
    DatasetDuplicate Attempt to create a Dataset that already exists.
    """

    def __init__(self, controller: str, name: str):
        self.controller = controller
        self.name = name

    def __str__(self):
        return f"Duplicate dataset {self.controller}|{self.name}"


class DatasetNotFound(DatasetError):
    """
    DatasetNotFound Attempt to attach to a Dataset that doesn't exist.
    """

    def __init__(self, controller: str, name: str):
        self.controller = controller
        self.name = name

    def __str__(self) -> str:
        return f"No dataset {self.controller}|{self.name}"


class DatasetBadParameterType(DatasetError):
    """
    DatasetBadParameterType A parameter of the wrong type was passed to a
                method in the Dataset module.

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
    DatasetTransitionError A base class for errors reporting disallowed
                dataset state transitions. It is never raised directly, but
                may be used in "except" clauses.
    """

    pass


class DatasetTerminalStateViolation(DatasetTransitionError):
    """
    DatasetTerminalStateViolation An attempt was made to change the state of
                a dataset currently in a terminal state.

    The error text will identify the dataset by controller and name, and both
    the current and requested new states.
    """

    def __init__(self, dataset: "Dataset", requested_state: "States"):
        self.dataset = dataset
        self.requested_state = requested_state

    def __str__(self) -> str:
        return f"Dataset {self.dataset} state {self.dataset.state} is terminal and cannot be advanced to {self.requested_state}"


class DatasetBadStateTransition(DatasetTransitionError):
    """
    DatasetTransitionError An attempt was made to advance a dataset to a new
                state that's not reachable from the current state.

    The error text will identify the dataset by controller and name, and both
    the current and requested new states.
    """

    def __init__(self, dataset: "Dataset", requested_state: "States"):
        self.dataset = dataset
        self.requested_state = requested_state

    def __str__(self) -> str:
        return f"Dataset {self.dataset} desired state {self.requested_state} is not allowed from current state {self.dataset.state}"


class MetadataError(DatasetError):
    """
    MetadataError A base class for errors reported by the Metadata class. It
                is never raised directly, but may be used in "except" clauses.
    """

    def __init__(self, dataset: "Dataset", key: str):
        self.dataset = dataset
        self.key = key

    def __str__(self) -> str:
        return f"Generic error on {self.dataset} key {self.key}"


class MetadataSqlError(MetadataError):
    """
    MetadataSqlError SQLAlchemy errors reported through Metadata operations.

    The exception will identify the dataset and the metadata key, along with
    the operation being attempted; the __cause__ will specify the original
    SQLAlchemy exception.
    """

    def __init__(self, operation: str, dataset: "Dataset", key: str):
        self.operation = operation
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"Error {self.operation} {self.dataset} key {self.key}"


class MetadataNotFound(MetadataError):
    """
    MetadataNotFound An attempt to `get` or remove a Metadata key that isn't
                present.

    The error text will identify the dataset and metadata key that was
    specified.
    """

    def __init__(self, dataset: "Dataset", key: str):
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"No metadata {self.key} for {self.dataset}"


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
        return f"Metadata key {self.key} is not supported"


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
    MetadataMissingKeyValue A value must be specified for the metadata key.

    The error text will identify the metadata key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Metadata key {self.key} value is required"


class MetadataDuplicateKey(MetadataError):
    """
    MetadataDuplicateKey An attempt to add a Metadata key that already exists
                on the dataset.

    The error text will identify the dataset and metadata key that was
    specified.
    """

    def __init__(self, dataset: "Dataset", key: str):
        super().__init__(dataset, key)

    def __str__(self) -> str:
        return f"{self.dataset} already has metadata key {self.key}"


class States(enum.Enum):
    """
    States: Track the progress of a dataset (tarball) through the various
    stages and operation of the Pbench server.
    """

    UPLOADING = ("Uploading", True)
    UPLOADED = ("Uploaded", False)
    UNPACKING = ("Unpacking", True)
    UNPACKED = ("Unpacked", False)
    INDEXING = ("Indexing", True)
    INDEXED = ("Indexed", False)
    EXPIRING = ("Expiring", True)
    EXPIRED = ("Expired", False)
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


class Dataset(Database.Base):
    """
    Identify a Pbench dataset (tarball plus metadata)

    Columns:
        id          Generated unique ID of table row
        owner       Owning username of the dataset
        access      Dataset is "private" to owner, or "public"
        controller  Name of controller node
        name        Base name of dataset (tarball)
        md5         The dataset MD5 hash (Elasticsearch ID)
        created     Date the dataset was PUT to server
        state       The current state of the dataset
        transition  The timestamp of the last state transition
    """

    __tablename__ = "datasets"

    transitions = {
        States.UPLOADING: [States.UPLOADED, States.QUARANTINED],
        States.UPLOADED: [States.UNPACKING, States.QUARANTINED],
        States.UNPACKING: [States.UNPACKED, States.QUARANTINED],
        States.UNPACKED: [States.INDEXING, States.QUARANTINED],
        States.INDEXING: [States.INDEXED, States.QUARANTINED],
        States.INDEXED: [States.INDEXING, States.EXPIRING, States.QUARANTINED],
        States.EXPIRING: [States.EXPIRED, States.INDEXED, States.QUARANTINED],
        # NOTE: EXPIRED and QUARANTINED do not appear as keys in the table
        # because they're terminal states that cannot be exited.
    }

    # "Virtual" metadata key paths to access Dataset column data
    ACCESS = "dataset.access"
    OWNER = "dataset.owner"

    # Acceptable values of the "access" column
    #
    # TODO: This may be expanded in the future to support groups
    PUBLIC_ACCESS = "public"
    PRIVATE_ACCESS = "private"
    ACCESS_KEYWORDS = [PUBLIC_ACCESS, PRIVATE_ACCESS]

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User")
    access = Column(String(255), unique=False, nullable=False, default="private")
    controller = Column(String(255), unique=False, nullable=False)
    name = Column(String(255), unique=False, nullable=False)

    # FIXME:
    # Ideally, `md5` would not be `nullable`, but allowing it means that
    # pbench-server-prep-shim-002 utility can construct a Dataset object
    # before accessing and checking the MD5 (in order to ensure that we
    # always have a Dataset before deciding to `quarantine` a dataset.)
    #
    # This could be improved when we drop `pbench-server-prep-shim-002`
    # as server `PUT` does not have the same problem.
    md5 = Column(String(255), unique=False, nullable=True)
    created = Column(DateTime, nullable=False, default=datetime.datetime.now())
    state = Column(Enum(States), unique=False, nullable=False, default=States.UPLOADING)
    transition = Column(DateTime, nullable=False, default=datetime.datetime.now())

    # NOTE: this relationship defines a `dataset` property in `Metadata`
    # that refers to the parent `Dataset` object.
    metadatas = relationship("Metadata", backref="dataset")

    # Require that the combination of controller and name is unique.
    #
    # NOTE: some existing server code depends on "name" alone being unique,
    # although it's not entirely clear that any code enforces this except
    # within a controller directory. (Although as a real dataset tarball is
    # timestamped, the chances of duplication are small.)
    __table_args__ = (UniqueConstraint("controller", "name"), {})

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

    @validates("owner")
    def validate_owner(self, key: str, value: Any) -> User:
        """
        Validate and translate owner name to User object

        Args:
            key: owner
            value: username

        Raises:
            DatasetBadParameter: the owner value given doesn't resolve to a
                Pbench username.

        Returns:
            User object
        """
        if type(value) is User:
            return value
        elif type(value) is str:
            user = User.query(username=value)
            if user:
                return user
        raise DatasetBadParameterType(value, "username")

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
    def _render_path(patharg=None, controllerarg=None, namearg=None) -> Tuple[str, str]:
        """
        _render_path Process a `path` string and convert it into `controller`
        and/or `name` strings.

        This pre-processes the controller and name before they are presented to
        a query or constructor. If the calling context has only the full file
        path of a dataset, this can extract both "controller" and "name" from
        the path. It can also be used to construct either "controller" or
        "name", as it will fill in either or both if not already present in
        the dict.

        If the path is a symlink (e.g., a "TO-BACKUP" or other Pbench command
        link, most likely when a dataset is quarantined due to some consistency
        check failure), this code will follow the link in order to construct a
        controller name from the original path without needing to make any
        possibly fragile assumptions regarding the structure of the symlink
        name.

        Args:
            patharg: A tarball file path from which the controller (host)
                name, the tarball dataset name (basename minus extension),
                or both will be derived.
            controllerarg: The controller name (hostname) of the dataset;
                this is retained if specified, or will be constructed
                from "path" if not present.
            namearg: The dataset name (file path basename minus ".tar.xz");
                this is retained if specified, or will be constructed from
                "path" if not present

        Returns:
            A tuple of (controller, name) based on the three arguments
        """
        controller_result = controllerarg
        name_result = namearg

        if patharg:
            path = Path(patharg)
            if path.is_symlink():
                path = Path(os.path.realpath(path))
            if not name_result:
                name_result = path.name
                if name_result.endswith(".tar.xz"):
                    name_result = name_result[:-7]
            if not controller_result:
                controller_result = path.parent.name
        return controller_result, name_result

    @staticmethod
    def create(**kwargs) -> "Dataset":
        """
        create A simple factory method to construct a new Dataset object and
        add it to the database.

        Args:
            kwargs (dict):
                "owner": The owner of the dataset; defaults to None.
                "path": A tarball file path from which the controller (host)
                    name, the tarball dataset name (basename minus extension),
                    or both will be derived.
                "controller": The controller name (hostname) of the dataset;
                    this is retained if specified, or will be constructed
                    from "path" if not present.
                "name": The dataset name (file path basename minus ".tar.xz");
                    this is retained if specified, or will be constructed from
                    "path" if not present.
                "state": The initial state of the new dataset.

        Returns:
            A new Dataset object initialized with the keyword parameters.
        """
        try:
            dataset = Dataset(**kwargs)
            dataset.add()
        except Exception:
            Dataset.logger.exception(
                "Failed create: {}|{}", kwargs.get("controller"), kwargs.get("name")
            )
            raise
        return dataset

    @staticmethod
    def attach(path=None, controller=None, name=None, state=None) -> "Dataset":
        """
        attach Attempt to fetch dataset for the controller and dataset name,
        or using a specified file path (see _render_path and the path_init
        event listener for details).

        If state is specified, attach will attempt to advance the dataset to
        that state.

        Args:
            "path": A tarball file path from which the controller (host)
                name, the tarball dataset name (basename minus extension),
                or both will be derived.
            "controller": The controller name (hostname) of the dataset;
                this is retained if specified, or will be constructed
                from "path" if not present.
            "name": The dataset name (file path basename minus ".tar.xz");
                this is retained if specified, or will be constructed from
                "path" if not present.
            "state": The desired state to advance the dataset.

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
        # Make sure we have controller and name from path
        controller, name = Dataset._render_path(path, controller, name)
        try:
            dataset = (
                Database.db_session.query(Dataset)
                .filter_by(controller=controller, name=name)
                .first()
            )
        except SQLAlchemyError as e:
            Dataset.logger.warning(
                "Error attaching {}>{}: {}", controller, name, str(e)
            )
            raise DatasetSqlError("attaching", controller, name) from e

        if dataset is None:
            Dataset.logger.warning("{}>{} not found", controller, name)
            raise DatasetNotFound(controller, name)
        elif state:
            dataset.advance(state)
        return dataset

    def __str__(self) -> str:
        """
        __str__ Return a string representation of the dataset

        Returns:
            string: Representation of the dataset
        """
        return f"{self.owner.username}({self.owner_id})|{self.controller}|{self.name}"

    def advance(self, new_state: States):
        """
        advance Modify the state of the Dataset object, if the new_state is
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
        self.transition = datetime.datetime.now()
        self.update()

    def add(self):
        """
        add Add the Dataset object to the database
        """
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except IntegrityError as e:
            Dataset.logger.exception(
                "Duplicate dataset {}|{}", self.controller, self.name
            )
            raise DatasetDuplicate(self.controller, self.name) from e
        except Exception as e:
            self.logger.exception("Can't add {} to DB", str(self))
            Database.db_session.rollback()
            raise DatasetSqlError("adding", self.controller, self.name) from e

    def update(self):
        """
        update Update the database row with the modified version of the
        Dataset object.
        """
        try:
            Database.db_session.commit()
        except Exception as e:
            self.logger.error("Can't update {} in DB", str(self))
            Database.db_session.rollback()
            raise DatasetSqlError("updating", self.controller, self.name) from e


@event.listens_for(Dataset, "init")
def path_init(target, args, kwargs):
    """Listen for an init event on a Dataset to process a path before the
    SQLAlchemy constructor sees it.

    We want the constructor to see both "controller" and "name" parameters in
    the kwargs representing the initial SQL column values. This listener allows
    us to provide those values by specifying a file path, which is processed
    into controller and name using the internal _render_path() helper.

    We will remove "path" from kwargs so that SQLAlchemy doesn't see it. (This
    is an explicitly allowed side effect of the listener architecture.)
    """
    if "path" in kwargs:
        controller, name = Dataset._render_path(
            patharg=kwargs.get("path"),
            controllerarg=kwargs.get("controller"),
            namearg=kwargs.get("name"),
        )
        if "controller" not in kwargs:
            kwargs["controller"] = controller
        if "name" not in kwargs:
            kwargs["name"] = name
        del kwargs["path"]


class Metadata(Database.Base):
    """Retain secondary information about datasets

    Columns:
        id          Generated unique ID of table row
        dataset_ref Dataset row ID (foreign key)
        key         Metadata key string
        value       Metadata value string
    """

    __tablename__ = "dataset_metadata"

    # "Native" keys are the value of the PostgreSQL "key" column in the SQL
    # table. We support hierarchical nested keys of the form "server.indexed",
    # but the first element of any nested key path must be one of these:
    NATIVE_KEYS = ["dashboard", "server", "user"]

    # +++ Standard Metadata keys:
    #
    # Metadata accessible through the API comes from both the parent Dataset
    # object and from JSON documents associated with multiple Metadata keys
    # attached to that Dataset.
    #
    # "Virtual" metadata keys representing Dataset column values have no prefix
    # and use the column name: "access", "owner";
    #
    # Metadata keys reserved for internal modification within the server are in
    # the "server" namespace, and are strictly controlled by keyword path:
    # e.g., "server.deleted", "server.archived";
    #
    # Metadata keys intended for use by the dashboard client are in the
    # "dashboard" namespace, and are also strictly controlled by keyword path:
    # e.g., "dashboard.seen", "dashboard.saved". While these can be modified by
    # any API client, the separate namespace provides some protection against
    # accidental modifications that might break dashboard semantics. Adding a
    # key to this namespace requires server modifications to define the new
    # keyword.
    #
    # Metadata keys within the "user" namespace are reserved for general client
    # use, although by convention a second-level key-space should be used to
    # provide some isolation. This is an "open" namespace, meaning that any API
    # client can define new keywords such as "user.contact" or "user.me.you"
    # and JSON subdocuments are available at any level. For example, if we've
    # set "user.contact.email" and "user.postman.test" then retrieving "user"
    # will return a JSON document like
    #     {"contact": {"email": "value"}, "postman": {"test": "value"}}
    # and retrieving "user.contact" would return
    #     {"email": "value"}
    #
    # The following class constants define the set of currently available
    # metadata keys, where the open "user" namespace is represented by the
    # special syntax "user.*".

    # DELETION timestamp for dataset based on user settings and system
    # settings at time the dataset is created.
    #
    # {"server.deletion": "2021-12-25"}
    DELETION = "server.deletion"

    # SEEN boolean flag to indicate that a user has acknowledged the new
    # dataset.
    #
    # {"dashboard.seen": True}
    SEEN = "dashboard.seen"

    # SAVED boolean flag to indicate that a user has accepted the new dataset
    # for further curation.
    #
    # {"dashboard.saved": True}
    SAVED = "dashboard.saved"

    # USER is arbitrary data saved on behalf of the owning user, as a JSON
    # document.
    #
    # Note that the hierarchical key management in the getvalue and setvalue
    # static methods (used consistently by the API layer) allow client code
    # to interact with these either as a complete JSON document ("user") or
    # as a full dotted key path ("user.contact.name.first") or at any JSON
    # layer between.
    #
    # API keyword validation uses the trailing ".*" here to indicate that only
    # the first element of the path should be validated, allowing the client
    # a completely uninterpreted namespace below that.
    #
    # {"user.cloud": "AWS", "user.mood": "CLOUDY"}}
    USER = "user.*"

    # REINDEX boolean flag to indicate when a dataset should be re-indexed
    #
    # {"server.reindex": True}
    REINDEX = "server.reindex"

    # ARCHIVED boolean flag to indicate when a tarball has been archived
    #
    # {"server.archived": True}
    ARCHIVED = "server.archived"

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
    USER_UPDATEABLE_METADATA = [SAVED, SEEN, USER]

    # Metadata keys that are accessible to clients
    USER_METADATA = USER_UPDATEABLE_METADATA + [DELETION]

    # Metadata keys that are for internal use only
    INTERNAL_METADATA = [REINDEX, ARCHIVED, TARBALL_PATH, INDEX_MAP]

    # All supported Metadata keys
    METADATA_KEYS = USER_METADATA + INTERNAL_METADATA

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=False, nullable=False, index=True)
    value = Column(JSON, unique=False, nullable=True)
    dataset_ref = Column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )

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
        v = value.lower()
        if type(v) is not str or v not in Metadata.NATIVE_KEYS:
            raise MetadataBadKey(value)
        return v

    @staticmethod
    def create(**kwargs) -> "Metadata":
        """
        Create a new Metadata object. This will fail if the key already exists
        for the referenced Dataset.

        NOTE: use this only for raw first-level Metadata keys, not dotted
        paths like "dashboard.seen", which will fail key validation. Instead,
        use the higher-level `set` helper.

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
    def is_key_path(key: str, valid: List[str]) -> bool:
        """
        Determine whether 'key' is a valid Metadata key path using the list
        specified in 'valid'. If the specified key is in the list, then it's
        valid. If the key is a dotted path and the first element plus a
        trailing ".*" is in the list, then this is an open key namespace where
        any subsequent path is acceptable: e.g., "user.*" allows "user", or
        "user.contact", "user.contact.name", etc.

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
        # Check for open namespace match
        return path[0] + ".*" in valid

    @staticmethod
    def getvalue(dataset: Dataset, key: str) -> JSON:
        """
        Returns the value of the specified key, which may be a dotted
        hierarchical path (e.g., "server.deleted").

        The specific value of the dotted key path is returned, not the
        top level Metadata object. (Note that this can always be found
        using Metadata.get(dataset, key)).

        E.g., for "user.contact.name" with the dataset's Metadata value for the
        "user" key as {"contact": {"name": "Dave", "email": "d@example.com"}},
        this would return "Dave".

        Args:
            dataset: associated dataset
            key: hierarchical key path to fetch

        Returns:
            Value of the key path
        """
        keys = key.lower().split(".")
        native_key = keys.pop(0)
        try:
            meta = Metadata.get(dataset, native_key)
            value = meta.value
            for i in keys:
                if i not in value:
                    return None
                value = value[i]
        except MetadataNotFound:
            value = None
        return value

    @staticmethod
    def setvalue(dataset: Dataset, key: str, value: Any) -> "Metadata":
        """
        Create or modify an existing metadata value. This method supports
        hierarchical dotted paths like "dashboard.seen" and should be used in
        most contexts where client-visible metadata paths are used.

        Args:
            dataset: Associated Dataset
            key: Lookup key (inluding hierarchical dotted paths)
            value: Value to be assigned to the specified key

        Returns:
            A Metadata object representing the new database row with the
            properly assigned value.
        """
        keys = key.lower().split(".")
        native_key = keys.pop(0)
        found = True
        try:
            meta = Metadata.get(dataset, native_key)
            meta_value = meta.value.copy()
        except MetadataNotFound:
            found = False
            meta_value = {}
        if not keys:
            meta_value = value
        else:
            hierarchy = meta_value
            for i in range(len(keys) - 1):
                inner_key = keys[i]
                if inner_key not in hierarchy:
                    hierarchy[inner_key] = {}
                hierarchy = hierarchy[inner_key]
            hierarchy[keys[-1]] = value
        if found:
            meta.value = meta_value
            meta.update()
        else:
            meta = Metadata.create(dataset=dataset, key=native_key, value=meta_value)
        return meta

    @staticmethod
    def get(dataset: Dataset, key: str) -> "Metadata":
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
            meta = (
                Database.db_session.query(Metadata)
                .filter_by(dataset=dataset, key=key)
                .first()
            )
        except SQLAlchemyError as e:
            Metadata.logger.exception("Can't get {}>>{} from DB", dataset, key)
            raise MetadataSqlError("getting", dataset, key) from e
        else:
            if meta is None:
                raise MetadataNotFound(dataset, key)
            return meta

    @staticmethod
    def remove(dataset: Dataset, key: str):
        """
        remove Remove a metadata key from the dataset

        Args:
            dataset (Dataset): Dataset with which key is associated
            key (string): Name of metadata key to remove

        Raises:
            DatasetSqlError: Something went wrong
        """
        try:
            Database.db_session.query(Metadata).filter_by(
                dataset=dataset, key=key
            ).delete()
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
            Metadata.get(dataset, self.key)
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
