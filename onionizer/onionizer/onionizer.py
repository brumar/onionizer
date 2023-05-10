import asyncio
import functools
import inspect
import typing
from abc import ABC
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Callable, Any, Iterable, Sequence, TypeVar, Generator, Mapping

T = TypeVar("T")  # pragma: no mutate

OnionGenerator = Generator[Any, T, T]  # pragma: no mutate
Out = OnionGenerator

__all__ = [
    "wrap",
    "decorate",
    "Out",
    "PositionalArgs",
    "MixedArgs",
    "KeywordArgs",
    "postprocessor",
    "preprocessor",
    "as_decorator",
]

class HARD_BYPASS:
    """
    This is a special value that can be returned by a middleware to totally bypass the onion.
    If a middleware returns this value, no other middleware will be called.
    """
    def __init__(self, value):
        self.value = value

class BYPASS:
    """
    This is a special value that can be returned by a middleware to bypass the wrapped function.
    other middleware will be called.
    """
    def __init__(self, value):
        self.value = value

def _capture_last_message(coroutine, value_to_send: Any) -> Any:
    middleware_output = _capture_message(coroutine, value_to_send)
    if middleware_output.status != "stop":
        raise RuntimeError(
            "Generator did not exhaust. Your function should yield exactly once."
        )
    return middleware_output.value

# dataclass representing middleware output
@dataclass
class MiddlewareOutput:
    value: Any
    coroutine_ended: bool

    @property
    def status(self):
        if isinstance(self.value, HARD_BYPASS):
            return 'hard_stop'
        if isinstance(self.value, BYPASS) or self.coroutine_ended:
            return 'stop'

    @property
    def output(self):
        if isinstance(self.value, (HARD_BYPASS, BYPASS)):
            return self.value.value
        else:
            return self.value

def get_middleware_output(coroutine):
    middleware_output = _capture_message(coroutine, None)
    return middleware_output


def _leave_the_onion(coroutines: Sequence, output: Any) -> Any:
    for coroutine in reversed(coroutines):
        # reversed to respect onion model
        output = _capture_last_message(coroutine, output)
    return output


def as_decorator(middleware):
    return decorate([middleware])


def decorate(layers):
    if not isinstance(layers, Iterable):
        if callable(layers):
            layers = [layers]
        else:
            raise TypeError(
                "layers must be a list of coroutines or a single coroutine"
            )

    def decorator(func):
        return wrap(func, layers)

    return decorator


async def _capture_async_message(coroutine, value_to_send: Any) -> Any:
    if hasattr(coroutine, "__next__"):
        return _capture_message(coroutine, value_to_send)
    elif hasattr(coroutine, "__anext__"):
        try:
            val = await coroutine.asend(value_to_send)
            return MiddlewareOutput(val, coroutine_ended=False)
        except StopAsyncIteration as e:
            # expected if the generator is exhausted
            return MiddlewareOutput(e.value, coroutine_ended=True)
    else:
        raise TypeError(
            f"Middleware {coroutine} is not a coroutine. "
            f"Did you forget to use a yield statement?"
        )
def _capture_message(coroutine, value_to_send: Any) -> MiddlewareOutput:
    if not hasattr(coroutine, "__next__"):
        raise TypeError(
            f"Middleware {coroutine} is not a coroutine. "
            f"Did you forget to use a yield statement?"
        )
    try:
        val = coroutine.send(value_to_send)
        return MiddlewareOutput(val, coroutine_ended=False)
    except StopIteration as e:
        # expected if the generator is exhausted
        return MiddlewareOutput(e.value, coroutine_ended=True)


async def async_get_middleware_output(coroutine):
    output = _capture_async_message(coroutine, None)
    if inspect.isawaitable(output):
        output = await output
    return output


