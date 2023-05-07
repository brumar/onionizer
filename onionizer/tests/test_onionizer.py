import asyncio
import contextlib

import pytest as pytest

import onionizer
from onionizer.onionizer import MixedArgs


@pytest.fixture
def func_that_adds():
    def func(x: int, y: int) -> int:
        return x + y

    return func


def test_mutate_arguments(func_that_adds):
    def middleware1(x: int, y: int) -> onionizer.Out[int]:
        result = yield MixedArgs((x + 1, y + 1), {})
        return result

    def middleware2(x: int, y: int) -> onionizer.Out[int]:
        result = yield MixedArgs((x, y + 1), {})
        return result

    wrapped_func = onionizer.wrap(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(0, 0)

    assert result == 3


def test_mutate_output(func_that_adds):
    def middleware1(x: int, y: int) -> onionizer.Out[int]:
        result = yield
        return result + 1

    def middleware2(x: int, y: int) -> onionizer.Out[int]:
        result = yield
        return result * 2

    wrapped_func = onionizer.wrap(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(0, 0)
    assert result == 1

    wrapped_func = onionizer.wrap(func_that_adds, [middleware2, middleware1])
    result = wrapped_func(0, 0)
    assert result == 2


def test_pos_only(func_that_adds):
    def middleware1(x: int, y: int):
        result = yield x + 1, y
        return result

    def middleware2(x: int, y: int):
        result = yield x, y + 1
        return result

    wrapped_func = onionizer.wrap(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(0, 0)
    assert result == 2


def test_kw_only(func_that_adds):
    def middleware1(x: int, y: int):
        result = yield {"x": x + 1, "y": y}
        return result

    def middleware2(x: int, y: int):
        result = yield {"x": x, "y": y + 1}
        return result

    wrapped_func = onionizer.wrap(func_that_adds, [middleware1, middleware2])
    result = wrapped_func(x=0, y=0)
    assert result == 2


def test_preprocessor(func_that_adds):
    @onionizer.preprocessor
    def midd1(x: int, y: int):
        return x + 1, y + 1

    assert midd1.__name__ == "midd1"

    wrapped_func = onionizer.wrap(func_that_adds, [midd1])
    result = wrapped_func(x=0, y=0)
    assert result == 2


def test_postprocessor(func_that_adds):
    @onionizer.postprocessor
    def midd1(val: int):
        return val ** 2

    assert midd1.__name__ == "midd1"

    wrapped_func = onionizer.wrap(func_that_adds, [midd1])
    result = wrapped_func(x=1, y=1)
    assert result == 4


def test_postprocessor_with_multiple_values():
    def dummy_func(x, y):
        return x, y

    @onionizer.postprocessor
    def midd1(couple: tuple):
        c1, c2 = couple
        return c2, c1

    wrapped_func = onionizer.wrap(dummy_func, [midd1])
    result = wrapped_func(x=1, y=2)
    assert result == (2, 1)


def test_support_for_context_managers():
    def func(x, y):
        return x / y

    @onionizer.postprocessor
    def midd1(val):
        return val + 1

    @contextlib.contextmanager
    def exception_catcher():
        try:
            yield
        except Exception as e:
            raise RuntimeError("Exception caught") from e

    wrapped_func = onionizer.wrap(func, [exception_catcher()])
    with pytest.raises(RuntimeError) as e:
        wrapped_func(x=1, y=0)
    assert str(e.value) == "Exception caught"

    another_wrapped_func = onionizer.wrap(func, [exception_catcher(), midd1])
    assert another_wrapped_func(x=1, y=1) == 2


def test_support_for_callable_instance(func_that_adds):

    class Middleware1:
        def __call__(self, x, y):
            result = yield
            return result

    wrapped_func = onionizer.wrap(func_that_adds, [Middleware1()])
    assert wrapped_func(x=1, y=1) == 2


def test_decorator():
    def middleware1(x, y):
        result = yield {"x": x + 1, "y": y}
        return result

    def middleware2(x, y):
        result = yield {"x": x, "y": y + 1}
        return result

    @onionizer.decorate([middleware1, middleware2])
    def func(x, y):
        return x + y

    @onionizer.decorate(middleware1)
    def func2(x, y):
        return x + y

    result = func(x=0, y=0)
    assert result == 2

    result2 = func2(x=0, y=0)
    assert result2 == 1


def test_incorrect_decorator():
    with pytest.raises(TypeError) as e:

        @onionizer.decorate(1)
        def func2(x, y):
            return x + y

    assert (
        str(e.value) == "layers must be a list of coroutines or a single coroutine"
    )


def test_as_decorator():
    @onionizer.as_decorator
    def middleware1(x, y):
        result = yield {"x": x + 1, "y": y}
        return result

    @onionizer.as_decorator
    def middleware2(x, y):
        result = yield {"x": x, "y": y + 1}
        return result

    @middleware1
    @middleware2
    def func(x, y):
        return x + y

    result = func(x=0, y=0)
    assert result == 2


def test_tooyielding_middleware(func_that_adds):
    def middleware1(*args):
        yield
        yield

    f2 = onionizer.wrap(
        func_that_adds, layers=[middleware1]
    )
    with pytest.raises(RuntimeError) as e:
        f2(1, 2)
    assert (
        str(e.value)
        == "Generator did not exhaust. Your function should yield exactly once."
    )


def test_incorrects_managers(func_that_adds):
    class MyManager:
        def __enter__(self):
            return self

    f = onionizer.wrap(func_that_adds, layers=[MyManager()])
    with pytest.raises(TypeError):
        f(1, 2)
    f2 = onionizer.wrap(
        func_that_adds, layers=[MyManager()])
    with pytest.raises(TypeError):
        f2(1, 2)


def test_incorrect_func():
    with pytest.raises(TypeError) as e:
        onionizer.wrap(1, [])
    assert str(e.value) == "func must be callable"


def test_incorrect_midlist(func_that_adds):
    def middleware1(*args):
        result = yield
        return result

    with pytest.raises(TypeError) as e:
        onionizer.wrap(func_that_adds, layers=middleware1)
    assert str(e.value) == "layers must be a list of coroutines"


def test_incorrect_yields(func_that_adds):
    def middleware1(x: int, y: int):
        yield 2
        return 1

    with pytest.raises(TypeError) as e:
        onionizer.wrap(func_that_adds, layers=[middleware1])(1, 2)
    assert (
        str(e.value) == "unrecognized yielded values. Pass a tuple, a dict or an instance of MixedArgs instead"
    )


@pytest.mark.parametrize('hardbypass,onlyyields', [(True, False), (True, False)])
def test_early_returns_but_with_yield(func_that_adds, hardbypass, onlyyields):
    if onlyyields:
        def mixed_middleware1(x: int, y: int):
            if x == 123:
                if hardbypass:
                    yield onionizer.HARD_BYPASS(-1)
                else:
                    yield onionizer.BYPASS(-1)
            else:
                result = yield
                return result
    else:
        def mixed_middleware1(x: int, y: int):
            if x == 123:
                if hardbypass:
                    return onionizer.HARD_BYPASS(-1)
                else:
                    return -1
            else:
                result = yield
                return result


    class MiddWare:
        def __init__(self):
            self.called_in = False
            self.called_out = False

        def __call__(self, *args, **kwargs):
            self.called_in = True
            r = yield
            self.called_out = True
            return r

    first_mid = MiddWare()
    last_mid = MiddWare()
    wrapped_func = onionizer.wrap(func_that_adds, [first_mid, mixed_middleware1, last_mid])
    result = wrapped_func(x=123, y=0)
    assert result == -1
    assert first_mid.called_in is True
    assert first_mid.called_out is not hardbypass
    assert last_mid.called_in is False
    assert last_mid.called_out is False


def test_error_for_async_middleware_on_syncfunc(func_that_adds):
    async def middleware1(x: int, y: int):
        await asyncio.sleep(0.1)
        res = yield
        yield res

    wrapped_func = onionizer.wrap(func_that_adds, [middleware1])
    with pytest.raises(TypeError):
        result = wrapped_func(x=1, y=2)


@pytest.mark.asyncio
async def test_sync_middleware_on_assyncfunc():

    async def func(x:int):
        await asyncio.sleep(0.1)
        return x
    def middleware1(x: int):
        res = yield (x+1, )
        return res

    wrapped_func = onionizer.wrap(func, [middleware1])
    result = await wrapped_func(0)
    assert result == 1

@pytest.mark.asyncio
async def test_async_middleware_on_assyncfunc():

    async def func(x:int):
        await asyncio.sleep(0.1)
        return x
    async def middleware1(x: int):
        await asyncio.sleep(0.1)
        res = yield x+1,
        yield res

    wrapped_func = onionizer.wrap(func, [middleware1])
    result = await wrapped_func(0)
    assert result == 1

@pytest.mark.asyncio
async def test_async_middleware_hard_bypass():
    async def func(x:int):
        await asyncio.sleep(0.1)
        return x
    async def middleware1(x: int):
        yield onionizer.HARD_BYPASS(-1)

    wrapped_func = onionizer.wrap(func, [middleware1])
    result = await wrapped_func(0)
    assert result == -1

@pytest.mark.asyncio
async def test_async_middleware_normal_bypass():
    async def func(x:int):
        await asyncio.sleep(0.1)
        return x
    def mid0(x: int):
        res = yield x,
        return res * 2
    async def middleware1(x: int):
        yield onionizer.BYPASS(-1)

    wrapped_func = onionizer.wrap(func, [mid0, middleware1])
    result = await wrapped_func(0)
    assert result == -2
