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

import os
import random
from typing import Union, Dict, Any
from typing_extensions import Literal

import uvicorn
import aiohttp
import aiofile
import fastapi

import predict

app = fastapi.FastAPI()
session = aiohttp.ClientSession()

MAX_IMAGE_SIZE = 25 * 1000000 # 25 mb
model = predict.load_model('./nsfw_model.h5')

async def download_image(url: str) -> Union[str, Literal[False]]:
    filename = f'{random.randint(6969, 6999)}.jpg'
    
    async with session.get(url) as resp:
        if resp.status != 200 or int(resp.headers['Content-Length']) > MAX_IMAGE_SIZE:
            return False
        
        async with aiofile.async_open(filename, mode='wb') as f:
            await f.write(await resp.read())
    
    return filename

@app.get('/')
async def nsfw(url: str) -> Dict[str, Any]:
    if url is None:
        return {'error': 'No url specified'}
    
    image = await download_image(url)
    if not image:
        return {'error': 'Image size too large or invalid url specified.'}
    
    results = predict.classify(model, image)  # Classify needs to look at a local file.
    os.remove(image)
    
    hentai = results['data']['hentai']
    sexy = results['data']['sexy']
    porn = results['data']['porn']
    drawings = results['data']['drawings']
    neutral = results['data']['neutral']
    if neutral >= 25 or drawings >= 40:
        results['data']['is_nsfw'] = False
    elif (sexy + porn + hentai) >= 70:
        results['data']['is_nsfw'] = True
    else:
        results['data']['is_nsfw'] = False
    
    return results

if __name__ == '__main__':
    uvicorn.run("server:app", host="localhost", port=8000, log_level="info")