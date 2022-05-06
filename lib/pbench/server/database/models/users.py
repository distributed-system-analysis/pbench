import datetime
import enum

from email_validator import validate_email
from flask_bcrypt import generate_password_hash
from sqlalchemy import Column, DateTime, Enum, Integer, LargeBinary, String
from sqlalchemy.orm import relationship, validates
from sqlalchemy.orm.exc import NoResultFound

from pbench.server.database.database import Database


class Roles(enum.Enum):
    ADMIN = 1


class User(Database.Base):
    """User Model for storing user related details"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(255), unique=False, nullable=False)
    last_name = Column(String(255), unique=False, nullable=False)
    password = Column(LargeBinary(128), nullable=False)
    registered_on = Column(DateTime, nullable=False, default=datetime.datetime.now())
    email = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(Roles), unique=False, nullable=True)
    auth_tokens = relationship("ActiveTokens", backref="users")

    # NOTE: this relationship defines a `user` property in `Metadata`
    # that refers to the parent `User` object.
    dataset_metadata = relationship(
        "Metadata", back_populates="user", cascade="all, delete-orphan"
    )

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
        """
        Return protected column names that are not allowed for external updates.
        auth_tokens is already protected from external updates via PUT api since
        it is of type sqlalchemy relationship ORM package and not a sqlalchemy column.
        """
        return ["registered_on", "id"]

    @staticmethod
    def query(id=None, username=None, email=None) -> "User":
        # Currently we would only query with single argument. Argument need to be either username/id/email
        if username:
            user = Database.db_session.query(User).filter_by(username=username).first()
        elif id:
            user = Database.db_session.query(User).filter_by(id=id).first()
        elif email:
            user = Database.db_session.query(User).filter_by(email=email).first()
        else:
            user = None

        return user

    @staticmethod
    def query_all() -> "list[User]":
        return Database.db_session.query(User).all()

    def add(self):
        """
        Add the current user object to the database
        """
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
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

    # validate the email field
    @validates("email")
    def evaluate_email(self, key, value):
        valid = validate_email(value)
        email = valid.email

        return email

    def update(self, **kwargs):
        """
        Update the current user object with given keyword arguments
        """
        try:
            for key, value in kwargs.items():
                if key == "auth_tokens":
                    # Insert the auth token
                    self.auth_tokens.append(value)
                    Database.db_session.add(value)
                else:
                    setattr(self, key, value)
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise

    @staticmethod
    def delete(username):
        """
        Delete the user with a given username except admin
        :param username:
        """
        user_query = Database.db_session.query(User).filter_by(username=username)
        if user_query.count() == 0:
            raise NoResultFound(f"User {username} does not exist")
        try:
            user_query.delete()
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise

    def is_admin(self):
        """This method checks whether the given user has an admin role.
        This can be extended to groups as well for example a user belonging to certain group has only those
        privileges that are assigned to the group.
        """
        return self.role is Roles.ADMIN

    @staticmethod
    def is_admin_username(username):
        # TODO: Need to add an interface to fetch admins list instead of hard-coding the names, preferably via sql query
        admins = ["admin"]
        return username in admins

    # TODO: Add password recovery mechanism
