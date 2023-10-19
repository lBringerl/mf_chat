import datetime
import functools
import logging
from pathlib import Path
import pickle
import re
from typing import Callable, Dict

import aiofiles
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ExtBot
)

from backends import AbstractBackend, SQLBackend, FREEBackend
from chat_context import BackendSwitcher, ChatContext
from description import DescriptionParser
from encoder import SimpleEncoder
from menu import Menu
from menus import MAIN_MENU, MODE_MENU, MODEL_MENU


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH=4096
START_MESSAGE = """
Привет! Я чат-бот Мегафона.
Прежде, чем начать работу со мной, 
открой меню командой /menu и выбери режим работы.
Чтобы посмотреть список доступных команд, введи /help
"""
AVAILABLE_COMMANDS = """
Вот список доступных команд:

/start - вывести приветствие

/help - вывести это сообщение

/settings - показать значения текущих параметров

/history - выгрузить историю общения с моделями

/menu - открыть главное меню

/mode - показать текущий режим работы

/model_name <value> - установить название модели

/context - показать текущий контекст

/context_depth <value> - установить глубину контекста. От 1 до 30

/max_tokens <value> - установить значение параметра модели `max_tokens`

/temperature <value> - установить значение параметра модели `temperature`. От 0.0 до 2.0

/top_p <value> - установить значение параметра модели `top_p`. От 0.0 до 1.0

/frequency_penalty <value> - установить значение параметра модели `frequency_penalty`. От -2 до 2

/presence_penalty <value> - установить значение параметра модели `presence_penalty`. От -2 до 2

/role <value> - установить значение параметра модели `role`. 'system', 'user' или 'assistant'
"""

with open('tg_key.key', 'r') as f:
    BOT_TOKEN = f.read()

with open('allowed_users.txt', 'r') as f:
    ALLOWED_USERS = [user for user in f.read().split('\n')]

PROJECT_DIR = Path(__file__).parent


class BotHandlerException(Exception):
    pass


