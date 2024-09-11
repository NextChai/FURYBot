""" 
The MIT License (MIT)

Copyright (c) 2020-present NextChai

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union
from typing_extensions import Unpack, Self

import discord
from discord import app_commands

from utils import BaseView, BaseViewKwargs, ChannelSelect, RoleSelect, ConfirmationGetter

if TYPE_CHECKING:
    from bot import FuryBot
    from .settings import InfractionsSettings


class InfractionsSettingsPanel(BaseView):
    def __init__(self, settings: InfractionsSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: InfractionsSettings = settings
