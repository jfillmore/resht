import sys

from . import shell

def main():
    sys.exit(shell.Shell(sys.argv[1:]).last_rv)


if __name__ == '__main__':
    main()
