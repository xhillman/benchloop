from sqlalchemy import select
from sqlalchemy.orm import Session

from benchloop_api.users.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_clerk_user_id(self, clerk_user_id: str) -> User | None:
        statement = select(User).where(User.clerk_user_id == clerk_user_id)
        return self._session.scalar(statement)

    def add(self, user: User) -> User:
        self._session.add(user)
        return user
