import { fb_logo, github_logo } from '../assets';
import { githubNavLinks } from "../constants";


const Navbar = () => {
    return (
        <div className="w-full flex py-6 justify-between items-center navbar">
            {/* FuryBot Logo */}
            <div className="pl-5">
                <img src={fb_logo} alt="Fury-Bot Logo" className="w-[50px] h-[50px] rounded-full drop-shadow-lg" />
            </div>

            {/* Navigation Links for desktop (hidden for mobile) */}
            <ul className="list-none sm:flex hidden justify-end items-center flex-1 space-x-5" >
                {githubNavLinks.map((nav, _index) => (
                    <li
                        key={nav.id}
                        className="font-poppins font-normal cursor-pointer text-[16px] text-neutral-500 rounded-md drop-shadow-md bg-neutral-100"
                    >
                        <div className="px-4 py-3 flex space-x-2">
                            <a href={`${nav.url}`}>{nav.title}</a>
                            <img src={github_logo} className="w-[25px] h-[25px]" />
                        </div>
                    </li>
                ))}
            </ul>

            {/* Navigation Links for mobile (hidden for desktop) */}
            

        </div>
    )
}

export default Navbar