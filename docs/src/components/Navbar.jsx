import { fb_logo, menu, close, } from '../assets';
import { navLinks } from "../constants";

import { useState, } from 'react';
import { Link } from 'react-router-dom';


const Navbar = () => {
    const [toggle, setToggle] = useState(false);

    return (
        <div>
            <nav className="w-full flex py-6 justify-between items-center navbar ">
                {/* FuryBot Logo */}
                <div className="pl-5">
                    <img src={fb_logo} alt="Fury-Bot Logo" className="sm:w-[50px] sm:h-[50px] w-[40px] h-[40px] rounded-full drop-shadow-lg" />
                </div>

                {/* Navigation buttons for desktop (hidden for mobile) */}
                <ul className="list-none sm:flex hidden justify-end items-center flex-1 space-x-5 pr-5" >
                    <li className="font-poppins font-normal cursor-pointer text-[16px] text-white-medium rounded-md bg-discord-gray shadow-lg">
                        {/* Links to the documentation */}
                        <Link to="/docs" className="px-4 py-3 flex space-x-2">Docs</Link>

                    </li>


                    {navLinks.map((nav, _index) => (
                        <li
                            key={nav.id}
                            className="font-poppins font-normal cursor-pointer text-[16px] text-white-medium rounded-md bg-discord-gray shadow-lg"
                        >
                            <button className="px-4 py-3 flex space-x-2">
                                <a href={`${nav.url}`}>{nav.title}</a>
                                {
                                    nav.icon && <img src={nav.icon} className="w-[25px] h-[25px]" />
                                }
                            </button>
                        </li>
                    ))}
                </ul>

                {/* Button to toggle the navbar that pops up */}
                <div className="sm:hidden items-center">
                    <div className="px-5">
                        <img
                            src={toggle ? close : menu}
                            alt="menu"
                            className={`w-[28px] h-[28px]`}
                            onClick={() => setToggle(!toggle)}
                        />
                    </div>
                </div>
            </nav>
            
            { /* The navigation bar that pops up when the menu button is clicked (only available for mobile) */ }
            <div className={`sm:hidden ${toggle ? "block" : "hidden"} flex justify-center items-center bg-gray-medium`}>
                {
                    navLinks.map((nav, _index) => (
                        <div className='font-poppins font-normal cursor-pointer text-md text-white-medium py-2'>
                            <a href={`${nav.url}`} className="px-2 text-center">{nav.title}</a>
                        </div>
                    ))
                }

                <div className="font-poppins font-normal cursor-pointer text-md text-white-medium py-2">
                    <Link to="/docs" className="px-4 py-3 flex space-x-2">Docs</Link>
                </div>
            </div>
        </div>
        
    )   
}

export default Navbar