"""Calculator library used by the CLI, the web API and the tests."""


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


OPERATIONS = {"add": add, "subtract": subtract, "multiply": multiply, "divide": divide}


if __name__ == "__main__":
    print("Calculator Application")
    print("----------------------")
    for name, fn in OPERATIONS.items():
        print(f"{name:9s} 10, 5 -> {fn(10, 5)}")
