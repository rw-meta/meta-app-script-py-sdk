# coding=utf-8

from __future__ import print_function

import logging
import sys
import traceback

import logstash
from logstash import formatter as logstash_formatter

import metaappscriptsdk

# http://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library
# Отключаем логи от бибилиотеки requests
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

LOGGER_ENTITY = {}


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def create_logger(service_id=None, debug=True):
    if not service_id:
        service_id = 'unknown'
    # http://stackoverflow.com/questions/3220284/how-to-customize-the-time-format-for-python-logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    formatter = StdoutFormatter('%(asctime)s:%(levelname)s: %(message)s %(context)s', datefmt="%H:%M:%S")
    ch.setFormatter(formatter)

    root_logger.addHandler(ch)

    if not debug:
        h = logstash.TCPLogstashHandler(host='192.168.3.27', port=24224)
        h.setFormatter(LogstashFormatter(message_type="logstash", tags=None, fqdn=True, service_id=service_id, debug=debug))
        root_logger.addHandler(h)


class StdoutFormatter(logging.Formatter, object):
    def format(self, record):
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        dict__ = record.__dict__
        dict__.setdefault('context', {})
        context = dict__.get('context')
        context.update(LOGGER_ENTITY)
        ex = context.get("e")
        if ex:
            context.update({'e': {
                'class': str(ex.__class__),
                'message': str(ex),
                'trace': str(traceback.format_exc()),
            }})
            eprint(str(ex) + "\n" + str(traceback.format_exc()))
        s = self._fmt % dict__
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            try:
                s = s + record.exc_text
            except UnicodeError:
                # Sometimes filenames have non-ASCII chars, which can lead
                # to errors when s is Unicode and record.exc_text is str
                # See issue 8924.
                # We also use replace for when there are multiple
                # encodings, e.g. UTF-8 for the filesystem and latin-1
                # for a script. See issue 13232.
                s = s + record.exc_text.decode(sys.getfilesystemencoding(),
                                               'replace')
        return s


class LogstashFormatter(logstash_formatter.LogstashFormatterBase):
    def __init__(self, message_type='logstash', tags=None, fqdn=False, service_id='unknown', debug=False):
        super().__init__(message_type, tags, fqdn)
        self.service_id = service_id
        self.debug = debug

    def format(self, record):
        # Create message dict
        context = record.context if hasattr(record, 'context') else {}
        context.update(metaappscriptsdk.logger.LOGGER_ENTITY)
        context.setdefault('srv', self.service_id)

        if record.exc_info:
            context.update(self.format_exception(record))

        message = {
            "message": record.getMessage(),
            "context": context,
            "level": record.levelno,
            "level_name": record.levelname,
            "channel": "es.metaappscript",
            "extra": {}
        }

        return self.serialize(message)

    def formatException(self, record):
        """
        Format and return the specified exception information as a string.
        :type record logging.LogRecord
        :rtype: dict
        """
        if record.exc_info is None:
            return {}

        (exc_type, exc_message, trace) = record.exc_info

        return {
            'e': {
                'class': str(exc_type.__name__),  # ZeroDivisionError
                'message': str(exc_message),  # integer division or modulo by zero
                'trace': list(traceback.format_tb(trace)),
            }
        }
