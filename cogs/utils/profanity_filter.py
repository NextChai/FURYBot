from typing import Callable, ClassVar, Dict, Iterable, List, Literal
import aiofile

from profanityfilter import ProfanityFilter

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

    async def load_dirty_words(self) -> None:
        """Loads the dirty words from our custom wordset and adds it to the profanity filter.
        
        Returns
        -------
        None
        """
        async with aiofile.async_open('txt/profanity.txt', 'r') as f:
            data = (await f.read()).split('\n')
            
        cleaned = [i for n, i in enumerate(data) if i not in data[:n]]  # Clean duplicates
        swears = await PermeateProfanity(swears=cleaned)
        self.append_words(swears)
            
    async def load_clean_words(self) -> None:
        """Loads the clean words mistaken for bad words and removes them from the profanity filter.
        
        Returns
        -------
        None
        """
        async with aiofile.async_open('txt/clean.txt', 'r') as f:
            data = await f.read()
            
        self.clean_wordset = data.split('\n')
        
    async def reload_words(self, wrapper: Callable) -> None:
        await wrapper(self.restore_words)
        await self.load_dirty_words()
        await self.load_clean_words()
            
    def get_profane_words(self) -> List[str]:
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
                clean.append(word)
        
        return clean
    
    async def add_word_to(self, filename: Literal['profanity', 'clean'], word: str, *, wrapper: Callable) -> None:
        async with aiofile.async_open(f'txt/{filename}.txt', 'a') as f:
            await f.write(f'\n{word}')
        
        await self.reload_words(wrapper=wrapper)
    