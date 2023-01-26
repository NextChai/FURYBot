import { fb_logo } from '../assets';
import { navLinks } from "../constants";


const Navbar = () => {
    return (
        <div className="w-full flex py-6 justify-between items-center navbar">
            {/* FuryBot Logo */}
            <div className="pl-5">
                <img src={fb_logo} alt="Fury-Bot Logo" className="w-[50px] h-[50px] rounded-full" />
            </div>

            {/* Navigation Links for desktop (hidden for mobile) */}
            <ul className="list-none sm:flex hidden justify-end items-center flex-1">
                {navLinks.map((nav, index) => (

                    /* We use setActive an active for a little effect when clicking a link */
                    <li
                        key={nav.id}
                        className="font-poppins font-normal cursor-pointer text-[16px] text-neutral-500 rounded-md drop-shadow-md bg-neutral-100"
                    >
                        <div className="px-4 py-3">
                            <a href={`${nav.url}`}>{nav.title}</a>
                        </div>

                    </li>
                ))}
            </ul>

        </div>
    )
}

export default Navbar