import logging

from metaappscriptsdk.logger import LOGGER_ENTITY

def preprocessing(func):
    def wrapper(self, msg, context=None):
        """ Этот декоратор занимается предобработкой входных параметров:
            1. Проверяет context на None.
            2. Добавляет к msg имя класса объекта ошибки. Например: msg + ModuleNotFoundError
         """
        if context is None:
            context = {}

        error_obj = context.get('e')
        if isinstance(error_obj, Exception):
            try:
                msg = msg + ' ' + str(error_obj.__class__.__name__)
            except:
                pass


        return func(self, msg, context)
    return wrapper

class Logger:
    """
    Прослойка для упрощения апи логгера
    """

    def set_entity(self, key, value):
        if value is None:
            self.remove_entity(key)
        else:
            LOGGER_ENTITY[key] = value

    def remove_entity(self, key):
        LOGGER_ENTITY.pop(key, None)

    def info(self, msg, context=None):
        if context is None:
            context = {}
        logging.info(msg, extra={'context': context})

    @preprocessing
    def warning(self, msg, context):
        logging.warning(msg, extra={'context': context})

    @preprocessing
    def error(self, msg, context):
        logging.error(msg, extra={'context': context})

    @preprocessing
    def critical(self, msg, context):
        logging.critical(msg, extra={'context': context})

    @preprocessing
    def exception(self, msg, context):
        logging.exception(msg, extra={'context': context})
