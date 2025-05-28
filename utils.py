# Utilities.
import sys
import csv
import json
import platform


def compacts(data):
    """Return object dump to compact json."""
    return json.dumps(data, separators=(',', ':'))

def dumps(data):
    """Return object dump to pretty json."""
    return json.dumps(data, indent=4)

def fileuri(path):
    """Return file uri for path."""
    if platform.system() == "Windows":
        return 'file:///' + path if path else None
    elif platform.system() == "Linux":
        return 'file://' + path if path else None
    raise NotImplementedError("Running on an unknown OS!")


def head_file(path, n=10):
    """Return first n lines from file. If n is None, return all lines."""
    lines = []
    with open(path) as f:
        for line in f if n is None else (f.readline() for _ in range(n)):
            if line:
                lines.append(line.strip())
    return lines

def head_list(data, n=10):
    """Return first n items from list. If n is None, return all items."""
    return data if n is None else data[:n]


def read_xml(path):
    """Read XML to string."""
    with open(path, 'r', encoding='utf-8') as f:
        xml_str = f.read()
        return xml_str


def save_csv(path, data, delimiter=','):
    """Save to delimited file. CSV default."""
    with open(path, 'w', newline='') as f:
        if not data:
            f.truncate()
            return
        fieldnames = data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        for item in data:
            writer.writerow(item)

def save_psv(path, data):
    """Save to PSV (Pipe Separated Values) file."""
    return save_csv(path, data, delimiter='|')

def save_json(path, data):
    """Save to JSON file."""
    with open(path, 'w') as f:
        if not data:
            f.truncate()
            return
        json.dump(data, f, indent=4)

def save_txt(path, data=None):
    """Save to TXT file."""
    with open(path, 'w') as f:
        if not data:
            f.truncate()
            return
        for line in data:
            f.write(line + '\n')

def save_txt_line(path, line=None):
    """Create or append line to TXT file. Truncate if line is None."""
    if line is None:
        with open(path, 'w', encoding='utf-8') as f:
            pass
        return
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


if __name__ == '__main__':
    # Tests for utils.
    def tests():
        print("tests")

    tests()
