CREATE SCHEMA IF NOT EXISTS infractions;

CREATE TABLE IF NOT EXISTS infractions.settings (
    guild_id BIGINT UNIQUE,
    notification_channel_id BIGINT,
    moderators BIGINT[], -- A list of USER IDs of the moderators
    moderator_role_ids BIGINT[], -- A list of ROLE IDs of the role(s) that the mods have
    enable_no_dms_open BOOLEAN DEFAULT FALSE,
    enable_infraction_counter BOOLEAN DEFAULT TRUE,
);

-- The tracker for member infractions. Keeps track of all infractions for a member.
CREATE TABLE IF NOT EXISTS infractions.member_counter (
    guild_id BIGINT,
    user_id BIGINT,
    message_id BIGINT, -- The message ID of the infraction notification
    channel_id BIGINT -- The channel the infraction notification was sent in
);