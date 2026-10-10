"""One bundled executable serves GUI, inference and model downloads."""
import sys


def main():
    if '--worker' in sys.argv:
        from .worker import main as run
    elif '--download' in sys.argv:
        from .downloads import main as run
    elif '--self-test' in sys.argv:
        from .selftest import main as run
    else:
        from .app import main as run
    run()


if __name__ == '__main__':
    main()