class BotHandler:

    def __init__(self,
                 bot: ExtBot,
                 main_menu: Menu,
                 mode_menu: Menu,
                 model_menu: Menu,
                 switcher_factory: Callable[[str], BackendSwitcher],
                 encoder: SimpleEncoder,
                 description_parser: DescriptionParser):
        self.main_menu = main_menu
        self.mode_menu = mode_menu
        self.model_menu = model_menu
        self._switcher_factory = switcher_factory
        self._contexts_dump_path = 'contexts.pickle'
        self._chat_contexts = self.load_contexts(self._contexts_dump_path)
        self._bot = bot
        self._history_file_name = 'history.log'
        self._encoder = encoder
        self._description_parser = description_parser
    
    async def _save_ask_to_history(self,
                                   context: ChatContext,
                                   ask: str,
                                   answer: str):
        async with aiofiles.open(self._history_file_name, 'a') as f:
            await f.write(f'{datetime.datetime.now()}:'
                          f'{context.username}:'
                          f'{context.switcher.model_name}:'
                          f'{context.switcher.mode}:\n'
                          'User input:\n'
                          f'{ask}\n'
                          'Model output:\n'
                          f'{answer}\n')

    def _create_new_chat_context(self, update: Update, context: CallbackContext):
        self._chat_contexts[context._chat_id] = ChatContext( # maybe use dependency injection
            chat_id=context._chat_id,
            username=update.message.from_user.username, # make unique (remove message)
            switcher=self._switcher_factory(update.message.from_user.username)
        )

    def get_chat_context(self,
                         update: Update,
                         context: CallbackContext) -> ChatContext:
        if context._chat_id not in self._chat_contexts:
            self._create_new_chat_context(update, context)
        return self._chat_contexts[context._chat_id]
    
    def dump_contexts(self, dump_path: str):
        with open(dump_path, 'wb') as f:
            pickle.dump(self._chat_contexts, f)
    
    @staticmethod
    def load_contexts(dump_path: str):
        if Path(dump_path).exists():
            with open(dump_path, 'rb') as f:
                try:
                    return pickle.load(f)
                except (EOFError, pickle.UnpicklingError):
                    return {}
        return {}

    def chat_context(func):
        @functools.wraps(func)
        async def wrapper(self: 'BotHandler',
                          update: Update,
                          context: CallbackContext,
                          *args,
                          **kwargs):
            chat_context = self.get_chat_context(update, context)
            res = await func(self,
                             chat_context,
                             update,
                             context,
                             *args,
                             **kwargs)
            self.dump_contexts(self._contexts_dump_path)
            return res
        return wrapper

    async def _show_main_menu(self, chat_id: int) -> None:
        await self._bot.send_message(chat_id,
                                     self.main_menu.title,
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=self.main_menu.markup)

    async def _show_mode_menu(self, chat_id: int) -> None:
        await self._bot.send_message(chat_id,
                                     self.mode_menu.title,
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=self.mode_menu.markup)

    async def _show_model_menu(self, chat_id: int) -> None:
        await self._bot.send_message(chat_id,
                                     self.model_menu.title,
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=self.model_menu.markup)

    @chat_context
    async def show_main_menu_callback(self,
                                      chat_context: ChatContext,
                                      update: Update,
                                      context: CallbackContext):
        await self._show_main_menu(chat_context.chat_id)

    @chat_context
    async def show_mode_callback(self,
                                 chat_context: ChatContext,
                                 update: Update,
                                 context: CallbackContext) -> None:
        await self._bot.send_message(
            chat_context.chat_id,
            f'В данный момент ты в режиме {chat_context.switcher.mode}'
        )

    @chat_context
    async def handle_menu_callback(self,
                                   chat_context: ChatContext,
                                   update: Update,
                                   context: CallbackContext) -> None:
        data = update.callback_query.data
        if data == 'MODE':
            await self._show_mode_menu(chat_context.chat_id)
        elif data == 'MODEL':
            await self._show_model_menu(chat_context.chat_id)
        elif data == 'SQL':
            chat_context.switcher.mode = data
            await self._bot.send_message(chat_context.chat_id,
                                         'Ты теперь используешь SQL режим. '
                                         'Скажи мне, какой SQL запрос '
                                         'сконструировать')
        elif data == 'FREE':
            chat_context.switcher.mode = data
            await self._bot.send_message(chat_context.chat_id,
                                         'Ты теперь используешь FREE режим. '
                                         'Спроси меня о чем угодно')
        elif data == 'GPT3.5':
                chat_context.switcher.model_name = 'gpt-3.5-turbo'
                await self._bot.send_message(
                    chat_context.chat_id,
                    'Ты теперь используешь версию '
                    f'{chat_context.switcher.model_name}'
                )
        elif data == 'GPT4':
            chat_context.switcher.model_name = 'gpt-4'
            await context.bot.send_message(
                chat_context.chat_id,
                'Ты теперь используешь версию '
                f'{chat_context.switcher.model_name}'
            )
        elif data == 'BACK':
            await self._show_main_menu(chat_context.chat_id)
        else:
            raise BotHandlerException(f'Unknown query data response: {data}')
        await update.callback_query.answer()

    def _find_table_mentions(self,
                             description_parser: DescriptionParser,
                             data: str) -> Dict[str, bool]:
        valid_mentions = {}
        matches = re.findall('\$([\w.]+)', data)
        tables = description_parser.tables
        for match in matches:
            valid_mentions[match] = match in tables
        return valid_mentions
    
    @chat_context
    async def handle_message_callback(self,
                                      chat_context: ChatContext,
                                      update: Update,
                                      context: CallbackContext) -> None:
        input_message = update.message.text
        if not input_message:
            return
        # TODO: Refactor. Too big function. Distinguish SQL and FREE modes
        mentions = self._find_table_mentions(self._description_parser,
                                             input_message)
        input_message = input_message.replace('$', '')
        if not all(mentions.values()):
            not_found_tables = [k for k, v in mentions.items() if not v]
            msg = f'Tables {not_found_tables} were not found.'
            await context.bot.send_message(chat_context.chat_id,
                                           msg,
                                           entities=update.message.entities)
            return

        encoded_additional_context = []
        for table in mentions:
            encoded_additional_context.append(
                self._encoder.encode(
                    self._description_parser.get_table_description(table)
                )
            )
        encoded_message = '\n'.join(
            encoded_additional_context
        ) + f'\n{self._encoder.encode(input_message)}'
        # await context.bot.send_message(chat_context.chat_id,
        #                                encoded_message,
        #                                entities=update.message.entities)
        answer = await chat_context.switcher.backend.handle(encoded_message)
        decoded_answer = self._encoder.decode(answer)
        await self._save_ask_to_history(context=chat_context,
                                        ask=self._encoder.decode(encoded_message),
                                        answer=decoded_answer)
        for i in range(len(decoded_answer) // MAX_MESSAGE_LENGTH):
            print(len(decoded_answer[i * MAX_MESSAGE_LENGTH:(i + 1) * MAX_MESSAGE_LENGTH + 1]))
            await context.bot.send_message(
                chat_context.chat_id,
                decoded_answer[i * MAX_MESSAGE_LENGTH:(i + 1) * MAX_MESSAGE_LENGTH + 1],
                entities=update.message.entities
            )
        left = len(decoded_answer) % MAX_MESSAGE_LENGTH
        if left:
            await context.bot.send_message(chat_context.chat_id,
                                           decoded_answer[-left:],
                                           entities=update.message.entities)
        # await context.bot.send_message(chat_context.chat_id,
        #                                answer,
        #                                entities=update.message.entities)
        # await context.bot.send_message(chat_context.chat_id,
        #                                decoded_answer,
        #                                entities=update.message.entities)

    @chat_context
    async def show_welcome_callback(self,
                                    chat_context: ChatContext,
                                    update: Update,
                                    context: CallbackContext) -> None:
        await self._bot.send_message(chat_context.chat_id, START_MESSAGE)

    @chat_context
    async def show_help_callback(self,
                                 chat_context: ChatContext,
                                 update: Update,
                                 context: CallbackContext) -> None:
        await self._bot.send_message(chat_context.chat_id, AVAILABLE_COMMANDS)
    
    @chat_context
    async def show_parameters_callback(self,
                                       chat_context: ChatContext,
                                       update: Update,
                                       context: CallbackContext) -> None:
        backend = chat_context.switcher.backend
        if isinstance(backend, SQLBackend): # TODO: remove if
            sql_prompt = backend.sql_prompt
        else:
            sql_prompt = None
        await self._bot.send_message(
            chat_context.chat_id,
            f'model_name: {backend.model_name}\n'
            f'/model_name <value>\n\n'
            f'context_depth: {backend.context_depth}\n'
            '/context_depth <value> (от 1 до 30)\n\n'
            f'sql_prompt: {sql_prompt}\n'
            '/sql_prompt <value> (строка с контекстом для sql режима)\n\n'
            f'max_tokens: {backend.max_tokens}\n'
            '/max_tokens <value> (от 0)\n\n'
            f'temperature: {backend.temperature}\n'
            '/temperature <value> (от 0.0 до 2.0)\n\n'
            f'top_p: {backend.top_p}\n'
            '/top_p <value> (от 0.0 до 1.0)\n\n'
            f'frequency_penalty: {backend.frequency_penalty}\n'
            '/frequency_penalty <value> (от -2.0 до 2.0)\n\n'
            f'presence_penalty: {backend.presence_penalty}\n'
            '/presence_penalty <value> (от -2.0 до 2.0)\n\n'
            f'role: {backend.role}\n'
            '/role <value> (`system`, `user` или `assistant`)'
        )
    
    @chat_context
    async def set_model_name_callback(self,
                                      chat_context: ChatContext,
                                      update: Update,
                                      context: CallbackContext) -> None:
        chat_context.switcher.backend.model_name = context.args[0]
    
    @chat_context
    async def show_context_callback(self,
                                    chat_context: ChatContext,
                                    update: Update,
                                    context: CallbackContext) -> None:
        msg = '\n'.join(
            f'{i}. {el}' for i, el in enumerate(
                chat_context.switcher.backend.context
            )
        )
        await self._bot.send_message(chat_context.chat_id, msg)
    
    @chat_context
    async def set_context_depth_callback(self,
                                         chat_context: ChatContext,
                                         update: Update,
                                         context: CallbackContext) -> None:
        chat_context.switcher.backend.context_depth = int(context.args[0])
    
    @chat_context
    async def set_sql_prompt_callback(self,
                                      chat_context: ChatContext,
                                      update: Update,
                                      context: CallbackContext) -> None:
        if not isinstance(chat_context.switcher.backend, SQLBackend):
            await self._bot.send_message(chat_context.chat_id,
                                         'Сначала нужно перейти в режим SQL')
            return
        chat_context.switcher.backend.sql_prompt = ' '.join(context.args)

    @chat_context
    async def set_context_depth_callback(self,
                                         chat_context: ChatContext,
                                         update: Update,
                                         context: CallbackContext) -> None:
        chat_context.switcher.backend.context_depth = int(context.args[0])
    
    @chat_context
    async def set_max_tokens_callback(self,
                                      chat_context: ChatContext,
                                      update: Update,
                                      context: CallbackContext) -> None:
        chat_context.switcher.backend.max_tokens = int(context.args[0])
    
    @chat_context
    async def set_temperature_callback(self,
                                       chat_context: ChatContext,
                                       update: Update,
                                       context: CallbackContext) -> None:
        chat_context.switcher.backend.temperature = float(context.args[0])
    
    @chat_context
    async def set_top_p_callback(self,
                                 chat_context: ChatContext,
                                 update: Update,
                                 context: CallbackContext) -> None:
        chat_context.switcher.backend.top_p = float(context.args[0])
    
    @chat_context
    async def set_frequency_penalty_callback(self,
                                             chat_context: ChatContext,
                                             update: Update,
                                             context: CallbackContext) -> None:
        chat_context.switcher.backend.frequency_penalty = float(context.args[0])

    @chat_context
    async def set_presence_penalty_callback(self,
                                            chat_context: ChatContext,
                                            update: Update,
                                            context: CallbackContext) -> None:
        chat_context.switcher.backend.presence_penalty = float(context.args[0])

    @chat_context
    async def set_role_callback(self,
                                chat_context: ChatContext,
                                update: Update,
                                context: CallbackContext) -> None:
        chat_context.switcher.backend.role = context.args[0]
    
    @chat_context
    async def get_history(self,
                          chat_context: ChatContext,
                          update: Update,
                          context: CallbackContext):
        with open(self._history_file_name, 'r') as f:
            await self._bot.send_document(chat_context.chat_id, f)


class IdleBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return START_MESSAGE


class NotAllowedBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return 'You are not allowed to use this bot'


def create_default_switcher(username):
    if username not in ALLOWED_USERS:
        return BackendSwitcher(modes={'NOT_ALLOWED': NotAllowedBackend()},
                               default_mode='NOT_ALLOWED',
                               default_model='')
    default_model = 'gpt-3.5-turbo'
    with open('context.txt', 'r') as f:
        sql_context = f.read()
    modes = {
        'SQL': SQLBackend(sql_context),
        'FREE': FREEBackend(),
        'IDLE': IdleBackend()
    }
    return BackendSwitcher(modes=modes,
                           default_mode='IDLE',
                           default_model=default_model)


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    description_parser = DescriptionParser(f'{PROJECT_DIR}/table_descriptions')
    encoder = SimpleEncoder(description_parser)
    bot_handler = BotHandler(bot=application.bot,
                             main_menu=MAIN_MENU,
                             mode_menu=MODE_MENU,
                             model_menu=MODEL_MENU,
                             switcher_factory=create_default_switcher,
                             encoder=encoder,
                             description_parser=description_parser)
    application.add_handler(
        CommandHandler('start', bot_handler.show_welcome_callback)
    )
    application.add_handler(
        CommandHandler('help', bot_handler.show_help_callback)
    )
    application.add_handler(
        CommandHandler('settings', bot_handler.show_parameters_callback)
    )
    application.add_handler(
        CommandHandler('menu', bot_handler.show_main_menu_callback)
    )
    application.add_handler(
        CommandHandler('mode', bot_handler.show_mode_callback)
    )
    application.add_handler(
        CommandHandler('model_name', bot_handler.set_model_name_callback)
    )
    application.add_handler(
        CommandHandler('context', bot_handler.show_context_callback)
    )
    application.add_handler(
        CommandHandler('context_depth', bot_handler.set_context_depth_callback)
    )
    application.add_handler(
        CommandHandler('sql_prompt', bot_handler.set_sql_prompt_callback)
    )
    application.add_handler(
        CommandHandler('max_tokens', bot_handler.set_max_tokens_callback)
    )
    application.add_handler(
        CommandHandler('temperature', bot_handler.set_temperature_callback)
    )
    application.add_handler(
        CommandHandler('top_p', bot_handler.set_top_p_callback)
    )
    application.add_handler(
        CommandHandler('frequency_penalty',
                       bot_handler.set_frequency_penalty_callback)
    )
    application.add_handler(
        CommandHandler('presence_penalty',
                       bot_handler.set_presence_penalty_callback)
    )
    application.add_handler(
        CommandHandler('role', bot_handler.set_role_callback)
    )
    application.add_handler(
        CommandHandler('history', bot_handler.get_history)
    )
    application.add_handler(
        CallbackQueryHandler(bot_handler.handle_menu_callback)
    )
    application.add_handler(MessageHandler(~filters.COMMAND,
                                           bot_handler.handle_message_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
