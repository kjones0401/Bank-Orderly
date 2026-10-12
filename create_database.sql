-- Run this script in MySQL Workbench with an administrator account.
-- v3 uses a SEPARATE database; original v2 tables are not altered.
CREATE DATABASE IF NOT EXISTS simple_bank_v3 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Create a dedicated bank_app user locally with a password of your choice.
-- Grant SELECT, INSERT, UPDATE, CREATE, REFERENCES on simple_bank_v3.*.
-- Do not put your password in files committed to GitHub.
-- Tables are created by banking.py on first launch.
