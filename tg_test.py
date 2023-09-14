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

    def __init__(self, modes: dict[str, AbstractBackend], default: str):
        self._modes = modes
        self._mode = default

    @property
    def backend(self) -> AbstractBackend:
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
                 menu: Menu,
                 switcher: BackendSwitcher):
        self.menu = menu
        self._switcher = switcher

    async def show_mode(self, update: Update, context: CallbackContext) -> None:
        await context.bot.send_message(
            update.message.from_user.id,
            f'В данный момент ты в режиме {self._switcher.mode}'
        )

    async def show_menu(self, update: Update, context: CallbackContext) -> None:
        await context.bot.send_message(
            update.message.from_user.id,
            self.menu.title,
            parse_mode=ParseMode.HTML,
            reply_markup=self.menu.markup
        )

    async def menu_handler(self,
                           update: Update,
                           context: CallbackContext) -> None:
        data = update.callback_query.data
        if data == 'SQL':
            await context.bot.send_message(
                update.callback_query.from_user.id,
                'Ты теперь используешь SQL режим. '
                'Скажи мне, какой SQL запрос сконструировать'
            )
        elif data == 'FREE':
            await context.bot.send_message(
                update.callback_query.from_user.id,
                'Ты теперь используешь FREE режим. '
                'Спроси меня о чем угодно'
            )
        else:
            raise BotHandlerException(f'Unknown query data response: {data}')
        self._switcher.mode = data
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
    modes = {
        'SQL': DummyBackend(),
        'FREE': FREEBackend(),
        'IDLE': IdleBackend()
    }
    switcher = BackendSwitcher(modes=modes, default='IDLE')
    title = '<b>Меню</b>\n\nВыбери режим, в котором хочешь работать с GPT.'
    menu = (MenuBuilder().set_title(title)
                         .add_button('SQL', 'SQL')
                         .add_button('Free', 'FREE')
                         .build())
    bot_handler = BotHandler(menu=menu, switcher=switcher)
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('mode', bot_handler.show_mode))
    application.add_handler(CommandHandler('menu', bot_handler.show_menu))
    application.add_handler(CallbackQueryHandler(bot_handler.menu_handler))
    application.add_handler(MessageHandler(~filters.COMMAND,
                                           bot_handler.chat_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
