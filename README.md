# Fury Bot
The Discord Bot for the FLVS Fury School Discord. This bot allows for the FLVS Fury Team to use Discord as the main
platform for all students to communicate by removing profanity, links, and other undesirable content.


## Overview
Fury Bot runs on a Cog Based Discord.py bot. The bot's job is to make the life of Moderation easier. It does
this my handling a lockdown, mute, and auto management system.

This bot will watch for specific features from the messages sent by members within the server,
and will auto moderate if nessecary.

### Auto Moderation
Fury Bot will take action upon any member who it deems to have posted something inappropriate, such as NSFW content, 
containing links or attachments, or containing profanity. This is done by using a set of predefined words that are deemed to be
inappropriate, and bulding upon that list to cover over 4610 profane words and phrases.

For each auto moderation action taken, Fury Bot will alert the user and the staff of the server that the action has been taken.

| **Auto Moderation Reason**                                 | **Auto Moderation Action**                        |
|------------------------------------------------------------|---------------------------------------------------|
| A profane message has been sent.                           | Lockdown for 5 minutes,                           |
| A message has been edited to display profanity.            | Lockdown for 5 minutes.                           |
| A member has mentioned a Role and pinged it.               | Lockdown for an hour.                             |
| A member has mentioned @here or @everyone and pinged it.   | Lockdown for an hour.                             |
| A member has uploaded attachments to their message.        | The message is deleted, they are warned.          |
| A member has sent a message that is over 700 characters.   | The message is deleted, they are warned.          |
| A member has sent a message that has links.                | The message is deleted, they are warned.          |
| A member has sent a profane message in a foreign language. | Lockdown for 5 minutes.                           |

### Profanity Checker
Fury bot has a complete profanity checker allowing for a list of allowed and denied terms to be set. This means
that the profanity checker is completely customizable, allowing for full control via commands.

### Link Checker
Similar to the profanity checker, the link checker is completely customizable, allowing for full control via commands.
Moderation can set a list of allowed domains, links, etc to be ignored.

## Honorable Mention
It's important to note that although a majority of the code inside of this bot is First Hand, there are some elements
of it that are not. These are listed below:

- `./utils/time.py` is fully from [Rapptz/RoboDanny](https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/time.py), 
with minor type hint modifications and improvements. 
- `./utils/context.py#L54-79 (tick)` is also from [Rapptz/RoboDanny](https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/context.py#L184-L193),
with minor type hint modifications and improvements to the function. 
- `./cogs/commands.py#Commands.translate` is inspred by 
[Rapptz/RoboDanny/funhouse.py#Funhouse.translate](https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/funhouse.py#L90-L93), with improvements
to message reference finding.
- The timer system in `./utils/timers` is from [Rapptz/RoboDanny](https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/reminder.py), with improvements
to typehing, minor bug fixes, and some other optimizations.
