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
    
    async def get_data(self, message: str, *, want_bool: bool = True, want_censor: bool = False, want_packet: bool = False) -> Union[bool, str, Tuple[bool, str]]:
        await self.event.wait()
        
        placeholder = message
        has_failed = False
        cleaned = message.replace(' ', '')
        temp = ''
        
        for tries in range(len(cleaned)):
            for char in cleaned:
                temp += char
                if temp in self.swears:
                    if want_bool:
                        return True
                    elif want_censor or want_packet:
                        placeholder = placeholder.replace(temp, '*'*len(temp))
                        has_failed = True
                    
            temp = ''
            cleaned = cleaned[1:]
            
        if want_bool:
            return False
        if want_censor:
            return placeholder
        
        # want packet
        return has_failed, placeholder
    
    async def contains_profanity(self, message: str) -> bool:
        return await self.get_data(message, want_bool=True) # type: ignore

    async def censor(self, message: str) -> bool:
        return await self.get_data(message, want_censor=True, want_bool=False) # type: ignore
    
    async def contains_and_censor(self, message: str) -> Tuple[bool, str]:
        return await self.get_data(message, want_packet=True, want_bool=False) # type: ignore
    