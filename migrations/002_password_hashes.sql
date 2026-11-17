-- Run once on an existing database before deploying password-hash login code.
-- Back up the database first. Existing plaintext credentials are upgraded on each
-- user's first successful login and the plaintext admin password is then cleared.

ALTER TABLE admin_login
    MODIFY COLUMN password VARCHAR(255) NULL,
    ADD COLUMN password_hash VARCHAR(255) NULL AFTER password;

ALTER TABLE faculty_login
    ADD COLUMN password_hash VARCHAR(255) NULL AFTER faculty_id;

ALTER TABLE student_login
    ADD COLUMN password_hash VARCHAR(255) NULL AFTER roll_no;
