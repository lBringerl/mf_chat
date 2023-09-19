import functools
import logging
from typing import Callable

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
from menu import Menu
from menus import MAIN_MENU, MODE_MENU, MODEL_MENU


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

with open('tg_key.key', 'r') as f:
    BOT_TOKEN = f.read()


class BotHandlerException(Exception):
    pass


class BotHandler:
    AVAILABLE_COMMANDS = """
    /menu - открыть главное меню

    /parameters - показать значения текущих параметров
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

    def __init__(self,
                 bot: ExtBot,
                 main_menu: Menu,
                 mode_menu: Menu,
                 model_menu: Menu,
                 switcher_factory: Callable[[], BackendSwitcher]): # maybe use Type[AbstractBackend]
        self.main_menu = main_menu
        self.mode_menu = mode_menu
        self.model_menu = model_menu
        self._switcher_factory = switcher_factory
        self._chat_contexts = {}
        self._bot = bot

    def _create_new_chat_context(self, update: Update, context: CallbackContext):
        self._chat_contexts[context._chat_id] = ChatContext( # maybe use dependency injection
            chat_id=context._chat_id,
            username=update.message.from_user.username, # make unique (remove message)
            switcher=self._switcher_factory()
        )

    def get_chat_context(self,
                         update: Update,
                         context: CallbackContext) -> ChatContext:
        if context._chat_id not in self._chat_contexts:
            self._create_new_chat_context(update, context)
        return self._chat_contexts[context._chat_id]

    def chat_context(func):
        @functools.wraps(func)
        async def wrapper(instance: 'BotHandler',
                          update: Update,
                          context: CallbackContext,
                          *args,
                          **kwargs):
            chat_context = instance.get_chat_context(update, context)
            return await func(instance,
                              chat_context,
                              update,
                              context,
                              *args,
                              **kwargs)
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
            if chat_context.switcher.mode == 'IDLE':
                await self._bot.send_message(chat_context.chat_id,
                                             'Сначала выбери режим работы')
            else:
                chat_context.switcher.model_name = 'gpt-3.5-turbo'
                await self._bot.send_message(
                    chat_context.chat_id,
                    'Ты теперь используешь версию '
                    f'{chat_context.switcher.model_name}'
                )
        elif data == 'GPT4':
            if chat_context.switcher.mode == 'IDLE':
                await context.bot.send_message(chat_context.chat_id,
                                               f'Сначала выбери режим работы')
            else:
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

    @chat_context
    async def handle_message_callback(self,
                                      chat_context: ChatContext,
                                      update: Update,
                                      context: CallbackContext) -> None:
        if not update.message.text:
            return
        answer = await chat_context.switcher.backend.handle(update.message.text)
        await context.bot.send_message(chat_context.chat_id,
                                     answer,
                                     entities=update.message.entities)
    
    @chat_context
    async def show_commands_callback(self,
                                     chat_context: ChatContext,
                                     update: Update,
                                     context: CallbackContext) -> None:
        await self._bot.send_message(
            chat_context.chat_id,
            f'Список доступных команд: {chat_context.switcher.mode}'
        )


class IdleBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return ('Привет! Я Мегафон GPT бот. Открой меню командой /menu, '
                'и выбери режим, чтобы общаться со мной.')


def create_default_switcher():
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
    bot_handler = BotHandler(bot=application.bot,
                             main_menu=MAIN_MENU,
                             mode_menu=MODE_MENU,
                             model_menu=MODEL_MENU,
                             switcher_factory=create_default_switcher)
    
    application.add_handler(CommandHandler('mode',
                                           bot_handler.show_mode_callback))
    application.add_handler(CommandHandler('menu',
                                           bot_handler.show_main_menu_callback))
    application.add_handler(
        CallbackQueryHandler(bot_handler.handle_menu_callback)
    )
    application.add_handler(MessageHandler(~filters.COMMAND,
                                           bot_handler.handle_message_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
