class AuthError(Exception):
    def __init__(self, request):
        self.request = request

    def __str__(self):
        return repr(self.request)


class ServerError(Exception):
    def __init__(self, request):
        self.request = request

    def __str__(self):
        return repr(self.request)


class NoContentError(Exception):
    def __init__(self, request):
        self.request = request

    def __str__(self):
        return repr(self.request)


class RequestError(Exception):
    def __init__(self, request):
        self.request = request

    def __str__(self):
        return repr(self.request)


class UnexpectedError(Exception):
    def __init__(self, request):
        self.request = request

    def __str__(self):
        return repr(self.request)


class DbQueryError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return repr(self.error)


class UnexpectedResponseError(Exception):
    pass


class RetryHttpRequestError(Exception):
    def __init__(self, err_details):
        self.err_details = err_details


class ApiProxyError(Exception):
    def __init__(self, err_details):
        self.err_details = err_details


class EndOfTriesError(Exception):
    def __init__(self, err_details=None):
        self.err_details = err_details
