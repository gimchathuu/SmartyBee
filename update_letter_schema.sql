-- Script to update letter_template table with new columns for Learn pages
-- Run this to add ImageURL and ExampleWords columns

USE smartybee_db;

-- Add ImageURL column to store letter images
ALTER TABLE letter_template 
ADD COLUMN IF NOT EXISTS ImageURL VARCHAR(255);

-- Add ExampleWords column to store example Sinhala words (JSON format)
ALTER TABLE letter_template 
ADD COLUMN IF NOT EXISTS ExampleWords TEXT;

-- Verify the changes
DESCRIBE letter_template;
