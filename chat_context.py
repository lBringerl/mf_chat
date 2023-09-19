from dataclasses import dataclass
from typing import Optional

from backends import ChatGPTBackend


class SwitcherException(Exception):
    pass


class BackendSwitcher:

    def __init__(self,
                 modes: dict[str, ChatGPTBackend],
                 default_mode: str,
                 default_model: str):
        self._modes = modes
        self._mode = default_mode
        self._model_name = default_model

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, value: str):
        self._model_name = value
        for _, v in self._modes.items():
            if isinstance(v, ChatGPTBackend):
                v.model_name = value

    @property
    def backend(self) -> ChatGPTBackend:
        return self._modes[self.mode]

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, mode: str):
        if mode not in self._modes:
            raise SwitcherException(f'Unknown mode - {mode}. '
                                    f'Mode must be among {self._modes.keys()}')
        self._mode = mode


@dataclass
class ChatContext:
    chat_id: Optional[int]
    username: str
    switcher: BackendSwitcher
