
# onionizer

[![PyPI - Version](https://img.shields.io/pypi/v/onionizer.svg)](https://pypi.org/project/onionizer)
[![Mutation tested with mutmut](https://img.shields.io/badge/mutation%20tested-mutmut-green)](https://mutmut.readthedocs.io/)
[![brumar](https://circleci.com/gh/brumar/onionizer.svg?style=shield)](https://circleci.com/gh/brumar/onionizer)
[![codecov](https://codecov.io/gh/brumar/onionizer/branch/main/graph/badge.svg?token=SJ55K5MH0U)](https://codecov.io/gh/brumar/onionizer)
![versions](https://img.shields.io/pypi/pyversions/pybadges.svg)

-----

**Table of Contents**

- [Introduction](#introduction)
- [Motivation](#motivation)
- [Installation](#installation)
- [Middlewares Composition](#usage)
- [Support For Context Managers](#support-for-context-managers)
- [Advanced Usage](#advanced-usage)
- [Onionizer vs raw decorators](#onionizer-vs-raw-decorators)
- [Gotchas](#gotchas)
- [Roadmap and Ideas](#roadmapideas)
- [License](#license)


## Introduction

Onionizer is a small and focused library that makes decorators easier to read, write and chain.

To understand its benefits, let's make a short detour and review the anatomy of a classical decorator:

```python
import functools
def my_decorator(func):  # yes, a function that takes a function and returns a function
    @functools.wraps(func)  # to preserve the signature and the docstring
    def wrapper(*args, **kwargs): # ouch, let's define a new function
        # A] write some stuff here
        result = func(*args, **kwargs)
        # B] write some stuff there
        return result
    return wrapper  # and return the function (don't forget this line)
```

Now compare it to the anatomy of a [pytest fixture](https://docs.pytest.org/en/7.3.x/explanation/fixtures.html#about-fixtures):
```python
import pytest
@pytest.fixture
def a_pytest_fixture():
    # A] write some stuff here
    yield 'something'
    # B] write some stuff there
```
Less visual noise, isn't it? The usage of `yield` is a nice trick to make the code more readable.
This pattern is also [the preferred way to write context managers](https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager).
If you believe that flat is better than nested, you might like this yield trickery.

With onionizer, you can write your decorators in a similar way:

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

Onionizer decorator-like are called middleware and sometimes referred to as onion layers.

Features include:
- middleware composition (accepting a list of onionizer middleware)
- possibility to mutate the arguments given to the wrapped function in a readable way
- support for context managers and callable objects
- onionizer middleware work seamlessly with sync and async functions (no need to write your logic twice anymore)

## Motivation

Onionizer is inspired by the onion model of middleware in web frameworks such as Django, Flask and FastAPI.

If you did a bit of web developement, you certainly found this pattern very convenient as you plug middleware to your application to add features such as authentication, logging, etc.

**Why not generalize this pattern to any function ? That's what Onionizer does.**

Hopefully, it could nudge communities share code more easily when they are using extensively the same specific API. Yes, I am looking at you `openai.ChatCompletion.create`.

## Installation

```bash
pip install onionizer
```
No extra dependencies required.

## Middlewares composition

`onionizer.as_decorator` was introduced in the introduction.
Another way to use onionizer is to wrap a function with a list of middleware using `onionizer.wrap` :

```python
import onionizer
def func(x, y):
    return x + y

def middleware1(x, y):
    result = yield x+1, y+1  # yield the new arguments and keyword arguments ; obtain the result
    return result # Do nothing with the result

def middleware2(x, y):
    result = yield x, y  # arguments are not preprocessed by this middleware
    return result*2 # double the result

wrapped_func = onionizer.wrap(func, [middleware1, middleware2])
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

## Support For Context Managers

Context managers are supported by onionizer.

```python
import onionizer 

def func(x, y):
    with exception_catcher():
        return x/y

@contextlib.contextmanager
def exception_catcher():
    try:
        yield
    except Exception as e:
        raise RuntimeError("Exception caught") from e

wrapped_func = onionizer.wrap(func, [exception_catcher()])  # notice the parenthesis, onionizer needs an instance of the context manager
wrapped_func(x=1, y=0) # raises RuntimeError("Exception caught")
```

Do use context manager if you need to do some cleanup after the wrapped function has been called or if you want to catch exceptions.

Indeed, having a `try-except` block around the yield statement will not work for onionizer middleware.


## Support For Async Functions

If you want to write decorators that are compatible with both sync and async functions, you will end up doing something like that:

```python
import asyncio
import functools

def dec(fn):
    if asyncio.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # do some stuff here
            res = await fn(*args, **kwargs)
            # do some stuff there
        return wrapper
    else:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # do some stuff here
            return fn(*args, **kwargs)
            # do some stuff there
        return wrapper
```
it's not very readable, isn't it? One temptation would be to abide to DRY principle and write a function for `do some stuff here` and another one for `do some stuff there`.
But that's forcing you to add unwanted abstractions to your code by splitting your behavior it into two functions.

With onionizer, you don't have to think about it anymore. Just write your middleware as usual and onionizer will take care of the rest.

```python
import onionizer
import asyncio

async def func(x:int):
    await asyncio.sleep(0.1)
    return x

def middleware1(x: int):
    res = yield x+1, 
    return res

wrapped_func = onionizer.wrap(func, [middleware1])  
result = await wrapped_func(0)  # as func is async, wrapped_func is async too
print(result) # 1
```

** can my middleware be async too ? **

Yes, it can. But this will work only if the wrapped function is async too.
Also, there is a small caveat: you will need to yield the final result instead of returning it.
This is a limitation of asynchronous generators (PEP 525).

```python
import asyncio
import onionizer

async def func(x:int):
    await asyncio.sleep(0.1)
    return x

async def middleware1(x: int):
    await asyncio.sleep(0.1)
    res = yield x+1,
    yield res

wrapped_func = onionizer.wrap(func, [middleware1])
result = await wrapped_func(0)
print(result) # 1
```


## Advanced Usage

### Easy way to pass mutated arguments to the wrapped function

The default way of using the yield statement is to pass either a tuple of positional arguments or a dict of keyword arguments.

```python
import onionizer
def func(x, y):
    return x + y

def middleware1(x: int, y: int):
    result = yield {'x': x, 'y': y + 1} # keyword arguments only
    return result

def middleware2(x: int, y: int):
    result = yield x + 1, y # positional arguments only
    return result

def middleware3(x: int, y: int):
    result = yield  # no mutation
    return result + 1

wrapped_func = onionizer.wrap(func, [middleware1, middleware2, middleware3])
print(wrapped_func(x=0, y=0)) # 3
```

### MixedArgs

In case you really need to pass both positional and keyword arguments, you can use `onionizer.MixedArgs` :

```python
import onionizer
def middleware1(x: int, y: int):
    result = yield onionizer.MixedArgs(args=(x+1, ), kwargs={'y': y+1}) # pass a tuple of positional arguments and a dict of keyword arguments
    return result
```

### Early return works

Let's say you need a caching or validation middleware, you can return a value to skip the wrapped function or any remaining onion layers.

```python
import onionizer
def func(x, y):
    return x + y

def middleware1(x: int, y: int):
    if x == 0:
        return 0 # early return
    else:
        result = yield
        return result

wrapped_func = onionizer.wrap(func, [middleware1])
print(wrapped_func(x=0, y=0)) # 0
```

On an early return, the next onion layers are skipped and the wrapped function won't be called.
However, to play nicely with the middleware already in play, all the previous onion layers will be called on the way back.
```python
import onionizer
def func(x, y):
    print("FUNC CALLED")
    return x + y

def middleware1(x: int, y: int):
    if x == 0:
        print("EARLY RETURN")
        return 0
    else:
        result = yield
        return result
    
def polite_middleware(x: int, y: int):
    print("Hello")
    result = yield
    print("Goodbye")
    return result
    
wrapped_func = onionizer.wrap(func, [polite_middleware, middleware1])  # polite_middleware will be called on the way back
print(wrapped_func(x=0, y=0)) 
# Hello
# EARLY RETURN
# Goodbye
```

By using the `HARD_BYPASS` container, it's possible to skip all remaining onion layers and return a value without calling the wrapped function.
This means not playing nicely with the other middleware that are already contacted.
This is **discouraged** and should be used as a last resort only.

```python
import onionizer
def func(x, y):
    print("FUNC CALLED")
    return x + y

def middleware1(x: int, y: int):
    if x == 0:
        return onionizer.HARD_BYPASS(0)
    else:
        result = yield
        return result

def polite_middleware(x: int, y: int):
    print("Hello")
    result = yield
    print("Goodbye")
    return result

wrapped_func = onionizer.wrap(func, [polite_middleware, middleware1])  # polite_middleware won't be called on the way back
print(wrapped_func(x=0, y=0))
# Hello
# 0
```

### Early return with async functions

Early return works with async functions too, but you will need to yield the result instead of returning it.
This is a limitation of asynchronous generators (PEP 525).

`yield onionizer.HARD_BYPASS(result)` will be understood by onionizer, as well as `yield onionizer.BYPASS(result)` to simulate a regular return.

### Typing

onionizer let you type nicely your middleware so that it's made apparent what arguments they expect and what they return.
The return value might be harder to type as your middleware is in fact a generator. 
We provide a `onionizer.Out` type to help you with that and let type checkers work their magic.

```python

import onionizer
def func(x: int, y: int) -> int:
    return x + y

def middleware1(x: int, y: int) -> onionizer.Out[int]:
    result = yield {'x': x, 'y': y + 1} # keyword arguments only
    return result
```

The proximity of the middleware signature with the wrapped function signature makes it easier to read and write
and value the fact that onionizer is a composition tool that cares about the domain model of the wrapped function (cf next section)

### Middlewares with state

Middlewares can be instances of classes that implement the `__call__` method, which is a practical way to store some state between calls.

```python
import onionizer

class MiddWare:
    def __init__(self):
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        r = yield
        return r


middware = MiddWare()
wrapped_func = onionizer.wrap(lambda x: x, [middware])
wrapped_func(None)
wrapped_func(None)
print(middware.call_count)  # 2
 ```

## Onionizer vs raw decorators

### tl;dr

When the very same API is used by many projects: use onionizer.

For truly cross-cutting concerns: use raw decorators.

### Extended discussion

Let's discuss the pros and cons of using onionizer vs raw decorators.

pros for onionizer middleware: 
- easier to read and write 
- features that eases the creation of your onion model.
- free support for async functions

cons for onionizer middleware:
- extra library to depend on (or extra code if you copy and paste the code from onionizer.py in your utils.py, which is fine if you ask me)
- some time required to get used to the API (but not much, it's really simple)

I believe middleware are a great pattern to build software by composition but also to share code between projects that revolves around the same API.
Generally, decorators are more thought as a way to handle cross-cutting concerns (logging, caching, etc.) and not as a way to share code between projects.
Middlewares, on the other hand, are a great way to share code between projects that revolves around the same API (cf this [2022 pycon talk](https://www.youtube.com/watch?v=_t7GxTbKocc) 
where the author explain and demonstrates how the WSGI spec which defines the signature of python web applications allows to share code between frameworks when using middleware.

When the very same API is used by many projects, I think it's a good idea to provide a framework to help code authors (yourself included) to build their own middleware without having to write raw decorators.
Onionizer lets you bootstrap this framework.

## Gotchas

- as stated earlier, sandwiching your `yield` statement with a `try-except` block won't work in a middleware. Use a context manager instead.
- only sync functions can be wrapped by onionizer at the moment.
- async middlewares can't use return statements, they have to yield the result instead (or yield `onionizer.HARD_BYPASS(result)` or `onionizer.BYPASS(result)`.

## Roadmap/Ideas

- [ ] extend the support for other types of functions: methods, generators async functions..
- [ ] (?) provide ports for other Middleware frameworks (e.g `@onionizer.as_wsgi_middleware`)
- [ ] (?) Provide a more consistent middleware experience with no use of return statement (`yield Return(val) ?` and `yield HardReturn(val) ?`)
- [ ] do not capture errors from the middleware itself


## License

`onionizer` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
