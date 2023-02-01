import React from 'react';

import { link } from '../assets';

const IMAGE_REGEX = /(\{image[\S]+\})/g;

/// This function will parse the given split descroption line and format it to be displayed
/// with any images that may be in the description.
function parse_description_doc(line, item) {
    // Match the description first to see if there's any images
    const matches = line.match(IMAGE_REGEX);
    if (!matches) {
        // There are no images, so just return the description
        return (
            <p className="text-slate-300 font-poppins text-md py-4 max-w-[70%]">
                {line}
            </p>
        )
    }

    // There are images, so we need to split the description  into parts by the images
    let split = line.split(IMAGE_REGEX);
    console.log(split);

    return <div>
        {
            split.map((split_item) => {
                console.log(split_item);
                console.log(typeof split_item);
                if (split_item.length == 0) {
                    // Sometimes we can get empty strings, so we just skip them
                    return null;
                }

                // If this is an image, we need to get the image from the item and display it
                if (split_item.startsWith("{image")) {
                    // Chop the "{" and "}" off the beginning and end of the string
                    let image_name = split_item.substring(1, split_item.length - 1);
                    let image = item[image_name];

                    return <img src={image} className="max-w-md h-auto" />
                }

                // This isn't an image, so we can display the text as normal.
                return (
                    <p className="text-slate-300 font-poppins text-md py-4 max-w-[70%]">
                        {split_item}
                    </p>
                )
            })
        }
    </div>
}

function DocumentationSelectionEntry(item) {
    return (
        <div>
            <p className="font-poppins text-white text-md pl-10 pt-5 pb-2 hover:scale-105 transition ease-in-out delay-50 duration-50">
                <a href={`#/docs/#${item.id}`}>{item.title}</a>
            </p>

            <ul className="list-disc text-slate-300 px-[5rem] hover:scale-105 transition ease-in-out delay-50 duration-50">
                {
                    item['subheadings'] == null ? null : (
                        item.subheadings.map((subheading, index) => (
                            <li key={index}>
                                <a href={`#/docs/#${subheading.id}`}>{subheading.title}</a>
                            </li>
                        ))
                    )
                }
            </ul>
        </div>
    )
}

function generate_subheadsings(size, documentation) {
    if (size < 1) {
        size = 1;
    }

    return (
        <div>
            {
                documentation.map((item) => DocumentationEntrySubheading(size, item))
            }
        </div>
    )
}

function DocumentationEntrySubheading(size, item) {
    return (
        <div className="py-4">

            <div className="flex space-x-2">
                <p className={`font-poppins text-white text-${size}xl font-semibold`} id={item.id}>
                    {item.title}
                </p>

                <a href={`#/docs/#${item.id}`}>
                    <img src={link} className="w-[10px] h-[10px]" />
                </a>
            </div>

            {
                item["description"] == null ? null : (
                    item.description.split("\n").map((line) => parse_description_doc(line, item))
                )
            }

            {
                item['subheadings'] == null ? null : generate_subheadsings(size - 1, item.subheadings)
            }

        </div>
    )
}


function DocumentationEntry(item) {
    return (
        <div className="py-3">
            {/* 
                The headings are built individually, and all subheadings are created using 
                recursion.
            */}

            <div className="flex space-x-2">
                <p className="text-fury font-poppins text-4xl font-bold" id={item.id}>
                    {item.title}
                </p>

                <a href={`#/docs/#${item.id}`}>
                    <img src={link} className="w-[15px] h-[15px]" />
                </a>
            </div>

            {
                item["description"] == null ? null : (
                    <p className="text-slate-300 font-poppins max-w-[70%] text-md px-1 py-2">
                        {item.description}
                    </p>
                )
            }

            {
                item['subheadings'] == null ? null : generate_subheadsings(3, item.subheadings)
            }
        </div>
    )
}

export {
    DocumentationSelectionEntry,
    DocumentationEntry
}