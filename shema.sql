CREATE TABLE IF NOT EXISTS profane_words (
    id SERIAL PRIMARY KEY,
    word TEXT UNIQUE
)

CREATE SCHEMA infractions;

CREATE TABLE IF NOT EXISTS infractions.time (
    guild_id BIGINT,
    type TEXT,
    time BIGINT -- In seconds,
)

CREATE TABLE IF NOT EXISTS infractions.settings (
    guild_id BIGINT UNIQUE,
    notification_channel_id BIGINT,
    moderators BIGINT[] DEFAULT ARRAY[]::BIGINT[],
    moderator_role_ids BIGINT[] DEFAULT ARRAY[]::BIGINT[],
    valid_links TEXT[] DEFAULT ARRAY[]::TEXT[],
    ignored_channel_ids BIGINT[] DEFAULT ARRAY[]::BIGINT[]
)

CREATE TABLE IF NOT EXISTS infractions.profanity (
    guild_id BIGINT UNIQUE,
    automod_rule_id BIGINT
)

CREATE SCHEMA teams;

CREATE TABLE IF NOT EXISTS teams.settings (
    id SERIAL PRIMARY KEY,
    category_id BIGINT,
    channels BIGINT[] DEFAULT ARRAY[]::BIGINT[],
    name TEXT UNIQUE,
    captain_roles BIGINT[] DEFAULT ARRAY[]::BIGINT[]
)

CREATE TABLE IF NOT EXISTS teams.members (
    team_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    member_id BIGINT,
    is_sub BOOLEAN DEFAULT FALSE
)

-- Reaction roles will work off of a "build your own" system.
-- This means we can have large chunks of information missing if
-- the moderators did not finish setup (ie. message_id missing -> buttons missing, etc)

CREATE SCHEMA reaction_role;

-- Represents a reaction role button (bound to views)
CREATE TABLE IF NOT EXISTS reaction_role.button (
    id SERIAL PRIMARY KEY,
    reaction_role INTEGER REFERENCES reaction_role.container(id) ON DELETE CASCADE,
    custom_id TEXT,
    message_id BIGINT,
    guild_id BIGINT,
    channel_id BIGINT,
    role_id BIGINT,
    label TEXT, -- Can be None
    emoji TEXT -- Can be None
);

-- Represents a reaction role reaction (bound to message reactions)
CREATE TABLE IF NOT EXISTS reaction_role.reaction (
    id SERIAL PRIMARY KEY,
    reaction_role INTEGER REFERENCES reaction_role.container(id) ON DELETE CASCADE,
    message_id BIGINT, 
    guild_id BIGINT,
    channel_id BIGINT, 
    role_id BIGINT,
    emoji TEXT
);

CREATE TABLE IF NOT EXISTS reaction_role.container (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    channel_id BIGINT, 
    message_id BIGINT,

    -- Can be None or missing elements. Please note 
    -- we will do no verification to ensure what the embed has is consistent
    -- with the reactions and buttons in the database. The customization
    -- of this is completely up to the user.
    embed JSONB
);