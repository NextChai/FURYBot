import { practice_start_embed, practice_start_slash_command, practice_ended_embed } from "../assets"

export const documentation = [
    {
        title: "Team Management",
        description: `Managing an e-sports team can be a complex and time-consuming task, but with Fury Bot, it's never been easier. \
            Our advanced team management system provides all the tools and features necessary to effectively organize, manage, and monitor your e-sports team. \
            From creating and managing rosters, to tracking practice times and performance statistics, Fury Bot streamlines the entire team management process and \
            helps you stay on top of your team's progress.`,
        id: "team-management",
        subheadings: [
            {
                title: "Team Practices",
                description: `A Comprehensive Tracking and Analytics Solution for E-sports Teams.\n \
                    The Fury Bot's Team Practice \
                    System is an advanced feature that provides real-time insights into the training habits of your e-sports teams. \
                    With the ability to keep track of when teams practice and the duration of their practices, this system empowers \
                    moderators with valuable information to optimize their team's performance.\n \
                    The system generates detailed statistics \
                    that highlight team member attendance and performance, enabling moderators to easily identify members \
                    who may be slacking off. Additionally, the Fury Bot Leaderboard System displays the top teams based on their total \
                    practice time, providing a competitive edge and motivation for teams to improve.\n \
                    This system is a \
                    valuable tool for moderators looking to take their e-sports teams to the next level. By providing an accurate \
                    and up-to-date view of team practice habits, moderators can make informed decisions and adjustments to \
                    improve their team's performance and achieve their goals.`,
                id: "team-practices",
                subheadings: [
                    {
                        title: "Starting a Practice as a Player",
                        description: `All members are required to participate in a weekly practice session on Mondays unless otherwise agreed upon by the team. \
                            The use of Fury Bot's Practice Session feature is essential to accurately record and monitor these practices.\n \
                            Initiating a Fury Bot Practice Session is a straightforward process, requiring only a single slash command. To start a session, \
                            connect to your team's voice chat and enter the command "/practice start." Please note this will include \
                            all members currently in the voice channel into the practice as well. {image_practice_start_slash_command}\n \
                            You will see a confirmation message that a practice session has started. This message will automatically update \
                            as members join the practice and mark themselves as not attending. {image_practice_start_embed}\n \
                            Shown on the image above, "Attending Members" are the members that have shown up to the practice. If you're unable \
                            to attend a given practice, it's crucial that you notify your team using the "I Can't Attend" button and provide a \
                            reason for your absence. If you do not join the practice and do not notify your team, you will be marked absent and \
                            a Captain will be made aware so that they can take appropriate action. {image_practice_ended_embed}\n \
                            When all team members have left the voice channel, the practice will end and you'll receieve a confirmation message \
                            in your team text chat. On the practice ended message, you can see the total practice time, when the practice started and ended, as well as \
                            the members who attended and those who were absent. During a given practice it's acceptable to leave and rejoin the \
                            voice channel, the Fury Bot will track your time accordingly.`,
                        id: "starting-a-practice-as-a-player",
                        image_practice_start_slash_command: practice_start_slash_command,
                        image_practice_start_embed: practice_start_embed,
                        image_practice_ended_embed: practice_ended_embed,
                        subheadings: [
                            {
                                title: "Starting a Practice FAQ",
                                description: `Below contains some of the frequently asked questions regarding starting a practice session. If you have \
                                    any additional questions, please contact a Captain or Moderator.`,
                                id: "starting-a-practice-faq",
                                subheadings: [
                                    {
                                        title: "My Team is Not Showing Up for Practice",
                                        description: `If you are the only member on your team that is showing up for a given practice, you should \
                                            start a practice session, wait to see if any members join, and then end the practice session. You should not remain \
                                            alone in the voice channel for an extended period of time. Fury Bot will automatically make a note of the \
                                            practice session and notify a Captain or Moderator. If you are unable to attend a practice, please use the \
                                            "I Can't Attend" button to notify your team.`,
                                        id: "my-team-is-not-showing-up-for-practice",
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ]
    },
]