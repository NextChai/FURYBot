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

import nltk
import io
from typing import TYPE_CHECKING, Dict, Literal, Optional, List, overload, Union

import discord
from discord import app_commands

from utils import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot


class Generator:
    """
    Generate random sentences from a corpus using Markov chains.

    with open(filename, 'r') as f:
        sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')
        sents = sent_detector.tokenize(f.read().strip())
        sent_tokens = [word_tokenize(sent.replace('\n', ' ').lower()) for sent in sents]
        generator = Generator(sent_tokens, args.chain_length)
        print(generator.generate())
    """

    # Ignore quotes in sentence generation.
    IGNORED = ['"', '\'']
    # Symbols that should not have space preceding it.
    NO_SPACE_BEFORE = [',', '.', '?', ':', ';', ')', '!', "n't", "''", "'t"]
    NO_SPACE_BEFORE_PREFIX = ['.', '\'']
    NO_SPACE_AFTER = ['(', '``']
    START = '<s>'
    END = '</s>'

    def __init__(self, sentences: List[str], chain_len: int = 2):
        """
        Creates a new sentence generator based on the given corpus.

        Args:
            sentences (list(list(string))): a list of tokenized senteces
            chain_len (int): max number of words to look back when generating a new
            sentence
        """
        self.lm: Dict[int, nltk.ConditionalProbDist] = {}  # stores the language model
        self.chain_len = chain_len
        words = self._delimit_sentences(sentences)

        self.lm[1] = self._bigram_mle_model(words)
        for i in range(2, chain_len + 1):
            self.lm[i] = self._ngram_mle_model(words, i + 1)

    @staticmethod
    def _bigram_mle_model(words: List[str]) -> nltk.ConditionalProbDist:
        cfdist = nltk.ConditionalFreqDist(nltk.bigrams(words))  # type: ignore
        return nltk.ConditionalProbDist(cfdist, nltk.MLEProbDist)

    @staticmethod
    def _ngram_mle_model(words: List[str], n: int):
        ngrams = nltk.ngrams(words, n)  # type: ignore
        cfdist = nltk.ConditionalFreqDist((tuple(x[: (n - 1)]), x[n - 1]) for x in ngrams)
        return nltk.ConditionalProbDist(cfdist, nltk.MLEProbDist)

    @staticmethod
    def _delimit_sentences(sents: List[str]):
        """
        Given a list of sentences returns a list of tokens that delimits where
        sentences start and end with <s> and </s>.

        Args:
            sentences (list(list(string))): a list of tokenized senteces
        """
        result: List[str] = []
        for sent in sents:
            result.append(Generator.START)
            result.extend([word for word in sent if word not in Generator.IGNORED])
            result.append(Generator.END)
        return result

    @staticmethod
    def stitch(sentence: List[str]):
        """
        Stitch sentence parts together with proper spacing. For example, for
        punctuations, contractions etc.
        """
        result: List[str] = []
        buf = ""
        for word in sentence:
            if word in Generator.NO_SPACE_AFTER:
                buf += word
            elif word in Generator.NO_SPACE_BEFORE or word[0] in Generator.NO_SPACE_BEFORE_PREFIX:
                if len(result) == 0:
                    result.append(buf + word)
                else:
                    result[-1] += buf + word
                buf = ""
            else:
                result.append(buf + word)
                buf = ""
        return " ".join(result)

    @overload
    def generate(self, as_list: Literal[True]) -> List[str]: ...

    @overload
    def generate(self, as_list: Literal[False]) -> str: ...

    def generate(self, as_list: bool = False) -> Union[List[str], str]:
        """
        Generates a random sentence.

        Args:
            as_list (bool): Returns a list of tokens if True, otherwise returns a
            single string.
        """
        # Generate words until we reach end of sentence
        sentence: List[str] = []
        context: List[str] = [Generator.START]
        while context[-1] != Generator.END:
            # Special case for bigrams
            if len(context) == 1:
                cur: str = self.lm[1][context[0]].generate()  # type: ignore
                context.append(cur)  # type: ignore
            else:
                cur: str = self.lm[len(context)][tuple(context)].generate()  # type: ignore
                context.append(cur)  # type: ignore
                if len(context) >= self.chain_len:
                    context.pop(0)

            if cur != Generator.END:
                sentence.append(cur)  # type: ignore

        if as_list:
            return sentence
        else:
            return self.stitch(sentence)


class Fun(BaseCog):
    @app_commands.command(name='avatar', description='Get the avatar of a user.')
    @app_commands.describe(member='The member to get the avatar of.')
    async def avatar(
        self, interaction: discord.Interaction[FuryBot], member: Optional[discord.Member] = None
    ) -> discord.InteractionMessage:
        """|coro|

        Gets the avatar of a user.

        Parameters
        ----------
        member: Optional[:class:`discord.Member`]
            The member to get the avatar of. Defaults to the author.
        """
        await interaction.response.defer()
        target = member or interaction.user

        avatar = await target.display_avatar.read()

        filename = f'{target.display_name}_avatar.png'
        file = discord.File(
            fp=io.BytesIO(avatar),
            filename=f'{target.display_name}_avatar.png',
            description=f'Avatar of {target.display_name}',
        )

        embed = self.bot.Embed(title=f'{target.display_name} Avatar')
        embed.set_image(url=f'attachment://{filename}')
        return await interaction.edit_original_response(embed=embed, attachments=[file])


async def setup(bot: FuryBot) -> None:
    """|coro|

    The setup function for the cog.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    """
    await bot.add_cog(Fun(bot))
