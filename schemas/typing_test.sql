CREATE SCHEMA IF NOT EXISTS typing_test;

CREATE TABLE IF NOT EXISTS typing_test.history (
    id SERIAL PRIMARY KEY,
    member_id BIGINT,
    guild_id BIGINT,
    started_typing_at TIMESTAMP WITH TIME ZONE,
    ended_typing_at TIMESTAMP WITH TIME ZONE,
    accuracy FLOAT
);