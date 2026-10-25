class ServiceError(Exception):
    def __init__(self, status_code: int, message: str, retry_after: str | None = None):
        self.status_code, self.message, self.retry_after = status_code, message, retry_after

def map_upstream_error(status: int, retry_after: str | None = None) -> ServiceError:
    messages = {401: (401, "AudicLabs rejected the API key."), 403: (403, "The API key does not have permission for this operation."),
                402: (402, "AudicLabs credits are exhausted."), 413: (413, "The audio file is too large."),
                422: (422, "AudicLabs could not read this audio. Try a supported audio file."),
                429: (429, "The service is rate limited. Please retry shortly."),
                503: (503, "The speech service is temporarily unavailable.")}
    code, message = messages.get(status, (502, "The speech service returned an unexpected error."))
    return ServiceError(code, message, retry_after)
