import datetime
import enum

from email_validator import validate_email
from flask_bcrypt import generate_password_hash
from sqlalchemy import Column, DateTime, Enum, Integer, LargeBinary, String
from sqlalchemy.orm import relationship, validates
from sqlalchemy.orm.exc import NoResultFound

from pbench.server.database.database import Database
from pbench.server.database.models.active_token import ActiveToken
from pbench.server.globals import server


class Roles(enum.Enum):
    ADMIN = 1


class User(Database.Base):
    """User Model for storing user related details"""

    # Table name is plural so it looks better SQL statements.
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(255), unique=False, nullable=False)
    last_name = Column(String(255), unique=False, nullable=False)
    password = Column(LargeBinary(128), nullable=False)
    registered_on = Column(DateTime, nullable=False, default=datetime.datetime.now())
    email = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(Roles), unique=False, nullable=True)
    auth_tokens = relationship("ActiveToken", back_populates="user")

    def __str__(self):
        return f"User, id: {self.id}, username: {self.username}"

    def get_json(self):
        return {
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "registered_on": self.registered_on,
        }

    @staticmethod
    def get_protected():
        """Return protected column names that are not allowed for external
        updates.  auth_tokens is already protected from external updates via
        PUT api since it is of type sqlalchemy relationship ORM package and
        not a sqlalchemy column.
        """
        return ["registered_on", "id"]

    @staticmethod
    def query(id=None, username=None, email=None) -> "User":
        """Find a given user by either their database ID, name, or email.

        Only one of the three keyword arguments will be used for the search,
        where `username` will be used if present, then `id` if present, then
        `email`.

        Returns the user object if found, None if it was not found (and when
        no keyword arguments were given).
        """
        if username:
            user = server.db_session.query(User).filter_by(username=username).first()
        elif id:
            user = server.db_session.query(User).filter_by(id=id).first()
        elif email:
            user = server.db_session.query(User).filter_by(email=email).first()
        else:
            user = None

        return user

    @staticmethod
    def query_all() -> "list[User]":
        return server.db_session.query(User).all()

    def add(self):
        """Add the current user object to the database."""
        try:
            server.db_session.add(self)
            server.db_session.commit()
        except Exception:
            server.db_session.rollback()
            raise

    @validates("role")
    def evaluate_role(self, key, value):
        try:
            return Roles[value.upper()]
        except KeyError:
            return None

    @validates("password")
    def evaluate_password(self, key, value):
        return generate_password_hash(value)

    @validates("email")
    def evaluate_email(self, key, value):
        valid = validate_email(value)
        return valid.email

    def add_token(self, token: ActiveToken):
        """Add the given token to active tokens list for this user."""
        try:
            self.auth_tokens.append(token)
            server.db_session.add(token)
            server.db_session.commit()
        except Exception:
            server.db_session.rollback()
            raise

    def update(self, **kwargs):
        """Update the current user object with given keyword arguments."""
        try:
            for key, value in kwargs.items():
                setattr(self, key, value)
            server.db_session.commit()
        except Exception:
            server.db_session.rollback()
            raise

    @staticmethod
    def delete(username):
        """Delete the user with a given username except admin.

        Args:
            username : The name of the user to delete

        Raises `NoResultFound` if the user does not exist.
        """
        user_query = server.db_session.query(User).filter_by(username=username)
        if user_query.count() == 0:
            raise NoResultFound(f"User {username} does not exist")
        try:
            user_query.delete()
            server.db_session.commit()
        except Exception:
            server.db_session.rollback()
            raise

    def is_admin(self):
        """Check whether the given user has an admin role.

        This can be extended to groups as well, for example, a user belonging
        to a certain group has only those privileges that are assigned to the
        group.

        Returns True if the user has an admin role, False otherwise.
        """
        return self.role is Roles.ADMIN

    @staticmethod
    def is_admin_username(username):
        """Return True if the given user name is the official "admin" user name,
        returns False otherwise.
        """
        # TODO: Need to add an interface to fetch admins list instead of
        # hard-coding the names, preferably via sql query.
        admins = ["admin"]
        return username in admins
