CREATE DATABASE tabletki;
\c tabletki;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE notifications (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    text TEXT,
    chat VARCHAR(255),
    template VARCHAR(255),
    nextDate TIMESTAMPTZ,
    isDone BOOLEAN
);