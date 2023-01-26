import React from 'react';

import { mobile_interface } from '../assets';
import styles from "../style";

const Hero = () => {
    return (
        <div className='w-full'>
            {/* Holds the bot description and supporting image */}
            <div className={`${styles.flexCenter} ${styles.flexStart} ${styles.paddingY}`}>
                <div>
                    <h1 className="text-light-text dark:text-dark-text font-poppins font-semibold ss:text-[62px] text-[52px] ss:leading-[100.8px] leading-[75px] px-[200px] text-center pt-11">
                        Time To See What Fury Bot Can Do To Your Server.
                    </h1>
                </div>

                <div>
                    <img src={mobile_interface} alt="mobile interface" />
                </div>

                <div>
                </div>

            </div>
        </div>
    )
}

export default Hero