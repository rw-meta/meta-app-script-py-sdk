import json
import os
import sys
import time
from os.path import expanduser

import requests

from metaappscriptsdk.exceptions import UnexpectedResponseError, DbQueryError, ServerError
from metaappscriptsdk.logger import create_logger, eprint
from metaappscriptsdk.logger.bulk_logger import BulkLogger
from metaappscriptsdk.logger.logger import Logger
from metaappscriptsdk.schedule.Schedule import Schedule
from metaappscriptsdk.services import get_api_call_headers, process_meta_api_error_code
from metaappscriptsdk.services.ApiProxyService import ApiProxyService
from metaappscriptsdk.services.DbQueryService import DbQueryService
from metaappscriptsdk.services.DbService import DbService
from metaappscriptsdk.services.ExportService import ExportService
from metaappscriptsdk.services.ExternalSystemService import ExternalSystemService
from metaappscriptsdk.services.FeedService import FeedService
from metaappscriptsdk.services.IssueService import IssueService
from metaappscriptsdk.services.MediaService import MediaService
from metaappscriptsdk.services.MetaqlService import MetaqlService
from metaappscriptsdk.services.SettingsService import SettingsService
from metaappscriptsdk.services.UserManagementService import UserManagementService
from metaappscriptsdk.services.StarterService import StarterService
from metaappscriptsdk.services.MailService import MailService
from metaappscriptsdk.worker import Worker


