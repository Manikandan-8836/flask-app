import cv2
import numpy as np
import re
import csv
import socket
import time

# Robot IP and port
ROBOT_IP = "192.168.125.1"
ROBOT_PORT = 1025


def image_to_gcode(image_path, output_file, scale=0.3, z_down=0, z_up=5):
    # Load the image and convert to grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (255, 255))  # Resize to match 255x255 work area

    # Invert the image so dark pixels represent ink
    _, binary_img = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)

    # Open G-code file for writing
    with open(output_file, "w") as f:
        f.write("G21 ; Set units to mm\n")  # Set to millimeters
        f.write("G90 ; Absolute positioning\n")

        # Move to starting position
        f.write("G0 X0 Y0 Z{:.2f}\n".format(z_up))

        # Traverse the image row by row
        for y in range(0, 255, 2):  # Step size = 2 for faster printing
            line_active = False  # Track if we're drawing
            first_point = None  # Store the first point of the line
            last_point = None  # Store the last point of the line

            # Move in a zigzag pattern (left to right, then right to left)
            x_range = range(255) if y % 4 == 0 else range(254, -1, -1)

            for x in x_range:
                if binary_img[y, x] == 255:  # If pixel should be drawn
                    x_scaled, y_scaled = x * scale, (255 - y) * scale  # Adjust for machine

                    if not line_active:
                        # Store the first point and start drawing
                        first_point = (x_scaled, y_scaled)
                        line_active = True

                    # Update the last point
                    last_point = (x_scaled, y_scaled)

                elif line_active:
                    # Once we finish a line (reach the end), write only the first and last point
                    f.write("G0 Z{:.2f}\n".format(z_up))  # Lift the pen
                    f.write("G0 X{:.2f} Y{:.2f} Z{:.2f}\n".format(first_point[0], first_point[1],
                                                                  z_up))  # Move to first point
                    f.write("G0 X{:.2f} Y{:.2f} Z{:.2f}\n".format(first_point[0], first_point[1],
                                                                  z_down))  # Lower the pen to start drawing
                    f.write("G1 X{:.2f} Y{:.2f} Z{:.2f}\n".format(last_point[0], last_point[1],
                                                                  z_down))  # Draw to last point
                    line_active = False  # Reset line state

            # If a line was active at the end of the row, lift the pen
            if line_active:
                f.write("G0 Z{:.2f}\n".format(z_up))  # Lift the pen after finishing the row

        # Move home at the end
        f.write("G0 X0 Y0 Z{:.2f}\n".format(z_up))

    print(f"G-code saved to {output_file}")


def gcode_to_csv(gcode_file, csv_file):
    coordinates = []
    last_entry = [0, 0, 0]  # Initialize last known coordinates

    with open(gcode_file, "r") as file:
        for line in file:
            # Extract X, Y, and Z values using regex
            match = re.findall(r"([XYZ])([-]?\d+\.?\d*)", line)
            if match:
                coord_dict = [None, None, None]  # [X, Y, Z] placeholders

                for axis, value in match:
                    idx = {"X": 0, "Y": 1, "Z": 2}[axis]  # Map X, Y, Z to indices
                    coord_dict[idx] = int(round(float(value)))  # Convert to int

                # Use the last known values if missing
                for i in range(3):
                    if coord_dict[i] is None:
                        coord_dict[i] = last_entry[i]

                coordinates.append(coord_dict)
                last_entry = coord_dict[:]  # Update last known coordinates

    # Save to CSV
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["X", "Y", "Z"])  # Header
        writer.writerows(coordinates)

    print(f"CSV file saved as {csv_file}")


def remove_consecutive_duplicates(input_csv, output_csv):
    unique_rows = []
    last_row = None  # Track the last recorded row

    # Read input CSV
    with open(input_csv, "r", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)  # Read header
        unique_rows.append(header)  # Keep header in output

        for row in reader:
            if row != last_row:  # Only append if different from the last recorded row
                unique_rows.append(row)
                last_row = row  # Update last recorded row

    # Write output CSV
    with open(output_csv, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(unique_rows)

    print(f"CSV file saved as {output_csv}")


# Example usage


def send_coordinates_to_robot(csv_path, ROBOT_IP, ROBOT_PORT):
    start = time.time()
    try:
        # Create a socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            # Connect to the robot
            client_socket.connect((ROBOT_IP, ROBOT_PORT))
            print(f"Connected to robot at {ROBOT_IP}:{ROBOT_PORT}")

            # Open the CSV file and send each coordinate line
            with open(csv_path, mode="r") as csv_file:
                csv_reader = csv.reader(csv_file)
                next(csv_reader)  # Skip the header row
                count = 0
                start = time.time()
                for row in csv_reader:
                    if count == 100:
                        stop = time.time()
                        out = stop - start
                        print(out)

                    if len(row) < 3:
                        continue  # Skip invalid rows

                    # Extract X, Y, Z
                    x = row[0]
                    y = row[1]
                    z = row[2]

                    # Format the message as "x y z"
                    if z == 5:
                        z = 3
                    message = f"{x} {y} {z}"

                    # Send the message to the robot
                    client_socket.sendall(message.encode("utf-8"))
                    print(f"Sent: {message}")

                    # Receive acknowledgment from the robot
                    ack = client_socket.recv(1024).decode("utf-8")
                    print(f"Robot ACK: {ack}")
                    count = count + 1

            # After all points are sent, send termination message
            termination_message = "done"
            client_socket.sendall(termination_message.encode("utf-8"))
            print("Sent termination message. Closing the connection.")
            end = time.time()
            final = end - start
            print(final)

    except Exception as e:
        print(f"Error while sending data to the robot: {e}")


# Main Function
def main():
    # Convert image to G-code and then to CSV
    image_to_gcode("img.png", "output_1.gcode")
    gcode_to_csv("output_1.gcode", "input_robot.csv")
    remove_consecutive_duplicates("input_robot.csv", "output.csv")

    print("G-code and CSV conversion complete.")
    n = int(input('Enter 1 to start:'))
    if n == 1:
        print('Connecting with robot')
        send_coordinates_to_robot("output.csv"
                                  "", ROBOT_IP, ROBOT_PORT)


if __name__ == "__main__":
    main()
