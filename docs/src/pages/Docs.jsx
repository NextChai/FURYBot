import React from 'react';
import { documentation } from '../constants';

function generate_subheadsings(size, documentation) {
    if (size < 1) {
        size = 1;
    }

    return (
        <div>
            {
                documentation.map((item) => (
                    <div className="py-4">
                        <p className={`font-poppins text-white text-${size}xl font-semibold`}>
                            {item.title}
                        </p>

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
                ))
            }
        </div>
    )
}


const Docs = () => {
    return (
        <div className="flex divide-x-2 divide-gray-light">
            
            <div className="w-80">
                { /* 
                    Desktop selection menu for the items. This *bar* can only go two items
                    deep. This means headings and subheadings but no subsubheadings. 
                */}
                {
                    documentation.map((item) => (
                        <div>
                            <p className="font-poppins text-white text-md pl-5 pt-5 pb-4">
                                {item.title}
                            </p>

                            <ul className="list-disc text-slate-300 px-[4rem]">
                                {
                                    item['subheadings'] == null ? null : (
                                        item.subheadings.map((subheading, index) => (
                                            <li key={index}>
                                                {subheading.title}
                                            </li>
                                        ))
                                    )
                                }
                            </ul>
                        </div>
                    ))
                }
            </div>

            <div className="w-full pl-8">
                {
                    documentation.map((item) => (
                        <div className="py-3">
                            <p className="text-fury font-poppins text-4xl font-bold">
                                {item.title}
                            </p>

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
                    ))
                }
            </div>
        </div>
    )
}

export default Docs