class MetaApp(object):
    debug = False
    service_id = None
    build_num = None
    starter_api_url = None
    meta_url = None
    api_proxy_url = None
    log = Logger()
    schedule = Schedule()
    worker = None

    # Будет поставляться в конец UserAgent
    user_agent_postfix = ""

    developer_settings = None

    # Пользователь, из под которого пройдет авторизация после того,
    # как мета авторизует разработчика, в случае, если разработчик имеет разрешения для авторизации из-под других пользователей
    auth_user_id = None

    MediaService = None
    MetaqlService = None
    ExportService = None
    SettingsService = None
    IssueService = None
    UserManagementService = None
    StarterService = None
    MailService = None
    ApiProxyService = None

    __default_headers = set()
    __db_list = {}

    def __init__(self, service_id: str = None, debug: bool = None,
                 starter_api_url: str = None,
                 meta_url: str = None,
                 api_proxy_url: str = None,
                 include_worker: bool = None
                 ):
        if debug is None:
            is_prod = os.environ.get('PRODUCTION', False)
            debug = os.environ.get('DEBUG', not is_prod)
            if include_worker is None:
                include_worker = True
            if debug == 'false':
                debug = False
        self.debug = debug

        self.meta_url = os.environ.get("META_URL", meta_url or "http://apimeta.1ad.ru")
        self.api_proxy_url = os.environ.get("API_PROXY_URL", api_proxy_url or "http://apiproxy.apis.kb.1ad.ru")

        if debug and not starter_api_url:
            starter_api_url = "http://STUB_URL"
        self.starter_api_url = os.environ.get("STARTER_URL", starter_api_url or "http://s2.meta.vmc.loc:28341")

        if service_id:
            self.log.warning("Параметр service_id скоро будет удален из MetaApp")

        gcloud_log_host_port = os.environ.get("GCLOUD_LOG_HOST_PORT", "n3.adp.vmc.loc:31891")
        service_ns = os.environ.get('SERVICE_NAMESPACE', "appscript")  # для ns в логах
        service_id = os.environ.get('SERVICE_ID', "local_debug_serivce")
        self.build_num = os.environ.get('BUILD_NUM', '0')
        self.service_id = service_id
        create_logger(service_id=service_id, service_ns=service_ns, gcloud_log_host_port=gcloud_log_host_port, debug=self.debug)

        self.__read_developer_settings()

        self.__default_headers = get_api_call_headers(self)
        self.MediaService = MediaService(self, self.__default_headers)
        self.MetaqlService = MetaqlService(self, self.__default_headers)
        self.SettingsService = SettingsService(self, self.__default_headers)
        self.ExportService = ExportService(self, self.__default_headers)
        self.IssueService = IssueService(self, self.__default_headers)
        self.StarterService = StarterService(self, self.__default_headers)
        self.MailService = MailService(self, self.__default_headers)
        self.DbService = DbService(self, self.__default_headers)
        self.UserManagementService = UserManagementService(self, self.__default_headers)
        self.ApiProxyService = ApiProxyService(self, self.__default_headers)
        self.ExternalSystemService = ExternalSystemService(self, self.__default_headers)
        self.FeedService = FeedService(self, self.__default_headers)

        if include_worker:
            stdin = "[]" if debug else ''.join(sys.stdin.readlines())
            self.worker = Worker(self, stdin)

    def bulk_log(self, log_message=u"Еще одна пачка обработана", total=None, part_log_time_minutes=5):
        """
        Возвращает инстант логгера для обработки списокв данных
        :param log_message: То, что будет написано, когда время придет
        :param total: Общее кол-во объектов, если вы знаете его
        :param part_log_time_minutes: Раз в какое кол-во минут пытаться писать лог
        :return: BulkLogger
        """
        return BulkLogger(log=self.log, log_message=log_message, total=total, part_log_time_minutes=part_log_time_minutes)

    def db(self, db_alias, shard_key=None):
        """
        Получить экземпляр работы с БД
        :type db_alias: basestring Альяс БД из меты
        :type shard_key: Любой тип. Некоторый идентификатор, который поможет мете найти нужную шарду. Тип зависи от принимающей стороны
        :rtype: DbQueryService
        """
        if shard_key is None:
            shard_key = ''

        db_key = db_alias + '__' + str(shard_key)
        if db_key not in self.__db_list:
            self.__db_list[db_key] = DbQueryService(self, self.__default_headers, {"db_alias": db_alias, "dbAlias": db_alias, "shard_find_key": shard_key, "shardKey": shard_key})
        return self.__db_list[db_key]

    @property
    def user_agent(self):
        return self.service_id + " | b" + self.build_num + (' | ' + self.user_agent_postfix if self.user_agent_postfix else "")

    def __read_developer_settings(self):
        """
        Читает конфигурации разработчика с локальной машины или из переменных окружения
        При этом переменная окружения приоритетнее
        :return:
        """
        dev_key_path = "/.rwmeta/developer_settings.json"
        is_windows = os.name == "nt"
        if is_windows:
            dev_key_path = dev_key_path.replace("/", "\\")
        dev_key_full_path = expanduser("~") + dev_key_path
        if self.debug:
            self.log.info(u"Читаем настройки разработчика из локального файла", {"path": dev_key_full_path})
        if os.path.isfile(dev_key_full_path):
            with open(dev_key_full_path, 'r') as myfile:
                self.developer_settings = json.loads(myfile.read())

        env_developer_settings = os.environ.get('META_SERVICE_ACCOUNT_SECRET', None)
        if not env_developer_settings:
            env_developer_settings = os.environ.get('X-META-Developer-Settings', None)
        if env_developer_settings:
            if self.debug:
                self.log.info(u"Читаем настройки разработчика из переменной окружения")
            self.developer_settings = json.loads(env_developer_settings)

        if not self.developer_settings:
            self.log.warning(u"НЕ УСТАНОВЛЕНЫ настройки разработчика, это может приводить к проблемам в дальнейшей работе!")

    def api_call(self, service, method, data, options):
        """
        :type app: metaappscriptsdk.MetaApp
        """
        if 'self' in data:
            # может не быть, если вызывается напрямую из кода,
            # а не из прослоек типа DbQueryService
            data.pop("self")

        if options:
            data.update(options)

        _headers = dict(self.__default_headers)

        if self.auth_user_id:
            _headers['X-META-AuthUserID'] = str(self.auth_user_id)

        request = {
            "url": self.meta_url + "/api/v1/adptools/" + service + "/" + method,
            "data": json.dumps(data),
            "headers": _headers,
            "timeout": (60, 1800)
        }

        for try_idx in range(20):
            try:
                # Пока непонятно почему частенько получаем ошибку:
                # Failed to establish a new connection: [Errno 110] Connection timed out',))
                # Пока пробуем делать доп. запросы
                # Так же жестко указываем timeout-ы
                resp = requests.post(**request)
                if resp.status_code == 200:
                    decoded_resp = json.loads(resp.text)
                    if 'data' in decoded_resp:
                        return decoded_resp['data'][method]
                    if 'error' in decoded_resp:
                        if 'details' in decoded_resp['error']:
                            eprint(decoded_resp['error']['details'])
                        raise DbQueryError(decoded_resp['error'])
                    raise UnexpectedResponseError()
                else:
                    process_meta_api_error_code(resp.status_code, request, resp.text)
            except (requests.exceptions.ConnectionError, ConnectionError, TimeoutError) as e:
                self.log.warning('META API Connection Error. Sleep...', {"e": e})
                time.sleep(15)

        raise ServerError(request)

    def native_api_call(self, service, method, data, options, multipart_form=False, multipart_form_data=None, stream=False, http_path="/api/meta/v1/", http_method='POST',
                        get_params={}, connect_timeout_sec=60):
        """
        :type app: metaappscriptsdk.MetaApp
        :rtype: requests.Response
        """
        if 'self' in data:
            # может не быть, если вызывается напрямую из кода,
            # а не из прослоек типа DbQueryService
            data.pop("self")

        if options:
            data.update(options)

        _headers = dict(self.__default_headers)

        if self.auth_user_id:
            _headers['X-META-AuthUserID'] = str(self.auth_user_id)

        request = {
            "url": self.meta_url + http_path + service + "/" + method,
            "timeout": (connect_timeout_sec, 1800),
            "stream": stream,
            "params": get_params,
        }

        if multipart_form:
            if multipart_form_data:
                request['files'] = multipart_form_data
            request['data'] = data
            _headers.pop('content-type', None)
        else:
            request['data'] = json.dumps(data)
        request['headers'] = _headers

        for try_idx in range(20):
            try:
                # Пока непонятно почему частенько получаем ошибку:
                # Failed to establish a new connection: [Errno 110] Connection timed out',))
                # Пока пробуем делать доп. запросы
                # Так же жестко указываем timeout-ы
                # resp = requests.post(**request)
                resp = requests.request(http_method, **request)
                if resp.status_code == 200:
                    return resp
                    # if 'data' in decoded_resp:
                    #     return decoded_resp['data'][method]
                    # if 'error' in decoded_resp:
                    #     if 'details' in decoded_resp['error']:
                    #         eprint(decoded_resp['error']['details'])
                    #     raise DbQueryError(decoded_resp['error'])
                    # raise UnexpectedResponseError()
                else:
                    process_meta_api_error_code(resp.status_code, request, resp.text)
            except (requests.exceptions.ConnectionError, ConnectionError, TimeoutError) as e:
                self.log.warning('META API Connection Error. Sleep...', {"e": e})
                time.sleep(15)

        raise ServerError(request)

    def get_lib_version(self):
        from metaappscriptsdk import info
        return info.__version__