def wrap(
    func: Callable[..., Any], layers: typing.Union[Sequence, Callable[..., Any]]
) -> Callable[..., Any]:
    """
    It takes a function and a list of middleware,
    and returns a function that calls the middleware in order, then the
    function, then the middleware list in reverse order

    def func(x, y):
        return x + y

    def middleware1(*args, **kwargs):
        result = yield (args[0]+1, args[1]), kwargs
        return result

    def middleware2(*args, **kwargs):
        result = yield (args[0], args[1]+1), kwargs
        return result


    wrapped_func = dip.wrap(func, [middleware1, middleware2])
    result = wrapped_func(0, 0)

    assert result == 2

    :param func: the function to be wrapped
    :type func: Callable[..., Any]
    :param layers: a list of functions that will be called in order
    :type layers: list
    :return: A function that wraps the original function with the middleware list
    """
    _check_validity(func, layers)

    if not asyncio.iscoroutinefunction(func):

        @functools.wraps(func)  # pragma: no mutate
        def wrapped_func(*args, **kwargs):
            arguments = MixedArgs(args, kwargs)
            coroutines = []
            a_middleware_exited_with_result = False
            with ExitStack() as stack:
                # programmatic support for context manager, possibly nested !
                # https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack
                for middleware in layers:
                    if hasattr(middleware, "__enter__") and hasattr(middleware, "__exit__"):
                        stack.enter_context(middleware)
                        continue
                    coroutine = arguments.call_function(middleware)
                    if not isinstance(coroutine, typing.Generator):

                        raise TypeError(
                            f"Middleware {middleware} is not a coroutine. "
                            f"Did you forget to use a yield statement?"
                        )
                    middleware_output = get_middleware_output(coroutine)
                    if middleware_output.status == "hard_stop":
                        return middleware_output.output
                    if middleware_output.status == "stop":
                        a_middleware_exited_with_result = True
                        break
                    arguments = _refine(middleware_output.output, arguments)
                    coroutines.append(coroutine)
                # just reached the core of the onion
                if a_middleware_exited_with_result is False:
                    output = arguments.call_function(func)
                else:
                    output = middleware_output.output
                # now we go back to the surface
                output = _leave_the_onion(coroutines, output)
                return output


        return wrapped_func

    else:
        @functools.wraps(func)  # pragma: no mutate
        async def wrapped_func(*args, **kwargs):
            with ExitStack() as stack:
                arguments = MixedArgs(args, kwargs)
                coroutines = []
                a_middleware_exited_with_result = False
                # programmatic support for context manager, possibly nested !
                # https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack
                for middleware in layers:
                    if hasattr(middleware, "__enter__") and hasattr(middleware, "__exit__"):
                        stack.enter_context(middleware)
                        continue
                    coroutine = arguments.call_function(middleware)
                    if not isinstance(coroutine, typing.Generator) and not isinstance(coroutine, typing.AsyncGenerator):

                        raise TypeError(
                            f"Middleware {middleware} is not a coroutine. "
                            f"Did you forget to use a yield statement?"
                        )
                    middleware_output = await async_get_middleware_output(coroutine)
                    if middleware_output.status == "hard_stop":
                        return middleware_output.output
                    if middleware_output.status == "stop":
                        a_middleware_exited_with_result = True
                        break
                    arguments = _refine(middleware_output.output, arguments)
                    coroutines.append(coroutine)
                # just reached the core of the onion
                if a_middleware_exited_with_result is False:
                    output = await arguments.call_function(func)
                else:
                    output = middleware_output.output
                # now we go back to the surface
                for coroutine1 in reversed(coroutines):
                # reversed to respect onion model
                    middleware_output = await _capture_async_message(coroutine1, output)
                    output = middleware_output.output
                return output
        return wrapped_func



def _check_validity(func, layers):
    if not callable(func):
        raise TypeError("func must be callable")
    if not isinstance(layers, Iterable):
        raise TypeError("layers must be a list of coroutines")
    # if sigcheck:
    #     _inspect_signatures(func, middlewares)


# def _inspect_signatures(func, middlewares):
#     func_signature = inspect.signature(func)
#     func_signature_params = func_signature.parameters
#     for middleware in middlewares:
#         if not (
#             hasattr(middleware, "ignore_signature_check")
#             and middleware.ignore_signature_check is True
#         ) and not all(hasattr(middleware, attr) for attr in ("__enter__", "__exit__")):
#             middleware_signature = inspect.signature(middleware)
#             middleware_signature_params = middleware_signature.parameters
#             if middleware_signature_params != func_signature_params:
#                 raise ValueError(
#                     f"Expected arguments of the target function mismatch "
#                     f"middleware expected arguments. {func.__name__}{func_signature} "
#                     f"differs with {middleware.__name__}{middleware_signature}"
#                 )


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
    if arguments is None:
        return previous_arguments
    if isinstance(arguments, ArgsMode):
        return arguments
    if isinstance(arguments, Sequence):
        return PositionalArgs(*arguments)
    if isinstance(arguments, Mapping):
        return KeywordArgs(arguments)
    raise TypeError('unrecognized yielded values. Pass a tuple, a dict or an instance of MixedArgs instead')


def preprocessor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> OnionGenerator:
        arguments = yield func(*args, **kwargs)
        return arguments

    return wrapper


def postprocessor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> OnionGenerator:
        output = yield
        return func(output)

    # wrapper.ignore_signature_check = True
    return wrapper
