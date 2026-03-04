import uuid
from .models import SessionStatus


class Session:
    def __init__(self):
        self.id = uuid.uuid4()
        self.status = SessionStatus.CREATED
        # ...