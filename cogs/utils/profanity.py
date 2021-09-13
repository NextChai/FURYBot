from typing import Any, ClassVar, Dict, Iterable, List, Set, Union, Tuple
import asyncio

class Profanity:
    mapping: ClassVar[Dict[str, List[str]]] = {
        'a': ['@'],
        'i': ['!', 'l', '1'],
        'd': ['b'],
        't': ['7'],
        'o': ['0'],
        's': ['$'],
        'y': ['i', 'ie']
    }  
    
    def __init__(self, *, swears: Iterable[Any], loop):
        self.swears: Union[List[Any], Set[Any]] = list(swears)
        self.loop = loop
        
        self.event = asyncio.Event()
        self.permeate_swears()
        
    def permeate_swears(self):
        for swear in self.swears:
            if swear.endswith('er'):
                self.swears.append(swear.replace('er', 'a')) # type: ignore
                
            for index, char in enumerate(swear):
                current = self.mapping.get(char.lower())
                if not current:
                    continue
                
                for switch in current:
                    formatted = swear[0:index] + switch + swear[index+1:]
                    self.swears.append(formatted) # type: ignore
                break 
