CREATE SCHEMA IF NOT EXISTS profanity;

-- A guild can have up to 6 custom profanity words, or 6 records
-- and 6,000 words in total.
CREATE TABLE IF NOT EXISTS profanity.settings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    automod_rule_id BIGINT
);


CREATE TABLE IF NOT EXISTS profanity.words (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    settings_id BIGINT REFERENCES profanity.settings(id) ON DELETE CASCADE,
    automod_rule_id BIGINT,
    word TEXT UNIQUE,
    added_at TIMESTAMP WITH TIME ZONE
);