# Overall Style
This page documents the methods and reasons for the main code style for this project.
Each element will discuss a different aspect about developing neat and quality code, as well as provide a little example to run by.
 
## Python Type Checker, Pyright
You should develop your project using [`Pyright's`](https://github.com/microsoft/pyright) strict mode. Type checking plays a large aspect in the development
of clean code, it allows for potential unknown mistakes you may be creating to be fixed before they even happen. Strict mode will ensure that every variable and definition
is a known type. If you create a variable with a type that can't be inferred, you will get a warning.
 
### Using Pyright
If your IDE does not have direct support for a changeable static type checker, such as VSCode does, you will need to use
[pyright's command line interface](https://github.com/RobertCraigie/pyright-python). You should run this after making any changes and before pushing any code.
 
If your IDE does have support for this however, install pyright and set it to strict mode.
 
### Error Lens
If you're developing in Visual Studio Code, it may be beneficial to install [Error Lens](https://github.com/karlsander/vscode-error-lens) into your
installation of VSCode. This will more easily alert you of any errors you create while you develop your code.
 
### Examples of Pyright Strict Mode
 
Let's take a look at this function called `foo`. It will take in an input, `x`, and return the input plus one.
```python
def foo(x):
    return x + 1
   
from typing_extensions import reveal_type
reveal_type(foo(1))
```
 
Although we know what `foo` does and what to pass into it, Pyright does not know what `x` is supposed to be. Let's check using pyright to see what's wrong.
 
```python
Found 1 source file
F:testing.py
  F:\testing.py:2:9 - error: Type of parameter "x" is unknown (reportUnknownParameterType)
  F:\testing.py:2:9 - error: Type annotation is missing for parameter "x" (reportMissingParameterType)        
  F:\testing.py:3:12 - error: Return type is unknown (reportUnknownVariableType)
  F:\testing.py:2:5 - error: Return type is unknown (reportUnknownParameterType)
  F:\testing.py:6:13 - information: Type of "foo(1)" is "Literal[2]"
4 errors, 0 warnings, 1 information
Completed in 0.584sec
```
 
So what does this mean? Pyright needs to know the type of `x`. Let's refactor our code and add type annotations.
```python
def foo(x: float) -> float:
    return x + 1
 
from typing_extensions import reveal_type
reveal_type(foo(1))
```
 
Now that pyright knows what type every item in `foo` is supposed to be, we get no errors.
```python
Found 1 source file
F:\testing.py
  F:\testing.py:6:13 - information: Type of "foo(1)" is "float"
0 errors, 0 warnings, 1 information
```
 
### Development with discord.py
When developing with [discord.py](https://github.com/Rapptz/discord.py), it's important to keep all of your code typed.
 
```python
@bot.command()
async def my_command(ctx: commands.Context[commands.Bot], arg: str, *, message: Optional[str] = None) -> None:
    ...
```
 
## Python Code Formatter
When many developers are working on a single project, it's important to have a consistent style of code. To achieve this, we use a tool called [`black`](https://black.readthedocs.io/en/stable/). Black will format your code to a consistent style. This is a good way to make sure your code is readable and easy to understand.
 
I encourage you to watch this [seminar on black](https://www.youtube.com/watch?v=esZLCuWs_2Y) to learn a bit more about how black works and why it is a good tool to use.
 
### Black in action
Before black formatting:
```python
def foo(
    bar: str,
    cas: int,
    foo: str
) -> str:
    return bar + str(cas) + foo
 
foo: Tuple[str, ...] = (
    'foo', 'bar',
    'cas',
    'foo',
    'baz'
)
```
After black formatting:
```python
def foo(bar: str, cas: int, foo: str) -> str:
    return bar + str(cas) + foo
 
 
foo: Tuple[str, ...] = ('foo', 'bar', 'cas', 'foo', 'baz')
```
 
## Documentation
When writing documentation, it's important to follow a consistent style. This is a good way to have many developers work on a project, and write code that
each of them can understand and build upon.
 
In our projects, we use [`Sphinx`](https://www.sphinx-doc.org/), more specifically [Sphinx Autodoc](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html), to generate documentation. 
 
It's important that **all your code is documented**. Code with missing documentation will be rejected until it has been documented.
 
### Writing Sphinx Documentation
Writing Sphinx documentation is very easy to do once you get the hang of it. You can review [this Sphinx documentation sheet](https://pythonhosted.org/an_example_pypi_project/sphinx.html) for all of the items you can use to help
you write your documentation.
 
Let's review some examples on good and bad practices when writing documentation.
 
```python
def good():
    """This is a one liner of documentation"""
    ...
 
def bad():
    """
    This is a one liner of documentation
    """
    ...
```
```python
def good(bar: str) -> str:
    """This is the docstring main description. This will tell us
    what the function does and when it should be called. It should
    begin on the top line.
 
    Parameters
    ----------
    bar: :class:`str`
        This is the docstring description of the parameter.
        It will be shown in the help.
 
    Returns
    -------
    :class:`str`
        This is the docstring description of the return value.
        It will be shown in the help.
    """
    return bar
 
def bad(bar: str) -> str:
    """
    This is a docstring main description. This will tell us
    what the function does and when it should be called. It should
    begin on the top line.
 
    Parameters
    ----------
    bar: str
        This is the docstring description of the parameter.
        It will be shown in the help.
   
    Returns
    -------
    str
        This is the docstring description of the return value.
        It will be shown in the help.
    """
    ...
```
 
### Discord.py Command Documentation
When documenting commands, we create the documentation string a bit different
so it can be parsed easier for a help command. Instead of referencing code definitions, such as :class:\`Bar\`, 
we opt to just reference the name of the code, such as `Bar`. Although this is normally considered bad practice, it's acceptable
here due to how Discord's markdown system works.

Let's take a look at that in action
```python
@bot.command()
async def my_command(ctx: commands.Context[commands.Bot], arg: str, *, message: Optional[str] = None) -> None:
    """A command to show you some useful information!
   
    Parameters
    ----------
    arg: str
        The argument to pass into the command.
    message: Optional[str]
        An optional message to pass into the command.
 
    How to Use
    ----------
    `<prefix>my_command foo this is a message!`
    """
    ...
```
 
## Imports
All imports should be formatted via isort when a new file is created and when imports are updated.

```shell
isort .
```

