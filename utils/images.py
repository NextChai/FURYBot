"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to
non-commercial purposes. Distribution, sublicensing, and sharing of this file
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not
misrepresent the original material. This license does not grant any
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import asyncio
import io
import math
from typing import TYPE_CHECKING, Callable, List, Optional, Sequence, Tuple, Union

import discord
import numpy
from PIL import Image
from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = (
    'async_merge_images',
    'flatten_image_to_fixed_width',
    'image_from_urls',
    'image_to_file',
    'ImageType',
)

ImageType: TypeAlias = Image.Image


def _normalize_images(data: Sequence[bytes]) -> Sequence[bytes]:
    images = [Image.open(io.BytesIO(image)) for image in data]

    # The goal is to crop all the images to be squares so they neatly fit into the image array.
    # This means that any image in the list of images can be N x Z, where N is the width and Z is the height.
    # All images will not have the same height or width, so we need to dynamically crop them to be squares.

    # First we'll make every image a square by cropping the image to the smallest dimension.
    # We'll crop it *from the middle* though as to not lose any information.
    cropped_images: List[ImageType] = []
    for image in images:
        smallest_dimension = min(image.width, image.height)
        middle = smallest_dimension // 2

        # Using the Cartesian pixel coordinate system, we can calculate the coordinates of the crop
        # so that the middle of the image is the middle of the square.
        left = image.width // 2 - middle
        upper = image.height // 2 - middle
        right = image.width // 2 + middle
        lower = image.height // 2 + middle

        cropped_images.append(image.crop((left, upper, right, lower)))

    # Now we can resize all the images to be the same size.
    # We'll resize every image to be the same size as the largest image.
    largest_image = max(cropped_images, key=lambda image: image.width)
    largest_image_width = largest_image.width
    largest_image_height = largest_image.height

    image_data: List[bytes] = []
    for image in cropped_images:
        resized = image.resize((largest_image_width, largest_image_height))

        buf = io.BytesIO()
        resized.save(buf, 'PNG')
        buf.seek(0)
        image_data.append(buf.getvalue())

    return image_data


def sync_merge_images(
    data: Sequence[bytes],
    *,
    images_per_row: int = 20,
    frame_width: int = 1920,
    background_color: Union[int, Tuple[int, int, int], str] = (0, 0, 0),
    normalize_images: bool = False,
    image_alteration: Optional[Callable[[ImageType], ImageType]] = None,
) -> ImageType:
    """Used to generate an image array based upon the given parameters.

    Parameters
    ----------
    data: Sequence[:class:`bytes`]
        A sequence of bytes to generate the image array from.
    images_per_row: :class:`int`
        The number of images to put on each row.
    frame_width: :class:`int`
        The width of the frame to generate.
    background_color: Union[:class:`int`, Tuple[:class:`int`, :class:`int`, :class:`int`], :class:`str`]
        A color to fill the frame with. Can be an integer, a tuple of integers, or a hex string.

    Returns
    -------
    Tuple[ImageType, List[Callable]]
        A tuple of image type with pasters to be called to paste onto the image.
    """
    if normalize_images:
        data = _normalize_images(data)

    total_images = len(data)
    total_rows = math.ceil(total_images / images_per_row)
    theoretiacal_images = total_rows * images_per_row

    missing_images = theoretiacal_images - total_images

    new_arr = numpy.array(data, dtype=object)
    if missing_images > 0:
        new_arr = numpy.append(new_arr, [None] * missing_images)  # pyright: ignore # This is not something we can control

    new_arr = new_arr.reshape((total_rows, images_per_row))

    # Let's use the frame width that is given to calculate the suspected size of each image
    # This number is going to a scale factor that we should multiply the image's height and width
    # by to get the final size of each image.
    original_image_width, original_image_height = Image.open(io.BytesIO(data[0])).size

    # These are the expected dimensions of the frame based upon the original data given to us.
    # Let's use this to create a scale factor
    original_frame_width = images_per_row * original_image_width
    original_frame_height = original_image_height * total_rows

    factor = frame_width / original_frame_width

    # Now we can use this factor to calculat the new dimensions of each image
    new_frame_width = int(original_frame_width * factor)
    new_frame_height = int(original_frame_height * factor)

    # Now we can also use this factor to update the imaghe width and height
    image_width = math.ceil(original_image_width * factor)
    image_height = math.ceil(original_image_height * factor)

    merged = Image.new('RGBA', (new_frame_width, new_frame_height), background_color)

    # Now we cam use this to build our image
    for y_coordinate, row in enumerate(new_arr):
        for x_coordinate, image_bytes in enumerate(row):
            if image_bytes is None:
                continue

            image = Image.open(io.BytesIO(image_bytes)).resize((image_width, image_height))
            if image_alteration:
                image = image_alteration(image)

            # Let's get the dimensions
            y_pixel_coordinate = int(y_coordinate * image_height)
            x_pixel_coordinate = int(x_coordinate * image_width)

            merged.paste(image, (x_pixel_coordinate, y_pixel_coordinate))

    return merged


