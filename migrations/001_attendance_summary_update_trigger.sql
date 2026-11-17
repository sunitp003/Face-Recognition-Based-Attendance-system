-- Safe migration: does not delete or rewrite attendance rows.
-- Back up the database and run this once.
USE attendance_database1;

DROP TRIGGER IF EXISTS update_attendance_summary_after_update;
DELIMITER //
CREATE TRIGGER update_attendance_summary_after_update
AFTER UPDATE ON attendance
FOR EACH ROW
BEGIN
    IF OLD.attendance_status <> NEW.attendance_status THEN
        UPDATE attendance_summary
        SET
            present_count = GREATEST(
                0,
                present_count
                + (CASE WHEN NEW.attendance_status = 'Present' THEN 1 ELSE 0 END)
                - (CASE WHEN OLD.attendance_status = 'Present' THEN 1 ELSE 0 END)
            ),
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
            END
        WHERE student_ID = NEW.student_ID
          AND batch = NEW.batch
          AND branch = NEW.branch
          AND subject_name = NEW.subject_name;
    END IF;
END//
DELIMITER ;
