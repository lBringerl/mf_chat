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


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

with open('tg_key.key', 'r') as f:
    BOT_TOKEN = f.read()


# async def echo(update: Update, context: CallbackContext) -> None:
#     print(f'{update.message.from_user.first_name} wrote {update.message.text}')

#     if screaming and update.message.text:
#         await context.bot.send_message(
#             update.message.chat_id,
#             f'{update.message.text.upper()}!!!',
#             entities=update.message.entities
#         )
#     else:
#         await update.message.copy(update.message.chat_id)


MODES = ('SQL', 'FREE')


class SwitcherException(Exception):
    pass


class Switcher:

    def __init__(self, mode: str = 'SQL'):
        self._mode: str = mode

    @property
    def mode(self):
        return self._mode
    
    @mode.setter
    def mode(self, mode: str):
        if mode not in MODES:
            raise SwitcherException(f'Unknown mode - {mode}. '
                                    f'Mode must be among {MODES}')
        self._mode = mode

    def set_sql_mode(self) -> None:
        logger.info('Setting sql mode')
        self.mode = 'SQL'
    
    def set_free_mode(self) -> None:
        logger.info('Setting free mode')
        self.mode = 'FREE'
    
    async def get_mode(self, update: Update, context: CallbackContext) -> None:
        logger.info(f'Current mode is {self.mode}')


class Menu:

    def __init__(self,
                 title: str,
                 markup: List[InlineKeyboardMarkup],
                 switcher: Switcher):
        self.title = title
        self.markup = markup
        self.switcher = switcher

    async def menu(self, update: Update, context: CallbackContext) -> None:
        await context.bot.send_message(
            update.message.from_user.id,
            self.title,
            parse_mode=ParseMode.HTML,
            reply_markup=self.markup
        )

    async def handler(self, update: Update, context: CallbackContext) -> None:
        data = update.callback_query.data
        if data == 'SQL':
            self.switcher.set_sql_mode()
        elif data == 'FREE':
            self.switcher.set_free_mode()
        await update.callback_query.answer()


class MenuBuilder:

    def __init__(self):
        self.title: Optional[str] = None
        self.markup: Optional[List[List]] = []
        self.switcher: Optional[Switcher] = None
    
    def add_button(self, text: str, callback_data: Any) -> 'MenuBuilder':
        self.markup.append(
            [InlineKeyboardButton(text, callback_data=callback_data)]
        )
        return self
    
    def set_title(self, title: str) -> 'MenuBuilder':
        self.title = title
        return self
    
    def set_switcher(self, switcher: Switcher) -> 'MenuBuilder':
        self.switcher = switcher
        return self
    
    def clear(self) -> 'MenuBuilder':
        self.title = None
        self.markup = []
        return self
    
    def build(self) -> Menu:
        return Menu(self.title,
                    InlineKeyboardMarkup(self.markup),
                    self.switcher)


def main():
    title = '<b>Menu 1</b>\n\nSelect a mode you want to work with GPT.'
    switcher = Switcher()
    menu = (MenuBuilder().set_title(title)
                         .add_button('SQL', 'SQL')
                         .add_button('Free', 'FREE')
                         .set_switcher(switcher)
                         .build())
    
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('mode', switcher.get_mode))
    application.add_handler(CommandHandler('menu', menu.menu))
    application.add_handler(CallbackQueryHandler(menu.handler))

    # application.add_handler(MessageHandler(~filters.COMMAND, echo))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