async def async_merge_images(
    bot: FuryBot,
    data: Sequence[bytes],
    *,
    images_per_row: int = 20,
    half_size: bool = False,
    frame_width: int = 1920,
    background_color: Union[int, Tuple[int, int, int], str] = (0, 0, 0),
    normalize_images: bool = False,
    image_alteration: Optional[Callable[[ImageType], ImageType]] = None,
) -> ImageType:
    """|coro|

    A coroutine to merge many images into a single image based upon the parameters given.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance to use to wrap blocking functions.
    data: Sequence[:class:`bytes`]
        A sequence of bytes to generate the image array from.
    images_per_row: :class:`int`
        The number of images to put on each row.
    half_size: :class:`bool`
        Whether or not to scale down the image by 1/2. Can be useful when uploading to discord.
    frame_width: :class:`int`
        The width of the frame to generate.
    background_color: Union[:class:`int`, Tuple[:class:`int`, :class:`int`, :class:`int`], :class:`str`]
        A color to fill the frame with. Can be an integer, a tuple of integers, or a hex string.

    Returns
    -------
    ImageType
        The merged image.
    """
    merged = await bot.wrap(
        sync_merge_images,
        data,
        images_per_row=images_per_row,
        frame_width=frame_width,
        background_color=background_color,
        normalize_images=normalize_images,
        image_alteration=image_alteration,
    )

    if half_size:
        merged = merged.resize((int(merged.width / 2), int(merged.height / 2)))

    return merged


def _sync_flatten_image_to_fixed_width(image_bytes: bytes, frame_width: int = 1920, frame_height: int = 1080) -> ImageType:
    existing_image = Image.open(io.BytesIO(image_bytes))

    # Let's reformat this image to fit the frame height (width does not matter)
    ratio = frame_height / existing_image.height
    new_image = existing_image.resize((frame_height, int(existing_image.height * ratio)))

    new = Image.new('RGBA', (frame_width, frame_height))

    # Now let's pasge the new image onto the middle of the frame
    new_middle = new.width // 2
    paste_x = new_middle - new_image.width // 2

    new.paste(new_image, (paste_x, 0))
    return new


async def flatten_image_to_fixed_width(
    bot: FuryBot, url: str, *, frame_width: int = 1920, frame_height: int = 1080
) -> ImageType:
    async with bot.session.get(url) as data:
        image_bytes = await data.read()

    return await bot.wrap(
        _sync_flatten_image_to_fixed_width, image_bytes, frame_width=frame_width, frame_height=frame_height
    )


async def image_from_urls(
    bot: FuryBot,
    urls: List[str],
    *,
    images_per_row: int = 20,
    frame_width: int = 1920,
    background_color: Union[int, Tuple[int, int, int], str] = (0, 0, 0),
    normalize_images: bool = False,
    image_alteration: Optional[Callable[[ImageType], ImageType]] = None,
) -> ImageType:
    """|coro|

    Similar to :func:`async_merge_images` but instead of taking a list of bytes, it takes a list of urls
    and will download them for you. To view all the other paramters, see :func:`async_merge_images`.

    Parameters
    ----------
    urls: List[:class:`str`]
        A list of urls to download and merge.
    """

    async def _download_image(url: str) -> bytes:
        async with bot.session.get(url) as response:
            return await response.read()

    data = await asyncio.gather(*(_download_image(url) for url in urls))
    return await async_merge_images(
        bot,
        data,
        images_per_row=images_per_row,
        frame_width=frame_width,
        background_color=background_color,
        normalize_images=normalize_images,
        image_alteration=image_alteration,
    )


def image_to_file(
    image: ImageType, *, filename: Optional[str] = None, description: Optional[str] = None, spoiler: bool = False
) -> discord.File:
    """Converts an image type into a discord.File object.

    Parameters
    ----------
    image: :class:`ImageType`
        The image to convert.
    filename: Optional[:class:`str`]
        The filename to use for the file.
    description: Optional[:class:`str`]
        The description to use for the file.
    spoiler: :class:`bool`
        Whether or not to mark the file as spoiler.
    """
    buff = io.BytesIO()
    image.save(buff, format='PNG')
    buff.seek(0)
    return discord.File(buff, filename, spoiler=spoiler, description=description)
