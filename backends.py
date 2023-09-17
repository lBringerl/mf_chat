from abc import ABC, abstractmethod
from collections import deque
from typing import Iterable, Tuple, Union

import openai


class AbstractBackend(ABC):
    
    @abstractmethod
    async def handle(self, message: str) -> str:
        raise NotImplemented


class ChatGPTBackendError(Exception):
    pass


class ChatGPTBackend(AbstractBackend):

    def __init__(self,
                 model_name: str,
                 context_depth: int = 20):
        with open('api_key.key') as f:
            self._api_key = f.read()
        openai.api_key = self._api_key
        self._model_name = model_name
        self._context_depth = context_depth
        self._context = deque([])

    @property
    def context(self) -> Iterable[str]:
        return self._context

    def save_context(self, message: str):
        self._context.append(message)
        if len(self._context) > self._context_depth:
            self._context.popleft()

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
        messages = [{'role': 'system', 'content': msg} for msg in self.context]
        messages.append({'role': 'system', 'content': message})
        response = openai.ChatCompletion.create(model=self._model_name,
                                                messages=messages)
        _, content = self._parse_response(response)
        return content

    def set_model_name(self, model_name):
        self._model_name = model_name


class FREEBackend(ChatGPTBackend):
    
    async def handle(self, message: str) -> str:
        self.save_context(message)
        return self.ask(message)


class SQLBackend(ChatGPTBackend):

    def __init__(self,
                 model_name: str,
                 sql_context: str,
                 context_depth: int = 20):
        super().__init__(model_name, context_depth)
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


