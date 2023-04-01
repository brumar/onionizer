import functools
import inspect
from abc import ABC
from contextlib import ExitStack
from typing import Callable, Any, Iterable, Sequence, TypeVar, Generator

T = TypeVar("T")

OnionGenerator = Generator[Any, T, T]

UNCHANGED = object()

__all__ = [
    "wrap_around",
    "decorate",
    "OnionGenerator",
    "UNCHANGED",
    "PositionalArgs",
    "MixedArgs",
    "KeywordArgs",
    "postprocessor",
    "preprocessor",
    "as_decorator",
]


def _capture_last_message(coroutine, value_to_send: Any) -> Any:
    try:
        coroutine.send(value_to_send)
    except StopIteration as e:
        # expected if the generator is exhausted
        return e.value
    else:
        raise RuntimeError(
            "Generator did not exhaust. Your function should yield exactly once."
        )


def _leave_the_onion(coroutines: Sequence, output: Any) -> Any:
    for coroutine in reversed(coroutines):
        # reversed to respect onion model
        output = _capture_last_message(coroutine, output)
    return output


def as_decorator(middleware):
    return decorate([middleware])


def decorate(middlewares):
    if not isinstance(middlewares, Iterable):
        if callable(middlewares):
            middlewares = [middlewares]
        else:
            raise TypeError(
                "middlewares must be a list of coroutines or a single coroutine"
            )

    def decorator(func):
        return wrap_around(func, middlewares)

    return decorator


def wrap_around(
    func: Callable[..., Any], middlewares: list, sigcheck: bool = True
) -> Callable[..., Any]:
    """
    It takes a function and a list of middlewares, and returns a function that calls the middlewares in order, then the
    function, then the middlewares in reverse order

    def func(x, y):
        return x + y

    def middleware1(*args, **kwargs):
        result = yield (args[0]+1, args[1]), kwargs
        return result

    def middleware2(*args, **kwargs):
        result = yield (args[0], args[1]+1), kwargs
        return result


    wrapped_func = dip.wrap_around(func, [middleware1, middleware2])
    result = wrapped_func(0, 0)

    assert result == 2

    :param func: the function to be wrapped
    :type func: Callable[..., Any]
    :param middlewares: a list of functions that will be called in order
    :type middlewares: list
    :return: A function that wraps the original function with the middlewares.
    """
    _check_validity(func, middlewares, sigcheck)

    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        arguments = MixedArgs(args, kwargs)
        coroutines = []
        with ExitStack() as stack:
            # programmatic support for context manager, possibly nested !
            # https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack
            for middleware in middlewares:
                if hasattr(middleware, "__enter__") and hasattr(middleware, "__exit__"):
                    stack.enter_context(middleware)
                    continue
                coroutine = arguments.call_function(middleware)
                coroutines.append(coroutine)
                raw_arguments = coroutine.send(None)
                arguments = _refine(raw_arguments, arguments)
            # just reached the core of the onion
            output = arguments.call_function(func)
            # now we go back to the surface
            output = _leave_the_onion(coroutines, output)
            return output

    return wrapped_func


def _check_validity(func, middlewares, sigcheck):
    if not callable(func):
        raise TypeError("func must be callable")
    if not isinstance(middlewares, Iterable):
        raise TypeError("middlewares must be a list of coroutines")
    if sigcheck:
        _inspect_signatures(func, middlewares)


def _inspect_signatures(func, middlewares):
    func_signature = inspect.signature(func)
    func_signature_params = func_signature.parameters
    for middleware in middlewares:
        if not hasattr(middleware, "ignore_signature_check") and not all(
            hasattr(middleware, attr) for attr in ("__enter__", "__exit__")
        ):
            middleware_signature = inspect.signature(middleware)
            middleware_signature_params = middleware_signature.parameters
            if middleware_signature_params != func_signature_params:
                raise ValueError(
                    f"Expected arguments of the target function mismatch middleware expecped arguments. {func.__name__}{func_signature} "
                    f"differs with {middleware.__name__}{middleware_signature}"
                )


def contextmanager(manager):
    @functools.wraps(manager)
    def wrapped(*args, **kwargs):
        with manager():
            output = yield UNCHANGED
            return output

    return wrapped


class ArgsMode(ABC):
    def call_function(self, func: Callable[..., Any]):
        raise NotImplementedError


class PositionalArgs(ArgsMode):
    def __init__(self, *args):
        self.args = args

    def call_function(self, func: Callable[..., Any]):
        return func(*self.args)


class KeywordArgs(ArgsMode):
    def __init__(self, kwargs):
        self.kwargs = kwargs

    def call_function(self, func: Callable[..., Any]):
        return func(**self.kwargs)


class MixedArgs(ArgsMode):
    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs

    def call_function(self, func: Callable[..., Any]):
        return func(*self.args, **self.kwargs)


def _refine(arguments, previous_arguments):
    if arguments is UNCHANGED:
        return previous_arguments
    if isinstance(arguments, ArgsMode):
        return arguments
    if len(arguments) != 2:
        raise TypeError(
            "arguments must be a tuple of length 2, maybe use onionizer.PositionalArgs or onionizer.MixedArgs instead"
        )
    args, kwargs = arguments
    return MixedArgs(args, kwargs)


def preprocessor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> OnionGenerator:
        arguments = yield func(*args, **kwargs)
        return arguments

    return wrapper


def postprocessor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> OnionGenerator:
        output = yield UNCHANGED
        return func(output)

    wrapper.ignore_signature_check = True
    return wrapper
