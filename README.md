# Fury Bot
The Discord Bot for the FLVS Fury School Discord. The FURY bot allows works to lock down a school discord, now allowing any links or profanity.

Unfortunately, I am including the list of profanity based words in the repo. This is strictly for educational purposes, and is not something that should be used to be abused.

# Features
Bot will detect and auto mod any message or member if:

- A message has links
- A message has profanity
- A member has a bad display name
- A member has updated their display name to an inappropriate one.
- A binary message has profanity
- A message has tried to mention @here or @everyone
- A message has been uploaded with images or files
- A message's content legnth is too long.
- A profanity check on messages that have been edited
- A member's status is profane.


# Credit
Some code used from [Robo Danny](https://github.com/Rapptz/RoboDanny/), made by [Rapptz](https://github.com/Rapptz/).

- `utils.context.Context.tick` 
- `cogs.moderation.Moderation.reload_or_load_extension`
- `cogs.moderation.Moderation.find_modules_from_git`
- `cogs.moderation.Moderation.git_pull`
