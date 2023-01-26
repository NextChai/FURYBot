import React from 'react';

import styles from "../style";

const Hero = () => {
    return (
        <div className='w-full bg-light-ws_bg dark:bg-dark-ws_bg'>
            {/* Holds the bot description and supporting image */}
            <div className={`${styles.flexCenter} ${styles.paddingY}`}>
                <div>
                    <h1 className="text-light-text dark:text-dark-text font-poppins font-semibold ss:text-[52px] text-[32px] text-center pt-11 max-w-xl">
                        Time To See What Fury Bot Can Do To Your Server.
                    </h1>
                </div>
            </div>

            {/* Holds supporting cards under the main caption. */}
            <div className={`w-full flex flex-wrap md:flex-nowrap space-x-6 ${styles.paddingX} ${styles.paddingY}`}>
                <div className="flex-auto border-solid border-2 rounded-md drop-shadow-md py-5">
                    <h1 className='font-poppins font-semibold text-light-text dark:text-dark-text text-lg text-center'>
                        School Discord Server Management
                    </h1>

                    <p className="font-poppins text-light-text dark:text-dark-text text-center py-4 px-5">
                        Fury Bot is a Discord bot to assist in the management of your e-sports Discord server.
                        Through years of experience in the e-sports industry, we have developed a bot that will
                        give you all the utilities you need to manage a PG-rated, safe, and fun Discord server.
                    </p>
                </div>

                <div className="flex-auto border-solid border-2  rounded-md drop-shadow-md py-5">
                    <h1 className='font-poppins font-semibold text-light-text dark:text-dark-text text-lg text-center'>
                        Team Managament
                    </h1>

                    <p className="font-poppins text-light-text dark:text-dark-text text-center py-4 px-5">
                        Fury Bot comes out of the box with a complete team management system. This system allows
                        you to create teams, add players to teams, manage team rosters, send annoucements to teams,
                        and much more. More about this can be found in the Team documentation.
                    </p>
                </div>

                <div className="flex-auto border-solid border-2 rounded-md drop-shadow-md py-5">
                    <h1 className='font-poppins font-semibold text-light-text dark:text-dark-text text-lg text-center'>
                        Member Moderation
                    </h1>

                    <p className="font-poppins text-light-text dark:text-dark-text text-center py-4 px-5">
                        The most important aspect about managing a Discord server fit for a school environment is
                        the ability to moderate your members. This includes weeding out profanity and looking for signs
                        of bullying, harassment, and other negative behavior. Fury Bot is here for you! Fury Bot comes
                        with a complete set of tools to help you manage your members.
                    </p>
                </div>

            </div>

        </div >
    )
}

export default Hero