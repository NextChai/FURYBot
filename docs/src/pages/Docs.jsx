import React from 'react';
import { documentation } from '../constants';
import { DocumentationSelectionEntry, DocumentationEntry } from '../components';


const Docs = () => {
    return (
        <div className="flex flex-wrap items-stretch divide-x-2 divide-gray-light">

            <div className="w-80 pb-7">

                { /* 
                    Desktop selection menu for the items. This *bar* can only go two items
                    deep. This means headings and subheadings but no subsubheadings. 
                */}
                {
                    documentation.map((item) => DocumentationSelectionEntry(item))
                }
                
            </div>
            

            <div className="w-full flex-1 pl-8">
                {
                    documentation.map((item) => DocumentationEntry(item))
                }
            </div>
        </div>
    )
}

export default Docs