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
CREATE TYPE teams.scrim_status AS ENUM ('pending_away', 'scheduled', 'pending_host');

CREATE TABLE IF NOT EXISTS teams.scrims (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    creator_id BIGINT,
    per_team INTEGER,
    home_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    away_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    home_message_id BIGINT,
    away_message_id BIGINT,
    status teams.scrim_status,
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

CREATE TYPE teams.practice_status AS ENUM ('ongoing', 'completed');

CREATE TABLE IF NOT EXISTS teams.practice (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE, -- Can be None
    team_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    channel_id BIGINT,
    guild_id BIGINT, 
    status teams.practice_status,
    started_by_id BIGINT,
    message_id BIGINT
);

CREATE TABLE IF NOT EXISTS teams.practice_member (
    id BIGSERIAL PRIMARY KEY,
    member_id BIGINT,
    practice_id INTEGER REFERENCES teams.practice(id) ON DELETE CASCADE,
    attending BOOLEAN DEFAULT TRUE,
    reason TEXT -- Can be None, will be not None if attending is False
);

CREATE TABLE IF NOT EXISTS teams.practice_member_history(
    id BIGSERIAL PRIMARY KEY,
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE, -- Can be none
    practice_id INTEGER REFERENCES teams.practice(id) ON DELETE CASCADE,
    member_id BIGINT,
    team_id INTEGER REFERENCES teams.settings(id) ON DELETE CASCADE,
    channel_id BIGINT,
    guild_id BIGINT
);

CREATE TABLE IF NOT EXISTS teams.practice_leaderboards(
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT UNIQUE,
    guild_id BIGINT UNIQUE,
    message_id BIGINT,
    top_team_id INTEGER REFERENCES teams.settings(id),
    role_id BIGINT
);

