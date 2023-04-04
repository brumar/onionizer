
# onionizer

[![PyPI - Version](https://img.shields.io/pypi/v/onionizer.svg)](https://pypi.org/project/onionizer)
[![Mutation tested with mutmut](https://img.shields.io/badge/mutation%20tested-mutmut-green)](https://mutmut.readthedocs.io/)
[![brumar](https://circleci.com/gh/brumar/onionizer.svg?style=shield)](https://circleci.com/gh/brumar/onionizer)
[![codecov](https://codecov.io/gh/brumar/onionizer/branch/main/graph/badge.svg?token=SJ55K5MH0U)](https://codecov.io/gh/brumar/onionizer)
![versions](https://img.shields.io/pypi/pyversions/pybadges.svg)

-----

**Table of Contents**

- [Introduction](#Introduction)
- [Motivation](#Motivation)
- [Installation](#Installation)
- [Usage](#Usage)
- [Features](#Features)
- [More on decorators vs middlewares: Flexibilty is good, until it's not](#More-on-decorators-vs-middlewares--Flexibilty-is-good-until-its-not)
- [Advanced Usage](#Advanced-Usage)


## Introduction

WARNING : this readme is a mess, I am working on it. Only the Introduction is acceptable at the moment.

Onionizer is a library that makes decorators easier to read, write and chain.
Let's review the anatomy of a classical decorator:

```python
import functools
def ensure_that_total_discount_is_acceptable(func):
    @functools.wraps(func)  # to preserve the signature and the docstring
    def wrapper(*args, **kwargs): # ouch, let's define a new function
        # A] write some stuff here
        result = func(*args, **kwargs)
        # B] write some stuff there
        return result
    return wrapper  # and return the function
```

Now compare it to a pytest fixture:
```python
import pytest
@pytest.fixture
def a_pytest_fixture():
    # A] write some stuff here
    yield 'something'
    # B] write some stuff there
```
Less visual noise, isn't it? 
This pattern is also [the preferred way to write context managers](https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager).

Of course, a pytest fixture is not a valid decorator, but with onionizer, one tweak is enough to make it one:

```python
import onionizer
@onionizer.as_decorator
def my_decorator(*args, **kwargs):
    # A] write some stuff here
    result = yield  # we obtain the result of the wrapped function
    # B] write some stuff there
    return result
```

Then you can use it as usual:
```python
@my_decorator
def my_function(*args, **kwargs):
    return 'something'
```

Onionizer decorator-like are called middlewares.

Features include:
- possibility to mutate the arguments given to the wrapped function
- ensure the middleware signature is compatible with the wrapped function
- middlewares composition (accepting a list of onionizer middlewares and context managers)

## Motivation

Onionizer is inspired by the onion model of middlewares in web frameworks such as Django, Flask and FastAPI.

If you are into web developement, you certainly found this pattern very convenient as you plug middlewares to your application to add features such as authentication, logging, etc.

**Why not generalize this pattern to any function ? That's what Onionizer does.**

Hopefully, it could nudge communities share code more easily when they are using extensively the same specific API. Yes, I am looking at you `openai.ChatCompletion.create`.

# Installation

```bash
pip install onionizer
```
No extra dependencies required.

## Middlewares composition

We saw the usage of onionizer.as_decorator in the introductive example.
Another way to use onionizer is to wrap a function with a list of middlewares using `onionizer.wrap_around` :

```python
import onionizer
def func(x, y):
    return x + y

def middleware1(x, y):
    result = yield (x+1, y+1), {}  # yield the new arguments and keyword arguments ; obtain the result
    return result # Do nothing with the result

def middleware2(x, y):
    result = yield (x, y), {}  # arguments are not preprocessed by this middleware
    return result*2 # double the result

wrapped_func = onionizer.wrap_around(func, [middleware1, middleware2])
result = wrapped_func(0, 0)
print(result) # 2
```

Tracing the execution layers by layers :
- `middleware1` is called with arguments `(0, 0)` ; it yields the new arguments `(1, 1)` and keyword arguments `{}` 
- `middleware2` is called with arguments `(1, 1)` ; it yields the new arguments `(1, 1)` and keyword arguments `{}` (unchanged)
- `wrapped_func` calls `func` with arguments `(1, 1)` which returns `2`
- `middleware2` returns `4`
- `middleware1` returns `4` (unchanged)

Alternatively, you can use the decorator syntax :
```python
@onionizer.decorate([middleware1, middleware2])
def func(x, y):
    return x + y
```

#### Support for context managers

context managers are de facto supported by onionizer.

```python
def func(x, y):
    with exception_catcher():
        return x/y

@contextlib.contextmanager
def exception_catcher():
    try:
        yield
    except Exception as e:
        raise RuntimeError("Exception caught") from e

wrapped_func = onionizer.wrap_around(func, [exception_catcher()])
wrapped_func(x=1, y=0) # raises RuntimeError("Exception caught")
```

## Advanced usage

### PositionalArgs and KeywordArgs

The default way of using the yield statement is to pass a tuple of positional arguments and a dict of keyword arguments.
But you can also pass `onionizer.PositionalArgs` and `onionizer.KeywordArgs` to simplify the preprocessing of arguments.
Onionizer provides two classes to simplify the preprocessing of arguments : `PositionalArgs`, `KeywordArgs`.

```python
import onionizer
def func(x, y):
    return x + y

def middleware1(x: int, y: int):
    result = yield onionizer.PositionalArgs(x + 1, y) # pass any number of positional arguments
    return result

def middleware2(x: int, y: int):
    result = yield onionizer.KeywordArgs({'x': x, 'y': y + 1}) # pass a dict with any number of keyword arguments
    return result
wrapped_func = onionizer.wrap_around(func, [middleware1, middleware2])
```
And if you want to keep the arguments unchanged, you can use `onionizer.UNCHANGED` :
```python
def wont_do_anything(x: int, y: int):
    result = yield onionizer.UNCHANGED
    return result
```


### Support for simple functions

You can use simple functions if you only want to preprocess arguments or postprocess results.

```python
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
        return val**2

    wrapped_func = onionizer.wrap_around(func_that_adds, [midd1])
    result = wrapped_func(x=1, y=1)
    assert result == 4
```

### Remove signature checks

By default, onionizer will check that the signature of the middlewares matches the signature of the wrapped function. This is to ensure that the middlewares are composable. If you want to disable this check, you can use `onionizer.wrap_around_no_check` instead of `onionizer.wrap_around`.

```python
def test_uncompatible_signature_but_disable_sigcheck(func_that_adds):
    def middleware1(*args):
        result = yield onionizer.UNCHANGED
        return result

    onionizer.wrap_around(func_that_adds, middlewares=[middleware1], sigcheck=False)
    assert True
```

## License

`onionizer` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Gotchas

- `Try: yield except:` won't work in a middleware. Use a context manager instead.
- only sync functions are supported at the moment, no methods, no classes, no generators, no coroutines, no async functions.
- middlewares must have the same signature as the wrapped function. Use sigcheck=False to disable this check. 
Authorize the use of `*args` and `**kwargs` in middlewares is under consideration