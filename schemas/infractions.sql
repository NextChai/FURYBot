CREATE SCHEMA IF NOT EXISTS infractions;

CREATE TABLE IF NOT EXISTS infractions.settings (
    guild_id BIGINT UNIQUE,
    notification_channel_id BIGINT,
    moderators BIGINT[], -- A list of USER IDs of the moderators
    moderator_role_ids BIGINT[] -- A list of ROLE IDs of the role(s) that the mods have
    enable_no_dms_open BOOLEAN DEFAULT FALSE
);