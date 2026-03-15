from sqlalchemy.orm import Session

from benchloop_api.ownership.repository import UserOwnedRepository
from benchloop_api.runs.models import Run


class RunRepository(UserOwnedRepository[Run]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Run)
