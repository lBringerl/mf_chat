from dataclasses import dataclass
import logging
from typing import Any, List, Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters
)

from backends import (
    AbstractBackend,
    ChatGPTBackend,
    SQLBackend,
    DummyBackend,
    DummyBackend2,
    FREEBackend,
    IdleBackend
)


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


@dataclass
class Menu:
    title: str
    markup: List[List[InlineKeyboardButton]]


class MenuBuilder:

    def __init__(self):
        self.title: Optional[str] = None
        self.markup: [List[List]] = []
    
    def add_button(self, text: str, callback_data: Any) -> 'MenuBuilder':
        self.markup.append(
            [InlineKeyboardButton(text, callback_data=callback_data)]
        )
        return self
    
    def set_title(self, title: str) -> 'MenuBuilder':
        self.title = title
        return self
    
    def clear(self) -> 'MenuBuilder':
        self.title = None
        self.markup = []
        return self
    
    def build(self) -> Menu:
        return Menu(title=self.title,
                    markup=InlineKeyboardMarkup(self.markup))


class BotHandlerException(Exception):
    pass


class BotHandler:

    def __init__(self,
                 main_menu: Menu,
                 mode_menu: Menu,
                 model_menu: Menu,
                 switcher: BackendSwitcher):
        self.main_menu = main_menu
        self.mode_menu = mode_menu
        self.model_menu = model_menu
        self._switcher = switcher

    async def show_mode(self, update: Update, context: CallbackContext) -> None:
        await context.bot.send_message(
            update.message.from_user.id,
            f'В данный момент ты в режиме {self._switcher.mode}'
        )

    async def show_main_menu(self,
                             update: Update,
                             context: CallbackContext) -> None:
        if update.message:
            await context.bot.send_message(
                update.message.from_user.id,
                self.main_menu.title,
                parse_mode=ParseMode.HTML,
                reply_markup=self.main_menu.markup
            )
        elif update.callback_query:
            await context.bot.send_message(
                update.callback_query.from_user.id,
                self.main_menu.title,
                parse_mode=ParseMode.HTML,
                reply_markup=self.main_menu.markup
            )

    async def show_mode_menu(self,
                             update: Update,
                             context: CallbackContext) -> None:
        await context.bot.send_message(
            update.callback_query.from_user.id,
            self.mode_menu.title,
            parse_mode=ParseMode.HTML,
            reply_markup=self.mode_menu.markup
        )

    async def show_model_menu(self,
                              update: Update,
                              context: CallbackContext) -> None:
        await context.bot.send_message(
            update.callback_query.from_user.id,
            self.model_menu.title,
            parse_mode=ParseMode.HTML,
            reply_markup=self.model_menu.markup
        )

    async def menu_handler(self,
                           update: Update,
                           context: CallbackContext) -> None:
        data = update.callback_query.data
        if data == 'MODE':
            await self.show_mode_menu(update, context)
        elif data == 'MODEL':
            await self.show_model_menu(update, context)
        elif data == 'SQL':
            self._switcher.mode = data
            await context.bot.send_message(
                update.callback_query.from_user.id,
                'Ты теперь используешь SQL режим. '
                'Скажи мне, какой SQL запрос сконструировать'
            )
        elif data == 'FREE':
            self._switcher.mode = data
            await context.bot.send_message(
                update.callback_query.from_user.id,
                'Ты теперь используешь FREE режим. '
                'Спроси меня о чем угодно'
            )
        elif data == 'GPT3.5':
            if self._switcher.mode == 'IDLE':
                await context.bot.send_message(
                    update.callback_query.from_user.id,
                    f'Сначала выбери режим работы'
                )
            else:
                self._switcher.model_name = 'gpt-3.5-turbo'
                await context.bot.send_message(
                    update.callback_query.from_user.id,
                    f'Ты теперь используешь версию {self._switcher.model_name}'
                )
        elif data == 'GPT4':
            if self._switcher.mode == 'IDLE':
                await context.bot.send_message(
                    update.callback_query.from_user.id,
                    f'Сначала выбери режим работы'
                )
            else:
                self._switcher.model_name = 'gpt-4'
                await context.bot.send_message(
                    update.callback_query.from_user.id,
                    f'Ты теперь используешь версию {self._switcher.model_name}'
                )
        elif data == 'BACK':
            await self.show_main_menu(update, context)
        else:
            raise BotHandlerException(f'Unknown query data response: {data}')
        await update.callback_query.answer()

    async def chat_handler(self,
                           update: Update,
                           context: CallbackContext) -> None:
        if not update.message.text:
            return
        answer = await self._switcher.backend.handle(update.message.text)
        await context.bot.send_message(update.message.chat_id,
                                       answer,
                                       entities=update.message.entities)


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
    
    mode_title = ('<b>Выбор режима</b>\n\n'
                  'Выбери режим, в котором хочешь работать с моделью')
    mode_menu = (MenuBuilder().set_title(mode_title)
                              .add_button('SQL', 'SQL')
                              .add_button('Free', 'FREE')
                              .add_button('Назад', 'BACK')
                              .build())
    model_title = ('<b>Выбор модели</b>\n\n'
                   'Выбери версию модели с которой хочешь работать')
    model_menu = (MenuBuilder().set_title(model_title)
                               .add_button('GPT-3.5', 'GPT3.5')
                               .add_button('GPT-4', 'GPT4')
                               .add_button('Назад', 'BACK')
                               .build())
    main_title = '<b>Главное меню</b>\n\n'
    main_menu = (MenuBuilder().set_title(main_title)
                              .add_button('Режим работы', 'MODE')
                              .add_button('Модель', 'MODEL')
                              .build())
    bot_handler = BotHandler(main_menu=main_menu,
                             mode_menu=mode_menu,
                             model_menu=model_menu,
                             switcher=switcher)
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('mode', bot_handler.show_mode))
    application.add_handler(CommandHandler('menu', bot_handler.show_main_menu))
    application.add_handler(CallbackQueryHandler(bot_handler.menu_handler))
    application.add_handler(MessageHandler(~filters.COMMAND,
                                           bot_handler.chat_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
