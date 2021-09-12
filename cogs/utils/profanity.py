from typing import Any, ClassVar, Dict, Iterable, List, Set, Union
import asyncio

class Profanity:
    mapping: ClassVar[Dict[str, List[str]]] = {
        'a': ['@'],
        'i': ['!', 'l', '1'],
        'd': ['b'],
        't': ['7'],
        'o': ['0'],
        's': ['$']
    }  
    
    def __init__(self, *, swears: Iterable[Any], loop):
        self.swears: Union[List[Any], Set[Any]] = list(swears)
        self.loop = loop
        
        self.event = asyncio.Event()
        self.loop.create_task(self.permeate_swears())
        
    async def permeate_swears(self):
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
        self.swears = set(self.swears)
        self.event.set()
        
    def is_set(self) -> bool:
        return self.event.is_set()
    
    async def contains_profanity(self, message: str) -> bool:
        await self.event.wait()
        
        cleaned = message.replace(' ', '')
        temp = ''
        for tries in range(len(cleaned)):
            for char in cleaned:
                temp += char
                if temp in self.swears:
                    return True
            temp = ''
            cleaned = cleaned[1:]
        return False

            