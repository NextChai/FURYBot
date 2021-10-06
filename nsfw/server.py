import os
import random
from typing import Literal, Union, Dict, Any

import uvicorn
import aiohttp
import aiofile
import fastapi

import predict

app = fastapi.FastAPI()
session = aiohttp.ClientSession()

MAX_IMAGE_SIZE = 25 * 1000000 # 25 mb
model = predict.load_model('./nsfw/nsfw_model.h5')

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