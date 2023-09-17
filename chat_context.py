from dataclasses import dataclass
from typing import Optional

from backends import AbstractBackend


@dataclass
class ChatContext:
    chat_id: Optional[int]
    username: str
    backend_instance: AbstractBackend
