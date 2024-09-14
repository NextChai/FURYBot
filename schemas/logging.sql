CREATE SCHEMA IF NOT EXISTS logging;

CREATE TABLE IF NOT EXISTS logging.settings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT UNIQUE,
    logging_channel_id BIGINT, -- Can be None
    webhook_url TEXT -- Can be None if deleted or if the webhook is not set
);

-- Denotes an event that is enabled for logging. 
CREATE TABLE IF NOT EXISTS logging.events (
    id SERIAL PRIMARY KEY,
    settings_id INT REFERENCES logging.settings(id) ON DELETE CASCADE,
    event_type TEXT
);