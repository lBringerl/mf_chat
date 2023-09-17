from dataclasses import dataclass
from typing import Any, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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
