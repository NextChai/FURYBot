import React from 'react';

import { link } from '../assets';

function DocumentationSelectionEntry(item) {
    return (
        <div>
            <p className="font-poppins text-white text-md pl-10 pt-5 pb-2 hover:scale-105 transition ease-in-out delay-50 duration-50">
                <a href={`#${item.id}`}>{item.title}</a>
            </p>

            <ul className="list-disc text-slate-300 px-[5rem] hover:scale-105 transition ease-in-out delay-50 duration-50">
                {
                    item['subheadings'] == null ? null : (
                        item.subheadings.map((subheading, index) => (
                            <li key={index}>
                                <a href={`#${subheading.id}`}>{subheading.title}</a>
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

                <a href={`#${item.id}`}>
                    <img src={link} className="w-[10px] h-[10px]" />
                </a>
            </div>

            {
                item["description"] == null ? null : (
                    item.description.split("\n").map((line) => (
                        <p className="text-slate-300 font-poppins text-md py-4 max-w-[70%]">
                            {line}
                        </p>
                    ))
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

                <a href={`#${item.id}`}>
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