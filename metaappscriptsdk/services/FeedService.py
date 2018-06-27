# coding=utf-8
import json



class FeedService:
    def __init__(self, app, default_headers):
        """
        :type app: metaappscriptsdk.MetaApp
        """
        self.__app = app
        self.__default_headers = default_headers
        self.__options = {}
        self.__data_get_cache = {}
        self.__data_get_flatten_cache = {}
        self.__metadb = app.db("meta")

    def get_feed(self, datasource_id):
        """
        Получение настроек для фида
        :param datasource_id: идентификатор фида
        :return: FeedDataSource
        """
        info = self.__metadb.one(
            """
            SELECT to_json(ds) as datasource
                 , to_json(fc) as connector
                 , to_json(fct) as connector_type
                 , to_json(ctp) as connector_type_preset,
                 , json_build_object('email', u.email, 'full_name', u.full_name) as author_user
              FROM meta.feed_datasource ds
              LEFT JOIN meta.feed_connector fc 
                     ON fc.id=ds.connector_id
              LEFT JOIN meta.feed_connector_type fct 
                     ON fct.id=fc.connector_type_id
              LEFT JOIN meta.feed_connector_type_preset ctp 
                     ON ctp.id=ds.connector_type_preset_id
              LEFT JOIN meta.user_list u 
                     ON u.id=ds.author_user_id
             WHERE ds.id = :datasource_id::uuid
            """,
            {"datasource_id": datasource_id}
        )
        return FeedDataSource(**info)

    def datasource_process(self, datasource_id):
        """
        deprecated
        Запускает настроенные обработки в фиде
        :param datasource_id: uuid
        """
        # TODO Выпилить потом класс используется для другого
        # TODO без applicationId не выбираются поля сущностей. Подумать на сколько это НЕ нормально
        response = self.__app.native_api_call('feed', 'datasource/' + datasource_id + '/process?applicationId=1', {},
                                              self.__options, False, None, False, http_method="POST")
        return json.loads(response.text)


class FeedDataSource:
    """
    Класс хранения данных по коннектору
    """

    def __init__(self, datasource, author_user, connector, connector_type, connector_type_preset):
        self.datasource = datasource
        self.author_user = author_user
        self.connector = connector
        self.connector_type = connector_type
        self.connector_type_preset = connector_type_preset
