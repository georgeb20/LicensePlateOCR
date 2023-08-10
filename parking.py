import pyodbc
from datetime import datetime, timedelta

class ParkingMeter:
    def __init__(self, db_connection_string):
        self.db_connection_string = db_connection_string

        # Initialize the database connection and create tables if not exists
        self.conn = pyodbc.connect(self.db_connection_string)

    def create_tables(self):
        with self.conn.cursor() as cursor:
            cursor.execute('''
                IF NOT EXISTS (
                    SELECT * FROM sysobjects
                    WHERE name='license_plates' AND xtype='U'
                )
                CREATE TABLE license_plates (
                    plate NVARCHAR(50) PRIMARY KEY,
                    start_time DATETIME,
                    end_time DATETIME,
                    total_time NVARCHAR(50)
                )
            ''')
            self.conn.commit()

    def car_seen(self, license_plate):
        current_time = datetime.now()

        with self.conn.cursor() as cursor:
            cursor.execute('SELECT * FROM license_plates WHERE plate = ?', license_plate)
            existing_record = cursor.fetchone()

            if existing_record:
                start_time = existing_record[1]
                elapsed_time = current_time - start_time
                cursor.execute('''
                    UPDATE license_plates
                    SET end_time = ?, total_time = ?
                    WHERE plate = ?
                ''', (current_time, str(elapsed_time), license_plate))
                self.conn.commit()

                # Call calculate_payment if the car has been seen before
                amount_due = self.calculate_payment(license_plate)
                print(f"Amount due for {license_plate}: ${amount_due:.2f}")
            else:
                cursor.execute('''
                    INSERT INTO license_plates (plate, start_time, end_time, total_time)
                    VALUES (?, ?, ?, ?)
                ''', (license_plate, current_time, None, str(timedelta(0))))
                self.conn.commit()

    def calculate_payment(self, license_plate):
        # Dictionary of flat hourly rates based on time intervals
        hourly_rates = {
            0.5: 3.00,
            1: 5.00,
            2: 8.00,
            3: 10.00,
            4: 15.00,
            float('inf'): 20.00  # Default rate for 4+ hours
        }

        with self.conn.cursor() as cursor:
            cursor.execute('SELECT * FROM license_plates WHERE plate = ?', license_plate)
            existing_record = cursor.fetchone()

            if existing_record:
                total_time_str = existing_record[3]  # The total_time value as a string
                total_time = timedelta(seconds=float(total_time_str.split(':')[-1]))  # Extract seconds part

                # Calculate hours from total_time
                hours = total_time.total_seconds() / 3600

                # Find the applicable flat hourly rate from the dictionary
                applicable_rate = next(rate for max_hours, rate in hourly_rates.items() if hours <= max_hours)
                amount_due = applicable_rate  # Just the applicable flat rate for the parking duration
                return amount_due
            else:
                return 0.0

    def close(self):
        self.conn.close()

# Usage example
connection_string = 'Driver={SQL Server};Server=GEO;Database=parking;Trusted_Connection=yes;'
parking_meter = ParkingMeter(connection_string)


# Car seen at different times
parking_meter.car_seen("ABC123")  # Car seen for the first time
parking_meter.car_seen("ABC12")  # Car seen for the first time
parking_meter.car_seen("ABC12")  # Car seen for the first time


# Don't forget to close the connection when done
parking_meter.close()
