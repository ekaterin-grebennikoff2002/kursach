CREATE DATABASE tabletki;
\c tabletki;

CREATE TABLE UserAccount  (
    id UUID PRIMARY KEY,
    chat VARCHAR(255)
);

CREATE TABLE Notifications (
    id UUID PRIMARY KEY,
    userId UUID,
    text TEXT,
    template VARCHAR(255),
    nextDate DATE,
    FOREIGN KEY (userId) REFERENCES UserAccount(id)
);