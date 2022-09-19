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

CREATE TABLE IF NOT EXISTS teams.scrims (
    host_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    scrimmer_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    host_votes BIGINT[] DEFAULT ARRAY[]::BIGINT[],
    scrimmer_votes BIGINT[] DEFAULT ARRAY[]::BIGINT[],
    when TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS timers(
    id BIGSERIAL PRIMARY KEY,
    precise BOOLEAN DEFAULT TRUE,
    event TEXT,
    extra JSONB,
    created TIMESTAMP,
    expires TIMESTAMP
);

CREATE TABLE IF NOT EXISTS timer_storage(
    id BIGSERIAL PRIMARY KEY,
    precise BOOLEAN,
    event TEXT,
    extra JSONB,
    created TIMESTAMP,
    expires TIMESTAMP
);
