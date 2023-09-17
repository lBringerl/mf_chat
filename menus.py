from menu import MenuBuilder


MODE_MENU = (MenuBuilder().set_title('<b>Выбор режима</b>\n\n'
                                     'Выбери режим, в котором хочешь '
                                     'работать с моделью')
                          .add_button('SQL', 'SQL')
                          .add_button('Free', 'FREE')
                          .add_button('Назад', 'BACK')
                          .build())

MODEL_MENU = (MenuBuilder().set_title('<b>Выбор модели</b>\n\n'
                                      'Выбери версию модели с которой хочешь '
                                      'работать')
                           .add_button('GPT-3.5', 'GPT3.5')
                           .add_button('GPT-4', 'GPT4')
                           .add_button('Назад', 'BACK')
                           .build())

MAIN_MENU = (MenuBuilder().set_title('<b>Главное меню</b>\n\n')
                          .add_button('Режим работы', 'MODE')
                          .add_button('Модель', 'MODEL')
                          .build())
