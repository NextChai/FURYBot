import React from 'react';

import styles from "../style";
import { hero } from "../constants";

const Hero = () => {
    return (
        <div className='w-full'>
            {/* Holds the bot description and supporting image */}
            <div className={`${styles.flexCenter} ${styles.paddingY}`}>
                <div>
                    <h1 className="text-primary-text-light font-poppins font-semibold ss:text-[62px] text-[25px] hover:scale-105 sm:hover:scale-110 transition ease-in-out delay-150 duration-300 text-center pt-11 max-w-4xl text-shadow">
                        Time To See What Fury Bot Can Do To Your Server
                    </h1>
                </div>
            </div>

            {/* Holds supporting cards under the main caption. Hidden for mobile users. */}
            <div className={`w-full sm:flex hidden space-x-6 px-10 py-16`}>
                {
                    hero.map((item) => (
                        <div className="rounded-md drop-shadow-md hover:drop-shadow-xl py-5 bg-discord-gray">
                            <h1 className='font-poppins font-semibold text-lg text-center text-fury'>
                                {item.title}
                            </h1>

                            <p className="font-poppins text-white-dark text-center py-4 px-5">
                                {item.description}
                            </p>
                        </div>
                    ))
                }
            </div>
            
            {/* Holds supporting cards under the main caption. Visible for mobile users. */}
            <div className={`w-full sm:hidden px-5 py-6`}>
                {
                    hero.map((item, index) => (
                        <div className='rounded-md drop-shadow-sm hover:drop-shadow-md py-2'>
                            <h1 className='font-poppins font-semibold text-md text-center text-fury'>
                                {item.title}
                            </h1>

                            <p className="font-poppins text-white-dark text-center text-sm py-4 px-5">
                                {item.description}
                            </p>

                            {
                                index !== hero.length - 1 ? <hr className="border-white border-opacity-20" /> : null
                            }
                            
                        </div>
                    ))
                }
            </div>

        </div >
    )
}

export default Hero