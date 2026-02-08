CREATE DATABASE IF NOT EXISTS smartybee_db;
USE smartybee_db;

-- Users
CREATE TABLE IF NOT EXISTS User (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(50) NOT NULL UNIQUE,
    PasswordHash VARCHAR(255) NOT NULL,
    Role ENUM('Admin', 'Guardian', 'Child') NOT NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Profiles
CREATE TABLE IF NOT EXISTS Child_Profile (
    ChildID INT AUTO_INCREMENT PRIMARY KEY,
    GuardianID INT, -- Links to User.UserID of the Guardian
    UserID INT, -- Links to User.UserID of the Child (For Login)
    Name VARCHAR(100),
    Age INT,
    Avatar VARCHAR(50) DEFAULT 'default_avatar.png', -- Added for avatar support
    TotalStars INT DEFAULT 0,
    FOREIGN KEY (GuardianID) REFERENCES User(UserID) ON DELETE CASCADE,
    FOREIGN KEY (UserID) REFERENCES User(UserID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Guardian_Profile (
    GuardianID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT,
    User_Name VARCHAR(50) NOT NULL UNIQUE,
    ProfilePicture VARCHAR(255) DEFAULT 'default_guardian.png',
    FOREIGN KEY (UserID) REFERENCES User(UserID) ON DELETE CASCADE
);

-- Content
CREATE TABLE IF NOT EXISTS Letter_Template (
    LetterID INT AUTO_INCREMENT PRIMARY KEY,
    SinhalaChar VARCHAR(10) CHARACTER SET utf8mb4,
    StrokePathJSON JSON, -- Stores "perfect" normalized path
    DifficultyLevel ENUM('Easy', 'Medium', 'Hard'),
    Level INT DEFAULT 1,
    ImageURL VARCHAR(255),
    ExampleWords JSON
);

CREATE TABLE IF NOT EXISTS Child_Letter_Assignment (
    AssignmentID INT AUTO_INCREMENT PRIMARY KEY,
    ChildID INT,
    LetterID INT,
    AssignedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE CASCADE,
    FOREIGN KEY (LetterID) REFERENCES Letter_Template(LetterID) ON DELETE CASCADE,
    UNIQUE KEY (ChildID, LetterID)
);

-- Session Logs
CREATE TABLE IF NOT EXISTS Session_Log (
    SessionID INT AUTO_INCREMENT PRIMARY KEY,
    ChildID INT,
    LetterID INT,
    AccuracyScore DECIMAL(5,2),
    StarsEarned INT DEFAULT 0,
    TimeTakenSeconds INT,
    PlayedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID)
);

-- Admin Users
CREATE TABLE IF NOT EXISTS Admin_User (
    AdminID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(50) NOT NULL UNIQUE,
    PasswordHash VARCHAR(255) NOT NULL,
    Role ENUM('SuperAdmin', 'Editor') DEFAULT 'SuperAdmin',
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- System Logs
CREATE TABLE IF NOT EXISTS System_Log (
    LogID INT AUTO_INCREMENT PRIMARY KEY,
    Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    Level VARCHAR(20), -- INFO, WARNING, ERROR
    Message TEXT
);

-- Feedback
CREATE TABLE IF NOT EXISTS Feedback (
    FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
    GuardianID INT,
    Message TEXT,
    SubmittedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (GuardianID) REFERENCES User(UserID) ON DELETE SET NULL
);

-- Letter Progress Feedback (Guardian to Child)
CREATE TABLE IF NOT EXISTS Letter_Progress_Feedback (
    FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
    ChildID INT,
    LetterID INT,
    GuardianID INT,
    Message TEXT,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE CASCADE,
    FOREIGN KEY (LetterID) REFERENCES Letter_Template(LetterID) ON DELETE CASCADE,
    FOREIGN KEY (GuardianID) REFERENCES User(UserID) ON DELETE CASCADE
);

-- Seed Data (Optional)
INSERT INTO Letter_Template (SinhalaChar, DifficultyLevel, StrokePathJSON) VALUES 
('අ', 'Easy', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]'); -- Dummy vertical line for testing
