import React from 'react';

import styles from "../style";

const Hero = () => {
    return (
        <div className='w-full'>
            {/* Holds the bot description and supporting image */}
            <div className={`${styles.flexCenter} ${styles.paddingY}`}>
                <div>
                    <h1 className="text-primary-text-light font-poppins font-semibold ss:text-[62px] text-[32px] hover:scale-110 transition ease-in-out delay-150 duration-300 text-center pt-11 max-w-4xl text-shadow">
                        Time To See What Fury Bot Can Do To Your Server
                    </h1>
                </div>
            </div>

            {/* Holds supporting cards under the main caption. */}
            <div className={`w-full flex flex-wrap md:flex-nowrap space-x-6 ${styles.paddingX} ${styles.paddingY}`}>
                <div className="flex-auto rounded-md drop-shadow-md hover:drop-shadow-xl py-5 bg-discord-gray">
                    <h1 className='font-poppins font-semibold text-lg text-center text-fury'>
                        School Discord Server Management
                    </h1>

                    <p className="font-poppins text-white-dark text-center py-4 px-5">
                    The Fury Bot is a Discord-based software tool designed to facilitate the management of your e-sports Discord server. 
                    Our extensive experience in the e-sports industry has enabled us to create a bot that provides all the necessary features 
                    to maintain a safe, enjoyable, and age-appropriate Discord server.
                    </p>
                </div>

                <div className="flex-auto rounded-md drop-shadow-md hover:drop-shadow-xl shadow-lg py-5 bg-discord-gray">
                    <h1 className='font-poppins font-semibold text-lg text-center text-fury'>
                        Team Managament
                    </h1>

                    <p className="font-poppins text-white-dark text-center py-4 px-5">
                    The Fury Bot is equipped with a comprehensive team management system out of the box. 
                    This system enables you to create teams, add players, oversee rosters, disseminate announcements to teams, 
                    and perform various other tasks. Further information about this system can be found in the Team Documentation.
                    </p>
                </div>

                <div className="flex-auto rounded-md drop-shadow-md hover:drop-shadow-xl shadow-lg py-5 bg-discord-gray">
                    <h1 className='font-poppins font-semibold text-lg text-center text-fury'>
                        Member Moderation
                    </h1>

                    <p className="font-poppins text-white-dark text-center py-4 px-5">
                    The key aspect of managing a Discord server that is appropriate for a school environment is the ability to regulate 
                    your members. This involves eliminating inappropriate language and monitoring for signs of bullying, harassment, 
                    and other undesirable behaviors. The Fury Bot is equipped to assist you in these efforts. It comes with a complete 
                    suite of tools to aid in the management of your members.
                    </p>
                </div>

            </div>
        </div >
    )
}

export default Hero