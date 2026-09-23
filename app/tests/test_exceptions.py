# File: app/tests/test_exceptions.py
"""Every application exception must produce a well-formed error envelope."""

import inspect
import typing

import pytest

from app.exceptions import auth_exceptions, base_exceptions, validation_exceptions
from app.exceptions.base_exceptions import BaseAppException

_DUMMY = {str: "value", int: 3, float: 0.5, list: ["a"], dict: {}, typing.Any: "x"}


def _exception_classes():
    for module in (base_exceptions, auth_exceptions, validation_exceptions):
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseAppException)
                and cls is not BaseAppException
                and cls.__module__ == module.__name__
            ):
                yield cls


def _build(cls):
    kwargs = {}
    for name, param in inspect.signature(cls.__init__).parameters.items():
        if name == "self" or param.default is not inspect.Parameter.empty:
            continue
        annotation = param.annotation
        origin = typing.get_origin(annotation)
        if origin is list:
            kwargs[name] = ["a"]
        elif origin is dict:
            kwargs[name] = {}
        elif origin is typing.Union or str(origin) == "types.UnionType":
            kwargs[name] = _DUMMY.get(typing.get_args(annotation)[0], "x")
        else:
            kwargs[name] = _DUMMY.get(annotation, "x")
    return cls(**kwargs)


@pytest.mark.parametrize("cls", list(_exception_classes()), ids=lambda c: c.__name__)
def test_exception_shape(cls):
    exc = _build(cls)
    assert isinstance(exc, BaseAppException)
    assert 400 <= exc.status_code < 600
    assert exc.error_code and exc.error_code.isupper()
    assert exc.message and isinstance(exc.message, str)
    assert isinstance(exc.details, dict)
    assert exc.detail == exc.message  # HTTPException compatibility


def test_unauthorized_sets_www_authenticate():
    exc = base_exceptions.UnauthorizedException()
    assert exc.headers == {"WWW-Authenticate": "Bearer"}


def test_rate_limit_retry_after_header():
    exc = base_exceptions.RateLimitException(retry_after=30)
    assert exc.status_code == 429
    assert exc.headers["Retry-After"] == "30"


def test_resource_limit_details():
    exc = base_exceptions.ResourceLimitException(resource="uploads", limit=5, current=6)
    assert exc.details == {"resource": "uploads", "limit": 5, "current": 6}
    assert "uploads limit exceeded" in exc.message


def test_external_service_message_prefixed():
    exc = base_exceptions.ExternalServiceException("stripe", message="timeout")
    assert exc.message == "stripe: timeout"
    assert exc.details["service"] == "stripe"


async def test_envelope_through_the_app(async_client):
    """A raised BaseAppException renders via the global handler."""
    from app.main import app

    @app.get("/__test_exc")
    async def _boom():
        raise validation_exceptions.DuplicateValueException(field="email", value="a@b.co")

    try:
        response = await async_client.get("/__test_exc")
    finally:
        app.router.routes[:] = [
            r for r in app.router.routes if getattr(r, "path", "") != "/__test_exc"
        ]

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "DUPLICATE_VALUE"
    assert body["details"]["field"] == "email"
    assert body["request_id"]
