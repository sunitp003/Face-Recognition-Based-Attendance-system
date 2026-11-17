-- Create the database
CREATE DATABASE IF NOT EXISTS `attendance_database1` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `attendance_database1`;

-- Drop existing tables if needed (Uncomment if resetting the database)
-- DROP TABLE IF EXISTS `attendance`;
-- DROP TABLE IF EXISTS `attendance_summary`;
-- DROP TABLE IF EXISTS `student_login`;
-- DROP TABLE IF EXISTS `faculty_login`;
-- DROP TABLE IF EXISTS `admin_login`;

-- Admin Table
CREATE TABLE IF NOT EXISTS `admin_login` (
  `username` VARCHAR(20) NOT NULL,
  `password` VARCHAR(15) NOT NULL,
  UNIQUE KEY `username_UNIQUE` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Faculty Table
CREATE TABLE IF NOT EXISTS `faculty_login` (
  `faculty_name` VARCHAR(50) NOT NULL,
  `faculty_id` VARCHAR(25) NOT NULL PRIMARY KEY,
  `department` VARCHAR(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Student Table
CREATE TABLE IF NOT EXISTS `student_login` (
  `student_name` VARCHAR(50) NOT NULL,
  `roll_no` VARCHAR(15) NOT NULL PRIMARY KEY,
  `branch` VARCHAR(50) DEFAULT NULL,
  `batch` VARCHAR(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Attendance Table (Raw Records)
CREATE TABLE IF NOT EXISTS `attendance` (
  `attendance_date` DATE NOT NULL,
  `student_ID` VARCHAR(15) NOT NULL,
  `faculty_ID` VARCHAR(25) NOT NULL,
  `batch` VARCHAR(20) NOT NULL,
  `branch` VARCHAR(50) NOT NULL,
  `year` VARCHAR(10) NOT NULL,
  `subject_name` VARCHAR(100) NOT NULL,
  `attendance_status` ENUM('Present', 'Absent') DEFAULT 'Absent',
  PRIMARY KEY (`attendance_date`, `subject_name`, `student_ID`, `batch`, `branch`),
  FOREIGN KEY (`student_ID`) REFERENCES `student_login` (`roll_no`) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (`faculty_ID`) REFERENCES `faculty_login` (`faculty_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Attendance Summary Table (Processed Data)
CREATE TABLE IF NOT EXISTS `attendance_summary` (
  `student_ID` VARCHAR(15) NOT NULL,
  `faculty_ID` VARCHAR(25) NOT NULL,
  `batch` VARCHAR(20) NOT NULL,
  `branch` VARCHAR(50) NOT NULL,
  `subject_name` VARCHAR(100) NOT NULL,
  `total_classes` INT DEFAULT 0,
  `present_count` INT DEFAULT 0,
  `attendance_percentage` DECIMAL(5,2) DEFAULT 0.00,
  PRIMARY KEY (`student_ID`, `batch`, `branch`, `subject_name`),
  FOREIGN KEY (`student_ID`) REFERENCES `student_login` (`roll_no`) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (`faculty_ID`) REFERENCES `faculty_login` (`faculty_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Optimized Attendance Trigger for Summary Table
DROP TRIGGER IF EXISTS update_attendance_summary;

DELIMITER //
CREATE TRIGGER update_attendance_summary
AFTER INSERT ON attendance
FOR EACH ROW
BEGIN
    INSERT INTO attendance_summary (student_ID, faculty_ID, batch, branch, subject_name, total_classes, present_count, attendance_percentage)
    VALUES (NEW.student_ID, NEW.faculty_ID, NEW.batch, NEW.branch, NEW.subject_name, 1, 
            CASE WHEN NEW.attendance_status = 'Present' THEN 1 ELSE 0 END,
            CASE WHEN NEW.attendance_status = 'Present' THEN 100 ELSE 0 END)
    ON DUPLICATE KEY UPDATE 
        total_classes = total_classes + 1,
        present_count = present_count + (CASE WHEN NEW.attendance_status = 'Present' THEN 1 ELSE 0 END),
        attendance_percentage = ROUND((present_count / NULLIF(total_classes, 0)) * 100, 2);

END;
//
DELIMITER ;


-- Dynamic SQL Query to Generate Attendance Report
SET @sql = NULL;
SELECT GROUP_CONCAT(DISTINCT 
        CONCAT('COALESCE(MAX(CASE WHEN attendance_date = ''', attendance_date, 
               ''' THEN attendance_status END), "Absent") AS `', attendance_date, '`')
       ) INTO @sql
FROM attendance;


SET @sql = CONCAT('SELECT a.student_ID, a.faculty_ID, a.batch, a.branch, a.subject_name, ', @sql, 
                  ', s.attendance_percentage
                  FROM attendance a
                  JOIN attendance_summary s ON a.student_ID = s.student_ID
                  GROUP BY a.student_ID, a.faculty_ID, a.batch, a.branch, a.subject_name, s.attendance_percentage');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Sample Data Insert (Optional)
INSERT INTO admin_login (username, password) VALUES ("Sunit", "sunit003");
UPDATE admin_login SET username = "sunit" WHERE username = "Sunit";

-- Debugging Queries
SELECT * FROM admin_login;
SELECT * FROM attendance;
SELECT * FROM faculty_login;
SELECT * FROM student_login;
SELECT * FROM attendance_summary;
DESC student_login;

INSERT INTO admin_login (username,password) 
VALUES ('sunit','sunit003');

INSERT INTO admin_login (username,password) 
VALUES ('sunit','sunit003');

USE `attendance_database1`;

-- Cleanup Commands (Use with Caution)
DELETE FROM attendance WHERE student_ID = '342529';
SET SQL_SAFE_UPDATES = 0;
DELETE FROM attendance;
SET SQL_SAFE_UPDATES = 1;

SET SQL_SAFE_UPDATES = 0;
DELETE FROM attendance_summary;
SET SQL_SAFE_UPDATES = 1;

SET SQL_SAFE_UPDATES = 0;
DELETE FROM student_login;
SET SQL_SAFE_UPDATES = 1;


USE `attendance_database1`;


DELETE FROM attendance WHERE student_ID = '342529';
DELETE FROM attendance_summary WHERE student_ID = '342529';
DELETE FROM student_login WHERE roll_no = '344135';
DELETE FROM faculty_login WHERE faculty_id = 'faculty456';

-- Sample Faculty and Student Data
-- INSERT INTO faculty_login (faculty_name, faculty_id, department) VALUES ('Dr. Smith', 'faculty456', 'CSE');
-- INSERT INTO student_login (student_name, roll_no, branch, batch) VALUES ('John Doe', '2021311', 'CS1', '2017');

-- Sample Attendance Data
-- INSERT INTO attendance (student_ID, faculty_ID, batch, branch, attendance_date, attendance_status) VALUES
-- ('2021311', 'faculty456', '2017', 'CS1', '2025-03-21', 'Present'),
-- ('2021311', 'faculty456', '2017', 'CS1', '2025-03-22', 'Absent');

SELECT * FROM attendance_summary;
