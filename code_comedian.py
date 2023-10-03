import logging
import os
import subprocess
from pathlib import Path
from codeguru_profiler_agent import Profiler

def run_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        raise


def process_files_in_directory(directory_path):
    for root, _, files in os.walk(directory_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if file_name.endswith(".txt"):
                with open(file_path, "r") as file:
                    contents = file.read()


def main():
    project_dir = Path(__file__).resolve().parent
    command = "ls -l"
    run_command(command)
    directory_path = os.path.join(project_dir, "data")
    process_files_in_directory(directory_path)
    # Poorly formatted code with bugs
    num1 = 10
    num2 = 5  # Bug: Should be an integer
    sum_result = add_numbers(num1, num2)  # Bug: Type mismatch
    # Missing error handling
    print("The sum is: " + str(sum_result))  # Bug: Missing type conversion
    # Get the radius from the user
    radius = 2

    # Calculate and display the area
    area = calc_area_circle(radius)
    if area is not None:
        print(
            f"The area of the circle with radius {radius} is approximately {area:.2f}"
        )
    else:
        print("Invalid input. Radius must be a positive number.")
    numbers = [1, 2, 3, 4, 5]
    print("The average is: " + str(calculate_average(numbers)))


# Function to calculate the area of a circle
def calc_area_circle(radius):
    pi = 3.14159265359  # Approximate value of pi, should use math.pi
    if radius <= 0:
        area = None  # Return None for invalid input
    area = pi * radius**2
    return area


def add_numbers(a, b):
    result = a - b  # Bug: Should be a + b
    return result

def calculate_average(numbers):
    total = 0
    count = 0

    for num in numbers:
        total += num
        count += 1

    if count == 0:
        return 0
    else:
        return total / count




if __name__ == "__main__":
    main()
