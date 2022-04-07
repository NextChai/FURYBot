CREATE TABLE IF NOT EXISTS timers(
    id BIGSERIAL PRIMARY KEY,
    precise BOOLEAN DEFAULT TRUE,
    event TEXT,
    extra JSONB,
    created TIMESTAMP,
    expires TIMESTAMP,
    dispatched BOOLEAN
);


CREATE TABLE IF NOT EXISTS teams(
    id BIGSERIAL PRIMARY KEY,
    team_name TEXT,
    roster BIGINT[] DEFAULT BIGINT[],
    subs BIGINT[] DEFAULT BIGINT[],
    captain_role BIGINT,
    channels JSONB,   -- {'text': null, 'voice': null, 'category': null}
    created TIMESTAMP DEFAULT now(),
    last_updated TIMESTAMP DEFAULT now()
);


CREATE TABLE IF NOT EXISTS tracking (
    id BIGSERIAL PRIMARY KEY,
    member BIGINT,
    team_id BIGINT,
    game_sessions TIMESTAMP[][] DEFAULT ARRAY[], -- game_sessions and game_information should be in sync
    game_information JSONB[],
    notifications BOOLEAN DEFAULT FALSE
);


CREATE TABLE IF NOT EXISTS profanity(
    id BIGSERIAL PRIMARY KEY,
    word TEXT,
    created_at TIMESTAMP DEFAULT now()
);


CREATE TABLE IF NOT EXISTS links (
    id BIGSERIAL PRIMARY KEY,
    url TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS highlight (
    id BIGSERIAL PRIMARY KEY,
    member BIGINT,
    phrase TEXT,
    count INT
)