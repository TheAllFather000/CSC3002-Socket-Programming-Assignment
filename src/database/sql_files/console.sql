SELECT data_type from information_schema.columns where table_name = 'user_info';

ALTER TABLE user_info
ALTER COLUMN colour TYPE json using colour::json;

DROP TABLE user_info;

CREATE TABLE user_info
(
    username varchar(20) PRIMARY KEY,
    password varchar(20) NOT NULL,
    colour json NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO user_info (username, password, colour) VALUES
                                                                   ('wyrm', 'pass',
                                                                    '{"r": 20, "g": 35, "b": 120}');
