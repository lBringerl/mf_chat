from abc import ABC, abstractmethod
from collections import deque
from typing import Iterable, Optional, Tuple, TypeVar, Union

import openai
from openai.error import InvalidRequestError


with open('api_key.key') as f:
    api_key = f.read()
    openai.api_key = api_key

BackendImpl = TypeVar('BackendImpl', bound='AbstractBackend')


class AbstractBackend(ABC):
    
    @abstractmethod
    async def handle(self, message: str) -> str:
        raise NotImplemented


class ChatGPTBackendError(Exception):
    pass


class ChatGPTBackend(AbstractBackend):

    def __init__(self):
        self._context = deque([])
        self._model_name: str = 'gpt-3.5-turbo'
        self._context_depth: int = 1
        self._max_tokens: Optional[int] = None
        self._temperature: Optional[float] = 1.0
        self._top_p: Optional[float] = 1.0
        self._frequency_penalty: Optional[float] = 0.0
        self._presence_penalty: Optional[float] = 0.0
        self._role: str = 'user'

    @property
    def context(self) -> Iterable[str]:
        return self._context

    def save_context(self, message: str):
        while len(self._context) > self._context_depth:
            self._context.popleft()
        self._context.append(message)

    def _parse_response(self, response: dict) -> Tuple[Union[str, None]]:
        choices = response.get('choices', None)
        if choices:
            choice = choices[-1]
            message = choice.get('message', None)
            role = message.get('role', None)
            content = message.get('content', None)
            return (role, content)
        return (None, None)

    def ask(self, message: str) -> str:
        messages = [{'role': self.role, 'content': msg} for msg in self.context]
        messages.append({'role': self.role, 'content': message})
        try:
            response = openai.ChatCompletion.create(
                model=self._model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty
            )
            _, content = self._parse_response(response)
        except InvalidRequestError as exc:
            return str(exc)
        return content

    @property
    def model_name(self) -> str:
        return self._model_name
    
    @model_name.setter
    def model_name(self, value: str):
        self._model_name = value
    
    @property
    def context_depth(self) -> int:
        return self._context_depth
    
    @context_depth.setter
    def context_depth(self, value: int):
        if value < 1 or value > 30:
            raise ChatGPTBackendError(
                '`context_depth` parameter must be in range from 1 to 30'
            )
        self._context_depth = value
    
    @property
    def max_tokens(self) -> Optional[int]:
        return self._max_tokens

    @max_tokens.setter
    def max_tokens(self, value: Optional[int]):
        self._max_tokens = value

    @property
    def temperature(self) -> Optional[float]:
        return self._temperature
    
    @temperature.setter
    def temperature(self, value: Optional[float]):
        if isinstance(value, float):
            if value < 0 or value > 2:
                raise ChatGPTBackendError(
                    '`temperature` parameter must be in range from 0 to 2'
                )
        self._temperature = value
    
    @property
    def top_p(self) -> Optional[float]:
        return self._top_p
    
    @top_p.setter
    def top_p(self, value: Optional[float]):
        if isinstance(value, float):
            if value < 0 or value > 1:
                raise ChatGPTBackendError(
                    '`top_p` parameter must be in range from 0 to 1'
                )
        self._top_p = value
    
    @property
    def frequency_penalty(self) -> Optional[float]:
        return self._frequency_penalty
    
    @frequency_penalty.setter
    def frequency_penalty(self, value: Optional[float]):
        if isinstance(value, float):
            if value < -2.0 or value > 2.0:
                raise ChatGPTBackendError(
                    '`frequency_penalty` parameter must be in range from -2 to 2'
                )
        self._frequency_penalty = value
    
    @property
    def presence_penalty(self) -> Optional[float]:
        return self._presence_penalty
    
    @presence_penalty.setter
    def presence_penalty(self, value: Optional[float]):
        if isinstance(value, float):
            if value < -2.0 or value > 2.0:
                raise ChatGPTBackendError(
                    '`presence_penalty` parameter must be in range from -2 to 2'
                )
        self._presence_penalty = value
    
    @property
    def role(self) -> str:
        return self._role
    
    @role.setter
    def role(self, value: str):
        if value not in {'system', 'user', 'assistant'}:
            raise ChatGPTBackendError(
                '`role` parameter must be either "system", "user" or "assistant"'
            )
        self._role = value


class FREEBackend(ChatGPTBackend):
    
    async def handle(self, message: str) -> str:
        self.save_context(message)
        return self.ask(message)


class SQLBackend(ChatGPTBackend):

    def __init__(self, sql_context: str):
        super().__init__()
        self._sql_context = sql_context

    @property
    def context(self) -> Iterable[str]:
        return deque([self._sql_context, *super().context])

    async def handle(self, message: str) -> str:
        return self.ask(message)


class DummyBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return (f'Hello! You said "{message}". '
                'But I\'m Dummy, I don\'t understand')


class DummyBackend2(AbstractBackend):

    async def handle(self, message: str) -> str:
        return (f'Hello! I\'m Dummy №2...')


