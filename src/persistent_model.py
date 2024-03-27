from abc import ABC, abstractmethod
import logging

from models import UserKey
import database


class AbstractPersistentModel(ABC):
    def __init__(self):
        self._state = None

    def __repr__(self):
        return f"{type(self).__name__}(state={self.state})"

    @property
    def state(self):
        if self._state is None:
            self._state = self._read_state()
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self._write_state(value)

    @abstractmethod
    def _read_state(self):
        ...

    @abstractmethod
    def _write_state(self, value):
        ...


class MongodbPersistentModel(AbstractPersistentModel):
    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = user_id

    def _read_state(self):
        try:
            application = database.find_user(self.user_id).application
            return None if application is None else application.status
        except Exception as e:
            logging.error(e, exc_info=True)
            return None

    def _write_state(self, value):
        database.update_user_application_state(
            user_id=self.user_id, application_state=value
        )
