CREATE TABLE IF NOT EXISTS timers(
    id BIGSERIAL PRIMARY KEY,
    precise BOOLEAN DEFAULT TRUE,
    event TEXT,
    extra JSONB,
    created TIMESTAMP WITH TIME ZONE,
    expires TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS timer_storage(
    id BIGSERIAL PRIMARY KEY,
    precise BOOLEAN,
    event TEXT,
    extra JSONB,
    created TIMESTAMP WITH TIME ZONE,
    expires TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS image_requests (
    id BIGSERIAL PRIMARY KEY,
    attachment_payload JSONB,
    requester_id BIGINT,
    guild_id BIGINT,
    channel_id BIGINT,
    message_id BIGINT,
    -- For the persistent view, can be None
    message TEXT
    -- The message the user attached to the upload
);
