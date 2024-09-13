CREATE SCHEMA IF NOT EXISTS images;

CREATE TABLE IF NOT EXISTS images.request_settings (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT, -- The ID of the channel to send to.
    guild_id BIGINT UNIQUE, -- The ID of the guild related to
    notification_role_id BIGINT
);

CREATE TABLE IF NOT EXISTS images.requests (
    id BIGSERIAL PRIMARY KEY,
    request_settings BIGINT REFERENCES images.request_settings(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE,
    attachment_payload JSONB,
    requester_id BIGINT,
    channel_id BIGINT, -- The ID of the channel to be sent in
    message_id BIGINT, -- The ID of the approved message (if any)
    message TEXT,
    moderator_request_message_id BIGINT, -- The ID of the mod view message to approve or deny the image
    denied_reason TEXT -- The reason, if any, that this image has been denied
);
