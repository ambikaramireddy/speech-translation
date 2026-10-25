class ServiceError(Exception):
    def __init__(self, status_code: int, message: str, retry_after: str | None = None):
        self.status_code, self.message, self.retry_after = status_code, message, retry_after

def map_upstream_error(
    status: int, retry_after: str | None = None, operation: str = "stt"
) -> ServiceError:
    if status in (400, 404, 422) and operation == "tts":
        return ServiceError(
            422,
            "AudicLabs rejected speech synthesis. Choose a valid voice ID from GET /v1/languages and match it to the requested language.",
        )
    if status in (400, 422):
        if operation == "lookup":
            return ServiceError(502, "AudicLabs could not load its language and voice catalog.")
        return ServiceError(422, "AudicLabs could not read this audio. Upload a supported audio file with clear speech.")

    messages = {
        401: (401, "AudicLabs rejected the API key."),
        403: (403, "The API key does not have permission for this operation."),
        402: (402, "AudicLabs credits are exhausted."),
        413: (413, "The audio file is too large."),
        429: (429, "The service is rate limited. Please retry shortly."),
        503: (503, "The speech service is temporarily unavailable."),
    }
    code, message = messages.get(status, (502, "The speech service returned an unexpected error."))
    return ServiceError(code, message, retry_after)
