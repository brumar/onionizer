# onionizer

[![PyPI - Version](https://img.shields.io/pypi/v/onionizer.svg)](https://pypi.org/project/onionizer)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/onionizer.svg)](https://pypi.org/project/onionizer)

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

Onionizer is a library that allows you to wrap a function with a list of middlewares.
Think of it of a more yumy-yumy way to create and use decorators.

```python
import onionizer

@onionizer.as_decorator
def ensure_that_total_discount_is_acceptable(original_price, context):
    # you can do yummy stuff here (before the wrapped function is called)
    result = yield onionizer.UNCHANGED
    # and here (after the wrapped function is called)
    if original_price/result > 0.5:
        raise ValueError("Total discount is too high")
    return result

@ensure_that_total_discount_is_acceptable
def discount_function(original_price: int, context: dict) -> int:
    ...
```
Yummy!

The equivalent behavior without onionizer would be:
```python
import functools
def ensure_that_total_discount_is_acceptable(func):
    @functools.wraps(func)
    def wrapper(original_price, context):
        result = func(original_price, context)
        if original_price/result > 0.5:
            raise ValueError("Total discount is too high")
        return result
    return wrapper

@ensure_that_total_discount_is_acceptable
def discount_function(original_price, context):
    ...
```
Less Yummy!

The onionizer example is a bit more concise (and more flat) as there is no need to define and return a wrapper function (while keeping in mind to use `functools.wraps` to preserve the docstring and the signature of the wrapped function).
Yielding `onionizer.UNCHANGED` ensure the reader that the arguments are not modified by the middleware.
Of course, you can yield other values if you want to mutate the arguments (more on that later).
If there is an incompatibility of signatures, the middleware will raise an error at wrapping time, whereas the decorator syntax will fail at runtime one day you did not expect.

## Motivation

Onionizer is inspired by the onion model of middlewares in web frameworks such as Django, Flask and FastAPI.

If you are into web developpement, you certainly found this pattern very convenient as you plug middlewares to your application to add features such as authentication, logging, etc.

**Why not generalize this pattern to any function ? That's what Onionizer does.**

Hopefully, it could nudge communities share code more easily when they are using extensively the same specific API. Yes, I am looking at you `openai.ChatCompletion.create`.

# Installation

```bash
pip install onionizer
```
Onionizer has no sub-dependencies

## Usage

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

assert result == 2
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

## Features

- support for normal function if you only want to preprocess arguments or postprocess results
- support for context managers out of the box. Use this to handle resources or exceptions (try/except around the yield statement wont work for the middlewares)
- simplified preprocessing of arguments using `PositionalArgs` and `KeywordArgs` to match your preferred style or onionizer.UNCHANGED (see below)


## More on decorators vs middlewares : Flexibilty is good, until it's not

Chances are, if asked to add behavior before and after a function, you would use decorators. 
And that's fine! Decorators are awesome and super flexible. But in the programming world, flexibility can also be a weakness. 

Onionizer middlewares are more constrained to ensure composability : a middleware that do not share the exact same signature as the wrapped function will raise an error at wrapping time.
Using the yield statement to separate the setup from the teardown is now a classic pattern in python development. 
You might already be familiar with it if you are using context managers using contextlib.contextmanager or if you are testing your code with pytest fixtures.
It's flat, explicit and easy to read, it's pythonic then. So let's eat more of these yummy-yummy yield statements!

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

### Support for context managers

Onionizer middlewares are context managers out of the box. You can use this to handle resources or exceptions (try/except around the yield statement wont work for the middlewares).

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
with pytest.raises(RuntimeError) as e:
    wrapped_func(x=1, y=0)
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