import contextlib

import pytest as pytest

import onionizer


@pytest.fixture
def func_that_adds():
    def func(x: int, y: int) -> int:
        return x + y

    return func


def test_mutate_arguments(func_that_adds):
    def middleware1(x: int, y: int) -> onionizer.OnionGenerator[int]:
        result = yield (x + 1, y + 1), {}
        return result

    def middleware2(x: int, y: int) -> onionizer.OnionGenerator[int]:
        result = yield (x, y + 1), {}
        return result

    wrapped_func = onionizer.wrap_around(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(0, 0)

    assert result == 3


def test_mutate_output(func_that_adds):
    def middleware1(x: int, y: int) -> onionizer.OnionGenerator[int]:
        result = yield onionizer.UNCHANGED
        return result + 1

    def middleware2(x: int, y: int) -> onionizer.OnionGenerator[int]:
        result = yield onionizer.UNCHANGED
        return result * 2

    wrapped_func = onionizer.wrap_around(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(0, 0)
    assert result == 1

    wrapped_func = onionizer.wrap_around(func_that_adds, [middleware2, middleware1])
    result = wrapped_func(0, 0)
    assert result == 2


def test_pos_only(func_that_adds):
    def middleware1(x: int, y: int):
        result = yield onionizer.PositionalArgs(x + 1, y)
        return result

    def middleware2(x: int, y: int):
        result = yield onionizer.PositionalArgs(x, y + 1)
        return result

    wrapped_func = onionizer.wrap_around(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(0, 0)
    assert result == 2


def test_kw_only(func_that_adds):
    def middleware1(x: int, y: int):
        result = yield onionizer.KeywordArgs({"x": x + 1, "y": y})
        return result

    def middleware2(x: int, y: int):
        result = yield onionizer.KeywordArgs({"x": x, "y": y + 1})
        return result

    wrapped_func = onionizer.wrap_around(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(x=0, y=0)
    assert result == 2


def test_preprocessor(func_that_adds):
    @onionizer.preprocessor
    def midd1(x: int, y: int):
        return onionizer.PositionalArgs(x + 1, y + 1)

    wrapped_func = onionizer.wrap_around(func_that_adds, [midd1])
    result = wrapped_func(x=0, y=0)
    assert result == 2


def test_postprocessor(func_that_adds):
    @onionizer.postprocessor
    def midd1(val: int):
        return val ** 2

    wrapped_func = onionizer.wrap_around(func_that_adds, [midd1])
    result = wrapped_func(x=1, y=1)
    assert result == 4


def test_postprocessor_with_multiple_values():
    def dummy_func(x, y):
        return x, y

    @onionizer.postprocessor
    def midd1(couple: tuple):
        c1, c2 = couple
        return c2, c1

    wrapped_func = onionizer.wrap_around(dummy_func, [midd1])
    result = wrapped_func(x=1, y=2)
    assert result == (2, 1)


def test_support_for_context_managers():
    def func(x, y):
        return x / y

    @contextlib.contextmanager
    def exception_catcher():
        try:
            yield
        except Exception as e:
            raise RuntimeError("Exception caught") from e

    wrapped_func = onionizer.wrap_around(func, [exception_catcher()])
    with pytest.raises(RuntimeError) as e:
        wrapped_func(x=1, y=0)
    assert str(e.value) == "Exception caught"


def test_decorator():
    def middleware1(x, y):
        result = yield onionizer.KeywordArgs({"x": x + 1, "y": y})
        return result

    def middleware2(x, y):
        result = yield onionizer.KeywordArgs({"x": x, "y": y + 1})
        return result

    @onionizer.decorate([middleware1, middleware2])
    def func(x, y):
        return x + y

    result = func(x=0, y=0)
    assert result == 2


def test_as_decorator():
    @onionizer.as_decorator
    def middleware1(x, y):
        result = yield onionizer.KeywordArgs({"x": x + 1, "y": y})
        return result

    @onionizer.as_decorator
    def middleware2(x, y):
        result = yield onionizer.KeywordArgs({"x": x, "y": y + 1})
        return result

    @middleware1
    @middleware2
    def func(x, y):
        return x + y

    result = func(x=0, y=0)
    assert result == 2


def test_uncompatible_signature(func_that_adds):
    def middleware1(*args):
        result = yield onionizer.UNCHANGED
        return result

    with pytest.raises(ValueError):
        onionizer.wrap_around(func_that_adds, middlewares=[middleware1])


def test_uncompatible_signature_but_disable_sigcheck(func_that_adds):
    def middleware1(*args):
        result = yield onionizer.UNCHANGED
        return result

    onionizer.wrap_around(func_that_adds, middlewares=[middleware1], sigcheck=False)
    assert True
