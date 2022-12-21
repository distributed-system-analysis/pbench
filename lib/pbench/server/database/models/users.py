import datetime
import enum
from typing import Optional

from email_validator import validate_email
from flask_bcrypt import generate_password_hash
from sqlalchemy import Column, DateTime, Enum, Integer, LargeBinary, String
from sqlalchemy.orm import relationship, validates
from sqlalchemy.orm.exc import NoResultFound

from pbench.server.database.database import Database
from pbench.server.database.models.auth_tokens import AuthToken
from pbench.server.globals import server


class Roles(enum.Enum):
    ADMIN = 1


class User(Database.Base):
    """User Model for storing user related details."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(255), unique=False, nullable=False)
    last_name = Column(String(255), unique=False, nullable=False)
    password = Column(LargeBinary(128), nullable=False)
    registered_on = Column(DateTime, nullable=False, default=datetime.datetime.now())
    email = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(Roles), unique=False, nullable=True)
    auth_tokens = relationship("AuthToken", back_populates="user")

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
    def get_protected() -> list[str]:
        """Return protected column names that are not allowed for external updates.

        `auth_tokens` is already protected from external updates via PUT api since
        it is of type sqlalchemy relationship ORM package and not a sqlalchemy column.
        """
        return ["registered_on", "id"]

    @staticmethod
    def query(id=None, username=None, email=None) -> Optional["User"]:
        """Find a user using one of the provided arguments.

        The first argument which is not None is used in the query.  The order
        in which the arguments are considered follows the method signature.

        Returns:
            A User object if a user is found, None otherwise.
        """
        if id:
            user = server.db_session.query(User).filter_by(id=id).first()
        elif username:
            user = server.db_session.query(User).filter_by(username=username).first()
        elif email:
            user = server.db_session.query(User).filter_by(email=email).first()
        else:
            user = None
        return user

    @staticmethod
    def query_all() -> list["User"]:
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
    def evaluate_role(self, key: str, value: str) -> Optional[str]:
        try:
            return Roles[value.upper()]
        except KeyError:
            return None

    @validates("password")
    def evaluate_password(self, key: str, value: str) -> str:
        return generate_password_hash(value)

    # validate the email field
    @validates("email")
    def evaluate_email(self, key: str, value: str) -> str:
        valid = validate_email(value)
        return valid.email

    def add_token(self, auth_token: AuthToken):
        """Add the given token to the database

        Args:
            token : An AuthToken object add for this user
        """
        try:
            self.auth_tokens.append(auth_token)
            server.db_session.add(auth_token)
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
    def delete(username: str):
        """Delete the user with a given username, except admin.

        Args:
            username : the username to delete
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

    def is_admin(self) -> bool:
        """This method checks whether the given user has an admin role.

        This can be extended to groups as well for example a user belonging to
        certain group has only those privileges that are assigned to the
        group.

        Returns:
            True if the user's role is ADMIN, False otherwise.
        """
        return self.role is Roles.ADMIN

    @staticmethod
    def is_admin_username(username: str) -> bool:
        """Determine if the given user name is an admin user.

        Returns:
            True if the user is an admin; False otherwise.
        """
        admins = ["admin"]
        return username in admins
