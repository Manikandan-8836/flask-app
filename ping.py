import subprocess

def ping_ip(ip):
    try:
        # Run the ping command for Windows (-n 1 sends 1 packet)
        result = subprocess.run(["ping", "-n", "1", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if "Reply from" is in the output, meaning the device responded
        if "Reply from" in result.stdout:
            print(f"{ip} is Connected")
        else:
            print(f"{ip} is Not Connected")

    except Exception as e:
        print(f"Error: {e}")

# Example usage
ping_ip("192.168.125.1")  # Replace with your IP
