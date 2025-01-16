CREATE SCHEMA IF NOT EXISTS locking;

CREATE TYPE IF NOT EXISTS locking.lock_status AS ENUM ('locked', 'unlocked');

CREATE TABLE IF NOT EXISTS locking.lock (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    affected_channels BIGINT[] NOT NULL,
    status locking.lock_status NOT NULL
);