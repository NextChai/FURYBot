CREATE TABLE IF NOT EXISTS profane_words (
    id SERIAL PRIMARY KEY,
    word TEXT UNIQUE
);

CREATE SCHEMA infractions;

CREATE TABLE IF NOT EXISTS infractions.time (
    guild_id BIGINT,
    type TEXT,
    time BIGINT -- In seconds,
);

CREATE TABLE IF NOT EXISTS infractions.settings (
    guild_id BIGINT UNIQUE,
    notification_channel_id BIGINT,
    moderators BIGINT [] DEFAULT ARRAY [] :: BIGINT [],
    moderator_role_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT [],
    valid_links TEXT [] DEFAULT ARRAY [] :: TEXT [],
    ignored_channel_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT []
);

CREATE TABLE IF NOT EXISTS infractions.profanity (
    guild_id BIGINT UNIQUE,
    automod_rule_id BIGINT
);

CREATE SCHEMA teams;

CREATE TABLE IF NOT EXISTS teams.settings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    category_channel_id BIGINT,
    text_channel_id BIGINT,
    voice_channel_id BIGINT,
    extra_channel_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT [],
    name TEXT UNIQUE,
    nickname TEXT,
    description TEXT,
    logo TEXT,
    captain_role_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT []
);

CREATE TABLE IF NOT EXISTS teams.members (
    team_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    member_id BIGINT,
    is_sub BOOLEAN DEFAULT FALSE
);

-- pending_scrimer: Pending for scrimmer to confirm
-- pending_host: Pending for host to confirm
-- scheduled: Scirm has been scheduled.
CREATE TYPE scrim_status AS ENUM ('pending_away', 'scheduled', 'pending_host');

CREATE TABLE IF NOT EXISTS teams.scrims (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    creator_id BIGINT,
    per_team INTEGER,
    home_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    away_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    home_message_id BIGINT,
    away_message_id BIGINT,
    status scrim_status,
    home_voter_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT [],
    away_voter_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT [],
    away_confirm_anyways_voter_ids BIGINT [] DEFAULT ARRAY [] :: BIGINT [],
    away_confirm_anyways_message_id BIGINT,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    scrim_chat_id BIGINT,
    -- Can be None
    scrim_scheduled_timer_id BIGINT,
    scrim_reminder_timer_id BIGINT,
    scrim_delete_timer_id BIGINT
);

CREATE TYPE practice_status AS ENUM ('ongoing', 'completed');

CREATE TABLE IF NOT EXISTS teams.practice (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE, -- Can be None
    team_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    channel_id INTEGER REFERENCES teams.settings(voice_channel_id),
    guild_id INTEGER REFERENCES teams.settings(guild_id), 
    status practice_status,
    started_by_id BIGINT,
    message_id BIGINT
);

CREATE TABLE IF NOT EXISTS teams.practice_member (
    id BIGSERIAL PRIMARY KEY,
    member_id BIGINT,
    practice_id INTEGER REFERENCES teams.practice(id) ON DELETE CASCADE
    attending BOOLEAN DEFAULT TRUE,
    reason TEXT -- Can be None, will be not None if attending is False
);

CREATE TABLE IF NOT EXISTS teams.practice_member_history(
    id BIGSERIAL PRIMARY KEY,
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE, -- Can be none
    team_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    channel_id INTEGER REFERENCES teams.settings(voice_channel_id),
    guild_id INTEGER REFERENCES teams.settings(guild_id),
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

CREATE TABLE IF NOT EXISTS image_requests (
    id BIGSERIAL PRIMARY KEY,
    attachment_payload JSONB,
    requester_id BIGINT,
    guild_id BIGINT,
    channel_id BIGINT,
    message_id BIGINT,
    -- For the persistent view, can be None
    message TEXT,
    -- The message the user attached to the upload
);