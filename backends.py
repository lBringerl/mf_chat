from abc import ABC, abstractmethod
from collections import deque
from typing import Iterable, Tuple

import openai


class AbstractBackend(ABC):
    
    @abstractmethod
    async def handle(self, message: str) -> str:
        raise NotImplemented


class ChatGPTBackendError(Exception):
    pass


class ChatGPTBackend(AbstractBackend):

    def __init__(self,
                 model_name: str = 'gpt-3.5-turbo',
                 context_depth: int = 10):
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
    
    def _parse_response(self, response: dict) -> Tuple[str]:
        if not isinstance(response, dict):
            raise ChatGPTBackendError(
                'Error parsing response. Response must be of type "dict"'
            )
        choices = response.get('choices', None)
        if not isinstance(choices, list):
            raise ChatGPTBackendError(
                'Error parsing response. "choices" '
                'section must be of type "list"'
            )
        for choice in choices:
            if not isinstance(choice, dict):
                raise ChatGPTBackendError(
                    'Error parsing response. Elements of "choices" '
                    'section must be of type "dict"'
                )
            message = choice.get('message', None)
            if not isinstance(message, dict):
                raise ChatGPTBackendError(
                    'Error parsing response. "message" section in choices '
                    'must be of type dict'
                )
            role = message.get('role', None)
            if role is None:
                raise ChatGPTBackendError(
                    'Error parsing response. '
                    'No "role" field in "message" section'
                )
            content = message.get('content', None)
            if content is None:
                raise ChatGPTBackendError(
                    'Error parsing response. '
                    'No "content" field in "message" section'
                )
            return (role, content)

    def ask(self, message: str) -> str:
        messages = [{'role': 'system', 'content': msg} for msg in self.context]
        messages.append(message)
        response = openai.ChatCompletion.create(model=self._model_name,
                                                messages=messages)
        _, content = self._parse_response(response)
        return content


class FREEBackend(ChatGPTBackend):
    
    async def handle(self, message: str) -> str:
        self.save_context(message)
        return self.ask(message)


class SQLBackend(ChatGPTBackend):

    @property
    def context(self) -> Iterable[str]:
        return super().context
    
    async def handle(self, message: str) -> str:
        return self.ask(message)



class DummyBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return (f'Hello! You said "{message}". '
                'But I\'m Dummy, I don\'t understand')


class DummyBackend2(AbstractBackend):

    async def handle(self, message: str) -> str:
        return (f'Hello! I\'m Dummy №2...')


class IdleBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return (f'Привет! Я Мегафон GPT бот. '
                'Чтобы начать со мной общение, '
                'открой меню командой /menu и выбери режим')

