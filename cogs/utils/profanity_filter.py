from typing import Callable, ClassVar, Dict, Iterable, List, Literal
import aiofile
import re

from profanityfilter import ProfanityFilter
 
from cogs.utils.errors import ProfanityFailure

class PermeateProfanity:
    mapping: ClassVar[Dict[str, List[str]]] = {
        'a': ['@'],
        'i': ['!', 'l', '1'],
        'd': ['b'],
        't': ['7'],
        'o': ['0'],
        's': ['$'],
        'y': ['i', 'ie']
    }  
    
    def __init__(self, *, swears: Iterable[str]):
        self._swears: List[str] = list(swears)
        
    def __await__(self):
        return self.permeate_swears().__await__()
        
    async def permeate_swears(self) -> List[str]:
        """Used to fill up all possible combinations of a swear word.
        
        .. note::
            
            `soysauce` would turn into: 'soysauce', '$oysauce', '$0ysauce', '$0isauce', etc."""
        for swear in self._swears:
            if swear.endswith('er'):
                self._swears.append(swear.replace('er', 'a')) # type: ignore
                
            for index, char in enumerate(swear):
                current = self.mapping.get(char.lower())
                if not current:
                    continue
                
                for switch in current:
                    formatted = swear[0:index] + switch + swear[index+1:]
                    self._swears.append(formatted) # type: ignore
                break 
        return self._swears
            
class CustomProfanity(ProfanityFilter):
    """The base profanity filter for the bot.
    
    .. note::
    
        :meth:`CustomProfanity.get_profane_words` is overwritten so a whitelist can be used.
        
    Attributes
    ----------
    clean_wordset: List[:class:`str`]
        The clean wordset of the bot, aka the whitelisted words.
    extra_profanity: List[:class:`str`]
        The bad words of the bot, aka the words that will get flagged.
    """
    def __init__(self) -> None:
        super().__init__() 
        self.invalid_regex = (
            '.',
            '^',
            '$',
            '.'
        )
        
    async def _split_filename_lines(self, filename: str) -> List[str]:
        """Used to async-open a file, decode its content, and split it by a new line.
        
        Parameters
        ----------
        filename: :class:`str`
            The filename to open and parse.
        
        Returns
        -------
        List[:class:`str`]
        """
        async with aiofile.async_open(filename, 'rb') as f:
            data = (await f.read()).decode('utf-8').split('\n')
            return [i for n, i in enumerate(data) if i not in data[:n]]

    async def load_dirty_words(self) -> None:
        """Loads the dirty words from our custom wordset and adds it to the profanity filter.
        
        Returns
        -------
        None
        """
        data = await self._split_filename_lines('txt/profanity.txt')
        swears = await PermeateProfanity(swears=data)
        
        self.append_words(swears)
            
    async def load_clean_words(self) -> None:
        """Loads the clean words mistaken for bad words and removes them from the profanity filter.
        
        Returns
        -------
        None
        """
        data = await self._split_filename_lines('txt/clean.txt')
        self.clean_wordset = data
        
    async def reload_words(self, wrapper: Callable) -> None:
        """Used to reload all clean and dirty words to the bot.
        
        Parameters
        ----------
        wrapper: Callable
            A wrapper that uses `loop.run_in_executr` to make non-async code async.
        
        Returns
        -------
        None
        """
        await wrapper(self.restore_words)
        await self.load_dirty_words()
        await self.load_clean_words()
            
    async def get_profane_words(self) -> List[str]:
        """A workaround to adding a whitelist to FURY Bot.
        
        .. note::

            If the bot's custom profanity hasn't been loaded the default one
            will be returned.
        
        Returns
        -------
        None
        """
        words = super().get_profane_words()
        
        if not hasattr(self, 'clean_wordset'):
            return words

        clean = []
        for word in words:
            if word not in self.clean_wordset:
                for invalid in self.invalid_regex:
                    word = word.replace(invalid, r'\{0}'.format(invalid))
                    
                clean.append(word)
        
        return clean
    
    async def censor(self, input_text: str) -> str:
        """Censor a string by replacing bad words with the character `*`
        
        Parameters
        ----------
        input_text: :class:`str`
            The text to censor.
        
        Returns
        -------
        :class:`str`
            The censored text.
        """
        bad_words = await self.get_profane_words()
        res = input_text
        
        for word in bad_words:
            regex_string = re.compile(r'{0}'.format(word))
            res = regex_string.sub('*' * len(word), res)
        
        return res
    
    async def has_bad_word(self, text: str) -> bool:
        return (await self.censor(text)) != text
    
    async def add_word_to(self, filename: Literal['profanity', 'clean'], word: str, *, wrapper: Callable) -> None:
        """Add a word to the black and whitelists of the profanity filter.
        
        Parameters
        ----------
        filename: Literal[:class:`str`]
            The filename to add to. Can be either `profanity` or `clean`
        word: :class:`str`
            The word to add to the list
        wrapper: Callable
            An async wrapper we can use to make non-async code async.
            
        Returns
        -------
        None
        
        Raises
        ------
        :class:`ProfanityFailure`
            Raised if the word you are trying to add is already in the profanity wordset you're trying
            to add to.
        """
        data = await self._split_filename_lines(filename)
        if word in data:
            raise ProfanityFailure(f'word {word} is already in file {filename}')
        
        async with aiofile.async_open(f'txt/{filename}.txt', 'a') as f:
            await f.write(f'\n{word}')
        
        await self.reload_words(wrapper=wrapper)