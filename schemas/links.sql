CREATE SCHEMA links;

CREATE TABLE IF NOT EXISTS links.settings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT UNIQUE,
    notifier_channel_id BIGINT
);

-- 1 (warn): send the warn_message to them
-- 2: (mute) Mute then for the delta
-- 3: (surpress) Delete the message.
CREATE TYPE links.diciplinary_action AS ENUM ('warn', 'mute', 'surpress');

CREATE TABLE IF NOT EXISTS links.actions (  
    id SERIAL PRIMARY KEY,
    settings_id INTEGER REFERENCES links.settings(id),
    type links.diciplinary_action,
    delta INTEGER, -- Amount to mute them for, in seconds
    warn_message TEXT -- Message to send when warning
);

CREATE TABLE IF NOT EXISTS links.allowed_links (
    id SERIAL PRIMARY KEY,
    settings_id INTEGER REFERENCES links.settings(id),
    url TEXT,
    added_at TIMESTAMP WITH TIME ZONE,
    added_by_id TEXT
);
