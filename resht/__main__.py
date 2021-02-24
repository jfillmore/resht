import sys
from . import shell
sys.exit(shell.Shell(sys.argv[1:]).last_rv)
