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

-- Keep attendance_summary correct when faculty edits Present/Absent.
DROP TRIGGER IF EXISTS update_attendance_summary_after_update;
DELIMITER //
CREATE TRIGGER update_attendance_summary_after_update
AFTER UPDATE ON attendance
FOR EACH ROW
BEGIN
    IF OLD.attendance_status <> NEW.attendance_status THEN
        UPDATE attendance_summary
        SET
            attendance_percentage = CASE
                WHEN total_classes > 0 THEN ROUND(
                    GREATEST(
                        0,
                        present_count
                        + (CASE WHEN NEW.attendance_status = 'Present' THEN 1 ELSE 0 END)
                        - (CASE WHEN OLD.attendance_status = 'Present' THEN 1 ELSE 0 END)
                    ) / total_classes * 100,
                    2
                )
                ELSE 0.00
            END,
            present_count = GREATEST(
                0,
                present_count
                + (CASE WHEN NEW.attendance_status = 'Present' THEN 1 ELSE 0 END)
                - (CASE WHEN OLD.attendance_status = 'Present' THEN 1 ELSE 0 END)
            )
        WHERE student_ID = NEW.student_ID
          AND batch = NEW.batch
          AND branch = NEW.branch
          AND subject_name = NEW.subject_name;
    END IF;
END//
DELIMITER ;

-- Create an administrator manually with a unique username and private password:
-- INSERT INTO admin_login (username, password) VALUES ('your_admin_username', 'your_private_password');

-- This schema file intentionally contains no sample-account inserts or DELETE statements.
