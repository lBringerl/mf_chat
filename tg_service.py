import functools
import logging

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

from backends import (
    AbstractBackend,
    ChatGPTBackend,
    SQLBackend,
    FREEBackend
)
from chat_context import ChatContext
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


class SwitcherException(Exception):
    pass


class BackendSwitcher:

    def __init__(self,
                 modes: dict[str, ChatGPTBackend],
                 default_mode: str,
                 models: set[str],
                 default_model: str):
        self._modes = modes
        self._mode = default_mode
        self._models = models
        self._model_name = default_model
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    @model_name.setter
    def model_name(self, model_name: str):
        if model_name not in self._models:
            raise SwitcherException(
                f'Unknown model_name - {model_name}. '
                f'Model name must be among {self._models}'
            )
        self._model_name = model_name
        for _, v in self._modes.items():
            if isinstance(v, ChatGPTBackend):
                v.set_model_name(model_name)

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



class BotHandlerException(Exception):
    pass


class BotHandler:

    def __init__(self,
                 bot: ExtBot,
                 main_menu: Menu,
                 mode_menu: Menu,
                 model_menu: Menu,
                 switcher: BackendSwitcher,
                 default_backend: AbstractBackend): # maybe use Type[AbstractBackend]
        self.main_menu = main_menu
        self.mode_menu = mode_menu
        self.model_menu = model_menu
        self._switcher = switcher
        self._default_backend = default_backend
        self._chat_contexts = {}
        self._bot = bot

    def _create_new_chat_context(self, update: Update, context: CallbackContext):
        self._chat_contexts[context._chat_id] = ChatContext( # maybe use dependency injection
            chat_id=context._chat_id,
            username=update.message.from_user.username, # make unique (remove message)
            backend_instance=self._default_backend
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
            f'В данный момент ты в режиме {self._switcher.mode}'
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
            self._switcher.mode = data
            await self._bot.send_message(chat_context.chat_id,
                                         'Ты теперь используешь SQL режим. '
                                         'Скажи мне, какой SQL запрос '
                                         'сконструировать')
        elif data == 'FREE':
            self._switcher.mode = data
            await self._send_message(chat_context.chat_id,
                                     'Ты теперь используешь FREE режим. '
                                     'Спроси меня о чем угодно')
        elif data == 'GPT3.5':
            if self._switcher.mode == 'IDLE':
                await self._bot.send_message(chat_context.chat_id,
                                             'Сначала выбери режим работы')
            else:
                self._switcher.model_name = 'gpt-3.5-turbo'
                await self._bot.send_message(chat_context.chat_id,
                                             'Ты теперь используешь версию '
                                             f'{self._switcher.model_name}')
        elif data == 'GPT4':
            if self._switcher.mode == 'IDLE':
                await context.bot.send_message(chat_context.chat_id,
                                               f'Сначала выбери режим работы')
            else:
                self._switcher.model_name = 'gpt-4'
                await context.bot.send_message(chat_context.chat_id,
                                               'Ты теперь используешь версию '
                                               f'{self._switcher.model_name}')
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
        answer = await self._switcher.backend.handle(update.message.text)
        await self._bot.send_message(chat_context.chat_id,
                                     answer,
                                     entities=update.message.entities)



class IdleBackend(AbstractBackend):

    async def handle(self, message: str) -> str:
        return ('Привет! Я Мегафон GPT бот. Открой меню командой /menu, '
                'и выбери режим, чтобы общаться со мной.')


def main():
    available_models = set(['gpt-3.5-turbo', 'gpt-4'])
    default_model = 'gpt-3.5-turbo'
    with open('context.txt', 'r') as f:
        sql_context = f.read()
    modes = {
        'SQL': SQLBackend(default_model, sql_context),
        'FREE': FREEBackend(default_model),
        'IDLE': IdleBackend()
    }
    switcher = BackendSwitcher(modes=modes,
                               default_mode='IDLE',
                               models=available_models,
                               default_model=default_model)
    
    application = Application.builder().token(BOT_TOKEN).build()
    bot_handler = BotHandler(bot=application.bot,
                             main_menu=MAIN_MENU,
                             mode_menu=MODE_MENU,
                             model_menu=MODEL_MENU,
                             switcher=switcher,
                             default_backend=IdleBackend())
    
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
